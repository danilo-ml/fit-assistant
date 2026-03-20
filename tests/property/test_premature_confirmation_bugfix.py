"""
Bug condition exploration tests for premature session confirmation bugs.

This test surfaces counterexamples demonstrating two bugs:

Bug 1 - Premature Confirmation (Timezone Mismatch):
  lambda_handler() in session_confirmation.py uses datetime.utcnow() to calculate
  the confirmation time window, but session_datetime values are stored as naive
  datetimes in Brazil local time (UTC-3). This 3-hour offset causes the system to
  match sessions that haven't even started yet. For example, at 08:00 local (11:00
  UTC), a session at 09:00 local with 60min duration has session_end = 10:00 (naive).
  The UTC window [09:55, 10:00] matches 10:00, so a premature confirmation is sent
  before the session has even started.

Bug 2 - Confirmation Response Fallthrough:
  When a premature confirmation is sent and the trainer replies "Sim", the
  process_confirmation_response() function may fail to find the pending session
  because find_pending_confirmation_session_for_trainer() sorts ascending and
  returns the oldest session. If the lookup fails, the "Sim" falls through to
  the AI agent.

**EXPECTED OUTCOME ON UNFIXED CODE**: Tests FAIL (confirms bugs exist)
**CRITICAL**: Do NOT fix the code when tests fail - failure proves the bugs exist.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3**
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
from handlers.session_confirmation import query_sessions_for_confirmation


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def utc_offset_strategy():
    """Generate UTC offsets representing Brazil timezone (UTC-3)."""
    return st.just(3)


def session_hour_strategy():
    """Generate session start hours in local time (business hours)."""
    return st.integers(min_value=6, max_value=22)


def duration_strategy():
    """Generate session durations in minutes."""
    return st.integers(min_value=30, max_value=120)


def handler_run_offset_strategy():
    """
    Generate the offset in minutes BEFORE the session starts (local time)
    when the handler runs. This represents the handler running BEFORE the
    session has ended, which should NOT trigger a confirmation.

    We pick offsets such that now_local is before session_end_local,
    meaning the session hasn't ended yet in local time.
    """
    return st.integers(min_value=10, max_value=150)


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
# Bug 1: Premature Confirmation (Timezone Mismatch)
# ---------------------------------------------------------------------------

class TestPrematureConfirmationTimezoneMismatch:
    """
    Property: For all sessions where session_end_local > now_local (session
    hasn't ended yet in local time), the session should NOT appear in the
    confirmation results.

    On UNFIXED code, datetime.utcnow() is used to calculate the time window
    but compared against naive local-time session_datetime values. The 3-hour
    offset (UTC vs UTC-3) causes sessions that haven't started or ended yet
    in local time to be incorrectly matched.

    **EXPECTED ON UNFIXED CODE**: FAILS — sessions are matched prematurely.

    **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3**
    """

    @given(
        session_hour=session_hour_strategy(),
        duration=duration_strategy(),
        minutes_before_end=handler_run_offset_strategy(),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_future_sessions_not_matched_for_confirmation(
        self, session_hour, duration, minutes_before_end
    ):
        """
        Create a session at a known local time. Set the handler's "now" to a
        UTC time such that now_local is BEFORE session_end_local (the session
        hasn't ended yet in local time). Assert the session is NOT matched.

        The bug: the code uses datetime.utcnow() directly, so the UTC time
        window is compared against local-time session_datetime. With a 3-hour
        offset, sessions that haven't ended in local time can be matched.

        Example from the real incident:
        - Session at 09:00 local, 60min duration → ends at 10:00 local
        - Handler runs at 08:00 local (11:00 UTC)
        - UTC window: [09:55, 10:00] — matches session_end 10:00 (naive local)
        - But the session hasn't even STARTED yet at 08:00 local!

        **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3**
        """
        # Use a fixed date to avoid edge cases
        base_date = datetime(2026, 3, 20)
        utc_offset_hours = 3  # Brazil is UTC-3

        # Session stored in local time (naive datetime, as in production)
        session_datetime_local = base_date.replace(hour=session_hour, minute=0)
        session_end_local = session_datetime_local + timedelta(minutes=duration)

        # Handler runs at a time when the session hasn't ended yet in local time
        # now_local = session_end_local - minutes_before_end
        now_local = session_end_local - timedelta(minutes=minutes_before_end)

        # Ensure now_local is actually before session_end_local
        assume(now_local < session_end_local)
        # Ensure now_local is a reasonable time (not negative day)
        assume(now_local.day == base_date.day or now_local.day == base_date.day - 1)

        # The BUGGY code uses datetime.utcnow(), so now_utc = now_local + 3h
        now_utc = now_local + timedelta(hours=utc_offset_hours)

        # The buggy code calculates the time window using UTC:
        check_time_start = now_utc - timedelta(hours=1, minutes=5)
        check_time_end = now_utc - timedelta(hours=1)

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

            # Call query_sessions_for_confirmation with the UTC-derived window
            # (this is what the buggy lambda_handler does)
            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=check_time_start,
                end_time=check_time_end,
            )

            matched_ids = {s.session_id for s in results}

            # PROPERTY: session hasn't ended in local time, so it should NOT
            # be in the confirmation results
            assert session.session_id not in matched_ids, (
                f"PREMATURE CONFIRMATION BUG (Timezone Mismatch): "
                f"Session {session.session_id} was matched for confirmation "
                f"but hasn't ended yet in local time!\n"
                f"  session_datetime (local): {session_datetime_local.isoformat()}\n"
                f"  session_end (local): {session_end_local.isoformat()}\n"
                f"  now (local): {now_local.isoformat()}\n"
                f"  now (UTC): {now_utc.isoformat()}\n"
                f"  UTC window: [{check_time_start.isoformat()}, "
                f"{check_time_end.isoformat()}]\n"
                f"  The code compared UTC window against local-time "
                f"session_datetime, causing a 3-hour offset mismatch."
            )


# ---------------------------------------------------------------------------
# Bug 2: Confirmation Response Fallthrough
# ---------------------------------------------------------------------------

class TestConfirmationResponseFallthrough:
    """
    Property: When a trainer replies "Sim" and a session with
    confirmation_status='pending_confirmation' exists for that trainer,
    process_confirmation_response() should return True.

    On UNFIXED code, if the premature confirmation was sent and the trainer
    replies, the lookup may fail (returning False), causing the "Sim" to
    fall through to the AI agent.

    **Validates: Requirements 1.3, 1.4, 2.1, 2.2, 2.3**
    """

    @given(
        confirmation_keyword=st.sampled_from([
            "Sim", "sim", "SIM", "Yes", "yes", "S", "s",
            "Não", "não", "NÃO", "No", "no", "N", "n",
        ]),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_confirmation_response_finds_pending_session(
        self, confirmation_keyword
    ):
        """
        Create a session with confirmation_status='pending_confirmation'
        (simulating a premature confirmation was sent). Simulate the trainer
        replying with a confirmation keyword. Verify that
        process_confirmation_response() returns True (finds the session).

        If it returns False, the "Sim"/"Não" falls through to the AI agent,
        which is the Bug 2 behavior.

        **Validates: Requirements 1.3, 1.4, 2.1, 2.2, 2.3**
        """
        trainer_id = f"trainer-{uuid.uuid4().hex[:8]}"
        trainer_phone = "+5511999990099"

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            # Create a session with pending_confirmation status
            session = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_id,
                student_id="student-001",
                student_name="Carlos",
                session_datetime=datetime(2026, 3, 20, 9, 0),
                duration_minutes=60,
                status="scheduled",
                confirmation_status="pending_confirmation",
                confirmation_requested_at=datetime(2026, 3, 20, 8, 0),
            )
            _insert_session(db_client, session)

            # Create trainer metadata (needed for phone lookup)
            db_client.put_item({
                'PK': f'TRAINER#{trainer_id}',
                'SK': 'METADATA',
                'entity_type': 'TRAINER',
                'trainer_id': trainer_id,
                'phone_number': trainer_phone,
                'name': 'Test Trainer',
            })

            # Mock the module-level db_client and twilio_client in message_processor
            mock_twilio = MagicMock()

            with patch('handlers.message_processor.db_client', db_client), \
                 patch('handlers.message_processor.twilio_client', mock_twilio):

                from handlers.message_processor import process_confirmation_response

                result = process_confirmation_response(
                    phone_number=trainer_phone,
                    message=confirmation_keyword,
                )

            # PROPERTY: With a pending_confirmation session existing for this
            # trainer, the function should find it and return True.
            # If it returns False, the confirmation keyword falls through
            # to the AI agent (Bug 2).
            assert result is True, (
                f"CONFIRMATION FALLTHROUGH BUG: "
                f"process_confirmation_response() returned False for "
                f"keyword '{confirmation_keyword}' even though a session "
                f"with confirmation_status='pending_confirmation' exists "
                f"for trainer {trainer_id}.\n"
                f"  This means the trainer's '{confirmation_keyword}' reply "
                f"would fall through to the Strands AI agent instead of "
                f"being processed as a confirmation response."
            )
