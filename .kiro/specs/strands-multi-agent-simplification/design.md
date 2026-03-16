# Design Document: Strands Multi-Agent Simplification

## Overview

This design replaces the over-engineered custom Strands implementation with the official strands-agents SDK. The current system has ~1,100 lines of custom SDK code (strands_sdk.py), a complex 6-agent orchestrator (swarm_orchestrator.py), and duplicated functionality in ai_agent.py. This complexity is unnecessary for FitAgent's straightforward use case.

The new design uses a single-agent architecture with the official strands-agents package. One agent with all tools is sufficient because:
- FitAgent has a single user type (trainers) with unified workflows
- All operations are synchronous and complete within seconds
- No complex multi-step workflows requiring agent handoffs
- Tool execution is deterministic (no need for specialized reasoning)

This simplification reduces code by ~80% while maintaining all functionality.

### Design Principles

1. **Aggressive Simplification**: Use 1 agent instead of 6, official SDK instead of custom code
2. **Security First**: Multi-tenancy enforced at tool execution layer via trainer_id validation
3. **Idiomatic Strands**: Follow SDK patterns without custom wrappers or abstractions
4. **Minimal Abstraction**: Direct integration with existing tool functions
5. **Production-Ready**: Proper error handling, logging, and timeout protection
6. **PT-BR Language**: All agent responses and WhatsApp messages in Brazilian Portuguese

## Architecture

### High-Level Architecture

```
WhatsApp Message
    ↓
Lambda: message_processor.py
    ↓
Service: strands_agent_service.py
    ↓
Strands Agent (single)
    ↓
Tool Functions (student_tools, session_tools, payment_tools)
    ↓
DynamoDB (multi-tenant data)
```

### Component Responsibilities

**strands_agent_service.py** (NEW)
- Initialize Strands Agent with tool registry
- Process incoming messages via agent.run()
- Inject trainer_id into tool execution context
- Handle errors and timeouts
- Return natural language responses

**Tool Functions** (EXISTING - no changes)
- src/tools/student_tools.py
- src/tools/session_tools.py  
- src/tools/payment_tools.py
- Each tool validates trainer_id and enforces multi-tenancy

**message_processor.py** (MINIMAL CHANGES)
- Replace SwarmOrchestrator/AIAgent calls with StrandsAgentService
- Remove feature flag logic (single implementation)
- Keep existing phone number routing and error handling

### Files to Delete

1. **src/services/strands_sdk.py** (~600 lines) - Custom SDK implementation
2. **src/services/swarm_orchestrator.py** (~1,100 lines) - 6-agent orchestrator
3. **src/services/ai_agent.py** (~800 lines) - Duplicate single-agent implementation

These files are replaced by ~200 lines in strands_agent_service.py using the official SDK.

### Files to Create

1. **src/services/strands_agent_service.py** - New service using official strands-agents SDK

## Components and Interfaces

### StrandsAgentService Class

```python
class StrandsAgentService:
    """
    Service for processing trainer messages using Strands Agents SDK.
    
    Provides a simple interface for WhatsApp message processing with:
    - Single agent with all FitAgent tools
    - Multi-tenancy via trainer_id injection
    - Error handling and timeout protection
    - Structured logging
    - PT-BR (Brazilian Portuguese) responses
    """
    
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        region: str = "us-east-1"
    ):
        """Initialize agent with Bedrock configuration and PT-BR system prompt."""
        
    def process_message(
        self,
        trainer_id: str,
        message: str,
        phone_number: str = None
    ) -> Dict[str, Any]:
        """
        Process a WhatsApp message through the Strands agent.
        
        Args:
            trainer_id: Trainer identifier for multi-tenancy
            message: User's WhatsApp message (in PT-BR)
            phone_number: Phone number for language detection
            
        Returns:
            {
                'success': bool,
                'response': str,  # Natural language response in PT-BR
                'error': str      # Optional error message in PT-BR
            }
        """
```

### Tool Decorator Pattern

Using Strands native @tool decorator:

