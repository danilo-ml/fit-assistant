# Design Document: Test Infrastructure Improvements

## Overview

This design establishes a comprehensive test infrastructure for FitAgent following the test pyramid architecture. The infrastructure addresses 66 failing tests, implements proper test categorization (unit, integration, E2E, property-based), integrates LocalStack for AWS service emulation, and establishes CI/CD testing pipelines.

The design prioritizes fast feedback loops through extensive unit testing (500+ tests), reliable integration testing with LocalStack (50-100 tests), critical E2E scenarios (3-10 tests), and property-based testing for invariant validation. The infrastructure supports both local development and CI/CD environments with consistent behavior.

### Key Design Principles

1. **Test Pyramid Architecture**: Many fast unit tests, fewer integration tests, minimal E2E tests
2. **Isolation and Repeatability**: Tests run independently with clean state between executions
3. **Fast Feedback**: Unit tests complete in <30s, integration in <5min, E2E in <10min
4. **Realistic Testing**: LocalStack provides realistic AWS service behavior without cloud costs
5. **Developer Experience**: Simple commands (make test-unit), clear error messages, comprehensive fixtures

## Architecture

### Test Infrastructure Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CI/CD Pipeline (GitHub Actions)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Lint    │→ │   Type   │→ │  Tests   │→ │ Coverage │   │
│  │ (flake8) │  │  Check   │  │ (pytest) │  │  Report  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Test Execution Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Unit Tests  │  │ Integration  │  │   E2E Tests  │     │
│  │   (500+)     │  │  Tests       │  │    (3-10)    │     │
│  │   <30s       │  │  (50-100)    │  │    <10min    │     │
│  │              │  │   <5min      │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         ↓                  ↓                  ↓             │
│  ┌──────────────────────────────────────────────────┐     │
│  │         Property-Based Tests (Hypothesis)         │     │
│  │              100+ examples per property           │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Test Support Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Fixtures   │  │   Factories  │  │    Mocks     │     │
│  │  (conftest)  │  │  (builders)  │  │  (external)  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  LocalStack  │  │     Moto     │  │   Docker     │     │
│  │  (AWS Svcs)  │  │  (AWS Mock)  │  │  Compose     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Test Categorization Strategy

Tests are organized by scope and execution speed:

1. **Unit Tests** (`tests/unit/`): Test individual functions/classes with mocked dependencies
   - Fast execution (<30s total)
   - No external dependencies
   - Use moto for AWS SDK mocking
   - Run by default in local development

2. **Integration Tests** (`tests/integration/`): Test component interactions with LocalStack
   - Medium execution (<5min total)
   - Real LocalStack services (DynamoDB, S3, SQS)
   - Mock external APIs (Twilio, Calendar, Bedrock)
   - Run in CI and on-demand locally

3. **E2E Tests** (`tests/e2e/`): Test complete user journeys
   - Slow execution (<10min total)
   - Full LocalStack environment
   - Mock all external APIs
   - Run in CI before deployment

4. **Property Tests** (`tests/property/`): Test invariants with generated inputs
   - Variable execution time
   - 100+ examples per property
   - Run in CI and on-demand locally
   - Use Hypothesis for input generation

5. **Contract Tests** (`tests/contract/`): Test Lambda handler schemas
   - Fast execution
   - Validate input/output contracts
   - Catch breaking API changes
   - Run with unit tests

### LocalStack Integration Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Environment                          │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              pytest Test Runner                     │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │Integration│  │   E2E    │  │ Property │        │    │
│  │  │   Tests   │  │  Tests   │  │  Tests   │        │    │
│  │  └─────┬─────┘  └─────┬────┘  └─────┬────┘        │    │
│  └────────┼──────────────┼─────────────┼─────────────┘    │
│           │              │             │                   │
│           └──────────────┴─────────────┘                   │
│                          ↓                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │         LocalStack Client Fixtures                  │    │
│  │  (dynamodb_localstack, s3_localstack, etc.)        │    │
│  └────────────────────────────────────────────────────┘    │
│                          ↓                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  LocalStack Container                        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ DynamoDB │  │    S3    │  │   SQS    │  │  Lambda  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │EventBridge│  │   KMS    │  │ Secrets  │                 │
│  └──────────┘  └──────────┘  │  Manager │                 │
│                               └──────────┘                 │
│                                                              │
│  Endpoint: http://localhost:4566                            │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Test Fixture System

