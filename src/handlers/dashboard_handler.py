"""
Dashboard handler Lambda function for the Admin Dashboard API.

Exposes two routes behind API Gateway:
  GET /dashboard/auth    — validate the admin token
  GET /dashboard/metrics — return aggregated platform metrics

Authentication uses a pre-shared token stored in AWS Secrets Manager.

Requirements: 1.3, 2.3, 7.1, 7.2, 7.3, 7.5, 7.6, 7.7, 8.1, 8.2, 8.3
"""

import json
import re
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from src.models.dynamodb_client import DynamoDBClient
from src.services.dashboard_metrics import DashboardMetricsService
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Date format expected in query parameters
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_RANGE_DAYS = 90

# CORS headers applied to every response
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Entry point for the Dashboard Lambda.

    Routes:
      OPTIONS *                — CORS preflight
      GET /dashboard/auth      — token validation
      GET /dashboard/metrics   — aggregated metrics
    """
    method = event.get("httpMethod", "")
    path = event.get("path", "")

    logger.info("Dashboard request", method=method, path=path)

    # Handle CORS preflight
    if method == "OPTIONS":
        return _response(200, {"message": "OK"})

    # --- Auth gate ---
    try:
        if not _validate_token(event):
            return _error_response(
                401,
                "Unauthorized",
                "Missing or invalid authorization token",
            )
    except _SecretsManagerError:
        return _error_response(
            500,
            "Internal Server Error",
            "Authentication service unavailable",
        )

    # --- Routing ---
    if path.rstrip("/") == "/dashboard/auth":
        return _response(200, {"valid": True})

    if path.rstrip("/") == "/dashboard/metrics":
        return _handle_metrics(event)

    return _error_response(404, "Not Found", "Route not found")


# ------------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------------

class _SecretsManagerError(Exception):
    """Raised when Secrets Manager is unreachable or the secret is missing."""


def _get_secret_token() -> str:
    """Read the dashboard token from Secrets Manager.

    Raises ``_SecretsManagerError`` if the secret cannot be retrieved.
    """
    try:
        from src.config import settings

        secret_name = getattr(
            settings,
            "dashboard_token_secret_name",
            None,
        ) or f"fitagent/dashboard-token/{settings.environment}"

        client = boto3.client(
            "secretsmanager",
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
        )
        response = client.get_secret_value(SecretId=secret_name)
        secret_string = response["SecretString"]

        # The secret may be a plain string or a JSON object with a "token" key
        try:
            parsed = json.loads(secret_string)
            if isinstance(parsed, dict):
                return parsed.get("token", secret_string)
        except (json.JSONDecodeError, TypeError):
            pass
        return secret_string
    except Exception as exc:
        logger.error("Secrets Manager error", error=str(exc))
        raise _SecretsManagerError(str(exc)) from exc


def _validate_token(event: Dict[str, Any]) -> bool:
    """Compare the Bearer token in the Authorization header to the stored secret."""
    headers = event.get("headers") or {}
    # API Gateway may normalise header names to lowercase
    auth_header = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth_header.startswith("Bearer "):
        return False
    provided_token = auth_header[len("Bearer "):]
    stored_token = _get_secret_token()
    return provided_token == stored_token


# ------------------------------------------------------------------
# Metrics endpoint
# ------------------------------------------------------------------

def _handle_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse date params, call the metrics service, return the response."""
    params = event.get("queryStringParameters") or {}

    start_str = params.get("start_date")
    end_str = params.get("end_date")

    # --- Defaults: last 30 days ---
    today = date.today()
    if not start_str and not end_str:
        end_str = today.isoformat()
        start_str = (today - timedelta(days=30)).isoformat()
    elif not start_str:
        # end_date provided but not start_date
        parsed_end = _parse_date(end_str)
        if parsed_end is None:
            return _error_response(
                400, "Bad Request", "Invalid date format. Use YYYY-MM-DD"
            )
        start_str = (parsed_end - timedelta(days=30)).isoformat()
    elif not end_str:
        # start_date provided but not end_date
        parsed_start = _parse_date(start_str)
        if parsed_start is None:
            return _error_response(
                400, "Bad Request", "Invalid date format. Use YYYY-MM-DD"
            )
        end_str = today.isoformat()

    # --- Validate format ---
    parsed_start = _parse_date(start_str)
    parsed_end = _parse_date(end_str)

    if parsed_start is None or parsed_end is None:
        return _error_response(
            400, "Bad Request", "Invalid date format. Use YYYY-MM-DD"
        )

    # --- Validate range ---
    if parsed_start > parsed_end:
        return _error_response(
            400, "Bad Request", "start_date must be before or equal to end_date"
        )

    if (parsed_end - parsed_start).days > _MAX_RANGE_DAYS:
        return _error_response(
            400, "Bad Request", "Date range cannot exceed 90 days"
        )

    # --- Fetch metrics ---
    try:
        db_client = DynamoDBClient()
        service = DashboardMetricsService(db_client)
        dashboard_response = service.get_all_metrics(start_str, end_str)
    except Exception as exc:
        logger.error("Metrics retrieval failed", error=str(exc))
        return _error_response(
            500, "Internal Server Error", "Failed to retrieve metrics"
        )

    # If all four sections failed, treat as complete failure
    if len(dashboard_response.errors) == 4:
        return _error_response(
            500, "Internal Server Error", "Failed to retrieve metrics"
        )

    return _response(200, dashboard_response.to_dict())


# ------------------------------------------------------------------
# Date parsing
# ------------------------------------------------------------------

def _parse_date(value: str) -> Optional[date]:
    """Parse a YYYY-MM-DD string into a ``date`` object, or return ``None``."""
    if not _DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# ------------------------------------------------------------------
# Response helpers
# ------------------------------------------------------------------

def _response(status_code: int, body: Any) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def _error_response(status_code: int, error: str, message: str) -> Dict[str, Any]:
    return _response(status_code, {"error": error, "message": message})
