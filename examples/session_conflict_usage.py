"""
Example usage of SessionConflictDetector.

This example demonstrates how to use the SessionConflictDetector class
to check for scheduling conflicts when scheduling or rescheduling sessions.
"""

from datetime import datetime, timedelta
from src.services.session_conflict import SessionConflictDetector
from src.models.dynamodb_client import DynamoDBClient


def example_basic_conflict_check():
    """Example: Basic conflict check when scheduling a new session."""
    print("=" * 60)
    print("Example 1: Basic Conflict Check")
    print("=" * 60)
    
    # Initialize the detector
    detector = SessionConflictDetector()
    
    # Proposed session details
    trainer_id = 'trainer123'
    proposed_time = datetime(2024, 1, 20, 14, 0)  # 2:00 PM
    duration = 60  # 1 hour
    
    print(f"\nChecking conflicts for:")
    print(f"  Trainer: {trainer_id}")
    print(f"  Time: {proposed_time.strftime('%Y-%m-%d %I:%M %p')}")
    print(f"  Duration: {duration} minutes")
    
    # Check for conflicts
    conflicts = detector.check_conflicts(
        trainer_id=trainer_id,
        session_datetime=proposed_time,
        duration_minutes=duration
    )
    
    # Handle results
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} conflicting session(s):")
        for conflict in conflicts:
            conflict_time = datetime.fromisoformat(conflict['session_datetime'])
            print(f"  - {conflict['student_name']} at {conflict_time.strftime('%I:%M %p')}")
            print(f"    Duration: {conflict['duration_minutes']} minutes")
            print(f"    Status: {conflict['status']}")
        return False
    else:
        print("\n✓ No conflicts found - session can be scheduled!")
        return True


def example_reschedule_with_exclusion():
    """Example: Check conflicts when rescheduling (exclude current session)."""
    print("\n" + "=" * 60)
    print("Example 2: Rescheduling with Exclusion")
    print("=" * 60)
    
    detector = SessionConflictDetector()
    
    # Existing session being rescheduled
    session_id = 'session456'
    trainer_id = 'trainer123'
    new_time = datetime(2024, 1, 20, 15, 0)  # 3:00 PM
    duration = 60
    
    print(f"\nRescheduling session {session_id}:")
    print(f"  New time: {new_time.strftime('%Y-%m-%d %I:%M %p')}")
    print(f"  Duration: {duration} minutes")
    
    # Check for conflicts, excluding the session being rescheduled
    conflicts = detector.check_conflicts(
        trainer_id=trainer_id,
        session_datetime=new_time,
        duration_minutes=duration,
        exclude_session_id=session_id  # Don't check against itself
    )
    
    if conflicts:
        print(f"\n⚠️  Cannot reschedule - conflicts with {len(conflicts)} session(s):")
        for conflict in conflicts:
            conflict_time = datetime.fromisoformat(conflict['session_datetime'])
            print(f"  - {conflict['student_name']} at {conflict_time.strftime('%I:%M %p')}")
        return False
    else:
        print("\n✓ No conflicts - session can be rescheduled!")
        return True


def example_multiple_time_slots():
    """Example: Find the first available time slot from multiple options."""
    print("\n" + "=" * 60)
    print("Example 3: Finding Available Time Slot")
    print("=" * 60)
    
    detector = SessionConflictDetector()
    
    trainer_id = 'trainer123'
    base_date = datetime(2024, 1, 20, 9, 0)  # Start at 9:00 AM
    duration = 60
    
    # Try multiple time slots (every hour from 9 AM to 5 PM)
    time_slots = [base_date + timedelta(hours=i) for i in range(9)]  # 9 AM to 5 PM
    
    print(f"\nSearching for available time slot on {base_date.strftime('%Y-%m-%d')}:")
    print(f"  Duration: {duration} minutes")
    print(f"  Checking slots from 9:00 AM to 5:00 PM\n")
    
    available_slots = []
    for slot in time_slots:
        conflicts = detector.check_conflicts(
            trainer_id=trainer_id,
            session_datetime=slot,
            duration_minutes=duration
        )
        
        status = "✓ Available" if not conflicts else f"✗ Conflict ({len(conflicts)})"
        print(f"  {slot.strftime('%I:%M %p')}: {status}")
        
        if not conflicts:
            available_slots.append(slot)
    
    if available_slots:
        print(f"\n✓ Found {len(available_slots)} available time slot(s)")
        print(f"  First available: {available_slots[0].strftime('%I:%M %p')}")
    else:
        print("\n⚠️  No available time slots found")
    
    return available_slots


def example_with_custom_client():
    """Example: Using SessionConflictDetector with a custom DynamoDB client."""
    print("\n" + "=" * 60)
    print("Example 4: Custom DynamoDB Client (LocalStack)")
    print("=" * 60)
    
    # Create custom DynamoDB client for LocalStack
    custom_client = DynamoDBClient(
        table_name='fitagent-main',
        endpoint_url='http://localhost:4566'  # LocalStack endpoint
    )
    
    # Initialize detector with custom client
    detector = SessionConflictDetector(dynamodb_client=custom_client)
    
    print("\n✓ SessionConflictDetector initialized with LocalStack client")
    print("  Endpoint: http://localhost:4566")
    print("  Table: fitagent-main")
    
    # Now use detector as normal
    conflicts = detector.check_conflicts(
        trainer_id='trainer123',
        session_datetime=datetime(2024, 1, 20, 14, 0),
        duration_minutes=60
    )
    
    print(f"\n  Conflicts found: {len(conflicts)}")
    return detector


def example_conflict_details():
    """Example: Examining detailed conflict information."""
    print("\n" + "=" * 60)
    print("Example 5: Detailed Conflict Information")
    print("=" * 60)
    
    detector = SessionConflictDetector()
    
    trainer_id = 'trainer123'
    proposed_time = datetime(2024, 1, 20, 14, 0)
    duration = 120  # 2 hours
    
    print(f"\nProposed session:")
    print(f"  Time: {proposed_time.strftime('%I:%M %p')} - {(proposed_time + timedelta(minutes=duration)).strftime('%I:%M %p')}")
    print(f"  Duration: {duration} minutes")
    
    conflicts = detector.check_conflicts(
        trainer_id=trainer_id,
        session_datetime=proposed_time,
        duration_minutes=duration
    )
    
    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} conflict(s):\n")
        for i, conflict in enumerate(conflicts, 1):
            start = datetime.fromisoformat(conflict['session_datetime'])
            end = start + timedelta(minutes=conflict['duration_minutes'])
            
            print(f"  Conflict #{i}:")
            print(f"    Session ID: {conflict['session_id']}")
            print(f"    Student: {conflict['student_name']}")
            print(f"    Time: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}")
            print(f"    Duration: {conflict['duration_minutes']} minutes")
            print(f"    Status: {conflict['status']}")
            if conflict.get('location'):
                print(f"    Location: {conflict['location']}")
            print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("SessionConflictDetector Usage Examples")
    print("=" * 60)
    
    try:
        # Run examples
        example_basic_conflict_check()
        example_reschedule_with_exclusion()
        example_multiple_time_slots()
        example_with_custom_client()
        example_conflict_details()
        
        print("\n" + "=" * 60)
        print("All examples completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
