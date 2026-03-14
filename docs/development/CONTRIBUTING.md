# Contributing to FitAgent

Thank you for your interest in contributing to FitAgent! This guide will help you get started with development.

## Development Setup

### Prerequisites
- Python 3.12+
- Docker and Docker Compose
- AWS CLI (for deployment)
- Git

### Local Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/your-org/fitagent.git
cd fitagent
```

2. Create virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

4. Copy environment template:
```bash
cp .env.example .env
```

5. Start LocalStack:
```bash
docker-compose up -d
```

6. Run tests to verify setup:
```bash
pytest
```

## Development Workflow

### Branch Strategy
- `main`: Production-ready code (protected)
- `dev`: Development branch (default)
- `feature/*`: Feature branches
- `bugfix/*`: Bug fix branches
- `hotfix/*`: Production hotfixes

### Creating a Feature

1. Create feature branch from `dev`:
```bash
git checkout dev
git pull origin dev
git checkout -b feature/your-feature-name
```

2. Make your changes following code standards

3. Write tests for new functionality

4. Run quality checks:
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type check
mypy src/

# Run tests
pytest --cov=src --cov-report=term
```

5. Commit with descriptive message:
```bash
git add .
git commit -m "feat: add session confirmation feature"
```

6. Push and create pull request:
```bash
git push origin feature/your-feature-name
```

## Code Standards

### Python Style Guide
- Follow PEP 8 style guide
- Use Black for formatting (line length: 100)
- Use type hints for all functions
- Write docstrings for public functions

### Naming Conventions
- **Files**: `snake_case.py`
- **Functions**: `snake_case()`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore()`

### Code Structure
```python
"""Module docstring describing purpose."""

# Standard library imports
import json
from datetime import datetime

# Third-party imports
import boto3
from pydantic import BaseModel

# Local imports
from src.models.entities import Trainer
from src.config import settings


def public_function(param: str) -> dict:
    """
    Function description.
    
    Args:
        param: Parameter description
        
    Returns:
        dict: Return value description
        
    Raises:
        ValueError: When validation fails
    """
    # Implementation
    pass
```

## Testing Guidelines

### Test Structure
- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test component interactions
- **Property tests**: Test invariants with Hypothesis

### Writing Tests
```python
import pytest
from src.tools.student_tools import register_student


def test_register_student_success(mock_dynamodb):
    """Test successful student registration."""
    # Arrange
    trainer_id = "test-trainer-id"
    student_data = {
        "name": "John Doe",
        "phone_number": "+1234567890"
    }
    
    # Act
    result = register_student(trainer_id, **student_data)
    
    # Assert
    assert result["success"] is True
    assert "student_id" in result["data"]


def test_register_student_duplicate_phone(mock_dynamodb):
    """Test registration with duplicate phone number."""
    # Test implementation
    pass
```

### Test Coverage
- Minimum coverage: 70%
- Critical paths: 90%+
- Run coverage report:
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Documentation

### Code Documentation
- Write docstrings for all public functions and classes
- Include type hints
- Document exceptions
- Add inline comments for complex logic

### Documentation Files
- Update relevant docs when changing functionality
- Keep README.md up to date
- Document breaking changes in commit messages

## Commit Message Format

Follow conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

### Examples
```
feat(session): add session confirmation workflow

Implement YES/NO confirmation for upcoming sessions.
Sends confirmation request 48h before session.

Closes #123
```

```
fix(calendar): handle OAuth token expiration

Add token refresh logic when calendar sync fails.
Improves error handling for expired tokens.
```

## Pull Request Process

### Before Submitting
1. Ensure all tests pass
2. Update documentation
3. Add tests for new features
4. Run code quality checks
5. Rebase on latest `dev` branch

### PR Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] No new warnings
```

### Review Process
1. Automated checks must pass (CI)
2. At least one approval required
3. No unresolved comments
4. Up to date with target branch

## Local Testing

### Running LocalStack
```bash
# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Testing with Twilio Sandbox
See [Twilio Sandbox Setup](../guides/TWILIO_SANDBOX_SETUP.md)

### Manual Testing
```bash
# Start local API server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Send test webhook
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"From": "whatsapp:+1234567890", "Body": "Hello"}'
```

## Debugging

### Local Debugging
- Use Python debugger (pdb)
- Add breakpoints in IDE
- Check CloudWatch logs in LocalStack

### Common Issues
See [Troubleshooting Guide](TROUBLESHOOTING.md)

## Release Process

### Version Numbering
Follow semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Steps
1. Update version in `src/__version__.py`
2. Update CHANGELOG.md
3. Create release branch: `release/v1.2.3`
4. Test thoroughly in staging
5. Merge to `main` via PR
6. Tag release: `git tag v1.2.3`
7. Deploy to production via CI/CD

## Getting Help

- Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [Architecture Documentation](../architecture/)
- Ask in team chat
- Create GitHub issue for bugs

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow
