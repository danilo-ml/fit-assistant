"""Unit tests for BulkImportService._detect_duplicates method."""

from unittest.mock import MagicMock

import pytest

from src.services.bulk_import_service import BulkImportService, RecordStatus
from src.services.import_parser import RawStudentRecord


@pytest.fixture
def mock_dynamodb():
    return MagicMock()


@pytest.fixture
def service(mock_dynamodb):
    return BulkImportService(
        dynamodb_client=mock_dynamodb,
        phone_validator=MagicMock(),
        input_sanitizer=MagicMock(),
    )


def _record(line_number: int, phone: str) -> RawStudentRecord:
    return RawStudentRecord(
        line_number=line_number,
        name="Test",
        phone_number=phone,
        email="t@t.com",
        training_goal="goal",
    )


class TestDetectDuplicatesNewRecords:
    """Records not found in DB and first in batch should NOT appear in result."""

    def test_all_new_records(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        records = [_record(1, "+5511111111111"), _record(2, "+5522222222222")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {}
        assert existing_ids == {}

    def test_single_new_record(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        records = [_record(1, "+5511111111111")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {}
        assert existing_ids == {}


class TestDetectDuplicatesAlreadyLinked:
    """Student exists and has active link to this trainer."""

    def test_already_linked(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "stu1",
        }
        mock_dynamodb.get_trainer_student_link.return_value = {
            "status": "active",
        }
        records = [_record(1, "+5511111111111")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {1: RecordStatus.ALREADY_LINKED}
        assert existing_ids == {}


class TestDetectDuplicatesLinkedExisting:
    """Student exists but NOT linked to this trainer (or link inactive)."""

    def test_existing_student_no_link(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "stu1",
        }
        mock_dynamodb.get_trainer_student_link.return_value = None
        records = [_record(1, "+5511111111111")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {1: RecordStatus.LINKED_EXISTING}
        assert existing_ids == {1: "stu1"}

    def test_existing_student_inactive_link(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "stu2",
        }
        mock_dynamodb.get_trainer_student_link.return_value = {
            "status": "inactive",
        }
        records = [_record(1, "+5511111111111")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {1: RecordStatus.LINKED_EXISTING}
        assert existing_ids == {1: "stu2"}


class TestDetectDuplicatesPhoneIsTrainer:
    """Phone number belongs to a trainer entity."""

    def test_phone_is_trainer(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "TRAINER",
            "trainer_id": "other_trainer",
        }
        records = [_record(1, "+5511111111111")]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {1: RecordStatus.PHONE_IS_TRAINER}
        assert existing_ids == {}


class TestDetectDuplicatesDuplicateInBatch:
    """Same phone number appears multiple times in the batch."""

    def test_duplicate_in_batch(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        records = [
            _record(1, "+5511111111111"),
            _record(2, "+5511111111111"),
        ]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        # First occurrence is new (not in duplicates), second is DUPLICATE_IN_BATCH
        assert duplicates == {2: RecordStatus.DUPLICATE_IN_BATCH}
        assert existing_ids == {}

    def test_triple_duplicate_in_batch(self, service, mock_dynamodb):
        mock_dynamodb.lookup_by_phone_number.return_value = None
        records = [
            _record(1, "+5511111111111"),
            _record(2, "+5511111111111"),
            _record(3, "+5511111111111"),
        ]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert duplicates == {
            2: RecordStatus.DUPLICATE_IN_BATCH,
            3: RecordStatus.DUPLICATE_IN_BATCH,
        }

    def test_batch_dup_takes_priority_over_db_lookup(self, service, mock_dynamodb):
        """Second occurrence should be DUPLICATE_IN_BATCH even if phone exists in DB."""
        mock_dynamodb.lookup_by_phone_number.return_value = {
            "entity_type": "STUDENT",
            "student_id": "stu1",
        }
        mock_dynamodb.get_trainer_student_link.return_value = None
        records = [
            _record(1, "+5511111111111"),
            _record(2, "+5511111111111"),
        ]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        # First is LINKED_EXISTING, second is DUPLICATE_IN_BATCH
        assert duplicates[1] == RecordStatus.LINKED_EXISTING
        assert duplicates[2] == RecordStatus.DUPLICATE_IN_BATCH
        assert existing_ids == {1: "stu1"}


class TestDetectDuplicatesMixedBatch:
    """Batch with a mix of new, existing, trainer, and duplicate records."""

    def test_mixed_batch(self, service, mock_dynamodb):
        def lookup_side_effect(phone):
            if phone == "+5511111111111":
                return None  # new
            elif phone == "+5522222222222":
                return {"entity_type": "STUDENT", "student_id": "stu2"}
            elif phone == "+5533333333333":
                return {"entity_type": "TRAINER", "trainer_id": "t2"}
            return None

        def link_side_effect(trainer_id, student_id):
            if student_id == "stu2":
                return {"status": "active"}
            return None

        mock_dynamodb.lookup_by_phone_number.side_effect = lookup_side_effect
        mock_dynamodb.get_trainer_student_link.side_effect = link_side_effect

        records = [
            _record(1, "+5511111111111"),  # new
            _record(2, "+5522222222222"),  # already linked
            _record(3, "+5533333333333"),  # trainer phone
            _record(4, "+5511111111111"),  # dup in batch
        ]

        duplicates, existing_ids = service._detect_duplicates("trainer1", records)

        assert 1 not in duplicates  # new record
        assert duplicates[2] == RecordStatus.ALREADY_LINKED
        assert duplicates[3] == RecordStatus.PHONE_IS_TRAINER
        assert duplicates[4] == RecordStatus.DUPLICATE_IN_BATCH
        assert existing_ids == {}
