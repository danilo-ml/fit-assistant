# Bugfix Requirements Document

## Introduction

The AI agent powered by Amazon Nova Pro (`us.amazon.nova-pro-v1:0`) via AWS Bedrock and Strands Agents SDK frequently hallucinates tool call results instead of actually executing the registered tools. CloudWatch logs confirm zero tool execution entries while the AI responds as if tools were successfully called, fabricating session IDs, enrollment confirmations, rescheduling results, and OAuth URLs. This affects core business operations (session scheduling, student enrollment, calendar connection) and produces false data that misleads trainers into believing actions were completed when nothing happened in DynamoDB.

The root cause is a combination of: (1) too many tools (20) registered on a single agent overwhelming the model's tool selection capability, (2) Nova Pro's inferior tool-calling reliability compared to Claude models, (3) multi-step operations where the model "shortcuts" by fabricating the second step, and (4) confirmation flows ("Confirmado"/"Sim") where the model fabricates results instead of executing the pending tool call.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the trainer requests to schedule a session (e.g., "Agendar sessão com Juliana dia 11/03 às 08:00") THEN the system fabricates a fake session ID and responds with "sessão criada com sucesso" without calling the `schedule_session` tool, resulting in no session record in DynamoDB.

1.2 WHEN the trainer requests to enroll a student in a group session (e.g., "Inscrever Juliana na sessão") THEN the system fabricates a confirmation message without calling the `enroll_student` tool, resulting in `enrolled_students` remaining empty in DynamoDB.

1.3 WHEN the trainer requests to reschedule a session THEN the system fabricates a fake rescheduled confirmation with a non-existent session ID without calling the `reschedule_session` tool, leaving the original session unchanged.

1.4 WHEN the trainer requests to connect their Google or Outlook calendar THEN the system fabricates a fake OAuth URL with incorrect `client_id` and `redirect_uri` parameters instead of calling the `connect_calendar` tool, producing a non-functional authorization link.

1.5 WHEN the trainer confirms a pending action with "Confirmado", "Sim", or similar affirmative responses THEN the system fabricates the result of the pending action instead of executing the corresponding tool call, producing false confirmation messages with no backend state change.

1.6 WHEN the trainer requests a multi-step operation (e.g., create group session then enroll students) THEN the system executes the first tool call but fabricates the result of the second step without calling the second tool, leaving the operation partially completed.

### Expected Behavior (Correct)

2.1 WHEN the trainer requests to schedule a session THEN the system SHALL call the `schedule_session` tool with the correct parameters and return the real session ID and confirmation from the tool's response, with the session record persisted in DynamoDB.

2.2 WHEN the trainer requests to enroll a student in a group session THEN the system SHALL call the `enroll_student` tool with the session ID and student names, and return the real enrollment result from the tool's response, with `enrolled_students` updated in DynamoDB.

2.3 WHEN the trainer requests to reschedule a session THEN the system SHALL call the `reschedule_session` tool with the session ID and new date/time, and return the real rescheduling result from the tool's response, with the session record updated in DynamoDB.

2.4 WHEN the trainer requests to connect their calendar THEN the system SHALL call the `connect_calendar` tool with the correct provider and return the exact OAuth URL from the tool's response, containing valid `client_id` and `redirect_uri` parameters.

2.5 WHEN the trainer confirms a pending action with an affirmative response THEN the system SHALL execute the corresponding tool call at that moment and return the real result from the tool's response, with the backend state updated accordingly.

2.6 WHEN the trainer requests a multi-step operation THEN the system SHALL execute each tool call sequentially, waiting for the real result of each step before proceeding to the next, ensuring all steps are completed with real data.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the trainer sends a natural language message that does not require tool execution (e.g., "Quais são seus recursos?", "Como funciona?") THEN the system SHALL CONTINUE TO respond with helpful information in PT-BR without calling any tools.

3.2 WHEN the trainer requests to view students or view calendar (read-only operations) THEN the system SHALL CONTINUE TO call the corresponding tool (`view_students`, `view_calendar`) and return real data from DynamoDB.

3.3 WHEN the trainer provides incomplete information for a tool call (e.g., "Agendar sessão com João" without date/time) THEN the system SHALL CONTINUE TO ask for the missing required parameters before attempting to execute the tool.

3.4 WHEN the system encounters a DynamoDB error, Bedrock throttling, or timeout THEN the system SHALL CONTINUE TO return appropriate error messages in PT-BR without fabricating success responses.

3.5 WHEN the trainer sends messages within the 30-second WhatsApp timeout window THEN the system SHALL CONTINUE TO respond within the timeout limit to maintain WhatsApp compatibility.

3.6 WHEN multiple trainers use the system concurrently THEN the system SHALL CONTINUE TO enforce multi-tenancy isolation via `trainer_id` injection, ensuring each trainer only accesses their own data.

3.7 WHEN the deterministic interception for calendar sync or enroll_student is triggered THEN the system SHALL CONTINUE TO bypass the AI agent and execute the tool directly, as these workarounds remain valid until the root cause is fully resolved.
