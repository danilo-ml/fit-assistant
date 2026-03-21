"""Unit tests for ImportParser.detect_format method."""

import pytest

from src.services.import_parser import ImportFormat, ImportParser


@pytest.fixture
def parser():
    return ImportParser()


class TestDetectFormatGoogleSheets:
    """Google Sheets URL detection (highest priority)."""

    def test_google_sheets_url_with_import_keyword(self, parser):
        body = "importar https://docs.google.com/spreadsheets/d/abc123/edit"
        assert parser.detect_format(body, []) == ImportFormat.GOOGLE_SHEETS

    def test_google_sheets_url_with_english_keyword(self, parser):
        body = "import https://docs.google.com/spreadsheets/d/abc123"
        assert parser.detect_format(body, []) == ImportFormat.GOOGLE_SHEETS

    def test_google_sheets_url_case_insensitive_keyword(self, parser):
        body = "IMPORTAR https://docs.google.com/spreadsheets/d/abc123"
        assert parser.detect_format(body, []) == ImportFormat.GOOGLE_SHEETS

    def test_google_sheets_url_without_keyword_returns_none(self, parser):
        body = "check this https://docs.google.com/spreadsheets/d/abc123"
        assert parser.detect_format(body, []) is None

    def test_google_sheets_takes_priority_over_csv(self, parser):
        body = "importar https://docs.google.com/spreadsheets/d/abc123"
        media = ["https://example.com/file.csv"]
        assert parser.detect_format(body, media) == ImportFormat.GOOGLE_SHEETS


class TestDetectFormatCSV:
    """CSV media attachment detection (second priority)."""

    def test_csv_with_import_keyword(self, parser):
        body = "importar alunos"
        media = ["https://example.com/file.csv"]
        assert parser.detect_format(body, media) == ImportFormat.CSV

    def test_csv_with_english_keyword(self, parser):
        body = "import students file"
        media = ["https://example.com/file.csv"]
        assert parser.detect_format(body, media) == ImportFormat.CSV

    def test_csv_case_insensitive_keyword(self, parser):
        body = "IMPORT this"
        media = ["https://example.com/file.csv"]
        assert parser.detect_format(body, media) == ImportFormat.CSV

    def test_csv_media_without_keyword_returns_none(self, parser):
        body = "here is a file"
        media = ["https://example.com/file.csv"]
        assert parser.detect_format(body, []) is None

    def test_empty_media_list_no_csv(self, parser):
        body = "importar something"
        assert parser.detect_format(body, []) is None


class TestDetectFormatStructuredText:
    """Structured text prefix detection (lowest priority)."""

    def test_importar_alunos_prefix(self, parser):
        body = "importar alunos\nJoão;+55119;j@e.com;goal"
        assert parser.detect_format(body, []) == ImportFormat.STRUCTURED_TEXT

    def test_import_students_prefix(self, parser):
        body = "import students\nJohn;+1555;j@e.com;goal"
        assert parser.detect_format(body, []) == ImportFormat.STRUCTURED_TEXT

    def test_case_insensitive_prefix(self, parser):
        body = "IMPORTAR ALUNOS\nJoão;+55119;j@e.com;goal"
        assert parser.detect_format(body, []) == ImportFormat.STRUCTURED_TEXT

    def test_mixed_case_prefix(self, parser):
        body = "Import Students\nJohn;+1555;j@e.com;goal"
        assert parser.detect_format(body, []) == ImportFormat.STRUCTURED_TEXT


class TestDetectFormatNone:
    """Cases that should return None."""

    def test_empty_message(self, parser):
        assert parser.detect_format("", []) is None

    def test_random_message(self, parser):
        assert parser.detect_format("hello world", []) is None

    def test_partial_prefix(self, parser):
        assert parser.detect_format("importar", []) is None

    def test_none_body_handled(self, parser):
        assert parser.detect_format("", []) is None
