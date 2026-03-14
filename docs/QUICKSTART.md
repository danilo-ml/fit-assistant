# Quick Start Guide

This guide will help you get the FitAgent WhatsApp Assistant up and running locally.

## Prerequisites

- Python 3.12+ installed
- Docker and Docker Compose installed
- Git installed

## Setup Steps

### 1. Start Local Environment

```bash
# Start all services (LocalStack + API)
make start
```

This single command:
- Creates `.env` from `.env.example` if needed
- Starts LocalStack with all AWS services
- Starts the API server
- Initializes DynamoDB tables, S3 buckets, SQS queues, KMS keys

### 2. Verify Setup

```bash
# Check health
curl http://localhost:8000/health

# View logs
make logs

# Verify all services
make verify
```

The API server will be available at:
- **API**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
- **LocalStack**: http://localhost:4566

### 3. Run Tests

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-property

# Run with coverage
make test-coverage
```

## Development Workflow

### Daily Commands

```bash
# Start development environment
make start

# View logs (Ctrl+C to exit)
make logs

# Run tests
make test

# Stop everything
make stop

# Restart after code changes
make restart

# Clean slate (remove volumes)
make clean
```

### Code Quality Checks

Run these on your host machine (requires Python 3.12+):

```bash
# Install dev dependencies (one time)
pip install -r requirements-dev.txt

# Format code
make format

# Lint code
make lint

# Type check
make type-check

# Run all quality checks
make quality
```

### Advanced Docker Commands

```bash
# Rebuild containers after dependency changes
docker-compose build

# Execute commands inside API container
docker-compose exec api bash
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
