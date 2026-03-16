# Bugfix Requirements Document

## Introduction

When users send messages to WhatsApp in the local development environment (LocalStack), they receive the error message "O serviço de IA está temporariamente indisponível. Por favor, tente novamente." instead of AI-generated responses. This occurs because the Bedrock service call fails with a `NotImplementedError` in LocalStack, as LocalStack does not implement the AWS Bedrock service. The bug prevents local development and testing of the AI conversation features.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the system runs in LocalStack environment AND a WhatsApp message is processed THEN the BedrockModel initialization does not use the configured endpoint_url parameter

1.2 WHEN BedrockModel attempts to call AWS Bedrock through LocalStack THEN LocalStack raises NotImplementedError because it does not implement Bedrock services

1.3 WHEN the NotImplementedError is caught by the generic Exception handler THEN the system returns the generic error message "O serviço de IA está temporariamente indisponível. Por favor, tente novamente."

1.4 WHEN running in LocalStack environment THEN Bedrock calls are directed to LocalStack endpoint instead of real AWS Bedrock endpoint

### Expected Behavior (Correct)

2.1 WHEN the system runs in LocalStack environment AND a WhatsApp message is processed THEN the BedrockModel SHALL be configured to use real AWS Bedrock endpoint (bypassing LocalStack)

2.2 WHEN BedrockModel is initialized with endpoint_url parameter THEN the Bedrock client SHALL use the specified endpoint for API calls

2.3 WHEN Bedrock calls succeed through the real AWS endpoint THEN the system SHALL return AI-generated responses to WhatsApp users

2.4 WHEN running in LocalStack environment THEN only DynamoDB, S3, SQS, and other LocalStack-supported services SHALL use LocalStack endpoint, while Bedrock SHALL use real AWS endpoint

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the system runs in production environment (non-LocalStack) THEN the system SHALL CONTINUE TO use the default AWS Bedrock endpoint without explicit endpoint_url configuration

3.2 WHEN DynamoDB, S3, SQS, and other LocalStack-supported services are called THEN they SHALL CONTINUE TO use the LocalStack endpoint in local development

3.3 WHEN Bedrock API errors occur (throttling, validation, access denied) THEN the system SHALL CONTINUE TO handle them with appropriate Portuguese error messages

3.4 WHEN message processing times out or encounters other non-Bedrock errors THEN the system SHALL CONTINUE TO handle them with existing error handling logic