```python
from strands_agents import tool

@tool
def register_student(
    trainer_id: str,
    name: str,
    phone_number: str,
    email: str,
    training_goal: str
) -> dict:
    """
    Register a new student and link them to the trainer.
    
    Args:
        trainer_id: Trainer identifier (injected by service)
        name: Student's full name
        phone_number: Phone in E.164 format
        email: Student's email address
        training_goal: Student's training goal
        
    Returns:
        {'success': bool, 'data': dict, 'error': str}
    """
```

### Multi-Tenancy Injection

The service injects trainer_id into tool execution context:

```python
# In StrandsAgentService.process_message()
tool_context = {
    'trainer_id': trainer_id,
    'db_client': self.db_client,
    's3_client': self.s3_client
}

# Strands SDK passes context to tools
result = agent.run(
    message=message,
    context=tool_context
)
```

### Integration with message_processor.py

Simplified handler integration:

```python
# OLD (complex)
if is_multi_agent_enabled(trainer_id):
    orchestrator = get_swarm_orchestrator()
    result = orchestrator.process_message(...)
else:
    result = trainer_handler.handle_message(...)

# NEW (simple)
agent_service = get_strands_agent_service()
result = agent_service.process_message(
    trainer_id=trainer_id,
    message=message_body.get("body", ""),
    phone_number=phone_number
)
```

## Data Models

### Tool Result Format

All tools return consistent structure:

```python
{
    'success': bool,
    'data': dict,      # Tool-specific data (optional)
    'error': str       # Error message (optional, only if success=False)
}
```

### Agent Response Format

Service returns:

```python
{
    'success': bool,
    'response': str,   # Natural language response for WhatsApp
    'error': str       # Error message (optional, only if success=False)
}
```

### Tool Context

Injected into every tool execution:

```python
{
    'trainer_id': str,           # Required for multi-tenancy
    'db_client': DynamoDBClient, # Database access
    's3_client': boto3.client,   # S3 for receipts
    'language': str              # User language (pt-BR, en-US)
}
```

### Existing Data Models (Unchanged)

- **Trainer**: PK=TRAINER#{id}, SK=METADATA
- **Student**: PK=TRAINER#{trainer_id}, SK=STUDENT#{student_id}
- **Session**: PK=TRAINER#{trainer_id}, SK=SESSION#{session_id}
- **Payment**: PK=TRAINER#{trainer_id}, SK=PAYMENT#{payment_id}

All DynamoDB operations scoped by trainer_id in partition key.


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following testable properties. Several criteria were redundant or overlapping:

- Requirements 5.1, 5.2, 5.3, 5.4, and 5.5 all relate to multi-tenancy enforcement and can be consolidated into comprehensive properties
- Requirements 4.4 and 9.1 are identical (use official @tool decorator)
- Requirements 3.3 and 9.2 both verify we use the official SDK without custom wrappers
- Requirements 6.1 and 6.3 both test error message quality and can be combined
- Requirement 8.3 is the same as 5.5 (multi-tenancy isolation)

The consolidated properties below eliminate this redundancy while ensuring complete coverage.

### Property 1: Tool Execution Correctness

*For any* tool function and any valid input parameters, executing the tool should produce the expected output format with success=True and appropriate data.

**Validates: Requirements 4.5**

### Property 2: Multi-Tenancy Injection

*For any* tool execution through the agent service, the trainer_id must be present in the tool execution context.

**Validates: Requirements 5.1**

### Property 3: Multi-Tenancy Validation

*For any* tool execution, if trainer_id is missing or invalid (empty string, None, malformed), the tool must reject execution and return an error with success=False.

**Validates: Requirements 5.2, 5.3**

### Property 4: Multi-Tenancy Data Isolation

*For any* two different trainer_ids (trainer_A and trainer_B), data created by trainer_A must not be accessible to trainer_B through any tool execution.

**Validates: Requirements 5.4, 5.5, 8.3**

### Property 5: Error Message Quality

*For any* tool execution that fails (success=False), the error message must be non-empty, descriptive (contains context about what failed), and must not expose internal implementation details (no stack traces, table names, or internal IDs).

