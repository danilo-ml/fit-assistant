# Reminder Handlers

This directory contains Lambda functions for automated reminder services.

## Session Reminder Handler

**File:** `session_reminder.py`

**Trigger:** EventBridge scheduled rule (hourly)

**Purpose:** Sends automated session reminders to students before their scheduled training sessions.

### Functionality

1. **Query Sessions:** Scans for sessions scheduled within the next 48 hours with status `scheduled` or `confirmed`
2. **Filter by Configuration:** Checks trainer reminder configuration (default 24 hours before session)
3. **Exclude Duplicates:** Skips sessions that already have reminders sent
4. **Exclude Cancelled:** Automatically filters out cancelled sessions
5. **Send WhatsApp Messages:** Sends formatted reminder messages via Twilio
6. **Record Delivery:** Creates reminder records in DynamoDB for audit purposes

### Message Format

```
🔔 Session Reminder

You have a training session with [Trainer Name]:
📅 [Day, Month Date, Year]
🕐 [Time]
⏱️ Duration: [X] minutes
📍 Location: [Location] (if provided)

See you there! 💪
```

### Configuration

Trainers can configure:
- `reminder_hours`: Hours before session to send reminder (1-48, default 24)
- `session_reminders_enabled`: Enable/disable session reminders (default true)

### Requirements Validated

- 8.1: Session reminders sent at configured hours before session
- 8.2: Reminder timing configurable between 1-48 hours
- 8.4: Reminder includes session details
- 8.5: Cancelled sessions excluded
- 8.6: Delivery status recorded in DynamoDB

## Payment Reminder Handler

**File:** `payment_reminder.py`

**Trigger:** EventBridge scheduled rule (monthly, configurable day)

**Purpose:** Sends automated payment reminders to students with unpaid sessions from the previous month.

### Functionality

1. **Calculate Date Range:** Determines previous month's date range
2. **Query Unpaid Payments:** Scans for payments with status `pending` from previous month
3. **Group by Student:** Consolidates multiple unpaid sessions per student
4. **Calculate Totals:** Sums total amount due and counts unpaid sessions
5. **Filter Recipients:** Only sends to students with unpaid sessions
6. **Send WhatsApp Messages:** Sends formatted reminder messages via Twilio
7. **Record Delivery:** Creates notification records in DynamoDB

### Message Format

```
💰 Payment Reminder

Hi [Student Name]!

This is a friendly reminder from [Trainer Name]
([Business Name])

You have [X] unpaid session(s) from last month:

💵 Total Amount Due: [Currency] [Amount]
📊 Number of Sessions: [X]

Please send your payment at your earliest convenience.

Thank you! 🙏
```

### Configuration

Trainers can configure:
- `payment_reminder_day`: Day of month to send reminders (1-28, default 1)
- `payment_reminders_enabled`: Enable/disable payment reminders (default true)

### Requirements Validated

- 9.1: Payment reminders sent on configured day of month
- 9.2: Reminder day configurable between 1-28
- 9.3: Only students with unpaid sessions receive reminders
- 9.4: Message includes total amount due and session count
- 9.5: Students with all payments confirmed excluded

## Error Handling

Both handlers implement robust error handling:

- **Partial Failures:** Continue processing remaining reminders if one fails
- **Missing Data:** Log errors and skip reminders for missing students/trainers
- **Twilio Failures:** Log errors but don't block other reminders
- **DynamoDB Errors:** Log errors and continue with available data

## Testing

Comprehensive unit tests cover:

- Successful reminder processing
- Configuration-based filtering
- Duplicate prevention
- Error handling and partial failures
- Message formatting
- Delivery tracking

Run tests:
```bash
pytest tests/unit/test_session_reminder.py -v
pytest tests/unit/test_payment_reminder.py -v
```

## Performance Considerations

### Session Reminders

- **Scan Operation:** Uses DynamoDB scan to find sessions (acceptable for MVP)
- **Optimization:** In production, consider maintaining an active trainers list to query sessions per trainer using GSI
- **Frequency:** Runs hourly, processes only sessions within reminder window

### Payment Reminders

- **Scan Operation:** Uses DynamoDB scan to find unpaid payments (acceptable for MVP)
- **Optimization:** In production, use payment-status-index GSI with trainer list
- **Frequency:** Runs monthly, processes previous month's data

## Deployment

These handlers are deployed as Lambda functions with:

- **Memory:** 256 MB (sufficient for reminder processing)
- **Timeout:** 5 minutes (allows processing of large reminder batches)
- **Concurrency:** No limit (low frequency, predictable load)
- **Environment Variables:** Standard FitAgent configuration

### EventBridge Rules

**Session Reminders:**
```yaml
Schedule: rate(1 hour)
Target: session-reminder Lambda function
```

**Payment Reminders:**
```yaml
Schedule: cron(0 10 1 * ? *)  # 10 AM on day 1 of each month
Target: payment-reminder Lambda function
```

Note: Payment reminder day can be configured per trainer, but the EventBridge rule runs on a fixed schedule. The handler filters based on trainer configuration.

## Monitoring

Key metrics to monitor:

- **Invocation Count:** Number of times handlers are triggered
- **Reminders Sent:** Count of successful reminder deliveries
- **Reminders Failed:** Count of failed reminder attempts
- **Duration:** Execution time per invocation
- **Errors:** Lambda errors and exceptions

CloudWatch Logs include structured JSON logs with:
- Session/payment IDs
- Student/trainer IDs
- Delivery status
- Error details

## Future Enhancements

1. **Trainer List Optimization:** Maintain active trainers list to avoid scans
2. **Batch Processing:** Process reminders in batches for better performance
3. **Retry Logic:** Implement exponential backoff for Twilio failures
4. **Delivery Confirmation:** Track WhatsApp delivery receipts via webhooks
5. **Customizable Messages:** Allow trainers to customize reminder templates
6. **Multi-Language Support:** Support reminders in different languages
7. **Time Zone Support:** Send reminders based on trainer/student time zones
