# Staging Deployment Guide

Guide for deploying FitAgent to the staging environment for testing before production.

## Prerequisites

- AWS CLI configured with appropriate credentials
- GitHub repository access
- Staging environment parameters configured
- Twilio sandbox account for testing

## Staging Environment

### Purpose
- Test new features before production
- Validate infrastructure changes
- Integration testing with real AWS services
- Performance testing under load

### Configuration
- **Environment**: `staging`
- **AWS Account**: Separate from production (recommended)
- **Domain**: `api-staging.fitagent.com`
- **Twilio**: Sandbox number for testing
- **Data**: Test data only, no real user data

## Deployment Methods

### 1. Automated Deployment (GitHub Actions)

**Trigger**: Push to `dev` branch

```yaml
# .github/workflows/deploy-staging.yml
name: Deploy to Staging
on:
  push:
    branches: [dev]
```

**Process**:
1. Push changes to `dev` branch
2. GitHub Actions runs tests
3. If tests pass, deploys to staging
4. Runs smoke tests
5. Notifies team of deployment status

**Monitor Deployment**:
```bash
# View workflow runs
gh run list --workflow=deploy-staging.yml

# View specific run
gh run view <run-id>
```

### 2. Manual Deployment

**Step 1: Validate CloudFormation Template**
```bash
aws cloudformation validate-template \
  --template-body file://infrastructure/template.yml
```

**Step 2: Package Lambda Functions**
```bash
# Create deployment package
zip -r lambda.zip src/ -x "*.pyc" -x "__pycache__/*" -x "tests/*"

# Upload to S3
aws s3 cp lambda.zip s3://fitagent-deployments-staging/lambda-$(date +%Y%m%d-%H%M%S).zip
```

**Step 3: Deploy Stack**
```bash
aws cloudformation deploy \
  --template-file infrastructure/template.yml \
  --stack-name fitagent-staging \
  --parameter-overrides file://infrastructure/parameters/staging.example.json \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

**Step 4: Update Secrets**
```bash
# Update Twilio credentials
aws secretsmanager update-secret \
  --secret-id fitagent/staging/twilio-auth-token \
  --secret-string "your-staging-auth-token"

# Update OAuth credentials
aws secretsmanager update-secret \
  --secret-id fitagent/staging/google-client-secret \
  --secret-string "your-staging-client-secret"
```

**Step 5: Verify Deployment**
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name fitagent-staging \
  --query 'Stacks[0].StackStatus'

# Test API endpoint
curl https://api-staging.fitagent.com/health
```

## Configuration

### Environment Variables

Create `infrastructure/parameters/staging.json` (not committed to git):
```json
{
  "Parameters": {
    "Environment": "staging",
    "DynamoDBTable": "fitagent-staging",
    "S3Bucket": "fitagent-receipts-staging",
    "TwilioAccountSid": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "TwilioAuthTokenSecretArn": "arn:aws:secretsmanager:...",
    "BedrockModelId": "anthropic.claude-3-haiku-20240307-v1:0"
  }
}
```

### Secrets Management

**Create Secrets**:
```bash
# Twilio
aws secretsmanager create-secret \
  --name fitagent/staging/twilio-auth-token \
  --secret-string "your-auth-token"

# Google OAuth
aws secretsmanager create-secret \
  --name fitagent/staging/google-client-id \
  --secret-string "your-client-id"

aws secretsmanager create-secret \
  --name fitagent/staging/google-client-secret \
  --secret-string "your-client-secret"

# Microsoft OAuth
aws secretsmanager create-secret \
  --name fitagent/staging/outlook-client-id \
  --secret-string "your-client-id"

aws secretsmanager create-secret \
  --name fitagent/staging/outlook-client-secret \
  --secret-string "your-client-secret"
```

## Testing in Staging

### 1. Smoke Tests

**Health Check**:
```bash
curl https://api-staging.fitagent.com/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:00:00Z",
  "version": "1.0.0",
  "services": {
    "dynamodb": "healthy",
    "s3": "healthy",
    "sqs": "healthy",
    "bedrock": "healthy"
  }
}
```

### 2. Integration Tests

**Run Test Suite**:
```bash
# Set staging endpoint
export API_ENDPOINT=https://api-staging.fitagent.com

# Run integration tests
pytest tests/integration/ -v --env=staging
```

### 3. Manual Testing with Twilio Sandbox

