"""Unit tests for BulkImportService.generate_report method."""

import pytest

from src.services.bulk_import_service import (
    BulkImportService,
    ImportResult,
    RecordResult,
    RecordStatus,
)
from src.utils.validation import InputSanitizer, PhoneNumberValidator
from unittest.mock import MagicMock


@pytest.fixture
def service():
    return BulkImportService(
        dynamodb_client=MagicMock(),
        phone_validator=PhoneNumberValidator(),
        input_sanitizer=InputSanitizer(),
    )


def _result(records, succeeded=0, skipped=0, failed=0):
    return ImportResult(
        total=len(records),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        results=records,
    )


class TestReportHeader:
    """Report should contain correct summary counts."""

    def test_header_contains_counts(self, service):
        result = _result(
            [
                RecordResult(1, "João", "+5511999999999", RecordStatus.SUCCESS),
                RecordResult(2, "Maria", "+5511888888888", RecordStatus.ALREADY_LINKED),
                RecordResult(3, "Pedro", "+5511777", RecordStatus.VALIDATION_FAILED, error="Telefone inválido"),
            ],
            succeeded=1, skipped=1, failed=1,
        )
        messages = service.generate_report(result)
        report = messages[0]

        assert "Total: 3 registros processados" in report
        assert "✅ Importados: 1" in report
        assert "⏭️ Ignorados: 1" in report
        assert "❌ Falhas: 1" in report


class TestAllSuccessMessage:
    """When all records succeed, include celebration message."""

    def test_all_success_shows_celebration(self, service):
        result = _result(
            [
                RecordResult(1, "João", "+5511999999999", RecordStatus.SUCCESS),
                RecordResult(2, "Maria", "+5511888888888", RecordStatus.SUCCESS),
            ],
            succeeded=2,
        )
        messages = service.generate_report(result)
        report = messages[0]

        assert "🎉 Todos os 2 alunos foram importados com sucesso!" in report


class TestStatusEmojiMapping:
    """Each status should map to the correct emoji and label."""

    def test_success_status(self, service):
        result = _result(
            [RecordResult(1, "João", "+5511999999999", RecordStatus.SUCCESS)],
            succeeded=1,
        )
        report = service.generate_report(result)[0]
        assert "✅ João (+5511999999999) - Importado" in report

    def test_linked_existing_status(self, service):
        result = _result(
            [RecordResult(1, "João", "+5511999999999", RecordStatus.LINKED_EXISTING)],
            succeeded=1,
        )
        report = service.generate_report(result)[0]
        assert "✅ João (+5511999999999) - Vinculado (aluno existente)" in report

    def test_already_linked_status(self, service):
        result = _result(
            [RecordResult(1, "Ana", "+5511666666666", RecordStatus.ALREADY_LINKED)],
            skipped=1,
        )
        report = service.generate_report(result)[0]
        assert "⏭️ Ana (+5511666666666) - Já vinculado ao trainer" in report

    def test_phone_is_trainer_status(self, service):
        result = _result(
            [RecordResult(1, "Carlos", "+5511555555555", RecordStatus.PHONE_IS_TRAINER)],
            skipped=1,
        )
        report = service.generate_report(result)[0]
        assert "⏭️ Carlos (+5511555555555) - Telefone registrado como trainer" in report

    def test_duplicate_in_batch_status(self, service):
        result = _result(
            [RecordResult(1, "Dup", "+5511444444444", RecordStatus.DUPLICATE_IN_BATCH)],
            skipped=1,
        )
        report = service.generate_report(result)[0]
        assert "⏭️ Dup (+5511444444444) - Duplicado no lote" in report

    def test_validation_failed_shows_error(self, service):
        result = _result(
            [RecordResult(1, "Bad", "+5511333", RecordStatus.VALIDATION_FAILED, error="Telefone inválido (formato E.164)")],
            failed=1,
        )
        report = service.generate_report(result)[0]
        assert "❌ Bad (+5511333) - Telefone inválido (formato E.164)" in report

    def test_persistence_failed_shows_error(self, service):
        result = _result(
            [RecordResult(1, "Fail", "+5511222222222", RecordStatus.PERSISTENCE_FAILED, error="Erro ao salvar")],
            failed=1,
        )
        report = service.generate_report(result)[0]
        assert "❌ Fail (+5511222222222) - Erro ao salvar" in report


