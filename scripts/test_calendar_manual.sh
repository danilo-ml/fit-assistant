#!/bin/bash
# Manual test script for Google Calendar integration

set -e

ENVIRONMENT="${1:-production}"
STACK_NAME="fitagent-${ENVIRONMENT}"

echo "=========================================="
echo "Google Calendar Integration Test"
echo "=========================================="
echo "Environment: ${ENVIRONMENT}"
echo ""

# Get OAuth callback URL
echo "1. Getting OAuth callback URL..."
OAUTH_URL=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --query 'Stacks[0].Outputs[?OutputKey==`OAuthCallbackUrl`].OutputValue' \
  --output text)

echo "   OAuth Callback URL: ${OAUTH_URL}"
echo ""

# Test OAuth endpoint accessibility
echo "2. Testing OAuth endpoint..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${OAUTH_URL}?code=test&state=test" || echo "000")

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "400" ]; then
    echo "   ✓ OAuth endpoint is accessible (HTTP ${HTTP_CODE})"
else
    echo "   ✗ OAuth endpoint returned HTTP ${HTTP_CODE}"
fi
echo ""

# Check Lambda function
echo "3. Checking OAuth callback Lambda function..."
LAMBDA_NAME="fitagent-oauth-callback-${ENVIRONMENT}"
LAMBDA_EXISTS=$(aws lambda get-function --function-name ${LAMBDA_NAME} 2>&1 | grep -c "FunctionName" || echo "0")

if [ "$LAMBDA_EXISTS" = "1" ]; then
    echo "   ✓ Lambda function exists: ${LAMBDA_NAME}"
    
    # Get Lambda configuration
    LAMBDA_RUNTIME=$(aws lambda get-function-configuration \
      --function-name ${LAMBDA_NAME} \
      --query 'Runtime' \
      --output text)
    
    LAMBDA_TIMEOUT=$(aws lambda get-function-configuration \
      --function-name ${LAMBDA_NAME} \
      --query 'Timeout' \
      --output text)
    
    echo "   Runtime: ${LAMBDA_RUNTIME}"
    echo "   Timeout: ${LAMBDA_TIMEOUT}s"
else
    echo "   ✗ Lambda function not found: ${LAMBDA_NAME}"
fi
echo ""

# Check Google OAuth secret
echo "4. Checking Google OAuth credentials..."
GOOGLE_SECRET_ARN=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --query 'Stacks[0].Outputs[?OutputKey==`GoogleOAuthSecretArn`].OutputValue' \
  --output text)

if [ -n "$GOOGLE_SECRET_ARN" ]; then
    echo "   ✓ Google OAuth secret exists"
    
    # Try to get secret value
    SECRET_VALUE=$(aws secretsmanager get-secret-value \
      --secret-id ${GOOGLE_SECRET_ARN} \
      --query 'SecretString' \
      --output text 2>/dev/null || echo "{}")
    
    CLIENT_ID=$(echo "$SECRET_VALUE" | jq -r '.client_id // empty')
    
    if [ -n "$CLIENT_ID" ] && [ "$CLIENT_ID" != "PLACEHOLDER_UPDATE_AFTER_DEPLOYMENT" ]; then
        echo "   ✓ Google OAuth credentials configured"
        echo "   Client ID: ${CLIENT_ID:0:20}..."
    else
        echo "   ⚠ Google OAuth credentials not yet configured"
        echo "   Update with: aws secretsmanager update-secret --secret-id ${GOOGLE_SECRET_ARN} --secret-string '{\"client_id\":\"YOUR_ID\",\"client_secret\":\"YOUR_SECRET\"}'"
    fi
else
    echo "   ✗ Google OAuth secret not found"
fi
echo ""

# Summary
echo "=========================================="
echo "Manual Testing Steps"
echo "=========================================="
echo ""
echo "To test the full OAuth flow:"
echo ""
echo "1. Configure Google OAuth redirect URI:"
echo "   ${OAUTH_URL}"
echo ""
echo "2. Update Google OAuth credentials in Secrets Manager:"
echo "   aws secretsmanager update-secret \\"
echo "     --secret-id ${GOOGLE_SECRET_ARN} \\"
echo "     --secret-string '{\"client_id\":\"YOUR_CLIENT_ID\",\"client_secret\":\"YOUR_CLIENT_SECRET\"}'"
echo ""
echo "3. Test via WhatsApp:"
echo "   - Send message: 'Connect my Google Calendar'"
echo "   - Click the OAuth URL in the response"
echo "   - Authorize access in Google"
echo "   - Verify you receive a success message"
echo ""
echo "4. Test calendar sync:"
echo "   - Send message: 'Schedule a session with John tomorrow at 2pm for 60 minutes'"
echo "   - Check your Google Calendar for the event"
echo "   - Verify event details match the session"
echo ""
echo "=========================================="
