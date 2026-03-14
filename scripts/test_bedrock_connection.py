#!/usr/bin/env python3
"""
Test script to verify AWS Bedrock connection is working.
This script tests the Bedrock client directly without going through the full message flow.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services.strands_agent_service import StrandsAgentService
from src.utils.logging import get_logger

logger = get_logger(__name__)


def test_bedrock_connection():
    """Test Bedrock connection with a simple message."""
    print("=" * 60)
    print("Testing AWS Bedrock Connection")
    print("=" * 60)
    print()
    
    try:
        # Initialize Strands Agent Service
        print("1. Initializing Strands Agent Service...")
        agent_service = StrandsAgentService()
        print(f"   ✅ Agent service initialized")
        print(f"   - Model: {agent_service.model_id}")
        print(f"   - Region: {agent_service.region}")
        print()
        
        # Test with a simple message
        print("2. Sending test message to Bedrock...")
        test_trainer_id = "test-trainer-123"
        test_message = "Olá! Você pode me ajudar?"
        
        result = agent_service.process_message(
            trainer_id=test_trainer_id,
            message=test_message,
        )
        
        print(f"   ✅ Message processed successfully")
        print()
        
        # Display results
        print("3. Results:")
        print(f"   - Success: {result.get('success')}")
        print(f"   - Response: {result.get('response', 'N/A')[:200]}")
        if result.get('error'):
            print(f"   - Error: {result.get('error')}")
        print()
        
        if result.get('success'):
            print("=" * 60)
            print("✅ BEDROCK CONNECTION TEST PASSED")
            print("=" * 60)
            return 0
        else:
            print("=" * 60)
            print("❌ BEDROCK CONNECTION TEST FAILED")
            print("=" * 60)
            return 1
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        print()
        print("=" * 60)
        print("❌ BEDROCK CONNECTION TEST FAILED")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_bedrock_connection())
