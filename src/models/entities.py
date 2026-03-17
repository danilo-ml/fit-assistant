"""
Pydantic models for all FitAgent entities.

This module defines data models for all entities in the system with methods
to serialize/deserialize to/from DynamoDB format following the single-table design.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import uuid4


class Trainer(BaseModel):
    """Trainer entity model."""
    
    trainer_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["TRAINER"] = "TRAINER"
    name: str
    email: str
    business_name: str
    phone_number: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format')
        return v
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': 'METADATA',
            'entity_type': self.entity_type,
            'trainer_id': self.trainer_id,
            'name': self.name,
            'email': self.email,
            'business_name': self.business_name,
            'phone_number': self.phone_number,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Trainer':
        """Create instance from DynamoDB item."""
        return cls(
            trainer_id=item['trainer_id'],
            name=item['name'],
            email=item['email'],
            business_name=item['business_name'],
            phone_number=item['phone_number'],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class Student(BaseModel):
    """Student entity model."""
    
    student_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["STUDENT"] = "STUDENT"
    name: str
    email: str
    phone_number: str
    training_goal: str
    payment_due_day: Optional[int] = None  # Day of month (1-31) for payment due date
    monthly_fee: Optional[Decimal] = None  # Monthly fee in BRL (2 decimal places)
    currency: str = "BRL"  # Always BRL for plan registrations
    plan_start_date: Optional[str] = None  # ISO format YYYY-MM (month plan starts)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format')
        return v
    
    @field_validator('payment_due_day')
    @classmethod
    def validate_payment_due_day(cls, v: Optional[int]) -> Optional[int]:
        """Validate payment due day is between 1 and 31."""
        if v is not None and (v < 1 or v > 31):
            raise ValueError('Payment due day must be between 1 and 31')
        return v

    @field_validator('monthly_fee')
    @classmethod
    def validate_monthly_fee(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate monthly fee is positive with exactly 2 decimal places."""
        if v is None:
            return v
        if not isinstance(v, Decimal):
            try:
                v = Decimal(str(v))
            except (InvalidOperation, ValueError):
                raise ValueError('Monthly fee must be a valid decimal number')
        if v <= 0:
            raise ValueError('Monthly fee must be greater than 0')
        if v.as_tuple().exponent != -2:
            raise ValueError('Monthly fee must have exactly 2 decimal places')
        return v

    @field_validator('plan_start_date')
    @classmethod
    def validate_plan_start_date(cls, v: Optional[str]) -> Optional[str]:
        """Validate plan start date is in YYYY-MM format."""
        if v is None:
            return v
        import re
        if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', v):
            raise ValueError('Plan start date must be in YYYY-MM format')
        return v
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'STUDENT#{self.student_id}',
            'SK': 'METADATA',
            'entity_type': self.entity_type,
            'student_id': self.student_id,
            'name': self.name,
            'email': self.email,
            'phone_number': self.phone_number,
            'training_goal': self.training_goal,
            'currency': self.currency,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        if self.payment_due_day is not None:
            item['payment_due_day'] = self.payment_due_day
        if self.monthly_fee is not None:
            item['monthly_fee'] = str(self.monthly_fee)
        if self.plan_start_date is not None:
            item['plan_start_date'] = self.plan_start_date
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Student':
        """Create instance from DynamoDB item."""
        monthly_fee = None
        if 'monthly_fee' in item and item['monthly_fee'] is not None:
            monthly_fee = Decimal(str(item['monthly_fee']))
        return cls(
            student_id=item['student_id'],
            name=item['name'],
            email=item['email'],
            phone_number=item['phone_number'],
            training_goal=item['training_goal'],
            payment_due_day=item.get('payment_due_day'),
            monthly_fee=monthly_fee,
            currency=item.get('currency', 'BRL'),
            plan_start_date=item.get('plan_start_date'),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class TrainerStudentLink(BaseModel):
    """Trainer-Student relationship link."""
    
    entity_type: Literal["TRAINER_STUDENT_LINK"] = "TRAINER_STUDENT_LINK"
    trainer_id: str
    student_id: str
    linked_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["active", "inactive"] = "active"
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': f'STUDENT#{self.student_id}',
            'entity_type': self.entity_type,
            'trainer_id': self.trainer_id,
            'student_id': self.student_id,
            'linked_at': self.linked_at.isoformat(),
            'status': self.status
        }
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'TrainerStudentLink':
        """Create instance from DynamoDB item."""
        return cls(
            trainer_id=item['trainer_id'],
            student_id=item['student_id'],
            linked_at=datetime.fromisoformat(item['linked_at']),
            status=item['status']
        )


