# 🚨 URGENT: Security Actions Required

## Exposed Credentials Detected

Twilio credentials were found in the Git repository. **Immediate action required.**

---

## ⚡ Quick Action Steps (Do This Now)

### 1. Rotate Twilio Auth Token (5 minutes)

```bash
# Go to Twilio Console
open https://console.twilio.com/

# Navigate to: Account → API keys & tokens → Rotate Token
# Copy the new token immediately
```

### 2. Update Local Environment (2 minutes)

```bash
# Edit your .env file
nano .env

# Replace with NEW credentials:
# TWILIO_ACCOUNT_SID=AC...your-new-sid...
# TWILIO_AUTH_TOKEN=...your-new-token...
```

### 3. Check for Unauthorized Usage (5 minutes)

```bash
# Check Twilio logs
open https://console.twilio.com/us1/monitor/logs/sms

# Look for:
# - Unexpected messages
# - Unknown phone numbers
# - Unusual timestamps
```

### 4. Update Staging/Production (10 minutes)

```bash
# Update AWS Secrets Manager
aws secretsmanager update-secret \
    --secret-id fitagent/staging/twilio \
    --secret-string '{
      "account_sid": "AC...new-sid...",
      "auth_token": "...new-token...",
      "whatsapp_number": "whatsapp:+1234567890"
    }' \
    --region us-east-1
```

---

## 📋 Complete Action Checklist

### Immediate (Within 1 Hour)

- [ ] **Rotate Twilio Auth Token**
  - Go to Twilio Console
  - Rotate token
  - Save new token securely

- [ ] **Check for Abuse**
  - Review Twilio message logs
  - Check billing for unusual charges
  - Look for unauthorized usage

- [ ] **Update All Environments**
  - Update local `.env` file
  - Update AWS Secrets Manager (staging)
  - Update AWS Secrets Manager (production)
  - Update CI/CD secrets (if applicable)

### Short Term (Within 24 Hours)

- [ ] **Clean Git History**
  - Use BFG Repo-Cleaner or git-filter-repo
  - Remove exposed credentials from history
  - Force push cleaned history
  - See: [SECURITY_INCIDENT_RESPONSE.md](SECURITY_INCIDENT_RESPONSE.md)

- [ ] **Implement Monitoring**
  - Set up Twilio usage alerts
  - Configure CloudWatch alarms
  - Enable anomaly detection

- [ ] **Install Pre-Commit Hooks**
  ```bash
  pip install pre-commit
  pre-commit install
  ```

### Medium Term (Within 1 Week)

- [ ] **Security Audit**
  - Review all other credentials
  - Check for other exposed secrets
  - Audit access logs

- [ ] **Update Documentation**
  - Document incident
  - Update security policies
  - Train team on best practices

- [ ] **Implement Additional Security**
  - Enable GitHub secret scanning
  - Set up automated security scans
  - Review IAM permissions

---

## 📚 Detailed Guides

For complete instructions, see:

1. **[SECURITY_INCIDENT_RESPONSE.md](SECURITY_INCIDENT_RESPONSE.md)**
   - Complete incident response guide
   - Step-by-step credential rotation
   - Git history cleaning
   - Monitoring setup

2. **[.github/SECURITY.md](.github/SECURITY.md)**
   - Security policy
   - Best practices
   - Reporting vulnerabilities
   - Security checklist

---

## 🔍 What Was Exposed

**Files containing credentials:**
- `infrastructure/parameters/staging.json` (commit: 5880233c2e)
- `scripts/start_local_with_twilio.sh` (commit: 5880233c2e)

**Exposed data:**
- Twilio Account SID: `AC[REDACTED]` (starts with AC)
- Twilio Auth Token: `[REDACTED]` (32 character hex string)
- Twilio WhatsApp Number: `whatsapp:+1[REDACTED]`

**Status:**
- ✅ Removed from current files
- ⚠️ Still in Git history (needs cleaning)
- ⚠️ Credentials need rotation

---

## ❓ FAQ

### Q: How serious is this?

**A:** High severity. Exposed Twilio credentials can be used to:
- Send unauthorized messages (costs money)
- Access your Twilio account
- View message history
- Modify account settings

### Q: Do I need to rotate the Account SID?

**A:** No, only the Auth Token needs rotation. The Account SID is like a username (public), but the Auth Token is like a password (secret).

### Q: Will rotating break existing services?

**A:** Yes, temporarily. You need to update all environments with the new token:
1. Local `.env` file
2. AWS Secrets Manager (staging/production)
3. CI/CD secrets
4. Any other services using Twilio

### Q: How do I know if credentials were abused?

**A:** Check:
1. Twilio message logs: https://console.twilio.com/us1/monitor/logs/sms
2. Twilio billing: https://console.twilio.com/us1/billing
3. Look for messages you didn't send
4. Check for unusual charges

### Q: Should I make the repository private?

**A:** If it's currently public, yes, make it private immediately. If it's already private, assess who has access and review access logs.

---

## 🆘 Need Help?

**Twilio Support:**
- Phone: 1-888-TWILIO-1
- Web: https://support.twilio.com/

**AWS Support:**
- Console: https://console.aws.amazon.com/support/

**Internal Security Team:**
- Email: security@fitagent.com
- Slack: #security-incidents

---

## ✅ After Completing Actions

Once you've completed all immediate actions:

1. **Verify everything works:**
   ```bash
   # Test local environment
   docker-compose up -d
   curl http://localhost:8000/health
   
   # Send test WhatsApp message
   ```

2. **Document the incident:**
   - What happened
   - When it was discovered
   - Actions taken
   - Lessons learned

3. **Update this checklist:**
   - Mark completed items
   - Add completion timestamps
   - Note any issues encountered

---

**Created:** 2024-01-15  
**Priority:** URGENT  
**Status:** ACTION REQUIRED
