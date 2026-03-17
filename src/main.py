"""
Main application entry point for local development.
This module provides a FastAPI application for testing webhook endpoints locally.
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Optional
import json
import os

# Set AWS region before importing handlers
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

app = FastAPI(
    title="FitAgent WhatsApp Assistant",
    description="Multi-tenant SaaS platform for personal trainers",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "fitagent-whatsapp-assistant"}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    """
    Twilio WhatsApp webhook endpoint for local testing.
    
    This endpoint simulates API Gateway and invokes the Lambda handler.
    """
    # Lazy import to avoid module-level boto3 initialization issues
    from src.handlers.webhook_handler import lambda_handler as webhook_lambda_handler
    
    # Get form data
    form_data = await request.form()
    
    # Convert form data to query string format
    body_parts = []
    for key, value in form_data.items():
        body_parts.append(f"{key}={value}")
    body = "&".join(body_parts)
    
    # Get headers
    headers = dict(request.headers)
    
    # Construct API Gateway event
    event = {
        "httpMethod": "POST",
        "headers": headers,
        "body": body,
        "requestContext": {
            "requestId": headers.get("x-request-id", "local-test"),
            "domainName": headers.get("host", "localhost:8000"),
            "path": "/webhook"
        }
    }
    
    # Invoke Lambda handler
    result = webhook_lambda_handler(event, None)
    
    # Return response
    return Response(
        content=result.get("body", ""),
        status_code=result.get("statusCode", 200),
        headers=result.get("headers", {})
    )


@app.post("/test/process-message")
async def test_process_message(
    phone_number: str = Form(...),
    message: str = Form(...),
    message_sid: Optional[str] = Form(None)
) -> dict:
    """
    Test endpoint to directly process a message without going through SQS.
    
    This bypasses the webhook and SQS queue for quick testing.
    """
    # Lazy import to avoid module-level boto3 initialization issues
    from src.handlers.message_processor import lambda_handler as processor_lambda_handler
    
    # Create SQS event format
    message_body = {
        "message_sid": message_sid or "TEST123",
        "from": phone_number,
        "to": "+14155238886",  # Your Twilio number
        "body": message,
        "num_media": 0,
        "media_urls": [],
        "timestamp": "",
        "request_id": "test-request"
    }
    
    sqs_event = {
        "Records": [
            {
                "messageId": "test-msg-id",
                "receiptHandle": "test-receipt",
                "body": json.dumps(message_body),
                "attributes": {
                    "ApproximateReceiveCount": "1"
                },
                "messageAttributes": {},
                "eventSource": "aws:sqs"
            }
        ]
    }
    
    # Process message
    result = processor_lambda_handler(sqs_event, None)
    
    return {
        "status": "processed",
        "result": result,
        "message_body": message_body
    }


# ------------------------------------------------------------------
# Dashboard API routes (local development)
# ------------------------------------------------------------------

def _invoke_dashboard_handler(request: Request, method: str, path: str) -> Response:
    """Build an API Gateway-style event and invoke the dashboard Lambda handler."""
    from src.handlers.dashboard_handler import lambda_handler as dashboard_lambda_handler

    headers = dict(request.headers)
    params = dict(request.query_params)

    event = {
        "httpMethod": method,
        "path": path,
        "headers": headers,
        "queryStringParameters": params if params else None,
        "requestContext": {
            "requestId": "local-dashboard",
            "domainName": headers.get("host", "localhost:8000"),
            "path": path,
        },
    }

    result = dashboard_lambda_handler(event, None)

    return Response(
        content=result.get("body", ""),
        status_code=result.get("statusCode", 200),
        headers=result.get("headers", {}),
    )


@app.get("/dashboard/auth")
async def dashboard_auth(request: Request) -> Response:
    """Dashboard token validation endpoint."""
    return _invoke_dashboard_handler(request, "GET", "/dashboard/auth")


@app.get("/dashboard/metrics")
async def dashboard_metrics(request: Request) -> Response:
    """Dashboard metrics endpoint."""
    return _invoke_dashboard_handler(request, "GET", "/dashboard/metrics")


@app.options("/dashboard/{path:path}")
async def dashboard_options(request: Request, path: str) -> Response:
    """CORS preflight for dashboard routes."""
    return _invoke_dashboard_handler(request, "OPTIONS", f"/dashboard/{path}")


# Mount static website files last (catch-all)
app.mount("/", StaticFiles(directory="static-website", html=True), name="static")
