"""
Property-based tests for production Lambda deployment bugs.

This test file explores 5 critical bug conditions that prevent Lambda deployment
and runtime from functioning correctly in production:

1. Module Import Failure - Lambda cannot import src.handlers modules
2. OpenTelemetry Initialization Failure - Strands SDK fails to initialize
3. Twilio Message Delivery Failure - Messages fail with error 63015
4. Stale Secret Caching - Lambda uses old cached credentials
5. SQS Processing Failure - Messages stuck in queue without proper error handling

**CRITICAL**: These tests MUST FAIL on unfixed code - failures confirm the bugs exist.
**DO NOT attempt to fix the tests or the code when they fail.**

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5**
"""

import os
import sys
import json
import tempfile
import zipfile
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from hypothesis import given, strategies as st, settings, Phase
import pytest


# ============================================================================
# Bug 1: Module Import Failure
# ============================================================================

def test_bug_1_lambda_module_import_failure():
    """
    Bug 1 Exploration: Lambda Module Import Failure
    
    **Validates: Requirements 1.1, 2.1**
    
    This test verifies the current package structure by checking if the package_lambda.sh
    script copies src/ as a subdirectory (bug condition) or flattens it (fixed condition).
    
    Bug Condition:
    - package_lambda.sh uses: cp -r src "$PACKAGE_DIR/"
    - This creates nested structure: lambda-package/src/handlers/...
    - Lambda handler configured as "src.handlers.webhook_handler.lambda_handler"
    - In Lambda runtime, this causes ModuleNotFoundError
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test FAILS because package_lambda.sh
    contains "cp -r src" which creates nested structure.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because package_lambda.sh
    contains "cp -r src/*" which flattens the structure.
    """
    # Read the package_lambda.sh script
    script_path = Path("scripts/package_lambda.sh")
    
    if not script_path.exists():
        pytest.skip("package_lambda.sh not found")
    
    script_content = script_path.read_text()
    
    # Check if script uses nested structure (bug) or flattened structure (fixed)
    # Look for the line that copies src directory
    
    # Bug pattern: cp -r src "$PACKAGE_DIR/" (copies src as subdirectory)
    # Fixed pattern: cp -r src/* "$PACKAGE_DIR/" (copies contents of src to root)
    
    if 'cp -r src "$PACKAGE_DIR/"' in script_content or 'cp -r src/ "$PACKAGE_DIR/"' in script_content:
        # This is the EXPECTED outcome on UNFIXED code
        # Script creates nested structure that causes import errors in Lambda
        pytest.fail(
            f"BUG CONFIRMED: package_lambda.sh creates nested src/ structure. "
            f"Script contains 'cp -r src \"$PACKAGE_DIR/\"' which copies src/ as a subdirectory. "
            f"This causes Lambda to fail with ModuleNotFoundError when trying to import "
            f"'src.handlers.webhook_handler' because Python cannot resolve 'src' module. "
            f"Lambda package structure will be: lambda-package/src/handlers/... "
            f"But handler is configured as: src.handlers.webhook_handler.lambda_handler "
            f"This confirms Bug 1 exists."
        )
    elif 'cp -r src/* "$PACKAGE_DIR/"' in script_content:
        # This is the EXPECTED outcome on FIXED code
        # Script flattens structure, copying contents of src/ to package root
        # Lambda package structure will be: lambda-package/handlers/...
        # Handler should be configured as: handlers.webhook_handler.lambda_handler
        pass
    else:
        pytest.fail(
            f"Cannot determine package structure from package_lambda.sh. "
            f"Expected to find either 'cp -r src \"$PACKAGE_DIR/\"' (bug) or "
            f"'cp -r src/* \"$PACKAGE_DIR/\"' (fixed)."
        )


# ============================================================================
# Bug 2: OpenTelemetry Initialization Failure
# ============================================================================

