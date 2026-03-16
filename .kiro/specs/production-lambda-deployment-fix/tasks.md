# Implementation Plan

- [x] 1. Write bug condition exploration tests (BEFORE implementing fixes)
  - **Property 1: Bug Condition** - Lambda Deployment and Runtime Failures
  - **CRITICAL**: These tests MUST FAIL on unfixed code - failures confirm the bugs exist
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior - they will validate the fixes when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bugs exist
  - **Scoped PBT Approach**: For deterministic bugs, scope properties to concrete failing cases to ensure reproducibility

  - [x] 1.1 Test Bug 1 - Module Import Failure
    - Create minimal Lambda package using current `scripts/package_lambda.sh`
    - Attempt to import `src.handlers.webhook_handler` in Python test environment
    - **EXPECTED OUTCOME**: Test FAILS with `ModuleNotFoundError: No module named 'src'`
    - Document counterexample: Package structure places `src/` as subdirectory, Python cannot resolve imports
    - _Requirements: 1.1, 2.1_

  - [x] 1.2 Test Bug 2 - OpenTelemetry Initialization Failure
    - Create Lambda function that imports and initializes Strands SDK
    - Monitor for OpenTelemetry propagator errors during initialization
    - **EXPECTED OUTCOME**: Test FAILS with `ValueError: Propagator tracecontext not found` or similar
    - Document counterexample: Missing or incompatible propagator dependencies in Lambda environment
    - _Requirements: 1.2, 2.2_

  - [x] 1.3 Test Bug 3 - Twilio Message Delivery Failure
    - Configure test environment with Secrets Manager containing sandbox credentials
    - Attempt to send WhatsApp message via Twilio API
    - **EXPECTED OUTCOME**: Test FAILS with Twilio error 63015 (sender not approved)
    - Document counterexample: Sandbox phone number in secrets causes delivery rejection
    - _Requirements: 1.3, 2.3_

  - [x] 1.4 Test Bug 4 - Stale Secret Caching
    - Deploy Lambda with initial Twilio credentials
    - Update credentials in Secrets Manager (simulated)
    - Invoke Lambda and check which credentials are used
    - **EXPECTED OUTCOME**: Test FAILS - Lambda uses old cached credentials
    - Document counterexample: Settings object cached across invocations prevents fresh secret loading
    - _Requirements: 1.4, 2.4_

  - [x] 1.5 Test Bug 5 - SQS Processing Failure
    - Send message to SQS queue that triggers processing error
    - Monitor message visibility and retry behavior
    - **EXPECTED OUTCOME**: Test FAILS - Message stuck in queue without DLQ routing
    - Document counterexample: Insufficient error handling leaves messages unprocessed
    - _Requirements: 1.5, 2.5_

  - Mark task complete when all exploration tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 2. Write preservation property tests (BEFORE implementing fixes)
  - **Property 2: Preservation** - Existing Development and Deployment Workflows
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code for non-buggy workflows
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements
  - Property-based testing generates many test cases for stronger guarantees
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)

  - [x] 2.1 Test Local Development Preservation
    - Observe: `make start`, `make test`, `make logs` work correctly on unfixed code
    - Write property-based test: Local development commands execute successfully
    - Verify test passes on UNFIXED code
    - _Requirements: 3.5_

  - [x] 2.2 Test Dependency Management Preservation
    - Observe: All packages from requirements.txt are included in Lambda package
    - Write property-based test: For all dependencies in requirements.txt, verify they exist in package
    - Verify test passes on UNFIXED code
    - _Requirements: 3.1_

  - [x] 2.3 Test CloudFormation Validation Preservation
    - Observe: `aws cloudformation validate-template` passes on infrastructure template
    - Write property-based test: Template validation succeeds without errors
    - Verify test passes on UNFIXED code
    - _Requirements: 3.4_

  - [x] 2.4 Test AWS Service Integration Preservation
    - Observe: DynamoDB queries, S3 operations, SQS operations work correctly
    - Write property-based test: For all AWS service operations, verify they execute with correct IAM permissions
    - Verify test passes on UNFIXED code
    - _Requirements: 3.3_

  - [x] 2.5 Test OpenTelemetry Patch Preservation
    - Observe: Strands SDK functionality remains intact after patching
    - Write property-based test: SDK operations produce same results with and without patch
    - Verify test passes on UNFIXED code
    - _Requirements: 3.2_

  - Mark task complete when all preservation tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix for production Lambda deployment failures

  - [x] 3.1 Implement Fix 1 - Module Import Resolution
    - Modify `scripts/package_lambda.sh` to flatten package structure
    - Change from `cp -r src "$PACKAGE_DIR/"` to `cp -r src/* "$PACKAGE_DIR/"`
    - Update handler configuration to use flat import paths (e.g., `handlers.webhook_handler.lambda_handler`)
    - Update all Python import statements to use flat imports (e.g., `from services.twilio_client import TwilioClient`)
    - _Bug_Condition: isBugCondition(input) where input.phase == "lambda_import" AND input.import_path STARTS_WITH "src." AND input.package_structure == "nested_src_directory"_
    - _Expected_Behavior: Lambda successfully imports all required modules without ModuleNotFoundError_
    - _Preservation: Production dependencies from requirements.txt continue to be included (3.1)_
    - _Requirements: 1.1, 2.1, 3.1_

  - [x] 3.2 Implement Fix 2 - OpenTelemetry Compatibility
    - Enhance `scripts/patch_opentelemetry_propagate.py` to improve patch logic
    - Search for exact pattern in OpenTelemetry propagate module
    - Replace ValueError raise with try-except block that logs warning and continues
    - Add verification step in `scripts/package_lambda.sh` to confirm patch was applied
    - Add fallback handling in Lambda handler to catch initialization errors
    - Ensure OpenTelemetry propagator packages are in requirements.txt
    - _Bug_Condition: isBugCondition(input) where input.phase == "sdk_initialization" AND input.sdk == "strands_agents" AND input.propagator_loading_fails == true_
    - _Expected_Behavior: SDK initializes successfully, skipping unavailable propagators with warnings_
    - _Preservation: OpenTelemetry patch preserves original Strands SDK functionality (3.2)_
    - _Requirements: 1.2, 2.2, 3.2_

  - [x] 3.3 Implement Fix 3 - Twilio Configuration Management
    - Add secret validation to `scripts/deploy_production.sh`
    - Retrieve Twilio secret and validate it doesn't contain sandbox number
    - Force Lambda update after secret changes by updating environment variable
    - Modify `src/config.py` to disable secrets caching in production
    - Implement cache invalidation mechanism with `reload_secrets()` method
    - _Bug_Condition: isBugCondition(input) where input.phase == "message_sending" AND input.twilio_error_code == 63015 AND input.phone_number_source == "stale_or_sandbox"_
    - _Expected_Behavior: Messages sent successfully using production Twilio phone number_
    - _Preservation: Twilio signature validation logic continues to work (3.3)_
    - _Requirements: 1.3, 2.3, 3.3_

  - [x] 3.4 Implement Fix 4 - Secret Caching Resolution
    - Modify `src/config.py` `_get_secret()` method to disable caching
    - Remove response caching in `_get_secrets_manager_client()`
    - Implement `reload_secrets()` method to force fresh secret retrieval
    - Update `scripts/deploy_production.sh` to force Lambda configuration update after secret changes
    - Add `SECRETS_UPDATED` environment variable with timestamp to trigger reload
    - _Bug_Condition: isBugCondition(input) where input.phase == "secret_retrieval" AND input.secret_updated_in_secrets_manager == true AND input.lambda_returns_old_value == true_
    - _Expected_Behavior: Lambda loads fresh credentials after function code update or environment variable change_
    - _Preservation: AWS Secrets Manager IAM permissions remain unchanged (3.3)_
    - _Requirements: 1.4, 2.4, 3.3_

  - [x] 3.5 Implement Fix 5 - SQS Message Processing Robustness
    - _Bug_Condition: isBugCondition(input) where input.phase == "message_processing" AND input.processing_error_occurs == true AND input.message_stuck_in_queue == true_
    - _Expected_Behavior: Messages either successfully processed, retried with exponential backoff, or moved to DLQ after max retries_
    - _Preservation: SQS FIFO queue ordering and deduplication logic preserved (3.3)_
    - _Requirements: 1.5, 2.5, 3.3_

    - [x] 3.5.1 Add error handling to message_processor.py
      - Add comprehensive try-except blocks to `src/handlers/message_processor.py`
      - Handle ValidationError (user input errors) - log and delete message
      - Handle ClientError (AWS service errors) - log and allow retry
      - Handle Exception (unexpected errors) - log and allow retry
      - Add structured logging for each error type with context

    - [x] 3.5.2 Configure SQS queue retry policy
      - Update CloudFormation template for SQS queue configuration
      - Set VisibilityTimeout: 300 seconds (5 minutes)
      - Set MessageRetentionPeriod: 1209600 seconds (14 days)
      - Set maxReceiveCount: 3 (retry up to 3 times before DLQ)

    - [x] 3.5.3 Add Dead Letter Queue (DLQ) configuration
      - Create DLQ resource in CloudFormation template
      - Configure RedrivePolicy to route failed messages to DLQ
      - Set appropriate retention period for DLQ messages

    - [x] 3.5.4 Implement CloudWatch alarms for monitoring
      - Add CloudWatch alarm for DLQ message count
      - Set threshold to alert when messages appear in DLQ
      - Configure SNS notification for alarm triggers

  - [x] 3.6 Implement Deployment Script Improvements
    - Add pre-deployment validation to `scripts/deploy_production.sh`
    - Validate all required secrets exist before deployment
    - Add post-deployment smoke test to invoke Lambda with test event
    - Check Lambda response for errors and fail deployment if found
    - Implement automatic rollback capability using CloudFormation RollbackConfiguration
    - Add rollback triggers based on CloudWatch alarms
    - _Bug_Condition: All five bug conditions from above_
    - _Expected_Behavior: Deployment succeeds with all validations passing, or rolls back automatically on failure_
    - _Preservation: CloudFormation template validation continues to run before deployment (3.4)_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.4_

  - [x] 3.7 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Lambda Deployment and Runtime Success
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run all bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: All tests PASS (confirms bugs are fixed)
    - Verify Bug 1 test: Lambda imports succeed without ModuleNotFoundError
    - Verify Bug 2 test: Strands SDK initializes without OpenTelemetry errors
    - Verify Bug 3 test: Twilio messages delivered successfully
    - Verify Bug 4 test: Fresh secrets loaded after updates
    - Verify Bug 5 test: SQS messages processed or routed to DLQ
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.8 Verify preservation tests still pass
    - **Property 2: Preservation** - Existing Development and Deployment Workflows
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run all preservation property tests from step 2
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions)
    - Verify local development preservation test passes
    - Verify dependency management preservation test passes
    - Verify CloudFormation validation preservation test passes
    - Verify AWS service integration preservation test passes
    - Verify OpenTelemetry patch preservation test passes
    - Confirm all tests still pass after fixes (no regressions)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint - Ensure all tests pass
  - Run complete test suite: `make test`
  - Verify all unit tests pass
  - Verify all integration tests pass
  - Verify all property-based tests pass
  - Verify bug condition exploration tests pass (bugs are fixed)
  - Verify preservation tests pass (no regressions)
  - Deploy to staging environment and run smoke tests
  - Test end-to-end WhatsApp message flow
  - Verify Lambda functions initialize and process messages correctly
  - Ensure all tests pass, ask the user if questions arise
