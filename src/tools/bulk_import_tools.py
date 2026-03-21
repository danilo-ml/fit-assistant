"""
AI agent tool function for bulk student import.

This module provides the bulk_import_students tool that the AI agent
can call to import multiple students from structured text, CSV files,
or Google Sheets links.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx
from strands import tool

from config import settings
from models.dynamodb_client import DynamoDBClient
from services.bulk_import_service import BulkImportService
from services.google_sheets_reader import (
    GoogleSheetsAccessError,
    GoogleSheetsReader,
    GoogleSheetsTimeoutError,
)
from services.import_parser import ImportFormat, ImportParser
from utils.validation import InputSanitizer, PhoneNumberValidator

logger = logging.getLogger(__name__)

# Initialize shared dependencies
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)

CSV_DOWNLOAD_TIMEOUT = 30


@tool
def bulk_import_students(
    trainer_id: str,
    message_body: str,
    media_urls: list = None,
) -> Dict[str, Any]:
    """
    Import multiple students from structured text, CSV file, or Google Sheets link.

    Use this tool when the trainer wants to register multiple students at once.
    The trainer can send student data as:
    - Structured text starting with "importar alunos" or "import students"
    - A CSV file attachment with caption containing "importar" or "import"
    - A Google Sheets link with message containing "importar" or "import"

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        message_body: The WhatsApp message text from the trainer
        media_urls: Optional list of media attachment URLs (for CSV files)

    Returns:
        dict: {
            'success': bool,
            'data': {'report': str},
            'error': str (optional, only present if success=False)
        }
    """
    if media_urls is None:
        media_urls = []

    parser = ImportParser()
    sheets_reader = GoogleSheetsReader()
    import_service = BulkImportService(
        dynamodb_client=dynamodb_client,
        phone_validator=PhoneNumberValidator(),
        input_sanitizer=InputSanitizer(),
    )

    # Detect input format
    fmt = parser.detect_format(message_body, media_urls)

    if fmt is None:
        return {
            "success": False,
            "data": {"report": ""},
            "error": (
                "Formato não reconhecido. Envie uma mensagem começando com "
                "'importar alunos', um arquivo CSV ou um link do Google Sheets."
            ),
        }

    try:
        records, parse_errors = _parse_input(
            fmt, message_body, media_urls, parser, sheets_reader
        )
    except GoogleSheetsAccessError:
        return {
            "success": False,
            "data": {"report": ""},
            "error": (
                "Não foi possível acessar a planilha. Verifique se o "
                "compartilhamento está configurado como "
                "'Qualquer pessoa com o link pode visualizar'."
            ),
        }
    except GoogleSheetsTimeoutError:
        return {
            "success": False,
            "data": {"report": ""},
            "error": (
                "Tempo limite excedido ao acessar a planilha. "
                "Tente novamente em alguns instantes."
            ),
        }
    except _CsvDownloadError as exc:
        return {
            "success": False,
            "data": {"report": ""},
            "error": str(exc),
        }

    # If parsing produced only errors and no records, report them
    if not records and parse_errors:
        error_lines = [e.message for e in parse_errors]
        return {
            "success": False,
            "data": {"report": ""},
            "error": "\n".join(error_lines),
        }

    # Check batch size limit before importing
    if len(records) > import_service.MAX_BATCH_SIZE:
        return {
            "success": False,
            "data": {"report": ""},
            "error": (
                f"Limite excedido: máximo de {import_service.MAX_BATCH_SIZE} "
                f"alunos por importação. Seu arquivo contém "
                f"{len(records)} registros."
            ),
        }

    # Validate and import
    result = import_service.validate_and_import(trainer_id, records)

    # Generate report
    report_messages = import_service.generate_report(result)
    report = "\n\n".join(report_messages)

    success = result.succeeded > 0 or result.total == 0
    return {
        "success": success,
        "data": {"report": report},
    }


class _CsvDownloadError(Exception):
    """Internal error for CSV download failures."""


def _parse_input(
    fmt: ImportFormat,
    message_body: str,
    media_urls: List[str],
    parser: ImportParser,
    sheets_reader: GoogleSheetsReader,
):
    """Parse input based on detected format.

    Returns:
        Tuple of (records, parse_errors).

    Raises:
        GoogleSheetsAccessError: If Google Sheets is not publicly accessible.
        GoogleSheetsTimeoutError: If Google Sheets request times out.
        _CsvDownloadError: If CSV file download fails.
    """
    if fmt == ImportFormat.GOOGLE_SHEETS:
        spreadsheet_id = sheets_reader.extract_spreadsheet_id(message_body)
        if not spreadsheet_id:
            return [], []
        csv_content = sheets_reader.fetch_csv(spreadsheet_id)
        return parser.parse_csv(csv_content)

    if fmt == ImportFormat.CSV:
        csv_content = _download_csv(media_urls)
        return parser.parse_csv(csv_content)

    # STRUCTURED_TEXT
    return parser.parse_structured_text(message_body)


def _download_csv(media_urls: List[str]) -> str:
    """Download CSV content from the first media URL.

    Raises:
        _CsvDownloadError: If the download fails for any reason.
    """
    if not media_urls:
        raise _CsvDownloadError(
            "Não foi possível baixar o arquivo CSV. Tente enviar novamente."
        )

    url = media_urls[0]
    try:
        with httpx.Client(timeout=CSV_DOWNLOAD_TIMEOUT) as client:
            response = client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    except Exception:
        raise _CsvDownloadError(
            "Não foi possível baixar o arquivo CSV. Tente enviar novamente."
        )
