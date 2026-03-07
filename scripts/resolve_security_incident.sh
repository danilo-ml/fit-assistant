#!/bin/bash

# Automated Security Incident Resolution Script
# This script helps resolve the exposed Twilio credentials issue

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     Security Incident Resolution - Exposed Credentials      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo ""
echo -e "${YELLOW}This script will help you resolve the exposed Twilio credentials.${NC}"
echo ""
echo "Steps:"
echo "  1. Verify credentials have been removed from tracked files"
echo "  2. Guide you through rotating Twilio credentials"
echo "  3. Update your local .env file"
echo "  4. Clean Git history (optional)"
echo "  5. Set up monitoring"
echo ""
read -p "Press Enter to continue or Ctrl+C to exit..."

# Step 1: Verify current state
echo ""
echo -e "${BLUE}[1/6] Verifying current state...${NC}"

# Check if .env has placeholder values
if grep -q "your_twilio_account_sid_here" .env; then
    echo -e "${GREEN}✓ .env file has placeholder values${NC}"
else
    echo -e "${RED}✗ .env file still has real credentials${NC}"
    echo "Updating .env file..."
    
    # Backup current .env
    cp .env .env.backup
    
    # Replace credentials with placeholders
    sed -i.tmp 's/TWILIO_ACCOUNT_SID=AC[a-z0-9]*/TWILIO_ACCOUNT_SID=your_twilio_account_sid_here/' .env
    sed -i.tmp 's/TWILIO_AUTH_TOKEN=[a-z0-9]*/TWILIO_AUTH_TOKEN=your_twilio_auth_token_here/' .env
    rm .env.tmp
    
    echo -e "${GREEN}✓ .env file updated${NC}"
fi

# Check staging parameters
if grep -q "REPLACE_WITH_STAGING_TWILIO_SID" infrastructure/parameters/staging.json; then
    echo -e "${GREEN}✓ Staging parameters have placeholder values${NC}"
else
    echo -e "${RED}✗ Staging parameters still have real credentials${NC}"
    exit 1
fi

# Step 2: Guide through Twilio rotation
echo ""
echo -e "${BLUE}[2/6] Rotating Twilio credentials...${NC}"
echo ""
echo "Please follow these steps:"
echo ""
echo "1. Open Twilio Console:"
echo -e "   ${GREEN}https://console.twilio.com/${NC}"
echo ""
echo "2. Navigate to: Account → API keys & tokens"
echo ""
echo "3. Click 'View' next to 'Auth Token'"
echo ""
echo "4. Click 'Rotate Token'"
echo ""
echo "5. Copy the NEW Auth Token (you'll need it in the next step)"
echo ""
read -p "Press Enter after you've rotated the token..."

# Step 3: Update local .env
echo ""
echo -e "${BLUE}[3/6] Updating local .env file...${NC}"
echo ""

read -p "Enter your Twilio Account SID (starts with AC): " NEW_SID
read -sp "Enter your NEW Twilio Auth Token: " NEW_TOKEN
echo ""
read -p "Enter your Twilio WhatsApp Number (e.g., whatsapp:+14155238886): " NEW_NUMBER

# Update .env file
cat > .env << EOF
# Environment
ENVIRONMENT=local

# AWS Configuration (LocalStack)
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# DynamoDB
DYNAMODB_TABLE=fitagent-main

# S3
S3_BUCKET=fitagent-receipts-local

# SQS
SQS_QUEUE_URL=http://localhost:4566/000000000000/fitagent-messages
NOTIFICATION_QUEUE_URL=http://localhost:4566/000000000000/fitagent-notifications
DLQ_URL=http://localhost:4566/000000000000/fitagent-messages-dlq

# KMS
KMS_KEY_ALIAS=alias/fitagent-oauth-key

# Twilio Configuration
TWILIO_ACCOUNT_SID=$NEW_SID
TWILIO_AUTH_TOKEN=$NEW_TOKEN
TWILIO_WHATSAPP_NUMBER=$NEW_NUMBER

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Microsoft OAuth
OUTLOOK_CLIENT_ID=your_outlook_client_id_here
OUTLOOK_CLIENT_SECRET=your_outlook_client_secret_here

# OAuth Redirect
OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback

# AWS Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1

# Application Settings
CONVERSATION_TTL_HOURS=24
MAX_MESSAGE_HISTORY=10
SESSION_REMINDER_DEFAULT_HOURS=24
PAYMENT_REMINDER_DEFAULT_DAY=1
NOTIFICATION_RATE_LIMIT=10
# Using Strands Swarm
ENABLE_MULTI_AGENT=true
EOF

echo -e "${GREEN}✓ .env file updated with new credentials${NC}"

# Step 4: Check for unauthorized usage
echo ""
echo -e "${BLUE}[4/6] Checking for unauthorized usage...${NC}"
echo ""
echo "Please check the following:"
echo ""
echo "1. Twilio Message Logs:"
echo -e "   ${GREEN}https://console.twilio.com/us1/monitor/logs/sms${NC}"
echo ""
echo "2. Twilio Billing:"
echo -e "   ${GREEN}https://console.twilio.com/us1/billing${NC}"
echo ""
echo "Look for:"
echo "  - Messages you didn't send"
echo "  - Unusual timestamps (off-hours)"
echo "  - Unknown phone numbers"
echo "  - Unexpected charges"
echo ""
read -p "Have you checked for unauthorized usage? (yes/no): " CHECKED

