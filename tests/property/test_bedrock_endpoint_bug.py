"""
Property-based test for Bedrock endpoint bug in LocalStack environment.

This test explores the bug condition where BedrockModel is initialized without
the endpoint_url parameter in LocalStack environment, causing Bedrock API calls
to be directed to LocalStack (which doesn't implement Bedrock) instead of real AWS.

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, call, Mock
from hypothesis import given, strategies as st, settings, Phase

# Mock strands module before importing StrandsAgentService
sys.modules['strands'] = Mock()
sys.modules['strands.models'] = Mock()
sys.modules['strands.models.bedrock'] = Mock()

from src.services.strands_agent_service import StrandsAgentService
from src.config import Settings


# Strategy for LocalStack environment configuration
@st.composite
def localstack_config(draw):
    """
    Generate LocalStack environment configuration.
    
    In LocalStack environment:
    - aws_endpoint_url is set (points to LocalStack)
    - aws_bedrock_endpoint_url should be set to real AWS or None (to use default)
    """
    return {
        'environment': 'local',
        'aws_endpoint_url': 'http://localhost:4566',  # LocalStack endpoint
        'aws_bedrock_endpoint_url': draw(st.one_of(
            st.none(),  # Use default AWS endpoint
            st.just('https://bedrock-runtime.us-east-1.amazonaws.com')  # Real AWS endpoint
        )),
        'bedrock_model_id': 'anthropic.claude-3-sonnet-20240229-v1:0',
        'bedrock_region': 'us-east-1'
    }


@given(config=localstack_config())
@settings(
    max_examples=10,
    phases=[Phase.generate, Phase.target],
    deadline=None
)
def test_bedrock_model_initialization_with_endpoint_url_in_localstack(config):
    """
    Property 1: Bug Condition - Bedrock Uses Real AWS Endpoint in LocalStack
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    
    For any message processing context where the system runs in LocalStack environment
    (aws_endpoint_url is set) and a WhatsApp message is processed, the BedrockModel
    SHALL be initialized with an endpoint_url parameter that points to the real AWS
    Bedrock endpoint (not LocalStack), enabling successful AI response generation.
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test FAILS because BedrockModel is
    initialized WITHOUT endpoint_url parameter, causing it to use LocalStack endpoint.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test PASSES because BedrockModel is
    initialized WITH endpoint_url parameter pointing to real AWS Bedrock endpoint.
    
    Bug Condition:
    - Environment is LocalStack (aws_endpoint_url is set)
    - BedrockModel is initialized without endpoint_url parameter
    - Bedrock calls are directed to LocalStack instead of real AWS
    - LocalStack raises NotImplementedError for Bedrock calls
    
    Expected Behavior (after fix):
    - BedrockModel SHALL be initialized with endpoint_url parameter
    - endpoint_url SHALL point to real AWS Bedrock endpoint (or None for default)
    - Bedrock calls SHALL succeed through real AWS endpoint
    - AI responses SHALL be returned to users
    """
    # Mock settings with LocalStack configuration
    with patch('src.services.strands_agent_service.settings') as mock_settings:
        mock_settings.bedrock_model_id = config['bedrock_model_id']
        mock_settings.bedrock_region = config['bedrock_region']
        mock_settings.aws_endpoint_url = config['aws_endpoint_url']
        mock_settings.aws_bedrock_endpoint_url = config['aws_bedrock_endpoint_url']
        mock_settings.dynamodb_table = 'fitagent-main'
        
        # Mock BedrockModel to capture initialization parameters
        with patch('src.services.strands_agent_service.BedrockModel') as MockBedrockModel:
            mock_model_instance = MagicMock()
            MockBedrockModel.return_value = mock_model_instance
            
            # Mock DynamoDBClient to avoid actual DB calls
            with patch('src.services.strands_agent_service.DynamoDBClient'):
                # Initialize StrandsAgentService
                service = StrandsAgentService()
                
                # CRITICAL ASSERTION: BedrockModel MUST be initialized with endpoint_url parameter
                # This assertion will FAIL on unfixed code because endpoint_url is not passed
                MockBedrockModel.assert_called_once()
                call_kwargs = MockBedrockModel.call_args[1]
                
                # Verify that endpoint_url parameter was passed to BedrockModel
                assert 'endpoint_url' in call_kwargs, (
                    f"BedrockModel was initialized WITHOUT endpoint_url parameter in LocalStack environment. "
                    f"This causes Bedrock calls to be directed to LocalStack (which doesn't implement Bedrock) "
                    f"instead of real AWS Bedrock endpoint. "
                    f"Called with: {call_kwargs}"
                )
                
                # Verify that endpoint_url matches the configured value
                actual_endpoint = call_kwargs['endpoint_url']
                expected_endpoint = config['aws_bedrock_endpoint_url']
                
                assert actual_endpoint == expected_endpoint, (
                    f"BedrockModel endpoint_url mismatch. "
                    f"Expected: {expected_endpoint}, "
                    f"Actual: {actual_endpoint}. "
                    f"In LocalStack environment, BedrockModel must use real AWS Bedrock endpoint "
                    f"(or None for default), not LocalStack endpoint."
                )
                
                # Verify other parameters are correct
                assert call_kwargs['model_id'] == config['bedrock_model_id']
                assert call_kwargs['region_name'] == config['bedrock_region']


def test_bedrock_api_call_fails_with_localstack_endpoint():
    """
    Test that Bedrock API calls fail with NotImplementedError when directed to LocalStack.
    
    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
    
    This test demonstrates the bug: when BedrockModel is initialized without endpoint_url
    in LocalStack environment, Bedrock API calls are directed to LocalStack, which raises
    NotImplementedError because LocalStack doesn't implement Bedrock service.
    
    **EXPECTED OUTCOME ON UNFIXED CODE**: This test documents the bug behavior - 
    NotImplementedError is raised and generic error message is returned.
    
    **EXPECTED OUTCOME ON FIXED CODE**: This test becomes irrelevant because BedrockModel
    will use real AWS endpoint, so LocalStack won't be called for Bedrock operations.
    """
    # Mock settings with LocalStack configuration
    with patch('src.services.strands_agent_service.settings') as mock_settings:
        mock_settings.bedrock_model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'
        mock_settings.bedrock_region = 'us-east-1'
        mock_settings.aws_endpoint_url = 'http://localhost:4566'  # LocalStack
        mock_settings.aws_bedrock_endpoint_url = None  # Not configured (bug condition)
        mock_settings.dynamodb_table = 'fitagent-main'
        
        # Mock BedrockModel to simulate LocalStack NotImplementedError
        with patch('src.services.strands_agent_service.BedrockModel') as MockBedrockModel:
            mock_model_instance = MagicMock()
            MockBedrockModel.return_value = mock_model_instance
            
            # Mock DynamoDBClient
            with patch('src.services.strands_agent_service.DynamoDBClient') as MockDB:
                mock_db = MagicMock()
                mock_db.get_trainer.return_value = {
                    'PK': 'TRAINER#test123',
                    'SK': 'METADATA',
                    'name': 'Test Trainer',
                    'phone_number': '+5511999999999'
                }
                MockDB.return_value = mock_db
                
                # Mock Agent to avoid actual agent creation
                with patch('src.services.strands_agent_service.Agent') as MockAgent:
                    mock_agent = MagicMock()
                    MockAgent.return_value = mock_agent
                    
                    # Configure mock agent to raise NotImplementedError when called
                    mock_agent.side_effect = NotImplementedError(
                        "Bedrock service is not implemented in LocalStack"
                    )
                    
                    # Initialize service and process message
                    service = StrandsAgentService()
                    
                    result = service.process_message(
                        trainer_id='test123',
                        message='Registrar novo aluno João',
                        phone_number='+5511999999999'
                    )
                    
                    # CRITICAL ASSERTION: On unfixed code, NotImplementedError is caught
                    # by generic Exception handler and returns generic Portuguese error message
                    assert result['success'] is False, (
                        "Expected failure due to NotImplementedError from LocalStack"
                    )
                    
                    # The generic error message is returned instead of AI response
                    assert 'error' in result
                    assert 'temporariamente indisponível' in result['error'].lower() or \
                           'erro' in result['error'].lower(), (
                        f"Expected generic Portuguese error message, got: {result.get('error')}"
                    )
                    
                    # This demonstrates the bug: users receive generic error instead of AI response
                    # because Bedrock calls fail when directed to LocalStack


def test_bedrock_endpoint_url_configuration_exists():
    """
    Test that aws_bedrock_endpoint_url configuration exists in settings.
    
    **Validates: Requirements 2.1, 2.2**
    
    This test verifies that the configuration for Bedrock endpoint URL exists,
    but is not being used in BedrockModel initialization (the bug).
    
    **EXPECTED OUTCOME**: This test PASSES on both unfixed and fixed code,
    confirming that the configuration exists but isn't being used (unfixed)
    or is being used correctly (fixed).
    """
    from src.config import settings
    
    # Verify that aws_bedrock_endpoint_url configuration exists
    assert hasattr(settings, 'aws_bedrock_endpoint_url'), (
        "Configuration for aws_bedrock_endpoint_url is missing from settings"
    )
    
    # The configuration exists but is not passed to BedrockModel (the bug)
    # After fix, this configuration will be passed to BedrockModel initialization


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
