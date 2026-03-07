# Staging Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying FitAgent to the staging environment. The staging deployment includes the multi-agent architecture with Strands SDK and the session confirmation feature.

**Target Environment:** AWS Staging  
**Stack Name:** `fitagent-staging`  
**Region:** `us-east-1` (configurable)  
**Estimated Deployment Time:** 15-20 minutes

---

## Prerequisites

### Required Tools

1. **AWS CLI** (v2.x or later)
   ```bash
   aws --version
   # Should output: aws-cli/2.x.x or later
   ```

2. **Python 3.12**
   ```bash
   python3 --version
   # Should output: Python 3.12.x
   ```

3. **pip** (Python package manager)
   ```bash
   pip --version
   ```

4. **Git** (for version control)
   ```bash
   git --version
   ```

### AWS Credentials

Ensure you have AWS credentials configured with appropriate permissions:

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

**Required IAM Permissions:**
- CloudFormation: Full access
- DynamoDB: Full access
- Lambda: Full access
- IAM: Create/update roles and policies
- S3: Create/manage buckets
- EventBridge: Create/manage rules
- CloudWatch Logs: Create/manage log groups
- Secrets Manager: Read/write secrets (for OAuth tokens)

### Environment Variables

Set the following environment variables before deployment:

```bash
export AWS_REGION=us-east-1
export DEPLOYMENT_BUCKET=fitagent-deployments-staging
export STACK_NAME=fitagent-staging
```

### Twilio Configuration

You'll need Twilio credentials for WhatsApp messaging:

1. **Twilio Account SID** - From Twilio Console
2. **Twilio Auth Token** - From Twilio Console  
3. **Twilio WhatsApp Number** - Format: `whatsapp:+14155238886`

**Update parameters file** with your Twilio credentials:
```bash
vim infrastructure/parameters/staging.json
# Replace REPLACE_WITH_STAGING_TWILIO_SID and REPLACE_WITH_STAGING_TWILIO_TOKEN
```

---

## Deployment Steps

### Step 1: Prepare the Codebase

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd fitagent
   ```

2. **Checkout the deployment branch**:
   ```bash
   git checkout main
   git pull origin main
   ```

3. **Verify all required files exist**:
   ```bash
   ls -la infrastructure/template.yml
   ls -la infrastructure/parameters/staging.json
   ls -la scripts/package_lambda.sh
   ls -la scripts/deploy_staging.sh
   ```

### Step 2: Install Dependencies

Install Python dependencies locally to verify no conflicts:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Verify Strands SDK installation**:
```bash
pip show strands-agents
# Should display package information
```

### Step 3: Update Configuration

1. **Review staging parameters**:
   ```bash
   cat infrastructure/parameters/staging.json
   ```

2. **Update Twilio credentials** (if not done in prerequisites):
   ```bash
   vim infrastructure/parameters/staging.json
   ```
   
   Replace placeholder values:
   - `REPLACE_WITH_STAGING_TWILIO_SID` → Your Twilio Account SID
   - `REPLACE_WITH_STAGING_TWILIO_TOKEN` → Your Twilio Auth Token

3. **Verify capacity settings**:
   - `TableReadCapacity: 10` - Adjust based on expected load
   - `TableWriteCapacity: 10` - Adjust based on expected load

### Step 4: Package Lambda Functions

Run the packaging script to create the deployment package:

```bash
chmod +x scripts/package_lambda.sh
./scripts/package_lambda.sh
```

**Expected output**:
```
=== FitAgent Lambda Packaging ===

[1/5] Cleaning previous builds...
✓ Build directory cleaned

[2/5] Installing dependencies...
✓ Dependencies installed

[3/5] Copying source code...
✓ Source code copied

[4/5] Verifying Strands SDK...
✓ Strands SDK found in package

[5/5] Creating deployment package...
✓ Deployment package created: build/lambda.zip (XX.XMB)

