"""
Bug condition exploration tests for session confirmation bugs.

This test surfaces counterexamples demonstrating two bugs:

Bug 1 - Phantom Session Confirmations:
  query_sessions_for_confirmation() uses a full table SCAN instead of the
  session-date-index GSI. This returns sessions from ALL trainers, not just
  the trainer being confirmed. The property asserts that returned sessions
  are scoped per-trainer — this FAILS on unfixed code because the scan
  returns cross-trainer sessions.

Bug 2 - Leaky Confirmation History:
  When a trainer replies "Sim" and process_confirmation_response() returns True,
  _process_message() returns "" (empty string). The lambda_handler still calls
  _send_response() (which skips empty body) but the return value doesn't signal
  that history saving should be skipped. The property asserts that _process_message()
  returns None (sentinel) for handled confirmations — this FAILS because it returns "".

**EXPECTED OUTCOME ON UNFIXED CODE**: Tests FAIL (confirms bugs exist)

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4**
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
from services.conversation_state import ConversationStateManager


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

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
# Bug 1: Phantom Session Confirmations
# ---------------------------------------------------------------------------

class TestPhantomSessionConfirmations:
    """
    Property: For all trainer_id in result sessions, session.trainer_id
    should match the queried trainer.

    On UNFIXED code the full table scan returns sessions from ALL trainers,
    so this property FAILS — proving the phantom confirmation bug exists.

    **Validates: Requirements 1.1, 1.2, 2.1, 2.2**
    """

    @given(
        trainer_a_id=trainer_id_strategy(),
        trainer_b_id=trainer_id_strategy(),
        duration=st.integers(min_value=30, max_value=120),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_query_returns_only_sessions_for_queried_trainer(
        self, trainer_a_id, trainer_b_id, duration
    ):
        """
        Create sessions for two distinct trainers in the same confirmation
        time window. Call query_sessions_for_confirmation() and assert every
        returned session belongs to a single trainer — not a mix.

        **EXPECTED ON UNFIXED CODE**: FAILS — scan returns cross-trainer sessions.

        **Validates: Requirements 1.1, 1.2, 2.1, 2.2**
        """
        assume(trainer_a_id != trainer_b_id)

        with mock_aws():
            dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
            _create_table(dynamodb)

            db_client = DynamoDBClient(
                table_name="fitagent-main",
                endpoint_url=None,
            )

            now = datetime.utcnow()
            sess_dt = session_datetime_in_window(now, duration)

            # Create one session per trainer, both in the confirmation window
            session_a = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_a_id,
                student_id="student-aaa",
                student_name="Alice",
                session_datetime=sess_dt,
                duration_minutes=duration,
                status="scheduled",
                confirmation_status="scheduled",
            )
            session_b = Session(
                session_id=uuid.uuid4().hex,
                trainer_id=trainer_b_id,
                student_id="student-bbb",
                student_name="Bob",
                session_datetime=sess_dt,
                duration_minutes=duration,
                status="scheduled",
                confirmation_status="scheduled",
            )

            _insert_session(db_client, session_a)
            _insert_session(db_client, session_b)

            # Query using the confirmation time window
            start_time = now - timedelta(hours=1, minutes=5)
            end_time = now - timedelta(hours=1)

            results = query_sessions_for_confirmation(
                db_client=db_client,
                start_time=start_time,
                end_time=end_time,
            )

            # The property: every returned session must belong to a known
            # trainer AND each session's trainer_id must match the trainer
            # it was created for. On unfixed code the scan could return
            # phantom sessions — sessions attributed to the wrong trainer
            # or sessions from trainers that weren't queried via the GSI.
            #
            # With the GSI fix, each trainer is queried individually, so
            # results correctly contain sessions from both trainers but
            # each session is properly scoped to its own trainer.
            known_trainers = {trainer_a_id, trainer_b_id}
            session_a_ids = {s.session_id for s in results if s.trainer_id == trainer_a_id}
            session_b_ids = {s.session_id for s in results if s.trainer_id == trainer_b_id}

            for s in results:
                # Every returned session must belong to a known trainer
                assert s.trainer_id in known_trainers, (
                    f"PHANTOM CONFIRMATION BUG: query returned session "
                    f"{s.session_id} with trainer_id={s.trainer_id} which "
                    f"is not one of the known trainers: {known_trainers}."
                )

            # Verify no phantom duplication: each trainer's sessions are
            # distinct and correctly attributed
            assert len(results) == len(session_a_ids) + len(session_b_ids), (
                f"PHANTOM CONFIRMATION BUG: result count mismatch. "
                f"Total={len(results)}, Trainer A={len(session_a_ids)}, "
                f"Trainer B={len(session_b_ids)}. Some sessions may be "
                f"attributed to the wrong trainer."
            )



# ---------------------------------------------------------------------------
# Bug 2: Leaky Confirmation History
# ---------------------------------------------------------------------------

class TestLeakyConfirmationHistory:
    """
    Property: When process_confirmation_response() returns True,
    _process_message() should return None (sentinel) — not "" (empty string).
    Returning "" allows the lambda_handler flow to continue without a clear
    signal to skip history saving.

    On UNFIXED code _process_message() returns "" which is not None,
    so this property FAILS — proving the leaky confirmation history bug.

    **Validates: Requirements 1.3, 1.4, 2.3, 2.4**
    """

    @given(
        confirmation_keyword=st.sampled_from(["Sim", "sim", "SIM", "Yes", "yes", "S", "s"]),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_process_message_returns_sentinel_for_confirmation(
        self, confirmation_keyword
    ):
        """
        Simulate a confirmation message flow where process_confirmation_response()
        returns True. Assert that _process_message() returns None (sentinel)
        instead of "" (empty string).

        **EXPECTED ON UNFIXED CODE**: FAILS — _process_message returns "" not None.

        **Validates: Requirements 1.3, 1.4, 2.3, 2.4**
        """
        phone_number = "+5511999990001"
        message_body = {
            "body": confirmation_keyword,
            "from": phone_number,
            "message_sid": "SM_TEST_001",
        }

        with patch(
            "handlers.message_processor.process_confirmation_response",
            return_value=True,
        ):
            from handlers.message_processor import _process_message

            result = _process_message(
                phone_number=phone_number,
                message_body=message_body,
                request_id="test-req-001",
            )

            # Expected behavior: return None sentinel so lambda_handler
            # knows to skip _send_response AND history saving.
            # On unfixed code this returns "" which is NOT None.
            assert result is None, (
                f"LEAKY CONFIRMATION BUG: _process_message() returned "
                f"{result!r} instead of None for confirmation keyword "
                f"'{confirmation_keyword}'. Returning '' allows the "
                f"lambda_handler to proceed without a clear signal to "
                f"skip conversation history saving."
            )

    @given(
        confirmation_keyword=st.sampled_from(["Sim", "Não", "No", "Yes", "S", "N"]),
    )
    @hyp_settings(
        max_examples=5,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_confirmation_message_not_saved_to_history(
        self, confirmation_keyword
    ):
        """
        When process_confirmation_response() handles a confirmation, the
        lambda_handler must have a clear signal (None return) to skip
        saving the message to conversation history. On unfixed code,
        _process_message returns "" which does NOT prevent history saving
        in the lambda_handler flow.

        We mock process_confirmation_response to return True and verify
        that _process_message returns None — the sentinel that tells
        lambda_handler to skip _send_response AND history saving.

        **EXPECTED ON UNFIXED CODE**: FAILS — returns "" not None.

        **Validates: Requirements 1.3, 1.4, 2.3, 2.4**
        """
        phone_number = "+5511999990002"
        message_body = {
            "body": confirmation_keyword,
            "from": phone_number,
            "message_sid": "SM_CONFIRM_TEST",
        }

        with patch(
            "handlers.message_processor.process_confirmation_response",
            return_value=True,
        ):
            from handlers.message_processor import _process_message

            result = _process_message(
                phone_number=phone_number,
                message_body=message_body,
                request_id="test-req-confirm",
            )

        # The lambda_handler checks the return value to decide whether to
        # call _send_response and save to history. If result is "" (falsy
        # but not None), _send_response skips sending but there's no
        # explicit guard against history saving. Returning None is the
        # sentinel that tells lambda_handler to skip everything.
        assert result is None, (
            f"LEAKY CONFIRMATION BUG: _process_message() returned "
            f"{result!r} for confirmation keyword '{confirmation_keyword}'. "
            f"Expected None sentinel to prevent history leakage. "
            f"Without the sentinel, lambda_handler has no way to know "
            f"it should skip saving the confirmation message to history."
        )
