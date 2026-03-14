# Scripts Directory

This directory contains specialized scripts for FitAgent. For daily development, use the **Makefile** instead (`make start`, `make test`, etc.).

## Development Scripts

### `start_local_with_twilio.sh` - E2E Testing Setup
**Complete setup for testing with real WhatsApp messages**

```bash
./scripts/start_local_with_twilio.sh
```

This script:
- Starts Docker services
- Launches ngrok tunnel
- Guides you through Twilio webhook configuration
- Shows live logs

Use this when you need to test with actual WhatsApp messages via Twilio Sandbox.

### `verify_setup.sh` - Environment Verification
**Checks that all services are properly configured**

```bash
./scripts/verify_setup.sh
```

Verifies:
- Docker is running
- Services are healthy
- DynamoDB tables exist
- SQS queues exist
- S3 buckets exist

Use this to troubleshoot setup issues.

## Deployment Scripts

### `deploy_staging.sh` - Deploy to Staging
Deploy application to staging environment.

### `deploy_production.sh` - Deploy to Production
Deploy application to production environment.

### `package_lambda.sh` - Package Lambda Functions
Create deployment packages for Lambda functions.

## Infrastructure Scripts

### `update_secrets.sh` - Update AWS Secrets
Update secrets in AWS Secrets Manager (OAuth tokens, API keys).

---

## Quick Reference

**Daily development (use Makefile):**
```bash
make start
make logs
make test
```

**E2E testing with WhatsApp:**
```bash
make e2e-twilio
# or directly: ./scripts/start_local_with_twilio.sh
```

**Troubleshooting:**
```bash
make verify
# or directly: ./scripts/verify_setup.sh
```
