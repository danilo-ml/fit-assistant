# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in FitAgent, please report it by emailing security@fitagent.com. Do not create a public GitHub issue.

**Please include:**
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and provide a timeline for resolution.

---

## Security Best Practices

### For Developers

#### 1. Never Commit Secrets

**Never commit:**
- API keys
- Passwords
- Auth tokens
- Private keys
- OAuth secrets
- Database credentials
- Environment variables with sensitive data

**Use instead:**
- AWS Secrets Manager (staging/production)
- `.env` files (local development, gitignored)
- CI/CD encrypted secrets

#### 2. Use Pre-Commit Hooks

Install pre-commit hooks to catch secrets before commit:

```bash
pip install pre-commit
pre-commit install
```

#### 3. Review Code for Security Issues

Before submitting PR:
- [ ] No hardcoded credentials
- [ ] No sensitive data in logs
- [ ] Input validation implemented
- [ ] SQL injection prevention (if applicable)
- [ ] XSS prevention (if applicable)
- [ ] CSRF protection (if applicable)
- [ ] Rate limiting implemented
- [ ] Authentication/authorization checks

#### 4. Keep Dependencies Updated

```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt
```

---

## Security Features

### Data Protection

**Encryption at Rest:**
- DynamoDB: KMS encryption enabled
- S3: Server-side encryption (SSE-S3)
- Secrets Manager: KMS encryption
- OAuth tokens: Encrypted with KMS

**Encryption in Transit:**
- All API calls use HTTPS/TLS 1.2+
- Twilio webhook uses TLS
- OAuth flows use secure redirects

### Access Control

**IAM Roles:**
- Least privilege principle
- Separate roles per Lambda function
- No long-term credentials in code

**Multi-Tenancy:**
- Data isolated per trainer
- Phone number-based routing
- Cross-tenant access blocked

### Monitoring

**CloudWatch Logs:**
- PII sanitized
- Phone numbers masked
- Structured logging with context

**CloudTrail:**
- All API calls logged
- Audit trail maintained
- Compliance ready

### Input Validation

**All inputs validated:**
- Phone numbers (E.164 format)
- Email addresses
- Dates and times
- Payment amounts
- Message content

---

## Compliance

### GDPR

**Data Protection:**
- Personal data encrypted
- Data retention policies enforced
- Right to access implemented
- Right to deletion supported
- Data portability available

**Data Processing:**
- Data processors documented (AWS, Twilio)
- Processing activities recorded
- Privacy policy maintained

### Security Standards

**Following:**
- OWASP Top 10
- AWS Well-Architected Framework
- CIS AWS Foundations Benchmark

---

## Incident Response

### If You Discover a Security Issue

1. **Do not commit or push** any code that might expose the issue
2. **Report immediately** to security@fitagent.com
3. **Document** what you found and how
4. **Wait for guidance** before taking action

### If Credentials Are Exposed

Follow the [Security Incident Response Guide](../SECURITY_INCIDENT_RESPONSE.md):

1. Rotate credentials immediately
2. Check for unauthorized usage
3. Clean Git history
4. Update all environments
5. Implement monitoring
6. Document incident

---

## Security Checklist

### Before Committing Code

- [ ] No secrets in code
- [ ] No secrets in comments
- [ ] No secrets in test files
- [ ] `.env` not committed
- [ ] Pre-commit hooks pass
- [ ] Code reviewed for security issues

### Before Deploying

- [ ] All tests passing
- [ ] Security scan completed
- [ ] Dependencies updated
- [ ] Secrets rotated (if needed)
- [ ] Monitoring configured
- [ ] Rollback plan ready

### Regular Maintenance

- [ ] Weekly: Review CloudWatch logs for anomalies
- [ ] Monthly: Update dependencies
- [ ] Quarterly: Security audit
- [ ] Annually: Penetration testing

---

## Security Tools

### Recommended Tools

**Secret Scanning:**
- [detect-secrets](https://github.com/Yelp/detect-secrets)
- [truffleHog](https://github.com/trufflesecurity/trufflehog)
- [git-secrets](https://github.com/awslabs/git-secrets)

**Dependency Scanning:**
- [pip-audit](https://github.com/pypa/pip-audit)
- [safety](https://github.com/pyupio/safety)
- [Dependabot](https://github.com/dependabot) (GitHub)

**Code Analysis:**
- [bandit](https://github.com/PyCQA/bandit) (Python security linter)
- [semgrep](https://semgrep.dev/) (Static analysis)
- [SonarQube](https://www.sonarqube.org/)

---

## Contact

**Security Team:**
- Email: security@fitagent.com
- Slack: #security
- PagerDuty: Security on-call

**Emergency Contact:**
- Phone: +1-555-SECURITY
- Available: 24/7

---

## Acknowledgments

We appreciate security researchers who responsibly disclose vulnerabilities. Contributors will be acknowledged (with permission) in our security hall of fame.

---

**Last Updated:** 2024-01-15  
**Next Review:** 2024-04-15
