"""
Dashboard response dataclasses for the Admin Dashboard API.

Defines data models for all metric sections returned by the dashboard endpoint,
along with JSON serialization and rate calculation utilities.
"""

from dataclasses import dataclass, field
from typing import List, Optional


def safe_rate(numerator: float, denominator: float) -> float:
    """Calculate a rate as numerator/denominator, clamped to [0.0, 1.0].

    Returns 0.0 when denominator is zero or negative.

    Args:
        numerator: The numerator value.
        denominator: The denominator value.

    Returns:
        A float between 0.0 and 1.0 inclusive.
    """
    if denominator <= 0:
        return 0.0
    return max(0.0, min(numerator / denominator, 1.0))


@dataclass
class PeriodInfo:
    """Time period for the dashboard query."""

    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
        }


@dataclass
class UserMetrics:
    """User activity metrics."""

    total_trainers: int
    total_students: int
    active_trainers: int
    active_students: int
    avg_students_per_trainer: float
    total_active_links: int

    def to_dict(self) -> dict:
        return {
            "total_trainers": self.total_trainers,
            "total_students": self.total_students,
            "active_trainers": self.active_trainers,
            "active_students": self.active_students,
            "avg_students_per_trainer": self.avg_students_per_trainer,
            "total_active_links": self.total_active_links,
        }


@dataclass
class SessionMetrics:
    """Session-related KPIs."""

    total_sessions: int
    scheduled_sessions: int
    completed_sessions: int
    cancelled_sessions: int
    missed_sessions: int
    completion_rate: float
    cancellation_rate: float

    def to_dict(self) -> dict:
        return {
            "total_sessions": self.total_sessions,
            "scheduled_sessions": self.scheduled_sessions,
            "completed_sessions": self.completed_sessions,
            "cancelled_sessions": self.cancelled_sessions,
            "missed_sessions": self.missed_sessions,
            "completion_rate": self.completion_rate,
            "cancellation_rate": self.cancellation_rate,
        }


@dataclass
class PaymentMetrics:
    """Payment-related KPIs."""

    total_payments: int
    pending_payments: int
    confirmed_payments: int
    total_confirmed_amount: float
    total_pending_amount: float
    confirmation_rate: float
    avg_payment_amount: float

    def to_dict(self) -> dict:
        return {
            "total_payments": self.total_payments,
            "pending_payments": self.pending_payments,
            "confirmed_payments": self.confirmed_payments,
            "total_confirmed_amount": self.total_confirmed_amount,
            "total_pending_amount": self.total_pending_amount,
            "confirmation_rate": self.confirmation_rate,
            "avg_payment_amount": self.avg_payment_amount,
        }


@dataclass
class DailyDataPoint:
    """A single day's count or amount for growth charts."""

    date: str  # YYYY-MM-DD
    count: int

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "count": self.count,
        }


@dataclass
class GrowthMetrics:
    """Growth trend metrics with daily breakdowns."""

    new_trainers: int
    new_students: int
    trainers_per_day: List[DailyDataPoint] = field(default_factory=list)
    students_per_day: List[DailyDataPoint] = field(default_factory=list)
    sessions_per_day: List[DailyDataPoint] = field(default_factory=list)
    revenue_per_day: List[DailyDataPoint] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "new_trainers": self.new_trainers,
            "new_students": self.new_students,
            "trainers_per_day": [dp.to_dict() for dp in self.trainers_per_day],
            "students_per_day": [dp.to_dict() for dp in self.students_per_day],
            "sessions_per_day": [dp.to_dict() for dp in self.sessions_per_day],
            "revenue_per_day": [dp.to_dict() for dp in self.revenue_per_day],
        }


@dataclass
class DashboardResponse:
    """Top-level API response for the dashboard metrics endpoint."""

    status: str  # "ok" or "partial"
    generated_at: str  # ISO 8601 timestamp
    period: PeriodInfo
    user_metrics: Optional[UserMetrics] = None
    session_metrics: Optional[SessionMetrics] = None
    payment_metrics: Optional[PaymentMetrics] = None
    growth_metrics: Optional[GrowthMetrics] = None
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "period": self.period.to_dict(),
            "user_metrics": self.user_metrics.to_dict() if self.user_metrics else None,
            "session_metrics": self.session_metrics.to_dict() if self.session_metrics else None,
            "payment_metrics": self.payment_metrics.to_dict() if self.payment_metrics else None,
            "growth_metrics": self.growth_metrics.to_dict() if self.growth_metrics else None,
            "errors": self.errors,
        }