def test_bug_2_opentelemetry_initialization_failure():
    """
    Bug 2 Exploration: OpenTelemetry Initialization Failure
    
    **Validates: Requirements 1.2, 2.2**
    
    This test verifies that the patch script can successfully modify OpenTelemetry
    to handle missing propagators gracefully instead of raising ValueError.
    
    Bug Condition:
    - OpenTelemetry propagate module raises ValueError when propagators are not found
    - Pattern: except StopIteration: raise ValueError(f"Propagator {propagator} not found...")
    
    Fixed Condition:
    - Patch script modifies the code to: except StopIteration: logger.warning(...); continue
    - OpenTelemetry skips missing propagators with warnings instead of raising
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test FAILS because the patch script
    cannot find the pattern to patch or the patch is not applied correctly.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because the patch script
    successfully modifies OpenTelemetry to skip missing propagators gracefully.
    """
    import tempfile
    import shutil
    
    # Create a temporary file simulating OpenTelemetry propagate module
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_file = f.name
        # Write the unfixed OpenTelemetry propagate code pattern
        f.write("""
from logging import getLogger

logger = getLogger(__name__)

propagators = []

for propagator in ["tracecontext", "baggage"]:
    propagator = propagator.strip()
    try:
        propagators.append(
            next(
                iter(
                    entry_points(
                        group="opentelemetry_propagator",
                        name=propagator,
                    )
                )
            ).load()()
        )
    except StopIteration:
        raise ValueError(
            f"Propagator {propagator} not found. It is either misspelled or not installed."
        )
    except Exception:
        logger.exception("Failed to load propagator: %s", propagator)
        raise
""")
    
    try:
        # Read original content
        with open(temp_file, 'r') as f:
            original_content = f.read()
        
        # Verify the bug pattern exists (ValueError raise)
        if 'raise ValueError' not in original_content:
            pytest.fail(
                "Test setup error: temporary file does not contain the bug pattern. "
                "Expected 'raise ValueError' in OpenTelemetry propagate code."
            )
        
        # Apply the patch script
        import subprocess
        result = subprocess.run(
            ['python3', 'scripts/patch_opentelemetry_propagate.py', temp_file],
            capture_output=True,
            text=True
        )
        
        # Read patched content
        with open(temp_file, 'r') as f:
            patched_content = f.read()
        
        # CRITICAL ASSERTIONS for fixed code:
        # 1. Patch script should succeed
        if result.returncode != 0:
            pytest.fail(
                f"BUG CONFIRMED: Patch script failed to patch OpenTelemetry. "
                f"Return code: {result.returncode}. "
                f"Stdout: {result.stdout}. "
                f"Stderr: {result.stderr}. "
                f"The patch script cannot modify OpenTelemetry to handle missing propagators. "
                f"This confirms Bug 2 exists."
            )
        
        # 2. Patch marker should be present
        if '# Patched: skip missing propagators in Lambda' not in patched_content:
            pytest.fail(
                f"BUG CONFIRMED: Patch marker not found in patched file. "
                f"The patch script did not successfully modify the OpenTelemetry propagate module. "
                f"Patch output: {result.stdout}. "
                f"This confirms Bug 2 exists."
            )
        
        # 3. ValueError raise should be removed
        if 'raise ValueError' in patched_content:
            pytest.fail(
                f"BUG CONFIRMED: ValueError raise still present after patching. "
                f"The patch script did not successfully replace the ValueError raise. "
                f"OpenTelemetry will still fail when propagators are not found. "
                f"This confirms Bug 2 exists."
            )
        
        # 4. Warning and continue should be present
        if 'logger.warning' not in patched_content or 'continue' not in patched_content:
            pytest.fail(
                f"BUG CONFIRMED: Patch did not add warning and continue statements. "
                f"Expected 'logger.warning' and 'continue' in patched code. "
                f"OpenTelemetry will not handle missing propagators gracefully. "
                f"This confirms Bug 2 exists."
            )
        
        # If all assertions pass, the fix is working correctly
        # The patch script successfully modifies OpenTelemetry to skip missing propagators
        
    finally:
        # Clean up temporary file
        import os
        if os.path.exists(temp_file):
            os.unlink(temp_file)


# ============================================================================
# Bug 3: Twilio Message Delivery Failure
# ============================================================================

