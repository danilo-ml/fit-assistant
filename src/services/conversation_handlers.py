"""
Conversation handlers for different user types.

This module implements three handler classes:
- OnboardingHandler: Handles trainer registration flow for new users
- TrainerHandler: Handles trainer menu and tool execution via AI agent
- StudentHandler: Handles student menu and session viewing

Each handler processes messages based on user type and conversation state,
integrating with the AIAgent for natural language understanding and tool execution.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from src.services.ai_agent import AIAgent
from src.services.conversation_state import ConversationStateManager
from src.models.dynamodb_client import DynamoDBClient
from src.models.entities import Trainer, Student
from src.utils.logging import get_logger
from src.utils.validation import PhoneNumberValidator
from src.config import settings

logger = get_logger(__name__)


class OnboardingHandler:
    """
    Handles onboarding flow for unregistered users.
    
    The onboarding process:
    1. Welcome message asking if user is trainer or student
    2. For trainers: Collect name, email, business name
    3. Create trainer record in DynamoDB
    4. Transition to trainer menu
    
    For students: Direct them to contact their trainer for registration.
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    def __init__(
        self,
        dynamodb_client: Optional[DynamoDBClient] = None,
        state_manager: Optional[ConversationStateManager] = None,
    ):
        """
        Initialize OnboardingHandler.
        
        Args:
            dynamodb_client: DynamoDB client for data operations
            state_manager: Conversation state manager
        """
        self.dynamodb = dynamodb_client or DynamoDBClient(
            table_name=settings.dynamodb_table,
            endpoint_url=settings.aws_endpoint_url,
        )
        self.state_manager = state_manager or ConversationStateManager(self.dynamodb)
    
    def handle_message(
        self,
        phone_number: str,
        message_body: Dict[str, Any],
        request_id: str,
    ) -> str:
        """
        Handle onboarding message from unregistered user.
        
        Args:
            phone_number: User's phone number
            message_body: Message payload from webhook
            request_id: Request ID for tracing
        
        Returns:
            Response text for user
        """
        logger.info(
            "Processing onboarding message",
            phone_number=phone_number,
            request_id=request_id,
        )
        
        # Get current conversation state
        state = self.state_manager.get_state(phone_number)
        message_text = message_body.get("body", "").strip().lower()
        
        # Check if this is the first message (no state)
        if not state or state.get("state") == "UNKNOWN":
            # Send welcome message
            response = self._send_welcome_message()
            
            # Initialize conversation state
            self.state_manager.update_state(
                phone_number=phone_number,
                state="ONBOARDING",
                context={"step": "user_type"},
                message={"role": "user", "content": message_text},
            )
            
            return response
        
        # Get current onboarding step
        context = state.get("context", {})
        step = context.get("step", "user_type")
        
        # Process based on current step
        if step == "user_type":
            return self._handle_user_type_selection(phone_number, message_text, request_id)
        
        elif step == "trainer_name":
            return self._handle_trainer_name(phone_number, message_text, request_id)
        
        elif step == "trainer_email":
            return self._handle_trainer_email(phone_number, message_text, request_id)
        
        elif step == "trainer_business":
            return self._handle_trainer_business(phone_number, message_text, request_id)
        
        else:
            # Unknown step - restart onboarding
            logger.warning(
                "Unknown onboarding step, restarting",
                phone_number=phone_number,
                step=step,
            )
            return self._send_welcome_message()
    
    def _send_welcome_message(self) -> str:
        """Send initial welcome message."""
        return (
            "Welcome to FitAgent! 👋\n\n"
            "I'm your AI assistant for managing training sessions and students.\n\n"
            "Are you a:\n"
            "1️⃣ Personal Trainer\n"
            "2️⃣ Student\n\n"
            "Please reply with 1 or 2 to get started."
        )
    
    def _handle_user_type_selection(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle user type selection (trainer or student)."""
        # Check if user selected trainer
        if "1" in message_text or "trainer" in message_text:
            # Start trainer registration
            self.state_manager.update_state(
                phone_number=phone_number,
                state="ONBOARDING",
                context={"step": "trainer_name", "user_type": "trainer"},
            )
            
            return (
                "Great! Let's get you set up as a trainer. 💪\n\n"
                "What's your full name?"
            )
        
        # Check if user selected student
        elif "2" in message_text or "student" in message_text:
            # Students need to be registered by their trainer
            return (
                "Thanks for your interest! 🙏\n\n"
                "Students are registered by their trainers. Please ask your trainer "
                "to add you to their roster, and they'll provide you with access.\n\n"
                "If you're a trainer, please reply with '1' to register."
            )
        
        else:
            # Invalid response
            return (
                "I didn't understand that. Please reply with:\n"
                "1️⃣ for Personal Trainer\n"
                "2️⃣ for Student"
            )
    
    def _handle_trainer_name(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer name collection."""
        # Validate name (basic check)
        if len(message_text) < 2:
            return "Please provide your full name (at least 2 characters)."
        
        # Store name and move to next step
        state = self.state_manager.get_state(phone_number)
        context = state.get("context", {})
        context["trainer_name"] = message_text.title()
        context["step"] = "trainer_email"
        
        self.state_manager.update_state(
            phone_number=phone_number,
            state="ONBOARDING",
            context=context,
        )
        
        return f"Nice to meet you, {context['trainer_name']}! 👋\n\nWhat's your email address?"
    
    def _handle_trainer_email(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer email collection."""
        # Basic email validation
        if "@" not in message_text or "." not in message_text:
            return "Please provide a valid email address (e.g., trainer@example.com)."
        
        # Store email and move to next step
        state = self.state_manager.get_state(phone_number)
        context = state.get("context", {})
        context["trainer_email"] = message_text.lower()
        context["step"] = "trainer_business"
        
        self.state_manager.update_state(
            phone_number=phone_number,
            state="ONBOARDING",
            context=context,
        )
        
        return "Perfect! What's your business name? (This is how students will see you)"
    
    def _handle_trainer_business(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer business name and complete registration."""
        # Validate business name
        if len(message_text) < 2:
            return "Please provide your business name (at least 2 characters)."
        
        # Get collected information
        state = self.state_manager.get_state(phone_number)
        context = state.get("context", {})
        
        trainer_name = context.get("trainer_name")
        trainer_email = context.get("trainer_email")
        business_name = message_text.title()
        
        # Validate phone number format
        if not PhoneNumberValidator.validate(phone_number):
            normalized = PhoneNumberValidator.normalize(phone_number)
            if normalized:
                phone_number = normalized
            else:
                logger.error(
                    "Invalid phone number format during registration",
                    phone_number=phone_number,
                )
                return (
                    "There was an issue with your phone number format. "
                    "Please contact support for assistance."
                )
        
        # Create trainer record
        try:
            trainer_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            trainer = Trainer(
                trainer_id=trainer_id,
                name=trainer_name,
                email=trainer_email,
                business_name=business_name,
                phone_number=phone_number,
                created_at=now,
                updated_at=now,
            )
            
            # Save to DynamoDB
            self.dynamodb.put_trainer(trainer)
            
            logger.info(
                "Trainer registered successfully",
                trainer_id=trainer_id,
                phone_number=phone_number,
                request_id=request_id,
            )
            
            # Update conversation state to trainer menu
            self.state_manager.update_state(
                phone_number=phone_number,
                state="TRAINER_MENU",
                user_id=trainer_id,
                user_type="TRAINER",
                context={"onboarding_completed": True},
            )
            
            # Send success message with menu
            return (
                f"🎉 Welcome to FitAgent, {trainer_name}!\n\n"
                f"Your account is now active. I can help you with:\n\n"
                "📝 Register and manage students\n"
                "📅 Schedule training sessions\n"
                "💰 Track payments\n"
                "🔔 Send notifications\n"
                "📆 Connect your calendar (Google/Outlook)\n\n"
                "What would you like to do? Just tell me in your own words!"
            )
        
        except Exception as e:
            logger.error(
                "Failed to register trainer",
                phone_number=phone_number,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "I'm sorry, there was an error creating your account. "
                "Please try again or contact support if the issue persists."
            )


class TrainerHandler:
    """
    Handles trainer messages with AI agent integration.
    
    This handler:
    - Uses AIAgent for natural language understanding
    - Executes tool functions based on trainer requests
    - Maintains conversation context across interactions
    - Provides trainer menu and capabilities
    
    Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
    """
    
    def __init__(
        self,
        ai_agent: Optional[AIAgent] = None,
        state_manager: Optional[ConversationStateManager] = None,
        dynamodb_client: Optional[DynamoDBClient] = None,
    ):
        """
        Initialize TrainerHandler.
        
        Args:
            ai_agent: AI agent for natural language processing
            state_manager: Conversation state manager
            dynamodb_client: DynamoDB client for data operations
        """
        self.ai_agent = ai_agent or AIAgent()
        self.dynamodb = dynamodb_client or DynamoDBClient(
            table_name=settings.dynamodb_table,
            endpoint_url=settings.aws_endpoint_url,
        )
        self.state_manager = state_manager or ConversationStateManager(self.dynamodb)
    
    def handle_message(
        self,
        trainer_id: str,
        user_data: Dict[str, Any],
        message_body: Dict[str, Any],
        request_id: str,
    ) -> str:
        """
        Handle trainer message with AI agent.
        
        Args:
            trainer_id: Trainer's unique identifier
            user_data: Trainer's user record from DynamoDB
            message_body: Message payload from webhook
            request_id: Request ID for tracing
        
        Returns:
            Response text from AI agent
        """
        logger.info(
            "Processing trainer message",
            trainer_id=trainer_id,
            request_id=request_id,
        )
        
        phone_number = user_data.get("phone_number")
        message_text = message_body.get("body", "").strip()
        
        # Get conversation state for history
        state = self.state_manager.get_state(phone_number)
        conversation_history = []
        
        if state:
            # Extract message history for AI context
            message_history = state.get("message_history", [])
            # Convert to Bedrock format (last 5 messages for context)
            for msg in message_history[-5:]:
                role = msg.get("role")
                content = msg.get("content", "")
                if role and content:
                    conversation_history.append({
                        "role": role,
                        "content": [{"text": content}]
                    })
        
        # Process message with AI agent
        try:
            result = self.ai_agent.process_message(
                trainer_id=trainer_id,
                message=message_text,
                conversation_history=conversation_history,
            )
            
            if result.get("success"):
                response_text = result.get("response", "")
                
                # Update conversation state with new messages
                self.state_manager.update_state(
                    phone_number=phone_number,
                    state="TRAINER_MENU",
                    user_id=trainer_id,
                    user_type="TRAINER",
                    message={"role": "user", "content": message_text},
                )
                
                # Add assistant response to history
                self.state_manager.update_state(
                    phone_number=phone_number,
                    state="TRAINER_MENU",
                    user_id=trainer_id,
                    user_type="TRAINER",
                    message={"role": "assistant", "content": response_text},
                )
                
                logger.info(
                    "Trainer message processed successfully",
                    trainer_id=trainer_id,
                    tool_calls=len(result.get("tool_calls", [])),
                    request_id=request_id,
                )
                
                return response_text
            
            else:
                # AI agent returned error
                error_message = result.get("error", "Unknown error")
                logger.error(
                    "AI agent returned error",
                    trainer_id=trainer_id,
                    error=error_message,
                    request_id=request_id,
                )
                
                return (
                    "I'm having trouble processing your request right now. "
                    "Please try again or rephrase your message."
                )
        
        except Exception as e:
            logger.error(
                "Failed to process trainer message",
                trainer_id=trainer_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "Something went wrong while processing your request. "
                "Please try again in a moment."
            )


class StudentHandler:
    """
    Handles student messages for session viewing and confirmation.
    
    This handler provides students with:
    - View upcoming sessions (next 30 days)
    - Confirm attendance for sessions
    - Cancel attendance (notifies trainer)
    
    Students have limited functionality compared to trainers.
    
    Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5
    """
    
    def __init__(
        self,
        dynamodb_client: Optional[DynamoDBClient] = None,
        state_manager: Optional[ConversationStateManager] = None,
    ):
        """
        Initialize StudentHandler.
        
        Args:
            dynamodb_client: DynamoDB client for data operations
            state_manager: Conversation state manager
        """
        self.dynamodb = dynamodb_client or DynamoDBClient(
            table_name=settings.dynamodb_table,
            endpoint_url=settings.aws_endpoint_url,
        )
        self.state_manager = state_manager or ConversationStateManager(self.dynamodb)
    
    def handle_message(
        self,
        student_id: str,
        user_data: Dict[str, Any],
        message_body: Dict[str, Any],
        request_id: str,
    ) -> str:
        """
        Handle student message.
        
        Args:
            student_id: Student's unique identifier
            user_data: Student's user record from DynamoDB
            message_body: Message payload from webhook
            request_id: Request ID for tracing
        
        Returns:
            Response text for student
        """
        logger.info(
            "Processing student message",
            student_id=student_id,
            request_id=request_id,
        )
        
        phone_number = user_data.get("phone_number")
        student_name = user_data.get("name", "Student")
        message_text = message_body.get("body", "").strip().lower()
        
        # Simple keyword-based routing for student actions
        if any(word in message_text for word in ["session", "schedule", "upcoming", "next"]):
            return self._view_upcoming_sessions(student_id, student_name, request_id)
        
        elif any(word in message_text for word in ["confirm", "yes", "attending"]):
            return self._handle_confirmation(student_id, message_text, request_id)
        
        elif any(word in message_text for word in ["cancel", "can't make", "cannot"]):
            return self._handle_cancellation(student_id, message_text, request_id)
        
        else:
            # Default menu
            return self._send_student_menu(student_name)
    
    def _send_student_menu(self, student_name: str) -> str:
        """Send student menu with available options."""
        return (
            f"Hi {student_name}! 👋\n\n"
            "I can help you with:\n\n"
            "📅 View upcoming sessions\n"
            "✅ Confirm attendance\n"
            "❌ Cancel attendance\n\n"
            "What would you like to do?"
        )
    
    def _view_upcoming_sessions(
        self,
        student_id: str,
        student_name: str,
        request_id: str,
    ) -> str:
        """
        View upcoming sessions for student (next 30 days).
        
        Validates: Requirements 7.1, 7.2, 7.5
        """
        try:
            # Query sessions for next 30 days
            now = datetime.utcnow()
            end_date = now + timedelta(days=30)
            
            # Get all sessions for this student
            sessions = self.dynamodb.get_student_sessions(
                student_id=student_id,
                start_datetime=now,
                end_datetime=end_date,
            )
            
            if not sessions:
                return (
                    f"Hi {student_name}! 👋\n\n"
                    "You don't have any upcoming sessions scheduled in the next 30 days.\n\n"
                    "Contact your trainer to schedule a session!"
                )
            
            # Format sessions in chronological order
            response = f"Hi {student_name}! 👋\n\nYour upcoming sessions:\n\n"
            
            for i, session in enumerate(sessions, 1):
                session_datetime = datetime.fromisoformat(session.get("session_datetime"))
                trainer_name = session.get("trainer_name", "Your trainer")
                location = session.get("location", "")
                duration = session.get("duration_minutes", 60)
                status = session.get("status", "scheduled")
                confirmed = session.get("student_confirmed", False)
                
                # Format date and time
                date_str = session_datetime.strftime("%A, %B %d")
                time_str = session_datetime.strftime("%I:%M %p")
                
                response += f"{i}. {date_str} at {time_str}\n"
                response += f"   Trainer: {trainer_name}\n"
                response += f"   Duration: {duration} minutes\n"
                
                if location:
                    response += f"   Location: {location}\n"
                
                if confirmed:
                    response += "   ✅ Confirmed\n"
                elif status == "scheduled":
                    response += "   ⏳ Pending confirmation\n"
                
                response += "\n"
            
            response += "Reply 'confirm' to confirm attendance or 'cancel' to cancel a session."
            
            logger.info(
                "Student sessions retrieved",
                student_id=student_id,
                session_count=len(sessions),
                request_id=request_id,
            )
            
            return response
        
        except Exception as e:
            logger.error(
                "Failed to retrieve student sessions",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "I'm having trouble retrieving your sessions right now. "
                "Please try again in a moment."
            )
    
    def _handle_confirmation(
        self,
        student_id: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """
        Handle student attendance confirmation.
        
        Updates the next upcoming unconfirmed session with student_confirmed=true
        and records the confirmation timestamp.
        
        Validates: Requirement 7.3
        """
        try:
            # Get upcoming sessions for this student
            now = datetime.utcnow()
            end_date = now + timedelta(days=30)
            
            sessions = self.dynamodb.get_student_sessions(
                student_id=student_id,
                start_datetime=now,
                end_datetime=end_date,
            )
            
            if not sessions:
                return (
                    "You don't have any upcoming sessions to confirm. "
                    "Contact your trainer to schedule a session!"
                )
            
            # Find the next unconfirmed session
            unconfirmed_session = None
            for session in sessions:
                if not session.get("student_confirmed", False) and session.get("status") == "scheduled":
                    unconfirmed_session = session
                    break
            
            if not unconfirmed_session:
                return (
                    "All your upcoming sessions are already confirmed! ✅\n\n"
                    "If you need to make changes, please contact your trainer."
                )
            
            # Update session with confirmation
            session_id = unconfirmed_session.get("session_id")
            trainer_id = unconfirmed_session.get("trainer_id")
            confirmation_time = datetime.utcnow().isoformat()
            
            # Update the session record
            unconfirmed_session["student_confirmed"] = True
            unconfirmed_session["student_confirmed_at"] = confirmation_time
            unconfirmed_session["updated_at"] = confirmation_time
            
            self.dynamodb.put_session(unconfirmed_session)
            
            # Format session details for response
            session_datetime = datetime.fromisoformat(unconfirmed_session.get("session_datetime"))
            date_str = session_datetime.strftime("%A, %B %d")
            time_str = session_datetime.strftime("%I:%M %p")
            trainer_name = unconfirmed_session.get("trainer_name", "Your trainer")
            
            logger.info(
                "Student confirmed attendance",
                student_id=student_id,
                session_id=session_id,
                trainer_id=trainer_id,
                request_id=request_id,
            )
            
            return (
                f"✅ Attendance confirmed!\n\n"
                f"Session: {date_str} at {time_str}\n"
                f"Trainer: {trainer_name}\n\n"
                f"See you there! 💪"
            )
        
        except Exception as e:
            logger.error(
                "Failed to confirm student attendance",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "I'm having trouble confirming your attendance right now. "
                "Please try again in a moment."
            )
    
    def _handle_cancellation(
        self,
        student_id: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """
        Handle student attendance cancellation.
        
        Notifies the trainer via WhatsApp within 5 minutes when student cancels.
        
        Validates: Requirement 7.4
        """
        try:
            # Get upcoming sessions for this student
            now = datetime.utcnow()
            end_date = now + timedelta(days=30)
            
            sessions = self.dynamodb.get_student_sessions(
                student_id=student_id,
                start_datetime=now,
                end_datetime=end_date,
            )
            
            if not sessions:
                return (
                    "You don't have any upcoming sessions to cancel. "
                    "If you need to make changes, please contact your trainer."
                )
            
            # Find the next scheduled session
            next_session = None
            for session in sessions:
                if session.get("status") == "scheduled":
                    next_session = session
                    break
            
            if not next_session:
                return (
                    "You don't have any scheduled sessions to cancel. "
                    "If you need to make changes, please contact your trainer."
                )
            
            # Get session and trainer details
            session_id = next_session.get("session_id")
            trainer_id = next_session.get("trainer_id")
            student_name = next_session.get("student_name", "Student")
            session_datetime = datetime.fromisoformat(next_session.get("session_datetime"))
            
            # Get trainer information for notification
            trainer = self.dynamodb.get_trainer(trainer_id)
            if not trainer:
                logger.error(
                    "Trainer not found for cancellation notification",
                    trainer_id=trainer_id,
                    session_id=session_id,
                    request_id=request_id,
                )
                return (
                    "I'm having trouble processing your cancellation. "
                    "Please contact your trainer directly."
                )
            
            trainer_phone = trainer.get("phone_number")
            trainer_name = trainer.get("name", "Trainer")
            
            # Format session details for notification
            date_str = session_datetime.strftime("%A, %B %d")
            time_str = session_datetime.strftime("%I:%M %p")
            duration = next_session.get("duration_minutes", 60)
            location = next_session.get("location", "")
            
            # Send WhatsApp notification to trainer
            from src.services.twilio_client import TwilioClient
            twilio_client = TwilioClient()
            
            notification_message = (
                f"⚠️ Session Cancellation Notice\n\n"
                f"Student: {student_name}\n"
                f"Date: {date_str}\n"
                f"Time: {time_str}\n"
                f"Duration: {duration} minutes\n"
            )
            
            if location:
                notification_message += f"Location: {location}\n"
            
            notification_message += (
                f"\n{student_name} has cancelled their attendance for this session. "
                f"Please reach out to reschedule if needed."
            )
            
            try:
                twilio_client.send_message(
                    to=trainer_phone,
                    body=notification_message,
                )
                
                logger.info(
                    "Trainer notified of student cancellation",
                    student_id=student_id,
                    trainer_id=trainer_id,
                    session_id=session_id,
                    trainer_phone=trainer_phone,
                    request_id=request_id,
                )
            
            except Exception as e:
                logger.error(
                    "Failed to send cancellation notification to trainer",
                    student_id=student_id,
                    trainer_id=trainer_id,
                    session_id=session_id,
                    error=str(e),
                    request_id=request_id,
                )
                # Continue with student response even if notification fails
            
            # Send confirmation to student
            return (
                f"Your cancellation has been noted. ✅\n\n"
                f"Session: {date_str} at {time_str}\n"
                f"Trainer: {trainer_name}\n\n"
                f"Your trainer has been notified and will reach out to you shortly.\n\n"
                f"To reschedule, please contact your trainer directly."
            )
        
        except Exception as e:
            logger.error(
                "Failed to handle student cancellation",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "I'm having trouble processing your cancellation right now. "
                "Please contact your trainer directly to cancel your session."
            )
