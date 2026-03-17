"""
AI agent tool functions for student management.

This module provides tool functions that the AI agent can call to:
- Register new students
- View student information
- Update student details

All functions follow the tool function pattern:
- Accept trainer_id as first parameter
- Return dict with 'success', 'data', and optional 'error' keys
- Validate inputs before processing
- Handle errors gracefully
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any

from strands import tool

from models.entities import Student, TrainerStudentLink
from models.dynamodb_client import DynamoDBClient
from utils.validation import PhoneNumberValidator, InputSanitizer
from config import settings

# Initialize DynamoDB client
dynamodb_client = DynamoDBClient(
    table_name=settings.dynamodb_table, endpoint_url=settings.aws_endpoint_url
)


@tool
def register_student(
    trainer_id: str, name: str, phone_number: str, email: str, training_goal: str,
    payment_due_day: int = None, monthly_fee: float = None, plan_start_date: str = None,
) -> Dict[str, Any]:
    """
    Register a new student and link them to the trainer.
    
    Use this tool when the trainer wants to add a new student to their roster.
    The tool validates the phone number format, checks for duplicates, and creates
    the student record with a link to the trainer.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        name: Student's full name (e.g., "João Silva")
        phone_number: Student's phone in E.164 format (e.g., "+5511999999999")
        email: Student's email address (e.g., "joao@example.com")
        training_goal: Student's training goal (e.g., "Perder peso e ganhar massa muscular")
        payment_due_day: Day of month (1-31) when student's payment is due (e.g., 10 for day 10)
        monthly_fee: Monthly fee in BRL (e.g., 150.00). Must be positive with 2 decimal places.
        plan_start_date: Plan start month in YYYY-MM format (e.g., "2024-01")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'student_id': str,
                'name': str,
                'phone_number': str,
                'email': str,
                'training_goal': str,
                'payment_due_day': int or None
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        When trainer says: "Registrar novo aluno João Silva"
        When trainer says: "Adicionar aluna Maria com telefone +5511988887777"
        When trainer says: "Cadastrar aluno Pedro, email pedro@email.com, objetivo: ganhar massa, vencimento dia 10"
    """
    try:
        # Sanitize all string inputs
        sanitized_params = InputSanitizer.sanitize_tool_parameters(
            {
                "name": name,
                "phone_number": phone_number,
                "email": email,
                "training_goal": training_goal,
            }
        )

        name = sanitized_params["name"]
        phone_number = sanitized_params["phone_number"]
        email = sanitized_params["email"]
        training_goal = sanitized_params["training_goal"]

        # Validate payment_due_day if provided
        if payment_due_day is not None:
            if not isinstance(payment_due_day, int) or payment_due_day < 1 or payment_due_day > 31:
                return {
                    "success": False,
                    "error": "Dia de vencimento deve ser um número entre 1 e 31",
                }

        # Validate and convert monthly_fee if provided
        monthly_fee_decimal = None
        if monthly_fee is not None:
            try:
                monthly_fee_decimal = Decimal(str(monthly_fee))
            except (InvalidOperation, ValueError):
                return {"success": False, "error": "Monthly fee must be a valid number"}
            if monthly_fee_decimal <= 0:
                return {"success": False, "error": "Monthly fee must be greater than 0"}
            if monthly_fee_decimal.as_tuple().exponent != -2:
                return {"success": False, "error": "Monthly fee must have exactly 2 decimal places"}

        # Validate plan_start_date if provided
        if plan_start_date is not None:
            if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', plan_start_date):
                return {"success": False, "error": "Plan start date must be in YYYY-MM format"}

        # Validate required fields
        if not name:
            return {"success": False, "error": "Student name is required"}

        if not email:
            return {"success": False, "error": "Student email is required"}

        if not training_goal:
            return {"success": False, "error": "Training goal is required"}

        # Validate phone number E.164 format
        if not PhoneNumberValidator.validate(phone_number):
            # Try to normalize it
            normalized_phone = PhoneNumberValidator.normalize(phone_number)
            if normalized_phone:
                phone_number = normalized_phone
            else:
                return {
                    "success": False,
                    "error": f"Invalid phone number format. Please use E.164 format (e.g., +14155552671). Got: {phone_number}",
                }

        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Check if student with this phone number already exists
        existing_user = dynamodb_client.lookup_by_phone_number(phone_number)

        if existing_user and existing_user.get("entity_type") == "STUDENT":
            # Student already exists, just create the link
            student_id = existing_user["student_id"]

            # Check if link already exists
            existing_link = dynamodb_client.get_trainer_student_link(trainer_id, student_id)
            if existing_link and existing_link.get("status") == "active":
                return {
                    "success": False,
                    "error": f"Student with phone number {phone_number} is already registered with this trainer",
                }

            # Create or reactivate the link
            link = TrainerStudentLink(trainer_id=trainer_id, student_id=student_id, status="active")
            dynamodb_client.put_trainer_student_link(link.to_dynamodb())

            # Get full student details
            student_data = dynamodb_client.get_student(student_id)

            return {
                "success": True,
                "data": {
                    "student_id": student_id,
                    "name": student_data["name"],
                    "phone_number": student_data["phone_number"],
                    "email": student_data["email"],
                    "training_goal": student_data["training_goal"],
                    "payment_due_day": student_data.get("payment_due_day"),
                },
            }

        elif existing_user and existing_user.get("entity_type") == "TRAINER":
            return {
                "success": False,
                "error": f"Phone number {phone_number} is already registered as a trainer",
            }

        # Create new student entity
        student = Student(
            name=name, phone_number=phone_number, email=email, training_goal=training_goal,
            payment_due_day=payment_due_day, monthly_fee=monthly_fee_decimal,
            plan_start_date=plan_start_date,
        )

        # Save student to DynamoDB
        dynamodb_client.put_student(student.to_dynamodb())

        # Create trainer-student link
        link = TrainerStudentLink(
            trainer_id=trainer_id, student_id=student.student_id, status="active"
        )
        dynamodb_client.put_trainer_student_link(link.to_dynamodb())

        return {
            "success": True,
            "data": {
                "student_id": student.student_id,
                "name": student.name,
                "phone_number": student.phone_number,
                "email": student.email,
                "training_goal": student.training_goal,
                "payment_due_day": student.payment_due_day,
                "monthly_fee": str(student.monthly_fee) if student.monthly_fee is not None else None,
                "currency": student.currency,
                "plan_start_date": student.plan_start_date,
            },
        }

    except ValueError as e:
        # Pydantic validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to register student: {str(e)}"}


@tool
def view_students(trainer_id: str) -> Dict[str, Any]:
    """
    View all students linked to the trainer.
    
    Use this tool when the trainer wants to see their complete list of students.
    Returns all active students with their contact information and training goals.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)

    Returns:
        dict: {
            'success': bool,
            'data': {
                'students': [
                    {
                        'student_id': str,
                        'name': str,
                        'phone_number': str,
                        'email': str,
                        'training_goal': str,
                        'created_at': str
                    },
                    ...
                ]
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        When trainer says: "Ver meus alunos"
        When trainer says: "Listar todos os alunos"
        When trainer says: "Quem são meus alunos?"
        When trainer says: "Mostrar lista de alunos"
    """
    try:
        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Query all trainer-student links
        links = dynamodb_client.get_trainer_students(trainer_id)

        # Extract student IDs from links and fetch full student details
        students = []
        for link in links:
            # Skip inactive links
            if link.get("status") != "active":
                continue

            student_id = link.get("student_id")
            if not student_id:
                continue

            # Fetch full student details
            student_data = dynamodb_client.get_student(student_id)
            if student_data:
                students.append(
                    {
                        "student_id": student_data["student_id"],
                        "name": student_data["name"],
                        "phone_number": student_data["phone_number"],
                        "email": student_data["email"],
                        "training_goal": student_data["training_goal"],
                        "payment_due_day": student_data.get("payment_due_day"),
                        "created_at": student_data.get("created_at", ""),
                    }
                )

        return {"success": True, "data": {"students": students}}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to retrieve students: {str(e)}"}


@tool
def update_student(
    trainer_id: str,
    student_id: str,
    name: str = None,
    email: str = None,
    phone_number: str = None,
    training_goal: str = None,
    payment_due_day: int = None,
    monthly_fee: float = None,
    plan_start_date: str = None,
) -> Dict[str, Any]:
    """
    Update student information.
    
    Use this tool when the trainer wants to modify a student's details such as
    name, email, phone number, training goal, or payment due day. At least one field
    must be provided for update. Only updates the fields that are provided.

    Args:
        trainer_id: Trainer identifier (injected automatically by the service)
        student_id: Student identifier (required - the ID of the student to update)
        name: Updated student name (optional, e.g., "João Silva Santos")
        email: Updated student email (optional, e.g., "joao.novo@example.com")
        phone_number: Updated phone in E.164 format (optional, e.g., "+5511988887777")
        training_goal: Updated training goal (optional, e.g., "Perder 10kg em 3 meses")
        payment_due_day: Day of month (1-31) when student's payment is due (optional, e.g., 10)
        monthly_fee: Monthly fee in BRL (optional, e.g., 150.00). Must be positive with 2 decimal places.
        plan_start_date: Plan start month in YYYY-MM format (optional, e.g., "2024-01")

    Returns:
        dict: {
            'success': bool,
            'data': {
                'student_id': str,
                'name': str,
                'phone_number': str,
                'email': str,
                'training_goal': str,
                'payment_due_day': int or None,
                'updated_at': str
            },
            'error': str (optional, only present if success=False)
        }

    Examples:
        When trainer says: "Atualizar objetivo do aluno João para perder peso"
        When trainer says: "Mudar email do aluno abc123 para novo@email.com"
        When trainer says: "Alterar telefone da Maria para +5511999998888"
        When trainer says: "Mudar vencimento do aluno para dia 15"
    """
    try:
        # Verify trainer exists
        trainer = dynamodb_client.get_trainer(trainer_id)
        if not trainer:
            return {"success": False, "error": f"Trainer not found: {trainer_id}"}

        # Verify student exists
        student_data = dynamodb_client.get_student(student_id)
        if not student_data:
            return {"success": False, "error": f"Student not found: {student_id}"}

        # Verify trainer-student link exists and is active
        link = dynamodb_client.get_trainer_student_link(trainer_id, student_id)
        if not link or link.get("status") != "active":
            return {
                "success": False,
                "error": f"Student {student_id} is not linked to trainer {trainer_id}",
            }

        # Check if at least one field is provided for update
        if not any([name, email, phone_number, training_goal, payment_due_day, monthly_fee, plan_start_date]):
            return {
                "success": False,
                "error": "At least one field must be provided for update",
            }

        # Validate payment_due_day if provided
        if payment_due_day is not None:
            if not isinstance(payment_due_day, int) or payment_due_day < 1 or payment_due_day > 31:
                return {
                    "success": False,
                    "error": "Dia de vencimento deve ser um número entre 1 e 31",
                }

        # Validate and convert monthly_fee if provided
        monthly_fee_decimal = None
        if monthly_fee is not None:
            try:
                monthly_fee_decimal = Decimal(str(monthly_fee))
            except (InvalidOperation, ValueError):
                return {"success": False, "error": "Monthly fee must be a valid number"}
            if monthly_fee_decimal <= 0:
                return {"success": False, "error": "Monthly fee must be greater than 0"}
            if monthly_fee_decimal.as_tuple().exponent != -2:
                return {"success": False, "error": "Monthly fee must have exactly 2 decimal places"}

        # Validate plan_start_date if provided
        if plan_start_date is not None:
            if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', plan_start_date):
                return {"success": False, "error": "Plan start date must be in YYYY-MM format"}

        # Sanitize inputs if provided
        update_params = {}
        if name is not None:
            update_params["name"] = name
        if email is not None:
            update_params["email"] = email
        if phone_number is not None:
            update_params["phone_number"] = phone_number
        if training_goal is not None:
            update_params["training_goal"] = training_goal

        sanitized_params = InputSanitizer.sanitize_tool_parameters(update_params)

        # Validate phone number if provided
        if "phone_number" in sanitized_params:
            new_phone = sanitized_params["phone_number"]
            if not PhoneNumberValidator.validate(new_phone):
                # Try to normalize it
                normalized_phone = PhoneNumberValidator.normalize(new_phone)
                if normalized_phone:
                    sanitized_params["phone_number"] = normalized_phone
                else:
                    return {
                        "success": False,
                        "error": f"Invalid phone number format. Please use E.164 format (e.g., +14155552671). Got: {new_phone}",
                    }

            # Check if new phone number is already used by another user
            existing_user = dynamodb_client.lookup_by_phone_number(
                sanitized_params["phone_number"]
            )
            if existing_user and existing_user.get("student_id") != student_id:
                return {
                    "success": False,
                    "error": f"Phone number {sanitized_params['phone_number']} is already registered to another user",
                }

        # Create updated student entity
        from datetime import datetime

        updated_student = Student(
            student_id=student_data["student_id"],
            name=sanitized_params.get("name", student_data["name"]),
            email=sanitized_params.get("email", student_data["email"]),
            phone_number=sanitized_params.get("phone_number", student_data["phone_number"]),
            training_goal=sanitized_params.get("training_goal", student_data["training_goal"]),
            payment_due_day=payment_due_day if payment_due_day is not None else student_data.get("payment_due_day"),
            monthly_fee=monthly_fee_decimal if monthly_fee_decimal is not None else (
                Decimal(str(student_data["monthly_fee"])) if student_data.get("monthly_fee") is not None else None
            ),
            currency=student_data.get("currency", "BRL"),
            plan_start_date=plan_start_date if plan_start_date is not None else student_data.get("plan_start_date"),
            created_at=datetime.fromisoformat(student_data["created_at"]),
            updated_at=datetime.utcnow(),
        )

        # Save updated student to DynamoDB
        dynamodb_client.put_student(updated_student.to_dynamodb())

        return {
            "success": True,
            "data": {
                "student_id": updated_student.student_id,
                "name": updated_student.name,
                "phone_number": updated_student.phone_number,
                "email": updated_student.email,
                "training_goal": updated_student.training_goal,
                "payment_due_day": updated_student.payment_due_day,
                "monthly_fee": str(updated_student.monthly_fee) if updated_student.monthly_fee is not None else None,
                "currency": updated_student.currency,
                "plan_start_date": updated_student.plan_start_date,
                "updated_at": updated_student.updated_at.isoformat(),
            },
        }

    except ValueError as e:
        # Pydantic validation errors
        return {"success": False, "error": f"Validation error: {str(e)}"}

    except Exception as e:
        # Unexpected errors
        return {"success": False, "error": f"Failed to update student: {str(e)}"}
