"""
Bug condition exploration test for OAuth URL lost in orchestrator response.

The orchestrator LLM paraphrases the calendar_agent tool result instead of
passing the OAuth URL through verbatim. The trainer sees "click the link above"
but no actual URL.

Bug condition from design:
  isBugCondition(input, tool_results, final_response) returns true when
  extractOAuthURL(tool_results) IS NOT None AND oauth_url NOT IN final_response

This test mocks the Strands Agent orchestrator to simulate the bug:
- calendar_agent tool result contains OAuth URL
- AgentResult.text paraphrases without the URL

**EXPECTED OUTCOME ON UNFIXED CODE**: Test FAILS (confirms bug exists)

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
"""

import os
import sys
import re
import urllib.parse
from unittest.mock import patch, MagicMock, PropertyMock

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


def provider_strategy():
    """Generate calendar provider names."""
    return st.sampled_from(["google", "outlook"])


def oauth_state_token_strategy():
    """Generate random OAuth state tokens (hex strings)."""
    return st.text(
        alphabet="0123456789abcdef",
        min_size=32,
        max_size=32,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOOGLE_OAUTH_PREFIX = "https://accounts.google.com/o/oauth2/v2/auth"
OUTLOOK_OAUTH_PREFIX = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"

PARAPHRASED_RESPONSES = [
    "Clique no link acima para autorizar o acesso ao Google Calendar.",
    "O link de autorização foi gerado. Clique nele para conectar.",
    "Pronto! Use o link acima para autorizar o acesso ao seu calendário.",
    "Gerei o link de autorização do Outlook Calendar. Clique acima para autorizar.",
    "Link gerado com sucesso! Autorize o acesso clicando no link acima.",
]


def build_oauth_url(provider: str, state_token: str) -> str:
    """Build a realistic OAuth URL for the given provider."""
    if provider == "google":
        params = {
            "client_id": "test-client-id.apps.googleusercontent.com",
            "redirect_uri": "https://api.fitagent.com/oauth/callback",
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/calendar",
            "state": state_token,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_OAUTH_PREFIX}?{urllib.parse.urlencode(params)}"
    else:
        params = {
            "client_id": "test-client-id-outlook",
            "redirect_uri": "https://api.fitagent.com/oauth/callback",
            "response_type": "code",
            "scope": "Calendars.ReadWrite offline_access",
            "state": state_token,
            "response_mode": "query",
        }
        return f"{OUTLOOK_OAUTH_PREFIX}?{urllib.parse.urlencode(params)}"


def build_calendar_agent_tool_result(provider: str, oauth_url: str) -> str:
    """Build the string that calendar_agent would return with the OAuth URL."""
    provider_name = "Google Calendar" if provider == "google" else "Outlook Calendar"
    return (
        f"Para conectar seu {provider_name}, clique no link abaixo para "
        f"autorizar o acesso:\n\n{oauth_url}\n\n"
        f"O link expira em 30 minutos. Após autorizar, suas sessões serão "
        f"sincronizadas automaticamente."
    )


def build_orchestrator_messages_with_tool_result(tool_result_text: str) -> list:
    """
    Build a mock orchestrator.messages list that contains the calendar_agent
    tool result with the OAuth URL, simulating what Strands stores internally.
    """
    return [
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "tool-use-123",
                        "content": [{"text": tool_result_text}],
                        "status": "success",
                    }
                }
            ],
        }
    ]


def create_mock_agent_result(paraphrased_text: str):
    """Create a mock AgentResult that has .text returning the paraphrased text."""
    mock_result = MagicMock()
    mock_result.text = paraphrased_text
    return mock_result


# ---------------------------------------------------------------------------
# Bug Condition Exploration Test
# ---------------------------------------------------------------------------

