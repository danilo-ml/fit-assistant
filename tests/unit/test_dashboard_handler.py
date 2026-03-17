"""
Unit tests for the Dashboard Lambda handler.

Tests cover: routing, CORS, auth validation, date parsing/defaults,
error responses, and the metrics endpoint.
"""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws
import boto3

from src.handlers.dashboard_handler import (
    CORS_HEADERS,
    _parse_date,
    lambda_handler,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

VALID_TOKEN = "test-admin-token-123"
SECRET_NAME = "fitagent/dashboard-token/local"


def _make_event(
    method="GET",
    path="/dashboard/metrics",
    headers=None,
    query_params=None,
):
    """Build a minimal API Gateway proxy event."""
    if headers is None:
        headers = {"Authorization": f"Bearer {VALID_TOKEN}"}
    return {
        "httpMethod": method,
        "path": path,
        "headers": headers,
        "queryStringParameters": query_params,
        "requestContext": {"requestId": "test-req-id"},
    }


@pytest.fixture
def mock_secrets():
    """Mock Secrets Manager so _get_secret_token returns VALID_TOKEN."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="us-east-1")
        client.create_secret(
            Name=SECRET_NAME,
            SecretString=json.dumps({"token": VALID_TOKEN}),
        )
        with patch("src.handlers.dashboard_handler.boto3.client") as mock_boto:
            mock_boto.return_value = client
            yield client


@pytest.fixture
def mock_metrics_service():
    """Patch DashboardMetricsService.get_all_metrics to return a canned response."""
    with patch("src.handlers.dashboard_handler.DashboardMetricsService") as cls:
        instance = MagicMock()
        cls.return_value = instance
        mock_resp = MagicMock()
        mock_resp.to_dict.return_value = {
            "status": "ok",
            "generated_at": "2024-01-15T10:00:00+00:00",
            "period": {"start_date": "2024-01-01", "end_date": "2024-01-15"},
            "user_metrics": {},
            "session_metrics": {},
            "payment_metrics": {},
            "growth_metrics": {},
            "errors": [],
        }
        mock_resp.errors = []
        instance.get_all_metrics.return_value = mock_resp
        yield instance


@pytest.fixture
def mock_dynamodb_client():
    """Patch DynamoDBClient construction."""
    with patch("src.handlers.dashboard_handler.DynamoDBClient"):
        yield


# ------------------------------------------------------------------
# CORS / OPTIONS
# ------------------------------------------------------------------

class TestCORSAndOptions:
    def test_options_returns_200(self, mock_secrets):
        event = _make_event(method="OPTIONS", path="/dashboard/metrics")
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert "Authorization" in resp["headers"]["Access-Control-Allow-Headers"]

    def test_all_responses_include_cors_headers(self, mock_secrets, mock_metrics_service, mock_dynamodb_client):
        event = _make_event(path="/dashboard/auth")
        resp = lambda_handler(event, None)
        for key in CORS_HEADERS:
            assert key in resp["headers"]


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------

class TestAuth:
    def test_missing_auth_header_returns_401(self, mock_secrets):
        event = _make_event(headers={})
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 401
        body = json.loads(resp["body"])
        assert body["error"] == "Unauthorized"
        assert "Missing or invalid" in body["message"]

    def test_invalid_token_returns_401(self, mock_secrets):
        event = _make_event(headers={"Authorization": "Bearer wrong-token"})
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 401

    def test_no_bearer_prefix_returns_401(self, mock_secrets):
        event = _make_event(headers={"Authorization": VALID_TOKEN})
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 401

    def test_valid_token_auth_endpoint(self, mock_secrets):
        event = _make_event(path="/dashboard/auth")
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["valid"] is True

    def test_secrets_manager_unavailable_returns_500(self):
        with patch("src.handlers.dashboard_handler.boto3.client") as mock_boto:
            mock_boto.return_value.get_secret_value.side_effect = Exception("Connection refused")
            event = _make_event(path="/dashboard/auth")
            resp = lambda_handler(event, None)
            assert resp["statusCode"] == 500
            body = json.loads(resp["body"])
            assert body["message"] == "Authentication service unavailable"

    def test_lowercase_authorization_header(self, mock_secrets):
        event = _make_event(
            path="/dashboard/auth",
            headers={"authorization": f"Bearer {VALID_TOKEN}"},
        )
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200


# ------------------------------------------------------------------
# Date parsing
# ------------------------------------------------------------------

class TestDateParsing:
    def test_valid_date(self):
        assert _parse_date("2024-01-15") == date(2024, 1, 15)

    def test_invalid_format(self):
        assert _parse_date("01-15-2024") is None
        assert _parse_date("2024/01/15") is None
        assert _parse_date("not-a-date") is None

    def test_invalid_calendar_date(self):
        assert _parse_date("2024-02-30") is None

    def test_no_params_defaults_to_last_30_days(
        self, mock_secrets, mock_metrics_service, mock_dynamodb_client
    ):
        event = _make_event(query_params=None)
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        # Verify the service was called with the correct default dates
        today = date.today()
        expected_start = (today - timedelta(days=30)).isoformat()
        expected_end = today.isoformat()
        mock_metrics_service.get_all_metrics.assert_called_once_with(
            expected_start, expected_end
        )

    def test_invalid_date_format_returns_400(self, mock_secrets):
        event = _make_event(query_params={"start_date": "bad", "end_date": "2024-01-15"})
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "Invalid date format" in body["message"]

    def test_start_after_end_returns_400(self, mock_secrets):
        event = _make_event(
            query_params={"start_date": "2024-02-01", "end_date": "2024-01-01"}
        )
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "start_date must be before" in body["message"]

    def test_range_exceeds_90_days_returns_400(self, mock_secrets):
        event = _make_event(
            query_params={"start_date": "2024-01-01", "end_date": "2024-06-01"}
        )
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "90 days" in body["message"]

    def test_equal_start_end_is_valid(
        self, mock_secrets, mock_metrics_service, mock_dynamodb_client
    ):
        event = _make_event(
            query_params={"start_date": "2024-01-15", "end_date": "2024-01-15"}
        )
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200


# ------------------------------------------------------------------
# Metrics endpoint
# ------------------------------------------------------------------

class TestMetricsEndpoint:
    def test_successful_metrics_response(
        self, mock_secrets, mock_metrics_service, mock_dynamodb_client
    ):
        event = _make_event(
            query_params={"start_date": "2024-01-01", "end_date": "2024-01-15"}
        )
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "ok"
        assert "user_metrics" in body
        assert "session_metrics" in body
        assert "payment_metrics" in body
        assert "growth_metrics" in body
        assert "errors" in body

    def test_complete_failure_returns_500(self, mock_secrets, mock_dynamodb_client):
        with patch("src.handlers.dashboard_handler.DashboardMetricsService") as cls:
            instance = MagicMock()
            cls.return_value = instance
            mock_resp = MagicMock()
            mock_resp.errors = ["user_metrics", "session_metrics", "payment_metrics", "growth_metrics"]
            mock_resp.to_dict.return_value = {"status": "partial", "errors": mock_resp.errors}
            instance.get_all_metrics.return_value = mock_resp
            event = _make_event(
                query_params={"start_date": "2024-01-01", "end_date": "2024-01-15"}
            )
            resp = lambda_handler(event, None)
            assert resp["statusCode"] == 500
            body = json.loads(resp["body"])
            assert body["error"] == "Internal Server Error"

    def test_service_exception_returns_500(self, mock_secrets, mock_dynamodb_client):
        with patch("src.handlers.dashboard_handler.DashboardMetricsService") as cls:
            instance = MagicMock()
            cls.return_value = instance
            instance.get_all_metrics.side_effect = Exception("DynamoDB down")
            event = _make_event(
                query_params={"start_date": "2024-01-01", "end_date": "2024-01-15"}
            )
            resp = lambda_handler(event, None)
            assert resp["statusCode"] == 500
            body = json.loads(resp["body"])
            assert body["message"] == "Failed to retrieve metrics"


# ------------------------------------------------------------------
# Routing
# ------------------------------------------------------------------

class TestRouting:
    def test_unknown_route_returns_404(self, mock_secrets):
        event = _make_event(path="/dashboard/unknown")
        resp = lambda_handler(event, None)
        assert resp["statusCode"] == 404
