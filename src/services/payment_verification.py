"""
Payment verification service for plan-based payment management.

Stateless service with pure static methods for verifying payments
against student plans and deriving month-by-month payment status.
"""

import re
from decimal import Decimal
from typing import Any, Dict, List


def _validate_yyyy_mm(value: str, field_name: str) -> None:
    """Validate a string is in YYYY-MM format with valid month."""
    if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', value):
        raise ValueError(f'{field_name} must be in YYYY-MM format')


def _month_diff(start: str, end: str) -> int:
    """Calculate inclusive month count between two YYYY-MM strings."""
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    return (ey - sy) * 12 + (em - sm) + 1


def _add_months(yyyy_mm: str, n: int) -> str:
    """Add n months to a YYYY-MM string and return new YYYY-MM."""
    y, m = int(yyyy_mm[:4]), int(yyyy_mm[5:7])
    total = (y * 12 + m - 1) + n
    new_y, new_m = divmod(total, 12)
    new_m += 1
    return f'{new_y:04d}-{new_m:02d}'


class PaymentVerificationService:
    """Stateless service for payment verification against student plans."""

    @staticmethod
    def calculate_months_covered(start_month: str, end_month: str) -> int:
        """
        Calculate number of months in a reference period (inclusive).

        Args:
            start_month: Start month in YYYY-MM format.
            end_month: End month in YYYY-MM format.

        Returns:
            Inclusive count of months from start to end.

        Raises:
            ValueError: If format is invalid or start > end.
        """
        _validate_yyyy_mm(start_month, 'start_month')
        _validate_yyyy_mm(end_month, 'end_month')
        if start_month > end_month:
            raise ValueError('start_month must be <= end_month')
        return _month_diff(start_month, end_month)

    @staticmethod
    def verify_payment(
        monthly_fee: Decimal,
        amount: Decimal,
        reference_start_month: str,
        reference_end_month: str,
    ) -> Dict[str, Any]:
        """
        Verify payment amount against plan.

        Args:
            monthly_fee: The student's monthly fee (positive Decimal).
            amount: The actual payment amount.
            reference_start_month: Start of reference period (YYYY-MM).
            reference_end_month: End of reference period (YYYY-MM).

        Returns:
            Dict with status, expected_amount, actual_amount, months_covered.

        Raises:
            ValueError: If inputs are invalid.
        """
        if not isinstance(monthly_fee, Decimal):
            raise ValueError('monthly_fee must be a Decimal')
        if monthly_fee <= 0:
            raise ValueError('monthly_fee must be greater than 0')
        if not isinstance(amount, Decimal):
            raise ValueError('amount must be a Decimal')

        months_covered = PaymentVerificationService.calculate_months_covered(
            reference_start_month, reference_end_month
        )
        expected_amount = monthly_fee * months_covered

        status = 'matched' if amount == expected_amount else 'mismatched'

        return {
            'status': status,
            'expected_amount': expected_amount,
            'actual_amount': amount,
            'months_covered': months_covered,
        }

    @staticmethod
    def get_payment_status_by_month(
        plan_start_date: str,
        confirmed_payments: List[Dict],
        current_month: str,
    ) -> List[Dict[str, str]]:
        """
        Derive month-by-month payment status.

        Each confirmed payment dict must have 'reference_start_month' and
        'reference_end_month' keys in YYYY-MM format.

        Args:
            plan_start_date: Plan start month (YYYY-MM).
            confirmed_payments: List of dicts with reference period fields.
            current_month: The current month (YYYY-MM).

        Returns:
            List of {'month': 'YYYY-MM', 'status': 'paid'|'pending'|'overdue'}
            spanning plan_start_date to current_month inclusive.

        Raises:
            ValueError: If inputs are invalid.
        """
        _validate_yyyy_mm(plan_start_date, 'plan_start_date')
        _validate_yyyy_mm(current_month, 'current_month')

        # Build set of paid months from confirmed payments
        paid_months: set = set()
        for payment in confirmed_payments:
            start = payment.get('reference_start_month')
            end = payment.get('reference_end_month')
            if start is None or end is None:
                continue
            _validate_yyyy_mm(start, 'reference_start_month')
            _validate_yyyy_mm(end, 'reference_end_month')
            count = _month_diff(start, end)
            for i in range(count):
                paid_months.add(_add_months(start, i))

        # Generate month-by-month status from plan_start_date to current_month
        total_months = _month_diff(plan_start_date, current_month)
        result: List[Dict[str, str]] = []
        for i in range(total_months):
            month = _add_months(plan_start_date, i)
            if month in paid_months:
                status = 'paid'
            elif month < current_month:
                status = 'overdue'
            else:
                status = 'pending'
            result.append({'month': month, 'status': status})

        return result
