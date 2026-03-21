"""Import Parser module for bulk student import.

Parses structured text messages, CSV content, and Google Sheets data
into a uniform list of RawStudentRecord objects for validation and import.
"""

import csv
import io
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ImportFormat(Enum):
    """Supported import formats for bulk student data."""
    STRUCTURED_TEXT = "structured_text"
    CSV = "csv"
    GOOGLE_SHEETS = "google_sheets"


@dataclass
class RawStudentRecord:
    """Intermediate representation of a parsed student record."""
    line_number: int
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    training_goal: Optional[str] = None
    payment_due_day: Optional[str] = None
    monthly_fee: Optional[str] = None
    plan_start_date: Optional[str] = None


@dataclass
class ParseError:
    """Error encountered during parsing."""
    line_number: int
    message: str


class ImportParser:
    """Parses bulk student import data from multiple formats.

    Supports structured text messages, CSV content, and Google Sheets data.
    All formats produce the same RawStudentRecord list for downstream processing.
    """

    BULK_IMPORT_PREFIXES = ("importar alunos", "import students")
    MAX_RECORDS = 50

    GOOGLE_SHEETS_URL_PATTERN = re.compile(
        r'https://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9_-]+',
        re.IGNORECASE,
    )
    IMPORT_KEYWORDS = ("importar", "import")

    def detect_format(
        self, message_body: str, media_urls: list
    ) -> Optional[ImportFormat]:
        """Detect import format from message content.

        Checks for Google Sheets URL first, then CSV media attachments,
        then structured text prefixes. Returns None if no format matches.
        """
        body_lower = message_body.lower() if message_body else ""

        # 1. Google Sheets URL
        if self.GOOGLE_SHEETS_URL_PATTERN.search(message_body or ""):
            if any(kw in body_lower for kw in self.IMPORT_KEYWORDS):
                return ImportFormat.GOOGLE_SHEETS

        # 2. CSV media attachment
        if media_urls:
            if any(kw in body_lower for kw in self.IMPORT_KEYWORDS):
                return ImportFormat.CSV

        # 3. Structured text prefix
        if any(body_lower.startswith(prefix) for prefix in self.BULK_IMPORT_PREFIXES):
            return ImportFormat.STRUCTURED_TEXT

        return None

    def parse_structured_text(
        self, message_body: str
    ) -> Tuple[List[RawStudentRecord], List[ParseError]]:
        """Parse 'importar alunos\\nname;phone;email;goal' format.

        Strips the prefix line and parses each subsequent line by semicolons.
        Fields order: name;phone_number;email;training_goal[;payment_due_day;monthly_fee;plan_start_date]
        Lines with fewer than 4 fields are recorded as ParseError.
        Empty lines are skipped. Line numbers are 1-based starting from the
        first data line after the prefix.
        """
        records: List[RawStudentRecord] = []
        errors: List[ParseError] = []

        body = message_body or ""

        # Strip the prefix line (case-insensitive)
        body_lower = body.lower()
        for prefix in self.BULK_IMPORT_PREFIXES:
            if body_lower.startswith(prefix):
                body = body[len(prefix):]
                break

        lines = body.split("\n")
        line_number = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            line_number += 1
            fields = [f.strip() for f in stripped.split(";")]

            if len(fields) < 4:
                errors.append(
                    ParseError(
                        line_number=line_number,
                        message=(
                            f"Linha {line_number}: formato inválido "
                            f"(esperado: nome;telefone;email;objetivo)"
                        ),
                    )
                )
                continue

            record = RawStudentRecord(
                line_number=line_number,
                name=fields[0],
                phone_number=fields[1],
                email=fields[2],
                training_goal=fields[3],
                payment_due_day=fields[4] if len(fields) > 4 and fields[4] else None,
                monthly_fee=fields[5] if len(fields) > 5 and fields[5] else None,
                plan_start_date=fields[6] if len(fields) > 6 and fields[6] else None,
            )
            records.append(record)

        return records, errors

    def parse_csv(
        self, csv_content: str
    ) -> Tuple[List[RawStudentRecord], List[ParseError]]:
        """Parse CSV with header row: name,phone_number,email,training_goal[,optional cols].

        Accepts optional columns: payment_due_day, monthly_fee, plan_start_date.
        Returns descriptive error if required columns are missing.
        Each row becomes a RawStudentRecord with 1-based line_number
        (row 1 = first data row after header). Strips whitespace from values.
        Empty optional fields become None. Missing required fields produce ParseError.
        """
        records: List[RawStudentRecord] = []
        errors: List[ParseError] = []

        required_columns = {"name", "phone_number", "email", "training_goal"}
        optional_columns = {"payment_due_day", "monthly_fee", "plan_start_date"}

        reader = csv.DictReader(io.StringIO(csv_content))

        # Validate header columns
        if reader.fieldnames is None:
            errors.append(
                ParseError(
                    line_number=0,
                    message="CSV inválido: arquivo vazio ou sem cabeçalho",
                )
            )
            return records, errors

        header_set = {h.strip() for h in reader.fieldnames}
        missing = required_columns - header_set
        if missing:
            sorted_missing = sorted(missing)
            errors.append(
                ParseError(
                    line_number=0,
                    message=f"CSV inválido: colunas ausentes: {', '.join(sorted_missing)}",
                )
            )
            return records, errors

        line_number = 0
        for row in reader:
            line_number += 1

            # Strip whitespace from all values
            stripped = {
                k.strip(): v.strip() if v else ""
                for k, v in row.items()
                if k is not None
            }

            # Check for missing required field values
            missing_fields = [
                col for col in sorted(required_columns)
                if not stripped.get(col)
            ]
            if missing_fields:
                errors.append(
                    ParseError(
                        line_number=line_number,
                        message=(
                            f"Linha {line_number}: campos obrigatórios vazios: "
                            f"{', '.join(missing_fields)}"
                        ),
                    )
                )
                continue

            record = RawStudentRecord(
                line_number=line_number,
                name=stripped["name"],
                phone_number=stripped["phone_number"],
                email=stripped["email"],
                training_goal=stripped["training_goal"],
                payment_due_day=stripped.get("payment_due_day") or None,
                monthly_fee=stripped.get("monthly_fee") or None,
                plan_start_date=stripped.get("plan_start_date") or None,
            )
            records.append(record)

        return records, errors

    def format_structured_text(self, records: List[Dict]) -> str:
        """Format student record dicts back to structured text.

        Produces 'importar alunos\\nname;phone;email;goal' format for round-trip.
        Each dict has keys: name, phone_number, email, training_goal (required),
        and optionally payment_due_day, monthly_fee, plan_start_date.
        Only includes optional fields in the semicolon-separated line if they have values.
        """
        lines = ["importar alunos"]
        optional_keys = ["payment_due_day", "monthly_fee", "plan_start_date"]

        for record in records:
            parts = [
                record.get("name", ""),
                record.get("phone_number", ""),
                record.get("email", ""),
                record.get("training_goal", ""),
            ]

            # Append optional fields only if they have values.
            # Must include earlier optional fields (as empty) if a later one has a value.
            optional_values = [record.get(k) for k in optional_keys]
            last_present = -1
            for i, val in enumerate(optional_values):
                if val:
                    last_present = i
            if last_present >= 0:
                for i in range(last_present + 1):
                    parts.append(optional_values[i] if optional_values[i] else "")

            lines.append(";".join(parts))

        return "\n".join(lines)

    def format_csv(self, records: List[Dict]) -> str:
        """Format student record dicts back to CSV string with header row.

        Always includes the 4 required columns: name, phone_number, email, training_goal.
        Includes optional columns (payment_due_day, monthly_fee, plan_start_date) only
        if any record has a value for them. Uses Python's csv module for proper formatting.
        """
        required_columns = ["name", "phone_number", "email", "training_goal"]
        optional_columns = ["payment_due_day", "monthly_fee", "plan_start_date"]

        # Determine which optional columns to include
        included_optional = [
            col for col in optional_columns
            if any(record.get(col) for record in records)
        ]

        fieldnames = required_columns + included_optional

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for record in records:
            row = {}
            for col in fieldnames:
                val = record.get(col)
                row[col] = val if val else ""
            writer.writerow(row)

        return output.getvalue()
