# Design Document: WhatsApp Template Notifications

## Overview

This feature extends FitAgent's WhatsApp messaging infrastructure to support Twilio Content API template messages alongside existing freeform messages. After April 1, 2025, WhatsApp requires business-initiated messages outside the 24-hour customer service window to use pre-approved templates via `content_sid` and `content_variables` parameters instead of the `body` parameter.

The design introduces a Template Registry for centralized template management, extends `TwilioClient.send_message()` to support template parameters, updates the SQS message format to carry template metadata, and modifies all notification handlers (session reminders, payment reminders, broadcast notifications) to resolve and include template information when available, with graceful fallback to freeform messages.

## Architecture

```mermaid
flowchart TD
    subgraph Handlers
        SR[session_reminder.py]
        PR[payment_reminder.py]
        NT[notification_tools.py]
    end

    subgraph Registry
        TR[TemplateRegistry]
        ENV[Environment Config / DynamoDB]
    end

    subgraph Queue
        SQS[SQS Notification Queue]
    end

    subgraph Sender
        NS[notification_sender.py]
        VB[Variable Builder]
    end

    subgraph Twilio
        TC[TwilioClient]
        TAPI[Twilio Content API]
    end

    SR -->|lookup template| TR
    PR -->|lookup template| TR
    NT -->|lookup template| TR
    TR -->|load config| ENV

    SR -->|queue with content_sid + vars| SQS
    PR -->|queue with content_sid + vars| SQS
    NT -->|queue with content_sid + vars| SQS

    SQS --> NS
    NS -->|build content_variables| VB
    NS -->|send_template_message or send_message| TC
    TC -->|content_sid + content_variables| TAPI
    TC -->|body (fallback)| TAPI
    NS -->|update status| DDB[(DynamoDB)]
```

The key design decision is to resolve templates at the point of queuing (handlers/tools) rather than at the point of sending (NotificationSender). This means the SQS message carries the `content_sid` and raw template variable data, and the NotificationSender constructs the final `content_variables` JSON string and dispatches via the appropriate TwilioClient method. This keeps the NotificationSender as a thin dispatcher while handlers own the business context needed to select templates.

Fallback to freeform is supported at two levels:
1. At queue time: if no template is configured for a notification type, the handler queues a freeform message (no `content_sid`).
2. At send time: if required template variables are missing, the NotificationSender falls back to freeform using the `message` body field.

## Components and Interfaces

### 1. TemplateRegistry (`src/services/template_registry.py`)

Centralized configuration mapping notification types to Twilio Content SIDs and placeholder definitions.

```python
from typing import Optional, Dict, List
from dataclasses import dataclass


@dataclass
class TemplateConfig:
    """Configuration for a single notification template."""
    content_sid: str                    # e.g. "HXb5b62575e6e4ff6129ad7c8efe1f983e"
    variables: List[str]               # ordered placeholder names, e.g. ["student_name", "session_date", "session_time"]


class TemplateRegistry:
    """
    Manages mapping of notification types to Twilio Content API templates.
    
    Loads configuration from environment variables or DynamoDB settings.
    Validates Content SID format on initialization.
    """

    VALID_NOTIFICATION_TYPES = {"session_reminder", "payment_reminder", "broadcast"}
    CONTENT_SID_PATTERN = r"^HX[0-9a-fA-F]{32}$"

    def __init__(self, config: Optional[Dict[str, Dict]] = None):
        """
        Initialize registry from config dict or environment/DynamoDB.
        
        Args:
            config: Optional dict mapping notification_type -> {"content_sid": str, "variables": list[str]}
        """
        ...

    def get_template(self, notification_type: str) -> Optional[TemplateConfig]:
        """
        Look up template for a notification type.
        
        Args:
            notification_type: One of "session_reminder", "payment_reminder", "broadcast"
            
        Returns:
            TemplateConfig if configured and valid, None otherwise.
        """
        ...

    def is_configured(self, notification_type: str) -> bool:
        """Check if a notification type has a valid template configured."""
        ...

    @staticmethod
    def validate_content_sid(content_sid: str) -> bool:
        """Validate Content SID matches Twilio format: HX + 32 hex chars."""
        ...
```

### 2. TwilioClient Extension (`src/services/twilio_client.py`)

Add a `send_template_message()` method alongside the existing `send_message()`.

```python
def send_template_message(
    self,
    to: str,
    content_sid: str,
    content_variables: str,
) -> dict:
    """
    Send a WhatsApp template message using Twilio Content API.
    
    Args:
        to: Recipient phone number in E.164 format
        content_sid: Twilio Content SID (HX...)
        content_variables: JSON string of placeholder values, e.g. '{"1":"John","2":"Monday"}'
    
    Returns:
        dict with message_sid, status, error_code, error_message
    """
    ...
```

