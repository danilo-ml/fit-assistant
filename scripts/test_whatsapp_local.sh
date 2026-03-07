#!/bin/bash

# Test script for simulating WhatsApp messages locally
# This script sends test messages to the local API to simulate Twilio webhooks

set -e

API_URL="http://localhost:8000"
PHONE_NUMBER="+1234567890"

echo "========================================="
echo "FitAgent WhatsApp Local Testing"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to test direct message processing (bypasses webhook/SQS)
test_direct_message() {
    local phone=$1
    local message=$2
    
    echo -e "${BLUE}Testing direct message processing...${NC}"
    echo "Phone: $phone"
    echo "Message: $message"
    echo ""
    
    response=$(curl -s -X POST "$API_URL/test/process-message" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "phone_number=$phone" \
        -d "message=$message" \
        -d "message_sid=TEST$(date +%s)")
    
    echo -e "${GREEN}Response:${NC}"
    echo "$response" | python -m json.tool 2>/dev/null || echo "$response"
    echo ""
}

# Function to test webhook endpoint (simulates Twilio)
test_webhook() {
    local phone=$1
    local message=$2
    
    echo -e "${BLUE}Testing webhook endpoint...${NC}"
    echo "Phone: $phone"
    echo "Message: $message"
    echo ""
    
    # Note: This will fail signature validation unless you have valid Twilio credentials
    # For local testing, use test_direct_message instead
    
    response=$(curl -s -X POST "$API_URL/webhook" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -H "X-Twilio-Signature: test-signature" \
        -d "MessageSid=SM$(date +%s)" \
        -d "From=whatsapp:$phone" \
        -d "To=whatsapp:+14155238886" \
        -d "Body=$message" \
        -d "NumMedia=0")
    
    echo -e "${GREEN}Response:${NC}"
    echo "$response"
    echo ""
}

# Check if API is running
echo -e "${YELLOW}Checking if API is running...${NC}"
if ! curl -s "$API_URL/health" > /dev/null; then
    echo "ERROR: API is not running at $API_URL"
    echo "Please start the services with: docker-compose up -d"
    exit 1
fi
echo -e "${GREEN}✓ API is running${NC}"
echo ""

# Test scenarios
echo "========================================="
echo "Test Scenario 1: New Trainer Onboarding"
echo "========================================="
test_direct_message "+1234567890" "Hello, I want to register as a trainer"

echo "========================================="
echo "Test Scenario 2: Register Student"
echo "========================================="
test_direct_message "+1234567890" "Register student John Doe, phone +1987654321"

echo "========================================="
echo "Test Scenario 3: Schedule Session"
echo "========================================="
test_direct_message "+1234567890" "Schedule session with John tomorrow at 3pm"

echo "========================================="
echo "Test Scenario 4: Student Query"
echo "========================================="
test_direct_message "+1987654321" "What are my upcoming sessions?"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Testing Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Tips:"
echo "  - View API logs: docker logs -f fitagent-api"
echo "  - View LocalStack logs: docker logs -f fitagent-localstack"
echo "  - Check DynamoDB: AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name fitagent-main --region us-east-1"
echo ""
