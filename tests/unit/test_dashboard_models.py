"""Unit tests for dashboard response dataclasses and safe_rate utility."""

from src.models.dashboard_models import (
    DailyDataPoint,
    DashboardResponse,
    GrowthMetrics,
    PaymentMetrics,
    PeriodInfo,
    SessionMetrics,
    UserMetrics,
    safe_rate,
)


class TestSafeRate:
    """Tests for the safe_rate utility function."""

    def test_normal_division(self):
        assert safe_rate(1, 2) == 0.5

    def test_zero_denominator_returns_zero(self):
        assert safe_rate(5, 0) == 0.0

    def test_negative_denominator_returns_zero(self):
        assert safe_rate(5, -1) == 0.0

    def test_clamps_to_one(self):
        assert safe_rate(10, 5) == 1.0

    def test_clamps_to_zero_for_negative_numerator(self):
        assert safe_rate(-1, 5) == 0.0

    def test_zero_numerator(self):
        assert safe_rate(0, 10) == 0.0

    def test_equal_values(self):
        assert safe_rate(7, 7) == 1.0


class TestPeriodInfo:
    def test_to_dict(self):
        p = PeriodInfo(start_date="2024-01-01", end_date="2024-01-31")
        assert p.to_dict() == {"start_date": "2024-01-01", "end_date": "2024-01-31"}


class TestUserMetrics:
    def test_to_dict(self):
        m = UserMetrics(
            total_trainers=10,
            total_students=50,
            active_trainers=8,
            active_students=40,
            avg_students_per_trainer=5.0,
            total_active_links=45,
        )
        d = m.to_dict()
        assert d["total_trainers"] == 10
        assert d["total_students"] == 50
        assert d["active_trainers"] == 8
        assert d["active_students"] == 40
        assert d["avg_students_per_trainer"] == 5.0
        assert d["total_active_links"] == 45


class TestSessionMetrics:
    def test_to_dict(self):
        m = SessionMetrics(
            total_sessions=100,
            scheduled_sessions=20,
            completed_sessions=60,
            cancelled_sessions=10,
            missed_sessions=10,
            completion_rate=0.857,
            cancellation_rate=0.1,
        )
        d = m.to_dict()
        assert d["total_sessions"] == 100
        assert d["completed_sessions"] == 60
        assert d["completion_rate"] == 0.857
        assert d["cancellation_rate"] == 0.1


class TestPaymentMetrics:
    def test_to_dict(self):
        m = PaymentMetrics(
            total_payments=50,
            pending_payments=10,
            confirmed_payments=40,
            total_confirmed_amount=4000.0,
            total_pending_amount=1000.0,
            confirmation_rate=0.8,
            avg_payment_amount=100.0,
        )
        d = m.to_dict()
        assert d["total_payments"] == 50
        assert d["total_confirmed_amount"] == 4000.0
        assert d["confirmation_rate"] == 0.8
        assert d["avg_payment_amount"] == 100.0


class TestDailyDataPoint:
    def test_to_dict(self):
        dp = DailyDataPoint(date="2024-01-15", count=5)
        assert dp.to_dict() == {"date": "2024-01-15", "count": 5}


class TestGrowthMetrics:
    def test_to_dict(self):
        m = GrowthMetrics(
            new_trainers=3,
            new_students=12,
            trainers_per_day=[DailyDataPoint("2024-01-01", 2), DailyDataPoint("2024-01-02", 1)],
            students_per_day=[],
            sessions_per_day=[],
            revenue_per_day=[],
        )
        d = m.to_dict()
        assert d["new_trainers"] == 3
        assert d["new_students"] == 12
        assert len(d["trainers_per_day"]) == 2
        assert d["trainers_per_day"][0] == {"date": "2024-01-01", "count": 2}


class TestDashboardResponse:
    def test_to_dict_full(self):
        resp = DashboardResponse(
            status="ok",
            generated_at="2024-01-15T10:30:00Z",
            period=PeriodInfo("2024-01-01", "2024-01-15"),
            user_metrics=UserMetrics(10, 50, 8, 40, 5.0, 45),
            session_metrics=SessionMetrics(100, 20, 60, 10, 10, 0.857, 0.1),
            payment_metrics=PaymentMetrics(50, 10, 40, 4000.0, 1000.0, 0.8, 100.0),
            growth_metrics=GrowthMetrics(3, 12),
            errors=[],
        )
        d = resp.to_dict()
        assert d["status"] == "ok"
        assert d["generated_at"] == "2024-01-15T10:30:00Z"
        assert d["period"]["start_date"] == "2024-01-01"
        assert d["user_metrics"]["total_trainers"] == 10
        assert d["session_metrics"]["total_sessions"] == 100
        assert d["payment_metrics"]["total_payments"] == 50
        assert d["growth_metrics"]["new_trainers"] == 3
        assert d["errors"] == []

    def test_to_dict_partial_with_none_sections(self):
        resp = DashboardResponse(
            status="partial",
            generated_at="2024-01-15T10:30:00Z",
            period=PeriodInfo("2024-01-01", "2024-01-15"),
            user_metrics=None,
            session_metrics=None,
            errors=["user_metrics", "session_metrics"],
        )
        d = resp.to_dict()
        assert d["status"] == "partial"
        assert d["user_metrics"] is None
        assert d["session_metrics"] is None
        assert d["payment_metrics"] is None
        assert d["growth_metrics"] is None
        assert d["errors"] == ["user_metrics", "session_metrics"]
