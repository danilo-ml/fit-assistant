# Receipt Storage Service

## Overview

The `ReceiptStorageService` handles payment receipt media storage in S3. It downloads receipt images or PDFs from Twilio's media URLs and uploads them to S3 with proper encryption and multi-tenant isolation.

## Features

- **Download from Twilio**: Authenticates with Twilio API to download media
- **S3 Upload**: Stores media in S3 with AES256 server-side encryption
- **Multi-tenant Isolation**: Uses structured S3 keys with trainer and student IDs
- **Presigned URLs**: Generates temporary URLs for viewing receipts (1 hour expiration)
- **MIME Type Handling**: Automatically determines file extensions from content type

## S3 Key Structure

```
receipts/{trainer_id}/{student_id}/{timestamp}_{uuid}.{ext}
```

Example:
```
receipts/550e8400-e29b-41d4-a716-446655440000/660e8400-e29b-41d4-a716-446655440001/20240115_103000_abc12345.jpg
```

This structure provides:
- **Trainer isolation**: Each trainer's receipts are in separate prefixes
- **Student organization**: Receipts grouped by student within trainer
- **Uniqueness**: Timestamp + UUID prevents collisions
- **Type identification**: File extension indicates media type

## Usage

### Store Receipt

```python
from src.services.receipt_storage import ReceiptStorageService

service = ReceiptStorageService()

result = service.store_receipt(
    trainer_id='550e8400-e29b-41d4-a716-446655440000',
    student_id='660e8400-e29b-41d4-a716-446655440001',
    media_url='https://api.twilio.com/2010-04-01/Accounts/AC.../Messages/MM.../Media/ME...',
    media_type='image/jpeg'
)

print(result)
# {
#     'success': True,
#     's3_key': 'receipts/550e8400.../660e8400.../20240115_103000_abc12345.jpg',
#     's3_bucket': 'fitagent-receipts',
#     'media_type': 'image/jpeg',
#     'size_bytes': 245678
# }
```

### Generate Presigned URL

```python
# Get URL for viewing receipt (expires in 1 hour)
url = service.get_receipt_url(
    s3_key='receipts/550e8400.../660e8400.../20240115_103000_abc12345.jpg'
)

# Custom expiration (30 minutes)
url = service.get_receipt_url(
    s3_key='receipts/550e8400.../660e8400.../20240115_103000_abc12345.jpg',
    expiration=1800
)
```

## Security

### Encryption at Rest
All receipts are stored with AES256 server-side encryption:
```python
ServerSideEncryption='AES256'
```

### Twilio Authentication
Downloads from Twilio use HTTP Basic Auth with account credentials:
```python
auth=(twilio_account_sid, twilio_auth_token)
```

### Presigned URLs
Temporary URLs expire after 1 hour by default, preventing long-term unauthorized access.

## Supported Media Types

- **Images**: JPEG, PNG, GIF
- **Documents**: PDF
- **Fallback**: Binary (.bin) for unknown types

MIME type to extension mapping:
```python
{
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'application/pdf': '.pdf'
}
```

## Error Handling

### Download Failures
```python
try:
    result = service.store_receipt(...)
except requests.RequestException as e:
    # Handle Twilio download failure
    # - Network issues
    # - Invalid media URL
    # - Authentication failure
```

### Upload Failures
```python
try:
    result = service.store_receipt(...)
except ClientError as e:
    # Handle S3 upload failure
    # - Bucket doesn't exist
    # - Insufficient permissions
    # - Network issues
```

## Configuration

The service uses settings from `src/config.py`:

```python
# S3 Configuration
s3_bucket: str = "fitagent-receipts"

# AWS Configuration
aws_region: str = "us-east-1"
aws_endpoint_url: Optional[str] = None  # For LocalStack

# Twilio Configuration
twilio_account_sid: str = ""
twilio_auth_token: str = ""
```

## Local Development

For LocalStack testing:

```bash
# Set LocalStack endpoint
export AWS_ENDPOINT_URL=http://localhost:4566

# Create S3 bucket
awslocal s3 mb s3://fitagent-receipts
```

The service automatically uses LocalStack when `aws_endpoint_url` is configured.

## Integration with Payment Tools

The service is used by `payment_tools.py` when registering payments with receipts:

```python
from src.services.receipt_storage import ReceiptStorageService

# Store receipt
storage_service = ReceiptStorageService()
result = storage_service.store_receipt(
    trainer_id=trainer_id,
    student_id=student_id,
    media_url=receipt_url,
    media_type=media_type
)

# Save S3 key to payment record
payment_record = {
    'receipt_s3_key': result['s3_key'],
    'receipt_media_type': result['media_type']
}
```

## Requirements

Implements:
- **Requirement 5.2**: Store receipt media in S3 with unique key containing trainer ID, student ID, and timestamp
- **Requirement 20.2**: Encrypt all data at rest in S3 using AWS managed keys (AES256)

## Testing

Unit tests are located in `tests/unit/test_receipt_storage.py`:

```bash
# Run receipt storage tests
pytest tests/unit/test_receipt_storage.py -v

# Run with coverage
pytest tests/unit/test_receipt_storage.py --cov=src.services.receipt_storage
```
