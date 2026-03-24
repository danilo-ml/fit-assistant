# Premature Session Confirmation - Bugfix Design

## Overview

The session confirmation flow has a timezone mismatch bug that causes premature confirmation messages. `session_confirmation.py` uses `datetime.utcnow()` to calculate the confirmation time window, but `session_datetime` values are stored as naive datetimes in local time (Brazil, UTC-3). This 3-hour offset causes the system to match sessions that haven't even started yet. As a consequence, when a trainer replies "Sim" to a premature confirmation, `find_pending_confirmation_session_for_trainer()` may fail to locate the pending session (due to timing/state issues), causing the reply to fall through to the Strands AI agent. The fix normalizes timezone handling in the time window calculation and hardens the confirmation response lookup.

## Glossary

- **Bug_Condition (C)**: Two conditions: (C1) `lambda_handler()` in `session_confirmation.py` uses `datetime.utcnow()` to compute the time window but compares against `session_datetime` stored in local time (UTC-3); (C2) `find_pending_confirmation_session_for_trainer()` fails to find a pending session created by a premature confirmation, causing the trainer's "Sim" reply to fall through to the AI agent
- **Property (P)**: (P1) Time window calculation uses consistent timezone reference so only genuinely-ended sessions are matched; (P2) Confirmation responses from trainers with a `pending_confirmation` session are always found and processed
- **Preservation**: Legitimate confirmation flows for sessions that genuinely ended 55-65 minutes ago, regular message routing, session status updates, and the per-trainer GSI query pattern (from previous fix) must remain unchanged
- **`lambda_handler()`**: Function in `src/handlers/session_confirmation.py` that calculates `check_time_start` and `check_time_end` using `datetime.utcnow()`
- **`query_sessions_for_confirmation()`**: Function in `src/handlers/session_confirmation.py` that compares the UTC-derived time window against naive local-time `session_datetime` values
- **`process_confirmation_response()`**: Function in `src/handlers/message_processor.py` that detects "Sim"/"Não" replies and delegates to `find_pending_confirmation_session_for_trainer()`
- **`find_pending_confirmation_session_for_trainer()`**: Function in `src/handlers/message_processor.py` that queries DynamoDB for sessions with `confirmation_status = 'pending_confirmation'`
- **`session-date-index` GSI**: DynamoDB Global Secondary Index with PK=`trainer_id`, SK=`session_datetime`, Projection=ALL
- **Brazil timezone (UTC-3)**: The operational timezone for all trainers; sessions are stored as naive datetimes in this timezone

## Bug Details

### Bug Condition

The bug manifests when the EventBridge-triggered confirmation handler runs and uses UTC time to calculate the 1-hour-ago window, but compares it against session datetimes stored in local time (UTC-3). This creates a 3-hour forward shift: at 08:00 local (11:00 UTC), the system looks for sessions ending around 10:00 (UTC-based calculation), which matches a 09:00 local session that hasn't even started. The premature confirmation then creates a cascading failure when the trainer replies.

**Formal Specification:**
```
FUNCTION isBugCondition_TimezoneMismatch(now_utc, session)
  INPUT: now_utc of type datetime (UTC), session of type Session
  OUTPUT: boolean

  check_time_end := now_utc - 1 hour
  check_time_start := now_utc - 1 hour 5 minutes
  session_end_local := session.session_datetime + session.duration_minutes

  RETURN session_end_local >= check_time_start
         AND session_end_local <= check_time_end
         AND session_end_local > (now_utc - 3 hours)
         -- i.e., the session hasn't actually ended 1 hour ago in local time,
         -- but the naive comparison makes it appear so
END FUNCTION

FUNCTION isBugCondition_ConfirmationFallthrough(message, phone_number)
  INPUT: message of type str, phone_number of type str
  OUTPUT: boolean

  normalized := message.strip().upper()
  RETURN normalized IN ['SIM', 'YES', 'S', 'NÃO', 'NAO', 'NO', 'N']
         AND hasPendingConfirmationSession(phone_number)
         AND find_pending_confirmation_session_for_trainer(trainer_id) returns None
         -- The session exists with pending_confirmation status but the lookup fails
END FUNCTION
```

### Examples