class Session(BaseModel):
    """Training session entity model."""
    
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["SESSION"] = "SESSION"
    trainer_id: str
    student_id: str
    student_name: str
    session_datetime: datetime
    duration_minutes: int = Field(ge=15, le=480)
    location: Optional[str] = None
    status: Literal["scheduled", "confirmed", "cancelled", "completed", "missed"] = "scheduled"
    
    # Session confirmation fields (new for multi-agent architecture)
    confirmation_status: Literal["scheduled", "completed", "missed", "pending_confirmation", "cancelled"] = "scheduled"
    confirmation_requested_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    confirmation_response: Optional[str] = None
    
    # Calendar integration fields
    calendar_event_id: Optional[str] = None
    calendar_provider: Optional[Literal["google", "outlook"]] = None
    
    # Legacy confirmation fields (deprecated, kept for backward compatibility)
    student_confirmed: bool = False
    student_confirmed_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': f'SESSION#{self.session_id}',
            'entity_type': self.entity_type,
            'session_id': self.session_id,
            'trainer_id': self.trainer_id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'session_datetime': self.session_datetime.isoformat(),
            'duration_minutes': self.duration_minutes,
            'status': self.status,
            'confirmation_status': self.confirmation_status,
            'student_confirmed': self.student_confirmed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            # GSI key for session-confirmation-index
            'confirmation_status_datetime': f'{self.confirmation_status}#{self.session_datetime.isoformat()}',
        }
        
        if self.location:
            item['location'] = self.location
        if self.calendar_event_id:
            item['calendar_event_id'] = self.calendar_event_id
        if self.calendar_provider:
            item['calendar_provider'] = self.calendar_provider
        if self.confirmation_requested_at:
            item['confirmation_requested_at'] = self.confirmation_requested_at.isoformat()
        if self.confirmed_at:
            item['confirmed_at'] = self.confirmed_at.isoformat()
        if self.confirmation_response:
            item['confirmation_response'] = self.confirmation_response
        if self.student_confirmed_at:
            item['student_confirmed_at'] = self.student_confirmed_at.isoformat()
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Session':
        """Create instance from DynamoDB item."""
        return cls(
            session_id=item['session_id'],
            trainer_id=item['trainer_id'],
            student_id=item['student_id'],
            student_name=item['student_name'],
            session_datetime=datetime.fromisoformat(item['session_datetime']),
            duration_minutes=item['duration_minutes'],
            location=item.get('location'),
            status=item.get('status', 'scheduled'),
            confirmation_status=item.get('confirmation_status', 'scheduled'),
            confirmation_requested_at=datetime.fromisoformat(item['confirmation_requested_at']) if item.get('confirmation_requested_at') else None,
            confirmed_at=datetime.fromisoformat(item['confirmed_at']) if item.get('confirmed_at') else None,
            confirmation_response=item.get('confirmation_response'),
            calendar_event_id=item.get('calendar_event_id'),
            calendar_provider=item.get('calendar_provider'),
            student_confirmed=item.get('student_confirmed', False),
            student_confirmed_at=datetime.fromisoformat(item['student_confirmed_at']) if item.get('student_confirmed_at') else None,
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class Payment(BaseModel):
    """Payment record entity model."""
    
    payment_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["PAYMENT"] = "PAYMENT"
    trainer_id: str
    student_id: str
    student_name: str
    amount: Decimal = Field(ge=0)
    currency: str = "USD"
    payment_date: str  # ISO date format YYYY-MM-DD
    payment_status: Literal["pending", "confirmed"] = "pending"
    receipt_s3_key: Optional[str] = None
    receipt_media_type: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    session_id: Optional[str] = None
    reference_start_month: Optional[str] = None  # ISO YYYY-MM
    reference_end_month: Optional[str] = None  # ISO YYYY-MM
    verification_status: Optional[Literal["matched", "mismatched"]] = None
    expected_amount: Optional[Decimal] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, v: Any) -> Decimal:
        """Convert amount to Decimal, accepting both float and Decimal inputs."""
        if v is None:
            raise ValueError('Amount is required')
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise ValueError('Amount must be a valid number')

    @field_validator('expected_amount', mode='before')
    @classmethod
    def validate_expected_amount(cls, v: Any) -> Optional[Decimal]:
        """Convert expected_amount to Decimal, accepting both float and Decimal inputs."""
        if v is None:
            return v
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError):
            raise ValueError('Expected amount must be a valid number')

    @field_validator('reference_start_month')
    @classmethod
    def validate_reference_start_month(cls, v: Optional[str]) -> Optional[str]:
        """Validate reference start month is in YYYY-MM format."""
        if v is None:
            return v
        import re
        if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', v):
            raise ValueError('Reference start month must be in YYYY-MM format')
        return v

    @field_validator('reference_end_month')
    @classmethod
    def validate_reference_end_month(cls, v: Optional[str]) -> Optional[str]:
        """Validate reference end month is in YYYY-MM format."""
        if v is None:
            return v
        import re
        if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', v):
            raise ValueError('Reference end month must be in YYYY-MM format')
        return v

    @model_validator(mode='after')
    def validate_reference_months(self) -> 'Payment':
        """Validate both reference months are present or both absent, and start <= end."""
        start = self.reference_start_month
        end = self.reference_end_month
        if (start is None) != (end is None):
            raise ValueError('Both reference_start_month and reference_end_month must be provided together')
        if start is not None and end is not None and start > end:
            raise ValueError('Reference start month must be <= end month')
        return self

    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': f'PAYMENT#{self.payment_id}',
            'entity_type': self.entity_type,
            'payment_id': self.payment_id,
            'trainer_id': self.trainer_id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'amount': str(self.amount),
            'currency': self.currency,
            'payment_date': self.payment_date,
            'payment_status': self.payment_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if self.receipt_s3_key:
            item['receipt_s3_key'] = self.receipt_s3_key
        if self.receipt_media_type:
            item['receipt_media_type'] = self.receipt_media_type
        if self.confirmed_at:
            item['confirmed_at'] = self.confirmed_at.isoformat()
        if self.session_id:
            item['session_id'] = self.session_id
        if self.reference_start_month is not None:
            item['reference_start_month'] = self.reference_start_month
        if self.reference_end_month is not None:
            item['reference_end_month'] = self.reference_end_month
        if self.verification_status is not None:
            item['verification_status'] = self.verification_status
        if self.expected_amount is not None:
            item['expected_amount'] = str(self.expected_amount)
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Payment':
        """Create instance from DynamoDB item."""
        amount = Decimal(str(item['amount']))
        expected_amount = None
        if 'expected_amount' in item and item['expected_amount'] is not None:
            expected_amount = Decimal(str(item['expected_amount']))
        return cls(
            payment_id=item['payment_id'],
            trainer_id=item['trainer_id'],
            student_id=item['student_id'],
            student_name=item['student_name'],
            amount=amount,
            currency=item['currency'],
            payment_date=item['payment_date'],
            payment_status=item['payment_status'],
            receipt_s3_key=item.get('receipt_s3_key'),
            receipt_media_type=item.get('receipt_media_type'),
            confirmed_at=datetime.fromisoformat(item['confirmed_at']) if item.get('confirmed_at') else None,
            session_id=item.get('session_id'),
            reference_start_month=item.get('reference_start_month'),
            reference_end_month=item.get('reference_end_month'),
            verification_status=item.get('verification_status'),
            expected_amount=expected_amount,
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class MessageHistoryEntry(BaseModel):
    """Single message in conversation history."""
    
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class ConversationState(BaseModel):
    """Conversation state entity model."""
    
    entity_type: Literal["CONVERSATION_STATE"] = "CONVERSATION_STATE"
    phone_number: str
    state: Literal["UNKNOWN", "ONBOARDING", "TRAINER_MENU", "STUDENT_MENU"]
    user_id: Optional[str] = None
    user_type: Optional[Literal["TRAINER", "STUDENT"]] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    message_history: List[MessageHistoryEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ttl: int  # Unix timestamp for TTL expiration
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format')
        return v
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'CONVERSATION#{self.phone_number}',
            'SK': 'STATE',
            'entity_type': self.entity_type,
            'phone_number': self.phone_number,
            'state': self.state,
            'context': self.context,
            'message_history': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in self.message_history
            ],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ttl': self.ttl
        }
        
        if self.user_id:
            item['user_id'] = self.user_id
        if self.user_type:
            item['user_type'] = self.user_type
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'ConversationState':
        """Create instance from DynamoDB item."""
        return cls(
            phone_number=item['phone_number'],
            state=item['state'],
            user_id=item.get('user_id'),
            user_type=item.get('user_type'),
            context=item.get('context', {}),
            message_history=[
                MessageHistoryEntry(
                    role=msg['role'],
                    content=msg['content'],
                    timestamp=datetime.fromisoformat(msg['timestamp'])
                )
                for msg in item.get('message_history', [])
            ],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            ttl=item['ttl']
        )


