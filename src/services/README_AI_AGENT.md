# AI Agent Service Documentation

## Overview

The AIAgent class provides natural language understanding and tool execution capabilities using AWS Bedrock with Claude 3 models. It serves as the core conversational AI interface for the FitAgent WhatsApp Assistant platform.

## Architecture

### Components

1. **Tool Registry**: JSON schemas defining all 11 available tools with parameters
2. **Tool Execution Map**: Mapping from tool names to Python functions
3. **Bedrock Integration**: AWS Bedrock Converse API for Claude model interaction
4. **Context Management**: Conversation history tracking for multi-turn interactions

### Tool-Calling Flow

```
User Message → Bedrock (Claude) → Tool Request → Execute Tool → Return Result → Bedrock → Natural Language Response
```

## Available Tools

### Student Management (3 tools)
- `register_student`: Register new student with trainer
- `view_students`: List all students for trainer
- `update_student`: Update student information

### Session Management (4 tools)
- `schedule_session`: Schedule new training session
- `reschedule_session`: Move session to new date/time
- `cancel_session`: Cancel existing session
- `view_calendar`: View sessions in date range

### Payment Management (3 tools)
- `register_payment`: Record payment from student
- `confirm_payment`: Confirm pending payment
- `view_payments`: List payments with filtering

### Calendar Integration (1 tool)
- `connect_calendar`: Generate OAuth URL for Google/Outlook

## Usage

### Basic Usage

```python
from src.services.ai_agent import AIAgent

# Initialize agent
agent = AIAgent()

# Process user message
result = agent.process_message(
    trainer_id="trainer123",
    message="Schedule a session with John tomorrow at 2pm for 60 minutes"
)

if result["success"]:
    print(result["response"])  # Natural language response
    print(result["tool_calls"])  # Tools that were executed
else:
    print(result["error"])  # Error message
```

### With Conversation History

```python
# Maintain conversation context
conversation_history = [
    {
        "role": "user",
        "content": [{"text": "I want to schedule a session"}]
    },
    {
        "role": "assistant",
        "content": [{"text": "Sure! Which student is this for?"}]
    }
]

result = agent.process_message(
    trainer_id="trainer123",
    message="John Doe",
    conversation_history=conversation_history
)
```

### Custom Configuration

```python
# Use different model or region
agent = AIAgent(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-west-2"
)
```

## Response Format

### Success Response

```python
{
    "success": True,
    "response": "I've scheduled a 60-minute session with John for tomorrow at 2:00 PM.",
    "tool_calls": [
        {
            "tool": "schedule_session",
            "parameters": {
                "student_name": "John",
                "date": "2024-01-21",
                "time": "14:00",
                "duration_minutes": 60
            },
            "result": {
                "success": True,
                "data": {
                    "session_id": "xyz789",
                    "student_name": "John",
                    "session_datetime": "2024-01-21T14:00:00",
                    "duration_minutes": 60,
                    "status": "scheduled"
                }
            }
        }
    ],
    "execution_time": 1.234
}
```

### Error Response

```python
{
    "success": False,
    "error": "I'm having trouble processing your request right now. Please try again in a moment.",
    "tool_calls": []
}
```

## Performance

- **Target**: Complete tool execution within 5 seconds
- **Tracking**: Execution time included in response
- **Optimization**: Max 5 iterations to prevent infinite loops

## Error Handling

### User-Facing Errors
- Invalid parameters → Request clarification
- Tool failures → Explain error and suggest next steps
- Missing information → Ask for required details

### System Errors
- Bedrock API errors → Generic retry message
- Tool execution errors → Logged with details
- Timeout protection → Max iterations limit

## Configuration

### Environment Variables

```bash
# AWS Bedrock Configuration
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1

# For LocalStack testing
AWS_ENDPOINT_URL=http://localhost:4566
```

### Settings (src/config.py)

```python
class Settings(BaseSettings):
    bedrock_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0"
    bedrock_region: str = "us-east-1"
    conversation_ttl_hours: int = 24
    max_message_history: int = 10
```

## Testing

### Unit Tests

```bash
# Run AI agent tests
pytest tests/unit/test_ai_agent.py -v

# Run with coverage
pytest tests/unit/test_ai_agent.py --cov=src.services.ai_agent
```

### Test Coverage

- Tool registry construction
- Tool execution with parameter injection
- Message processing with Bedrock
- Conversation context management
- Error handling scenarios
- Performance requirements

## Integration with Message Processor

The AI agent is called from the message processor handlers:

```python
from src.services.ai_agent import AIAgent

agent = AIAgent()

def handle_trainer_message(trainer_id: str, message: str):
    """Handle trainer messages with AI agent."""
    result = agent.process_message(
        trainer_id=trainer_id,
        message=message
    )
    
    if result["success"]:
        return result["response"]
    else:
        return "I'm sorry, I couldn't process that request."
```

## Logging

All operations are logged with structured JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Tool executed successfully",
  "service": "fitagent",
  "trainer_id": "trainer123",
  "tool_name": "schedule_session",
  "success": true
}
```

## Security Considerations

1. **Parameter Injection**: trainer_id automatically injected, not user-controllable
2. **Input Sanitization**: All tool inputs sanitized before execution
3. **Error Messages**: Generic errors to users, detailed logs for debugging
4. **Rate Limiting**: Handled at API Gateway level

## Troubleshooting

### Common Issues

**Issue**: "Maximum tool execution iterations reached"
- **Cause**: Bedrock repeatedly requesting tools without finishing
- **Solution**: Simplify user request or check tool implementations

**Issue**: "I'm having trouble processing your request"
- **Cause**: Bedrock API error (throttling, timeout, etc.)
- **Solution**: Check CloudWatch logs for specific error, retry request

**Issue**: Tool execution fails
- **Cause**: Invalid parameters or business logic error
- **Solution**: Check tool logs for specific error message

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('src.services.ai_agent').setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Streaming Responses**: Support for real-time response streaming
2. **Tool Chaining**: Automatic multi-step workflows
3. **Context Summarization**: Compress long conversation histories
4. **Custom Tools**: Dynamic tool registration per trainer
5. **Multi-Language**: Support for non-English conversations

## References

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Claude 3 Model Guide](https://docs.anthropic.com/claude/docs)
- [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [Tool Use with Claude](https://docs.anthropic.com/claude/docs/tool-use)

## Requirements Validation

This implementation validates the following requirements:

- **Requirement 12.1**: Uses AWS Bedrock with Claude models for NLU ✓
- **Requirement 12.2**: Implements tool-calling architecture with 11 functions ✓
- **Requirement 12.3**: Executes tools and returns results within 5 seconds ✓
- **Requirement 12.4**: Validates tool parameters before execution ✓
- **Requirement 12.5**: Provides user-friendly error messages ✓
- **Requirement 12.6**: Maintains conversation context across tool executions ✓
