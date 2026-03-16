# Implementation Plan: Test Infrastructure Improvements

## Overview

This implementation plan establishes a comprehensive test infrastructure for FitAgent following the test pyramid architecture. The plan addresses 66 failing tests, implements proper test categorization (unit, integration, E2E, property-based, contract), integrates LocalStack for AWS service emulation, and establishes CI/CD testing pipelines. The implementation follows a six-phase approach: foundation setup, fixing existing tests, adding new test categories, improving fixtures, configuring CI/CD, and documentation.

## Tasks

- [x] 1. Set up test infrastructure foundation
  - [x] 1.1 Create test directory structure and configuration files
    - Create `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/property/`, `tests/contract/` directories
    - Create `tests/fixtures/`, `tests/utils/`, `tests/examples/` directories
    - Create `pytest.ini` with markers and Hypothesis configurationf
    - Create `.coveragerc` with coverage targets and exclusions
    - Update `requirements-dev.txt` with test dependencies (pytest, hypothesis, moto, pytest-cov)
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 1.2 Write property test for test configuration loading
    - **Property 2: Test Fixture Data Isolation**
    - **Validates: Requirements 6.9**

- [x] 2. Create test fixture system
  - [x] 2.1 Implement entity factories
    - Create `tests/fixtures/factories.py` with TrainerFactory, StudentFactory, SessionFactory, PaymentFactory
    - Each factory provides builder pattern with sensible defaults
    - Factories generate valid test entities with UUID4 IDs
    - _Requirements: 6.1, 6.2_

  - [x] 2.2 Implement AWS client fixtures for unit tests
    - Create moto-based fixtures in `tests/conftest.py`: dynamodb_client, s3_client, sqs_client
    - Fixtures provide mocked AWS clients for fast unit tests
    - _Requirements: 6.3, 6.4_

  - [x] 2.3 Implement LocalStack client fixtures for integration/E2E tests
    - Create LocalStack-based fixtures in `tests/conftest.py`: dynamodb_localstack, s3_localstack, sqs_localstack, lambda_localstack, events_localstack
    - Add localstack_endpoint fixture with health check
    - Fixtures connect to LocalStack at http://localhost:4566
    - _Requirements: 5.1, 5.2, 6.3_

  - [x] 2.4 Implement external API mocks
    - Create `tests/fixtures/mocks.py` with MockTwilioClient, MockBedrockClient, MockCalendarClient
    - Mock clients track calls and provide configurable responses
    - Create pytest fixtures: mock_twilio, mock_bedrock, mock_calendar
    - _Requirements: 6.5_

  - [x] 2.5 Create test utilities
    - Create `tests/utils/localstack_helpers.py` with wait_for_localstack, initialize_localstack_resources, cleanup_localstack_resources
    - Create `tests/utils/test_data.py` with generate_phone_number, generate_future_datetime, generate_receipt_image
    - Create `tests/utils/assertions.py` with assert_dynamodb_item_exists, assert_s3_object_exists, assert_sqs_message_sent, assert_portuguese_message
    - _Requirements: 6.6, 6.7, 6.8_

- [x] 3. Checkpoint - Verify fixture system works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Fix existing failing tests (Phase 1: LocalStack connection issues)
  - [x] 4.1 Update fixtures to properly detect LocalStack vs moto usage
    - Modify conftest.py to check USE_LOCALSTACK environment variable
    - Add health checks before LocalStack test execution
    - Implement retry logic for transient connection failures
    - _Requirements: 1.1, 1.2_

  - [x] 4.2 Fix 15 tests failing due to LocalStack connection issues
    - Update tests to use correct fixtures (localstack vs moto)
    - Add wait_for_localstack calls where needed
    - Verify tests pass with LocalStack running
    - _Requirements: 1.1, 1.2_

- [x] 5. Fix existing failing tests (Phase 2: Language assertion fixes)
  - [x] 5.1 Audit and fix Portuguese message assertions
    - Update all message assertions to expect Portuguese responses
    - Use assert_portuguese_message helper for language validation
    - Document language expectations in test docstrings
    - Fix approximately 25 tests with incorrect language assertions
    - _Requirements: 1.3_

- [x] 6. Fix existing failing tests (Phase 3: Mock object fixes)
  - [ ] 6.1 Replace dict mocks with proper ConversationState objects
    - Update conversation_state fixtures to return real ConversationState objects
    - Replace dict mocks in tests with proper typed objects
    - Add type hints to catch future mock misuse
    - Fix approximately 20 tests with incorrect mock types
    - _Requirements: 1.4_

- [ ] 7. Fix existing failing tests (Phase 4-6: Remaining issues)
  - [ ] 7.1 Document property test bugs and mark with xfail
    - Review property test failures and document as GitHub issues
    - Mark tests with @pytest.mark.xfail(reason="Known bug #123")
    - Link to bug tracking in test docstrings
    - _Requirements: 1.5_

  - [ ] 7.2 Add calendar integration error handling tests
    - Add error case tests for calendar API failures
    - Test OAuth token expiration scenarios
    - Test calendar service unavailability
    - _Requirements: 1.6_

  - [ ] 7.3 Fix message processor batch handling tests
    - Review and fix batch processing logic tests
    - Add tests for partial batch failures
    - Test SQS batch item failure reporting
    - _Requirements: 1.7_

