# Production Lambda Deployment Fix - Bugfix Design

## Overview

The production Lambda deployment for FitAgent is experiencing five critical failures that prevent the WhatsApp service from functioning. This bugfix addresses the complete deployment pipeline to restore service functionality. The issues span module import errors, OpenTelemetry SDK initialization failures, Twilio configuration problems, stale secret caching, and SQS message processing issues. The fix strategy involves correcting the Lambda package structure, patching OpenTelemetry compatibility issues, ensuring proper secret management, and implementing robust error handling for message processing.

## Glossary

- **Bug_Condition (C)**: The conditions that trigger deployment failures - Lambda import errors, OpenTelemetry initialization failures, Twilio configuration issues, stale secret caching, or SQS processing failures
- **Property (P)**: The desired behavior - successful Lambda deployment with working imports, proper SDK initialization, correct Twilio configuration, fresh secret loading, and reliable message processing
- **Preservation**: Existing functionality that must remain unchanged - local development environment, dependency management, CloudFormation validation, IAM permissions, and AWS service integrations
- **Lambda Package Structure**: The directory layout and file organization within the Lambda deployment ZIP file that determines how Python imports resolve
- **OpenTelemetry Propagators**: Components in the OpenTelemetry SDK that handle distributed tracing context propagation across service boundaries
- **Secrets Manager Caching**: Lambda's behavior of caching environment variables and secrets across invocations, requiring function updates to reload changed values
- **SQS FIFO Queue**: First-In-First-Out queue that guarantees message ordering and exactly-once processing using MessageGroupId and MessageDeduplicationId
- **E.164 Format**: International phone number format starting with + followed by country code and number (e.g., +5511940044117)

## Bug Details

### Bug Condition

The bugs manifest across five distinct failure scenarios in the Lambda deployment and runtime lifecycle:

**Bug 1: Module Import Failure**
The bug occurs when Lambda attempts to import handler modules after deployment. The Lambda runtime cannot resolve `src.handlers.webhook_handler` because the package structure places the `src/` directory inside the Lambda root, but Python's import system expects either flat imports or the `src` directory to be in PYTHONPATH.

**Bug 2: OpenTelemetry Initialization Failure**
The bug occurs when the Strands SDK initializes OpenTelemetry propagators during Lambda cold start. The SDK attempts to load propagators (tracecontext, b3, jaeger) that may not be available or compatible with Python 3.12 Lambda runtime, causing initialization to fail with "Propagator not found" errors.

**Bug 3: Twilio Message Delivery Failure**
The bug occurs when Lambda attempts to send WhatsApp messages via Twilio. The system uses incorrect or sandbox phone numbers from stale configuration, resulting in Twilio error 63015 (sender not approved or configuration issue).

**Bug 4: Stale Secret Caching**
The bug occurs when Twilio secrets are updated in AWS Secrets Manager but Lambda continues using old cached values. Lambda functions cache the Settings object and Secrets Manager responses across invocations, preventing updated credentials from being loaded without redeployment.

**Bug 5: SQS Message Processing Failure**
The bug occurs when messages fail to process due to errors in the message processor Lambda. Messages may be left stuck in the queue without proper error handling, retry logic, or dead-letter queue routing.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type DeploymentContext OR RuntimeContext
  OUTPUT: boolean
  
  RETURN (
    // Bug 1: Import errors
    (input.phase == "lambda_import" AND 
     input.import_path STARTS_WITH "src." AND
     input.package_structure == "nested_src_directory")
    
    OR
    
    // Bug 2: OpenTelemetry failures
    (input.phase == "sdk_initialization" AND
     input.sdk == "strands_agents" AND
     input.propagator_loading_fails == true)
    
    OR
    
    // Bug 3: Twilio delivery failures
    (input.phase == "message_sending" AND
     input.twilio_error_code == 63015 AND
     input.phone_number_source == "stale_or_sandbox")
    
    OR
    
    // Bug 4: Stale secret caching
    (input.phase == "secret_retrieval" AND
     input.secret_updated_in_secrets_manager == true AND
     input.lambda_returns_old_value == true)
    
    OR
    
    // Bug 5: SQS processing failures
    (input.phase == "message_processing" AND
     input.processing_error_occurs == true AND
     input.message_stuck_in_queue == true)
  )