=== Packaging Complete ===
Package location: build/lambda.zip
Package size: XX.XMB
```

**Troubleshooting**:
- If package exceeds 50MB, consider using Lambda Layers for large dependencies
- If Strands SDK is missing, verify `requirements.txt` includes `strands-agents>=0.1.0`

### Step 5: Validate CloudFormation Template

Before deployment, validate the CloudFormation template:

```bash
aws cloudformation validate-template \
    --template-body file://infrastructure/template.yml \
    --region us-east-1
```

**Expected output**: JSON response with template parameters and capabilities.

### Step 6: Deploy to Staging

Run the deployment script:

```bash
chmod +x scripts/deploy_staging.sh
./scripts/deploy_staging.sh
```

**Deployment process** (15-20 minutes):

1. **Prerequisites validation** - Checks AWS CLI, credentials, files
2. **Template validation** - Validates CloudFormation syntax
3. **S3 bucket creation** - Creates deployment bucket if needed
4. **Lambda package upload** - Uploads to S3 with versioning
5. **Parameter preparation** - Converts JSON to CloudFormation format
6. **Stack deployment** - Creates or updates CloudFormation stack
7. **Lambda code update** - Updates function code from S3
8. **Output display** - Shows stack outputs and next steps

**Expected output**:
```
=== FitAgent Staging Deployment ===

Stack Name: fitagent-staging
Region: us-east-1
Template: infrastructure/template.yml
Parameters: infrastructure/parameters/staging.json

[1/8] Validating prerequisites...
✓ AWS CLI found
✓ AWS credentials valid (Account: 123456789012)
✓ Template file found
✓ Parameters file found
✓ Lambda package found

[2/8] Validating CloudFormation template...
✓ Template validation passed

[3/8] Checking deployment bucket...
✓ Deployment bucket exists

[4/8] Uploading Lambda package to S3...
✓ Lambda package uploaded: s3://fitagent-deployments-staging/lambda-packages/lambda-20240115-143022.zip

[5/8] Preparing deployment parameters...
✓ Parameters prepared

[6/8] Checking stack status...
✓ Will perform stack creation

[7/8] Deploying CloudFormation stack...
  Operation: create
  This may take 5-10 minutes...
  
  Waiting for stack creation to complete...
✓ Stack deployment complete

[8/8] Updating Lambda function code...
  Updating fitagent-message-processor-staging...
  Updating fitagent-session-confirmation-staging...
✓ Lambda functions updated

=== Deployment Complete ===

Stack Outputs:
[Table showing all CloudFormation outputs]

Next Steps:
  1. Enable feature flag for test trainers
  2. Run smoke tests: pytest tests/smoke/test_staging_deployment.py
  3. Monitor CloudWatch logs and metrics
  4. Verify WhatsApp message processing
```

### Step 7: Run Smoke Tests

Verify the deployment with automated smoke tests:

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run smoke tests
pytest tests/smoke/test_staging_deployment.py -v

# Run with detailed output
pytest tests/smoke/test_staging_deployment.py -v -s
```

**Expected output**:
```
tests/smoke/test_staging_deployment.py::TestStackDeployment::test_stack_exists PASSED
tests/smoke/test_staging_deployment.py::TestStackDeployment::test_stack_has_required_outputs PASSED
tests/smoke/test_staging_deployment.py::TestDynamoDBTable::test_table_exists PASSED
tests/smoke/test_staging_deployment.py::TestDynamoDBTable::test_table_has_required_gsis PASSED
...

============================================================
✓ All smoke tests passed!
============================================================

Staging environment is ready for testing.
```

### Step 8: Enable Multi-Agent Feature Flag

The multi-agent architecture is disabled by default. Enable it for test trainers:

**Option A: Enable globally** (all trainers):
```bash
aws lambda update-function-configuration \
    --function-name fitagent-message-processor-staging \
    --environment "Variables={ENABLE_MULTI_AGENT=true,...}" \
    --region us-east-1
```

**Option B: Enable per-trainer** (recommended for gradual rollout):