#### 1.1 Entity Factories (`tests/fixtures/factories.py`)

Provides builder pattern for creating test entities with sensible defaults:

```python
class TrainerFactory:
    """Factory for creating Trainer test entities."""
    
    @staticmethod
    def create(
        trainer_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Trainer:
        """Create a Trainer with defaults."""
        pass

class StudentFactory:
    """Factory for creating Student test entities."""
    
    @staticmethod
    def create(
        student_id: Optional[str] = None,
        trainer_id: str = None,
        phone_number: Optional[str] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Student:
        """Create a Student with defaults."""
        pass

class SessionFactory:
    """Factory for creating Session test entities."""
    
    @staticmethod
    def create(
        session_id: Optional[str] = None,
        trainer_id: str = None,
        student_id: str = None,
        session_datetime: Optional[datetime] = None,
        **kwargs
    ) -> Session:
        """Create a Session with defaults."""
        pass

class PaymentFactory:
    """Factory for creating Payment test entities."""
    
    @staticmethod
    def create(
        payment_id: Optional[str] = None,
        trainer_id: str = None,
        student_id: str = None,
        amount: Optional[Decimal] = None,
        **kwargs
    ) -> Payment:
        """Create a Payment with defaults."""
        pass
```

#### 1.2 AWS Client Fixtures (`tests/conftest.py`)

Provides both moto-based (unit tests) and LocalStack-based (integration/E2E) AWS clients:

```python
# Moto-based fixtures for unit tests
@pytest.fixture
def dynamodb_client() -> boto3.client:
    """Mocked DynamoDB client using moto."""
    pass

@pytest.fixture
def s3_client() -> boto3.client:
    """Mocked S3 client using moto."""
    pass

# LocalStack-based fixtures for integration/E2E tests
@pytest.fixture(scope="session")
def localstack_endpoint() -> str:
    """LocalStack endpoint URL."""
    return os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")

@pytest.fixture
def dynamodb_localstack(localstack_endpoint) -> boto3.client:
    """Real DynamoDB client connected to LocalStack."""
    pass

@pytest.fixture
def s3_localstack(localstack_endpoint) -> boto3.client:
    """Real S3 client connected to LocalStack."""
    pass

@pytest.fixture
def sqs_localstack(localstack_endpoint) -> boto3.client:
    """Real SQS client connected to LocalStack."""
    pass

@pytest.fixture
def lambda_localstack(localstack_endpoint) -> boto3.client:
    """Real Lambda client connected to LocalStack."""
    pass

@pytest.fixture
def events_localstack(localstack_endpoint) -> boto3.client:
    """Real EventBridge client connected to LocalStack."""
    pass
```

#### 1.3 External API Mocks (`tests/fixtures/mocks.py`)

Provides mock implementations for external services:

```python
class MockTwilioClient:
    """Mock Twilio client for testing."""
    
    def __init__(self):
        self.messages_sent = []
    
    def send_message(self, to: str, from_: str, body: str) -> dict:
        """Mock message sending."""
        pass

class MockBedrockClient:
    """Mock Bedrock client for testing."""
    
    def __init__(self, responses: Optional[List[str]] = None):
        self.responses = responses or []
        self.call_count = 0
    
    def invoke_model(self, modelId: str, body: dict) -> dict:
        """Mock model invocation."""
        pass

class MockCalendarClient:
    """Mock Google Calendar/Outlook client for testing."""
    
    def __init__(self):
        self.events = []
    
    def create_event(self, event: dict) -> dict:
        """Mock event creation."""
        pass
    
    def list_events(self, start: datetime, end: datetime) -> List[dict]:
        """Mock event listing."""
        pass

@pytest.fixture
def mock_twilio() -> MockTwilioClient:
    """Provide mocked Twilio client."""
    return MockTwilioClient()

@pytest.fixture
def mock_bedrock() -> MockBedrockClient:
    """Provide mocked Bedrock client."""
    return MockBedrockClient()

@pytest.fixture
def mock_calendar() -> MockCalendarClient:
    """Provide mocked Calendar client."""
    return MockCalendarClient()
```

