"""
AI agent tool functions for payment management.

This module provides tool functions that the AI agent can call to:
- Register payment records
- Confirm payments
- View payment information

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

from typing import Dict, Any
from datetime import datetime

from strands import tool

from models.entities import Payment
from models.dynamodb_client import DynamoDBClient
from utils.validation import InputSanitizer
from config import settings

# Initialize DynamoDB client
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)


@tool
def register_payment(
    trainer_id: str,
    student_name: str,
    amount: float,
    payment_date: str,
    student_id: str = None,
    receipt_s3_key: str = None,
    receipt_media_type: str = None,
    session_id: str = None,
    currency: str = "USD",
) -> Dict[str, Any]:
    """
    Register a payment record with status="pending".
    
    Use this tool when the trainer wants to record a payment received from a student.
    The tool validates the payment details, links it to the student, and stores the
    payment record with pending status. Optionally supports receipt media storage.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        student_name: Student name (required)
        amount: Payment amount (required, must be > 0)
        payment_date: Payment date in ISO format YYYY-MM-DD (required)
        student_id: Student identifier (optional, will be looked up if not provided)
        receipt_s3_key: S3 key for receipt media (optional)
        receipt_media_type: MIME type of receipt media (optional)
        session_id: Associated session ID (optional)
        currency: Currency code (default: USD)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'payment_id': str,
                'trainer_id': str,
                'student_id': str,
                'student_name': str,
                'amount': float,
                'currency': str,
                'payment_date': str,
                'payment_status': str,
                'receipt_s3_key': str (optional),
                'receipt_media_type': str (optional),
                'session_id': str (optional)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> register_payment(
        ...     trainer_id='abc123',
        ...     student_name='John Doe',
        ...     amount=100.00,
        ...     payment_date='2024-01-15'
        ... )
        {
            'success': True,
            'data': {
                'payment_id': 'def456',
                'trainer_id': 'abc123',
                'student_id': 'student789',
                'student_name': 'John Doe',
                'amount': 100.00,
                'currency': 'USD',
                'payment_date': '2024-01-15',
                'payment_status': 'pending'
            }
        }

        >>> register_payment(
        ...     trainer_id='abc123',
        ...     student_name='Jane Smith',
        ...     amount=150.00,
        ...     payment_date='2024-01-16',
        ...     receipt_s3_key='receipts/abc123/student456/20240116_receipt.jpg',
        ...     receipt_media_type='image/jpeg'
        ... )
        {
            'success': True,
            'data': {
                'payment_id': 'ghi789',
                'trainer_id': 'abc123',
                'student_id': 'student456',
                'student_name': 'Jane Smith',
                'amount': 150.00,
                'currency': 'USD',
                'payment_date': '2024-01-16',
                'payment_status': 'pending',
                'receipt_s3_key': 'receipts/abc123/student456/20240116_receipt.jpg',
                'receipt_media_type': 'image/jpeg'
            }
        }

    Validates: Requirements 5.3, 5.7
    """
    try:
        # Sanitize all string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "student_name": student_name,
                "payment_date": payment_date,
                "currency": currency,
            }
        )

        student_name = sanitized_params["student_name"]
        payment_date = sanitized_params["payment_date"]
        currency = sanitized_params["currency"]

        # Sanitize optional string fields
        if receipt_s3_key:
            receipt_s3_key = InputSanitizer.sanitize_string(receipt_s3_key)
        if receipt_media_type:
            receipt_media_type = InputSanitizer.sanitize_string(receipt_media_type)
        if session_id:
            session_id = InputSanitizer.sanitize_string(session_id)
        if student_id:
            student_id = InputSanitizer.sanitize_string(student_id)

        # Validate required fields
        if not student_name:
            return {"success": False, "error": "Student name is required"}

        if not payment_date:
            return {"success": False, "error": "Payment date is required"}

        # Validate amount
        if amount <= 0:
            return {
                "success": False,
                "error": f"Payment amount must be greater than 0. Got: {amount}",
            }

        # Validate payment_date format (YYYY-MM-DD)
        try:
            datetime.strptime(payment_date, "%Y-%m-%d")
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid payment date format. Expected YYYY-MM-DD, got: {payment_date}",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # If student_id not provided, try to find student by name
        if not student_id:
            # Get all students for this trainer
            trainer_students = dynamodb_client.get_trainer_students(trainer_id)

            # Find student by name (case-insensitive match)
            matching_students = [
                s for s in trainer_students if s.get("name", "").lower() == student_name.lower()
            ]

            if not matching_students:
                return {
                    "success": False,
                    "error": f"Student '{student_name}' not found. Please register the student first or provide student_id.",
                }

            if len(matching_students) > 1:
                return {
                    "success": False,
                    "error": f"Multiple students found with name '{student_name}'. Please provide student_id to disambiguate.",
                }

            student_id = matching_students[0]["student_id"]
        else:
            # Verify student exists and is linked to trainer
            link = dynamodb_client.get_trainer_student_link(trainer_id, student_id)
            if not link or link.get("status") != "active":
                return {
                    "success": False,
                    "error": f"Student {student_id} is not linked to trainer {trainer_id}",
                }

        # Create payment entity with status="pending"
        payment = Payment(
            trainer_id=trainer_id,
            student_id=student_id,
            student_name=student_name,
            amount=amount,
            currency=currency,
            payment_date=payment_date,
            payment_status="pending",
            receipt_s3_key=receipt_s3_key,
            receipt_media_type=receipt_media_type,
            session_id=session_id,
        )

        # Save payment to DynamoDB
        dynamodb_client.put_payment(payment.to_dynamodb())

        # Build response data
        response_data = {
            "payment_id": payment.payment_id,
            "trainer_id": payment.trainer_id,
            "student_id": payment.student_id,
            "student_name": payment.student_name,
            "amount": payment.amount,
            "currency": payment.currency,
            "payment_date": payment.payment_date,
            "payment_status": payment.payment_status,
        }

        # Add optional fields if present
        if payment.receipt_s3_key:
            response_data["receipt_s3_key"] = payment.receipt_s3_key
        if payment.receipt_media_type:
            response_data["receipt_media_type"] = payment.receipt_media_type
        if payment.session_id:
            response_data["session_id"] = payment.session_id

        return {"success": True, "data": response_data}

    except ValueError as e:
        # Pydantic validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to register payment: {str(e)}"}


def confirm_payment(
    trainer_id: str,
    payment_id: str,
) -> Dict[str, Any]:
    """
    Confirm a payment by updating status to "confirmed" and recording timestamp.

    This tool:
    1. Validates that the payment exists
    2. Validates that the payment belongs to the trainer
    3. Updates payment status from "pending" to "confirmed"
    4. Records the confirmation timestamp
    5. Returns updated payment information

    Args:
        trainer_id: Trainer identifier (required)
        payment_id: Payment identifier (required)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'payment_id': str,
                'trainer_id': str,
                'student_id': str,
                'student_name': str,
                'amount': float,
                'currency': str,
                'payment_date': str,
                'payment_status': str,
                'confirmed_at': str,
                'receipt_s3_key': str (optional),
                'receipt_media_type': str (optional),
                'session_id': str (optional)
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> confirm_payment(
        ...     trainer_id='abc123',
        ...     payment_id='def456'
        ... )
        {
            'success': True,
            'data': {
                'payment_id': 'def456',
                'trainer_id': 'abc123',
                'student_id': 'student789',
                'student_name': 'John Doe',
                'amount': 100.00,
                'currency': 'USD',
                'payment_date': '2024-01-15',
                'payment_status': 'confirmed',
                'confirmed_at': '2024-01-16T09:00:00.123456'
            }
        }

    Validates: Requirements 5.4
    """
    try:
        # Sanitize inputs
        payment_id = InputSanitizer.sanitize_string(payment_id)

        # Validate required fields
        if not payment_id:
            return {"success": False, "error": "Payment ID is required"}

        # Get payment from DynamoDB
        payment_item = dynamodb_client.get_payment(trainer_id, payment_id)

        if not payment_item:
            return {
                "success": False,
                "error": f"Payment not found: {payment_id}",
            }

        # Verify payment belongs to trainer
        if payment_item.get("trainer_id") != trainer_id:
            return {
                "success": False,
                "error": f"Payment {payment_id} does not belong to trainer {trainer_id}",
            }

        # Check if already confirmed
        if payment_item.get("payment_status") == "confirmed":
            return {
                "success": False,
                "error": f"Payment {payment_id} is already confirmed",
            }

        # Update payment status to "confirmed" and record timestamp
        confirmation_timestamp = datetime.utcnow()
        payment_item["payment_status"] = "confirmed"
        payment_item["confirmed_at"] = confirmation_timestamp.isoformat()
        payment_item["updated_at"] = confirmation_timestamp.isoformat()

        # Save updated payment to DynamoDB
        dynamodb_client.put_payment(payment_item)

        # Build response data
        response_data = {
            "payment_id": payment_item["payment_id"],
            "trainer_id": payment_item["trainer_id"],
            "student_id": payment_item["student_id"],
            "student_name": payment_item["student_name"],
            "amount": payment_item["amount"],
            "currency": payment_item["currency"],
            "payment_date": payment_item["payment_date"],
            "payment_status": payment_item["payment_status"],
            "confirmed_at": payment_item["confirmed_at"],
        }

        # Add optional fields if present
        if payment_item.get("receipt_s3_key"):
            response_data["receipt_s3_key"] = payment_item["receipt_s3_key"]
        if payment_item.get("receipt_media_type"):
            response_data["receipt_media_type"] = payment_item["receipt_media_type"]
        if payment_item.get("session_id"):
            response_data["session_id"] = payment_item["session_id"]

        return {"success": True, "data": response_data}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to confirm payment: {str(e)}"}


@tool
def view_payments(
    trainer_id: str,
    student_name: str = None,
    status: str = None,
) -> Dict[str, Any]:
    """
    View all payments for a trainer with optional filtering.
    
    Use this tool when the trainer wants to see payment records. The tool can filter
    by student name or payment status (pending/confirmed) and returns a list of all
    matching payments with their details.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        student_name: Filter by student name (optional, case-insensitive)
        status: Filter by payment status (optional, "pending" or "confirmed")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'payments': [
                    {
                        'payment_id': str,
                        'trainer_id': str,
                        'student_id': str,
                        'student_name': str,
                        'amount': float,
                        'currency': str,
                        'payment_date': str,
                        'payment_status': str,
                        'receipt_s3_key': str (optional),
                        'receipt_media_type': str (optional),
                        'session_id': str (optional),
                        'confirmed_at': str (optional),
                        'created_at': str
                    },
                    ...
                ]
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        >>> view_payments(trainer_id='abc123')
        {
            'success': True,
            'data': {
                'payments': [
                    {
                        'payment_id': 'def456',
                        'trainer_id': 'abc123',
                        'student_id': 'student789',
                        'student_name': 'John Doe',
                        'amount': 100.00,
                        'currency': 'USD',
                        'payment_date': '2024-01-15',
                        'payment_status': 'pending',
                        'created_at': '2024-01-15T10:30:00Z'
                    }
                ]
            }
        }

        >>> view_payments(trainer_id='abc123', student_name='John Doe')
        {
            'success': True,
            'data': {
                'payments': [
                    {
                        'payment_id': 'def456',
                        'trainer_id': 'abc123',
                        'student_id': 'student789',
                        'student_name': 'John Doe',
                        'amount': 100.00,
                        'currency': 'USD',
                        'payment_date': '2024-01-15',
                        'payment_status': 'pending',
                        'created_at': '2024-01-15T10:30:00Z'
                    }
                ]
            }
        }

        >>> view_payments(trainer_id='abc123', status='confirmed')
        {
            'success': True,
            'data': {
                'payments': [
                    {
                        'payment_id': 'ghi789',
                        'trainer_id': 'abc123',
                        'student_id': 'student456',
                        'student_name': 'Jane Smith',
                        'amount': 150.00,
                        'currency': 'USD',
                        'payment_date': '2024-01-16',
                        'payment_status': 'confirmed',
                        'confirmed_at': '2024-01-17T09:00:00Z',
                        'created_at': '2024-01-16T10:30:00Z'
                    }
                ]
            }
        }

    Validates: Requirements 5.5
    """
    try:
        # Sanitize optional inputs
        if student_name:
            student_name = InputSanitizer.sanitize_string(student_name)
        if status:
            status = InputSanitizer.sanitize_string(status)

        # Validate status if provided
        if status and status not in ["pending", "confirmed"]:
            return {
                "success": False,
                "error": f"Invalid status. Must be 'pending' or 'confirmed'. Got: {status}",
            }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Query all payments for the trainer
        all_payments = dynamodb_client.get_trainer_payments(trainer_id)

        # Apply filters
        filtered_payments = []
        for payment in all_payments:
            # Filter by status if provided
            if status and payment.get("payment_status") != status:
                continue

            # Filter by student_name if provided (case-insensitive)
            if student_name and payment.get("student_name", "").lower() != student_name.lower():
                continue

            # Build payment data
            payment_data = {
                "payment_id": payment["payment_id"],
                "trainer_id": payment["trainer_id"],
                "student_id": payment["student_id"],
                "student_name": payment["student_name"],
                "amount": payment["amount"],
                "currency": payment["currency"],
                "payment_date": payment["payment_date"],
                "payment_status": payment["payment_status"],
                "created_at": payment.get("created_at", ""),
            }

            # Add optional fields if present
            if payment.get("receipt_s3_key"):
                payment_data["receipt_s3_key"] = payment["receipt_s3_key"]
            if payment.get("receipt_media_type"):
                payment_data["receipt_media_type"] = payment["receipt_media_type"]
            if payment.get("session_id"):
                payment_data["session_id"] = payment["session_id"]
            if payment.get("confirmed_at"):
                payment_data["confirmed_at"] = payment["confirmed_at"]

            filtered_payments.append(payment_data)

        return {"success": True, "data": {"payments": filtered_payments}}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to retrieve payments: {str(e)}"}