1. Create a test trainer in DynamoDB:
   ```python
   # Use AWS Console or boto3
   import boto3
   
   dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
   table = dynamodb.Table('fitagent-main-staging')
   
   table.put_item(Item={
       'PK': 'TRAINER#test-trainer-001',
       'SK': 'FEATURE_FLAGS',
       'enable_multi_agent': True,
       'enable_session_confirmation': True,
   })
   ```

2. Verify feature flag:
   ```bash
   aws dynamodb get-item \
       --table-name fitagent-main-staging \
       --key '{"PK":{"S":"TRAINER#test-trainer-001"},"SK":{"S":"FEATURE_FLAGS"}}' \
       --region us-east-1
   ```

### Step 9: Verify Deployment

1. **Check Lambda function logs**:
   ```bash
   aws logs tail /aws/lambda/fitagent-message-processor-staging --follow
   ```

2. **Verify DynamoDB table**:
   ```bash
   aws dynamodb describe-table \
       --table-name fitagent-main-staging \
       --region us-east-1
   ```

3. **Check EventBridge rule**:
   ```bash
   aws events describe-rule \
       --name session-confirmation-trigger-staging \
       --region us-east-1
   ```

4. **Test WhatsApp integration** (manual):
   - Send a test message to your Twilio WhatsApp number
   - Verify message is processed in CloudWatch logs
   - Check for any errors or warnings

---

## Post-Deployment Configuration

### Configure OAuth for Calendar Integration

1. **Google Calendar OAuth**:
   - Create OAuth credentials in Google Cloud Console
   - Add redirect URI: `https://your-api-gateway-url/oauth/callback`
   - Store credentials in AWS Secrets Manager:
     ```bash
     aws secretsmanager create-secret \
         --name fitagent/staging/google-oauth \
         --secret-string '{"client_id":"...","client_secret":"..."}' \
         --region us-east-1
     ```

2. **Microsoft Outlook OAuth**:
   - Register app in Azure AD
   - Add redirect URI
   - Store credentials in AWS Secrets Manager:
     ```bash
     aws secretsmanager create-secret \
         --name fitagent/staging/outlook-oauth \
         --secret-string '{"client_id":"...","client_secret":"..."}' \
         --region us-east-1
     ```

### Configure Monitoring and Alerts

1. **CloudWatch Alarms**:
   ```bash
   # Lambda error rate alarm
   aws cloudwatch put-metric-alarm \
       --alarm-name fitagent-staging-lambda-errors \
       --alarm-description "Alert on Lambda errors" \
       --metric-name Errors \
       --namespace AWS/Lambda \
       --statistic Sum \
       --period 300 \
       --threshold 5 \
       --comparison-operator GreaterThanThreshold \
       --evaluation-periods 1
   ```

2. **DynamoDB throttling alarm**:
   ```bash
   aws cloudwatch put-metric-alarm \
       --alarm-name fitagent-staging-dynamodb-throttles \
       --metric-name UserErrors \
       --namespace AWS/DynamoDB \
       --statistic Sum \
       --period 300 \
       --threshold 10 \
       --comparison-operator GreaterThanThreshold
   ```

### Set Up Log Insights Queries

Create CloudWatch Insights queries for monitoring:

1. **Agent handoff tracking**:
   ```
   fields @timestamp, handoff_from, handoff_to, handoff_reason
   | filter @message like /handoff/
   | sort @timestamp desc
   ```

2. **Error tracking**:
   ```
   fields @timestamp, @message, error, trainer_id
   | filter @message like /ERROR/
   | sort @timestamp desc
   ```

3. **Performance monitoring**:
   ```
   fields @timestamp, duration, handoff_count
   | stats avg(duration), max(duration), count() by bin(5m)
   ```

---

## Testing Checklist

### Functional Testing

- [ ] **Student Management**
  - [ ] Register new student
  - [ ] View student list
  - [ ] Update student information

- [ ] **Session Scheduling**
  - [ ] Schedule new session
  - [ ] Reschedule existing session
  - [ ] Cancel session
  - [ ] View calendar
  - [ ] Conflict detection works

