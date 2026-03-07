"""
Shared pytest fixtures for all tests.
"""

import os
import pytest
import boto3
from moto import mock_aws


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_SECURITY_TOKEN"] = "test"
    os.environ["AWS_SESSION_TOKEN"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_client(aws_credentials):
    """Create a mocked DynamoDB client."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        
        # Create the main table
        client.create_table(
            TableName="fitagent-main",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "phone_number", "AttributeType": "S"},
                {"AttributeName": "entity_type", "AttributeType": "S"},
                {"AttributeName": "trainer_id", "AttributeType": "S"},
                {"AttributeName": "session_datetime", "AttributeType": "S"},
                {"AttributeName": "payment_status", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "phone-number-index",
                    "KeySchema": [
                        {"AttributeName": "phone_number", "KeyType": "HASH"},
                        {"AttributeName": "entity_type", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                },
                {
                    "IndexName": "session-date-index",
                    "KeySchema": [
                        {"AttributeName": "trainer_id", "KeyType": "HASH"},
                        {"AttributeName": "session_datetime", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                },
                {
                    "IndexName": "payment-status-index",
                    "KeySchema": [
                        {"AttributeName": "trainer_id", "KeyType": "HASH"},
                        {"AttributeName": "payment_status", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5
                    }
                }
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        
        yield client


@pytest.fixture
def s3_client(aws_credentials):
    """Create a mocked S3 client."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="fitagent-receipts-local")
        yield client


@pytest.fixture
def sqs_client(aws_credentials):
    """Create a mocked SQS client."""
    with mock_aws():
        client = boto3.client("sqs", region_name="us-east-1")
        
        # Create queues
        dlq_response = client.create_queue(QueueName="fitagent-messages-dlq")
        dlq_url = dlq_response["QueueUrl"]
        
        dlq_attrs = client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=["QueueArn"]
        )
        dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
        
        # Main queue with DLQ
        client.create_queue(
            QueueName="fitagent-messages",
            Attributes={
                "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}'
            }
        )
        
        # Notification queue
        client.create_queue(QueueName="fitagent-notifications")
        
        yield client


@pytest.fixture
def kms_client(aws_credentials):
    """Create a mocked KMS client."""
    with mock_aws():
        client = boto3.client("kms", region_name="us-east-1")
        
        # Create key
        key_response = client.create_key(Description="FitAgent OAuth token encryption")
        key_id = key_response["KeyMetadata"]["KeyId"]
        
        # Create alias
        client.create_alias(
            AliasName="alias/fitagent-oauth-key",
            TargetKeyId=key_id
        )
        
        yield client


@pytest.fixture
def secretsmanager_client(aws_credentials):
    """Create a mocked Secrets Manager client."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        
        # Create secrets
        client.create_secret(
            Name="fitagent/twilio",
            SecretString='{"account_sid":"test","auth_token":"test"}'
        )
        
        client.create_secret(
            Name="fitagent/google-oauth",
            SecretString='{"client_id":"test","client_secret":"test"}'
        )
        
        client.create_secret(
            Name="fitagent/outlook-oauth",
            SecretString='{"client_id":"test","client_secret":"test"}'
        )
        
        yield client