**Validates: Requirements 6.1, 6.3, 6.5**

### Property 6: Error Logging

*For any* error condition (tool failure, validation error, timeout), a structured log entry must be created with appropriate severity level and context fields (trainer_id, tool_name, error_type).

**Validates: Requirements 6.4**

### Property 7: Response Format

*For any* message processed through the agent service, the response must be a non-empty string in PT-BR (Brazilian Portuguese) suitable for WhatsApp display (natural language, not JSON or technical output).

**Validates: Requirements 7.3, 7.6**

### Property 8: Execution Timeout

*For any* message processed through the agent service, the total execution time must be less than 10 seconds to maintain WhatsApp compatibility.

**Validates: Requirements 7.4**

## Error Handling

### Error Categories

**Validation Errors** (User-facing)
- Invalid trainer_id: "Unable to process request - authentication failed"
- Invalid tool parameters: "Invalid input: {field} must be {constraint}"
- Missing required fields: "Missing required information: {field}"

**System Errors** (Retry-able)
- DynamoDB throttling: "Service temporarily unavailable, please try again"
- Bedrock API errors: "AI service unavailable, please try again"
- Timeout errors: "Request took too long, please try again"

**Data Errors** (User-facing)
- Student not found: "Student {name} not found in your records"
- Session conflict: "Time slot already booked for {datetime}"
- Duplicate phone number: "Student with phone {number} already registered"

### Error Handling Strategy

1. **Tool Level**: Each tool validates inputs and returns structured errors
2. **Service Level**: StrandsAgentService catches exceptions and converts to user-friendly messages
3. **Handler Level**: message_processor.py logs errors and sends WhatsApp response

### Timeout Protection

```python
# In StrandsAgentService.process_message()
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Agent execution exceeded 10 seconds")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)  # 10-second timeout

try:
    result = agent.run(message=message, context=context)
finally:
    signal.alarm(0)  # Cancel alarm
```

### Structured Logging

All errors logged with context:

```python
logger.error(
    "Tool execution failed",
    trainer_id=trainer_id,
    tool_name=tool_name,
    error_type=type(e).__name__,
    error_message=str(e),
    exc_info=True  # Include traceback in logs only
)
```

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests:

- **Unit tests**: Verify specific examples, integration points, and edge cases
- **Property tests**: Verify universal properties across all inputs using randomization

Both are complementary and necessary for comprehensive coverage. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across the input space.

### Property-Based Testing

**Library**: Hypothesis (Python property-based testing library)

**Configuration**: Minimum 100 iterations per property test (due to randomization)

**Test Tagging**: Each property test must reference its design document property:
```python
# Feature: strands-multi-agent-simplification, Property 4: Multi-Tenancy Data Isolation
@given(trainer_a=trainer_ids(), trainer_b=trainer_ids())
def test_data_isolation(trainer_a, trainer_b):
    assume(trainer_a != trainer_b)
    # Test implementation
```

### Unit Testing Focus

Unit tests should focus on:
- Specific examples demonstrating correct behavior (e.g., registering a student with valid data)
- Integration points (e.g., StrandsAgentService integration with message_processor.py)
- Edge cases (e.g., DynamoDB unavailable, Bedrock timeout)
- Error conditions (e.g., invalid trainer_id, missing required fields)

Avoid writing too many unit tests for input variations—property tests handle comprehensive input coverage.

### Test Organization

```
tests/
├── unit/
│   ├── test_strands_agent_service.py
│   │   - Test service initialization
│   │   - Test message processing interface
│   │   - Test error handling
│   │   - Test timeout protection
│   │
│   ├── test_tool_registration.py
│   │   - Test all tools are registered
│   │   - Test tool decorator usage
│   │   - Test tool signatures
│   │
│   └── test_integration.py
│       - Test message_processor integration
│       - Test end-to-end message flow
│       - Test DynamoDB unavailable scenario
│
├── property/
│   ├── test_tool_correctness.py
│   │   - Property 1: Tool execution correctness
│   │
│   ├── test_multi_tenancy.py
│   │   - Property 2: Multi-tenancy injection
│   │   - Property 3: Multi-tenancy validation
│   │   - Property 4: Multi-tenancy data isolation
│   │
│   ├── test_error_handling.py
│   │   - Property 5: Error message quality
│   │   - Property 6: Error logging
│   │
│   └── test_agent_service.py
│       - Property 7: Response format
│       - Property 8: Execution timeout
```

