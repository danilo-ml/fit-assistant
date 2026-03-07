# SessionConflictDetector

## Overview

The `SessionConflictDetector` class provides conflict detection for training session scheduling. It checks for time overlaps between a proposed session and existing sessions for a trainer, using the `session-date-index` GSI for efficient querying.

## Features

- **Time Overlap Detection**: Identifies sessions that overlap with a proposed time slot
- **30-Minute Buffer**: Queries sessions with a 30-minute buffer before and after for comprehensive conflict detection
- **Status Filtering**: Only considers `scheduled` and `confirmed` sessions (excludes `cancelled` and `completed`)
- **Exclusion Support**: Can exclude a specific session ID (useful when rescheduling)
- **Efficient Querying**: Uses DynamoDB GSI for fast date-range queries

## Usage

### Basic Conflict Check

```python
from datetime import datetime
from src.services.session_conflict import SessionConflictDetector

# Initialize detector
detector = SessionConflictDetector()

# Check for conflicts
conflicts = detector.check_conflicts(
    trainer_id='trainer123',
    session_datetime=datetime(2024, 1, 20, 14, 0),  # 2:00 PM
    duration_minutes=60
)

if conflicts:
    print(f"Found {len(conflicts)} conflicting sessions:")
    for conflict in conflicts:
        print(f"  - {conflict['student_name']} at {conflict['session_datetime']}")
else:
    print("No conflicts - session can be scheduled")
```

### Rescheduling (Exclude Current Session)

```python
# When rescheduling, exclude the session being rescheduled
conflicts = detector.check_conflicts(
    trainer_id='trainer123',
    session_datetime=datetime(2024, 1, 20, 15, 0),
    duration_minutes=60,
    exclude_session_id='session456'  # Don't check against itself
)
```

### With Custom DynamoDB Client

```python
from src.models.dynamodb_client import DynamoDBClient

# Use custom DynamoDB client (e.g., for testing or custom configuration)
custom_client = DynamoDBClient(endpoint_url='http://localhost:4566')
detector = SessionConflictDetector(dynamodb_client=custom_client)

conflicts = detector.check_conflicts(
    trainer_id='trainer123',
    session_datetime=datetime(2024, 1, 20, 14, 0),
    duration_minutes=60
)
```

## Integration with Session Tools

The `SessionConflictDetector` is typically used in the session scheduling tools:

```python
from src.services.session_conflict import SessionConflictDetector
from src.models.dynamodb_client import DynamoDBClient

def schedule_session(trainer_id: str, student_name: str, session_datetime: datetime, 
                     duration_minutes: int, **kwargs) -> dict:
    """Schedule a training session with conflict detection."""
    
    # Check for conflicts
    detector = SessionConflictDetector()
    conflicts = detector.check_conflicts(
        trainer_id=trainer_id,
        session_datetime=session_datetime,
        duration_minutes=duration_minutes
    )
    
    if conflicts:
        return {
            'success': False,
            'error': 'Session conflicts with existing sessions',
            'conflicts': [
                {
                    'session_id': c['session_id'],
                    'student_name': c['student_name'],
                    'time': c['session_datetime']
                }
                for c in conflicts
            ]
        }
    
    # No conflicts - proceed with scheduling
    # ... create session record ...
    
    return {
        'success': True,
        'session_id': session_id,
        'message': 'Session scheduled successfully'
    }
```

## Conflict Detection Logic

### Overlap Condition

Two sessions overlap if:
```
(session1_start < session2_end) AND (session1_end > session2_start)
```

This catches all overlap scenarios:
- Sessions with same start time
- One session starts during another
- One session completely contains another
- Partial overlaps at start or end

### Query Window

The detector queries sessions with a 30-minute buffer:
```
query_start = proposed_start - 30 minutes
query_end = proposed_end + 30 minutes
```

This ensures all potentially conflicting sessions are retrieved, even those that might be just outside the exact time window.

### Status Filtering

Only sessions with status `scheduled` or `confirmed` are considered for conflicts. Sessions with status `cancelled` or `completed` are excluded.

## Return Value

The `check_conflicts()` method returns a list of conflicting session dictionaries. Each dictionary contains:

```python
{
    'session_id': 'session123',
    'trainer_id': 'trainer456',
    'student_id': 'student789',
    'student_name': 'John Doe',
    'session_datetime': '2024-01-20T14:00:00',
    'duration_minutes': 60,
    'status': 'scheduled',
    'location': 'Gym A',  # Optional
    # ... other session fields ...
}
```

An empty list `[]` indicates no conflicts.

## Performance Considerations

- **GSI Query**: Uses `session-date-index` GSI for efficient date-range queries
- **Filtered Results**: DynamoDB filters by status at query time, reducing data transfer
- **In-Memory Overlap Check**: Final overlap detection happens in memory on filtered results
- **Typical Performance**: < 100ms for trainers with hundreds of sessions

## Testing

Comprehensive unit tests are available in `tests/unit/test_session_conflict.py`:

```bash
# Run tests
pytest tests/unit/test_session_conflict.py -v

# Run with coverage
pytest tests/unit/test_session_conflict.py --cov=src.services.session_conflict
```

## Requirements Validation

This implementation satisfies **Requirement 3.2**:
> THE FitAgent_Platform SHALL validate that the session time does not conflict with existing sessions for the trainer

And supports **Property 10: Session Conflict Detection**:
> For any trainer, when attempting to schedule a session that overlaps with an existing non-cancelled session, the system should detect and report the conflict.