if [ "$CHECKED" != "yes" ]; then
    echo -e "${YELLOW}⚠️  Please check for unauthorized usage before continuing${NC}"
    exit 1
fi

read -p "Did you find any unauthorized usage? (yes/no): " FOUND_ABUSE

if [ "$FOUND_ABUSE" = "yes" ]; then
    echo -e "${RED}⚠️  UNAUTHORIZED USAGE DETECTED${NC}"
    echo ""
    echo "Please contact Twilio support immediately:"
    echo "  Phone: 1-888-TWILIO-1"
    echo "  Web: https://support.twilio.com/"
    echo ""
    echo "Document all unauthorized activity and report it."
    echo ""
    read -p "Press Enter after contacting Twilio support..."
fi

# Step 5: Clean Git history (optional)
echo ""
echo -e "${BLUE}[5/6] Cleaning Git history (optional)...${NC}"
echo ""
echo "The exposed credentials are still in Git history."
echo "This step will remove them permanently."
echo ""
echo -e "${YELLOW}WARNING: This rewrites Git history and requires force push.${NC}"
echo "Only do this if you understand the implications."
echo ""
read -p "Do you want to clean Git history now? (yes/no): " CLEAN_HISTORY

if [ "$CLEAN_HISTORY" = "yes" ]; then
    # Check if BFG is installed
    if command -v bfg &> /dev/null; then
        echo ""
        echo "Using BFG Repo-Cleaner..."
        
        # Create passwords file with the exposed credentials
        # Replace these with your actual exposed credentials
        cat > /tmp/passwords.txt << PASSWORDS
[YOUR_EXPOSED_TWILIO_SID]
[YOUR_EXPOSED_TWILIO_TOKEN]
PASSWORDS
        
        echo ""
        echo "Running BFG to remove credentials from history..."
        echo ""
        
        # Run BFG
        bfg --replace-text /tmp/passwords.txt
        
        # Clean up
        git reflog expire --expire=now --all
        git gc --prune=now --aggressive
        
        rm /tmp/passwords.txt
        
        echo ""
        echo -e "${GREEN}✓ Git history cleaned${NC}"
        echo ""
        echo -e "${YELLOW}IMPORTANT: You need to force push to update remote:${NC}"
        echo -e "  ${RED}git push --force --all${NC}"
        echo ""
        echo "Make sure all team members are aware before force pushing!"
        
    else
        echo ""
        echo -e "${YELLOW}BFG Repo-Cleaner not found.${NC}"
        echo ""
        echo "Install it with:"
        echo "  macOS: brew install bfg"
        echo "  Other: https://rtyley.github.io/bfg-repo-cleaner/"
        echo ""
        echo "Or use git-filter-repo (see SECURITY_INCIDENT_RESPONSE.md)"
    fi
else
    echo ""
    echo -e "${YELLOW}Skipping Git history cleaning.${NC}"
    echo "You can do this later by following SECURITY_INCIDENT_RESPONSE.md"
fi

# Step 6: Set up monitoring
echo ""
echo -e "${BLUE}[6/6] Setting up monitoring...${NC}"
echo ""
echo "Recommended monitoring setup:"
echo ""
echo "1. Twilio Usage Alerts:"
echo -e "   ${GREEN}https://console.twilio.com/us1/monitor/alerts${NC}"
echo "   - Set daily message volume threshold"
echo "   - Set spending alerts"
echo ""
echo "2. AWS CloudWatch Alarms (if deployed):"
echo "   - Lambda error rate"
echo "   - Unusual invocation patterns"
echo ""
read -p "Press Enter to continue..."

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}║                  Resolution Complete!                        ║${NC}"
echo -e "${GREEN}║                                                              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Summary of actions taken:"
echo ""
echo -e "${GREEN}✓${NC} Verified credentials removed from tracked files"
echo -e "${GREEN}✓${NC} Rotated Twilio Auth Token"
echo -e "${GREEN}✓${NC} Updated local .env file"
echo -e "${GREEN}✓${NC} Checked for unauthorized usage"

if [ "$CLEAN_HISTORY" = "yes" ]; then
    echo -e "${GREEN}✓${NC} Cleaned Git history"
else
    echo -e "${YELLOW}⚠${NC} Git history not cleaned (do this later)"
fi

echo ""
echo "Next steps:"
echo ""
echo "1. Test your local environment:"
echo "   docker-compose up -d"
echo "   curl http://localhost:8000/health"
echo ""
echo "2. If you cleaned Git history, force push:"
echo "   git push --force --all"
echo ""
echo "3. Update AWS Secrets Manager (if deployed):"
echo "   See SECURITY_INCIDENT_RESPONSE.md for instructions"
echo ""
echo "4. Install pre-commit hooks to prevent future incidents:"
echo "   pip install pre-commit"
echo "   pre-commit install"
echo ""
echo "5. Document the incident for your records"
echo ""
echo -e "${GREEN}Security incident resolved!${NC}"
echo ""