- [ ] 8. Checkpoint - Verify all existing tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement contract test framework
  - [ ] 9.1 Create contract test schemas
    - Create `tests/contract/schemas.py` with Pydantic schemas for all Lambda handlers
    - Define WebhookHandlerInput/Output, MessageProcessorInput/Output, and schemas for 5 other handlers
    - _Requirements: 4.1, 4.2_

  - [ ] 9.2 Write contract tests for all Lambda handlers
    - Create `tests/contract/test_handler_contracts.py`
    - Write contract tests for webhook_handler, message_processor, session_reminder, payment_reminder, notification_sender, oauth_callback, session_confirmation
    - Each test validates input/output schema compliance
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 9.3 Write property test for contract validation
    - **Property 1: Contract Test Failure Detection**
    - **Validates: Requirements 4.8**

- [ ] 10. Implement E2E test framework
  - [ ] 10.1 Create E2E test base class
    - Create `tests/e2e/base.py` with E2ETestBase class
    - Implement setup_e2e_environment fixture with full LocalStack setup
    - Add helper methods: send_whatsapp_message, wait_for_sqs_processing, trigger_eventbridge_rule
    - _Requirements: 3.1, 3.2_

  - [ ] 10.2 Create Lambda deployment script for E2E tests
    - Create `tests/e2e/deploy_lambdas.sh` to deploy Lambda functions to LocalStack
    - Script packages and deploys all 7 Lambda handlers
    - _Requirements: 3.3_

  - [ ] 10.3 Write E2E test for trainer onboarding journey
    - Create `tests/e2e/test_trainer_onboarding_e2e.py`
    - Test complete flow: WhatsApp message → webhook → SQS → message processor → Bedrock → response
    - _Requirements: 3.4, 3.5_

  - [ ] 10.4 Write E2E test for student registration and session scheduling
    - Create `tests/e2e/test_student_registration_e2e.py`
    - Test flow: register student → schedule session → conflict detection → confirmation
    - _Requirements: 3.6_

  - [ ] 10.5 Write E2E test for payment tracking
    - Create `tests/e2e/test_payment_tracking_e2e.py`
    - Test flow: submit receipt → S3 upload → payment record → status update
    - _Requirements: 3.7_

  - [ ] 10.6 Write E2E test for calendar integration
    - Create `tests/e2e/test_calendar_integration_e2e.py`
    - Test flow: OAuth connection → calendar sync → event creation → conflict detection
    - _Requirements: 3.8_

  - [ ] 10.7 Write E2E test for session reminders
    - Create `tests/e2e/test_session_reminders_e2e.py`
    - Test flow: EventBridge trigger → reminder Lambda → SQS → notification
    - _Requirements: 3.9_

- [ ] 11. Implement property-based tests
  - [ ] 11.1 Write property tests for session scheduling
    - Create `tests/property/test_session_properties.py`
    - Test properties: no overlap, conflict detection, valid datetime ranges
    - Use Hypothesis to generate session data
    - _Requirements: 7.1, 7.2_

  - [ ] 11.2 Write property tests for payment tracking
    - Create `tests/property/test_payment_properties.py`
    - Test properties: amount validation, status transitions, receipt URL format
    - _Requirements: 7.3_

  - [ ] 11.3 Write property tests for phone number validation
    - Create `tests/property/test_validation_properties.py`
    - Test properties: format validation, country code handling, normalization
    - _Requirements: 7.4_

  - [ ] 11.4 Write property tests for conversation state management
    - Create `tests/property/test_conversation_state_properties.py`
    - Test properties: state transitions, data persistence, timeout handling
    - _Requirements: 7.5_

  - [ ] 11.5 Write property tests for DynamoDB operations
    - Create `tests/property/test_dynamodb_properties.py`
    - Test properties: round-trip consistency, query correctness, GSI integrity
    - _Requirements: 7.6, 7.7_

