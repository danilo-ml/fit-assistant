"""
Example usage of DynamoDB client abstraction layer.

This demonstrates common access patterns for the FitAgent platform.
"""

from datetime import datetime, timedelta
from src.models.dynamodb_client import DynamoDBClient
from src.models.entities import Trainer, Student, TrainerStudentLink, Session, Payment


def example_trainer_workflow():
    """Example: Complete trainer workflow."""
    db = DynamoDBClient()
    
    # 1. Create a trainer
    trainer = Trainer(
        name='John Doe',
        email='john@fittraining.com',
        business_name='Fit Training Pro',
        phone_number='+12345678901'
    )
    db.put_trainer(trainer.to_dynamodb())
    print(f"✓ Created trainer: {trainer.trainer_id}")
    
    # 2. Register students
    students = []
    for i, (name, goal) in enumerate([
        ('Alice Smith', 'Weight loss'),
        ('Bob Johnson', 'Muscle gain'),
        ('Carol White', 'General fitness')
    ]):
        student = Student(
            name=name,
            email=f'{name.lower().replace(" ", ".")}@example.com',
            phone_number=f'+1987654321{i}',
            training_goal=goal
        )
        db.put_student(student.to_dynamodb())
        students.append(student)
        
        # Link student to trainer
        link = TrainerStudentLink(
            trainer_id=trainer.trainer_id,
            student_id=student.student_id
        )
        db.put_trainer_student_link(link.to_dynamodb())
        print(f"✓ Registered student: {name}")
    
    # 3. Schedule sessions
    base_time = datetime.utcnow() + timedelta(days=1)
    for i, student in enumerate(students):
        session = Session(
            trainer_id=trainer.trainer_id,
            student_id=student.student_id,
            student_name=student.name,
            session_datetime=base_time + timedelta(hours=i*2),
            duration_minutes=60,
            location='Main Gym'
        )
        db.put_session(session.to_dynamodb())
        print(f"✓ Scheduled session with {student.name}")
    
    # 4. Query upcoming sessions
    upcoming = db.get_upcoming_sessions(trainer.trainer_id, days_ahead=7)
    print(f"\n📅 Upcoming sessions: {len(upcoming)}")
    for session in upcoming:
        print(f"  - {session['student_name']} at {session['session_datetime']}")
    
    # 5. Register payment
    payment = Payment(
        trainer_id=trainer.trainer_id,
        student_id=students[0].student_id,
        student_name=students[0].name,
        amount=150.00,
        payment_date=datetime.utcnow().date().isoformat()
    )
    db.put_payment(payment.to_dynamodb())
    print(f"\n💰 Registered payment from {students[0].name}")
    
    # 6. Query pending payments
    pending = db.get_payments_by_status(trainer.trainer_id, 'pending')
    print(f"💳 Pending payments: {len(pending)}")
    
    return trainer.trainer_id


def example_phone_lookup():
    """Example: User identification by phone number."""
    db = DynamoDBClient()
    
    # Lookup user by phone number (simulates incoming WhatsApp message)
    phone = '+12345678901'
    user = db.lookup_by_phone_number(phone)
    
    if user:
        print(f"\n📱 Phone lookup for {phone}:")
        print(f"  Type: {user['entity_type']}")
        print(f"  Name: {user['name']}")
        print(f"  ID: {user.get('trainer_id') or user.get('student_id')}")
    else:
        print(f"\n📱 Phone {phone} not found - initiate onboarding")


def example_session_conflict_detection():
    """Example: Detect scheduling conflicts."""
    db = DynamoDBClient()
    trainer_id = 'trainer123'
    
    # Get sessions in a specific time window
    target_time = datetime.utcnow() + timedelta(days=1, hours=14)
    window_start = target_time - timedelta(hours=1)
    window_end = target_time + timedelta(hours=1)
    
    existing_sessions = db.get_sessions_by_date_range(
        trainer_id,
        window_start,
        window_end,
        status_filter=['scheduled', 'confirmed']
    )
    
    if existing_sessions:
        print(f"\n⚠️  Conflict detected! {len(existing_sessions)} session(s) in time window")
        for session in existing_sessions:
            print(f"  - {session['student_name']} at {session['session_datetime']}")
    else:
        print(f"\n✓ No conflicts - time slot available")


def example_student_view():
    """Example: Student viewing their sessions."""
    db = DynamoDBClient()
    student_id = 'student456'
    
    # Get upcoming sessions for student
    now = datetime.utcnow()
    future = now + timedelta(days=30)
    
    sessions = db.get_student_sessions(student_id, now, future)
    
    print(f"\n📋 Your upcoming sessions:")
    for session in sessions:
        print(f"  - {session['session_datetime']} with trainer {session['trainer_id']}")
        print(f"    Duration: {session['duration_minutes']} minutes")
        print(f"    Location: {session.get('location', 'TBD')}")


def example_batch_operations():
    """Example: Efficient batch operations."""
    db = DynamoDBClient()
    
    # Batch write multiple students
    students = [
        Student(
            name=f'Student {i}',
            email=f'student{i}@example.com',
            phone_number=f'+1555000{i:04d}',
            training_goal='Fitness'
        )
        for i in range(10)
    ]
    
    items = [s.to_dynamodb() for s in students]
    success = db.batch_write_items(items)
    
    if success:
        print(f"\n✓ Batch created {len(students)} students")
        
        # Batch retrieve
        keys = [{'PK': f'STUDENT#{s.student_id}', 'SK': 'METADATA'} for s in students]
        retrieved = db.batch_get_items(keys)
        print(f"✓ Batch retrieved {len(retrieved)} students")


if __name__ == '__main__':
    print("=" * 60)
    print("DynamoDB Client Usage Examples")
    print("=" * 60)
    
    # Note: These examples require a running DynamoDB instance
    # Use LocalStack for local testing
    
    print("\n1. Trainer Workflow Example")
    print("-" * 60)
    # example_trainer_workflow()
    
    print("\n2. Phone Number Lookup Example")
    print("-" * 60)
    # example_phone_lookup()
    
    print("\n3. Session Conflict Detection Example")
    print("-" * 60)
    # example_session_conflict_detection()
    
    print("\n4. Student View Example")
    print("-" * 60)
    # example_student_view()
    
    print("\n5. Batch Operations Example")
    print("-" * 60)
    # example_batch_operations()
    
    print("\n" + "=" * 60)
    print("Uncomment function calls to run examples")
    print("=" * 60)
