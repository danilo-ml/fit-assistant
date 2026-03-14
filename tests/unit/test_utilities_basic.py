"""
Basic tests to verify test utilities work correctly.

These tests validate that the test data generators and assertion helpers
are properly configured and functional.
"""

import pytest
from datetime import datetime, timedelta

from tests.utils.test_data import (
    generate_phone_number,
    generate_future_datetime,
    generate_past_datetime,
    generate_receipt_image,
    create_test_conversation_state,
    generate_iso_date,
    generate_random_amount,
    generate_session_duration
)

from tests.utils.assertions import (
    assert_portuguese_message,
    assert_valid_phone_number,
    assert_valid_iso_datetime,
    assert_valid_uuid,
    assert_dict_contains
)


@pytest.mark.unit
def test_generate_phone_number():
    """Test phone number generation."""
    phone = generate_phone_number()
    assert phone.startswith("+55")
    assert len(phone) == 14  # +55 + 11 digits


@pytest.mark.unit
def test_generate_phone_number_us():
    """Test US phone number generation."""
    phone = generate_phone_number(country_code="+1")
    assert phone.startswith("+1")
    assert len(phone) == 12  # +1 + 10 digits


@pytest.mark.unit
def test_generate_future_datetime():
    """Test future datetime generation."""
    future = generate_future_datetime(days_ahead=2, hour=14, minute=30)
    
    assert future > datetime.utcnow()
    assert future.hour == 14
    assert future.minute == 30


@pytest.mark.unit
def test_generate_past_datetime():
    """Test past datetime generation."""
    past = generate_past_datetime(days_ago=2, hour=10, minute=0)
    
    assert past < datetime.utcnow()
    assert past.hour == 10
    assert past.minute == 0


@pytest.mark.unit
@pytest.mark.skipif(not hasattr(pytest, 'PIL_AVAILABLE'), reason="PIL not installed")
def test_generate_receipt_image():
    """Test receipt image generation."""
    try:
        image_bytes = generate_receipt_image()
        assert isinstance(image_bytes, bytes)
        assert len(image_bytes) > 0
    except ImportError:
        pytest.skip("PIL not available")


@pytest.mark.unit
def test_create_test_conversation_state():
    """Test conversation state creation."""
    state = create_test_conversation_state(
        phone_number="+5511999999999",
        state="TRAINER_MENU",
        user_id="test123"
    )
    
    assert state.phone_number == "+5511999999999"
    assert state.state == "TRAINER_MENU"
    assert state.user_id == "test123"


@pytest.mark.unit
def test_generate_iso_date():
    """Test ISO date generation."""
    today = generate_iso_date()
    tomorrow = generate_iso_date(days_offset=1)
    yesterday = generate_iso_date(days_offset=-1)
    
    assert len(today) == 10  # YYYY-MM-DD
    assert tomorrow > today
    assert yesterday < today


@pytest.mark.unit
def test_generate_random_amount():
    """Test random amount generation."""
    amount = generate_random_amount(min_amount=100.0, max_amount=200.0)
    
    assert 100.0 <= amount <= 200.0
    assert isinstance(amount, float)


@pytest.mark.unit
def test_generate_session_duration():
    """Test session duration generation."""
    duration = generate_session_duration()
    
    assert duration in [30, 45, 60, 90, 120]


@pytest.mark.unit
def test_assert_portuguese_message_valid():
    """Test Portuguese message assertion with valid message."""
    # Should not raise
    assert_portuguese_message("Olá, como você está?")
    assert_portuguese_message("Seu treino está agendado para amanhã.")


@pytest.mark.unit
def test_assert_portuguese_message_invalid():
    """Test Portuguese message assertion with English message."""
    with pytest.raises(AssertionError):
        assert_portuguese_message("Hello, how are you?")


@pytest.mark.unit
def test_assert_valid_phone_number():
    """Test phone number validation."""
    # Should not raise
    assert_valid_phone_number("+5511999999999")
    assert_valid_phone_number("+12025551234")


@pytest.mark.unit
def test_assert_valid_phone_number_invalid():
    """Test phone number validation with invalid number."""
    with pytest.raises(AssertionError):
        assert_valid_phone_number("11999999999")  # Missing +


@pytest.mark.unit
def test_assert_valid_iso_datetime():
    """Test ISO datetime validation."""
    # Should not raise
    assert_valid_iso_datetime("2024-12-01T10:00:00")
    assert_valid_iso_datetime("2024-12-01T10:00:00Z")


@pytest.mark.unit
def test_assert_valid_iso_datetime_invalid():
    """Test ISO datetime validation with invalid datetime."""
    with pytest.raises(AssertionError):
        assert_valid_iso_datetime("not-a-datetime")


@pytest.mark.unit
def test_assert_valid_uuid():
    """Test UUID validation."""
    from uuid import uuid4
    
    # Should not raise
    assert_valid_uuid(str(uuid4()))
    assert_valid_uuid("550e8400-e29b-41d4-a716-446655440000")


@pytest.mark.unit
def test_assert_valid_uuid_invalid():
    """Test UUID validation with invalid UUID."""
    with pytest.raises(AssertionError):
        assert_valid_uuid("not-a-uuid")


@pytest.mark.unit
def test_assert_dict_contains():
    """Test dictionary contains assertion."""
    actual = {"a": 1, "b": 2, "c": 3}
    expected = {"a": 1, "b": 2}
    
    # Should not raise
    assert_dict_contains(actual, expected)


@pytest.mark.unit
def test_assert_dict_contains_missing_key():
    """Test dictionary contains assertion with missing key."""
    actual = {"a": 1, "b": 2}
    expected = {"a": 1, "c": 3}
    
    with pytest.raises(AssertionError):
        assert_dict_contains(actual, expected)
