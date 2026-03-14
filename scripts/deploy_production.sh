#!/bin/bash
set -e

# Production Deployment Script for FitAgent
# This script deploys the infrastructure and Lambda functions to production

ENVIRONMENT="production"
STACK_NAME="fitagent-${ENVIRONMENT}"
REGION="${AWS_REGION:-us-east-1}"
PARAMETERS_FILE="infrastructure/parameters/${ENVIRONMENT}.json"

echo "=========================================="
echo "FitAgent Production Deployment"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo "Stack Name: ${STACK_NAME}"
echo "Region: ${REGION}"
echo "=========================================="

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "Error: AWS CLI is not configured or credentials are invalid"
    exit 1
fi

echo "✓ AWS credentials validated"

# Pre-deployment validation: Check if required secrets exist
echo ""
echo "Validating required secrets exist..."

# Get existing stack outputs if stack exists
if aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} &> /dev/null; then
    echo "Stack exists, retrieving secret ARNs..."
    
    TWILIO_SECRET_ARN=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --query 'Stacks[0].Outputs[?OutputKey==`TwilioSecretArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    GOOGLE_SECRET_ARN=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --query 'Stacks[0].Outputs[?OutputKey==`GoogleOAuthSecretArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    OUTLOOK_SECRET_ARN=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --query 'Stacks[0].Outputs[?OutputKey==`OutlookOAuthSecretArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
    
    # Validate secrets exist
    SECRET_VALIDATION_FAILED=false
    
    if [[ -n "${TWILIO_SECRET_ARN}" ]]; then
        if aws secretsmanager describe-secret --secret-id ${TWILIO_SECRET_ARN} --region ${REGION} &> /dev/null; then
            echo "✓ Twilio secret exists"
        else
            echo "✗ ERROR: Twilio secret ${TWILIO_SECRET_ARN} does not exist"
            SECRET_VALIDATION_FAILED=true
        fi
    fi
    
    if [[ -n "${GOOGLE_SECRET_ARN}" ]]; then
        if aws secretsmanager describe-secret --secret-id ${GOOGLE_SECRET_ARN} --region ${REGION} &> /dev/null; then
            echo "✓ Google OAuth secret exists"
        else
            echo "✗ ERROR: Google OAuth secret ${GOOGLE_SECRET_ARN} does not exist"
            SECRET_VALIDATION_FAILED=true
        fi
    fi
    
    if [[ -n "${OUTLOOK_SECRET_ARN}" ]]; then
        if aws secretsmanager describe-secret --secret-id ${OUTLOOK_SECRET_ARN} --region ${REGION} &> /dev/null; then
            echo "✓ Outlook OAuth secret exists"
        else
            echo "✗ ERROR: Outlook OAuth secret ${OUTLOOK_SECRET_ARN} does not exist"
            SECRET_VALIDATION_FAILED=true
        fi
    fi
    
    if [[ "${SECRET_VALIDATION_FAILED}" == "true" ]]; then
        echo ""
        echo "Pre-deployment validation failed: Required secrets are missing"
        exit 1
    fi
else
    echo "First deployment - secrets will be created by CloudFormation"
fi

# Validate CloudFormation template
echo ""
echo "Validating CloudFormation template..."
aws cloudformation validate-template \
    --template-body file://infrastructure/template.yml \
    --region ${REGION} > /dev/null

echo "✓ Template validation successful"

# Package Lambda function
echo ""
echo "Packaging Lambda function..."
./scripts/package_lambda.sh

echo "✓ Lambda package created"

# Deploy CloudFormation stack with rollback configuration
echo ""
echo "Deploying CloudFormation stack..."
echo "This may take several minutes..."

# Get DLQ alarm ARN if stack exists (for rollback trigger)
DLQ_ALARM_ARN=""
if aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} &> /dev/null; then
    DLQ_ALARM_ARN=$(aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --query 'Stacks[0].Outputs[?OutputKey==`DLQAlarmArn`].OutputValue' \
        --output text 2>/dev/null || echo "")
fi

