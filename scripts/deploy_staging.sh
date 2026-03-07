#!/bin/bash
# Staging Deployment Script for FitAgent
# Deploys CloudFormation stack to staging environment with validation

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STACK_NAME="fitagent-staging"
TEMPLATE_FILE="infrastructure/template.yml"
PARAMETERS_FILE="infrastructure/parameters/staging.json"
REGION="${AWS_REGION:-us-east-1}"
DEPLOYMENT_BUCKET="${DEPLOYMENT_BUCKET:-fitagent-deployments-staging}"
LAMBDA_PACKAGE="build/lambda.zip"

echo -e "${GREEN}=== FitAgent Staging Deployment ===${NC}"
echo ""
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "Template: $TEMPLATE_FILE"
echo "Parameters: $PARAMETERS_FILE"
echo ""

# Step 1: Validate prerequisites
echo -e "${YELLOW}[1/8] Validating prerequisites...${NC}"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ ERROR: AWS CLI not found${NC}"
    echo "  Install: https://aws.amazon.com/cli/"
    exit 1
fi
echo "✓ AWS CLI found"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}✗ ERROR: AWS credentials not configured${NC}"
    echo "  Run: aws configure"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✓ AWS credentials valid (Account: $ACCOUNT_ID)"

# Check required files
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}✗ ERROR: Template file not found: $TEMPLATE_FILE${NC}"
    exit 1
fi
echo "✓ Template file found"

if [ ! -f "$PARAMETERS_FILE" ]; then
    echo -e "${RED}✗ ERROR: Parameters file not found: $PARAMETERS_FILE${NC}"
    exit 1
fi
echo "✓ Parameters file found"

if [ ! -f "$LAMBDA_PACKAGE" ]; then
    echo -e "${RED}✗ ERROR: Lambda package not found: $LAMBDA_PACKAGE${NC}"
    echo "  Run: ./scripts/package_lambda.sh"
    exit 1
fi
echo "✓ Lambda package found"

echo ""

# Step 2: Validate CloudFormation template
echo -e "${YELLOW}[2/8] Validating CloudFormation template...${NC}"
aws cloudformation validate-template \
    --template-body file://"$TEMPLATE_FILE" \
    --region "$REGION" \
    > /dev/null

echo "✓ Template validation passed"
echo ""

# Step 3: Create S3 deployment bucket if needed
echo -e "${YELLOW}[3/8] Checking deployment bucket...${NC}"
if aws s3 ls "s3://$DEPLOYMENT_BUCKET" 2>&1 | grep -q 'NoSuchBucket'; then
    echo "  Creating deployment bucket: $DEPLOYMENT_BUCKET"
    aws s3 mb "s3://$DEPLOYMENT_BUCKET" --region "$REGION"
    
    # Enable versioning
    aws s3api put-bucket-versioning \
        --bucket "$DEPLOYMENT_BUCKET" \
        --versioning-configuration Status=Enabled
    
    echo "✓ Deployment bucket created"
else
    echo "✓ Deployment bucket exists"
fi
echo ""

# Step 4: Upload Lambda package to S3
echo -e "${YELLOW}[4/8] Uploading Lambda package to S3...${NC}"
PACKAGE_VERSION=$(date +%Y%m%d-%H%M%S)
S3_KEY="lambda-packages/lambda-${PACKAGE_VERSION}.zip"

aws s3 cp "$LAMBDA_PACKAGE" "s3://$DEPLOYMENT_BUCKET/$S3_KEY" \
    --region "$REGION" \
    --metadata "version=$PACKAGE_VERSION,environment=staging"

echo "✓ Lambda package uploaded: s3://$DEPLOYMENT_BUCKET/$S3_KEY"
echo ""

# Step 5: Parse parameters file
echo -e "${YELLOW}[5/8] Preparing deployment parameters...${NC}"

# Extract parameters from JSON and convert to CloudFormation format
PARAMS=$(python3 -c "
import json
import sys

with open('$PARAMETERS_FILE') as f:
    data = json.load(f)

params = []
for key, value in data.get('Parameters', {}).items():
    params.append(f'ParameterKey={key},ParameterValue={value}')

print(' '.join(params))
")

echo "✓ Parameters prepared"
echo ""

# Step 6: Check if stack exists
echo -e "${YELLOW}[6/8] Checking stack status...${NC}"
if aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" &> /dev/null; then
    
    STACK_STATUS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].StackStatus' \
        --output text)
    
    echo "  Stack exists with status: $STACK_STATUS"
    
    # Check if stack is in a failed state
    if [[ "$STACK_STATUS" == *"FAILED"* ]] || [[ "$STACK_STATUS" == *"ROLLBACK"* ]]; then
        echo -e "${RED}✗ ERROR: Stack is in failed state: $STACK_STATUS${NC}"
        echo "  Delete the stack and try again: aws cloudformation delete-stack --stack-name $STACK_NAME"
        exit 1
    fi
    
    OPERATION="update"
    echo "✓ Will perform stack update"
