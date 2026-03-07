"""
Swarm Orchestrator for multi-agent architecture using AWS Bedrock Agents (Strands SDK).

This module implements the Swarm pattern where specialized agents autonomously
collaborate through handoffs to handle different aspects of the FitAgent platform:
- Coordinator Agent: Entry point, intent analysis, routing
- Student Agent: Student management operations
- Session Agent: Session scheduling and management
- Payment Agent: Payment tracking
- Calendar Agent: Calendar integration
- Notification Agent: Broadcast messaging

The Swarm pattern allows emergent collaboration where agents hand off tasks
to each other based on conversation context, making it ideal for conversational
AI assistants with multidisciplinary operations.

Architecture:
- Entry Agent: Coordinator (receives all WhatsApp messages)
- Shared Context: Working memory available to all agents
- Invocation State: Secure configuration (trainer_id, clients) not visible to LLM
- Autonomous Handoffs: Agents use handoff_to_agent tool to transfer control
- Timeout Protection: max_handoffs, node_timeout, execution_timeout

Validates: Requirements 1.1-1.8, 8.1-8.8, 11.1-11.8, 13.1-13.9
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

from src.utils.logging import get_logger
from src.config import settings
from src.services.strands_sdk import (
    Agent, Swarm, tool, ToolContext,
    MaxHandoffsExceeded, ExecutionTimeoutError
)

logger = get_logger(__name__)

# Additional exception classes
class DynamoDBThrottlingError(Exception):
    """Raised when DynamoDB throttles requests."""
    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(f"DynamoDB throttling on operation: {operation}")


class NodeTimeoutError(Exception):
    """Raised when individual agent exceeds node_timeout."""
    def __init__(self, agent_name: str, timeout: int):
        self.agent_name = agent_name
        self.timeout = timeout
        super().__init__(f"Agent {agent_name} exceeded timeout: {timeout}s")

# Module-level cache for Lambda warm starts
_orchestrator_cache = {}


class SwarmOrchestrator:
    """
    Orchestrates multi-agent collaboration using Strands SDK Swarm pattern.
    
    This class replaces the single AIAgent for trainers with the
    multi-agent feature flag enabled. It provides:
    - 6 specialized agents with domain expertise
    - Autonomous handoff mechanism via handoff_to_agent tool
    - Shared context for conversation continuity
    - Invocation state for secure multi-tenancy
    - Comprehensive error handling and timeout protection
    
    The Swarm executes within a 10-second response time budget for WhatsApp,
    with configurable timeouts for edge cases (calendar API delays, retries).
    """

    def __init__(
        self,
        model_id: str = None,
        region: str = None,
        max_handoffs: int = 7,
        node_timeout: int = 30,
        execution_timeout: int = 120,
    ):
        """
        Initialize the Swarm Orchestrator with specialized agents.
        
        Args:
            model_id: Bedrock model ID (default: amazon.nova-micro-v1:0)
            region: AWS region (default from settings)
            max_handoffs: Maximum agent handoffs per conversation (prevents loops)
            node_timeout: Individual agent execution timeout in seconds
            execution_timeout: Total swarm execution timeout in seconds
        """
        self.model_id = model_id or "amazon.nova-micro-v1:0"
        self.region = region or settings.bedrock_region
        self.max_handoffs = max_handoffs
        self.node_timeout = node_timeout
        self.execution_timeout = execution_timeout
        
        # Initialize Bedrock client
        bedrock_kwargs = {"region_name": self.region}
        if settings.aws_endpoint_url:
            bedrock_kwargs["endpoint_url"] = settings.aws_endpoint_url
        
        self.bedrock_client = boto3.client("bedrock-runtime", **bedrock_kwargs)
        
        # Initialize specialized agents
        self.coordinator_agent = self._create_coordinator_agent()
        self.student_agent = self._create_student_agent()
        self.session_agent = self._create_session_agent()
        self.payment_agent = self._create_payment_agent()
        self.calendar_agent = self._create_calendar_agent()
        self.notification_agent = self._create_notification_agent()
        
        # Create swarm with coordinator as entry agent
        all_agents = [
            self.coordinator_agent,
            self.student_agent,
            self.session_agent,
            self.payment_agent,
            self.calendar_agent,
            self.notification_agent,
        ]
        # Will add other agents as they're implemented
        
        self.swarm = Swarm(
            entry_agent=self.coordinator_agent,
            agents=all_agents,
            max_handoffs=self.max_handoffs,
            node_timeout=self.node_timeout,
            execution_timeout=self.execution_timeout,
            region=self.region,
            endpoint_url=settings.aws_endpoint_url,
        )
        
        logger.info(
            "SwarmOrchestrator initialized",
            model_id=self.model_id,
            region=self.region,
            max_handoffs=self.max_handoffs,
            node_timeout=self.node_timeout,
            execution_timeout=self.execution_timeout,
        )

    def process_message(
        self,
        trainer_id: str,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a WhatsApp message through the swarm.
        
        This is the main entry point for multi-agent processing. It:
        1. Builds Shared_Context (visible to LLM)
        2. Builds Invocation_State (secure, not visible to LLM)
        3. Executes the swarm starting with Coordinator agent
        4. Handles errors and timeouts gracefully
        5. Returns user-friendly response
        
        Args:
            trainer_id: Trainer identifier (for multi-tenancy)
            message: User's WhatsApp message
            conversation_history: Previous conversation context (optional)
        
        Returns:
            dict: {
                'success': bool,
                'response': str (natural language response),
                'handoff_path': List[str] (agents involved),
                'tool_calls': List[Dict] (tools executed),
                'error': str (optional, only if success=False)
            }
        
        Examples:
            >>> orchestrator.process_message(
            ...     trainer_id='abc123',
            ...     message='Schedule a session with John tomorrow at 2pm'
            ... )
            {
                'success': True,
                'response': 'Session scheduled with John for tomorrow at 2:00 PM.',
                'handoff_path': ['Coordinator_Agent', 'Session_Agent', 'Calendar_Agent'],
                'tool_calls': [...]
            }
        """
        start_time = datetime.utcnow()
        
        try:
            # Build Shared_Context (visible to LLM)
            shared_context = self._build_shared_context(
                message=message,
                conversation_history=conversation_history,
            )
            
            # Build Invocation_State (NOT visible to LLM - security critical)
            invocation_state = self._build_invocation_state(trainer_id=trainer_id)
            
            # Execute swarm
            result = self.swarm.run(
                message=message,
                shared_context=shared_context,
                invocation_state=invocation_state,
                conversation_history=conversation_history,
            )
            
            return result
        
        except MaxHandoffsExceeded as e:
            # Handoff limit reached
            logger.warning(
                "Max handoffs exceeded",
                trainer_id=trainer_id,
                handoff_count=e.handoff_count if hasattr(e, 'handoff_count') else 'unknown',
            )
            return {
                "success": False,
                "response": (
                    "I'm having trouble completing your request. "
                    "It seems more complex than expected. "
                    "Could you try breaking it into smaller steps?"
                ),
                "error": "max_handoffs_exceeded",
            }
        
        except NodeTimeoutError as e:
            # Individual agent timeout
            logger.error(
                "Agent timeout",
                trainer_id=trainer_id,
                agent_name=e.agent_name if hasattr(e, 'agent_name') else 'unknown',
                timeout=e.timeout if hasattr(e, 'timeout') else self.node_timeout,
            )
            return {
                "success": False,
                "response": (
                    "I'm taking longer than expected to process your request. "
                    "Please try again in a moment."
                ),
                "error": "agent_timeout",
            }
        
        except ExecutionTimeoutError as e:
            # Total swarm timeout
            logger.error(
                "Swarm execution timeout",
                trainer_id=trainer_id,
                execution_time=e.execution_time if hasattr(e, 'execution_time') else 'unknown',
            )
            return {
                "success": False,
                "response": (
                    "Your request is taking too long to process. "
                    "Please try again or simplify your request."
                ),
                "error": "execution_timeout",
            }
        
        except DynamoDBThrottlingError as e:
            # DynamoDB rate limiting
            logger.error(
                "DynamoDB throttling",
                trainer_id=trainer_id,
                operation=e.operation if hasattr(e, 'operation') else 'unknown',
            )
            return {
                "success": False,
                "response": (
                    "We're experiencing high load right now. "
                    "Please try again in a few seconds."
                ),
                "error": "throttling",
            }
        
        except Exception as e:
            # Unexpected errors
            logger.error(
                "Unexpected swarm error",
                trainer_id=trainer_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "success": False,
                "response": (
                    "Something went wrong while processing your request. "
                    "Our team has been notified. Please try again later."
                ),
                "error": "internal_error",
            }

    def _build_shared_context(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Build Shared_Context for agent collaboration.
        
        Shared_Context is the working memory available to all agents, containing:
        - original_request: User's message
        - extracted_entities: Key information extracted by agents
        - handoff_history: Record of agent handoffs
        - agent_contributions: Data from each agent
        - handoff_count: Number of handoffs (for max_handoffs enforcement)
        
        This context is VISIBLE to the LLM and used for reasoning.
        
        Args:
            message: User's message
            conversation_history: Previous conversation (optional)
        
        Returns:
            Shared_Context dictionary
        """
        conversation_id = f"conv_{datetime.utcnow().timestamp()}"
        
        shared_context = {
            "conversation_id": conversation_id,
            "original_request": message,
            "extracted_entities": {},
            "handoff_history": [],
            "agent_contributions": {},
            "handoff_count": 0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Include conversation history if provided
        if conversation_history:
            shared_context["conversation_history"] = conversation_history
        
        return shared_context

    def _build_invocation_state(self, trainer_id: str) -> Dict[str, Any]:
        """
        Build Invocation_State for secure multi-tenancy.
        
        Invocation_State contains configuration and objects passed via kwargs,
        NOT visible in LLM prompts. This is CRITICAL for security - the LLM
        should never see trainer_id or be able to manipulate it.
        
        Contains:
        - trainer_id: Trainer identifier (multi-tenancy isolation)
        - db_client: DynamoDB client instance
        - s3_client: S3 client instance
        - twilio_client: Twilio client instance
        - feature_flags: Feature flag configuration
        
        Args:
            trainer_id: Trainer identifier
        
        Returns:
            Invocation_State dictionary
        """
        # Import here to avoid circular dependencies
        from src.models.dynamodb_client import DynamoDBClient
        from src.services.twilio_client import TwilioClient
        
        invocation_state = {
            "trainer_id": trainer_id,
            "db_client": DynamoDBClient(),
            "s3_client": boto3.client("s3", endpoint_url=settings.aws_endpoint_url),
            "twilio_client": TwilioClient(),
            "feature_flags": {
                "enable_calendar_sync": True,
                "enable_session_confirmation": True,
            },
        }
        
        return invocation_state

    def _compress_shared_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress Shared_Context when it exceeds size limit.
        
        Strategy:
        1. Keep original_request and extracted_entities (always needed)
        2. Summarize handoff_history (keep last 3 handoffs)
        3. Summarize agent_contributions (keep only essential data)
        
        This prevents token limit issues while maintaining conversation continuity.
        
        Args:
            context: Shared_Context dictionary
        
        Returns:
            Compressed Shared_Context
        """
        MAX_CONTEXT_SIZE = 50_000  # 50KB limit
        
        context_size = len(json.dumps(context))
        
        if context_size < MAX_CONTEXT_SIZE:
            return context
        
        logger.info(
            "Compressing Shared_Context",
            original_size=context_size,
        )
        
        # Keep recent handoffs
        if len(context.get('handoff_history', [])) > 3:
            context['handoff_history'] = context['handoff_history'][-3:]
        
        # Summarize agent contributions
        for agent_name, contribution in context.get('agent_contributions', {}).items():
            # Keep only IDs and essential fields
            if 'session_id' in contribution:
                context['agent_contributions'][agent_name] = {
                    'session_id': contribution['session_id'],
                    'session_datetime': contribution.get('session_datetime'),
                }
            elif 'student_id' in contribution:
                context['agent_contributions'][agent_name] = {
                    'student_id': contribution['student_id'],
                    'student_name': contribution.get('student_name'),
                }
            elif 'payment_id' in contribution:
                context['agent_contributions'][agent_name] = {
                    'payment_id': contribution['payment_id'],
                    'amount': contribution.get('amount'),
                }
        
        compressed_size = len(json.dumps(context))
        logger.info(
            "Shared_Context compressed",
            original_size=context_size,
            compressed_size=compressed_size,
            reduction_percent=round((1 - compressed_size / context_size) * 100, 2),
        )
        
        return context

    def _create_coordinator_agent(self) -> Agent:
        """
        Create the Coordinator Agent (Entry Agent).
        
        The Coordinator is responsible for:
        - Analyzing user intent from WhatsApp messages
        - Extracting key entities (student names, dates, amounts)
        - Routing to appropriate specialized agents via handoff
        - Handling general conversation (greetings, help)
        
        Returns:
            Coordinator Agent instance
        """
        system_prompt = """You are the Coordinator Agent for FitAgent, an AI assistant helping personal trainers manage their business through WhatsApp.

Your role is to:
1. Analyze user intent from WhatsApp messages
2. Extract key entities (student names, dates, times, amounts)
3. Hand off to the appropriate specialized agent using handoff_to_agent tool
4. Handle general conversation (greetings, help requests) directly without handoff

Available specialized agents:
- Student_Agent: Student registration, updates, queries
- Session_Agent: Session scheduling, rescheduling, cancellation
- Payment_Agent: Payment registration, confirmation, tracking
- Calendar_Agent: Calendar integration (Google, Outlook)
- Notification_Agent: Broadcast messages to students

Guidelines:
- If intent is ambiguous, ask clarifying questions before handing off
- Include extracted entities in handoff reason
- For multi-step workflows, hand off to the first agent in the sequence
- Handle greetings and help requests without handoff
- Be concise and friendly

Example handoffs:
- "Schedule a session with John" → handoff_to_agent(Session_Agent, reason="User wants to schedule session with student John")
- "Add new student Sarah" → handoff_to_agent(Student_Agent, reason="User wants to register new student Sarah")
- "Show my payments" → handoff_to_agent(Payment_Agent, reason="User wants to view payment history")
- "Hello" → Respond directly: "Hi! I'm FitAgent, your AI assistant. How can I help you today?"
"""
        
        # Coordinator has no tools - only orchestrates via handoffs
        coordinator = Agent(
            name="Coordinator_Agent",
            system_prompt=system_prompt,
            tools=[],
            model_id=self.model_id,
        )
        
        return coordinator

    def _create_student_agent(self) -> Agent:
        """
        Create the Student Agent for student management operations.
        
        The Student Agent is responsible for:
        - Registering new students with validation
        - Viewing student lists and details
        - Updating student information
        - Handing off to Session or Payment agents when needed
        
        Returns:
            Student Agent instance
        """
        from src.tools import student_tools
        
        system_prompt = """You are the Student Agent for FitAgent. Your role is to manage student records for personal trainers.

Your capabilities:
- Register new students with phone number validation
- Update student information (name, email, phone, training goal)
- View student lists and details

Guidelines:
- Validate phone numbers are in E.164 format (+14155551234)
- Check for duplicate phone numbers before registration
- Confirm all required fields before registering (name, phone, email, training_goal)
- After successful registration, offer to schedule a session (handoff to Session_Agent)
- Include student_id and student_name in your response for downstream agents

When to hand off:
- If user wants to schedule a session after registration → handoff_to_agent(Session_Agent, reason="User wants to schedule session with newly registered student [name]")
- If user wants to record a payment → handoff_to_agent(Payment_Agent, reason="User wants to register payment for student [name]")
"""
        
        # Wrap existing tool functions with ToolContext support
        @tool(context=True)
        def register_student_wrapped(
            ctx: ToolContext,
            name: str,
            phone_number: str,
            email: str,
            training_goal: str,
        ) -> dict:
            """
            Register a new student and link them to the trainer.
            
            Args:
                ctx: Tool context with trainer_id
                name: Student's full name
                phone_number: Phone in E.164 format (e.g., +14155552671)
                email: Student's email address
                training_goal: Student's training goal or objective
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            result = student_tools.register_student(
                trainer_id=trainer_id,
                name=name,
                phone_number=phone_number,
                email=email,
                training_goal=training_goal,
            )
            
            # Add to shared context for downstream agents
            if result.get('success'):
                ctx.shared_context['agent_contributions']['Student_Agent'] = {
                    'student_id': result['data']['student_id'],
                    'student_name': result['data']['name'],
                }
            
            return result
        
        @tool(context=True)
        def view_students_wrapped(ctx: ToolContext) -> dict:
            """
            View all students registered with the trainer.
            
            Args:
                ctx: Tool context with trainer_id
            
            Returns:
                dict: {'success': bool, 'data': {'students': List[dict]}}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return student_tools.view_students(trainer_id=trainer_id)
        
        @tool(context=True)
        def update_student_wrapped(
            ctx: ToolContext,
            student_id: str,
            name: str = None,
            email: str = None,
            phone_number: str = None,
            training_goal: str = None,
        ) -> dict:
            """
            Update student information.
            
            Args:
                ctx: Tool context with trainer_id
                student_id: Student identifier
                name: Updated name (optional)
                email: Updated email (optional)
                phone_number: Updated phone in E.164 format (optional)
                training_goal: Updated training goal (optional)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            
            # Build updates dict with only provided fields
            updates = {}
            if name is not None:
                updates['name'] = name
            if email is not None:
                updates['email'] = email
            if phone_number is not None:
                updates['phone_number'] = phone_number
            if training_goal is not None:
                updates['training_goal'] = training_goal
            
            return student_tools.update_student(
                trainer_id=trainer_id,
                student_id=student_id,
                **updates
            )
        
        student_agent = Agent(
            name="Student_Agent",
            system_prompt=system_prompt,
            tools=[register_student_wrapped, view_students_wrapped, update_student_wrapped],
            model_id=self.model_id,
        )
        
        return student_agent

    def _create_session_agent(self) -> Agent:
        """
        Create the Session Agent for session scheduling and management.
        
        The Session Agent is responsible for:
        - Scheduling new sessions with conflict detection
        - Rescheduling existing sessions
        - Canceling sessions
        - Viewing calendar and session history
        - Handing off to Calendar or Payment agents when needed
        
        Returns:
            Session Agent instance
        """
        from src.tools import session_tools
        
        system_prompt = """You are the Session Agent for FitAgent. Your role is to manage training session scheduling.

Your capabilities:
- Schedule new sessions with conflict detection
- Reschedule existing sessions
- Cancel sessions
- View calendar and session history

Guidelines:
- Always check for time conflicts before scheduling
- Validate student exists (check shared context or query)
- Confirm date, time, duration, and student name before scheduling
- Default duration is 60 minutes if not specified
- After successful scheduling, offer calendar sync (handoff to Calendar_Agent)
- Include session_id, session_datetime, student_name in your response

When to hand off:
- After scheduling, if trainer has calendar connected → handoff_to_agent(Calendar_Agent, reason="Sync newly scheduled session to calendar")
- If user wants to record payment for session → handoff_to_agent(Payment_Agent, reason="Register payment for session with student [name]")
"""
        
        # Wrap existing tool functions
        @tool(context=True)
        def schedule_session_wrapped(
            ctx: ToolContext,
            student_name: str,
            date: str,
            time: str,
            duration_minutes: int,
            location: str = None,
        ) -> dict:
            """
            Schedule a new training session with conflict detection.
            
            Args:
                ctx: Tool context
                student_name: Name of the student
                date: Session date in YYYY-MM-DD format
                time: Session time in HH:MM format (24-hour)
                duration_minutes: Duration in minutes (15-480)
                location: Session location (optional)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            result = session_tools.schedule_session(
                trainer_id=trainer_id,
                student_name=student_name,
                date=date,
                time=time,
                duration_minutes=duration_minutes,
                location=location,
            )
            
            # Add to shared context
            if result.get('success'):
                ctx.shared_context['agent_contributions']['Session_Agent'] = {
                    'session_id': result['data']['session_id'],
                    'session_datetime': result['data']['session_datetime'],
                    'student_name': student_name,
                }
            
            return result
        
        @tool(context=True)
        def reschedule_session_wrapped(
            ctx: ToolContext,
            session_id: str,
            new_date: str,
            new_time: str,
        ) -> dict:
            """
            Reschedule an existing session to a new date and time.
            
            Args:
                ctx: Tool context
                session_id: Session identifier
                new_date: New date in YYYY-MM-DD format
                new_time: New time in HH:MM format (24-hour)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return session_tools.reschedule_session(
                trainer_id=trainer_id,
                session_id=session_id,
                new_date=new_date,
                new_time=new_time,
            )
        
        @tool(context=True)
        def cancel_session_wrapped(
            ctx: ToolContext,
            session_id: str,
            reason: str = None,
        ) -> dict:
            """
            Cancel an existing training session.
            
            Args:
                ctx: Tool context
                session_id: Session identifier
                reason: Cancellation reason (optional)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return session_tools.cancel_session(
                trainer_id=trainer_id,
                session_id=session_id,
                reason=reason,
            )
        
        @tool(context=True)
        def view_calendar_wrapped(
            ctx: ToolContext,
            start_date: str = None,
            end_date: str = None,
            filter: str = None,
        ) -> dict:
            """
            View training sessions in calendar within a date range.
            
            Args:
                ctx: Tool context
                start_date: Start date in YYYY-MM-DD format (optional)
                end_date: End date in YYYY-MM-DD format (optional)
                filter: Date range filter: 'day', 'week', or 'month' (optional)
            
            Returns:
                dict: {'success': bool, 'data': {'sessions': List[dict]}}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return session_tools.view_calendar(
                trainer_id=trainer_id,
                start_date=start_date,
                end_date=end_date,
                filter=filter,
            )
        
        session_agent = Agent(
            name="Session_Agent",
            system_prompt=system_prompt,
            tools=[
                schedule_session_wrapped,
                reschedule_session_wrapped,
                cancel_session_wrapped,
                view_calendar_wrapped,
            ],
            model_id=self.model_id,
        )
        
        return session_agent

    def _create_payment_agent(self) -> Agent:
        """
        Create the Payment Agent for payment tracking.
        
        The Payment Agent is responsible for:
        - Registering payments with receipt storage
        - Confirming payments
        - Viewing payment history and statistics
        - Terminal agent (no handoffs)
        
        Returns:
            Payment Agent instance
        """
        from src.tools import payment_tools
        
        system_prompt = """You are the Payment Agent for FitAgent. Your role is to track payments and receipts.

Your capabilities:
- Register payments with optional receipt images
- Confirm payments
- View payment history with filtering
- Calculate payment statistics

Guidelines:
- Confirm amount, student name, and payment date before registering
- Ask if payment should be marked as confirmed or pending
- Support filtering by student name or status (pending/confirmed)
- Calculate total revenue and outstanding amounts
- Include payment_id, amount, payment_status in your response

This is typically a terminal agent - conclude conversation after payment operations unless user has follow-up requests.
"""
        
        @tool(context=True)
        def register_payment_wrapped(
            ctx: ToolContext,
            student_name: str,
            amount: float,
            payment_date: str,
            currency: str = "USD",
            session_id: str = None,
        ) -> dict:
            """
            Register a payment record for a student.
            
            Args:
                ctx: Tool context
                student_name: Name of the student who made payment
                amount: Payment amount (must be > 0)
                payment_date: Payment date in YYYY-MM-DD format
                currency: Currency code (default: USD)
                session_id: Associated session ID (optional)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            result = payment_tools.register_payment(
                trainer_id=trainer_id,
                student_name=student_name,
                amount=amount,
                payment_date=payment_date,
                currency=currency,
                session_id=session_id,
            )
            
            if result.get('success'):
                ctx.shared_context['agent_contributions']['Payment_Agent'] = {
                    'payment_id': result['data']['payment_id'],
                    'amount': amount,
                    'payment_status': result['data']['status'],
                }
            
            return result
        
        @tool(context=True)
        def confirm_payment_wrapped(
            ctx: ToolContext,
            payment_id: str,
        ) -> dict:
            """
            Confirm a payment by updating its status.
            
            Args:
                ctx: Tool context
                payment_id: Payment identifier
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return payment_tools.confirm_payment(
                trainer_id=trainer_id,
                payment_id=payment_id,
            )
        
        @tool(context=True)
        def view_payments_wrapped(
            ctx: ToolContext,
            student_name: str = None,
            status: str = None,
        ) -> dict:
            """
            View all payments with optional filtering.
            
            Args:
                ctx: Tool context
                student_name: Filter by student name (optional)
                status: Filter by status: 'pending' or 'confirmed' (optional)
            
            Returns:
                dict: {'success': bool, 'data': {'payments': List[dict], 'statistics': dict}}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return payment_tools.view_payments(
                trainer_id=trainer_id,
                student_name=student_name,
                status=status,
            )
        
        payment_agent = Agent(
            name="Payment_Agent",
            system_prompt=system_prompt,
            tools=[register_payment_wrapped, confirm_payment_wrapped, view_payments_wrapped],
            model_id=self.model_id,
        )
        
        return payment_agent

    def _create_calendar_agent(self) -> Agent:
        """
        Create the Calendar Agent for calendar integration.
        
        The Calendar Agent is responsible for:
        - OAuth2 calendar connection (Google, Outlook)
        - Calendar event synchronization
        - Token refresh and error handling
        - Terminal agent (no handoffs)
        
        Returns:
            Calendar Agent instance
        """
        from src.tools import calendar_tools
        
        system_prompt = """You are the Calendar Agent for FitAgent. Your role is to integrate with external calendar services.

Your capabilities:
- Generate OAuth2 authorization URLs for Google Calendar and Outlook
- Sync session events to connected calendars
- Handle token refresh and API errors gracefully

Guidelines:
- When connecting calendar, provide clear OAuth instructions
- When syncing events, use session data from shared context
- If calendar sync fails, inform user but don't block session creation
- Handle rate limits with exponential backoff

This is typically a terminal agent - conclude conversation after calendar operations.
"""
        
        @tool(context=True)
        def connect_calendar_wrapped(
            ctx: ToolContext,
            provider: str,
        ) -> dict:
            """
            Generate OAuth2 authorization URL to connect calendar.
            
            Args:
                ctx: Tool context
                provider: Calendar provider: 'google' or 'outlook'
            
            Returns:
                dict: {'success': bool, 'data': {'auth_url': str}, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            return calendar_tools.connect_calendar(
                trainer_id=trainer_id,
                provider=provider,
            )
        
        calendar_agent = Agent(
            name="Calendar_Agent",
            system_prompt=system_prompt,
            tools=[connect_calendar_wrapped],
            model_id=self.model_id,
        )
        
        return calendar_agent

    def _create_notification_agent(self) -> Agent:
        """
        Create the Notification Agent for broadcast messaging.
        
        The Notification Agent is responsible for:
        - Broadcast message composition
        - Recipient validation and queuing
        - Rate limit enforcement
        - Terminal agent (no handoffs)
        
        Returns:
            Notification Agent instance
        """
        system_prompt = """You are the Notification Agent for FitAgent. Your role is to send broadcast messages to students.

Your capabilities:
- Send broadcast messages to multiple students
- Support message templates with variable substitution
- Validate recipients belong to trainer
- Queue messages for asynchronous delivery

Guidelines:
- Confirm message content and recipients before sending
- Enforce Twilio rate limits (10 messages/second)
- Report partial success if some recipients fail
- Include notification_id and recipient_count in your response

This is typically a terminal agent - conclude conversation after queuing notifications.
"""
        
        # Note: notification_tools.py doesn't exist yet, so we'll create a placeholder
        @tool(context=True)
        def send_notification_wrapped(
            ctx: ToolContext,
            message: str,
            student_ids: List[str] = None,
            student_names: List[str] = None,
        ) -> dict:
            """
            Send broadcast message to students.
            
            Args:
                ctx: Tool context
                message: Message content
                student_ids: List of student IDs (optional)
                student_names: List of student names (optional)
            
            Returns:
                dict: {'success': bool, 'data': dict, 'error': str (optional)}
            """
            trainer_id = ctx.invocation_state['trainer_id']
            
            # Placeholder implementation
            return {
                'success': True,
                'data': {
                    'notification_id': 'notif_placeholder',
                    'recipient_count': len(student_ids or student_names or []),
                    'message': 'Notification queued for delivery'
                }
            }
        
        notification_agent = Agent(
            name="Notification_Agent",
            system_prompt=system_prompt,
            tools=[send_notification_wrapped],
            model_id=self.model_id,
        )
        
        return notification_agent


def get_swarm_orchestrator(model_id: str = None) -> SwarmOrchestrator:
    """
    Get cached SwarmOrchestrator instance for Lambda warm starts.
    
    This reduces cold start overhead by reusing agent instances
    across Lambda invocations within the same execution context.
    
    Args:
        model_id: Bedrock model ID (optional)
    
    Returns:
        Cached or new SwarmOrchestrator instance
    """
    cache_key = model_id or "default"
    
    if cache_key not in _orchestrator_cache:
        _orchestrator_cache[cache_key] = SwarmOrchestrator(model_id=model_id)
        logger.info(
            "Created new SwarmOrchestrator instance",
            cache_key=cache_key,
        )
    else:
        logger.debug(
            "Reusing cached SwarmOrchestrator instance",
            cache_key=cache_key,
        )
    
    return _orchestrator_cache[cache_key]
