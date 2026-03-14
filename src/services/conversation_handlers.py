"""
Conversation handlers for different user types.

This module implements three handler classes:
- OnboardingHandler: Handles trainer registration flow for new users
- TrainerHandler: Handles trainer menu and tool execution via AI agent
- StudentHandler: Handles student menu and session viewing

Each handler processes messages based on user type and conversation state,
integrating with StrandsAgentService for natural language understanding and tool execution.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

from services.strands_agent_service import StrandsAgentService
from services.conversation_state import ConversationStateManager
from models.dynamodb_client import DynamoDBClient
from models.entities import Trainer, Student
from utils.logging import get_logger
from utils.validation import PhoneNumberValidator
from config import settings

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
        if not state or state.state == "UNKNOWN":
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
        context = state.context
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
            "Bem-vindo ao FitAgent! 👋\n\n"
            "Sou seu assistente de IA para gerenciar sessões de treino e alunos.\n\n"
            "Você é:\n"
            "1️⃣ Personal Trainer\n"
            "2️⃣ Aluno\n\n"
            "Por favor, responda com 1 ou 2 para começar."
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
                "Ótimo! Vamos configurar sua conta como trainer. 💪\n\n"
                "Qual é o seu nome completo?"
            )
        
        # Check if user selected student
        elif "2" in message_text or "student" in message_text or "aluno" in message_text:
            # Students need to be registered by their trainer
            return (
                "Obrigado pelo seu interesse! 🙏\n\n"
                "Alunos são registrados por seus trainers. Por favor, peça ao seu trainer "
                "para adicioná-lo à lista de alunos, e ele fornecerá acesso.\n\n"
                "Se você é um trainer, por favor responda com '1' para se registrar."
            )
        
        else:
            # Invalid response
            return (
                "Não entendi isso. Por favor, responda com:\n"
                "1️⃣ para Personal Trainer\n"
                "2️⃣ para Aluno"
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
            return "Por favor, forneça seu nome completo (pelo menos 2 caracteres)."
        
        # Store name and move to next step
        state = self.state_manager.get_state(phone_number)
        context = state.context
        context["trainer_name"] = message_text.title()
        context["step"] = "trainer_email"
        
        self.state_manager.update_state(
            phone_number=phone_number,
            state="ONBOARDING",
            context=context,
        )
        
        return f"Prazer em conhecê-lo, {context['trainer_name']}! 👋\n\nQual é o seu endereço de e-mail?"
    
    def _handle_trainer_email(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer email collection."""
        # Basic email validation
        if "@" not in message_text or "." not in message_text:
            return "Por favor, forneça um endereço de e-mail válido (ex: trainer@example.com)."
        
        # Store email and move to next step
        state = self.state_manager.get_state(phone_number)
        context = state.context
        context["trainer_email"] = message_text.lower()
        context["step"] = "trainer_business"
        
        self.state_manager.update_state(
            phone_number=phone_number,
            state="ONBOARDING",
            context=context,
        )
        
        return "Perfeito! Qual é o nome do seu negócio? (É assim que os alunos verão você)"
    
    def _handle_trainer_business(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer business name and complete registration."""
        # Validate business name
        if len(message_text) < 2:
            return "Por favor, forneça o nome do seu negócio (pelo menos 2 caracteres)."
        
        # Get collected information
        state = self.state_manager.get_state(phone_number)
        context = state.context
        
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
                    "Houve um problema com o formato do seu número de telefone. "
                    "Por favor, entre em contato com o suporte para assistência."
                )
        
        # Create trainer record
        try:
            trainer_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            trainer = Trainer(
                trainer_id=trainer_id,
                name=trainer_name,
                email=trainer_email,
                business_name=business_name,
                phone_number=phone_number,
                created_at=now,
                updated_at=now,
            )
            
            # Save to DynamoDB (use to_dynamodb() method for proper formatting)
            self.dynamodb.put_trainer(trainer.to_dynamodb())
            
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
                f"🎉 Bem-vindo ao FitAgent, {trainer_name}!\n\n"
                f"Sua conta está ativa agora. Posso ajudá-lo com:\n\n"
                "📝 Registrar e gerenciar alunos\n"
                "📅 Agendar sessões de treino\n"
                "💰 Rastrear pagamentos\n"
                "🔔 Enviar notificações\n"
                "📆 Conectar seu calendário (Google/Outlook)\n\n"
                "O que você gostaria de fazer? Apenas me diga com suas próprias palavras!"
            )
        
        except Exception as e:
            logger.error(
                "Failed to register trainer",
                phone_number=phone_number,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "Desculpe, houve um erro ao criar sua conta. "
                "Por favor, tente novamente ou entre em contato com o suporte se o problema persistir."
            )


class TrainerHandler:
    """
    Handles trainer messages with AI agent integration.
    
    This handler:
    - Uses StrandsAgentService for natural language understanding
    - Executes tool functions based on trainer requests
    - Maintains conversation context across interactions
    - Provides trainer menu and capabilities
    
    Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
    """
    
    def __init__(
        self,
        agent_service: Optional[StrandsAgentService] = None,
        state_manager: Optional[ConversationStateManager] = None,
        dynamodb_client: Optional[DynamoDBClient] = None,
    ):
        """
        Initialize TrainerHandler.
        
        Args:
            agent_service: Strands agent service for natural language processing
            state_manager: Conversation state manager
            dynamodb_client: DynamoDB client for data operations
        """
        self.agent_service = agent_service or StrandsAgentService()
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
        Handle trainer message with Strands agent service.
        
        Args:
            trainer_id: Trainer's unique identifier
            user_data: Trainer's user record from DynamoDB
            message_body: Message payload from webhook
            request_id: Request ID for tracing
        
        Returns:
            Response text from Strands agent
        """
        logger.info(
            "Processing trainer message",
            trainer_id=trainer_id,
            request_id=request_id,
        )
        
        phone_number = user_data.get("phone_number")
        message_text = message_body.get("body", "").strip()
        
        # Process message with Strands agent service
        try:
            result = self.agent_service.process_message(
                trainer_id=trainer_id,
                message=message_text,
                phone_number=phone_number,
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
                    request_id=request_id,
                )
                
                return response_text
            
            else:
                # Strands agent service returned error
                error_message = result.get("error", "Unknown error")
                logger.error(
                    "Strands agent service returned error",
                    trainer_id=trainer_id,
                    error=error_message,
                    request_id=request_id,
                )
                
                return (
                    "Estou tendo problemas para processar sua solicitação agora. "
                    "Por favor, tente novamente ou reformule sua mensagem."
                )
        
        except Exception as e:
            logger.error(
                "Failed to process trainer message",
                trainer_id=trainer_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "Algo deu errado ao processar sua solicitação. "
                "Por favor, tente novamente em alguns instantes."
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
            f"Olá {student_name}! 👋\n\n"
            "Posso ajudá-lo com:\n\n"
            "📅 Ver próximas sessões\n"
            "✅ Confirmar presença\n"
            "❌ Cancelar presença\n\n"
            "O que você gostaria de fazer?"
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
                    f"Olá {student_name}! 👋\n\n"
                    "Você não tem sessões agendadas nos próximos 30 dias.\n\n"
                    "Entre em contato com seu trainer para agendar uma sessão!"
                )
            
            # Format sessions in chronological order
            response = f"Olá {student_name}! 👋\n\nSuas próximas sessões:\n\n"
            
            for i, session in enumerate(sessions, 1):
                session_datetime = datetime.fromisoformat(session.get("session_datetime"))
                trainer_name = session.get("trainer_name", "Seu trainer")
                location = session.get("location", "")
                duration = session.get("duration_minutes", 60)
                status = session.get("status", "scheduled")
                confirmed = session.get("student_confirmed", False)
                
                # Format date and time
                date_str = session_datetime.strftime("%A, %B %d")
                time_str = session_datetime.strftime("%I:%M %p")
                
                response += f"{i}. {date_str} às {time_str}\n"
                response += f"   Trainer: {trainer_name}\n"
                response += f"   Duração: {duration} minutos\n"
                
                if location:
                    response += f"   Local: {location}\n"
                
                if confirmed:
                    response += "   ✅ Confirmado\n"
                elif status == "scheduled":
                    response += "   ⏳ Aguardando confirmação\n"
                
                response += "\n"
            
            response += "Responda 'confirmar' para confirmar presença ou 'cancelar' para cancelar uma sessão."
            
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
                "Estou tendo problemas para recuperar suas sessões agora. "
                "Por favor, tente novamente em alguns instantes."
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
                    "Você não tem sessões futuras para confirmar. "
                    "Entre em contato com seu trainer para agendar uma sessão!"
                )
            
            # Find the next unconfirmed session
            unconfirmed_session = None
            for session in sessions:
                if not session.get("student_confirmed", False) and session.get("status") == "scheduled":
                    unconfirmed_session = session
                    break
            
            if not unconfirmed_session:
                return (
                    "Todas as suas próximas sessões já estão confirmadas! ✅\n\n"
                    "Se precisar fazer alterações, por favor entre em contato com seu trainer."
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
                f"✅ Presença confirmada!\n\n"
                f"Sessão: {date_str} às {time_str}\n"
                f"Trainer: {trainer_name}\n\n"
                f"Te vejo lá! 💪"
            )
        
        except Exception as e:
            logger.error(
                "Failed to confirm student attendance",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "Estou tendo problemas para confirmar sua presença agora. "
                "Por favor, tente novamente em alguns instantes."
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
                    "Você não tem sessões futuras para cancelar. "
                    "Se precisar fazer alterações, por favor entre em contato com seu trainer."
                )
            
            # Find the next scheduled session
            next_session = None
            for session in sessions:
                if session.get("status") == "scheduled":
                    next_session = session
                    break
            
            if not next_session:
                return (
                    "Você não tem sessões agendadas para cancelar. "
                    "Se precisar fazer alterações, por favor entre em contato com seu trainer."
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
                    "Estou tendo problemas para processar seu cancelamento. "
                    "Por favor, entre em contato com seu trainer diretamente."
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
                f"⚠️ Aviso de Cancelamento de Sessão\n\n"
                f"Aluno: {student_name}\n"
                f"Data: {date_str}\n"
                f"Hora: {time_str}\n"
                f"Duração: {duration} minutos\n"
            )
            
            if location:
                notification_message += f"Local: {location}\n"
            
            notification_message += (
                f"\n{student_name} cancelou a presença nesta sessão. "
                f"Por favor, entre em contato para reagendar se necessário."
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
                f"Seu cancelamento foi registrado. ✅\n\n"
                f"Sessão: {date_str} às {time_str}\n"
                f"Trainer: {trainer_name}\n\n"
                f"Seu trainer foi notificado e entrará em contato com você em breve.\n\n"
                f"Para reagendar, por favor entre em contato com seu trainer diretamente."
            )
        
        except Exception as e:
            logger.error(
                "Failed to handle student cancellation",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            
            return (
                "Estou tendo problemas para processar seu cancelamento agora. "
                "Por favor, entre em contato com seu trainer diretamente para cancelar sua sessão."
            )