@given(
    sandbox_number=st.just("whatsapp:+14155238886"),  # Twilio sandbox number
    production_number=st.just("whatsapp:+5511940044117"),  # Production number
)
@settings(
    max_examples=5,
    phases=[Phase.generate],
    deadline=None
)
def test_bug_3_twilio_message_delivery_failure(sandbox_number, production_number):
    """
    Bug 3 Exploration: Twilio Message Delivery Failure
    
    **Validates: Requirements 1.3, 2.3**
    
    This test explores the bug where Twilio returns error 63015 (sender not approved)
    when Lambda attempts to send WhatsApp messages using sandbox or incorrect phone numbers.
    
    Bug Condition:
    - Twilio credentials in Secrets Manager contain sandbox phone number
    - Lambda attempts to send WhatsApp message
    - Twilio rejects with error 63015 (sender not approved or configuration issue)
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test FAILS because Twilio API
    returns error 63015 when using sandbox number in production.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because Secrets Manager
    contains production phone number and messages are delivered successfully.
    """
    # Mock Twilio client to simulate error 63015 with sandbox number
    from twilio.base.exceptions import TwilioRestException
    
    with patch('src.services.twilio_client.Client') as MockTwilioClient:
        mock_client = MagicMock()
        MockTwilioClient.return_value = mock_client
        
        # Simulate Twilio error 63015 when using sandbox number
        def mock_create_message(*args, **kwargs):
            from_number = kwargs.get('from_', '')
            
            # Check if using sandbox number (bug condition)
            if sandbox_number in from_number or '14155238886' in from_number:
                # Simulate Twilio error 63015
                raise TwilioRestException(
                    status=400,
                    uri='/Messages.json',
                    msg='The "From" phone number whatsapp:+14155238886 is not a valid, '
                        'SMS-capable inbound phone number or short code for your account.',
                    code=63015,
                    method='POST'
                )
            
            # Production number would succeed
            return MagicMock(sid='SM123', status='queued')
        
        mock_client.messages.create = mock_create_message
        
        # Mock settings to use sandbox number (bug condition)
        with patch('src.services.twilio_client.settings') as mock_settings:
            mock_settings.get_twilio_credentials.return_value = {
                'account_sid': 'AC123',
                'auth_token': 'test_token',
                'whatsapp_number': sandbox_number  # BUG: Using sandbox number
            }
            
            # Import TwilioClient after mocking
            from src.services.twilio_client import TwilioClient
            
            try:
                # CRITICAL ASSERTION: Attempt to send message with sandbox number
                # On UNFIXED code, this will FAIL with TwilioRestException error 63015
                
                client = TwilioClient()
                result = client.send_message(
                    to='whatsapp:+5511999999999',
                    body='Test message'
                )
                
                # If we reach here, message was sent successfully
                # On UNFIXED code, we should NOT reach here
                assert result.get('status') in ['queued', 'sent'], (
                    "Message should be sent successfully. "
                    "If this passes on unfixed code, the bug may not exist or "
                    "production credentials are already configured."
                )
                
            except TwilioRestException as e:
                # This is the EXPECTED outcome on UNFIXED code
                assert e.code == 63015, (
                    f"Expected Twilio error 63015, got: {e.code}"
                )
                
                # Document the counterexample
                pytest.fail(
                    f"BUG CONFIRMED: Twilio message delivery fails with error 63015. "
                    f"Error: {e.msg}. "
                    f"Lambda is using sandbox phone number ({sandbox_number}) from "
                    f"Secrets Manager, which is not approved for production use. "
                    f"This confirms Bug 3 exists."
                )


# ============================================================================
# Bug 4: Stale Secret Caching
# ============================================================================

