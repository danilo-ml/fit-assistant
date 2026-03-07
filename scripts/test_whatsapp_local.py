#!/usr/bin/env python3
"""
Local WhatsApp testing script for FitAgent.

This script simulates WhatsApp messages by calling the local API endpoints.
It's useful for testing the complete flow without needing actual Twilio webhooks.
"""

import requests
import json
import time
from typing import Dict, Any


API_URL = "http://localhost:8000"


def test_message(phone_number: str, message: str) -> Dict[str, Any]:
    """
    Send a test message to the local API.
    
    Args:
        phone_number: Phone number in E.164 format (e.g., +1234567890)
        message: Message text to send
        
    Returns:
        API response as dictionary
    """
    print(f"\n{'='*60}")
    print(f"📱 From: {phone_number}")
    print(f"💬 Message: {message}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{API_URL}/test/process-message",
            data={
                "phone_number": phone_number,
                "message": message,
                "message_sid": f"TEST{int(time.time())}"
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✅ Status: {result.get('status')}")
        print(f"\n📤 Response:")
        print(json.dumps(result, indent=2))
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error: {e}")
        return {"error": str(e)}


def check_api_health() -> bool:
    """Check if the API is running."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Run test scenarios."""
    print("\n" + "="*60)
    print("🤖 FitAgent WhatsApp Local Testing")
    print("="*60)
    
    # Check API health
    print("\n🔍 Checking API status...")
    if not check_api_health():
        print("❌ API is not running at", API_URL)
        print("Please start services with: docker-compose up -d")
        return
    
    print("✅ API is running")
    
    # Test scenarios
    scenarios = [
        {
            "name": "Trainer Onboarding",
            "phone": "+1234567890",
            "message": "Hello, I want to register as a trainer"
        },
        {
            "name": "Register Student",
            "phone": "+1234567890",
            "message": "Register student John Doe, phone +1987654321, email john@example.com"
        },
        {
            "name": "View Students",
            "phone": "+1234567890",
            "message": "Show me all my students"
        },
        {
            "name": "Schedule Session",
            "phone": "+1234567890",
            "message": "Schedule a session with John tomorrow at 3pm for 1 hour"
        },
        {
            "name": "Student Query",
            "phone": "+1987654321",
            "message": "What are my upcoming sessions?"
        },
        {
            "name": "Register Payment",
            "phone": "+1234567890",
            "message": "Register payment from John for $50"
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n\n{'#'*60}")
        print(f"# Test {i}/{len(scenarios)}: {scenario['name']}")
        print(f"{'#'*60}")
        
        test_message(scenario["phone"], scenario["message"])
        
        # Small delay between tests
        if i < len(scenarios):
            time.sleep(2)
    
    print("\n\n" + "="*60)
    print("✅ Testing Complete!")
    print("="*60)
    print("\n📊 Useful Commands:")
    print("  - View API logs: docker logs -f fitagent-api")
    print("  - View LocalStack logs: docker logs -f fitagent-localstack")
    print("  - Check DynamoDB data:")
    print("    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \\")
    print("    aws --endpoint-url=http://localhost:4566 \\")
    print("    dynamodb scan --table-name fitagent-main --region us-east-1")
    print()


if __name__ == "__main__":
    main()
