"""Unit tests for DashboardMetricsService."""

from unittest.mock import MagicMock, patch
from decimal import Decimal

import pytest

from src.models.dashboard_models import (
    DashboardResponse,
    GrowthMetrics,
    PaymentMetrics,
    SessionMetrics,
    UserMetrics,
)
from src.services.dashboard_metrics import DashboardMetricsService


# ---------------------------------------------------------------------------
# Helpers to build fake DynamoDB scan responses
# ---------------------------------------------------------------------------

def _make_trainer(trainer_id, created_at="2024-01-05T10:00:00"):
    return {
        "PK": f"TRAINER#{trainer_id}",
        "SK": "METADATA",
        "entity_type": "TRAINER",
        "trainer_id": trainer_id,
        "created_at": created_at,
    }


def _make_student(student_id, created_at="2024-01-05T10:00:00"):
    return {
        "PK": f"STUDENT#{student_id}",
        "SK": "METADATA",
        "entity_type": "STUDENT",
        "student_id": student_id,
        "created_at": created_at,
    }


def _make_link(trainer_id, student_id, status="active"):
    return {
        "PK": f"TRAINER#{trainer_id}",
        "SK": f"STUDENT#{student_id}",
        "entity_type": "TRAINER_STUDENT_LINK",
        "trainer_id": trainer_id,
        "student_id": student_id,
        "status": status,
    }


def _make_session(trainer_id, student_id, session_datetime, status="scheduled"):
    return {
        "PK": f"TRAINER#{trainer_id}",
        "SK": f"SESSION#sess1",
        "entity_type": "SESSION",
        "trainer_id": trainer_id,
        "student_id": student_id,
        "session_datetime": session_datetime,
        "status": status,
    }


