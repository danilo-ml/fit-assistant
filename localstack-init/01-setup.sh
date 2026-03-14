#!/bin/bash

echo "========================================="
echo "Initializing LocalStack resources..."
echo "========================================="

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
sleep 5

# Create DynamoDB table
echo "Creating DynamoDB table: fitagent-main"
awslocal dynamodb create-table \
    --table-name fitagent-main \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
        AttributeName=phone_number,AttributeType=S \
        AttributeName=entity_type,AttributeType=S \
        AttributeName=trainer_id,AttributeType=S \
        AttributeName=session_datetime,AttributeType=S \
        AttributeName=payment_status,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --global-secondary-indexes \
        '[
            {
                "IndexName": "phone-number-index",
                "KeySchema": [
                    {"AttributeName": "phone_number", "KeyType": "HASH"},
                    {"AttributeName": "entity_type", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            },
            {
                "IndexName": "session-date-index",
                "KeySchema": [
                    {"AttributeName": "trainer_id", "KeyType": "HASH"},
                    {"AttributeName": "session_datetime", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            },
            {
                "IndexName": "payment-status-index",
                "KeySchema": [
                    {"AttributeName": "trainer_id", "KeyType": "HASH"},
                    {"AttributeName": "payment_status", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            }
        ]' \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

echo "✓ DynamoDB table created"

# Create S3 bucket
echo "Creating S3 bucket: fitagent-receipts-local"
awslocal s3 mb s3://fitagent-receipts-local --region us-east-1
awslocal s3api put-bucket-encryption \
    --bucket fitagent-receipts-local \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'

echo "✓ S3 bucket created with encryption"

# Create SQS queues
echo "Creating SQS queues..."

# Dead letter queue (FIFO)
awslocal sqs create-queue \
    --queue-name fitagent-messages-dlq.fifo \
    --attributes '{"FifoQueue":"true","ContentBasedDeduplication":"false"}' \
    --region us-east-1

DLQ_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url http://localhost:4566/000000000000/fitagent-messages-dlq.fifo \
    --attribute-names QueueArn \
    --region us-east-1 \
    --query 'Attributes.QueueArn' \
    --output text)

# Main message queue with DLQ (FIFO)
awslocal sqs create-queue \
    --queue-name fitagent-messages.fifo \
    --attributes "{
        \"FifoQueue\":\"true\",
        \"ContentBasedDeduplication\":\"false\",
        \"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
    }" \
    --region us-east-1

# Notification queue (FIFO)
awslocal sqs create-queue \
    --queue-name fitagent-notifications.fifo \
    --attributes '{"FifoQueue":"true","ContentBasedDeduplication":"false"}' \
    --region us-east-1

echo "✓ SQS FIFO queues created"

# Create KMS key for encryption
echo "Creating KMS key for OAuth token encryption..."
KEY_ID=$(awslocal kms create-key \
    --description "FitAgent OAuth token encryption" \
    --region us-east-1 \
    --query 'KeyMetadata.KeyId' \
    --output text)

awslocal kms create-alias \
    --alias-name alias/fitagent-oauth-key \
    --target-key-id "${KEY_ID}" \
    --region us-east-1

echo "✓ KMS key created with alias: alias/fitagent-oauth-key"

# Create Secrets Manager secrets (placeholders)
echo "Creating Secrets Manager secrets..."
awslocal secretsmanager create-secret \
    --name fitagent/twilio \
    --description "Twilio credentials" \
    --secret-string '{"account_sid":"test","auth_token":"test"}' \
    --region us-east-1

awslocal secretsmanager create-secret \
    --name fitagent/google-oauth \
    --description "Google OAuth credentials" \
    --secret-string '{"client_id":"test","client_secret":"test"}' \
    --region us-east-1

awslocal secretsmanager create-secret \
    --name fitagent/outlook-oauth \
    --description "Outlook OAuth credentials" \
    --secret-string '{"client_id":"test","client_secret":"test"}' \
    --region us-east-1

echo "✓ Secrets Manager secrets created"

echo "========================================="
echo "LocalStack initialization complete!"
echo "========================================="
echo ""
echo "Resources created:"
echo "  - DynamoDB table: fitagent-main"
echo "  - S3 bucket: fitagent-receipts-local"
echo "  - SQS FIFO queues: fitagent-messages.fifo, fitagent-notifications.fifo, fitagent-messages-dlq.fifo"
echo "  - KMS key: alias/fitagent-oauth-key"
echo "  - Secrets Manager: fitagent/twilio, fitagent/google-oauth, fitagent/outlook-oauth"
echo ""
