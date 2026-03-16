# WhatsApp AI Service Error Fix - Bugfix Design

## Overview

The bug occurs when running FitAgent in LocalStack environment: WhatsApp messages fail to receive AI-generated responses because the BedrockModel initialization does not use the configured `endpoint_url` parameter. This causes Bedrock API calls to be directed to LocalStack, which does not implement the Bedrock service, resulting in `NotImplementedError`. The fix involves ensuring BedrockModel bypasses LocalStack and uses the real AWS Bedrock endpoint in local development, while preserving existing behavior for production environments and other AWS services.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when BedrockModel is initialized in LocalStack environment without using the configured endpoint_url parameter
- **Property (P)**: The desired behavior when running in LocalStack - BedrockModel should use real AWS Bedrock endpoint (bypassing LocalStack)
- **Preservation**: Existing production behavior (default AWS endpoints) and LocalStack behavior for other services (DynamoDB, S3, SQS) that must remain unchanged
- **BedrockModel**: The Strands SDK class in `strands.models.bedrock` that wraps AWS Bedrock API calls
- **endpoint_url**: Configuration parameter that specifies which AWS endpoint to use for API calls
- **LocalStack**: Local AWS service emulator used for development - does not implement Bedrock service
- **StrandsAgentService**: The service class in `src/services/strands_agent_service.py` that initializes BedrockModel

## Bug Details

### Bug Condition

The bug manifests when the system runs in LocalStack environment (indicated by `settings.aws_endpoint_url` being set) and a WhatsApp message is processed. The `StrandsAgentService.__init__` method initializes `BedrockModel` with only `model_id` and `region_name` parameters, but does not pass the `endpoint_url` parameter. This causes BedrockModel to use the default AWS SDK configuration, which in LocalStack environments is configured to route all AWS API calls to LocalStack. Since LocalStack does not implement Bedrock, the API call fails with `NotImplementedError`.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type MessageProcessingContext
  OUTPUT: boolean
  
  RETURN input.environment == "local"
         AND input.aws_endpoint_url IS NOT NULL
         AND input.bedrock_endpoint_url IS NULL
         AND BedrockModel.initialized_without_endpoint_url == TRUE
END FUNCTION
```

### Examples

- **Example 1**: User sends "Registrar novo aluno João" via WhatsApp in LocalStack environment
  - Expected: AI processes message and returns "Aluno João registrado com sucesso!"
  - Actual: Returns "O serviço de IA está temporariamente indisponível. Por favor, tente novamente."
  - Root cause: BedrockModel calls LocalStack endpoint, gets NotImplementedError

- **Example 2**: User sends "Ver meus alunos" via WhatsApp in LocalStack environment
  - Expected: AI processes message and returns list of students
  - Actual: Returns generic error message
  - Root cause: Same - Bedrock call fails at LocalStack

- **Example 3**: User sends any message in production environment
  - Expected: AI processes message correctly using default AWS Bedrock endpoint
  - Actual: Works correctly (no bug in production)

- **Edge Case**: User sends message when `aws_bedrock_endpoint_url` is explicitly set to real AWS endpoint
  - Expected: Should work correctly even in LocalStack environment
  - Actual: Currently not passed to BedrockModel, so bug still occurs

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Production environment must continue to use default AWS Bedrock endpoint without explicit endpoint_url configuration
- DynamoDB, S3, SQS, and other LocalStack-supported services must continue to use LocalStack endpoint in local development
- Bedrock API error handling (throttling, validation, access denied) must continue to work with existing Portuguese error messages
- Message processing timeout logic and other non-Bedrock error handling must remain unchanged

**Scope:**
All inputs that do NOT involve LocalStack environment with Bedrock calls should be completely unaffected by this fix. This includes:
- Production deployments (environment != "local")
- LocalStack operations for DynamoDB, S3, SQS (these should still use LocalStack)
- Error handling for non-Bedrock errors (timeouts, validation, connection errors)
- All tool execution logic (student_tools, session_tools, payment_tools)

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is:

1. **Missing endpoint_url Parameter**: The `StrandsAgentService.__init__` method (line 88-91) creates BedrockModel with only `model_id` and `region_name`:
   ```python
   self.model = BedrockModel(
       model_id=self.model_id,
       region_name=self.region
   )
   ```
   The `endpoint_url` parameter is not passed, even though it's stored in `self.endpoint_url`.

2. **LocalStack Global AWS Configuration**: In LocalStack environments, the AWS SDK is typically configured globally (via environment variables or boto3 session) to route all API calls to LocalStack endpoint. Without an explicit `endpoint_url` parameter, BedrockModel inherits this global configuration.

3. **LocalStack Bedrock Not Implemented**: LocalStack does not implement the AWS Bedrock service, so when BedrockModel attempts to call Bedrock through LocalStack, it raises `NotImplementedError`.

4. **Generic Exception Handler**: The `NotImplementedError` is caught by the generic `Exception` handler in `process_message` (line 557-568), which returns the generic Portuguese error message.

## Correctness Properties

Property 1: Bug Condition - Bedrock Uses Real AWS Endpoint in LocalStack

_For any_ message processing context where the system runs in LocalStack environment (aws_endpoint_url is set) and a WhatsApp message is processed, the BedrockModel SHALL be initialized with an endpoint_url parameter that points to the real AWS Bedrock endpoint (not LocalStack), enabling successful AI response generation.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Production and Other Services Unchanged

_For any_ message processing context where the system runs in production environment (aws_endpoint_url is not set) OR where other AWS services (DynamoDB, S3, SQS) are called, the system SHALL produce exactly the same behavior as the original code, preserving default AWS endpoint usage for production and LocalStack endpoint usage for supported services.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/services/strands_agent_service.py`

