"""
Simplified Strands SDK implementation for Swarm pattern.

This module provides a minimal implementation of the Swarm pattern concept
described in the AWS Bedrock Agents documentation. Since the actual Strands SDK
is not available as a Python package, this implementation provides the core
functionality needed for multi-agent orchestration:

- Agent class: Represents a specialized agent with tools and system prompt
- Swarm class: Orchestrates agent collaboration with handoffs
- tool decorator: Marks functions as agent tools
- ToolContext: Provides access to shared_context and invocation_state

The implementation uses AWS Bedrock's Converse API with tool calling to
enable autonomous agent handoffs through the handoff_to_agent tool.
"""

import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from functools import wraps
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolContext:
    """
    Context passed to tool functions decorated with @tool(context=True).
    
    Provides access to:
    - shared_context: Working memory visible to LLM (conversation state)
    - invocation_state: Secure configuration NOT visible to LLM (trainer_id, clients)
    """
    shared_context: Dict[str, Any]
    invocation_state: Dict[str, Any]


def tool(context: bool = False):
    """
    Decorator to mark a function as an agent tool.
    
    Args:
        context: If True, inject ToolContext as first parameter
    
    Returns:
        Decorated function with tool metadata
    
    Examples:
        >>> @tool(context=True)
        ... def my_tool(ctx: ToolContext, param1: str) -> dict:
        ...     trainer_id = ctx.invocation_state['trainer_id']
        ...     return {'success': True, 'data': param1}
        
        >>> @tool()
        ... def simple_tool(param1: str) -> dict:
        ...     return {'success': True, 'data': param1}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        # Mark function as a tool
        wrapper._is_tool = True
        wrapper._requires_context = context
        wrapper._tool_name = func.__name__
        wrapper._tool_doc = func.__doc__ or ""
        
        return wrapper
    
    return decorator


class Agent:
    """
    Represents a specialized agent in the swarm.
    
    Each agent has:
    - name: Unique identifier
    - system_prompt: Instructions defining agent's role and behavior
    - tools: List of tool functions the agent can call
    - model_id: Bedrock model to use for this agent
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: List[Callable] = None,
        model_id: str = "amazon.nova-micro-v1:0",
    ):
        """
        Initialize an agent.
        
        Args:
            name: Agent name (e.g., "Coordinator_Agent")
            system_prompt: System instructions for the agent
            tools: List of tool functions (decorated with @tool)
            model_id: Bedrock model ID
        """
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model_id = model_id
        
        # Build tool registry for Bedrock
        self.tool_registry = self._build_tool_registry()
        
        logger.info(
            "Agent initialized",
            agent_name=name,
            tool_count=len(self.tools),
            model_id=model_id,
        )
    
    def _build_tool_registry(self) -> List[Dict[str, Any]]:
        """
        Build tool registry in Bedrock format.
        
        Returns:
            List of tool specifications
        """
        registry = []
        
        for tool_func in self.tools:
            if not hasattr(tool_func, '_is_tool'):
                continue
            
            # Extract tool metadata
            tool_name = tool_func._tool_name
            tool_doc = tool_func._tool_doc
            
            # Parse function signature for parameters
            # For simplicity, we'll use a basic schema
            # In production, use inspect module for full parameter extraction
            
            tool_spec = {
                "toolSpec": {
                    "name": tool_name,
                    "description": tool_doc or f"Execute {tool_name}",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {},
                            "required": []
                        }
                    }
                }
            }
            
            registry.append(tool_spec)
        
        return registry