- [ ] **Session Confirmation**
  - [ ] Confirmation message sent 1 hour after session
  - [ ] YES response marks session as completed
  - [ ] NO response marks session as missed
  - [ ] Cancelled sessions don't send confirmations

- [ ] **Payment Tracking**
  - [ ] Register payment
  - [ ] Confirm payment
  - [ ] View payment history
  - [ ] Upload receipt image

- [ ] **Calendar Integration**
  - [ ] Connect Google Calendar
  - [ ] Connect Outlook Calendar
  - [ ] Sync session to calendar
  - [ ] Handle OAuth token refresh

- [ ] **Notifications**
  - [ ] Send broadcast message
  - [ ] Message template substitution
  - [ ] Rate limiting works

### Multi-Agent Testing

- [ ] **Coordinator Agent**
  - [ ] Routes student queries to Student_Agent
  - [ ] Routes session queries to Session_Agent
  - [ ] Routes payment queries to Payment_Agent
  - [ ] Handles greetings without handoff

- [ ] **Agent Handoffs**
  - [ ] Student → Session handoff works
  - [ ] Session → Calendar handoff works
  - [ ] Session → Payment handoff works
  - [ ] Max handoffs limit enforced

- [ ] **Context Propagation**
  - [ ] Entities extracted by Coordinator
  - [ ] Shared_Context passed between agents
  - [ ] Invocation_State isolated per trainer

### Performance Testing

- [ ] **Response Time**
  - [ ] Messages processed within 10 seconds
  - [ ] Agent handoffs complete within 30 seconds
  - [ ] Total execution under 120 seconds

- [ ] **Scalability**
  - [ ] DynamoDB handles concurrent requests
  - [ ] Lambda functions scale appropriately
  - [ ] No throttling errors under load

### Security Testing

- [ ] **Multi-Tenancy**
  - [ ] Trainers can only access their own data
  - [ ] Cross-tenant queries blocked
  - [ ] Invocation_State not visible in logs

- [ ] **Data Protection**
  - [ ] OAuth tokens encrypted with KMS
  - [ ] PII sanitized in logs
  - [ ] Phone numbers masked in CloudWatch

---

## Monitoring and Observability

### Key Metrics to Monitor

1. **Lambda Metrics**:
   - Invocation count
   - Error rate
   - Duration (p50, p95, p99)
   - Concurrent executions
   - Throttles

2. **DynamoDB Metrics**:
   - Read/write capacity utilization
   - Throttled requests
   - System errors
   - GSI performance

3. **Business Metrics**:
   - Messages processed per hour
   - Agent handoff count
   - Session confirmations sent
   - Calendar sync success rate

### CloudWatch Dashboards

Create a staging dashboard with:

```bash
aws cloudwatch put-dashboard \
    --dashboard-name fitagent-staging \
    --dashboard-body file://infrastructure/cloudwatch-dashboard.json
```

**Dashboard widgets**:
- Lambda invocation count (line chart)
- Lambda error rate (line chart)
- DynamoDB read/write capacity (line chart)
- Agent handoff distribution (pie chart)
- Response time distribution (histogram)

### Log Aggregation

All logs are centralized in CloudWatch Logs:

- `/aws/lambda/fitagent-message-processor-staging`
- `/aws/lambda/fitagent-session-confirmation-staging`

**Retention**: Set to 7 days for staging (cost optimization)

```bash
aws logs put-retention-policy \
    --log-group-name /aws/lambda/fitagent-message-processor-staging \
    --retention-in-days 7
```

---

## Rollback Procedures

### Emergency Rollback

If critical issues are detected, immediately disable multi-agent:

```bash
# Disable multi-agent feature flag
aws lambda update-function-configuration \
    --function-name fitagent-message-processor-staging \
    --environment "Variables={ENABLE_MULTI_AGENT=false,...}" \
    --region us-east-1
```

System will automatically fall back to single-agent architecture.

### Full Stack Rollback

To completely roll back the deployment:

```bash
# Delete the CloudFormation stack
aws cloudformation delete-stack \
    --stack-name fitagent-staging \
    --region us-east-1

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
    --stack-name fitagent-staging \
    --region us-east-1
```

**Warning**: This will delete all resources including DynamoDB table data.

### Partial Rollback (Lambda Only)

To roll back only Lambda functions to a previous version:

```bash
# List function versions
aws lambda list-versions-by-function \
    --function-name fitagent-message-processor-staging

# Update alias to point to previous version
aws lambda update-alias \
    --function-name fitagent-message-processor-staging \
    --name staging \
    --function-version <previous-version>
```

---

## Troubleshooting

### Common Issues

#### 1. Package Size Exceeds Lambda Limit

**Symptom**: Deployment fails with "Unzipped size must be smaller than 262144000 bytes"

**Solution**:
- Use Lambda Layers for large dependencies (boto3, Strands SDK)
- Remove unnecessary files from package
- Consider using Docker-based Lambda deployment

#### 2. DynamoDB Throttling

**Symptom**: `ProvisionedThroughputExceededException` in logs

**Solution**:
- Increase read/write capacity in `staging.json`
- Enable auto-scaling for DynamoDB table
- Add exponential backoff in application code

#### 3. Lambda Timeout

**Symptom**: Function times out after 180 seconds

**Solution**:
- Check for infinite loops in agent handoffs
- Verify max_handoffs configuration (should be 5-7)
- Review slow DynamoDB queries
- Check external API latency (Twilio, Calendar APIs)

#### 4. OAuth Token Expired

**Symptom**: Calendar sync fails with 401 Unauthorized

**Solution**:
- Implement token refresh logic
- Verify token expiration handling
- Check Secrets Manager for valid tokens

#### 5. EventBridge Rule Not Triggering

**Symptom**: Session confirmations not sent

**Solution**:
- Verify rule is ENABLED
- Check Lambda permission for EventBridge invocation
- Review CloudWatch Events logs
- Test Lambda function manually

### Debug Commands

```bash
# View Lambda function configuration
aws lambda get-function-configuration \
    --function-name fitagent-message-processor-staging

# Tail Lambda logs in real-time
aws logs tail /aws/lambda/fitagent-message-processor-staging --follow

# Invoke Lambda function manually
aws lambda invoke \
    --function-name fitagent-message-processor-staging \
    --payload '{"message":"test","phone_number":"+14155551234"}' \
    response.json

# Check DynamoDB table status
aws dynamodb describe-table \
    --table-name fitagent-main-staging

# List EventBridge rules
aws events list-rules --name-prefix session-confirmation
```

---

## Cost Estimation

### Staging Environment Monthly Costs

**Assumptions**:
- 1,000 messages/day
- 100 trainers
- 500 sessions/month
- 7-day log retention

**Estimated costs**:

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| Lambda (Message Processor) | 30K invocations, 1GB RAM, 5s avg | $5 |
| Lambda (Session Confirmation) | 8,640 invocations, 512MB RAM, 2s avg | $1 |
| DynamoDB | 10 RCU, 10 WCU, 1GB storage | $7 |
| S3 | 1GB storage, 1K requests | $0.50 |
| CloudWatch Logs | 5GB ingestion, 7-day retention | $3 |
| EventBridge | 8,640 events/month | $0.01 |
| **Total** | | **~$16.50/month** |

**Cost optimization tips**:
- Use on-demand pricing for DynamoDB if traffic is unpredictable
- Reduce log retention to 3 days
- Use S3 Intelligent-Tiering for receipt storage
- Enable Lambda reserved concurrency to avoid over-provisioning

---

## Security Considerations

### Data Protection

1. **Encryption at Rest**:
   - DynamoDB: KMS encryption enabled
   - S3: Server-side encryption (SSE-S3)
   - Secrets Manager: KMS encryption

2. **Encryption in Transit**:
   - All API calls use HTTPS
   - Twilio webhook uses TLS 1.2+
   - OAuth flows use secure redirects

