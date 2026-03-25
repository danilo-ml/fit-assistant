"""
Property-based test for vencimento routing bug.

This test explores the bug condition where messages about changing payment
due dates (vencimento) are incorrectly routed to payment_agent instead of
student_agent. The payment_agent doesn't have the update_student tool, so
it asks the trainer for the internal student ID.

**CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bug exists.

**Validates: Requirements 1.1, 1.2**
"""

import os
import sys
import re
import pytest
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings, Phase

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Mock strands before importing the service
_mock_strands = MagicMock()
_mock_strands.tool = lambda fn: fn

_mock_agent_cls = MagicMock()
_mock_strands.Agent = _mock_agent_cls

_mock_strands_models = MagicMock()
_mock_strands_models_bedrock = MagicMock()

sys.modules['strands'] = _mock_strands
sys.modules['strands.models'] = _mock_strands_models
sys.modules['strands.models.bedrock'] = _mock_strands_models_bedrock

from src.services.strands_agent_service import StrandsAgentService


# --- Strategies ---

palavras_vencimento = st.sampled_from([
    "vencimento",
    "dia de vencimento",
    "dia do pagamento",
])

acoes_alteracao = st.sampled_from([
    "alterar",
    "mudar",
    "trocar",
    "atualizar",
])

nomes_alunos = st.sampled_from([
    "juliana nano",
    "maria silva",
    "joão santos",
    "ana costa",
    "pedro oliveira",
    "lucas ferreira",
    "camila souza",
])

dias = st.integers(min_value=1, max_value=31)



# --- Message templates ---

def build_vencimento_message(palavra_vencimento, acao, nome_aluno, dia):
    """Build a message about changing payment due date for a student."""
    templates = [
        f"{acao} {palavra_vencimento} da mensalidade da {nome_aluno} para dia {dia}",
        f"{acao} {palavra_vencimento} da {nome_aluno} para dia {dia}",
        f"{acao} o {palavra_vencimento} da {nome_aluno} para dia {dia}",
    ]
    # Use a deterministic selection based on the hash of inputs
    idx = hash((palavra_vencimento, acao, nome_aluno, dia)) % len(templates)
    return templates[idx]


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

            # Reset Agent mock
            _mock_agent_cls.reset_mock()
            agent_instance = MagicMock()
            agent_instance.return_value = MagicMock(text="ok")
            _mock_agent_cls.return_value = agent_instance

            service.process_message(
                trainer_id=trainer_id,
                message='test',
                phone_number='+5511999999999',
            )

            # Find the orchestrator Agent() call — the one with routing rules
            for call_entry in _mock_agent_cls.call_args_list:
                kwargs = call_entry[1] if call_entry[1] else {}
                prompt = kwargs.get('system_prompt', '')
                if 'REGRAS DE ROTEAMENTO' in prompt or 'student_agent' in prompt:
                    return prompt

            return None


def _get_student_agent_docstring(trainer_id: str) -> str:
    """
    Build domain agent tools and extract the student_agent tool's docstring.

    Calls _build_domain_agent_tools and returns the __doc__ attribute of the
    student_agent function (the first tool returned).
    """
    with patch('src.services.strands_agent_service.settings') as mock_settings:
        mock_settings.bedrock_model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
        mock_settings.bedrock_region = 'us-east-1'
        mock_settings.aws_endpoint_url = None
        mock_settings.aws_bedrock_endpoint_url = None
        mock_settings.dynamodb_table = 'fitagent-main'

        with patch('src.services.strands_agent_service.DynamoDBClient') as MockDB:
            mock_db = MagicMock()
            MockDB.return_value = mock_db

            service = StrandsAgentService.__new__(StrandsAgentService)
            service.model = MagicMock()
            service.db_client = mock_db

            # Reset Agent mock so inner Agent() calls don't fail
            _mock_agent_cls.reset_mock()
            _mock_agent_cls.return_value = MagicMock()

            student_agent, *_ = service._build_domain_agent_tools(trainer_id)
            return student_agent.__doc__ or ""


def _prompt_routes_vencimento_to_student_agent(prompt: str) -> bool:
    """
    Check if the orchestrator prompt contains explicit routing rules that
    would route vencimento/due-date change messages to student_agent.

    The prompt must contain a rule that explicitly associates vencimento
    keywords with student_agent, not payment_agent.
    """
    prompt_lower = prompt.lower()

    # Check 1: The prompt must have an explicit rule routing vencimento to student_agent
    # Look for vencimento-related keywords in the student_agent section
    has_vencimento_student_rule = False

    # Split prompt into lines and check for student_agent rules mentioning vencimento
    lines = prompt_lower.split('\n')
    for line in lines:
        if 'student_agent' in line and any(
            kw in line for kw in ['vencimento', 'dia de vencimento', 'dia do pagamento']
        ):
            has_vencimento_student_rule = True
            break

    # Check 2: Look for a disambiguation rule that prioritizes student_agent for vencimento
    has_disambiguation = False
    for line in lines:
        if ('vencimento' in line or 'dia do pagamento' in line) and \
           'student_agent' in line and \
           any(w in line for w in ['prioridade', 'sempre', 'desambiguação', 'mesmo que']):
            has_disambiguation = True
            break

    return has_vencimento_student_rule or has_disambiguation


