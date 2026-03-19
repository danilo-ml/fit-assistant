# Agent Tool Hallucination Fix - Bugfix Design

## Overview

The AI agent powered by Amazon Nova Pro (`us.amazon.nova-pro-v1:0`) via Strands Agents SDK hallucinates tool call results instead of executing registered tools. The agent fabricates session IDs, enrollment confirmations, OAuth URLs, and rescheduling results — producing false data with zero actual tool execution in CloudWatch logs.

This design recommends the **Agents-as-Tools** multi-agent pattern from the official Strands SDK 1.0+. An orchestrator agent delegates to specialized domain agents (Student, Session, Payment, Calendar), each wrapped as a `@tool` function with only their domain tools. This reduces tool-calling complexity per agent, uses Claude Haiku for reliable tool execution, and leverages the native SDK pattern rather than custom orchestration code.

## Glossary

- **Bug_Condition (C)**: The AI agent responds as if a tool was executed but no actual tool call was made via the Strands SDK
- **Tool Hallucination**: When the LLM generates fabricated tool output (fake IDs, URLs, confirmations) without invoking the tool function
- **Agents-as-Tools**: Official Strands SDK pattern where specialized agents are wrapped as `@tool` callable functions used by an orchestrator agent
- **Orchestrator Agent**: Top-level agent that receives user messages and delegates to the appropriate domain agent tool
- **Domain Agent**: Specialized agent with focused tools for one domain (Student, Session, Payment, Calendar)

## Bug Details

### Bug Condition

The bug manifests when a trainer sends a message requiring tool execution. The current `StrandsAgentService.process_message()` invokes a single Strands Agent with 20 tools, but Nova Pro generates fabricated tool results instead of making actual tool calls.

### Root Causes

1. **Model Capability Mismatch**: Nova Pro has inferior tool-calling reliability compared to Claude. With 20 tools, the model "shortcuts" by generating plausible-looking output instead of invoking the tool-calling protocol.
2. **Tool Overload**: 20 tools on a single agent exceeds Nova Pro's effective capacity. Similar tools (`schedule_session` vs `schedule_group_session` vs `schedule_recurring_session`) confuse the model.
3. **System Prompt Overload**: The system prompt is ~4000+ tokens with many rules, diluting the model's attention on the critical instruction to actually call tools.
4. **Confirmation Flow Ambiguity**: "Sim"/"Confirmado" lacks clear context about which pending tool to execute.
5. **Multi-Step Shortcutting**: For sequential tool calls, the model fabricates the second step after executing the first.

## Strands SDK Pattern Analysis

