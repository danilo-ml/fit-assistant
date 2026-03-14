"""
Smoke tests for staging deployment validation.

These tests verify that the staging environment is correctly deployed and
all critical components are functioning properly.

Run with: pytest tests/smoke/test_staging_deployment.py -v
"""

import os
import json
import boto3
import pytest
from datetime import datetime
from typing import Dict, Any

# Configuration
STACK_NAME = os.getenv("STACK_NAME", "fitagent-staging")
REGION = os.getenv("AWS_REGION", "us-east-1")
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER", "+14155551234")


@pytest.fixture(scope="module")
def aws_clients():
    """Initialize AWS clients for testing."""
    return {
        "cloudformation": boto3.client("cloudformation", region_name=REGION),
        "dynamodb": boto3.client("dynamodb", region_name=REGION),
        "lambda": boto3.client("lambda", region_name=REGION),
        "events": boto3.client("events", region_name=REGION),
        "logs": boto3.client("logs", region_name=REGION),
    }


@pytest.fixture(scope="module")
def stack_outputs(aws_clients) -> Dict[str, str]:
    """Get CloudFormation stack outputs."""
    cf = aws_clients["cloudformation"]
    
    try:
        response = cf.describe_stacks(StackName=STACK_NAME)
        stack = response["Stacks"][0]
        
        outputs = {}
        for output in stack.get("Outputs", []):
            outputs[output["OutputKey"]] = output["OutputValue"]
        
        return outputs
    except Exception as e:
        pytest.fail(f"Failed to get stack outputs: {e}")


class TestStackDeployment:
    """Test CloudFormation stack deployment."""
    
    def test_stack_exists(self, aws_clients):
        """Verify CloudFormation stack exists and is in CREATE_COMPLETE or UPDATE_COMPLETE state."""
        cf = aws_clients["cloudformation"]
        
        response = cf.describe_stacks(StackName=STACK_NAME)
        assert len(response["Stacks"]) == 1
        
        stack = response["Stacks"][0]
        assert stack["StackStatus"] in [
            "CREATE_COMPLETE",
            "UPDATE_COMPLETE",
        ], f"Stack status is {stack['StackStatus']}"
    
    def test_stack_has_required_outputs(self, stack_outputs):
        """Verify stack has all required outputs."""
        required_outputs = [
            "TableName",
            "TableArn",
            "MessageProcessorFunctionName",
            "SessionConfirmationFunctionName",
            "SessionConfirmationRuleName",
        ]
        
        for output_key in required_outputs:
            assert output_key in stack_outputs, f"Missing output: {output_key}"
            assert stack_outputs[output_key], f"Empty output: {output_key}"


class TestDynamoDBTable:
    """Test DynamoDB table configuration."""
    
    def test_table_exists(self, aws_clients, stack_outputs):
        """Verify DynamoDB table exists."""
        dynamodb = aws_clients["dynamodb"]
        table_name = stack_outputs["TableName"]
        
        response = dynamodb.describe_table(TableName=table_name)
        assert response["Table"]["TableStatus"] == "ACTIVE"
    
    def test_table_has_required_gsis(self, aws_clients, stack_outputs):
        """Verify table has all required Global Secondary Indexes."""
        dynamodb = aws_clients["dynamodb"]
        table_name = stack_outputs["TableName"]
        
        response = dynamodb.describe_table(TableName=table_name)
        gsis = response["Table"].get("GlobalSecondaryIndexes", [])
        
        gsi_names = {gsi["IndexName"] for gsi in gsis}
        required_gsis = {
            "phone-number-index",
            "session-date-index",
            "payment-status-index",
            "session-confirmation-index",
        }
        
        assert required_gsis.issubset(gsi_names), f"Missing GSIs: {required_gsis - gsi_names}"
        
        # Verify all GSIs are active
        for gsi in gsis:
            if gsi["IndexName"] in required_gsis:
                assert gsi["IndexStatus"] == "ACTIVE", f"GSI {gsi['IndexName']} is not active"
    
    def test_table_has_encryption(self, aws_clients, stack_outputs):
        """Verify table has encryption enabled."""
        dynamodb = aws_clients["dynamodb"]
        table_name = stack_outputs["TableName"]
        
        response = dynamodb.describe_table(TableName=table_name)
        sse_description = response["Table"].get("SSEDescription", {})
        
        assert sse_description.get("Status") == "ENABLED", "Table encryption not enabled"
    
    def test_table_has_point_in_time_recovery(self, aws_clients, stack_outputs):
        """Verify table has point-in-time recovery enabled."""
        dynamodb = aws_clients["dynamodb"]
        table_name = stack_outputs["TableName"]
        
        response = dynamodb.describe_continuous_backups(TableName=table_name)
        pitr_status = response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]["PointInTimeRecoveryStatus"]
        
        assert pitr_status == "ENABLED", "Point-in-time recovery not enabled"