- Session scheduled at 09:00 local (stored as naive `2026-03-20T09:00:00`, 60min duration). Handler runs at 08:00 local (11:00 UTC). UTC window: `[09:55, 10:00]`. Session end = `09:00 + 60min = 10:00` (naive). Since `10:00` falls in `[09:55, 10:00]`, the session is matched — but it hasn't even started yet in local time. Premature confirmation sent.
- Trainer receives premature confirmation at 08:00 for a 09:00 session. Replies "Sim" at 08:24. `find_pending_confirmation_session_for_trainer()` queries for `confirmation_status = 'pending_confirmation'` — the session IS in that state (set when the premature confirmation was sent), but the function returns the first item sorted by `session_datetime`. If there are multiple pending sessions or the query fails for another reason, the reply falls through to the AI agent.
- Session scheduled at 14:00 local (60min). Handler runs at 18:05 local (21:05 UTC). UTC window: `[19:55, 20:00]`. Session end = `15:00` (naive). `15:00` is NOT in `[19:55, 20:00]`, so this legitimate session is MISSED for confirmation — the timezone mismatch can also cause false negatives.
- Session scheduled at 16:00 local (60min). Handler runs at 17:05 local (20:05 UTC). UTC window: `[18:55, 19:00]`. Session end = `17:00` (naive). `17:00` is NOT in `[18:55, 19:00]`. This session genuinely ended 1h5m ago in local time but is missed because the UTC window is 3 hours ahead.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Sessions that genuinely ended between 55 and 65 minutes ago (in local time) must continue to receive confirmation requests
- Regular trainer messages (not confirmation responses) are routed to the Strands AI agent normally
- When "Sim"/"Não" is sent but NO pending confirmation exists, the message is treated as a regular message
- Session `confirmation_status` updates to `completed` or `missed` with correct timestamps continue to work
- Confirmation acknowledgment messages ("✅ Sessão com..." / "❌ Sessão com...") continue to be sent via Twilio
- The per-trainer GSI query pattern (from previous spec fix) remains unchanged
- `format_confirmation_message()` output format remains unchanged
- The confirmation handler returns `{sent: 0, failed: 0}` when no sessions need confirmation

**Scope:**
All inputs that do NOT involve the timezone mismatch in time window calculation or the confirmation response lookup should be completely unaffected by this fix. This includes:
- All regular WhatsApp messages from trainers and students
- Onboarding flow messages
- Student message handling
- Payment, calendar, and notification operations
- Non-confirmation keyword messages

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **`datetime.utcnow()` vs naive local datetimes (Bug 1 — Primary)**: `session_confirmation.py` line ~57 calls `datetime.utcnow()` to get `now`, then computes `check_time_start = now - timedelta(hours=1, minutes=5)` and `check_time_end = now - timedelta(hours=1)`. These are UTC timestamps. But `session.session_datetime` is stored as a naive datetime in Brazil local time (UTC-3). The comparison `start_time <= session_end <= end_time` compares UTC values against local values without conversion, creating a 3-hour offset.

2. **No timezone awareness anywhere in the pipeline**: Neither the stored `session_datetime` nor the computed time window carries timezone info. Python's `datetime` comparison of naive datetimes doesn't raise errors — it just compares the raw values, silently producing wrong results.

3. **`find_pending_confirmation_session_for_trainer()` returns oldest session (Bug 2)**: The function sorts by `session_datetime` ascending and returns `items[0]` — the oldest pending session. If a trainer has multiple pending sessions (e.g., one premature, one legitimate), the function may return the wrong one. More critically, if the premature confirmation was sent but the session state was later modified (e.g., by a concurrent process), the lookup may fail entirely.

4. **No robustness in confirmation response matching**: `process_confirmation_response()` depends entirely on `find_pending_confirmation_session_for_trainer()` finding exactly one pending session. If the function returns `None` (no pending session found), the entire confirmation flow returns `False`, and the "Sim" message falls through to the AI agent pipeline.

## Correctness Properties

Property 1: Bug Condition - Timezone-Consistent Time Window Calculation

_For any_ invocation of the session confirmation handler, the time window calculation SHALL use the same timezone reference as the stored `session_datetime` values (Brazil local time, UTC-3), ensuring that only sessions whose end time (`session_datetime + duration_minutes`) genuinely falls within the 55-65 minute ago window in local time are matched for confirmation. Sessions that have not yet ended in local time SHALL NOT be matched.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Legitimate Confirmation Flow and Message Routing

_For any_ session that has genuinely ended between 55 and 65 minutes ago in consistent timezone terms, the confirmation handler SHALL continue to send a confirmation request. _For any_ trainer reply to a valid pending confirmation, `find_pending_confirmation_session_for_trainer()` SHALL reliably find and return the pending session. _For any_ non-confirmation message, the message routing pipeline SHALL behave identically to the original code.

**Validates: Requirements 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `src/handlers/session_confirmation.py`

**Function**: `lambda_handler()`

**Specific Changes**:
1. **Replace `datetime.utcnow()` with local time**: Use `datetime.now()` with the Brazil timezone (UTC-3) or apply a fixed offset of `-timedelta(hours=3)` to `datetime.utcnow()`. Since sessions are stored as naive local datetimes, the time window must also be in local time. The simplest approach is `now = datetime.utcnow() - timedelta(hours=3)` to convert UTC to Brazil time, or use `pytz`/`zoneinfo` with `America/Sao_Paulo` if available.
2. **Update time window comments**: Clarify in code comments that the time window is calculated in Brazil local time to match stored `session_datetime` values.

**Function**: `query_sessions_for_confirmation()`

**Specific Changes**:
3. **Ensure consistent timezone in comparison**: The `start_time` and `end_time` parameters passed from `lambda_handler()` will now be in local time, so the comparison `start_time <= session_end <= end_time` will be timezone-consistent. No changes needed in this function itself if the caller passes correct local-time values.

