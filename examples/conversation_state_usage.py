"""
Example usage of ConversationStateManager.

This example demonstrates how to use the ConversationStateManager
to manage conversation state for WhatsApp users.
"""

from src.services.conversation_state import ConversationStateManager
from src.models.dynamodb_client import DynamoDBClient


def example_new_user_flow():
    """Example: New user starting a conversation."""
    print("=== New User Flow ===\n")
    
    # Initialize manager
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # 1. User sends first message - no state exists yet
    print("1. User sends first message")
    state = manager.add_message(
        phone_number=phone,
        role='user',
        content='Hello'
    )
    print(f"   State: {state.state}")
    print(f"   Messages: {len(state.message_history)}")
    print()
    
    # 2. System identifies this is a new user, transitions to ONBOARDING
    print("2. System transitions to ONBOARDING")
    state = manager.transition_state(
        phone_number=phone,
        new_state='ONBOARDING'
    )
    print(f"   State: {state.state}")
    print()
    
    # 3. Add assistant response
    print("3. Assistant responds with onboarding prompt")
    state = manager.add_message(
        phone_number=phone,
        role='assistant',
        content='Welcome! Are you a trainer or a student?'
    )
    print(f"   Messages: {len(state.message_history)}")
    print()


def example_trainer_identification():
    """Example: Identifying and transitioning to trainer menu."""
    print("=== Trainer Identification Flow ===\n")
    
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # 1. User completes onboarding as trainer
    print("1. User identified as trainer")
    state = manager.transition_state(
        phone_number=phone,
        new_state='TRAINER_MENU',
        user_id='trainer123',
        user_type='TRAINER'
    )
    print(f"   State: {state.state}")
    print(f"   User ID: {state.user_id}")
    print(f"   User Type: {state.user_type}")
    print()
    
    # 2. Add conversation with context
    print("2. User requests to schedule session")
    state = manager.update_state(
        phone_number=phone,
        state='TRAINER_MENU',
        context={'last_action': 'schedule_session', 'step': 'collect_student_name'},
        message={'role': 'user', 'content': 'I want to schedule a session'}
    )
    print(f"   Context: {state.context}")
    print()


def example_message_history_management():
    """Example: Message history with 10-message limit."""
    print("=== Message History Management ===\n")
    
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # Initialize state
    manager.transition_state(
        phone_number=phone,
        new_state='TRAINER_MENU',
        user_id='trainer123',
        user_type='TRAINER'
    )
    
    # Add 12 messages to test the 10-message limit
    print("Adding 12 messages...")
    for i in range(12):
        role = 'user' if i % 2 == 0 else 'assistant'
        manager.add_message(
            phone_number=phone,
            role=role,
            content=f'Message {i + 1}'
        )
    
    # Retrieve message history
    history = manager.get_message_history(phone)
    print(f"Message history length: {len(history)} (should be 10)")
    print(f"First message: {history[0].content}")
    print(f"Last message: {history[-1].content}")
    print()


def example_context_management():
    """Example: Managing context for multi-step actions."""
    print("=== Context Management ===\n")
    
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # Initialize trainer state
    manager.transition_state(
        phone_number=phone,
        new_state='TRAINER_MENU',
        user_id='trainer123',
        user_type='TRAINER'
    )
    
    # Step 1: Start scheduling session
    print("1. Start scheduling session")
    state = manager.update_context(
        phone_number=phone,
        context_updates={
            'action': 'schedule_session',
            'step': 'collect_student_name'
        }
    )
    print(f"   Context: {state.context}")
    print()
    
    # Step 2: Collect student name
    print("2. Student name collected")
    state = manager.update_context(
        phone_number=phone,
        context_updates={
            'step': 'collect_date',
            'student_name': 'John Doe'
        }
    )
    print(f"   Context: {state.context}")
    print()
    
    # Step 3: Collect date
    print("3. Date collected")
    state = manager.update_context(
        phone_number=phone,
        context_updates={
            'step': 'collect_time',
            'date': '2024-01-20'
        }
    )
    print(f"   Context: {state.context}")
    print()
    
    # Step 4: Complete action
    print("4. Session scheduled, clear context")
    state = manager.update_context(
        phone_number=phone,
        context_updates={
            'action': None,
            'step': None,
            'student_name': None,
            'date': None,
            'last_session_id': 'session123'
        }
    )
    print(f"   Context: {state.context}")
    print()


