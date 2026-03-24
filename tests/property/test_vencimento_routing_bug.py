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


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
