"""
Receipt storage service for handling payment receipt media.

This service downloads receipt media from Twilio and uploads to S3 with
encryption and proper key structure for multi-tenant isolation.

Requirements: 5.2, 20.2
"""

import uuid
import mimetypes
from datetime import datetime
from typing import Optional
import requests
import boto3
from botocore.exceptions import ClientError
from config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class ReceiptStorageService:
    """
    Service for storing and retrieving payment receipt media in S3.

    Provides:
    - store_receipt(): Download from Twilio and upload to S3
    - get_receipt_url(): Generate presigned URLs for viewing receipts

    S3 Key Format: receipts/{trainer_id}/{student_id}/{timestamp}_{uuid}.{ext}
    Encryption: AES256 server-side encryption
    """

    def __init__(
        self,
        s3_bucket: Optional[str] = None,
        aws_region: Optional[str] = None,
        aws_endpoint_url: Optional[str] = None,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
    ):
        """
        Initialize receipt storage service.

        Args:
            s3_bucket: S3 bucket name (defaults to settings)
            aws_region: AWS region (defaults to settings)
            aws_endpoint_url: AWS endpoint URL for LocalStack (defaults to settings)
            twilio_account_sid: Twilio account SID (defaults to settings)
            twilio_auth_token: Twilio auth token (defaults to settings)
        """
        self.s3_bucket = s3_bucket or settings.s3_bucket
        self.aws_region = aws_region or settings.aws_region
        self.twilio_account_sid = twilio_account_sid or settings.twilio_account_sid
        self.twilio_auth_token = twilio_auth_token or settings.twilio_auth_token

        # Initialize S3 client
        s3_config = {"region_name": self.aws_region}
        if aws_endpoint_url or settings.aws_endpoint_url:
            s3_config["endpoint_url"] = aws_endpoint_url or settings.aws_endpoint_url

        self.s3_client = boto3.client("s3", **s3_config)

        logger.info(
            "ReceiptStorageService initialized",
            s3_bucket=self.s3_bucket,
            aws_region=self.aws_region,
        )

    def store_receipt(
        self, trainer_id: str, student_id: str, media_url: str, media_type: str
    ) -> dict:
        """
        Download receipt media from Twilio and upload to S3.

        Downloads the media file from Twilio's servers and uploads it to S3
        with AES256 server-side encryption. The S3 key follows the format:
        receipts/{trainer_id}/{student_id}/{timestamp}_{uuid}.{ext}

        Args:
            trainer_id: Trainer identifier for multi-tenant isolation
            student_id: Student identifier for organization
            media_url: Twilio media URL to download from
            media_type: MIME type of the media (e.g., 'image/jpeg', 'application/pdf')

        Returns:
            dict: {
                'success': bool,
                's3_key': str,
                's3_bucket': str,
                'media_type': str,
                'size_bytes': int
            }

        Raises:
            requests.RequestException: If download from Twilio fails
            ClientError: If S3 upload fails

        Example:
            >>> service = ReceiptStorageService()
            >>> result = service.store_receipt(
            ...     trainer_id='trainer-123',
            ...     student_id='student-456',
            ...     media_url='https://api.twilio.com/media/ME123',
            ...     media_type='image/jpeg'
            ... )
            >>> print(result['s3_key'])
            receipts/trainer-123/student-456/20240115_103000_abc123.jpg
        """
        logger.info(
            "Starting receipt storage",
            trainer_id=trainer_id,
            student_id=student_id,
            media_type=media_type,
        )

        try:
            # Download media from Twilio
            logger.info("Downloading media from Twilio", media_url=media_url[:50] + "...")
            response = requests.get(
                media_url, auth=(self.twilio_account_sid, self.twilio_auth_token), timeout=30
            )
            response.raise_for_status()

            media_content = response.content
            content_size = len(media_content)

            logger.info(
                "Media downloaded successfully", size_bytes=content_size, media_type=media_type
            )

            # Determine file extension from MIME type
            extension = mimetypes.guess_extension(media_type)
            if not extension:
                # Fallback extensions for common types
                extension_map = {
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/gif": ".gif",
                    "application/pdf": ".pdf",
                }
                extension = extension_map.get(media_type, ".bin")

            # Generate S3 key with format: receipts/{trainer_id}/{student_id}/{timestamp}_{uuid}.{ext}
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]  # Use first 8 chars of UUID for brevity
            s3_key = f"receipts/{trainer_id}/{student_id}/{timestamp}_{unique_id}{extension}"

            logger.info("Uploading to S3", s3_key=s3_key, s3_bucket=self.s3_bucket)

            # Upload to S3 with AES256 server-side encryption
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=media_content,
                ContentType=media_type,
                ServerSideEncryption="AES256",
                Metadata={
                    "trainer_id": trainer_id,
                    "student_id": student_id,
                    "uploaded_at": datetime.utcnow().isoformat(),
                },
            )

            logger.info("Receipt stored successfully", s3_key=s3_key, size_bytes=content_size)

            return {
                "success": True,
                "s3_key": s3_key,
                "s3_bucket": self.s3_bucket,
                "media_type": media_type,
                "size_bytes": content_size,
            }

        except requests.RequestException as e:
            logger.error(
                "Failed to download media from Twilio",
                media_url=media_url[:50] + "...",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        except ClientError as e:
            logger.error(
                "Failed to upload to S3",
                s3_bucket=self.s3_bucket,
                s3_key=s3_key if "s3_key" in locals() else "unknown",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        except Exception as e:
            logger.error(
                "Unexpected error during receipt storage",
                trainer_id=trainer_id,
                student_id=student_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def get_receipt_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for viewing receipt media.

        Creates a temporary URL that allows viewing the receipt without
        requiring AWS credentials. URL expires after the specified time.

        Args:
            s3_key: S3 key of the receipt (from store_receipt result)
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)

        Returns:
            str: Presigned URL for accessing the receipt

        Raises:
            ClientError: If presigned URL generation fails

        Example:
            >>> service = ReceiptStorageService()
            >>> url = service.get_receipt_url(
            ...     s3_key='receipts/trainer-123/student-456/20240115_103000_abc123.jpg'
            ... )
            >>> print(url)
            https://s3.amazonaws.com/fitagent-receipts/receipts/...?X-Amz-Signature=...
        """
        logger.info("Generating presigned URL", s3_key=s3_key, expiration=expiration)

        try:
            presigned_url = self.s3_client.generate_presigned_url(
                "get_object", Params={"Bucket": self.s3_bucket, "Key": s3_key}, ExpiresIn=expiration
            )

            logger.info(
                "Presigned URL generated successfully", s3_key=s3_key, expiration=expiration
            )

            return presigned_url

        except ClientError as e:
            logger.error(
                "Failed to generate presigned URL",
                s3_bucket=self.s3_bucket,
                s3_key=s3_key,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
