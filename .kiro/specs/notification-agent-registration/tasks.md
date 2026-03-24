# Tasks

- [x] 1. Add notification_tools import to strands_agent_service.py
  - [x] 1.1 Add `notification_tools` to the existing tools import line in `src/services/strands_agent_service.py`
- [x] 2. Create inner tool wrapper and notification_agent in _build_domain_agent_tools()
  - [x] 2.1 Create `send_notification_inner` @tool function inside `_build_domain_agent_tools()` that calls `notification_tools.send_notification(trainer_id, message, recipients, specific_student_ids)`
  - [x] 2.2 Create `notification_agent` @tool function following the Agents-as-Tools pattern with a PT-BR system prompt focused on notification management, using `send_notification_inner` as its tool
  - [x] 2.3 Update the return statement of `_build_domain_agent_tools()` to include `notification_agent` in the returned tuple
  - [x] 2.4 Update the logger.info call to include `notification_agent` in the agents list
- [x] 3. Register notification_agent in the orchestrator
  - [x] 3.1 Update the tuple destructuring in `process_message()` to unpack `notification_agent` from `_build_domain_agent_tools()`
  - [x] 3.2 Add `notification_agent` to the orchestrator's `tools=[...]` list
- [x] 4. Update orchestrator system prompt
  - [x] 4.1 Add `notification_agent` to the list of available agents in the orchestrator_prompt with description of its capabilities
  - [x] 4.2 Add routing keywords for notification_agent (notificação, notificar, avisar, mensagem para alunos, enviar mensagem, broadcast)
- [x] 5. Write unit tests
  - [x] 5.1 Write test verifying `_build_domain_agent_tools()` returns notification_agent in the tuple
  - [x] 5.2 Write test verifying the orchestrator tools list includes notification_agent
  - [x] 5.3 Write test verifying the orchestrator_prompt mentions notification_agent and routing keywords
  - [x] 5.4 Write test verifying existing agents (student, session, payment, calendar) are still present after the fix