END FUNCTION
```

### Examples

**Bug 1 - Module Import Error:**
- Trigger: Deploy Lambda with `src/` directory in package root, handler configured as `src.handlers.webhook_handler.lambda_handler`
- Current Behavior: Lambda fails with "Runtime.ImportModuleError: Unable to import module 'src.handlers.webhook_handler': No module named 'src'"
- Expected Behavior: Lambda successfully imports the handler module and processes requests

**Bug 2 - OpenTelemetry Initialization Error:**
- Trigger: Lambda cold start with Strands SDK attempting to initialize OpenTelemetry propagators
- Current Behavior: SDK fails with "Propagator tracecontext not found" or similar errors, preventing agent initialization
- Expected Behavior: SDK initializes successfully, skipping unavailable propagators with warnings

**Bug 3 - Twilio Delivery Error:**
- Trigger: Lambda attempts to send WhatsApp message using `twilio_client.messages.create()`
- Current Behavior: Twilio returns error 63015 because the sender phone number is a sandbox number or not approved
- Expected Behavior: Messages are sent successfully using the production Twilio phone number

**Bug 4 - Stale Secret Caching:**
- Trigger: Update Twilio credentials in Secrets Manager, then invoke Lambda without redeployment
- Current Behavior: Lambda continues using old cached credentials (sandbox phone number)
- Expected Behavior: Lambda loads fresh credentials after function code update or environment variable change

**Bug 5 - SQS Processing Failure:**
- Trigger: Message processor Lambda encounters an error (e.g., DynamoDB timeout, validation error)
- Current Behavior: Message remains in queue without proper retry or DLQ routing
- Expected Behavior: Message is either successfully processed, retried with exponential backoff, or moved to DLQ after max retries

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Local development environment with LocalStack and Docker Compose must continue to work exactly as before
- Production dependencies from requirements.txt must continue to be included in the Lambda package
- CloudFormation template validation must continue to run before deployment
- IAM permissions for Lambda functions accessing DynamoDB, S3, SQS, and Secrets Manager must remain unchanged
- The OpenTelemetry patch must preserve the original functionality of the Strands SDK while adding compatibility fixes
- Twilio signature validation logic must continue to work for webhook security
- SQS FIFO queue ordering guarantees (MessageGroupId by phone number) must be preserved
- Message deduplication logic (MessageDeduplicationId by message_sid) must be preserved

**Scope:**
All inputs that do NOT involve Lambda deployment, runtime initialization, Twilio message sending, secret loading, or SQS message processing should be completely unaffected by this fix. This includes:
- Local development workflows using `make start`, `make test`, `make logs`
- Unit tests, integration tests, and property-based tests
- DynamoDB single-table design and GSI queries
- S3 receipt storage and presigned URL generation
- Calendar sync with Google Calendar and Microsoft Outlook APIs
- Menu system and conversation state management
- AI agent tool functions for student, session, and payment management

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

### Bug 1: Module Import Errors

1. **Incorrect Package Structure**: The `package_lambda.sh` script copies the `src/` directory into the Lambda package root, creating a structure like:
   ```
   lambda-package/
   ├── src/
   │   ├── handlers/
   │   │   └── webhook_handler.py
   │   ├── services/
   │   └── ...
   ├── boto3/
   ├── strands_agents/
   └── ...
   ```
   However, the Lambda handler is configured as `src.handlers.webhook_handler.lambda_handler`, which requires Python to resolve `src` as a top-level module. This fails because `src` is a directory, not a Python package in the import path.

2. **Missing PYTHONPATH Configuration**: Lambda's Python runtime does not automatically add subdirectories to PYTHONPATH, so imports like `from src.handlers import webhook_handler` fail.

**Solution**: Either flatten the package structure (copy contents of `src/` to package root) OR configure the Lambda handler path to match the actual structure.

### Bug 2: OpenTelemetry Initialization Failures

1. **Missing Propagator Dependencies**: The Strands SDK attempts to load OpenTelemetry propagators (tracecontext, b3, jaeger) that may not be installed or compatible with Python 3.12 Lambda runtime.

2. **Strict Error Handling**: The OpenTelemetry propagate module raises `ValueError` when a propagator is not found, causing initialization to fail rather than gracefully skipping unavailable propagators.

3. **Lambda Environment Constraints**: Lambda's restricted environment may not have all the system dependencies required for certain OpenTelemetry components.

**Solution**: The `patch_opentelemetry_propagate.py` script attempts to fix this by replacing the `raise ValueError` with a warning and continue statement, but the patch may not be applied correctly or completely.

### Bug 3: Twilio Message Delivery Failures

1. **Sandbox Phone Number in Secrets**: The Twilio credentials in Secrets Manager may still contain the sandbox phone number (e.g., `whatsapp:+14155238886`) instead of the production phone number.

2. **Incorrect Secret Structure**: The secret JSON structure may not match what the code expects (e.g., missing `whatsapp:` prefix or incorrect key names).

3. **Phone Number Approval**: The production Twilio phone number may not be approved for WhatsApp messaging or may not have the correct sender profile configured.

**Solution**: Update Secrets Manager with correct production credentials and ensure the phone number is approved in Twilio console.

### Bug 4: Stale Configuration Caching

1. **Settings Object Caching**: The `src/config.py` module creates a global `settings = Settings()` instance that is cached across Lambda invocations. When secrets are updated in Secrets Manager, the Lambda function continues using the cached Settings object with old values.

2. **Secrets Manager Client Caching**: The `_get_secrets_manager_client()` method may cache responses, preventing fresh secret retrieval.

3. **No Cache Invalidation**: There is no mechanism to invalidate the settings cache when secrets are updated, requiring a Lambda function code update or environment variable change to force reinitialization.

**Solution**: Implement cache invalidation logic or force Lambda to reload settings on each invocation when in production environment.

### Bug 5: SQS Message Processing Issues

1. **Insufficient Error Handling**: The message processor Lambda may not have proper try-catch blocks to handle errors gracefully, causing messages to remain in the queue.

2. **Missing Retry Configuration**: The SQS queue may not have proper retry policies (maxReceiveCount, visibilityTimeout) configured to handle transient failures.

3. **No Dead-Letter Queue Routing**: Failed messages may not be routed to a DLQ after max retries, making it difficult to debug and recover from processing failures.

4. **Visibility Timeout Issues**: The visibility timeout may be too short, causing messages to become visible again before processing completes, leading to duplicate processing attempts.

**Solution**: Implement robust error handling in the message processor, configure proper SQS retry policies, and ensure DLQ routing is set up correctly.

## Correctness Properties

Property 1: Bug Condition - Successful Lambda Deployment and Runtime

_For any_ Lambda deployment where the package contains the `src/` directory structure and handler modules, the fixed deployment process SHALL successfully import all required modules, initialize the Strands SDK with OpenTelemetry compatibility, load fresh Twilio credentials from Secrets Manager, and process SQS messages with proper error handling, enabling the WhatsApp service to function correctly in production.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Existing Development and Deployment Workflows

_For any_ development or deployment workflow that does NOT involve Lambda runtime imports, SDK initialization, Twilio message sending, secret loading, or SQS processing (such as local development, testing, CloudFormation validation, or AWS service integrations), the fixed code SHALL produce exactly the same behavior as the original code, preserving all existing functionality for non-affected workflows.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the following changes are required:

#### Fix 1: Module Import Resolution

**File**: `scripts/package_lambda.sh`

**Specific Changes**:
1. **Flatten Package Structure**: Instead of copying `src/` as a subdirectory, copy the contents of `src/` directly to the package root:
   ```bash
   # OLD: cp -r src "$PACKAGE_DIR/"
   # NEW: cp -r src/* "$PACKAGE_DIR/"
   ```
   This creates a flat structure where `handlers/`, `services/`, `tools/`, etc. are at the package root.

2. **Update Handler Configuration**: Update CloudFormation template or deployment script to use flat import paths:
   ```yaml
   # OLD: Handler: src.handlers.webhook_handler.lambda_handler
   # NEW: Handler: handlers.webhook_handler.lambda_handler
   ```

3. **Update Import Statements**: Update all Python files to use relative imports or flat imports:
   ```python
   # OLD: from src.services.twilio_client import TwilioClient
   # NEW: from services.twilio_client import TwilioClient
   ```

**Alternative Solution**: Keep the `src/` structure but add it to PYTHONPATH in the Lambda handler:
```python
import sys
sys.path.insert(0, '/var/task/src')
```

#### Fix 2: OpenTelemetry Compatibility

**File**: `scripts/patch_opentelemetry_propagate.py`

**Specific Changes**:
1. **Improve Patch Logic**: The current patch attempts to replace `raise ValueError` with a warning and continue, but the logic may not correctly identify the patch location. Enhance the patch to:
   - Search for the exact pattern in the OpenTelemetry propagate module
   - Replace the ValueError raise with a try-except block that logs a warning and continues
   - Verify the patch was applied successfully

2. **Add Fallback Handling**: If the patch fails, add a wrapper in the Lambda handler to catch OpenTelemetry initialization errors and continue with degraded functionality (no distributed tracing).

3. **Verify Propagator Dependencies**: Ensure all required OpenTelemetry propagator packages are included in `requirements.txt`:
   ```
   opentelemetry-propagator-b3>=1.20.0,<2.0.0
   opentelemetry-propagator-jaeger>=1.20.0,<2.0.0
   ```

**File**: `scripts/package_lambda.sh`

**Specific Changes**:
4. **Verify Patch Application**: Add verification step after patching to ensure the patch was applied:
   ```bash
   if grep -q "skip missing propagators in Lambda" "$OTEL_PROPAGATE_FILE"; then
       echo "✓ OpenTelemetry propagate patch applied successfully"
   else
       echo "✗ WARNING: OpenTelemetry propagate patch may not have been applied"
   fi
   ```

#### Fix 3: Twilio Configuration Management

**File**: `scripts/deploy_production.sh`

**Specific Changes**:
1. **Add Secret Validation**: After deployment, validate that Secrets Manager contains production credentials (not sandbox):
   ```bash
   # Retrieve and validate Twilio secret
   TWILIO_SECRET=$(aws secretsmanager get-secret-value --secret-id $TWILIO_SECRET_ARN --query SecretString --output text)
   WHATSAPP_NUMBER=$(echo $TWILIO_SECRET | jq -r '.whatsapp_number')
   
   if [[ $WHATSAPP_NUMBER == *"14155238886"* ]]; then
       echo "ERROR: Twilio secret still contains sandbox number"
       exit 1
   fi
   ```

2. **Force Lambda Update**: After updating secrets, force Lambda to reload by updating an environment variable:
   ```bash
   aws lambda update-function-configuration \
       --function-name ${LAMBDA_FUNCTION} \
       --environment Variables={SECRETS_UPDATED=$(date +%s)} \
       --region ${REGION}
   ```

**File**: `src/config.py`

**Specific Changes**:
3. **Disable Secrets Caching**: Modify the `_get_secret()` method to disable caching in production:
   ```python
   def _get_secret(self, secret_name: str) -> Dict[str, Any]:
       try:
           client = self._get_secrets_manager_client()
           # Disable caching by not storing the response
           response = client.get_secret_value(SecretId=secret_name)
           return json.loads(response['SecretString'])
       except Exception as e:
           print(f"Warning: Could not retrieve secret {secret_name}: {e}")
           return {}
   ```

4. **Add Cache Invalidation**: Implement a mechanism to reload settings when secrets are updated:
   ```python
   def reload_secrets(self):
       """Force reload of secrets from Secrets Manager."""
       # Clear any cached values
       self._twilio_credentials_cache = None
       self._google_oauth_cache = None
       self._outlook_oauth_cache = None
   ```

#### Fix 4: SQS Message Processing Robustness

**File**: `src/handlers/message_processor.py` (assumed to exist)

**Specific Changes**:
1. **Add Comprehensive Error Handling**: Wrap message processing in try-except blocks with specific error handling:
   ```python
   try:
       # Process message
       result = process_message(message)
   except ValidationError as e:
       # User input errors - log and delete message (don't retry)
       logger.error("Validation error", error=str(e))
       return  # Message will be deleted from queue
   except ClientError as e:
       # AWS service errors - may be transient, allow retry
       logger.error("AWS service error", error=str(e))
       raise  # Message will be retried
   except Exception as e:
       # Unexpected errors - log and allow retry
       logger.error("Unexpected error", error=str(e))
       raise
   ```

2. **Implement Exponential Backoff**: Configure SQS queue with proper retry policy in CloudFormation:
   ```yaml
   VisibilityTimeout: 300  # 5 minutes
   MessageRetentionPeriod: 1209600  # 14 days
   ReceiveMessageWaitTimeSeconds: 20  # Long polling
   RedrivePolicy:
     deadLetterTargetArn: !GetAtt MessageDLQ.Arn
     maxReceiveCount: 3  # Retry 3 times before DLQ
   ```

3. **Add DLQ Monitoring**: Implement CloudWatch alarms for DLQ message count:
   ```yaml
   DLQAlarm:
     Type: AWS::CloudWatch::Alarm
     Properties:
       AlarmDescription: Alert when messages are in DLQ
       MetricName: ApproximateNumberOfMessagesVisible
       Namespace: AWS/SQS
       Statistic: Sum
       Period: 300
       EvaluationPeriods: 1
       Threshold: 1
       ComparisonOperator: GreaterThanOrEqualToThreshold
   ```

#### Fix 5: Deployment Script Improvements

**File**: `scripts/deploy_production.sh`

**Specific Changes**:
1. **Add Pre-Deployment Validation**: Validate that all required secrets exist before deployment:
   ```bash
   # Validate secrets exist
   for SECRET_ARN in $TWILIO_SECRET_ARN $GOOGLE_SECRET_ARN $OUTLOOK_SECRET_ARN; do
       if ! aws secretsmanager describe-secret --secret-id $SECRET_ARN &>/dev/null; then
           echo "ERROR: Secret $SECRET_ARN does not exist"
           exit 1
       fi
   done
   ```

2. **Add Post-Deployment Smoke Test**: Test Lambda function after deployment:
   ```bash
   # Invoke Lambda with test event
   aws lambda invoke \
       --function-name ${LAMBDA_FUNCTION} \
       --payload '{"test": true}' \
       --region ${REGION} \
       /tmp/lambda-response.json
   
   # Check for errors
   if grep -q "errorMessage" /tmp/lambda-response.json; then
       echo "ERROR: Lambda invocation failed"
       cat /tmp/lambda-response.json
       exit 1
   fi
   ```

3. **Add Rollback Capability**: Implement automatic rollback on deployment failure:
   ```bash
   # Deploy with rollback configuration
   aws cloudformation deploy \
       --template-file infrastructure/template.yml \
       --stack-name ${STACK_NAME} \
       --parameter-overrides file://${PARAMETERS_FILE} \
       --capabilities CAPABILITY_NAMED_IAM \
       --region ${REGION} \
       --no-fail-on-empty-changeset \
       --rollback-configuration RollbackTriggers=[{Arn=${ALARM_ARN},Type=AWS::CloudWatch::Alarm}]
   ```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior. Each bug requires specific testing approaches due to their different failure modes.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fixes. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Create test scenarios that replicate each bug condition in isolation. Run these tests on the UNFIXED code to observe failures and understand the root causes. Use LocalStack for AWS service mocking and actual Lambda deployment simulation.

**Test Cases**:

1. **Bug 1 - Module Import Test**: Package Lambda with current script and attempt to import handler (will fail on unfixed code)
   - Create a minimal Lambda package using `package_lambda.sh`
   - Attempt to import `src.handlers.webhook_handler` in Python
   - Expected failure: `ModuleNotFoundError: No module named 'src'`
   - Root cause confirmation: Package structure places `src/` as subdirectory

2. **Bug 2 - OpenTelemetry Initialization Test**: Initialize Strands SDK in Lambda environment (will fail on unfixed code)
   - Create Lambda function that imports and initializes Strands SDK
   - Monitor for OpenTelemetry propagator errors during cold start
   - Expected failure: `ValueError: Propagator tracecontext not found`
   - Root cause confirmation: Missing or incompatible propagator dependencies

3. **Bug 3 - Twilio Message Delivery Test**: Send WhatsApp message using current configuration (will fail on unfixed code)
   - Configure Lambda with Secrets Manager containing sandbox credentials
   - Attempt to send WhatsApp message via Twilio
   - Expected failure: Twilio error 63015 (sender not approved)
   - Root cause confirmation: Sandbox phone number in secrets

4. **Bug 4 - Secret Caching Test**: Update secret and invoke Lambda without redeployment (will fail on unfixed code)
   - Deploy Lambda with initial Twilio credentials
   - Update credentials in Secrets Manager
   - Invoke Lambda and check which credentials are used
   - Expected failure: Lambda uses old cached credentials
   - Root cause confirmation: Settings object caching across invocations

5. **Bug 5 - SQS Processing Test**: Trigger processing error and observe message handling (will fail on unfixed code)
   - Send message to SQS queue that will cause processing error
   - Monitor message visibility and retry behavior
   - Expected failure: Message stuck in queue without DLQ routing
   - Root cause confirmation: Insufficient error handling and retry configuration

**Expected Counterexamples**:
- Lambda import errors with "No module named 'src'" message
- OpenTelemetry initialization failures with propagator not found errors
- Twilio API rejections with error code 63015
- Stale credentials being used after Secrets Manager updates
- Messages remaining in SQS queue after processing failures

### Fix Checking

**Goal**: Verify that for all inputs where the bug conditions hold, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL deployment WHERE isBugCondition(deployment) DO
  result := deploy_and_test_fixed(deployment)
  ASSERT expectedBehavior(result)
END FOR

WHERE expectedBehavior(result) IS:
  - Lambda imports succeed without module errors
  - Strands SDK initializes without OpenTelemetry errors
  - Twilio messages are delivered successfully
  - Fresh secrets are loaded after updates
  - SQS messages are processed or routed to DLQ
```

