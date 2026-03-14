#!/usr/bin/env python3
"""
Test script for Google Calendar integration.

This script tests the calendar integration by:
1. Checking if OAuth callback endpoint is accessible
2. Testing calendar tool functions
3. Verifying calendar sync service
"""

import sys
import os
import requests
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tools.calendar_tools import connect_calendar
from services.calendar_sync import CalendarSyncService
from models.dynamodb_client import DynamoDBClient
from config import settings


def test_oauth_endpoint():
    """Test if OAuth callback endpoint is accessible."""
    print("=" * 60)
    print("Testing OAuth Callback Endpoint")
    print("=" * 60)
    
    # Test with invalid state to verify endpoint exists
    oauth_url = settings.oauth_redirect_uri
    
    if not oauth_url:
        print("❌ OAUTH_REDIRECT_URI not configured")
        return False
    
    print(f"OAuth Redirect URI: {oauth_url}")
    
    try:
        # Try to access the endpoint (should return error page but 200 status)
        response = requests.get(
            oauth_url,
            params={"code": "test", "state": "test"},
            timeout=10,
            allow_redirects=False
        )
        
        if response.status_code in [200, 400]:
            print(f"✓ OAuth endpoint is accessible (status: {response.status_code})")
            return True
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to reach OAuth endpoint: {e}")
        return False


def test_connect_calendar_tool():
    """Test the connect_calendar tool function."""
    print("\n" + "=" * 60)
    print("Testing connect_calendar Tool")
    print("=" * 60)
    
    # Create a test trainer first
    dynamodb = DynamoDBClient(
        table_name=settings.dynamodb_table,
        endpoint_url=settings.aws_endpoint_url
    )
    
    test_trainer_id = "test-trainer-calendar-integration"
    
    # Create test trainer
    trainer_data = {
        "PK": f"TRAINER#{test_trainer_id}",
        "SK": "METADATA",
        "entity_type": "TRAINER",
        "trainer_id": test_trainer_id,
        "name": "Test Trainer",
        "phone_number": "+1234567890",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    
    try:
        dynamodb.dynamodb.put_item(
            TableName=settings.dynamodb_table,
            Item=trainer_data
        )
        print(f"✓ Created test trainer: {test_trainer_id}")
    except Exception as e:
        print(f"⚠ Could not create test trainer: {e}")
    
    # Test Google Calendar connection
    print("\nTesting Google Calendar connection...")
    result = connect_calendar(test_trainer_id, "google")
    
    if result.get("success"):
        oauth_url = result["data"]["oauth_url"]
        provider = result["data"]["provider"]
        expires_in = result["data"]["expires_in"]
        
        print(f"✓ OAuth URL generated successfully")
        print(f"  Provider: {provider}")
        print(f"  Expires in: {expires_in} seconds")
        print(f"  URL: {oauth_url[:80]}...")
        
        # Verify URL structure
        if "accounts.google.com/o/oauth2/v2/auth" in oauth_url:
            print("✓ OAuth URL has correct Google endpoint")
        else:
            print("❌ OAuth URL has incorrect endpoint")
            return False
            
        if settings.oauth_redirect_uri in oauth_url:
            print(f"✓ OAuth URL contains redirect URI")
        else:
            print(f"❌ OAuth URL missing redirect URI")
            return False
            
        return True
    else:
        print(f"❌ Failed to generate OAuth URL: {result.get('error')}")
        return False


def test_calendar_credentials():
    """Test if calendar credentials are configured."""
    print("\n" + "=" * 60)
    print("Testing Calendar Credentials")
    print("=" * 60)
    
    # Test Google credentials
    print("\nGoogle OAuth Credentials:")
    google_creds = settings.get_google_oauth_credentials()
    
    if google_creds["client_id"] and google_creds["client_secret"]:
        print(f"✓ Google credentials configured")
        print(f"  Client ID: {google_creds['client_id'][:20]}...")
        google_ok = True
    else:
        print("❌ Google credentials not configured")
        print("  Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        google_ok = False
    
    # Test Outlook credentials
    print("\nOutlook OAuth Credentials:")
    outlook_creds = settings.get_outlook_oauth_credentials()
    
    if outlook_creds["client_id"] and outlook_creds["client_secret"]:
        print(f"✓ Outlook credentials configured")
        print(f"  Client ID: {outlook_creds['client_id'][:20]}...")
        outlook_ok = True
    else:
        print("⚠ Outlook credentials not configured (optional)")
        outlook_ok = True  # Not required for Google Calendar test
    
    return google_ok


def test_calendar_sync_service():
    """Test calendar sync service initialization."""
    print("\n" + "=" * 60)
    print("Testing Calendar Sync Service")
    print("=" * 60)
    
    try:
        service = CalendarSyncService()
        print("✓ Calendar sync service initialized")
        
        # Test that service has required methods
        required_methods = ['create_event', 'update_event', 'delete_event']
        for method in required_methods:
            if hasattr(service, method):
                print(f"✓ Service has {method} method")
            else:
                print(f"❌ Service missing {method} method")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize calendar sync service: {e}")
        return False


def main():
    """Run all calendar integration tests."""
    print("\n" + "=" * 60)
    print("Google Calendar Integration Test Suite")
    print("=" * 60)
    print(f"Environment: {settings.environment}")
    print(f"DynamoDB Table: {settings.dynamodb_table}")
    print(f"OAuth Redirect URI: {settings.oauth_redirect_uri}")
    print("=" * 60)
    
    results = {
        "OAuth Endpoint": test_oauth_endpoint(),
        "Calendar Credentials": test_calendar_credentials(),
        "Calendar Sync Service": test_calendar_sync_service(),
        "Connect Calendar Tool": test_connect_calendar_tool(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        print("\nNext steps:")
        print("1. Configure Google OAuth redirect URIs in Google Console")
        print("2. Test OAuth flow by connecting a calendar via WhatsApp")
        print("3. Schedule a session and verify it appears in Google Calendar")
    else:
        print("❌ Some tests failed")
        print("\nPlease fix the issues above before proceeding")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
