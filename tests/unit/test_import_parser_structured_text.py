"""Unit tests for ImportParser.parse_structured_text method."""

import pytest

from src.services.import_parser import ImportParser, ParseError, RawStudentRecord


@pytest.fixture
def parser():
    return ImportParser()


class TestParseStructuredTextBasic:
    """Basic parsing of valid structured text messages."""

    def test_single_student_with_portuguese_prefix(self, parser):
        body = "importar alunos\nJoão Silva;+5511999999999;joao@email.com;Perder peso"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert len(errors) == 0
        assert records[0].name == "João Silva"
        assert records[0].phone_number == "+5511999999999"
        assert records[0].email == "joao@email.com"
        assert records[0].training_goal == "Perder peso"
        assert records[0].line_number == 1

    def test_single_student_with_english_prefix(self, parser):
        body = "import students\nJohn Doe;+15551234567;john@email.com;Lose weight"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert len(errors) == 0
        assert records[0].name == "John Doe"

    def test_multiple_students(self, parser):
        body = (
            "importar alunos\n"
            "João Silva;+5511999999999;joao@email.com;Perder peso\n"
            "Maria Santos;+5511888888888;maria@email.com;Ganhar massa muscular"
        )
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 2
        assert len(errors) == 0
        assert records[0].line_number == 1
        assert records[1].line_number == 2
        assert records[0].name == "João Silva"
        assert records[1].name == "Maria Santos"

    def test_case_insensitive_prefix(self, parser):
        body = "IMPORTAR ALUNOS\nJoão;+5511999;joao@e.com;Goal"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert len(errors) == 0


class TestParseStructuredTextOptionalFields:
    """Parsing with optional fields (payment_due_day, monthly_fee, plan_start_date)."""

    def test_with_payment_due_day(self, parser):
        body = "importar alunos\nJoão;+5511999;joao@e.com;Goal;10"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert records[0].payment_due_day == "10"
        assert records[0].monthly_fee is None
        assert records[0].plan_start_date is None

    def test_with_all_optional_fields(self, parser):
        body = "importar alunos\nJoão;+5511999;joao@e.com;Goal;10;150.00;2024-01"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert records[0].payment_due_day == "10"
        assert records[0].monthly_fee == "150.00"
        assert records[0].plan_start_date == "2024-01"

    def test_empty_optional_fields_become_none(self, parser):
        body = "importar alunos\nJoão;+5511999;joao@e.com;Goal;;;"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert records[0].payment_due_day is None
        assert records[0].monthly_fee is None
        assert records[0].plan_start_date is None


class TestParseStructuredTextErrors:
    """Error handling for malformed lines."""

    def test_line_with_fewer_than_4_fields(self, parser):
        body = "importar alunos\nJoão;+5511999;joao@e.com"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 0
        assert len(errors) == 1
        assert errors[0].line_number == 1
        assert "formato inválido" in errors[0].message

    def test_mixed_valid_and_invalid_lines(self, parser):
        body = (
            "importar alunos\n"
            "João;+5511999;joao@e.com;Goal\n"
            "BadLine;only two\n"
            "Maria;+5511888;maria@e.com;Goal2"
        )
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 2
        assert len(errors) == 1
        assert errors[0].line_number == 2
        assert records[0].line_number == 1
        assert records[1].line_number == 3

    def test_single_field_line(self, parser):
        body = "importar alunos\njust-a-name"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 0
        assert len(errors) == 1


class TestParseStructuredTextEdgeCases:
    """Edge cases and whitespace handling."""

    def test_empty_lines_are_skipped(self, parser):
        body = (
            "importar alunos\n"
            "\n"
            "João;+5511999;joao@e.com;Goal\n"
            "\n"
            "Maria;+5511888;maria@e.com;Goal2\n"
            "\n"
        )
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 2
        assert records[0].line_number == 1
        assert records[1].line_number == 2

    def test_whitespace_stripped_from_fields(self, parser):
        body = "importar alunos\n  João Silva ; +5511999 ; joao@e.com ; Perder peso "
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert records[0].name == "João Silva"
        assert records[0].phone_number == "+5511999"
        assert records[0].email == "joao@e.com"
        assert records[0].training_goal == "Perder peso"

    def test_only_prefix_no_data(self, parser):
        body = "importar alunos"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 0
        assert len(errors) == 0

    def test_prefix_with_only_empty_lines(self, parser):
        body = "importar alunos\n\n\n"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 0
        assert len(errors) == 0

    def test_empty_message(self, parser):
        records, errors = parser.parse_structured_text("")
        assert len(records) == 0
        assert len(errors) == 0

    def test_whitespace_only_lines_skipped(self, parser):
        body = "importar alunos\n   \nJoão;+5511999;joao@e.com;Goal"
        records, errors = parser.parse_structured_text(body)
        assert len(records) == 1
        assert records[0].line_number == 1
