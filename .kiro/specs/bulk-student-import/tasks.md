# Implementation Plan: Bulk Student Import

## Overview

Implement bulk student import functionality allowing trainers to register multiple students via structured text messages, CSV file attachments, or Google Sheets links through WhatsApp. The implementation introduces three new service modules (`Import_Parser`, `Google_Sheets_Reader`, `Bulk_Import_Service`) and a new Strands agent tool (`bulk_import_students`), integrating with the existing DynamoDB single-table design and student registration pipeline.

## Tasks

- [x] 1. Implement Import_Parser module
  - [x] 1.1 Create `src/services/import_parser.py` with `ImportFormat` enum, `RawStudentRecord` and `ParseError` dataclasses, and `ImportParser` class skeleton
    - Define `ImportFormat` enum with `STRUCTURED_TEXT`, `CSV`, `GOOGLE_SHEETS` values
    - Define `RawStudentRecord` dataclass with fields: `line_number`, `name`, `phone_number`, `email`, `training_goal`, `payment_due_day`, `monthly_fee`, `plan_start_date`
    - Define `ParseError` dataclass with `line_number` and `message`
    - Define `BULK_IMPORT_PREFIXES` and `MAX_RECORDS` constants
    - _Requirements: 1.1, 1.2, 2.2, 2.3, 8.1_

  - [x] 1.2 Implement `detect_format` method
    - Check for Google Sheets URL pattern first, then CSV media attachments, then structured text prefixes
    - Case-insensitive matching for "importar alunos" / "import students" prefixes
    - Check caption for "importar" / "import" keywords for CSV and Google Sheets
    - Return `None` if no format matches
    - _Requirements: 1.1, 2.1, 9.1_

  - [x] 1.3 Implement `parse_structured_text` method
    - Strip the prefix line ("importar alunos" / "import students")
    - Split remaining lines by newline, parse each line by semicolons
    - Mark lines with fewer than 4 fields as `ParseError` with line number
    - Return tuple of `(List[RawStudentRecord], List[ParseError])`
    - _Requirements: 1.2, 1.3, 1.4, 8.1_

  - [x] 1.4 Implement `parse_csv` method
    - Accept CSV content string, try UTF-8 first then Latin-1 decoding
    - Validate required header columns: `name`, `phone_number`, `email`, `training_goal`
    - Accept optional columns: `payment_due_day`, `monthly_fee`, `plan_start_date`
    - Return descriptive error if required columns are missing
    - _Requirements: 2.2, 2.3, 2.5, 2.6, 8.4_

  - [x] 1.5 Implement `format_structured_text` and `format_csv` methods for round-trip support
    - `format_structured_text`: Convert list of student record dicts back to "importar alunos\nname;phone;email;goal" format
    - `format_csv`: Convert list of student record dicts back to CSV string with header row
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ]* 1.6 Write property test for format detection (Property 1)
    - **Property 1: Format Detection**
    - **Validates: Requirements 1.1, 2.1**

  - [ ]* 1.7 Write property test for structured text round-trip (Property 2)
    - **Property 2: Structured Text Parse-Format Round-Trip**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [ ]* 1.8 Write property test for CSV round-trip (Property 3)
    - **Property 3: CSV Parse-Format Round-Trip**
    - **Validates: Requirements 8.4**