### Property Test Examples

**Property 4: Multi-Tenancy Data Isolation**
```python
from hypothesis import given, assume
from hypothesis.strategies import text, emails, phone_numbers

@given(
    trainer_a=text(min_size=1, max_size=50),
    trainer_b=text(min_size=1, max_size=50),
    student_name=text(min_size=1, max_size=100),
    student_email=emails(),
    student_phone=phone_numbers()
)
def test_multi_tenancy_isolation(trainer_a, trainer_b, student_name, student_email, student_phone):
    """
    Feature: strands-multi-agent-simplification, Property 4: Multi-Tenancy Data Isolation
    
    For any two different trainer_ids, data created by one trainer
    must not be accessible to the other trainer.
    """
    assume(trainer_a != trainer_b)
    
    # Trainer A registers a student
    result_a = register_student(
        trainer_id=trainer_a,
        name=student_name,
        phone_number=student_phone,
        email=student_email,
        training_goal="Test goal"
    )
    assert result_a['success']
    student_id = result_a['data']['student_id']
    
    # Trainer B tries to view students
    result_b = view_students(trainer_id=trainer_b)
    assert result_b['success']
    
    # Trainer B should not see Trainer A's student
    student_ids_b = [s['student_id'] for s in result_b['data']['students']]
    assert student_id not in student_ids_b
```

**Property 5: Error Message Quality**
```python
from hypothesis import given
from hypothesis.strategies import text, one_of, none, just

@given(
    trainer_id=one_of(none(), just(""), text(max_size=0)),
    message=text(min_size=1, max_size=500)
)
def test_error_message_quality(trainer_id, message):
    """
    Feature: strands-multi-agent-simplification, Property 5: Error Message Quality
    
    For any tool execution that fails, the error message must be descriptive
    and must not expose internal implementation details.
    """
    service = StrandsAgentService()
    result = service.process_message(
        trainer_id=trainer_id,
        message=message
    )
    
    # Should fail due to invalid trainer_id
    assert not result['success']
    assert 'error' in result
    
    error_msg = result['error']
    
    # Error message must be non-empty and descriptive
    assert len(error_msg) > 0
    assert len(error_msg) > 10  # More than just "Error"
    
    # Must not expose internal details
    assert 'Traceback' not in error_msg
    assert 'Exception' not in error_msg
    assert 'DynamoDB' not in error_msg
    assert 'fitagent-main' not in error_msg  # Table name
    assert 'TRAINER#' not in error_msg  # Internal key format
```

### Integration Testing

**Test: End-to-End Message Processing**
```python
def test_message_processor_integration():
    """
    Test that StrandsAgentService integrates correctly with
    message_processor.py Lambda handler.
    """
    # Simulate SQS event
    event = {
        'Records': [{
            'body': json.dumps({
                'phone_number': '+5511999999999',
                'message': 'Registrar novo aluno João',
                'trainer_id': 'test_trainer_123'
            })
        }]
    }
    
    # Call Lambda handler
    response = lambda_handler(event, {})
    
    # Should succeed
    assert response['statusCode'] == 200
    
    # Should have processed message
    body = json.loads(response['body'])
    assert 'response' in body
    assert len(body['response']) > 0
```

### Test Coverage Requirements

- Minimum 70% code coverage for strands_agent_service.py
- 100% coverage for multi-tenancy validation logic
- All 8 correctness properties must have property-based tests
- All error paths must have unit tests

### Mock Strategy

**Mock Bedrock**: Use moto or custom mock for Bedrock responses
**Mock DynamoDB**: Use LocalStack or moto for DynamoDB operations
**Mock Strands SDK**: Only if necessary for unit tests; prefer integration tests with real SDK

