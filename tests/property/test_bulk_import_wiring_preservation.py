"""
Property-based tests for preservation of existing agent tools and routing.

These tests verify that existing domain agent tools, system prompts, and
orchestrator routing keywords are present in the UNFIXED code. After the
fix is applied, these same tests confirm no regressions were introduced.

**IMPORTANT**: These tests MUST PASS on unfixed code — they test baseline
behavior that must be preserved.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, Mock
from hypothesis import given, strategies as st, settings, Phase

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Mock strands module: @tool is a passthrough decorator, Agent is a MagicMock
# NOTE: If strands is already mocked (e.g. by the bug test file running first),
# we reuse the existing mock so that StrandsAgentService's bound Agent reference
# matches the _mock_agent_cls we inspect in our tests.
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

# Get the Agent mock that StrandsAgentService actually references.
# This is critical: when both test files run together, the module is only
# imported once, so we must use the same Agent mock the service holds.
import strands as _strands_mod
_mock_agent_cls = _strands_mod.Agent


# ── Helpers ─────────────────────────────────────────────────────────────

def _build_and_invoke_agents(trainer_id: str):
    """
    Build a StrandsAgentService, call _build_domain_agent_tools, invoke
    each agent tool function, and return the list of Agent() call entries.

    Returns a list of (kwargs_dict, agent_name_hint) for each Agent() call,
    plus the raw tool functions tuple.
    """
    with patch('src.services.strands_agent_service.settings') as mock_settings:
        mock_settings.bedrock_model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
        mock_settings.bedrock_region = 'us-east-1'
        mock_settings.aws_endpoint_url = None
        mock_settings.aws_bedrock_endpoint_url = None
        mock_settings.dynamodb_table = 'fitagent-main'

        with patch('src.services.strands_agent_service.DynamoDBClient'):
            service = StrandsAgentService.__new__(StrandsAgentService)
            service.model = MagicMock()
            service.db_client = MagicMock()

            _mock_agent_cls.reset_mock()
            agent_instance = MagicMock()
            agent_instance.return_value = MagicMock(text="ok")
            _mock_agent_cls.return_value = agent_instance

            tools = service._build_domain_agent_tools(trainer_id)
            student_agent_fn, session_agent_fn, payment_agent_fn, calendar_agent_fn = tools

            # Invoke student, session, payment agents to trigger inner Agent()
            for fn in (student_agent_fn, session_agent_fn, payment_agent_fn):
                try:
                    fn("test query")
                except Exception:
                    pass

            # calendar_agent calls connect_calendar directly, no inner Agent
            try:
                calendar_agent_fn("conectar google calendar")
            except Exception:
                pass

            return _mock_agent_cls.call_args_list, tools


def _get_agent_tools_by_index(agent_calls, index):
    """Extract tool names from the Agent() call at the given index."""
    if index >= len(agent_calls):
        return []
    kwargs = agent_calls[index][1] if agent_calls[index][1] else {}
    tools_list = kwargs.get('tools', [])
    return [
        t.__name__ if hasattr(t, '__name__') else str(t)
        for t in tools_list
    ]


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


# ── Test 1 (PBT): student_agent preserves existing tools ───────────────

@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(max_examples=10, phases=[Phase.generate], deadline=None)
def test_student_agent_has_existing_tools(trainer_id):
    """
    Property 2 - Test 1: For all trainer_id, student_agent Agent tools
    include register_student, view_students, update_student.

    **Validates: Requirements 3.1**

    These three tools are the baseline student management tools that must
    remain present regardless of any additions.

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    agent_calls, _ = _build_and_invoke_agents(trainer_id)

    # student_agent is the first Agent() call
    assert len(agent_calls) >= 1, "student_agent did not create an inner Agent"

    tool_names = _get_agent_tools_by_index(agent_calls, 0)

    expected = ['register_student', 'view_students', 'update_student']
    for name in expected:
        assert name in tool_names, (
            f"student_agent is missing existing tool '{name}'. "
            f"Current tools: {tool_names}"
        )


