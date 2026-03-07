# FitAgent Local Development - Quick Start

## 🚀 Start Services

```bash
# Start all services
docker-compose up -d

# Check status
docker ps --filter "name=fitagent"

# View logs
docker logs -f fitagent-api
```

## ✅ Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# Check LocalStack
curl http://localhost:4566/_localstack/health

# Check DynamoDB table
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb list-tables --region us-east-1
```

## 🧪 Test WhatsApp Messaging

### Quick Test (Python)
```bash
python scripts/test_whatsapp_local.py
```

### Quick Test (Bash)
```bash
./scripts/test_whatsapp_local.sh
```

### Manual Test (cURL)
```bash
curl -X POST http://localhost:8000/test/process-message \
  -d "phone_number=+1234567890" \
  -d "message=Hello, I want to register as a trainer"
```

### Interactive Test (Browser)
Open http://localhost:8000/docs and use the Swagger UI

## 📊 View Data

```bash
# Scan all DynamoDB items
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test \
  aws --endpoint-url=http://localhost:4566 \
  dynamodb scan --table-name fitagent-main --region us-east-1
```

## 🧹 Clean Up

```bash
# Stop services
docker-compose down

# Stop and remove data
docker-compose down -v
```

## 📚 Full Documentation

- **Testing Guide**: [LOCAL_TESTING_GUIDE.md](LOCAL_TESTING_GUIDE.md)
- **API Docs**: http://localhost:8000/docs
- **README**: [README.md](README.md)

## 🔧 Common Commands

```bash
# Restart API only
docker-compose restart api

# Rebuild after code changes
docker-compose up -d --build

# View API logs
docker logs -f fitagent-api

# Run tests
pytest --cov=src --cov-report=term

# Format code
black src/

# Lint code
flake8 src/
```

## 🐛 Troubleshooting

**API not responding?**
```bash
docker logs fitagent-api --tail 50
docker-compose restart api
```

**LocalStack issues?**
```bash
docker logs fitagent-localstack --tail 50
docker-compose restart localstack
```

**Need fresh start?**
```bash
docker-compose down -v
docker-compose up -d --build
```
