"""Unit tests for ImportParser.parse_csv method."""

import pytest

from src.services.import_parser import ImportParser, ParseError, RawStudentRecord


@pytest.fixture
def parser():
    return ImportParser()


class TestParseCsvBasic:
    """Basic parsing of valid CSV content."""

    def test_single_row(self, parser):
        csv = "name,phone_number,email,training_goal\nJoão Silva,+5511999999999,joao@email.com,Perder peso"
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert len(errors) == 0
        assert records[0].name == "João Silva"
        assert records[0].phone_number == "+5511999999999"
        assert records[0].email == "joao@email.com"
        assert records[0].training_goal == "Perder peso"
        assert records[0].line_number == 1

    def test_multiple_rows(self, parser):
        csv = (
            "name,phone_number,email,training_goal\n"
            "João Silva,+5511999999999,joao@email.com,Perder peso\n"
            "Maria Santos,+5511888888888,maria@email.com,Ganhar massa"
        )
        records, errors = parser.parse_csv(csv)
        assert len(records) == 2
        assert len(errors) == 0
        assert records[0].line_number == 1
        assert records[1].line_number == 2
        assert records[0].name == "João Silva"
        assert records[1].name == "Maria Santos"


class TestParseCsvOptionalColumns:
    """Parsing with optional columns."""

    def test_all_optional_columns_present(self, parser):
        csv = (
            "name,phone_number,email,training_goal,payment_due_day,monthly_fee,plan_start_date\n"
            "João,+5511999,joao@e.com,Goal,10,150.00,2024-01"
        )
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert records[0].payment_due_day == "10"
        assert records[0].monthly_fee == "150.00"
        assert records[0].plan_start_date == "2024-01"

    def test_empty_optional_fields_become_none(self, parser):
        csv = (
            "name,phone_number,email,training_goal,payment_due_day,monthly_fee,plan_start_date\n"
            "João,+5511999,joao@e.com,Goal,,,"
        )
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert records[0].payment_due_day is None
        assert records[0].monthly_fee is None
        assert records[0].plan_start_date is None

    def test_partial_optional_fields(self, parser):
        csv = (
            "name,phone_number,email,training_goal,payment_due_day\n"
            "João,+5511999,joao@e.com,Goal,15"
        )
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert records[0].payment_due_day == "15"
        assert records[0].monthly_fee is None
        assert records[0].plan_start_date is None


class TestParseCsvMissingHeaders:
    """Error handling for missing required columns."""

    def test_missing_one_required_column(self, parser):
        csv = "name,phone_number,email\nJoão,+5511999,joao@e.com"
        records, errors = parser.parse_csv(csv)
        assert len(records) == 0
        assert len(errors) == 1
        assert "training_goal" in errors[0].message
        assert "colunas ausentes" in errors[0].message

    def test_missing_multiple_required_columns(self, parser):
        csv = "name,email\nJoão,joao@e.com"
        records, errors = parser.parse_csv(csv)
        assert len(records) == 0
        assert len(errors) == 1
        assert "phone_number" in errors[0].message
        assert "training_goal" in errors[0].message

    def test_empty_csv(self, parser):
        records, errors = parser.parse_csv("")
        assert len(records) == 0
        assert len(errors) == 1
        assert errors[0].line_number == 0


class TestParseCsvRowErrors:
    """Error handling for rows with missing required values."""

    def test_row_with_empty_required_field(self, parser):
        csv = "name,phone_number,email,training_goal\nJoão,,joao@e.com,Goal"
        records, errors = parser.parse_csv(csv)
        assert len(records) == 0
        assert len(errors) == 1
        assert errors[0].line_number == 1
        assert "phone_number" in errors[0].message

    def test_mixed_valid_and_invalid_rows(self, parser):
        csv = (
            "name,phone_number,email,training_goal\n"
            "João,+5511999,joao@e.com,Goal\n"
            ",,maria@e.com,\n"
            "Pedro,+5511777,pedro@e.com,Strength"
        )
        records, errors = parser.parse_csv(csv)
        assert len(records) == 2
        assert len(errors) == 1
        assert errors[0].line_number == 2
        assert records[0].line_number == 1
        assert records[1].line_number == 3


class TestParseCsvWhitespace:
    """Whitespace handling."""

    def test_whitespace_stripped_from_values(self, parser):
        csv = "name,phone_number,email,training_goal\n  João Silva , +5511999 , joao@e.com , Perder peso "
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert records[0].name == "João Silva"
        assert records[0].phone_number == "+5511999"
        assert records[0].email == "joao@e.com"
        assert records[0].training_goal == "Perder peso"

    def test_whitespace_in_header_names(self, parser):
        csv = " name , phone_number , email , training_goal \nJoão,+5511999,joao@e.com,Goal"
        records, errors = parser.parse_csv(csv)
        assert len(records) == 1
        assert records[0].name == "João"
