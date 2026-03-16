"""
Payment reminder Lambda function triggered daily by EventBridge.

This handler runs daily and:
1. Scans all active students with payment_due_day set
2. Sends reminders 3 days before due date and on the due date
3. Messages are sent in PT-BR via WhatsApp

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict

from models.dynamodb_client import DynamoDBClient
from services.twilio_client import TwilioClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)

# Initialize services
dynamodb_client = DynamoDBClient()
twilio_client = TwilioClient()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for sending payment reminders.

    Triggered daily by EventBridge. Checks which students have
    payment_due_day matching today (due date) or today + 3 days
    (advance reminder), and sends WhatsApp reminders.
    """
    logger.info(
        "Payment reminder handler invoked",
        event_time=event.get("time"),
    )

    today = datetime.utcnow().date()
    today_day = today.day
    advance_day = (today + timedelta(days=3)).day
    advance_month_rolls = (today + timedelta(days=3)).month != today.month

    reminders_sent = 0
    reminders_failed = 0

    try:
        # Get all active trainer-student links
        students_by_trainer = _get_all_active_students()

        for trainer_id, students in students_by_trainer.items():
            trainer = dynamodb_client.get_trainer(trainer_id)
            if not trainer:
                continue

            trainer_name = trainer.get("name", "Seu personal")
            business_name = trainer.get("business_name", "")

            for student_info in students:
                due_day = student_info.get("payment_due_day")
                if due_day is None:
                    continue

                student_name = student_info.get("name", "Aluno")
                student_phone = student_info.get("phone_number")
                if not student_phone:
                    continue

                is_due_today = (today_day == due_day)
                is_advance = (advance_day == due_day and not advance_month_rolls) or \
                             (advance_month_rolls and advance_day == due_day)

                if not is_due_today and not is_advance:
                    continue

                try:
                    reminder_type = "due_today" if is_due_today else "advance"
                    _send_reminder(
                        student_phone=student_phone,
                        student_name=student_name,
                        trainer_name=trainer_name,
                        business_name=business_name,
                        due_day=due_day,
                        reminder_type=reminder_type,
                    )
                    reminders_sent += 1
                    logger.info(
                        "Payment reminder sent",
                        student_phone=student_phone,
                        reminder_type=reminder_type,
                        due_day=due_day,
                    )
                except Exception as e:
                    reminders_failed += 1
                    logger.error(
                        "Failed to send payment reminder",
                        student_phone=student_phone,
                        error=str(e),
                    )

        logger.info(
            "Payment reminder processing completed",
            reminders_sent=reminders_sent,
            reminders_failed=reminders_failed,
        )

        return {
            "statusCode": 200,
            "body": {
                "reminders_sent": reminders_sent,
                "reminders_failed": reminders_failed,
            },
        }

    except Exception as e:
        logger.error(
            "Payment reminder handler failed",
            error=str(e),
        )
        raise


def _get_all_active_students() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get all active students grouped by trainer_id.

    Scans trainer-student links and fetches student details
    including payment_due_day.

    Returns:
        Dict mapping trainer_id -> list of student dicts
    """
    from boto3.dynamodb.conditions import Attr

    grouped = defaultdict(list)

    try:
        response = dynamodb_client.table.scan(
            FilterExpression=Attr("entity_type").eq("TRAINER_STUDENT_LINK")
            & Attr("status").eq("active")
        )
        links = response.get("Items", [])

        while "LastEvaluatedKey" in response:
            response = dynamodb_client.table.scan(
                FilterExpression=Attr("entity_type").eq("TRAINER_STUDENT_LINK")
                & Attr("status").eq("active"),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            links.extend(response.get("Items", []))

        for link in links:
            trainer_id = link.get("trainer_id")
            student_id = link.get("student_id")
            if not trainer_id or not student_id:
                continue

            student = dynamodb_client.get_student(student_id)
            if student:
                grouped[trainer_id].append(student)

    except Exception as e:
        logger.error("Failed to get active students", error=str(e))

    return dict(grouped)


def _send_reminder(
    student_phone: str,
    student_name: str,
    trainer_name: str,
    business_name: str,
    due_day: int,
    reminder_type: str,
) -> None:
    """
    Send payment reminder to student via WhatsApp in PT-BR.

    Args:
        student_phone: Student's phone number
        student_name: Student's name
        trainer_name: Trainer's name
        business_name: Trainer's business name
        due_day: Day of month payment is due
        reminder_type: "advance" (3 days before) or "due_today"
    """
    if reminder_type == "advance":
        message = (
            f"💰 Lembrete de Pagamento\n\n"
            f"Olá {student_name}!\n\n"
            f"Passando para lembrar que o vencimento da sua mensalidade "
            f"com {trainer_name}"
        )
        if business_name:
            message += f" ({business_name})"
        message += (
            f" é no dia {due_day}.\n\n"
            f"Quando efetuar o pagamento, envie o comprovante "
            f"(foto do Pix, transferência ou recibo) aqui neste chat.\n\n"
            f"Obrigado! 🙏"
        )
    else:
        message = (
            f"💰 Vencimento Hoje\n\n"
            f"Olá {student_name}!\n\n"
            f"Hoje é o dia do vencimento da sua mensalidade "
            f"com {trainer_name}"
        )
        if business_name:
            message += f" ({business_name})"
        message += (
            f".\n\n"
            f"Quando efetuar o pagamento, envie o comprovante "
            f"(foto do Pix, transferência ou recibo) aqui neste chat.\n\n"
            f"Obrigado! 🙏"
        )

    twilio_client.send_message(to=student_phone, body=message)
