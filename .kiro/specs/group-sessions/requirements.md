# Requirements Document

## Introduction

Group Sessions extends FitAgent to allow trainers to schedule training sessions with multiple students simultaneously. Each trainer has a configurable maximum group size. Students enrolled in group sessions receive WhatsApp reminders on the day of the session. This feature builds on the existing 1:1 session scheduling, DynamoDB single-table design, and EventBridge-based reminder infrastructure.

## Glossary

- **Trainer**: A personal trainer who manages students and sessions through the FitAgent WhatsApp interface
- **Student**: A client linked to one or more trainers who participates in training sessions
- **Group_Session**: A training session entity with multiple enrolled students, a maximum capacity, and a session type of "group"
- **Group_Size_Limit**: The maximum number of students a trainer allows in a single group session, stored in the Trainer_Config entity
- **Trainer_Config**: A per-trainer configuration record in DynamoDB that stores preferences including reminder settings and group size limits
- **Reminder_Service**: The EventBridge-triggered Lambda function that sends WhatsApp reminders to students for upcoming sessions
- **Session_Tool**: The AI agent tool function that trainers invoke via WhatsApp to create, modify, and cancel sessions
- **Enrollment**: The association between a Student and a Group_Session, tracking participation status

## Requirements

### Requirement 1: Configure Group Size Limit

**User Story:** As a trainer, I want to set a maximum number of students for my group sessions, so that I can control class sizes according to my capacity.

#### Acceptance Criteria

1. THE Trainer_Config SHALL store a group_size_limit field with a default value of 10 students
2. WHEN a trainer requests to change the group size limit via WhatsApp, THE Session_Tool SHALL update the group_size_limit in the Trainer_Config entity
3. WHEN a trainer sets a group size limit, THE Session_Tool SHALL accept values between 2 and 50 inclusive
4. IF a trainer provides a group size limit outside the range of 2 to 50, THEN THE Session_Tool SHALL return a validation error message describing the allowed range

### Requirement 2: Schedule a Group Session

**User Story:** As a trainer, I want to schedule a group training session with a date, time, duration, and optional location, so that I can organize classes for multiple students.

#### Acceptance Criteria

1. WHEN a trainer requests to schedule a group session, THE Session_Tool SHALL create a Group_Session entity with session_type set to "group" and max_participants set to the trainer's configured group_size_limit
2. WHEN a trainer specifies a custom max_participants value during scheduling, THE Session_Tool SHALL use that value instead of the default group_size_limit
3. THE Group_Session entity SHALL store trainer_id, session_datetime, duration_minutes, location, status, session_type, max_participants, and a list of enrolled student identifiers
4. WHEN a group session is created, THE Session_Tool SHALL check for scheduling conflicts with existing sessions for the same trainer using the Session_Conflict_Detector
5. IF the specified max_participants exceeds the trainer's configured group_size_limit, THEN THE Session_Tool SHALL return a validation error indicating the maximum allowed capacity

### Requirement 3: Enroll Students in a Group Session

**User Story:** As a trainer, I want to add students to a group session, so that I can manage who attends each class.

#### Acceptance Criteria

1. WHEN a trainer requests to add a student to a group session, THE Session_Tool SHALL add the student identifier to the Group_Session enrolled students list
2. IF the number of enrolled students equals the max_participants of the Group_Session, THEN THE Session_Tool SHALL reject the enrollment and return a message indicating the session is full
3. WHEN a student is enrolled, THE Session_Tool SHALL verify the student is linked to the trainer before adding the student to the Group_Session
4. IF the student is already enrolled in the Group_Session, THEN THE Session_Tool SHALL return a message indicating the student is already enrolled
5. WHEN a trainer requests to add multiple students in a single message, THE Session_Tool SHALL enroll each valid student and report the result for each student individually

### Requirement 4: Remove Students from a Group Session

**User Story:** As a trainer, I want to remove students from a group session, so that I can manage attendance changes.

#### Acceptance Criteria

