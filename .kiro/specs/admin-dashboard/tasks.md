# Implementation Plan: Admin Dashboard

## Overview

Implement a lightweight admin dashboard with a single Lambda API endpoint, a metrics aggregation service, and a static HTML frontend. The backend queries DynamoDB for platform-wide KPIs (users, sessions, payments, growth) and returns JSON. Auth uses a pre-shared token stored in Secrets Manager. The frontend is a single HTML file with vanilla JS served from the existing S3 static website bucket.

## Tasks

- [x] 1. Define data models and utility functions
  - [x] 1.1 Create dashboard response dataclasses in `src/models/dashboard_models.py`
    - Define `PeriodInfo`, `UserMetrics`, `SessionMetrics`, `PaymentMetrics`, `DailyDataPoint`, `GrowthMetrics`, `DashboardResponse` dataclasses
    - Add `to_dict()` methods for JSON serialization
    - Add a `safe_rate(numerator, denominator)` utility function that returns `numerator/denominator` if denominator > 0, else 0.0, clamped to [0.0, 1.0]
    - _Requirements: 2.1, 3.1–3.6, 4.1–4.7, 5.1–5.7, 6.1–6.6, 7.5_

  - [ ]* 1.2 Write property test for rate calculation (Property 4)
    - **Property 4: Rate calculation correctness**
    - Test `safe_rate` with Hypothesis-generated non-negative integers for numerator and denominator
    - Assert result is `numerator/denominator` when denominator > 0, `0.0` when denominator == 0, and always in [0.0, 1.0]
    - **Validates: Requirements 3.5, 4.6, 4.7, 5.6, 5.7**

- [x] 2. Implement DashboardMetricsService
  - [x] 2.1 Create `src/services/dashboard_metrics.py` with `DashboardMetricsService` class
    - Constructor receives a `DynamoDBClient` instance
    - Implement `get_all_metrics(start_date, end_date)` that calls each section method independently, catches exceptions per section, and assembles the `DashboardResponse`
    - Implement `get_user_metrics(start_date, end_date)`: scan for trainers/students by entity_type, count active links, derive active trainers/students from sessions, compute avg students per trainer
    - Implement `get_session_metrics(start_date, end_date)`: scan sessions in date range, count by status, compute completion and cancellation rates using `safe_rate`
    - Implement `get_payment_metrics(start_date, end_date)`: scan payments in date range, sum amounts by status, compute confirmation rate and avg payment amount using `safe_rate`
    - Implement `get_growth_metrics(start_date, end_date)`: count new trainers/students by `created_at` in range, group sessions and confirmed payments by day
    - _Requirements: 3.1–3.6, 4.1–4.7, 5.1–5.7, 6.1–6.6, 7.1, 7.4, 7.6_

  - [ ]* 2.2 Write property test for entity counting (Property 1)
    - **Property 1: Entity counting correctness**
    - Generate random lists of trainer, student, and link dicts with Hypothesis; pass to a mock DynamoDB client; call `get_user_metrics`
    - Assert `total_trainers`, `total_students`, `total_active_links`, `new_trainers`, `new_students` match expected counts
    - **Validates: Requirements 3.1, 3.2, 3.6, 6.1, 6.2**

  - [ ]* 2.3 Write property test for active entity counting (Property 2)
    - **Property 2: Active entity counting from sessions**
    - Generate random session dicts with various statuses and trainer/student IDs; call `get_user_metrics`
    - Assert `active_trainers` == distinct trainer_ids and `active_students` == distinct student_ids from sessions with status in ["scheduled", "completed"]
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 2.4 Write property test for session status invariant (Property 3)
    - **Property 3: Session status count invariant**
    - Generate random session dicts; call `get_session_metrics`
    - Assert `scheduled + completed + cancelled + missed == total_sessions` and each count matches the number of sessions with that status
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

  - [ ]* 2.5 Write property test for payment aggregation (Property 5)
    - **Property 5: Payment amount aggregation**
    - Generate random payment dicts with amounts and statuses; call `get_payment_metrics`
    - Assert `total_confirmed_amount` == sum of confirmed amounts, `total_pending_amount` == sum of pending amounts, status counts sum to total
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

  - [ ]* 2.6 Write property test for daily breakdown consistency (Property 6)
    - **Property 6: Daily breakdown consistency**
    - Generate random entities with dates; call growth metrics
    - Assert sum of `trainers_per_day` counts == `new_trainers`, sum of `students_per_day` == `new_students`, sum of `sessions_per_day` == `total_sessions`, sum of `revenue_per_day` == `total_confirmed_amount`
    - **Validates: Requirements 6.3, 6.4, 6.5, 6.6**

  - [ ]* 2.7 Write property test for date range scoping (Property 7)
    - **Property 7: Date range scoping**
    - Generate entities both inside and outside a date range; call metrics methods
    - Assert only items within [start_date, end_date] are counted in session, payment, and growth metrics
    - **Validates: Requirements 2.3, 7.2**

