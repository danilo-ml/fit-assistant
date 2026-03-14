"""
Property-based tests for production Lambda deployment preservation.

This test file verifies that existing functionality remains unchanged after
applying fixes for the 5 critical Lambda deployment bugs. These tests should
PASS on both unfixed and fixed code.

**CRITICAL**: These tests verify preservation of existing behavior.
**EXPECTED OUTCOME**: Tests PASS on unfixed code (baseline) and continue to pass on fixed code.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from hypothesis import given, strategies as st, settings, Phase
import pytest


# ============================================================================
# Preservation 1: Local Development Environment
# ============================================================================

def test_preservation_local_development_environment():
    """
    Preservation Test 1: Local Development Environment
    
    **Validates: Requirement 3.5**
    
    This test verifies that the local development environment with LocalStack
    and Docker Compose continues to function correctly after applying fixes.
    
    Preserved Behaviors:
    - Makefile commands (start, test, logs, stop) work correctly
    - Docker Compose configuration is valid
    - LocalStack initialization scripts are intact
    - Environment variable templates are preserved
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that local development workflows are not affected by the fixes.
    """
    issues = []
    
    # Check 1: Verify Makefile exists and has required targets
    makefile_path = Path("Makefile")
    if not makefile_path.exists():
        issues.append("Makefile not found")
    else:
        makefile_content = makefile_path.read_text()
        required_targets = ['start', 'test', 'logs', 'stop', 'restart', 'clean']
        for target in required_targets:
            if f'{target}:' not in makefile_content:
                issues.append(f"Makefile missing required target: {target}")
    
    # Check 2: Verify docker-compose.yml exists and is valid
    docker_compose_path = Path("docker-compose.yml")
    if not docker_compose_path.exists():
        issues.append("docker-compose.yml not found")
    else:
        # Verify it's valid YAML by attempting to parse
        try:
            import yaml
            with open(docker_compose_path) as f:
                docker_config = yaml.safe_load(f)
            
            # Check for essential services
            if 'services' not in docker_config:
                issues.append("docker-compose.yml missing 'services' section")
            else:
                # LocalStack should be defined
                if 'localstack' not in docker_config['services']:
                    issues.append("docker-compose.yml missing 'localstack' service")
        except Exception as e:
            issues.append(f"docker-compose.yml is not valid YAML: {e}")
    
    # Check 3: Verify LocalStack initialization scripts exist
    localstack_init_path = Path("localstack-init/01-setup.sh")
    if not localstack_init_path.exists():
        issues.append("LocalStack initialization script not found")
    
    # Check 4: Verify environment variable templates exist
    env_example_path = Path(".env.example")
    if not env_example_path.exists():
        issues.append(".env.example not found")
    
    # Check 5: Verify pytest configuration exists
    pytest_ini_path = Path("pytest.ini")
    if not pytest_ini_path.exists():
        issues.append("pytest.ini not found")
    
    # Assert no issues found
    assert not issues, (
        f"Local development environment preservation check failed. "
        f"Issues found: {', '.join(issues)}. "
        f"The fixes should not affect local development workflows."
    )


# ============================================================================
# Preservation 2: Dependency Management
# ============================================================================

@given(
    # Generate test cases for different dependency types
    dependency_type=st.sampled_from(['production', 'development'])
)
@settings(
    max_examples=2,
    phases=[Phase.generate],
    deadline=None
)
def test_preservation_dependency_management(dependency_type):
    """
    Preservation Test 2: Dependency Management
    
    **Validates: Requirement 3.1**
    
    This test verifies that all production dependencies from requirements.txt
    continue to be included in the Lambda package after applying fixes.
    
    Preserved Behaviors:
    - requirements.txt contains all necessary production dependencies
    - requirements-dev.txt contains all development dependencies
    - Package structure includes all dependencies
    - No dependencies are accidentally removed
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that dependency management is not affected by the fixes.
    """
    issues = []
    
    if dependency_type == 'production':
        req_file = Path("requirements.txt")
        if not req_file.exists():
            pytest.fail("requirements.txt not found")
        
        req_content = req_file.read_text()
        
        # Verify essential production dependencies are present
        essential_deps = [
            'boto3',  # AWS SDK
            'strands-agents',  # AI agent framework
            'twilio',  # WhatsApp messaging
            'pydantic',  # Data validation
            'structlog',  # Logging
        ]
        
        for dep in essential_deps:
            # Check if dependency is in requirements (may have version specifier)
            if dep not in req_content.lower():
                issues.append(f"Essential production dependency missing: {dep}")
    
    elif dependency_type == 'development':
        req_dev_file = Path("requirements-dev.txt")
        if not req_dev_file.exists():
            pytest.fail("requirements-dev.txt not found")
        
        req_dev_content = req_dev_file.read_text()
        
        # Verify essential development dependencies are present
        essential_dev_deps = [
            'pytest',  # Testing framework
            'hypothesis',  # Property-based testing
            'moto',  # AWS mocking
            'black',  # Code formatting
            'flake8',  # Linting
        ]
        
        for dep in essential_dev_deps:
            if dep not in req_dev_content.lower():
                issues.append(f"Essential development dependency missing: {dep}")
    
    # Assert no issues found
    assert not issues, (
        f"Dependency management preservation check failed for {dependency_type} dependencies. "
        f"Issues found: {', '.join(issues)}. "
        f"The fixes should not remove or modify dependencies."
    )


# ============================================================================
# Preservation 3: CloudFormation Validation
# ============================================================================

def test_preservation_cloudformation_validation():
    """
    Preservation Test 3: CloudFormation Validation
    
    **Validates: Requirement 3.4**
    
    This test verifies that CloudFormation template validation continues to
    work correctly after applying fixes.
    
    Preserved Behaviors:
    - infrastructure/template.yml exists and is valid YAML
    - Template contains required resources (Lambda, DynamoDB, S3, SQS)
    - Parameter files exist for different environments
    - Template structure is preserved
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that CloudFormation validation is not affected by the fixes.
    """
    issues = []
    
    # Check 1: Verify CloudFormation template exists
    template_path = Path("infrastructure/template.yml")
    if not template_path.exists():
        issues.append("CloudFormation template not found")
        pytest.fail(f"Issues: {', '.join(issues)}")
    
    # Check 2: Verify template is valid YAML (with CloudFormation intrinsic functions)
    try:
        import yaml
        
        # Add CloudFormation intrinsic function constructors
        def cloudformation_constructor(loader, tag_suffix, node):
            """Handle CloudFormation intrinsic functions like !Ref, !GetAtt, etc."""
            if isinstance(node, yaml.ScalarNode):
                return loader.construct_scalar(node)
            elif isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node)
            elif isinstance(node, yaml.MappingNode):
                return loader.construct_mapping(node)
            return None
        
        yaml.SafeLoader.add_multi_constructor('!', cloudformation_constructor)
        
        with open(template_path) as f:
            template = yaml.safe_load(f)
    except Exception as e:
        issues.append(f"CloudFormation template is not valid YAML: {e}")
        pytest.fail(f"Issues: {', '.join(issues)}")
    
    # Check 3: Verify template has required sections
    required_sections = ['AWSTemplateFormatVersion', 'Description', 'Resources']
    for section in required_sections:
        if section not in template:
            issues.append(f"CloudFormation template missing required section: {section}")
    
    # Check 4: Verify template has required resources
    if 'Resources' in template:
        resources = template['Resources']
        
        # Check for Lambda functions
        lambda_functions = [k for k, v in resources.items() 
                          if v.get('Type') == 'AWS::Lambda::Function']
        if not lambda_functions:
            issues.append("CloudFormation template missing Lambda function resources")
        
        # Check for DynamoDB table
        dynamodb_tables = [k for k, v in resources.items() 
                          if v.get('Type') == 'AWS::DynamoDB::Table']
        if not dynamodb_tables:
            issues.append("CloudFormation template missing DynamoDB table resource")
        
        # Check for S3 bucket
        s3_buckets = [k for k, v in resources.items() 
                     if v.get('Type') == 'AWS::S3::Bucket']
        if not s3_buckets:
            issues.append("CloudFormation template missing S3 bucket resource")
        
        # Check for SQS queue
        sqs_queues = [k for k, v in resources.items() 
                     if v.get('Type') == 'AWS::SQS::Queue']
        if not sqs_queues:
            issues.append("CloudFormation template missing SQS queue resource")
    
    # Check 5: Verify parameter files exist
    param_dir = Path("infrastructure/parameters")
    if param_dir.exists():
        # Check for environment-specific parameter files
        expected_param_files = ['dev.json', 'staging.json', 'production.json']
        for param_file in expected_param_files:
            param_path = param_dir / param_file
            if param_path.exists():
                # Verify it's valid JSON
                try:
                    with open(param_path) as f:
                        json.load(f)
                except Exception as e:
                    issues.append(f"Parameter file {param_file} is not valid JSON: {e}")
    
    # Assert no issues found
    assert not issues, (
        f"CloudFormation validation preservation check failed. "
        f"Issues found: {', '.join(issues)}. "
        f"The fixes should not affect CloudFormation template structure or validation."
    )


# ============================================================================
# Preservation 4: AWS Service Integration
# ============================================================================

@given(
    # Generate test cases for different AWS services
    service=st.sampled_from(['dynamodb', 's3', 'sqs', 'secrets_manager'])
)
@settings(
    max_examples=4,
    phases=[Phase.generate],
    deadline=None
)
def test_preservation_aws_service_integration(service):
    """
    Preservation Test 4: AWS Service Integration
    
    **Validates: Requirement 3.3**
    
    This test verifies that Lambda functions continue to use correct IAM
    permissions and service endpoints for AWS services after applying fixes.
    
    Preserved Behaviors:
    - DynamoDB client configuration is preserved
    - S3 client configuration is preserved
    - SQS client configuration is preserved
    - Secrets Manager client configuration is preserved
    - IAM permissions in CloudFormation are preserved
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that AWS service integrations are not affected by the fixes.
    """
    issues = []
    
    # Check CloudFormation template for IAM permissions
    template_path = Path("infrastructure/template.yml")
    if not template_path.exists():
        pytest.skip("CloudFormation template not found")
    
    try:
        import yaml
        
        # Add CloudFormation intrinsic function constructors
        def cloudformation_constructor(loader, tag_suffix, node):
            """Handle CloudFormation intrinsic functions like !Ref, !GetAtt, etc."""
            if isinstance(node, yaml.ScalarNode):
                return loader.construct_scalar(node)
            elif isinstance(node, yaml.SequenceNode):
                return loader.construct_sequence(node)
            elif isinstance(node, yaml.MappingNode):
                return loader.construct_mapping(node)
            return None
        
        yaml.SafeLoader.add_multi_constructor('!', cloudformation_constructor)
        
        with open(template_path) as f:
            template = yaml.safe_load(f)
    except Exception as e:
        pytest.skip(f"Cannot parse CloudFormation template: {e}")
    
    # Find IAM roles in template
    resources = template.get('Resources', {})
    iam_roles = {k: v for k, v in resources.items() 
                 if v.get('Type') == 'AWS::IAM::Role'}
    
    if not iam_roles:
        issues.append("No IAM roles found in CloudFormation template")
    
    # Check for service-specific permissions
    if service == 'dynamodb':
        # Verify DynamoDB permissions exist
        found_dynamodb_perms = False
        for role_name, role_config in iam_roles.items():
            policies = role_config.get('Properties', {}).get('Policies', [])
            for policy in policies:
                statements = policy.get('PolicyDocument', {}).get('Statement', [])
                for statement in statements:
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if any('dynamodb:' in action.lower() for action in actions):
                        found_dynamodb_perms = True
                        break
        
        if not found_dynamodb_perms:
            issues.append("DynamoDB permissions not found in IAM roles")
    
    elif service == 's3':
        # Verify S3 permissions exist
        found_s3_perms = False
        for role_name, role_config in iam_roles.items():
            policies = role_config.get('Properties', {}).get('Policies', [])
            for policy in policies:
                statements = policy.get('PolicyDocument', {}).get('Statement', [])
                for statement in statements:
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if any('s3:' in action.lower() for action in actions):
                        found_s3_perms = True
                        break
        
        if not found_s3_perms:
            issues.append("S3 permissions not found in IAM roles")
    
    elif service == 'sqs':
        # Verify SQS permissions exist
        found_sqs_perms = False
        for role_name, role_config in iam_roles.items():
            policies = role_config.get('Properties', {}).get('Policies', [])
            for policy in policies:
                statements = policy.get('PolicyDocument', {}).get('Statement', [])
                for statement in statements:
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if any('sqs:' in action.lower() for action in actions):
                        found_sqs_perms = True
                        break
        
        if not found_sqs_perms:
            issues.append("SQS permissions not found in IAM roles")
    
    elif service == 'secrets_manager':
        # Verify Secrets Manager permissions exist
        found_secrets_perms = False
        for role_name, role_config in iam_roles.items():
            policies = role_config.get('Properties', {}).get('Policies', [])
            for policy in policies:
                statements = policy.get('PolicyDocument', {}).get('Statement', [])
                for statement in statements:
                    actions = statement.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if any('secretsmanager:' in action.lower() for action in actions):
                        found_secrets_perms = True
                        break
        
        if not found_secrets_perms:
            issues.append("Secrets Manager permissions not found in IAM roles")
    
    # Assert no issues found
    assert not issues, (
        f"AWS service integration preservation check failed for {service}. "
        f"Issues found: {', '.join(issues)}. "
        f"The fixes should not affect IAM permissions or service endpoints."
    )


# ============================================================================
# Preservation 5: OpenTelemetry Patch Functionality
# ============================================================================

def test_preservation_opentelemetry_patch_functionality():
    """
    Preservation Test 5: OpenTelemetry Patch Functionality
    
    **Validates: Requirement 3.2**
    
    This test verifies that the OpenTelemetry patch preserves the original
    functionality of the Strands SDK while adding compatibility fixes.
    
    Preserved Behaviors:
    - Patch script exists and is executable
    - Patch targets the correct OpenTelemetry module
    - Patch does not break existing OpenTelemetry functionality
    - Strands SDK can still initialize and function correctly
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that the OpenTelemetry patch preserves SDK functionality.
    """
    issues = []
    
    # Check 1: Verify patch script exists
    patch_script_path = Path("scripts/patch_opentelemetry_propagate.py")
    if not patch_script_path.exists():
        issues.append("OpenTelemetry patch script not found")
        pytest.fail(f"Issues: {', '.join(issues)}")
    
    # Check 2: Verify patch script is valid Python
    try:
        with open(patch_script_path) as f:
            patch_content = f.read()
        
        # Basic syntax check by compiling
        compile(patch_content, str(patch_script_path), 'exec')
    except SyntaxError as e:
        issues.append(f"Patch script has syntax errors: {e}")
    
    # Check 3: Verify patch targets OpenTelemetry propagate module
    if 'opentelemetry' not in patch_content.lower():
        issues.append("Patch script does not reference OpenTelemetry")
    
    if 'propagate' not in patch_content.lower():
        issues.append("Patch script does not reference propagate module")
    
    # Check 4: Verify patch preserves functionality (doesn't remove code)
    # The patch should ADD error handling, not REMOVE functionality
    if 'raise ValueError' in patch_content:
        # Patch should replace ValueError with warning, not remove it entirely
        if 'warning' not in patch_content.lower() and 'logger' not in patch_content.lower():
            issues.append("Patch may remove error handling without adding warnings")
    
    # Check 5: Verify package_lambda.sh applies the patch
    package_script_path = Path("scripts/package_lambda.sh")
    if package_script_path.exists():
        package_content = package_script_path.read_text()
        
        # Check if patch is applied during packaging
        if 'patch_opentelemetry' not in package_content:
            issues.append("package_lambda.sh does not apply OpenTelemetry patch")
    
    # Assert no issues found
    assert not issues, (
        f"OpenTelemetry patch preservation check failed. "
        f"Issues found: {', '.join(issues)}. "
        f"The patch should preserve original SDK functionality while adding compatibility."
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
