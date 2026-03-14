"""
Test data generation utilities.

Provides functions for generating valid test data like phone numbers,
datetimes, images, and conversation states.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from io import BytesIO

from src.models.entities import ConversationState, MessageHistoryEntry

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def generate_phone_number(country_code: str = "+55") -> str:
    """
    Generate a valid test phone number.
    
    Args:
        country_code: Country code prefix (default: "+55" for Brazil)
    
    Returns:
        Phone number in E.164 format
    """
    # Generate unique phone number using timestamp and random digits
    timestamp_suffix = str(int(time.time() * 1000))[-9:]
    
    # For Brazil (+55), format is +55 11 9XXXX-XXXX
    if country_code == "+55":
        return f"+5511{timestamp_suffix}"
    
    # For US (+1), format is +1 XXX-XXX-XXXX
    elif country_code == "+1":
        area_code = random.randint(200, 999)
        exchange = random.randint(200, 999)
        line = random.randint(1000, 9999)
        return f"+1{area_code}{exchange}{line}"
    
    # Generic format for other countries
    else:
        return f"{country_code}{timestamp_suffix}"


def generate_future_datetime(
    days_ahead: int = 1,
    hour: int = 10,
    minute: int = 0
) -> datetime:
    """
    Generate a future datetime for session scheduling.
    
    Args:
        days_ahead: Number of days in the future (default: 1)
        hour: Hour of day (default: 10)
        minute: Minute of hour (default: 0)
    
    Returns:
        Future datetime with specified time
    """
    future_date = datetime.utcnow() + timedelta(days=days_ahead)
    return future_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )


def generate_past_datetime(
    days_ago: int = 1,
    hour: int = 10,
    minute: int = 0
) -> datetime:
    """
    Generate a past datetime for historical data.
    
    Args:
        days_ago: Number of days in the past (default: 1)
        hour: Hour of day (default: 10)
        minute: Minute of hour (default: 0)
    
    Returns:
        Past datetime with specified time
    """
    past_date = datetime.utcnow() - timedelta(days=days_ago)
    return past_date.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )


def generate_receipt_image(
    width: int = 800,
    height: int = 600,
    format: str = "JPEG"
) -> bytes:
    """
    Generate a test receipt image.
    
    Args:
        width: Image width in pixels (default: 800)
        height: Image height in pixels (default: 600)
        format: Image format (default: "JPEG")
    
    Returns:
        Image bytes
    
    Raises:
        ImportError: If PIL is not installed
    """
    if not PIL_AVAILABLE:
        raise ImportError("PIL (Pillow) is required for image generation. Install with: pip install Pillow")
    
    # Create a simple colored image
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    
    # Add some colored rectangles to simulate receipt content
    draw = ImageDraw.Draw(img)
    
    # Header
    draw.rectangle([(50, 50), (width - 50, 100)], fill=(200, 200, 200))
    
    # Lines of text
    for i in range(5):
        y = 150 + (i * 60)
        draw.rectangle([(50, y), (width - 50, y + 30)], fill=(220, 220, 220))
    
    # Total amount box
    draw.rectangle([(50, height - 150), (width - 50, height - 100)], fill=(180, 180, 180))
    
    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format=format)
    return buffer.getvalue()


def create_test_conversation_state(
    phone_number: str,
    state: str = "UNKNOWN",
    user_id: Optional[str] = None,
    user_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    add_message_history: bool = False,
    **kwargs
) -> ConversationState:
    """
    Create a test conversation state.
    
    Args:
        phone_number: Phone number in E.164 format
        state: Conversation state (default: "UNKNOWN")
        user_id: User ID (default: None)
        user_type: User type (default: None)
        context: Context dictionary (default: {})
        add_message_history: Whether to add sample message history (default: False)
        **kwargs: Additional fields to override
    
    Returns:
        ConversationState instance
    """
    message_history = []
    
    if add_message_history:
        message_history = [
            MessageHistoryEntry(
                role="user",
                content="Olá",
                timestamp=datetime.utcnow() - timedelta(minutes=5)
            ),
            MessageHistoryEntry(
                role="assistant",
                content="Olá! Como posso ajudar?",
                timestamp=datetime.utcnow() - timedelta(minutes=4)
            )
        ]
    
    # Default TTL: 24 hours from now
    ttl = int((datetime.utcnow() + timedelta(hours=24)).timestamp())
    
    return ConversationState(
        phone_number=phone_number,
        state=state,
        user_id=user_id,
        user_type=user_type,
        context=context or {},
        message_history=message_history,
        ttl=ttl,
        **kwargs
    )


def generate_iso_date(days_offset: int = 0) -> str:
    """
    Generate an ISO date string.
    
    Args:
        days_offset: Number of days to offset from today (negative for past, positive for future)
    
    Returns:
        ISO date string (YYYY-MM-DD)
    """
    date = datetime.utcnow().date() + timedelta(days=days_offset)
    return date.isoformat()


def generate_random_amount(min_amount: float = 50.0, max_amount: float = 500.0) -> float:
    """
    Generate a random payment amount.
    
    Args:
        min_amount: Minimum amount (default: 50.0)
        max_amount: Maximum amount (default: 500.0)
    
    Returns:
        Random amount rounded to 2 decimal places
    """
    amount = random.uniform(min_amount, max_amount)
    return round(amount, 2)


def generate_session_duration() -> int:
    """
    Generate a realistic session duration in minutes.
    
    Returns:
        Duration in minutes (30, 45, 60, 90, or 120)
    """
    return random.choice([30, 45, 60, 90, 120])
