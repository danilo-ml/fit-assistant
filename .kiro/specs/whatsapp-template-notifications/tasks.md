# Implementation Plan: WhatsApp Template Notifications

## Overview

Extend FitAgent's WhatsApp messaging to support Twilio Content API template messages. Implementation proceeds bottom-up: configuration → registry → client → queue format → dispatch → handler integration → tests.

## Tasks

- [x] 1. Add template environment configuration to Pydantic Settings
  - [x] 1.1 Add template fields to Settings class in `src/config.py`
    - Add optional fields: `template_session_reminder_sid`, `template_session_reminder_vars`, `template_payment_reminder_sid`, `template_payment_reminder_vars`, `template_broadcast_sid`, `template_broadcast_vars`
    - All fields are `Optional[str]` defaulting to `None`
    - _Requirements: 10.1_

- [x] 2. Implement TemplateRegistry service
  - [x] 2.1 Create `src/services/template_registry.py` with `TemplateConfig` dataclass and `TemplateRegistry` class
    - Define `TemplateConfig` dataclass with `content_sid: str` and `variables: List[str]`
    - Implement `__init__` loading from environment config via Settings
    - Implement `get_template(notification_type)` returning `Optional[TemplateConfig]`
    - Implement `is_configured(notification_type)` returning `bool`
    - Implement `validate_content_sid(content_sid)` static method with regex `^HX[0-9a-fA-F]{32}$`
    - Define `VALID_NOTIFICATION_TYPES = {"session_reminder", "payment_reminder", "broadcast"}`
    - Log warning and exclude invalid Content SIDs on initialization
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 10.1, 10.2, 10.3_

  - [x] 2.2 Implement `build_content_variables()` utility function in `src/services/template_registry.py`
    - Accept `TemplateConfig` and `context: Dict[str, str]`
    - Map ordered variable names to 1-indexed string keys: `{"1": value1, "2": value2, ...}`
    - Return JSON string, or `None` if any required variable is missing from context
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 2.3 Write property test: Content SID format validation
    - **Property 4: Content SID format validation**
    - **Validates: Requirements 10.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 2.4 Write property test: Content Variables construction
    - **Property 5: Content Variables construction**
    - **Validates: Requirements 3.1, 3.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 2.5 Write property test: Missing variables produce fallback
    - **Property 6: Missing variables produce fallback**
    - **Validates: Requirements 3.3**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 2.6 Write property test: Content Variables serialization round-trip
    - **Property 7: Content Variables serialization round-trip**
    - **Validates: Requirements 3.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 2.7 Write property test: Template Registry configuration round-trip
    - **Property 3: Template Registry configuration round-trip**
    - **Validates: Requirements 2.1, 2.2, 10.1**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 2.8 Write unit tests for TemplateRegistry and build_content_variables
    - Test registry initialization from config dict and environment variables
    - Test `get_template` for valid, missing, and invalid notification types
    - Test `is_configured` returns correct booleans
    - Test `validate_content_sid` with valid and invalid SID strings
    - Test `build_content_variables` with complete, partial, and empty contexts
    - File: `tests/unit/test_template_registry.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 10.2, 10.3_

- [x] 3. Extend TwilioClient with template message support
  - [x] 3.1 Add `send_template_message()` method to `TwilioClient` in `src/services/twilio_client.py`
    - Accept `to: str`, `content_sid: str`, `content_variables: str`
    - Call Twilio API with `content_sid` and `content_variables` params (no `body`)
    - Return dict with `message_sid`, `status`, `error_code`, `error_message`
    - Handle error 63016 on freeform messages with log recommendation
    - Log invalid Content SID and invalid Content Variables errors with details
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 9.1, 9.2, 9.3_

  - [ ]* 3.2 Write property test: TwilioClient dispatch method selection
    - **Property 1: TwilioClient dispatch method selection**
    - **Validates: Requirements 1.1, 1.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 3.3 Write property test: TwilioClient return structure completeness
    - **Property 2: TwilioClient return structure completeness**
    - **Validates: Requirements 1.3, 1.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 3.4 Write unit tests for `send_template_message()`
    - Test successful template message send with mocked Twilio SDK
    - Test error code 63016 handling and logging
    - Test invalid Content SID error handling
    - Test invalid Content Variables error handling
    - Test return dict always contains required keys
    - File: `tests/unit/test_twilio_client_template.py`
    - _Requirements: 1.1, 1.3, 1.4, 9.1, 9.2, 9.3_

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Update SQS message format and broadcast notification queuing
  - [x] 5.1 Update `_queue_notification_messages()` in `src/tools/notification_tools.py`
    - Import `TemplateRegistry` and look up `broadcast` template
    - When template is configured, add `notification_type`, `content_sid`, and `template_variables` to SQS message body
    - `template_variables` should include `trainer_name` and `message_content` keys
    - Preserve existing `message` field for backward compatibility and fallback
    - Preserve existing rate limiting logic (`DelaySeconds = min(i // 10, 900)`)
    - When no template configured, queue freeform message as before
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 5.2 Write property test: SQS message format invariants
    - **Property 8: SQS message format invariants**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 5.3 Write property test: Rate limiting preservation
    - **Property 15: Rate limiting preservation**
    - **Validates: Requirements 8.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 5.4 Write unit tests for broadcast template integration
    - Test SQS message body includes template fields when broadcast template configured
    - Test SQS message body omits template fields when no template configured
    - Test backward compatibility (message field always present)
    - Test rate limiting delays unchanged
    - File: `tests/unit/test_notification_tools_template.py`
    - _Requirements: 4.1, 4.2, 4.3, 8.1, 8.2, 8.3, 8.4_

- [x] 6. Update NotificationSender dispatch logic
  - [x] 6.1 Update `_send_notification_message()` in `src/handlers/notification_sender.py`
    - Accept optional `content_sid` and `template_variables` parameters
    - When `content_sid` is present, use `build_content_variables()` to construct JSON and call `send_template_message()`
    - When variables are missing or incomplete, log warning and fall back to freeform `send_message()`
    - Return `sending_method` ("template" or "freeform") in result dict
    - _Requirements: 5.1, 5.2, 3.3_

  - [x] 6.2 Update `lambda_handler()` in `src/handlers/notification_sender.py` to extract template fields from SQS message
    - Parse `content_sid`, `template_variables`, and `notification_type` from message body
    - Pass template fields to `_send_notification_message()`
    - _Requirements: 5.1, 5.2_

  - [x] 6.3 Update `_update_notification_status()` to record `sending_method` in DynamoDB
    - Add `sending_method` field to recipient status updates
    - Record error code and error message on failure
    - _Requirements: 5.3, 5.4, 9.4_

  - [ ]* 6.4 Write property test: NotificationSender dispatch consistency
    - **Property 9: NotificationSender dispatch consistency**
    - **Validates: Requirements 5.1, 5.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 6.5 Write property test: Sending method recorded in delivery status
    - **Property 10: Sending method recorded in delivery status**
    - **Validates: Requirements 5.3**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 6.6 Write property test: Template message retry parity
    - **Property 11: Template message retry parity**
    - **Validates: Requirements 5.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 6.7 Write property test: Error details recorded on failure
    - **Property 16: Error details recorded on failure**
    - **Validates: Requirements 9.4**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 6.8 Write unit tests for NotificationSender template dispatch
    - Test dispatch via `send_template_message()` when `content_sid` present
    - Test fallback to `send_message()` when `content_sid` absent
    - Test fallback on missing template variables
    - Test `sending_method` recorded in DynamoDB status
    - Test retry behavior for template message failures
    - Test error details recorded on final failure
    - File: `tests/unit/test_notification_sender_template.py`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 9.4_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Integrate template support into session reminder handler
  - [x] 8.1 Update `src/handlers/session_reminder.py` to use TemplateRegistry
    - Import `TemplateRegistry` and look up `session_reminder` template
    - When template configured, include `content_sid` and `template_variables` with keys `student_name`, `session_date`, `session_time`
    - When no template configured, send freeform message as before
    - Apply to both `_send_individual_session_reminder()` and `_send_group_session_reminders()`
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 8.2 Write property test: Session reminder template variables
    - **Property 12: Session reminder template variables**
    - **Validates: Requirements 6.1, 6.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 8.3 Write unit tests for session reminder template integration
    - Test template lookup and variable construction
    - Test fallback to freeform when template not configured
    - Test group session reminders include template data per student
    - File: `tests/unit/test_session_reminder_template.py`
    - _Requirements: 6.1, 6.2, 6.3_

- [x] 9. Integrate template support into payment reminder handler
  - [x] 9.1 Update `src/handlers/payment_reminder.py` to use TemplateRegistry
    - Import `TemplateRegistry` and look up `payment_reminder` template
    - When template configured, include `content_sid` and `template_variables` with keys `student_name`, `amount_due`, `due_date`
    - When no template configured, send freeform message as before
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ]* 9.2 Write property test: Payment reminder template variables
    - **Property 13: Payment reminder template variables**
    - **Validates: Requirements 7.1, 7.2**
    - File: `tests/property/test_template_notification_properties.py`

  - [ ]* 9.3 Write unit tests for payment reminder template integration
    - Test template lookup and variable construction
    - Test fallback to freeform when template not configured
    - File: `tests/unit/test_payment_reminder_template.py`
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 10. Integrate template support into broadcast notification
  - [ ]* 10.1 Write property test: Broadcast notification template variables
    - **Property 14: Broadcast notification template variables**
    - **Validates: Requirements 8.1, 8.2**
    - File: `tests/property/test_template_notification_properties.py`

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use Hypothesis with `@settings(max_examples=100)` and tag format: `# Feature: whatsapp-template-notifications, Property {N}: {title}`
- All property tests go in `tests/property/test_template_notification_properties.py`
- Unit tests go in `tests/unit/` with one file per component
- Checkpoints ensure incremental validation
