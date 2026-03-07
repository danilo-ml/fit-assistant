# Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying FitAgent to the production environment for the first time. This is the initial production deployment of the Strands-based multi-agent architecture.

**Target Environment:** AWS Production  
**Stack Name:** `fitagent-production`  
**Region:** `us-east-1` (configurable)  
**Estimated Deployment Time:** 30-45 minutes  
**Deployment Strategy:** Initial deployment with gradual feature rollout

---

## ⚠️ Critical Pre-Deployment Checklist

Before proceeding with production deployment, ensure ALL items are completed:

### Testing Requirements
- [ ] All unit tests passing (100% critical paths)
- [ ] All integration tests passing
- [ ] Staging environment tested for minimum 2 weeks
- [ ] Load testing completed (expected peak + 50%)
- [ ] Security audit completed
- [ ] Penetration testing completed
- [ ] Disaster recovery plan tested

### Business Requirements
- [ ] Product owner approval obtained
- [ ] Change management ticket approved
- [ ] Maintenance window scheduled (if needed)
- [ ] Customer communication sent (if downtime expected)
- [ ] Rollback plan documented and reviewed
- [ ] On-call engineer identified and available

### Technical Requirements
- [ ] Production parameters file created and reviewed
- [ ] Twilio production number configured
- [ ] OAuth credentials configured for production
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Cost budget approved
- [ ] Performance baselines established


---

## Prerequisites

### Required Tools

1. **AWS CLI** (v2.x or later)
   ```bash
   aws --version
   # Required: aws-cli/2.x.x or later
   ```

2. **Python 3.12**
   ```bash
   python3 --version
   # Required: Python 3.12.x
   ```

3. **jq** (JSON processor for scripts)
   ```bash
   jq --version
   # Install: brew install jq (macOS) or apt-get install jq (Linux)
   ```

4. **Git** (for version control and tagging)
   ```bash
   git --version
   ```

### AWS Credentials and Permissions

**Production deployments require elevated permissions:**

```bash
aws configure --profile production
# Enter production AWS Access Key ID and Secret Access Key
```

**Required IAM Permissions:**
- CloudFormation: Full access
- DynamoDB: Full access (including backup/restore)
- Lambda: Full access
- IAM: Create/update roles and policies
- S3: Full access
- EventBridge: Full access
- CloudWatch: Full access (logs, metrics, alarms)
- Secrets Manager: Full access
- KMS: Key management and encryption
- SNS: Topic creation for alerts
- Route53: DNS management (if using custom domain)

**Security Best Practices:**
- Use MFA for production deployments
- Use temporary credentials (AWS STS)
- Enable CloudTrail for all API calls
- Restrict production access to authorized personnel only


### Environment Configuration

Create production parameters file:

```bash
cp infrastructure/parameters/staging.json infrastructure/parameters/production.json
```

Edit `infrastructure/parameters/production.json`:

```json
{
  "Parameters": {
    "Environment": "production",
    "TableReadCapacity": 50,
    "TableWriteCapacity": 50,
    "TwilioAccountSid": "PRODUCTION_TWILIO_SID",
    "TwilioAuthToken": "PRODUCTION_TWILIO_TOKEN",
    "TwilioWhatsAppNumber": "whatsapp:+1234567890",
    "EnableAutoScaling": true,
    "MinReadCapacity": 25,
    "MaxReadCapacity": 200,
    "MinWriteCapacity": 25,
    "MaxWriteCapacity": 200,
    "TargetUtilization": 70,
    "EnablePointInTimeRecovery": true,
    "LogRetentionDays": 30,
    "EnableXRayTracing": true
  },
  "Tags": {
    "Environment": "production",
    "Application": "FitAgent",
    "ManagedBy": "CloudFormation",
    "CostCenter": "Production",
    "Owner": "Platform-Team",
    "Compliance": "GDPR",
    "BackupPolicy": "Daily"
  }
}
```

**Key Production Differences:**
- Higher DynamoDB capacity (50 RCU/WCU vs 10)
- Auto-scaling enabled
- Point-in-time recovery enabled
- Longer log retention (30 days vs 7)
- X-Ray tracing enabled for debugging
- Production Twilio number (not sandbox)


### Twilio Production Configuration

**Production requires a dedicated Twilio phone number (not sandbox):**

1. **Purchase Production Number:**
   - Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/search
   - Search for available numbers with WhatsApp capability
   - Purchase number (~$1/month + usage)

2. **Enable WhatsApp on Production Number:**
   - Submit WhatsApp Business Profile for approval
   - This process takes 1-3 business days
   - Required information:
     - Business name: "FitAgent"
     - Business description
     - Business website
     - Business address
     - Business category: "Fitness & Wellness"

3. **Configure Production Webhook:**
   - Set webhook URL to production API Gateway endpoint
   - Format: `https://api.fitagent.com/webhook`
   - Enable signature validation
   - Set HTTP method to POST

4. **Store Credentials Securely:**
   ```bash
   # Store in AWS Secrets Manager (recommended)
   aws secretsmanager create-secret \
       --name fitagent/production/twilio \
       --secret-string '{
         "account_sid": "AC...",
         "auth_token": "...",
         "whatsapp_number": "whatsapp:+1234567890"
       }' \
       --region us-east-1
   ```

---

## Deployment Strategy

### Initial Production Deployment with Gradual Rollout

This is the first production deployment of FitAgent. The deployment follows a phased approach:

**Phase 1: Infrastructure Deployment (Week 1)**
- Deploy CloudFormation stack with all AWS resources
- Start with conservative feature flags (multi-agent disabled initially)
- Verify all resources created successfully
- Run comprehensive smoke tests
- Monitor for 48 hours

**Phase 2: Initial User Onboarding (Week 2)**
- Onboard first 5-10 pilot trainers
- Monitor system behavior with real users
- Gather feedback and fix issues
- Verify all core features working

**Phase 3: Gradual User Growth (Week 3-4)**
- Onboard additional trainers in batches
- Monitor capacity and performance
- Scale resources as needed
- Continue gathering feedback

**Phase 4: Feature Enablement (Week 5+)**
- Enable multi-agent architecture for pilot users
- Enable session confirmation feature
- Monitor advanced features
- Full rollout based on stability


---

## Step-by-Step Deployment Process

### Step 1: Pre-Deployment Verification

Run comprehensive checks before starting deployment:

```bash
# Create deployment script
cat > scripts/pre_deployment_check.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Pre-Deployment Verification ==="
echo ""

# Check AWS credentials
echo "[1/10] Checking AWS credentials..."
aws sts get-caller-identity --profile production > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ AWS credentials valid"
    aws sts get-caller-identity --profile production
else
    echo "✗ AWS credentials invalid"
    exit 1
fi

# Check staging environment
echo ""
echo "[2/10] Checking staging environment..."
STAGING_STATUS=$(aws cloudformation describe-stacks \
    --stack-name fitagent-staging \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STAGING_STATUS" = "CREATE_COMPLETE" ] || [ "$STAGING_STATUS" = "UPDATE_COMPLETE" ]; then
    echo "✓ Staging stack healthy: $STAGING_STATUS"
else
    echo "✗ Staging stack not healthy: $STAGING_STATUS"
    exit 1
fi

# Check test results
echo ""
echo "[3/10] Checking test results..."
if [ -f "test-results.xml" ]; then
    echo "✓ Test results found"
else
    echo "⚠ Test results not found - run tests first"
fi

# Check production parameters
echo ""
echo "[4/10] Checking production parameters..."
if [ -f "infrastructure/parameters/production.json" ]; then
    echo "✓ Production parameters file exists"
    # Validate JSON
    jq empty infrastructure/parameters/production.json 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "✓ Production parameters valid JSON"
    else
        echo "✗ Production parameters invalid JSON"
        exit 1
    fi
else
    echo "✗ Production parameters file not found"
    exit 1
fi

# Check Lambda package
echo ""
echo "[5/10] Checking Lambda package..."
if [ -f "build/lambda.zip" ]; then
    SIZE=$(du -h build/lambda.zip | cut -f1)
    echo "✓ Lambda package exists ($SIZE)"
else
    echo "✗ Lambda package not found - run package script"
    exit 1
fi

# Check CloudFormation template
echo ""
echo "[6/10] Validating CloudFormation template..."
aws cloudformation validate-template \
    --template-body file://infrastructure/template.yml \
    --profile production > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ CloudFormation template valid"
else
    echo "✗ CloudFormation template invalid"
    exit 1
fi

# Check Twilio credentials
echo ""
echo "[7/10] Checking Twilio credentials..."
TWILIO_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id fitagent/production/twilio \
    --profile production \
    --query 'SecretString' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$TWILIO_SECRET" != "NOT_FOUND" ]; then
    echo "✓ Twilio credentials found in Secrets Manager"
else
    echo "✗ Twilio credentials not found"
    exit 1
fi

# Check backup strategy
echo ""
echo "[8/10] Checking backup configuration..."
# This will be checked after initial deployment
echo "⚠ Manual verification required"

# Check monitoring setup
echo ""
echo "[9/10] Checking monitoring setup..."
# This will be configured after deployment
echo "⚠ Will be configured post-deployment"

# Check rollback plan
echo ""
echo "[10/10] Checking rollback plan..."
if [ -f "infrastructure/ROLLBACK_PLAN.md" ]; then
    echo "✓ Rollback plan documented"
else
    echo "⚠ Rollback plan not found"
fi

echo ""
echo "=== Pre-Deployment Check Complete ==="
echo ""
echo "Ready to proceed with deployment!"
EOF

chmod +x scripts/pre_deployment_check.sh
./scripts/pre_deployment_check.sh
```


