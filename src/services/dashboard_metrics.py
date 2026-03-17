"""
Dashboard Metrics Service for the Admin Dashboard.

Aggregates platform-wide KPIs from DynamoDB: user activity, sessions,
payments, and growth trends. Each section is computed independently
so partial failures return available data.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Dict, Any

from boto3.dynamodb.conditions import Attr

from models.dashboard_models import (
    DailyDataPoint,
    DashboardResponse,
    GrowthMetrics,
    PaymentMetrics,
    PeriodInfo,
    SessionMetrics,
    UserMetrics,
    safe_rate,
)
from models.dynamodb_client import DynamoDBClient


class DashboardMetricsService:
    """Aggregates platform-wide metrics from DynamoDB for the admin dashboard."""

    def __init__(self, dynamodb_client: DynamoDBClient):
        self.db = dynamodb_client

    def get_all_metrics(self, start_date: str, end_date: str) -> DashboardResponse:
        """Aggregate all metric sections, catching errors per section.

        Each section is called independently. If a section raises, it is
        recorded as ``None`` and its name is appended to the errors list.
        """
        errors: List[str] = []

        user_metrics = None
        try:
            user_metrics = self.get_user_metrics(start_date, end_date)
        except Exception:
            errors.append("user_metrics")

        session_metrics = None
        try:
            session_metrics = self.get_session_metrics(start_date, end_date)
        except Exception:
            errors.append("session_metrics")

        payment_metrics = None
        try:
            payment_metrics = self.get_payment_metrics(start_date, end_date)
        except Exception:
            errors.append("payment_metrics")

        growth_metrics = None
        try:
            growth_metrics = self.get_growth_metrics(start_date, end_date)
        except Exception:
            errors.append("growth_metrics")

        status = "ok" if not errors else "partial"

        return DashboardResponse(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            period=PeriodInfo(start_date=start_date, end_date=end_date),
            user_metrics=user_metrics,
            session_metrics=session_metrics,
            payment_metrics=payment_metrics,
            growth_metrics=growth_metrics,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Section helpers
    # ------------------------------------------------------------------

    def get_user_metrics(self, start_date: str, end_date: str) -> UserMetrics:
        """Compute user activity metrics."""
        trainers = self._scan_by_entity_type("TRAINER")
        students = self._scan_by_entity_type("STUDENT")
        links = self._scan_by_entity_type("TRAINER_STUDENT_LINK")

        total_trainers = len(trainers)
        total_students = len(students)
        total_active_links = sum(
            1 for link in links if link.get("status") == "active"
        )

        # Active trainers/students derived from sessions in the date range
        sessions = self._scan_sessions_in_range(start_date, end_date)
        active_statuses = {"scheduled", "completed"}
        active_trainer_ids = set()
        active_student_ids = set()
        for s in sessions:
            if s.get("status") in active_statuses:
                if s.get("trainer_id"):
                    active_trainer_ids.add(s["trainer_id"])
                if s.get("student_id"):
                    active_student_ids.add(s["student_id"])

        avg_students = safe_rate(total_active_links, total_trainers) if total_trainers > 0 else 0.0
        # avg_students_per_trainer is not a rate clamped to 1 — it's a plain average
        if total_trainers > 0:
            avg_students = total_active_links / total_trainers
        else:
            avg_students = 0.0

        return UserMetrics(
            total_trainers=total_trainers,
            total_students=total_students,
            active_trainers=len(active_trainer_ids),
            active_students=len(active_student_ids),
            avg_students_per_trainer=avg_students,
            total_active_links=total_active_links,
        )

    def get_session_metrics(self, start_date: str, end_date: str) -> SessionMetrics:
        """Compute session KPIs for the given date range."""
        sessions = self._scan_sessions_in_range(start_date, end_date)

        status_counts: Dict[str, int] = defaultdict(int)
        for s in sessions:
            status_counts[s.get("status", "unknown")] += 1

        total = len(sessions)
        scheduled = status_counts.get("scheduled", 0)
        completed = status_counts.get("completed", 0)
        cancelled = status_counts.get("cancelled", 0)
        missed = status_counts.get("missed", 0)

        completion_rate = safe_rate(completed, completed + missed)
        cancellation_rate = safe_rate(cancelled, total)

        return SessionMetrics(
            total_sessions=total,
            scheduled_sessions=scheduled,
            completed_sessions=completed,
            cancelled_sessions=cancelled,
            missed_sessions=missed,
            completion_rate=completion_rate,
            cancellation_rate=cancellation_rate,
        )

    def get_payment_metrics(self, start_date: str, end_date: str) -> PaymentMetrics:
        """Compute payment KPIs for the given date range."""
        payments = self._scan_payments_in_range(start_date, end_date)

        total = len(payments)
        pending = 0
        confirmed = 0
        total_confirmed_amount = 0.0
        total_pending_amount = 0.0

        for p in payments:
            status = p.get("payment_status", "")
            amount = float(p.get("amount", 0))
            if status == "confirmed":
                confirmed += 1
                total_confirmed_amount += amount
            elif status == "pending":
                pending += 1
                total_pending_amount += amount

        confirmation_rate = safe_rate(confirmed, total)
        avg_payment = (total_confirmed_amount / confirmed) if confirmed > 0 else 0.0

        return PaymentMetrics(
            total_payments=total,
            pending_payments=pending,
            confirmed_payments=confirmed,
            total_confirmed_amount=total_confirmed_amount,
            total_pending_amount=total_pending_amount,
            confirmation_rate=confirmation_rate,
            avg_payment_amount=avg_payment,
        )

    def get_growth_metrics(self, start_date: str, end_date: str) -> GrowthMetrics:
        """Compute growth trend metrics with daily breakdowns."""
        trainers = self._scan_by_entity_type("TRAINER")
        students = self._scan_by_entity_type("STUDENT")

        new_trainers_list = [
            t for t in trainers
            if self._in_date_range(t.get("created_at", ""), start_date, end_date)
        ]
        new_students_list = [
            s for s in students
            if self._in_date_range(s.get("created_at", ""), start_date, end_date)
        ]

        sessions = self._scan_sessions_in_range(start_date, end_date)
        payments = self._scan_payments_in_range(start_date, end_date)
        confirmed_payments = [
            p for p in payments if p.get("payment_status") == "confirmed"
        ]

        trainers_per_day = self._group_by_day(new_trainers_list, "created_at")
        students_per_day = self._group_by_day(new_students_list, "created_at")
        sessions_per_day = self._group_by_day(sessions, "session_datetime")
        revenue_per_day = self._group_revenue_by_day(confirmed_payments)

        return GrowthMetrics(
            new_trainers=len(new_trainers_list),
            new_students=len(new_students_list),
            trainers_per_day=trainers_per_day,
            students_per_day=students_per_day,
            sessions_per_day=sessions_per_day,
            revenue_per_day=revenue_per_day,
        )

    # ------------------------------------------------------------------
    # DynamoDB scan helpers
    # ------------------------------------------------------------------

    def _scan_by_entity_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """Full table scan filtered by ``entity_type``."""
        items: List[Dict[str, Any]] = []
        filter_expr = Attr("entity_type").eq(entity_type)
        response = self.db.table.scan(FilterExpression=filter_expr)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.db.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items

    def _scan_sessions_in_range(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """Scan for SESSION entities whose ``session_datetime`` falls in range."""
        filter_expr = (
            Attr("entity_type").eq("SESSION")
            & Attr("session_datetime").gte(start_date)
            & Attr("session_datetime").lte(end_date + "T23:59:59")
        )
        items: List[Dict[str, Any]] = []
        response = self.db.table.scan(FilterExpression=filter_expr)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.db.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items

    def _scan_payments_in_range(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """Scan for PAYMENT entities whose ``created_at`` falls in range."""
        filter_expr = (
            Attr("entity_type").eq("PAYMENT")
            & Attr("created_at").gte(start_date)
            & Attr("created_at").lte(end_date + "T23:59:59")
        )
        items: List[Dict[str, Any]] = []
        response = self.db.table.scan(FilterExpression=filter_expr)
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = self.db.table.scan(
                FilterExpression=filter_expr,
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items

    # ------------------------------------------------------------------
    # Date / grouping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _in_date_range(value: str, start_date: str, end_date: str) -> bool:
        """Check whether an ISO datetime/date string falls within [start, end]."""
        if not value:
            return False
        date_part = value[:10]  # YYYY-MM-DD
        return start_date <= date_part <= end_date

    @staticmethod
    def _extract_date(value: str) -> str:
        """Extract YYYY-MM-DD from an ISO datetime string."""
        return value[:10] if value else ""

    @classmethod
    def _group_by_day(
        cls, items: List[Dict[str, Any]], date_field: str
    ) -> List[DailyDataPoint]:
        """Group items by day and return sorted ``DailyDataPoint`` list."""
        counts: Dict[str, int] = defaultdict(int)
        for item in items:
            day = cls._extract_date(item.get(date_field, ""))
            if day:
                counts[day] += 1
        return [
            DailyDataPoint(date=d, count=c)
            for d, c in sorted(counts.items())
        ]

    @classmethod
    def _group_revenue_by_day(
        cls, payments: List[Dict[str, Any]]
    ) -> List[DailyDataPoint]:
        """Group confirmed payment amounts by day."""
        amounts: Dict[str, float] = defaultdict(float)
        for p in payments:
            day = cls._extract_date(p.get("created_at", ""))
            if day:
                amounts[day] += float(p.get("amount", 0))
        return [
            DailyDataPoint(date=d, count=int(a))
            for d, a in sorted(amounts.items())
        ]
