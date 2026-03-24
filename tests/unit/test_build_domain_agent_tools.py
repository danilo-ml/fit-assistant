"""
Unit tests for StrandsAgentService._build_domain_agent_tools() and orchestrator tools.

Verifies that the method returns notification_agent in the tuple and that
the orchestrator Agent is created with notification_agent in its tools list,
confirming the bugfix for notification agent registration.
"""

import pytest
from unittest.mock import patch, MagicMock, call


@pytest.fixture
def service():
    """Create a StrandsAgentService instance with mocked dependencies."""
    with patch("services.strands_agent_service.BedrockModel"), \
         patch("services.strands_agent_service.DynamoDBClient"):
        from services.strands_agent_service import StrandsAgentService
        return StrandsAgentService(
            model_id="test-model",
            region="us-east-1",
            endpoint_url="https://test-endpoint",
        )


class TestBuildDomainAgentToolsReturnsNotificationAgent:
    """Tests that _build_domain_agent_tools() includes notification_agent."""

    def test_returns_tuple_with_five_elements(self, service):
        """The method should return a 5-element tuple after the fix."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        assert isinstance(result, tuple)
        assert len(result) == 5

    def test_notification_agent_is_fifth_element(self, service):
        """notification_agent should be the 5th element in the returned tuple."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        student_agent, session_agent, payment_agent, calendar_agent, notification_agent = result
        assert notification_agent is not None

    def test_notification_agent_is_callable(self, service):
        """notification_agent should be a callable tool function."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        *_, notification_agent = result
        assert callable(notification_agent)

    def test_all_existing_agents_still_returned(self, service):
        """All 4 original agents should still be present alongside notification_agent."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        student_agent, session_agent, payment_agent, calendar_agent, notification_agent = result
        assert callable(student_agent)
        assert callable(session_agent)
        assert callable(payment_agent)
        assert callable(calendar_agent)


class TestOrchestratorToolsIncludeNotificationAgent:
    """Tests that the orchestrator Agent is created with notification_agent in its tools list."""

    def test_orchestrator_tools_list_includes_notification_agent(self, service):
        """The orchestrator Agent should be created with notification_agent in tools."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="mocked response")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(
                trainer_id="trainer-123",
                message="Olá, envie uma notificação",
            )

        # The orchestrator is the Agent() call that receives the tools kwarg
        orchestrator_call = None
        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                orchestrator_call = c
                break

        assert orchestrator_call is not None, "Agent() was never called with a tools list"
        tools = orchestrator_call.kwargs["tools"]
        tool_names = [getattr(t, "__name__", str(t)) for t in tools]
        assert "notification_agent" in tool_names, (
            f"notification_agent not found in orchestrator tools: {tool_names}"
        )

    def test_orchestrator_tools_list_has_five_agents(self, service):
        """The orchestrator should have exactly 5 agent tools."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="ok")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(
                trainer_id="trainer-123",
                message="teste",
            )

        orchestrator_call = None
        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                orchestrator_call = c
                break

        assert orchestrator_call is not None
        tools = orchestrator_call.kwargs["tools"]
        assert len(tools) == 5, f"Expected 5 tools, got {len(tools)}"

    def test_orchestrator_tools_contain_all_expected_agents(self, service):
        """The orchestrator tools should contain all 5 domain agents by name."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="ok")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(
                trainer_id="trainer-123",
                message="teste",
            )

        orchestrator_call = None
        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                orchestrator_call = c
                break

        assert orchestrator_call is not None
        tools = orchestrator_call.kwargs["tools"]
        tool_names = {getattr(t, "__name__", str(t)) for t in tools}
        expected = {"student_agent", "session_agent", "payment_agent", "calendar_agent", "notification_agent"}
        assert expected == tool_names, f"Expected {expected}, got {tool_names}"


class TestOrchestratorPromptMentionsNotificationAgent:
    """Tests that the orchestrator_prompt references notification_agent and routing keywords."""

    def _get_orchestrator_prompt(self, service):
        """Helper: invoke process_message and capture the system_prompt passed to the orchestrator Agent."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="ok")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(trainer_id="trainer-123", message="teste")

        # Find the orchestrator Agent() call (the one with a tools kwarg)
        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                return c.kwargs.get("system_prompt", "")
        pytest.fail("Agent() was never called with a tools list")

    def test_prompt_mentions_notification_agent(self, service):
        """The orchestrator system prompt should reference notification_agent."""
        prompt = self._get_orchestrator_prompt(service)
        assert "notification_agent" in prompt

    def test_prompt_contains_routing_keywords(self, service):
        """The orchestrator prompt should contain routing keywords for notifications."""
        prompt = self._get_orchestrator_prompt(service)
        expected_keywords = [
            "notificação",
            "notificar",
            "avisar",
            "mensagem para alunos",
            "enviar mensagem",
            "broadcast",
        ]
        found = [kw for kw in expected_keywords if kw in prompt.lower()]
        assert len(found) >= 3, (
            f"Expected at least 3 routing keywords in prompt, found {len(found)}: {found}"
        )

    def test_prompt_describes_notification_agent_role(self, service):
        """The prompt should describe what notification_agent handles."""
        prompt = self._get_orchestrator_prompt(service)
        # The prompt should associate notification_agent with sending notifications/messages
        assert "notification_agent" in prompt
        # Check that notification_agent line describes its purpose
        prompt_lower = prompt.lower()
        assert any(
            word in prompt_lower
            for word in ["notificação", "notificar", "mensagem", "avisar"]
        ), "Prompt should describe notification_agent's purpose with notification-related words"


