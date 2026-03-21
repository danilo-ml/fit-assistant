"""Unit tests for BulkImportService._batch_persist method."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from src.services.bulk_import_service import (
    BulkImportService,
    RecordResult,
    RecordStatus,
)
from src.services.import_parser import RawStudentRecord
from src.utils.validation import InputSanitizer, PhoneNumberValidator


@pytest.fixture
def mock_db():
    """Create a mock DynamoDB client."""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """Create a BulkImportService with real validator/sanitizer and mock DB client."""
    return BulkImportService(
        dynamodb_client=mock_db,
        phone_validator=PhoneNumberValidator(),
        input_sanitizer=InputSanitizer(),
    )


def _record(**overrides) -> RawStudentRecord:
    """Helper to create a valid RawStudentRecord."""
    defaults = dict(
        line_number=1,
        name="João Silva",
        phone_number="+5511999999999",
        email="joao@email.com",
        training_goal="Perder peso",
    )
    defaults.update(overrides)
    return RawStudentRecord(**defaults)


class TestNewRecordPersistence:
    """Tests for persisting brand-new student records."""

    def test_single_new_record_creates_student_and_link(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=1)]

        results = service._batch_persist("trainer-1", records)

        assert len(results) == 1
        assert results[0].status == RecordStatus.SUCCESS
        assert results[0].student_id is not None
        assert results[0].name == "João Silva"
        assert results[0].phone_number == "+5511999999999"

        # Should have been called with 2 items (Student + TrainerStudentLink)
        items = mock_db.batch_write_items.call_args[0][0]
        assert len(items) == 2
        pks = {item["PK"] for item in items}
        assert any(pk.startswith("STUDENT#") for pk in pks)
        assert any(pk.startswith("TRAINER#") for pk in pks)

    def test_new_record_student_entity_has_correct_fields(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(
            line_number=1,
            payment_due_day="15",
            monthly_fee="150.00",
            plan_start_date="2024-06",
        )]

        results = service._batch_persist("trainer-1", records)

        items = mock_db.batch_write_items.call_args[0][0]
        student_item = next(i for i in items if i["SK"] == "METADATA")
        assert student_item["name"] == "João Silva"
        assert student_item["email"] == "joao@email.com"
        assert student_item["phone_number"] == "+5511999999999"
        assert student_item["training_goal"] == "Perder peso"
        assert student_item["payment_due_day"] == 15
        assert student_item["monthly_fee"] == "150.00"
        assert student_item["plan_start_date"] == "2024-06"
        assert student_item["currency"] == "BRL"

    def test_new_record_link_entity_has_active_status(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=1)]

        service._batch_persist("trainer-1", records)

        items = mock_db.batch_write_items.call_args[0][0]
        link_item = next(i for i in items if i["SK"].startswith("STUDENT#"))
        assert link_item["PK"] == "TRAINER#trainer-1"
        assert link_item["status"] == "active"
        assert link_item["entity_type"] == "TRAINER_STUDENT_LINK"

    def test_optional_fields_omitted_when_empty(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=1)]

        service._batch_persist("trainer-1", records)

        items = mock_db.batch_write_items.call_args[0][0]
        student_item = next(i for i in items if i["SK"] == "METADATA")
        assert "payment_due_day" not in student_item
        assert "monthly_fee" not in student_item
        assert "plan_start_date" not in student_item

    def test_empty_string_optional_fields_omitted(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(
            line_number=1,
            payment_due_day="",
            monthly_fee="",
            plan_start_date="",
        )]

        service._batch_persist("trainer-1", records)

        items = mock_db.batch_write_items.call_args[0][0]
        student_item = next(i for i in items if i["SK"] == "METADATA")
        assert "payment_due_day" not in student_item
        assert "monthly_fee" not in student_item
        assert "plan_start_date" not in student_item


class TestLinkedExistingRecords:
    """Tests for LINKED_EXISTING records (only TrainerStudentLink created)."""

    def test_linked_existing_creates_only_link(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=3)]
        existing_ids = {3: "existing-student-id"}
        linked_lines = {3}

        results = service._batch_persist(
            "trainer-1", records,
            existing_student_ids=existing_ids,
            linked_existing_lines=linked_lines,
        )

        assert len(results) == 1
        assert results[0].status == RecordStatus.LINKED_EXISTING
        assert results[0].student_id == "existing-student-id"

        # Only 1 item (TrainerStudentLink), no Student entity
        items = mock_db.batch_write_items.call_args[0][0]
        assert len(items) == 1
        assert items[0]["PK"] == "TRAINER#trainer-1"
        assert items[0]["SK"] == "STUDENT#existing-student-id"
        assert items[0]["status"] == "active"

    def test_mixed_new_and_linked_existing(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [
            _record(line_number=1, name="New Student", phone_number="+5511111111111"),
            _record(line_number=2, name="Existing Student", phone_number="+5522222222222"),
        ]
        existing_ids = {2: "existing-id-2"}
        linked_lines = {2}

        results = service._batch_persist(
            "trainer-1", records,
            existing_student_ids=existing_ids,
            linked_existing_lines=linked_lines,
        )

        assert len(results) == 2
        assert results[0].status == RecordStatus.SUCCESS
        assert results[1].status == RecordStatus.LINKED_EXISTING
        assert results[1].student_id == "existing-id-2"

        # 3 items total: Student + Link for new, Link for existing
        items = mock_db.batch_write_items.call_args[0][0]
        assert len(items) == 3


class TestChunking:
    """Tests for batch chunking into groups of 25 items."""

    def test_large_batch_is_chunked(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        # 13 new records = 26 items (2 each) -> 2 chunks (25 + 1)
        records = [
            _record(line_number=i, phone_number=f"+551199900{i:04d}")
            for i in range(1, 14)
        ]

        service._batch_persist("trainer-1", records)

        assert mock_db.batch_write_items.call_count == 2
        first_chunk = mock_db.batch_write_items.call_args_list[0][0][0]
        second_chunk = mock_db.batch_write_items.call_args_list[1][0][0]
        assert len(first_chunk) == 25
        assert len(second_chunk) == 1

    def test_exactly_25_items_single_chunk(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        # 12 new records = 24 items, + 1 linked_existing = 25 items total
        records = [
            _record(line_number=i, phone_number=f"+551199900{i:04d}")
            for i in range(1, 14)
        ]
        existing_ids = {13: "existing-id"}
        linked_lines = {13}

        service._batch_persist(
            "trainer-1", records,
            existing_student_ids=existing_ids,
            linked_existing_lines=linked_lines,
        )

        assert mock_db.batch_write_items.call_count == 1
        items = mock_db.batch_write_items.call_args[0][0]
        assert len(items) == 25

    def test_empty_records_no_writes(self, service, mock_db):
        results = service._batch_persist("trainer-1", [])

        assert results == []
        mock_db.batch_write_items.assert_not_called()


class TestRetryLogic:
    """Tests for retry with exponential backoff on batch write failures."""

    @patch("src.services.bulk_import_service.time.sleep")
    def test_retry_on_failure_then_success(self, mock_sleep, service, mock_db):
        # Fail twice, succeed on third attempt
        mock_db.batch_write_items.side_effect = [False, False, True]
        records = [_record(line_number=1)]

        results = service._batch_persist("trainer-1", records)

        assert results[0].status == RecordStatus.SUCCESS
        assert mock_db.batch_write_items.call_count == 3
        # Backoff: sleep(1), sleep(2)
        assert mock_sleep.call_args_list == [call(1), call(2)]

    @patch("src.services.bulk_import_service.time.sleep")
    def test_all_retries_exhausted_marks_persistence_failed(self, mock_sleep, service, mock_db):
        # Fail all 3 attempts
        mock_db.batch_write_items.return_value = False
        records = [_record(line_number=1)]

        results = service._batch_persist("trainer-1", records)

        assert results[0].status == RecordStatus.PERSISTENCE_FAILED
        assert results[0].error is not None
        assert mock_db.batch_write_items.call_count == 3
        # Backoff: sleep(1), sleep(2), sleep(4)
        assert mock_sleep.call_args_list == [call(1), call(2), call(4)]

    @patch("src.services.bulk_import_service.time.sleep")
    def test_partial_chunk_failure(self, mock_sleep, service, mock_db):
        # 13 records = 2 chunks. First chunk succeeds, second fails all retries.
        mock_db.batch_write_items.side_effect = [True, False, False, False]
        records = [
            _record(line_number=i, phone_number=f"+551199900{i:04d}")
            for i in range(1, 14)
        ]

        results = service._batch_persist("trainer-1", records)

        # First 12 records (in first chunk of 25 items = 12 students) succeed
        # 13th record (in second chunk) fails
        succeeded = [r for r in results if r.status == RecordStatus.SUCCESS]
        failed = [r for r in results if r.status == RecordStatus.PERSISTENCE_FAILED]
        assert len(succeeded) == 12
        assert len(failed) == 1
        assert failed[0].line_number == 13

    @patch("src.services.bulk_import_service.time.sleep")
    def test_first_attempt_success_no_sleep(self, mock_sleep, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=1)]

        results = service._batch_persist("trainer-1", records)

        assert results[0].status == RecordStatus.SUCCESS
        mock_sleep.assert_not_called()


class TestResultMapping:
    """Tests for correct result mapping back to records."""

    def test_results_preserve_record_order(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [
            _record(line_number=5, name="Alice", phone_number="+5511111111111"),
            _record(line_number=2, name="Bob", phone_number="+5522222222222"),
            _record(line_number=8, name="Carol", phone_number="+5533333333333"),
        ]

        results = service._batch_persist("trainer-1", records)

        assert [r.line_number for r in results] == [5, 2, 8]
        assert [r.name for r in results] == ["Alice", "Bob", "Carol"]

    def test_each_new_record_gets_unique_student_id(self, service, mock_db):
        mock_db.batch_write_items.return_value = True
        records = [
            _record(line_number=1, phone_number="+5511111111111"),
            _record(line_number=2, phone_number="+5522222222222"),
        ]

        results = service._batch_persist("trainer-1", records)

        ids = [r.student_id for r in results]
        assert ids[0] != ids[1]
        assert all(sid is not None for sid in ids)

    def test_defaults_none_for_existing_student_ids(self, service, mock_db):
        """Calling without existing_student_ids/linked_existing_lines works."""
        mock_db.batch_write_items.return_value = True
        records = [_record(line_number=1)]

        results = service._batch_persist("trainer-1", records)

        assert len(results) == 1
        assert results[0].status == RecordStatus.SUCCESS