### 2. Test Utilities

#### 2.1 LocalStack Helpers (`tests/utils/localstack_helpers.py`)

Utilities for LocalStack management and health checking:

```python
def wait_for_localstack(
    endpoint: str = "http://localhost:4566",
    timeout: int = 30,
    services: Optional[List[str]] = None
) -> bool:
    """Wait for LocalStack services to be ready."""
    pass

def initialize_localstack_resources(
    dynamodb_client,
    s3_client,
    sqs_client
) -> None:
    """Initialize LocalStack with required resources."""
    pass

def cleanup_localstack_resources(
    dynamodb_client,
    s3_client,
    sqs_client
) -> None:
    """Clean up LocalStack resources after tests."""
    pass

def get_localstack_logs() -> str:
    """Retrieve LocalStack container logs for debugging."""
    pass
```

#### 2.2 Test Data Helpers (`tests/utils/test_data.py`)

Utilities for generating test data:

```python
def generate_phone_number(country_code: str = "+55") -> str:
    """Generate a valid test phone number."""
    pass

def generate_future_datetime(days_ahead: int = 1) -> datetime:
    """Generate a future datetime for session scheduling."""
    pass

def generate_receipt_image() -> bytes:
    """Generate a test receipt image."""
    pass

def create_test_conversation_state(
    phone_number: str,
    role: str = "trainer",
    **kwargs
) -> ConversationState:
    """Create a test conversation state."""
    pass
```

#### 2.3 Assertion Helpers (`tests/utils/assertions.py`)

Custom assertions for common test patterns:

```python
def assert_dynamodb_item_exists(
    client,
    table_name: str,
    pk: str,
    sk: str
) -> dict:
    """Assert item exists in DynamoDB and return it."""
    pass

def assert_s3_object_exists(
    client,
    bucket: str,
    key: str
) -> bool:
    """Assert object exists in S3."""
    pass

def assert_sqs_message_sent(
    client,
    queue_url: str,
    expected_body: dict,
    timeout: int = 5
) -> dict:
    """Assert message was sent to SQS queue."""
    pass

def assert_portuguese_message(message: str) -> None:
    """Assert message is in Portuguese."""
    pass
```

### 3. Contract Test Framework

#### 3.1 Handler Contract Schemas (`tests/contract/schemas.py`)

Defines expected input/output schemas for Lambda handlers:

```python
from pydantic import BaseModel
from typing import Dict, Any, Optional

class WebhookHandlerInput(BaseModel):
    """Expected input schema for webhook_handler."""
    body: str
    headers: Dict[str, str]
    httpMethod: str
    path: str

class WebhookHandlerOutput(BaseModel):
    """Expected output schema for webhook_handler."""
    statusCode: int
    body: str
    headers: Optional[Dict[str, str]] = None

class MessageProcessorInput(BaseModel):
    """Expected input schema for message_processor."""
    Records: list

class MessageProcessorOutput(BaseModel):
    """Expected output schema for message_processor."""
    batchItemFailures: list

# Similar schemas for other handlers...
```

#### 3.2 Contract Test Runner (`tests/contract/test_handler_contracts.py`)

Tests that validate handler contracts:

```python
def test_webhook_handler_contract(mock_twilio, mock_bedrock):
    """Validate webhook_handler input/output contract."""
    pass

def test_message_processor_contract(dynamodb_client, mock_bedrock):
    """Validate message_processor input/output contract."""
    pass

# Similar tests for other handlers...
```

### 4. E2E Test Framework

#### 4.1 E2E Test Base Class (`tests/e2e/base.py`)

Base class for E2E tests with common setup:

