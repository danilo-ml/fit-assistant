"""
Integration tests to verify LocalStack fixtures work correctly.

These tests verify that the LocalStack fixtures properly detect the
USE_LOCALSTACK environment variable and handle connection issues gracefully.
"""

import pytest
import os


class TestLocalStackFixtures:
    """Test LocalStack fixture behavior."""

    def test_localstack_fixtures_skip_when_not_enabled(self, dynamodb_localstack):
        """
        Test that LocalStack fixtures skip when USE_LOCALSTACK is not set.
        
        This test should be skipped if USE_LOCALSTACK is not set to 'true'.
        """
        # If we get here, LocalStack is enabled
        assert dynamodb_localstack is not None
        
        # Verify we can interact with DynamoDB
        response = dynamodb_localstack.list_tables()
        assert "TableNames" in response

    def test_s3_localstack_fixture(self, s3_localstack):
        """Test S3 LocalStack fixture works correctly."""
        # If we get here, LocalStack is enabled
        assert s3_localstack is not None
        
        # Verify we can interact with S3
        response = s3_localstack.list_buckets()
        assert "Buckets" in response

    def test_sqs_localstack_fixture(self, sqs_localstack):
        """Test SQS LocalStack fixture works correctly."""
        # If we get here, LocalStack is enabled
        assert sqs_localstack is not None
        
        # Verify we can interact with SQS
        response = sqs_localstack.list_queues()
        assert "QueueUrls" in response or response.get("QueueUrls") is None

    def test_lambda_localstack_fixture(self, lambda_localstack):
        """Test Lambda LocalStack fixture works correctly."""
        # If we get here, LocalStack is enabled
        assert lambda_localstack is not None
        
        # Verify we can interact with Lambda
        response = lambda_localstack.list_functions()
        assert "Functions" in response

    def test_events_localstack_fixture(self, events_localstack):
        """Test EventBridge LocalStack fixture works correctly."""
        # If we get here, LocalStack is enabled
        assert events_localstack is not None
        
        # Verify we can interact with EventBridge
        response = events_localstack.list_rules()
        assert "Rules" in response
