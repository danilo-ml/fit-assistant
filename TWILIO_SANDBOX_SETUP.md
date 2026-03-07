# Twilio Sandbox Local Testing Guide

This guide shows you how to test FitAgent with real WhatsApp messages using Twilio Sandbox and your local environment.

## 🎯 Why Use Twilio Sandbox?

**Advantages:**
- ✅ Test with real WhatsApp messages
- ✅ Test complete webhook flow
- ✅ Test Twilio signature validation
- ✅ Test media uploads (images, receipts)
- ✅ See actual user experience
- ✅ Free for development

**vs. Mock Testing:**
- Mock testing is faster but doesn't test the full integration
- Twilio Sandbox tests the complete end-to-end flow

## 📋 Prerequisites

1. Twilio account (free tier works)
2. ngrok or similar tunneling tool
3. WhatsApp on your phone
4. Local services running

## 🚀 Complete Setup (Step-by-Step)

### Step 1: Install ngrok

```bash
# macOS
brew install ngrok

# Or download from https://ngrok.com/download
```

### Step 2: Start Local Services

```bash
# Start all services
docker-compose up -d

# Verify services are running
docker ps --filter "name=fitagent"

# Check API health
curl http://localhost:8000/health
```

### Step 3: Expose Local API with ngrok

```bash
# Start ngrok tunnel
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://abc123.ngrok.io -> http://localhost:8000
```

**Important:** Copy the `https://` URL (e.g., `https://abc123.ngrok.io`)

**Keep this terminal open!** ngrok must stay running.

### Step 4: Configure Twilio Sandbox

1. **Go to Twilio Console:**
   - Visit: https://console.twilio.com/
   - Login to your account

2. **Navigate to WhatsApp Sandbox:**
   - Go to: Messaging → Try it out → Send a WhatsApp message
   - Or direct link: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

3. **Join Sandbox (First Time Only):**
   - You'll see a code like: `join <word>-<word>`
   - Send this message to the Twilio WhatsApp number from your phone
   - Example: Send `join happy-dog` to `+1 415 523 8886`

4. **Configure Webhook URL:**
   - In Twilio Console, find "Sandbox Configuration"
   - Set "When a message comes in" to:
     ```
     https://your-ngrok-url.ngrok.io/webhook
     ```
   - Example: `https://abc123.ngrok.io/webhook`
   - Method: `HTTP POST`
   - Click "Save"

### Step 5: Update Local Environment Variables

Make sure your `.env` file has Twilio credentials:

```bash
# Edit .env file
nano .env
```

Add/verify these values:
```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=AC...your-account-sid...
TWILIO_AUTH_TOKEN=...your-auth-token...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# These should already be set
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://localhost:4566
DYNAMODB_TABLE=fitagent-main
```

**Get your credentials:**
- Account SID: https://console.twilio.com/
- Auth Token: Click "Show" next to Auth Token

### Step 6: Restart API to Load New Config

```bash
# Restart API container
docker-compose restart api

# Wait a few seconds
sleep 5

# Verify it's running
curl http://localhost:8000/health
```

### Step 7: Test with WhatsApp!

**Send a message from your phone:**
1. Open WhatsApp
2. Go to the Twilio Sandbox number chat
3. Send: `Hello, I want to register as a trainer`

**Watch the logs:**
```bash
# In a new terminal, watch API logs
docker logs -f fitagent-api
```

You should see:
- Webhook request received
- Signature validation
- Message processing
- Response sent

## 🧪 Test Scenarios

### Scenario 1: Trainer Registration
```
You: Hello, I want to register as a trainer
Bot: Welcome! Let's get you registered...
```

### Scenario 2: Register Student
```
You: Register student John Doe, phone +1234567890, email john@example.com
Bot: Student John Doe has been registered successfully!
```

### Scenario 3: Schedule Session
```
You: Schedule session with John tomorrow at 3pm for 1 hour
Bot: Session scheduled for [date] at 3:00 PM with John Doe
```

### Scenario 4: View Students
```
You: Show me all my students
Bot: You have 2 students:
     1. John Doe (+1234567890)
     2. Jane Smith (+0987654321)
```

### Scenario 5: Test with Media (Receipt Upload)
```
You: [Send an image]
You: Register payment from John for $50
Bot: Payment of $50 registered for John Doe. Receipt saved.
```

## 🔍 Monitoring & Debugging

### Watch Real-Time Logs

**Terminal 1 - API Logs:**
```bash
docker logs -f fitagent-api
```

**Terminal 2 - LocalStack Logs:**
```bash
docker logs -f fitagent-localstack
```

**Terminal 3 - ngrok Web Interface:**
- Open: http://localhost:4040
- See all HTTP requests/responses
- Very useful for debugging!

### Check Webhook Requests in ngrok

1. Open http://localhost:4040 in browser
2. You'll see all webhook requests from Twilio
3. Click on a request to see:
   - Headers (including X-Twilio-Signature)
   - Body (form data)
   - Response from your API

### Verify Data in DynamoDB

```bash
# List all items
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1

# Count items
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main \
  --select COUNT --region us-east-1
```

### Check Twilio Logs

1. Go to: https://console.twilio.com/us1/monitor/logs/sms
2. See all messages sent/received
3. Check for errors or delivery issues

## 🐛 Troubleshooting

### Issue: "Invalid Twilio Signature"

**Cause:** Webhook URL doesn't match or credentials are wrong