- [ ] 12. Expand unit test coverage
  - [ ] 12.1 Write unit tests for services layer
    - Add tests for message_router, conversation_handlers, menu_system, calendar_sync, receipt_storage, session_conflict
    - Target 80%+ coverage for services
    - _Requirements: 2.1, 2.2, 8.1_

  - [ ]* 12.2 Write unit tests for services layer edge cases
    - Test error conditions, boundary cases, invalid inputs
    - _Requirements: 2.1, 2.2_

  - [ ] 12.3 Write unit tests for tools layer
    - Add tests for student_tools, session_tools, payment_tools, calendar_tools, notification_tools
    - Target 90%+ coverage for tools
    - _Requirements: 2.3, 8.1_

  - [ ]* 12.4 Write unit tests for tools layer edge cases
    - Test error conditions, validation failures, external API errors
    - _Requirements: 2.3_

  - [ ] 12.5 Write unit tests for handlers layer
    - Add tests for all 7 Lambda handlers with mocked dependencies
    - Target 60%+ coverage for handlers
    - _Requirements: 2.4, 8.1_

  - [ ]* 12.6 Write unit tests for handlers layer error scenarios
    - Test exception handling, retry logic, DLQ scenarios
    - _Requirements: 2.4_

  - [ ] 12.7 Write unit tests for models layer
    - Add tests for entities, dynamodb_client with moto
    - Target 80%+ coverage for models
    - _Requirements: 2.5, 8.1_

  - [ ]* 12.8 Write unit tests for models layer validation
    - Test Pydantic validation, type coercion, constraint enforcement
    - _Requirements: 2.5_

  - [ ] 12.9 Write unit tests for utils layer
    - Add tests for validation, encryption, logging, retry, i18n
    - Target 75%+ coverage for utils
    - _Requirements: 2.6, 8.1_

  - [ ]* 12.10 Write unit tests for utils layer edge cases
    - Test error handling, boundary conditions, encoding issues
    - _Requirements: 2.6_

- [ ] 13. Checkpoint - Verify test pyramid targets met
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Add integration tests
  - [ ] 14.1 Write integration tests for DynamoDB operations
    - Create `tests/integration/test_dynamodb_integration.py`
    - Test entity CRUD operations, GSI queries, batch operations with LocalStack
    - _Requirements: 2.7, 2.8_

  - [ ]* 14.2 Write integration tests for DynamoDB error scenarios
    - Test conditional writes, transaction failures, throttling
    - _Requirements: 2.7_

  - [ ] 14.3 Write integration tests for S3 operations
    - Create `tests/integration/test_s3_integration.py`
    - Test receipt upload, presigned URLs, object retrieval with LocalStack
    - _Requirements: 2.9_

  - [ ]* 14.4 Write integration tests for S3 error scenarios
    - Test upload failures, missing objects, permission errors
    - _Requirements: 2.9_

  - [ ] 14.5 Write integration tests for SQS operations
    - Create `tests/integration/test_sqs_integration.py`
    - Test message sending, receiving, batch processing, DLQ with LocalStack
    - _Requirements: 2.10_

  - [ ]* 14.6 Write integration tests for SQS error scenarios
    - Test message visibility timeout, poison messages, queue purging
    - _Requirements: 2.10_

  - [ ] 14.7 Write integration tests for webhook flow
    - Create `tests/integration/test_webhook_flow.py`
    - Test API Gateway → Lambda → SQS flow with LocalStack
    - _Requirements: 2.11_

  - [ ] 14.8 Write integration tests for calendar sync
    - Create `tests/integration/test_calendar_sync.py`
    - Test calendar API integration with mocked external APIs
    - _Requirements: 2.12_

- [ ] 15. Configure CI/CD pipeline
  - [ ] 15.1 Create GitHub Actions workflow for tests
    - Create `.github/workflows/test.yml` with jobs for lint, type-check, unit, integration, E2E, property, contract tests
    - Configure LocalStack service container for integration and E2E jobs
    - Add coverage reporting with codecov
    - _Requirements: 5.3, 5.4, 5.5, 5.6_

  - [ ] 15.2 Update Makefile with test commands
    - Add make targets: test, test-unit, test-integration, test-e2e, test-property, test-contract, test-all, test-coverage
    - Each target includes LocalStack startup/shutdown where needed
    - _Requirements: 9.4, 9.5_

  - [ ] 15.3 Configure test execution timeouts and retries
    - Set pytest timeouts: 30s unit, 5min integration, 10min E2E
    - Configure pytest-rerunfailures for flaky tests
    - Add timeout markers to slow tests
    - _Requirements: 5.7, 5.8_

  - [ ] 15.4 Set up coverage enforcement
    - Configure coverage thresholds: 70% overall, 80% services, 90% tools
    - Add coverage check to CI pipeline that fails build if below threshold
    - Generate HTML coverage reports
    - _Requirements: 8.2, 8.3, 8.4_

- [ ] 16. Create test documentation
  - [ ] 16.1 Create tests README
    - Create `tests/README.md` with overview of test structure and quick start guide
    - Document test categories, execution commands, fixture usage
    - _Requirements: 10.1_

  - [ ] 16.2 Create comprehensive testing guide
    - Create `tests/TESTING_GUIDE.md` with detailed guide for writing unit, integration, E2E, property-based tests
    - Include sections on using fixtures, debugging tests, best practices
    - _Requirements: 10.2, 10.3, 10.4_

  - [ ] 16.3 Create example test files
    - Create `tests/examples/example_unit_test.py`, `example_integration_test.py`, `example_e2e_test.py`, `example_property_test.py`
    - Each example demonstrates best practices and common patterns
    - _Requirements: 10.5_

- [ ] 17. Final checkpoint - Run complete test suite
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows a logical progression: foundation → fix existing → add new → configure CI/CD → document
- LocalStack must be running for integration and E2E tests (handled by Makefile commands)
- All tests should be idempotent and isolated (no shared state between tests)