Based on the [official Strands Agents documentation](https://strandsagents.com/) and the [AWS multi-agent collaboration blog](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/), Strands SDK 1.0+ offers 4 multi-agent patterns:

| Pattern | Description | Best For |
|---|---|---|
| **Agents-as-Tools** | Orchestrator calls specialized agents wrapped as `@tool` | Hierarchical delegation, domain routing |
| **Swarm** | Decentralized agents with shared memory and handoffs | Collaborative brainstorming, iterative refinement |
| **Graph** | Deterministic workflow with conditional routing | Multi-stage pipelines with approval gates |
| **Workflow** | Sequential pipeline, output feeds into next agent | Content generation with review stages |

### Why Agents-as-Tools (not Swarm)

For FitAgent's use case (WhatsApp chatbot → classify intent → call ONE domain agent → return response):

- **Agents-as-Tools** is the correct pattern because:
  - The flow is simple: user message → orchestrator decides which specialist → specialist executes tools → response
  - No need for agents to collaborate, brainstorm, or iterate with each other
  - The orchestrator maintains control and synthesizes the final response
  - Native SDK pattern — no custom orchestration code needed
  - Each domain agent has focused tools (3-12), well within model capacity

- **Swarm** is NOT appropriate because:
  - Designed for decentralized collaboration where agents share memory and refine each other's work
  - Adds unnecessary latency with multiple iterations and handoffs
  - Overkill for a simple intent-routing use case
  - More complex to debug and monitor

### Official SDK Code Pattern

From the [Strands Agents-as-Tools documentation](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/):

```python
from strands import Agent, tool

# Specialized agent wrapped as a tool
@tool
def student_agent(query: str) -> str:
    """Handle student management queries (register, view, update students)."""
    agent = Agent(
        system_prompt="You manage student records for personal trainers...",
        tools=[register_student, view_students, update_student]
    )
    response = agent(query)
    return str(response)

# Orchestrator uses domain agents as tools
orchestrator = Agent(
    system_prompt="Route queries to the appropriate specialist agent...",
    tools=[student_agent, session_agent, payment_agent, calendar_agent]
)

result = orchestrator("Registrar novo aluno João Silva...")
```

## Recommended Architecture

```
User Message (WhatsApp)
    │
    ▼
┌──────────────────────────────────────┐
│       Orchestrator Agent              │  ← Claude Haiku
│  tools=[student_agent,               │     Decides which specialist to call
│         session_agent,                │     Handles general chat directly
│         payment_agent,                │
│         calendar_agent]               │
└──────────┬───────────────────────────┘
           │ calls @tool function
    ┌──────┴──────┬──────────────┬──────────────┐
    ▼             ▼              ▼              ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│@tool     │ │@tool     │ │@tool     │ │@tool     │
│student_  │ │session_  │ │payment_  │ │calendar_ │
│agent()   │ │agent()   │ │agent()   │ │agent()   │
│ 3 tools  │ │12 tools  │ │ 4 tools  │ │ 1 tool   │
│(Haiku)   │ │(Haiku)   │ │(Haiku)   │ │(Haiku)   │
└─────────┘ └──────────┘ └──────────┘ └──────────┘
```

### Agent Specifications

**Orchestrator Agent** (Claude Haiku, 4 tool-agents)
- Receives user message + conversation history
- Decides which domain agent to call based on intent
- Handles general conversation directly (greetings, help, feature questions)
- System prompt includes routing guidance in PT-BR

**Student Agent Tool** (Claude Haiku, 3 tools)
- `register_student`, `view_students`, `update_student`
- Focused PT-BR prompt for student management

**Session Agent Tool** (Claude Haiku, 12 tools)
- Individual: `schedule_session`, `schedule_recurring_session`, `reschedule_session`, `cancel_session`, `cancel_student_sessions`, `view_calendar`
- Group: `schedule_group_session`, `enroll_student`, `remove_student`, `cancel_group_session`, `reschedule_group_session`, `configure_group_size_limit`
- Focused PT-BR prompt for scheduling, conflict detection, group sessions
- Includes date/time context (current date, Brazil timezone)

**Payment Agent Tool** (Claude Haiku, 4 tools)
- `register_payment`, `confirm_payment`, `view_payments`, `view_payment_status`
- Focused PT-BR prompt for payment tracking

**Calendar Agent Tool** (Claude Haiku, 1 tool)
- `connect_calendar`
- Focused PT-BR prompt: NEVER invent OAuth URLs, always use tool result

### Latency Analysis

Two sequential LLM calls (orchestrator + domain agent) within 30-second timeout:
- Claude Haiku: ~1-3s per call
- Orchestrator call: ~1-2s (just routing, no tool execution)
- Domain agent call: ~2-5s (tool selection + execution)
- Total expected: 3-7s, well within 30s budget

### Cost Analysis

| Component | Model | Cost/1M input | Cost/1M output |
|---|---|---|---|
| Current (single agent) | Nova Pro | $0.80 | $3.20 |
| Orchestrator | Claude Haiku | $0.25 | $1.25 |
| Domain Agent | Claude Haiku | $0.25 | $1.25 |

Per message: ~2 Haiku calls ≈ $0.001 vs 1 Nova Pro call ≈ $0.002 → **~50% cost reduction**

## Preservation Requirements

**Unchanged Behaviors:**
- Natural language responses to non-tool messages (handled by orchestrator directly)
- Read-only operations (`view_students`, `view_calendar`, `view_payments`) return real DynamoDB data
- Incomplete information handling prompts for missing required parameters
- Error handling returns appropriate PT-BR messages
- 30-second WhatsApp timeout enforcement
- Multi-tenancy isolation via `trainer_id` injection
- Conversation history maintained across messages

## Correctness Properties

Property 1: Tool Execution Guarantee

_For any_ trainer message requiring a tool call, the orchestrator SHALL delegate to the correct domain agent, which SHALL execute the tool via Strands SDK and return only real data. No fabricated IDs, URLs, or confirmations.

**Validates: Bugfix Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

Property 2: Preservation

_For any_ input NOT requiring a tool call, the system SHALL produce equivalent behavior to the original system.

**Validates: Bugfix Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7**

Property 3: Routing Correctness

_For any_ trainer message, the orchestrator SHALL route to the correct domain agent based on intent.

## Fix Implementation

### Changes Required

**File**: `src/services/strands_agent_service.py` — Major refactor

1. **Create domain agent tool functions**: 4 functions decorated with `@tool` — `student_agent(query)`, `session_agent(query)`, `payment_agent(query)`, `calendar_agent(query)`. Each creates a Strands `Agent` with focused system prompt and domain-specific tools, calls it, and returns the string response.

2. **Create orchestrator agent**: Single `Agent` with `tools=[student_agent, session_agent, payment_agent, calendar_agent]` and a routing system prompt in PT-BR.

3. **Refactor `process_message()`**: Replace `agent = self._create_agent_for_trainer(trainer_id)` + `agent(message)` with `orchestrator(message)`. The orchestrator decides which domain agent to call. Maintain conversation history, timeout, and error handling.

4. **Inject trainer_id**: Each domain agent tool function receives `trainer_id` via closure (same pattern as current wrapper tools in `_create_agent_for_trainer`). The domain agent's inner tools are bound to the trainer_id.

5. **Remove `_create_agent_for_trainer()`**: Delete the old single-agent factory with 20 tools.

**File**: `src/services/conversation_handlers.py`

6. **Remove deterministic interceptions**: Delete `_handle_calendar_sync_if_requested()`, `_handle_enroll_if_requested()`, and `_find_recent_group_session_id()`. The multi-agent architecture eliminates the hallucination that required these workarounds.

**File**: `src/config.py`

7. **Update model config**: Change `bedrock_model_id` default to `anthropic.claude-3-haiku-20240307-v1:0`.

**File**: `.env`, `.env.example`, `infrastructure/template.yml`

8. **Update environment**: Set model ID to Claude Haiku.

## Testing Strategy

### Unit Tests
- Test orchestrator routes student queries to student_agent
- Test orchestrator routes session queries to session_agent
- Test orchestrator handles general chat without calling domain agents
- Test each domain agent executes its tools correctly
- Test trainer_id injection works across all domain agents
- Test error handling: domain agent failure, timeout

### Integration Tests
- Full flow: message → orchestrator → domain agent → DynamoDB → PT-BR response
- Multi-step: "Criar sessão em grupo e inscrever João" → session_agent handles both
- Conversation continuity across messages
- 30-second timeout with two sequential LLM calls
- Concurrent trainers (multi-tenancy isolation)

### Preservation Tests
- General conversation handled by orchestrator directly
- Read-only operations return real data
- Incomplete info prompting still works
- Error messages still in PT-BR
