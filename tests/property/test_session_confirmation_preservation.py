"""
Preservation property tests for session confirmation fix.

These tests verify baseline behaviors that MUST be preserved after the fix:
- Non-confirmation messages are not intercepted by process_confirmation_response()
- format_confirmation_message() produces consistent output for given inputs
- Single-trainer session queries return correct results (the bug is cross-trainer only)

**EXPECTED OUTCOME ON UNFIXED CODE**: Tests PASS (confirms baseline behavior to preserve)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import os
import sys
import uuid
import pytest
import boto3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from moto import mock_aws
from hypothesis import given, settings as hyp_settings, assume, HealthCheck
from hypothesis import strategies as st

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from models.entities import Session
from models.dynamodb_client import DynamoDBClient
from handlers.session_confirmation import (
    query_sessions_for_confirmation,
    format_confirmation_message,
)


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Confirmation keywords that process_confirmation_response() recognizes
CONFIRMATION_KEYWORDS = {'SIM', 'YES', 'S', 'NÃO', 'NAO', 'NO', 'N'}


def non_confirmation_message_strategy():
    """Generate messages that are NOT confirmation keywords after strip().upper()."""
    return st.text(min_size=1, max_size=100).filter(
        lambda s: s.strip().upper() not in CONFIRMATION_KEYWORDS
    )


def student_name_strategy():
    """Generate realistic student names."""
    return st.text(
        alphabet=st.sampled_from(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ àáãâéêíóôõúç"
        ),
        min_size=2,
        max_size=40,
    ).filter(lambda s: len(s.strip()) >= 2)


def duration_strategy():
    """Generate valid session durations (15-480 minutes per model constraint)."""
    return st.integers(min_value=15, max_value=480)


def session_datetime_strategy():
    """Generate session datetimes within a reasonable range."""
    return st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31),
    )


def trainer_id_strategy():
    """Generate distinct trainer IDs."""
    return st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=8,
        max_size=12,
    ).map(lambda s: f"trainer-{s}")


def session_datetime_in_window(base_time: datetime, duration_minutes: int):
    """
    Return a session_datetime such that session_end falls within the
    confirmation time window [base_time - 1h5m, base_time - 1h].

    session_end = session_datetime + duration_minutes
    We need: base_time - 1h5m <= session_end <= base_time - 1h
    So: base_time - 1h5m - duration <= session_datetime <= base_time - 1h - duration
    """
    window_end = base_time - timedelta(hours=1)
    window_start = base_time - timedelta(hours=1, minutes=5)
    latest_start = window_end - timedelta(minutes=duration_minutes)
    earliest_start = window_start - timedelta(minutes=duration_minutes)
    return earliest_start + (latest_start - earliest_start) / 2  # midpoint


# ---------------------------------------------------------------------------
# Helper: create mocked DynamoDB table with GSIs
# ---------------------------------------------------------------------------

def _create_table(dynamodb_resource):
    """Create the fitagent-main table with all required GSIs."""
    table = dynamodb_resource.create_table(
        TableName="fitagent-main",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "phone_number", "AttributeType": "S"},
            {"AttributeName": "entity_type", "AttributeType": "S"},
            {"AttributeName": "trainer_id", "AttributeType": "S"},
            {"AttributeName": "session_datetime", "AttributeType": "S"},
            {"AttributeName": "payment_status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "phone-number-index",
                "KeySchema": [
                    {"AttributeName": "phone_number", "KeyType": "HASH"},
                    {"AttributeName": "entity_type", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
            {
                "IndexName": "session-date-index",
                "KeySchema": [
                    {"AttributeName": "trainer_id", "KeyType": "HASH"},
                    {"AttributeName": "session_datetime", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
            {
                "IndexName": "payment-status-index",
                "KeySchema": [
                    {"AttributeName": "trainer_id", "KeyType": "HASH"},
                    {"AttributeName": "payment_status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5,
                },
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def _insert_session(db_client: DynamoDBClient, session: Session):
    """Insert a Session entity into DynamoDB."""
    db_client.put_item(session.to_dynamodb())


# ---------------------------------------------------------------------------
# Property 2a: Non-confirmation messages return False
# ---------------------------------------------------------------------------

class TestNonConfirmationMessageRouting:
    """
    Property: For all messages that are NOT confirmation keywords (or where
    no pending confirmation exists), process_confirmation_response() returns
    False and the message is routed normally.

    This preserves requirement 3.1 (regular messages routed to AI agent)
    and 3.2 ("Sim"/"Não" without pending confirmation treated as regular).

    **Validates: Requirements 3.1, 3.2**
    """

    @given(message=non_confirmation_message_strategy())
    @hyp_settings(
        max_examples=10,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_non_confirmation_messages_return_false(self, message):
        """
        For any message that is not a confirmation keyword,
        process_confirmation_response() returns False regardless of state.

        **Validates: Requirements 3.1, 3.2**
        """
        phone_number = "+5511999990099"

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            # Patch the module-level db_client used by process_confirmation_response
            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            with patch("handlers.message_processor.db_client", db_client):
                from handlers.message_processor import process_confirmation_response

                result = process_confirmation_response(phone_number, message)

            assert result is False, (
                f"process_confirmation_response() returned True for non-confirmation "
                f"message {message!r}. Expected False so message routes normally."
            )

    @given(
        keyword=st.sampled_from(["Sim", "sim", "SIM", "Yes", "yes", "S", "s",
                                  "Não", "não", "NÃO", "Nao", "nao", "NAO",
                                  "No", "no", "NO", "N", "n"]),
    )
    @hyp_settings(
        max_examples=10,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_confirmation_keywords_without_pending_return_false(self, keyword):
        """
        When a confirmation keyword is sent but no trainer/pending session
        exists for that phone number, process_confirmation_response() returns
        False — the message is treated as a regular message.

        **Validates: Requirements 3.1, 3.2**
        """
        phone_number = "+5511888880001"

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            with patch("handlers.message_processor.db_client", db_client):
                from handlers.message_processor import process_confirmation_response

                result = process_confirmation_response(phone_number, keyword)

            assert result is False, (
                f"process_confirmation_response() returned True for keyword "
                f"{keyword!r} with no trainer/pending session. Expected False."
            )


# ---------------------------------------------------------------------------
# Property 2b: format_confirmation_message() consistency
# ---------------------------------------------------------------------------

class TestFormatConfirmationMessageConsistency:
    """
    Property: For all valid (student_name, session_datetime, duration_minutes),
    format_confirmation_message() produces output containing the student name,
    formatted date, and formatted time.

    **Validates: Requirements 3.3, 3.5**
    """

    @given(
        student_name=student_name_strategy(),
        session_dt=session_datetime_strategy(),
        duration=duration_strategy(),
    )
    @hyp_settings(
        max_examples=10,
        deadline=10000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_format_contains_expected_components(
        self, student_name, session_dt, duration
    ):
        """
        The formatted message must contain:
        - The student name
        - The date in dd/mm/yyyy format
        - The time in HH:MM format
        - The duration in minutes
        - "SIM" and "NÃO" response instructions

        **Validates: Requirements 3.3, 3.5**
        """
        result = format_confirmation_message(
            student_name=student_name,
            session_datetime=session_dt,
            duration_minutes=duration,
        )

        expected_date = session_dt.strftime("%d/%m/%Y")
        expected_time = session_dt.strftime("%H:%M")

        assert student_name in result, (
            f"Student name {student_name!r} not found in message: {result!r}"
        )
        assert expected_date in result, (
            f"Date {expected_date!r} not found in message: {result!r}"
        )
        assert expected_time in result, (
            f"Time {expected_time!r} not found in message: {result!r}"
        )
        assert str(duration) in result, (
            f"Duration {duration} not found in message: {result!r}"
        )
        assert "SIM" in result or "Sim" in result or "sim" in result, (
            f"Confirmation instruction 'SIM' not found in message: {result!r}"
        )

    @given(
        student_name=student_name_strategy(),
        session_dt=session_datetime_strategy(),
        duration=duration_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=10000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_format_is_deterministic(self, student_name, session_dt, duration):
        """
        Calling format_confirmation_message() twice with the same inputs
        produces identical output.

        **Validates: Requirements 3.3, 3.5**
        """
        result1 = format_confirmation_message(
            student_name=student_name,
            session_datetime=session_dt,
            duration_minutes=duration,
        )
        result2 = format_confirmation_message(
            student_name=student_name,
            session_datetime=session_dt,
            duration_minutes=duration,
        )

        assert result1 == result2, (
            f"format_confirmation_message() is not deterministic.\n"
            f"Call 1: {result1!r}\nCall 2: {result2!r}"
        )


# ---------------------------------------------------------------------------
# Property 2c: Single-trainer session query correctness
# ---------------------------------------------------------------------------

class TestSingleTrainerSessionQuery:
    """
    Property: For all single-trainer session sets with confirmation_status =
    scheduled, the query returns those sessions correctly. The bug is
    cross-trainer (scan returns ALL trainers), but single-trainer behavior
    is correct and must be preserved.

    **Validates: Requirements 3.3, 3.4, 3.5**
    """

    @given(
        trainer_id=trainer_id_strategy(),
        num_sessions=st.integers(min_value=1, max_value=5),
        duration=st.integers(min_value=30, max_value=120),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_single_trainer_sessions_returned_correctly(
        self, trainer_id, num_sessions, duration
    ):
        """
        Create N sessions for a single trainer in the confirmation window.
        All sessions with confirmation_status=scheduled and status!=cancelled
        should be returned by query_sessions_for_confirmation().

        **Validates: Requirements 3.3, 3.4, 3.5**
        """
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            now = datetime.utcnow()
            sess_dt = session_datetime_in_window(now, duration)

            expected_sessions = []
            for i in range(num_sessions):
                session = Session(
                    session_id=uuid.uuid4().hex,
                    trainer_id=trainer_id,
                    student_id=f"student-{i:03d}",
                    student_name=f"Student {i}",
                    session_datetime=sess_dt,
                    duration_minutes=duration,
                    status="scheduled",
                    confirmation_status="scheduled",
                )
                _insert_session(db_client, session)
                expected_sessions.append(session.session_id)

            start_time = now - timedelta(hours=1, minutes=5)
            end_time = now - timedelta(hours=1)

            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=start_time,
                end_time=end_time,
            )

            result_ids = {s.session_id for s in results}
            expected_ids = set(expected_sessions)

            assert expected_ids.issubset(result_ids), (
                f"Not all single-trainer sessions were returned.\n"
                f"Expected: {expected_ids}\nGot: {result_ids}\n"
                f"Missing: {expected_ids - result_ids}"
            )

            # All returned sessions should belong to our trainer
            for s in results:
                if s.session_id in expected_ids:
                    assert s.trainer_id == trainer_id, (
                        f"Session {s.session_id} has trainer_id={s.trainer_id}, "
                        f"expected {trainer_id}"
                    )

    @given(
        trainer_id=trainer_id_strategy(),
        duration=st.integers(min_value=30, max_value=120),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_cancelled_sessions_excluded(self, trainer_id, duration):
        """
        Sessions with status=cancelled should NOT be returned even if
        confirmation_status=scheduled.

        **Validates: Requirements 3.3, 3.5**
        """
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            now = datetime.utcnow()
            sess_dt = session_datetime_in_window(now, duration)

            # Insert a cancelled session
            cancelled_session = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_id,
                student_id="student-cancelled",
                student_name="Cancelled Student",
                session_datetime=sess_dt,
                duration_minutes=duration,
                status="cancelled",
                confirmation_status="scheduled",
            )
            _insert_session(db_client, cancelled_session)

            # Insert a valid session
            valid_session = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_id,
                student_id="student-valid",
                student_name="Valid Student",
                session_datetime=sess_dt,
                duration_minutes=duration,
                status="scheduled",
                confirmation_status="scheduled",
            )
            _insert_session(db_client, valid_session)

            start_time = now - timedelta(hours=1, minutes=5)
            end_time = now - timedelta(hours=1)

            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=start_time,
                end_time=end_time,
            )

            result_ids = {s.session_id for s in results}

            assert cancelled_session.session_id not in result_ids, (
                f"Cancelled session {cancelled_session.session_id} was returned "
                f"by query_sessions_for_confirmation(). It should be excluded."
            )
            assert valid_session.session_id in result_ids, (
                f"Valid session {valid_session.session_id} was NOT returned."
            )

    def test_empty_table_returns_empty(self):
        """
        When no sessions exist, query returns empty list and handler
        would return {sent: 0, failed: 0}.

        **Validates: Requirements 3.5**
        """
        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            now = datetime.utcnow()
            start_time = now - timedelta(hours=1, minutes=5)
            end_time = now - timedelta(hours=1)

            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=start_time,
                end_time=end_time,
            )

            assert results == [], (
                f"Expected empty list for empty table, got {len(results)} sessions."
            )