**Setup**:
1. Configure Twilio webhook to staging endpoint
2. Join sandbox: Send "join [sandbox-name]" to Twilio number
3. Test conversation flows

**Test Scenarios**:
- Register new student
- Schedule session
- Record payment
- Connect calendar
- Send notification

### 4. Load Testing

**Using Artillery**:
```bash
# Install artillery
npm install -g artillery

# Run load test
artillery run tests/load/staging-load-test.yml
```

**Monitor Performance**:
```bash
# CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=fitagent-staging-message-processor \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

## Monitoring

### CloudWatch Dashboards

**Create Staging Dashboard**:
```bash
aws cloudwatch put-dashboard \
  --dashboard-name fitagent-staging \
  --dashboard-body file://infrastructure/cloudwatch-dashboard-staging.json
```

**Key Metrics**:
- Lambda invocations and errors
- API Gateway requests and latency
- DynamoDB read/write capacity
- SQS queue depth and age

### Alarms

**Set Up Alarms**:
```bash
# High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name fitagent-staging-high-error-rate \
  --alarm-description "Error rate > 5%" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold

# High latency
aws cloudwatch put-metric-alarm \
  --alarm-name fitagent-staging-high-latency \
  --alarm-description "Latency > 3 seconds" \
  --metric-name Duration \
  --namespace AWS/Lambda \
  --statistic Average \
  --period 300 \
  --threshold 3000 \
  --comparison-operator GreaterThanThreshold
```

### Logs

**View Logs**:
```bash
# Tail logs
aws logs tail /aws/lambda/fitagent-staging-message-processor --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/fitagent-staging-message-processor \
  --filter-pattern "ERROR"
```

## Rollback Procedure

### 1. Identify Issue
- Check CloudWatch alarms
- Review error logs
- Verify metrics

### 2. Rollback Stack
```bash
# Get previous stack version
aws cloudformation list-stack-resources \
  --stack-name fitagent-staging

# Rollback to previous version
aws cloudformation cancel-update-stack \
  --stack-name fitagent-staging
```

### 3. Verify Rollback
```bash
# Check stack status
aws cloudformation describe-stacks \
  --stack-name fitagent-staging

# Test health endpoint
curl https://api-staging.fitagent.com/health
```

## Promotion to Production

### Pre-Production Checklist

- [ ] All staging tests pass
- [ ] No critical bugs identified
- [ ] Performance metrics acceptable
- [ ] Security scan completed
- [ ] Documentation updated
- [ ] Team approval obtained

### Promotion Process

1. **Tag Release**:
```bash
git tag -a v1.2.3 -m "Release v1.2.3"
git push origin v1.2.3
```

2. **Merge to Main**:
```bash
git checkout main
git merge dev
git push origin main
```

3. **Deploy to Production**:
See [Production Deployment Guide](PRODUCTION_DEPLOYMENT.md)

## Troubleshooting

### Common Issues

**Issue**: Stack deployment fails
```bash
# Check stack events
aws cloudformation describe-stack-events \
  --stack-name fitagent-staging \
  --max-items 10
```

**Issue**: Lambda function errors
```bash
# Check function logs
aws logs tail /aws/lambda/fitagent-staging-message-processor --since 1h
```

**Issue**: Webhook not receiving messages
- Verify Twilio webhook URL
- Check API Gateway logs
- Verify SQS queue receiving messages

### Getting Help

- Check [Troubleshooting Guide](../development/TROUBLESHOOTING.md)
- Review CloudWatch logs and metrics
- Contact DevOps team

## Cleanup

### Delete Staging Stack

**Warning**: This will delete all staging resources and data.

```bash
# Delete stack
aws cloudformation delete-stack \
  --stack-name fitagent-staging

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name fitagent-staging

# Verify deletion
aws cloudformation describe-stacks \
  --stack-name fitagent-staging
```

### Delete Secrets

```bash
# List secrets
aws secretsmanager list-secrets \
  --filters Key=name,Values=fitagent/staging

# Delete secrets
aws secretsmanager delete-secret \
  --secret-id fitagent/staging/twilio-auth-token \
  --force-delete-without-recovery
```

## Best Practices

1. **Always test in staging first** before production deployment
2. **Use separate AWS accounts** for staging and production
3. **Monitor metrics** during and after deployment
4. **Keep staging data separate** from production
5. **Document all changes** in deployment notes
6. **Run full test suite** before promoting to production
7. **Have rollback plan ready** before deployment
