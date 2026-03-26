# Requirements Document

## Introduction

FitAgent currently sends WhatsApp notifications to students using freeform messages via the Twilio `body` parameter. This approach fails with Twilio error 63016 when messages are sent outside the WhatsApp 24-hour customer service window. After April 1, 2025, WhatsApp requires all business-initiated template messages to be sent using Twilio Content SID and Content Variables instead of the `body` parameter.

This feature adds support for sending pre-approved WhatsApp template messages using Twilio's Content API, enabling reliable delivery of business-initiated notifications (session reminders, payment reminders, broadcast messages) regardless of the customer service window state.

## Glossary

- **TwilioClient**: The service wrapper (`src/services/twilio_client.py`) responsible for sending WhatsApp messages via the Twilio API.
- **NotificationSender**: The Lambda handler (`src/handlers/notification_sender.py`) that processes SQS notification messages and dispatches them via TwilioClient.
- **NotificationTool**: The AI agent tool function (`src/tools/notification_tools.py`) that queues broadcast notifications to students via SQS.
- **Content_SID**: A unique Twilio identifier (e.g., `HXb5b62575e6e4ff6129ad7c8efe1f983e`) referencing a pre-approved WhatsApp message template.
- **Content_Variables**: A JSON string mapping placeholder indices to values (e.g., `'{"1":"value1","2":"value2"}'`) used to fill template placeholders.
- **Customer_Service_Window**: A 24-hour period after the last inbound WhatsApp message from a user, during which freeform messages are permitted.
- **Template_Message**: A pre-approved WhatsApp message structure with placeholders, required for business-initiated messages outside the Customer_Service_Window.
- **Freeform_Message**: A WhatsApp message sent using the `body` parameter, permitted only within the Customer_Service_Window.
- **Template_Registry**: A configuration mapping that associates notification types with their corresponding Content_SID and placeholder definitions.
- **SQS_Notification_Queue**: The SQS queue used to buffer and rate-limit outbound notification messages before delivery.

## Requirements

### Requirement 1: Send Template Messages via Content API

**User Story:** As a trainer, I want my notifications to reach students reliably, so that business-initiated messages are delivered even outside the 24-hour customer service window.

#### Acceptance Criteria

1. WHEN a template message request is received with a valid Content_SID and Content_Variables, THE TwilioClient SHALL send the message using the Twilio `content_sid` and `content_variables` parameters instead of the `body` parameter.
2. WHEN a template message request is received without a Content_SID, THE TwilioClient SHALL send the message using the `body` parameter as a Freeform_Message.
3. THE TwilioClient SHALL return the message SID, delivery status, and any error information for both template and freeform messages.
4. WHEN the Twilio API returns an error for a template message, THE TwilioClient SHALL include the error code and error message in the returned result.

### Requirement 2: Template Registry Configuration

**User Story:** As a system administrator, I want a centralized mapping of notification types to WhatsApp templates, so that templates can be managed and updated without code changes.

#### Acceptance Criteria

1. THE Template_Registry SHALL store a mapping of notification type identifiers to Content_SID values and placeholder definitions.
2. WHEN a notification type is looked up in the Template_Registry, THE Template_Registry SHALL return the associated Content_SID and a list of required placeholder variable names.
3. IF a notification type is not found in the Template_Registry, THEN THE Template_Registry SHALL return an indication that no template is configured for that type.
4. THE Template_Registry SHALL support the following notification types: `session_reminder`, `payment_reminder`, and `broadcast`.

### Requirement 3: Template Variable Construction

**User Story:** As a developer, I want Content_Variables to be built automatically from notification context data, so that template placeholders are filled correctly without manual formatting.

#### Acceptance Criteria

1. WHEN a notification is prepared for sending, THE NotificationSender SHALL construct the Content_Variables JSON string by mapping notification context data to the placeholder definitions from the Template_Registry.
2. THE NotificationSender SHALL format Content_Variables as a JSON string with string keys representing placeholder indices (e.g., `'{"1":"value1","2":"value2"}'`).
3. IF a required placeholder variable is missing from the notification context, THEN THE NotificationSender SHALL log a warning and fall back to sending a Freeform_Message using the `body` parameter.
4. FOR ALL valid notification context data, constructing Content_Variables then serializing to JSON then deserializing SHALL produce an equivalent mapping (round-trip property).

### Requirement 4: Notification Queue Message Format Update

**User Story:** As a developer, I want the SQS notification message format to carry template information, so that the NotificationSender can determine whether to send a template or freeform message.

#### Acceptance Criteria

