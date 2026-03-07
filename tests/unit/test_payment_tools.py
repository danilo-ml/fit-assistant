"""
Unit tests for payment tool functions.
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from src.tools.payment_tools import register_payment, confirm_payment, view_payments


class TestRegisterPayment:
    """Test register_payment tool function."""

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_success(self, mock_db):
        """Test successful payment registration."""
        # Setup mocks
        trainer_id = "trainer123"
        student_id = "student456"
        
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "John Trainer",
            "entity_type": "TRAINER",
        }
        
        mock_db.get_trainer_students.return_value = [
            {
                "student_id": student_id,
                "name": "Jane Student",
                "entity_type": "STUDENT",
            }
        ]
        
        mock_db.put_payment.return_value = {}

        # Execute
        result = register_payment(
            trainer_id=trainer_id,
            student_name="Jane Student",
            amount=100.00,
            payment_date="2024-01-15",
        )

        # Verify
        assert result["success"] is True
        assert "data" in result
        assert "payment_id" in result["data"]
        assert result["data"]["trainer_id"] == trainer_id
        assert result["data"]["student_id"] == student_id
        assert result["data"]["student_name"] == "Jane Student"
        assert result["data"]["amount"] == 100.00
        assert result["data"]["currency"] == "USD"
        assert result["data"]["payment_date"] == "2024-01-15"
        assert result["data"]["payment_status"] == "pending"

        # Verify DynamoDB calls
        mock_db.get_trainer.assert_called_once_with(trainer_id)
        mock_db.get_trainer_students.assert_called_once_with(trainer_id)
        mock_db.put_payment.assert_called_once()

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_with_receipt(self, mock_db):
        """Test payment registration with receipt media."""
        trainer_id = "trainer123"
        student_id = "student456"
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "name": "Jane Student"}
        ]
        mock_db.put_payment.return_value = {}

        result = register_payment(
            trainer_id=trainer_id,
            student_name="Jane Student",
            amount=150.00,
            payment_date="2024-01-16",
            receipt_s3_key="receipts/trainer123/student456/20240116_receipt.jpg",
            receipt_media_type="image/jpeg",
        )

        assert result["success"] is True
        assert result["data"]["receipt_s3_key"] == "receipts/trainer123/student456/20240116_receipt.jpg"
        assert result["data"]["receipt_media_type"] == "image/jpeg"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_with_student_id(self, mock_db):
        """Test payment registration with explicit student_id."""
        trainer_id = "trainer123"
        student_id = "student456"
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_student_link.return_value = {
            "trainer_id": trainer_id,
            "student_id": student_id,
            "status": "active",
        }
        mock_db.put_payment.return_value = {}

        result = register_payment(
            trainer_id=trainer_id,
            student_id=student_id,
            student_name="Jane Student",
            amount=200.00,
            payment_date="2024-01-17",
        )

        assert result["success"] is True
        assert result["data"]["student_id"] == student_id
        mock_db.get_trainer_student_link.assert_called_once_with(trainer_id, student_id)

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_missing_student_name(self, mock_db):
        """Test payment registration fails without student name."""
        result = register_payment(
            trainer_id="trainer123",
            student_name="",
            amount=100.00,
            payment_date="2024-01-15",
        )

        assert result["success"] is False
        assert "Student name is required" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_invalid_amount(self, mock_db):
        """Test payment registration fails with invalid amount."""
        result = register_payment(
            trainer_id="trainer123",
            student_name="Jane Student",
            amount=0,
            payment_date="2024-01-15",
        )

        assert result["success"] is False
        assert "amount must be greater than 0" in result["error"]

        result = register_payment(
            trainer_id="trainer123",
            student_name="Jane Student",
            amount=-50.00,
            payment_date="2024-01-15",
        )

        assert result["success"] is False
        assert "amount must be greater than 0" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_invalid_date_format(self, mock_db):
        """Test payment registration fails with invalid date format."""
        result = register_payment(
            trainer_id="trainer123",
            student_name="Jane Student",
            amount=100.00,
            payment_date="01/15/2024",
        )

        assert result["success"] is False
        assert "Invalid payment date format" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_trainer_not_found(self, mock_db):
        """Test payment registration fails when trainer doesn't exist."""
        mock_db.get_trainer.return_value = None

        result = register_payment(
            trainer_id="nonexistent",
            student_name="Jane Student",
            amount=100.00,
            payment_date="2024-01-15",
        )

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_student_not_found(self, mock_db):
        """Test payment registration fails when student doesn't exist."""
        mock_db.get_trainer.return_value = {"trainer_id": "trainer123"}
        mock_db.get_trainer_students.return_value = []

        result = register_payment(
            trainer_id="trainer123",
            student_name="Unknown Student",
            amount=100.00,
            payment_date="2024-01-15",
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_with_session_id(self, mock_db):
        """Test payment registration with associated session."""
        trainer_id = "trainer123"
        student_id = "student456"
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "name": "Jane Student"}
        ]
        mock_db.put_payment.return_value = {}

        result = register_payment(
            trainer_id=trainer_id,
            student_name="Jane Student",
            amount=100.00,
            payment_date="2024-01-15",
            session_id="session789",
        )

        assert result["success"] is True
        assert result["data"]["session_id"] == "session789"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_register_payment_custom_currency(self, mock_db):
        """Test payment registration with custom currency."""
        trainer_id = "trainer123"
        student_id = "student456"
        
        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_students.return_value = [
            {"student_id": student_id, "name": "Jane Student"}
        ]
        mock_db.put_payment.return_value = {}

        result = register_payment(
            trainer_id=trainer_id,
            student_name="Jane Student",
            amount=100.00,
            payment_date="2024-01-15",
            currency="EUR",
        )

        assert result["success"] is True
        assert result["data"]["currency"] == "EUR"


