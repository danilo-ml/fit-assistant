# Quick Start Guide

This guide will help you get the FitAgent WhatsApp Assistant up and running locally.

## Prerequisites

- Python 3.12+ installed
- Docker and Docker Compose installed
- Git installed

## Setup Steps

### 1. Install Python Dependencies

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials (optional for local development)
# For local testing, the default values work with LocalStack
```

### 3. Start LocalStack Services

```bash
# Start all services (LocalStack + API)
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify LocalStack is ready
docker-compose logs localstack | grep "Ready"
```

This will automatically:
- Start LocalStack with DynamoDB, S3, SQS, Lambda, API Gateway, EventBridge, KMS, Secrets Manager
- Initialize DynamoDB table with GSIs
- Create S3 bucket with encryption
- Set up SQS queues with dead-letter queues
- Create KMS key for OAuth encryption
- Create placeholder secrets

### 4. Run Tests

```bash
# Run all tests
pytest

# Run specific test types
pytest tests/unit/ -v          # Unit tests only
pytest tests/integration/ -v   # Integration tests only
pytest tests/property/ -v      # Property-based tests only

# Run with coverage (requires pytest-cov)
pip install pytest-cov
pytest --cov=src --cov-report=html --cov-report=term
```

### 5. Access the API

The API server will be available at:
- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **LocalStack**: http://localhost:4566

### 6. Verify LocalStack Resources

```bash
# Install awscli-local
pip install awscli-local

# List DynamoDB tables
awslocal dynamodb list-tables

# List S3 buckets
awslocal s3 ls

# List SQS queues
awslocal sqs list-queues
```

## Development Workflow

### Running Tests During Development

```bash
# Run tests in watch mode (requires pytest-watch)
pip install pytest-watch
ptw

# Run specific test file
pytest tests/unit/test_config.py -v

# Run tests matching pattern
pytest -k "test_settings" -v
```

### Code Quality Checks

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type check
mypy src/
```

### Working with LocalStack

```bash
# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Restart services
docker-compose restart

# View logs
docker-compose logs -f localstack
docker-compose logs -f api
```

## Project Structure Overview

```
.
├── src/                    # Source code
│   ├── handlers/          # Lambda entry points
│   ├── services/          # Business logic
│   ├── tools/             # AI agent tools
│   ├── models/            # Data models
│   ├── utils/             # Utilities
│   └── config.py          # Configuration
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── property/         # Property-based tests
├── infrastructure/        # CloudFormation templates
├── localstack-init/      # LocalStack setup scripts
└── docker-compose.yml    # Local environment
```

## Next Steps

1. **Implement Data Models** (Task 2): Create Pydantic models for entities
2. **Add Validation Utilities** (Task 3): Phone number validation, input sanitization
3. **Build Message Processing** (Task 7-8): Twilio integration and message routing
4. **Develop AI Agent Tools** (Task 10-12): Student, session, and payment management

## Troubleshooting

### LocalStack Not Starting

```bash
# Check Docker is running
docker ps

# Check logs for errors
docker-compose logs localstack

# Restart with clean state
docker-compose down -v
docker-compose up -d
```

### Tests Failing

```bash
# Ensure dependencies are installed
pip install -r requirements-dev.txt

# Check Python version
python3 --version  # Should be 3.12+

# Run tests with verbose output
pytest -vv --tb=long
```

### Import Errors

```bash
# Ensure you're in the project root
pwd

# Activate virtual environment
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements-dev.txt
```

## Additional Resources

- [README.md](README.md) - Full project documentation
- [requirements.txt](requirements.txt) - Production dependencies
- [requirements-dev.txt](requirements-dev.txt) - Development dependencies
- [.env.example](.env.example) - Environment variable template

## Support

For issues or questions, please refer to the main README.md or open a GitHub issue.