The existing `send_message(to, body, media_url)` remains unchanged for freeform messages.

### 3. Content Variable Builder (`src/services/template_registry.py`)

A utility function to construct the `content_variables` JSON string from notification context data and a `TemplateConfig`.

```python
def build_content_variables(
    template_config: TemplateConfig,
    context: Dict[str, str],
) -> Optional[str]:
    """
    Build content_variables JSON string from context data.
    
    Maps template_config.variables (ordered placeholder names) to 
    1-indexed string keys: {"1": context[var1], "2": context[var2], ...}
    
    Args:
        template_config: Template configuration with ordered variable names
        context: Dict mapping variable names to string values
        
    Returns:
        JSON string like '{"1":"value1","2":"value2"}', or None if any required variable is missing.
    """
    ...
```

### 4. SQS Message Format Update

The existing SQS message body gains three optional fields:

```json
{
    "notification_id": "uuid",
    "trainer_id": "uuid",
    "recipient": {"student_id": "...", "student_name": "...", "phone_number": "..."},
    "message": "Freeform body text (always present for backward compat)",
    "attempt": 0,
    "notification_type": "session_reminder",
    "content_sid": "HXb5b62575e6e4ff6129ad7c8efe1f983e",
    "template_variables": {"student_name": "John", "session_date": "Monday", "session_time": "10:00 AM"}
}
```

- `notification_type`, `content_sid`, `template_variables` are optional. When absent, the NotificationSender sends a freeform message using `message`.
- `message` is always present for backward compatibility and fallback.

### 5. NotificationSender Dispatch Logic (`src/handlers/notification_sender.py`)

Updated `_send_notification_message()` to check for `content_sid` in the SQS message body:

```python
def _send_notification_message(trainer_id, recipient, message, content_sid=None, template_variables=None):
    if content_sid and template_variables:
        # Build content_variables JSON string
        template_config = template_registry.get_template(notification_type)
        variables_json = build_content_variables(template_config, template_variables)
        if variables_json:
            result = twilio_client.send_template_message(to=phone, content_sid=content_sid, content_variables=variables_json)
            return {**result, "sending_method": "template"}
        else:
            logger.warning("Missing template variables, falling back to freeform")
    
    # Fallback to freeform
    result = twilio_client.send_message(to=phone, body=message)
    return {**result, "sending_method": "freeform"}
```

### 6. Handler Updates

Each handler is updated to look up the template registry and include template data when queuing:

- **session_reminder.py**: Looks up `session_reminder` template, provides `student_name`, `session_date`, `session_time`.
- **payment_reminder.py**: Looks up `payment_reminder` template, provides `student_name`, `amount_due`, `due_date`.
- **notification_tools.py**: Looks up `broadcast` template, provides `trainer_name`, `message_content`.

All handlers fall back to freeform if no template is configured.

## Data Models

### TemplateConfig

| Field | Type | Description |
|-------|------|-------------|
| `content_sid` | `str` | Twilio Content SID (`HX` + 32 hex chars) |
| `variables` | `List[str]` | Ordered list of placeholder variable names |

### Template Registry Storage (Environment Config)

Template configuration is stored as environment variables with a structured naming convention:

```
TEMPLATE_SESSION_REMINDER_SID=HXabc123...
TEMPLATE_SESSION_REMINDER_VARS=student_name,session_date,session_time

TEMPLATE_PAYMENT_REMINDER_SID=HXdef456...
TEMPLATE_PAYMENT_REMINDER_VARS=student_name,amount_due,due_date

TEMPLATE_BROADCAST_SID=HXghi789...
TEMPLATE_BROADCAST_VARS=trainer_name,message_content
```

Alternatively, templates can be stored in DynamoDB under the trainer config or a global config item:

| PK | SK | Fields |
|----|-----|--------|
| `CONFIG#GLOBAL` | `TEMPLATES` | `templates: { "session_reminder": { "content_sid": "HX...", "variables": [...] }, ... }` |

The registry loads from environment variables first, then falls back to DynamoDB. This allows per-environment overrides (dev/staging/prod use different approved templates).

### DynamoDB Notification Record Update

The existing notification recipient status gains a `sending_method` field:

```json
{
    "student_id": "uuid",
    "phone_number": "+1234567890",
    "status": "sent",
    "sending_method": "template",
    "sent_at": "2025-01-15T10:00:00",
    "message_sid": "SM..."
}
```

