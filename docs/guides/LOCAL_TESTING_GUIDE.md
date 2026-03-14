# Local Testing Guide

Complete guide for testing FitAgent locally with mock endpoints and Twilio Sandbox.

## Quick Start

```bash
# 1. Start services
make start

# 2. Run tests
make test
```

Optional: Verify setup with `make verify`

---

## Testing Options

### Option 1: Mock Testing (Recommended for Development)

Test without Twilio - fastest iteration:

```bash
# Run automated tests
make test

# Manual test via API
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Hello, I want to register as a trainer"
```

### Option 2: E2E with Twilio Sandbox

Test with real WhatsApp messages:

1. **Get Twilio credentials** from https://console.twilio.com/
2. **Update .env**:
   ```env
   TWILIO_ACCOUNT_SID=ACxxxxxxxx
   TWILIO_AUTH_TOKEN=xxxxxxxx
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   ```
3. **Run the setup**:
   ```bash
   make e2e-twilio
   ```
   
The script will start services, launch ngrok, and guide you through Twilio configuration.

---

## Troubleshooting

### Services not starting
```bash
# Clean restart
make clean
make start
```

### Twilio signature validation failing
- Verify credentials in .env match Twilio Console
- Ensure webhook URL is exactly: `https://your-ngrok-url/webhook`
- Restart after changing .env: `make restart`

### Check logs
```bash
# All logs
make logs

# API only
docker logs -f fitagent-api

# LocalStack only
docker logs -f fitagent-localstack
```

---

## Verification

```bash
# Check services
./scripts/verify_setup.sh

# Check data
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1
```

---

## Documentation

- Complete setup: `docs/guides/TWILIO_SANDBOX_SETUP.md`
- CI/CD: `docs/guides/CI_CD_SETUP.md`