- [x] 2. Implement Google_Sheets_Reader module
  - [x] 2.1 Create `src/services/google_sheets_reader.py` with `GoogleSheetsReader` class, custom exceptions, and URL pattern
    - Define `GoogleSheetsAccessError` and `GoogleSheetsTimeoutError` exception classes
    - Define `SHEETS_URL_PATTERN` regex, `EXPORT_URL_TEMPLATE`, and `TIMEOUT_SECONDS = 10`
    - _Requirements: 9.2, 9.4, 9.9_

  - [x] 2.2 Implement `extract_spreadsheet_id` method
    - Use regex to extract spreadsheet ID from Google Sheets URL
    - Return `None` if URL does not match the pattern
    - _Requirements: 9.1, 9.2_

  - [x] 2.3 Implement `fetch_csv` method
    - Use `httpx` to GET the CSV export endpoint with 10-second timeout
    - Raise `GoogleSheetsAccessError` on 403/404 responses with user-friendly message
    - Raise `GoogleSheetsTimeoutError` on timeout
    - Return CSV content string on success
    - _Requirements: 9.3, 9.4, 9.9_

  - [ ]* 2.4 Write property test for Google Sheets URL extraction (Property 14)
    - **Property 14: Google Sheets URL Extraction**
    - **Validates: Requirements 9.1, 9.2**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Bulk_Import_Service module
  - [x] 4.1 Create `src/services/bulk_import_service.py` with `RecordStatus` enum, `RecordResult` and `ImportResult` dataclasses, and `BulkImportService` class skeleton
    - Define `RecordStatus` enum: `SUCCESS`, `ALREADY_LINKED`, `LINKED_EXISTING`, `PHONE_IS_TRAINER`, `DUPLICATE_IN_BATCH`, `VALIDATION_FAILED`, `PERSISTENCE_FAILED`
    - Define `RecordResult` and `ImportResult` dataclasses
    - Initialize `BulkImportService` with `dynamodb_client`, `PhoneNumberValidator`, `InputSanitizer`
    - Define constants: `MAX_BATCH_SIZE = 50`, `DYNAMO_BATCH_SIZE = 25`, `MAX_RETRIES = 3`
    - _Requirements: 1.5, 5.1, 5.2_

  - [x] 4.2 Implement `_validate_record` method
    - Validate name ≥ 2 characters
    - Validate phone_number is E.164 (attempt normalization by prepending "+" if missing)
    - Validate email contains "@" and "."
    - Validate training_goal is non-empty
    - Validate optional fields: payment_due_day (1-31), monthly_fee (positive, ≤2 decimals), plan_start_date (YYYY-MM)
    - Sanitize all string fields using `InputSanitizer`
    - Return list of error messages (empty = valid)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 7.4_

  - [x] 4.3 Implement `_detect_duplicates` method
    - For each record, look up phone_number via `dynamodb_client.lookup_by_phone_number`
    - Classify as `ALREADY_LINKED` if active student linked to trainer
    - Classify as `LINKED_EXISTING` if student exists but not linked to trainer
    - Classify as `PHONE_IS_TRAINER` if phone belongs to a trainer
    - Track seen phone numbers within batch; classify subsequent occurrences as `DUPLICATE_IN_BATCH`
    - Return dict mapping line_number to `RecordStatus` for non-new records
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [x] 4.4 Implement `_batch_persist` method
    - Create `Student` entity and `TrainerStudentLink` entity for each new valid record
    - For `LINKED_EXISTING` records, create only `TrainerStudentLink`
    - Use `dynamodb_client.batch_write_items` in chunks (each student = 2 items, so ~12 students per 25-item batch)
    - Implement retry logic: up to 3 retries with exponential backoff (1s, 2s, 4s) for `UnprocessedItems`
    - Mark remaining failures as `PERSISTENCE_FAILED`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 7.1, 7.2_

  - [x] 4.5 Implement `validate_and_import` orchestration method
    - Reject batch if > 50 records
    - Run validation on all records, collect errors
    - Skip DB writes if all records fail validation
    - Run duplicate detection on valid records
    - Persist valid non-duplicate records
    - Assemble and return `ImportResult`
    - _Requirements: 1.5, 2.4, 5.4, 5.5, 9.7_

  - [x] 4.6 Implement `generate_report` method
    - Format Import_Report with total, succeeded, skipped, failed counts
    - List each failed/skipped record with name (or line number), phone, and reason
    - Use emoji formatting (✅, ⏭️, ❌) for WhatsApp readability
    - Split into multiple messages if report exceeds 4096 characters
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 4.7 Write property test for batch size limit enforcement (Property 4)
    - **Property 4: Batch Size Limit Enforcement**
    - **Validates: Requirements 1.5, 2.4, 9.7**

  - [ ]* 4.8 Write property test for validation correctness (Property 5)
    - **Property 5: Validation Correctness**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6, 3.7, 3.8**

  - [ ]* 4.9 Write property test for phone number normalization (Property 6)
    - **Property 6: Phone Number Normalization**
    - **Validates: Requirements 3.3**

  - [ ]* 4.10 Write property test for duplicate detection classification (Property 7)
    - **Property 7: Duplicate Detection Classification**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ]* 4.11 Write property test for persistence entity creation (Property 8)
    - **Property 8: Persistence Creates Correct Entities**
    - **Validates: Requirements 5.1, 7.2**

  - [ ]* 4.12 Write property test for partial failure independence (Property 9)
    - **Property 9: Partial Failure Independence**
    - **Validates: Requirements 5.4**

  - [ ]* 4.13 Write property test for report completeness (Property 10)
    - **Property 10: Report Completeness**
    - **Validates: Requirements 6.2, 6.3**

  - [ ]* 4.14 Write property test for report message splitting (Property 11)
    - **Property 11: Report Message Splitting**
    - **Validates: Requirements 6.5**

  - [ ]* 4.15 Write property test for input sanitization (Property 13)
    - **Property 13: Input Sanitization**
    - **Validates: Requirements 7.4**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement bulk_import_students agent tool and wire everything together
  - [x] 6.1 Create the `bulk_import_students` tool function in `src/tools/bulk_import_tools.py`
    - Decorate with `@tool` from `strands`
    - Accept `trainer_id`, `message_body`, and optional `media_urls` parameters
    - Instantiate `ImportParser`, `GoogleSheetsReader`, `BulkImportService`
    - Call `detect_format` to determine input type
    - For `GOOGLE_SHEETS`: extract spreadsheet ID, fetch CSV, then parse CSV
    - For `CSV`: download CSV from media URL, then parse CSV
    - For `STRUCTURED_TEXT`: parse structured text directly
    - Handle parse errors and batch size limit before calling `validate_and_import`
    - Call `generate_report` and return formatted report string
    - Return `{'success': bool, 'data': {'report': str}, 'error': str}` following existing tool pattern
    - _Requirements: 1.1, 2.1, 9.1, 9.8_

  - [x] 6.2 Handle error cases in the tool function
    - Return descriptive error for unrecognized format
    - Return Google Sheets access/timeout errors with user-friendly Portuguese messages
    - Return CSV download failure error
    - Return batch size exceeded error with record count
    - _Requirements: 2.4, 2.5, 9.4, 9.7, 9.9_

  - [ ]* 6.3 Write property test for schema consistency (Property 12)
    - **Property 12: Schema Consistency with register_student**
    - **Validates: Requirements 7.1, 7.3**

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `max_examples=100` and `deadline=None` as specified in the design
- All property tests go in `tests/property/test_bulk_import_properties.py`
- The implementation reuses existing `PhoneNumberValidator`, `InputSanitizer`, `Student`, `TrainerStudentLink`, and `DynamoDBClient` from the codebase
- Checkpoints ensure incremental validation between major implementation phases