### Step 2: Create Production Parameters File

```bash
# Create production parameters
cat > infrastructure/parameters/production.json << 'EOF'
{
  "Parameters": {
    "Environment": "production",
    "TableReadCapacity": 50,
    "TableWriteCapacity": 50,
    "TwilioAccountSid": "REPLACE_WITH_PRODUCTION_SID",
    "TwilioAuthToken": "REPLACE_WITH_PRODUCTION_TOKEN",
    "TwilioWhatsAppNumber": "whatsapp:+1234567890",
    "EnableMultiAgent": false,
    "EnableSessionConfirmation": false,
    "BedrockModelId": "anthropic.claude-3-sonnet-20240229-v1:0",
    "BedrockRegion": "us-east-1",
    "LogLevel": "INFO",
    "EnableXRayTracing": true,
    "EnablePointInTimeRecovery": true,
    "BackupRetentionDays": 35,
    "LogRetentionDays": 30
  },
  "Tags": {
    "Environment": "production",
    "Application": "FitAgent",
    "ManagedBy": "CloudFormation",
    "CostCenter": "Production",
    "Owner": "Platform-Team",
    "Compliance": "GDPR",
    "BackupPolicy": "Daily",
    "DataClassification": "Confidential"
  }
}
EOF

# Update with actual Twilio credentials
echo "⚠️  Update Twilio credentials in infrastructure/parameters/production.json"
```

**Important Configuration Notes:**

- `EnableMultiAgent: false` - Start with single-agent for safety
- `EnableSessionConfirmation: false` - Enable after monitoring
- `BedrockModelId` - Use Claude 3 Sonnet for production quality
- `EnableXRayTracing: true` - Essential for debugging
- `EnablePointInTimeRecovery: true` - Required for data protection
- `LogRetentionDays: 30` - Balance cost vs compliance


### Step 3: Package Lambda Functions

```bash
# Run packaging script
./scripts/package_lambda.sh

# Verify package contents
unzip -l build/lambda.zip | head -20

# Check package size (should be < 50MB uncompressed)
unzip -l build/lambda.zip | awk '{sum+=$1} END {print "Total size:", sum/1024/1024, "MB"}'

# Verify Strands SDK is included
unzip -l build/lambda.zip | grep strands
```

**Expected output:**
```
Total size: 45.2 MB
strands_agents/
strands_agents/__init__.py
strands_agents/agent.py
...
```

### Step 4: Create Deployment Bucket

```bash
# Create S3 bucket for deployments
aws s3 mb s3://fitagent-deployments-production \
    --region us-east-1 \
    --profile production

# Enable versioning
aws s3api put-bucket-versioning \
    --bucket fitagent-deployments-production \
    --versioning-configuration Status=Enabled \
    --profile production

# Enable encryption
aws s3api put-bucket-encryption \
    --bucket fitagent-deployments-production \
    --server-side-encryption-configuration '{
      "Rules": [{
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "AES256"
        }
      }]
    }' \
    --profile production

# Block public access
aws s3api put-public-access-block \
    --bucket fitagent-deployments-production \
    --public-access-block-configuration \
        BlockPublicAcls=true,\
        IgnorePublicAcls=true,\
        BlockPublicPolicy=true,\
        RestrictPublicBuckets=true \
    --profile production

echo "✓ Deployment bucket created and secured"
```


### Step 5: Upload Lambda Package to S3

```bash
# Generate version tag
VERSION=$(date +%Y%m%d-%H%M%S)
GIT_COMMIT=$(git rev-parse --short HEAD)
PACKAGE_NAME="lambda-${VERSION}-${GIT_COMMIT}.zip"

# Upload to S3
aws s3 cp build/lambda.zip \
    s3://fitagent-deployments-production/lambda-packages/${PACKAGE_NAME} \
    --profile production

# Tag the package
aws s3api put-object-tagging \
    --bucket fitagent-deployments-production \
    --key lambda-packages/${PACKAGE_NAME} \
    --tagging "TagSet=[
        {Key=Version,Value=${VERSION}},
        {Key=GitCommit,Value=${GIT_COMMIT}},
        {Key=Environment,Value=production}
    ]" \
    --profile production

echo "✓ Lambda package uploaded: s3://fitagent-deployments-production/lambda-packages/${PACKAGE_NAME}"

# Save package location for deployment
echo "s3://fitagent-deployments-production/lambda-packages/${PACKAGE_NAME}" > .deployment-package
```

### Step 6: Deploy CloudFormation Stack

```bash
# Create production deployment script
cat > scripts/deploy_production.sh << 'EOF'
#!/bin/bash
set -e

echo "=== FitAgent Production Deployment ==="
echo ""
echo "⚠️  WARNING: This will deploy to PRODUCTION environment"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

# Configuration
STACK_NAME="fitagent-production"
REGION="us-east-1"
PROFILE="production"
TEMPLATE="infrastructure/template.yml"
PARAMETERS="infrastructure/parameters/production.json"

# Read Lambda package location
if [ -f ".deployment-package" ]; then
    LAMBDA_PACKAGE=$(cat .deployment-package)
    echo "Using Lambda package: $LAMBDA_PACKAGE"
else
    echo "✗ Lambda package location not found"
    exit 1
fi

# Convert parameters JSON to CloudFormation format
PARAMS=$(jq -r '.Parameters | to_entries | map("ParameterKey=\(.key),ParameterValue=\(.value)") | join(" ")' $PARAMETERS)
TAGS=$(jq -r '.Tags | to_entries | map("Key=\(.key),Value=\(.value)") | join(" ")' $PARAMETERS)

echo ""
echo "[1/5] Checking if stack exists..."
STACK_EXISTS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$STACK_EXISTS" = "NOT_FOUND" ]; then
    echo "Stack does not exist - will create new stack"
    OPERATION="create"
else
    echo "Stack exists with status: $STACK_EXISTS"
    OPERATION="update"
fi

echo ""
echo "[2/5] Deploying CloudFormation stack..."
echo "Operation: $OPERATION"
echo "This may take 15-20 minutes..."
echo ""

if [ "$OPERATION" = "create" ]; then
    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://$TEMPLATE \
        --parameters $PARAMS \
        --tags $TAGS \
        --capabilities CAPABILITY_IAM \
        --region $REGION \
        --profile $PROFILE \
        --on-failure ROLLBACK
    
    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete \
        --stack-name $STACK_NAME \
        --region $REGION \
        --profile $PROFILE
else
    aws cloudformation update-stack \
        --stack-name $STACK_NAME \
        --template-body file://$TEMPLATE \
        --parameters $PARAMS \
        --tags $TAGS \
        --capabilities CAPABILITY_IAM \
        --region $REGION \
        --profile $PROFILE || {
            if [ $? -eq 254 ]; then
                echo "No updates to be performed"
            else
                exit 1
            fi
        }
    
    echo "Waiting for stack update..."
    aws cloudformation wait stack-update-complete \
        --stack-name $STACK_NAME \
        --region $REGION \
        --profile $PROFILE 2>/dev/null || true
fi

echo "✓ Stack deployment complete"

echo ""
echo "[3/5] Updating Lambda function code..."

# Get Lambda function names from stack outputs
FUNCTIONS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query 'Stacks[0].Outputs[?contains(OutputKey, `FunctionName`)].OutputValue' \
    --output text)

for FUNCTION in $FUNCTIONS; do
    echo "Updating $FUNCTION..."
    aws lambda update-function-code \
        --function-name $FUNCTION \
        --s3-bucket fitagent-deployments-production \
        --s3-key ${LAMBDA_PACKAGE#s3://fitagent-deployments-production/} \
        --region $REGION \
        --profile $PROFILE > /dev/null
    
    # Wait for update to complete
    aws lambda wait function-updated \
        --function-name $FUNCTION \
        --region $REGION \
        --profile $PROFILE
    
    echo "✓ $FUNCTION updated"
done

echo ""
echo "[4/5] Retrieving stack outputs..."
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --profile $PROFILE \
    --query 'Stacks[0].Outputs' \
    --output table

echo ""
echo "[5/5] Creating deployment record..."
cat > deployment-record-$(date +%Y%m%d-%H%M%S).json << RECORD
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "stack_name": "$STACK_NAME",
  "operation": "$OPERATION",
  "lambda_package": "$LAMBDA_PACKAGE",
  "git_commit": "$(git rev-parse HEAD)",
  "deployed_by": "$(aws sts get-caller-identity --profile $PROFILE --query 'Arn' --output text)"
}
RECORD

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Next steps:"
echo "  1. Run smoke tests: pytest tests/smoke/test_production_deployment.py"
echo "  2. Configure monitoring and alerts"
echo "  3. Enable backup policies"
echo "  4. Update Twilio webhook URL"
echo "  5. Monitor CloudWatch logs for 24 hours"
echo ""
EOF

chmod +x scripts/deploy_production.sh
```

