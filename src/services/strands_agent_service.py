"""
Strands Agent Service for FitAgent.

This service provides a simple interface for processing trainer messages using
the official strands-agents SDK. It implements a single-agent architecture with
all FitAgent tools registered, multi-tenancy enforcement via trainer_id injection,
and PT-BR (Brazilian Portuguese) language support.

Key Features:
- Single agent with all tools (student, session, payment management)
- Multi-tenancy via trainer_id injection into tool execution (agent created per-request)
- Timeout protection (10-second limit for WhatsApp compatibility)
- Structured logging for all operations
- PT-BR system prompt for Brazilian Portuguese responses
- Error handling with user-friendly messages

Requirements: 3.1, 3.3, 5.1, 6.4, 7.1, 7.4, 7.6
"""

import signal
import os
from typing import Dict, Any, Optional
from datetime import datetime

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel
from botocore.exceptions import ClientError

from tools import student_tools, session_tools, payment_tools, calendar_tools
from models.dynamodb_client import DynamoDBClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


class TimeoutError(Exception):
    """Raised when agent execution exceeds timeout limit."""
    pass


class StrandsAgentService:
    """
    Service for processing trainer messages using Strands Agents SDK.
    
    Provides a simple interface for WhatsApp message processing with:
    - Single agent with all FitAgent tools
    - Multi-tenancy via trainer_id injection
    - Error handling and timeout protection
    - Structured logging
    - PT-BR (Brazilian Portuguese) responses
    
    Example:
        service = StrandsAgentService()
        result = service.process_message(
            trainer_id='abc123',
            message='Registrar novo aluno João',
            phone_number='+5511999999999'
        )
        # Returns: {'success': True, 'response': 'Aluno João registrado com sucesso!'}
    """
    
    def __init__(
        self,
        model_id: str = None,
        region: str = None,
        endpoint_url: str = None
    ):
        """
        Initialize Strands Agent Service with Bedrock configuration and PT-BR system prompt.
        
        Args:
            model_id: Bedrock model ID (defaults to settings.bedrock_model_id)
            region: AWS region (defaults to settings.bedrock_region)
            endpoint_url: Bedrock endpoint URL (defaults to settings.aws_bedrock_endpoint_url)
        """
        self.model_id = model_id or settings.bedrock_model_id
        self.region = region or settings.bedrock_region
        self.endpoint_url = endpoint_url or settings.aws_bedrock_endpoint_url
        
        # Initialize DynamoDB client for tool execution
        self.db_client = DynamoDBClient(
            table_name=settings.dynamodb_table,
            endpoint_url=settings.aws_endpoint_url
        )
        
        # Temporarily remove AWS_ENDPOINT_URL to prevent Bedrock from using LocalStack
        # Save original value to restore after BedrockModel initialization
        original_endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        if original_endpoint_url:
            del os.environ['AWS_ENDPOINT_URL']
        
        try:
            # Create Bedrock model instance (reused across requests)
            # With AWS_ENDPOINT_URL removed, boto3 will use real AWS endpoints
            try:
                self.model = BedrockModel(
                    model_id=self.model_id,
                    region_name=self.region,
                    endpoint_url=self.endpoint_url
                )
            except ValueError as e:
                # Handle OpenTelemetry propagator initialization errors
                # This can occur in Lambda environments where some propagators are not available
                if "Propagator" in str(e) and "not found" in str(e):
                    logger.warning(
                        "OpenTelemetry propagator initialization failed, continuing with degraded tracing",
                        error=str(e)
                    )
                    # Retry initialization - the patched OpenTelemetry should skip missing propagators
                    self.model = BedrockModel(
                        model_id=self.model_id,
                        region_name=self.region,
                        endpoint_url=self.endpoint_url
                    )
                else:
                    # Re-raise if it's a different ValueError
                    raise
        finally:
            # Restore AWS_ENDPOINT_URL for other services (DynamoDB, S3, SQS)
            if original_endpoint_url:
                os.environ['AWS_ENDPOINT_URL'] = original_endpoint_url
        
        # PT-BR system prompt for Brazilian Portuguese responses
        self.system_prompt = """Você é um assistente de IA para personal trainers no Brasil.

Sua função é ajudar personal trainers a gerenciar seus negócios através do WhatsApp:
- Registrar e gerenciar alunos
- Agendar, reagendar e cancelar sessões de treino
- Registrar e acompanhar pagamentos
- Visualizar calendário e compromissos

IMPORTANTE:
- Sempre responda em português brasileiro (PT-BR)
- Seja claro, objetivo e amigável
- Otimize a experiência do usuário, se for pedir informações peça de uma vez só e não enviar em várias mensagens
- Use as ferramentas disponíveis para executar as ações solicitadas
- Confirme as ações realizadas com detalhes relevantes
- Se houver erro, explique de forma clara e sugira alternativas. Não devolva erro sistemico para o usuário final
- CADA mensagem é independente - não há histórico de conversa anterior
- Se o usuário responder com informações incompletas (ex: "próximo mês"), peça esclarecimento sobre qual ação ele quer realizar

REGRA CRÍTICA - Coleta de Informações:
- NUNCA invente ou assuma informações que o usuário não forneceu
- Se uma ferramenta requer parâmetros OBRIGATÓRIOS que não foram fornecidos, PERGUNTE ao usuário
- Parâmetros OPCIONAIS podem ser omitidos (deixe como None/null)
- Para registrar aluno, você PRECISA de: nome completo, telefone (formato +5511999999999), email, e objetivo de treino
- Para agendar sessão, você PRECISA de: student_id (ID do aluno), data/hora (formato ISO), duração em minutos
- Para agendar sessão, são OPCIONAIS: local (location) e observações (notes)
- Para registrar pagamento, você PRECISA de: student_id, valor, data, método de pagamento
- Se faltar qualquer informação OBRIGATÓRIA, pergunte de forma clara e específica
- SEMPRE confirme os detalhes antes de executar ações importantes

Quando o trainer solicitar uma ação:
1. Identifique a ferramenta apropriada
2. Verifique se você tem TODAS as informações necessárias
3. Se faltar informação, PERGUNTE antes de executar
4. Execute a ferramenta SOMENTE quando tiver todos os dados
5. Confirme o resultado em linguagem natural

Exemplos de interações:
- "Registrar novo aluno João" → PERGUNTE: "Para registrar o aluno João, preciso do telefone (formato +5511999999999), email e objetivo de treino. Pode me passar essas informações?"
- "Registrar aluno João Silva, telefone +5511988887777, email joao@email.com, objetivo: ganhar massa" → use register_student com todos os parâmetros
- "Agendar sessão com Juliana Nano dia 11/03/2026 às 08:00, 60 minutos" → use schedule_session com student_name="Juliana Nano", date="2026-03-11", time="08:00", duration_minutes=60
- "Agendar sessão semanalmente toda terça-feira com Juliana Nano às 18:00, 60 minutos" → use schedule_recurring_session com student_name="Juliana Nano", day_of_week="terça-feira", time="18:00", duration_minutes=60, number_of_weeks=4 (ou pergunte quantas semanas)
- "Cancelar sessão xyz789" → use cancel_session
- "Ver meus alunos" → use view_students
- "Registrar pagamento de R$100 do Pedro" → use register_payment

IMPORTANTE - Agendamentos Recorrentes:
- Para sessões semanais/recorrentes, use schedule_recurring_session
- Pergunte quantas semanas agendar se não especificado (sugestão: 4 semanas = 1 mês)
- Dias da semana aceitos: segunda-feira, terça-feira, quarta-feira, quinta-feira, sexta-feira, sábado, domingo
- A ferramenta cria múltiplas sessões automaticamente e detecta conflitos

IMPORTANTE - Busca de Alunos:
- Quando o usuário mencionar o NOME de um aluno (ex: "Juliana Nano", "Pedro"), use schedule_session ou schedule_recurring_session diretamente com student_name
- NUNCA assuma ou invente um student_id
- Após encontrar o aluno na lista, use o student_id retornado para agendar sessões ou registrar pagamentos
"""
        
        logger.info(
            "StrandsAgentService initialized",
            model_id=self.model_id,
            region=self.region,
            has_endpoint=bool(self.endpoint_url)
        )
    
    def _create_agent_for_trainer(self, trainer_id: str) -> Agent:
        """
        Create a Strands Agent with tools bound to a specific trainer_id.
        
        This method creates wrapper tools that inject trainer_id while preserving
        the @tool decorator metadata that Strands requires.
        
        Args:
            trainer_id: Trainer identifier to inject into all tool calls
            
        Returns:
            Configured Agent instance with trainer-specific tools
        """
        from strands import tool
        from datetime import datetime, timezone, timedelta
        
        # Get current date/time in Brazil timezone (UTC-3)
        brazil_offset = timezone(timedelta(hours=-3))
        now = datetime.now(brazil_offset)
        current_date = now.strftime('%d/%m/%Y')
        current_time = now.strftime('%H:%M')
        current_datetime_iso = now.strftime('%Y-%m-%dT%H:%M:%S')
        day_of_week = now.strftime('%A')
        
        # Map English day names to Portuguese
        day_names = {
            'Monday': 'Segunda-feira',
            'Tuesday': 'Terça-feira',
            'Wednesday': 'Quarta-feira',
            'Thursday': 'Quinta-feira',
            'Friday': 'Sexta-feira',
            'Saturday': 'Sábado',
            'Sunday': 'Domingo'
        }
        day_of_week_pt = day_names.get(day_of_week, day_of_week)
        
        # Add current date/time context to system prompt
        system_prompt_with_context = f"""{self.system_prompt}

CONTEXTO TEMPORAL ATUAL:
- Data de hoje: {current_date} ({day_of_week_pt})
- Hora atual: {current_time} (horário de Brasília, UTC-3)
- Hora atual UTC: {current_datetime_iso}

IMPORTANTE - Interpretação de Datas e Horários:
- O usuário fornece horários no fuso horário de Brasília (UTC-3)
- As ferramentas esperam horários em UTC
- SEMPRE adicione 3 horas ao horário fornecido pelo usuário antes de chamar as ferramentas
- Exemplo: usuário diz "19:00" → use "22:00:00" na ferramenta (19:00 + 3 horas)
- Exemplo: usuário diz "hoje às 08:00" → use "{current_date}T11:00:00" (08:00 + 3 horas)
- Quando o usuário mencionar "hoje" = {current_date}
- Quando o usuário mencionar "amanhã" = dia seguinte a {current_date}
- Formato de data/hora para ferramentas: YYYY-MM-DDTHH:MM:SS em UTC
- NUNCA altere datas fornecidas pelo usuário, apenas converta o horário para UTC
"""
        
        # Create wrapper functions that inject trainer_id
        # Each wrapper preserves the original function's signature (minus trainer_id)
        # and is decorated with @tool so Strands can recognize it
        
        @tool
        def register_student(name: str, phone_number: str, email: str, training_goal: str) -> Dict[str, Any]:
            """Register a new student and link them to the trainer."""
            return student_tools.register_student(trainer_id, name, phone_number, email, training_goal)
        
        @tool
        def view_students() -> Dict[str, Any]:
            """View all students linked to the trainer."""
            return student_tools.view_students(trainer_id)
        
        @tool
        def update_student(
            student_id: str,
            name: str = None,
            email: str = None,
            phone_number: str = None,
            training_goal: str = None
        ) -> Dict[str, Any]:
            """Update student information."""
            return student_tools.update_student(trainer_id, student_id, name, email, phone_number, training_goal)
        
        @tool
        def schedule_session(
            student_name: str,
            date: str,
            time: str,
            duration_minutes: int,
            location: str = None
        ) -> Dict[str, Any]:
            """Schedule a new training session."""
            return session_tools.schedule_session(trainer_id, student_name, date, time, duration_minutes, location)
        
        @tool
        def schedule_recurring_session(
            student_name: str,
            day_of_week: str,
            time: str,
            duration_minutes: int,
            number_of_weeks: int,
            location: str = None
        ) -> Dict[str, Any]:
            """Schedule recurring training sessions on the same day and time each week."""
            return session_tools.schedule_recurring_session(trainer_id, student_name, day_of_week, time, duration_minutes, number_of_weeks, location)
        
        @tool
        def reschedule_session(
            session_id: str,
            new_date: str,
            new_time: str
        ) -> Dict[str, Any]:
            """Reschedule an existing training session."""
            return session_tools.reschedule_session(trainer_id, session_id, new_date, new_time)
        
        @tool
        def cancel_session(session_id: str, reason: str = None) -> Dict[str, Any]:
            """Cancel a training session."""
            return session_tools.cancel_session(trainer_id, session_id, reason)
        
        @tool
        def view_calendar(start_date: str = None, end_date: str = None, filter: str = None) -> Dict[str, Any]:
            """View training sessions in the calendar."""
            return session_tools.view_calendar(trainer_id, start_date, end_date, filter)
        
        @tool
        def register_payment(
            student_id: str,
            amount: float,
            payment_date: str,
            payment_method: str,
            reference_month: str = None,
            notes: str = None
        ) -> Dict[str, Any]:
            """Register a payment from a student."""
            return payment_tools.register_payment(trainer_id, student_id, amount, payment_date, payment_method, reference_month, notes)
        
        @tool
        def confirm_payment(payment_id: str) -> Dict[str, Any]:
            """Confirm a payment."""
            return payment_tools.confirm_payment(trainer_id, payment_id)
        
        @tool
        def view_payments(
            student_id: str = None,
            status: str = None,
            start_date: str = None,
            end_date: str = None
        ) -> Dict[str, Any]:
            """View payment records."""
            return payment_tools.view_payments(trainer_id, student_id, status, start_date, end_date)
        
        @tool
        def connect_calendar(provider: str) -> Dict[str, Any]:
            """Connect Google Calendar or Outlook Calendar to sync training sessions."""
            return calendar_tools.connect_calendar(trainer_id, provider)
        
        # Collect all wrapper tools
        tools = [
            register_student,
            view_students,
            update_student,
            schedule_session,
            schedule_recurring_session,
            reschedule_session,
            cancel_session,
            view_calendar,
            register_payment,
            confirm_payment,
            view_payments,
            connect_calendar,
        ]
        
        # Create agent with system prompt and trainer-specific tools
        agent = Agent(
            model=self.model,
            system_prompt=system_prompt_with_context,
            tools=tools
        )
        
        logger.info(
            "Strands Agent created with context",
            trainer_id=trainer_id,
            tool_count=len(tools)
        )
        
        return agent
    
    def _timeout_handler(self, signum, frame):
        """
        Signal handler for timeout protection.
        
        Raises TimeoutError when execution exceeds 30 seconds.
        """
        raise TimeoutError("Agent execution exceeded 30 seconds")
    
    def process_message(
        self,
        trainer_id: str,
        message: str,
        phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a WhatsApp message through the Strands agent.
        
        This method:
        1. Validates trainer_id
        2. Injects trainer_id into tool execution context
        3. Executes agent with 10-second timeout protection
        4. Returns natural language response in PT-BR
        5. Handles errors gracefully with user-friendly messages
        
        Args:
            trainer_id: Trainer identifier for multi-tenancy (required)
            message: User's WhatsApp message in PT-BR (required)
            phone_number: Phone number for logging (optional)
            
        Returns:
            {
                'success': bool,
                'response': str,  # Natural language response in PT-BR
                'error': str      # Optional error message in PT-BR (only if success=False)
            }
            
        Example:
            >>> service.process_message(
            ...     trainer_id='abc123',
            ...     message='Registrar novo aluno João Silva',
            ...     phone_number='+5511999999999'
            ... )
            {
                'success': True,
                'response': 'Aluno João Silva registrado com sucesso! ID: def456'
            }
        """
        start_time = datetime.utcnow()
        
        logger.info(
            "Processing message",
            trainer_id=trainer_id,
            phone_number=phone_number,
            message_length=len(message) if message else 0
        )
        
        try:
            # Validate trainer_id
            if not trainer_id or not isinstance(trainer_id, str) or not trainer_id.strip():
                logger.warning(
                    "Invalid trainer_id",
                    trainer_id=trainer_id,
                    phone_number=phone_number
                )
                return {
                    'success': False,
                    'error': 'Não foi possível processar sua solicitação. Por favor, tente novamente.'
                }
            
            # Validate message
            if not message or not isinstance(message, str) or not message.strip():
                logger.warning(
                    "Invalid or empty message",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    message_value=message
                )
                return {
                    'success': False,
                    'error': 'Mensagem vazia ou inválida. Por favor, envie uma mensagem válida.'
                }
            
            # Verify trainer exists - handle DynamoDB errors
            try:
                trainer = self.db_client.get_trainer(trainer_id)
                if not trainer:
                    logger.warning(
                        "Trainer not found",
                        trainer_id=trainer_id,
                        phone_number=phone_number
                    )
                    return {
                        'success': False,
                        'error': 'Trainer não encontrado. Por favor, verifique seu cadastro.'
                    }
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                # Handle DynamoDB throttling
                if error_code == 'ProvisionedThroughputExceededException':
                    logger.error(
                        "DynamoDB throttling error",
                        trainer_id=trainer_id,
                        phone_number=phone_number,
                        error_code=error_code
                    )
                    return {
                        'success': False,
                        'error': 'O serviço está temporariamente indisponível devido ao alto volume de requisições. Por favor, tente novamente em alguns instantes.'
                    }
                
                # Handle resource not found
                elif error_code == 'ResourceNotFoundException':
                    logger.error(
                        "DynamoDB resource not found",
                        trainer_id=trainer_id,
                        phone_number=phone_number,
                        error_code=error_code
                    )
                    return {
                        'success': False,
                        'error': 'Serviço temporariamente indisponível. Por favor, tente novamente.'
                    }
                
                # Handle other DynamoDB errors
                else:
                    logger.error(
                        "DynamoDB error",
                        trainer_id=trainer_id,
                        phone_number=phone_number,
                        error_code=error_code,
                        error_message=str(e)
                    )
                    return {
                        'success': False,
                        'error': 'Serviço temporariamente indisponível. Por favor, tente novamente.'
                    }
            
            # Create agent with trainer-specific tools (multi-tenancy enforcement)
            agent = self._create_agent_for_trainer(trainer_id)
            
            # Set up timeout protection (30 seconds - increased from 10 for complex operations)
            # Note: WhatsApp has ~20s timeout, but we allow 30s for complex multi-tool operations
            signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(30)
            
            try:
                # Execute agent with message
                # Strands agents are called like functions: agent(prompt)
                # The agent will automatically use tools as needed
                bedrock_start_time = datetime.utcnow()
                agent_result = agent(message)
                bedrock_execution_time = (datetime.utcnow() - bedrock_start_time).total_seconds()
                
                logger.info(
                    "Bedrock execution completed",
                    trainer_id=trainer_id,
                    bedrock_time_seconds=bedrock_execution_time
                )
                
                # Extract response text from AgentResult object
                # AgentResult has a 'text' or 'content' attribute with the response
                if hasattr(agent_result, 'text'):
                    response_text = agent_result.text
                elif hasattr(agent_result, 'content'):
                    response_text = agent_result.content
                elif isinstance(agent_result, str):
                    response_text = agent_result
                else:
                    # Fallback: convert to string
                    response_text = str(agent_result)
                
                # Cancel timeout alarm
                signal.alarm(0)
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(
                    "Message processed successfully",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    execution_time_seconds=execution_time,
                    response_length=len(response_text)
                )
                
                return {
                    'success': True,
                    'response': response_text
                }
                
            except TimeoutError:
                signal.alarm(0)  # Cancel alarm
                
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                logger.error(
                    "Agent execution timeout",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    timeout_seconds=30,
                    execution_time_seconds=execution_time,
                    message_preview=message[:100] if message else None
                )
                
                return {
                    'success': False,
                    'error': 'A solicitação demorou muito para processar. Por favor, tente novamente com uma mensagem mais simples.'
                }
            
            # Handle Bedrock API errors
            except ClientError as e:
                signal.alarm(0)  # Cancel alarm
                
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                
                logger.error(
                    "Bedrock API error",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    error_code=error_code,
                    error_message=error_message
                )
                
                # Handle specific Bedrock errors
                if error_code in ['ThrottlingException', 'TooManyRequestsException']:
                    return {
                        'success': False,
                        'error': 'O serviço de IA está temporariamente sobrecarregado. Por favor, tente novamente em alguns instantes.'
                    }
                elif error_code == 'ModelNotReadyException':
                    return {
                        'success': False,
                        'error': 'O serviço de IA está inicializando. Por favor, tente novamente em alguns instantes.'
                    }
                elif error_code == 'ValidationException':
                    return {
                        'success': False,
                        'error': 'Não foi possível processar sua mensagem. Por favor, reformule e tente novamente.'
                    }
                elif error_code in ['AccessDeniedException', 'UnauthorizedException']:
                    return {
                        'success': False,
                        'error': 'Serviço temporariamente indisponível. Por favor, tente novamente.'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'O serviço de IA está temporariamente indisponível. Por favor, tente novamente.'
                    }
            
            finally:
                # Ensure alarm is cancelled
                signal.alarm(0)
        
        except ValueError as e:
            # Validation errors - user-facing
            logger.warning(
                "Validation error",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Extract meaningful error message
            error_msg = str(e)
            if 'phone' in error_msg.lower():
                user_error = 'Formato de telefone inválido. Use o formato internacional (ex: +5511999999999).'
            elif 'email' in error_msg.lower():
                user_error = 'Formato de email inválido. Por favor, verifique o endereço de email.'
            elif 'date' in error_msg.lower() or 'time' in error_msg.lower():
                user_error = 'Formato de data ou hora inválido. Use AAAA-MM-DD para data e HH:MM para hora.'
            elif 'amount' in error_msg.lower() or 'payment' in error_msg.lower():
                user_error = 'Valor de pagamento inválido. O valor deve ser maior que zero.'
            else:
                user_error = f'Erro de validação: {error_msg}'
            
            return {
                'success': False,
                'error': user_error
            }
        
        except KeyError as e:
            # Missing required field errors
            logger.warning(
                "Missing required field",
                trainer_id=trainer_id,
                phone_number=phone_number,
                missing_field=str(e),
                error_type=type(e).__name__
            )
            
            field_name = str(e).strip("'\"")
            return {
                'success': False,
                'error': f'Campo obrigatório ausente: {field_name}. Por favor, forneça todas as informações necessárias.'
            }
        
        except ClientError as e:
            # Catch any remaining ClientError exceptions not caught above
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            logger.error(
                "AWS service error",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error_code=error_code,
                error_type=type(e).__name__,
                exc_info=True
            )
            
            return {
                'success': False,
                'error': 'Serviço temporariamente indisponível. Por favor, tente novamente.'
            }
        
        except ConnectionError as e:
            # Network/connection errors
            logger.error(
                "Connection error",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            
            return {
                'success': False,
                'error': 'Erro de conexão. Por favor, verifique sua conexão e tente novamente.'
            }
        
        except TimeoutError as e:
            # Timeout errors not caught in the inner try block
            logger.error(
                "Timeout error",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return {
                'success': False,
                'error': 'A solicitação demorou muito para processar. Por favor, tente novamente com uma mensagem mais simples.'
            }
        
        except Exception as e:
            # Unexpected errors - log details but return generic message
            logger.error(
                "Unexpected error processing message",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            
            return {
                'success': False,
                'error': 'Ocorreu um erro ao processar sua mensagem. Por favor, tente novamente.'
            }


def get_strands_agent_service() -> StrandsAgentService:
    """
    Factory function to create a StrandsAgentService instance.
    
    This function provides a convenient way to get a configured service instance
    with default settings from the application configuration.
    
    Returns:
        StrandsAgentService instance
        
    Example:
        service = get_strands_agent_service()
        result = service.process_message(
            trainer_id='abc123',
            message='Ver meus alunos'
        )
    """
    return StrandsAgentService()
