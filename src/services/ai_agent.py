"""
AI Agent service using AWS Bedrock with Claude models.

This module provides the AIAgent class that:
- Uses AWS Bedrock (Claude 3 Sonnet) for natural language understanding
- Defines tool registry with JSON schemas for all 10 tool functions
- Executes tools based on user natural language requests
- Maintains conversation context across tool executions
- Returns user-friendly error messages on tool failures
- Completes tool execution within 5 seconds

The agent integrates with all tool functions from src/tools/:
- register_student, view_students, update_student (student_tools.py)
- schedule_session, reschedule_session, cancel_session, view_calendar (session_tools.py)
- register_payment, confirm_payment, view_payments (payment_tools.py)
- connect_calendar (calendar_tools.py)

Architecture:
- Tool Registry: JSON schemas define tool parameters and validation
- Tool Execution: Maps tool names to actual Python functions
- Context Management: Maintains conversation history for multi-turn interactions
- Error Handling: Graceful degradation with user-friendly messages

Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
"""

import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.tools import student_tools, session_tools, payment_tools, calendar_tools
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)


class AIAgent:
    """
    AI Agent using AWS Bedrock for natural language understanding and tool execution.
    
    This class implements the tool-calling architecture where:
    1. User sends natural language message
    2. Bedrock (Claude) determines which tool(s) to call
    3. Agent executes the tool function(s)
    4. Agent returns results to Bedrock for natural language response
    5. User receives conversational response
    
    The agent maintains conversation context to support multi-turn interactions
    and complex workflows that require multiple tool calls.
    """

    def __init__(
        self,
        model_id: str = None,
        region: str = None,
        endpoint_url: str = None,
    ):
        """
        Initialize the AI Agent with AWS Bedrock client.
        
        Args:
            model_id: Bedrock model ID (default from settings)
            region: AWS region (default from settings)
            endpoint_url: AWS endpoint URL for LocalStack (optional)
        """
        self.model_id = model_id or settings.bedrock_model_id
        self.region = region or settings.bedrock_region
        self.endpoint_url = endpoint_url or settings.aws_endpoint_url
        
        # Initialize Bedrock client
        bedrock_kwargs = {"region_name": self.region}
        if self.endpoint_url:
            bedrock_kwargs["endpoint_url"] = self.endpoint_url
        
        self.bedrock_client = boto3.client("bedrock-runtime", **bedrock_kwargs)
        
        # Initialize tool registry and execution map
        self.tool_registry = self._build_tool_registry()
        self.tool_execution_map = self._build_tool_execution_map()
        
        logger.info(
            "AIAgent initialized",
            model_id=self.model_id,
            region=self.region,
            tool_count=len(self.tool_registry),
        )

    def _build_tool_registry(self) -> List[Dict[str, Any]]:
        """
        Build the tool registry with JSON schemas for all 10 tool functions.
        
        Each tool definition includes:
        - name: Tool function name
        - description: What the tool does (for Claude to understand)
        - input_schema: JSON Schema defining parameters
        
        Returns:
            List of tool definitions in Bedrock format
        """
        return [
            # Student Management Tools
            {
                "toolSpec": {
                    "name": "register_student",
                    "description": "Register a new student and link them to the trainer. Use this when the trainer wants to add a new student to their roster. Collects student name, phone number, email, and training goal.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Student's full name"
                                },
                                "phone_number": {
                                    "type": "string",
                                    "description": "Student's phone number in E.164 format (e.g., +14155552671)"
                                },
                                "email": {
                                    "type": "string",
                                    "description": "Student's email address"
                                },
                                "training_goal": {
                                    "type": "string",
                                    "description": "Student's training goal or objective"
                                }
                            },
                            "required": ["name", "phone_number", "email", "training_goal"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "view_students",
                    "description": "View all students registered with the trainer. Use this when the trainer wants to see their student list or check student information.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "update_student",
                    "description": "Update student information such as name, email, phone number, or training goal. Use this when the trainer wants to modify existing student details.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "student_id": {
                                    "type": "string",
                                    "description": "Student identifier"
                                },
                                "name": {
                                    "type": "string",
                                    "description": "Updated student name (optional)"
                                },
                                "email": {
                                    "type": "string",
                                    "description": "Updated email address (optional)"
                                },
                                "phone_number": {
                                    "type": "string",
                                    "description": "Updated phone number in E.164 format (optional)"
                                },
                                "training_goal": {
                                    "type": "string",
                                    "description": "Updated training goal (optional)"
                                }
                            },
                            "required": ["student_id"]
                        }
                    }
                }
            },
            # Session Management Tools
            {
                "toolSpec": {
                    "name": "schedule_session",
                    "description": "Schedule a new training session with a student. Use this when the trainer wants to book a session. Checks for scheduling conflicts automatically.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "student_name": {
                                    "type": "string",
                                    "description": "Name of the student for this session"
                                },
                                "date": {
                                    "type": "string",
                                    "description": "Session date in YYYY-MM-DD format"
                                },
                                "time": {
                                    "type": "string",
                                    "description": "Session time in HH:MM format (24-hour)"
                                },
                                "duration_minutes": {
                                    "type": "integer",
                                    "description": "Session duration in minutes (15-480)"
                                },
                                "location": {
                                    "type": "string",
                                    "description": "Session location (optional)"
                                }
                            },
                            "required": ["student_name", "date", "time", "duration_minutes"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "reschedule_session",
                    "description": "Reschedule an existing session to a new date and time. Use this when the trainer wants to move a session. Checks for conflicts at the new time.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Session identifier to reschedule"
                                },
                                "new_date": {
                                    "type": "string",
                                    "description": "New session date in YYYY-MM-DD format"
                                },
                                "new_time": {
                                    "type": "string",
                                    "description": "New session time in HH:MM format (24-hour)"
                                }
                            },
                            "required": ["session_id", "new_date", "new_time"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "cancel_session",
                    "description": "Cancel an existing training session. Use this when the trainer wants to cancel a scheduled session.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "session_id": {
                                    "type": "string",
                                    "description": "Session identifier to cancel"
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Cancellation reason (optional)"
                                }
                            },
                            "required": ["session_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "view_calendar",
                    "description": "View training sessions in the trainer's calendar within a date range. Use this when the trainer wants to see their schedule. Can filter by day, week, or month, or specify custom date range.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "start_date": {
                                    "type": "string",
                                    "description": "Start date in YYYY-MM-DD format (optional if filter provided)"
                                },
                                "end_date": {
                                    "type": "string",
                                    "description": "End date in YYYY-MM-DD format (optional if filter provided)"
                                },
                                "filter": {
                                    "type": "string",
                                    "description": "Convenient date range filter: 'day', 'week', or 'month' (optional)",
                                    "enum": ["day", "week", "month"]
                                }
                            },
                            "required": []
                        }
                    }
                }
            },
            # Payment Management Tools
            {
                "toolSpec": {
                    "name": "register_payment",
                    "description": "Register a payment record for a student. Use this when the trainer receives payment or wants to record a payment. Creates a payment record with pending status.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "student_name": {
                                    "type": "string",
                                    "description": "Name of the student who made the payment"
                                },
                                "amount": {
                                    "type": "number",
                                    "description": "Payment amount (must be greater than 0)"
                                },
                                "payment_date": {
                                    "type": "string",
                                    "description": "Payment date in YYYY-MM-DD format"
                                },
                                "currency": {
                                    "type": "string",
                                    "description": "Currency code (default: USD)",
                                    "default": "USD"
                                },
                                "session_id": {
                                    "type": "string",
                                    "description": "Associated session ID (optional)"
                                }
                            },
                            "required": ["student_name", "amount", "payment_date"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "confirm_payment",
                    "description": "Confirm a payment by updating its status to confirmed. Use this when the trainer verifies and confirms a payment record.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "payment_id": {
                                    "type": "string",
                                    "description": "Payment identifier to confirm"
                                }
                            },
                            "required": ["payment_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "view_payments",
                    "description": "View all payments for the trainer with optional filtering. Use this when the trainer wants to see payment records. Can filter by student name or payment status (pending/confirmed).",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "student_name": {
                                    "type": "string",
                                    "description": "Filter by student name (optional)"
                                },
                                "status": {
                                    "type": "string",
                                    "description": "Filter by payment status (optional)",
                                    "enum": ["pending", "confirmed"]
                                }
                            },
                            "required": []
                        }
                    }
                }
            },
            # Calendar Integration Tool
            {
                "toolSpec": {
                    "name": "connect_calendar",
                    "description": "Generate OAuth2 authorization URL to connect Google Calendar or Outlook Calendar. Use this when the trainer wants to sync their sessions with their calendar app.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "provider": {
                                    "type": "string",
                                    "description": "Calendar provider to connect",
                                    "enum": ["google", "outlook"]
                                }
                            },
                            "required": ["provider"]
                        }
                    }
                }
            },
        ]

    def _build_tool_execution_map(self) -> Dict[str, Callable]:
        """
        Build mapping from tool names to actual Python functions.
        
        This map is used to execute the tool when Bedrock requests it.
        The trainer_id is injected automatically during execution.
        
        Returns:
            Dictionary mapping tool names to functions
        """
        return {
            # Student tools
            "register_student": student_tools.register_student,
            "view_students": student_tools.view_students,
            "update_student": student_tools.update_student,
            # Session tools
            "schedule_session": session_tools.schedule_session,
            "reschedule_session": session_tools.reschedule_session,
            "cancel_session": session_tools.cancel_session,
            "view_calendar": session_tools.view_calendar,
            # Payment tools
            "register_payment": payment_tools.register_payment,
            "confirm_payment": payment_tools.confirm_payment,
            "view_payments": payment_tools.view_payments,
            # Calendar tools
            "connect_calendar": calendar_tools.connect_calendar,
        }

    def process_message(
        self,
        trainer_id: str,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message using AWS Bedrock and execute any requested tools.
        
        This is the main entry point for the AI agent. It:
        1. Prepares the conversation with system prompt and history
        2. Calls Bedrock Converse API with tool definitions
        3. Executes any tools that Bedrock requests
        4. Returns the final response to the user
        
        The method handles multi-turn tool execution where Bedrock may request
        multiple tools in sequence to complete a complex task.
        
        Args:
            trainer_id: Trainer identifier (injected into all tool calls)
            message: User's natural language message
            conversation_history: Previous messages in conversation (optional)
        
        Returns:
            dict: {
                'success': bool,
                'response': str (natural language response for user),
                'tool_calls': List[Dict] (tools that were executed),
                'error': str (optional, only if success=False)
            }
        
        Examples:
            >>> agent.process_message(
            ...     trainer_id='abc123',
            ...     message='Schedule a session with John tomorrow at 2pm for 60 minutes'
            ... )
            {
                'success': True,
                'response': 'I've scheduled a 60-minute session with John for tomorrow at 2:00 PM.',
                'tool_calls': [
                    {
                        'tool': 'schedule_session',
                        'parameters': {...},
                        'result': {'success': True, 'data': {...}}
                    }
                ]
            }
        """
        start_time = datetime.utcnow()
        tool_calls_executed = []
        
        try:
            # Prepare system prompt with trainer context
            system_prompt = self._build_system_prompt(trainer_id)
            
            # Build conversation messages
            messages = []
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": [{"text": message}]
            })
            
            # Call Bedrock Converse API with tool support
            # This may require multiple iterations if tools are called
            max_iterations = 5  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                logger.info(
                    "Calling Bedrock Converse API",
                    trainer_id=trainer_id,
                    iteration=iteration,
                    message_count=len(messages),
                )
                
                # Call Bedrock
                response = self.bedrock_client.converse(
                    modelId=self.model_id,
                    messages=messages,
                    system=[{"text": system_prompt}],
                    toolConfig={"tools": self.tool_registry},
                    inferenceConfig={
                        "maxTokens": 2048,
                        "temperature": 0.7,
                        "topP": 0.9,
                    },
                )
                
                # Extract response
                stop_reason = response.get("stopReason")
                output_message = response.get("output", {}).get("message", {})
                
                # Add assistant's response to conversation
                messages.append(output_message)
                
                # Check if Bedrock wants to use tools
                if stop_reason == "tool_use":
                    # Extract tool use requests from content
                    tool_results = []
                    
                    for content_block in output_message.get("content", []):
                        if "toolUse" in content_block:
                            tool_use = content_block["toolUse"]
                            tool_name = tool_use.get("name")
                            tool_input = tool_use.get("input", {})
                            tool_use_id = tool_use.get("toolUseId")
                            
                            logger.info(
                                "Executing tool",
                                trainer_id=trainer_id,
                                tool_name=tool_name,
                                tool_input=tool_input,
                            )
                            
                            # Execute the tool
                            tool_result = self._execute_tool(
                                trainer_id=trainer_id,
                                tool_name=tool_name,
                                tool_input=tool_input,
                            )
                            
                            # Track tool execution
                            tool_calls_executed.append({
                                "tool": tool_name,
                                "parameters": tool_input,
                                "result": tool_result,
                            })
                            
                            # Prepare tool result for Bedrock
                            tool_results.append({
                                "toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": tool_result}],
                                }
                            })
                    
                    # Add tool results to conversation
                    messages.append({
                        "role": "user",
                        "content": tool_results,
                    })
                    
                    # Continue loop to get Bedrock's response with tool results
                    continue
                
                elif stop_reason in ["end_turn", "max_tokens"]:
                    # Bedrock has finished - extract final response
                    final_response = ""
                    
                    for content_block in output_message.get("content", []):
                        if "text" in content_block:
                            final_response += content_block["text"]
                    
                    # Calculate execution time
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    logger.info(
                        "AI agent completed",
                        trainer_id=trainer_id,
                        execution_time=execution_time,
                        tool_calls=len(tool_calls_executed),
                        iterations=iteration,
                    )
                    
                    # Check 5-second requirement
                    if execution_time > 5.0:
                        logger.warning(
                            "Tool execution exceeded 5 seconds",
                            trainer_id=trainer_id,
                            execution_time=execution_time,
                        )
                    
                    return {
                        "success": True,
                        "response": final_response.strip(),
                        "tool_calls": tool_calls_executed,
                        "execution_time": execution_time,
                    }
                
                else:
                    # Unexpected stop reason
                    logger.warning(
                        "Unexpected stop reason from Bedrock",
                        stop_reason=stop_reason,
                    )
                    break
            
            # If we exit the loop without returning, we hit max iterations
            return {
                "success": False,
                "error": "Maximum tool execution iterations reached. Please try simplifying your request.",
                "tool_calls": tool_calls_executed,
            }
        
        except ClientError as e:
            # AWS Bedrock API errors
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            logger.error(
                "Bedrock API error",
                trainer_id=trainer_id,
                error_code=error_code,
                error_message=error_message,
            )
            
            return {
                "success": False,
                "error": f"I'm having trouble processing your request right now. Please try again in a moment.",
                "tool_calls": tool_calls_executed,
            }
        
        except Exception as e:
            # Unexpected errors
            logger.error(
                "Unexpected error in AI agent",
                trainer_id=trainer_id,
                error=str(e),
            )
            
            return {
                "success": False,
                "error": "Something went wrong while processing your request. Please try again.",
                "tool_calls": tool_calls_executed,
            }

    def _build_system_prompt(self, trainer_id: str) -> str:
        """
        Build system prompt with trainer context.
        
        The system prompt instructs Claude on its role and capabilities.
        
        Args:
            trainer_id: Trainer identifier
        
        Returns:
            System prompt string
        """
        return f"""You are FitAgent, an AI assistant helping personal trainers manage their business through WhatsApp.

You are currently assisting trainer ID: {trainer_id}

Your capabilities:
- Register and manage students
- Schedule, reschedule, and cancel training sessions
- Track payments and receipts
- Connect calendar apps (Google Calendar, Outlook)
- View schedules and payment records

Guidelines:
- Be friendly, professional, and concise
- Always confirm actions before executing them
- If information is missing, ask the user for clarification
- Use the tools available to complete user requests
- Provide clear feedback on what actions were taken
- If a tool fails, explain the error in user-friendly terms and suggest next steps

When scheduling sessions:
- Always check for conflicts
- Confirm the date, time, and student name
- Ask for duration if not provided (default 60 minutes)

When handling payments:
- Confirm the amount and student name
- Ask if the payment should be marked as confirmed or pending

Remember: You're helping trainers run their business efficiently through natural conversation."""

    def _execute_tool(
        self,
        trainer_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool function with parameter validation.
        
        This method:
        1. Validates that the tool exists
        2. Injects trainer_id into parameters
        3. Calls the tool function
        4. Returns the result (success/error)
        
        Args:
            trainer_id: Trainer identifier (injected automatically)
            tool_name: Name of the tool to execute
            tool_input: Tool parameters from Bedrock
        
        Returns:
            Tool execution result dict
        """
        try:
            # Validate tool exists
            if tool_name not in self.tool_execution_map:
                logger.error(
                    "Unknown tool requested",
                    tool_name=tool_name,
                )
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}",
                }
            
            # Get tool function
            tool_function = self.tool_execution_map[tool_name]
            
            # Inject trainer_id as first parameter
            tool_params = {"trainer_id": trainer_id, **tool_input}
            
            # Execute tool with timeout protection
            # Note: In production, consider using threading.Timer for hard timeout
            result = tool_function(**tool_params)
            
            logger.info(
                "Tool executed successfully",
                trainer_id=trainer_id,
                tool_name=tool_name,
                success=result.get("success", False),
            )
            
            return result
        
        except TypeError as e:
            # Parameter validation errors
            logger.error(
                "Tool parameter error",
                trainer_id=trainer_id,
                tool_name=tool_name,
                error=str(e),
            )
            
            return {
                "success": False,
                "error": f"Invalid parameters for {tool_name}: {str(e)}",
            }
        
        except Exception as e:
            # Unexpected tool execution errors
            logger.error(
                "Tool execution error",
                trainer_id=trainer_id,
                tool_name=tool_name,
                error=str(e),
            )
            
            return {
                "success": False,
                "error": f"Failed to execute {tool_name}: {str(e)}",
            }