class TestConfirmPayment:
    """Test confirm_payment tool function."""

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_success(self, mock_db):
        """Test successful payment confirmation."""
        from src.tools.payment_tools import confirm_payment

        trainer_id = "trainer123"
        payment_id = "payment456"

        # Setup mock - payment exists with pending status
        mock_db.get_payment.return_value = {
            "PK": f"TRAINER#{trainer_id}",
            "SK": f"PAYMENT#{payment_id}",
            "entity_type": "PAYMENT",
            "payment_id": payment_id,
            "trainer_id": trainer_id,
            "student_id": "student789",
            "student_name": "Jane Student",
            "amount": 100.00,
            "currency": "USD",
            "payment_date": "2024-01-15",
            "payment_status": "pending",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }

        mock_db.put_payment.return_value = {}

        # Execute
        result = confirm_payment(
            trainer_id=trainer_id,
            payment_id=payment_id,
        )

        # Verify
        assert result["success"] is True
        assert "data" in result
        assert result["data"]["payment_id"] == payment_id
        assert result["data"]["trainer_id"] == trainer_id
        assert result["data"]["student_id"] == "student789"
        assert result["data"]["student_name"] == "Jane Student"
        assert result["data"]["amount"] == 100.00
        assert result["data"]["currency"] == "USD"
        assert result["data"]["payment_date"] == "2024-01-15"
        assert result["data"]["payment_status"] == "confirmed"
        assert "confirmed_at" in result["data"]

        # Verify confirmed_at is a valid ISO timestamp
        from datetime import datetime
        confirmed_at = datetime.fromisoformat(result["data"]["confirmed_at"])
        assert confirmed_at is not None

        # Verify DynamoDB calls
        mock_db.get_payment.assert_called_once_with(trainer_id, payment_id)
        mock_db.put_payment.assert_called_once()

        # Verify the payment was updated correctly
        updated_payment = mock_db.put_payment.call_args[0][0]
        assert updated_payment["payment_status"] == "confirmed"
        assert "confirmed_at" in updated_payment
        assert "updated_at" in updated_payment

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_with_receipt(self, mock_db):
        """Test payment confirmation includes receipt fields if present."""
        from src.tools.payment_tools import confirm_payment

        trainer_id = "trainer123"
        payment_id = "payment456"

        mock_db.get_payment.return_value = {
            "payment_id": payment_id,
            "trainer_id": trainer_id,
            "student_id": "student789",
            "student_name": "Jane Student",
            "amount": 150.00,
            "currency": "USD",
            "payment_date": "2024-01-16",
            "payment_status": "pending",
            "receipt_s3_key": "receipts/trainer123/student789/20240116_receipt.jpg",
            "receipt_media_type": "image/jpeg",
            "created_at": "2024-01-16T10:00:00",
            "updated_at": "2024-01-16T10:00:00",
        }

        mock_db.put_payment.return_value = {}

        result = confirm_payment(
            trainer_id=trainer_id,
            payment_id=payment_id,
        )

        assert result["success"] is True
        assert result["data"]["receipt_s3_key"] == "receipts/trainer123/student789/20240116_receipt.jpg"
        assert result["data"]["receipt_media_type"] == "image/jpeg"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_with_session_id(self, mock_db):
        """Test payment confirmation includes session_id if present."""
        from src.tools.payment_tools import confirm_payment

        trainer_id = "trainer123"
        payment_id = "payment456"

        mock_db.get_payment.return_value = {
            "payment_id": payment_id,
            "trainer_id": trainer_id,
            "student_id": "student789",
            "student_name": "Jane Student",
            "amount": 100.00,
            "currency": "USD",
            "payment_date": "2024-01-15",
            "payment_status": "pending",
            "session_id": "session999",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }

        mock_db.put_payment.return_value = {}

        result = confirm_payment(
            trainer_id=trainer_id,
            payment_id=payment_id,
        )

        assert result["success"] is True
        assert result["data"]["session_id"] == "session999"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_not_found(self, mock_db):
        """Test payment confirmation fails when payment doesn't exist."""
        from src.tools.payment_tools import confirm_payment

        mock_db.get_payment.return_value = None

        result = confirm_payment(
            trainer_id="trainer123",
            payment_id="nonexistent",
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_wrong_trainer(self, mock_db):
        """Test payment confirmation fails when payment belongs to different trainer."""
        from src.tools.payment_tools import confirm_payment

        mock_db.get_payment.return_value = {
            "payment_id": "payment456",
            "trainer_id": "trainer999",  # Different trainer
            "student_id": "student789",
            "student_name": "Jane Student",
            "amount": 100.00,
            "currency": "USD",
            "payment_date": "2024-01-15",
            "payment_status": "pending",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }

        result = confirm_payment(
            trainer_id="trainer123",
            payment_id="payment456",
        )

        assert result["success"] is False
        assert "does not belong to trainer" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_already_confirmed(self, mock_db):
        """Test payment confirmation fails when payment is already confirmed."""
        from src.tools.payment_tools import confirm_payment

        trainer_id = "trainer123"
        payment_id = "payment456"

        mock_db.get_payment.return_value = {
            "payment_id": payment_id,
            "trainer_id": trainer_id,
            "student_id": "student789",
            "student_name": "Jane Student",
            "amount": 100.00,
            "currency": "USD",
            "payment_date": "2024-01-15",
            "payment_status": "confirmed",  # Already confirmed
            "confirmed_at": "2024-01-16T09:00:00",
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-16T09:00:00",
        }

        result = confirm_payment(
            trainer_id=trainer_id,
            payment_id=payment_id,
        )

        assert result["success"] is False
        assert "already confirmed" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_confirm_payment_missing_payment_id(self, mock_db):
        """Test payment confirmation fails without payment_id."""
        from src.tools.payment_tools import confirm_payment

        result = confirm_payment(
            trainer_id="trainer123",
            payment_id="",
        )

        assert result["success"] is False
        assert "Payment ID is required" in result["error"]


class TestViewPayments:
    """Test view_payments tool function."""

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_success(self, mock_db):
        """Test successful payment retrieval."""
        trainer_id = "trainer123"

        # Setup mock - trainer exists
        mock_db.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "John Trainer",
        }

        # Setup mock - payments exist
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "payment_id": "payment2",
                "trainer_id": trainer_id,
                "student_id": "student2",
                "student_name": "John Student",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "confirmed_at": "2024-01-17T09:00:00Z",
                "created_at": "2024-01-16T10:00:00Z",
            },
        ]

        # Execute
        result = view_payments(trainer_id=trainer_id)

        # Verify
        assert result["success"] is True
        assert "data" in result
        assert "payments" in result["data"]
        assert len(result["data"]["payments"]) == 2

        # Verify first payment
        payment1 = result["data"]["payments"][0]
        assert payment1["payment_id"] == "payment1"
        assert payment1["student_name"] == "Jane Student"
        assert payment1["amount"] == 100.00
        assert payment1["payment_status"] == "pending"
        assert "confirmed_at" not in payment1

        # Verify second payment
        payment2 = result["data"]["payments"][1]
        assert payment2["payment_id"] == "payment2"
        assert payment2["student_name"] == "John Student"
        assert payment2["amount"] == 150.00
        assert payment2["payment_status"] == "confirmed"
        assert payment2["confirmed_at"] == "2024-01-17T09:00:00Z"

        # Verify DynamoDB calls
        mock_db.get_trainer.assert_called_once_with(trainer_id)
        mock_db.get_trainer_payments.assert_called_once_with(trainer_id)

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_empty(self, mock_db):
        """Test payment retrieval with no payments."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = []

        result = view_payments(trainer_id=trainer_id)

        assert result["success"] is True
        assert result["data"]["payments"] == []

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_filter_by_student_name(self, mock_db):
        """Test payment retrieval filtered by student name."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "payment_id": "payment2",
                "trainer_id": trainer_id,
                "student_id": "student2",
                "student_name": "John Student",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "created_at": "2024-01-16T10:00:00Z",
            },
        ]

        # Filter by student name
        result = view_payments(trainer_id=trainer_id, student_name="Jane Student")

        assert result["success"] is True
        assert len(result["data"]["payments"]) == 1
        assert result["data"]["payments"][0]["student_name"] == "Jane Student"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_filter_by_student_name_case_insensitive(self, mock_db):
        """Test payment retrieval filtered by student name is case-insensitive."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
        ]

        # Filter with different case
        result = view_payments(trainer_id=trainer_id, student_name="jane student")

        assert result["success"] is True
        assert len(result["data"]["payments"]) == 1
        assert result["data"]["payments"][0]["student_name"] == "Jane Student"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_filter_by_status_pending(self, mock_db):
        """Test payment retrieval filtered by pending status."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "payment_id": "payment2",
                "trainer_id": trainer_id,
                "student_id": "student2",
                "student_name": "John Student",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "created_at": "2024-01-16T10:00:00Z",
            },
        ]

        # Filter by pending status
        result = view_payments(trainer_id=trainer_id, status="pending")

        assert result["success"] is True
        assert len(result["data"]["payments"]) == 1
        assert result["data"]["payments"][0]["payment_status"] == "pending"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_filter_by_status_confirmed(self, mock_db):
        """Test payment retrieval filtered by confirmed status."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "payment_id": "payment2",
                "trainer_id": trainer_id,
                "student_id": "student2",
                "student_name": "John Student",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "confirmed_at": "2024-01-17T09:00:00Z",
                "created_at": "2024-01-16T10:00:00Z",
            },
        ]

        # Filter by confirmed status
        result = view_payments(trainer_id=trainer_id, status="confirmed")

        assert result["success"] is True
        assert len(result["data"]["payments"]) == 1
        assert result["data"]["payments"][0]["payment_status"] == "confirmed"
        assert "confirmed_at" in result["data"]["payments"][0]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_filter_by_both(self, mock_db):
        """Test payment retrieval filtered by both student name and status."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
            {
                "payment_id": "payment2",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 150.00,
                "currency": "USD",
                "payment_date": "2024-01-16",
                "payment_status": "confirmed",
                "confirmed_at": "2024-01-17T09:00:00Z",
                "created_at": "2024-01-16T10:00:00Z",
            },
            {
                "payment_id": "payment3",
                "trainer_id": trainer_id,
                "student_id": "student2",
                "student_name": "John Student",
                "amount": 200.00,
                "currency": "USD",
                "payment_date": "2024-01-17",
                "payment_status": "pending",
                "created_at": "2024-01-17T10:00:00Z",
            },
        ]

        # Filter by both student name and status
        result = view_payments(
            trainer_id=trainer_id, student_name="Jane Student", status="confirmed"
        )

        assert result["success"] is True
        assert len(result["data"]["payments"]) == 1
        assert result["data"]["payments"][0]["payment_id"] == "payment2"
        assert result["data"]["payments"][0]["student_name"] == "Jane Student"
        assert result["data"]["payments"][0]["payment_status"] == "confirmed"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_with_optional_fields(self, mock_db):
        """Test payment retrieval includes optional fields when present."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "confirmed",
                "receipt_s3_key": "receipts/trainer123/student1/20240115_receipt.jpg",
                "receipt_media_type": "image/jpeg",
                "session_id": "session123",
                "confirmed_at": "2024-01-16T09:00:00Z",
                "created_at": "2024-01-15T10:00:00Z",
            },
        ]

        result = view_payments(trainer_id=trainer_id)

        assert result["success"] is True
        payment = result["data"]["payments"][0]
        assert payment["receipt_s3_key"] == "receipts/trainer123/student1/20240115_receipt.jpg"
        assert payment["receipt_media_type"] == "image/jpeg"
        assert payment["session_id"] == "session123"
        assert payment["confirmed_at"] == "2024-01-16T09:00:00Z"

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_trainer_not_found(self, mock_db):
        """Test payment retrieval fails when trainer doesn't exist."""
        mock_db.get_trainer.return_value = None

        result = view_payments(trainer_id="nonexistent")

        assert result["success"] is False
        assert "Trainer not found" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_invalid_status(self, mock_db):
        """Test payment retrieval fails with invalid status."""
        trainer_id = "trainer123"

        result = view_payments(trainer_id=trainer_id, status="invalid_status")

        assert result["success"] is False
        assert "Invalid status" in result["error"]
        assert "pending" in result["error"]
        assert "confirmed" in result["error"]

    @patch("src.tools.payment_tools.dynamodb_client")
    def test_view_payments_no_matching_filters(self, mock_db):
        """Test payment retrieval returns empty list when no payments match filters."""
        trainer_id = "trainer123"

        mock_db.get_trainer.return_value = {"trainer_id": trainer_id}
        mock_db.get_trainer_payments.return_value = [
            {
                "payment_id": "payment1",
                "trainer_id": trainer_id,
                "student_id": "student1",
                "student_name": "Jane Student",
                "amount": 100.00,
                "currency": "USD",
                "payment_date": "2024-01-15",
                "payment_status": "pending",
                "created_at": "2024-01-15T10:00:00Z",
            },
        ]

        # Filter by non-existent student
        result = view_payments(trainer_id=trainer_id, student_name="Unknown Student")

        assert result["success"] is True
        assert result["data"]["payments"] == []