def _make_payment(trainer_id, student_id, amount, payment_status, created_at):
    return {
        "PK": f"TRAINER#{trainer_id}",
        "SK": "PAYMENT#pay1",
        "entity_type": "PAYMENT",
        "trainer_id": trainer_id,
        "student_id": student_id,
        "amount": Decimal(str(amount)),
        "payment_status": payment_status,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# Mock DynamoDB table helper
# ---------------------------------------------------------------------------

def _build_service_with_items(items):
    """Build a DashboardMetricsService backed by a mock table containing *items*."""
    mock_db = MagicMock()

    def fake_scan(**kwargs):
        filter_expr = kwargs.get("FilterExpression")
        # We can't evaluate boto3 ConditionExpression objects directly,
        # so we store all items and let the service filter via Attr.
        # Instead, we use moto in integration tests. For unit tests we
        # simulate by returning all items and relying on the service's
        # own filtering.  However, the service delegates filtering to
        # DynamoDB.  So we need a smarter mock.
        #
        # Approach: return all items (no pagination) and let the caller
        # rely on the FilterExpression being correct.  We test correctness
        # via integration tests; here we verify the *logic* given data.
        return {"Items": items}

    mock_db.table.scan.side_effect = fake_scan
    return DashboardMetricsService(mock_db)


def _build_service_with_scan_results(scan_results_by_call):
    """Build service where successive scan() calls return different results."""
    mock_db = MagicMock()
    call_idx = {"i": 0}

    def fake_scan(**kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        if idx < len(scan_results_by_call):
            return {"Items": scan_results_by_call[idx]}
        return {"Items": []}

    mock_db.table.scan.side_effect = fake_scan
    return DashboardMetricsService(mock_db)


# ---------------------------------------------------------------------------
# Tests: get_all_metrics
# ---------------------------------------------------------------------------

class TestGetAllMetrics:
    def test_returns_dashboard_response(self):
        service = _build_service_with_items([])
        result = service.get_all_metrics("2024-01-01", "2024-01-31")
        assert isinstance(result, DashboardResponse)
        assert result.status == "ok"
        assert result.errors == []
        assert result.period.start_date == "2024-01-01"
        assert result.period.end_date == "2024-01-31"

    def test_partial_on_section_failure(self):
        service = _build_service_with_items([])
        # Make get_user_metrics raise
        with patch.object(service, "get_user_metrics", side_effect=RuntimeError("boom")):
            result = service.get_all_metrics("2024-01-01", "2024-01-31")
        assert result.status == "partial"
        assert "user_metrics" in result.errors
        assert result.user_metrics is None
        # Other sections should still be present
        assert result.session_metrics is not None

    def test_multiple_section_failures(self):
        service = _build_service_with_items([])
        with patch.object(service, "get_user_metrics", side_effect=RuntimeError):
            with patch.object(service, "get_session_metrics", side_effect=RuntimeError):
                with patch.object(service, "get_payment_metrics", side_effect=RuntimeError):
                    result = service.get_all_metrics("2024-01-01", "2024-01-31")
        assert result.status == "partial"
        assert set(result.errors) == {"user_metrics", "session_metrics", "payment_metrics"}
        assert result.growth_metrics is not None


# ---------------------------------------------------------------------------
# Tests: get_user_metrics
# ---------------------------------------------------------------------------

class TestGetUserMetrics:
    def test_empty_table(self):
        # 4 scans: trainers, students, links, sessions
        service = _build_service_with_scan_results([[], [], [], []])
        result = service.get_user_metrics("2024-01-01", "2024-01-31")
        assert isinstance(result, UserMetrics)
        assert result.total_trainers == 0
        assert result.total_students == 0
        assert result.active_trainers == 0
        assert result.active_students == 0
        assert result.avg_students_per_trainer == 0.0
        assert result.total_active_links == 0

    def test_counts_trainers_and_students(self):
        trainers = [_make_trainer("t1"), _make_trainer("t2")]
        students = [_make_student("s1"), _make_student("s2"), _make_student("s3")]
        links = [
            _make_link("t1", "s1", "active"),
            _make_link("t1", "s2", "active"),
            _make_link("t2", "s3", "inactive"),
        ]
        sessions = []
        service = _build_service_with_scan_results([trainers, students, links, sessions])
        result = service.get_user_metrics("2024-01-01", "2024-01-31")
        assert result.total_trainers == 2
        assert result.total_students == 3
        assert result.total_active_links == 2
        assert result.avg_students_per_trainer == 1.0  # 2 active links / 2 trainers

    def test_active_trainers_and_students_from_sessions(self):
        trainers = [_make_trainer("t1"), _make_trainer("t2")]
        students = [_make_student("s1"), _make_student("s2")]
        links = []
        sessions = [
            _make_session("t1", "s1", "2024-01-10T09:00:00", "completed"),
            _make_session("t1", "s2", "2024-01-11T09:00:00", "scheduled"),
            _make_session("t2", "s1", "2024-01-12T09:00:00", "cancelled"),
        ]
        service = _build_service_with_scan_results([trainers, students, links, sessions])
        result = service.get_user_metrics("2024-01-01", "2024-01-31")
        # t1 has completed+scheduled sessions, t2 only cancelled → not active
        assert result.active_trainers == 1
        # s1 has completed, s2 has scheduled → both active
        assert result.active_students == 2


# ---------------------------------------------------------------------------
# Tests: get_session_metrics
# ---------------------------------------------------------------------------

class TestGetSessionMetrics:
    def test_empty_sessions(self):
        service = _build_service_with_scan_results([[]])
        result = service.get_session_metrics("2024-01-01", "2024-01-31")
        assert isinstance(result, SessionMetrics)
        assert result.total_sessions == 0
        assert result.completion_rate == 0.0
        assert result.cancellation_rate == 0.0

    def test_counts_by_status(self):
        sessions = [
            _make_session("t1", "s1", "2024-01-10T09:00:00", "scheduled"),
            _make_session("t1", "s2", "2024-01-11T09:00:00", "completed"),
            _make_session("t1", "s3", "2024-01-12T09:00:00", "completed"),
            _make_session("t1", "s4", "2024-01-13T09:00:00", "cancelled"),
            _make_session("t1", "s5", "2024-01-14T09:00:00", "missed"),
        ]
        service = _build_service_with_scan_results([sessions])
        result = service.get_session_metrics("2024-01-01", "2024-01-31")
        assert result.total_sessions == 5
        assert result.scheduled_sessions == 1
        assert result.completed_sessions == 2
        assert result.cancelled_sessions == 1
        assert result.missed_sessions == 1
        # completion_rate = 2 / (2 + 1) = 0.666...
        assert abs(result.completion_rate - 2 / 3) < 1e-9
        # cancellation_rate = 1 / 5 = 0.2
        assert result.cancellation_rate == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Tests: get_payment_metrics
# ---------------------------------------------------------------------------

class TestGetPaymentMetrics:
    def test_empty_payments(self):
        service = _build_service_with_scan_results([[]])
        result = service.get_payment_metrics("2024-01-01", "2024-01-31")
        assert isinstance(result, PaymentMetrics)
        assert result.total_payments == 0
        assert result.confirmation_rate == 0.0
        assert result.avg_payment_amount == 0.0

    def test_sums_amounts_by_status(self):
        payments = [
            _make_payment("t1", "s1", 100.0, "confirmed", "2024-01-10T10:00:00"),
            _make_payment("t1", "s2", 200.0, "confirmed", "2024-01-11T10:00:00"),
            _make_payment("t1", "s3", 50.0, "pending", "2024-01-12T10:00:00"),
        ]
        service = _build_service_with_scan_results([payments])
        result = service.get_payment_metrics("2024-01-01", "2024-01-31")
        assert result.total_payments == 3
        assert result.confirmed_payments == 2
        assert result.pending_payments == 1
        assert result.total_confirmed_amount == pytest.approx(300.0)
        assert result.total_pending_amount == pytest.approx(50.0)
        assert result.confirmation_rate == pytest.approx(2 / 3)
        assert result.avg_payment_amount == pytest.approx(150.0)


# ---------------------------------------------------------------------------
# Tests: get_growth_metrics
# ---------------------------------------------------------------------------

class TestGetGrowthMetrics:
    def test_empty_data(self):
        # 4 scans: trainers, students, sessions, payments
        service = _build_service_with_scan_results([[], [], [], []])
        result = service.get_growth_metrics("2024-01-01", "2024-01-31")
        assert isinstance(result, GrowthMetrics)
        assert result.new_trainers == 0
        assert result.new_students == 0
        assert result.trainers_per_day == []
        assert result.sessions_per_day == []

    def test_counts_new_registrations_in_range(self):
        trainers = [
            _make_trainer("t1", "2024-01-05T10:00:00"),
            _make_trainer("t2", "2023-12-01T10:00:00"),  # outside range
        ]
        students = [
            _make_student("s1", "2024-01-10T10:00:00"),
            _make_student("s2", "2024-01-15T10:00:00"),
        ]
        sessions = [
            _make_session("t1", "s1", "2024-01-10T09:00:00", "completed"),
        ]
        payments = [
            _make_payment("t1", "s1", 100.0, "confirmed", "2024-01-10T10:00:00"),
        ]
        service = _build_service_with_scan_results([trainers, students, sessions, payments])
        result = service.get_growth_metrics("2024-01-01", "2024-01-31")
        assert result.new_trainers == 1  # only t1 in range
        assert result.new_students == 2
        assert len(result.trainers_per_day) == 1
        assert result.trainers_per_day[0].date == "2024-01-05"
        assert result.trainers_per_day[0].count == 1

    def test_daily_breakdown_groups_by_day(self):
        trainers = []
        students = []
        sessions = [
            _make_session("t1", "s1", "2024-01-10T09:00:00", "completed"),
            _make_session("t1", "s2", "2024-01-10T14:00:00", "scheduled"),
            _make_session("t1", "s3", "2024-01-11T09:00:00", "completed"),
        ]
        payments = []
        service = _build_service_with_scan_results([trainers, students, sessions, payments])
        result = service.get_growth_metrics("2024-01-01", "2024-01-31")
        assert len(result.sessions_per_day) == 2
        assert result.sessions_per_day[0].date == "2024-01-10"
        assert result.sessions_per_day[0].count == 2
        assert result.sessions_per_day[1].date == "2024-01-11"
        assert result.sessions_per_day[1].count == 1


# ---------------------------------------------------------------------------
# Tests: helper methods
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_in_date_range_inclusive(self):
        assert DashboardMetricsService._in_date_range("2024-01-01T00:00:00", "2024-01-01", "2024-01-31")
        assert DashboardMetricsService._in_date_range("2024-01-31T23:59:59", "2024-01-01", "2024-01-31")
        assert not DashboardMetricsService._in_date_range("2023-12-31T23:59:59", "2024-01-01", "2024-01-31")
        assert not DashboardMetricsService._in_date_range("2024-02-01T00:00:00", "2024-01-01", "2024-01-31")

    def test_in_date_range_empty_string(self):
        assert not DashboardMetricsService._in_date_range("", "2024-01-01", "2024-01-31")

    def test_extract_date(self):
        assert DashboardMetricsService._extract_date("2024-01-15T10:30:00") == "2024-01-15"
        assert DashboardMetricsService._extract_date("2024-01-15") == "2024-01-15"
        assert DashboardMetricsService._extract_date("") == ""