**Run the deployment:**

```bash
./scripts/deploy_production.sh
```


### Step 7: Configure Production Monitoring

```bash
# Create CloudWatch alarms
cat > scripts/setup_production_monitoring.sh << 'EOF'
#!/bin/bash
set -e

STACK_NAME="fitagent-production"
REGION="us-east-1"
PROFILE="production"
SNS_TOPIC_ARN="arn:aws:sns:us-east-1:ACCOUNT_ID:fitagent-production-alerts"

echo "=== Setting Up Production Monitoring ==="

# Create SNS topic for alerts
echo "[1/8] Creating SNS topic for alerts..."
SNS_TOPIC_ARN=$(aws sns create-topic \
    --name fitagent-production-alerts \
    --region $REGION \
    --profile $PROFILE \
    --query 'TopicArn' \
    --output text)

echo "✓ SNS Topic created: $SNS_TOPIC_ARN"

# Subscribe email to SNS topic
read -p "Enter email for alerts: " ALERT_EMAIL
aws sns subscribe \
    --topic-arn $SNS_TOPIC_ARN \
    --protocol email \
    --notification-endpoint $ALERT_EMAIL \
    --region $REGION \
    --profile $PROFILE

echo "✓ Email subscription created (check inbox for confirmation)"

# Lambda error rate alarm
echo ""
echo "[2/8] Creating Lambda error rate alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-lambda-errors \
    --alarm-description "Alert when Lambda error rate exceeds threshold" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=FunctionName,Value=fitagent-message-processor-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ Lambda error alarm created"

# Lambda duration alarm
echo ""
echo "[3/8] Creating Lambda duration alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-lambda-duration \
    --alarm-description "Alert when Lambda duration is too high" \
    --metric-name Duration \
    --namespace AWS/Lambda \
    --statistic Average \
    --period 300 \
    --threshold 30000 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 3 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=FunctionName,Value=fitagent-message-processor-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ Lambda duration alarm created"

# Lambda throttles alarm
echo ""
echo "[4/8] Creating Lambda throttles alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-lambda-throttles \
    --alarm-description "Alert when Lambda is throttled" \
    --metric-name Throttles \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=FunctionName,Value=fitagent-message-processor-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ Lambda throttles alarm created"

# DynamoDB read throttles
echo ""
echo "[5/8] Creating DynamoDB read throttles alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-dynamodb-read-throttles \
    --alarm-description "Alert when DynamoDB reads are throttled" \
    --metric-name ReadThrottleEvents \
    --namespace AWS/DynamoDB \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=TableName,Value=fitagent-main-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ DynamoDB read throttles alarm created"

# DynamoDB write throttles
echo ""
echo "[6/8] Creating DynamoDB write throttles alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-dynamodb-write-throttles \
    --alarm-description "Alert when DynamoDB writes are throttled" \
    --metric-name WriteThrottleEvents \
    --namespace AWS/DynamoDB \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 2 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=TableName,Value=fitagent-main-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ DynamoDB write throttles alarm created"

# SQS dead letter queue alarm
echo ""
echo "[7/8] Creating SQS DLQ alarm..."
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-production-dlq-messages \
    --alarm-description "Alert when messages land in DLQ" \
    --metric-name ApproximateNumberOfMessagesVisible \
    --namespace AWS/SQS \
    --statistic Average \
    --period 300 \
    --threshold 1 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions $SNS_TOPIC_ARN \
    --dimensions Name=QueueName,Value=fitagent-messages-dlq-production \
    --region $REGION \
    --profile $PROFILE

echo "✓ SQS DLQ alarm created"

# Create CloudWatch dashboard
echo ""
echo "[8/8] Creating CloudWatch dashboard..."
cat > /tmp/dashboard.json << DASHBOARD
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum", "label": "Invocations"}],
          [".", "Errors", {"stat": "Sum", "label": "Errors"}],
          [".", "Throttles", {"stat": "Sum", "label": "Throttles"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$REGION",
        "title": "Lambda Metrics",
        "period": 300
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Duration", {"stat": "Average", "label": "Avg Duration"}],
          ["...", {"stat": "Maximum", "label": "Max Duration"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$REGION",
        "title": "Lambda Duration",
        "period": 300,
        "yAxis": {"left": {"label": "Milliseconds"}}
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ConsumedReadCapacityUnits", {"stat": "Sum"}],
          [".", "ConsumedWriteCapacityUnits", {"stat": "Sum"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$REGION",
        "title": "DynamoDB Capacity",
        "period": 300
      }
    },
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/DynamoDB", "ReadThrottleEvents", {"stat": "Sum"}],
          [".", "WriteThrottleEvents", {"stat": "Sum"}]
        ],
        "view": "timeSeries",
        "stacked": false,
        "region": "$REGION",
        "title": "DynamoDB Throttles",
        "period": 300
      }
    }
  ]
}
DASHBOARD

aws cloudwatch put-dashboard \
    --dashboard-name FitAgent-Production \
    --dashboard-body file:///tmp/dashboard.json \
    --region $REGION \
    --profile $PROFILE

echo "✓ CloudWatch dashboard created"

echo ""
echo "=== Monitoring Setup Complete ==="
echo ""
echo "Dashboard: https://console.aws.amazon.com/cloudwatch/home?region=$REGION#dashboards:name=FitAgent-Production"
echo "Alarms: https://console.aws.amazon.com/cloudwatch/home?region=$REGION#alarmsV2:"
echo ""
EOF

chmod +x scripts/setup_production_monitoring.sh
./scripts/setup_production_monitoring.sh
```


### Step 8: Enable DynamoDB Backups

```bash
# Enable point-in-time recovery
aws dynamodb update-continuous-backups \
    --table-name fitagent-main-production \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
    --region us-east-1 \
    --profile production

echo "✓ Point-in-time recovery enabled"

# Create backup plan with AWS Backup
aws backup create-backup-plan \
    --backup-plan '{
      "BackupPlanName": "FitAgent-Production-Daily",
      "Rules": [{
        "RuleName": "DailyBackup",
        "TargetBackupVaultName": "Default",
        "ScheduleExpression": "cron(0 5 * * ? *)",
        "StartWindowMinutes": 60,
        "CompletionWindowMinutes": 120,
        "Lifecycle": {
          "DeleteAfterDays": 35
        }
      }]
    }' \
    --region us-east-1 \
    --profile production

echo "✓ Backup plan created (daily at 5 AM UTC, 35-day retention)"

# Tag DynamoDB table for backup
aws dynamodb tag-resource \
    --resource-arn $(aws dynamodb describe-table \
        --table-name fitagent-main-production \
        --query 'Table.TableArn' \
        --output text \
        --profile production) \
    --tags Key=BackupPolicy,Value=Daily \
    --region us-east-1 \
    --profile production

echo "✓ Backup tags applied"
```

### Step 9: Configure Twilio Production Webhook

```bash
# Get API Gateway URL from CloudFormation outputs
API_URL=$(aws cloudformation describe-stacks \
    --stack-name fitagent-production \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
    --output text \
    --region us-east-1 \
    --profile production)

echo "Production Webhook URL: $API_URL"
echo ""
echo "Configure in Twilio Console:"
echo "1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/incoming"
echo "2. Select your production WhatsApp number"
echo "3. Under 'Messaging', set:"
echo "   - When a message comes in: $API_URL"
echo "   - HTTP Method: POST"
echo "4. Click 'Save'"
echo ""
read -p "Press Enter after configuring Twilio..."
```


### Step 10: Run Production Smoke Tests