### Pydantic Settings Extension (`src/config.py`)

New optional fields added to `Settings`:

```python
# Template Configuration
template_session_reminder_sid: Optional[str] = None
template_session_reminder_vars: Optional[str] = None  # comma-separated
template_payment_reminder_sid: Optional[str] = None
template_payment_reminder_vars: Optional[str] = None
template_broadcast_sid: Optional[str] = None
template_broadcast_vars: Optional[str] = None
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: TwilioClient dispatch method selection

*For any* message send request, the TwilioClient SHALL call the Twilio API with `content_sid` and `content_variables` parameters (and no `body`) if and only if a `content_sid` is provided; otherwise it SHALL call the Twilio API with the `body` parameter (and no `content_sid`).

**Validates: Requirements 1.1, 1.2**

### Property 2: TwilioClient return structure completeness

*For any* message sent via TwilioClient (template or freeform, success or failure), the returned dict SHALL contain the keys `message_sid`, `status`, `error_code`, and `error_message`.

**Validates: Requirements 1.3, 1.4**

### Property 3: Template Registry configuration round-trip

*For any* valid template configuration (notification type, Content SID, and variable list), storing it in the TemplateRegistry and then looking it up by notification type SHALL return a TemplateConfig with the same Content SID and the same ordered list of variable names.

**Validates: Requirements 2.1, 2.2, 10.1**

### Property 4: Content SID format validation

*For any* string, `TemplateRegistry.validate_content_sid()` SHALL return `True` if and only if the string matches the pattern `HX` followed by exactly 32 hexadecimal characters (case-insensitive).

**Validates: Requirements 10.2**

### Property 5: Content Variables construction

*For any* TemplateConfig with N ordered variable names and a context dict containing all N variable names as keys with non-empty string values, `build_content_variables()` SHALL return a valid JSON string with string keys `"1"` through `"N"` where key `"i"` maps to the context value for the i-th variable name.

**Validates: Requirements 3.1, 3.2**

### Property 6: Missing variables produce fallback

*For any* TemplateConfig with N variable names and a context dict that is missing at least one of those variable names, `build_content_variables()` SHALL return `None`.

**Validates: Requirements 3.3**

### Property 7: Content Variables serialization round-trip

*For any* valid notification context data (dict of string keys to string values), constructing Content Variables via `build_content_variables()`, then deserializing the resulting JSON string, SHALL produce a dict whose values (mapped back through the variable name ordering) are equivalent to the original context values.

**Validates: Requirements 3.4**

### Property 8: SQS message format invariants

*For any* notification queued via the NotificationTool, the SQS message body SHALL always contain the fields `notification_id`, `trainer_id`, `recipient`, `message`, and `attempt`; and SHALL contain `content_sid`, `template_variables`, and `notification_type` if and only if a template is configured for the notification type.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 9: NotificationSender dispatch consistency

*For any* SQS message processed by the NotificationSender, the sender SHALL invoke `send_template_message()` if the message contains a `content_sid` field with a non-empty value, and SHALL invoke `send_message()` with the `body` parameter otherwise.

**Validates: Requirements 5.1, 5.2**

### Property 10: Sending method recorded in delivery status

*For any* notification message successfully processed by the NotificationSender, the DynamoDB notification status update SHALL include a `sending_method` field with value `"template"` or `"freeform"` matching the actual dispatch method used.

**Validates: Requirements 5.3**

### Property 11: Template message retry parity

*For any* template message that fails with a Twilio error and has `attempt < 2`, the NotificationSender SHALL requeue the message with `attempt` incremented by 1 and a delay of 300 seconds, identical to the existing freeform retry behavior.

**Validates: Requirements 5.4**

### Property 12: Session reminder template variables

*For any* session reminder triggered when the `session_reminder` template is configured, the queued notification SHALL include the correct `content_sid` and a `template_variables` dict containing `student_name`, `session_date`, and `session_time` keys with non-empty string values derived from the session and student data.

**Validates: Requirements 6.1, 6.2**

### Property 13: Payment reminder template variables

*For any* payment reminder triggered when the `payment_reminder` template is configured, the queued notification SHALL include the correct `content_sid` and a `template_variables` dict containing `student_name`, `amount_due`, and `due_date` keys with non-empty string values derived from the student and payment data.

**Validates: Requirements 7.1, 7.2**

### Property 14: Broadcast notification template variables

*For any* broadcast notification sent when the `broadcast` template is configured, each queued SQS message SHALL include the correct `content_sid` and a `template_variables` dict containing `trainer_name` and `message_content` keys with non-empty string values.

**Validates: Requirements 8.1, 8.2**

### Property 15: Rate limiting preservation

*For any* batch of N broadcast notification messages queued by the NotificationTool, the i-th message (0-indexed) SHALL have an SQS `DelaySeconds` value of `min(i // 10, 900)`, preserving the existing 10 messages/second rate limit.

**Validates: Requirements 8.4**

### Property 16: Error details recorded on failure

*For any* notification message that fails after exhausting retries, the DynamoDB notification status update SHALL include non-empty `error` field containing the error information from the Twilio API response.

**Validates: Requirements 9.4**

## Error Handling

### TwilioClient Error Handling

| Error Scenario | Behavior |
|---|---|
| Twilio error 63016 on freeform message | Log error with recommendation to use template. Return error details in result dict. |
| Invalid Content SID error | Log error including the Content SID value. Return error details in result dict. |
| Invalid Content Variables error | Log error including the provided variables. Return error details in result dict. |
| Network/timeout error | Raise exception to trigger SQS retry via NotificationSender. |

### Template Registry Error Handling

| Error Scenario | Behavior |
|---|---|
| Invalid Content SID format in config | Log warning, exclude notification type from registry. Other types remain available. |
| Missing environment variables | Notification type not registered. Handlers fall back to freeform. |
| DynamoDB config read failure | Log error, continue with environment variable config only. |

### NotificationSender Error Handling

| Error Scenario | Behavior |
|---|---|
| Missing required template variables | Log warning, fall back to freeform using `message` body field. |
| Template send failure (attempt < 2) | Requeue to SQS with 5-minute delay, increment attempt counter. |
| Template send failure (attempt >= 2) | Mark as failed in DynamoDB with error code and message. |
| Malformed SQS message body | Log error, let SQS handle via DLQ after max receives. |

### Handler Fallback Chain

All handlers (session_reminder, payment_reminder, notification_tools) follow the same fallback chain:

1. Look up template in TemplateRegistry
2. If template found → include `content_sid` and `template_variables` in queued message
3. If template not found → queue freeform message with `message` body only
4. At send time, if template variables incomplete → fall back to freeform

This two-level fallback ensures messages are always delivered, even if template configuration is incomplete or missing.

## Testing Strategy

### Property-Based Testing

Property-based tests use **Hypothesis** (already in the project's test dependencies) with a minimum of **100 iterations** per property. Each test is tagged with a comment referencing the design property.

Tag format: `# Feature: whatsapp-template-notifications, Property {number}: {title}`

Tests go in `tests/property/test_template_notification_properties.py`.

Key properties to implement:

1. **Content SID validation** (Property 4): Generate arbitrary strings and verify `validate_content_sid()` returns True iff the string matches `HX` + 32 hex chars.
2. **Content Variables construction** (Property 5): Generate random TemplateConfigs and matching context dicts, verify output JSON structure.
3. **Missing variables fallback** (Property 6): Generate configs with incomplete contexts, verify `None` return.
4. **Content Variables round-trip** (Property 7): Generate valid contexts, build variables, deserialize, verify equivalence.
5. **SQS message format invariants** (Property 8): Generate notifications with/without templates, verify required fields.
6. **Rate limiting preservation** (Property 15): Generate batch sizes, verify delay calculation.

### Unit Testing

Unit tests use **pytest** with **moto** for AWS service mocking. Tests go in `tests/unit/`.

Focus areas:
- `test_template_registry.py`: Registry initialization, lookup, validation, missing types, invalid SIDs.
- `test_twilio_client_template.py`: `send_template_message()` with mocked Twilio SDK, error code handling (63016, invalid SID, invalid variables).
- `test_notification_sender_template.py`: Dispatch logic (template vs freeform), fallback on missing variables, retry behavior, DynamoDB status updates with `sending_method`.
- `test_session_reminder_template.py`: Template lookup and variable construction for session reminders, fallback behavior.
- `test_payment_reminder_template.py`: Template lookup and variable construction for payment reminders, fallback behavior.
- `test_notification_tools_template.py`: Broadcast template integration, SQS message format with template fields, backward compatibility.

### Integration Testing

Integration tests in `tests/integration/` verify end-to-end flows with LocalStack:
- Queue a template notification → process via NotificationSender → verify Twilio API call parameters and DynamoDB status.
- Queue a freeform notification → verify backward-compatible behavior.
- Template fallback: queue with template but missing variables → verify freeform fallback.

### Test Configuration

Each property-based test runs with `@settings(max_examples=100)` from Hypothesis. Each property test references its design document property with the tag format specified above. Each correctness property is implemented by a single property-based test function.