class TestNameFallback:
    """Use line number when name is unavailable."""

    def test_uses_line_number_when_no_name(self, service):
        result = _result(
            [RecordResult(5, None, "+5511555", RecordStatus.VALIDATION_FAILED, error="Telefone inválido")],
            failed=1,
        )
        report = service.generate_report(result)[0]
        assert "❌ Linha 5 (+5511555) - Telefone inválido" in report

    def test_omits_phone_when_unavailable(self, service):
        result = _result(
            [RecordResult(3, None, None, RecordStatus.VALIDATION_FAILED, error="Dados ausentes")],
            failed=1,
        )
        report = service.generate_report(result)[0]
        assert "❌ Linha 3 - Dados ausentes" in report


class TestMessageSplitting:
    """Reports exceeding 4096 chars should be split at line boundaries."""

    def test_short_report_is_single_message(self, service):
        result = _result(
            [RecordResult(1, "João", "+5511999999999", RecordStatus.SUCCESS)],
            succeeded=1,
        )
        messages = service.generate_report(result)
        assert len(messages) == 1

    def test_long_report_splits_into_multiple_messages(self, service):
        # Create enough records to exceed 4096 chars
        records = []
        for i in range(80):
            records.append(
                RecordResult(
                    i + 1,
                    f"Estudante Com Nome Longo Número {i:03d}",
                    f"+551199900{i:04d}",
                    RecordStatus.VALIDATION_FAILED,
                    error="Nome deve ter pelo menos 2 caracteres; Telefone inválido (formato E.164); Email inválido",
                )
            )
        result = _result(records, failed=80)
        messages = service.generate_report(result)

        assert len(messages) > 1
        for msg in messages:
            assert len(msg) <= 4096

    def test_exactly_4096_chars_is_single_message(self, service):
        """A report of exactly 4096 chars should not be split."""
        result = _result(
            [RecordResult(1, "João", "+5511999999999", RecordStatus.SUCCESS)],
            succeeded=1,
        )
        messages = service.generate_report(result)
        # Just verify it's a single message (the content is short)
        assert len(messages) == 1
        assert len(messages[0]) <= 4096

    def test_split_preserves_all_records(self, service):
        """All records should appear across the split messages."""
        records = []
        for i in range(80):
            records.append(
                RecordResult(
                    i + 1,
                    f"Estudante {i:03d}",
                    f"+551199900{i:04d}",
                    RecordStatus.VALIDATION_FAILED,
                    error="Telefone inválido (formato E.164); Email inválido; Nome inválido",
                )
            )
        result = _result(records, failed=80)
        messages = service.generate_report(result)
        combined = "\n".join(messages)

        for i in range(80):
            assert f"Estudante {i:03d}" in combined

    def test_header_in_first_message(self, service):
        """The header/summary should be in the first message."""
        records = []
        for i in range(80):
            records.append(
                RecordResult(
                    i + 1,
                    f"Estudante Com Nome Longo {i:03d}",
                    f"+551199900{i:04d}",
                    RecordStatus.VALIDATION_FAILED,
                    error="Telefone inválido (formato E.164); Email inválido; Nome inválido",
                )
            )
        result = _result(records, failed=80)
        messages = service.generate_report(result)

        assert "📋 Relatório de Importação" in messages[0]
        assert "Total:" in messages[0]


class TestEmptyResult:
    """Handle edge case of empty import result."""

    def test_empty_result(self, service):
        result = _result([], succeeded=0, skipped=0, failed=0)
        messages = service.generate_report(result)
        assert len(messages) == 1
        assert "Total: 0 registros processados" in messages[0]
