# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

### 1. Do Not Disclose Publicly
- Do not open a public GitHub issue
- Do not discuss in public forums or social media
- Do not share details until we've addressed the issue

### 2. Report Privately
Send details to: **security@fitagent.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)
- Your contact information

### 3. Response Timeline
- **24 hours**: Initial acknowledgment
- **72 hours**: Preliminary assessment
- **7 days**: Detailed response with timeline
- **30 days**: Fix deployed (for critical issues)

### 4. Disclosure Policy
- We'll work with you on responsible disclosure
- Credit will be given (unless you prefer anonymity)
- Public disclosure after fix is deployed

## Security Best Practices

### Authentication & Authorization
- Phone number-based user identification
- Multi-tenant data isolation (trainer_id in all queries)
- OAuth 2.0 for calendar integrations
- No password storage (WhatsApp handles auth)

### Data Protection
- **Encryption at Rest**: DynamoDB and S3 use AWS KMS
- **Encryption in Transit**: TLS 1.2+ for all API calls
- **Token Storage**: OAuth tokens encrypted in Secrets Manager
- **PII Handling**: Minimal collection, encrypted storage

### API Security
- **Rate Limiting**: API Gateway throttling enabled
- **Input Validation**: All inputs validated before processing
- **Webhook Signatures**: Twilio signature verification
- **CORS**: Restricted to authorized origins

### AWS Security
- **IAM Roles**: Least-privilege policies for all services
- **VPC**: Lambda functions in private subnets (optional)
- **Security Groups**: Restrictive inbound/outbound rules
- **CloudTrail**: Audit logging enabled
- **GuardDuty**: Threat detection enabled

### Secrets Management
- **AWS Secrets Manager**: Store all API keys and tokens
- **Automatic Rotation**: Enable for supported secrets
- **No Hardcoding**: Never commit secrets to code
- **Environment Variables**: Use for non-sensitive config only

### Code Security
- **Dependency Scanning**: Automated with GitHub Dependabot
- **SAST**: Static analysis in CI pipeline
- **Code Review**: Required for all changes
- **Pre-commit Hooks**: Prevent secret commits

## Security Checklist

### Development
- [ ] No secrets in code or .env files
- [ ] Input validation for all user inputs
- [ ] SQL injection prevention (use parameterized queries)
- [ ] XSS prevention (sanitize outputs)
- [ ] CSRF protection (for web endpoints)
- [ ] Dependency updates (monthly)

### Deployment
- [ ] Secrets in AWS Secrets Manager
- [ ] IAM roles with least privilege
- [ ] CloudTrail logging enabled
- [ ] VPC configuration reviewed
- [ ] Security groups configured
- [ ] KMS encryption enabled

### Operations
- [ ] Monitor CloudWatch alarms
- [ ] Review CloudTrail logs weekly
- [ ] Rotate credentials quarterly
- [ ] Update dependencies monthly
- [ ] Security audit annually
- [ ] Incident response plan tested

## Common Vulnerabilities

### Prevented
- **SQL Injection**: Using DynamoDB (NoSQL) with parameterized queries
- **XSS**: Input sanitization and output encoding
- **CSRF**: Stateless API with token-based auth
- **SSRF**: Restricted outbound network access
- **Path Traversal**: Input validation on file paths

### Mitigated
- **DDoS**: API Gateway rate limiting and WAF
- **Brute Force**: Rate limiting on authentication endpoints
- **Data Leakage**: Encryption at rest and in transit
- **Privilege Escalation**: Multi-tenant isolation

## Compliance

### Data Privacy
- **GDPR**: User data deletion on request
- **CCPA**: Data access and deletion rights
- **HIPAA**: Not applicable (no health data)

### Standards
- **OWASP Top 10**: Addressed in design
- **CIS Benchmarks**: AWS configuration follows CIS guidelines
- **SOC 2**: Planned for future certification

## Incident Response

### Detection
- CloudWatch alarms for anomalies
- GuardDuty threat detection
- Manual security reviews

### Response Process
1. **Identify**: Confirm security incident
2. **Contain**: Isolate affected systems
3. **Eradicate**: Remove threat
4. **Recover**: Restore normal operations
5. **Learn**: Post-incident review

### Contact
- **Security Team**: security@fitagent.com
- **On-Call**: +1-555-SECURITY (24/7)

## Security Updates

### Notification Channels
- GitHub Security Advisories
- Email to registered users
- Status page updates

### Update Policy
- **Critical**: Immediate deployment
- **High**: Within 7 days
- **Medium**: Within 30 days
- **Low**: Next release cycle

## Third-Party Security

### AWS Services
- Regular security updates by AWS
- Compliance certifications maintained
- Security best practices followed

### Dependencies
- Automated vulnerability scanning
- Monthly dependency updates
- Security patches applied promptly

### Twilio
- Webhook signature verification
- TLS for all communications
- Rate limiting enabled

## Security Contacts

- **General Security**: security@fitagent.com
- **Vulnerability Reports**: security@fitagent.com
- **Security Questions**: security@fitagent.com

## Acknowledgments

We thank the following security researchers for responsible disclosure:
- (List will be updated as vulnerabilities are reported and fixed)

## Additional Resources

- [AWS Security Best Practices](https://aws.amazon.com/security/best-practices/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Twilio Security](https://www.twilio.com/security)
