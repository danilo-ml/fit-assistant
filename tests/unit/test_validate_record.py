"""Unit tests for BulkImportService._validate_record method."""

import pytest
from unittest.mock import MagicMock

from src.services.bulk_import_service import BulkImportService
from src.services.import_parser import RawStudentRecord
from src.utils.validation import InputSanitizer, PhoneNumberValidator


@pytest.fixture
def service():
    """Create a BulkImportService with real validator/sanitizer and mock DB client."""
    mock_db = MagicMock()
    return BulkImportService(
        dynamodb_client=mock_db,
        phone_validator=PhoneNumberValidator(),
        input_sanitizer=InputSanitizer(),
    )


def _valid_record(**overrides) -> RawStudentRecord:
    """Helper to create a valid RawStudentRecord with optional overrides."""
    defaults = dict(
        line_number=1,
        name="João Silva",
        phone_number="+5511999999999",
        email="joao@email.com",
        training_goal="Perder peso",
    )
    defaults.update(overrides)
    return RawStudentRecord(**defaults)


class TestValidRecords:
    def test_valid_record_returns_no_errors(self, service):
        record = _valid_record()
        assert service._validate_record(record) == []

    def test_valid_record_with_all_optional_fields(self, service):
        record = _valid_record(
            payment_due_day="15",
            monthly_fee="150.00",
            plan_start_date="2024-01",
        )
        assert service._validate_record(record) == []

    def test_valid_record_with_integer_monthly_fee(self, service):
        record = _valid_record(monthly_fee="300")
        assert service._validate_record(record) == []

    def test_valid_record_with_one_decimal_fee(self, service):
        record = _valid_record(monthly_fee="150.5")
        assert service._validate_record(record) == []


class TestNameValidation:
    def test_name_too_short(self, service):
        record = _valid_record(name="A")
        errors = service._validate_record(record)
        assert any("2 caracteres" in e for e in errors)

    def test_name_empty(self, service):
        record = _valid_record(name="")
        errors = service._validate_record(record)
        assert any("2 caracteres" in e for e in errors)

    def test_name_none(self, service):
        record = _valid_record(name=None)
        errors = service._validate_record(record)
        assert any("2 caracteres" in e for e in errors)

    def test_name_exactly_2_chars(self, service):
        record = _valid_record(name="Jo")
        assert service._validate_record(record) == []


class TestPhoneValidation:
    def test_valid_e164_phone(self, service):
        record = _valid_record(phone_number="+5511999999999")
        assert service._validate_record(record) == []

    def test_phone_missing_plus_normalizable(self, service):
        record = _valid_record(phone_number="5511999999999")
        errors = service._validate_record(record)
        assert not any("Telefone" in e for e in errors)
        assert record.phone_number == "+5511999999999"

    def test_phone_invalid_format(self, service):
        record = _valid_record(phone_number="abc123")
        errors = service._validate_record(record)
        assert any("Telefone" in e for e in errors)

    def test_phone_none(self, service):
        record = _valid_record(phone_number=None)
        errors = service._validate_record(record)
        assert any("Telefone" in e for e in errors)

    def test_phone_empty(self, service):
        record = _valid_record(phone_number="")
        errors = service._validate_record(record)
        assert any("Telefone" in e for e in errors)

    def test_phone_with_plus_but_invalid(self, service):
        record = _valid_record(phone_number="+abc")
        errors = service._validate_record(record)
        assert any("Telefone" in e for e in errors)


class TestEmailValidation:
    def test_email_missing_at(self, service):
        record = _valid_record(email="joaoemail.com")
        errors = service._validate_record(record)
        assert any("Email" in e for e in errors)

    def test_email_missing_dot(self, service):
        record = _valid_record(email="joao@emailcom")
        errors = service._validate_record(record)
        assert any("Email" in e for e in errors)

    def test_email_none(self, service):
        record = _valid_record(email=None)
        errors = service._validate_record(record)
        assert any("Email" in e for e in errors)

    def test_email_empty(self, service):
        record = _valid_record(email="")
        errors = service._validate_record(record)
        assert any("Email" in e for e in errors)


class TestTrainingGoalValidation:
    def test_training_goal_empty(self, service):
        record = _valid_record(training_goal="")
        errors = service._validate_record(record)
        assert any("Objetivo" in e for e in errors)

    def test_training_goal_none(self, service):
        record = _valid_record(training_goal=None)
        errors = service._validate_record(record)
        assert any("Objetivo" in e for e in errors)


