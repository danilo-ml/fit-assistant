"""
Strands Agent Service for FitAgent.

This service provides a multi-agent architecture for processing trainer messages using
the official Strands Agents SDK Agents-as-Tools pattern. An orchestrator agent delegates
to 4 specialized domain agents (Student, Session, Payment, Calendar), each wrapped as a
@tool function with focused tools.

Key Features:
- Agents-as-Tools pattern: orchestrator + 4 domain agents
- Each domain agent has focused tools (3-12) for reliable tool execution
- Multi-tenancy via trainer_id injection into tool execution (agent created per-request)
- Timeout protection (30-second limit for WhatsApp compatibility)
- Structured logging for all operations
- PT-BR system prompt for Brazilian Portuguese responses
- Error handling with user-friendly messages

Requirements: 3.1, 3.3, 5.1, 6.4, 7.1, 7.4, 7.6
"""

import os
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import boto3
from strands import Agent
from strands.models.bedrock import BedrockModel
from botocore.exceptions import ClientError

from tools import student_tools, session_tools, payment_tools, calendar_tools, group_session_tools, bulk_import_tools, notification_tools
from models.dynamodb_client import DynamoDBClient
from utils.logging import get_logger
from config import settings

logger = get_logger(__name__)


class StrandsAgentService:
    """
    Service for processing trainer messages using Strands Agents SDK.

    Uses the Agents-as-Tools multi-agent pattern:
    - Orchestrator agent routes queries to domain specialists
    - Student agent: register, view, update students (3 tools)
    - Session agent: schedule, reschedule, cancel sessions + group sessions (12 tools)
    - Payment agent: register, confirm, view payments (4 tools)
    - Calendar agent: connect calendar (1 tool)

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
        Initialize Strands Agent Service with Bedrock configuration.

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
        original_endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
        if original_endpoint_url:
            del os.environ['AWS_ENDPOINT_URL']

        try:
            try:
                self.model = BedrockModel(
                    model_id=self.model_id,
                    region_name=self.region,
                    endpoint_url=self.endpoint_url
                )
            except ValueError as e:
                if "Propagator" in str(e) and "not found" in str(e):
                    logger.warning(
                        "OpenTelemetry propagator initialization failed, continuing with degraded tracing",
                        error=str(e)
                    )
                    self.model = BedrockModel(
                        model_id=self.model_id,
                        region_name=self.region,
                        endpoint_url=self.endpoint_url,
                        temperature=0.2,
                    )
                else:
                    raise
        finally:
            if original_endpoint_url:
                os.environ['AWS_ENDPOINT_URL'] = original_endpoint_url

        logger.info(
            "StrandsAgentService initialized",
            model_id=self.model_id,
            region=self.region,
            has_endpoint=bool(self.endpoint_url)
        )

    def _build_domain_agent_tools(self, trainer_id: str):
        """
        Build 4 domain agent @tool functions for the Agents-as-Tools pattern.

        Each domain agent is a @tool-decorated function that creates a specialized
        Agent with focused tools bound to the given trainer_id via closure.

        Args:
            trainer_id: Trainer identifier to inject into all tool calls

        Returns:
            Tuple of (student_agent, session_agent, payment_agent, calendar_agent, notification_agent)
        """
        from strands import tool
        from datetime import datetime, timezone, timedelta

        # Get current date/time in Brazil timezone (UTC-3)
        brazil_offset = timezone(timedelta(hours=-3))
        now = datetime.now(brazil_offset)
        current_date = now.strftime('%d/%m/%Y')
        current_date_iso = now.strftime('%Y-%m-%d')
        current_time = now.strftime('%H:%M')
        day_of_week = now.strftime('%A')

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

        model = self.model

        # ── Student domain inner tools ──────────────────────────────────
        @tool
        def register_student(name: str, phone_number: str, email: str, training_goal: str, payment_due_day: int = None, monthly_fee: float = None, plan_start_date: str = None) -> Dict[str, Any]:
            """Register a new student and link them to the trainer. monthly_fee is the monthly payment amount in BRL (e.g. 300.00). plan_start_date is the month the plan starts in YYYY-MM format."""
            return student_tools.register_student(trainer_id, name, phone_number, email, training_goal, payment_due_day, monthly_fee, plan_start_date)

        @tool
        def view_students() -> Dict[str, Any]:
            """View all students linked to the trainer."""
            return student_tools.view_students(trainer_id)

        @tool
        def update_student(
            student_name: str = None, student_id: str = None, name: str = None,
            email: str = None, phone_number: str = None, training_goal: str = None,
            payment_due_day: int = None, monthly_fee: float = None, plan_start_date: str = None,
        ) -> Dict[str, Any]:
            """Update student information. Can identify student by student_name or student_id. monthly_fee is the monthly payment amount in BRL (e.g. 300.00). plan_start_date is the month the plan starts in YYYY-MM format."""
            return student_tools.update_student(trainer_id, student_id, student_name, name, email, phone_number, training_goal, payment_due_day, monthly_fee, plan_start_date)

        @tool
        def bulk_import_students(message_body: str, media_urls: list = None) -> Dict[str, Any]:
            """Import multiple students from structured text, CSV file, or Google Sheets link. Use when the trainer wants to register many students at once via text starting with 'importar alunos', a CSV attachment, or a Google Sheets link."""
            return bulk_import_tools.bulk_import_students(trainer_id, message_body, media_urls)

        # ── Session domain inner tools ──────────────────────────────────
        @tool
        def schedule_session(student_name: str, date: str, time: str, duration_minutes: int, location: str = None) -> Dict[str, Any]:
            """Schedule a new training session."""
            return session_tools.schedule_session(trainer_id, student_name, date, time, duration_minutes, location)

        @tool
        def schedule_recurring_session(student_name: str, day_of_week: str, time: str, duration_minutes: int, number_of_weeks: int = None, location: str = None) -> Dict[str, Any]:
            """Schedule recurring training sessions on the same day(s) and time each week. Supports multiple days comma-separated (e.g. 'terça-feira, quinta-feira'). If number_of_weeks is not provided, defaults to 12 weeks (3 months)."""
            return session_tools.schedule_recurring_session(trainer_id, student_name, day_of_week, time, duration_minutes, number_of_weeks, location)

        @tool
        def reschedule_session(session_id: str, new_date: str, new_time: str) -> Dict[str, Any]:
            """Reschedule an existing training session."""
            return session_tools.reschedule_session(trainer_id, session_id, new_date, new_time)

        @tool
        def cancel_session(session_id: str, reason: str = None) -> Dict[str, Any]:
            """Cancel a training session."""
            return session_tools.cancel_session(trainer_id, session_id, reason)

        @tool
        def cancel_student_sessions(student_name: str, reason: str = None) -> Dict[str, Any]:
            """Cancel all scheduled sessions with a specific student."""
            return session_tools.cancel_student_sessions(trainer_id, student_name, reason)

        @tool
        def view_calendar(start_date: str = None, end_date: str = None, filter: str = None) -> Dict[str, Any]:
            """View training sessions in the calendar."""
            return session_tools.view_calendar(trainer_id, start_date, end_date, filter)

        # ── Group session inner tools ───────────────────────────────────
        @tool
        def schedule_group_session(date: str, time: str, duration_minutes: int, location: str = None, max_participants: int = None) -> Dict[str, Any]:
            """Schedule a new group training session for multiple students. Defaults max_participants to the trainer's configured group_size_limit."""
            return group_session_tools.schedule_group_session(trainer_id, date, time, duration_minutes, location, max_participants)

        @tool
        def enroll_student(session_id: str, student_names: List[str]) -> Dict[str, Any]:
            """Enroll one or more students in a group training session. Validates each student individually."""
            return group_session_tools.enroll_student(trainer_id, session_id, student_names)

        @tool
        def remove_student(session_id: str, student_name: str) -> Dict[str, Any]:
            """Remove a student from a group training session."""
            return group_session_tools.remove_student(trainer_id, session_id, student_name)

        @tool
        def cancel_group_session(session_id: str, reason: str = None) -> Dict[str, Any]:
            """Cancel an existing group training session. Returns the list of enrolled student names."""
            return group_session_tools.cancel_group_session(trainer_id, session_id, reason)

        @tool
        def reschedule_group_session(session_id: str, new_date: str, new_time: str) -> Dict[str, Any]:
            """Reschedule an existing group training session to a new date and time. Preserves all enrolled students."""
            return group_session_tools.reschedule_group_session(trainer_id, session_id, new_date, new_time)

        @tool
        def configure_group_size_limit(limit: int) -> Dict[str, Any]:
            """Configure the maximum number of students allowed in a group session. Limit must be between 2 and 50."""
            return group_session_tools.configure_group_size_limit(trainer_id, limit)

        # ── Payment domain inner tools ──────────────────────────────────
        @tool
        def register_payment(
            student_name: str, amount: float, payment_date: str,
            student_id: str = None, receipt_s3_key: str = None, receipt_media_type: str = None,
            session_id: str = None, currency: str = "USD",
            reference_start_month: str = None, reference_end_month: str = None,
        ) -> Dict[str, Any]:
            """Register a payment from a student. reference_start_month and reference_end_month define the period covered in YYYY-MM format (e.g. '2024-01' to '2024-03' for 3 months)."""
            return payment_tools.register_payment(trainer_id, student_name, amount, payment_date, student_id, receipt_s3_key, receipt_media_type, session_id, currency, reference_start_month, reference_end_month)

        @tool
        def confirm_payment(payment_id: str) -> Dict[str, Any]:
            """Confirm a payment."""
            return payment_tools.confirm_payment(trainer_id, payment_id)

        @tool
        def view_payments(student_name: str = None, status: str = None) -> Dict[str, Any]:
            """View payment records for the trainer. Can filter by student name and/or status ('pending' or 'confirmed')."""
            return payment_tools.view_payments(trainer_id, student_name, status)

        @tool
        def view_payment_status(student_name: str = None, student_id: str = None) -> Dict[str, Any]:
            """View month-by-month payment status for a student showing which months are paid, pending, or overdue. The student must have a plan configured with monthly_fee and plan_start_date."""
            return payment_tools.view_payment_status(trainer_id, student_name, student_id)

        # ── Calendar domain inner tools ─────────────────────────────────
        @tool
        def connect_calendar(provider: str) -> Dict[str, Any]:
            """Connect Google Calendar or Outlook Calendar to sync training sessions. IMPORTANT: You MUST call this tool to get the OAuth URL. NEVER invent or construct OAuth URLs yourself."""
            return calendar_tools.connect_calendar(trainer_id, provider)

        @tool
        def disconnect_calendar() -> Dict[str, Any]:
            """Disconnect the trainer's Google Calendar and revoke OAuth access. Use when the trainer wants to stop syncing their calendar."""
            return calendar_tools.disconnect_calendar(trainer_id)

        @tool
        def get_calendar_status() -> Dict[str, Any]:
            """Check whether the trainer's Google Calendar is currently connected. Returns connection status, provider, and connection date."""
            return calendar_tools.get_calendar_status(trainer_id)

        # ── Notification domain inner tools ─────────────────────────────
        @tool
        def send_notification_inner(message: str, recipients: str = "all", specific_student_ids: List[str] = None) -> Dict[str, Any]:
            """Send a notification/message to students. recipients can be 'all' (all active students), 'specific' (requires specific_student_ids), or 'upcoming_sessions' (students with sessions in next 7 days)."""
            return notification_tools.send_notification(trainer_id, message, recipients, specific_student_ids)

        # ── Domain Agent Tool Functions ─────────────────────────────────

        @tool
        def student_agent(query: str) -> str:
            """Handle student management queries: register new students, view student list, update student information, change payment due date (vencimento/dia de pagamento)."""
            agent = Agent(
                model=model,
                system_prompt="""Você é um agente especializado em gerenciamento de alunos para personal trainers no Brasil.

Sua função é EXCLUSIVAMENTE gerenciar alunos:
- Registrar novos alunos (register_student)
- Listar alunos cadastrados (view_students)
- Atualizar informações de alunos (update_student)
- Importar múltiplos alunos de uma vez (bulk_import_students)

REGRAS CRÍTICAS:
- Para importação em massa, use bulk_import_students passando a mensagem completa do usuário como message_body.
- SEMPRE chame as ferramentas disponíveis para executar ações. NUNCA invente resultados.
- NUNCA fabrique IDs de alunos, nomes ou qualquer dado.
- Se faltar informação obrigatória, PERGUNTE ao usuário.
- Para registrar aluno, você PRECISA de: nome completo, telefone no formato E.164, email, objetivo de treino e dia de vencimento (1-31).
- As pessoas não sabem o que é formato E.164 portanto não avise sobre o formato de exemplos reais como "+5511912345678"
- Quando uma ferramenta retornar dados (ex: view_students), você DEVE formatar e exibir TODOS os dados na resposta: nome, telefone, email, objetivo de treino e dia de vencimento. Use formato de lista numerada. NUNCA diga 'aqui está a lista' sem incluir os dados reais.
- Para ALTERAR dados de alunos existentes (incluindo vencimento/dia de pagamento), use SEMPRE update_student com student_name. Use register_student APENAS para cadastrar alunos NOVOS.
- Para alterar o dia de vencimento, use update_student com o parâmetro payment_due_day (1-31).
- Responda SEMPRE em português brasileiro (PT-BR).
- Seja claro, objetivo e amigável.""",
                tools=[register_student, view_students, update_student, bulk_import_students],
            )
            result = agent(query)
            return str(result)

        @tool
        def session_agent(query: str) -> str:
            """Handle session scheduling queries: schedule, reschedule, cancel individual and group training sessions, view calendar, enroll/remove students from group sessions."""
            agent = Agent(
                model=model,
                system_prompt=f"""Você é um agente especializado em agendamento de sessões de treino para personal trainers no Brasil.

Sua função é EXCLUSIVAMENTE gerenciar sessões de treino:
- Agendar sessões individuais (schedule_session)
- Agendar sessões recorrentes (schedule_recurring_session)
- Reagendar sessões (reschedule_session)
- Cancelar sessões (cancel_session)
- Cancelar todas as sessões de um aluno (cancel_student_sessions)
- Visualizar calendário (view_calendar)
- Agendar sessões em grupo (schedule_group_session)
- Inscrever alunos em sessão de grupo (enroll_student)
- Remover alunos de sessão de grupo (remove_student)
- Cancelar sessão de grupo (cancel_group_session)
- Reagendar sessão de grupo (reschedule_group_session)
- Configurar limite de grupo (configure_group_size_limit)

CONTEXTO TEMPORAL ATUAL:
- Data de hoje: {current_date} ({day_of_week_pt})
- Data ISO: {current_date_iso}
- Hora atual: {current_time} (horário de Brasília)

REGRAS CRÍTICAS:
- SEMPRE chame as ferramentas disponíveis para executar ações. NUNCA invente resultados.
- NUNCA fabrique IDs de sessão ou qualquer dado.
- O usuário fornece horários no fuso de Brasília. NUNCA converta para UTC.
- Passe o horário EXATAMENTE como o usuário informou.
- "hoje" = {current_date_iso}, "amanhã" = dia seguinte.
- Formato de data para ferramentas: YYYY-MM-DD. Formato de hora: HH:MM.
- Se faltar informação obrigatória, PERGUNTE ao usuário.
- schedule_group_session APENAS cria a sessão vazia. Para inscrever alunos, chame enroll_student SEPARADAMENTE.
- Para sessões recorrentes sem período especificado, use 12 semanas como padrão.
- Dias da semana: segunda-feira, terça-feira, quarta-feira, quinta-feira, sexta-feira, sábado, domingo.
- Responda SEMPRE em português brasileiro (PT-BR).
- Seja claro, objetivo e amigável.""",
                tools=[
                    schedule_session, schedule_recurring_session, reschedule_session,
                    cancel_session, cancel_student_sessions, view_calendar,
                    schedule_group_session, enroll_student, remove_student,
                    cancel_group_session, reschedule_group_session, configure_group_size_limit,
                ],
            )
            result = agent(query)
            return str(result)

        @tool
        def payment_agent(query: str) -> str:
            """Handle payment queries: register payments, confirm payments, view payment records and payment status."""
            agent = Agent(
                model=model,
                system_prompt="""Você é um agente especializado em gerenciamento de pagamentos para personal trainers no Brasil.

Sua função é EXCLUSIVAMENTE gerenciar pagamentos:
- Registrar pagamentos (register_payment)
- Confirmar pagamentos (confirm_payment)
- Visualizar pagamentos (view_payments)
- Ver status de pagamento mensal (view_payment_status)

REGRAS CRÍTICAS:
- SEMPRE chame as ferramentas disponíveis para executar ações. NUNCA invente resultados.
- NUNCA fabrique IDs de pagamento ou qualquer dado.
- Se faltar informação obrigatória, PERGUNTE ao usuário.
- Para registrar pagamento, você PRECISA de: nome do aluno, valor, data de pagamento, método.
- Responda SEMPRE em português brasileiro (PT-BR).
- Seja claro, objetivo e amigável.""",
                tools=[register_payment, confirm_payment, view_payments, view_payment_status],
            )
            result = agent(query)
            return str(result)

        @tool
        def calendar_agent(query: str) -> str:
            """Handle calendar integration queries: connect, disconnect, or check status of Google Calendar or Outlook Calendar for session sync."""
            query_lower = query.lower()

            # Route disconnect requests directly
            if any(kw in query_lower for kw in ["desconectar", "disconnect", "remover calendário", "revogar"]):
                result = disconnect_calendar()
                if isinstance(result, dict) and result.get("success"):
                    provider = result["data"].get("provider", "google")
                    provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"
                    return f"Seu {provider_name} foi desconectado com sucesso. As sessões não serão mais sincronizadas."
                elif isinstance(result, dict) and not result.get("success"):
                    return result.get("error", "Não foi possível desconectar o calendário. Tente novamente.")
                else:
                    return str(result)

            # Route status requests directly
            if any(kw in query_lower for kw in ["status", "conectado", "connected", "verificar calendário"]):
                result = get_calendar_status()
                if isinstance(result, dict) and result.get("success"):
                    data = result["data"]
                    if data.get("connected"):
                        provider = data.get("provider", "google")
                        provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"
                        connected_at = data.get("connected_at", "data desconhecida")
                        return f"Seu {provider_name} está conectado desde {connected_at}."
                    else:
                        return "Nenhum calendário está conectado. Use o comando de conectar calendário para sincronizar suas sessões."
                elif isinstance(result, dict) and not result.get("success"):
                    return result.get("error", "Não foi possível verificar o status do calendário.")
                else:
                    return str(result)

            # Default: connect flow
            if "outlook" in query_lower or "microsoft" in query_lower:
                provider = "outlook"
                provider_name = "Outlook Calendar"
            else:
                provider = "google"
                provider_name = "Google Calendar"

            # Call the tool directly to guarantee the URL is in the response
            result = connect_calendar(provider)

            if isinstance(result, dict) and result.get("success"):
                oauth_url = result["data"]["oauth_url"]
                return (
                    f"Para conectar seu {provider_name}, clique no link abaixo para autorizar o acesso:\n\n"
                    f"{oauth_url}\n\n"
                    f"O link expira em 30 minutos. Após autorizar, suas sessões serão sincronizadas automaticamente."
                )
            elif isinstance(result, dict) and not result.get("success"):
                return result.get("error", "Não foi possível gerar o link de autorização. Tente novamente.")
            else:
                return str(result)

        @tool
        def notification_agent(query: str) -> str:
            """Handle notification queries: send messages/notifications to students (all, specific, or those with upcoming sessions)."""
            agent = Agent(
                model=model,
                system_prompt="""Você é um agente especializado em envio de notificações e mensagens para alunos de personal trainers no Brasil.

Sua função é EXCLUSIVAMENTE enviar notificações/mensagens para alunos:
- Enviar notificação para todos os alunos (send_notification_inner com recipients="all")
- Enviar notificação para alunos específicos (send_notification_inner com recipients="specific" e specific_student_ids)
- Enviar notificação para alunos com sessões próximas (send_notification_inner com recipients="upcoming_sessions")

TIPOS DE DESTINATÁRIOS:
- "all": Todos os alunos ativos do trainer
- "specific": Alunos específicos (requer lista de IDs)
- "upcoming_sessions": Alunos com sessões nos próximos 7 dias

REGRAS CRÍTICAS:
- SEMPRE chame as ferramentas disponíveis para executar ações. NUNCA invente resultados.
- NUNCA fabrique IDs de alunos ou qualquer dado.
- Se faltar informação obrigatória, PERGUNTE ao usuário.
- Para enviar notificação, você PRECISA de: mensagem e tipo de destinatários.
- Se o usuário não especificar destinatários, use "all" como padrão.
- Responda SEMPRE em português brasileiro (PT-BR).
- Seja claro, objetivo e amigável.""",
                tools=[send_notification_inner],
            )
            result = agent(query)
            return str(result)

        logger.info(
            "Domain agent tools built",
            trainer_id=trainer_id,
            agents=["student_agent(+bulk_import_students)", "session_agent", "payment_agent", "calendar_agent(connect+disconnect+status)", "notification_agent"]
        )

        return student_agent, session_agent, payment_agent, calendar_agent, notification_agent

    def _is_bulk_import_message(self, message: str) -> bool:
        """Check if a message is a bulk import request.

        Detects structured text prefixes, Google Sheets URLs with import keywords,
        and CSV-related import keywords. Mirrors the detection logic in ImportParser
        but avoids instantiating it for a simple check.
        """
        lower = message.lower()
        # Structured text prefix
        if lower.startswith("importar alunos") or lower.startswith("import students"):
            return True
        # Google Sheets URL with import keyword
        if "docs.google.com/spreadsheets" in message:
            if "importar" in lower or "import" in lower:
                return True
        return False

    def _handle_bulk_import_fast_path(
        self, trainer_id: str, message: str, phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute bulk import directly, bypassing the LLM agent chain.

        This avoids the orchestrator → student_agent double-LLM round-trip
        that causes timeouts in production for bulk import operations.
        """
        start_time = datetime.utcnow()

        logger.info(
            "Bulk import fast-path triggered",
            trainer_id=trainer_id,
            phone_number=phone_number,
            message_preview=message[:80] if message else None,
        )

        try:
            result = bulk_import_tools.execute_bulk_import(
                trainer_id=trainer_id,
                message_body=message,
                media_urls=None,
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            logger.info(
                "Bulk import fast-path raw result",
                trainer_id=trainer_id,
                result_keys=list(result.keys()) if isinstance(result, dict) else str(type(result)),
                success=result.get("success") if isinstance(result, dict) else None,
                has_error=bool(result.get("error")) if isinstance(result, dict) else None,
                has_report=bool(result.get("data", {}).get("report")) if isinstance(result, dict) else None,
            )

            if result.get("success"):
                report = result.get("data", {}).get("report", "")
                logger.info(
                    "Bulk import fast-path completed",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    execution_time_seconds=execution_time,
                )
                return {"success": True, "response": report}
            else:
                # The tool returns error in "error" key for explicit failures,
                # but for validation failures the report is in data.report
                error = result.get("error") or result.get("data", {}).get("report") or "Erro ao importar alunos."
                logger.warning(
                    "Bulk import fast-path returned error",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    error=error[:200],
                    execution_time_seconds=execution_time,
                )
                return {"success": False, "error": error}

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(
                "Bulk import fast-path exception",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_seconds=execution_time,
                exc_info=True,
            )
            return {
                "success": False,
                "error": "Ocorreu um erro ao importar os alunos. Por favor, tente novamente.",
            }

    def _extract_oauth_url_from_messages(self, messages: list) -> Tuple[Optional[str], Optional[str]]:
        """
        Scan orchestrator messages for tool results containing OAuth URLs.

        Iterates through the orchestrator's messages list looking for tool results
        that contain Google or Microsoft OAuth authorization URLs.

        Args:
            messages: The orchestrator's messages list.

        Returns:
            Tuple of (oauth_url, full_tool_result_text) if found,
            or (None, None) if no OAuth URL is present.
        """
        oauth_pattern = re.compile(
            r'(https://accounts\.google\.com/o/oauth2/\S+|https://login\.microsoftonline\.com/\S+)'
        )

        for msg in messages:
            if msg.get('role') != 'user' or not isinstance(msg.get('content'), list):
                continue
            for block in msg['content']:
                if not isinstance(block, dict) or not block.get('toolResult'):
                    continue
                tool_content = block['toolResult'].get('content', [])
                for item in tool_content:
                    if not isinstance(item, dict) or not item.get('text'):
                        continue
                    text = item['text']
                    match = oauth_pattern.search(text)
                    if match:
                        return match.group(1), text

        return None, None

    def process_message(
        self,
        trainer_id: str,
        message: str,
        phone_number: Optional[str] = None,
        conversation_history: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Process a WhatsApp message through the orchestrator agent.

        This method:
        1. Validates trainer_id
        2. Builds domain agent tools bound to trainer_id
        3. Creates orchestrator agent with domain agent tools
        4. Executes with 30-second timeout protection
        5. Returns natural language response in PT-BR
        6. Handles errors gracefully with user-friendly messages

        Args:
            trainer_id: Trainer identifier for multi-tenancy (required)
            message: User's WhatsApp message in PT-BR (required)
            phone_number: Phone number for logging (optional)
            conversation_history: Previous conversation messages (optional)

        Returns:
            {'success': bool, 'response': str, 'error': str (optional)}
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

            # Fast-path: detect bulk import messages and call the tool directly,
            # bypassing the two nested LLM round-trips (orchestrator → student_agent)
            # that frequently exceed the 30-second timeout in production.
            if self._is_bulk_import_message(message):
                return self._handle_bulk_import_fast_path(trainer_id, message, phone_number)

            # Build domain agent tools bound to this trainer_id
            student_agent, session_agent, payment_agent, calendar_agent, notification_agent = \
                self._build_domain_agent_tools(trainer_id)

            # Create orchestrator agent with domain agent tools
            orchestrator_prompt = """Você é um assistente de IA para personal trainers no Brasil via WhatsApp.

Você tem 5 agentes especialistas disponíveis como ferramentas. Encaminhe a solicitação do usuário para o agente correto:

- student_agent: Para QUALQUER assunto sobre alunos (registrar, listar, atualizar alunos, alterar vencimento/dia de pagamento)
- session_agent: Para QUALQUER assunto sobre sessões de treino (agendar, reagendar, cancelar sessões individuais ou em grupo, ver calendário, inscrever/remover alunos de grupos)
- payment_agent: Para QUALQUER assunto sobre pagamentos (registrar, confirmar, visualizar pagamentos e status)
- calendar_agent: Para QUALQUER assunto sobre conectar/sincronizar calendário (Google Calendar, Outlook)
- notification_agent: Para QUALQUER assunto sobre enviar notificações ou mensagens para alunos (notificar, avisar, broadcast)

REGRA PRIORITÁRIA — VENCIMENTO/DIA DE PAGAMENTO:
Se a mensagem contém "vencimento" ou "dia de vencimento" ou "dia do pagamento" junto com ação de alteração ("alterar", "mudar", "trocar", "atualizar"), SEMPRE encaminhe para student_agent, mesmo que contenha "mensalidade". O campo payment_due_day é um atributo do cadastro do aluno, não uma operação de pagamento.

EXEMPLOS DE ROTEAMENTO:
- "alterar vencimento da mensalidade da juliana para dia 28" → student_agent
- "mudar dia de pagamento do João para 15" → student_agent
- "registrar pagamento de R$300 da Maria" → payment_agent
- "ver pagamentos do Pedro" → payment_agent

REGRAS DE ROTEAMENTO:
- Palavras como "aluno", "aluna", "registrar aluno", "listar alunos", "atualizar aluno", "importar alunos", "import students", "planilha", "Google Sheets", "CSV" → student_agent
- Palavras como "vencimento", "dia de vencimento", "dia do pagamento" combinadas com ações de alteração ("alterar", "mudar", "trocar", "atualizar") → student_agent (pois payment_due_day é um dado cadastral do aluno)
- Palavras como "sessão", "agendar", "reagendar", "cancelar sessão", "calendário", "treino", "horário", "grupo", "inscrever" → session_agent
- Palavras como "pagamento", "pagar", "valor", "recibo", "confirmar pagamento" → payment_agent
- "mensalidade" → payment_agent APENAS para registrar/visualizar/confirmar pagamentos, NÃO para alterar vencimento
- Palavras como "conectar calendário", "desconectar calendário", "status calendário", "sincronizar", "Google Calendar", "Outlook" → calendar_agent
- Palavras como "notificação", "notificar", "avisar", "mensagem para alunos", "enviar mensagem", "broadcast", "avisar alunos" → notification_agent
- Para conversa geral (saudações, perguntas sobre funcionalidades, ajuda) → responda diretamente SEM chamar nenhuma ferramenta

REGRAS CRÍTICAS:
- Quando encaminhar para um agente, passe a mensagem COMPLETA do usuário como query.
- NUNCA invente resultados. Sempre use os agentes especialistas para executar ações.
- Se o usuário confirmar uma ação pendente ("Sim", "Confirmado"), encaminhe para o agente apropriado com contexto.
- Quando um agente retornar URLs ou links, você DEVE incluir a URL COMPLETA na sua resposta. NUNCA omita links.
- Quando o calendar_agent retornar uma resposta contendo um link, COPIE A RESPOSTA INTEIRA do calendar_agent como sua resposta final. NÃO resuma, NÃO parafraseie, NÃO diga "o link acima". O link SÓ existe se você incluí-lo na resposta.
- Responda SEMPRE em português brasileiro (PT-BR).
- Seja claro, objetivo e amigável."""

            orchestrator = Agent(
                model=self.model,
                system_prompt=orchestrator_prompt,
                tools=[student_agent, session_agent, payment_agent, calendar_agent, notification_agent],
            )

            # Inject conversation history if available
            if conversation_history:
                orchestrator.messages = conversation_history
                logger.info(
                    "Conversation history loaded",
                    trainer_id=trainer_id,
                    history_count=len(conversation_history),
                )

            # Execute orchestrator with thread-based timeout (30 seconds)
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

            def _run_agent():
                return orchestrator(message)

            try:
                bedrock_start_time = datetime.utcnow()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_agent)
                    agent_result = future.result(timeout=30)

                bedrock_execution_time = (datetime.utcnow() - bedrock_start_time).total_seconds()

                logger.info(
                    "Bedrock execution completed",
                    trainer_id=trainer_id,
                    bedrock_time_seconds=bedrock_execution_time
                )

                # Extract response text from AgentResult object
                if hasattr(agent_result, 'text'):
                    response_text = agent_result.text
                elif hasattr(agent_result, 'content'):
                    response_text = agent_result.content
                elif isinstance(agent_result, str):
                    response_text = agent_result
                else:
                    response_text = str(agent_result)

                # Fallback: if the orchestrator didn't produce final text but
                # a tool returned a non-empty result, use the last tool result.
                # This happens when the LLM treats the tool call as the complete
                # action and doesn't generate a follow-up message.
                if not response_text and hasattr(orchestrator, 'messages'):
                    for msg in reversed(orchestrator.messages):
                        if msg.get('role') == 'user' and isinstance(msg.get('content'), list):
                            for block in msg['content']:
                                if isinstance(block, dict) and block.get('toolResult'):
                                    tool_content = block['toolResult'].get('content', [])
                                    for item in tool_content:
                                        if isinstance(item, dict) and item.get('text'):
                                            response_text = item['text']
                                            break
                                if response_text:
                                    break
                        if response_text:
                            break

                # Post-processing: ensure OAuth URLs from calendar_agent are preserved
                # in the final response. The LLM may paraphrase tool results and drop URLs.
                if response_text and hasattr(orchestrator, 'messages'):
                    oauth_url, tool_result_text = self._extract_oauth_url_from_messages(orchestrator.messages)
                    if oauth_url and oauth_url not in response_text:
                        response_text = tool_result_text

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

            except FuturesTimeoutError:
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

                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))

                logger.error(
                    "Bedrock API error",
                    trainer_id=trainer_id,
                    phone_number=phone_number,
                    error_code=error_code,
                    error_message=error_message
                )

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

        except ValueError as e:
            logger.warning(
                "Validation error",
                trainer_id=trainer_id,
                phone_number=phone_number,
                error=str(e),
                error_type=type(e).__name__
            )

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

    Returns:
        StrandsAgentService instance
    """
    return StrandsAgentService()
