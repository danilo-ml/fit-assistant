"""
Unit tests for ReceiptStorageService.

Tests receipt media download from Twilio and upload to S3 with encryption.

Requirements: 5.2, 20.2
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
import requests
from src.services.receipt_storage import ReceiptStorageService


class TestReceiptStorageService:
    """Test suite for ReceiptStorageService."""

    @pytest.fixture
    def service(self):
        """Create ReceiptStorageService instance with test configuration."""
        return ReceiptStorageService(
            s3_bucket="test-bucket",
            aws_region="us-east-1",
            aws_endpoint_url="http://localhost:4566",
            twilio_account_sid="test_sid",
            twilio_auth_token="test_token",
        )

    @pytest.fixture
    def mock_s3_client(self, service):
        """Mock S3 client."""
        with patch.object(service, "s3_client") as mock:
            yield mock

    @pytest.fixture
    def mock_requests_get(self):
        """Mock requests.get for Twilio downloads."""
        with patch("src.services.receipt_storage.requests.get") as mock:
            yield mock

    def test_initialization(self, service):
        """Test service initializes with correct configuration."""
        assert service.s3_bucket == "test-bucket"
        assert service.aws_region == "us-east-1"
        assert service.twilio_account_sid == "test_sid"
        assert service.twilio_auth_token == "test_token"
        assert service.s3_client is not None

    def test_store_receipt_success_jpeg(self, service, mock_s3_client, mock_requests_get):
        """Test successful receipt storage with JPEG image."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt
        result = service.store_receipt(
            trainer_id="trainer-123",
            student_id="student-456",
            media_url="https://api.twilio.com/media/ME123",
            media_type="image/jpeg",
        )

        # Verify download was called with correct auth
        mock_requests_get.assert_called_once_with(
            "https://api.twilio.com/media/ME123", auth=("test_sid", "test_token"), timeout=30
        )

        # Verify S3 upload was called
        assert mock_s3_client.put_object.called
        call_kwargs = mock_s3_client.put_object.call_args[1]

        # Verify S3 parameters
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Body"] == b"fake_image_data"
        assert call_kwargs["ContentType"] == "image/jpeg"
        assert call_kwargs["ServerSideEncryption"] == "AES256"

        # Verify S3 key format: receipts/{trainer_id}/{student_id}/{timestamp}_{uuid}.{ext}
        s3_key = call_kwargs["Key"]
        assert s3_key.startswith("receipts/trainer-123/student-456/")
        assert s3_key.endswith(".jpg")

        # Verify metadata
        assert call_kwargs["Metadata"]["trainer_id"] == "trainer-123"
        assert call_kwargs["Metadata"]["student_id"] == "student-456"
        assert "uploaded_at" in call_kwargs["Metadata"]

        # Verify result
        assert result["success"] is True
        assert result["s3_key"] == s3_key
        assert result["s3_bucket"] == "test-bucket"
        assert result["media_type"] == "image/jpeg"
        assert result["size_bytes"] == len(b"fake_image_data")

    def test_store_receipt_success_pdf(self, service, mock_s3_client, mock_requests_get):
        """Test successful receipt storage with PDF document."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_pdf_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt
        result = service.store_receipt(
            trainer_id="trainer-789",
            student_id="student-012",
            media_url="https://api.twilio.com/media/ME456",
            media_type="application/pdf",
        )

        # Verify S3 key has .pdf extension
        call_kwargs = mock_s3_client.put_object.call_args[1]
        s3_key = call_kwargs["Key"]
        assert s3_key.endswith(".pdf")

        # Verify result
        assert result["success"] is True
        assert result["media_type"] == "application/pdf"

    def test_store_receipt_success_png(self, service, mock_s3_client, mock_requests_get):
        """Test successful receipt storage with PNG image."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_png_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt
        result = service.store_receipt(
            trainer_id="trainer-abc",
            student_id="student-def",
            media_url="https://api.twilio.com/media/ME789",
            media_type="image/png",
        )

        # Verify S3 key has .png extension
        call_kwargs = mock_s3_client.put_object.call_args[1]
        s3_key = call_kwargs["Key"]
        assert s3_key.endswith(".png")

        # Verify result
        assert result["success"] is True
        assert result["media_type"] == "image/png"

    def test_store_receipt_unknown_mime_type(self, service, mock_s3_client, mock_requests_get):
        """Test receipt storage with unknown MIME type uses .bin extension."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt with unknown type
        result = service.store_receipt(
            trainer_id="trainer-123",
            student_id="student-456",
            media_url="https://api.twilio.com/media/ME999",
            media_type="application/unknown",
        )

        # Verify S3 key has .bin extension
        call_kwargs = mock_s3_client.put_object.call_args[1]
        s3_key = call_kwargs["Key"]
        assert s3_key.endswith(".bin")

        # Verify result
        assert result["success"] is True

    def test_store_receipt_s3_key_format(self, service, mock_s3_client, mock_requests_get):
        """Test S3 key follows correct format with all components."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt
        service.store_receipt(
            trainer_id="trainer-xyz",
            student_id="student-uvw",
            media_url="https://api.twilio.com/media/ME111",
            media_type="image/jpeg",
        )

        # Verify S3 key format
        call_kwargs = mock_s3_client.put_object.call_args[1]
        s3_key = call_kwargs["Key"]

        # Split key into components
        parts = s3_key.split("/")
        assert len(parts) == 4
        assert parts[0] == "receipts"
        assert parts[1] == "trainer-xyz"
        assert parts[2] == "student-uvw"

        # Verify filename has timestamp_uuid.ext format
        filename = parts[3]
        assert "_" in filename
        assert filename.endswith(".jpg")

        # Verify timestamp format (YYYYMMDD_HHMMSS)
        timestamp_part = filename.split("_")[0] + "_" + filename.split("_")[1]
        assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS

    def test_store_receipt_twilio_download_failure(self, service, mock_requests_get):
        """Test handling of Twilio download failure."""
        # Mock failed download
        mock_requests_get.side_effect = requests.RequestException("Network error")

        # Verify exception is raised
        with pytest.raises(requests.RequestException):
            service.store_receipt(
                trainer_id="trainer-123",
                student_id="student-456",
                media_url="https://api.twilio.com/media/ME123",
                media_type="image/jpeg",
            )

    def test_store_receipt_twilio_http_error(self, service, mock_requests_get):
        """Test handling of Twilio HTTP error response."""
        # Mock HTTP error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_requests_get.return_value = mock_response

        # Verify exception is raised
        with pytest.raises(requests.HTTPError):
            service.store_receipt(
                trainer_id="trainer-123",
                student_id="student-456",
                media_url="https://api.twilio.com/media/ME123",
                media_type="image/jpeg",
            )

    def test_store_receipt_s3_upload_failure(self, service, mock_s3_client, mock_requests_get):
        """Test handling of S3 upload failure."""
        # Mock successful download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload failure
        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket does not exist"}}, "PutObject"
        )

        # Verify exception is raised
        with pytest.raises(ClientError):
            service.store_receipt(
                trainer_id="trainer-123",
                student_id="student-456",
                media_url="https://api.twilio.com/media/ME123",
                media_type="image/jpeg",
            )

    def test_get_receipt_url_success(self, service, mock_s3_client):
        """Test successful presigned URL generation."""
        # Mock presigned URL generation
        mock_s3_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/test-bucket/receipts/trainer-123/student-456/20240115_103000_abc123.jpg?X-Amz-Signature=..."

        # Generate URL
        url = service.get_receipt_url(
            s3_key="receipts/trainer-123/student-456/20240115_103000_abc123.jpg"
        )

        # Verify presigned URL was called with correct parameters
        mock_s3_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "test-bucket",
                "Key": "receipts/trainer-123/student-456/20240115_103000_abc123.jpg",
            },
            ExpiresIn=3600,
        )

        # Verify URL is returned
        assert url.startswith("https://s3.amazonaws.com/")
        assert "X-Amz-Signature" in url

    def test_get_receipt_url_custom_expiration(self, service, mock_s3_client):
        """Test presigned URL generation with custom expiration."""
        # Mock presigned URL generation
        mock_s3_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/..."

        # Generate URL with 30 minute expiration
        service.get_receipt_url(
            s3_key="receipts/trainer-123/student-456/20240115_103000_abc123.jpg", expiration=1800
        )

        # Verify custom expiration was used
        call_kwargs = mock_s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs["ExpiresIn"] == 1800

    def test_get_receipt_url_failure(self, service, mock_s3_client):
        """Test handling of presigned URL generation failure."""
        # Mock presigned URL failure
        mock_s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Key does not exist"}}, "GetObject"
        )

        # Verify exception is raised
        with pytest.raises(ClientError):
            service.get_receipt_url(s3_key="receipts/trainer-123/student-456/nonexistent.jpg")

    def test_store_receipt_encryption_enabled(self, service, mock_s3_client, mock_requests_get):
        """Test that AES256 encryption is enabled for S3 uploads."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipt
        service.store_receipt(
            trainer_id="trainer-123",
            student_id="student-456",
            media_url="https://api.twilio.com/media/ME123",
            media_type="image/jpeg",
        )

        # Verify AES256 encryption is enabled (Requirement 20.2)
        call_kwargs = mock_s3_client.put_object.call_args[1]
        assert call_kwargs["ServerSideEncryption"] == "AES256"

    def test_store_receipt_multi_tenant_isolation(self, service, mock_s3_client, mock_requests_get):
        """Test that S3 keys provide multi-tenant isolation."""
        # Mock Twilio download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock S3 upload
        mock_s3_client.put_object = Mock()

        # Store receipts for different trainers
        service.store_receipt(
            trainer_id="trainer-aaa",
            student_id="student-111",
            media_url="https://api.twilio.com/media/ME1",
            media_type="image/jpeg",
        )

        key1 = mock_s3_client.put_object.call_args[1]["Key"]

        service.store_receipt(
            trainer_id="trainer-bbb",
            student_id="student-222",
            media_url="https://api.twilio.com/media/ME2",
            media_type="image/jpeg",
        )

        key2 = mock_s3_client.put_object.call_args[1]["Key"]

        # Verify keys are in different trainer prefixes
        assert "trainer-aaa" in key1
        assert "trainer-bbb" in key2
        assert key1 != key2

    def test_store_receipt_unexpected_error(self, service, mock_requests_get):
        """Test handling of unexpected errors during receipt storage."""
        # Mock successful download
        mock_response = Mock()
        mock_response.content = b"fake_data"
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response

        # Mock unexpected error during S3 upload (not ClientError)
        with patch.object(service, "s3_client") as mock_s3:
            mock_s3.put_object.side_effect = ValueError("Unexpected error")

            # Verify exception is raised
            with pytest.raises(ValueError):
                service.store_receipt(
                    trainer_id="trainer-123",
                    student_id="student-456",
                    media_url="https://api.twilio.com/media/ME123",
                    media_type="image/jpeg",
                )
