"""
Unit tests for StrandsAgentService._extract_oauth_url_from_messages helper.

Tests the private method that scans orchestrator messages for OAuth URLs
in tool results from calendar_agent.
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_tool_result_message(text, tool_use_id="tool-123", status="success"):
    """Helper to build an orchestrator message with a toolResult block."""
    return {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": text}],
                    "status": status,
                }
            }
        ],
    }


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


class TestExtractOAuthUrlFromMessages:
    """Tests for _extract_oauth_url_from_messages."""

    def test_google_oauth_url_found(self, service):
        url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&state=xyz123"
        tool_text = f"Para conectar seu Google Calendar, clique no link abaixo:\n\n{url}\n\nO link expira em 30 minutos."
        messages = [_make_tool_result_message(tool_text)]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url == url
        assert full_text == tool_text

    def test_outlook_oauth_url_found(self, service):
        url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=abc&state=xyz"
        tool_text = f"Para conectar seu Outlook Calendar:\n\n{url}\n\nO link expira em 30 minutos."
        messages = [_make_tool_result_message(tool_text)]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url == url
        assert full_text == tool_text

    def test_no_oauth_url_returns_none(self, service):
        messages = [_make_tool_result_message("Aluno João registrado com sucesso!")]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url is None
        assert full_text is None

    def test_empty_messages_returns_none(self, service):
        oauth_url, full_text = service._extract_oauth_url_from_messages([])

        assert oauth_url is None
        assert full_text is None

    def test_skips_non_user_role_messages(self, service):
        url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc"
        messages = [
            {"role": "assistant", "content": [{"text": url}]},
        ]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url is None
        assert full_text is None

    def test_skips_messages_without_tool_result(self, service):
        messages = [
            {"role": "user", "content": [{"text": "Conectar calendário google"}]},
        ]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url is None
        assert full_text is None

    def test_handles_malformed_messages(self, service):
        messages = [
            {"role": "user", "content": "just a string, not a list"},
            {"role": "user"},
            {},
        ]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url is None
        assert full_text is None

    def test_calendar_error_no_url(self, service):
        """Calendar errors (no URL generated) should return None."""
        messages = [
            _make_tool_result_message(
                "Google Calendar integration is not configured. Please contact support.",
                status="error",
            )
        ]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url is None
        assert full_text is None

    def test_finds_url_among_multiple_messages(self, service):
        """Should find the OAuth URL even when mixed with other tool results."""
        url = "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&state=test123&redirect_uri=https%3A%2F%2Fexample.com"
        tool_text = f"Clique no link:\n\n{url}"
        messages = [
            _make_tool_result_message("Aluno registrado com sucesso!"),
            {"role": "assistant", "content": [{"text": "Ok, vou conectar o calendário."}]},
            _make_tool_result_message(tool_text),
        ]

        oauth_url, full_text = service._extract_oauth_url_from_messages(messages)

        assert oauth_url == url
        assert full_text == tool_text
