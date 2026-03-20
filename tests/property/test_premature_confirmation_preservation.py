"""
Preservation property tests for premature session confirmation bugfix.

These tests capture baseline behaviors that MUST be preserved after the fix:
1. Sessions whose end time falls within the time window are correctly matched
   (tested with both times in the same reference frame to isolate the timezone bug)
2. Non-confirmation messages cause process_confirmation_response() to return False
3. format_confirmation_message() produces consistent output for all valid inputs
4. find_pending_confirmation_session_for_trainer() returns a session when one
   exists with pending_confirmation status

**EXPECTED OUTCOME ON UNFIXED CODE**: Tests PASS (confirms baseline behavior)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""

import os
import sys
import uuid
import re
import boto3
import pytest
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

def session_hour_strategy():
    """Generate session start hours in local time (business hours)."""
    return st.integers(min_value=6, max_value=22)


def duration_strategy():
    """Generate session durations in minutes (15-480 as per model constraints)."""
    return st.integers(min_value=15, max_value=480)


def window_offset_strategy():
    """
    Generate offsets in minutes within the 55-65 minute confirmation window.
    The handler checks for sessions that ended between 60-65 and 60 minutes ago.
    We use 55-65 to cover the full [now - 1h5m, now - 1h] window.
    """
    return st.integers(min_value=55, max_value=65)


def student_name_strategy():
    """Generate realistic student names."""
    return st.text(
        alphabet=st.characters(whitelist_categories=('L', 'Zs'), min_codepoint=65, max_codepoint=122),
        min_size=1,
        max_size=50,
    ).filter(lambda s: s.strip())


def non_confirmation_message_strategy():
    """
    Generate messages that are NOT confirmation keywords.
    Confirmation keywords: SIM, YES, S, NÃO, NAO, NO, N (case-insensitive).
    """
    confirmation_keywords = {
        'sim', 'yes', 's', 'não', 'nao', 'no', 'n',
        'SIM', 'YES', 'S', 'NÃO', 'NAO', 'NO', 'N',
        'Sim', 'Yes', 'Não', 'Nao', 'No',
    }
    return st.text(min_size=2, max_size=100).filter(
        lambda s: s.strip().upper() not in {k.upper() for k in confirmation_keywords}
        and len(s.strip()) > 0
    )


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
# Property 1: Sessions within the time window are matched
# (using consistent timezone — both times in the same reference frame)
# ---------------------------------------------------------------------------

class TestSessionsWithinWindowAreMatched:
    """
    Property: For all sessions where session_end falls within the time window
    [start_time, end_time] (using consistent timezone), query_sessions_for_confirmation()
    returns those sessions.

    We test with both the session time and the window in the SAME reference frame
    (local time) to isolate the timezone bug. This confirms the core matching logic
    works correctly when timezone is not a factor.

    **Validates: Requirements 3.1**
    """

    @given(
        session_hour=session_hour_strategy(),
        duration=duration_strategy(),
        window_offset_minutes=window_offset_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_sessions_in_window_are_matched_consistent_timezone(
        self, session_hour, duration, window_offset_minutes
    ):
        """
        Create a session at a known time. Calculate the time window such that
        session_end falls within [start_time, end_time], with both the session
        time and the window in the same reference frame (no timezone mismatch).

        This tests the core matching logic of query_sessions_for_confirmation()
        independent of the timezone bug.

        **Validates: Requirements 3.1**
        """
        base_date = datetime(2026, 3, 20)

        # Session in local time (as stored in production)
        session_datetime_local = base_date.replace(hour=session_hour, minute=0)
        session_end_local = session_datetime_local + timedelta(minutes=duration)

        # Ensure session_end doesn't overflow to next day in a problematic way
        assume(session_end_local.day == base_date.day)

        # Calculate "now" in the SAME reference frame (local time) such that
        # session_end is within the [now - 1h5m, now - 1h] window.
        # now_local = session_end_local + window_offset_minutes
        now_local = session_end_local + timedelta(minutes=window_offset_minutes)

        # The time window in local time (same frame as session_datetime)
        check_time_start = now_local - timedelta(hours=1, minutes=5)
        check_time_end = now_local - timedelta(hours=1)

        # Verify our setup: session_end should be in the window
        assume(check_time_start <= session_end_local <= check_time_end)

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            trainer_id = f"trainer-{uuid.uuid4().hex[:8]}"
            session = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_id,
                student_id="student-001",
                student_name="Maria",
                session_datetime=session_datetime_local,
                duration_minutes=duration,
                status="scheduled",
                confirmation_status="scheduled",
            )
            _insert_session(db_client, session)

            # query_sessions_for_confirmation() now expects UTC and converts
            # to local time internally (subtracts 3h). Pass UTC values so the
            # internal conversion produces the correct local-time window.
            utc_offset = timedelta(hours=3)
            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=check_time_start + utc_offset,
                end_time=check_time_end + utc_offset,
            )

            matched_ids = {s.session_id for s in results}

            assert session.session_id in matched_ids, (
                f"PRESERVATION FAILURE: Session {session.session_id} was NOT matched "
                f"even though session_end falls within the time window.\n"
                f"  session_datetime: {session_datetime_local.isoformat()}\n"
                f"  session_end: {session_end_local.isoformat()}\n"
                f"  window: [{check_time_start.isoformat()}, {check_time_end.isoformat()}]\n"
                f"  now_local: {now_local.isoformat()}"
            )


# ---------------------------------------------------------------------------
# Property 2: Non-confirmation messages return False
# ---------------------------------------------------------------------------

class TestNonConfirmationMessagesReturnFalse:
    """
    Property: For all non-confirmation messages, process_confirmation_response()
    returns False.

    This ensures regular trainer messages continue to be routed to the AI agent
    normally after the fix.

    **Validates: Requirements 3.2, 3.3**
    """

    @given(
        message=non_confirmation_message_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_non_confirmation_messages_return_false(self, message):
        """
        For any message that is NOT a confirmation keyword (Sim/Yes/S/Não/No/N),
        process_confirmation_response() should return False, meaning the message
        will be routed to the AI agent normally.

        **Validates: Requirements 3.2, 3.3**
        """
        trainer_phone = "+5511999990001"

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            mock_twilio = MagicMock()

            with patch('handlers.message_processor.db_client', db_client), \
                 patch('handlers.message_processor.twilio_client', mock_twilio):

                from handlers.message_processor import process_confirmation_response

                result = process_confirmation_response(
                    phone_number=trainer_phone,
                    message=message,
                )

            assert result is False, (
                f"PRESERVATION FAILURE: process_confirmation_response() returned True "
                f"for non-confirmation message '{message}'. This message should be "
                f"routed to the AI agent, not treated as a confirmation response."
            )


# ---------------------------------------------------------------------------
# Property 3: format_confirmation_message() produces consistent output
# ---------------------------------------------------------------------------

class TestFormatConfirmationMessageConsistency:
    """
    Property: For all valid (student_name, session_datetime, duration_minutes)
    inputs, format_confirmation_message() produces consistent, well-formed output.

    **Validates: Requirements 3.5**
    """

    @given(
        student_name=st.text(min_size=1, max_size=50).filter(lambda s: s.strip()),
        session_hour=st.integers(min_value=0, max_value=23),
        session_minute=st.integers(min_value=0, max_value=59),
        duration=duration_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_format_confirmation_message_consistent_output(
        self, student_name, session_hour, session_minute, duration
    ):
        """
        For any valid inputs, format_confirmation_message() should:
        - Return a non-empty string
        - Contain the student name
        - Contain the duration
        - Contain "SIM ou NÃO" prompt
        - Contain the 📋 emoji header

        **Validates: Requirements 3.5**
        """
        session_datetime = datetime(2026, 3, 20, session_hour, session_minute)

        result = format_confirmation_message(
            student_name=student_name,
            session_datetime=session_datetime,
            duration_minutes=duration,
        )

        # Basic structure checks
        assert isinstance(result, str), "Result should be a string"
        assert len(result) > 0, "Result should not be empty"
        assert student_name in result, (
            f"Student name '{student_name}' not found in message: {result}"
        )
        assert str(duration) in result, (
            f"Duration '{duration}' not found in message: {result}"
        )
        assert "📋" in result, "Message should contain 📋 emoji header"
        assert "SIM" in result or "Sim" in result.upper(), (
            "Message should contain SIM/NÃO prompt"
        )


# ---------------------------------------------------------------------------
# Property 4: find_pending_confirmation_session_for_trainer() returns session
# ---------------------------------------------------------------------------

class TestFindPendingConfirmationSession:
    """
    Property: For all trainers with exactly one pending_confirmation session,
    find_pending_confirmation_session_for_trainer() returns that session.

    **Validates: Requirements 3.4, 3.6**
    """

    @given(
        session_hour=session_hour_strategy(),
        duration=duration_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_find_pending_session_returns_existing_session(
        self, session_hour, duration
    ):
        """
        Create a trainer with exactly one session in pending_confirmation status.
        Verify that find_pending_confirmation_session_for_trainer() returns it.

        **Validates: Requirements 3.4, 3.6**
        """
        trainer_id = f"trainer-{uuid.uuid4().hex[:8]}"

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            session_datetime = datetime(2026, 3, 20, session_hour, 0)
            session = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_id,
                student_id="student-001",
                student_name="Carlos",
                session_datetime=session_datetime,
                duration_minutes=duration,
                status="scheduled",
                confirmation_status="pending_confirmation",
                confirmation_requested_at=datetime(2026, 3, 20, session_hour + 1, 5)
                if session_hour < 23 else datetime(2026, 3, 21, 0, 5),
            )
            _insert_session(db_client, session)

            # Mock the module-level db_client in message_processor
            with patch('handlers.message_processor.db_client', db_client):
                from handlers.message_processor import find_pending_confirmation_session_for_trainer

                result = find_pending_confirmation_session_for_trainer(
                    trainer_id=trainer_id,
                )

            assert result is not None, (
                f"PRESERVATION FAILURE: find_pending_confirmation_session_for_trainer() "
                f"returned None for trainer {trainer_id} even though a session with "
                f"confirmation_status='pending_confirmation' exists.\n"
                f"  session_id: {session.session_id}\n"
                f"  session_datetime: {session_datetime.isoformat()}"
            )
            assert result.get('session_id') == session.session_id, (
                f"PRESERVATION FAILURE: Returned wrong session. "
                f"Expected {session.session_id}, got {result.get('session_id')}"
            )