3. **Access Control**:
   - IAM roles follow least privilege principle
   - Lambda functions have minimal permissions
   - DynamoDB access scoped to specific tables

### Compliance

- **GDPR**: PII sanitized in logs, data retention policies
- **HIPAA**: Not applicable (fitness training data)
- **SOC 2**: CloudTrail enabled for audit logs

### Secrets Management

All sensitive credentials stored in:
- AWS Secrets Manager (OAuth tokens)
- Lambda environment variables (encrypted at rest)
- Parameter Store (non-sensitive config)

**Never commit secrets to Git!**

---

## Next Steps

After successful staging deployment:

1. **Gradual Rollout**:
   - Enable multi-agent for 10% of trainers
   - Monitor for 1 week
   - Increase to 50% if stable
   - Full rollout after 2 weeks

2. **Production Deployment**:
   - Create `infrastructure/parameters/production.json`
   - Update capacity settings for production load
   - Follow same deployment process
   - Enable auto-scaling for DynamoDB

3. **Continuous Monitoring**:
   - Set up PagerDuty/Opsgenie alerts
   - Create runbooks for common issues
   - Schedule weekly review of metrics

4. **Documentation**:
   - Update API documentation
   - Create user guides for trainers
   - Document known issues and workarounds

---

## Support and Escalation

### Contact Information

- **DevOps Team**: devops@fitagent.com
- **On-Call Engineer**: +1-555-ON-CALL
- **Slack Channel**: #fitagent-staging

### Escalation Path

1. **Level 1**: Check this runbook and troubleshooting section
2. **Level 2**: Contact DevOps team via Slack
3. **Level 3**: Page on-call engineer for critical issues
4. **Level 4**: Escalate to engineering manager

### SLA

- **Response Time**: 1 hour for critical issues
- **Resolution Time**: 4 hours for critical issues
- **Uptime Target**: 99.5% for staging

---

## Appendix

### A. CloudFormation Stack Outputs

| Output Key | Description |
|------------|-------------|
| TableName | DynamoDB table name |
| TableArn | DynamoDB table ARN |
| MessageProcessorFunctionName | Message processor Lambda name |
| SessionConfirmationFunctionName | Session confirmation Lambda name |
| SessionConfirmationRuleName | EventBridge rule name |

### B. Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| ENVIRONMENT | Environment name | staging |
| DYNAMODB_TABLE | DynamoDB table name | fitagent-main-staging |
| ENABLE_MULTI_AGENT | Multi-agent feature flag | true/false |
| BEDROCK_MODEL_ID | Default Bedrock model | amazon.nova-micro-v1:0 |
| TWILIO_ACCOUNT_SID | Twilio account SID | ACxxxxx |
| TWILIO_AUTH_TOKEN | Twilio auth token | (secret) |

### C. Useful AWS CLI Commands

```bash
# Get stack status
aws cloudformation describe-stacks --stack-name fitagent-staging

# List all Lambda functions
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `fitagent-staging`)].FunctionName'

# Get DynamoDB table metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/DynamoDB \
    --metric-name ConsumedReadCapacityUnits \
    --dimensions Name=TableName,Value=fitagent-main-staging \
    --start-time 2024-01-01T00:00:00Z \
    --end-time 2024-01-02T00:00:00Z \
    --period 3600 \
    --statistics Sum

# Export DynamoDB table (backup)
aws dynamodb export-table-to-point-in-time \
    --table-arn arn:aws:dynamodb:us-east-1:123456789012:table/fitagent-main-staging \
    --s3-bucket fitagent-backups-staging \
    --export-format DYNAMODB_JSON
```

### D. References

- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudFormation User Guide](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/)
- [Strands Agents SDK Documentation](https://github.com/aws-samples/strands-agents)
- [Twilio WhatsApp API](https://www.twilio.com/docs/whatsapp)

---

**Document Version**: 1.0  
**Last Updated**: 2024-01-15  
**Maintained By**: DevOps Team