```python
class E2ETestBase:
    """Base class for E2E tests."""
    
    @pytest.fixture(autouse=True)
    def setup_e2e_environment(
        self,
        dynamodb_localstack,
        s3_localstack,
        sqs_localstack,
        lambda_localstack,
        events_localstack,
        mock_twilio,
        mock_bedrock,
        mock_calendar
    ):
        """Set up complete E2E test environment."""
        self.dynamodb = dynamodb_localstack
        self.s3 = s3_localstack
        self.sqs = sqs_localstack
        self.lambda_client = lambda_localstack
        self.events = events_localstack
        self.twilio = mock_twilio
        self.bedrock = mock_bedrock
        self.calendar = mock_calendar
        
        # Initialize resources
        initialize_localstack_resources(
            self.dynamodb,
            self.s3,
            self.sqs
        )
        
        yield
        
        # Cleanup
        cleanup_localstack_resources(
            self.dynamodb,
            self.s3,
            self.sqs
        )
    
    def send_whatsapp_message(
        self,
        from_number: str,
        body: str
    ) -> dict:
        """Simulate incoming WhatsApp message."""
        pass
    
    def wait_for_sqs_processing(
        self,
        queue_url: str,
        timeout: int = 10
    ) -> None:
        """Wait for SQS message processing."""
        pass
    
    def trigger_eventbridge_rule(
        self,
        rule_name: str,
        event: dict
    ) -> None:
        """Trigger EventBridge rule."""
        pass
```

#### 4.2 E2E Test Scenarios (`tests/e2e/`)

Individual E2E test files for critical journeys:

- `test_trainer_onboarding_e2e.py`: Complete trainer onboarding flow
- `test_student_registration_e2e.py`: Student registration and session scheduling
- `test_payment_tracking_e2e.py`: Payment receipt submission and tracking
- `test_calendar_integration_e2e.py`: Calendar sync with Google Calendar
- `test_session_reminders_e2e.py`: Automated session reminders

### 5. CI/CD Integration

#### 5.1 GitHub Actions Workflow (`
.github/workflows/test.yml`)

Enhanced test workflow with LocalStack integration:

```yaml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  AWS_REGION: us-east-1
  PYTHON_VERSION: '3.12'
  LOCALSTACK_VERSION: '3.0'

jobs:
  lint-and-type-check:
    name: Lint and Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt
      - name: Run flake8
        run: flake8 src/ tests/
      - name: Run mypy
        run: mypy src/ --ignore-missing-imports

  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v -m unit \
            --cov=src --cov-report=xml --cov-report=term \
            --durations=10
      - name: Check coverage thresholds
        run: |
          coverage report --fail-under=70
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unit

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      localstack:
        image: localstack/localstack:${{ env.LOCALSTACK_VERSION }}
        ports:
          - 4566:4566
        env:
          SERVICES: dynamodb,s3,sqs,lambda,events,kms,secretsmanager
          DEBUG: 1
          DATA_DIR: /tmp/localstack/data
        options: >-
          --health-cmd "awslocal dynamodb list-tables"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install awscli-local
      - name: Wait for LocalStack
        run: |
          timeout 60 bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "\"dynamodb\": \"available\""; do sleep 2; done'
      - name: Initialize LocalStack resources
        run: |
          export AWS_ENDPOINT_URL=http://localhost:4566
          bash localstack-init/01-setup.sh
      - name: Run integration tests
        env:
          AWS_ENDPOINT_URL: http://localhost:4566
          AWS_ACCESS_KEY_ID: test
          AWS_SECRET_ACCESS_KEY: test
          AWS_DEFAULT_REGION: us-east-1
        run: |
          pytest tests/integration/ -v -m integration \
            --durations=10
      - name: Upload LocalStack logs on failure
        if: failure()
        run: |
          docker logs $(docker ps -q --filter ancestor=localstack/localstack:${{ env.LOCALSTACK_VERSION }}) > localstack.log
          cat localstack.log

  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    services:
      localstack:
        image: localstack/localstack:${{ env.LOCALSTACK_VERSION }}
        ports:
          - 4566:4566
        env:
          SERVICES: dynamodb,s3,sqs,lambda,events,kms,secretsmanager
          DEBUG: 1
          LAMBDA_EXECUTOR: docker
        options: >-
          --health-cmd "awslocal dynamodb list-tables"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
          pip install awscli-local
      - name: Wait for LocalStack
        run: |
          timeout 60 bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "\"dynamodb\": \"available\""; do sleep 2; done'
      - name: Initialize LocalStack resources
        run: |
          export AWS_ENDPOINT_URL=http://localhost:4566
          bash localstack-init/01-setup.sh
      - name: Deploy Lambda functions to LocalStack
        env:
          AWS_ENDPOINT_URL: http://localhost:4566
        run: |
          bash tests/e2e/deploy_lambdas.sh
      - name: Run E2E tests
        env:
          AWS_ENDPOINT_URL: http://localhost:4566
          AWS_ACCESS_KEY_ID: test
          AWS_SECRET_ACCESS_KEY: test
          AWS_DEFAULT_REGION: us-east-1
        run: |
          pytest tests/e2e/ -v -m e2e \
            --durations=10

  property-tests:
    name: Property-Based Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run property tests
        run: |
          pytest tests/property/ -v -m property \
            --hypothesis-show-statistics \
            --durations=10

  contract-tests:
    name: Contract Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
          cache: 'pip'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run contract tests
        run: |
          pytest tests/contract/ -v -m contract \
            --durations=10
