# Implementation Plan: Group Sessions

## Overview

Extend FitAgent to support multi-student group training sessions. Implementation adds a `GroupSession` Pydantic model, extends `TrainerConfig` with `group_size_limit`, creates 6 new tool functions for group session management, updates the `view_calendar` tool and `session_reminder.py` Lambda to handle group sessions. All changes reuse the existing DynamoDB single-table design, conflict detection, and calendar sync infrastructure.

## Tasks

- [x] 1. Extend data models for group sessions
  - [x] 1.1 Add `group_size_limit` field to `TrainerConfig` in `src/models/entities.py`
    - Add `group_size_limit: int = Field(default=10, ge=2, le=50)` to the `TrainerConfig` model
    - Update `to_dynamodb()` to include `group_size_limit`
    - Update `from_dynamodb()` to read `group_size_limit` with default of 10
    - _Requirements: 1.1, 9.5_

  - [x] 1.2 Create `GroupSession` Pydantic model in `src/models/entities.py`
    - Define `GroupSession(BaseModel)` with fields: `session_id`, `entity_type="SESSION"`, `trainer_id`, `session_type="group"`, `session_datetime`, `duration_minutes` (15–480), `location`, `status`, `max_participants` (2–50), `enrolled_students` (list of dicts with `student_id` and `student_name`), `calendar_event_id`, `calendar_provider`, `created_at`, `updated_at`
    - Implement `to_dynamodb()` with `PK=TRAINER#{trainer_id}`, `SK=SESSION#{session_id}`, include `session_type`, `enrolled_students`, `max_participants`, and `trainer_id`/`session_datetime` for GSI
    - Implement `from_dynamodb()` class method
    - _Requirements: 2.3, 9.1, 9.2, 9.3, 9.4_

  - [ ]* 1.3 Write property test for `GroupSession` serialization round trip
    - **Property 3: GroupSession serialization round trip**
    - **Validates: Requirements 2.3, 9.1, 9.2, 9.3**
    - Place in `tests/property/test_group_session_properties.py`
    - Use Hypothesis to generate random `GroupSession` instances and verify `from_dynamodb(to_dynamodb(gs))` produces equivalent objects

  - [ ]* 1.4 Write unit tests for `TrainerConfig.group_size_limit` and `GroupSession` model
    - Test default `group_size_limit` is 10
    - Test `GroupSession` validation rejects `max_participants` outside 2–50
    - Test `GroupSession` DynamoDB key pattern `PK=TRAINER#{trainer_id}`, `SK=SESSION#{session_id}`
    - Place in `tests/unit/test_group_session_models.py`
    - _Requirements: 1.1, 9.1, 9.2_

- [x] 2. Implement `configure_group_size_limit` tool
  - [x] 2.1 Create `configure_group_size_limit` tool function in `src/tools/group_session_tools.py`
    - Create new file `src/tools/group_session_tools.py` with imports matching existing `session_tools.py` pattern
    - Implement `configure_group_size_limit(trainer_id, limit)` decorated with `@tool`
    - Validate limit is in range [2, 50], return validation error otherwise
    - Read existing `TrainerConfig` or create new one, set `group_size_limit`, save to DynamoDB
    - Return `{'success': True, 'data': {'group_size_limit': limit}}`
    - _Requirements: 1.2, 1.3, 1.4_

  - [ ]* 2.2 Write property test for group size limit validation
    - **Property 1: Group size limit validation round trip**
    - **Validates: Requirements 1.2, 1.3, 1.4**
    - Use Hypothesis `integers()` strategy; verify success for [2, 50], error outside range
    - Place in `tests/property/test_group_session_properties.py`

- [x] 3. Implement `schedule_group_session` tool
  - [x] 3.1 Create `schedule_group_session` tool function in `src/tools/group_session_tools.py`
    - Implement `schedule_group_session(trainer_id, date, time, duration_minutes, location?, max_participants?)` with `@tool`
    - Default `max_participants` to trainer's `group_size_limit` from `TrainerConfig`
    - Reject if `max_participants` exceeds trainer's `group_size_limit`
    - Validate date/time, check not in past
    - Check conflicts via `SessionConflictDetector`
    - Create `GroupSession` entity, save to DynamoDB
    - Sync with calendar via `CalendarSyncService`
    - Return session data with conflicts if any
    - _Requirements: 2.1, 2.2, 2.4, 2.5_

  - [ ]* 3.2 Write property test for group session max_participants
    - **Property 2: Group session creation uses correct max_participants**
    - **Validates: Requirements 2.1, 2.2, 2.5**
    - Use Hypothesis to generate trainer configs and optional max_participants values
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 3.3 Write property test for conflict detection on group sessions
    - **Property 4: Conflict detection for group sessions**
    - **Validates: Requirements 2.4, 6.2**
    - Generate overlapping and non-overlapping session times, verify conflicts reported correctly
    - Place in `tests/property/test_group_session_properties.py`

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement `enroll_student` and `remove_student` tools
  - [x] 5.1 Create `enroll_student` tool function in `src/tools/group_session_tools.py`
    - Implement `enroll_student(trainer_id, session_id, student_names: list[str])` with `@tool`
    - For each student name: verify linked to trainer, not already enrolled, session not full
    - Add valid students to `enrolled_students` list, update `updated_at`, save to DynamoDB
    - Return per-student results (success/failure with reason)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 5.2 Create `remove_student` tool function in `src/tools/group_session_tools.py`
    - Implement `remove_student(trainer_id, session_id, student_name)` with `@tool`
    - Verify student is enrolled, remove from `enrolled_students`, update `updated_at`
    - Return error if student not enrolled
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 5.3 Write property test for enrollment constraints
    - **Property 5: Enrollment respects capacity and trainer linkage**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 5.4 Write property test for batch enrollment results
    - **Property 6: Batch enrollment returns per-student results**
    - **Validates: Requirements 3.5**
    - Verify result list has exactly one entry per requested student
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 5.5 Write property test for student removal
    - **Property 7: Student removal updates list and timestamp**
    - **Validates: Requirements 4.1, 4.3**
    - Place in `tests/property/test_group_session_properties.py`

