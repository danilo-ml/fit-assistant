# Security Incident Response - Exposed Twilio Credentials

## ⚠️ IMMEDIATE ACTION REQUIRED

Twilio credentials were exposed in the Git repository. Follow these steps immediately:

---

## Step 1: Rotate Twilio Credentials (URGENT)

### Rotate Auth Token

1. **Go to Twilio Console:**
   ```
   https://console.twilio.com/
   ```

2. **Navigate to Account Settings:**
   - Click on your account name (top right)
   - Select "Account" → "API keys & tokens"

3. **Rotate Auth Token:**
   - Click "View" next to "Auth Token"
   - Click "Rotate Token"
   - Copy the new token immediately
   - Store it securely (see Step 2)

4. **Update All Environments:**
   - Update `.env` file locally
   - Update AWS Secrets Manager (staging/production)
   - Update CI/CD secrets

### Check for Unauthorized Usage

1. **Review Twilio Usage Logs:**
   ```
   https://console.twilio.com/us1/monitor/logs/sms
   ```

2. **Look for:**
   - Unexpected message volume
   - Messages to unknown numbers
   - Unusual timestamps (off-hours activity)
   - Geographic anomalies

3. **Check Billing:**
   ```
   https://console.twilio.com/us1/billing/manage-billing/billing-overview
   ```
   - Look for unexpected charges
   - Review usage patterns

---

## Step 2: Secure Credentials Properly

### Local Development

**Update `.env` file with new credentials:**

```bash
# Edit .env (NEVER commit this file)
nano .env
```

Add new credentials:
```env
TWILIO_ACCOUNT_SID=AC...your-new-sid...
TWILIO_AUTH_TOKEN=...your-new-token...
TWILIO_WHATSAPP_NUMBER=whatsapp:+1234567890
```

**Verify `.env` is in `.gitignore`:**

```bash
# Check if .env is ignored
git check-ignore .env

# If not, add it
echo ".env" >> .gitignore
```

### Staging Environment

**Store in AWS Secrets Manager:**

```bash
# Create or update secret
aws secretsmanager create-secret \
    --name fitagent/staging/twilio \
    --description "Twilio credentials for staging" \
    --secret-string '{
      "account_sid": "AC...new-sid...",
      "auth_token": "...new-token...",
      "whatsapp_number": "whatsapp:+1234567890"
    }' \
    --region us-east-1 \
    --profile staging

# Or update existing secret
aws secretsmanager update-secret \
    --secret-id fitagent/staging/twilio \
    --secret-string '{
      "account_sid": "AC...new-sid...",
      "auth_token": "...new-token...",
      "whatsapp_number": "whatsapp:+1234567890"
    }' \
    --region us-east-1 \
    --profile staging
```

### Production Environment

**Store in AWS Secrets Manager:**

```bash
aws secretsmanager create-secret \
    --name fitagent/production/twilio \
    --description "Twilio credentials for production" \
    --secret-string '{
      "account_sid": "AC...new-sid...",
      "auth_token": "...new-token...",
      "whatsapp_number": "whatsapp:+1234567890"
    }' \
    --region us-east-1 \
    --profile production
```

---

## Step 3: Clean Git History

The exposed credentials are in Git history and need to be removed.

### Option A: Using BFG Repo-Cleaner (Recommended)

```bash
# Install BFG
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Clone a fresh copy
git clone --mirror git@github.com:your-org/fitagent.git

# Remove the exposed credentials
bfg --replace-text passwords.txt fitagent.git

# Create passwords.txt with the exposed credentials
# Replace these with your actual exposed values
cat > passwords.txt << EOF
[YOUR_EXPOSED_TWILIO_SID]
[YOUR_EXPOSED_TWILIO_TOKEN]
EOF

# Clean up
cd fitagent.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push (WARNING: This rewrites history)
git push --force
```

### Option B: Using git-filter-repo

```bash
# Install git-filter-repo
pip install git-filter-repo

# Create a fresh clone
git clone git@github.com:your-org/fitagent.git fitagent-clean
cd fitagent-clean

# Remove sensitive data
git filter-repo --replace-text <(cat <<EOF
[EXPOSED_TWILIO_SID]==>REDACTED_TWILIO_SID
[EXPOSED_TWILIO_TOKEN]==>REDACTED_TWILIO_TOKEN
EOF
)

# Force push
git push --force --all
```

### Option C: Contact GitHub Support

If the repository is public or you need help:

1. **Report to GitHub:**
   - Go to: https://github.com/contact
   - Select "Report a security vulnerability"
   - Request removal of exposed credentials from cache

2. **Make Repository Private (if public):**
   - Go to repository Settings
   - Scroll to "Danger Zone"
   - Click "Change visibility" → "Make private"

---

## Step 4: Update CI/CD Secrets

If using GitHub Actions or other CI/CD:

### GitHub Actions

1. **Go to Repository Settings:**
   ```
   https://github.com/your-org/fitagent/settings/secrets/actions
   ```

2. **Update Secrets:**
   - `TWILIO_ACCOUNT_SID` → New SID
   - `TWILIO_AUTH_TOKEN` → New token
   - `TWILIO_WHATSAPP_NUMBER` → Your number