1. WHEN a trainer requests to remove a student from a group session, THE Session_Tool SHALL remove the student identifier from the Group_Session enrolled students list
2. IF the student is not enrolled in the specified Group_Session, THEN THE Session_Tool SHALL return a message indicating the student is not enrolled in that session
3. WHEN a student is removed, THE Session_Tool SHALL update the Group_Session updated_at timestamp

### Requirement 5: Cancel a Group Session

**User Story:** As a trainer, I want to cancel a group session, so that I can notify all enrolled students when plans change.

#### Acceptance Criteria

1. WHEN a trainer requests to cancel a group session, THE Session_Tool SHALL set the Group_Session status to "cancelled"
2. WHEN a group session is cancelled, THE Session_Tool SHALL return the list of enrolled student names so the trainer is aware of who was affected
3. IF the Group_Session is already cancelled, THEN THE Session_Tool SHALL return a message indicating the session is already cancelled
4. WHEN a group session has a linked calendar event, THE Session_Tool SHALL delete the calendar event via the Calendar_Sync_Service

### Requirement 6: Reschedule a Group Session

**User Story:** As a trainer, I want to reschedule a group session to a new date and time, so that I can adjust plans without recreating the session and re-enrolling students.

#### Acceptance Criteria

1. WHEN a trainer requests to reschedule a group session, THE Session_Tool SHALL update the session_datetime of the Group_Session and preserve the enrolled students list
2. WHEN a group session is rescheduled, THE Session_Tool SHALL check for scheduling conflicts at the new date and time
3. IF the Group_Session status is "cancelled", THEN THE Session_Tool SHALL reject the reschedule and return a message indicating cancelled sessions cannot be rescheduled
4. WHEN a group session has a linked calendar event, THE Session_Tool SHALL update the calendar event via the Calendar_Sync_Service

### Requirement 7: View Group Sessions in Calendar

**User Story:** As a trainer, I want to see group sessions in my calendar view alongside individual sessions, so that I have a complete picture of my schedule.

#### Acceptance Criteria

1. WHEN a trainer views the calendar, THE Session_Tool SHALL include Group_Session entities in the results alongside individual sessions
2. THE Session_Tool SHALL display the session_type, enrolled student count, and max_participants for each Group_Session in the calendar response
3. WHEN a trainer filters the calendar by a specific student name, THE Session_Tool SHALL include Group_Sessions where that student is enrolled

### Requirement 8: Day-of Session Reminders for Group Sessions

**User Story:** As a student, I want to receive a WhatsApp reminder on the day of my group session, so that I do not forget to attend.

#### Acceptance Criteria

1. WHEN the current date matches the date of a scheduled Group_Session, THE Reminder_Service SHALL send a WhatsApp reminder to each enrolled student
2. THE Reminder_Service SHALL include the session date, time, duration, location, and trainer name in each reminder message
3. THE Reminder_Service SHALL send individual reminder messages to each enrolled student rather than a single group message
4. IF a Group_Session status is "cancelled", THEN THE Reminder_Service SHALL skip sending reminders for that session
5. WHILE the trainer's session_reminders_enabled configuration is set to false, THE Reminder_Service SHALL skip sending reminders for that trainer's Group_Sessions
6. THE Reminder_Service SHALL record a Reminder entity for each student reminder sent, tracking delivery status per recipient

### Requirement 9: Group Session Data Storage

**User Story:** As a system operator, I want group session data stored following the existing single-table DynamoDB design, so that the data model remains consistent and queryable.

#### Acceptance Criteria

1. THE Group_Session entity SHALL use the DynamoDB key pattern PK=TRAINER#{trainer_id} and SK=SESSION#{session_id}, consistent with existing Session entities
2. THE Group_Session entity SHALL include a session_type attribute set to "group" to distinguish group sessions from individual sessions
3. THE Group_Session entity SHALL store enrolled students as a list of objects containing student_id and student_name
4. THE Group_Session entity SHALL be queryable via the existing session-date-index GSI using trainer_id and session_datetime
5. THE Trainer_Config entity SHALL include the group_size_limit attribute with a default value of 10
