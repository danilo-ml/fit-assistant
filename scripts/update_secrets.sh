#!/bin/bash
set -e

# Script to update AWS Secrets Manager secrets for FitAgent
# Usage: ./scripts/update_secrets.sh <environment> <secret_type>
# Example: ./scripts/update_secrets.sh production twilio

ENVIRONMENT="${1:-production}"
SECRET_TYPE="${2}"
REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="fitagent-${ENVIRONMENT}"

if [ -z "$SECRET_TYPE" ]; then
    echo "Usage: $0 <environment> <secret_type>"
    echo ""
    echo "Available secret types:"
    echo "  twilio    - Update Twilio credentials"
    echo "  google    - Update Google OAuth credentials"
    echo "  outlook   - Update Outlook OAuth credentials"
    echo "  all       - Update all secrets interactively"
    exit 1
fi

# Function to get secret ARN from CloudFormation
get_secret_arn() {
    local output_key=$1
    aws cloudformation describe-stacks \
        --stack-name ${STACK_NAME} \
        --region ${REGION} \
        --query "Stacks[0].Outputs[?OutputKey=='${output_key}'].OutputValue" \
        --output text
}

# Function to update Twilio secret
update_twilio_secret() {
    echo "=========================================="
    echo "Update Twilio Credentials"
    echo "=========================================="
    
    read -p "Twilio Account SID: " TWILIO_SID
    read -sp "Twilio Auth Token: " TWILIO_TOKEN
    echo ""
    read -p "Twilio WhatsApp Number (format: whatsapp:+1234567890): " TWILIO_NUMBER
    
    SECRET_ARN=$(get_secret_arn "TwilioSecretArn")
    
    SECRET_JSON=$(cat <<EOF
{
  "account_sid": "${TWILIO_SID}",
  "auth_token": "${TWILIO_TOKEN}",
  "whatsapp_number": "${TWILIO_NUMBER}"
}
EOF
)
    
    aws secretsmanager update-secret \
        --secret-id ${SECRET_ARN} \
        --secret-string "${SECRET_JSON}" \
        --region ${REGION}
    
    echo "✓ Twilio credentials updated successfully"
}

# Function to update Google OAuth secret
update_google_secret() {
    echo "=========================================="
    echo "Update Google OAuth Credentials"
    echo "=========================================="
    
    read -p "Google Client ID: " GOOGLE_CLIENT_ID
    read -sp "Google Client Secret: " GOOGLE_CLIENT_SECRET
    echo ""
    
    SECRET_ARN=$(get_secret_arn "GoogleOAuthSecretArn")
    
    SECRET_JSON=$(cat <<EOF
{
  "client_id": "${GOOGLE_CLIENT_ID}",
  "client_secret": "${GOOGLE_CLIENT_SECRET}"
}
EOF
)
    
    aws secretsmanager update-secret \
        --secret-id ${SECRET_ARN} \
        --secret-string "${SECRET_JSON}" \
        --region ${REGION}
    
    echo "✓ Google OAuth credentials updated successfully"
}

# Function to update Outlook OAuth secret
update_outlook_secret() {
    echo "=========================================="
    echo "Update Outlook OAuth Credentials"
    echo "=========================================="
    
    read -p "Outlook Client ID: " OUTLOOK_CLIENT_ID
    read -sp "Outlook Client Secret: " OUTLOOK_CLIENT_SECRET
    echo ""
    
    SECRET_ARN=$(get_secret_arn "OutlookOAuthSecretArn")
    
    SECRET_JSON=$(cat <<EOF
{
  "client_id": "${OUTLOOK_CLIENT_ID}",
  "client_secret": "${OUTLOOK_CLIENT_SECRET}"
}
EOF
)
    
    aws secretsmanager update-secret \
        --secret-id ${SECRET_ARN} \
        --secret-string "${SECRET_JSON}" \
        --region ${REGION}
    
    echo "✓ Outlook OAuth credentials updated successfully"
}

# Main logic
case "$SECRET_TYPE" in
    twilio)
        update_twilio_secret
        ;;
    google)
        update_google_secret
        ;;
    outlook)
        update_outlook_secret
        ;;
    all)
        update_twilio_secret
        echo ""
        update_google_secret
        echo ""
        update_outlook_secret
        ;;
    *)
        echo "Error: Unknown secret type '${SECRET_TYPE}'"
        echo "Valid types: twilio, google, outlook, all"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Secrets Update Complete!"
echo "=========================================="