# ── Test 2 (PBT): session_agent preserves all 12 tools ─────────────────

@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(max_examples=10, phases=[Phase.generate], deadline=None)
def test_session_agent_has_all_12_tools(trainer_id):
    """
    Property 2 - Test 2: For all trainer_id, session_agent Agent tools
    include all 12 session/group tools.

    **Validates: Requirements 3.2**

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    agent_calls, _ = _build_and_invoke_agents(trainer_id)

    # session_agent is the second Agent() call
    assert len(agent_calls) >= 2, "session_agent did not create an inner Agent"

    tool_names = _get_agent_tools_by_index(agent_calls, 1)

    expected = [
        'schedule_session', 'schedule_recurring_session', 'reschedule_session',
        'cancel_session', 'cancel_student_sessions', 'view_calendar',
        'schedule_group_session', 'enroll_student', 'remove_student',
        'cancel_group_session', 'reschedule_group_session', 'configure_group_size_limit',
    ]
    for name in expected:
        assert name in tool_names, (
            f"session_agent is missing existing tool '{name}'. "
            f"Current tools: {tool_names}"
        )

    assert len(tool_names) == 12, (
        f"session_agent should have exactly 12 tools, got {len(tool_names)}: {tool_names}"
    )


# ── Test 3 (PBT): payment_agent preserves all 4 tools ──────────────────

@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(max_examples=10, phases=[Phase.generate], deadline=None)
def test_payment_agent_has_all_4_tools(trainer_id):
    """
    Property 2 - Test 3: For all trainer_id, payment_agent Agent tools
    include all 4 payment tools.

    **Validates: Requirements 3.3**

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    agent_calls, _ = _build_and_invoke_agents(trainer_id)

    # payment_agent is the third Agent() call
    assert len(agent_calls) >= 3, "payment_agent did not create an inner Agent"

    tool_names = _get_agent_tools_by_index(agent_calls, 2)

    expected = ['register_payment', 'confirm_payment', 'view_payments', 'view_payment_status']
    for name in expected:
        assert name in tool_names, (
            f"payment_agent is missing existing tool '{name}'. "
            f"Current tools: {tool_names}"
        )

    assert len(tool_names) == 4, (
        f"payment_agent should have exactly 4 tools, got {len(tool_names)}: {tool_names}"
    )


# ── Test 4: Orchestrator prompt has existing routing keywords ───────────

