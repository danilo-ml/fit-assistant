"""
Shared pytest fixtures for all tests.
"""

import os
import sys
import pytest
import boto3
from moto import mock_aws

# Set AWS environment variables BEFORE any imports that might use boto3
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_SECURITY_TOKEN"] = "test"
os.environ["AWS_SESSION_TOKEN"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Add src directory to Python path to support both absolute and relative imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope="session", autouse=True)
def aws_credentials():
    """Mock AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["AWS_SECURITY_TOKEN"] = "test"
    os.environ["AWS_SESSION_TOKEN"] = "test"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


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
        
        # Create queues (FIFO)
        dlq_response = client.create_queue(
            QueueName="fitagent-messages-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false"
            }
        )
        dlq_url = dlq_response["QueueUrl"]
        
        dlq_attrs = client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=["QueueArn"]
        )
        dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
        
        # Main queue with DLQ (FIFO)
        client.create_queue(
            QueueName="fitagent-messages.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false",
                "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}'
            }
        )
        
        # Notification queue (FIFO)
        client.create_queue(
            QueueName="fitagent-notifications.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false"
            }
        )
        
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


# ============================================================================
# LocalStack Fixtures for Integration/E2E Tests
# ============================================================================

@pytest.fixture(scope="session")
def localstack_endpoint() -> str:
    """
    LocalStack endpoint URL.
    
    Returns the endpoint URL for LocalStack services. Checks for health
    before returning to ensure LocalStack is ready.
    """
    endpoint = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    
    # Only perform health check if USE_LOCALSTACK is enabled
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if use_localstack:
        from tests.utils.localstack_helpers import wait_for_localstack
        try:
            wait_for_localstack(endpoint=endpoint, timeout=30)
        except TimeoutError as e:
            pytest.skip(f"LocalStack not available: {str(e)}")
    
    return endpoint


@pytest.fixture
def dynamodb_localstack(localstack_endpoint):
    """
    Real DynamoDB client connected to LocalStack.
    
    Use this fixture for integration and E2E tests that need realistic
    DynamoDB behavior. Requires LocalStack to be running.
    """
    # Check if LocalStack should be used
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if not use_localstack:
        pytest.skip("LocalStack not enabled. Set USE_LOCALSTACK=true to run this test.")
    
    client = boto3.client(
        "dynamodb",
        endpoint_url=localstack_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    # Retry logic for transient connection failures
    max_retries = 3
    retry_delay = 1
    import time
    
    for attempt in range(max_retries):
        try:
            # Ensure table exists (should be created by localstack-init scripts)
            client.describe_table(TableName="fitagent-main")
            break
        except client.exceptions.ResourceNotFoundException:
            # Create table if it doesn't exist
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
                    {"AttributeName": "payment_status", "AttributeType": "S"},
                    {"AttributeName": "confirmation_status_datetime", "AttributeType": "S"}
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
                    },
                    {
                        "IndexName": "session-confirmation-index",
                        "KeySchema": [
                            {"AttributeName": "trainer_id", "KeyType": "HASH"},
                            {"AttributeName": "confirmation_status_datetime", "KeyType": "RANGE"}
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
            break
        except Exception as e:
            # Handle transient connection failures
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                pytest.fail(f"Failed to connect to LocalStack DynamoDB after {max_retries} attempts: {str(e)}")
    
    yield client
    
    # Cleanup: Clear all items from table after test
    try:
        response = client.scan(TableName="fitagent-main")
        for item in response.get("Items", []):
            client.delete_item(
                TableName="fitagent-main",
                Key={"PK": item["PK"], "SK": item["SK"]}
            )
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def s3_localstack(localstack_endpoint):
    """
    Real S3 client connected to LocalStack.
    
    Use this fixture for integration and E2E tests that need realistic
    S3 behavior. Requires LocalStack to be running.
    """
    # Check if LocalStack should be used
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if not use_localstack:
        pytest.skip("LocalStack not enabled. Set USE_LOCALSTACK=true to run this test.")
    
    client = boto3.client(
        "s3",
        endpoint_url=localstack_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    # Retry logic for transient connection failures
    max_retries = 3
    retry_delay = 1
    import time
    
    bucket_name = "fitagent-receipts-local"
    for attempt in range(max_retries):
        try:
            # Ensure bucket exists
            client.head_bucket(Bucket=bucket_name)
            break
        except client.exceptions.NoSuchBucket:
            client.create_bucket(Bucket=bucket_name)
            break
        except Exception as e:
            # Handle transient connection failures
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                pytest.fail(f"Failed to connect to LocalStack S3 after {max_retries} attempts: {str(e)}")
    
    yield client
    
    # Cleanup: Delete all objects from bucket after test
    try:
        response = client.list_objects_v2(Bucket=bucket_name)
        for obj in response.get("Contents", []):
            client.delete_object(Bucket=bucket_name, Key=obj["Key"])
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def sqs_localstack(localstack_endpoint):
    """
    Real SQS client connected to LocalStack.
    
    Use this fixture for integration and E2E tests that need realistic
    SQS behavior. Requires LocalStack to be running.
    """
    # Check if LocalStack should be used
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if not use_localstack:
        pytest.skip("LocalStack not enabled. Set USE_LOCALSTACK=true to run this test.")
    
    client = boto3.client(
        "sqs",
        endpoint_url=localstack_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    # Retry logic for transient connection failures
    max_retries = 3
    retry_delay = 1
    import time
    
    for attempt in range(max_retries):
        try:
            # Ensure queues exist
            # Create DLQ
            dlq_response = client.create_queue(
                QueueName="fitagent-messages-dlq.fifo",
                Attributes={
                    "FifoQueue": "true",
                    "ContentBasedDeduplication": "false"
                }
            )
            dlq_url = dlq_response["QueueUrl"]
            
            dlq_attrs = client.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=["QueueArn"]
            )
            dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
            
            # Create main queue
            client.create_queue(
                QueueName="fitagent-messages.fifo",
                Attributes={
                    "FifoQueue": "true",
                    "ContentBasedDeduplication": "false",
                    "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}'
                }
            )
            
            # Create notification queue
            client.create_queue(
                QueueName="fitagent-notifications.fifo",
                Attributes={
                    "FifoQueue": "true",
                    "ContentBasedDeduplication": "false"
                }
            )
            break
        except client.exceptions.QueueNameExists:
            # Queues already exist
            break
        except Exception as e:
            # Handle transient connection failures
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
            else:
                pytest.fail(f"Failed to connect to LocalStack SQS after {max_retries} attempts: {str(e)}")
    
    yield client
    
    # Cleanup: Purge all queues after test
    try:
        for queue_name in ["fitagent-messages.fifo", "fitagent-notifications.fifo", "fitagent-messages-dlq.fifo"]:
            queue_url = client.get_queue_url(QueueName=queue_name)["QueueUrl"]
            client.purge_queue(QueueUrl=queue_url)
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def lambda_localstack(localstack_endpoint):
    """
    Real Lambda client connected to LocalStack.
    
    Use this fixture for E2E tests that need to deploy and invoke
    Lambda functions. Requires LocalStack to be running.
    """
    # Check if LocalStack should be used
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if not use_localstack:
        pytest.skip("LocalStack not enabled. Set USE_LOCALSTACK=true to run this test.")
    
    client = boto3.client(
        "lambda",
        endpoint_url=localstack_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    yield client


@pytest.fixture
def events_localstack(localstack_endpoint):
    """
    Real EventBridge client connected to LocalStack.
    
    Use this fixture for E2E tests that need to create and trigger
    EventBridge rules. Requires LocalStack to be running.
    """
    # Check if LocalStack should be used
    use_localstack = os.getenv("USE_LOCALSTACK", "false").lower() == "true"
    if not use_localstack:
        pytest.skip("LocalStack not enabled. Set USE_LOCALSTACK=true to run this test.")
    
    client = boto3.client(
        "events",
        endpoint_url=localstack_endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    
    yield client



# ============================================================================
# External API Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_twilio():
    """
    Provide mocked Twilio client.
    
    Returns a MockTwilioClient that tracks all messages sent and provides
    configurable responses for testing.
    """
    from tests.fixtures.mocks import MockTwilioClient
    return MockTwilioClient()


# mock_bedrock fixture removed - use real AWS Bedrock for consistency


@pytest.fixture
def mock_calendar():
    """
    Provide mocked Calendar client.
    
    Returns a MockCalendarClient that simulates Google Calendar/Outlook
    operations and tracks all events.
    """
    from tests.fixtures.mocks import MockCalendarClient
    return MockCalendarClient()
