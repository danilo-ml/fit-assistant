#!/bin/bash
# Setup script for AWS Bedrock configuration

set -e

echo "=========================================="
echo "AWS Bedrock Setup for FitAgent"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    echo "Please install it first: https://aws.amazon.com/cli/"
    exit 1
fi

echo "✅ AWS CLI is installed"
echo ""

# Check AWS credentials
echo "Checking AWS credentials..."
if aws sts get-caller-identity &> /dev/null; then
    echo "✅ AWS credentials are configured"
    aws sts get-caller-identity
    echo ""
else
    echo "❌ AWS credentials are not configured"
    echo ""
    echo "Please run: aws configure"
    echo "You'll need:"
    echo "  - AWS Access Key ID"
    echo "  - AWS Secret Access Key"
    echo "  - Default region (us-east-1 recommended)"
    exit 1
fi

# Check Bedrock access
echo "Checking Bedrock model access..."
REGION="us-east-1"
MODEL_ID="anthropic.claude-3-sonnet-20240229-v1:0"

# Try to list foundation models (this checks if Bedrock is accessible)
if aws bedrock list-foundation-models --region $REGION &> /dev/null; then
    echo "✅ Bedrock is accessible in region $REGION"
else
    echo "⚠️  Cannot access Bedrock in region $REGION"
    echo "Please ensure:"
    echo "  1. Your AWS account has Bedrock enabled"
    echo "  2. You've requested model access in AWS Console"
    echo "  3. Your IAM user/role has bedrock:* permissions"
fi
echo ""

# Update .env file
echo "Updating .env configuration..."

if [ -f .env ]; then
    # Backup .env
    cp .env .env.backup
    echo "✅ Backed up .env to .env.backup"
    
    # Ensure AWS_BEDROCK_ENDPOINT_URL is empty
    if grep -q "AWS_BEDROCK_ENDPOINT_URL" .env; then
        sed -i.tmp 's/AWS_BEDROCK_ENDPOINT_URL=.*/AWS_BEDROCK_ENDPOINT_URL=/' .env
        rm -f .env.tmp
        echo "✅ Cleared AWS_BEDROCK_ENDPOINT_URL (using real AWS)"
    fi
    
    echo ""
    echo "✅ Configuration updated!"
else
    echo "❌ .env file not found"
    echo "Please copy .env.example to .env first"
    exit 1
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart your Docker containers:"
echo "   make restart"
echo ""
echo "2. Test Bedrock connection:"
echo "   python scripts/test_e2e.py"
echo ""
echo "3. Check logs for 'Using REAL AWS Bedrock'"
echo "   make logs"
echo ""
echo "For more details, see: docs/guides/AWS_BEDROCK_SETUP.md"
