"""
Property-based test for student_agent prompt bug.

This test explores the bug condition where the student_agent's system_prompt
is missing critical instructions:
- No instruction to format and display ALL data returned by view_students
- No instruction to NEVER omit data returned by tools
- No differentiation between update_student and register_student
- No mention of payment_due_day for vencimento changes

**CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bug exists.

**Validates: Requirements 1.3, 1.4**
"""

import os
import sys
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


# --- Strategies ---

campos_aluno = st.sampled_from([
    "nome",
    "telefone",
    "email",
    "objetivo",
    "dia de vencimento",
    "payment_due_day",
])

nomes_alunos = st.sampled_from([
    "juliana nano",
    "maria silva",
    "joão santos",
    "ana costa",
    "pedro oliveira",
])

dias = st.integers(min_value=1, max_value=31)

acoes_alteracao = st.sampled_from([
    "alterar",
    "mudar",
    "trocar",
    "atualizar",
])


# --- Helper to extract student_agent system_prompt ---

def _get_student_agent_prompt(trainer_id: str) -> str:
    """
    Build domain agent tools, call student_agent("test") to trigger the
    inner Agent() creation, and capture the system_prompt kwarg.

    Returns the system_prompt string of the student_agent's inner Agent.
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

            # Reset Agent mock
            _mock_agent_cls.reset_mock()
            agent_instance = MagicMock()
            agent_instance.return_value = MagicMock(text="ok")
            _mock_agent_cls.return_value = agent_instance

            # Build domain tools and get student_agent function
            student_agent, *_ = service._build_domain_agent_tools(trainer_id)

            # Call student_agent to trigger the inner Agent() creation
            student_agent(query="test")

            # Find the Agent() call that has the student_agent prompt
            for call_entry in _mock_agent_cls.call_args_list:
                kwargs = call_entry[1] if call_entry[1] else {}
                prompt = kwargs.get('system_prompt', '')
                if 'gerenciamento de alunos' in prompt.lower():
                    return prompt

            return ""


# --- Property-based tests ---


@given(
    campo=campos_aluno,
    nome=nomes_alunos,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_prompt_instructs_formatting_all_data(campo, nome):
    """
    Property 1: Bug Condition — Prompt do student_agent Instrui Formatação de Resultados.

    **Validates: Requirements 1.3**

    The student_agent system_prompt SHALL contain explicit instructions to
    format and display ALL data returned by view_students (nome, telefone,
    email, objetivo, dia de vencimento) in a readable format.

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt does not instruct the
    LLM to format and display data returned by tools.

    **EXPECTED ON FIXED CODE**: PASSES — prompt contains formatting instructions.
    """
    prompt = _get_student_agent_prompt("test-trainer-001")
    assert prompt, "Could not extract student_agent system_prompt"

    prompt_lower = prompt.lower()

    # The prompt must instruct to display/format ALL data from view_students
    has_format_instruction = any(keyword in prompt_lower for keyword in [
        "formatar",
        "exibir todos",
        "mostrar todos",
        "incluir todos os dados",
        "listar todos os dados",
        "formato legível",
        "lista numerada",
        "exiba todos",
        "mostre todos",
    ])

    # The prompt must mention the specific fields to display
    mentions_fields = all(
        any(field in prompt_lower for field in variants)
        for variants in [
            ["nome"],
            ["telefone", "phone"],
            ["email"],
            ["objetivo", "training_goal"],
            ["vencimento", "payment_due_day"],
        ]
    )

    assert has_format_instruction and mentions_fields, (
        f"Bug confirmed: student_agent prompt does NOT contain instructions to format "
        f"and display ALL data returned by view_students.\n"
        f"Campo tested: '{campo}', Aluno: '{nome}'\n"
        f"has_format_instruction={has_format_instruction}, mentions_fields={mentions_fields}\n"
        f"The prompt lists tools but does NOT instruct the LLM to include actual data "
        f"in the response. This causes 'aqui está a lista' without any real data."
    )


@given(
    campo=campos_aluno,
    nome=nomes_alunos,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_prompt_instructs_never_omit_data(campo, nome):
    """
    Property 2: Bug Condition — Prompt do student_agent Instrui NUNCA Omitir Dados.

    **Validates: Requirements 1.3**

    The student_agent system_prompt SHALL contain an explicit instruction
    to NEVER omit data returned by tools — i.e., never say "here is the list"
    without including the actual data.

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt has no such instruction.

    **EXPECTED ON FIXED CODE**: PASSES — prompt contains anti-omission rule.
    """
    prompt = _get_student_agent_prompt("test-trainer-001")
    assert prompt, "Could not extract student_agent system_prompt"

    prompt_lower = prompt.lower()

    has_anti_omission = any(keyword in prompt_lower for keyword in [
        "nunca omit",
        "nunca diga",
        "nunca responda sem incluir",
        "sempre inclua os dados",
        "sempre inclua todos",
        "não omita",
        "não diga 'aqui está a lista' sem",
        "incluir os dados reais",
        "dados reais",
        "nunca omita",
    ])

    assert has_anti_omission, (
        f"Bug confirmed: student_agent prompt does NOT contain instruction to NEVER "
        f"omit data returned by tools.\n"
        f"Campo tested: '{campo}', Aluno: '{nome}'\n"
        f"The prompt should explicitly say something like 'NUNCA diga aqui está a lista "
        f"sem incluir os dados reais'. Without this, the LLM summarizes tool results "
        f"without including actual data."
    )


@given(
    acao=acoes_alteracao,
    nome=nomes_alunos,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_prompt_differentiates_update_from_register(acao, nome):
    """
    Property 3: Bug Condition — Prompt Diferencia update_student de register_student.

    **Validates: Requirements 1.4**

    The student_agent system_prompt SHALL contain explicit instructions to
    use update_student for existing students and register_student ONLY for
    new students. Without this, the LLM may try to register_student when
    it should update_student.

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt does not differentiate
    the two operations.

    **EXPECTED ON FIXED CODE**: PASSES — prompt contains clear differentiation.
    """
    prompt = _get_student_agent_prompt("test-trainer-001")
    assert prompt, "Could not extract student_agent system_prompt"

    prompt_lower = prompt.lower()

    # Must explicitly say update_student is for existing students
    has_update_for_existing = any(keyword in prompt_lower for keyword in [
        "update_student para alunos existentes",
        "update_student para alterar",
        "update_student para atualizar",
        "alunos existentes.*update_student",
        "alterar dados.*update_student",
        "atualizar dados.*update_student",
        "use update_student",
    ])

    # Must explicitly say register_student is ONLY for new students
    has_register_for_new = any(keyword in prompt_lower for keyword in [
        "register_student apenas para novos",
        "register_student somente para novos",
        "register_student para cadastrar",
        "novos alunos.*register_student",
        "register_student.*novos",
        "apenas para cadastrar alunos novos",
    ])

    assert has_update_for_existing and has_register_for_new, (
        f"Bug confirmed: student_agent prompt does NOT differentiate update_student "
        f"from register_student.\n"
        f"Ação: '{acao}', Aluno: '{nome}'\n"
        f"has_update_for_existing={has_update_for_existing}, "
        f"has_register_for_new={has_register_for_new}\n"
        f"The prompt lists both tools but does NOT instruct when to use each one. "
        f"This causes the LLM to sometimes use register_student for existing students."
    )


@given(
    nome=nomes_alunos,
    dia=dias,
)
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_prompt_mentions_payment_due_day(nome, dia):
    """
    Property 4: Bug Condition — Prompt Menciona payment_due_day para Vencimento.

    **Validates: Requirements 1.4**

    The student_agent system_prompt SHALL mention payment_due_day as the
    parameter to use with update_student for changing the payment due date.

    **EXPECTED ON UNFIXED CODE**: FAILS — the prompt does not mention
    payment_due_day in the context of vencimento changes.

    **EXPECTED ON FIXED CODE**: PASSES — prompt mentions payment_due_day.
    """
    prompt = _get_student_agent_prompt("test-trainer-001")
    assert prompt, "Could not extract student_agent system_prompt"

    prompt_lower = prompt.lower()

    # Must mention payment_due_day in context of vencimento/update
    has_payment_due_day_instruction = any(keyword in prompt_lower for keyword in [
        "payment_due_day",
        "dia de vencimento.*update_student",
        "update_student.*payment_due_day",
        "vencimento.*update_student",
        "alterar.*vencimento.*update_student",
    ])

    assert has_payment_due_day_instruction, (
        f"Bug confirmed: student_agent prompt does NOT mention payment_due_day "
        f"for vencimento changes.\n"
        f"Aluno: '{nome}', Dia: {dia}\n"
        f"The prompt should instruct: 'Para alterar o dia de vencimento, use "
        f"update_student com o parâmetro payment_due_day (1-31)'. Without this, "
        f"the LLM doesn't know which parameter to use for vencimento changes."
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