```

#### 5.2 Makefile Commands

Simplified test execution commands:

```makefile
.PHONY: test test-unit test-integration test-e2e test-property test-contract test-all

test: test-unit
	@echo "✓ Unit tests passed"

test-unit:
	pytest tests/unit/ -v -m unit --cov=src --cov-report=term

test-integration:
	@echo "Starting LocalStack..."
	docker-compose up -d localstack
	@echo "Waiting for LocalStack..."
	@bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "\"dynamodb\": \"available\""; do sleep 2; done'
	@echo "Initializing resources..."
	AWS_ENDPOINT_URL=http://localhost:4566 bash localstack-init/01-setup.sh
	@echo "Running integration tests..."
	AWS_ENDPOINT_URL=http://localhost:4566 pytest tests/integration/ -v -m integration
	@echo "Stopping LocalStack..."
	docker-compose down

test-e2e:
	@echo "Starting LocalStack..."
	docker-compose up -d localstack
	@echo "Waiting for LocalStack..."
	@bash -c 'until curl -s http://localhost:4566/_localstack/health | grep -q "\"dynamodb\": \"available\""; do sleep 2; done'
	@echo "Initializing resources..."
	AWS_ENDPOINT_URL=http://localhost:4566 bash localstack-init/01-setup.sh
	@echo "Deploying Lambda functions..."
	AWS_ENDPOINT_URL=http://localhost:4566 bash tests/e2e/deploy_lambdas.sh
	@echo "Running E2E tests..."
	AWS_ENDPOINT_URL=http://localhost:4566 pytest tests/e2e/ -v -m e2e
	@echo "Stopping LocalStack..."
	docker-compose down

test-property:
	pytest tests/property/ -v -m property --hypothesis-show-statistics

test-contract:
	pytest tests/contract/ -v -m contract

test-all:
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) test-e2e
	$(MAKE) test-property
	$(MAKE) test-contract

test-coverage:
	pytest tests/unit/ tests/integration/ -v \
		--cov=src --cov-report=html --cov-report=term \
		--cov-fail-under=70
	@echo "Coverage report generated in htmlcov/index.html"
```

## Data Models

### Test Entity Models

Test entities mirror production entities but with builder patterns for easy construction:

```python
@dataclass
class TestTrainer:
    """Test representation of Trainer entity."""
    trainer_id: str
    phone_number: str
    name: str
    email: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": f"TRAINER#{self.trainer_id}",
            "SK": "METADATA",
            "entity_type": "trainer",
            "phone_number": self.phone_number,
            "name": self.name,
            "email": self.email,
            "created_at": self.created_at.isoformat()
        }

@dataclass
class TestStudent:
    """Test representation of Student entity."""
    student_id: str
    trainer_id: str
    phone_number: str
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": f"TRAINER#{self.trainer_id}",
            "SK": f"STUDENT#{self.student_id}",
            "entity_type": "student",
            "phone_number": self.phone_number,
            "name": self.name,
            "student_id": self.student_id,
            "trainer_id": self.trainer_id,
            "created_at": self.created_at.isoformat()
        }