class TestExistingAgentsPreservation:
    """Preservation tests: verify the 4 original agents (student, session, payment, calendar)
    remain present, correctly ordered, and properly referenced after the notification_agent fix.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """

    ORIGINAL_AGENT_NAMES = ["student_agent", "session_agent", "payment_agent", "calendar_agent"]

    def test_original_agents_tuple_order_preserved(self, service):
        """The first 4 elements must be student, session, payment, calendar in that order."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        for idx, expected_name in enumerate(self.ORIGINAL_AGENT_NAMES):
            actual_name = getattr(result[idx], "__name__", None)
            assert actual_name == expected_name, (
                f"Position {idx}: expected '{expected_name}', got '{actual_name}'"
            )

    def test_each_existing_agent_has_correct_name(self, service):
        """Each original agent tool function should have the correct __name__ attribute."""
        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = MagicMock(return_value="mocked response")
            result = service._build_domain_agent_tools("trainer-123")

        agent_names = [getattr(t, "__name__", None) for t in result[:4]]
        assert agent_names == self.ORIGINAL_AGENT_NAMES

    def test_each_existing_agent_accepts_query_parameter(self, service):
        """Each original agent should accept a 'query' string parameter (Agents-as-Tools pattern)."""
        mock_agent_instance = MagicMock(return_value="mocked response")

        with patch("strands.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            result = service._build_domain_agent_tools("trainer-123")

        for idx, expected_name in enumerate(self.ORIGINAL_AGENT_NAMES):
            agent_fn = result[idx]
            # Calling with a query string should not raise TypeError
            agent_fn(query="test query")

    def test_orchestrator_tools_order_preserves_original_agents(self, service):
        """The orchestrator tools list should have the 4 original agents in positions 0-3."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="ok")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(trainer_id="trainer-123", message="teste")

        orchestrator_call = None
        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                orchestrator_call = c
                break

        assert orchestrator_call is not None
        tools = orchestrator_call.kwargs["tools"]
        first_four_names = [getattr(t, "__name__", str(t)) for t in tools[:4]]
        assert first_four_names == self.ORIGINAL_AGENT_NAMES, (
            f"First 4 tools should be original agents in order, got {first_four_names}"
        )

    def _get_orchestrator_prompt(self, service):
        """Helper: capture the system_prompt passed to the orchestrator Agent."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(text="ok")
        mock_agent_instance.messages = []

        mock_db = MagicMock()
        mock_db.get_trainer.return_value = {"PK": "TRAINER#t1", "SK": "METADATA"}
        service.db_client = mock_db

        with patch("services.strands_agent_service.Agent") as mock_agent_cls:
            mock_agent_cls.return_value = mock_agent_instance
            service.process_message(trainer_id="trainer-123", message="teste")

        for c in mock_agent_cls.call_args_list:
            if c.kwargs.get("tools"):
                return c.kwargs.get("system_prompt", "")
        pytest.fail("Agent() was never called with a tools list")

    def test_prompt_still_mentions_all_original_agents(self, service):
        """The orchestrator prompt must still reference all 4 original agents by name."""
        prompt = self._get_orchestrator_prompt(service)
        for agent_name in self.ORIGINAL_AGENT_NAMES:
            assert agent_name in prompt, (
                f"Original agent '{agent_name}' missing from orchestrator prompt"
            )

    def test_prompt_still_has_student_agent_routing_keywords(self, service):
        """The prompt must still contain routing keywords for student_agent."""
        prompt = self._get_orchestrator_prompt(service).lower()
        student_keywords = ["aluno", "registrar", "listar alunos", "atualizar aluno"]
        found = [kw for kw in student_keywords if kw in prompt]
        assert len(found) >= 2, (
            f"Expected at least 2 student routing keywords, found {found}"
        )

    def test_prompt_still_has_session_agent_routing_keywords(self, service):
        """The prompt must still contain routing keywords for session_agent."""
        prompt = self._get_orchestrator_prompt(service).lower()
        session_keywords = ["sessão", "agendar", "reagendar", "cancelar", "calendário"]
        found = [kw for kw in session_keywords if kw in prompt]
        assert len(found) >= 2, (
            f"Expected at least 2 session routing keywords, found {found}"
        )

    def test_prompt_still_has_payment_agent_routing_keywords(self, service):
        """The prompt must still contain routing keywords for payment_agent."""
        prompt = self._get_orchestrator_prompt(service).lower()
        payment_keywords = ["pagamento", "pagar", "recibo", "mensalidade"]
        found = [kw for kw in payment_keywords if kw in prompt]
        assert len(found) >= 2, (
            f"Expected at least 2 payment routing keywords, found {found}"
        )

    def test_prompt_still_has_calendar_agent_routing_keywords(self, service):
        """The prompt must still contain routing keywords for calendar_agent."""
        prompt = self._get_orchestrator_prompt(service).lower()
        calendar_keywords = ["conectar calendário", "sincronizar", "google calendar", "outlook"]
        found = [kw for kw in calendar_keywords if kw in prompt]
        assert len(found) >= 2, (
            f"Expected at least 2 calendar routing keywords, found {found}"
        )