```bash
# Create production smoke tests
mkdir -p tests/smoke

cat > tests/smoke/test_production_deployment.py << 'EOF'
"""
Production deployment smoke tests.
Run these after deploying to verify basic functionality.
"""
import boto3
import pytest
import os

# Use production profile
os.environ['AWS_PROFILE'] = 'production'
REGION = 'us-east-1'
STACK_NAME = 'fitagent-production'

@pytest.fixture
def cloudformation():
    return boto3.client('cloudformation', region_name=REGION)

@pytest.fixture
def dynamodb():
    return boto3.client('dynamodb', region_name=REGION)

@pytest.fixture
def lambda_client():
    return boto3.client('lambda', region_name=REGION)

@pytest.fixture
def stack_outputs(cloudformation):
    response = cloudformation.describe_stacks(StackName=STACK_NAME)
    outputs = response['Stacks'][0]['Outputs']
    return {o['OutputKey']: o['OutputValue'] for o in outputs}


class TestStackDeployment:
    """Verify CloudFormation stack is deployed correctly."""
    
    def test_stack_exists(self, cloudformation):
        """Stack should exist and be in healthy state."""
        response = cloudformation.describe_stacks(StackName=STACK_NAME)
        stack = response['Stacks'][0]
        
        assert stack['StackStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']
        assert 'production' in stack['StackName'].lower()
    
    def test_stack_has_required_outputs(self, stack_outputs):
        """Stack should have all required outputs."""
        required_outputs = [
            'TableName',
            'MessageProcessorFunctionName',
            'WebhookUrl'
        ]
        
        for output in required_outputs:
            assert output in stack_outputs, f"Missing output: {output}"


class TestDynamoDBTable:
    """Verify DynamoDB table configuration."""
    
    def test_table_exists(self, dynamodb, stack_outputs):
        """Table should exist."""
        table_name = stack_outputs['TableName']
        response = dynamodb.describe_table(TableName=table_name)
        
        assert response['Table']['TableStatus'] == 'ACTIVE'
    
    def test_table_has_required_gsis(self, dynamodb, stack_outputs):
        """Table should have all required GSIs."""
        table_name = stack_outputs['TableName']
        response = dynamodb.describe_table(TableName=table_name)
        
        gsi_names = [gsi['IndexName'] for gsi in response['Table'].get('GlobalSecondaryIndexes', [])]
        
        required_gsis = [
            'phone-number-index',
            'session-date-index',
            'payment-status-index'
        ]
        
        for gsi in required_gsis:
            assert gsi in gsi_names, f"Missing GSI: {gsi}"
    
    def test_point_in_time_recovery_enabled(self, dynamodb, stack_outputs):
        """Point-in-time recovery should be enabled."""
        table_name = stack_outputs['TableName']
        response = dynamodb.describe_continuous_backups(TableName=table_name)
        
        pitr_status = response['ContinuousBackupsDescription']['PointInTimeRecoveryDescription']['PointInTimeRecoveryStatus']
        assert pitr_status == 'ENABLED'


class TestLambdaFunctions:
    """Verify Lambda functions are configured correctly."""
    
    def test_message_processor_exists(self, lambda_client, stack_outputs):
        """Message processor Lambda should exist."""
        function_name = stack_outputs['MessageProcessorFunctionName']
        response = lambda_client.get_function(FunctionName=function_name)
        
        assert response['Configuration']['State'] == 'Active'
        assert response['Configuration']['Runtime'].startswith('python3')
    
    def test_lambda_has_correct_environment(self, lambda_client, stack_outputs):
        """Lambda should have production environment variables."""
        function_name = stack_outputs['MessageProcessorFunctionName']
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        
        env_vars = response['Environment']['Variables']
        
        assert env_vars.get('ENVIRONMENT') == 'production'
        assert 'DYNAMODB_TABLE' in env_vars
        assert 'production' in env_vars['DYNAMODB_TABLE'].lower()
    
    def test_lambda_has_xray_enabled(self, lambda_client, stack_outputs):
        """Lambda should have X-Ray tracing enabled."""
        function_name = stack_outputs['MessageProcessorFunctionName']
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        
        assert response['TracingConfig']['Mode'] == 'Active'


class TestMonitoring:
    """Verify monitoring is configured."""
    
    def test_cloudwatch_alarms_exist(self):
        """CloudWatch alarms should be configured."""
        cloudwatch = boto3.client('cloudwatch', region_name=REGION)
        response = cloudwatch.describe_alarms(
            AlarmNamePrefix='fitagent-production'
        )
        
        assert len(response['MetricAlarms']) >= 5, "Missing CloudWatch alarms"
    
    def test_sns_topic_exists(self):
        """SNS topic for alerts should exist."""
        sns = boto3.client('sns', region_name=REGION)
        response = sns.list_topics()
        
        topic_arns = [t['TopicArn'] for t in response['Topics']]
        production_topics = [t for t in topic_arns if 'production' in t.lower()]
        
        assert len(production_topics) > 0, "No production SNS topics found"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
EOF

# Run smoke tests
pytest tests/smoke/test_production_deployment.py -v

echo ""
echo "✓ All smoke tests passed!"
```


---

## Post-Deployment Configuration

### Configure OAuth for Calendar Integration

**Google Calendar:**

```bash
# Store production OAuth credentials
aws secretsmanager create-secret \
    --name fitagent/production/google-oauth \
    --description "Google Calendar OAuth credentials for production" \
    --secret-string '{
      "client_id": "YOUR_GOOGLE_CLIENT_ID",
      "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
      "redirect_uri": "https://api.fitagent.com/oauth/callback"
    }' \
    --region us-east-1 \
    --profile production

# Tag the secret
aws secretsmanager tag-resource \
    --secret-id fitagent/production/google-oauth \
    --tags Key=Environment,Value=production Key=Service,Value=GoogleCalendar \
    --region us-east-1 \
    --profile production
```

**Microsoft Outlook:**

```bash
# Store production OAuth credentials
aws secretsmanager create-secret \
    --name fitagent/production/outlook-oauth \
    --description "Outlook Calendar OAuth credentials for production" \
    --secret-string '{
      "client_id": "YOUR_OUTLOOK_CLIENT_ID",
      "client_secret": "YOUR_OUTLOOK_CLIENT_SECRET",
      "redirect_uri": "https://api.fitagent.com/oauth/callback"
    }' \
    --region us-east-1 \
    --profile production

# Tag the secret
aws secretsmanager tag-resource \
    --secret-id fitagent/production/outlook-oauth \
    --tags Key=Environment,Value=production Key=Service,Value=OutlookCalendar \
    --region us-east-1 \
    --profile production
```

### Enable Auto-Scaling for DynamoDB

```bash
# Register DynamoDB table as scalable target
aws application-autoscaling register-scalable-target \
    --service-namespace dynamodb \
    --resource-id table/fitagent-main-production \
    --scalable-dimension dynamodb:table:ReadCapacityUnits \
    --min-capacity 25 \
    --max-capacity 200 \
    --region us-east-1 \
    --profile production

aws application-autoscaling register-scalable-target \
    --service-namespace dynamodb \
    --resource-id table/fitagent-main-production \
    --scalable-dimension dynamodb:table:WriteCapacityUnits \
    --min-capacity 25 \
    --max-capacity 200 \
    --region us-east-1 \
    --profile production

# Create scaling policy for reads
aws application-autoscaling put-scaling-policy \
    --service-namespace dynamodb \
    --resource-id table/fitagent-main-production \
    --scalable-dimension dynamodb:table:ReadCapacityUnits \
    --policy-name FitAgentReadAutoScaling \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
      "TargetValue": 70.0,
      "PredefinedMetricSpecification": {
        "PredefinedMetricType": "DynamoDBReadCapacityUtilization"
      },
      "ScaleInCooldown": 60,
      "ScaleOutCooldown": 60
    }' \
    --region us-east-1 \
    --profile production

# Create scaling policy for writes
aws application-autoscaling put-scaling-policy \
    --service-namespace dynamodb \
    --resource-id table/fitagent-main-production \
    --scalable-dimension dynamodb:table:WriteCapacityUnits \
    --policy-name FitAgentWriteAutoScaling \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
      "TargetValue": 70.0,
      "PredefinedMetricSpecification": {
        "PredefinedMetricType": "DynamoDBWriteCapacityUtilization"
      },
      "ScaleInCooldown": 60,
      "ScaleOutCooldown": 60
    }' \
    --region us-east-1 \
    --profile production

echo "✓ Auto-scaling configured (target: 70% utilization)"
```

### Configure Log Insights Queries

```bash
# Save useful queries for production monitoring
cat > cloudwatch-insights-queries.txt << 'EOF'
# Query 1: Error Analysis
fields @timestamp, @message, error, trainer_id, phone_number
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100

# Query 2: Performance Metrics
fields @timestamp, duration, handoff_count, trainer_id
| stats avg(duration) as avg_duration, max(duration) as max_duration, count() as total_requests by bin(5m)

# Query 3: Agent Handoffs
fields @timestamp, handoff_from, handoff_to, handoff_reason, trainer_id
| filter @message like /handoff/
| stats count() by handoff_from, handoff_to

# Query 4: Twilio Webhook Requests
fields @timestamp, phone_number, message_body, response_status
| filter @message like /Webhook request received/
| sort @timestamp desc

# Query 5: DynamoDB Operations
fields @timestamp, operation, table_name, duration_ms
| filter @message like /DynamoDB/
| stats avg(duration_ms) as avg_duration, max(duration_ms) as max_duration by operation

# Query 6: Session Confirmations
fields @timestamp, session_id, trainer_id, confirmation_status
| filter @message like /session_confirmation/
| stats count() by confirmation_status
EOF

echo "✓ CloudWatch Insights queries saved to cloudwatch-insights-queries.txt"
```


