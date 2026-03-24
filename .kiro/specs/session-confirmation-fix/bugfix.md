# Bugfix Requirements Document

## Introduction

The session confirmation flow in FitAgent's WhatsApp assistant has two critical bugs affecting trainer experience. First, the system sends phantom session confirmation messages for sessions that don't exist in the trainer's schedule at the stated time, caused by an inefficient full table scan in `query_sessions_for_confirmation()` that doesn't properly filter by trainer or validate session time windows using the available `session-date-index` GSI. Second, when a trainer replies "Sim" (Yes) to confirm a session, the confirmation is processed correctly but the message also leaks through to the Strands AI agent, which interprets "Sim" as a standalone command and generates nonsensical responses about rescheduling group sessions and removing students from the calendar.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the EventBridge-triggered session confirmation handler runs THEN the system performs a full DynamoDB table SCAN filtering only by `entity_type = SESSION`, `confirmation_status = scheduled`, and `status != cancelled`, without scoping the query to any specific trainer or using the `session-date-index` GSI

1.2 WHEN the table scan returns sessions with `confirmation_status = scheduled` THEN the system calculates session end times in-memory and may match sessions whose `session_datetime` does not correspond to a real upcoming session for the trainer, resulting in phantom confirmation messages being sent for sessions that don't exist at the stated time

1.3 WHEN a trainer replies "Sim", "Yes", "S", "Não", "No", or "N" to a confirmation request THEN `process_confirmation_response()` correctly processes the confirmation and returns `True`, but the `_process_message()` function returns an empty string `""` which is then passed to `_send_response()`

1.4 WHEN `_process_message()` returns an empty string after a successful confirmation response THEN `_send_response()` skips sending (empty body check), but the message has already been fully processed through the confirmation path — however, the flow structure in `_process_message()` correctly short-circuits via the early return, so the AI agent is NOT reached for the confirmation message itself; the real issue is that `process_confirmation_response()` sends its own acknowledgment via `twilio_client.send_message()` AND the orchestrator agent may have previously generated a nonsensical response from conversation history context where "Sim" appeared as a standalone message

1.5 WHEN the DynamoDB table contains a large number of sessions across all trainers THEN the full table scan becomes increasingly expensive and slow, potentially causing Lambda timeouts and unnecessary read capacity consumption

### Expected Behavior (Correct)

2.1 WHEN the session confirmation handler runs THEN the system SHALL query each trainer's sessions individually using the `session-date-index` GSI with `trainer_id` as partition key and `session_datetime` range as sort key, scoped to the confirmation time window (sessions that ended between 55 and 65 minutes ago)

2.2 WHEN querying sessions for confirmation THEN the system SHALL only return sessions that have `confirmation_status = scheduled` and `status != cancelled`, and whose calculated end time (`session_datetime + duration_minutes`) falls within the confirmation time window, ensuring no phantom sessions are sent for confirmation

2.3 WHEN a trainer replies with a confirmation response ("Sim"/"Yes"/"S" or "Não"/"No"/"N") and `process_confirmation_response()` returns `True` THEN the system SHALL immediately stop processing that message and SHALL NOT pass it to the message routing pipeline or the Strands AI agent under any circumstances

2.4 WHEN `process_confirmation_response()` successfully handles a confirmation THEN the system SHALL send exactly one acknowledgment message to the trainer (the confirmation ack) and no additional AI-generated responses

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a trainer sends a regular message (not a confirmation response) THEN the system SHALL CONTINUE TO route the message through the normal pipeline to the Strands AI agent for processing

3.2 WHEN a trainer sends "Sim" or "No" but there is no pending confirmation session for that trainer THEN the system SHALL CONTINUE TO treat the message as a regular message and route it to the AI agent

3.3 WHEN sessions with `confirmation_status = scheduled` exist and their end time falls within the confirmation window THEN the system SHALL CONTINUE TO send confirmation request messages to the appropriate trainer via Twilio

3.4 WHEN a trainer confirms or denies a session THEN the system SHALL CONTINUE TO update the session's `confirmation_status` to `completed` or `missed` respectively, along with the `confirmed_at` timestamp and `confirmation_response` fields

3.5 WHEN the confirmation handler runs and no sessions need confirmation THEN the system SHALL CONTINUE TO return successfully with `sent: 0, failed: 0` without errors
