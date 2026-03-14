#!/bin/bash
# Export SSO credentials for Docker use

set -e

PROFILE="danilosousa"

echo "=========================================="
echo "Exporting AWS SSO Credentials"
echo "=========================================="
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    exit 1
fi

# Check if logged in
if ! aws sts get-caller-identity --profile $PROFILE &> /dev/null; then
    echo "❌ Not logged in to AWS SSO"
    echo "Please run: aws sso login --profile $PROFILE"
    exit 1
fi

echo "✅ AWS SSO session is active"
echo ""

# Export credentials
echo "Exporting credentials..."
CREDS=$(aws configure export-credentials --profile $PROFILE --format env)

if [ $? -ne 0 ]; then
    echo "❌ Failed to export credentials"
    exit 1
fi

# Parse credentials
export AWS_ACCESS_KEY_ID=$(echo "$CREDS" | grep AWS_ACCESS_KEY_ID | cut -d'=' -f2)
export AWS_SECRET_ACCESS_KEY=$(echo "$CREDS" | grep AWS_SECRET_ACCESS_KEY | cut -d'=' -f2)
export AWS_SESSION_TOKEN=$(echo "$CREDS" | grep AWS_SESSION_TOKEN | cut -d'=' -f2)
export AWS_CREDENTIAL_EXPIRATION=$(echo "$CREDS" | grep AWS_CREDENTIAL_EXPIRATION | cut -d'=' -f2)

echo "✅ Credentials exported"
echo ""
echo "Credentials expire at: $AWS_CREDENTIAL_EXPIRATION"
echo ""

# Create .env.bedrock file
cat > .env.bedrock << EOF
# AWS SSO Temporary Credentials
# Generated: $(date)
# Expires: $AWS_CREDENTIAL_EXPIRATION
# Profile: $PROFILE

BEDROCK_AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
BEDROCK_AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
BEDROCK_AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN
EOF

echo "✅ Credentials saved to .env.bedrock"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Update docker-compose.yml to use these credentials"
echo "2. Restart Docker: make restart"
echo "3. Test Bedrock"
echo ""
echo "Note: Credentials expire in ~1 hour. Re-run this script when they expire."
echo ""
echo "To apply credentials now, run:"
echo "  source .env.bedrock"
echo "  docker-compose down && docker-compose up -d"