**File**: `src/handlers/message_processor.py`

**Function**: `find_pending_confirmation_session_for_trainer()`

**Specific Changes**:
4. **Sort by most recent session instead of oldest**: Change the sort to descending order (`reverse=True`) so the most recently scheduled pending session is returned first. This makes the function more robust when multiple pending sessions exist (e.g., due to a premature confirmation that wasn't cleaned up).
5. **Add logging for debugging**: Log the number of pending sessions found and which one was selected, to aid debugging if the issue recurs.

**Function**: `process_confirmation_response()`

**Specific Changes**:
6. **Add fallback logging when no pending session found**: When `find_pending_confirmation_session_for_trainer()` returns `None` for a confirmation keyword, log a warning with the trainer_id so premature confirmation issues can be detected in monitoring.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the timezone mismatch bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the timezone mismatch BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate the confirmation handler running at various local times and verify that sessions are incorrectly matched due to the UTC vs local time mismatch. Mock `datetime.utcnow()` to control the current time and create sessions with known local-time datetimes.

**Test Cases**:
1. **Premature Match Test**: Create a session at 09:00 local (60min). Mock `utcnow()` to return 11:00 UTC (08:00 local). Assert the session IS matched by the unfixed code (will demonstrate the bug — session hasn't started yet)
2. **Missed Legitimate Session Test**: Create a session at 14:00 local (60min). Mock `utcnow()` to return 21:05 UTC (18:05 local). Assert the session is NOT matched by the unfixed code (will demonstrate false negative — session ended 3h5m ago in local time but the UTC window misses it)
3. **Confirmation Fallthrough Test**: Send premature confirmation, then simulate trainer replying "Sim" after a delay. Assert that `process_confirmation_response()` returns `False` on unfixed code when the pending session lookup fails (will demonstrate the cascading bug)

**Expected Counterexamples**:
- Sessions matched for confirmation that haven't ended yet in local time
- Sessions missed for confirmation that genuinely ended in the correct window
- Possible causes: `datetime.utcnow()` used directly against naive local-time session datetimes

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL (now_utc, session) WHERE isBugCondition_TimezoneMismatch(now_utc, session) DO
  now_local := now_utc - 3 hours
  result := query_sessions_for_confirmation_fixed(db_client, now_local - 1h5m, now_local - 1h)
  ASSERT session NOT IN result  -- premature sessions should not be matched
END FOR

FOR ALL (message, phone_number) WHERE isBugCondition_ConfirmationFallthrough(message, phone_number) DO
  -- After timezone fix, premature confirmations won't be sent, so this path won't occur
  -- But if a pending session exists, the lookup should find it
  result := find_pending_confirmation_session_for_trainer_fixed(trainer_id)
  ASSERT result IS NOT None when pending session exists
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL (now_local, session) WHERE session genuinely ended 55-65 min ago in local time DO
  result_fixed := query_sessions_for_confirmation_fixed(db_client, start, end)
  ASSERT session IN result_fixed  -- legitimate sessions still matched
END FOR

FOR ALL (message, phone_number) WHERE message is NOT a confirmation keyword DO
  ASSERT process_confirmation_response_fixed(phone_number, message) == False
  ASSERT message is routed to AI agent normally
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (random session times, durations, current times)
- It catches edge cases at time window boundaries that manual tests might miss
- It provides strong guarantees that legitimate confirmation flows are unchanged

**Test Plan**: Observe behavior on UNFIXED code first for sessions that fall within the correct local-time window, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Legitimate Session Confirmation Preservation**: Create sessions that genuinely ended 55-65 min ago in local time. Verify they are still matched after the fix.
2. **Regular Message Routing Preservation**: Verify non-confirmation messages continue to be routed to the AI agent normally.
3. **No-Pending Confirmation Preservation**: Verify "Sim"/"Não" without a pending session continues to return `False` and route to AI agent.
4. **Confirmation Status Update Preservation**: Verify `confirmation_status` updates to `completed`/`missed` continue to work correctly.

### Unit Tests

- Test time window calculation with mocked `datetime.utcnow()` at various UTC offsets
- Test that sessions in the future (local time) are never matched
- Test that sessions genuinely ended 1 hour ago (local time) are matched
- Test `find_pending_confirmation_session_for_trainer()` returns most recent pending session
- Test edge cases: sessions ending exactly at window boundaries, midnight crossings

### Property-Based Tests

- Generate random `(utc_time, session_datetime, duration)` tuples and verify that only sessions whose local-time end falls in the 55-65 min window are matched
- Generate random confirmation keyword messages with/without pending sessions and verify correct routing
- Generate random session configurations and verify preservation of the per-trainer GSI query behavior

### Integration Tests

- Test full flow: session created at known local time → handler runs at correct local time → confirmation sent → trainer replies "Sim" → session updated
- Test that premature confirmations no longer occur across a range of UTC offsets
- Test midnight boundary: session at 23:30 local, handler runs at 00:35 local next day
