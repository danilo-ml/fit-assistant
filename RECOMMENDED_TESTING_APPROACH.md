# Recommended Testing Approach for FitAgent

## 🎯 Best Way to Test Locally: Twilio Sandbox + ngrok

**Yes, testing with Twilio Sandbox is the BEST approach for local development!**

Here's why and how to do it properly.

## 📊 Testing Methods Comparison

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **Twilio Sandbox + ngrok** ✅ | • Real WhatsApp messages<br>• Complete E2E flow<br>• Tests webhooks<br>• Tests signature validation<br>• Free | • Requires ngrok<br>• URL changes on restart<br>• Requires internet | **Full integration testing** |
| Mock Testing | • Fast<br>• No external dependencies<br>• Repeatable | • Doesn't test webhooks<br>• Doesn't test Twilio integration<br>• Not realistic | Unit/integration tests |
| Staging Deployment | • Real AWS services<br>• Production-like<br>• Stable URL | • Costs money<br>• Slower iteration<br>• Harder to debug | Pre-production validation |

## 🚀 Recommended Full Testing Workflow

### Phase 1: Quick Development Testing (Mock)
**When:** During active development, testing individual features

```bash
# Quick test without Twilio
python scripts/test_whatsapp_local.py
```

**Use for:**
- Testing business logic
- Testing data models
- Quick iterations
- Unit tests

### Phase 2: Integration Testing (Twilio Sandbox) ⭐ RECOMMENDED
**When:** Testing complete flow, before committing code

```bash
# One-command startup
./scripts/start_local_with_twilio.sh
```

**Use for:**
- Testing complete E2E flow
- Testing with real WhatsApp
- Validating webhook integration
- Testing media uploads
- User acceptance testing

### Phase 3: Pre-Production Testing (Staging)
**When:** Before deploying to production

```bash
# Deploy to staging
./scripts/deploy_staging.sh
```

**Use for:**
- Testing with real AWS Bedrock
- Testing with real calendar APIs
- Performance testing
- Final validation

## 🎯 Complete Setup Guide (Recommended Approach)

### Prerequisites

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Get Twilio credentials
# 1. Go to https://console.twilio.com/
# 2. Copy Account SID and Auth Token
```

### Step-by-Step Setup

#### 1. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Twilio credentials
nano .env
```

Update these values in `.env`:
```env
TWILIO_ACCOUNT_SID=AC...your-account-sid...
TWILIO_AUTH_TOKEN=...your-auth-token...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
```

#### 2. Start Everything (Automated)

```bash
# This script does everything for you!
./scripts/start_local_with_twilio.sh
```

This script will:
1. ✅ Check prerequisites (ngrok, Docker)
2. ✅ Start Docker services (API + LocalStack)
3. ✅ Wait for services to be ready
4. ✅ Start ngrok tunnel
5. ✅ Display your webhook URL
6. ✅ Guide you through Twilio configuration
7. ✅ Start watching logs

#### 3. Configure Twilio (One-Time)

The script will show you the webhook URL. Then:

1. **Join Sandbox (First Time Only):**
   - Go to: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
   - Send the join code to Twilio WhatsApp number
   - Example: Send `join happy-dog` to `+1 415 523 8886`

2. **Configure Webhook:**
   - In Twilio Console, find "Sandbox Configuration"
   - Set "When a message comes in" to: `https://your-ngrok-url.ngrok.io/webhook`
   - Method: `HTTP POST`
   - Click "Save"

#### 4. Test!

Send a WhatsApp message to the Twilio number:
```
Hello, I want to register as a trainer
```

Watch the logs in your terminal to see the processing!

### Alternative: Manual Setup

If you prefer manual control:

**Terminal 1 - Services:**
```bash
docker-compose up
```

**Terminal 2 - ngrok:**
```bash
ngrok http 8000
# Copy the https URL
```

**Terminal 3 - Logs:**
```bash
docker logs -f fitagent-api
```

**Browser:**
- Configure Twilio webhook with ngrok URL
- Open http://localhost:4040 for ngrok inspector

## 🧪 Testing Scenarios

### Basic Flow Test

1. **Trainer Registration:**
   ```
   You: Hello, I want to register as a trainer
   Bot: Welcome! Let's get you registered...
   ```

2. **Register Student:**
   ```
   You: Register student John Doe, phone +1234567890
   Bot: Student John Doe registered successfully!
   ```

3. **Schedule Session:**
   ```
   You: Schedule session with John tomorrow at 3pm
   Bot: Session scheduled for [date] at 3:00 PM
   ```

4. **View Students:**
   ```
   You: Show me all my students
   Bot: You have 1 student: John Doe (+1234567890)
   ```

### Advanced Testing

**Test with Media (Receipt Upload):**
1. Send an image via WhatsApp
2. Send: "Register payment from John for $50"
3. Bot should save the receipt to S3

