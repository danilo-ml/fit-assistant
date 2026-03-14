#!/bin/bash
# Setup script for AWS Bedrock access

set -e

echo "🚀 FitAgent - AWS Bedrock Setup"
echo "================================"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first:"
    echo "   brew install awscli  # macOS"
    echo "   pip install awscli   # Python"
    exit 1
fi

echo "✅ AWS CLI found"
echo ""

# Check if credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "⚠️  AWS credentials not configured"
    echo ""
    echo "Please run: aws configure"
    echo ""
    echo "You'll need:"
    echo "  - AWS Access Key ID"
    echo "  - AWS Secret Access Key"
    echo "  - Default region (us-east-1 recommended)"
    echo ""
    exit 1
fi

echo "✅ AWS credentials configured"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "   Account ID: $ACCOUNT_ID"
echo ""

# Check Bedrock access
echo "🔍 Checking Bedrock access..."
if aws bedrock list-foundation-models --region us-east-1 &> /dev/null; then
    echo "✅ Bedrock API accessible"
    echo ""
    
    # Check for Claude 3 Sonnet
    CLAUDE_MODELS=$(aws bedrock list-foundation-models \
        --region us-east-1 \
        --query 'modelSummaries[?contains(modelId, `claude-3-sonnet`)].modelId' \
        --output text)
    
    if [ -n "$CLAUDE_MODELS" ]; then
        echo "✅ Claude 3 Sonnet access enabled"
        echo "   Model: $CLAUDE_MODELS"
    else
        echo "⚠️  Claude 3 Sonnet not accessible"
        echo ""
        echo "To enable access:"
        echo "1. Go to: https://console.aws.amazon.com/bedrock/"
        echo "2. Click 'Model access' in left sidebar"
        echo "3. Click 'Manage model access'"
        echo "4. Enable 'Anthropic Claude 3 Sonnet'"
        echo "5. Wait for approval (usually instant)"
        echo ""
    fi
    
    # Check for Amazon Nova models
    NOVA_MODELS=$(aws bedrock list-foundation-models \
        --region us-east-1 \
        --query 'modelSummaries[?contains(modelId, `nova`)].modelId' \
        --output text)
    
    if [ -n "$NOVA_MODELS" ]; then
        echo "✅ Amazon Nova models access enabled"
        echo "   Models: $NOVA_MODELS"
    else
        echo "⚠️  Amazon Nova models not accessible"
        echo "   (Optional, but cheaper for development)"
    fi
else
    echo "❌ Cannot access Bedrock API"
    echo ""
    echo "Possible issues:"
    echo "1. IAM permissions missing (need bedrock:* permissions)"
    echo "2. Bedrock not available in your region"
    echo "3. Model access not requested"
    echo ""
    exit 1
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Restart services: docker-compose restart sqs-processor"
echo "2. Watch logs: docker logs -f fitagent-sqs-processor"
echo "3. Send a WhatsApp message to test"
echo ""
echo "Expected log output:"
echo '  "endpoint_url": "real AWS"'
echo '  "language": "pt-BR"'
echo ""
