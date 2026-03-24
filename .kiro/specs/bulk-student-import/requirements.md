# Requirements Document

## Introduction

Bulk Student Import enables personal trainers to register multiple students at once through the WhatsApp interface, instead of adding them one by one via conversational AI. Trainers with large rosters (40+ students) can send a structured text message, a CSV file attachment, or a Google Sheets link containing student data, and the Bulk_Import_Service validates, deduplicates, and registers all students in a single operation, reporting results back through WhatsApp. The Google Sheets option is designed as the most accessible method for non-technical trainers who may not be familiar with CSV files — they simply share a spreadsheet link via WhatsApp.

## Glossary

- **Trainer**: A registered personal trainer who manages students through FitAgent via WhatsApp
- **Student**: A client linked to one or more trainers, identified by phone number in E.164 format
- **Bulk_Import_Service**: The backend service responsible for parsing, validating, and persisting bulk student data
- **Import_Parser**: The component that parses structured text messages and CSV file attachments into student records
- **Import_Report**: A summary message sent back to the trainer describing the outcome of a bulk import operation
- **CSV_File**: A comma-separated values file attachment sent via WhatsApp containing student records
- **Structured_Text_Message**: A WhatsApp text message containing multiple student records in a defined line-by-line format
- **E164_Phone_Number**: A phone number in international E.164 format (e.g., +5511999999999)
- **Duplicate_Student**: A student whose phone number already exists in the system, either linked to the requesting trainer or registered globally
- **Import_Batch**: A collection of student records submitted in a single bulk import request
- **Partial_Failure**: An import outcome where some student records succeed and others fail validation or persistence
- **Google_Sheets_URL**: A publicly shared Google Sheets URL (e.g., https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit?usp=sharing) sent by the Trainer via WhatsApp
- **Google_Sheets_Reader**: The component that fetches and parses student data from a publicly shared Google Sheets spreadsheet using the Google Sheets API or CSV export endpoint

## Requirements

### Requirement 1: Bulk Import via Structured Text Message

**User Story:** As a trainer, I want to send a single WhatsApp message with multiple student records in a structured format, so that I can register many students without repeating the conversational flow for each one.

#### Acceptance Criteria

1. WHEN the Trainer sends a message starting with "importar alunos" or "import students" followed by student records, THE Import_Parser SHALL recognize the message as a bulk import request
2. THE Import_Parser SHALL accept student records in the format: one student per line, with fields separated by semicolons in the order: name;phone_number;email;training_goal
3. WHEN the Import_Parser receives a valid structured text message, THE Import_Parser SHALL extract each line as a separate student record
4. IF a line in the structured text message contains fewer than 4 semicolon-separated fields, THEN THE Import_Parser SHALL mark that line as invalid and include the line number in the Import_Report
5. THE Bulk_Import_Service SHALL accept a maximum of 50 student records per single Import_Batch

### Requirement 2: Bulk Import via CSV File Attachment

**User Story:** As a trainer, I want to attach a CSV file to a WhatsApp message to import students, so that I can prepare the data in a spreadsheet and upload it conveniently.

#### Acceptance Criteria

1. WHEN the Trainer sends a WhatsApp message with a CSV_File attachment and the caption contains "importar" or "import", THE Import_Parser SHALL download and parse the CSV_File
2. THE Import_Parser SHALL accept CSV files with a header row containing columns: name, phone_number, email, training_goal
3. THE Import_Parser SHALL accept CSV files with optional columns: payment_due_day, monthly_fee, plan_start_date
4. IF the CSV_File exceeds 50 rows of student data (excluding the header), THEN THE Bulk_Import_Service SHALL reject the file and inform the Trainer of the 50-student limit
5. IF the CSV_File is not a valid CSV format or is missing required columns, THEN THE Import_Parser SHALL return a descriptive error identifying the missing columns
6. THE Import_Parser SHALL accept CSV files encoded in UTF-8 or Latin-1 (ISO-8859-1)

### Requirement 3: Student Data Validation

**User Story:** As a trainer, I want each student record to be validated before import, so that only correct data enters the system.

#### Acceptance Criteria

1. THE Bulk_Import_Service SHALL validate that each student name contains at least 2 characters
2. THE Bulk_Import_Service SHALL validate that each phone_number conforms to E164_Phone_Number format
3. WHEN a phone_number does not start with "+", THE Bulk_Import_Service SHALL attempt to normalize the phone_number by prepending "+"
4. THE Bulk_Import_Service SHALL validate that each email contains an "@" character and a "." character
5. THE Bulk_Import_Service SHALL validate that each training_goal is a non-empty string
6. WHERE payment_due_day is provided, THE Bulk_Import_Service SHALL validate that the value is an integer between 1 and 31
7. WHERE monthly_fee is provided, THE Bulk_Import_Service SHALL validate that the value is a positive number with at most 2 decimal places
8. WHERE plan_start_date is provided, THE Bulk_Import_Service SHALL validate that the value is in YYYY-MM format

### Requirement 4: Duplicate Detection

**User Story:** As a trainer, I want the system to detect duplicate students during import, so that I do not accidentally create duplicate records.

#### Acceptance Criteria