**Test Cases**:

1. **Fix 1 Verification - Module Import Success**:
   - Package Lambda with fixed script (flattened structure)
   - Deploy to LocalStack Lambda environment
   - Invoke handler and verify successful import
   - Assert: No ImportModuleError, handler executes successfully

2. **Fix 2 Verification - OpenTelemetry Initialization Success**:
   - Package Lambda with patched OpenTelemetry module
   - Initialize Strands SDK during cold start
   - Verify SDK initializes without errors (may log warnings for missing propagators)
   - Assert: No ValueError, SDK is functional

3. **Fix 3 Verification - Twilio Message Delivery Success**:
   - Update Secrets Manager with production credentials
   - Deploy Lambda with secret validation
   - Send test WhatsApp message
   - Assert: Message delivered successfully, no error 63015

4. **Fix 4 Verification - Fresh Secret Loading**:
   - Deploy Lambda with cache invalidation logic
   - Update Twilio credentials in Secrets Manager
   - Update Lambda environment variable to force reload
   - Invoke Lambda and verify new credentials are used
   - Assert: Fresh credentials loaded, not cached values

5. **Fix 5 Verification - SQS Processing Robustness**:
   - Send message that triggers processing error
   - Verify message is retried with exponential backoff
   - After max retries, verify message is moved to DLQ
   - Assert: Message either processed successfully or in DLQ, not stuck in main queue

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL workflow WHERE NOT isBugCondition(workflow) DO
  ASSERT original_behavior(workflow) = fixed_behavior(workflow)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy workflows

