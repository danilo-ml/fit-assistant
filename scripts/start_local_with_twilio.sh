#!/bin/bash

# Complete startup script for local testing with Twilio Sandbox
# This script starts all services and guides you through the setup

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     FitAgent - Local Testing with Twilio Sandbox            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Check if ngrok is installed
echo -e "${YELLOW}[1/6] Checking prerequisites...${NC}"
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}❌ ngrok is not installed${NC}"
    echo ""
    echo "Install ngrok:"
    echo "  macOS:  brew install ngrok"
    echo "  Other:  https://ngrok.com/download"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ ngrok is installed${NC}"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found, copying from .env.example${NC}"
    cp .env.example .env
    echo -e "${RED}⚠️  Please edit .env and add your Twilio credentials:${NC}"
    echo "   - TWILIO_ACCOUNT_SID"
    echo "   - TWILIO_AUTH_TOKEN"
    echo "   - TWILIO_WHATSAPP_NUMBER"
    echo ""
    echo "Then run this script again."
    exit 1
fi
echo -e "${GREEN}✓ .env file exists${NC}"

# Check if Twilio credentials are set
if grep -q "your_twilio_account_sid" .env || grep -q "your_twilio_auth_token_here" .env; then
    echo -e "${YELLOW}⚠️  Twilio credentials not configured in .env${NC}"
    echo ""
    echo "Please update .env with your Twilio credentials:"
    echo "  1. Go to: https://console.twilio.com/"
    echo "  2. Copy your Account SID and Auth Token"
    echo "  3. Update TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env"
    echo ""
    read -p "Press Enter after updating .env, or Ctrl+C to exit..."
fi

echo ""
echo -e "${YELLOW}[2/6] Starting Docker services...${NC}"
docker-compose up -d

echo ""
echo -e "${YELLOW}[3/6] Waiting for services to be ready...${NC}"
sleep 10

# Check if API is responding
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is ready${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -n "."
    sleep 1
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}❌ API failed to start${NC}"
    echo "Check logs: docker logs fitagent-api"
    exit 1
fi

# Check if LocalStack is ready
if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ LocalStack is ready${NC}"
else
    echo -e "${YELLOW}⚠️  LocalStack is starting (this is normal)${NC}"
fi

echo ""
echo -e "${YELLOW}[4/6] Starting ngrok tunnel...${NC}"
echo -e "${BLUE}Starting ngrok in background...${NC}"

# Kill any existing ngrok processes
pkill ngrok 2>/dev/null || true
sleep 2

# Start ngrok in background
ngrok http 8000 > /dev/null &
NGROK_PID=$!
sleep 3

# Get ngrok URL
NGROK_URL=""
for i in {1..10}; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | \
        python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")
    
    if [ ! -z "$NGROK_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}❌ Failed to get ngrok URL${NC}"
    echo "Try running manually: ngrok http 8000"
    exit 1
fi

echo -e "${GREEN}✓ ngrok tunnel started${NC}"
echo -e "${BLUE}   URL: ${NGROK_URL}${NC}"

echo ""
echo -e "${YELLOW}[5/6] Configuration Instructions${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Your ngrok URL:${NC}"
echo -e "${BLUE}${NGROK_URL}/webhook${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "📱 Configure Twilio Sandbox:"
echo ""
echo "1. Go to: ${BLUE}https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn${NC}"
echo ""
echo "2. Join Sandbox (if first time):"
echo "   - Send the join code to the Twilio WhatsApp number"
echo "   - Example: 'join happy-dog' to +1 415 523 8886"
echo ""
echo "3. Configure Webhook:"
echo "   - Find 'Sandbox Configuration'"
echo "   - Set 'When a message comes in' to:"
echo -e "     ${GREEN}${NGROK_URL}/webhook${NC}"
echo "   - Method: HTTP POST"
echo "   - Click 'Save'"
echo ""
echo -e "${YELLOW}Press Enter after configuring Twilio...${NC}"
read

echo ""
echo -e "${YELLOW}[6/6] Testing setup...${NC}"
echo ""
echo "Send a test message from WhatsApp:"
echo -e "${BLUE}  'Hello'${NC}"
echo ""
echo "You should see logs below..."
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Watching API logs (Ctrl+C to stop):${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Follow logs
docker logs -f fitagent-api 2>&1 | grep --line-buffered -E "Webhook|Processing|ERROR|WARNING|INFO.*message"
