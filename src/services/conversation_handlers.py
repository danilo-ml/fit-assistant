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
        
        elif step == "trainer_info":
            return self._handle_trainer_info(phone_number, message_body.get("body", "").strip(), request_id)
        
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
            # Start trainer registration - ask all info at once
            self.state_manager.update_state(
                phone_number=phone_number,
                state="ONBOARDING",
                context={"step": "trainer_info", "user_type": "trainer"},
            )
            
            return (
                "Ótimo! Vamos configurar sua conta como trainer. 💪\n\n"
                "Por favor, envie as seguintes informações (uma por linha):\n\n"
                "1️⃣ Nome completo\n"
                "2️⃣ E-mail\n"
                "3️⃣ Nome do seu negócio\n\n"
                "Exemplo:\n"
                "João Silva\n"
                "joao@email.com\n"
                "João Personal Trainer"
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
    
    def _handle_trainer_info(
        self,
        phone_number: str,
        message_text: str,
        request_id: str,
    ) -> str:
        """Handle trainer info collection (name, email, business name) in a single message."""
        lines = [line.strip() for line in message_text.strip().splitlines() if line.strip()]

        if len(lines) < 3:
            return (
                "Não consegui identificar todas as informações. "
                "Por favor, envie as 3 informações, uma por linha:\n\n"
                "1️⃣ Nome completo\n"
                "2️⃣ E-mail\n"
                "3️⃣ Nome do seu negócio\n\n"
                "Exemplo:\n"
                "João Silva\n"
                "joao@email.com\n"
                "João Personal Trainer"
            )

        trainer_name = lines[0].title()
        trainer_email = lines[1].lower()
        business_name = lines[2].title()

        # Validate name
        if len(trainer_name) < 2:
            return "O nome precisa ter pelo menos 2 caracteres. Por favor, envie as 3 informações novamente."

        # Validate email
        if "@" not in trainer_email or "." not in trainer_email:
            return (
                "O e-mail informado não parece válido. "
                "Por favor, envie as 3 informações novamente com um e-mail válido (ex: trainer@example.com)."
            )

        # Validate business name
        if len(business_name) < 2:
            return "O nome do negócio precisa ter pelo menos 2 caracteres. Por favor, envie as 3 informações novamente."

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
        
        # Intercept calendar sync requests directly to avoid AI hallucinating OAuth URLs
        calendar_response = self._handle_calendar_sync_if_requested(
            trainer_id, message_text, request_id
        )
        if calendar_response:
            self.state_manager.update_state(
                phone_number=phone_number,
                state="TRAINER_MENU",
                user_id=trainer_id,
                user_type="TRAINER",
                message={"role": "user", "content": message_text},
            )
            self.state_manager.update_state(
                phone_number=phone_number,
                state="TRAINER_MENU",
                user_id=trainer_id,
                user_type="TRAINER",
                message={"role": "assistant", "content": calendar_response},
            )
            return calendar_response
        
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
    
    def _handle_calendar_sync_if_requested(
        self,
        trainer_id: str,
        message_text: str,
        request_id: str,
    ) -> Optional[str]:
        """
        Detect calendar sync requests and handle them directly.
        
        This bypasses the AI agent to prevent hallucinated OAuth URLs.
        Calls connect_calendar tool directly and formats the response.
        
        Returns:
            Formatted response with real OAuth URL, or None if not a calendar request.
        """
        text_lower = message_text.lower()
        
        # Detect calendar sync intent
        calendar_keywords = ["sincronizar", "sincroniza", "sync", "conectar calendario",
                             "conectar calendário", "calendar", "google calendar",
                             "outlook calendar", "vincular calendario", "vincular calendário"]
        
        if not any(kw in text_lower for kw in calendar_keywords):
            return None
        
        # Determine provider
        if "outlook" in text_lower or "microsoft" in text_lower:
            provider = "outlook"
            provider_name = "Outlook"
        else:
            provider = "google"
            provider_name = "Google Calendar"
        
        logger.info(
            "Calendar sync request intercepted",
            trainer_id=trainer_id,
            provider=provider,
            request_id=request_id,
        )
        
        try:
            from tools.calendar_tools import connect_calendar
            result = connect_calendar(trainer_id, provider)
            
            if result.get("success"):
                oauth_url = result["data"]["oauth_url"]
                return (
                    f"Para conectar seu {provider_name}, clique no link abaixo para autorizar o acesso:\n\n"
                    f"{oauth_url}\n\n"
                    f"O link expira em 30 minutos. Após autorizar, seu calendário será "
                    f"sincronizado automaticamente com suas sessões de treino."
                )
            else:
                error = result.get("error", "Erro desconhecido")
                logger.error(
                    "Calendar connect_calendar failed",
                    trainer_id=trainer_id,
                    error=error,
                    request_id=request_id,
                )
                return (
                    f"Não foi possível gerar o link de conexão com o {provider_name}: {error}\n\n"
                    "Por favor, tente novamente ou entre em contato com o suporte."
                )
        except Exception as e:
            logger.error(
                "Calendar sync interception error",
                trainer_id=trainer_id,
                error=str(e),
                request_id=request_id,
            )
            return (
                f"Ocorreu um erro ao tentar conectar seu {provider_name}. "
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
        has_media = int(message_body.get("num_media", 0)) > 0
        media_urls = message_body.get("media_urls", [])
        
        # Check conversation state for pending payment context
        state = self.state_manager.get_state(phone_number)
        pending_payment = state.context.get("pending_payment") if state and state.context else None
        
        # If student sends media (image/pdf) -> treat as payment receipt
        if has_media and media_urls:
            return self._handle_payment_receipt(
                student_id=student_id,
                user_data=user_data,
                message_body=message_body,
                media_urls=media_urls,
                request_id=request_id,
            )
        
        # If there's a pending payment waiting for reference month
        if pending_payment and pending_payment.get("awaiting_reference_month"):
            return self._handle_reference_month_response(
                student_id=student_id,
                user_data=user_data,
                message_text=message_text,
                pending_payment=pending_payment,
                request_id=request_id,
            )
        
        # Payment-related keywords (PT-BR)
        payment_keywords = [
            "paguei", "pago", "pagamento", "pix", "transferi",
            "comprovante", "recibo", "boleto", "transferência",
        ]
        if any(word in message_text for word in payment_keywords):
            return (
                "Para registrar seu pagamento, por favor envie o comprovante "
                "(foto do Pix, transferência ou recibo) aqui neste chat. 📸"
            )
        
        # Simple keyword-based routing for student actions
        if any(word in message_text for word in ["session", "schedule", "upcoming", "next",
                                                   "sessão", "sessões", "agenda", "próxima",
                                                   "treino", "treinos"]):
            return self._view_upcoming_sessions(student_id, student_name, request_id)
        
        elif any(word in message_text for word in ["confirm", "yes", "attending",
                                                     "confirmar", "sim", "presença"]):
            return self._handle_confirmation(student_id, message_text, request_id)
        
        elif any(word in message_text for word in ["cancel", "can't make", "cannot",
                                                     "cancelar", "não posso", "não vou"]):
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
            "❌ Cancelar presença\n"
            "💰 Enviar comprovante de pagamento\n\n"
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

    def _handle_payment_receipt(
        self,
        student_id: str,
        user_data: Dict[str, Any],
        message_body: Dict[str, Any],
        media_urls: list,
        request_id: str,
    ) -> str:
        """
        Handle payment receipt submission from student.

        Stores the receipt in S3, determines the reference month,
        creates a pending payment record, and notifies the trainer
        to confirm receipt.
        """
        from services.receipt_storage import ReceiptStorageService
        from services.twilio_client import TwilioClient

        phone_number = user_data.get("phone_number")
        student_name = user_data.get("name", "Aluno")

        try:
            # Find trainer(s) linked to this student
            trainer_links = self._get_student_trainer_links(student_id)
            if not trainer_links:
                return (
                    "Não encontrei nenhum trainer vinculado à sua conta. "
                    "Por favor, entre em contato com seu trainer."
                )

            # Use first active trainer (most common case: 1 trainer per student)
            trainer_id = trainer_links[0]["trainer_id"]
            trainer = self.dynamodb.get_trainer(trainer_id)
            if not trainer:
                return "Erro ao localizar seu trainer. Tente novamente."

            trainer_phone = trainer.get("phone_number")
            trainer_name = trainer.get("name", "Trainer")

            # Store receipt media in S3
            receipt_service = ReceiptStorageService()
            media = media_urls[0]  # Use first media attachment
            media_url = media.get("url", "")
            media_type = media.get("content_type", "image/jpeg")

            receipt_result = receipt_service.store_receipt(
                trainer_id=trainer_id,
                student_id=student_id,
                media_url=media_url,
                media_type=media_type,
            )

            s3_key = receipt_result.get("s3_key", "")

            # Check message text for reference month hint
            message_text = message_body.get("body", "").strip()
            reference_month = self._extract_reference_month(message_text)

            if not reference_month:
                # Save pending state and ask for reference month
                self.state_manager.update_state(
                    phone_number=phone_number,
                    state="STUDENT_MENU",
                    user_id=student_id,
                    user_type="STUDENT",
                    context={
                        "pending_payment": {
                            "awaiting_reference_month": True,
                            "trainer_id": trainer_id,
                            "s3_key": s3_key,
                            "media_type": media_type,
                        }
                    },
                )
                return (
                    "Recebi seu comprovante! 📄\n\n"
                    "Para qual mês de referência é esse pagamento?\n"
                    "Exemplo: março 2026, 03/2026"
                )

            # All info available — register and notify trainer
            return self._register_and_notify_payment(
                student_id=student_id,
                student_name=student_name,
                trainer_id=trainer_id,
                trainer_phone=trainer_phone,
                trainer_name=trainer_name,
                s3_key=s3_key,
                media_type=media_type,
                reference_month=reference_month,
                phone_number=phone_number,
            )

        except Exception as e:
            logger.error(
                "Failed to process payment receipt",
                student_id=student_id,
                error=str(e),
                request_id=request_id,
            )
            return (
                "Tive um problema ao processar seu comprovante. "
                "Por favor, tente enviar novamente."
            )

    def _handle_reference_month_response(
        self,
        student_id: str,
        user_data: Dict[str, Any],
        message_text: str,
        pending_payment: dict,
        request_id: str,
    ) -> str:
        """Handle student's response with the reference month for a pending receipt."""
        phone_number = user_data.get("phone_number")
        student_name = user_data.get("name", "Aluno")
        trainer_id = pending_payment.get("trainer_id")
        s3_key = pending_payment.get("s3_key")
        media_type = pending_payment.get("media_type", "image/jpeg")

        reference_month = self._extract_reference_month(message_text)
        if not reference_month:
            return (
                "Não consegui identificar o mês. Por favor, informe no formato:\n"
                "março 2026 ou 03/2026"
            )

        trainer = self.dynamodb.get_trainer(trainer_id)
        if not trainer:
            return "Erro ao localizar seu trainer. Tente novamente."

        trainer_phone = trainer.get("phone_number")
        trainer_name = trainer.get("name", "Trainer")

        # Clear pending state
        self.state_manager.update_state(
            phone_number=phone_number,
            state="STUDENT_MENU",
            user_id=student_id,
            user_type="STUDENT",
            context={"pending_payment": None},
        )

        return self._register_and_notify_payment(
            student_id=student_id,
            student_name=student_name,
            trainer_id=trainer_id,
            trainer_phone=trainer_phone,
            trainer_name=trainer_name,
            s3_key=s3_key,
            media_type=media_type,
            reference_month=reference_month,
            phone_number=phone_number,
        )

    def _register_and_notify_payment(
        self,
        student_id: str,
        student_name: str,
        trainer_id: str,
        trainer_phone: str,
        trainer_name: str,
        s3_key: str,
        media_type: str,
        reference_month: str,
        phone_number: str,
    ) -> str:
        """
        Create a pending payment record and notify the trainer to confirm.
        """
        from models.entities import Payment
        from services.twilio_client import TwilioClient
        from services.receipt_storage import ReceiptStorageService

        now = datetime.utcnow()

        # Create payment record with status pending_trainer_confirmation
        payment = Payment(
            trainer_id=trainer_id,
            student_id=student_id,
            student_name=student_name,
            amount=0,  # Trainer will confirm the amount
            currency="BRL",
            payment_date=now.strftime("%Y-%m-%d"),
            payment_status="pending",
            receipt_s3_key=s3_key,
            receipt_media_type=media_type,
        )

        self.dynamodb.put_payment(payment.to_dynamodb())

        # Generate presigned URL for the receipt so trainer can view it
        receipt_service = ReceiptStorageService()
        try:
            receipt_url = receipt_service.get_receipt_url(s3_key, expiration=86400)
        except Exception:
            receipt_url = None

        # Notify trainer via WhatsApp
        twilio = TwilioClient()
        notification = (
            f"💳 Comprovante de Pagamento Recebido\n\n"
            f"Aluno: {student_name}\n"
            f"Mês referência: {reference_month}\n"
            f"ID do pagamento: {payment.payment_id}\n\n"
        )
        if receipt_url:
            notification += f"📎 Comprovante: {receipt_url}\n\n"
        notification += (
            f"Para confirmar o recebimento, envie:\n"
            f"\"confirmar pagamento {payment.payment_id}\""
        )

        try:
            twilio.send_message(to=trainer_phone, body=notification)
        except Exception as e:
            logger.error(
                "Failed to notify trainer about payment",
                trainer_id=trainer_id,
                error=str(e),
            )

        logger.info(
            "Payment receipt processed and trainer notified",
            student_id=student_id,
            trainer_id=trainer_id,
            payment_id=payment.payment_id,
            reference_month=reference_month,
        )

        return (
            f"✅ Comprovante recebido e enviado para {trainer_name}!\n\n"
            f"Mês referência: {reference_month}\n"
            f"Seu trainer irá confirmar o recebimento em breve."
        )

    def _get_student_trainer_links(self, student_id: str) -> list:
        """Get active trainer links for a student."""
        from boto3.dynamodb.conditions import Attr

        try:
            response = self.dynamodb.table.scan(
                FilterExpression=Attr("entity_type").eq("TRAINER_STUDENT_LINK")
                & Attr("student_id").eq(student_id)
                & Attr("status").eq("active")
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error("Failed to get trainer links", student_id=student_id, error=str(e))
            return []

    @staticmethod
    def _extract_reference_month(text: str) -> str:
        """
        Extract reference month from text.

        Supports formats like:
        - "março 2026", "marco 2026"
        - "03/2026", "3/2026"
        - "março", "mar" (assumes current year)

        Returns:
            Formatted string like "03/2026" or empty string if not found.
        """
        import re

        text = text.strip().lower()

        month_names = {
            "janeiro": "01", "jan": "01",
            "fevereiro": "02", "fev": "02",
            "março": "03", "marco": "03", "mar": "03",
            "abril": "04", "abr": "04",
            "maio": "05", "mai": "05",
            "junho": "06", "jun": "06",
            "julho": "07", "jul": "07",
            "agosto": "08", "ago": "08",
            "setembro": "09", "set": "09",
            "outubro": "10", "out": "10",
            "novembro": "11", "nov": "11",
            "dezembro": "12", "dez": "12",
        }

        # Try MM/YYYY or M/YYYY
        match = re.search(r'(\d{1,2})\s*/\s*(\d{4})', text)
        if match:
            month = match.group(1).zfill(2)
            year = match.group(2)
            if 1 <= int(month) <= 12:
                return f"{month}/{year}"

        # Try "month_name year"
        for name, num in month_names.items():
            if name in text:
                year_match = re.search(r'(\d{4})', text)
                year = year_match.group(1) if year_match else str(datetime.utcnow().year)
                return f"{num}/{year}"

        return ""