class TrainerConfig(BaseModel):
    """Trainer configuration entity model."""
    
    entity_type: Literal["TRAINER_CONFIG"] = "TRAINER_CONFIG"
    trainer_id: str
    reminder_hours: int = Field(default=24, ge=1, le=48)
    payment_reminder_day: int = Field(default=1, ge=1, le=28)
    payment_reminders_enabled: bool = True
    session_reminders_enabled: bool = True
    timezone: str = "America/New_York"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': 'CONFIG',
            'entity_type': self.entity_type,
            'trainer_id': self.trainer_id,
            'reminder_hours': self.reminder_hours,
            'payment_reminder_day': self.payment_reminder_day,
            'payment_reminders_enabled': self.payment_reminders_enabled,
            'session_reminders_enabled': self.session_reminders_enabled,
            'timezone': self.timezone,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'TrainerConfig':
        """Create instance from DynamoDB item."""
        return cls(
            trainer_id=item['trainer_id'],
            reminder_hours=item['reminder_hours'],
            payment_reminder_day=item['payment_reminder_day'],
            payment_reminders_enabled=item['payment_reminders_enabled'],
            session_reminders_enabled=item['session_reminders_enabled'],
            timezone=item['timezone'],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class CalendarConfig(BaseModel):
    """Calendar configuration entity model."""
    
    entity_type: Literal["CALENDAR_CONFIG"] = "CALENDAR_CONFIG"
    trainer_id: str
    provider: Literal["google", "outlook"]
    encrypted_refresh_token: bytes
    scope: str
    calendar_id: Optional[str] = None
    connected_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': 'CALENDAR_CONFIG',
            'entity_type': self.entity_type,
            'trainer_id': self.trainer_id,
            'provider': self.provider,
            'encrypted_refresh_token': self.encrypted_refresh_token,
            'scope': self.scope,
            'connected_at': self.connected_at.isoformat(),
            'last_sync_at': self.last_sync_at.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        if self.calendar_id:
            item['calendar_id'] = self.calendar_id
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'CalendarConfig':
        """Create instance from DynamoDB item."""
        return cls(
            trainer_id=item['trainer_id'],
            provider=item['provider'],
            encrypted_refresh_token=item['encrypted_refresh_token'],
            scope=item['scope'],
            calendar_id=item.get('calendar_id'),
            connected_at=datetime.fromisoformat(item['connected_at']),
            last_sync_at=datetime.fromisoformat(item['last_sync_at']),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class NotificationRecipient(BaseModel):
    """Single recipient in a notification."""
    
    student_id: str
    phone_number: str
    status: Literal["queued", "sent", "delivered", "failed"] = "queued"
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class Notification(BaseModel):
    """Notification entity model."""
    
    notification_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["NOTIFICATION"] = "NOTIFICATION"
    trainer_id: str
    message: str
    recipient_count: int
    status: Literal["queued", "processing", "completed", "failed"] = "queued"
    recipients: List[NotificationRecipient] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        return {
            'PK': f'TRAINER#{self.trainer_id}',
            'SK': f'NOTIFICATION#{self.notification_id}',
            'entity_type': self.entity_type,
            'notification_id': self.notification_id,
            'trainer_id': self.trainer_id,
            'message': self.message,
            'recipient_count': self.recipient_count,
            'status': self.status,
            'recipients': [
                {
                    'student_id': r.student_id,
                    'phone_number': r.phone_number,
                    'status': r.status,
                    'sent_at': r.sent_at.isoformat() if r.sent_at else None,
                    'delivered_at': r.delivered_at.isoformat() if r.delivered_at else None
                }
                for r in self.recipients
            ],
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Notification':
        """Create instance from DynamoDB item."""
        return cls(
            notification_id=item['notification_id'],
            trainer_id=item['trainer_id'],
            message=item['message'],
            recipient_count=item['recipient_count'],
            status=item['status'],
            recipients=[
                NotificationRecipient(
                    student_id=r['student_id'],
                    phone_number=r['phone_number'],
                    status=r['status'],
                    sent_at=datetime.fromisoformat(r['sent_at']) if r.get('sent_at') else None,
                    delivered_at=datetime.fromisoformat(r['delivered_at']) if r.get('delivered_at') else None
                )
                for r in item.get('recipients', [])
            ],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at'])
        )


class Reminder(BaseModel):
    """Reminder delivery record entity model."""
    
    reminder_id: str = Field(default_factory=lambda: uuid4().hex)
    entity_type: Literal["REMINDER"] = "REMINDER"
    session_id: str
    reminder_type: Literal["session", "payment"]
    recipient_phone: str
    status: Literal["sent", "delivered", "failed"]
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    delivered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('recipient_phone')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format')
        return v
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'SESSION#{self.session_id}',
            'SK': f'REMINDER#{self.reminder_id}',
            'entity_type': self.entity_type,
            'reminder_id': self.reminder_id,
            'session_id': self.session_id,
            'reminder_type': self.reminder_type,
            'recipient_phone': self.recipient_phone,
            'status': self.status,
            'sent_at': self.sent_at.isoformat(),
            'created_at': self.created_at.isoformat()
        }
        
        if self.delivered_at:
            item['delivered_at'] = self.delivered_at.isoformat()
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'Reminder':
        """Create instance from DynamoDB item."""
        return cls(
            reminder_id=item['reminder_id'],
            session_id=item['session_id'],
            reminder_type=item['reminder_type'],
            recipient_phone=item['recipient_phone'],
            status=item['status'],
            sent_at=datetime.fromisoformat(item['sent_at']),
            delivered_at=datetime.fromisoformat(item['delivered_at']) if item.get('delivered_at') else None,
            created_at=datetime.fromisoformat(item['created_at'])
        )




class MenuContext(BaseModel):
    """Menu navigation context stored in DynamoDB."""
    
    entity_type: Literal["MENU_CONTEXT"] = "MENU_CONTEXT"
    phone_number: str = Field(pattern=r'^\+[1-9]\d{1,14}$')
    user_id: str
    user_type: Literal["TRAINER", "STUDENT"]
    menu_enabled: bool = True
    current_menu: str = "main"
    navigation_stack: List[str] = Field(default_factory=list, max_length=3)
    pending_action: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ttl: int
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number is in E.164 format."""
        import re
        if not re.match(r'^\+[1-9]\d{1,14}$', v):
            raise ValueError('Phone number must be in E.164 format')
        return v
    
    @field_validator('navigation_stack')
    @classmethod
    def validate_navigation_stack(cls, v: List[str]) -> List[str]:
        """Validate navigation stack doesn't exceed max depth."""
        if len(v) > 3:
            raise ValueError('Navigation stack cannot exceed 3 levels')
        return v
    
    def to_dynamodb(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': f'MENU#{self.phone_number}',
            'SK': 'CONTEXT',
            'entity_type': self.entity_type,
            'phone_number': self.phone_number,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'menu_enabled': self.menu_enabled,
            'current_menu': self.current_menu,
            'navigation_stack': self.navigation_stack,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ttl': self.ttl
        }
        
        if self.pending_action:
            item['pending_action'] = self.pending_action
        
        return item
    
    @classmethod
    def from_dynamodb(cls, item: Dict[str, Any]) -> 'MenuContext':
        """Create instance from DynamoDB item."""
        return cls(
            phone_number=item['phone_number'],
            user_id=item['user_id'],
            user_type=item['user_type'],
            menu_enabled=item.get('menu_enabled', True),
            current_menu=item.get('current_menu', 'main'),
            navigation_stack=item.get('navigation_stack', []),
            pending_action=item.get('pending_action'),
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            ttl=item['ttl']
        )