**Test Multi-User:**
- Use your phone as trainer
- Use friend's phone as student (they also join sandbox)
- Test student queries

## 🔍 Monitoring & Debugging

### Essential Monitoring Tools

**1. API Logs (Real-time):**
```bash
docker logs -f fitagent-api
```

**2. ngrok Inspector (HTTP Requests):**
- Open: http://localhost:4040
- See all webhook requests/responses
- Debug signature validation

**3. DynamoDB Data:**
```bash
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1
```

**4. Twilio Logs:**
- Go to: https://console.twilio.com/us1/monitor/logs/sms
- See message delivery status

### Debugging Checklist

When something doesn't work:

- [ ] Services running? `docker ps --filter "name=fitagent"`
- [ ] API responding? `curl http://localhost:8000/health`
- [ ] ngrok running? Check http://localhost:4040
- [ ] Webhook URL correct in Twilio?
- [ ] Twilio credentials in .env?
- [ ] API restarted after .env changes?
- [ ] Check logs: `docker logs fitagent-api --tail 50`

## 🎨 Recommended Development Workflow

### Daily Development Cycle

```bash
# Morning: Start everything
./scripts/start_local_with_twilio.sh

# During development:
# - Make code changes
# - Docker auto-reloads (volume mounted)
# - Test via WhatsApp
# - Check logs

# Quick tests without WhatsApp:
python scripts/test_whatsapp_local.py

# Run unit tests:
pytest tests/unit/ -v

# End of day: Stop services
docker-compose down
pkill ngrok
```

### Before Committing Code

```bash
# 1. Run all tests
pytest --cov=src --cov-report=term

# 2. Test E2E with Twilio
./scripts/start_local_with_twilio.sh
# Send test messages via WhatsApp

# 3. Check code quality
black src/
flake8 src/
mypy src/

# 4. Commit
git add .
git commit -m "Feature: ..."
```

## 📈 Testing Maturity Levels

### Level 1: Basic (You are here!)
- ✅ Local services running
- ✅ Mock testing available
- ✅ Twilio Sandbox setup
- ✅ Manual E2E testing

### Level 2: Intermediate (Next steps)
- [ ] Automated E2E tests with Twilio
- [ ] CI/CD pipeline
- [ ] Staging environment
- [ ] Integration tests in CI

### Level 3: Advanced (Future)
- [ ] Production monitoring
- [ ] Automated regression tests
- [ ] Load testing
- [ ] A/B testing framework

## 🚨 Common Issues & Solutions

### Issue: ngrok URL keeps changing

**Problem:** Free ngrok URLs change on restart

**Solutions:**
1. **Quick fix:** Update Twilio webhook each time
2. **Better:** Use ngrok paid plan ($8/month) for fixed subdomain
3. **Best:** Deploy to staging for stable URL

### Issue: Slow responses

**Problem:** Twilio times out (15 seconds)

**Solutions:**
1. Check LocalStack is running: `docker ps | grep localstack`
2. Optimize AI agent calls (use caching)
3. Use async processing (already implemented via SQS)

### Issue: Signature validation fails

**Problem:** "Invalid Twilio signature" error

**Solutions:**
1. Verify TWILIO_AUTH_TOKEN in .env
2. Ensure webhook URL matches exactly (https, no trailing slash)
3. Restart API: `docker-compose restart api`
4. Check ngrok URL hasn't changed

## 📚 Documentation Reference

- **Quick Start:** [QUICK_START.md](QUICK_START.md)
- **Twilio Setup:** [TWILIO_SANDBOX_SETUP.md](TWILIO_SANDBOX_SETUP.md)
- **Mock Testing:** [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)
- **E2E Summary:** [E2E_TESTING_SUMMARY.md](E2E_TESTING_SUMMARY.md)

## 🎉 Summary

### Best Practice: Hybrid Approach

**For rapid development:**
```bash
python scripts/test_whatsapp_local.py  # Fast mock testing
```

**For integration testing:**
```bash
./scripts/start_local_with_twilio.sh   # Full E2E with WhatsApp
```

**For pre-production:**
```bash
./scripts/deploy_staging.sh            # Real AWS environment
```

### Why Twilio Sandbox is Best for Local Testing

✅ **Complete E2E testing** - Tests the entire flow
✅ **Real user experience** - See exactly what users see
✅ **Free** - No cost for development
✅ **Fast iteration** - Make changes, test immediately
✅ **Catches integration bugs** - Tests webhook, signatures, etc.
✅ **Easy setup** - One script does everything

### Quick Start Command

```bash
# Everything you need in one command:
./scripts/start_local_with_twilio.sh
```

**That's it! You're ready to test FitAgent locally with real WhatsApp messages!** 🚀