---

## Gradual Feature Rollout

### Phase 1: Initial Production (Week 1)

**Objective:** Verify infrastructure stability and basic functionality

```bash
# Verify feature flags are set conservatively
aws lambda get-function-configuration \
    --function-name fitagent-message-processor-production \
    --query 'Environment.Variables.ENABLE_MULTI_AGENT' \
    --output text \
    --region us-east-1 \
    --profile production

# Should output: false or not set
```

**Monitoring checklist:**
- [ ] Lambda invocations successful (>99%)
- [ ] DynamoDB operations healthy
- [ ] No throttling errors
- [ ] Response times < 10 seconds
- [ ] No messages in DLQ
- [ ] Twilio webhook responding correctly

**Duration:** 7 days of monitoring

### Phase 2: Pilot User Onboarding (Week 2)

**Objective:** Onboard first real trainers and validate system with actual usage

```bash
# Monitor first user registrations
aws logs tail /aws/lambda/fitagent-message-processor-production \
    --follow \
    --filter-pattern "trainer registration" \
    --region us-east-1 \
    --profile production
```

**Pilot criteria:**
- 5-10 trainers
- Mix of usage patterns (different student counts, session frequencies)
- Willing to provide feedback
- Understand this is initial launch

**Monitoring (7 days):**
- User feedback collection
- Error rate monitoring
- Performance metrics
- Feature usage patterns

### Phase 3: Enable Multi-Agent (Week 3+)

**Objective:** Enable advanced features for stable pilot users

```bash
# Enable multi-agent for specific trainers via feature flags
cat > enable-multi-agent-pilot.py << 'EOF'
import boto3

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('fitagent-main-production')

# List of pilot trainer IDs
pilot_trainers = [
    'TRAINER#uuid-1',
    'TRAINER#uuid-2',
    # Add pilot trainer IDs
]

for trainer_id in pilot_trainers:
    table.put_item(Item={
        'PK': trainer_id,
        'SK': 'FEATURE_FLAGS',
        'enable_multi_agent': True,
        'enable_session_confirmation': True,
        'rollout_phase': 'pilot',
        'enabled_at': '2024-01-15T00:00:00Z'
    })
    print(f"✓ Enabled advanced features for {trainer_id}")

print(f"\nTotal trainers in pilot: {len(pilot_trainers)}")
EOF

python enable-multi-agent-pilot.py
```

**Monitoring (14 days):**
- Compare pilot vs standard users
- Monitor handoff success rate
- Check for increased errors
- Verify response times acceptable
- Gather user feedback

### Phase 4: Broader Rollout (Week 5+)

Based on pilot success, gradually enable for more users:

```bash
# Enable globally via Lambda environment variable (when ready)
aws lambda update-function-configuration \
    --function-name fitagent-message-processor-production \
    --environment "Variables={
        ENVIRONMENT=production,
        DYNAMODB_TABLE=fitagent-main-production,
        ENABLE_MULTI_AGENT=true,
        ENABLE_SESSION_CONFIRMATION=true
    }" \
    --region us-east-1 \
    --profile production

echo "✓ Advanced features enabled for all users"
```

**Post-rollout monitoring (ongoing):**
- Continuous monitoring of all metrics
- Weekly review of performance data
- Monthly capacity planning
- Quarterly feature reviews


---

## Rollback Procedures

### Emergency Rollback (< 5 minutes)

**When to use:** Critical production outage, data corruption, security incident

```bash
# Immediate rollback script
cat > scripts/emergency_rollback.sh << 'EOF'
#!/bin/bash
set -e

echo "⚠️  EMERGENCY ROLLBACK INITIATED"
echo ""
read -p "Confirm emergency rollback (type 'ROLLBACK'): " CONFIRM

if [ "$CONFIRM" != "ROLLBACK" ]; then
    echo "Rollback cancelled"
    exit 0
fi

STACK_NAME="fitagent-production"
REGION="us-east-1"
PROFILE="production"

# Step 1: Disable advanced features immediately
echo "[1/3] Disabling advanced features..."
aws lambda update-function-configuration \
    --function-name fitagent-message-processor-production \
    --environment "Variables={
        ENVIRONMENT=production,
        DYNAMODB_TABLE=fitagent-main-production,
        ENABLE_MULTI_AGENT=false,
        ENABLE_SESSION_CONFIRMATION=false
    }" \
    --region $REGION \
    --profile $PROFILE

echo "✓ Advanced features disabled"

# Step 2: Revert to previous Lambda version
echo ""
echo "[2/3] Reverting Lambda to previous version..."
PREVIOUS_VERSION=$(aws lambda list-versions-by-function \
    --function-name fitagent-message-processor-production \
    --region $REGION \
    --profile $PROFILE \
    --query 'Versions[-2].Version' \
    --output text)

aws lambda update-alias \
    --function-name fitagent-message-processor-production \
    --name production \
    --function-version $PREVIOUS_VERSION \
    --region $REGION \
    --profile $PROFILE 2>/dev/null || echo "No alias to update"

echo "✓ Lambda reverted to version $PREVIOUS_VERSION"

# Step 3: Send alert
echo ""
echo "[3/3] Sending alert notification..."
SNS_TOPIC=$(aws sns list-topics \
    --region $REGION \
    --profile $PROFILE \
    --query 'Topics[?contains(TopicArn, `production-alerts`)].TopicArn' \
    --output text)

if [ ! -z "$SNS_TOPIC" ]; then
    aws sns publish \
        --topic-arn $SNS_TOPIC \
        --subject "EMERGENCY ROLLBACK: FitAgent Production" \
        --message "Emergency rollback executed at $(date). Advanced features disabled. Lambda reverted to version $PREVIOUS_VERSION." \
        --region $REGION \
        --profile $PROFILE
    echo "✓ Alert sent"
fi

echo ""
echo "=== EMERGENCY ROLLBACK COMPLETE ==="
echo ""
echo "Next steps:"
echo "  1. Monitor CloudWatch logs"
echo "  2. Verify system is stable"
echo "  3. Investigate root cause"
echo "  4. Schedule post-mortem"
EOF

chmod +x scripts/emergency_rollback.sh
```

### Gradual Rollback (Recommended)

**When to use:** Non-critical issues, performance degradation

```bash
# Gradual rollback - reduce feature flag percentage
# Phase 1: Reduce to 50%
# Phase 2: Reduce to 25%
# Phase 3: Reduce to 10%
# Phase 4: Disable completely

# Update feature flags in DynamoDB to reduce exposure
```

### Full Stack Rollback

**When to use:** Infrastructure issues, need to revert entire deployment

```bash
# WARNING: This will delete all resources
# Ensure data is backed up before proceeding

aws cloudformation delete-stack \
    --stack-name fitagent-production \
    --region us-east-1 \
    --profile production

# Wait for deletion
aws cloudformation wait stack-delete-complete \
    --stack-name fitagent-production \
    --region us-east-1 \
    --profile production

# Restore from backup if needed
```


---

## Monitoring and Observability

### Key Metrics to Track

**Lambda Metrics:**
- Invocation count (target: steady growth)
- Error rate (target: < 1%)
- Duration p50/p95/p99 (target: < 5s / < 10s / < 30s)
- Concurrent executions (monitor for limits)
- Throttles (target: 0)

**DynamoDB Metrics:**
- Read/write capacity utilization (target: 60-80%)
- Throttled requests (target: 0)
- System errors (target: 0)
- Latency p50/p95/p99 (target: < 10ms / < 50ms / < 100ms)

**Business Metrics:**
- Messages processed per hour
- Active trainers per day
- Sessions scheduled per day
- Payment registrations per day
- Calendar sync success rate
- Agent handoff rate (if multi-agent enabled)

**Cost Metrics:**
- Lambda invocation costs
- DynamoDB capacity costs
- S3 storage costs
- Data transfer costs
- Total daily/monthly spend

### CloudWatch Dashboards

Access production dashboard:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=FitAgent-Production
```

### Setting Up Alerts

**Critical Alerts (Page on-call):**
- Lambda error rate > 5% for 5 minutes
- DynamoDB throttling > 50 events in 5 minutes
- Messages in DLQ > 10
- Lambda duration > 60s (p95)
- API Gateway 5xx errors > 10 in 5 minutes

**Warning Alerts (Email/Slack):**
- Lambda error rate > 2% for 10 minutes
- DynamoDB capacity > 80% for 15 minutes
- Lambda duration > 30s (p95)
- Cost exceeds daily budget by 20%

**Info Alerts (Email):**
- Daily summary report
- Weekly performance report
- Monthly cost report

### Log Analysis

**Real-time log monitoring:**
```bash
# Tail production logs
aws logs tail /aws/lambda/fitagent-message-processor-production \
    --follow \
    --format short \
    --region us-east-1 \
    --profile production