class TestPaymentDueDayValidation:
    def test_valid_day_1(self, service):
        record = _valid_record(payment_due_day="1")
        assert service._validate_record(record) == []

    def test_valid_day_31(self, service):
        record = _valid_record(payment_due_day="31")
        assert service._validate_record(record) == []

    def test_day_zero(self, service):
        record = _valid_record(payment_due_day="0")
        errors = service._validate_record(record)
        assert any("vencimento" in e for e in errors)

    def test_day_32(self, service):
        record = _valid_record(payment_due_day="32")
        errors = service._validate_record(record)
        assert any("vencimento" in e for e in errors)

    def test_day_not_integer(self, service):
        record = _valid_record(payment_due_day="abc")
        errors = service._validate_record(record)
        assert any("vencimento" in e for e in errors)

    def test_day_none_is_ok(self, service):
        record = _valid_record(payment_due_day=None)
        assert service._validate_record(record) == []

    def test_day_empty_string_is_ok(self, service):
        record = _valid_record(payment_due_day="")
        assert service._validate_record(record) == []


class TestMonthlyFeeValidation:
    def test_fee_positive(self, service):
        record = _valid_record(monthly_fee="150.00")
        assert service._validate_record(record) == []

    def test_fee_zero(self, service):
        record = _valid_record(monthly_fee="0")
        errors = service._validate_record(record)
        assert any("Mensalidade" in e for e in errors)

    def test_fee_negative(self, service):
        record = _valid_record(monthly_fee="-50")
        errors = service._validate_record(record)
        assert any("Mensalidade" in e for e in errors)

    def test_fee_too_many_decimals(self, service):
        record = _valid_record(monthly_fee="150.123")
        errors = service._validate_record(record)
        assert any("decimais" in e or "Mensalidade" in e for e in errors)

    def test_fee_not_a_number(self, service):
        record = _valid_record(monthly_fee="abc")
        errors = service._validate_record(record)
        assert any("Mensalidade" in e for e in errors)

    def test_fee_none_is_ok(self, service):
        record = _valid_record(monthly_fee=None)
        assert service._validate_record(record) == []

    def test_fee_empty_string_is_ok(self, service):
        record = _valid_record(monthly_fee="")
        assert service._validate_record(record) == []


class TestPlanStartDateValidation:
    def test_valid_date(self, service):
        record = _valid_record(plan_start_date="2024-01")
        assert service._validate_record(record) == []

    def test_valid_date_december(self, service):
        record = _valid_record(plan_start_date="2024-12")
        assert service._validate_record(record) == []

    def test_invalid_month_00(self, service):
        record = _valid_record(plan_start_date="2024-00")
        errors = service._validate_record(record)
        assert any("Data" in e or "AAAA-MM" in e for e in errors)

    def test_invalid_month_13(self, service):
        record = _valid_record(plan_start_date="2024-13")
        errors = service._validate_record(record)
        assert any("Data" in e or "AAAA-MM" in e for e in errors)

    def test_invalid_format_full_date(self, service):
        record = _valid_record(plan_start_date="2024-01-15")
        errors = service._validate_record(record)
        assert any("Data" in e or "AAAA-MM" in e for e in errors)

    def test_invalid_format_random(self, service):
        record = _valid_record(plan_start_date="Jan 2024")
        errors = service._validate_record(record)
        assert any("Data" in e or "AAAA-MM" in e for e in errors)

    def test_date_none_is_ok(self, service):
        record = _valid_record(plan_start_date=None)
        assert service._validate_record(record) == []

    def test_date_empty_string_is_ok(self, service):
        record = _valid_record(plan_start_date="")
        assert service._validate_record(record) == []


class TestSanitization:
    def test_html_tags_stripped_from_name(self, service):
        record = _valid_record(name="<b>João</b> Silva")
        service._validate_record(record)
        assert "<b>" not in record.name
        assert "João" in record.name

    def test_script_tags_stripped(self, service):
        record = _valid_record(name="<script>alert('xss')</script>João Silva")
        service._validate_record(record)
        assert "<script>" not in record.name
        assert "João" in record.name

    def test_whitespace_stripped(self, service):
        record = _valid_record(name="  João Silva  ")
        service._validate_record(record)
        assert record.name == "João Silva"

    def test_email_sanitized(self, service):
        record = _valid_record(email="  joao@email.com  ")
        service._validate_record(record)
        assert record.email == "joao@email.com"

    def test_training_goal_sanitized(self, service):
        record = _valid_record(training_goal="<i>Perder peso</i>")
        service._validate_record(record)
        assert "<i>" not in record.training_goal

    def test_phone_normalized_in_place(self, service):
        record = _valid_record(phone_number="5511999999999")
        service._validate_record(record)
        assert record.phone_number == "+5511999999999"


class TestMultipleErrors:
    def test_multiple_validation_errors(self, service):
        record = RawStudentRecord(
            line_number=1,
            name="A",
            phone_number="invalid",
            email="bademail",
            training_goal="",
        )
        errors = service._validate_record(record)
        assert len(errors) >= 3