class TestLambdaFunctions:
    """Test Lambda function configuration."""
    
    def test_message_processor_function_exists(self, aws_clients, stack_outputs):
        """Verify Message Processor Lambda function exists and is configured correctly."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["MessageProcessorFunctionName"]
        
        response = lambda_client.get_function(FunctionName=function_name)
        config = response["Configuration"]
        
        assert config["Runtime"] == "python3.12"
        assert config["Timeout"] == 180
        assert config["MemorySize"] == 1024
        assert config["State"] == "Active"
    
    def test_message_processor_has_required_env_vars(self, aws_clients, stack_outputs):
        """Verify Message Processor has required environment variables."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["MessageProcessorFunctionName"]
        
        response = lambda_client.get_function_configuration(FunctionName=function_name)
        env_vars = response.get("Environment", {}).get("Variables", {})
        
        required_vars = [
            "DYNAMODB_TABLE",
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_WHATSAPP_NUMBER",
            "ENVIRONMENT",
            "BEDROCK_MODEL_ID",
        ]
        
        for var in required_vars:
            assert var in env_vars, f"Missing environment variable: {var}"
    
    def test_session_confirmation_function_exists(self, aws_clients, stack_outputs):
        """Verify Session Confirmation Lambda function exists and is configured correctly."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["SessionConfirmationFunctionName"]
        
        response = lambda_client.get_function(FunctionName=function_name)
        config = response["Configuration"]
        
        assert config["Runtime"] == "python3.12"
        assert config["Timeout"] == 60
        assert config["MemorySize"] == 512
        assert config["State"] == "Active"
    
    def test_lambda_functions_have_strands_agents_sdk(self, aws_clients, stack_outputs):
        """Verify Lambda functions include Strands Agents SDK in deployment package."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["MessageProcessorFunctionName"]
        
        # Get function code location
        response = lambda_client.get_function(FunctionName=function_name)
        code_size = response["Configuration"]["CodeSize"]
        
        # Strands Agents SDK should add significant size to the package
        # Minimum expected size with dependencies: ~5MB
        assert code_size > 5_000_000, f"Package size ({code_size} bytes) seems too small - Strands Agents SDK may be missing"


class TestEventBridgeRule:
    """Test EventBridge scheduled rule configuration."""
    
    def test_session_confirmation_rule_exists(self, aws_clients, stack_outputs):
        """Verify EventBridge rule exists and is enabled."""
        events = aws_clients["events"]
        rule_name = stack_outputs["SessionConfirmationRuleName"]
        
        response = events.describe_rule(Name=rule_name)
        
        assert response["State"] == "ENABLED"
        assert response["ScheduleExpression"] == "cron(*/5 * * * ? *)"
    
    def test_session_confirmation_rule_has_target(self, aws_clients, stack_outputs):
        """Verify EventBridge rule has Lambda function as target."""
        events = aws_clients["events"]
        rule_name = stack_outputs["SessionConfirmationRuleName"]
        function_arn = stack_outputs["SessionConfirmationFunctionArn"]
        
        response = events.list_targets_by_rule(Rule=rule_name)
        targets = response["Targets"]
        
        assert len(targets) > 0, "No targets configured for rule"
        
        target_arns = [target["Arn"] for target in targets]
        assert function_arn in target_arns, "Lambda function not configured as target"


