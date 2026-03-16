# Requirements Document

## Introduction

This document specifies requirements for improving the FitAgent test infrastructure to achieve a 95%+ pass rate, implement proper test pyramid architecture, and establish reliable CI/CD testing with LocalStack. The current test suite has 676 tests with a 90% pass rate (66 failing tests) and lacks proper test categorization following the test pyramid approach.

## Glossary

- **Test_Suite**: The complete collection of automated tests for the FitAgent system
- **Test_Pyramid**: Testing strategy with many fast unit tests at the base, fewer integration tests in the middle, and minimal E2E tests at the top
- **Unit_Test**: Test that validates a single function or class in isolation with mocked dependencies
- **Integration_Test**: Test that validates interaction between multiple components with real dependencies
- **E2E_Test**: End-to-end test that validates complete user journeys through the system
- **Property_Test**: Test that validates invariants and properties across generated input ranges using Hypothesis
- **Contract_Test**: Test that validates Lambda handler input/output contracts match expected schemas
- **LocalStack**: AWS service emulator for local development and testing
- **CI_Pipeline**: Continuous Integration pipeline that runs automated tests on code changes
- **Test_Fixture**: Reusable test setup code that provides consistent test data and environment
- **Mock_Object**: Test double that simulates real object behavior in isolated tests
- **Test_Coverage**: Percentage of code lines executed during test runs

## Requirements

### Requirement 1: Fix Failing Tests

**User Story:** As a developer, I want all existing tests to pass reliably, so that I can trust the test suite to catch regressions.

#### Acceptance Criteria

1. WHEN LocalStack-dependent tests run, THE Test_Suite SHALL connect to LocalStack successfully
2. WHEN tests validate response messages, THE Test_Suite SHALL assert against the correct language (Portuguese)
3. WHEN tests use conversation state, THE Test_Suite SHALL use proper ConversationState objects instead of dict mocks
4. WHEN property tests detect bugs, THE Test_Suite SHALL document the bugs as known issues
5. WHEN calendar integration tests run, THE Test_Suite SHALL handle error cases correctly
6. WHEN message processor batch tests run, THE Test_Suite SHALL process batches without failures
7. THE Test_Suite SHALL achieve a minimum 95% pass rate across all test categories

### Requirement 2: Implement Test Pyramid Architecture

**User Story:** As a developer, I want tests organized following the test pyramid, so that I get fast feedback and reliable coverage.

#### Acceptance Criteria

1. THE Test_Suite SHALL contain at least 500 Unit_Tests for isolated component validation
2. THE Test_Suite SHALL contain between 50 and 100 Integration_Tests for component interaction validation
3. THE Test_Suite SHALL contain between 3 and 10 E2E_Tests for critical user journey validation
4. THE Test_Suite SHALL maintain existing Property_Tests for invariant validation
5. WHEN Unit_Tests execute, THE Test_Suite SHALL complete execution within 30 seconds
6. WHEN Integration_Tests execute, THE Test_Suite SHALL complete execution within 5 minutes
7. WHEN E2E_Tests execute, THE Test_Suite SHALL complete execution within 10 minutes
8. THE Test_Suite SHALL organize tests in separate directories: tests/unit/, tests/integration/, tests/e2e/, tests/property/

### Requirement 3: Create Critical E2E Test Scenarios

**User Story:** As a product owner, I want E2E tests for critical user journeys, so that I know the system works end-to-end.

#### Acceptance Criteria

1. THE Test_Suite SHALL include an E2E_Test for trainer onboarding through WhatsApp
2. THE Test_Suite SHALL include an E2E_Test for student registration and session scheduling
3. THE Test_Suite SHALL include an E2E_Test for payment receipt submission and tracking
4. THE Test_Suite SHALL include an E2E_Test for calendar integration with Google Calendar
5. THE Test_Suite SHALL include an E2E_Test for automated session reminders via EventBridge
6. WHEN E2E_Tests run, THE Test_Suite SHALL use real LocalStack services (DynamoDB, S3, SQS, EventBridge, Lambda)
7. WHEN E2E_Tests run, THE Test_Suite SHALL mock external APIs (Twilio, Google Calendar, Bedrock)

### Requirement 4: Implement Lambda Handler Contract Tests

**User Story:** As a developer, I want contract tests for Lambda handlers, so that I catch interface breaking changes early.

#### Acceptance Criteria

1. THE Test_Suite SHALL include Contract_Tests for webhook_handler input/output schemas
2. THE Test_Suite SHALL include Contract_Tests for message_processor input/output schemas
3. THE Test_Suite SHALL include Contract_Tests for session_reminder input/output schemas
4. THE Test_Suite SHALL include Contract_Tests for payment_reminder input/output schemas
5. THE Test_Suite SHALL include Contract_Tests for notification_sender input/output schemas
6. THE Test_Suite SHALL include Contract_Tests for oauth_callback input/output schemas
7. THE Test_Suite SHALL include Contract_Tests for session_confirmation input/output schemas
8. WHEN Lambda handler signatures change, THE Contract_Test SHALL fail if the contract is violated

### Requirement 5: Configure LocalStack for CI/CD

