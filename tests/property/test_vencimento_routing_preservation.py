"""
Property-based tests for preservation of routing behavior.

These tests verify that EXISTING correct routing behavior is maintained:
- Payment operation messages route to payment_agent
- Student update messages (without vencimento keywords) route to student_agent

**IMPORTANT**: These tests MUST PASS on unfixed code — they test baseline
behavior that must be preserved after the fix.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import os
import sys
import re
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings, Phase

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Mock strands before importing the service — reuse existing mock if present
if 'strands' in sys.modules and hasattr(sys.modules['strands'], 'Agent'):
    _mock_strands = sys.modules['strands']
else:
    _mock_strands = MagicMock()
    _mock_strands.tool = lambda fn: fn
    sys.modules['strands'] = _mock_strands

if 'strands.models' not in sys.modules:
    sys.modules['strands.models'] = MagicMock()
if 'strands.models.bedrock' not in sys.modules:
    sys.modules['strands.models.bedrock'] = MagicMock()

from src.services.strands_agent_service import StrandsAgentService

import strands as _strands_mod
_mock_agent_cls = _strands_mod.Agent


# --- Helper to extract orchestrator prompt ---

def _get_orchestrator_prompt(trainer_id: str):
    """
    Build a StrandsAgentService, call process_message, and capture the
    orchestrator Agent() call to extract its system_prompt.
    """
    with patch('src.services.strands_agent_service.settings') as mock_settings:
        mock_settings.bedrock_model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
        mock_settings.bedrock_region = 'us-east-1'
        mock_settings.aws_endpoint_url = None
        mock_settings.aws_bedrock_endpoint_url = None
        mock_settings.dynamodb_table = 'fitagent-main'

        with patch('src.services.strands_agent_service.DynamoDBClient') as MockDB:
            mock_db = MagicMock()
            mock_db.get_trainer.return_value = {
                'PK': f'TRAINER#{trainer_id}',
                'SK': 'METADATA',
                'name': 'Test Trainer',
                'phone_number': '+5511999999999',
            }
            MockDB.return_value = mock_db

            service = StrandsAgentService.__new__(StrandsAgentService)
            service.model = MagicMock()
            service.db_client = mock_db

            _mock_agent_cls.reset_mock()
            agent_instance = MagicMock()
            agent_instance.return_value = MagicMock(text="ok")
            _mock_agent_cls.return_value = agent_instance

            service.process_message(
                trainer_id=trainer_id,
                message='test',
                phone_number='+5511999999999',
            )

            for call_entry in _mock_agent_cls.call_args_list:
                kwargs = call_entry[1] if call_entry[1] else {}
                prompt = kwargs.get('system_prompt', '')
                if 'REGRAS DE ROTEAMENTO' in prompt or 'student_agent' in prompt:
                    return prompt

            return None


# --- Routing analysis helpers ---

def _extract_routing_section(prompt: str, agent_name: str) -> str:
    """Extract the routing rule line(s) for a given agent from the prompt."""
    lines = prompt.split('\n')
    relevant = []
    for line in lines:
        if agent_name in line.lower():
            relevant.append(line.lower().strip())
    return ' '.join(relevant)


def _prompt_routes_to_payment_agent(prompt: str, message: str) -> bool:
    """
    Check if the orchestrator prompt contains routing keywords that would
    match the given payment message and route it to payment_agent.

    We check that the prompt has payment_agent routing rules containing
    keywords that appear in the message.
    """
    prompt_lower = prompt.lower()
    message_lower = message.lower()

    # Payment routing keywords from the orchestrator prompt
    payment_keywords = [
        "pagamento", "pagar", "valor", "recibo",
        "mensalidade", "confirmar pagamento"
    ]

    # Check that the prompt has a payment_agent routing rule
    payment_section = _extract_routing_section(prompt, 'payment_agent')
    if not payment_section:
        return False

    # Check that at least one payment keyword from the message appears
    # in the payment_agent routing rules
    for kw in payment_keywords:
        if kw in message_lower and kw in payment_section:
            return True

    return False


def _prompt_routes_to_student_agent(prompt: str, message: str) -> bool:
    """
    Check if the orchestrator prompt contains routing rules that would
    match the given student update message and route it to student_agent.

    The prompt uses two mechanisms for student routing:
    1. Explicit keywords in REGRAS DE ROTEAMENTO (e.g. "aluno", "atualizar aluno")
    2. Agent description: "student_agent: Para QUALQUER assunto sobre alunos
       (registrar, listar, atualizar alunos)" — the LLM uses this description
       to route messages about updating student fields even when the exact
       keyword "aluno" isn't in the user message.

    For preservation, we verify that:
    - The prompt has a student_agent section with "atualizar" capability
    - The prompt does NOT route the message's action keywords to another agent
    """
    prompt_lower = prompt.lower()
    message_lower = message.lower()

    # Check 1: student_agent description mentions "atualizar alunos" or "atualizar aluno"
    student_section = _extract_routing_section(prompt, 'student_agent')
    if not student_section:
        return False

    has_update_capability = 'atualizar' in student_section

    # Check 2: The message's action verb (atualizar/mudar) is NOT exclusively
    # routed to another agent. We verify that the student_agent routing rules
    # or description cover "atualizar" as a student operation.
    if not has_update_capability:
        return False

    # Check 3: Ensure the message doesn't contain keywords that would
    # route it to payment_agent instead (e.g. "pagamento", "mensalidade")
    payment_keywords = ["pagamento", "pagar", "valor", "recibo", "mensalidade"]
    for pk in payment_keywords:
        if pk in message_lower:
            return False

    return True


# --- Strategies ---

nomes_alunos = st.sampled_from([
    "Maria", "João", "Ana", "Pedro", "Lucas",
    "Camila", "juliana nano", "Carlos", "Fernanda",
])

valores_pagamento = st.sampled_from([
    "R$100", "R$200", "R$300", "R$500", "R$150",
    "R$250", "R$80", "R$1000",
])

verbos_pagamento_registrar = st.sampled_from([
    "registrar pagamento",
    "registrar o pagamento",
    "lançar pagamento",
])

verbos_pagamento_ver = st.sampled_from([
    "ver pagamentos",
    "listar pagamentos",
    "mostrar pagamentos",
    "visualizar pagamentos",
])

verbos_pagamento_confirmar = st.sampled_from([
    "confirmar pagamento",
    "confirmar o pagamento",
])

ids_pagamento = st.sampled_from([
    "abc123", "def456", "ghi789", "pay001", "pay002",
])

campos_aluno_sem_vencimento = st.sampled_from([
    "email", "telefone", "objetivo", "nome",
])

novos_valores_campo = st.sampled_from([
    "joao@email.com", "+5511988887777", "hipertrofia",
    "emagrecimento", "condicionamento", "maria@gmail.com",
])


# --- Message builders ---

def build_registrar_pagamento_msg(verbo, valor, nome):
    """Build a payment registration message."""
    templates = [
        f"{verbo} de {valor} da {nome}",
        f"{verbo} de {valor} do {nome}",
        f"{verbo} {valor} da {nome}",
    ]
    idx = hash((verbo, valor, nome)) % len(templates)
    return templates[idx]


def build_ver_pagamentos_msg(verbo, nome):
    """Build a view payments message."""
    templates = [
        f"{verbo} do {nome}",
        f"{verbo} da {nome}",
    ]
    idx = hash((verbo, nome)) % len(templates)
    return templates[idx]


def build_confirmar_pagamento_msg(verbo, id_pagamento):
    """Build a confirm payment message."""
    return f"{verbo} {id_pagamento}"


def build_status_pagamento_msg(nome):
    """Build a payment status message."""
    templates = [
        f"status de pagamento da {nome}",
        f"status de pagamento do {nome}",
        f"status pagamento {nome}",
    ]
    idx = hash(nome) % len(templates)
    return templates[idx]


def build_atualizar_aluno_msg(campo, nome, novo_valor):
    """Build a student update message WITHOUT vencimento keywords."""
    templates = [
        f"atualizar {campo} do {nome} para {novo_valor}",
        f"atualizar {campo} da {nome} para {novo_valor}",
        f"mudar {campo} do {nome} para {novo_valor}",
    ]
    idx = hash((campo, nome, novo_valor)) % len(templates)
    return templates[idx]


# --- Property-based tests ---

@given(
    verbo=verbos_pagamento_registrar,
    valor=valores_pagamento,
    nome=nomes_alunos,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_registrar_pagamento_routes_to_payment_agent(verbo, valor, nome):
    """
    Property 2: Preservation — registrar pagamento routes to payment_agent.

    **Validates: Requirements 3.1**

    For any message about registering a payment (combining payment verbs ×
    values × student names), the orchestrator prompt SHALL contain routing
    keywords that match these messages to payment_agent.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    message = build_registrar_pagamento_msg(verbo, valor, nome)

    prompt = _get_orchestrator_prompt("test-trainer-preservation")
    assert prompt is not None, "Could not find orchestrator prompt"

    assert _prompt_routes_to_payment_agent(prompt, message), (
        f"Preservation violated: payment registration message should route to payment_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt must contain payment_agent routing keywords matching this message."
    )


