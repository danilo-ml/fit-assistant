# Implementation Plan: Agent Tool Hallucination Fix (Agents-as-Tools Pattern)

## Overview

Replace the single 20-tool Nova Pro agent with the official Strands SDK **Agents-as-Tools** pattern: an orchestrator agent (Claude Haiku) delegates to 4 specialized domain agents (`student_agent`, `session_agent`, `payment_agent`, `calendar_agent`), each wrapped as a `@tool` function with focused tools. Remove existing deterministic interception workarounds.

## Tasks

- [x] 1. Update config and model settings
  - [x] 1.1 Update `src/config.py`
    - Change `bedrock_model_id` default to `anthropic.claude-3-haiku-20240307-v1:0`
    - _Requirements: Design — switch from Nova Pro to Claude Haiku_

  - [x] 1.2 Update `.env` and `.env.example`
    - Set `BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0`
    - _Requirements: Design — environment variables_

  - [x] 1.3 Update `infrastructure/template.yml`
    - Update Lambda environment variable `BEDROCK_MODEL_ID` default to Claude Haiku
    - _Requirements: Design — infrastructure update_

- [x] 2. Refactor `StrandsAgentService` to Agents-as-Tools pattern
  - [x] 2.1 Create domain agent `@tool` functions in `StrandsAgentService`
    - Create `_build_domain_agent_tools(self, trainer_id)` method that returns 4 `@tool`-decorated functions:
      - `student_agent(query: str) -> str` — creates Agent with `register_student`, `view_students`, `update_student`
      - `session_agent(query: str) -> str` — creates Agent with all session + group session tools (12 tools)
      - `payment_agent(query: str) -> str` — creates Agent with `register_payment`, `confirm_payment`, `view_payments`, `view_payment_status`
      - `calendar_agent(query: str) -> str` — creates Agent with `connect_calendar`
    - Each domain agent gets its own focused PT-BR system prompt
    - Each domain agent uses Claude Haiku via `self.model`
    - Inner tools bound to `trainer_id` via closure (same wrapper pattern as current `_create_agent_for_trainer`)
    - Session agent prompt includes date/time context (current date, Brazil timezone, no UTC conversion)
    - Calendar agent prompt emphasizes: NEVER invent OAuth URLs
    - _Requirements: Bugfix 2.1-2.6, Design — domain agent tools_

  - [x] 2.2 Create orchestrator agent in `process_message()`
    - Create orchestrator `Agent` with `tools=[student_agent, session_agent, payment_agent, calendar_agent]`
    - Orchestrator system prompt in PT-BR with routing guidance:
      - Student keywords → student_agent
      - Session/scheduling keywords → session_agent
      - Payment keywords → payment_agent
      - Calendar/sync keywords → calendar_agent
      - General chat → respond directly without calling any tool
    - Orchestrator uses Claude Haiku via `self.model`
    - Load conversation history into orchestrator agent
    - Maintain 30-second timeout via ThreadPoolExecutor
    - Preserve all existing error handling (DynamoDB, Bedrock, timeout, validation)
    - _Requirements: Bugfix 2.1-2.6, 3.4, 3.5, 3.6, Design — orchestrator agent_

  - [x] 2.3 Remove `_create_agent_for_trainer()` method
    - Delete the old single-agent factory with 20 tools
    - _Requirements: Design — remove old architecture_

  - [x] 2.4 Simplify `self.system_prompt` in `__init__`
    - Remove the massive monolithic prompt (no longer used by single agent)
    - Replace with orchestrator-specific routing prompt
    - _Requirements: Design — system prompt overload fix_

- [x] 3. Remove deterministic interception workarounds from `conversation_handlers.py`
  - [x] 3.1 Remove `_handle_calendar_sync_if_requested()` method and its call in `handle_message()`
    - Calendar agent now handles this properly
    - _Requirements: Design — remove workarounds_

  - [x] 3.2 Remove `_handle_enroll_if_requested()` and `_find_recent_group_session_id()` methods and their calls in `handle_message()`
    - Session agent now handles enrollment properly
    - _Requirements: Design — remove workarounds_

- [x] 4. Test and validate
  - [x] 4.1 Run existing test suite to check for regressions
    - `make test` inside Docker container
    - Fix any broken imports or test failures from the refactor
    - _Requirements: Bugfix 3.1-3.7_

  - [x] 4.2 Manual validation of key flows
    - Test: "Agendar sessão com Juliana dia 20/03 às 08:00, 60 minutos" → verify real session in DynamoDB
    - Test: "Inscrever Juliana na sessão [id]" → verify real enrollment
    - Test: "Conectar meu Google Calendar" → verify real OAuth URL from tool
    - Test: "Ver meus alunos" → verify real data returned
    - Test: "Olá, como funciona?" → verify general response without tool calls
    - _Requirements: Bugfix 2.1-2.6, 3.1-3.7_
