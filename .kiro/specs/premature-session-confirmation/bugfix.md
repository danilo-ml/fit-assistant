# Bugfix Requirements Document

## Introduction

The session confirmation flow has two related bugs that caused a real incident on 20/03/2026. A trainer received a confirmation request at 08:00 for a session scheduled at 09:00 (the session hadn't even started yet). When the trainer replied "Sim" (Yes) at 08:24, the system failed to recognize it as a confirmation response and instead routed the message to the Strands AI agent, which responded with "can't schedule because 09:00 already passed."

The root cause of Bug 1 is a timezone mismatch: `session_confirmation.py` uses `datetime.utcnow()` to calculate the confirmation time window, but sessions are stored in local time (Brazil, UTC-3) as naive datetimes without timezone info. When the system runs at 08:00 local (11:00 UTC), the time window calculation uses UTC, which can match sessions that haven't occurred yet in local time.

Bug 2 is a consequence of Bug 1: because the confirmation was sent prematurely, by the time the trainer replied "Sim" at 08:24, the `find_pending_confirmation_session_for_trainer()` function either couldn't find the pending session (timing/state issue) or the confirmation flow failed silently, causing the message to fall through to the AI agent.

Note: A previous spec (`session-confirmation-fix`) already addressed cross-trainer phantom confirmations (table scan → GSI query) and leaky confirmation history (empty string → None sentinel). This spec addresses the remaining timezone mismatch and premature confirmation issues that were NOT covered by that fix.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the EventBridge-triggered session confirmation handler runs THEN the system uses `datetime.utcnow()` to calculate the confirmation time window (`check_time_start` and `check_time_end`), but compares these UTC timestamps against `session_datetime` values that are stored in local time (Brazil, UTC-3) as naive datetimes, causing a timezone mismatch of up to 3 hours

1.2 WHEN a session is scheduled at 09:00 local time (stored as naive `2026-03-20T09:00:00`) and the handler runs at 08:00 local time (11:00 UTC) THEN the system calculates `check_time_end = 11:00 - 1h = 10:00 UTC` and `check_time_start = 11:00 - 1h5m = 09:55 UTC`, and since `session_end = 09:00 + 60min = 10:00` (naive local) falls within `[09:55, 10:00]` (naive UTC), the session is incorrectly matched and a premature confirmation is sent before the session has even started

1.3 WHEN a premature confirmation is sent and the trainer replies "Sim" after some delay THEN the `process_confirmation_response()` function may fail to find the pending confirmation session because `find_pending_confirmation_session_for_trainer()` queries for `confirmation_status = 'pending_confirmation'` but the session state may have been altered or the timing window has shifted, causing the function to return `False`

1.4 WHEN `process_confirmation_response()` returns `False` for a "Sim" reply to a premature confirmation THEN the message falls through to the normal message routing pipeline and is processed by the Strands AI agent, which interprets "Sim" as a standalone message and generates an inappropriate response about scheduling

### Expected Behavior (Correct)

2.1 WHEN the session confirmation handler calculates the time window THEN the system SHALL convert `datetime.utcnow()` to the trainer's local timezone (or convert stored `session_datetime` values to UTC) before comparing, ensuring consistent timezone handling across the confirmation time window calculation

2.2 WHEN a session is scheduled at 09:00 local time and the handler runs at 08:00 local time THEN the system SHALL NOT match this session for confirmation because the session has not yet ended (session end = 10:00 local, which is in the future), and no premature confirmation message shall be sent

2.3 WHEN the confirmation time window is calculated correctly with consistent timezone handling THEN the system SHALL only send confirmation requests for sessions whose end time (`session_datetime + duration_minutes`) genuinely falls within the 1-hour-ago window in the same timezone reference frame

2.4 WHEN a trainer replies with a confirmation keyword ("Sim"/"Yes"/"S"/"Não"/"No"/"N") and a pending confirmation session exists for that trainer THEN the system SHALL reliably find and process the pending session, regardless of when the confirmation request was originally sent

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a session has genuinely ended more than 55 minutes ago and less than 65 minutes ago (in consistent timezone terms) THEN the system SHALL CONTINUE TO send a confirmation request to the trainer

3.2 WHEN a trainer sends a regular message that is not a confirmation keyword THEN the system SHALL CONTINUE TO route the message through the normal pipeline to the Strands AI agent

3.3 WHEN a trainer replies "Sim" or "Não" and there is no pending confirmation session THEN the system SHALL CONTINUE TO treat the message as a regular message and route it to the AI agent

3.4 WHEN a trainer confirms or denies a session THEN the system SHALL CONTINUE TO update the session's `confirmation_status` to `completed` or `missed` respectively, along with `confirmed_at` timestamp and `confirmation_response` fields

3.5 WHEN the confirmation handler runs and no sessions need confirmation THEN the system SHALL CONTINUE TO return successfully with `sent: 0, failed: 0` without errors

3.6 WHEN sessions are queried using the `session-date-index` GSI (as fixed by the previous spec) THEN the system SHALL CONTINUE TO scope queries per trainer and not return cross-trainer phantom sessions
