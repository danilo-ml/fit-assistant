"""
Mock implementations for external services.

These mocks provide test doubles for external APIs (Twilio, Bedrock, Calendar)
that track calls and provide configurable responses for testing.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4
import json


class MockTwilioClient:
    """
    Mock Twilio client for testing.
    
    Tracks all messages sent and provides configurable responses.
    """
    
    def __init__(self):
        """Initialize mock client with empty message history."""
        self.messages_sent: List[Dict[str, Any]] = []
        self.should_fail = False
        self.failure_message = "Mock Twilio error"
    
    def send_message(self, to: str, from_: str, body: str, media_url: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Mock message sending.
        
        Args:
            to: Recipient phone number
            from_: Sender phone number
            body: Message body
            media_url: Optional list of media URLs
        
        Returns:
            Mock message response with SID
        
        Raises:
            Exception: If should_fail is True
        """
        if self.should_fail:
            raise Exception(self.failure_message)
        
        message_sid = f"SM{uuid4().hex[:32]}"
        message = {
            "sid": message_sid,
            "to": to,
            "from": from_,
            "body": body,
            "media_url": media_url or [],
            "status": "queued",
            "date_created": datetime.utcnow().isoformat()
        }
        
        self.messages_sent.append(message)
        return message
    
    def get_message(self, sid: str) -> Optional[Dict[str, Any]]:
        """
        Get a sent message by SID.
        
        Args:
            sid: Message SID
        
        Returns:
            Message dict or None if not found
        """
        for msg in self.messages_sent:
            if msg["sid"] == sid:
                return msg
        return None
    
    def clear_history(self):
        """Clear message history."""
        self.messages_sent = []
    
    def set_failure(self, should_fail: bool = True, message: str = "Mock Twilio error"):
        """
        Configure mock to fail on next send.
        
        Args:
            should_fail: Whether to fail
            message: Error message to raise
        """
        self.should_fail = should_fail
        self.failure_message = message


# MockBedrockClient removed - use real AWS Bedrock for consistency between environments


class MockCalendarClient:
    """
    Mock Google Calendar/Outlook client for testing.
    
    Simulates calendar operations and tracks all events.
    """
    
    def __init__(self):
        """Initialize mock client with empty event list."""
        self.events: List[Dict[str, Any]] = []
        self.should_fail = False
        self.failure_message = "Mock Calendar error"
    
    def create_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock event creation.
        
        Args:
            event: Event data with summary, start, end, etc.
        
        Returns:
            Created event with ID
        
        Raises:
            Exception: If should_fail is True
        """
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Generate event ID
        event_id = f"event_{uuid4().hex[:16]}"
        
        # Add metadata
        created_event = {
            "id": event_id,
            "status": "confirmed",
            "created": datetime.utcnow().isoformat(),
            "updated": datetime.utcnow().isoformat(),
            **event
        }
        
        self.events.append(created_event)
        return created_event
    
    def update_event(self, event_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mock event update.
        
        Args:
            event_id: Event ID to update
            event: Updated event data
        
        Returns:
            Updated event
        
        Raises:
            Exception: If event not found or should_fail is True
        """
        if self.should_fail:
            raise Exception(self.failure_message)
        
        for i, existing_event in enumerate(self.events):
            if existing_event["id"] == event_id:
                updated_event = {
                    **existing_event,
                    **event,
                    "updated": datetime.utcnow().isoformat()
                }
                self.events[i] = updated_event
                return updated_event
        
        raise Exception(f"Event not found: {event_id}")
    
    def delete_event(self, event_id: str) -> None:
        """
        Mock event deletion.
        
        Args:
            event_id: Event ID to delete
        
        Raises:
            Exception: If event not found or should_fail is True
        """
        if self.should_fail:
            raise Exception(self.failure_message)
        
        for i, event in enumerate(self.events):
            if event["id"] == event_id:
                self.events.pop(i)
                return
        
        raise Exception(f"Event not found: {event_id}")
    
    def list_events(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str = "primary"
    ) -> List[Dict[str, Any]]:
        """
        Mock event listing.
        
        Args:
            start: Start datetime for query
            end: End datetime for query
            calendar_id: Calendar ID (default: "primary")
        
        Returns:
            List of events in time range
        
        Raises:
            Exception: If should_fail is True
        """
        if self.should_fail:
            raise Exception(self.failure_message)
        
        # Filter events by time range
        filtered_events = []
        for event in self.events:
            event_start = datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
            event_end = datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
            
            # Check if event overlaps with query range
            if event_start < end and event_end > start:
                filtered_events.append(event)
        
        return filtered_events
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an event by ID.
        
        Args:
            event_id: Event ID
        
        Returns:
            Event dict or None if not found
        """
        for event in self.events:
            if event["id"] == event_id:
                return event
        return None
    
    def clear_events(self):
        """Clear all events."""
        self.events = []
    
    def set_failure(self, should_fail: bool = True, message: str = "Mock Calendar error"):
        """
        Configure mock to fail on next operation.
        
        Args:
            should_fail: Whether to fail
            message: Error message to raise
        """
        self.should_fail = should_fail
        self.failure_message = message