### Other CI/CD Platforms

Update secrets in your CI/CD platform:
- CircleCI: Project Settings → Environment Variables
- GitLab CI: Settings → CI/CD → Variables
- Jenkins: Credentials → Update credentials

---

## Step 5: Implement Security Best Practices

### Add Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: package.lock.json

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
      - id: check-merge-conflict
      - id: detect-private-key
      - id: end-of-file-fixer
      - id: trailing-whitespace
EOF

# Install hooks
pre-commit install

# Create baseline
detect-secrets scan > .secrets.baseline
```

### Update .gitignore

```bash
# Add to .gitignore
cat >> .gitignore << 'EOF'

# Environment variables
.env
.env.local
.env.*.local

# Secrets
secrets/
*.pem
*.key
*.p12
*.pfx

# AWS credentials
.aws/credentials

# Terraform state (if using)
*.tfstate
*.tfstate.backup

# IDE
.vscode/settings.json
.idea/

EOF
```

### Create .env.example Template

```bash
cat > .env.example << 'EOF'
# Environment
ENVIRONMENT=local

# AWS Configuration (LocalStack)
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# DynamoDB
DYNAMODB_TABLE=fitagent-main

# S3
S3_BUCKET=fitagent-receipts-local

# SQS
SQS_QUEUE_URL=http://localhost:4566/000000000000/fitagent-messages
NOTIFICATION_QUEUE_URL=http://localhost:4566/000000000000/fitagent-notifications
DLQ_URL=http://localhost:4566/000000000000/fitagent-messages-dlq

# Twilio Configuration (REPLACE WITH YOUR CREDENTIALS)
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Google OAuth (REPLACE WITH YOUR CREDENTIALS)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Microsoft OAuth (REPLACE WITH YOUR CREDENTIALS)
OUTLOOK_CLIENT_ID=your_outlook_client_id_here
OUTLOOK_CLIENT_SECRET=your_outlook_client_secret_here

# OAuth Redirect
OAUTH_REDIRECT_URI=http://localhost:8000/oauth/callback

# AWS Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
EOF
```

---

## Step 6: Monitor for Abuse

### Set Up Twilio Alerts

1. **Usage Alerts:**
   ```
   https://console.twilio.com/us1/monitor/alerts
   ```

2. **Create Alerts for:**
   - Daily message volume > threshold
   - Unusual spending patterns
   - Failed authentication attempts

### Set Up AWS CloudWatch Alarms

```bash
# Create alarm for unusual Lambda invocations
aws cloudwatch put-metric-alarm \
    --alarm-name fitagent-unusual-activity \
    --alarm-description "Alert on unusual Lambda activity" \
    --metric-name Invocations \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 3600 \
    --threshold 1000 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --region us-east-1
```

---

## Step 7: Document and Report

### Internal Documentation

Create incident report:

```markdown
# Security Incident Report

**Date:** [Current Date]
**Incident:** Exposed Twilio credentials in Git repository
**Severity:** High
**Status:** Resolved

## Timeline
- [Time]: Credentials exposed in commit [hash]
- [Time]: Incident discovered
- [Time]: Credentials rotated
- [Time]: Git history cleaned
- [Time]: Monitoring implemented

## Impact Assessment
- No unauthorized usage detected
- No financial impact
- No customer data compromised

## Actions Taken
1. Rotated Twilio Auth Token
2. Updated all environments with new credentials
3. Cleaned Git history
4. Implemented pre-commit hooks
5. Added monitoring and alerts

## Lessons Learned
- Need better secret management practices
- Pre-commit hooks should be mandatory
- Regular security audits needed

## Follow-up Actions
- [ ] Quarterly security training
- [ ] Implement secret scanning in CI/CD
- [ ] Review all other credentials
```

### External Reporting (if required)

If you have compliance requirements (GDPR, SOC 2, etc.):

1. **Notify Security Team**
2. **Document in Compliance System**
3. **Update Security Policies**

---

## Prevention Checklist

Going forward, ensure:

- [ ] `.env` is in `.gitignore`
- [ ] Pre-commit hooks installed
- [ ] Secrets stored in AWS Secrets Manager
- [ ] CI/CD uses encrypted secrets
- [ ] Regular security audits scheduled
- [ ] Team trained on secret management
- [ ] Monitoring and alerts configured
- [ ] Incident response plan documented

---

## Resources

**Twilio Security:**
- https://www.twilio.com/docs/usage/security

**AWS Secrets Manager:**
- https://docs.aws.amazon.com/secretsmanager/

**Git Secret Scanning:**
- https://github.com/Yelp/detect-secrets
- https://github.com/trufflesecurity/trufflehog

**GitHub Security:**
- https://docs.github.com/en/code-security

---

## Support Contacts

**Twilio Support:**
- https://support.twilio.com/
- Phone: 1-888-TWILIO-1

**AWS Support:**
- https://console.aws.amazon.com/support/

**Internal Security Team:**
- Email: security@fitagent.com
- Slack: #security-incidents

---

**Document Created:** 2024-01-15  
**Last Updated:** 2024-01-15  
**Next Review:** After incident resolution