1. WHEN a notification is queued with a known notification type, THE NotificationTool SHALL include the `notification_type`, `content_sid`, and `template_variables` fields in the SQS message body alongside the existing `message` field.
2. WHEN a notification is queued without a known notification type, THE NotificationTool SHALL include only the `message` field in the SQS message body for freeform delivery.
3. THE NotificationTool SHALL preserve backward compatibility by continuing to include the `message` field in all SQS messages.
4. THE SQS_Notification_Queue message format SHALL maintain the existing `notification_id`, `trainer_id`, `recipient`, `message`, and `attempt` fields.

### Requirement 5: NotificationSender Template Dispatch

**User Story:** As a trainer, I want the notification system to automatically choose the correct sending method, so that messages are delivered using templates when available and freeform otherwise.

#### Acceptance Criteria

1. WHEN the NotificationSender processes an SQS message containing a `content_sid` field, THE NotificationSender SHALL send the message via TwilioClient using the template message method with Content_SID and Content_Variables.
2. WHEN the NotificationSender processes an SQS message without a `content_sid` field, THE NotificationSender SHALL send the message via TwilioClient using the freeform message method with the `body` parameter.
3. THE NotificationSender SHALL update the DynamoDB notification delivery status with the sending method used (`template` or `freeform`).
4. WHEN a template message fails with a Twilio error, THE NotificationSender SHALL follow the existing retry logic of 2 retries with 5-minute delays.

### Requirement 6: Session Reminder Template Support

**User Story:** As a trainer, I want session reminders to use WhatsApp templates, so that reminder messages reach students even if they haven't messaged recently.

#### Acceptance Criteria

1. WHEN a session reminder is triggered, THE session reminder handler SHALL look up the `session_reminder` template in the Template_Registry and include the Content_SID and template variables in the notification.
2. THE session reminder template variables SHALL include the student name, session date, and session time as placeholder values.
3. IF the `session_reminder` template is not configured in the Template_Registry, THEN THE session reminder handler SHALL fall back to sending the reminder as a Freeform_Message.

### Requirement 7: Payment Reminder Template Support

**User Story:** As a trainer, I want payment reminders to use WhatsApp templates, so that payment notifications reach students reliably.

#### Acceptance Criteria

1. WHEN a payment reminder is triggered, THE payment reminder handler SHALL look up the `payment_reminder` template in the Template_Registry and include the Content_SID and template variables in the notification.
2. THE payment reminder template variables SHALL include the student name, amount due, and due date as placeholder values.
3. IF the `payment_reminder` template is not configured in the Template_Registry, THEN THE payment reminder handler SHALL fall back to sending the reminder as a Freeform_Message.

### Requirement 8: Broadcast Notification Template Support

**User Story:** As a trainer, I want to send broadcast notifications using templates when appropriate, so that bulk messages to students are delivered reliably.

#### Acceptance Criteria

1. WHEN the NotificationTool sends a broadcast notification and a `broadcast` template is configured in the Template_Registry, THE NotificationTool SHALL include the Content_SID and template variables in each queued SQS message.
2. THE broadcast template variables SHALL include the trainer name and the message content as placeholder values.
3. WHEN the NotificationTool sends a broadcast notification and no `broadcast` template is configured, THE NotificationTool SHALL queue messages for freeform delivery using the `body` parameter.
4. THE NotificationTool SHALL continue to support the existing rate limiting of 10 messages per second via SQS message delays.

### Requirement 9: Error Handling for Template Failures

**User Story:** As a developer, I want clear error handling when template messages fail, so that issues can be diagnosed and resolved quickly.

#### Acceptance Criteria

1. IF the Twilio API returns error code 63016 for a freeform message, THEN THE TwilioClient SHALL log the error with a recommendation to use a template message.
2. IF the Twilio API returns an error indicating an invalid Content_SID, THEN THE TwilioClient SHALL log the error with the Content_SID value for debugging.
3. IF the Twilio API returns an error indicating invalid Content_Variables, THEN THE TwilioClient SHALL log the error with the provided variables for debugging.
4. THE NotificationSender SHALL record the error code and error message in the DynamoDB notification status when a message fails.

### Requirement 10: Template Registry Environment Configuration

**User Story:** As a system administrator, I want template Content SIDs to be configurable per environment, so that development, staging, and production can use different approved templates.

#### Acceptance Criteria

1. THE Template_Registry SHALL load Content_SID mappings from environment configuration or DynamoDB settings.
2. WHEN the application starts, THE Template_Registry SHALL validate that all configured Content_SID values follow the Twilio Content SID format (starting with `HX` followed by 32 hexadecimal characters).
3. IF a configured Content_SID value is invalid, THEN THE Template_Registry SHALL log a warning and exclude that notification type from template delivery.