```

**Search for errors:**
```bash
# Last hour of errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/fitagent-message-processor-production \
    --start-time $(date -u -d '1 hour ago' +%s)000 \
    --filter-pattern "ERROR" \
    --region us-east-1 \
    --profile production
```


---

## Security and Compliance

### Security Checklist

- [ ] **IAM Roles:** Follow least privilege principle
- [ ] **Encryption at Rest:** Enabled for DynamoDB, S3, Secrets Manager
- [ ] **Encryption in Transit:** All API calls use HTTPS/TLS 1.2+
- [ ] **Secrets Management:** No hardcoded credentials, use Secrets Manager
- [ ] **VPC Configuration:** Lambda in VPC if accessing private resources
- [ ] **CloudTrail:** Enabled for audit logging
- [ ] **GuardDuty:** Enabled for threat detection
- [ ] **WAF:** Configured on API Gateway (if applicable)
- [ ] **DDoS Protection:** AWS Shield Standard enabled
- [ ] **Backup Strategy:** Point-in-time recovery + daily backups
- [ ] **Access Control:** MFA required for production access
- [ ] **Log Sanitization:** PII masked in CloudWatch logs

### GDPR Compliance

**Data Protection:**
- Personal data encrypted at rest and in transit
- Phone numbers hashed in logs
- OAuth tokens encrypted with KMS
- Data retention policies enforced (30 days for logs)

**User Rights:**
- Right to access: Trainers can export their data
- Right to deletion: Implement data deletion workflow
- Right to portability: Data export in JSON format

**Data Processing Agreement:**
- Document data flows
- Identify data processors (AWS, Twilio)
- Maintain records of processing activities

### Audit Logging

Enable CloudTrail for all API calls:

```bash
# Create CloudTrail trail
aws cloudtrail create-trail \
    --name fitagent-production-audit \
    --s3-bucket-name fitagent-audit-logs-production \
    --is-multi-region-trail \
    --enable-log-file-validation \
    --region us-east-1 \
    --profile production

# Start logging
aws cloudtrail start-logging \
    --name fitagent-production-audit \
    --region us-east-1 \
    --profile production

echo "✓ CloudTrail audit logging enabled"
```

### Penetration Testing

**Before production launch:**
- Conduct security assessment
- Test authentication/authorization
- Test input validation
- Test rate limiting
- Test for common vulnerabilities (OWASP Top 10)

**Ongoing:**
- Quarterly security reviews
- Annual penetration testing
- Continuous vulnerability scanning


---

## Disaster Recovery

### Backup Strategy

**DynamoDB:**
- Point-in-time recovery: Enabled (restore to any point in last 35 days)
- Daily backups: Automated via AWS Backup
- Retention: 35 days
- Cross-region replication: Optional (for critical deployments)

**S3 (Receipt Storage):**
- Versioning: Enabled
- Lifecycle policy: Move to Glacier after 90 days
- Cross-region replication: Optional

**Lambda Code:**
- Versioned in S3 deployment bucket
- Git tags for each deployment
- Deployment records maintained

### Recovery Procedures

**Scenario 1: DynamoDB Table Corruption**

```bash
# Restore from point-in-time
aws dynamodb restore-table-to-point-in-time \
    --source-table-name fitagent-main-production \
    --target-table-name fitagent-main-production-restored \
    --restore-date-time 2024-01-15T10:00:00Z \
    --region us-east-1 \
    --profile production

# Wait for restore to complete
aws dynamodb wait table-exists \
    --table-name fitagent-main-production-restored \
    --region us-east-1 \
    --profile production

# Update Lambda to use restored table
# Verify data integrity
# Switch traffic to restored table
```

**Scenario 2: Lambda Function Failure**

```bash
# Revert to previous version (see Emergency Rollback section)
./scripts/emergency_rollback.sh
```

**Scenario 3: Complete Region Failure**

```bash
# If using cross-region replication:
# 1. Update Route53 to point to backup region
# 2. Verify backup region resources are healthy
# 3. Update Twilio webhook to backup region URL
# 4. Monitor for issues
```

### RTO and RPO Targets

**Recovery Time Objective (RTO):**
- Critical: 1 hour
- High: 4 hours
- Medium: 24 hours

**Recovery Point Objective (RPO):**
- DynamoDB: 5 minutes (point-in-time recovery)
- S3: 0 (versioning enabled)
- Lambda: 0 (versioned deployments)

### Disaster Recovery Testing

**Quarterly DR drill:**
1. Simulate table corruption
2. Restore from backup
3. Verify data integrity
4. Measure recovery time
5. Document lessons learned


---

## Cost Management

### Estimated Production Costs

**Assumptions:**
- 10,000 messages/day (300K/month)
- 500 active trainers
- 5,000 sessions/month
- 30-day log retention

**Monthly Cost Breakdown:**

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| Lambda (Message Processor) | 300K invocations, 1GB RAM, 5s avg | $25 |
| Lambda (Session Confirmation) | 5K invocations, 512MB RAM, 2s avg | $2 |
| Lambda (Reminders) | 10K invocations, 512MB RAM, 1s avg | $3 |
| DynamoDB | 50 RCU, 50 WCU, 10GB storage | $35 |
| DynamoDB (Auto-scaling) | Variable capacity | $20 |
| S3 (Receipts) | 10GB storage, 10K requests | $2 |
| S3 (Backups) | 50GB storage | $1 |
| CloudWatch Logs | 50GB ingestion, 30-day retention | $25 |
| CloudWatch Metrics | Custom metrics | $5 |
| EventBridge | 10K events/month | $0.10 |
| SQS | 300K requests | $0.12 |
| Secrets Manager | 5 secrets | $2 |
| KMS | 10K requests | $1 |
| API Gateway | 300K requests | $1 |
| Data Transfer | 100GB out | $9 |
| **Total** | | **~$131/month** |

**Cost Optimization Tips:**

1. **Lambda:**
   - Use ARM64 architecture (20% cheaper)
   - Optimize memory allocation
   - Reduce cold starts with provisioned concurrency (if needed)

2. **DynamoDB:**
   - Use on-demand pricing if traffic is unpredictable
   - Optimize GSI usage
   - Enable auto-scaling to avoid over-provisioning

3. **CloudWatch Logs:**
   - Reduce log retention to 14 days (saves 50%)
   - Filter logs before ingestion
   - Use log sampling for high-volume logs

4. **S3:**
   - Use Intelligent-Tiering for receipts
   - Enable lifecycle policies
   - Compress backups

### Budget Alerts

```bash
# Create budget with alerts
aws budgets create-budget \
    --account-id $(aws sts get-caller-identity --query Account --output text) \
    --budget '{
      "BudgetName": "FitAgent-Production-Monthly",
      "BudgetLimit": {
        "Amount": "200",
        "Unit": "USD"
      },
      "TimeUnit": "MONTHLY",
      "BudgetType": "COST"
    }' \
    --notifications-with-subscribers '[
      {
        "Notification": {
          "NotificationType": "ACTUAL",
          "ComparisonOperator": "GREATER_THAN",
          "Threshold": 80,
          "ThresholdType": "PERCENTAGE"
        },
        "Subscribers": [{
          "SubscriptionType": "EMAIL",
          "Address": "devops@fitagent.com"
        }]
      },
      {
        "Notification": {
          "NotificationType": "FORECASTED",
          "ComparisonOperator": "GREATER_THAN",
          "Threshold": 100,
          "ThresholdType": "PERCENTAGE"
        },
        "Subscribers": [{
          "SubscriptionType": "EMAIL",
          "Address": "devops@fitagent.com"
        }]
      }
    ]' \
    --region us-east-1 \
    --profile production