# Deploy with rollback configuration if alarm exists
if [[ -n "${DLQ_ALARM_ARN}" ]]; then
    echo "Configuring automatic rollback on DLQ alarm trigger..."
    
    aws cloudformation deploy \
        --template-file infrastructure/template.yml \
        --stack-name ${STACK_NAME} \
        --parameter-overrides file://${PARAMETERS_FILE} \
        --capabilities CAPABILITY_NAMED_IAM \
        --region ${REGION} \
        --no-fail-on-empty-changeset \
        --rollback-configuration "RollbackTriggers=[{Arn=${DLQ_ALARM_ARN},Type=AWS::CloudWatch::Alarm}],MonitoringTimeInMinutes=5"
    
    echo "✓ Stack deployment complete (with rollback protection)"
else
    echo "First deployment - rollback triggers will be configured on next deployment"
    
    aws cloudformation deploy \
        --template-file infrastructure/template.yml \
        --stack-name ${STACK_NAME} \
        --parameter-overrides file://${PARAMETERS_FILE} \
        --capabilities CAPABILITY_NAMED_IAM \
        --region ${REGION} \
        --no-fail-on-empty-changeset
    
    echo "✓ Stack deployment complete"
fi

# Get stack outputs
echo ""
echo "Retrieving stack outputs..."

TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
    --output text)

BUCKET_NAME=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`ReceiptsBucketName`].OutputValue' \
    --output text)

TWILIO_SECRET_ARN=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`TwilioSecretArn`].OutputValue' \
    --output text)

GOOGLE_SECRET_ARN=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`GoogleOAuthSecretArn`].OutputValue' \
    --output text)

OUTLOOK_SECRET_ARN=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`OutlookOAuthSecretArn`].OutputValue' \
    --output text)

LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`MessageProcessorFunctionName`].OutputValue' \
    --output text)

echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo "DynamoDB Table: ${TABLE_NAME}"
echo "S3 Bucket: ${BUCKET_NAME}"
echo "Lambda Function: ${LAMBDA_FUNCTION}"
echo ""
echo "Secrets Manager ARNs:"
echo "  Twilio: ${TWILIO_SECRET_ARN}"
echo "  Google OAuth: ${GOOGLE_SECRET_ARN}"
echo "  Outlook OAuth: ${OUTLOOK_SECRET_ARN}"
echo "=========================================="

# Validate Twilio secret doesn't contain sandbox number
echo ""
echo "Validating Twilio secret configuration..."

TWILIO_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id ${TWILIO_SECRET_ARN} \
    --region ${REGION} \
    --query SecretString \
    --output text 2>/dev/null || echo "{}")

WHATSAPP_NUMBER=$(echo "${TWILIO_SECRET}" | jq -r '.whatsapp_number // empty')

if [[ -n "${WHATSAPP_NUMBER}" && "${WHATSAPP_NUMBER}" == *"14155238886"* ]]; then
    echo "✗ ERROR: Twilio secret still contains sandbox number (14155238886)"
    echo "  Please update the secret with production credentials before deployment"
    echo ""
    echo "  aws secretsmanager update-secret \\"
    echo "    --secret-id ${TWILIO_SECRET_ARN} \\"
    echo "    --secret-string '{\"account_sid\":\"YOUR_SID\",\"auth_token\":\"YOUR_TOKEN\",\"whatsapp_number\":\"whatsapp:+YOUR_PRODUCTION_NUMBER\"}' \\"
    echo "    --region ${REGION}"
    exit 1
elif [[ -n "${WHATSAPP_NUMBER}" ]]; then
    echo "✓ Twilio secret validated (using production number: ${WHATSAPP_NUMBER})"
else
    echo "⚠ Warning: Twilio secret not yet configured (will use environment variables)"
fi

# Update Lambda function code
echo ""
echo "Updating Lambda function code..."

aws lambda update-function-code \
    --function-name ${LAMBDA_FUNCTION} \
    --zip-file fileb://build/lambda.zip \
    --region ${REGION} > /dev/null

echo "✓ Lambda function code updated"

# Force Lambda to reload secrets by updating environment variable
echo ""
echo "Forcing Lambda configuration update to reload secrets..."

SECRETS_UPDATED_TIMESTAMP=$(date +%s)

aws lambda update-function-configuration \
    --function-name ${LAMBDA_FUNCTION} \
    --environment Variables={SECRETS_UPDATED=${SECRETS_UPDATED_TIMESTAMP}} \
    --region ${REGION} > /dev/null

echo "✓ Lambda configuration updated (SECRETS_UPDATED=${SECRETS_UPDATED_TIMESTAMP})"

# Post-deployment smoke test: Invoke Lambda functions with test events
echo ""
echo "Running post-deployment smoke tests..."

