#!/bin/bash
# Start FitAgent local environment with AWS SSO for Bedrock

set -e

PROFILE="danilosousa"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}=========================================="
echo "FitAgent - Start with AWS SSO"
echo -e "==========================================${NC}"
echo ""

# Step 1: Check prerequisites
echo -e "${BLUE}[1/5] Checking prerequisites...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    echo "Install it from: https://aws.amazon.com/cli/"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ All prerequisites installed${NC}"
echo ""

# Step 2: Check/Login to AWS SSO
echo -e "${BLUE}[2/5] Checking AWS SSO session...${NC}"

if ! aws sts get-caller-identity --profile $PROFILE &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to AWS SSO${NC}"
    echo ""
    echo -e "${BLUE}Please complete AWS SSO login in your browser...${NC}"
    echo ""
    
    # Try to login
    aws sso login --profile $PROFILE
    
    # Check if login was successful
    if ! aws sts get-caller-identity --profile $PROFILE &> /dev/null; then
        echo ""
        echo -e "${RED}❌ AWS SSO login failed or was cancelled${NC}"
        echo ""
        echo "If you haven't configured SSO yet, run:"
        echo "  aws configure sso --profile $PROFILE"
        echo ""
        echo "If you're having issues, check:"
        echo "  1. Your browser allowed the SSO page to open"
        echo "  2. You completed the authorization in the browser"
        echo "  3. Your SSO configuration is correct"
        exit 1
    fi
fi

echo -e "${GREEN}✅ AWS SSO session is active${NC}"
echo ""

# Step 3: Export credentials
echo -e "${BLUE}[3/5] Exporting AWS credentials...${NC}"

CREDS=$(aws configure export-credentials --profile $PROFILE --format env)

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to export credentials${NC}"
    exit 1
fi

# Parse credentials
export BEDROCK_AWS_ACCESS_KEY_ID=$(echo "$CREDS" | grep AWS_ACCESS_KEY_ID | cut -d'=' -f2)
export BEDROCK_AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | grep AWS_SECRET_ACCESS_KEY | cut -d'=' -f2)
export BEDROCK_AWS_SESSION_TOKEN=$(echo "$CREDS" | grep AWS_SESSION_TOKEN | cut -d'=' -f2)
EXPIRATION=$(echo "$CREDS" | grep AWS_CREDENTIAL_EXPIRATION | cut -d'=' -f2)

# Save to .env.bedrock
cat > .env.bedrock << EOF
# AWS SSO Temporary Credentials
# Generated: $(date)
# Expires: $EXPIRATION
# Profile: $PROFILE

BEDROCK_AWS_ACCESS_KEY_ID=$BEDROCK_AWS_ACCESS_KEY_ID
BEDROCK_AWS_SECRET_ACCESS_KEY=$BEDROCK_AWS_SECRET_ACCESS_KEY
BEDROCK_AWS_SESSION_TOKEN=$BEDROCK_AWS_SESSION_TOKEN
EOF

echo -e "${GREEN}✅ Credentials exported and saved to .env.bedrock${NC}"
echo -e "${YELLOW}   Expires at: $EXPIRATION${NC}"
echo ""

# Step 4: Create .env if it doesn't exist
echo -e "${BLUE}[4/5] Checking environment configuration...${NC}"

if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example${NC}"
    cp .env.example .env
fi

echo -e "${GREEN}✅ Environment configured${NC}"
echo ""

# Step 5: Start Docker services
echo -e "${BLUE}[5/5] Starting Docker services...${NC}"
echo ""

# Stop any running containers first
docker-compose down 2>/dev/null || true

# Start services with SSO credentials
docker-compose up -d

echo ""
echo -e "${GREEN}✅ Services started successfully!${NC}"
echo ""

# Wait for services to be ready
echo -e "${BLUE}Waiting for services to be ready...${NC}"
sleep 5

# Check health
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API is healthy${NC}"
else
    echo -e "${YELLOW}⚠️  API is starting up (may take a few more seconds)${NC}"
fi

echo ""
echo -e "${BLUE}=========================================="
echo "Services Running"
echo -e "==========================================${NC}"
echo ""
echo -e "  ${GREEN}API:${NC}         http://localhost:8000"
echo -e "  ${GREEN}Health:${NC}      http://localhost:8000/health"
echo -e "  ${GREEN}LocalStack:${NC}  http://localhost:4566"
echo ""
echo -e "${BLUE}=========================================="
echo "Useful Commands"
echo -e "==========================================${NC}"
echo ""
echo -e "  ${GREEN}View logs:${NC}       make logs"
echo -e "  ${GREEN}Stop services:${NC}   make stop"
echo -e "  ${GREEN}Run tests:${NC}       make test"
echo -e "  ${GREEN}Restart:${NC}         make restart"
echo ""
echo -e "${YELLOW}Note: SSO credentials expire in ~1 hour${NC}"
echo -e "${YELLOW}When they expire, run this script again:${NC}"
echo -e "  ./scripts/start_with_sso.sh"
echo ""