class Swarm:
    """
    Orchestrates multi-agent collaboration using the Swarm pattern.
    
    The Swarm:
    - Starts with an entry_agent
    - Allows agents to hand off to each other via handoff_to_agent tool
    - Maintains shared_context across all agents
    - Enforces max_handoffs, node_timeout, execution_timeout
    """
    
    def __init__(
        self,
        entry_agent: Agent,
        agents: List[Agent] = None,
        max_handoffs: int = 7,
        node_timeout: int = 30,
        execution_timeout: int = 120,
        region: str = "us-east-1",
        endpoint_url: str = None,
    ):
        """
        Initialize the swarm.
        
        Args:
            entry_agent: First agent to receive messages
            agents: List of all agents in the swarm
            max_handoffs: Maximum handoffs per conversation
            node_timeout: Individual agent timeout (seconds)
            execution_timeout: Total swarm timeout (seconds)
            region: AWS region
            endpoint_url: AWS endpoint URL (for LocalStack)
        """
        self.entry_agent = entry_agent
        self.agents = agents or [entry_agent]
        self.max_handoffs = max_handoffs
        self.node_timeout = node_timeout
        self.execution_timeout = execution_timeout
        
        # Build agent lookup map
        self.agent_map = {agent.name: agent for agent in self.agents}
        
        # Initialize Bedrock client
        bedrock_kwargs = {"region_name": region}
        if endpoint_url:
            bedrock_kwargs["endpoint_url"] = endpoint_url
        
        self.bedrock_client = boto3.client("bedrock-runtime", **bedrock_kwargs)
        
        logger.info(
            "Swarm initialized",
            entry_agent=entry_agent.name,
            agent_count=len(self.agents),
            max_handoffs=max_handoffs,
        )
    
    def run(
        self,
        message: str,
        shared_context: Dict[str, Any],
        invocation_state: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the swarm starting with entry_agent.
        
        Args:
            message: User's message
            shared_context: Working memory (visible to LLM)
            invocation_state: Secure config (NOT visible to LLM)
            conversation_history: Previous messages (optional)
        
        Returns:
            dict: {
                'success': bool,
                'response': str,
                'handoff_path': List[str],
                'tool_calls': List[Dict],
                'shared_context': Dict,
            }
        """
        start_time = datetime.utcnow()
        handoff_path = [self.entry_agent.name]
        tool_calls_executed = []
        current_agent = self.entry_agent
        
        # Build conversation messages
        messages = []
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({
            "role": "user",
            "content": [{"text": message}]
        })
        
        # Execute swarm with handoff support
        handoff_count = 0
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check execution timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > self.execution_timeout:
                raise ExecutionTimeoutError(elapsed)
            
            # Check max handoffs
            if handoff_count >= self.max_handoffs:
                raise MaxHandoffsExceeded(handoff_count)
            
            logger.info(
                "Swarm iteration",
                iteration=iteration,
                current_agent=current_agent.name,
                handoff_count=handoff_count,
            )
            
            # Call Bedrock with current agent
            try:
                # Add handoff_to_agent tool to agent's tools
                tools_with_handoff = self._add_handoff_tool(current_agent.tool_registry)
                
                response = self.bedrock_client.converse(
                    modelId=current_agent.model_id,
                    messages=messages,
                    system=[{"text": current_agent.system_prompt}],
                    toolConfig={"tools": tools_with_handoff},
                    inferenceConfig={
                        "maxTokens": 2048,
                        "temperature": 0.7,
                    },
                )
                
                stop_reason = response.get("stopReason")
                output_message = response.get("output", {}).get("message", {})
                
                # Add assistant response to messages
                messages.append(output_message)
                
                # Handle tool use
                if stop_reason == "tool_use":
                    tool_results = []
                    handoff_requested = False
                    next_agent_name = None
                    
                    for content_block in output_message.get("content", []):
                        if "toolUse" in content_block:
                            tool_use = content_block["toolUse"]
                            tool_name = tool_use.get("name")
                            tool_input = tool_use.get("input", {})
                            tool_use_id = tool_use.get("toolUseId")
                            
                            # Check if it's a handoff
                            if tool_name == "handoff_to_agent":
                                handoff_requested = True
                                next_agent_name = tool_input.get("agent_name")
                                handoff_reason = tool_input.get("reason", "")
                                
                                # Record handoff
                                shared_context['handoff_history'].append({
                                    'from_agent': current_agent.name,
                                    'to_agent': next_agent_name,
                                    'reason': handoff_reason,
                                    'timestamp': datetime.utcnow().isoformat(),
                                })
                                shared_context['handoff_count'] = handoff_count + 1
                                
                                tool_results.append({
                                    "toolResult": {
                                        "toolUseId": tool_use_id,
                                        "content": [{"json": {
                                            "success": True,
                                            "message": f"Handed off to {next_agent_name}"
                                        }}],
                                    }
                                })
                            else:
                                # Execute regular tool
                                tool_result = self._execute_tool(
                                    agent=current_agent,
                                    tool_name=tool_name,
                                    tool_input=tool_input,
                                    shared_context=shared_context,
                                    invocation_state=invocation_state,
                                )
                                
                                tool_calls_executed.append({
                                    "agent": current_agent.name,
                                    "tool": tool_name,
                                    "parameters": tool_input,
                                    "result": tool_result,
                                })
                                
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
                    
                    # Handle handoff
                    if handoff_requested and next_agent_name:
                        if next_agent_name in self.agent_map:
                            current_agent = self.agent_map[next_agent_name]
                            handoff_path.append(next_agent_name)
                            handoff_count += 1
                            logger.info(
                                "Agent handoff",
                                from_agent=handoff_path[-2],
                                to_agent=next_agent_name,
                                handoff_count=handoff_count,
                            )
                        else:
                            logger.warning(
                                "Invalid handoff target",
                                target_agent=next_agent_name,
                            )
                    
                    continue
                
                elif stop_reason in ["end_turn", "max_tokens"]:
                    # Agent finished - extract response
                    final_response = ""
                    for content_block in output_message.get("content", []):
                        if "text" in content_block:
                            final_response += content_block["text"]
                    
                    execution_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    logger.info(
                        "Swarm completed",
                        execution_time=execution_time,
                        handoff_count=handoff_count,
                        tool_calls=len(tool_calls_executed),
                    )
                    
                    return {
                        "success": True,
                        "response": final_response.strip(),
                        "handoff_path": handoff_path,
                        "tool_calls": tool_calls_executed,
                        "shared_context": shared_context,
                        "execution_time": execution_time,
                    }
            
            except ClientError as e:
                logger.error(
                    "Bedrock API error in swarm",
                    error=str(e),
                    current_agent=current_agent.name,
                )
                raise
        
        # Max iterations reached
        return {
            "success": False,
            "error": "Maximum iterations reached",
            "handoff_path": handoff_path,
            "tool_calls": tool_calls_executed,
        }
    
    def _add_handoff_tool(self, tool_registry: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add handoff_to_agent tool to agent's tool registry.
        
        Args:
            tool_registry: Agent's existing tools
        
        Returns:
            Tool registry with handoff tool added
        """
        handoff_tool = {
            "toolSpec": {
                "name": "handoff_to_agent",
                "description": "Hand off the conversation to another specialized agent. Use this when the user's request requires expertise from a different agent.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": f"Name of the agent to hand off to. Available agents: {', '.join(self.agent_map.keys())}",
                                "enum": list(self.agent_map.keys())
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for the handoff (what the next agent should do)"
                            }
                        },
                        "required": ["agent_name", "reason"]
                    }
                }
            }
        }
        
        return tool_registry + [handoff_tool]
    
    def _execute_tool(
        self,
        agent: Agent,
        tool_name: str,
        tool_input: Dict[str, Any],
        shared_context: Dict[str, Any],
        invocation_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute a tool function.
        
        Args:
            agent: Current agent
            tool_name: Tool to execute
            tool_input: Tool parameters
            shared_context: Shared context
            invocation_state: Invocation state
        
        Returns:
            Tool execution result
        """
        # Find tool function
        tool_func = None
        for tool in agent.tools:
            if hasattr(tool, '_tool_name') and tool._tool_name == tool_name:
                tool_func = tool
                break
        
        if not tool_func:
            return {
                "success": False,
                "error": f"Tool {tool_name} not found"
            }
        
        try:
            # Check if tool requires context
            if hasattr(tool_func, '_requires_context') and tool_func._requires_context:
                ctx = ToolContext(
                    shared_context=shared_context,
                    invocation_state=invocation_state,
                )
                result = tool_func(ctx, **tool_input)
            else:
                result = tool_func(**tool_input)
            
            return result
        
        except Exception as e:
            logger.error(
                "Tool execution error",
                tool_name=tool_name,
                error=str(e),
            )
            return {
                "success": False,
                "error": str(e)
            }


# Exception classes
class MaxHandoffsExceeded(Exception):
    """Raised when swarm exceeds max_handoffs limit."""
    def __init__(self, handoff_count: int):
        self.handoff_count = handoff_count
        super().__init__(f"Maximum handoffs exceeded: {handoff_count}")


class ExecutionTimeoutError(Exception):
    """Raised when swarm execution exceeds timeout."""
    def __init__(self, execution_time: float):
        self.execution_time = execution_time
        super().__init__(f"Execution timeout: {execution_time}s")
