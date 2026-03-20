"""
Preservation property tests for non-calendar message behavior.

These tests verify that non-calendar flows (student management, session scheduling,
payments, greetings) and calendar error flows are unaffected by any future fix to
the OAuth URL bug. They capture baseline behavior on UNFIXED code.

Property 2 from design: For any input that does NOT trigger a calendar_agent tool
call returning an OAuth URL (isBugCondition returns false), process_message SHALL
produce the same response as the original function.

**EXPECTED OUTCOME ON UNFIXED CODE**: Tests PASS (confirms baseline behavior)

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import os
import sys
from unittest.mock import patch, MagicMock

from hypothesis import given, settings as hyp_settings, HealthCheck
from hypothesis import strategies as st

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.strands_agent_service import StrandsAgentService


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def trainer_id_strategy():
    """Generate random trainer IDs."""
    return st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=8,
        max_size=16,
    ).map(lambda s: f"trainer-{s}")


# Non-calendar message categories per design preservation requirements
STUDENT_MESSAGES = [
    "Registrar novo aluno João Silva",
    "Listar meus alunos",
    "Atualizar email do aluno Maria",
    "Ver alunos cadastrados",
    "Cadastrar aluna Ana telefone +5511988887777",
]

SESSION_MESSAGES = [
    "Agendar sessão com João amanhã às 10h",
    "Reagendar sessão 123 para sexta às 14h",
    "Cancelar sessão com Maria",
    "Ver meu calendário desta semana",
    "Agendar treino em grupo para sábado às 9h",
]

PAYMENT_MESSAGES = [
    "Registrar pagamento de R$300 do João",
    "Ver pagamentos pendentes",
    "Confirmar pagamento 456",
    "Status de pagamento da Maria",
    "Listar pagamentos do mês",
]

GREETING_MESSAGES = [
    "Olá",
    "Oi, tudo bem?",
    "Bom dia!",
    "Me ajuda por favor",
    "O que você pode fazer?",
]

CALENDAR_ERROR_MESSAGES = [
    "Conectar calendário yahoo",
    "Conectar calendário google",
    "Conectar calendário outlook",
]


def non_calendar_message_strategy():
    """Generate random non-calendar messages from student/session/payment/greeting domains."""
    return st.sampled_from(
        STUDENT_MESSAGES + SESSION_MESSAGES + PAYMENT_MESSAGES + GREETING_MESSAGES
    )


def calendar_error_message_strategy():
    """Generate calendar connection messages that will result in errors (no URL)."""
    return st.sampled_from(CALENDAR_ERROR_MESSAGES)


# Non-calendar response texts (what the orchestrator would return)
STUDENT_RESPONSES = [
    "Aluno João Silva registrado com sucesso! ID: STU-abc123",
    "Você tem 5 alunos cadastrados:\n1. João Silva\n2. Maria Santos\n3. Ana Lima",
    "Email do aluno Maria atualizado com sucesso para maria@email.com",
    "Aluna Ana cadastrada com sucesso!",
]

SESSION_RESPONSES = [
    "Sessão agendada com João para amanhã às 10:00. ID: SES-xyz789",
    "Sessão 123 reagendada para sexta-feira às 14:00.",
    "Sessão com Maria cancelada com sucesso.",
    "Seu calendário desta semana:\n- Seg 10:00 João\n- Qua 14:00 Maria",
    "Sessão em grupo agendada para sábado às 09:00. Máximo 8 participantes.",
]

PAYMENT_RESPONSES = [
    "Pagamento de R$300,00 do João registrado com sucesso!",
    "Pagamentos pendentes:\n1. Maria - R$250,00 (vencimento 15/01)",
    "Pagamento 456 confirmado com sucesso!",
    "Status de pagamento da Maria: 2 meses em dia, 1 pendente.",
]

GREETING_RESPONSES = [
    "Olá! Sou seu assistente FitAgent. Posso ajudar com alunos, sessões, pagamentos e calendário.",
    "Oi! Tudo bem sim! Como posso ajudar?",
    "Bom dia! Em que posso ajudar hoje?",
    "Posso ajudar com: gestão de alunos, agendamento de sessões, pagamentos e integração de calendário.",
]

CALENDAR_ERROR_RESPONSES = [
    "Provedor inválido. Use 'google' ou 'outlook'.",
    "Google Calendar integration is not configured. Please contact support.",
    "Outlook Calendar integration is not configured. Please contact support.",
    "Não foi possível gerar o link de autorização. Tente novamente.",
]


def non_calendar_response_strategy():
    """Generate random non-calendar response texts."""
    return st.sampled_from(
        STUDENT_RESPONSES + SESSION_RESPONSES + PAYMENT_RESPONSES + GREETING_RESPONSES
    )


def calendar_error_response_strategy():
    """Generate random calendar error response texts (no URL)."""
    return st.sampled_from(CALENDAR_ERROR_RESPONSES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_mock_agent_result(response_text: str):
    """Create a mock AgentResult that has .text returning the given text."""
    mock_result = MagicMock()
    mock_result.text = response_text
    return mock_result


def build_non_calendar_messages_list(response_text: str) -> list:
    """
    Build a mock orchestrator.messages list for non-calendar flows.
    No OAuth URLs present — isBugCondition returns false.
    """
    return [
        {
            "role": "assistant",
            "content": [{"text": response_text}],
        }
    ]


def _run_process_message(trainer_id, message, mock_response_text, mock_messages):
    """
    Run process_message with full mocking of the Strands Agent orchestrator.
    Returns the result dict from process_message.
    """
    mock_agent_result = create_mock_agent_result(mock_response_text)

    mock_orchestrator = MagicMock()
    mock_orchestrator.return_value = mock_agent_result
    mock_orchestrator.messages = mock_messages

    with patch.object(StrandsAgentService, '__init__', lambda self, **kwargs: None):
        service = StrandsAgentService()
        service.model = MagicMock()
        service.db_client = MagicMock()
        service.db_client.get_trainer.return_value = {
            "trainer_id": trainer_id,
            "name": "Test Trainer",
        }

        mock_tools = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
        with patch.object(service, '_build_domain_agent_tools', return_value=mock_tools):
            with patch('services.strands_agent_service.Agent', return_value=mock_orchestrator):
                result = service.process_message(
                    trainer_id=trainer_id,
                    message=message,
                    phone_number="+5511999999999",
                )

    return result


# ---------------------------------------------------------------------------
# Preservation Property Tests
# ---------------------------------------------------------------------------

class TestNonCalendarMessagePreservation:
    """
    Property 2: Preservation — Non-Calendar Message Behavior Unchanged.

    For all inputs where isBugCondition returns false (no OAuth URL in tool
    results), process_message response_text passes through unmodified.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """

    @given(
        trainer_id=trainer_id_strategy(),
        message=non_calendar_message_strategy(),
        response_text=non_calendar_response_strategy(),
    )
    @hyp_settings(
        max_examples=20,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_non_calendar_response_passes_through_unmodified(
        self, trainer_id, message, response_text
    ):
        """
        For non-calendar messages (student, session, payment, greeting),
        the orchestrator response_text is returned unchanged by process_message.

        isBugCondition is false because there is no OAuth URL in tool results.

        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        mock_messages = build_non_calendar_messages_list(response_text)

        result = _run_process_message(
            trainer_id=trainer_id,
            message=message,
            mock_response_text=response_text,
            mock_messages=mock_messages,
        )

        assert result.get('success') is True, (
            f"process_message failed unexpectedly: {result.get('error')}"
        )
        assert result.get('response') == response_text, (
            f"PRESERVATION VIOLATION: Non-calendar response was modified.\n"
            f"  Message: {message!r}\n"
            f"  Expected response: {response_text!r}\n"
            f"  Actual response: {result.get('response')!r}\n"
            f"  These should be identical for non-calendar flows."
        )

    @given(
        trainer_id=trainer_id_strategy(),
        message=calendar_error_message_strategy(),
        error_response=calendar_error_response_strategy(),
    )
    @hyp_settings(
        max_examples=10,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_calendar_error_response_passes_through_unmodified(
        self, trainer_id, message, error_response
    ):
        """
        For calendar connection errors (invalid provider, missing credentials),
        the error response (no URL) is returned unchanged by process_message.

        isBugCondition is false because no OAuth URL was generated.

        **Validates: Requirements 3.2, 3.3**
        """
        mock_messages = build_non_calendar_messages_list(error_response)

        result = _run_process_message(
            trainer_id=trainer_id,
            message=message,
            mock_response_text=error_response,
            mock_messages=mock_messages,
        )

        assert result.get('success') is True, (
            f"process_message failed unexpectedly: {result.get('error')}"
        )
        assert result.get('response') == error_response, (
            f"PRESERVATION VIOLATION: Calendar error response was modified.\n"
            f"  Message: {message!r}\n"
            f"  Expected response: {error_response!r}\n"
            f"  Actual response: {result.get('response')!r}\n"
            f"  Error responses without URLs should pass through unchanged."
        )