**Test Plan**: Observe behavior on UNFIXED code first for non-affected workflows, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Local Development Preservation**: Verify local environment continues to work
   - Run `make start` to start LocalStack and services
   - Run `make test` to execute test suite
   - Verify all tests pass and services function correctly
   - Assert: Local development workflow unchanged

2. **Dependency Management Preservation**: Verify all production dependencies are included
   - Compare package contents before and after fix
   - Verify all packages from requirements.txt are present
   - Check package size remains within Lambda limits
   - Assert: All dependencies included, no regressions

3. **CloudFormation Validation Preservation**: Verify template validation continues to work
   - Run `aws cloudformation validate-template` on infrastructure template
   - Verify validation passes without errors
   - Assert: Template validation unchanged

4. **AWS Service Integration Preservation**: Verify DynamoDB, S3, SQS access continues to work
   - Test DynamoDB queries (get_item, query, put_item)
   - Test S3 operations (upload, presigned URLs)
   - Test SQS operations (send_message, receive_message)
   - Assert: All AWS service integrations function correctly

5. **Twilio Signature Validation Preservation**: Verify webhook security continues to work
   - Send webhook request with valid Twilio signature
   - Send webhook request with invalid signature
   - Verify valid requests are accepted, invalid requests are rejected
   - Assert: Signature validation logic unchanged

### Unit Tests

- Test Lambda package structure after running fixed `package_lambda.sh` script
- Test OpenTelemetry patch application and verification
- Test Secrets Manager secret retrieval with and without caching
- Test SQS message processing error handling for different error types
- Test deployment script validation steps (secret existence, template validation)

### Property-Based Tests

- Generate random Lambda package structures and verify imports resolve correctly
- Generate random OpenTelemetry configurations and verify SDK initialization handles missing propagators
- Generate random Secrets Manager updates and verify Lambda loads fresh values after environment changes
- Generate random SQS message processing scenarios and verify messages are either processed or routed to DLQ
- Generate random deployment configurations and verify CloudFormation validation passes

### Integration Tests

- Test full deployment pipeline from packaging to Lambda invocation
- Test end-to-end WhatsApp message flow: webhook → SQS → processing → Twilio response
- Test secret rotation: update Secrets Manager → update Lambda → verify new credentials used
- Test SQS retry flow: processing error → retry with backoff → DLQ routing after max retries
- Test rollback scenario: deployment failure → automatic rollback to previous version
