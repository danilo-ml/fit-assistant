"""
Custom assertion helpers for common test patterns.

Provides assertion functions for DynamoDB, S3, SQS, and language validation.
"""

import time
import re
from typing import Dict, Any, Optional


def assert_dynamodb_item_exists(
    client,
    table_name: str,
    pk: str,
    sk: str
) -> Dict[str, Any]:
    """
    Assert item exists in DynamoDB and return it.
    
    Args:
        client: Boto3 DynamoDB client
        table_name: Table name
        pk: Partition key value
        sk: Sort key value
    
    Returns:
        DynamoDB item
    
    Raises:
        AssertionError: If item doesn't exist
    """
    response = client.get_item(
        TableName=table_name,
        Key={"PK": {"S": pk}, "SK": {"S": sk}}
    )
    
    assert "Item" in response, f"Item not found: PK={pk}, SK={sk}"
    return response["Item"]


def assert_dynamodb_item_not_exists(
    client,
    table_name: str,
    pk: str,
    sk: str
) -> None:
    """
    Assert item does not exist in DynamoDB.
    
    Args:
        client: Boto3 DynamoDB client
        table_name: Table name
        pk: Partition key value
        sk: Sort key value
    
    Raises:
        AssertionError: If item exists
    """
    response = client.get_item(
        TableName=table_name,
        Key={"PK": {"S": pk}, "SK": {"S": sk}}
    )
    
    assert "Item" not in response, f"Item should not exist: PK={pk}, SK={sk}"


def assert_s3_object_exists(
    client,
    bucket: str,
    key: str
) -> bool:
    """
    Assert object exists in S3.
    
    Args:
        client: Boto3 S3 client
        bucket: Bucket name
        key: Object key
    
    Returns:
        True if object exists
    
    Raises:
        AssertionError: If object doesn't exist
    """
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except client.exceptions.NoSuchKey:
        raise AssertionError(f"S3 object not found: s3://{bucket}/{key}")


def assert_s3_object_not_exists(
    client,
    bucket: str,
    key: str
) -> None:
    """
    Assert object does not exist in S3.
    
    Args:
        client: Boto3 S3 client
        bucket: Bucket name
        key: Object key
    
    Raises:
        AssertionError: If object exists
    """
    try:
        client.head_object(Bucket=bucket, Key=key)
        raise AssertionError(f"S3 object should not exist: s3://{bucket}/{key}")
    except client.exceptions.NoSuchKey:
        pass  # Expected