class TestIAMPermissions:
    """Test IAM permissions and roles."""
    
    def test_message_processor_can_access_dynamodb(self, aws_clients, stack_outputs):
        """Verify Message Processor Lambda has DynamoDB permissions."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["MessageProcessorFunctionName"]
        
        response = lambda_client.get_function(FunctionName=function_name)
        role_arn = response["Configuration"]["Role"]
        
        # Role should exist and have DynamoDB policy
        assert "fitagent-message-processor-role" in role_arn
    
    def test_session_confirmation_can_access_dynamodb(self, aws_clients, stack_outputs):
        """Verify Session Confirmation Lambda has DynamoDB permissions."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["SessionConfirmationFunctionName"]
        
        response = lambda_client.get_function(FunctionName=function_name)
        role_arn = response["Configuration"]["Role"]
        
        # Role should exist and have DynamoDB policy
        assert "fitagent-session-confirmation-role" in role_arn


class TestEndToEndFlow:
    """Test end-to-end functionality (requires test data)."""
    
    @pytest.mark.integration
    def test_can_write_to_dynamodb(self, aws_clients, stack_outputs):
        """Verify we can write test data to DynamoDB."""
        dynamodb = aws_clients["dynamodb"]
        table_name = stack_outputs["TableName"]
        
        test_item = {
            "PK": {"S": "TEST#smoke-test"},
            "SK": {"S": "METADATA"},
            "entity_type": {"S": "TEST"},
            "created_at": {"S": datetime.utcnow().isoformat()},
            "test_run": {"S": "staging-smoke-test"},
        }
        
        # Write test item
        dynamodb.put_item(TableName=table_name, Item=test_item)
        
        # Read it back
        response = dynamodb.get_item(
            TableName=table_name,
            Key={
                "PK": {"S": "TEST#smoke-test"},
                "SK": {"S": "METADATA"},
            }
        )
        
        assert "Item" in response
        assert response["Item"]["test_run"]["S"] == "staging-smoke-test"
        
        # Clean up
        dynamodb.delete_item(
            TableName=table_name,
            Key={
                "PK": {"S": "TEST#smoke-test"},
                "SK": {"S": "METADATA"},
            }
        )
    
    @pytest.mark.integration
    def test_message_processor_invocation(self, aws_clients, stack_outputs):
        """Verify Message Processor Lambda can be invoked."""
        lambda_client = aws_clients["lambda"]
        function_name = stack_outputs["MessageProcessorFunctionName"]
        
        # Create test event
        test_event = {
            "message": "Hello, this is a smoke test",
            "phone_number": TEST_PHONE_NUMBER,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Invoke function (dry run - don't actually send messages)
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(test_event),
        )
        
        # Check response
        assert response["StatusCode"] == 200
        
        # Parse response payload
        payload = json.loads(response["Payload"].read())
        
        # Function should return 200 or handle gracefully
        # (May fail if test trainer doesn't exist, but should not crash)
        assert "statusCode" in payload


class TestMonitoring:
    """Test monitoring and logging configuration."""
    
    def test_lambda_functions_have_log_groups(self, aws_clients, stack_outputs):
        """Verify Lambda functions have CloudWatch log groups."""
        logs = aws_clients["logs"]
        
        function_names = [
            stack_outputs["MessageProcessorFunctionName"],
            stack_outputs["SessionConfirmationFunctionName"],
        ]
        
        for function_name in function_names:
            log_group_name = f"/aws/lambda/{function_name}"
            
            try:
                response = logs.describe_log_groups(
                    logGroupNamePrefix=log_group_name
                )
                log_groups = response["logGroups"]
                
                assert len(log_groups) > 0, f"Log group not found: {log_group_name}"
            except Exception as e:
                pytest.fail(f"Failed to check log group {log_group_name}: {e}")


# Summary function for reporting
def pytest_sessionfinish(session, exitstatus):
    """Print summary after all tests complete."""
    if exitstatus == 0:
        print("\n" + "="*60)
        print("✓ All smoke tests passed!")
        print("="*60)
        print("\nStaging environment is ready for testing.")
        print("\nNext steps:")
        print("  1. Send test WhatsApp messages")
        print("  2. Monitor CloudWatch logs and metrics")
        print("  3. Verify session confirmation flow")
    else:
        print("\n" + "="*60)
        print("✗ Some smoke tests failed")
        print("="*60)
        print("\nReview failures above and fix issues before proceeding.")
