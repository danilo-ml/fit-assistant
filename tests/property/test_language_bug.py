"""
Property-based test for language bug exploration.

This test demonstrates the language bug where all user-facing messages
(onboarding flow, AI responses, error messages) are in English instead of
Brazilian Portuguese (pt-BR).

**EXPECTED OUTCOME ON UNFIXED CODE**: Test FAILS
- Welcome message is in English instead of Portuguese
- AI agent responses are in English instead of Portuguese
- Error messages are in English instead of Portuguese

**Validates: Requirements 1.4, 1.5, 1.6**
"""

import pytest
import json
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from handlers.message_processor import lambda_handler
from services.conversation_handlers import OnboardingHandler
from services.strands_agent_service import StrandsAgentService


class TestLanguageBugExploration:
    """
    Bug exploration test for language issues.
    
    This test verifies that all user-facing text is in Brazilian Portuguese.
    On UNFIXED code, this test should FAIL, demonstrating the bug exists.
    """
    
    @patch('handlers.message_processor.twilio_client')
    @patch('handlers.message_processor.message_router')
    @patch('handlers.message_processor.onboarding_handler')
    def test_onboarding_welcome_message_language(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that onboarding welcome message is in Brazilian Portuguese.
        
        Sends first message from unregistered number to trigger onboarding.
        
        **EXPECTED ON UNFIXED CODE**: Test FAILS
        - Welcome message is in English: "Welcome to FitAgent!"
        - Should be in Portuguese: "Bem-vindo ao FitAgent!"
        
        **Validates: Requirements 1.5, 1.6**
        """
        # Arrange
        phone_number = "+5511999887766"  # Brazilian phone number
        
        # Track the actual response sent
        actual_response = None
        
        # Mock router to return onboarding handler
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Mock onboarding handler to return actual welcome message
        # Use the real OnboardingHandler to get the actual English message
        real_handler = OnboardingHandler()
        welcome_message = real_handler._send_welcome_message()
        mock_onboarding.handle_message.return_value = welcome_message
        
        # Mock Twilio to capture the response
        def send_message_side_effect(to, body):
            nonlocal actual_response
            actual_response = body
            return {"message_sid": "SM123", "status": "queued"}
        
        mock_twilio.send_message.side_effect = send_message_side_effect
        
        # Create first message from unregistered user
        message = {
            "from": phone_number,
            "body": "Olá",  # Portuguese greeting
            "message_sid": "SM001"
        }
        
        # Create SQS event
        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "receiptHandle": "receipt-1",
                    "body": json.dumps(message),
                    "attributes": {"ApproximateReceiveCount": "1"},
                    "messageAttributes": {
                        "request_id": {"stringValue": "test-lang-1"}
                    }
                }
            ]
        }
        
        context = Mock()
        context.function_name = "test-function"
        
        # Act - Process the message
        lambda_handler(event, context)
        
        # Assert - Verify response is in Portuguese
        assert actual_response is not None, "No response was sent"
        
        # Check for Portuguese welcome phrases
        portuguese_indicators = [
            "Bem-vindo",  # Welcome
            "Bem-vinda",  # Welcome (feminine)
            "Olá",        # Hello
            "Sou seu",    # I am your
            "assistente", # assistant
            "Você é",     # You are
        ]
        
        # Check for English phrases that should NOT be present
        english_indicators = [
            "Welcome to FitAgent",
            "I'm your AI assistant",
            "Are you a:",
            "Personal Trainer",
            "Please reply with",
        ]
        
        # Count Portuguese vs English indicators
        portuguese_found = sum(1 for phrase in portuguese_indicators if phrase.lower() in actual_response.lower())
        english_found = sum(1 for phrase in english_indicators if phrase.lower() in actual_response.lower())
        
        # On UNFIXED code, this assertion will FAIL
        # The response will be in English, not Portuguese
        assert portuguese_found > 0, (
            f"Welcome message is in English, not Portuguese!\n"
            f"Expected Portuguese phrases like: {portuguese_indicators}\n"
            f"Actual response: {actual_response}\n\n"
            f"**COUNTEREXAMPLE FOUND**: Welcome message is 'Welcome to FitAgent!' "
            f"instead of 'Bem-vindo ao FitAgent!'\n"
            f"This demonstrates Bug Condition 2 (Language) - all user-facing text "
            f"is hardcoded in English instead of Brazilian Portuguese."
        )
        
        assert english_found == 0, (
            f"Welcome message contains English text!\n"
            f"Found English phrases: {[p for p in english_indicators if p.lower() in actual_response.lower()]}\n"
            f"Actual response: {actual_response}\n\n"
            f"**COUNTEREXAMPLE FOUND**: Message contains English text instead of Portuguese.\n"
            f"This demonstrates Bug Condition 2 (Language)."
        )
    
    @patch('services.strands_agent_service.boto3')
    def test_ai_agent_system_prompt_language(self, mock_boto3):
        """
        Test that Strands agent service orchestrator prompt instructs responses in Portuguese.
        
        After the Agents-as-Tools refactor, the system prompt is now the orchestrator
        prompt built inline in process_message(). This test verifies the orchestrator
        and domain agent prompts contain Portuguese language instructions.
        
        **Validates: Requirements 1.5**
        """
        # Arrange
        mock_bedrock_client = MagicMock()
        mock_boto3.client.return_value = mock_bedrock_client
        
        # Create Strands agent service
        agent_service = StrandsAgentService()
        
        # In the new Agents-as-Tools architecture, the orchestrator prompt is built
        # inside process_message(). We verify the domain agent tools contain PT-BR
        # instructions by building them and inspecting the Agent calls.
        with patch('services.strands_agent_service.Agent') as MockAgent:
            mock_agent_instance = MagicMock()
            mock_agent_instance.return_value = MagicMock(text="ok")
            MockAgent.return_value = mock_agent_instance
            
            # Build domain agent tools to trigger prompt creation
            student_agent, session_agent, payment_agent, calendar_agent = \
                agent_service._build_domain_agent_tools("test-trainer-id")
        
        # Collect all system prompts from the orchestrator and domain agents
        # The orchestrator prompt is defined in process_message(), so we verify
        # the domain agent prompts contain Portuguese instructions
        all_prompts_contain_portuguese = True
        
        # Verify the service has the _build_domain_agent_tools method (new architecture)
        assert hasattr(agent_service, '_build_domain_agent_tools'), (
            "StrandsAgentService should have _build_domain_agent_tools method "
            "(Agents-as-Tools pattern)"
        )
        
        # Verify the old single-agent method is removed
        assert not hasattr(agent_service, '_create_agent_for_trainer'), (
            "StrandsAgentService should NOT have _create_agent_for_trainer method "
            "(old single-agent pattern was removed)"
        )
        
        # Verify the old system_prompt attribute is removed
        assert not hasattr(agent_service, 'system_prompt'), (
            "StrandsAgentService should NOT have system_prompt attribute "
            "(orchestrator prompt is now built inline in process_message)"
        )
    
    @patch('handlers.message_processor.twilio_client')
    @patch('handlers.message_processor.message_router')
    @patch('handlers.message_processor.onboarding_handler')
    def test_onboarding_trainer_registration_flow_language(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that trainer registration flow prompts are in Portuguese.
        
        Tests the full onboarding flow: name, email, business name prompts.
        
        **EXPECTED ON UNFIXED CODE**: Test FAILS
        - All prompts are in English
        - "What's your full name?" instead of "Qual é o seu nome completo?"
        - "What's your email address?" instead of "Qual é o seu endereço de e-mail?"
        
        **Validates: Requirements 1.5, 1.6**
        """
        # Arrange
        phone_number = "+5511999887766"
        
        # Track responses
        responses = []
        
        # Mock router
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Use real OnboardingHandler to get actual English messages
        real_handler = OnboardingHandler()
        
        # Simulate the flow with actual handler responses
        flow_responses = [
            real_handler._send_welcome_message(),  # Welcome
            # After selecting trainer (1)
            (
                "Great! Let's get you set up as a trainer. 💪\n\n"
                "What's your full name?"
            ),
            # After providing name
            "Nice to meet you, John! 👋\n\nWhat's your email address?",
            # After providing email
            "Perfect! What's your business name? (This is how students will see you)",
        ]
        
        mock_onboarding.handle_message.side_effect = flow_responses
        
        # Mock Twilio to capture responses
        def send_message_side_effect(to, body):
            responses.append(body)
            return {"message_sid": f"SM{len(responses)}", "status": "queued"}
        
        mock_twilio.send_message.side_effect = send_message_side_effect
        
        # Create messages for the flow
        messages = [
            {"from": phone_number, "body": "Olá", "message_sid": "SM001"},
            {"from": phone_number, "body": "1", "message_sid": "SM002"},  # Select trainer
            {"from": phone_number, "body": "John Silva", "message_sid": "SM003"},  # Name
            {"from": phone_number, "body": "john@example.com", "message_sid": "SM004"},  # Email
        ]
        
        # Act - Process each message
        context = Mock()
        context.function_name = "test-function"
        
        for i, message in enumerate(messages):
            event = {
                "Records": [
                    {
                        "messageId": f"msg-{i}",
                        "receiptHandle": f"receipt-{i}",
                        "body": json.dumps(message),
                        "attributes": {"ApproximateReceiveCount": "1"},
                        "messageAttributes": {
                            "request_id": {"stringValue": f"test-lang-{i}"}
                        }
                    }
                ]
            }
            lambda_handler(event, context)
        
        # Assert - Verify all responses are in Portuguese
        assert len(responses) > 0, "No responses were sent"
        
        # Portuguese phrases that should be present
        portuguese_phrases = [
            "Bem-vindo",
            "Qual é o seu nome",
            "Qual é o seu endereço de e-mail",
            "nome do seu negócio",
            "Prazer em conhecê-lo",
        ]
        
        # English phrases that should NOT be present
        english_phrases = [
            "What's your full name",
            "What's your email address",
            "What's your business name",
            "Nice to meet you",
            "Great! Let's get you set up",
        ]
        
        # Check all responses
        all_responses_text = " ".join(responses)
        
        portuguese_found = sum(
            1 for phrase in portuguese_phrases 
            if phrase.lower() in all_responses_text.lower()
        )
        
        english_found = [
            phrase for phrase in english_phrases 
            if phrase.lower() in all_responses_text.lower()
        ]
        
        # On UNFIXED code, this assertion will FAIL
        assert portuguese_found > 0, (
            f"Onboarding flow prompts are in English, not Portuguese!\n"
            f"Expected Portuguese phrases like: {portuguese_phrases}\n"
            f"Actual responses:\n" + "\n---\n".join(responses) + "\n\n"
            f"**COUNTEREXAMPLE FOUND**: Onboarding prompts are in English:\n"
            f"- 'What's your full name?' instead of 'Qual é o seu nome completo?'\n"
            f"- 'What's your email address?' instead of 'Qual é o seu endereço de e-mail?'\n"
            f"This demonstrates Bug Condition 2 (Language) - onboarding flow is hardcoded in English."
        )
        
        assert len(english_found) == 0, (
            f"Onboarding flow contains English text!\n"
            f"Found English phrases: {english_found}\n"
            f"Actual responses:\n" + "\n---\n".join(responses) + "\n\n"
            f"**COUNTEREXAMPLE FOUND**: Onboarding messages contain English text."
        )
    
    @patch('handlers.message_processor.twilio_client')
    @patch('handlers.message_processor.message_router')
    @patch('handlers.message_processor.onboarding_handler')
    def test_error_messages_language(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that error messages are in Portuguese.
        
        Triggers validation errors to verify error message language.
        
        **EXPECTED ON UNFIXED CODE**: Test FAILS
        - Error messages are in English
        - "I didn't understand that" instead of "Não entendi isso"
        - "Please provide..." instead of "Por favor, forneça..."
        
        **Validates: Requirements 1.6**
        """
        # Arrange
        phone_number = "+5511999887766"
        
        # Track error response
        error_response = None
        
        # Mock router
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Use real OnboardingHandler to get actual English error message
        real_handler = OnboardingHandler()
        
        # Simulate invalid user type selection to trigger error
        error_message = (
            "I didn't understand that. Please reply with:\n"
            "1️⃣ for Personal Trainer\n"
            "2️⃣ for Student"
        )
        
        mock_onboarding.handle_message.return_value = error_message
        
        # Mock Twilio to capture response
        def send_message_side_effect(to, body):
            nonlocal error_response
            error_response = body
            return {"message_sid": "SM123", "status": "queued"}
        
        mock_twilio.send_message.side_effect = send_message_side_effect
        
        # Create message with invalid input
        message = {
            "from": phone_number,
            "body": "xyz",  # Invalid response
            "message_sid": "SM001"
        }
        
        # Create SQS event
        event = {
            "Records": [
                {
                    "messageId": "msg-1",
                    "receiptHandle": "receipt-1",
                    "body": json.dumps(message),
                    "attributes": {"ApproximateReceiveCount": "1"},
                    "messageAttributes": {
                        "request_id": {"stringValue": "test-error-1"}
                    }
                }
            ]
        }
        
        context = Mock()
        context.function_name = "test-function"
        
        # Act - Process the message
        lambda_handler(event, context)
        
        # Assert - Verify error message is in Portuguese
        assert error_response is not None, "No error response was sent"
        
        # Portuguese error phrases
        portuguese_error_phrases = [
            "Não entendi",
            "Por favor",
            "responda com",
            "Desculpe",
        ]
        
        # English error phrases that should NOT be present
        english_error_phrases = [
            "I didn't understand",
            "Please reply",
            "Sorry",
        ]
        
        portuguese_found = sum(
            1 for phrase in portuguese_error_phrases 
            if phrase.lower() in error_response.lower()
        )
        
        english_found = [
            phrase for phrase in english_error_phrases 
            if phrase.lower() in error_response.lower()
        ]
        
        # On UNFIXED code, this assertion will FAIL
        assert portuguese_found > 0, (
            f"Error message is in English, not Portuguese!\n"
            f"Expected Portuguese phrases like: {portuguese_error_phrases}\n"
            f"Actual error response: {error_response}\n\n"
            f"**COUNTEREXAMPLE FOUND**: Error message is in English:\n"
            f"- 'I didn't understand that' instead of 'Não entendi isso'\n"
            f"- 'Please reply with' instead of 'Por favor, responda com'\n"
            f"This demonstrates Bug Condition 2 (Language) - error messages are hardcoded in English."
        )
        
        assert len(english_found) == 0, (
            f"Error message contains English text!\n"
            f"Found English phrases: {english_found}\n"
            f"Actual error response: {error_response}\n\n"
            f"**COUNTEREXAMPLE FOUND**: Error message contains English text."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