- [x] 6. Implement `cancel_group_session` and `reschedule_group_session` tools
  - [x] 6.1 Create `cancel_group_session` tool function in `src/tools/group_session_tools.py`
    - Implement `cancel_group_session(trainer_id, session_id, reason?)` with `@tool`
    - Set status to "cancelled", return enrolled student names
    - Reject if already cancelled
    - Delete calendar event via `CalendarSyncService` if linked
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 6.2 Create `reschedule_group_session` tool function in `src/tools/group_session_tools.py`
    - Implement `reschedule_group_session(trainer_id, session_id, new_date, new_time)` with `@tool`
    - Update `session_datetime`, preserve `enrolled_students`
    - Reject if cancelled
    - Check conflicts at new time via `SessionConflictDetector`
    - Update calendar event via `CalendarSyncService` if linked
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 6.3 Write property test for cancellation
    - **Property 8: Cancellation sets status and returns enrolled names**
    - **Validates: Requirements 5.1, 5.2**
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 6.4 Write property test for reschedule preserving enrollment
    - **Property 9: Reschedule preserves enrolled students**
    - **Validates: Requirements 6.1**
    - Place in `tests/property/test_group_session_properties.py`

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Update `view_calendar` tool for group sessions
  - [x] 8.1 Extend `view_calendar` in `src/tools/session_tools.py` to include group session metadata
    - For sessions with `session_type="group"`, include `session_type`, `enrolled_student_count` (length of `enrolled_students`), and `max_participants` in the response
    - _Requirements: 7.1, 7.2_

  - [x] 8.2 Add student name filter support for group sessions in `view_calendar`
    - When a `student_name` filter is provided, include group sessions where that student appears in `enrolled_students`
    - _Requirements: 7.3_

  - [ ]* 8.3 Write property test for calendar view group metadata
    - **Property 10: Calendar view includes group session metadata**
    - **Validates: Requirements 7.1, 7.2**
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 8.4 Write property test for calendar student filter
    - **Property 11: Calendar student filter includes group sessions**
    - **Validates: Requirements 7.3**
    - Place in `tests/property/test_group_session_properties.py`

- [x] 9. Update session reminder Lambda for group sessions
  - [x] 9.1 Update `src/handlers/session_reminder.py` to handle group sessions
    - In `_get_sessions_needing_reminders`, include sessions with `session_type="group"`
    - In `_send_session_reminder`, when `session_type="group"`, iterate over `enrolled_students` and send individual WhatsApp reminders to each student
    - Record a separate `Reminder` entity per student
    - Include session date, time, duration, location, and trainer name in each message
    - Skip cancelled group sessions
    - Skip group sessions when trainer's `session_reminders_enabled` is false
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 9.2 Write property test for group session reminders
    - **Property 12: Group session reminders send per-student messages**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.6**
    - Verify exactly N reminders sent for N enrolled students
    - Place in `tests/property/test_group_session_properties.py`

  - [ ]* 9.3 Write property test for disabled reminders
    - **Property 13: Disabled reminders skip group sessions**
    - **Validates: Requirements 8.5**
    - Verify zero reminders when `session_reminders_enabled` is false
    - Place in `tests/property/test_group_session_properties.py`

- [x] 10. Wire group session tools into the AI agent
  - [x] 10.1 Register group session tools with the Strands agent
    - Import all 6 tool functions from `src/tools/group_session_tools.py` in the agent service
    - Add them to the agent's tool list alongside existing session tools
    - _Requirements: 1.2, 2.1, 3.1, 4.1, 5.1, 6.1_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- All property tests go in `tests/property/test_group_session_properties.py` with `@settings(max_examples=100)`
- Checkpoints ensure incremental validation
- No new DynamoDB tables, GSIs, or Lambda functions are needed