class TestOAuthURLLostInOrchestratorResponse:
    """
    Property: When calendar_agent returns a response containing an OAuth URL,
    the final response from process_message MUST contain that complete URL.

    On UNFIXED code, the orchestrator LLM paraphrases the tool result and
    drops the URL. process_message has no post-processing to recover it,
    so this property FAILS — proving the bug exists.

    **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
    """

    @given(
        trainer_id=trainer_id_strategy(),
        provider=provider_strategy(),
        state_token=oauth_state_token_strategy(),
        paraphrased_idx=st.integers(min_value=0, max_value=len(PARAPHRASED_RESPONSES) - 1),
    )
    @hyp_settings(
        max_examples=10,
        deadline=30000,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_process_message_preserves_oauth_url(
        self, trainer_id, provider, state_token, paraphrased_idx
    ):
        """
        Simulate the bug condition: calendar_agent returns OAuth URL in tool
        result, but orchestrator's AgentResult.text paraphrases without the URL.

        Assert that process_message response contains the complete OAuth URL.

        **EXPECTED ON UNFIXED CODE**: FAILS — process_message returns the
        paraphrased text without the OAuth URL because there is no
        post-processing to recover dropped URLs.

        **Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
        """
        # Build the OAuth URL and tool result
        oauth_url = build_oauth_url(provider, state_token)
        tool_result_text = build_calendar_agent_tool_result(provider, oauth_url)
        paraphrased_text = PARAPHRASED_RESPONSES[paraphrased_idx]

        # Build mock orchestrator messages containing the tool result
        mock_messages = build_orchestrator_messages_with_tool_result(tool_result_text)

        # Create mock AgentResult with paraphrased text (no URL)
        mock_agent_result = create_mock_agent_result(paraphrased_text)

        # Mock the orchestrator Agent to return our paraphrased result
        mock_orchestrator = MagicMock()
        mock_orchestrator.return_value = mock_agent_result
        mock_orchestrator.messages = mock_messages

        # Patch StrandsAgentService.__init__ to avoid real AWS connections
        with patch.object(StrandsAgentService, '__init__', lambda self, **kwargs: None):
            service = StrandsAgentService()
            service.model = MagicMock()
            service.db_client = MagicMock()
            service.db_client.get_trainer.return_value = {"trainer_id": trainer_id, "name": "Test Trainer"}

            # Patch _build_domain_agent_tools to return mock tools
            mock_tools = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
            with patch.object(service, '_build_domain_agent_tools', return_value=mock_tools):
                # Patch Agent constructor to return our mock orchestrator
                with patch('services.strands_agent_service.Agent', return_value=mock_orchestrator):
                    message = f"Conectar calendário {provider}"
                    result = service.process_message(
                        trainer_id=trainer_id,
                        message=message,
                        phone_number="+5511999999999",
                    )

        # Verify the bug condition holds: tool result has URL but response doesn't
        # extractOAuthURL(tool_results) IS NOT None
        assert oauth_url in tool_result_text, (
            "Test setup error: OAuth URL not in tool result text"
        )
        # oauth_url NOT IN final_response (this is the bug)
        # We assert the EXPECTED behavior: response MUST contain the URL
        assert result.get('success') is True, (
            f"process_message failed: {result.get('error', 'unknown error')}"
        )

        response_text = result.get('response', '')

        # Determine expected URL prefix based on provider
        if provider == "google":
            url_prefix = "https://accounts.google.com/o/oauth2/"
        else:
            url_prefix = "https://login.microsoftonline.com/"

        # The core property: the OAuth URL MUST be in the final response
        assert oauth_url in response_text, (
            f"OAUTH URL LOST BUG: process_message returned response without "
            f"the OAuth URL.\n"
            f"  Provider: {provider}\n"
            f"  Expected URL prefix: {url_prefix}\n"
            f"  OAuth URL: {oauth_url[:80]}...\n"
            f"  Response: {response_text!r}\n"
            f"  Bug condition: calendar_agent tool result contains the OAuth "
            f"URL but the orchestrator paraphrased it away. process_message "
            f"has no post-processing to recover the dropped URL."
        )
