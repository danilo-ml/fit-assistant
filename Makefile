.PHONY: help start stop restart logs test test-unit test-integration test-coverage clean verify setup e2e-twilio format lint type-check

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)FitAgent - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC)"
	@echo "  make start    # Start all services"
	@echo "  make logs     # View logs"
	@echo "  make test     # Run tests"
	@echo ""

# Development
start: ## Start all services (Docker Compose)
	@echo "$(BLUE)Starting FitAgent services...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)Creating .env from .env.example$(NC)"; \
		cp .env.example .env; \
	fi
	@docker-compose up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo ""
	@echo "API: http://localhost:8000"
	@echo "Health: http://localhost:8000/health"
	@echo "LocalStack: http://localhost:4566"
	@echo ""
	@echo "View logs: make logs"

start-sso: ## Start all services with AWS SSO for Bedrock
	@./scripts/start_with_sso.sh

stop: ## Stop all services
	@echo "$(BLUE)Stopping services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

restart: ## Restart all services
	@echo "$(BLUE)Restarting services...$(NC)"
	@docker-compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

logs: ## View logs (Ctrl+C to exit)
	@docker-compose logs -f

clean: ## Stop services and remove volumes (clean slate)
	@echo "$(BLUE)Cleaning up...$(NC)"
	@docker-compose down -v
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Testing
test: ## Run all tests inside container
	@docker-compose exec api pytest

test-unit: ## Run unit tests only
	@docker-compose exec api pytest tests/unit/ -v

test-integration: ## Run integration tests only
	@docker-compose exec api pytest tests/integration/ -v

test-property: ## Run property-based tests only
	@docker-compose exec api pytest tests/property/ -v

test-coverage: ## Run tests with coverage report
	@docker-compose exec api pytest --cov=src --cov-report=html --cov-report=term
	@echo ""
	@echo "$(GREEN)Coverage report: htmlcov/index.html$(NC)"

# Verification
verify: ## Verify setup (check all services are healthy)
	@./scripts/verify_setup.sh

# E2E Testing
e2e-twilio: ## Start E2E testing with Twilio + ngrok
	@./scripts/start_local_with_twilio.sh

# Code Quality (run on host, not in container)
format: ## Format code with black and isort
	@echo "$(BLUE)Formatting code...$(NC)"
	@black src/ tests/
	@isort src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint: ## Lint code with flake8
	@echo "$(BLUE)Linting code...$(NC)"
	@flake8 src/ tests/
	@echo "$(GREEN)✓ Linting passed$(NC)"

type-check: ## Type check with mypy
	@echo "$(BLUE)Type checking...$(NC)"
	@mypy src/
	@echo "$(GREEN)✓ Type checking passed$(NC)"

quality: format lint type-check ## Run all code quality checks

# Setup
setup: ## Initial setup (install pre-commit hooks)
	@echo "$(BLUE)Setting up development environment...$(NC)"
	@pip install pre-commit
	@pre-commit install
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

# Deployment
deploy-staging: ## Deploy to staging environment
	@./scripts/deploy_staging.sh

deploy-production: ## Deploy to production environment
	@./scripts/deploy_production.sh

package: ## Package Lambda functions
	@./scripts/package_lambda.sh