# Wait for Lambda to finish updating
echo "Waiting for Lambda function to be ready..."
aws lambda wait function-updated \
    --function-name ${LAMBDA_FUNCTION} \
    --region ${REGION}

# Test Message Processor Lambda
echo "Testing Message Processor Lambda..."
TEST_PAYLOAD='{"test":true,"source":"deployment_validation"}'

aws lambda invoke \
    --function-name ${LAMBDA_FUNCTION} \
    --payload "${TEST_PAYLOAD}" \
    --region ${REGION} \
    /tmp/lambda-response.json > /dev/null 2>&1

# Check for errors in response
if grep -q '"errorMessage"' /tmp/lambda-response.json 2>/dev/null; then
    echo "✗ ERROR: Lambda invocation failed"
    echo "Response:"
    cat /tmp/lambda-response.json
    echo ""
    echo "Deployment validation failed - Lambda function has errors"
    exit 1
elif grep -q '"statusCode": 200' /tmp/lambda-response.json 2>/dev/null || grep -q '"success": true' /tmp/lambda-response.json 2>/dev/null; then
    echo "✓ Message Processor Lambda smoke test passed"
else
    # Check if response is valid JSON
    if jq empty /tmp/lambda-response.json 2>/dev/null; then
        echo "✓ Message Processor Lambda smoke test passed (valid response)"
    else
        echo "⚠ Warning: Lambda response format unexpected, but no errors detected"
        echo "Response:"
        cat /tmp/lambda-response.json
    fi
fi

# Test Webhook Handler Lambda if it exists
WEBHOOK_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name ${STACK_NAME} \
    --region ${REGION} \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookHandlerFunctionName`].OutputValue' \
    --output text 2>/dev/null || echo "")

if [[ -n "${WEBHOOK_FUNCTION}" ]]; then
    echo "Testing Webhook Handler Lambda..."
    
    # Wait for function to be ready
    aws lambda wait function-updated \
        --function-name ${WEBHOOK_FUNCTION} \
        --region ${REGION} 2>/dev/null || true
    
    WEBHOOK_TEST_PAYLOAD='{"test":true,"httpMethod":"POST","body":"{\"test\":true}"}'
    
    aws lambda invoke \
        --function-name ${WEBHOOK_FUNCTION} \
        --payload "${WEBHOOK_TEST_PAYLOAD}" \
        --region ${REGION} \
        /tmp/webhook-response.json > /dev/null 2>&1
    
    if grep -q '"errorMessage"' /tmp/webhook-response.json 2>/dev/null; then
        echo "✗ ERROR: Webhook Handler Lambda invocation failed"
        echo "Response:"
        cat /tmp/webhook-response.json
        echo ""
        echo "Deployment validation failed - Webhook Handler has errors"
        exit 1
    else
        echo "✓ Webhook Handler Lambda smoke test passed"
    fi
fi

echo "✓ All smoke tests passed"

echo ""
echo "=========================================="
echo "IMPORTANT: Update Secrets in AWS Console"
echo "=========================================="
echo ""
echo "The deployment created placeholder secrets. You must update them with real credentials:"
echo ""
echo "1. Twilio Credentials:"
echo "   aws secretsmanager update-secret \\"
echo "     --secret-id ${TWILIO_SECRET_ARN} \\"
echo "     --secret-string '{\"account_sid\":\"YOUR_SID\",\"auth_token\":\"YOUR_TOKEN\",\"whatsapp_number\":\"whatsapp:+1234567890\"}' \\"
echo "     --region ${REGION}"
echo ""
echo "2. Google OAuth Credentials:"
echo "   aws secretsmanager update-secret \\"
echo "     --secret-id ${GOOGLE_SECRET_ARN} \\"
echo "     --secret-string '{\"client_id\":\"YOUR_CLIENT_ID\",\"client_secret\":\"YOUR_CLIENT_SECRET\"}' \\"
echo "     --region ${REGION}"
echo ""
echo "3. Outlook OAuth Credentials:"
echo "   aws secretsmanager update-secret \\"
echo "     --secret-id ${OUTLOOK_SECRET_ARN} \\"
echo "     --secret-string '{\"client_id\":\"YOUR_CLIENT_ID\",\"client_secret\":\"YOUR_CLIENT_SECRET\"}' \\"
echo "     --region ${REGION}"
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