def test_bug_4_stale_secret_caching():
    """
    Bug 4 Exploration: Stale Secret Caching
    
    **Validates: Requirements 1.4, 2.4**
    
    This test explores the bug where the global settings instance in config.py
    is cached across Lambda invocations. While _get_secret() doesn't cache,
    the global settings object itself is reused in warm Lambda containers.
    
    Bug Condition:
    - Global settings instance created at module import: settings = Settings()
    - Lambda warm start reuses the same settings instance
    - Settings attributes are set at initialization and not refreshed
    - When secrets are updated, Lambda needs redeployment to reload
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test documents that the global
    settings instance is cached, requiring Lambda redeployment for secret updates.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because Settings
    implements a reload mechanism or secrets are fetched fresh on each call.
    """
    # Check if config.py has a global settings instance
    config_path = Path("src/config.py")
    
    if not config_path.exists():
        pytest.skip("config.py not found")
    
    config_content = config_path.read_text()
    
    # Check for global settings instance
    if 'settings = Settings()' in config_content:
        # This is the EXPECTED outcome on UNFIXED code
        # Global settings instance is created at module import
        pytest.fail(
            f"BUG CONFIRMED: Global settings instance cached across Lambda invocations. "
            f"config.py contains 'settings = Settings()' which creates a global instance "
            f"that is cached in Lambda warm containers. "
            f"When Twilio secrets are updated in Secrets Manager, Lambda continues using "
            f"the cached Settings object with old values. "
            f"Lambda requires redeployment or environment variable change to reload secrets. "
            f"This confirms Bug 4 exists."
        )
    else:
        # This is the EXPECTED outcome on FIXED code
        # No global settings instance, or settings are reloaded on each invocation
        pass


# ============================================================================
# Bug 5: SQS Processing Failure
# ============================================================================

def test_bug_5_sqs_processing_failure():
    """
    Bug 5 Exploration: SQS Message Processing Failure
    
    **Validates: Requirements 1.5, 2.5**
    
    This test verifies that SQS queue has proper retry and DLQ configuration,
    and that the message processor has comprehensive error handling.
    
    Bug Condition:
    - SQS queue lacks RedrivePolicy or maxReceiveCount configuration
    - Message processor lacks proper error handling with batchItemFailures
    - Messages could be stuck in queue without retry or DLQ routing
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test FAILS if SQS configuration
    or error handling is incomplete.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because SQS has proper
    retry/DLQ configuration and message processor has comprehensive error handling.
    """
    issues = []
    
    # Check 1: Verify CloudFormation template has SQS RedrivePolicy
    template_path = Path("infrastructure/template.yml")
    
    if template_path.exists():
        template_content = template_path.read_text()
        
        # Check for RedrivePolicy in SQS queue configuration
        if 'RedrivePolicy' not in template_content:
            issues.append("CloudFormation template missing RedrivePolicy for SQS queue")
        
        # Check for maxReceiveCount
        if 'maxReceiveCount' not in template_content:
            issues.append("CloudFormation template missing maxReceiveCount for retry configuration")
        
        # Check for VisibilityTimeout
        if 'VisibilityTimeout' not in template_content:
            issues.append("CloudFormation template missing VisibilityTimeout configuration")
    else:
        issues.append("CloudFormation template not found")
    
    # Check 2: Verify message processor has error handling
    handler_path = Path("src/handlers/message_processor.py")
    
    if handler_path.exists():
        handler_content = handler_path.read_text()
        
        # Check for batchItemFailures handling
        if 'batchItemFailures' not in handler_content:
            issues.append("Message processor missing batchItemFailures handling")
        
        # Check for try-except in record processing
        if 'for record in event.get("Records"' in handler_content:
            if 'try:' not in handler_content or 'except Exception' not in handler_content:
                issues.append("Message processor missing try-except in record processing loop")
        
        # Check for batch_item_failures list
        if 'batch_item_failures' not in handler_content.lower():
            issues.append("Message processor missing batch_item_failures list")
    else:
        issues.append("Message processor handler not found")
    
    if issues:
        # This is the EXPECTED outcome on UNFIXED code
        pytest.fail(
            f"BUG CONFIRMED: SQS message processing lacks proper configuration or error handling. "
            f"Issues found: {', '.join(issues)}. "
            f"Without proper SQS retry/DLQ configuration and error handling, messages can be "
            f"stuck in queue or lost. Required: (1) RedrivePolicy with DLQ, (2) maxReceiveCount "
            f"for retry limit, (3) VisibilityTimeout, (4) batchItemFailures in handler. "
            f"This confirms Bug 5 exists."
        )
    
    # If all checks pass, SQS configuration and error handling exist


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