# --- Property-based tests ---

@given(
    palavra_vencimento=palavras_vencimento,
    acao=acoes_alteracao,
    nome_aluno=nomes_alunos,
    dia=dias,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_orchestrator_routes_vencimento_changes_to_student_agent(
    palavra_vencimento, acao, nome_aluno, dia
):
    """
    Property 1: Bug Condition — Roteamento de Alteração de Vencimento.

    **Validates: Requirements 1.1, 1.2**

    For any message combining a vencimento keyword with an alteration action
    and a student name, the orchestrator_prompt SHALL contain routing rules
    that direct these messages to student_agent (not payment_agent).

    The bug condition (isBugCondition) is:
      - message contains SOME word from ["vencimento", "dia de vencimento", "dia do pagamento"]
      - AND message contains SOME action from ["alterar", "mudar", "trocar", "atualizar"]
      - AND message identifies a student by name

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt routes "mensalidade"
    and "vencimento" to payment_agent without disambiguation.

    **EXPECTED ON FIXED CODE**: PASSES — prompt has explicit vencimento → student_agent rule.
    """
    message = build_vencimento_message(palavra_vencimento, acao, nome_aluno, dia)

    # Get the orchestrator prompt
    prompt = _get_orchestrator_prompt("test-trainer-001")
    assert prompt is not None, "Could not find orchestrator Agent creation with routing prompt"

    # Verify the prompt routes vencimento changes to student_agent
    routes_correctly = _prompt_routes_vencimento_to_student_agent(prompt)

    assert routes_correctly, (
        f"Bug confirmed: orchestrator_prompt does NOT route vencimento changes to student_agent.\n"
        f"Message: '{message}'\n"
        f"The prompt contains 'mensalidade' → payment_agent but lacks a disambiguation rule "
        f"for vencimento/dia de pagamento + alteration actions → student_agent.\n"
        f"Current student_agent routing rule: "
        f"{[line.strip() for line in prompt.split(chr(10)) if 'student_agent' in line.lower()]}\n"
        f"Current payment_agent routing rule: "
        f"{[line.strip() for line in prompt.split(chr(10)) if 'payment_agent' in line.lower()]}"
    )


@given(
    palavra_vencimento=palavras_vencimento,
    acao=acoes_alteracao,
    nome_aluno=nomes_alunos,
    dia=dias,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_priority_rule_appears_before_routing_rules(
    palavra_vencimento, acao, nome_aluno, dia
):
    """
    Property 1b: Bug Condition — Posição da Regra Prioritária.

    **Validates: Requirements 1.1, 1.2**

    The orchestrator_prompt SHALL contain a priority/disambiguation rule
    (e.g. "REGRA PRIORITÁRIA" or equivalent) that appears BEFORE the general
    "REGRAS DE ROTEAMENTO" section. This ensures the LLM sees the vencimento
    disambiguation instruction before encountering "mensalidade → payment_agent".

    **EXPECTED ON UNFIXED CODE**: FAILS — "REGRA DE DESAMBIGUAÇÃO" appears
    AFTER "REGRAS DE ROTEAMENTO", so the LLM prioritizes the earlier rules.

    **EXPECTED ON FIXED CODE**: PASSES — priority rule is positioned before
    general routing rules.
    """
    message = build_vencimento_message(palavra_vencimento, acao, nome_aluno, dia)

    prompt = _get_orchestrator_prompt("test-trainer-001")
    assert prompt is not None, "Could not find orchestrator Agent creation with routing prompt"

    prompt_upper = prompt.upper()

    # Find position of priority/disambiguation rule
    priority_pos = -1
    for marker in ["REGRA PRIORITÁRIA", "REGRA PRIORITARIA"]:
        pos = prompt_upper.find(marker)
        if pos >= 0:
            priority_pos = pos
            break

    # Find position of general routing rules
    routing_pos = prompt_upper.find("REGRAS DE ROTEAMENTO")

    assert priority_pos >= 0, (
        f"Bug confirmed: orchestrator_prompt does NOT contain a 'REGRA PRIORITÁRIA' section.\n"
        f"Message: '{message}'\n"
        f"The disambiguation rule ('REGRA DE DESAMBIGUAÇÃO') exists but is not labeled as "
        f"a priority rule. The LLM sees 'mensalidade → payment_agent' first and ignores "
        f"the later disambiguation.\n"
        f"Sections found: {[s.strip() for s in prompt.split(chr(10)) if 'REGRA' in s.upper()]}"
    )

    assert routing_pos >= 0, (
        f"Could not find 'REGRAS DE ROTEAMENTO' section in the prompt."
    )

    assert priority_pos < routing_pos, (
        f"Bug confirmed: priority rule appears AFTER routing rules (pos {priority_pos} vs {routing_pos}).\n"
        f"Message: '{message}'\n"
        f"The LLM processes instructions top-to-bottom and will match "
        f"'mensalidade → payment_agent' before reaching the disambiguation rule."
    )


@given(
    palavra_vencimento=palavras_vencimento,
    acao=acoes_alteracao,
    nome_aluno=nomes_alunos,
    dia=dias,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_docstring_mentions_vencimento(
    palavra_vencimento, acao, nome_aluno, dia
):
    """
    Property 1c: Bug Condition — Docstring do student_agent Menciona Vencimento.

    **Validates: Requirements 1.1, 1.2**

    The @tool student_agent docstring SHALL mention "vencimento" or
    "dia de pagamento" so the LLM considers student_agent as a candidate
    when routing vencimento-related messages.

    **EXPECTED ON UNFIXED CODE**: FAILS — the docstring says only
    "Handle student management queries: register new students, view student list,
    update student information" with no mention of vencimento.

    **EXPECTED ON FIXED CODE**: PASSES — docstring includes vencimento/dia de pagamento.
    """
    message = build_vencimento_message(palavra_vencimento, acao, nome_aluno, dia)

    docstring = _get_student_agent_docstring("test-trainer-001")
    docstring_lower = docstring.lower()

    has_vencimento = "vencimento" in docstring_lower
    has_dia_pagamento = "dia de pagamento" in docstring_lower

    assert has_vencimento or has_dia_pagamento, (
        f"Bug confirmed: student_agent docstring does NOT mention 'vencimento' or 'dia de pagamento'.\n"
        f"Message: '{message}'\n"
        f"Current docstring: '{docstring}'\n"
        f"Without 'vencimento' in the tool description, the LLM has no signal to route "
        f"vencimento messages to student_agent."
    )


@given(
    palavra_vencimento=palavras_vencimento,
    acao=acoes_alteracao,
    nome_aluno=nomes_alunos,
    dia=dias,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_prompt_contains_concrete_routing_examples(
    palavra_vencimento, acao, nome_aluno, dia
):
    """
    Property 1d: Bug Condition — Exemplos Concretos de Roteamento no Prompt.

    **Validates: Requirements 1.1, 1.2**

    The orchestrator_prompt SHALL contain concrete routing examples
    (e.g. "alterar vencimento da mensalidade da juliana → student_agent")
    to guide the LLM with few-shot examples, not just abstract rules.

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt contains only abstract
    keyword → agent rules without concrete message examples.

    **EXPECTED ON FIXED CODE**: PASSES — prompt includes concrete examples.
    """
    message = build_vencimento_message(palavra_vencimento, acao, nome_aluno, dia)

    prompt = _get_orchestrator_prompt("test-trainer-001")
    assert prompt is not None, "Could not find orchestrator Agent creation with routing prompt"

    prompt_lower = prompt.lower()

    # Look for concrete routing examples — messages with → or -> pointing to an agent
    # Examples like: "alterar vencimento da mensalidade da juliana → student_agent"
    has_concrete_example = False

    # Check for arrow-style examples (→ or ->)
    example_pattern = re.compile(
        r'(alterar|mudar|trocar|atualizar).*(vencimento|dia de pagamento|dia do pagamento).*'
        r'(→|->)\s*student_agent',
        re.IGNORECASE,
    )
    if example_pattern.search(prompt):
        has_concrete_example = True

    # Also check for "exemplo" or "ex:" sections with vencimento routing
    if not has_concrete_example:
        exemplo_pattern = re.compile(
            r'(exemplo|ex:|e\.g\.).*'
            r'(vencimento|dia de pagamento).*student_agent',
            re.IGNORECASE,
        )
        if exemplo_pattern.search(prompt):
            has_concrete_example = True

    assert has_concrete_example, (
        f"Bug confirmed: orchestrator_prompt does NOT contain concrete routing examples.\n"
        f"Message: '{message}'\n"
        f"The prompt uses only abstract keyword → agent rules without concrete message "
        f"examples. LLMs respond better to few-shot examples than abstract rules.\n"
        f"Expected something like: 'alterar vencimento da mensalidade da juliana → student_agent'"
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
