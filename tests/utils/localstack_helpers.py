"""
LocalStack helper utilities for test setup and management.

Provides functions for waiting for LocalStack readiness, initializing resources,
and cleaning up after tests.
"""

import time
import requests
from typing import List, Optional
import boto3


def wait_for_localstack(
    endpoint: str = "http://localhost:4566",
    timeout: int = 30,
    services: Optional[List[str]] = None
) -> bool:
    """
    Wait for LocalStack services to be ready.
    
    Args:
        endpoint: LocalStack endpoint URL
        timeout: Maximum seconds to wait
        services: List of service names to check (default: ["dynamodb", "s3", "sqs"])
    
    Returns:
        True if services are ready, False if timeout
    
    Raises:
        TimeoutError: If services don't become ready within timeout
    """
    if services is None:
        services = ["dynamodb", "s3", "sqs"]
    
    health_url = f"{endpoint}/_localstack/health"
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(health_url, timeout=2)
            if response.status_code == 200:
                health_data = response.json()
                services_status = health_data.get("services", {})
                
                # Check if all required services are available
                all_ready = all(
                    services_status.get(service) in ["available", "running"]
                    for service in services
                )
                
                if all_ready:
                    return True
        except (requests.RequestException, ValueError):
            pass  # Connection failed or invalid JSON, retry
        
        time.sleep(1)
    
    raise TimeoutError(
        f"LocalStack services {services} did not become ready within {timeout} seconds"
    )


def initialize_localstack_resources(
    dynamodb_client,
    s3_client,
    sqs_client
) -> None:
    """
    Initialize LocalStack with required resources.
    
    Creates DynamoDB tables, S3 buckets, and SQS queues needed for tests.
    Safe to call multiple times - checks if resources exist before creating.
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        s3_client: Boto3 S3 client
        sqs_client: Boto3 SQS client
    """
    # Create DynamoDB table if it doesn't exist
    try:
        dynamodb_client.describe_table(TableName="fitagent-main")
    except dynamodb_client.exceptions.ResourceNotFoundException:
        dynamodb_client.create_table(
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
        
        # Wait for table to be active
        waiter = dynamodb_client.get_waiter("table_exists")
        waiter.wait(TableName="fitagent-main")
    
    # Create S3 bucket if it doesn't exist
    bucket_name = "fitagent-receipts-local"
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except Exception:
        s3_client.create_bucket(Bucket=bucket_name)
    
    # Create SQS queues if they don't exist
    try:
        # Create DLQ
        dlq_response = sqs_client.create_queue(
            QueueName="fitagent-messages-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false"
            }
        )
        dlq_url = dlq_response["QueueUrl"]
        
        dlq_attrs = sqs_client.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=["QueueArn"]
        )
        dlq_arn = dlq_attrs["Attributes"]["QueueArn"]
        
        # Create main queue
        sqs_client.create_queue(
            QueueName="fitagent-messages.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false",
                "RedrivePolicy": f'{{"deadLetterTargetArn":"{dlq_arn}","maxReceiveCount":"3"}}'
            }
        )
        
        # Create notification queue
        sqs_client.create_queue(
            QueueName="fitagent-notifications.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "false"
            }
        )
    except sqs_client.exceptions.QueueNameExists:
        pass  # Queues already exist


def cleanup_localstack_resources(
    dynamodb_client,
    s3_client,
    sqs_client
) -> None:
    """
    Clean up LocalStack resources after tests.
    
    Removes all items from DynamoDB tables, objects from S3 buckets,
    and messages from SQS queues. Does not delete the resources themselves.
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        s3_client: Boto3 S3 client
        sqs_client: Boto3 SQS client
    """
    # Clear DynamoDB table
    try:
        response = dynamodb_client.scan(TableName="fitagent-main")
        for item in response.get("Items", []):
            dynamodb_client.delete_item(
                TableName="fitagent-main",
                Key={"PK": item["PK"], "SK": item["SK"]}
            )
        
        # Handle pagination if there are more items
        while "LastEvaluatedKey" in response:
            response = dynamodb_client.scan(
                TableName="fitagent-main",
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            for item in response.get("Items", []):
                dynamodb_client.delete_item(
                    TableName="fitagent-main",
                    Key={"PK": item["PK"], "SK": item["SK"]}
                )
    except Exception:
        pass  # Ignore cleanup errors
    
    # Clear S3 bucket
    try:
        bucket_name = "fitagent-receipts-local"
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        for obj in response.get("Contents", []):
            s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
        
        # Handle pagination if there are more objects
        while response.get("IsTruncated"):
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                ContinuationToken=response["NextContinuationToken"]
            )
            for obj in response.get("Contents", []):
                s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
    except Exception:
        pass  # Ignore cleanup errors
    
    # Purge SQS queues
    try:
        for queue_name in ["fitagent-messages.fifo", "fitagent-notifications.fifo", "fitagent-messages-dlq.fifo"]:
            queue_url = sqs_client.get_queue_url(QueueName=queue_name)["QueueUrl"]
            sqs_client.purge_queue(QueueUrl=queue_url)
    except Exception:
        pass  # Ignore cleanup errors


def get_localstack_logs() -> str:
    """
    Retrieve LocalStack container logs for debugging.
    
    Returns:
        Container logs as string, or error message if retrieval fails
    """
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "logs", "localstack_main"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"Failed to retrieve LocalStack logs: {str(e)}"
