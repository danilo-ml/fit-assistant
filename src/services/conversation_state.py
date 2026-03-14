"""
Conversation state management service for FitAgent.

This module provides the ConversationStateManager class for managing
conversation state in DynamoDB with TTL-based expiration and message history.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Literal
from models.dynamodb_client import DynamoDBClient
from models.entities import ConversationState, MessageHistoryEntry


class ConversationStateManager:
    """
    Manages conversation state for WhatsApp users.

    Responsibilities:
    - Store and retrieve conversation state per phone number
    - Maintain message history (last 10 messages)
    - Calculate TTL for automatic state expiration (24 hours)
    - Support state transitions: UNKNOWN → ONBOARDING → TRAINER_MENU/STUDENT_MENU
    - Track user identity (user_id, user_type) when identified
    - Store context for pending actions

    **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6**
    """

    def __init__(self, dynamodb_client: Optional[DynamoDBClient] = None, ttl_hours: int = 24):
        """
        Initialize ConversationStateManager.

        Args:
            dynamodb_client: DynamoDB client instance (creates new if None)
            ttl_hours: Hours until conversation state expires (default: 24)
        """
        self.dynamodb = dynamodb_client or DynamoDBClient()
        self.ttl_hours = ttl_hours

    def get_state(self, phone_number: str) -> Optional[ConversationState]:
        """
        Retrieve conversation state for a phone number.

        Args:
            phone_number: Phone number in E.164 format

        Returns:
            ConversationState if found, None otherwise

        **Validates: Requirement 11.1** - Maintain conversation state per phone number
        """
        item = self.dynamodb.get_item(pk=f"CONVERSATION#{phone_number}", sk="STATE")

        if not item:
            return None

        return ConversationState.from_dynamodb(item)

    def update_state(
        self,
        phone_number: str,
        state: Literal["UNKNOWN", "ONBOARDING", "TRAINER_MENU", "STUDENT_MENU"],
        user_id: Optional[str] = None,
        user_type: Optional[Literal["TRAINER", "STUDENT"]] = None,
        context: Optional[Dict[str, Any]] = None,
        message: Optional[Dict[str, str]] = None,
    ) -> ConversationState:
        """
        Update conversation state with new information.

        Args:
            phone_number: Phone number in E.164 format
            state: New conversation state
            user_id: User identifier (trainer_id or student_id)
            user_type: Type of user (TRAINER or STUDENT)
            context: Additional context data for pending actions
            message: Message to add to history with 'role' and 'content' keys

        Returns:
            Updated ConversationState

        **Validates: Requirements 11.2, 11.3, 11.4, 11.5** - State transitions and context management
        """
        now = datetime.utcnow()
        ttl = int((now + timedelta(hours=self.ttl_hours)).timestamp())

        # Get existing state or create new
        current_state = self.get_state(phone_number)

        if current_state:
            # Preserve existing data
            message_history = current_state.message_history
            created_at = current_state.created_at
            existing_context = current_state.context
            existing_user_id = current_state.user_id
            existing_user_type = current_state.user_type
        else:
            # Initialize new state
            message_history = []
            created_at = now
            existing_context = {}
            existing_user_id = None
            existing_user_type = None

        # Add new message to history if provided
        if message:
            message_history.append(
                MessageHistoryEntry(role=message["role"], content=message["content"], timestamp=now)
            )
            # Keep only last 10 messages
            message_history = message_history[-10:]

        # Merge context (new values override existing)
        merged_context = {**existing_context, **(context or {})}

        # Create updated state
        conversation_state = ConversationState(
            phone_number=phone_number,
            state=state,
            user_id=user_id or existing_user_id,
            user_type=user_type or existing_user_type,
            context=merged_context,
            message_history=message_history,
            created_at=created_at,
            updated_at=now,
            ttl=ttl,
        )

        # Save to DynamoDB
        self.dynamodb.put_item(conversation_state.to_dynamodb())

        return conversation_state

    def clear_state(self, phone_number: str) -> bool:
        """
        Clear conversation state for a phone number.

        This is for manual cleanup. Automatic cleanup happens via DynamoDB TTL.

        Args:
            phone_number: Phone number in E.164 format

        Returns:
            True if state was deleted, False if not found

        **Validates: Requirement 11.6** - State expiration and cleanup
        """
        return self.dynamodb.delete_item(pk=f"CONVERSATION#{phone_number}", sk="STATE")

    def transition_state(
        self,
        phone_number: str,
        new_state: Literal["UNKNOWN", "ONBOARDING", "TRAINER_MENU", "STUDENT_MENU"],
        user_id: Optional[str] = None,
        user_type: Optional[Literal["TRAINER", "STUDENT"]] = None,
    ) -> ConversationState:
        """
        Transition conversation to a new state.

        Convenience method for state transitions without adding messages.

        Args:
            phone_number: Phone number in E.164 format
            new_state: Target state
            user_id: User identifier when transitioning to menu states
            user_type: User type when transitioning to menu states

        Returns:
            Updated ConversationState

        **Validates: Requirements 11.2, 11.3, 11.4** - State transitions
        """
        return self.update_state(
            phone_number=phone_number, state=new_state, user_id=user_id, user_type=user_type
        )

    def add_message(
        self, phone_number: str, role: Literal["user", "assistant"], content: str
    ) -> ConversationState:
        """
        Add a message to conversation history without changing state.

        Args:
            phone_number: Phone number in E.164 format
            role: Message role (user or assistant)
            content: Message content

        Returns:
            Updated ConversationState

        **Validates: Requirement 11.5** - Message history management
        """
        current_state = self.get_state(phone_number)

        if not current_state:
            # Initialize with UNKNOWN state if no state exists
            return self.update_state(
                phone_number=phone_number,
                state="UNKNOWN",
                message={"role": role, "content": content},
            )

        return self.update_state(
            phone_number=phone_number,
            state=current_state.state,
            user_id=current_state.user_id,
            user_type=current_state.user_type,
            context=current_state.context,
            message={"role": role, "content": content},
        )

    def get_message_history(self, phone_number: str) -> List[MessageHistoryEntry]:
        """
        Get message history for a phone number.

        Args:
            phone_number: Phone number in E.164 format

        Returns:
            List of MessageHistoryEntry objects (up to 10 most recent)

        **Validates: Requirement 11.5** - Message history retrieval
        """
        state = self.get_state(phone_number)
        return state.message_history if state else []

    def update_context(
        self, phone_number: str, context_updates: Dict[str, Any]
    ) -> ConversationState:
        """
        Update context data without changing state or adding messages.

        Args:
            phone_number: Phone number in E.164 format
            context_updates: Context data to merge with existing context

        Returns:
            Updated ConversationState

        **Validates: Requirement 11.5** - Context management for pending actions
        """
        current_state = self.get_state(phone_number)

        if not current_state:
            # Initialize with UNKNOWN state if no state exists
            return self.update_state(
                phone_number=phone_number, state="UNKNOWN", context=context_updates
            )

        return self.update_state(
            phone_number=phone_number,
            state=current_state.state,
            user_id=current_state.user_id,
            user_type=current_state.user_type,
            context=context_updates,
        )
