"""Unit tests for BulkImportService.validate_and_import orchestration method."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.bulk_import_service import (
    BulkImportService,
    ImportResult,
    RecordResult,
    RecordStatus,
)
from src.services.import_parser import RawStudentRecord
from src.utils.validation import InputSanitizer, PhoneNumberValidator


@pytest.fixture
def mock_dynamodb():
    return MagicMock()


@pytest.fixture
def service(mock_dynamodb):
    return BulkImportService(
        dynamodb_client=mock_dynamodb,
        phone_validator=PhoneNumberValidator(),
        input_sanitizer=InputSanitizer(),
    )


def _record(line_number: int, **overrides) -> RawStudentRecord:
    defaults = dict(
        line_number=line_number,
        name="João Silva",
        phone_number="+5511999999999",
        email="joao@email.com",
        training_goal="Perder peso",
    )
    defaults.update(overrides)
    return RawStudentRecord(**defaults)


class TestBatchSizeLimit:
    """Reject batch if > 50 records (MAX_BATCH_SIZE)."""

    def test_rejects_batch_over_50(self, service):
        records = [_record(i, phone_number=f"+551199900{i:04d}") for i in range(51)]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 51
        assert result.succeeded == 0
        assert result.skipped == 0
        assert result.failed == 51
        assert all(r.status == RecordStatus.VALIDATION_FAILED for r in result.results)
        assert "50" in result.results[0].error

    def test_accepts_batch_of_exactly_50(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        mock_dynamodb.batch_write_items.return_value = True
        records = [
            _record(i, phone_number=f"+551199900{i:04d}")
            for i in range(50)
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 50
        assert result.failed == 0


class TestAllValidRecords:
    """All records pass validation and are new — all should succeed."""

    def test_all_new_records_succeed(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        mock_dynamodb.batch_write_items.return_value = True

        records = [
            _record(1, phone_number="+5511111111111"),
            _record(2, phone_number="+5522222222222", name="Maria"),
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 2
        assert result.succeeded == 2
        assert result.skipped == 0
        assert result.failed == 0
        assert len(result.results) == 2
        assert result.results[0].status == RecordStatus.SUCCESS
        assert result.results[1].status == RecordStatus.SUCCESS


class TestAllInvalidRecords:
    """All records fail validation — no DB writes should happen."""

    def test_no_db_writes_when_all_invalid(self, service, mock_dynamodb):
        records = [
            _record(1, name="A", phone_number="bad", email="nope", training_goal=""),
            _record(2, name="B", phone_number="bad2", email="nope2", training_goal=""),
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 2
        assert result.succeeded == 0
        assert result.skipped == 0
        assert result.failed == 2
        assert all(r.status == RecordStatus.VALIDATION_FAILED for r in result.results)
        # No DB calls should have been made
        mock_dynamodb.lookup_by_phone_number.assert_not_called()
        mock_dynamodb.batch_write_items.assert_not_called()


class TestMixedValidAndInvalid:
    """Mix of valid and invalid records — partial failure support."""

    def test_valid_records_persist_invalid_fail(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        mock_dynamodb.batch_write_items.return_value = True

        records = [
            _record(1, phone_number="+5511111111111"),  # valid
            _record(2, name="A", phone_number="bad", email="x", training_goal=""),  # invalid
            _record(3, phone_number="+5533333333333", name="Pedro"),  # valid
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 3
        assert result.succeeded == 2
        assert result.failed == 1
        assert result.skipped == 0
        assert result.results[0].status == RecordStatus.SUCCESS
        assert result.results[1].status == RecordStatus.VALIDATION_FAILED
        assert result.results[2].status == RecordStatus.SUCCESS


class TestDuplicateHandling:
    """Duplicate detection integration in the orchestration flow."""

    def test_already_linked_is_skipped(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "stu1",
        }
        mock_dynamodb.get_trainer_student_link.return_value = {"status": "active"}

        records = [_record(1, phone_number="+5511111111111")]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 1
        assert result.succeeded == 0
        assert result.skipped == 1
        assert result.failed == 0
        assert result.results[0].status == RecordStatus.ALREADY_LINKED

    def test_phone_is_trainer_is_skipped(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "TRAINER",
            "trainer_id": "other",
        }

        records = [_record(1, phone_number="+5511111111111")]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 1
        assert result.skipped == 1
        assert result.results[0].status == RecordStatus.PHONE_IS_TRAINER

    def test_duplicate_in_batch_is_skipped(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        mock_dynamodb.batch_write_items.return_value = True

        records = [
            _record(1, phone_number="+5511111111111"),
            _record(2, phone_number="+5511111111111", name="Dup"),
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 2
        assert result.succeeded == 1
        assert result.skipped == 1
        assert result.results[0].status == RecordStatus.SUCCESS
        assert result.results[1].status == RecordStatus.DUPLICATE_IN_BATCH

    def test_linked_existing_creates_link_only(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "existing_stu",
        }
        mock_dynamodb.get_trainer_student_link.return_value = None
        mock_dynamodb.batch_write_items.return_value = True

        records = [_record(1, phone_number="+5511111111111")]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 1
        assert result.succeeded == 1
        assert result.skipped == 0
        assert result.failed == 0
        assert result.results[0].status == RecordStatus.LINKED_EXISTING
        assert result.results[0].student_id == "existing_stu"


class TestResultOrdering:
    """Results should be in the same order as input records."""

    def test_results_preserve_original_order(self, service, mock_dynamodb):
        def lookup_side_effect(phone):
            if phone == "+5522222222222":
                return {"entity_type": "TRAINER", "trainer_id": "t2"}
            return None

        mock_dynamodb.lookup_by_phone_number.side_effect = lookup_side_effect
        mock_dynamodb.batch_write_items.return_value = True

        records = [
            _record(1, phone_number="+5511111111111"),  # new -> SUCCESS
            _record(2, name="X", phone_number="bad", email="x", training_goal=""),  # invalid
            _record(3, phone_number="+5522222222222"),  # trainer phone -> skipped
            _record(4, phone_number="+5544444444444", name="Ana"),  # new -> SUCCESS
        ]
        result = service.validate_and_import("trainer1", records)

        assert len(result.results) == 4
        assert result.results[0].line_number == 1
        assert result.results[1].line_number == 2
        assert result.results[2].line_number == 3
        assert result.results[3].line_number == 4
        assert result.results[0].status == RecordStatus.SUCCESS
        assert result.results[1].status == RecordStatus.VALIDATION_FAILED
        assert result.results[2].status == RecordStatus.PHONE_IS_TRAINER
        assert result.results[3].status == RecordStatus.SUCCESS


class TestCountAccuracy:
    """ImportResult counts should be accurate."""

    def test_counts_with_mixed_outcomes(self, service, mock_dynamodb):
        def lookup_side_effect(phone):
            if phone == "+5522222222222":
                return {"entity_type": "STUDENT", "student_id": "stu1"}
            if phone == "+5533333333333":
                return {"entity_type": "TRAINER", "trainer_id": "t2"}
            return None

        mock_dynamodb.lookup_by_phone_number.side_effect = lookup_side_effect
        mock_dynamodb.get_trainer_student_link.return_value = {"status": "active"}
        mock_dynamodb.batch_write_items.return_value = True

        records = [
            _record(1, phone_number="+5511111111111"),  # new -> SUCCESS
            _record(2, phone_number="+5522222222222"),  # already linked -> skipped
            _record(3, phone_number="+5533333333333"),  # trainer -> skipped
            _record(4, name="X", phone_number="bad", email="x", training_goal=""),  # invalid
            _record(5, phone_number="+5555555555555", name="Pedro"),  # new -> SUCCESS
        ]
        result = service.validate_and_import("trainer1", records)

        assert result.total == 5
        assert result.succeeded == 2
        assert result.skipped == 2
        assert result.failed == 1