**Fix:**
1. Verify ngrok URL is correct in Twilio Console
2. Check TWILIO_AUTH_TOKEN in .env
3. Restart API: `docker-compose restart api`
4. Make sure URL uses `https://` (not `http://`)

### Issue: "Webhook timeout"

**Cause:** API is slow or not responding

**Fix:**
1. Check API logs: `docker logs fitagent-api --tail 50`
2. Verify LocalStack is running: `docker ps | grep localstack`
3. Check ngrok is running: `curl http://localhost:4040/api/tunnels`

### Issue: "No response from bot"

**Cause:** Message processing failed

**Fix:**
1. Check API logs for errors
2. Verify DynamoDB table exists:
   ```bash
   AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
     aws --endpoint-url=http://localhost:4566 \
     dynamodb list-tables --region us-east-1
   ```
3. Check if message was received:
   ```bash
   docker logs fitagent-api 2>&1 | grep "Webhook request received"
   ```

### Issue: ngrok URL keeps changing

**Solution:** Use ngrok with a fixed domain (paid feature) or update Twilio webhook URL each time

**Free alternative:**
```bash
# Use localtunnel (free, but less stable)
npm install -g localtunnel
lt --port 8000 --subdomain fitagent-dev
```

### Issue: "Cannot connect to LocalStack"

**Fix:**
```bash
# Restart LocalStack
docker-compose restart localstack

# Wait for initialization
sleep 30

# Verify it's ready
curl http://localhost:4566/_localstack/health
```

## 📊 Complete Testing Workflow

### Recommended Setup (3 Terminals)

**Terminal 1 - Services:**
```bash
docker-compose up
# Or use -d for detached mode
```

**Terminal 2 - ngrok:**
```bash
ngrok http 8000
```

**Terminal 3 - Monitoring:**
```bash
# Watch logs
docker logs -f fitagent-api

# Or check data
watch -n 2 'AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --select COUNT --region us-east-1'
```

### Testing Checklist

- [ ] Services running (`docker ps`)
- [ ] ngrok tunnel active (check http://localhost:4040)
- [ ] Twilio webhook configured with ngrok URL
- [ ] .env has correct Twilio credentials
- [ ] API restarted after config changes
- [ ] Joined Twilio Sandbox on WhatsApp
- [ ] Can send/receive messages

## 🎯 Best Practices

### 1. Use ngrok Web Interface
- Always keep http://localhost:4040 open
- Inspect requests/responses
- Debug signature validation issues

### 2. Monitor Logs Continuously
```bash
# Use tmux or multiple terminals
docker logs -f fitagent-api | grep -E "ERROR|WARNING|Webhook"
```

### 3. Test Incrementally
1. First test: Simple "Hello" message
2. Then test: Trainer registration
3. Then test: Student operations
4. Finally test: Complex flows with media

### 4. Clear Data Between Tests
```bash
# Delete all DynamoDB items
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb delete-table --table-name fitagent-main --region us-east-1

# Restart LocalStack to recreate
docker-compose restart localstack
sleep 30
```

### 5. Save ngrok URL
```bash
# Get current ngrok URL programmatically
curl -s http://localhost:4040/api/tunnels | \
  python -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"
```

## 🔄 Quick Restart Procedure

If something goes wrong:

```bash
# 1. Stop everything
docker-compose down
pkill ngrok

# 2. Start fresh
docker-compose up -d
sleep 10

# 3. Start ngrok
ngrok http 8000

# 4. Update Twilio webhook with new ngrok URL

# 5. Test
# Send "Hello" from WhatsApp
```

## 📱 Testing from Multiple Phones

You can test multi-user scenarios:

1. **Trainer Phone:** Your phone (joined sandbox)
2. **Student Phone:** Friend's phone (also join sandbox)

**Test flow:**
1. Trainer registers: "I want to register as a trainer"
2. Trainer adds student: "Register student Jane, phone +1234567890"
3. Student queries: "What are my sessions?" (from student phone)

## 🚀 Advanced: Production-Like Testing

For more realistic testing:

1. **Use Twilio Phone Number** (not sandbox)
   - Buy a number: ~$1/month
   - Enable WhatsApp on it
   - No "join" message needed
   - More reliable

2. **Use ngrok Paid Plan**
   - Fixed subdomain
   - No need to update webhook URL
   - Better for continuous testing

3. **Deploy to Staging**
   - See TASK_14.3_STAGING_DEPLOYMENT_SUMMARY.md
   - Test with real AWS services
   - More stable than local

## 📚 Next Steps

After successful local testing:

1. **Run Integration Tests:**
   ```bash
   pytest tests/integration/ -v
   ```

2. **Deploy to Staging:**
   ```bash
   ./scripts/deploy_staging.sh
   ```

3. **Test in Staging:**
   - Update Twilio webhook to staging URL
   - Test with real AWS Bedrock
   - Test with real calendar integrations

## 🎉 Summary

**Complete Local Testing with Twilio Sandbox:**

1. ✅ Start services: `docker-compose up -d`
2. ✅ Start ngrok: `ngrok http 8000`
3. ✅ Configure Twilio webhook with ngrok URL
4. ✅ Update .env with Twilio credentials
5. ✅ Restart API: `docker-compose restart api`
6. ✅ Send WhatsApp message
7. ✅ Watch logs: `docker logs -f fitagent-api`
8. ✅ Verify data in DynamoDB

**This is the BEST way to test locally with real WhatsApp integration!** 🚀
