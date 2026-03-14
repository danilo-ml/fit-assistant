"""
Local SQS poller for development.

In production, Lambda is triggered automatically by SQS.
For local development, this script polls SQS and processes messages.
"""

import json
import time
import os

# Set AWS environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import boto3
from handlers.message_processor import lambda_handler
from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)

# Initialize SQS client
sqs_client = boto3.client(
    "sqs",
    endpoint_url=settings.aws_endpoint_url,
    region_name=settings.aws_region,
    aws_access_key_id=settings.aws_access_key_id,
    aws_secret_access_key=settings.aws_secret_access_key,
)


def poll_and_process():
    """Poll SQS queue and process messages."""
    logger.info("Starting SQS poller", queue_url=settings.sqs_queue_url)
    
    while True:
        try:
            # Receive messages from SQS
            response = sqs_client.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=1,  # FIFO queue processes one at a time per group
                WaitTimeSeconds=20,  # Long polling
                MessageAttributeNames=["All"],
            )
            
            messages = response.get("Messages", [])
            
            if not messages:
                logger.debug("No messages in queue")
                continue
            
            for message in messages:
                logger.info(
                    "Processing message from SQS",
                    message_id=message["MessageId"],
                    receipt_handle=message["ReceiptHandle"][:20] + "...",
                )
                
                # Create Lambda event format
                event = {
                    "Records": [
                        {
                            "messageId": message["MessageId"],
                            "receiptHandle": message["ReceiptHandle"],
                            "body": message["Body"],
                            "attributes": message.get("Attributes", {}),
                            "messageAttributes": message.get("MessageAttributes", {}),
                            "eventSource": "aws:sqs",
                        }
                    ]
                }
                
                try:
                    # Process message
                    lambda_handler(event, None)
                    
                    # Delete message from queue
                    sqs_client.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                    
                    logger.info(
                        "Message processed and deleted",
                        message_id=message["MessageId"],
                    )
                    
                except Exception as e:
                    logger.error(
                        "Failed to process message",
                        message_id=message["MessageId"],
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Message will be retried automatically by SQS
                    
        except KeyboardInterrupt:
            logger.info("Stopping SQS poller")
            break
        except Exception as e:
            logger.error(
                "Error in SQS poller",
                error=str(e),
                error_type=type(e).__name__,
            )
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    poll_and_process()
