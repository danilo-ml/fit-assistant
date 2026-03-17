# Implementation Plan: Student Plan Payments

## Overview

Extend FitAgent's payment system to support plan-based payment management. Implementation proceeds bottom-up: model changes first, then the pure verification service, then tool modifications, and finally tests. All financial fields use `Decimal` for precision. Python 3.12, pytest, Hypothesis, moto.

## Tasks

- [x] 1. Extend Student and Payment Pydantic models with plan fields
  - [x] 1.1 Add plan fields to Student model in `src/models/entities.py`
    - Add `monthly_fee: Optional[Decimal] = None` with validator (positive, 2 decimal places)
    - Add `currency: str = "BRL"` default field
    - Add `plan_start_date: Optional[str] = None` with YYYY-MM format validator
    - Update `to_dynamodb()` to serialize new fields (Decimal as str for DynamoDB Number)
    - Update `from_dynamodb()` to deserialize with `Decimal(str(value))` for monthly_fee
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 6.1, 6.3_

  - [x] 1.2 Add reference period and verification fields to Payment model in `src/models/entities.py`
    - Add `reference_start_month: Optional[str] = None` with YYYY-MM validator
    - Add `reference_end_month: Optional[str] = None` with YYYY-MM validator
    - Add `verification_status: Optional[Literal["matched", "mismatched"]] = None`
    - Add `expected_amount: Optional[Decimal] = None`
    - Migrate `amount` field from `float` to `Decimal` with backward-compatible validator
    - Add validator ensuring both reference months are present or both absent, and start <= end
    - Update `to_dynamodb()` and `from_dynamodb()` for new fields
    - _Requirements: 3.1, 3.6, 6.2, 6.4_

  - [ ]* 1.3 Write property test for Student round-trip serialization
    - **Property 6: Student plan data round-trip serialization**
    - **Validates: Requirements 6.1, 6.3**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random Student objects with and without plan fields using Hypothesis
    - Verify `Student.from_dynamodb(student.to_dynamodb())` produces equivalent object

  - [ ]* 1.4 Write property test for Payment round-trip serialization
    - **Property 7: Payment with reference period round-trip serialization**
    - **Validates: Requirements 6.2, 6.4**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random Payment objects with reference period fields
    - Verify `Payment.from_dynamodb(payment.to_dynamodb())` produces equivalent object

  - [ ]* 1.5 Write property test for monthly fee validation
    - **Property 8: Monthly fee validation rejects invalid values**
    - **Validates: Requirements 1.3, 1.5**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate invalid fees (negative, zero, wrong decimal places) and verify rejection
    - Generate valid fees (positive, 2 decimal places) and verify acceptance

- [x] 2. Implement PaymentVerificationService
  - [x] 2.1 Create `src/services/payment_verification.py` with PaymentVerificationService class
    - Implement `calculate_months_covered(start_month, end_month) -> int` (inclusive count)
    - Implement `verify_payment(monthly_fee, amount, reference_start_month, reference_end_month) -> dict` returning status, expected_amount, actual_amount, months_covered
    - Implement `get_payment_status_by_month(plan_start_date, confirmed_payments, current_month) -> list` returning month-by-month status (paid/pending/overdue)
    - Raise `ValueError` for invalid inputs (bad YYYY-MM format, start > end)
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 3.2, 3.3, 3.4, 4.2, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 2.2 Write property test for verification expected amount calculation
    - **Property 1: Verification expected amount equals fee times months**
    - **Validates: Requirements 2.1, 2.5, 3.2, 3.3, 3.4, 4.2**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random Decimal fees (0.01–99999.99, 2 places) and valid YYYY-MM period pairs
    - Verify expected_amount == monthly_fee × months_covered

  - [ ]* 2.3 Write property test for verification status matched iff correct
    - **Property 2: Verification status is matched iff amount equals expected**
    - **Validates: Requirements 2.2, 2.3**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random fees, periods, and amounts
    - Verify status is "matched" ↔ amount == expected, "mismatched" otherwise with both amounts in response

  - [ ]* 2.4 Write property test for confirmed payments marking months as paid
    - **Property 3: Confirmed payments mark all covered months as paid**
    - **Validates: Requirements 3.5, 4.3**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random plan + confirmed payments with reference periods
    - Verify all covered months have status "paid"

  - [ ]* 2.5 Write property test for month status classification
    - **Property 4: Month status classification correctness**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random plan_start_date, confirmed payments, and fixed current_month
    - Verify each month follows: covered → paid, past + uncovered → overdue, current/future + uncovered → pending

  - [ ]* 2.6 Write property test for payment status range completeness
    - **Property 5: Payment status range spans plan start to current month**
    - **Validates: Requirements 5.5**
    - File: `tests/property/test_plan_payment_properties.py`
    - Generate random plan_start_date and current_month (>= plan_start_date)
    - Verify returned months form contiguous range from start to current with no gaps