@dataclass
class TestSession:
    """Test representation of Session entity."""
    session_id: str
    trainer_id: str
    student_id: str
    session_datetime: datetime
    duration_minutes: int = 60
    status: str = "scheduled"
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": f"TRAINER#{self.trainer_id}",
            "SK": f"SESSION#{self.session_id}",
            "entity_type": "session",
            "session_id": self.session_id,
            "trainer_id": self.trainer_id,
            "student_id": self.student_id,
            "session_datetime": self.session_datetime.isoformat(),
            "duration_minutes": self.duration_minutes,
            "status": self.status
        }

@dataclass
class TestPayment:
    """Test representation of Payment entity."""
    payment_id: str
    trainer_id: str
    student_id: str
    amount: Decimal
    payment_status: str = "pending"
    receipt_url: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format."""
        return {
            "PK": f"TRAINER#{self.trainer_id}",
            "SK": f"PAYMENT#{self.payment_id}",
            "entity_type": "payment",
            "payment_id": self.payment_id,
            "trainer_id": self.trainer_id,
            "student_id": self.student_id,
            "amount": str(self.amount),
            "payment_status": self.payment_status,
            "receipt_url": self.receipt_url,
            "created_at": self.created_at.isoformat()
        }
```

### Test Configuration Model

```python
@dataclass
class TestConfig:
    """Configuration for test execution."""
    use_localstack: bool = False
    localstack_endpoint: str = "http://localhost:4566"
    aws_region: str = "us-east-1"
    dynamodb_table: str = "fitagent-main"
    s3_bucket: str = "fitagent-receipts-local"
    sqs_queue_url: str = "http://localhost:4566/000000000000/fitagent-messages.fifo"
    mock_external_apis: bool = True
    hypothesis_max_examples: int = 100
    test_timeout_seconds: int = 30
    
    @classmethod
    def from_environment(cls) -> "TestConfig":
        """Create config from environment variables."""
        return cls(
            use_localstack=os.getenv("USE_LOCALSTACK", "false").lower() == "true",
            localstack_endpoint=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            dynamodb_table=os.getenv("DYNAMODB_TABLE", "fitagent-main"),
            s3_bucket=os.getenv("S3_BUCKET", "fitagent-receipts-local"),
            sqs_queue_url=os.getenv("SQS_QUEUE_URL", "http://localhost:4566/000000000000/fitagent-messages.fifo")
        )
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Contract Test Failure Detection

*For any* Lambda handler, when the handler's input or output schema changes in a way that violates the established contract, the corresponding contract test shall fail and report the schema violation.

**Validates: Requirements 4.8**

### Property 2: Test Fixture Data Isolation

*For any* test execution using test fixtures, data created by one test shall not be visible to or affect any other test, regardless of execution order or parallelization.

**Validates: Requirements 6.9**

## Error Handling

### Test Execution Errors

1. **LocalStack Connection Failures**
   - Detection: Health check timeout or connection refused
   - Handling: Retry with exponential backoff (3 attempts)
   - Fallback: Fail fast with clear error message and LocalStack logs
   - Recovery: Restart LocalStack container and reinitialize resources

2. **Test Timeout Errors**
   - Detection: Test exceeds configured timeout (30s unit, 5min integration, 10min E2E)
   - Handling: Terminate test execution and capture state
   - Reporting: Include partial execution logs and resource states
   - Prevention: Set appropriate timeouts per test category

3. **Fixture Setup Failures**
   - Detection: Exception during fixture initialization
   - Handling: Skip dependent tests with clear error message
   - Cleanup: Ensure partial resources are cleaned up
   - Reporting: Log fixture name and failure reason

4. **Resource Cleanup Failures**
   - Detection: Exception during teardown
   - Handling: Log warning but don't fail test
   - Mitigation: Use session-scoped cleanup as backup
   - Monitoring: Track cleanup failures in CI metrics

### Test Data Errors

1. **Invalid Test Entity Creation**
   - Detection: Validation error in factory methods
   - Handling: Raise descriptive ValueError with field details
   - Prevention: Use Pydantic validation in test models
   - Documentation: Include valid examples in factory docstrings

2. **DynamoDB Key Conflicts**
   - Detection: ConditionalCheckFailedException
   - Handling: Generate new unique ID and retry
   - Prevention: Use UUID4 for all test entity IDs
   - Isolation: Clear tables between test runs

3. **S3 Upload Failures**
   - Detection: ClientError from boto3
   - Handling: Retry with exponential backoff (3 attempts)
   - Fallback: Skip S3-dependent assertions with warning
   - Verification: Check bucket exists before upload

### CI/CD Pipeline Errors

1. **Coverage Threshold Failures**
   - Detection: Coverage below configured threshold (70% overall)
   - Handling: Fail build with coverage report
   - Reporting: Identify specific uncovered files and lines
   - Action: Block merge until coverage improves

2. **Flaky Test Detection**
   - Detection: Test passes/fails inconsistently across runs
   - Handling: Mark test with @pytest.mark.flaky
   - Monitoring: Track flaky test rate in CI metrics
   - Action: Investigate and fix root cause

3. **LocalStack Service Unavailability**
   - Detection: Service not in "available" state after health check
   - Handling: Retry health check with timeout
   - Fallback: Fail build with LocalStack logs
   - Recovery: Cache LocalStack image to reduce startup issues

## Testing Strategy

### Test Pyramid Distribution

The test suite follows the test pyramid with this distribution:

- **Unit Tests**: 500+ tests (75% of suite)
  - Fast execution (<30s total)
  - High isolation with mocked dependencies
  - Focus: Individual functions, classes, business logic
  - Coverage target: 80%+ for services, 90%+ for tools

- **Integration Tests**: 50-100 tests (15% of suite)
  - Medium execution (<5min total)
  - Real LocalStack services
  - Focus: Component interactions, data flow, AWS integrations
  - Coverage target: Critical integration paths

- **E2E Tests**: 3-10 tests (2% of suite)
  - Slow execution (<10min total)
  - Full system simulation
  - Focus: Critical user journeys end-to-end
  - Coverage target: Happy paths for core features

- **Property Tests**: 20-30 tests (5% of suite)
  - Variable execution (depends on complexity)
  - 100+ generated examples per property
  - Focus: Invariants, edge cases, round-trip properties
  - Coverage target: Critical business rules

- **Contract Tests**: 7 tests (1% of suite)
  - Fast execution
  - Schema validation
  - Focus: Lambda handler interfaces
  - Coverage target: All Lambda handlers

### Test Execution Strategy

**Local Development**:
```bash
# Default: Run only unit tests (fast feedback)
make test

# Run specific category
make test-integration
make test-e2e
make test-property

# Run all tests before committing
make test-all
```

**CI/CD Pipeline**:
1. Lint and type check (parallel)
2. Unit tests with coverage (parallel)
3. Contract tests (parallel)
4. Integration tests with LocalStack (sequential)
5. Property tests (sequential)
6. E2E tests with LocalStack (sequential)
7. Coverage validation (fail if <70%)

**Test Isolation Strategy**:
- Each test gets fresh fixtures (function scope)
- DynamoDB tables cleared between integration tests
- S3 buckets use unique prefixes per test
- SQS queues purged before each test
- No shared state between tests

**Mocking Strategy**:
- Unit tests: Mock all external dependencies (AWS, Twilio, Bedrock, Calendar)
- Integration tests: Real LocalStack AWS services, mock external APIs
- E2E tests: Real LocalStack AWS services, mock external APIs
- Property tests: Mix of mocked and real depending on test focus

### Property-Based Testing Configuration

Using Hypothesis for property-based testing:

```python
# pytest.ini configuration
[pytest]
markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (LocalStack required)
    e2e: End-to-end tests (full system)
    property: Property-based tests (Hypothesis)
    contract: Contract tests (schema validation)
    slow: Slow tests (>5s execution)
    flaky: Known flaky tests (retry enabled)

# Hypothesis settings
hypothesis_profile = default

[hypothesis]
max_examples = 100
deadline = 5000
derandomize = false
print_blob = true
```

Property test example:

```python
from hypothesis import given, strategies as st
import pytest

@pytest.mark.property
@given(
    trainer_id=st.uuids(),
    session_datetime=st.datetimes(
        min_value=datetime(2024, 1, 1),
        max_value=datetime(2025, 12, 31)
    ),
    duration_minutes=st.integers(min_value=30, max_value=180)
)
def test_session_scheduling_no_overlap_property(
    trainer_id,
    session_datetime,
    duration_minutes,
    dynamodb_client
):
    """
    Property: For any trainer and session time, scheduling a session
    should prevent overlapping sessions from being scheduled.
    
    Feature: test-infrastructure-improvements, Property 1
    """
    # Test implementation
    pass
```

### Coverage Strategy

**Coverage Targets**:
- Overall: 70% minimum
- src/services/: 80% minimum
- src/tools/: 90% minimum
- src/handlers/: 60% minimum
- src/models/: 80% minimum
- src/utils/: 75% minimum

**Coverage Exclusions**:
- Test files (tests/)
- Configuration files (config.py)
- Main entry points (main.py, local_sqs_poller.py)
- Type stubs and protocols
- Defensive error handling (should-never-happen cases)

**Coverage Enforcement**:
```python
# .coveragerc
[run]
source = src
omit =
    */tests/*
    */conftest.py
    */__pycache__/*
    */site-packages/*
    src/main.py
    src/local_sqs_poller.py

[report]
precision = 2
show_missing = true
skip_covered = false
fail_under = 70

[html]
directory = htmlcov
```

### Test Categorization

Tests are marked using pytest markers:

```python
# Unit test example
@pytest.mark.unit
def test_phone_number_validation():
    """Test phone number validation logic."""
    pass

# Integration test example
@pytest.mark.integration
def test_dynamodb_session_storage(dynamodb_localstack):
    """Test session storage in DynamoDB."""
    pass

# E2E test example
@pytest.mark.e2e
@pytest.mark.slow
def test_trainer_onboarding_flow(e2e_environment):
    """Test complete trainer onboarding journey."""
    pass

# Property test example
@pytest.mark.property
@given(phone_number=st.text())
def test_phone_validation_property(phone_number):
    """Test phone validation invariants."""
    pass

# Contract test example
@pytest.mark.contract
def test_webhook_handler_contract():
    """Test webhook handler input/output contract."""
    pass
```

### Fixing Failing Tests Strategy

**Phase 1: LocalStack Connection Issues**
1. Update fixtures to properly detect LocalStack vs moto usage
2. Add health checks before test execution
3. Implement retry logic for transient connection failures
4. Add clear error messages for connection failures

**Phase 2: Language Assertion Fixes**
1. Audit all message assertions in tests
2. Update assertions to expect Portuguese responses
3. Add helper function `assert_portuguese_message()`
4. Document language expectations in test docstrings

**Phase 3: Mock Object Fixes**
1. Replace dict mocks with proper ConversationState objects
2. Update conversation_state fixtures to return real objects
3. Ensure all conversation state tests use proper types
4. Add type hints to catch future mock misuse

**Phase 4: Property Test Bug Documentation**
1. Review property test failures
2. Document bugs as GitHub issues
3. Mark tests with @pytest.mark.xfail(reason="Known bug #123")
4. Link to bug tracking in test docstrings

**Phase 5: Calendar Integration Error Handling**
1. Add error case tests for calendar API failures
2. Test OAuth token expiration scenarios
3. Test calendar service unavailability
4. Verify graceful degradation

**Phase 6: Message Processor Batch Fixes**
1. Review batch processing logic
2. Add tests for partial batch failures
3. Test SQS batch item failure reporting
4. Verify DLQ handling

### Test Documentation Strategy

Documentation will be provided in:

1. **README.md** (tests/): Overview of test structure and quick start
2. **TESTING_GUIDE.md**: Comprehensive testing guide covering:
   - Writing unit tests
   - Writing integration tests with LocalStack
   - Writing E2E tests
   - Writing property-based tests
   - Using test fixtures
   - Running tests locally
   - Debugging failing tests
   - Best practices and patterns

3. **Inline Documentation**: Each test file includes:
   - Module docstring explaining test scope
   - Test function docstrings with clear descriptions
   - Comments for complex test setup
   - Links to requirements being validated

4. **Example Tests**: Reference implementations in:
   - tests/examples/example_unit_test.py
   - tests/examples/example_integration_test.py
   - tests/examples/example_e2e_test.py
   - tests/examples/example_property_test.py

This design provides a comprehensive, maintainable test infrastructure that supports rapid development while ensuring system correctness through multiple testing strategies.
