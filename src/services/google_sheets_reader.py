"""Google Sheets Reader module for bulk student import.

Fetches spreadsheet data from publicly shared Google Sheets using the
CSV export endpoint. No API key or OAuth required — works for any sheet
shared with "Anyone with the link can view."
"""

import re
from typing import Optional

import httpx


class GoogleSheetsAccessError(Exception):
    """Raised when a Google Sheets spreadsheet is not publicly accessible.

    Typically caused by 403/404 responses when the sheet sharing is not
    set to "Anyone with the link can view."
    """


class GoogleSheetsTimeoutError(Exception):
    """Raised when a request to Google Sheets exceeds the timeout limit."""


SHEETS_URL_PATTERN = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)"
)

EXPORT_URL_TEMPLATE = (
    "https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv"
)

TIMEOUT_SECONDS = 10


class GoogleSheetsReader:
    """Reads CSV data from publicly shared Google Sheets.

    Uses the public CSV export endpoint (/export?format=csv) instead of the
    Google Sheets API, avoiding the need for API credentials.
    """

    def extract_spreadsheet_id(self, url: str) -> Optional[str]:
        """Extract spreadsheet ID from a Google Sheets URL.

        Args:
            url: A string that may contain a Google Sheets URL.

        Returns:
            The spreadsheet ID if the URL matches, or None otherwise.
        """
        match = SHEETS_URL_PATTERN.search(url)
        if match:
            return match.group(1)
        return None

    def fetch_csv(self, spreadsheet_id: str) -> str:
        """Fetch CSV content from a public Google Sheets export endpoint.

        Args:
            spreadsheet_id: The Google Sheets spreadsheet ID.

        Returns:
            The CSV content as a string.

        Raises:
            GoogleSheetsAccessError: If the sheet is not publicly shared
                (403/404 response).
            GoogleSheetsTimeoutError: If the request exceeds TIMEOUT_SECONDS.
        """
        export_url = EXPORT_URL_TEMPLATE.format(spreadsheet_id=spreadsheet_id)

        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                response = client.get(export_url, follow_redirects=True)
        except httpx.TimeoutException:
            raise GoogleSheetsTimeoutError(
                "Tempo limite excedido ao acessar a planilha. "
                "Tente novamente em alguns instantes."
            )

        if response.status_code in (403, 404):
            raise GoogleSheetsAccessError(
                "Não foi possível acessar a planilha. Verifique se o "
                "compartilhamento está configurado como "
                "'Qualquer pessoa com o link pode visualizar'."
            )

        response.raise_for_status()
        return response.text
