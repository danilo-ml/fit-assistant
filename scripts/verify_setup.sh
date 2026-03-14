#!/bin/bash

# Verification script for FitAgent local setup
# This script checks that all services are properly configured

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     FitAgent - Setup Verification                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

ERRORS=0

# Check Docker
echo -e "${YELLOW}[1/8] Checking Docker...${NC}"
if docker info &> /dev/null; then
    echo -e "${GREEN}✓ Docker is running${NC}"
else
    echo -e "${RED}✗ Docker is not running${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Docker Compose
echo -e "${YELLOW}[2/8] Checking Docker Compose...${NC}"
if docker-compose version &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose is installed${NC}"
else
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check if services are running
echo -e "${YELLOW}[3/8] Checking services...${NC}"
if docker ps --filter "name=fitagent" | grep -q "fitagent"; then
    echo -e "${GREEN}✓ FitAgent services are running${NC}"
    docker ps --filter "name=fitagent" --format "  - {{.Names}}: {{.Status}}"
else
    echo -e "${RED}✗ FitAgent services are not running${NC}"
    echo -e "${YELLOW}  Run: docker-compose up -d${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check API health
echo -e "${YELLOW}[4/8] Checking API health...${NC}"
if curl -s http://localhost:8000/health | grep -q "healthy"; then
    echo -e "${GREEN}✓ API is healthy${NC}"
else
    echo -e "${RED}✗ API is not responding${NC}"
    echo -e "${YELLOW}  Check logs: docker logs fitagent-api${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check LocalStack health
echo -e "${YELLOW}[5/8] Checking LocalStack...${NC}"
if curl -s http://localhost:4566/_localstack/health &> /dev/null; then
    echo -e "${GREEN}✓ LocalStack is running${NC}"
else
    echo -e "${RED}✗ LocalStack is not responding${NC}"
    echo -e "${YELLOW}  Check logs: docker logs fitagent-localstack${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check DynamoDB table
echo -e "${YELLOW}[6/8] Checking DynamoDB table...${NC}"
if AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
   aws --endpoint-url=http://localhost:4566 \
   dynamodb describe-table --table-name fitagent-main --region us-east-1 &> /dev/null; then
    echo -e "${GREEN}✓ DynamoDB table 'fitagent-main' exists${NC}"
else
    echo -e "${RED}✗ DynamoDB table 'fitagent-main' not found${NC}"
    echo -e "${YELLOW}  Wait for LocalStack initialization or restart: docker-compose restart localstack${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check SQS queues
echo -e "${YELLOW}[7/8] Checking SQS FIFO queues...${NC}"
QUEUES=$(AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
   aws --endpoint-url=http://localhost:4566 \
   sqs list-queues --region us-east-1 2>/dev/null | grep -o "fitagent-[^\"]*" || echo "")

if echo "$QUEUES" | grep -q "fitagent-messages.fifo"; then
    echo -e "${GREEN}✓ SQS queue 'fitagent-messages.fifo' exists${NC}"
else
    echo -e "${RED}✗ SQS queue 'fitagent-messages.fifo' not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

if echo "$QUEUES" | grep -q "fitagent-messages-dlq.fifo"; then
    echo -e "${GREEN}✓ SQS queue 'fitagent-messages-dlq.fifo' exists${NC}"
else
    echo -e "${RED}✗ SQS queue 'fitagent-messages-dlq.fifo' not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

if echo "$QUEUES" | grep -q "fitagent-notifications.fifo"; then
    echo -e "${GREEN}✓ SQS queue 'fitagent-notifications.fifo' exists${NC}"
else
    echo -e "${RED}✗ SQS queue 'fitagent-notifications.fifo' not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check S3 bucket
echo -e "${YELLOW}[8/8] Checking S3 bucket...${NC}"
if AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
   aws --endpoint-url=http://localhost:4566 \
   s3 ls s3://fitagent-receipts-local --region us-east-1 &> /dev/null; then
    echo -e "${GREEN}✓ S3 bucket 'fitagent-receipts-local' exists${NC}"
else
    echo -e "${RED}✗ S3 bucket 'fitagent-receipts-local' not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Setup is ready.${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Run mock tests: python scripts/test_whatsapp_local.py"
    echo "  2. Run unit tests: pytest tests/unit/ -v"
    echo "  3. For E2E testing: See docs/guides/E2E_TESTING_QUICKSTART.md"
else
    echo -e "${RED}✗ Found $ERRORS error(s). Please fix them before proceeding.${NC}"
    echo ""
    echo -e "${YELLOW}Common fixes:${NC}"
    echo "  - Start services: docker-compose up -d"
    echo "  - Wait for initialization: sleep 30"
    echo "  - Restart services: docker-compose restart"
    echo "  - Check logs: docker logs fitagent-api"
    echo "  - Check logs: docker logs fitagent-localstack"
fi
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

exit $ERRORS
