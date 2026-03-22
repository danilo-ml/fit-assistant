"""
Property-based test for bulk_import_students tool wiring bug.

This test explores the bug condition where bulk_import_students is fully
implemented in src/tools/bulk_import_tools.py but is never wired into the
student_agent in src/services/strands_agent_service.py.

**CRITICAL**: These tests MUST FAIL on unfixed code - failure confirms the bug exists.

**Validates: Requirements 1.1, 1.3, 2.1, 2.3**
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, Mock, call
from hypothesis import given, strategies as st, settings, Phase

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# We need to mock strands so that:
# 1. @tool decorator is a passthrough (returns the function as-is)
# 2. Agent class is a MagicMock we can inspect
_mock_strands = MagicMock()
# Make @tool a passthrough decorator
_mock_strands.tool = lambda fn: fn

_mock_agent_cls = MagicMock()
_mock_strands.Agent = _mock_agent_cls

_mock_strands_models = MagicMock()
_mock_strands_models_bedrock = MagicMock()

sys.modules['strands'] = _mock_strands
sys.modules['strands.models'] = _mock_strands_models
sys.modules['strands.models.bedrock'] = _mock_strands_models_bedrock

from src.services.strands_agent_service import StrandsAgentService


def _build_and_invoke_student_agent(trainer_id: str):
    """
    Build a StrandsAgentService, call _build_domain_agent_tools, invoke
    student_agent, and return the captured Agent() call kwargs.
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

            # Reset the Agent mock to capture fresh calls
            _mock_agent_cls.reset_mock()
            # Make Agent() return a callable mock that returns a result
            agent_instance = MagicMock()
            agent_instance.return_value = MagicMock(text="ok")
            _mock_agent_cls.return_value = agent_instance

            # Build domain agent tools
            tools = service._build_domain_agent_tools(trainer_id)
            student_agent_fn = tools[0]

            # Invoke student_agent — this triggers Agent() inside
            try:
                student_agent_fn("test query")
            except Exception:
                pass

            return _mock_agent_cls.call_args_list


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


@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_has_bulk_import_tool(trainer_id):
    """
    Property 1 - Test 1: Bug Condition — bulk_import_students tool missing from student_agent.

    **Validates: Requirements 1.1, 2.1**

    For any trainer_id, when _build_domain_agent_tools is called and the
    student_agent is invoked, the inner Agent SHALL be created with
    bulk_import_students in its tools list.

    **EXPECTED ON UNFIXED CODE**: FAILS — student_agent tools are only
    [register_student, view_students, update_student], no bulk_import_students.

    **EXPECTED ON FIXED CODE**: PASSES — bulk_import_students is present.
    """
    agent_calls = _build_and_invoke_student_agent(trainer_id)

    assert len(agent_calls) >= 1, "student_agent did not create an inner Agent"

    # The first Agent() call should be from student_agent
    student_call_kwargs = agent_calls[0][1] if agent_calls[0][1] else {}
    tools_list = student_call_kwargs.get('tools', [])
    tool_names = [
        t.__name__ if hasattr(t, '__name__') else str(t)
        for t in tools_list
    ]

    assert 'bulk_import_students' in tool_names, (
        f"student_agent tools list is missing bulk_import_students. "
        f"Current tools: {tool_names}. "
        f"The bulk_import_students tool exists in src/tools/bulk_import_tools.py "
        f"but is not wired into the student_agent."
    )


@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_student_agent_prompt_mentions_bulk_import(trainer_id):
    """
    Property 1 - Test 2: Bug Condition — student_agent system prompt lacks bulk import mention.

    **Validates: Requirements 1.3, 2.1**

    For any trainer_id, the student_agent's system prompt SHALL mention
    "importar" or "bulk_import" so the sub-agent knows it can handle
    bulk import requests.

    **EXPECTED ON UNFIXED CODE**: FAILS — prompt only mentions register,
    view, and update students.

    **EXPECTED ON FIXED CODE**: PASSES — prompt mentions bulk import.
    """
    agent_calls = _build_and_invoke_student_agent(trainer_id)

    assert len(agent_calls) >= 1, "student_agent did not create an inner Agent"

    student_call_kwargs = agent_calls[0][1] if agent_calls[0][1] else {}
    system_prompt = student_call_kwargs.get('system_prompt', '')
    prompt_lower = system_prompt.lower()

    assert 'importar' in prompt_lower or 'bulk_import' in prompt_lower, (
        f"student_agent system prompt does not mention bulk import capability. "
        f"The prompt should reference 'importar' or 'bulk_import' so the agent "
        f"knows when to invoke the bulk_import_students tool. "
        f"Current prompt excerpt: {system_prompt[:200]}..."
    )


@given(trainer_id=st.text(min_size=1, max_size=20))
@settings(
    max_examples=10,
    phases=[Phase.generate],
    deadline=None,
)
def test_orchestrator_prompt_has_bulk_import_routing_keywords(trainer_id):
    """
    Property 1 - Test 3: Bug Condition — orchestrator prompt lacks bulk import routing keywords.

    **Validates: Requirements 1.3, 2.3**

    For any trainer_id, the orchestrator system prompt SHALL contain bulk
    import routing keywords: "importar alunos", "planilha", "Google Sheets", "CSV"
    so that bulk import messages are routed to the student_agent.

    **EXPECTED ON UNFIXED CODE**: FAILS — orchestrator routing rules only
    mention "aluno", "registrar aluno", "listar alunos", "atualizar aluno".

    **EXPECTED ON FIXED CODE**: PASSES — routing rules include bulk import keywords.
    """
    orchestrator_prompt = _get_orchestrator_prompt(trainer_id)

    assert orchestrator_prompt is not None, (
        "Could not find orchestrator Agent creation with routing prompt"
    )

    prompt_lower = orchestrator_prompt.lower()

    missing_keywords = []
    required_keywords = [
        'importar alunos',
        'planilha',
        'google sheets',
        'csv',
    ]
    for kw in required_keywords:
        if kw.lower() not in prompt_lower:
            missing_keywords.append(kw)

    assert not missing_keywords, (
        f"Orchestrator routing prompt is missing bulk import keywords: "
        f"{missing_keywords}. The orchestrator needs these keywords to "
        f"correctly route bulk import messages to student_agent. "
        f"Current student_agent routing rule: "
        f"{[line.strip() for line in orchestrator_prompt.split(chr(10)) if 'student_agent' in line.lower()]}"
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