def test_orchestrator_prompt_has_existing_routing_keywords():
    """
    Property 2 - Test 4: Orchestrator prompt contains existing routing
    keywords for session_agent, payment_agent, and calendar_agent.

    **Validates: Requirements 3.4**

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    prompt = _get_orchestrator_prompt("test-trainer-123")

    assert prompt is not None, (
        "Could not find orchestrator Agent creation with routing prompt"
    )

    prompt_lower = prompt.lower()

    # session_agent routing keywords
    session_keywords = ['sessão', 'agendar', 'reagendar', 'cancelar sessão', 'calendário', 'grupo']
    for kw in session_keywords:
        assert kw in prompt_lower, (
            f"Orchestrator prompt missing session_agent routing keyword: '{kw}'"
        )

    # payment_agent routing keywords
    payment_keywords = ['pagamento', 'pagar', 'valor', 'recibo']
    for kw in payment_keywords:
        assert kw in prompt_lower, (
            f"Orchestrator prompt missing payment_agent routing keyword: '{kw}'"
        )

    # calendar_agent routing keywords
    calendar_keywords = ['conectar calendário', 'sincronizar', 'google calendar', 'outlook']
    for kw in calendar_keywords:
        assert kw in prompt_lower, (
            f"Orchestrator prompt missing calendar_agent routing keyword: '{kw}'"
        )

    # student_agent baseline routing keywords
    student_keywords = ['aluno', 'registrar aluno', 'listar alunos', 'atualizar aluno']
    for kw in student_keywords:
        assert kw in prompt_lower, (
            f"Orchestrator prompt missing student_agent routing keyword: '{kw}'"
        )


# ── Test 5 (PBT): Closure-wrapped inner tools bind trainer_id ──────────

@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(max_examples=10, phases=[Phase.generate], deadline=None)
def test_closure_wrapped_tools_bind_trainer_id(trainer_id):
    """
    Property 2 - Test 5: For all trainer_id, closure-wrapped inner tools
    correctly bind trainer_id. Call register_student inner tool from the
    student_agent's Agent tools list and verify trainer_id is passed through.

    **Validates: Requirements 3.5**

    **EXPECTED ON UNFIXED CODE**: PASS
    **EXPECTED ON FIXED CODE**: PASS
    """
    agent_calls, _ = _build_and_invoke_agents(trainer_id)

    assert len(agent_calls) >= 1, "student_agent did not create an inner Agent"

    # Get the actual inner tool functions from the student_agent Agent() call
    kwargs = agent_calls[0][1] if agent_calls[0][1] else {}
    tools_list = kwargs.get('tools', [])

    # Find register_student in the tools list
    register_fn = None
    for t in tools_list:
        if hasattr(t, '__name__') and t.__name__ == 'register_student':
            register_fn = t
            break

    assert register_fn is not None, (
        "Could not find register_student in student_agent tools"
    )

    # The closure references student_tools module imported in strands_agent_service.
    # We need to build fresh tools with the mock in place so the closure captures it.
    import tools.student_tools as st_mod
    original_register = st_mod.register_student

    mock_register = MagicMock(return_value={'success': True, 'data': {}})
    st_mod.register_student = mock_register

    try:
        # Rebuild domain tools so the closure captures the patched function
        with patch('src.services.strands_agent_service.settings') as mock_settings2:
            mock_settings2.bedrock_model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
            mock_settings2.bedrock_region = 'us-east-1'
            mock_settings2.aws_endpoint_url = None
            mock_settings2.aws_bedrock_endpoint_url = None
            mock_settings2.dynamodb_table = 'fitagent-main'

            with patch('src.services.strands_agent_service.DynamoDBClient'):
                svc = StrandsAgentService.__new__(StrandsAgentService)
                svc.model = MagicMock()
                svc.db_client = MagicMock()

                _mock_agent_cls.reset_mock()
                ai = MagicMock()
                ai.return_value = MagicMock(text="ok")
                _mock_agent_cls.return_value = ai

                fresh_tools = svc._build_domain_agent_tools(trainer_id)
                student_fn = fresh_tools[0]

                # Invoke student_agent to trigger inner Agent() creation
                try:
                    student_fn("test query")
                except Exception:
                    pass

                # Get the inner register_student from the Agent() call
                fresh_calls = _mock_agent_cls.call_args_list
                assert len(fresh_calls) >= 1
                inner_kwargs = fresh_calls[0][1] if fresh_calls[0][1] else {}
                inner_tools = inner_kwargs.get('tools', [])

                inner_register = None
                for t in inner_tools:
                    if hasattr(t, '__name__') and t.__name__ == 'register_student':
                        inner_register = t
                        break

                assert inner_register is not None, "register_student not found in fresh build"

                # Call the closure-wrapped inner tool
                inner_register(
                    name="Test Student",
                    phone_number="+5511999999999",
                    email="test@example.com",
                    training_goal="Fitness",
                )

                # Verify trainer_id was passed as the first argument
                mock_register.assert_called_once()
                call_args = mock_register.call_args
                actual_trainer_id = call_args[0][0] if call_args[0] else call_args[1].get('trainer_id')

                assert actual_trainer_id == trainer_id, (
                    f"Closure did not bind trainer_id correctly. "
                    f"Expected '{trainer_id}', got '{actual_trainer_id}'"
                )
    finally:
        st_mod.register_student = original_register


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