echo "✓ Budget alerts configured (80% actual, 100% forecasted)"
```

### Cost Monitoring

**Daily cost check:**
```bash
# Get yesterday's costs
aws ce get-cost-and-usage \
    --time-period Start=$(date -u -d '1 day ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=SERVICE \
    --region us-east-1 \
    --profile production
```


---

## Troubleshooting

### Common Production Issues

#### Issue 1: High Lambda Error Rate

**Symptoms:**
- CloudWatch alarm triggered
- Error rate > 5%
- Users reporting failures

**Diagnosis:**
```bash
# Check recent errors
aws logs filter-log-events \
    --log-group-name /aws/lambda/fitagent-message-processor-production \
    --start-time $(date -u -d '1 hour ago' +%s)000 \
    --filter-pattern "ERROR" \
    --region us-east-1 \
    --profile production | jq '.events[].message'

# Check error types
aws logs insights query \
    --log-group-name /aws/lambda/fitagent-message-processor-production \
    --start-time $(date -u -d '1 hour ago' +%s) \
    --end-time $(date -u +%s) \
    --query-string 'fields @timestamp, error | filter @message like /ERROR/ | stats count() by error'
```

**Resolution:**
1. Identify error pattern
2. Check if it's a known issue
3. Apply hotfix if available
4. Otherwise, execute emergency rollback

#### Issue 2: DynamoDB Throttling

**Symptoms:**
- `ProvisionedThroughputExceededException` in logs
- Slow response times
- Failed operations

**Diagnosis:**
```bash
# Check throttle metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ReadThrottleEvents \
    --dimensions Name=TableName,Value=fitagent-main-production \
    --start-time $(date -u -d '1 hour ago' --iso-8601) \
    --end-time $(date -u --iso-8601) \
    --period 300 \
    --statistics Sum \
    --region us-east-1 \
    --profile production
```

**Resolution:**
```bash
# Temporarily increase capacity
aws dynamodb update-table \
    --table-name fitagent-main-production \
    --provisioned-throughput ReadCapacityUnits=100,WriteCapacityUnits=100 \
    --region us-east-1 \
    --profile production

# Or enable on-demand mode
aws dynamodb update-table \
    --table-name fitagent-main-production \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1 \
    --profile production
```

#### Issue 3: Messages in Dead Letter Queue

**Symptoms:**
- DLQ alarm triggered
- Messages not being processed

**Diagnosis:**
```bash
# Check DLQ messages
aws sqs receive-message \
    --queue-url https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/fitagent-messages-dlq-production \
    --max-number-of-messages 10 \
    --region us-east-1 \
    --profile production
```

**Resolution:**
1. Analyze failed messages
2. Fix underlying issue
3. Replay messages from DLQ:

```bash
# Replay DLQ messages (after fixing issue)
cat > scripts/replay_dlq.sh << 'EOF'
#!/bin/bash
DLQ_URL="https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/fitagent-messages-dlq-production"
MAIN_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/fitagent-messages-production"

while true; do
    MSG=$(aws sqs receive-message --queue-url $DLQ_URL --max-number-of-messages 1 --profile production)
    
    if [ -z "$MSG" ] || [ "$MSG" = "null" ]; then
        echo "No more messages in DLQ"
        break
    fi
    
    BODY=$(echo $MSG | jq -r '.Messages[0].Body')
    RECEIPT=$(echo $MSG | jq -r '.Messages[0].ReceiptHandle')
    
    # Send to main queue
    aws sqs send-message --queue-url $MAIN_QUEUE_URL --message-body "$BODY" --profile production
    
    # Delete from DLQ
    aws sqs delete-message --queue-url $DLQ_URL --receipt-handle "$RECEIPT" --profile production
    
    echo "Replayed 1 message"
done
EOF

chmod +x scripts/replay_dlq.sh
./scripts/replay_dlq.sh
```

#### Issue 4: Twilio Webhook Failures

**Symptoms:**
- Messages not reaching Lambda
- Twilio showing webhook errors

**Diagnosis:**
```bash
# Check API Gateway logs
aws logs tail /aws/apigateway/fitagent-production \
    --follow \
    --region us-east-1 \
    --profile production

# Check Twilio webhook logs
# Go to: https://console.twilio.com/us1/monitor/logs/sms
```

**Resolution:**
1. Verify webhook URL is correct
2. Check API Gateway is healthy
3. Verify Twilio signature validation
4. Check Lambda permissions

#### Issue 5: High Costs

**Symptoms:**
- Budget alert triggered
- Unexpected cost increase

**Diagnosis:**
```bash
# Analyze cost by service
aws ce get-cost-and-usage \
    --time-period Start=$(date -u -d '7 days ago' +%Y-%m-%d),End=$(date -u +%Y-%m-%d) \
    --granularity DAILY \
    --metrics BlendedCost \
    --group-by Type=SERVICE \
    --region us-east-1 \
    --profile production
```

**Resolution:**
1. Identify cost spike source
2. Check for runaway processes
3. Optimize resource usage
4. Review and adjust capacity


---

## Maintenance and Operations

### Regular Maintenance Tasks

**Daily:**
- [ ] Review CloudWatch dashboard
- [ ] Check error rates and alerts
- [ ] Monitor cost trends
- [ ] Review DLQ for failed messages

**Weekly:**
- [ ] Review performance metrics
- [ ] Analyze slow queries
- [ ] Check backup status
- [ ] Review security logs
- [ ] Update documentation

**Monthly:**
- [ ] Review and optimize costs
- [ ] Update dependencies
- [ ] Security patch review
- [ ] Capacity planning review
- [ ] Disaster recovery drill

**Quarterly:**
- [ ] Security audit
- [ ] Performance optimization
- [ ] Architecture review
- [ ] Cost optimization review

### Deployment Checklist

Before each production deployment:

- [ ] All tests passing in staging
- [ ] Code review completed
- [ ] Security review completed
- [ ] Performance testing completed
- [ ] Rollback plan documented
- [ ] Change management ticket approved
- [ ] Stakeholders notified
- [ ] Monitoring configured
- [ ] On-call engineer available
- [ ] Deployment window scheduled

### On-Call Runbook

**Incident Response Process:**

1. **Acknowledge Alert** (< 5 minutes)
   - Check alert details
   - Assess severity
   - Notify team if needed

2. **Initial Assessment** (< 15 minutes)
   - Check CloudWatch dashboard
   - Review recent deployments
   - Check error logs
   - Determine impact

3. **Mitigation** (< 30 minutes)
   - Apply immediate fix if known
   - Execute rollback if needed
   - Communicate status

4. **Resolution** (< 2 hours)
   - Implement permanent fix
   - Verify system stability
   - Update documentation

5. **Post-Mortem** (within 48 hours)
   - Document incident
   - Identify root cause
   - Create action items
   - Update runbook

### Contact Information

**Escalation Path:**

1. **Level 1:** On-call engineer
   - Response time: 15 minutes
   - Contact: PagerDuty

2. **Level 2:** Platform team lead
   - Response time: 30 minutes
   - Contact: Slack #fitagent-production

3. **Level 3:** Engineering manager
   - Response time: 1 hour
   - Contact: Phone

4. **Level 4:** CTO
   - For critical business impact
   - Contact: Phone

**External Contacts:**

- **AWS Support:** Enterprise support plan
- **Twilio Support:** Priority support
- **Security Team:** security@fitagent.com


---

## Post-Deployment Validation

### Validation Checklist

After deployment, verify all systems are operational:

**Infrastructure:**
- [ ] CloudFormation stack status: CREATE_COMPLETE or UPDATE_COMPLETE
- [ ] All Lambda functions active
- [ ] DynamoDB table active with correct capacity
- [ ] S3 buckets created and accessible
- [ ] SQS queues created
- [ ] EventBridge rules enabled
- [ ] API Gateway endpoint responding

**Functionality:**
- [ ] Send test WhatsApp message
- [ ] Verify message processed successfully
- [ ] Check DynamoDB for test data
- [ ] Verify Twilio webhook working
- [ ] Test calendar integration (if enabled)
- [ ] Test payment registration
- [ ] Test session scheduling

**Monitoring:**
- [ ] CloudWatch dashboard accessible
- [ ] All alarms configured
- [ ] SNS notifications working
- [ ] Logs flowing to CloudWatch
- [ ] X-Ray traces visible

**Security:**
- [ ] Secrets Manager credentials accessible
- [ ] KMS encryption working
- [ ] IAM roles have correct permissions
- [ ] CloudTrail logging enabled
- [ ] No public access to resources

**Performance:**
- [ ] Response times within SLA
- [ ] No throttling errors
- [ ] Auto-scaling configured
- [ ] Capacity utilization healthy

### Smoke Test Script

```bash
# Run comprehensive smoke tests
cat > scripts/production_smoke_test.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Production Smoke Tests ==="
echo ""

STACK_NAME="fitagent-production"
REGION="us-east-1"
PROFILE="production"

# Test 1: Stack exists
echo "[1/10] Checking CloudFormation stack..."
STACK_STATUS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].StackStatus' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" = "UPDATE_COMPLETE" ]; then
    echo "✓ Stack healthy: $STACK_STATUS"
else
    echo "✗ Stack unhealthy: $STACK_STATUS"
    exit 1
fi

# Test 2: Lambda functions
echo ""
echo "[2/10] Checking Lambda functions..."
FUNCTIONS=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?contains(OutputKey, `FunctionName`)].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

for FUNCTION in $FUNCTIONS; do
    STATE=$(aws lambda get-function \
        --function-name $FUNCTION \
        --query 'Configuration.State' \
        --output text \
        --region $REGION \
        --profile $PROFILE)
    
    if [ "$STATE" = "Active" ]; then
        echo "✓ $FUNCTION: Active"
    else
        echo "✗ $FUNCTION: $STATE"
        exit 1
    fi