- [x] 3. Checkpoint - Verify models and service
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Modify student tools to support plan registration
  - [x] 4.1 Update `register_student` in `src/tools/student_tools.py`
    - Add optional `monthly_fee: float` and `plan_start_date: str` parameters
    - Convert `monthly_fee` to `Decimal` internally, validate > 0 and 2 decimal places
    - Validate `plan_start_date` is YYYY-MM format
    - Pass new fields to Student model constructor
    - _Requirements: 1.1, 1.3, 1.5, 1.6_

  - [x] 4.2 Update `update_student` in `src/tools/student_tools.py`
    - Add optional `monthly_fee: float` and `plan_start_date: str` parameters
    - Same validation as register_student
    - Update existing student record with new plan fields
    - _Requirements: 1.2, 1.3, 1.5_

  - [ ]* 4.3 Write unit tests for student plan registration and update
    - File: `tests/unit/test_plan_payments.py`
    - Test register_student with monthly_fee and plan_start_date
    - Test update_student modifying monthly_fee
    - Test validation rejection for fee <= 0, wrong precision, invalid date format
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6_

- [x] 5. Modify payment tools and add view_payment_status
  - [x] 5.1 Update `register_payment` in `src/tools/payment_tools.py`
    - Add optional `reference_start_month: str` and `reference_end_month: str` parameters
    - When reference period provided and student has a plan, call `PaymentVerificationService.verify_payment()`
    - Store verification_status and expected_amount on Payment record
    - When student has no plan, set verification_status=None and include warning in response
    - Validate both reference months present or both absent
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.1, 3.6, 4.1, 4.4_

  - [x] 5.2 Add `view_payment_status` tool function in `src/tools/payment_tools.py`
    - Accept trainer_id, and student_name or student_id
    - Look up student to get plan_start_date and monthly_fee
    - Query confirmed payments for the student
    - Call `PaymentVerificationService.get_payment_status_by_month()`
    - Return month-by-month status list with paid/pending/overdue
    - Return error if student has no plan configured
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 5.3 Write unit tests for payment registration with verification
    - File: `tests/unit/test_plan_payments.py`
    - Test register_payment with matched verification (R$450 for 3 months at R$150/month)
    - Test register_payment with mismatched verification
    - Test register_payment for student with no plan (warning)
    - Test register_payment with invalid reference period (start > end)
    - Test register_payment with only one reference month provided
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 4.1, 4.4_

  - [ ]* 5.4 Write unit tests for view_payment_status
    - File: `tests/unit/test_plan_payments.py`
    - Test mixed status (some paid, some overdue, some pending months)
    - Test student with no plan returns error
    - Test Decimal precision in payment amounts
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate the 8 correctness properties from the design document
- All financial fields use `Decimal` to avoid floating-point precision issues
- Unit tests use moto for DynamoDB mocking, Hypothesis for property-based tests