else
    OPERATION="create"
    echo "✓ Will perform stack creation"
fi
echo ""

# Step 7: Deploy stack
echo -e "${YELLOW}[7/8] Deploying CloudFormation stack...${NC}"
echo "  Operation: $OPERATION"
echo "  This may take 5-10 minutes..."
echo ""

if [ "$OPERATION" == "create" ]; then
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body file://"$TEMPLATE_FILE" \
        --parameters $PARAMS \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        --tags Key=Environment,Value=staging Key=Application,Value=FitAgent \
        > /dev/null
    
    echo "  Waiting for stack creation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name "$STACK_NAME" \
        --region "$REGION"
else
    # Check if there are changes to deploy
    CHANGE_SET_NAME="staging-changeset-$(date +%s)"
    
    aws cloudformation create-change-set \
        --stack-name "$STACK_NAME" \
        --change-set-name "$CHANGE_SET_NAME" \
        --template-body file://"$TEMPLATE_FILE" \
        --parameters $PARAMS \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION" \
        > /dev/null
    
    echo "  Waiting for change set creation..."
    aws cloudformation wait change-set-create-complete \
        --stack-name "$STACK_NAME" \
        --change-set-name "$CHANGE_SET_NAME" \
        --region "$REGION" 2>&1 || true
    
    # Check if there are changes
    CHANGE_SET_STATUS=$(aws cloudformation describe-change-set \
        --stack-name "$STACK_NAME" \
        --change-set-name "$CHANGE_SET_NAME" \
        --region "$REGION" \
        --query 'Status' \
        --output text)
    
    if [ "$CHANGE_SET_STATUS" == "FAILED" ]; then
        STATUS_REASON=$(aws cloudformation describe-change-set \
            --stack-name "$STACK_NAME" \
            --change-set-name "$CHANGE_SET_NAME" \
            --region "$REGION" \
            --query 'StatusReason' \
            --output text)
        
        if [[ "$STATUS_REASON" == *"didn't contain changes"* ]]; then
            echo "✓ No changes to deploy"
            aws cloudformation delete-change-set \
                --stack-name "$STACK_NAME" \
                --change-set-name "$CHANGE_SET_NAME" \
                --region "$REGION"
        else
            echo -e "${RED}✗ ERROR: Change set creation failed: $STATUS_REASON${NC}"
            exit 1
        fi
    else
        # Execute change set
        aws cloudformation execute-change-set \
            --stack-name "$STACK_NAME" \
            --change-set-name "$CHANGE_SET_NAME" \
            --region "$REGION"
        
        echo "  Waiting for stack update to complete..."
        aws cloudformation wait stack-update-complete \
            --stack-name "$STACK_NAME" \
            --region "$REGION"
    fi
fi

echo "✓ Stack deployment complete"
echo ""

# Step 8: Update Lambda function code
echo -e "${YELLOW}[8/8] Updating Lambda function code...${NC}"

# Get function names from stack outputs
MESSAGE_PROCESSOR_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`MessageProcessorFunctionName`].OutputValue' \
    --output text)

SESSION_CONFIRMATION_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[?OutputKey==`SessionConfirmationFunctionName`].OutputValue' \
    --output text)

# Update Message Processor function
echo "  Updating $MESSAGE_PROCESSOR_FUNCTION..."
aws lambda update-function-code \
    --function-name "$MESSAGE_PROCESSOR_FUNCTION" \
    --s3-bucket "$DEPLOYMENT_BUCKET" \
    --s3-key "$S3_KEY" \
    --region "$REGION" \
    > /dev/null

# Update Session Confirmation function
echo "  Updating $SESSION_CONFIRMATION_FUNCTION..."
aws lambda update-function-code \
    --function-name "$SESSION_CONFIRMATION_FUNCTION" \
    --s3-bucket "$DEPLOYMENT_BUCKET" \
    --s3-key "$S3_KEY" \
    --region "$REGION" \
    > /dev/null

echo "✓ Lambda functions updated"
echo ""

# Display stack outputs
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo -e "${BLUE}Stack Outputs:${NC}"
aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo "  1. Enable feature flag for test trainers"
echo "  2. Run smoke tests: pytest tests/smoke/test_staging_deployment.py"
echo "  3. Monitor CloudWatch logs and metrics"
echo "  4. Verify WhatsApp message processing"
echo ""
echo "Rollback command (if needed):"
echo "  aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION"
echo ""