- [x] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement Dashboard Lambda Handler
  - [x] 4.1 Create `src/handlers/dashboard_handler.py`
    - Implement `lambda_handler(event, context)` following existing handler patterns
    - Route `GET /dashboard/auth` to token validation endpoint (returns `{"valid": true}`)
    - Route `GET /dashboard/metrics` to metrics endpoint
    - Implement `_validate_token(event)`: read token from Secrets Manager (`fitagent/dashboard-token/{environment}`), compare against `Authorization: Bearer <token>` header
    - Parse `start_date` and `end_date` query params (default last 30 days), validate YYYY-MM-DD format, enforce max 90-day range, reject start > end
    - Return proper HTTP error responses (401, 400, 500) per the design error handling table
    - Add CORS headers for the static frontend
    - _Requirements: 1.3, 2.3, 7.1, 7.2, 7.3, 7.5, 7.6, 7.7, 8.1, 8.2, 8.3_

  - [ ]* 4.2 Write property test for invalid token rejection (Property 9)
    - **Property 9: Invalid token rejection**
    - Generate random strings that don't match the stored token; invoke handler
    - Assert HTTP 401 and no metric data in response body
    - **Validates: Requirements 1.3, 8.1, 8.2**

  - [ ]* 4.3 Write property test for response structure completeness (Property 8)
    - **Property 8: Response structure completeness**
    - Generate random valid date ranges and mock DynamoDB data; invoke handler with valid token
    - Assert response contains all required keys: `status`, `generated_at`, `period`, `user_metrics`, `session_metrics`, `payment_metrics`, `growth_metrics`, `errors`
    - Assert `generated_at` is valid ISO 8601, `period` contains `start_date` and `end_date`
    - **Validates: Requirements 2.1, 2.2, 7.5**

  - [ ]* 4.4 Write property test for partial response on section failure (Property 10)
    - **Property 10: Partial response on section failure**
    - Mock 1–4 metric section methods to raise exceptions; invoke handler
    - Assert `status == "partial"`, successful sections have data, `errors` lists exactly the failed section names
    - **Validates: Requirements 7.6**

  - [ ]* 4.5 Write unit tests for dashboard handler
    - Test date parameter parsing and defaults (no params → last 30 days)
    - Test date validation: invalid format returns 400, range > 90 days returns 400, start > end returns 400
    - Test auth: missing header returns 401, invalid token returns 401, valid token proceeds
    - Test successful metrics response structure
    - _Requirements: 7.2, 7.3, 7.7, 8.1, 8.2_

- [x] 5. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create static frontend dashboard
  - [x] 6.1 Create `static-website/dashboard.html`
    - Single HTML file with embedded CSS and vanilla JavaScript
    - Login screen: text input for API token, "Login" button; validates token via `GET /dashboard/auth`
    - Store token in `localStorage` with 8-hour client-side session TTL
    - Dashboard view: KPI cards in CSS Grid layout organized into four sections (User, Session, Payment, Growth)
    - Time period selector with options: Today, Last 7 Days, Last 30 Days, Custom Date Range
    - Refresh button that fetches `GET /dashboard/metrics?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` with `Authorization: Bearer <token>`
    - Render growth trend line charts using Chart.js via CDN
    - Handle errors: network errors show retry banner, 401 clears token and redirects to login, partial responses show warning listing unavailable sections
    - Logout button that clears token and returns to login
    - _Requirements: 1.1–1.5, 2.1–2.5, 3.1–3.6, 4.1–4.7, 5.1–5.7, 6.1–6.6_

- [x] 7. Infrastructure updates
  - [x] 7.1 Add Dashboard Lambda and API Gateway resources to `infrastructure/template.yml`
    - Add `DashboardTokenSecret` (Secrets Manager) for `fitagent/dashboard-token/{environment}`
    - Add `DashboardLambdaRole` IAM role with DynamoDB read (Query, Scan, GetItem) and Secrets Manager read permissions
    - Add `DashboardFunction` Lambda resource (Python 3.12, handler `handlers.dashboard_handler.lambda_handler`)
    - Add API Gateway resources: `/dashboard/auth` GET method and `/dashboard/metrics` GET method, both integrated with Dashboard Lambda
    - Add Lambda permission for API Gateway invocation
    - Add `DASHBOARD_TOKEN_SECRET_NAME` environment variable to the Lambda function
    - _Requirements: 7.1, 8.1_

  - [x] 7.2 Add `dashboard_token_secret_name` to `src/config.py` Settings class
    - Add optional field `dashboard_token_secret_name: Optional[str] = None`
    - Add `get_dashboard_token()` method that reads from Secrets Manager
    - _Requirements: 8.1, 8.2_

- [x] 8. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Integration tests
  - [ ]* 9.1 Write integration tests for dashboard handler with mocked DynamoDB
    - Seed DynamoDB (via moto) with known trainers, students, links, sessions, and payments
    - Invoke `lambda_handler` with valid token and date range
    - Assert complete response matches expected metric values from seeded data
    - Test auth flow: valid token returns 200, invalid token returns 401
    - Test partial failure: mock one service method to raise, verify `status: "partial"` and `errors` array
    - _Requirements: 7.1, 7.5, 7.6, 8.1_

- [x] 10. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design uses Python, so all implementation tasks use Python 3.12
- Tests use pytest + Hypothesis (already in the project stack) with moto for AWS mocking
