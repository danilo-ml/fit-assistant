"""Unit tests for ImportParser.format_structured_text and format_csv methods."""

import pytest

from src.services.import_parser import ImportParser


@pytest.fixture
def parser():
    return ImportParser()


class TestFormatStructuredText:
    """Tests for format_structured_text method."""

    def test_single_record_required_fields_only(self, parser):
        records = [
            {"name": "João Silva", "phone_number": "+5511999999999",
             "email": "joao@email.com", "training_goal": "Perder peso"}
        ]
        result = parser.format_structured_text(records)
        assert result == (
            "importar alunos\n"
            "João Silva;+5511999999999;joao@email.com;Perder peso"
        )

    def test_multiple_records(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com", "training_goal": "Goal1"},
            {"name": "Maria", "phone_number": "+5511888", "email": "m@e.com", "training_goal": "Goal2"},
        ]
        result = parser.format_structured_text(records)
        lines = result.split("\n")
        assert lines[0] == "importar alunos"
        assert lines[1] == "João;+5511999;j@e.com;Goal1"
        assert lines[2] == "Maria;+5511888;m@e.com;Goal2"

    def test_with_all_optional_fields(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": "10",
             "monthly_fee": "150.00", "plan_start_date": "2024-01"}
        ]
        result = parser.format_structured_text(records)
        assert result == "importar alunos\nJoão;+5511999;j@e.com;Goal;10;150.00;2024-01"

    def test_with_partial_optional_fields(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": "10"}
        ]
        result = parser.format_structured_text(records)
        assert result == "importar alunos\nJoão;+5511999;j@e.com;Goal;10"

    def test_optional_fields_none_not_included(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": None,
             "monthly_fee": None, "plan_start_date": None}
        ]
        result = parser.format_structured_text(records)
        assert result == "importar alunos\nJoão;+5511999;j@e.com;Goal"

    def test_empty_records_list(self, parser):
        result = parser.format_structured_text([])
        assert result == "importar alunos"

    def test_round_trip_required_fields(self, parser):
        records = [
            {"name": "João Silva", "phone_number": "+5511999999999",
             "email": "joao@email.com", "training_goal": "Perder peso"}
        ]
        text = parser.format_structured_text(records)
        parsed, errors = parser.parse_structured_text(text)
        assert len(errors) == 0
        assert len(parsed) == 1
        assert parsed[0].name == "João Silva"
        assert parsed[0].phone_number == "+5511999999999"
        assert parsed[0].email == "joao@email.com"
        assert parsed[0].training_goal == "Perder peso"

    def test_round_trip_with_optional_fields(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": "10",
             "monthly_fee": "150.00", "plan_start_date": "2024-01"}
        ]
        text = parser.format_structured_text(records)
        parsed, errors = parser.parse_structured_text(text)
        assert len(errors) == 0
        assert len(parsed) == 1
        assert parsed[0].payment_due_day == "10"
        assert parsed[0].monthly_fee == "150.00"
        assert parsed[0].plan_start_date == "2024-01"


class TestFormatCsv:
    """Tests for format_csv method."""

    def test_single_record_required_fields_only(self, parser):
        records = [
            {"name": "João Silva", "phone_number": "+5511999999999",
             "email": "joao@email.com", "training_goal": "Perder peso"}
        ]
        result = parser.format_csv(records)
        lines = result.strip().splitlines()
        assert lines[0] == "name,phone_number,email,training_goal"
        assert lines[1] == "João Silva,+5511999999999,joao@email.com,Perder peso"

    def test_optional_columns_included_when_any_record_has_value(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": "10"},
            {"name": "Maria", "phone_number": "+5511888", "email": "m@e.com",
             "training_goal": "Goal2"},
        ]
        result = parser.format_csv(records)
        lines = result.strip().splitlines()
        assert "payment_due_day" in lines[0]
        assert "monthly_fee" not in lines[0]

    def test_all_optional_columns(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal", "payment_due_day": "10",
             "monthly_fee": "150.00", "plan_start_date": "2024-01"}
        ]
        result = parser.format_csv(records)
        lines = result.strip().splitlines()
        assert lines[0] == "name,phone_number,email,training_goal,payment_due_day,monthly_fee,plan_start_date"

    def test_no_optional_columns_when_none_have_values(self, parser):
        records = [
            {"name": "João", "phone_number": "+5511999", "email": "j@e.com",
             "training_goal": "Goal"}
        ]
        result = parser.format_csv(records)
        lines = result.strip().splitlines()
        assert lines[0] == "name,phone_number,email,training_goal"

    def test_round_trip_csv(self, parser):
        records = [
            {"name": "João Silva", "phone_number": "+5511999999999",
             "email": "joao@email.com", "training_goal": "Perder peso",
             "payment_due_day": "10", "monthly_fee": "150.00",
             "plan_start_date": "2024-01"}
        ]
        csv_str = parser.format_csv(records)
        parsed, errors = parser.parse_csv(csv_str)
        assert len(errors) == 0
        assert len(parsed) == 1
        assert parsed[0].name == "João Silva"
        assert parsed[0].phone_number == "+5511999999999"
        assert parsed[0].email == "joao@email.com"
        assert parsed[0].training_goal == "Perder peso"
        assert parsed[0].payment_due_day == "10"
        assert parsed[0].monthly_fee == "150.00"
        assert parsed[0].plan_start_date == "2024-01"

    def test_empty_records_list(self, parser):
        result = parser.format_csv([])
        lines = result.strip().splitlines()
        assert lines[0] == "name,phone_number,email,training_goal"
        assert len(lines) == 1
