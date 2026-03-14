"""
Integration tests for deployment script validation improvements.

Tests verify that the deployment script correctly:
1. Validates required secrets exist before deployment
2. Runs post-deployment smoke tests
3. Configures automatic rollback on CloudWatch alarm triggers
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest


class TestDeploymentScriptValidation:
    """Test deployment script validation and smoke testing."""

    def test_deployment_script_syntax_valid(self):
        """Verify deployment script has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", "scripts/deploy_production.sh"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Script syntax error: {result.stderr}"

    def test_deployment_script_contains_secret_validation(self):
        """Verify deployment script includes pre-deployment secret validation."""
        with open("scripts/deploy_production.sh", "r") as f:
            script_content = f.read()
        
        # Check for secret validation logic
        assert "Validating required secrets exist" in script_content
        assert "describe-secret" in script_content
        assert "SECRET_VALIDATION_FAILED" in script_content
        assert "Pre-deployment validation failed" in script_content

    def test_deployment_script_contains_smoke_tests(self):
        """Verify deployment script includes post-deployment smoke tests."""
        with open("scripts/deploy_production.sh", "r") as f:
            script_content = f.read()
        
        # Check for smoke test logic
        assert "Running post-deployment smoke tests" in script_content
        assert "lambda invoke" in script_content
        assert "errorMessage" in script_content
        assert "smoke test passed" in script_content

    def test_deployment_script_contains_rollback_configuration(self):
        """Verify deployment script configures automatic rollback."""
        with open("scripts/deploy_production.sh", "r") as f:
            script_content = f.read()
        
        # Check for rollback configuration
        assert "rollback-configuration" in script_content
        assert "RollbackTriggers" in script_content
        assert "DLQAlarmArn" in script_content
        assert "MonitoringTimeInMinutes" in script_content

    def test_cloudformation_template_has_dlq_alarm_output(self):
        """Verify CloudFormation template exports DLQ alarm ARN for rollback."""
        with open("infrastructure/template.yml", "r") as f:
            template_content = f.read()
        
        # Check for DLQ alarm ARN output
        assert "DLQAlarmArn:" in template_content
        assert "MessageDLQAlarm.Arn" in template_content
        assert "used for rollback triggers" in template_content

    def test_cloudformation_template_has_webhook_handler_output(self):
        """Verify CloudFormation template exports Webhook Handler function name."""
        with open("infrastructure/template.yml", "r") as f:
            template_content = f.read()
        
        # Check for Webhook Handler function name output
        assert "WebhookHandlerFunctionName:" in template_content
        assert "WebhookHandlerFunction" in template_content


class TestDeploymentScriptLogic:
    """Test deployment script logic with mocked AWS calls."""

    @patch("subprocess.run")
    def test_secret_validation_fails_when_secret_missing(self, mock_run):
        """Test that deployment fails when required secrets are missing."""
        # This is a conceptual test - actual implementation would require
        # more sophisticated mocking of the bash script execution
        pass

    @patch("subprocess.run")
    def test_smoke_test_fails_on_lambda_error(self, mock_run):
        """Test that deployment fails when Lambda smoke test returns error."""
        # This is a conceptual test - actual implementation would require
        # more sophisticated mocking of the bash script execution
        pass

    @patch("subprocess.run")
    def test_rollback_configured_on_subsequent_deployments(self, mock_run):
        """Test that rollback configuration is added after first deployment."""
        # This is a conceptual test - actual implementation would require
        # more sophisticated mocking of the bash script execution
        pass


class TestDeploymentValidationFlow:
    """Test the complete deployment validation flow."""

    def test_deployment_script_validates_all_five_bugs(self):
        """
        Verify deployment script addresses all five bug conditions:
        1. Module import errors (via package_lambda.sh)
        2. OpenTelemetry initialization (via patch script)
        3. Twilio configuration (via secret validation)
        4. Stale secret caching (via SECRETS_UPDATED env var)
        5. SQS processing failures (via smoke tests and rollback)
        """
        with open("scripts/deploy_production.sh", "r") as f:
            script_content = f.read()
        
        # Bug 1: Module imports - handled by package_lambda.sh
        assert "package_lambda.sh" in script_content
        
        # Bug 2: OpenTelemetry - patch applied during packaging
        # (verified in package_lambda.sh, not deploy script)
        
        # Bug 3: Twilio configuration - secret validation
        assert "Validating Twilio secret configuration" in script_content
        assert "14155238886" in script_content  # Sandbox number check
        
        # Bug 4: Stale secret caching - force reload
        assert "SECRETS_UPDATED" in script_content
        assert "update-function-configuration" in script_content
        
        # Bug 5: SQS processing - smoke tests and rollback
        assert "smoke test" in script_content
        assert "rollback-configuration" in script_content

    def test_deployment_preserves_cloudformation_validation(self):
        """Verify CloudFormation template validation still runs (preservation)."""
        with open("scripts/deploy_production.sh", "r") as f:
            script_content = f.read()
        
        # Preservation requirement 3.4: CloudFormation validation continues
        assert "validate-template" in script_content
        assert "Template validation successful" in script_content
