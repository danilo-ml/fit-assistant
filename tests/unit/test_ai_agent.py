"""
Unit tests for AI Agent service.

Tests the AIAgent class including:
- Tool registry construction
- Tool execution mapping
- Message processing with Bedrock
- Tool execution with parameter injection
- Error handling and user-friendly messages
- Conversation context management
- 5-second execution time requirement

Uses moto for AWS mocking and pytest fixtures for test data.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import json

from src.services.ai_agent import AIAgent
from src.config import settings


class TestAIAgentInitialization:
    """Test AIAgent initialization and setup."""

    def test_agent_initialization_with_defaults(self):
        """Test agent initializes with default settings."""
        agent = AIAgent()
        
        assert agent.model_id == settings.bedrock_model_id
        assert agent.region == settings.bedrock_region
        assert agent.bedrock_client is not None
        assert len(agent.tool_registry) == 11  # 11 tools total
        assert len(agent.tool_execution_map) == 11

    def test_agent_initialization_with_custom_params(self):
        """Test agent initializes with custom parameters."""
        custom_model = "anthropic.claude-3-haiku-20240307-v1:0"
        custom_region = "us-west-2"
        
        agent = AIAgent(model_id=custom_model, region=custom_region)
        
        assert agent.model_id == custom_model
        assert agent.region == custom_region

    def test_tool_registry_structure(self):
        """Test tool registry has correct structure."""
        agent = AIAgent()
        
        # Verify all tools have required fields
        for tool in agent.tool_registry:
            assert "toolSpec" in tool
            assert "name" in tool["toolSpec"]
            assert "description" in tool["toolSpec"]
            assert "inputSchema" in tool["toolSpec"]
            assert "json" in tool["toolSpec"]["inputSchema"]

    def test_tool_registry_contains_all_tools(self):
        """Test tool registry contains all 11 required tools."""
        agent = AIAgent()
        
        tool_names = [tool["toolSpec"]["name"] for tool in agent.tool_registry]
        
        expected_tools = [
            "register_student",
            "view_students",
            "update_student",
            "schedule_session",
            "reschedule_session",
            "cancel_session",
            "view_calendar",
            "register_payment",
            "confirm_payment",
            "view_payments",
            "connect_calendar",
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"

    def test_tool_execution_map_completeness(self):
        """Test tool execution map contains all tools."""
        agent = AIAgent()
        
        expected_tools = [
            "register_student",
            "view_students",
            "update_student",
            "schedule_session",
            "reschedule_session",
            "cancel_session",
            "view_calendar",
            "register_payment",
            "confirm_payment",
            "view_payments",
            "connect_calendar",
        ]
        
        for tool_name in expected_tools:
            assert tool_name in agent.tool_execution_map
            assert callable(agent.tool_execution_map[tool_name])


class TestToolExecution:
    """Test tool execution with parameter injection."""

    def test_execute_tool_with_valid_parameters(self):
        """Test executing a tool with valid parameters."""
        agent = AIAgent()
        
        # Mock the tool function in the execution map
        mock_view_students = Mock(return_value={
            "success": True,
            "data": {"students": []}
        })
        agent.tool_execution_map["view_students"] = mock_view_students
        
        result = agent._execute_tool(
            trainer_id="trainer123",
            tool_name="view_students",
            tool_input={},
        )
        
        assert result["success"] is True
        mock_view_students.assert_called_once_with(trainer_id="trainer123")

    def test_execute_tool_injects_trainer_id(self):
        """Test that trainer_id is automatically injected into tool calls."""
        agent = AIAgent()
        
        # Mock the tool function in the execution map
        mock_register = Mock(return_value={
            "success": True,
            "data": {"student_id": "student123"}
        })
        agent.tool_execution_map["register_student"] = mock_register
        
        result = agent._execute_tool(
            trainer_id="trainer456",
            tool_name="register_student",
            tool_input={
                "name": "John Doe",
                "phone_number": "+14155552671",
                "email": "john@example.com",
                "training_goal": "Build muscle"
            },
        )
        
        # Verify trainer_id was injected
        mock_register.assert_called_once()
        call_args = mock_register.call_args[1]
        assert call_args["trainer_id"] == "trainer456"
        assert call_args["name"] == "John Doe"

    def test_execute_tool_with_unknown_tool(self):
        """Test executing an unknown tool returns error."""
        agent = AIAgent()
        
        result = agent._execute_tool(
            trainer_id="trainer123",
            tool_name="unknown_tool",
            tool_input={},
        )
        
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_execute_tool_with_invalid_parameters(self):
        """Test executing a tool with invalid parameters returns error."""
        agent = AIAgent()
        
        with patch('src.tools.student_tools.register_student') as mock_register:
            # Simulate TypeError from missing required parameter
            mock_register.side_effect = TypeError("missing required argument: 'name'")
            
            result = agent._execute_tool(
                trainer_id="trainer123",
                tool_name="register_student",
                tool_input={},  # Missing required parameters
            )
            
            assert result["success"] is False
            assert "Invalid parameters" in result["error"]

    def test_execute_tool_handles_tool_failure(self):
        """Test executing a tool that returns failure."""
        agent = AIAgent()
        
        # Mock the tool function in the execution map
        mock_register = Mock(return_value={
            "success": False,
            "error": "Student already exists"
        })
        agent.tool_execution_map["register_student"] = mock_register
        
        result = agent._execute_tool(
            trainer_id="trainer123",
            tool_name="register_student",
            tool_input={
                "name": "John Doe",
                "phone_number": "+14155552671",
                "email": "john@example.com",
                "training_goal": "Build muscle"
            },
        )
        
        assert result["success"] is False
        assert result["error"] == "Student already exists"


class TestSystemPrompt:
    """Test system prompt generation."""

    def test_build_system_prompt_includes_trainer_id(self):
        """Test system prompt includes trainer ID."""
        agent = AIAgent()
        
        prompt = agent._build_system_prompt("trainer123")
        
        assert "trainer123" in prompt
        assert "FitAgent" in prompt

    def test_build_system_prompt_includes_capabilities(self):
        """Test system prompt describes agent capabilities."""
        agent = AIAgent()
        
        prompt = agent._build_system_prompt("trainer123")
        
        # Check for key capabilities
        assert "students" in prompt.lower()
        assert "sessions" in prompt.lower() or "schedule" in prompt.lower()
        assert "payments" in prompt.lower()
        assert "calendar" in prompt.lower()


class TestMessageProcessing:
    """Test message processing with Bedrock integration."""

    @patch('boto3.client')
    def test_process_message_simple_response(self, mock_boto_client):
        """Test processing a message that doesn't require tools."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Bedrock response (no tool use)
        mock_bedrock.converse.return_value = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Hello! How can I help you today?"}
                    ]
                }
            }
        }
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        result = agent.process_message(
            trainer_id="trainer123",
            message="Hello",
        )
        
        assert result["success"] is True
        assert "Hello" in result["response"]
        assert len(result["tool_calls"]) == 0
        assert result["execution_time"] < 5.0

    @patch('boto3.client')
    def test_process_message_with_tool_use(self, mock_boto_client):
        """Test processing a message that requires tool execution."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Bedrock responses (tool use, then final response)
        mock_bedrock.converse.side_effect = [
            # First call: Bedrock requests tool use
            {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool123",
                                    "name": "view_students",
                                    "input": {}
                                }
                            }
                        ]
                    }
                }
            },
            # Second call: Bedrock provides final response
            {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"text": "You have 0 students registered."}
                        ]
                    }
                }
            }
        ]
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        # Mock the tool execution
        with patch('src.tools.student_tools.view_students') as mock_view_students:
            mock_view_students.return_value = {
                "success": True,
                "data": {"students": []}
            }
            
            result = agent.process_message(
                trainer_id="trainer123",
                message="Show me my students",
            )
            
            assert result["success"] is True
            assert "students" in result["response"].lower()
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["tool"] == "view_students"
            assert result["execution_time"] < 5.0

    @patch('boto3.client')
    def test_process_message_with_multiple_tools(self, mock_boto_client):
        """Test processing a message that requires multiple tool calls."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Mock Bedrock responses (multiple tool uses)
        mock_bedrock.converse.side_effect = [
            # First call: Request view_students
            {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool1",
                                    "name": "view_students",
                                    "input": {}
                                }
                            }
                        ]
                    }
                }
            },
            # Second call: Request view_calendar
            {
                "stopReason": "tool_use",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "toolUse": {
                                    "toolUseId": "tool2",
                                    "name": "view_calendar",
                                    "input": {"filter": "week"}
                                }
                            }
                        ]
                    }
                }
            },
            # Third call: Final response
            {
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"text": "You have 2 students and 3 sessions this week."}
                        ]
                    }
                }
            }
        ]
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        # Mock the tool executions
        with patch('src.tools.student_tools.view_students') as mock_view_students, \
             patch('src.tools.session_tools.view_calendar') as mock_view_calendar:
            
            mock_view_students.return_value = {
                "success": True,
                "data": {"students": [{"name": "John"}, {"name": "Jane"}]}
            }
            
            mock_view_calendar.return_value = {
                "success": True,
                "data": {"sessions": [{}, {}, {}], "total_count": 3}
            }
            
            result = agent.process_message(
                trainer_id="trainer123",
                message="Give me a summary of my students and schedule",
            )
            
            assert result["success"] is True
            assert len(result["tool_calls"]) == 2
            assert result["tool_calls"][0]["tool"] == "view_students"
            assert result["tool_calls"][1]["tool"] == "view_calendar"

    @patch('boto3.client')
    def test_process_message_with_conversation_history(self, mock_boto_client):
        """Test processing a message with conversation history."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_bedrock.converse.return_value = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Sure, I'll schedule that session."}
                    ]
                }
            }
        }
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        conversation_history = [
            {
                "role": "user",
                "content": [{"text": "I want to schedule a session"}]
            },
            {
                "role": "assistant",
                "content": [{"text": "Sure! Which student is this for?"}]
            },
        ]
        
        result = agent.process_message(
            trainer_id="trainer123",
            message="John Doe",
            conversation_history=conversation_history,
        )
        
        assert result["success"] is True
        # Verify conversation history was included in the call
        call_args = mock_bedrock.converse.call_args[1]
        assert len(call_args["messages"]) >= 3  # History + new message

    @patch('boto3.client')
    def test_process_message_handles_bedrock_error(self, mock_boto_client):
        """Test handling Bedrock API errors gracefully."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Simulate Bedrock error
        from botocore.exceptions import ClientError
        mock_bedrock.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "converse"
        )
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        result = agent.process_message(
            trainer_id="trainer123",
            message="Hello",
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "try again" in result["error"].lower()

    @patch('boto3.client')
    def test_process_message_max_iterations(self, mock_boto_client):
        """Test that max iterations prevents infinite loops."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        # Always return tool_use to create infinite loop
        mock_bedrock.converse.return_value = {
            "stopReason": "tool_use",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tool123",
                                "name": "view_students",
                                "input": {}
                            }
                        }
                    ]
                }
            }
        }
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        with patch('src.tools.student_tools.view_students') as mock_view_students:
            mock_view_students.return_value = {
                "success": True,
                "data": {"students": []}
            }
            
            result = agent.process_message(
                trainer_id="trainer123",
                message="Show me my students",
            )
            
            assert result["success"] is False
            assert "maximum" in result["error"].lower() or "iterations" in result["error"].lower()


class TestToolSchemas:
    """Test tool schema definitions."""

    def test_register_student_schema(self):
        """Test register_student tool has correct schema."""
        agent = AIAgent()
        
        tool = next(
            t for t in agent.tool_registry
            if t["toolSpec"]["name"] == "register_student"
        )
        
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert "name" in schema["properties"]
        assert "phone_number" in schema["properties"]
        assert "email" in schema["properties"]
        assert "training_goal" in schema["properties"]
        assert set(schema["required"]) == {"name", "phone_number", "email", "training_goal"}

    def test_schedule_session_schema(self):
        """Test schedule_session tool has correct schema."""
        agent = AIAgent()
        
        tool = next(
            t for t in agent.tool_registry
            if t["toolSpec"]["name"] == "schedule_session"
        )
        
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert "student_name" in schema["properties"]
        assert "date" in schema["properties"]
        assert "time" in schema["properties"]
        assert "duration_minutes" in schema["properties"]
        assert "location" in schema["properties"]
        assert set(schema["required"]) == {"student_name", "date", "time", "duration_minutes"}

    def test_view_calendar_schema(self):
        """Test view_calendar tool has correct schema."""
        agent = AIAgent()
        
        tool = next(
            t for t in agent.tool_registry
            if t["toolSpec"]["name"] == "view_calendar"
        )
        
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert "start_date" in schema["properties"]
        assert "end_date" in schema["properties"]
        assert "filter" in schema["properties"]
        assert schema["properties"]["filter"]["enum"] == ["day", "week", "month"]
        assert len(schema["required"]) == 0  # All parameters optional

    def test_register_payment_schema(self):
        """Test register_payment tool has correct schema."""
        agent = AIAgent()
        
        tool = next(
            t for t in agent.tool_registry
            if t["toolSpec"]["name"] == "register_payment"
        )
        
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert "student_name" in schema["properties"]
        assert "amount" in schema["properties"]
        assert "payment_date" in schema["properties"]
        assert set(schema["required"]) == {"student_name", "amount", "payment_date"}

    def test_connect_calendar_schema(self):
        """Test connect_calendar tool has correct schema."""
        agent = AIAgent()
        
        tool = next(
            t for t in agent.tool_registry
            if t["toolSpec"]["name"] == "connect_calendar"
        )
        
        schema = tool["toolSpec"]["inputSchema"]["json"]
        assert "provider" in schema["properties"]
        assert schema["properties"]["provider"]["enum"] == ["google", "outlook"]
        assert schema["required"] == ["provider"]


class TestPerformanceRequirements:
    """Test performance requirements."""

    @patch('boto3.client')
    def test_execution_time_tracked(self, mock_boto_client):
        """Test that execution time is tracked and returned."""
        # Mock Bedrock client
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_bedrock.converse.return_value = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello!"}]
                }
            }
        }
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        result = agent.process_message(
            trainer_id="trainer123",
            message="Hello",
        )
        
        assert "execution_time" in result
        assert isinstance(result["execution_time"], float)
        assert result["execution_time"] >= 0

    @patch('boto3.client')
    def test_execution_time_under_5_seconds(self, mock_boto_client):
        """Test that simple operations complete under 5 seconds."""
        # Mock Bedrock client with fast response
        mock_bedrock = MagicMock()
        mock_boto_client.return_value = mock_bedrock
        
        mock_bedrock.converse.return_value = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello!"}]
                }
            }
        }
        
        agent = AIAgent()
        agent.bedrock_client = mock_bedrock
        
        result = agent.process_message(
            trainer_id="trainer123",
            message="Hello",
        )
        
        # Requirement: Complete tool execution within 5 seconds
        assert result["execution_time"] < 5.0
