#!/bin/bash
# Setup AWS SSO for Bedrock access

set -e

echo "=========================================="
echo "AWS SSO Setup for FitAgent Bedrock"
echo "=========================================="
echo ""

PROFILE="danilosousa"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    echo "Please install it first: https://aws.amazon.com/cli/"
    exit 1
fi

echo "✅ AWS CLI is installed"
echo ""

# Login to AWS SSO
echo "Logging in to AWS SSO with profile: $PROFILE"
echo ""

if aws sso login --profile $PROFILE; then
    echo ""
    echo "✅ AWS SSO login successful!"
    echo ""
else
    echo ""
    echo "❌ AWS SSO login failed"
    echo ""
    echo "Make sure your AWS SSO is configured:"
    echo "  aws configure sso --profile $PROFILE"
    exit 1
fi

# Verify credentials
echo "Verifying AWS credentials..."
if aws sts get-caller-identity --profile $PROFILE &> /dev/null; then
    echo "✅ AWS credentials are working"
    aws sts get-caller-identity --profile $PROFILE
    echo ""
else
    echo "❌ Cannot verify AWS credentials"
    exit 1
fi

# Check Bedrock access
echo "Checking Bedrock access..."
REGION="us-east-1"

if aws bedrock list-foundation-models --region $REGION --profile $PROFILE &> /dev/null; then
    echo "✅ Bedrock is accessible"
    echo ""
else
    echo "⚠️  Cannot access Bedrock"
    echo "Please ensure:"
    echo "  1. Your AWS account has Bedrock enabled"
    echo "  2. You've requested model access in AWS Console"
    echo "  3. Your IAM role has bedrock:* permissions"
    echo ""
fi

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Restart Docker containers:"
echo "   make restart"
echo ""
echo "2. Check logs for 'Using REAL AWS Bedrock':"
echo "   make logs | grep Bedrock"
echo ""
echo "3. Test the system:"
echo "   python scripts/test_e2e.py"
echo ""
echo "Note: Your SSO session will expire. When it does, run:"
echo "  aws sso login --profile $PROFILE"