def assert_sqs_message_sent(
    client,
    queue_url: str,
    expected_body: Optional[Dict[str, Any]] = None,
    timeout: int = 5,
    message_group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Assert message was sent to SQS queue.
    
    Polls the queue for a message and optionally validates the body.
    
    Args:
        client: Boto3 SQS client
        queue_url: Queue URL
        expected_body: Expected message body (optional)
        timeout: Maximum seconds to wait for message
        message_group_id: Expected message group ID for FIFO queues (optional)
    
    Returns:
        Message dict
    
    Raises:
        AssertionError: If message not found or body doesn't match
    """
    import json
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
            AttributeNames=["All"]
        )
        
        if "Messages" in response and len(response["Messages"]) > 0:
            message = response["Messages"][0]
            
            # Validate message group ID if specified
            if message_group_id is not None:
                actual_group_id = message.get("Attributes", {}).get("MessageGroupId")
                assert actual_group_id == message_group_id, \
                    f"Message group ID mismatch: expected {message_group_id}, got {actual_group_id}"
            
            # Validate body if specified
            if expected_body is not None:
                actual_body = json.loads(message["Body"])
                assert actual_body == expected_body, \
                    f"Message body mismatch: expected {expected_body}, got {actual_body}"
            
            # Delete message to clean up
            client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"]
            )
            
            return message
        
        time.sleep(0.5)
    
    raise AssertionError(f"No message received from queue within {timeout} seconds")


def assert_sqs_queue_empty(
    client,
    queue_url: str,
    timeout: int = 2
) -> None:
    """
    Assert SQS queue is empty.
    
    Args:
        client: Boto3 SQS client
        queue_url: Queue URL
        timeout: Seconds to wait for messages
    
    Raises:
        AssertionError: If queue has messages
    """
    response = client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=timeout
    )
    
    assert "Messages" not in response or len(response["Messages"]) == 0, \
        f"Queue should be empty but has {len(response.get('Messages', []))} messages"


def assert_portuguese_message(message: str) -> None:
    """
    Assert message is in Portuguese.
    
    Checks for common Portuguese words and patterns to validate
    that the message is in Portuguese, not English.
    
    Args:
        message: Message text to validate
    
    Raises:
        AssertionError: If message appears to be in English
    """
    # Common Portuguese words/patterns
    portuguese_indicators = [
        r'\bvocê\b', r'\bseu\b', r'\bsua\b', r'\bcom\b', r'\bpara\b',
        r'\bpor\b', r'\bsão\b', r'\bestá\b', r'\bestão\b', r'\btem\b',
        r'\bque\b', r'\bmais\b', r'\bsobre\b', r'\baqui\b', r'\bagora\b',
        r'\bsim\b', r'\bnão\b', r'\bpode\b', r'\bfazer\b', r'\bver\b',
        r'\bção\b', r'\bções\b', r'\bção\b'  # Common Portuguese suffixes
    ]
    
    # Common English words that shouldn't appear in Portuguese messages
    english_indicators = [
        r'\byou\b', r'\byour\b', r'\bthe\b', r'\band\b', r'\bfor\b',
        r'\bwith\b', r'\bthis\b', r'\bthat\b', r'\bhave\b', r'\bhas\b',
        r'\bare\b', r'\bwas\b', r'\bwere\b', r'\bbeen\b', r'\bcan\b'
    ]
    
    message_lower = message.lower()
    
    # Check for English indicators (should not be present)
    for pattern in english_indicators:
        if re.search(pattern, message_lower):
            raise AssertionError(
                f"Message appears to be in English (found '{pattern}'): {message}"
            )
    
    # Check for Portuguese indicators (at least one should be present)
    has_portuguese = any(
        re.search(pattern, message_lower)
        for pattern in portuguese_indicators
    )
    
    if not has_portuguese:
        # If no clear Portuguese indicators, check for Portuguese characters
        has_portuguese_chars = any(char in message for char in ['ã', 'õ', 'ç', 'á', 'é', 'í', 'ó', 'ú', 'â', 'ê', 'ô'])
        
        if not has_portuguese_chars:
            raise AssertionError(
                f"Message does not appear to be in Portuguese: {message}"
            )


def assert_valid_phone_number(phone_number: str) -> None:
    """
    Assert phone number is in valid E.164 format.
    
    Args:
        phone_number: Phone number to validate
    
    Raises:
        AssertionError: If phone number is not in E.164 format
    """
    pattern = r'^\+[1-9]\d{1,14}$'
    assert re.match(pattern, phone_number), \
        f"Phone number not in E.164 format: {phone_number}"


def assert_valid_iso_datetime(datetime_str: str) -> None:
    """
    Assert string is a valid ISO datetime.
    
    Args:
        datetime_str: Datetime string to validate
    
    Raises:
        AssertionError: If string is not a valid ISO datetime
    """
    from datetime import datetime
    
    try:
        datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise AssertionError(f"Invalid ISO datetime: {datetime_str}")


def assert_valid_uuid(uuid_str: str) -> None:
    """
    Assert string is a valid UUID.
    
    Args:
        uuid_str: UUID string to validate
    
    Raises:
        AssertionError: If string is not a valid UUID
    """
    from uuid import UUID
    
    try:
        UUID(uuid_str)
    except (ValueError, AttributeError):
        raise AssertionError(f"Invalid UUID: {uuid_str}")


def assert_dict_contains(actual: Dict[str, Any], expected: Dict[str, Any]) -> None:
    """
    Assert dictionary contains all expected key-value pairs.
    
    Args:
        actual: Actual dictionary
        expected: Expected key-value pairs
    
    Raises:
        AssertionError: If any expected key-value pair is missing or different
    """
    for key, expected_value in expected.items():
        assert key in actual, f"Key '{key}' not found in dictionary"
        assert actual[key] == expected_value, \
            f"Value mismatch for key '{key}': expected {expected_value}, got {actual[key]}"