**User Story:** As a DevOps engineer, I want LocalStack running in CI/CD, so that integration tests run reliably in the pipeline.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL start LocalStack services before running Integration_Tests
2. THE CI_Pipeline SHALL initialize DynamoDB tables using localstack-init scripts
3. THE CI_Pipeline SHALL initialize S3 buckets using localstack-init scripts
4. THE CI_Pipeline SHALL initialize SQS queues using localstack-init scripts
5. THE CI_Pipeline SHALL wait for LocalStack health checks before running tests
6. WHEN LocalStack services fail to start, THE CI_Pipeline SHALL fail with a descriptive error message
7. WHEN tests complete, THE CI_Pipeline SHALL stop LocalStack services and clean up resources
8. THE CI_Pipeline SHALL cache LocalStack Docker images to reduce startup time

### Requirement 6: Improve Test Fixtures and Utilities

**User Story:** As a developer, I want reusable test fixtures, so that I can write tests faster with less duplication.

#### Acceptance Criteria

1. THE Test_Suite SHALL provide Test_Fixtures for creating valid Trainer entities
2. THE Test_Suite SHALL provide Test_Fixtures for creating valid Student entities
3. THE Test_Suite SHALL provide Test_Fixtures for creating valid Session entities
4. THE Test_Suite SHALL provide Test_Fixtures for creating valid Payment entities
5. THE Test_Suite SHALL provide Test_Fixtures for mocked Twilio clients
6. THE Test_Suite SHALL provide Test_Fixtures for mocked Bedrock clients
7. THE Test_Suite SHALL provide Test_Fixtures for mocked Calendar API clients
8. THE Test_Suite SHALL provide Test_Fixtures for LocalStack AWS clients (DynamoDB, S3, SQS)
9. WHEN tests use Test_Fixtures, THE Test_Suite SHALL ensure data isolation between tests

### Requirement 7: Maintain Property-Based Testing

**User Story:** As a developer, I want property-based tests for critical invariants, so that I catch edge cases automatically.

#### Acceptance Criteria

1. THE Test_Suite SHALL include a Property_Test for session scheduling invariants (no overlapping sessions)
2. THE Test_Suite SHALL include a Property_Test for payment calculation invariants (total equals sum of payments)
3. THE Test_Suite SHALL include a Property_Test for phone number validation invariants
4. THE Test_Suite SHALL include a Property_Test for DynamoDB key generation invariants (unique keys)
5. THE Test_Suite SHALL include a Property_Test for calendar sync round-trip properties (create then read equals original)
6. WHEN Property_Tests detect counterexamples, THE Test_Suite SHALL report the minimal failing case
7. THE Test_Suite SHALL run Property_Tests with at least 100 generated examples per property

### Requirement 8: Achieve Test Coverage Targets

**User Story:** As a tech lead, I want 70% minimum test coverage, so that critical code paths are validated.

#### Acceptance Criteria

1. THE Test_Suite SHALL achieve at least 70% line coverage across all source code
2. THE Test_Suite SHALL achieve at least 80% line coverage for services/ directory
3. THE Test_Suite SHALL achieve at least 90% line coverage for tools/ directory
4. THE Test_Suite SHALL achieve at least 60% line coverage for handlers/ directory
5. WHEN coverage reports generate, THE Test_Suite SHALL identify uncovered critical paths
6. WHEN coverage drops below thresholds, THE CI_Pipeline SHALL fail the build
7. THE Test_Suite SHALL exclude test files and configuration files from coverage calculations

### Requirement 9: Implement Test Categorization and Execution

**User Story:** As a developer, I want to run specific test categories, so that I get fast feedback during development.

#### Acceptance Criteria

1. THE Test_Suite SHALL support running only Unit_Tests via pytest marker
2. THE Test_Suite SHALL support running only Integration_Tests via pytest marker
3. THE Test_Suite SHALL support running only E2E_Tests via pytest marker
4. THE Test_Suite SHALL support running only Property_Tests via pytest marker
5. THE Test_Suite SHALL support running smoke tests for quick validation
6. WHEN developers run tests locally, THE Test_Suite SHALL default to Unit_Tests only
7. WHEN CI_Pipeline runs, THE Test_Suite SHALL execute all test categories in sequence
8. THE Test_Suite SHALL provide make commands for each test category (make test-unit, make test-integration, make test-e2e)

### Requirement 10: Document Testing Strategy and Guidelines

**User Story:** As a new developer, I want testing documentation, so that I understand how to write and run tests.

#### Acceptance Criteria

1. THE Test_Suite SHALL include documentation for writing Unit_Tests
2. THE Test_Suite SHALL include documentation for writing Integration_Tests
3. THE Test_Suite SHALL include documentation for writing E2E_Tests
4. THE Test_Suite SHALL include documentation for writing Property_Tests
5. THE Test_Suite SHALL include documentation for using Test_Fixtures
6. THE Test_Suite SHALL include documentation for running tests locally with LocalStack
7. THE Test_Suite SHALL include documentation for debugging failing tests
8. THE Test_Suite SHALL include examples of well-written tests for each category
