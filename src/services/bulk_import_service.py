"""Bulk Import Service module for bulk student import.

Orchestrates validation, duplicate detection, persistence, and report
generation for bulk student import operations.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from models.dynamodb_client import DynamoDBClient
from models.entities import Student, TrainerStudentLink
from services.import_parser import RawStudentRecord
from utils.validation import InputSanitizer, PhoneNumberValidator

logger = logging.getLogger(__name__)


class RecordStatus(Enum):
    """Status of a single record in a bulk import batch."""
    SUCCESS = "success"
    ALREADY_LINKED = "already_linked"
    LINKED_EXISTING = "linked_existing"
    PHONE_IS_TRAINER = "phone_registered_as_trainer"
    DUPLICATE_IN_BATCH = "duplicate_in_batch"
    VALIDATION_FAILED = "validation_failed"
    PERSISTENCE_FAILED = "persistence_failed"


@dataclass
class RecordResult:
    """Result of processing a single student record."""
    line_number: int
    name: Optional[str]
    phone_number: Optional[str]
    status: RecordStatus
    error: Optional[str] = None
    student_id: Optional[str] = None


@dataclass
class ImportResult:
    """Aggregate result of a bulk import operation."""
    total: int
    succeeded: int
    skipped: int
    failed: int
    results: List[RecordResult] = field(default_factory=list)


class BulkImportService:
    """Orchestrates bulk student import: validation, dedup, persist, report."""

    MAX_BATCH_SIZE = 50
    DYNAMO_BATCH_SIZE = 25
    MAX_RETRIES = 3

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        phone_validator: PhoneNumberValidator,
        input_sanitizer: InputSanitizer,
    ):
        self.dynamodb_client = dynamodb_client
        self.phone_validator = phone_validator
        self.input_sanitizer = input_sanitizer

    def validate_and_import(
        self, trainer_id: str, records: List[RawStudentRecord]
    ) -> ImportResult:
        """Full pipeline: validate -> deduplicate -> persist -> return results."""
        total = len(records)

        # Reject batch if > MAX_BATCH_SIZE records
        if total > self.MAX_BATCH_SIZE:
            error_msg = (
                f"Limite excedido: máximo de {self.MAX_BATCH_SIZE} alunos "
                f"por importação. Seu arquivo contém {total} registros."
            )
            results = [
                RecordResult(
                    line_number=r.line_number,
                    name=r.name,
                    phone_number=r.phone_number,
                    status=RecordStatus.VALIDATION_FAILED,
                    error=error_msg,
                )
                for r in records
            ]
            return ImportResult(
                total=total,
                succeeded=0,
                skipped=0,
                failed=total,
                results=results,
            )

        # Run validation on all records, collect errors
        # Maps line_number -> list of error messages
        validation_errors: Dict[int, List[str]] = {}
        for record in records:
            errors = self._validate_record(record)
            if errors:
                validation_errors[record.line_number] = errors

        # Build results dict keyed by line_number to preserve original order
        results_map: Dict[int, RecordResult] = {}

        # Mark validation failures
        for record in records:
            if record.line_number in validation_errors:
                results_map[record.line_number] = RecordResult(
                    line_number=record.line_number,
                    name=record.name,
                    phone_number=record.phone_number,
                    status=RecordStatus.VALIDATION_FAILED,
                    error="; ".join(validation_errors[record.line_number]),
                )

        # Collect valid records
        valid_records = [
            r for r in records if r.line_number not in validation_errors
        ]

        # If all records fail validation, return immediately (skip DB writes)
        if not valid_records:
            return ImportResult(
                total=total,
                succeeded=0,
                skipped=0,
                failed=total,
                results=[results_map[r.line_number] for r in records],
            )

        # Run duplicate detection on valid records
        duplicates, existing_student_ids = self._detect_duplicates(
            trainer_id, valid_records
        )

        # Classify duplicates into skipped vs linked_existing
        skipped_statuses = {
            RecordStatus.ALREADY_LINKED,
            RecordStatus.PHONE_IS_TRAINER,
            RecordStatus.DUPLICATE_IN_BATCH,
        }

        linked_existing_lines: Set[int] = set()
        records_to_persist: List[RawStudentRecord] = []

        for record in valid_records:
            line = record.line_number
            if line in duplicates:
                dup_status = duplicates[line]
                if dup_status in skipped_statuses:
                    results_map[line] = RecordResult(
                        line_number=line,
                        name=record.name,
                        phone_number=record.phone_number,
                        status=dup_status,
                    )
                elif dup_status == RecordStatus.LINKED_EXISTING:
                    linked_existing_lines.add(line)
                    records_to_persist.append(record)
            else:
                # New record — needs full persistence
                records_to_persist.append(record)

        # Persist valid non-duplicate records (new + LINKED_EXISTING)
        if records_to_persist:
            persist_results = self._batch_persist(
                trainer_id,
                records_to_persist,
                existing_student_ids=existing_student_ids,
                linked_existing_lines=linked_existing_lines,
            )
            for pr in persist_results:
                results_map[pr.line_number] = pr

        # Assemble final results in original order
        all_results = [results_map[r.line_number] for r in records]

        # Compute counts
        succeeded = sum(
            1
            for r in all_results
            if r.status in (RecordStatus.SUCCESS, RecordStatus.LINKED_EXISTING)
        )
        skipped = sum(
            1 for r in all_results if r.status in skipped_statuses
        )
        failed = sum(
            1
            for r in all_results
            if r.status
            in (RecordStatus.VALIDATION_FAILED, RecordStatus.PERSISTENCE_FAILED)
        )

        return ImportResult(
            total=total,
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
            results=all_results,
        )

    # Regex for YYYY-MM format validation
    _PLAN_DATE_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

    def _validate_record(self, record: RawStudentRecord) -> List[str]:
        """Validate a single record. Returns list of error messages (empty = valid).

        Sanitizes all string fields in-place and normalizes phone numbers
        so downstream code uses clean data.
        """
        errors: List[str] = []

        # --- Sanitize all string fields in-place ---
        if record.name is not None:
            record.name = self.input_sanitizer.sanitize_string(record.name)
        if record.phone_number is not None:
            record.phone_number = self.input_sanitizer.sanitize_string(record.phone_number)
        if record.email is not None:
            record.email = self.input_sanitizer.sanitize_string(record.email)
        if record.training_goal is not None:
            record.training_goal = self.input_sanitizer.sanitize_string(record.training_goal)
        if record.payment_due_day is not None:
            record.payment_due_day = self.input_sanitizer.sanitize_string(record.payment_due_day)
        if record.monthly_fee is not None:
            record.monthly_fee = self.input_sanitizer.sanitize_string(record.monthly_fee)
        if record.plan_start_date is not None:
            record.plan_start_date = self.input_sanitizer.sanitize_string(record.plan_start_date)

        # --- Validate name (>= 2 characters) ---
        if not record.name or len(record.name) < 2:
            errors.append("Nome deve ter pelo menos 2 caracteres")

        # --- Validate phone_number (E.164, with normalization attempt) ---
        if not record.phone_number:
            errors.append("Telefone é obrigatório")
        else:
            phone = record.phone_number
            if self.phone_validator.validate(phone):
                # Already valid E.164
                pass
            elif not phone.startswith("+"):
                # Attempt normalization by prepending "+"
                candidate = "+" + phone
                if self.phone_validator.validate(candidate):
                    record.phone_number = candidate
                else:
                    errors.append("Telefone inválido (formato E.164)")
            else:
                errors.append("Telefone inválido (formato E.164)")

        # --- Validate email (must contain "@" and ".") ---
        if not record.email or "@" not in record.email or "." not in record.email:
            errors.append("Email inválido (deve conter '@' e '.')")

        # --- Validate training_goal (non-empty) ---
        if not record.training_goal:
            errors.append("Objetivo de treino é obrigatório")

        # --- Validate optional fields ---

        # payment_due_day: integer between 1 and 31
        if record.payment_due_day is not None and record.payment_due_day != "":
            try:
                day = int(record.payment_due_day)
                if day < 1 or day > 31:
                    errors.append("Dia de vencimento deve ser entre 1 e 31")
            except (ValueError, TypeError):
                errors.append("Dia de vencimento deve ser um número inteiro entre 1 e 31")

        # monthly_fee: positive number with at most 2 decimal places
        if record.monthly_fee is not None and record.monthly_fee != "":
            try:
                fee = float(record.monthly_fee)
                if fee <= 0:
                    errors.append("Mensalidade deve ser um valor positivo")
                else:
                    # Check at most 2 decimal places
                    parts = record.monthly_fee.split(".")
                    if len(parts) == 2 and len(parts[1]) > 2:
                        errors.append("Mensalidade deve ter no máximo 2 casas decimais")
            except (ValueError, TypeError):
                errors.append("Mensalidade deve ser um número válido")

        # plan_start_date: YYYY-MM format
        if record.plan_start_date is not None and record.plan_start_date != "":
            if not self._PLAN_DATE_PATTERN.match(record.plan_start_date):
                errors.append("Data de início deve estar no formato AAAA-MM")

        return errors

    def _detect_duplicates(
        self, trainer_id: str, records: List[RawStudentRecord]
    ) -> Tuple[Dict[int, RecordStatus], Dict[int, str]]:
        """Check phone numbers against DynamoDB and within-batch duplicates.

        Returns a tuple of:
          - dict mapping line_number -> RecordStatus for non-new records
          - dict mapping line_number -> existing student_id for LINKED_EXISTING records
        """
        duplicates: Dict[int, RecordStatus] = {}
        existing_student_ids: Dict[int, str] = {}
        seen_phones: set = set()

        for record in records:
            phone = record.phone_number
            line = record.line_number

            # Within-batch duplicate check (only first occurrence is processed)
            if phone in seen_phones:
                duplicates[line] = RecordStatus.DUPLICATE_IN_BATCH
                continue
            seen_phones.add(phone)

            # Look up phone number in DynamoDB
            lookup = self.dynamodb_client.lookup_by_phone_number(phone)
            if lookup is None:
                # New record — not added to duplicates dict
                continue

            entity_type = lookup.get("entity_type")

            if entity_type == "TRAINER":
                duplicates[line] = RecordStatus.PHONE_IS_TRAINER
            elif entity_type == "STUDENT":
                student_id = lookup["student_id"]
                link = self.dynamodb_client.get_trainer_student_link(
                    trainer_id, student_id
                )
                if link and link.get("status") == "active":
                    duplicates[line] = RecordStatus.ALREADY_LINKED
                else:
                    duplicates[line] = RecordStatus.LINKED_EXISTING
                    existing_student_ids[line] = student_id

        return duplicates, existing_student_ids

    def _batch_persist(
        self,
        trainer_id: str,
        valid_records: List[RawStudentRecord],
        existing_student_ids: Dict[int, str] = None,
        linked_existing_lines: Set[int] = None,
    ) -> List[RecordResult]:
        """Persist records using DynamoDB batch_write_items in chunks of 25.

        For new records: creates Student + TrainerStudentLink (2 items each).
        For LINKED_EXISTING records: creates only TrainerStudentLink (1 item).

        Chunks items into groups of up to 25 and retries failed chunks
        up to MAX_RETRIES times with exponential backoff (1s, 2s, 4s).
        """
        if existing_student_ids is None:
            existing_student_ids = {}
        if linked_existing_lines is None:
            linked_existing_lines = set()

        # Build DynamoDB items and track which record each item belongs to.
        # items_with_owner: list of (dynamodb_item_dict, record_line_number)
        items_with_owner: List[tuple] = []
        # Map line_number -> (RecordResult, student_id) for building results
        record_map: Dict[int, RecordResult] = {}

        for record in valid_records:
            line = record.line_number
            is_linked_existing = line in linked_existing_lines

            if is_linked_existing:
                # Only create TrainerStudentLink for existing students
                student_id = existing_student_ids[line]
                link = TrainerStudentLink(
                    trainer_id=trainer_id,
                    student_id=student_id,
                    status="active",
                )
                items_with_owner.append((link.to_dynamodb(), line))
                record_map[line] = RecordResult(
                    line_number=line,
                    name=record.name,
                    phone_number=record.phone_number,
                    status=RecordStatus.LINKED_EXISTING,
                    student_id=student_id,
                )
            else:
                # Create Student entity + TrainerStudentLink
                payment_due_day = None
                if record.payment_due_day is not None and record.payment_due_day != "":
                    payment_due_day = int(record.payment_due_day)

                monthly_fee = None
                if record.monthly_fee is not None and record.monthly_fee != "":
                    monthly_fee = Decimal(record.monthly_fee)

                plan_start_date = None
                if record.plan_start_date is not None and record.plan_start_date != "":
                    plan_start_date = record.plan_start_date

                student = Student(
                    name=record.name,
                    email=record.email,
                    phone_number=record.phone_number,
                    training_goal=record.training_goal,
                    payment_due_day=payment_due_day,
                    monthly_fee=monthly_fee,
                    plan_start_date=plan_start_date,
                )
                link = TrainerStudentLink(
                    trainer_id=trainer_id,
                    student_id=student.student_id,
                    status="active",
                )
                items_with_owner.append((student.to_dynamodb(), line))
                items_with_owner.append((link.to_dynamodb(), line))
                record_map[line] = RecordResult(
                    line_number=line,
                    name=record.name,
                    phone_number=record.phone_number,
                    status=RecordStatus.SUCCESS,
                    student_id=student.student_id,
                )

        # Chunk items into groups of DYNAMO_BATCH_SIZE (25)
        chunks: List[List[tuple]] = []
        for i in range(0, len(items_with_owner), self.DYNAMO_BATCH_SIZE):
            chunks.append(items_with_owner[i : i + self.DYNAMO_BATCH_SIZE])

        # Write each chunk with retry logic
        failed_lines: set = set()
        for chunk in chunks:
            items = [item for item, _owner in chunk]
            success = False

            for attempt in range(self.MAX_RETRIES):
                if self.dynamodb_client.batch_write_items(items):
                    success = True
                    break
                # Exponential backoff: 1s, 2s, 4s
                time.sleep(2 ** attempt)

            if not success:
                # Mark all records in this chunk as PERSISTENCE_FAILED
                for _item, owner_line in chunk:
                    failed_lines.add(owner_line)

        # Build final results
        results: List[RecordResult] = []
        for record in valid_records:
            result = record_map[record.line_number]
            if record.line_number in failed_lines:
                result.status = RecordStatus.PERSISTENCE_FAILED
                result.error = "Erro ao salvar registro no banco de dados"
            results.append(result)

        return results

    # WhatsApp message size limit
    MAX_MESSAGE_LENGTH = 4096

    # Status to emoji/label mapping
    _STATUS_DISPLAY = {
        RecordStatus.SUCCESS: ("✅", "Importado"),
        RecordStatus.LINKED_EXISTING: ("✅", "Vinculado (aluno existente)"),
        RecordStatus.ALREADY_LINKED: ("⏭️", "Já vinculado ao trainer"),
        RecordStatus.PHONE_IS_TRAINER: ("⏭️", "Telefone registrado como trainer"),
        RecordStatus.DUPLICATE_IN_BATCH: ("⏭️", "Duplicado no lote"),
    }

    def generate_report(self, result: ImportResult) -> List[str]:
        """Generate Import_Report as list of WhatsApp messages (each <= 4096 chars)."""
        # Build header section
        header = (
            "📋 Relatório de Importação\n"
            "\n"
            f"Total: {result.total} registros processados\n"
            f"✅ Importados: {result.succeeded}\n"
            f"⏭️ Ignorados: {result.skipped}\n"
            f"❌ Falhas: {result.failed}\n"
        )

        # All-success shortcut
        if result.succeeded == result.total and result.total > 0:
            header += (
                f"\n🎉 Todos os {result.total} alunos foram importados com sucesso!"
            )

        # Build detail lines
        detail_lines: List[str] = []
        for r in result.results:
            display_name = r.name if r.name else f"Linha {r.line_number}"
            phone_part = f" ({r.phone_number})" if r.phone_number else ""

            if r.status in self._STATUS_DISPLAY:
                emoji, label = self._STATUS_DISPLAY[r.status]
                detail_lines.append(
                    f"{emoji} {display_name}{phone_part} - {label}"
                )
            elif r.status == RecordStatus.VALIDATION_FAILED:
                reason = r.error or "Erro de validação"
                detail_lines.append(
                    f"❌ {display_name}{phone_part} - {reason}"
                )
            elif r.status == RecordStatus.PERSISTENCE_FAILED:
                reason = r.error or "Erro ao salvar"
                detail_lines.append(
                    f"❌ {display_name}{phone_part} - {reason}"
                )

        # Combine header + details, then split into messages
        if detail_lines:
            details_header = "\nDetalhes:\n"
            full_details = details_header + "\n".join(detail_lines)
        else:
            full_details = ""

        full_report = header + full_details

        # If it fits in one message, return as-is
        if len(full_report) <= self.MAX_MESSAGE_LENGTH:
            return [full_report]

        # Split into multiple messages at line boundaries
        return self._split_report(header, detail_lines)

    def _split_report(
        self, header: str, detail_lines: List[str]
    ) -> List[str]:
        """Split report into multiple messages, each <= MAX_MESSAGE_LENGTH chars.

        The header (summary section) goes in the first message.
        Detail lines are appended to the first message and overflow into
        subsequent messages, always splitting at line boundaries.
        """
        messages: List[str] = []
        current = header + "\nDetalhes:\n"

        for line in detail_lines:
            candidate = current + line + "\n"
            if len(candidate) > self.MAX_MESSAGE_LENGTH:
                # Current message is full — flush it
                messages.append(current.rstrip("\n"))
                current = line + "\n"
            else:
                current = candidate

        # Flush remaining content
        if current.strip():
            messages.append(current.rstrip("\n"))

        return messages

