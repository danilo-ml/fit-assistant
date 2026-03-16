"""
Session Confirmation Lambda Handler.

This handler is triggered by EventBridge every 5 minutes to:
1. Find sessions that ended 1 hour ago
2. Send confirmation requests to trainers via WhatsApp
3. Update session status to pending_confirmation

The confirmation flow:
- Session ends at time T
- At T+1 hour, send confirmation request to trainer
- Trainer replies YES (completed) or NO (missed)
- Update session confirmation_status accordingly

Validates: Requirements 7.1.1, 7.1.2, 7.1.3, 7.1.7, 7.1.8
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

import boto3
from boto3.dynamodb.conditions import Attr

from models.dynamodb_client import DynamoDBClient
from models.entities import Session
from services.twilio_client import TwilioClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


def lambda_handler(event, context):
    """
    EventBridge scheduled handler for session confirmation requests.
    
    Triggered every 5 minutes to check for sessions that ended 1 hour ago
    and send confirmation requests to students.
    
    Args:
        event: EventBridge scheduled event (cron: */5 * * * ? *)
        context: Lambda context
    
    Returns:
        dict: {'statusCode': int, 'body': str}
    """
    try:
        logger.info("Session confirmation handler started")
        
        # Initialize clients
        db_client = DynamoDBClient()
        twilio_client = TwilioClient()
        
        # Calculate time window: sessions that ended 1 hour ago
        now = datetime.utcnow()
        check_time_start = now - timedelta(hours=1, minutes=5)  # 1h5m ago
        check_time_end = now - timedelta(hours=1)  # 1h ago
        
        # Query sessions needing confirmation
        sessions = query_sessions_for_confirmation(
            db_client=db_client,
            start_time=check_time_start,
            end_time=check_time_end,
        )
        
        logger.info(
            "Found sessions for confirmation",
            count=len(sessions),
            time_window=f"{check_time_start.isoformat()} to {check_time_end.isoformat()}",
        )
        
        # Send confirmation requests
        sent_count = 0
        failed_count = 0
        
        for session in sessions:
            try:
                send_confirmation_request(
                    session=session,
                    twilio_client=twilio_client,
                    db_client=db_client,
                )
                sent_count += 1
            except Exception as e:
                logger.error(
                    "Failed to send confirmation request",
                    session_id=session.session_id,
                    error=str(e),
                )
                failed_count += 1
        
        logger.info(
            "Session confirmation handler completed",
            sent=sent_count,
            failed=failed_count,
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'sent': sent_count,
                'failed': failed_count,
            })
        }
    
    except Exception as e:
        logger.error(
            "Session confirmation handler error",
            error=str(e),
        )
        raise


def query_sessions_for_confirmation(
    db_client: DynamoDBClient,
    start_time: datetime,
    end_time: datetime,
) -> List[Session]:
    """
    Query sessions that need confirmation requests.
    
    Finds sessions where:
    - session_datetime + duration is between start_time and end_time
    - confirmation_status = "scheduled"
    - status != "cancelled"
    
    Args:
        db_client: DynamoDB client
        start_time: Start of time window
        end_time: End of time window
    
    Returns:
        List of Session objects needing confirmation
    """
    sessions = []
    
    # Scan table for sessions (in production, optimize with GSI)
    # Filter: confirmation_status = "scheduled" AND status != "cancelled"
    response = db_client.table.scan(
        FilterExpression=Attr('entity_type').eq('SESSION') &
                        Attr('confirmation_status').eq('scheduled') &
                        Attr('status').ne('cancelled')
    )
    
    for item in response.get('Items', []):
        try:
            session = Session.from_dynamodb(item)
            
            # Calculate session end time
            session_end = session.session_datetime + timedelta(
                minutes=session.duration_minutes
            )
            
            # Check if session ended in the time window
            if start_time <= session_end <= end_time:
                sessions.append(session)
        except Exception as e:
            logger.warning(
                "Failed to parse session",
                item=item,
                error=str(e),
            )
    
    return sessions


def send_confirmation_request(
    session: Session,
    twilio_client: TwilioClient,
    db_client: DynamoDBClient,
) -> None:
    """
    Send confirmation request to trainer and update session status.
    
    Args:
        session: Session object
        twilio_client: Twilio client
        db_client: DynamoDB client
    """
    # Get student name from session (already stored in session entity)
    student_name = session.student_name or 'aluno'
    
    # Get trainer phone number
    trainer_item = db_client.get_item(
        pk=f"TRAINER#{session.trainer_id}",
        sk="METADATA",
    )
    
    if not trainer_item:
        logger.error(
            "Trainer not found for confirmation",
            session_id=session.session_id,
            trainer_id=session.trainer_id,
        )
        return
    
    trainer_phone = trainer_item.get('phone_number')
    
    # Format confirmation message
    message = format_confirmation_message(
        student_name=student_name,
        session_datetime=session.session_datetime,
        duration_minutes=session.duration_minutes,
    )
    
    # Send via Twilio to trainer
    twilio_client.send_message(
        to=trainer_phone,
        body=message,
    )
    
    # Update session status
    now = datetime.utcnow()
    db_client.update_item(
        pk=f"TRAINER#{session.trainer_id}",
        sk=f"SESSION#{session.session_id}",
        updates={
            'confirmation_status': 'pending_confirmation',
            'confirmation_requested_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'confirmation_status_datetime': f'pending_confirmation#{session.session_datetime.isoformat()}',
        }
    )
    
    logger.info(
        "Confirmation request sent to trainer",
        session_id=session.session_id,
        trainer_phone=trainer_phone,
    )


def format_confirmation_message(
    student_name: str,
    session_datetime: datetime,
    duration_minutes: int,
) -> str:
    """
    Format confirmation request message for trainer.
    
    Args:
        student_name: Student's name
        session_datetime: Session date and time
        duration_minutes: Session duration
    
    Returns:
        Formatted message string
    """
    date_str = session_datetime.strftime("%d/%m/%Y")
    time_str = session_datetime.strftime("%H:%M")
    
    return (
        f"📋 Confirmação de sessão\n\n"
        f"A sessão de {duration_minutes} minutos com {student_name} "
        f"em {date_str} às {time_str} aconteceu?\n\n"
        f"Responda SIM ou NÃO."
    )
