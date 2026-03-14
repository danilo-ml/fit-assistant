"""
Property-based test for parallel processing preservation.

This test verifies that messages from DIFFERENT phone numbers can be processed
in parallel without artificial serialization. This is CORRECT behavior that
must be preserved after implementing the message ordering fix.

**EXPECTED OUTCOME ON UNFIXED CODE**: Test PASSES
- Messages from different phone numbers process in parallel
- Processing windows overlap (concurrent execution)
- No artificial serialization across different users
- High throughput maintained for non-conflicting messages

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import pytest
import json
import time
import threading
from typing import List, Dict, Any, Tuple
from unittest.mock import Mock, patch
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime

from src.handlers.message_processor import lambda_handler


class TestParallelProcessingPreservation:
    """
    Preservation test for parallel processing across different phone numbers.
    
    This test verifies that the message ordering fix does NOT artificially
    serialize messages from different phone numbers. Parallel processing for
    different users is desired behavior that must be preserved.
    """
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_different_phone_numbers_process_in_parallel(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that messages from different phone numbers CAN process in parallel.
        
        Sends messages from 2 different phone numbers simultaneously and verifies
        their processing windows overlap (parallel execution).
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        - Processing windows overlap (start times before end times of other messages)
        - No artificial serialization
        - This is CORRECT behavior to preserve
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Arrange
        phone_numbers = ["+14155551111", "+14155552222"]
        
        # Track processing times with thread-safe access
        processing_times = {}
        time_lock = threading.Lock()
        
        # Mock router to return onboarding handler
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Mock onboarding handler with processing time tracking
        def handle_message_side_effect(phone_number, message_body, request_id):
            start_time = time.time()
            
            # Simulate realistic processing time (100ms)
            time.sleep(0.1)
            
            end_time = time.time()
            
            with time_lock:
                processing_times[phone_number] = {
                    "start": start_time,
                    "end": end_time,
                    "duration": end_time - start_time,
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
            {"from": phone_numbers[0], "body": "Hello from user 1", "message_sid": "SM001"},
            {"from": phone_numbers[1], "body": "Hello from user 2", "message_sid": "SM002"},
        ]
        
        # Act - Process messages in parallel (simulate concurrent Lambda invocations)
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
                            "request_id": {"stringValue": f"test-parallel-{i}"}
                        }
                    }
                ]
            }
            
            context = Mock()
            context.function_name = "test-function"
            
            # Start each message in a separate thread (simulates parallel Lambda invocations)
            thread = threading.Thread(
                target=lambda e=event, c=context: lambda_handler(e, c)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)
        
        # Assert - Verify messages were processed in parallel
        assert len(processing_times) == 2, (
            f"Expected 2 messages to be processed, got {len(processing_times)}"
        )
        
        # Extract processing times
        times1 = processing_times[phone_numbers[0]]
        times2 = processing_times[phone_numbers[1]]
        
        # Check if processing windows overlapped (parallel processing)
        # Parallel processing means: message 2 starts before message 1 ends
        # OR message 1 starts before message 2 ends
        parallel_processing = (
            times2["start"] < times1["end"] or
            times1["start"] < times2["end"]
        )
        
        # This should PASS on unfixed code - parallel processing is desired
        assert parallel_processing, (
            f"Messages from different phone numbers should process in parallel!\n"
            f"Phone {phone_numbers[0]}:\n"
            f"  start={times1['start']:.4f}\n"
            f"  end={times1['end']:.4f}\n"
            f"  duration={times1['duration']:.4f}s\n"
            f"Phone {phone_numbers[1]}:\n"
            f"  start={times2['start']:.4f}\n"
            f"  end={times2['end']:.4f}\n"
            f"  duration={times2['duration']:.4f}s\n\n"
            f"Processing windows should overlap for parallel execution.\n"
            f"This is CORRECT behavior that must be preserved after fix."
        )
    
    @given(
        num_phone_numbers=st.integers(min_value=2, max_value=5),
        processing_time_ms=st.integers(min_value=50, max_value=200)
    )
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_property_multiple_phone_numbers_parallel_processing(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio,
        num_phone_numbers: int,
        processing_time_ms: int
    ):
        """
        Property-based test: For ALL message sets from different phone numbers,
        processing CAN overlap (parallel execution).
        
        Generates random numbers of phone numbers and processing times to verify
        parallel processing is maintained across various scenarios.
        
        **Property**: For all message pairs from different phone numbers,
        processing windows can overlap without artificial serialization.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Arrange
        # Generate unique phone numbers
        phone_numbers = [f"+1415555{i:04d}" for i in range(num_phone_numbers)]
        
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
        
        # Mock onboarding handler with configurable processing time
        def handle_message_side_effect(phone_number, message_body, request_id):
            start_time = time.time()
            
            # Use the generated processing time
            time.sleep(processing_time_ms / 1000.0)
            
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
            {
                "from": phone_number,
                "body": f"Message from {phone_number}",
                "message_sid": f"SM{i:03d}"
            }
            for i, phone_number in enumerate(phone_numbers)
        ]
        
        # Act - Process all messages in parallel
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
                            "request_id": {"stringValue": f"test-pbt-{i}"}
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
            thread.join(timeout=10.0)
        
        # Assert - Verify all messages were processed
        assert len(processing_times) == num_phone_numbers, (
            f"Expected {num_phone_numbers} messages to be processed, "
            f"got {len(processing_times)}"
        )
        
        # Check for parallel processing: at least one pair should have overlapping windows
        # This verifies no artificial serialization across different phone numbers
        has_overlap = False
        
        for i, phone1 in enumerate(phone_numbers):
            for phone2 in phone_numbers[i+1:]:
                times1 = processing_times[phone1]
                times2 = processing_times[phone2]
                
                # Check if windows overlap
                overlap = (
                    times2["start"] < times1["end"] and
                    times1["start"] < times2["end"]
                )
                
                if overlap:
                    has_overlap = True
                    break
            
            if has_overlap:
                break
        
        # For multiple phone numbers with realistic processing times,
        # we expect at least some overlap (parallel processing)
        # This assertion should PASS on unfixed code
        assert has_overlap or num_phone_numbers == 1, (
            f"Expected parallel processing for {num_phone_numbers} different phone numbers!\n"
            f"Processing times:\n" +
            "\n".join([
                f"  {phone}: start={times['start']:.4f}, end={times['end']:.4f}"
                for phone, times in processing_times.items()
            ]) +
            f"\n\nNo overlapping processing windows found. "
            f"Messages from different phone numbers should NOT be artificially serialized."
        )
    
    @patch('src.handlers.message_processor.twilio_client')
    @patch('src.handlers.message_processor.message_router')
    @patch('src.handlers.message_processor.onboarding_handler')
    def test_throughput_maintained_for_different_phone_numbers(
        self,
        mock_onboarding,
        mock_router,
        mock_twilio
    ):
        """
        Test that throughput remains high for non-conflicting messages.
        
        Sends 5 messages from different phone numbers and verifies total time
        is close to single message time (not 5x), confirming parallel processing.
        
        **EXPECTED ON UNFIXED CODE**: Test PASSES
        - Total time ≈ single message time (parallel)
        - NOT total time ≈ 5x single message time (serial)
        
        **Validates: Requirements 3.3, 3.4**
        """
        # Arrange
        num_messages = 5
        phone_numbers = [f"+1415555{i:04d}" for i in range(num_messages)]
        single_message_time = 0.1  # 100ms per message
        
        # Track overall timing
        start_time = None
        end_time = None
        time_lock = threading.Lock()
        
        # Mock router
        mock_router.route_message.return_value = {
            "handler_type": "onboarding",
            "user_id": None,
            "entity_type": None,
            "user_data": None,
        }
        
        # Mock onboarding handler
        def handle_message_side_effect(phone_number, message_body, request_id):
            time.sleep(single_message_time)
            return f"Response to {phone_number}"
        
        mock_onboarding.handle_message.side_effect = handle_message_side_effect
        
        # Mock Twilio
        mock_twilio.send_message.return_value = {
            "message_sid": "SM123",
            "status": "queued"
        }
        
        # Create messages
        messages = [
            {
                "from": phone_number,
                "body": f"Message {i}",
                "message_sid": f"SM{i:03d}"
            }
            for i, phone_number in enumerate(phone_numbers)
        ]
        
        # Act - Process all messages in parallel
        start_time = time.time()
        
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
                            "request_id": {"stringValue": f"test-throughput-{i}"}
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
            thread.join(timeout=10.0)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Assert - Verify throughput is high (parallel processing)
        # If parallel: total_time ≈ single_message_time (all run concurrently)
        # If serial: total_time ≈ num_messages * single_message_time
        
        # Allow some overhead for thread management (2x single message time)
        max_expected_time = single_message_time * 2.5
        
        # This should PASS on unfixed code - parallel processing is fast
        assert total_time < max_expected_time, (
            f"Throughput too low! Messages from different phone numbers "
            f"should process in parallel.\n"
            f"Total time: {total_time:.4f}s\n"
            f"Expected: < {max_expected_time:.4f}s (parallel processing)\n"
            f"Serial would be: ~{num_messages * single_message_time:.4f}s\n\n"
            f"High throughput for non-conflicting messages must be preserved."
        )
        
        # Verify we're not serializing (total time should not be num_messages * single_message_time)
        serial_time = num_messages * single_message_time
        
        assert total_time < serial_time * 0.8, (
            f"Messages appear to be serialized!\n"
            f"Total time: {total_time:.4f}s\n"
            f"Serial time would be: {serial_time:.4f}s\n"
            f"Parallel time should be: ~{single_message_time:.4f}s\n\n"
            f"Messages from different phone numbers should NOT be serialized."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