done

# Test 3: DynamoDB table
echo ""
echo "[3/10] Checking DynamoDB table..."
TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`TableName`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

TABLE_STATUS=$(aws dynamodb describe-table \
    --table-name $TABLE_NAME \
    --query 'Table.TableStatus' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$TABLE_STATUS" = "ACTIVE" ]; then
    echo "✓ DynamoDB table: Active"
else
    echo "✗ DynamoDB table: $TABLE_STATUS"
    exit 1
fi

# Test 4: API Gateway
echo ""
echo "[4/10] Checking API Gateway..."
API_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "405" ]; then
    echo "✓ API Gateway responding: $HTTP_CODE"
else
    echo "✗ API Gateway not responding: $HTTP_CODE"
    exit 1
fi

# Test 5: CloudWatch alarms
echo ""
echo "[5/10] Checking CloudWatch alarms..."
ALARM_COUNT=$(aws cloudwatch describe-alarms \
    --alarm-name-prefix fitagent-production \
    --query 'length(MetricAlarms)' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$ALARM_COUNT" -ge 5 ]; then
    echo "✓ CloudWatch alarms configured: $ALARM_COUNT"
else
    echo "⚠ Only $ALARM_COUNT alarms configured (expected >= 5)"
fi

# Test 6: Backup configuration
echo ""
echo "[6/10] Checking backup configuration..."
PITR_STATUS=$(aws dynamodb describe-continuous-backups \
    --table-name $TABLE_NAME \
    --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$PITR_STATUS" = "ENABLED" ]; then
    echo "✓ Point-in-time recovery: Enabled"
else
    echo "⚠ Point-in-time recovery: $PITR_STATUS"
fi

# Test 7: Secrets Manager
echo ""
echo "[7/10] Checking Secrets Manager..."
SECRET_COUNT=$(aws secretsmanager list-secrets \
    --filters Key=name,Values=fitagent/production \
    --query 'length(SecretList)' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$SECRET_COUNT" -ge 1 ]; then
    echo "✓ Secrets configured: $SECRET_COUNT"
else
    echo "⚠ No secrets found"
fi

# Test 8: CloudWatch Logs
echo ""
echo "[8/10] Checking CloudWatch Logs..."
LOG_GROUPS=$(aws logs describe-log-groups \
    --log-group-name-prefix /aws/lambda/fitagent \
    --query 'length(logGroups)' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ "$LOG_GROUPS" -ge 1 ]; then
    echo "✓ Log groups created: $LOG_GROUPS"
else
    echo "✗ No log groups found"
    exit 1
fi

# Test 9: SNS topics
echo ""
echo "[9/10] Checking SNS topics..."
SNS_TOPICS=$(aws sns list-topics \
    --query 'Topics[?contains(TopicArn, `production`)].TopicArn' \
    --output text \
    --region $REGION \
    --profile $PROFILE)

if [ ! -z "$SNS_TOPICS" ]; then
    echo "✓ SNS topics configured"
else
    echo "⚠ No SNS topics found"
fi

# Test 10: Cost budget
echo ""
echo "[10/10] Checking cost budget..."
BUDGET_EXISTS=$(aws budgets describe-budgets \
    --account-id $(aws sts get-caller-identity --query Account --output text --profile $PROFILE) \
    --query 'Budgets[?contains(BudgetName, `Production`)].BudgetName' \
    --output text \
    --region us-east-1 \
    --profile $PROFILE 2>/dev/null || echo "")

if [ ! -z "$BUDGET_EXISTS" ]; then
    echo "✓ Cost budget configured"
else
    echo "⚠ No cost budget found"
fi

echo ""
echo "=== Smoke Tests Complete ==="
echo ""
echo "✓ All critical tests passed"
echo "⚠ Some optional configurations missing (review warnings)"
EOF

chmod +x scripts/production_smoke_test.sh
./scripts/production_smoke_test.sh
```


---

## Appendix

### A. Production Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| ENVIRONMENT | Environment name | production | Yes |
| AWS_REGION | AWS region | us-east-1 | Yes |
| DYNAMODB_TABLE | DynamoDB table name | fitagent-main-production | Yes |
| S3_BUCKET | S3 bucket for receipts | fitagent-receipts-production | Yes |
| SQS_QUEUE_URL | Main SQS queue URL | https://sqs... | Yes |
| NOTIFICATION_QUEUE_URL | Notification queue URL | https://sqs... | Yes |
| DLQ_URL | Dead letter queue URL | https://sqs... | Yes |
| TWILIO_ACCOUNT_SID | Twilio account SID | AC... | Yes |
| TWILIO_AUTH_TOKEN | Twilio auth token | (secret) | Yes |
| TWILIO_WHATSAPP_NUMBER | Twilio WhatsApp number | whatsapp:+1... | Yes |
| ENABLE_MULTI_AGENT | Multi-agent feature flag | false | No |
| ENABLE_SESSION_CONFIRMATION | Session confirmation flag | false | No |
| BEDROCK_MODEL_ID | AWS Bedrock model | anthropic.claude-3-sonnet... | Yes |
| BEDROCK_REGION | Bedrock region | us-east-1 | Yes |
| LOG_LEVEL | Logging level | INFO | No |
| ENABLE_XRAY_TRACING | X-Ray tracing | true | No |

### B. CloudFormation Stack Outputs

| Output Key | Description | Usage |
|------------|-------------|-------|
| TableName | DynamoDB table name | Reference in Lambda |
| TableArn | DynamoDB table ARN | IAM policies |
| MessageProcessorFunctionName | Message processor Lambda | Monitoring, updates |
| MessageProcessorFunctionArn | Lambda ARN | EventBridge rules |
| SessionConfirmationFunctionName | Session confirmation Lambda | Monitoring |
| WebhookUrl | API Gateway webhook URL | Twilio configuration |
| S3BucketName | S3 bucket name | Receipt storage |
| SQSQueueUrl | Main queue URL | Message sending |

### C. Useful AWS CLI Commands

```bash
# Get stack outputs
aws cloudformation describe-stacks \
    --stack-name fitagent-production \
    --query 'Stacks[0].Outputs' \
    --output table

# List all Lambda functions
aws lambda list-functions \
    --query 'Functions[?starts_with(FunctionName, `fitagent-production`)].FunctionName'

# Get Lambda logs (last 10 minutes)
aws logs tail /aws/lambda/fitagent-message-processor-production \
    --since 10m \
    --follow

# Query DynamoDB table
aws dynamodb scan \
    --table-name fitagent-main-production \
    --select COUNT

# Get current costs
aws ce get-cost-and-usage \
    --time-period Start=$(date -d '1 day ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
    --granularity DAILY \
    --metrics BlendedCost

# Export DynamoDB table
aws dynamodb export-table-to-point-in-time \
    --table-arn arn:aws:dynamodb:us-east-1:ACCOUNT:table/fitagent-main-production \
    --s3-bucket fitagent-backups-production \
    --export-format DYNAMODB_JSON

# Update Lambda environment variable
aws lambda update-function-configuration \
    --function-name fitagent-message-processor-production \
    --environment "Variables={KEY=VALUE}"
```

### D. References and Documentation

**AWS Documentation:**
- [Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudFormation User Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/)
- [Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

**Third-Party Documentation:**
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Strands Agents SDK](https://github.com/aws-samples/strands-agents)

**Internal Documentation:**
- [Staging Deployment Guide](STAGING_DEPLOYMENT.md)
- [Architecture Documentation](../README.md)
- [Testing Guide](../RECOMMENDED_TESTING_APPROACH.md)

### E. Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-01-15 | DevOps Team | Initial production deployment guide |

---

## Summary

This production deployment guide provides comprehensive instructions for the initial deployment of FitAgent to AWS production environment. Key highlights:

✅ **Pre-deployment checklist** ensures all requirements are met
✅ **Step-by-step deployment** with automated scripts
✅ **Monitoring and alerting** configured from day one
✅ **Security and compliance** best practices implemented
✅ **Disaster recovery** procedures documented
✅ **Cost management** with budget alerts
✅ **Gradual rollout** strategy for safe feature enablement
✅ **Troubleshooting guide** for common issues
✅ **Rollback procedures** for emergency situations

**Next Steps After Deployment:**

1. Monitor production infrastructure for 7 days
2. Onboard pilot trainers (5-10 users)
3. Gather feedback and optimize
4. Gradually enable advanced features (multi-agent, session confirmation)
5. Scale user base based on system stability
6. Conduct weekly performance reviews
7. Optimize costs based on actual usage
8. Schedule quarterly disaster recovery drills

**Support:**
- On-call: PagerDuty
- Slack: #fitagent-production
- Email: devops@fitagent.com

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Maintained By**: Platform Team  
**Review Cycle**: Quarterly