def example_state_retrieval():
    """Example: Retrieving existing state."""
    print("=== State Retrieval ===\n")
    
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # Create state
    manager.update_state(
        phone_number=phone,
        state='TRAINER_MENU',
        user_id='trainer123',
        user_type='TRAINER',
        context={'last_action': 'view_students'},
        message={'role': 'user', 'content': 'Show my students'}
    )
    
    # Retrieve state
    print("Retrieving state...")
    state = manager.get_state(phone)
    
    if state:
        print(f"   Phone: {state.phone_number}")
        print(f"   State: {state.state}")
        print(f"   User ID: {state.user_id}")
        print(f"   User Type: {state.user_type}")
        print(f"   Context: {state.context}")
        print(f"   Messages: {len(state.message_history)}")
        print(f"   TTL: {state.ttl} (expires in ~24 hours)")
    else:
        print("   No state found")
    print()


def example_state_cleanup():
    """Example: Manual state cleanup."""
    print("=== State Cleanup ===\n")
    
    manager = ConversationStateManager()
    phone = "+1234567890"
    
    # Create state
    manager.update_state(
        phone_number=phone,
        state='TRAINER_MENU',
        user_id='trainer123',
        user_type='TRAINER'
    )
    
    print("State created")
    state = manager.get_state(phone)
    print(f"   State exists: {state is not None}")
    print()
    
    # Clear state
    print("Clearing state...")
    success = manager.clear_state(phone)
    print(f"   Cleared: {success}")
    print()
    
    # Verify cleared
    state = manager.get_state(phone)
    print(f"   State exists: {state is not None}")
    print()


def example_student_flow():
    """Example: Student conversation flow."""
    print("=== Student Flow ===\n")
    
    manager = ConversationStateManager()
    phone = "+9876543210"
    
    # 1. Student identified
    print("1. Student identified")
    state = manager.transition_state(
        phone_number=phone,
        new_state='STUDENT_MENU',
        user_id='student456',
        user_type='STUDENT'
    )
    print(f"   State: {state.state}")
    print(f"   User Type: {state.user_type}")
    print()
    
    # 2. Student views upcoming sessions
    print("2. Student requests upcoming sessions")
    state = manager.update_state(
        phone_number=phone,
        state='STUDENT_MENU',
        context={'last_action': 'view_sessions'},
        message={'role': 'user', 'content': 'Show my upcoming sessions'}
    )
    print(f"   Context: {state.context}")
    print()
    
    # 3. Student confirms attendance
    print("3. Student confirms attendance")
    state = manager.update_state(
        phone_number=phone,
        state='STUDENT_MENU',
        context={'last_action': 'confirm_attendance', 'session_id': 'session123'},
        message={'role': 'user', 'content': 'I confirm attendance for tomorrow'}
    )
    print(f"   Context: {state.context}")
    print()


if __name__ == '__main__':
    print("ConversationStateManager Usage Examples")
    print("=" * 60)
    print()
    
    # Note: These examples use mock data and won't actually connect to DynamoDB
    # In production, ensure DynamoDB is configured with proper credentials
    
    try:
        example_new_user_flow()
        example_trainer_identification()
        example_message_history_management()
        example_context_management()
        example_state_retrieval()
        example_state_cleanup()
        example_student_flow()
        
        print("=" * 60)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"Error running examples: {e}")
        print("Note: Examples require DynamoDB to be configured")