1. WHEN a student phone_number in the Import_Batch already exists as an active student linked to the requesting Trainer, THE Bulk_Import_Service SHALL skip that record and mark it as "already linked" in the Import_Report
2. WHEN a student phone_number in the Import_Batch exists as a Student in the system but is not linked to the requesting Trainer, THE Bulk_Import_Service SHALL create a new TrainerStudentLink for the existing Student
3. WHEN a student phone_number in the Import_Batch is registered as a Trainer, THE Bulk_Import_Service SHALL skip that record and mark it as "phone registered as trainer" in the Import_Report
4. WHEN the Import_Batch contains two or more records with the same phone_number, THE Bulk_Import_Service SHALL process only the first occurrence and mark subsequent duplicates as "duplicate in batch" in the Import_Report

### Requirement 5: Batch Registration and Persistence

**User Story:** As a trainer, I want all valid students from a bulk import to be saved to the database reliably, so that I can trust the import results.

#### Acceptance Criteria

1. THE Bulk_Import_Service SHALL create a Student entity and a TrainerStudentLink entity for each valid new student record
2. THE Bulk_Import_Service SHALL use DynamoDB batch_write_items to persist student records in batches of up to 25 items
3. IF a DynamoDB write operation fails for a subset of records, THEN THE Bulk_Import_Service SHALL retry the failed items up to 3 times with exponential backoff
4. THE Bulk_Import_Service SHALL process valid records independently of invalid records within the same Import_Batch (Partial_Failure support)
5. WHEN all records in an Import_Batch fail validation, THE Bulk_Import_Service SHALL return the Import_Report without attempting any database writes

### Requirement 6: Import Result Reporting

**User Story:** As a trainer, I want to receive a clear summary of the import results, so that I know which students were added and which had issues.

#### Acceptance Criteria

1. WHEN the Bulk_Import_Service completes processing an Import_Batch, THE Bulk_Import_Service SHALL send an Import_Report to the Trainer via WhatsApp
2. THE Import_Report SHALL include the total number of records processed, the number successfully imported, the number skipped, and the number that failed validation
3. THE Import_Report SHALL list each failed or skipped record with the student name (or line number if name is unavailable), the phone_number, and the reason for failure or skip
4. WHEN all records are successfully imported, THE Import_Report SHALL include a confirmation message with the count of new students added
5. THE Import_Report SHALL be formatted to fit within WhatsApp message size limits (maximum 4096 characters); IF the report exceeds this limit, THEN THE Bulk_Import_Service SHALL split the report into multiple sequential messages

### Requirement 7: Integration with Existing Registration Flow

**User Story:** As a trainer, I want bulk-imported students to be identical to individually registered students, so that all features work the same regardless of how a student was added.

#### Acceptance Criteria

1. THE Bulk_Import_Service SHALL create Student entities with the same schema and validation rules used by the register_student tool
2. THE Bulk_Import_Service SHALL create TrainerStudentLink entities with status "active" for each successfully imported student
3. WHEN a bulk-imported Student is queried via the view_students tool, THE view_students tool SHALL return the student in the same format as individually registered students
4. THE Bulk_Import_Service SHALL sanitize all string inputs using the same InputSanitizer used by the register_student tool

### Requirement 9: Bulk Import via Google Sheets Link

**User Story:** As a non-technical trainer, I want to share a Google Sheets link via WhatsApp to import students, so that I can use a familiar spreadsheet tool without needing to know what a CSV file is.

#### Acceptance Criteria

1. WHEN the Trainer sends a WhatsApp message containing a Google_Sheets_URL and the message contains "importar" or "import", THE Google_Sheets_Reader SHALL extract the spreadsheet ID from the URL
2. THE Google_Sheets_Reader SHALL validate that the URL matches the Google Sheets URL pattern (https://docs.google.com/spreadsheets/d/{spreadsheet_id})
3. THE Google_Sheets_Reader SHALL fetch the spreadsheet data by requesting the CSV export endpoint (https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv) for publicly shared sheets
4. IF the Google Sheets spreadsheet is not publicly shared or the export request fails, THEN THE Google_Sheets_Reader SHALL return a descriptive error instructing the Trainer to set the spreadsheet sharing to "Anyone with the link can view"
5. THE Google_Sheets_Reader SHALL expect the first sheet to contain a header row with columns: name, phone_number, email, training_goal
6. THE Google_Sheets_Reader SHALL accept optional columns in the spreadsheet: payment_due_day, monthly_fee, plan_start_date
7. IF the spreadsheet exceeds 50 rows of student data (excluding the header), THEN THE Bulk_Import_Service SHALL reject the import and inform the Trainer of the 50-student limit
8. WHEN the Google_Sheets_Reader successfully fetches and parses the spreadsheet data, THE Google_Sheets_Reader SHALL pass the parsed records to the Bulk_Import_Service for validation and registration using the same pipeline as CSV and structured text imports
9. IF the Google_Sheets_Reader cannot reach the Google Sheets export endpoint within 10 seconds, THEN THE Google_Sheets_Reader SHALL return a timeout error and instruct the Trainer to try again

### Requirement 8: Parse and Format Round-Trip

**User Story:** As a developer, I want to verify that parsing and formatting student import data is consistent, so that data integrity is maintained.

#### Acceptance Criteria

1. THE Import_Parser SHALL parse structured text messages into a list of student record dictionaries
2. THE Import_Parser SHALL format a list of student record dictionaries back into the structured text message format
3. FOR ALL valid lists of student record dictionaries, parsing the formatted output SHALL produce a list equivalent to the original input (round-trip property)
4. FOR ALL valid CSV content strings, parsing then formatting then parsing the CSV content SHALL produce a list equivalent to the first parse result (round-trip property)
