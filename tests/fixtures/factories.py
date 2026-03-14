"""
Entity factories for creating test data with sensible defaults.

These factories use the builder pattern to create valid test entities
with UUID4 IDs and sensible defaults, making test setup easier and more readable.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import uuid4
import time

from src.models.entities import (
    Trainer,
    Student,
    TrainerStudentLink,
    Session,
    Payment,
    ConversationState,
    MessageHistoryEntry,
    TrainerConfig,
    CalendarConfig,
    Notification,
    NotificationRecipient,
    Reminder,
    MenuContext
)


class TrainerFactory:
    """Factory for creating Trainer test entities."""
    
    @staticmethod
    def create(
        trainer_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        business_name: Optional[str] = None,
        **kwargs
    ) -> Trainer:
        """
        Create a Trainer with defaults.
        
        Args:
            trainer_id: Trainer ID (default: random UUID4 hex)
            phone_number: Phone number in E.164 format (default: +5511999999XXX)
            name: Trainer name (default: "Test Trainer")
            email: Email address (default: "trainer@test.com")
            business_name: Business name (default: "Test Fitness")
            **kwargs: Additional fields to override
        
        Returns:
            Trainer instance with sensible defaults
        """
        if trainer_id is None:
            trainer_id = uuid4().hex
        
        if phone_number is None:
            # Generate unique phone number using timestamp
            suffix = str(int(time.time() * 1000))[-9:]
            phone_number = f"+5511{suffix}"
        
        return Trainer(
            trainer_id=trainer_id,
            phone_number=phone_number,
            name=name or "Test Trainer",
            email=email or f"trainer_{trainer_id[:8]}@test.com",
            business_name=business_name or "Test Fitness",
            **kwargs
        )


class StudentFactory:
    """Factory for creating Student test entities."""
    
    @staticmethod
    def create(
        student_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        training_goal: Optional[str] = None,
        **kwargs
    ) -> Student:
        """
        Create a Student with defaults.
        
        Args:
            student_id: Student ID (default: random UUID4 hex)
            phone_number: Phone number in E.164 format (default: +5511888888XXX)
            name: Student name (default: "Test Student")
            email: Email address (default: "student@test.com")
            training_goal: Training goal (default: "Perder peso")
            **kwargs: Additional fields to override
        
        Returns:
            Student instance with sensible defaults
        """
        if student_id is None:
            student_id = uuid4().hex
        
        if phone_number is None:
            # Generate unique phone number using timestamp
            suffix = str(int(time.time() * 1000))[-9:]
            phone_number = f"+5511{suffix}"
        
        return Student(
            student_id=student_id,
            phone_number=phone_number,
            name=name or "Test Student",
            email=email or f"student_{student_id[:8]}@test.com",
            training_goal=training_goal or "Perder peso",
            **kwargs
        )


class TrainerStudentLinkFactory:
    """Factory for creating TrainerStudentLink test entities."""
    
    @staticmethod
    def create(
        trainer_id: str,
        student_id: str,
        status: str = "active",
        **kwargs
    ) -> TrainerStudentLink:
        """
        Create a TrainerStudentLink with defaults.
        
        Args:
            trainer_id: Trainer ID (required)
            student_id: Student ID (required)
            status: Link status (default: "active")
            **kwargs: Additional fields to override
        
        Returns:
            TrainerStudentLink instance with sensible defaults
        """
        return TrainerStudentLink(
            trainer_id=trainer_id,
            student_id=student_id,
            status=status,
            **kwargs
        )


class SessionFactory:
    """Factory for creating Session test entities."""
    
    @staticmethod
    def create(
        session_id: Optional[str] = None,
        trainer_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        session_datetime: Optional[datetime] = None,
        duration_minutes: int = 60,
        status: str = "scheduled",
        **kwargs
    ) -> Session:
        """
        Create a Session with defaults.
        
        Args:
            session_id: Session ID (default: random UUID4 hex)
            trainer_id: Trainer ID (default: random UUID4 hex)
            student_id: Student ID (default: random UUID4 hex)
            student_name: Student name (default: "Test Student")
            session_datetime: Session datetime (default: tomorrow at 10:00)
            duration_minutes: Duration in minutes (default: 60)
            status: Session status (default: "scheduled")
            **kwargs: Additional fields to override
        
        Returns:
            Session instance with sensible defaults
        """
        if session_id is None:
            session_id = uuid4().hex
        
        if trainer_id is None:
            trainer_id = uuid4().hex
        
        if student_id is None:
            student_id = uuid4().hex
        
        if session_datetime is None:
            # Default to tomorrow at 10:00 AM
            tomorrow = datetime.utcnow() + timedelta(days=1)
            session_datetime = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        
        return Session(
            session_id=session_id,
            trainer_id=trainer_id,
            student_id=student_id,
            student_name=student_name or "Test Student",
            session_datetime=session_datetime,
            duration_minutes=duration_minutes,
            status=status,
            **kwargs
        )


class PaymentFactory:
    """Factory for creating Payment test entities."""
    
    @staticmethod
    def create(
        payment_id: Optional[str] = None,
        trainer_id: Optional[str] = None,
        student_id: Optional[str] = None,
        student_name: Optional[str] = None,
        amount: Optional[float] = None,
        currency: str = "BRL",
        payment_date: Optional[str] = None,
        payment_status: str = "pending",
        **kwargs
    ) -> Payment:
        """
        Create a Payment with defaults.
        
        Args:
            payment_id: Payment ID (default: random UUID4 hex)
            trainer_id: Trainer ID (default: random UUID4 hex)
            student_id: Student ID (default: random UUID4 hex)
            student_name: Student name (default: "Test Student")
            amount: Payment amount (default: 100.00)
            currency: Currency code (default: "BRL")
            payment_date: Payment date in ISO format (default: today)
            payment_status: Payment status (default: "pending")
            **kwargs: Additional fields to override
        
        Returns:
            Payment instance with sensible defaults
        """
        if payment_id is None:
            payment_id = uuid4().hex
        
        if trainer_id is None:
            trainer_id = uuid4().hex
        
        if student_id is None:
            student_id = uuid4().hex
        
        if amount is None:
            amount = 100.00
        
        if payment_date is None:
            payment_date = datetime.utcnow().date().isoformat()
        
        return Payment(
            payment_id=payment_id,
            trainer_id=trainer_id,
            student_id=student_id,
            student_name=student_name or "Test Student",
            amount=amount,
            currency=currency,
            payment_date=payment_date,
            payment_status=payment_status,
            **kwargs
        )


class ConversationStateFactory:
    """Factory for creating ConversationState test entities."""
    
    @staticmethod
    def create(
        phone_number: Optional[str] = None,
        state: str = "UNKNOWN",
        user_id: Optional[str] = None,
        user_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        message_history: Optional[List[MessageHistoryEntry]] = None,
        ttl: Optional[int] = None,
        **kwargs
    ) -> ConversationState:
        """
        Create a ConversationState with defaults.
        
        Args:
            phone_number: Phone number in E.164 format (default: +5511777777XXX)
            state: Conversation state (default: "UNKNOWN")
            user_id: User ID (default: None)
            user_type: User type (default: None)
            context: Context dictionary (default: {})
            message_history: Message history (default: [])
            ttl: TTL timestamp (default: 24 hours from now)
            **kwargs: Additional fields to override
        
        Returns:
            ConversationState instance with sensible defaults
        """
        if phone_number is None:
            # Generate unique phone number using timestamp
            suffix = str(int(time.time() * 1000))[-9:]
            phone_number = f"+5511{suffix}"
        
        if ttl is None:
            # Default TTL: 24 hours from now
            ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        
        return ConversationState(
            phone_number=phone_number,
            state=state,
            user_id=user_id,
            user_type=user_type,
            context=context or {},
            message_history=message_history or [],
            ttl=ttl,
            **kwargs
        )


class TrainerConfigFactory:
    """Factory for creating TrainerConfig test entities."""
    
    @staticmethod
    def create(
        trainer_id: Optional[str] = None,
        reminder_hours: int = 24,
        payment_reminder_day: int = 1,
        payment_reminders_enabled: bool = True,
        session_reminders_enabled: bool = True,
        timezone: str = "America/Sao_Paulo",
        **kwargs
    ) -> TrainerConfig:
        """
        Create a TrainerConfig with defaults.
        
        Args:
            trainer_id: Trainer ID (default: random UUID4 hex)
            reminder_hours: Hours before session to send reminder (default: 24)
            payment_reminder_day: Day of month to send payment reminder (default: 1)
            payment_reminders_enabled: Enable payment reminders (default: True)
            session_reminders_enabled: Enable session reminders (default: True)
            timezone: Timezone (default: "America/Sao_Paulo")
            **kwargs: Additional fields to override
        
        Returns:
            TrainerConfig instance with sensible defaults
        """
        if trainer_id is None:
            trainer_id = uuid4().hex
        
        return TrainerConfig(
            trainer_id=trainer_id,
            reminder_hours=reminder_hours,
            payment_reminder_day=payment_reminder_day,
            payment_reminders_enabled=payment_reminders_enabled,
            session_reminders_enabled=session_reminders_enabled,
            timezone=timezone,
            **kwargs
        )


class NotificationFactory:
    """Factory for creating Notification test entities."""
    
    @staticmethod
    def create(
        notification_id: Optional[str] = None,
        trainer_id: Optional[str] = None,
        message: Optional[str] = None,
        recipient_count: int = 0,
        status: str = "queued",
        recipients: Optional[List[NotificationRecipient]] = None,
        **kwargs
    ) -> Notification:
        """
        Create a Notification with defaults.
        
        Args:
            notification_id: Notification ID (default: random UUID4 hex)
            trainer_id: Trainer ID (default: random UUID4 hex)
            message: Notification message (default: "Test notification")
            recipient_count: Number of recipients (default: 0)
            status: Notification status (default: "queued")
            recipients: List of recipients (default: [])
            **kwargs: Additional fields to override
        
        Returns:
            Notification instance with sensible defaults
        """
        if notification_id is None:
            notification_id = uuid4().hex
        
        if trainer_id is None:
            trainer_id = uuid4().hex
        
        return Notification(
            notification_id=notification_id,
            trainer_id=trainer_id,
            message=message or "Test notification",
            recipient_count=recipient_count,
            status=status,
            recipients=recipients or [],
            **kwargs
        )


class MenuContextFactory:
    """Factory for creating MenuContext test entities."""
    
    @staticmethod
    def create(
        phone_number: Optional[str] = None,
        user_id: Optional[str] = None,
        user_type: str = "TRAINER",
        menu_enabled: bool = True,
        current_menu: str = "main",
        navigation_stack: Optional[List[str]] = None,
        ttl: Optional[int] = None,
        **kwargs
    ) -> MenuContext:
        """
        Create a MenuContext with defaults.
        
        Args:
            phone_number: Phone number in E.164 format (default: +5511666666XXX)
            user_id: User ID (default: random UUID4 hex)
            user_type: User type (default: "TRAINER")
            menu_enabled: Menu enabled flag (default: True)
            current_menu: Current menu (default: "main")
            navigation_stack: Navigation stack (default: [])
            ttl: TTL timestamp (default: 24 hours from now)
            **kwargs: Additional fields to override
        
        Returns:
            MenuContext instance with sensible defaults
        """
        if phone_number is None:
            # Generate unique phone number using timestamp
            suffix = str(int(time.time() * 1000))[-9:]
            phone_number = f"+5511{suffix}"
        
        if user_id is None:
            user_id = uuid4().hex
        
        if ttl is None:
            # Default TTL: 24 hours from now
            ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
        
        return MenuContext(
            phone_number=phone_number,
            user_id=user_id,
            user_type=user_type,
            menu_enabled=menu_enabled,
            current_menu=current_menu,
            navigation_stack=navigation_stack or [],
            ttl=ttl,
            **kwargs
        )
