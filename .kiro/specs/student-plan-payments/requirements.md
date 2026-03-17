# Requirements Document

## Introduction

This feature adds plan-based payment management to FitAgent. Each student is assigned a plan with a monthly fee (mensalidade) in R$ BRL. A payment verification service checks whether a student's payment amount matches their plan. The system supports flexible payment schedules: students can pay in advance (e.g., quarterly or annual lump sums) or pay late covering multiple past months in a single transaction.

## Glossary

- **Plan_Registry**: The data record that associates a student with a plan type and monthly fee value in R$ BRL
- **Payment_Verification_Service**: The service that validates whether a payment amount corresponds to the student's plan and the number of months covered
- **Monthly_Fee**: The recurring amount (mensalidade) in R$ BRL that a student owes per month according to their plan
- **Payment_Period**: The range of months (reference months) that a single payment covers
- **Advance_Payment**: A payment that covers one or more future months beyond the current due month
- **Late_Payment**: A payment that covers one or more past-due months
- **Payment_Record**: An entry in the system representing a financial transaction from a student to a trainer
- **FitAgent**: The WhatsApp-based AI assistant platform for personal trainers

## Requirements

### Requirement 1: Register Plan and Monthly Fee on Student

**User Story:** As a trainer, I want to register a plan with a monthly fee value in R$ BRL for each student, so that the system knows how much each student should pay per month.

#### Acceptance Criteria

1. WHEN a trainer registers a new student, THE Plan_Registry SHALL accept a monthly fee value (mensalidade) in R$ BRL as a required field
2. WHEN a trainer updates an existing student, THE Plan_Registry SHALL allow modification of the monthly fee value
3. THE Plan_Registry SHALL store the monthly fee as a positive decimal value with exactly two decimal places precision
4. THE Plan_Registry SHALL store the currency as "BRL" for all plan registrations
5. IF a trainer provides a monthly fee value less than or equal to zero, THEN THE Plan_Registry SHALL reject the registration and return a descriptive error message
6. WHEN a student's plan is registered, THE Plan_Registry SHALL record the plan start date

### Requirement 2: Verify Payment Amount Against Student Plan

**User Story:** As a trainer, I want the system to verify whether a payment amount matches the student's plan, so that I can confirm payments are correct.

#### Acceptance Criteria

1. WHEN a payment is registered for a student, THE Payment_Verification_Service SHALL calculate the expected amount based on the student's monthly fee and the number of months covered by the payment
2. WHEN the payment amount equals the expected amount for the covered months, THE Payment_Verification_Service SHALL mark the verification status as "matched"
3. WHEN the payment amount does not equal the expected amount for the covered months, THE Payment_Verification_Service SHALL mark the verification status as "mismatched" and include the expected amount and the actual amount in the response
4. IF a payment is registered for a student who has no plan registered, THEN THE Payment_Verification_Service SHALL skip verification and return a warning indicating no plan is configured
5. THE Payment_Verification_Service SHALL calculate the expected amount as: monthly_fee × number_of_months_covered

### Requirement 3: Support Advance Payments

**User Story:** As a trainer, I want to register advance payments (e.g., quarterly, semi-annual, annual) for a student, so that students who pay ahead are properly tracked.

#### Acceptance Criteria

1. WHEN a trainer registers a payment, THE Payment_Record SHALL accept a reference period specifying the start month and end month covered
2. WHEN a student makes a quarterly advance payment, THE Payment_Verification_Service SHALL verify the amount against 3 × monthly_fee
3. WHEN a student makes a semi-annual advance payment, THE Payment_Verification_Service SHALL verify the amount against 6 × monthly_fee
4. WHEN a student makes an annual advance payment, THE Payment_Verification_Service SHALL verify the amount against 12 × monthly_fee
5. WHEN an advance payment is confirmed, THE Payment_Record SHALL mark each covered month as "paid" in the student's payment history
6. THE Payment_Record SHALL store the start month and end month of the reference period in ISO format (YYYY-MM)

### Requirement 4: Support Late Payments Covering Past Months

**User Story:** As a trainer, I want to register a single payment that covers multiple past-due months, so that students who pay late can settle their debt in one transaction.

#### Acceptance Criteria

1. WHEN a trainer registers a payment covering past-due months, THE Payment_Record SHALL accept a reference period that includes months prior to the current month
2. WHEN a late payment covers multiple months, THE Payment_Verification_Service SHALL verify the amount against the total of monthly fees for all covered months
3. WHEN a late payment is confirmed, THE Payment_Record SHALL mark each covered past-due month as "paid" in the student's payment history
4. THE Payment_Record SHALL allow a reference period that spans both past-due months and the current month in a single payment

### Requirement 5: View Student Payment Status by Month

**User Story:** As a trainer, I want to see which months a student has paid and which are pending, so that I can track payment compliance.

#### Acceptance Criteria

1. WHEN a trainer requests payment status for a student, THE Payment_Verification_Service SHALL return a list of months with their payment status ("paid", "pending", or "overdue")
2. THE Payment_Verification_Service SHALL classify a month as "overdue" when the month has passed and no payment covers that month
3. THE Payment_Verification_Service SHALL classify a month as "pending" when the month has not yet passed and no payment covers that month
4. THE Payment_Verification_Service SHALL classify a month as "paid" when a confirmed payment covers that month
5. WHEN a trainer requests payment status, THE Payment_Verification_Service SHALL return months from the student's plan start date up to the current month

### Requirement 6: Payment Amount Serialization and Round-Trip Integrity

**User Story:** As a developer, I want payment amounts and plan data to serialize and deserialize correctly, so that no financial data is lost or corrupted during storage.

#### Acceptance Criteria

1. THE Plan_Registry SHALL serialize the monthly fee value to DynamoDB and deserialize it back without loss of precision
2. THE Payment_Record SHALL serialize the reference period (start month, end month) to DynamoDB and deserialize it back to equivalent values
3. FOR ALL valid Plan_Registry objects, serializing to DynamoDB format then deserializing SHALL produce an equivalent object (round-trip property)
4. FOR ALL valid Payment_Record objects with reference periods, serializing to DynamoDB format then deserializing SHALL produce an equivalent object (round-trip property)