**Function**: `StrandsAgentService.__init__`

**Specific Changes**:
1. **Pass endpoint_url to BedrockModel**: Modify the BedrockModel initialization (lines 88-91) to include the `endpoint_url` parameter:
   ```python
   # Current (buggy):
   self.model = BedrockModel(
       model_id=self.model_id,
       region_name=self.region
   )
   
   # Fixed:
   self.model = BedrockModel(
       model_id=self.model_id,
       region_name=self.region,
       endpoint_url=self.endpoint_url  # Add this parameter
   )
   ```

2. **Conditional Endpoint Logic**: The fix relies on the existing configuration logic where:
   - In LocalStack: `settings.aws_bedrock_endpoint_url` should be set to real AWS endpoint (or None to use default)
   - In Production: `settings.aws_bedrock_endpoint_url` is None, so BedrockModel uses default AWS endpoint
   - The `endpoint_url` parameter in BedrockModel should accept None and use default when None

3. **Verify BedrockModel API**: Confirm that the Strands SDK's BedrockModel class accepts an `endpoint_url` parameter. If not, we may need to:
   - Use boto3 client configuration directly
   - Or pass endpoint via boto3 session configuration
   - Or use environment variables to override endpoint for Bedrock specifically

4. **Configuration Documentation**: Update `.env.example` to document that `AWS_BEDROCK_ENDPOINT_URL` should be left empty (or set to real AWS endpoint) in LocalStack environments

5. **No Changes to Error Handling**: The existing error handling logic should continue to work correctly once Bedrock calls succeed

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write integration tests that simulate WhatsApp message processing in LocalStack environment with mock Bedrock responses. Run these tests on the UNFIXED code to observe the NotImplementedError and confirm the root cause.

**Test Cases**:
1. **LocalStack Message Processing Test**: Send a message through StrandsAgentService in LocalStack environment (will fail on unfixed code with NotImplementedError)
2. **BedrockModel Initialization Test**: Verify that BedrockModel is initialized without endpoint_url parameter in LocalStack (will show missing parameter on unfixed code)
3. **Endpoint Configuration Test**: Verify that aws_bedrock_endpoint_url is available in settings but not used (will confirm configuration exists but isn't passed)
4. **Error Message Test**: Verify that NotImplementedError results in generic Portuguese error message (will confirm error handling path)

**Expected Counterexamples**:
- BedrockModel initialization does not include endpoint_url parameter
- Bedrock API calls are directed to LocalStack endpoint instead of real AWS
- NotImplementedError is raised by LocalStack when Bedrock is called
- Generic error message is returned to user instead of AI response

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := StrandsAgentService_fixed.process_message(input)
  ASSERT result.success == TRUE
  ASSERT result.response CONTAINS ai_generated_text
  ASSERT BedrockModel.endpoint_url == real_aws_endpoint OR None
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT StrandsAgentService_original.process_message(input) = StrandsAgentService_fixed.process_message(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for production environment and other AWS services, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Production Environment Preservation**: Observe that message processing works correctly in production environment on unfixed code (if we have production access), then write test to verify this continues after fix
2. **DynamoDB Operations Preservation**: Observe that DynamoDB operations use LocalStack endpoint correctly on unfixed code, then write test to verify this continues after fix
3. **S3 Operations Preservation**: Observe that S3 operations use LocalStack endpoint correctly on unfixed code, then write test to verify this continues after fix
4. **Error Handling Preservation**: Observe that non-Bedrock errors (validation, timeout, connection) are handled correctly on unfixed code, then write test to verify this continues after fix

### Unit Tests

- Test BedrockModel initialization with endpoint_url parameter in LocalStack environment
- Test BedrockModel initialization without endpoint_url parameter in production environment
- Test that endpoint_url is correctly passed from settings to StrandsAgentService to BedrockModel
- Test edge cases (endpoint_url is None, endpoint_url is empty string, endpoint_url is invalid)

### Property-Based Tests

- Generate random message inputs and verify successful AI responses in LocalStack environment with fixed code
- Generate random environment configurations (local vs production) and verify correct endpoint usage
- Generate random AWS service operations (DynamoDB, S3, SQS) and verify they continue using correct endpoints
- Test that all error handling paths continue to work across many scenarios

### Integration Tests

- Test full WhatsApp message flow in LocalStack environment with real Bedrock API calls
- Test switching between LocalStack and production environments
- Test that DynamoDB, S3, and SQS continue to work with LocalStack while Bedrock uses real AWS
- Test error scenarios (Bedrock throttling, validation errors) to ensure error messages are still in Portuguese