@given(
    verbo=verbos_pagamento_ver,
    nome=nomes_alunos,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_ver_pagamentos_routes_to_payment_agent(verbo, nome):
    """
    Property 2: Preservation — ver pagamentos routes to payment_agent.

    **Validates: Requirements 3.2**

    For any message about viewing payments, the orchestrator prompt SHALL
    contain routing keywords that match these messages to payment_agent.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    message = build_ver_pagamentos_msg(verbo, nome)

    prompt = _get_orchestrator_prompt("test-trainer-preservation")
    assert prompt is not None, "Could not find orchestrator prompt"

    assert _prompt_routes_to_payment_agent(prompt, message), (
        f"Preservation violated: view payments message should route to payment_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt must contain payment_agent routing keywords matching this message."
    )


@given(
    verbo=verbos_pagamento_confirmar,
    id_pagamento=ids_pagamento,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_confirmar_pagamento_routes_to_payment_agent(verbo, id_pagamento):
    """
    Property 2: Preservation — confirmar pagamento routes to payment_agent.

    **Validates: Requirements 3.4**

    For any message about confirming a payment, the orchestrator prompt SHALL
    contain routing keywords that match these messages to payment_agent.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    message = build_confirmar_pagamento_msg(verbo, id_pagamento)

    prompt = _get_orchestrator_prompt("test-trainer-preservation")
    assert prompt is not None, "Could not find orchestrator prompt"

    assert _prompt_routes_to_payment_agent(prompt, message), (
        f"Preservation violated: confirm payment message should route to payment_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt must contain payment_agent routing keywords matching this message."
    )


@given(nome=nomes_alunos)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_status_pagamento_routes_to_payment_agent(nome):
    """
    Property 2: Preservation — status de pagamento routes to payment_agent.

    **Validates: Requirements 3.2**

    For any message about payment status, the orchestrator prompt SHALL
    contain routing keywords that match these messages to payment_agent.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    message = build_status_pagamento_msg(nome)

    prompt = _get_orchestrator_prompt("test-trainer-preservation")
    assert prompt is not None, "Could not find orchestrator prompt"

    assert _prompt_routes_to_payment_agent(prompt, message), (
        f"Preservation violated: payment status message should route to payment_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt must contain payment_agent routing keywords matching this message."
    )


@given(
    campo=campos_aluno_sem_vencimento,
    nome=nomes_alunos,
    novo_valor=novos_valores_campo,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_atualizar_aluno_sem_vencimento_routes_to_student_agent(campo, nome, novo_valor):
    """
    Property 2: Preservation — student updates WITHOUT vencimento keywords
    route to student_agent.

    **Validates: Requirements 3.3**

    For any message about updating student data (email, telefone, objetivo, nome)
    that does NOT contain vencimento keywords, the orchestrator prompt SHALL
    contain routing keywords that match these messages to student_agent.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    message = build_atualizar_aluno_msg(campo, nome, novo_valor)

    # Sanity: ensure the message does NOT contain vencimento keywords
    palavras_vencimento = ["vencimento", "dia de vencimento", "dia do pagamento"]
    for pv in palavras_vencimento:
        assert pv not in message.lower(), (
            f"Test bug: generated message contains vencimento keyword '{pv}': {message}"
        )

    prompt = _get_orchestrator_prompt("test-trainer-preservation")
    assert prompt is not None, "Could not find orchestrator prompt"

    assert _prompt_routes_to_student_agent(prompt, message), (
        f"Preservation violated: student update message should route to student_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt must contain student_agent routing keywords matching this message."
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
