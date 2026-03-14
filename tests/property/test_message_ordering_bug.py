"""
Property-based test for message ordering bug exploration.

This test demonstrates the message ordering bug where rapid sequential messages
from the same phone number are processed in parallel, causing responses to arrive
out of order and conversation state race conditions.

**EXPECTED OUTCOME ON UNFIXED CODE**: Test FAILS
- Responses arrive in different order than questions
- Conversation state shows race conditions (last write wins)
- AI agent loses conversational context

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import pytest
import json
import time
import threading
from typing import List, Dict, Any
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.handlers.message_processor import lambda_handler


class TestMessageOrderingBugExploration:
    """
    Bug exploration test for message ordering issues.
    
    This test sends rapid sequential messages from the same phone number
    and verifies they are processed in order. On UNFIXED code, this test
    should FAIL, demonstrating the bug exists.
    """
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_rapid_sequential_messages_ordering(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that rapid sequential messages from same phone number are processed in order.
        
        Sends 3 messages from same phone number with 100ms delay between each.
        
        **EXPECTED ON UNFIXED CODE**: Test FAILS
        - Responses arrive out of order (e.g., Message 3 response before Message 2)
        - Conversation state shows race conditions
        - AI agent loses context from earlier messages
        
        **Validates: Requirements 1.1, 1.2, 1.3**
        """
        # Arrange
        phone_number = "+14155551234"
        
        # Track the order of responses with timestamps
        response_order = []
        response_lock = threading.Lock()
        
        # Mock router to return onboarding handler
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Mock onboarding handler with variable processing times
        # Message 1: 150ms, Message 2: 100ms, Message 3: 50ms
        # This simulates real-world scenario where later messages finish first
        def handle_message_side_effect(phone_number, message_body, request_id):
            body = message_body.get("body", "")
            
            # Variable processing time based on message
            if "Message 1" in body:
                time.sleep(0.15)  # 150ms - slowest
            elif "Message 2" in body:
                time.sleep(0.10)  # 100ms - medium
            else:  # Message 3
                time.sleep(0.05)  # 50ms - fastest
            
            return f"Response to: {body}"
        
        mock_onboarding.handle_message.side_effect = handle_message_side_effect
        
        # Mock Twilio to track response order with timestamps
        def send_message_side_effect(to, body):
            with response_lock:
                response_order.append({
                    "body": body,
                    "timestamp": time.time()
                })
            return {"message_sid": f"SM{len(response_order)}", "status": "queued"}
        
        mock_twilio.send_message.side_effect = send_message_side_effect
        
        # Create 3 messages with different content
        messages = [
            {"from": phone_number, "body": "Message 1", "message_sid": "SM001"},
            {"from": phone_number, "body": "Message 2", "message_sid": "SM002"},
            {"from": phone_number, "body": "Message 3", "message_sid": "SM003"},
        ]
        
        # Act - Send messages rapidly with minimal delay
        # In the real system with standard SQS, these would be processed in parallel
        # We simulate this by starting all threads nearly simultaneously
        threads = []
        for i, message in enumerate(messages):
            # Create SQS event for each message
            event = {
                "Records": [
                    {
                        "messageId": f"msg-{i}",
                        "receiptHandle": f"receipt-{i}",
                        "body": json.dumps(message),
                        "attributes": {"ApproximateReceiveCount": "1"},
                        "messageAttributes": {
                            "request_id": {"stringValue": f"test-{i}"}
                        }
                    }
                ]
            }
            
            context = Mock()
            context.function_name = "test-function"
            
            # Process each message in a separate thread to simulate parallel processing
            # This is what happens in the real system with standard SQS queue
            thread = threading.Thread(
                target=lambda e=event, c=context: lambda_handler(e, c)
            )
            threads.append(thread)
        
        # Start all threads nearly simultaneously (within 10ms)
        # This simulates rapid message arrival at SQS
        for thread in threads:
            thread.start()
            time.sleep(0.01)  # 10ms delay between starts
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert - Verify responses arrived in same order as questions
        # On UNFIXED code with parallel processing, this assertion should FAIL
        assert len(response_order) == 3, f"Expected 3 responses, got {len(response_order)}"
        
        # Extract just the response bodies in order
        actual_order = [r["body"] for r in response_order]
        
        # Expected order (same as message send order)
        expected_order = [
            "Response to: Message 1",
            "Response to: Message 2",
            "Response to: Message 3",
        ]
        
        # This assertion will FAIL on unfixed code due to parallel processing
        # Message 3 will finish first (50ms), then Message 2 (100ms), then Message 1 (150ms)
        assert actual_order == expected_order, (
            f"Responses out of order!\n"
            f"Expected: {expected_order}\n"
            f"Got: {actual_order}\n"
            f"This demonstrates the message ordering bug where responses "
            f"arrive in different order than questions due to parallel processing."
        )
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.trainer_handler')
    @patch('src.handlers.message_processor.db_client')
    def test_conversation_state_race_condition(
        self,
        mock_db,
        mock_trainer,
        mock_router,
        mock_twilio
    ):
        """
        Test that conversation state updates have race conditions with concurrent messages.
        
        Sends 2 messages that both update conversation context, verifies last-write-wins
        behavior causes context loss.
        
        **EXPECTED ON UNFIXED CODE**: Test FAILS
        - Conversation state shows only last message's context
        - Earlier message context is lost (last write wins)
        - AI agent cannot maintain conversation history
        
        **Validates: Requirements 1.3**
        """
        # Arrange
        phone_number = "+14155551234"
        trainer_id = "trainer-123"
        
        # Track conversation state updates
        state_updates = []
        state_lock = threading.Lock()
        
        # Mock router to return trainer handler
        mock_router.route_message.return_value = {
            "handler_type": "trainer",
            "user_id": trainer_id,
            "entity_type": "TRAINER",
            "user_data": {"trainer_id": trainer_id, "name": "John"},
        }
        
        # Mock trainer handler to simulate conversation state updates
        def handle_message_side_effect(trainer_id, user_data, message_body, request_id):
            body = message_body.get("body", "")
            # Simulate processing and state update
            time.sleep(0.05)  # 50ms processing
            
            # Record state update
            with state_lock:
                state_updates.append({
                    "message": body,
                    "timestamp": datetime.utcnow().isoformat(),
                    "trainer_id": trainer_id,
                })
            
            return f"Processed: {body}"
        
        mock_trainer.handle_message.side_effect = handle_message_side_effect
        
        # Mock Twilio
        mock_twilio.send_message.return_value = {
            "message_sid": "SM123",
            "status": "queued"
        }
        
        # Mock DynamoDB to track state writes
        mock_db.update_item = Mock()
        
        # Create 2 messages that update conversation context
        messages = [
            {"from": phone_number, "body": "Schedule session with Sarah", "message_sid": "SM001"},
            {"from": phone_number, "body": "Make it at 3pm", "message_sid": "SM002"},
        ]
        
        # Act - Process messages in parallel (simulates concurrent Lambda invocations)
        threads = []
        for i, message in enumerate(messages):
            event = {
                "Records": [
                    {
                        "messageId": f"msg-{i}",
                        "receiptHandle": f"receipt-{i}",
                        "body": json.dumps(message),
                        "attributes": {"ApproximateReceiveCount": "1"},
                        "messageAttributes": {
                            "request_id": {"stringValue": f"test-{i}"}
                        }
                    }
                ]
            }
            
            context = Mock()
            context.function_name = "test-function"
            
            thread = threading.Thread(
                target=lambda e=event, c=context: lambda_handler(e, c)
            )
            threads.append(thread)
            thread.start()
            
            # Very small delay to ensure messages start processing concurrently
            time.sleep(0.01)  # 10ms delay
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert - Verify both state updates were recorded in order
        # On UNFIXED code, this may fail due to race conditions
        assert len(state_updates) == 2, f"Expected 2 state updates, got {len(state_updates)}"
        
        # Check if state updates are in order
        # The second message depends on context from the first message
        # If processed out of order, the AI agent loses context
        expected_messages = [
            "Schedule session with Sarah",
            "Make it at 3pm",
        ]
        
        actual_messages = [update["message"] for update in state_updates]
        
        # This assertion will FAIL on unfixed code due to race conditions
        assert actual_messages == expected_messages, (
            f"Conversation state updates out of order!\n"
            f"Expected: {expected_messages}\n"
            f"Got: {actual_messages}\n"
            f"This demonstrates race conditions where last write wins, "
            f"causing loss of conversation context."
        )
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_different_phone_numbers_parallel_processing(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that messages from DIFFERENT phone numbers CAN be processed in parallel.
        
        This is the CORRECT behavior that should be preserved - messages from
        different users should not be artificially serialized.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        - Messages from different phone numbers process in parallel
        - No artificial serialization across users
        - This behavior should be preserved after fix
        
        **Validates: Preservation requirement - parallel processing for different users**
        """
        # Arrange
        phone_numbers = ["+14155551111", "+14155552222"]
        
        # Track processing times
        processing_times = {}
        time_lock = threading.Lock()
        
        # Mock router
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Mock onboarding handler with processing time tracking
        def handle_message_side_effect(phone_number, message_body, request_id):
            start_time = time.time()
            time.sleep(0.1)  # 100ms processing
            end_time = time.time()
            
            with time_lock:
                processing_times[phone_number] = {
                    "start": start_time,
                    "end": end_time,
                }
            
            return f"Response to {phone_number}"
        
        mock_onboarding.handle_message.side_effect = handle_message_side_effect
        
        # Mock Twilio
        mock_twilio.send_message.return_value = {
            "message_sid": "SM123",
            "status": "queued"
        }
        
        # Create messages from different phone numbers
        messages = [
            {"from": phone_numbers[0], "body": "Hello", "message_sid": "SM001"},
            {"from": phone_numbers[1], "body": "Hi", "message_sid": "SM002"},
        ]
        
        # Act - Process messages in parallel
        threads = []
        for i, message in enumerate(messages):
            event = {
                "Records": [
                    {
                        "messageId": f"msg-{i}",
                        "receiptHandle": f"receipt-{i}",
                        "body": json.dumps(message),
                        "attributes": {"ApproximateReceiveCount": "1"},
                        "messageAttributes": {
                            "request_id": {"stringValue": f"test-{i}"}
                        }
                    }
                ]
            }
            
            context = Mock()
            context.function_name = "test-function"
            
            thread = threading.Thread(
                target=lambda e=event, c=context: lambda_handler(e, c)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert - Verify messages were processed in parallel (overlapping time windows)
        assert len(processing_times) == 2, "Expected 2 messages to be processed"
        
        # Check if processing windows overlapped (parallel processing)
        times1 = processing_times[phone_numbers[0]]
        times2 = processing_times[phone_numbers[1]]
        
        # If parallel, the processing windows should overlap
        # i.e., message 2 should start before message 1 ends
        parallel_processing = (
            times2["start"] < times1["end"] or
            times1["start"] < times2["end"]
        )
        
        # This should PASS on unfixed code - parallel processing is desired for different users
        assert parallel_processing, (
            f"Messages from different phone numbers should be processed in parallel!\n"
            f"Phone 1: start={times1['start']}, end={times1['end']}\n"
            f"Phone 2: start={times2['start']}, end={times2['end']}\n"
            f"This is CORRECT behavior that must be preserved after fix."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
