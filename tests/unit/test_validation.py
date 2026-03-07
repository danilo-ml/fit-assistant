"""
Unit tests for phone number validation utilities.
"""

import pytest
from src.utils.validation import PhoneNumberValidator, InputSanitizer


class TestPhoneNumberValidator:
    """Test suite for PhoneNumberValidator class."""
    
    # Valid E.164 format tests
    def test_validate_valid_us_number(self):
        """Test validation of valid US phone number."""
        assert PhoneNumberValidator.validate("+14155552671") is True
    
    def test_validate_valid_uk_number(self):
        """Test validation of valid UK phone number."""
        assert PhoneNumberValidator.validate("+442071838750") is True
    
    def test_validate_valid_brazil_number(self):
        """Test validation of valid Brazil phone number."""
        assert PhoneNumberValidator.validate("+5511987654321") is True
    
    def test_validate_valid_short_number(self):
        """Test validation of valid short international number."""
        assert PhoneNumberValidator.validate("+12345") is True
    
    def test_validate_valid_max_length_number(self):
        """Test validation of maximum length E.164 number (15 digits)."""
        assert PhoneNumberValidator.validate("+123456789012345") is True
    
    # Invalid E.164 format tests
    def test_validate_missing_plus_prefix(self):
        """Test validation fails for number without + prefix."""
        assert PhoneNumberValidator.validate("14155552671") is False
    
    def test_validate_with_spaces(self):
        """Test validation fails for number with spaces."""
        assert PhoneNumberValidator.validate("+1 415 555 2671") is False
    
    def test_validate_with_dashes(self):
        """Test validation fails for number with dashes."""
        assert PhoneNumberValidator.validate("+1-415-555-2671") is False
    
    def test_validate_with_parentheses(self):
        """Test validation fails for number with parentheses."""
        assert PhoneNumberValidator.validate("+1(415)555-2671") is False
    
    def test_validate_too_long(self):
        """Test validation fails for number exceeding 15 digits."""
        assert PhoneNumberValidator.validate("+1234567890123456") is False
    
    def test_validate_too_short(self):
        """Test validation fails for number with only country code."""
        assert PhoneNumberValidator.validate("+1") is False
    
    def test_validate_starts_with_zero(self):
        """Test validation fails for number starting with 0 after +."""
        assert PhoneNumberValidator.validate("+0123456789") is False
    
    def test_validate_empty_string(self):
        """Test validation fails for empty string."""
        assert PhoneNumberValidator.validate("") is False
    
    def test_validate_none(self):
        """Test validation fails for None."""
        assert PhoneNumberValidator.validate(None) is False
    
    def test_validate_non_string(self):
        """Test validation fails for non-string input."""
        assert PhoneNumberValidator.validate(14155552671) is False
    
    def test_validate_with_letters(self):
        """Test validation fails for number with letters."""
        assert PhoneNumberValidator.validate("+1415555CALL") is False
    
    def test_validate_with_special_chars(self):
        """Test validation fails for number with special characters."""
        assert PhoneNumberValidator.validate("+1-415-555-2671") is False
    
    # Normalize method tests - valid inputs
    def test_normalize_us_with_parentheses_and_dashes(self):
        """Test normalization of US number with (XXX) XXX-XXXX format."""
        result = PhoneNumberValidator.normalize("(415) 555-2671")
        assert result == "+14155552671"
    
    def test_normalize_us_with_dashes(self):
        """Test normalization of US number with XXX-XXX-XXXX format."""
        result = PhoneNumberValidator.normalize("415-555-2671")
        assert result == "+14155552671"
    
    def test_normalize_us_with_spaces(self):
        """Test normalization of US number with spaces."""
        result = PhoneNumberValidator.normalize("415 555 2671")
        assert result == "+14155552671"
    
    def test_normalize_us_with_dots(self):
        """Test normalization of US number with dots."""
        result = PhoneNumberValidator.normalize("415.555.2671")
        assert result == "+14155552671"
    
    def test_normalize_already_e164_with_spaces(self):
        """Test normalization of E.164 number with spaces."""
        result = PhoneNumberValidator.normalize("+1 415 555 2671")
        assert result == "+14155552671"
    
    def test_normalize_with_country_code_no_plus(self):
        """Test normalization of number with country code but no + prefix."""
        result = PhoneNumberValidator.normalize("14155552671")
        assert result == "+14155552671"
    
    def test_normalize_without_country_code(self):
        """Test normalization adds default country code."""
        result = PhoneNumberValidator.normalize("4155552671")
        assert result == "+14155552671"
    
    def test_normalize_already_valid_e164(self):
        """Test normalization of already valid E.164 number."""
        result = PhoneNumberValidator.normalize("+14155552671")
        assert result == "+14155552671"
    
    def test_normalize_uk_number(self):
        """Test normalization of UK number."""
        result = PhoneNumberValidator.normalize("+44 20 7183 8750")
        assert result == "+442071838750"
    
    def test_normalize_brazil_number(self):
        """Test normalization of Brazil number."""
        result = PhoneNumberValidator.normalize("+55 11 98765-4321")
        assert result == "+5511987654321"
    
    def test_normalize_with_custom_country_code(self):
        """Test normalization with custom default country code."""
        result = PhoneNumberValidator.normalize("2071838750", default_country_code="44")
        assert result == "+442071838750"
    
    def test_normalize_mixed_formatting(self):
        """Test normalization with mixed formatting characters."""
        result = PhoneNumberValidator.normalize("+1 (415) 555-2671")
        assert result == "+14155552671"
    
    # Normalize method tests - invalid inputs
    def test_normalize_empty_string(self):
        """Test normalization returns None for empty string."""
        result = PhoneNumberValidator.normalize("")
        assert result is None
    
    def test_normalize_none(self):
        """Test normalization returns None for None input."""
        result = PhoneNumberValidator.normalize(None)
        assert result is None
    
    def test_normalize_non_string(self):
        """Test normalization returns None for non-string input."""
        result = PhoneNumberValidator.normalize(4155552671)
        assert result is None
    
    def test_normalize_too_long(self):
        """Test normalization returns None for number exceeding max length."""
        result = PhoneNumberValidator.normalize("+1234567890123456")
        assert result is None
    
    def test_normalize_with_letters(self):
        """Test normalization returns None for number with letters."""
        result = PhoneNumberValidator.normalize("415-555-CALL")
        assert result is None
    
    def test_normalize_only_special_chars(self):
        """Test normalization returns None for only special characters."""
        result = PhoneNumberValidator.normalize("---()...")
        assert result is None
    
    # is_valid_e164 alias method tests
    def test_is_valid_e164_valid_number(self):
        """Test is_valid_e164 alias method with valid number."""
        assert PhoneNumberValidator.is_valid_e164("+14155552671") is True
    
    def test_is_valid_e164_invalid_number(self):
        """Test is_valid_e164 alias method with invalid number."""
        assert PhoneNumberValidator.is_valid_e164("4155552671") is False
    
    # Edge cases
    def test_normalize_whitespace_only(self):
        """Test normalization returns None for whitespace-only string."""
        result = PhoneNumberValidator.normalize("   ")
        assert result is None
    
    def test_validate_plus_only(self):
        """Test validation fails for just + character."""
        assert PhoneNumberValidator.validate("+") is False
    
    def test_normalize_international_format_with_leading_zeros(self):
        """Test normalization handles numbers with leading zeros after country code."""
        # Some countries have leading zeros in local format
        # For example, UK: 020 7183 8750 with country code becomes +44 020 7183 8750
        result = PhoneNumberValidator.normalize("+44 020 7183 8750")
        # The normalization removes spaces but keeps the 0 - this creates an invalid E.164
        # because country codes cannot start with 0, but the full number +4402071838750 is valid
        assert result == "+4402071838750"
    
    def test_normalize_very_short_number(self):
        """Test normalization handles very short number."""
        # "123" starts with "1" so it's treated as having country code already
        # It becomes "+123" which is technically valid E.164 (minimum 4 chars: +[1-9][digit][digit])
        result = PhoneNumberValidator.normalize("123")
        assert result == "+123"
    
    def test_validate_with_extension(self):
        """Test validation fails for number with extension."""
        assert PhoneNumberValidator.validate("+14155552671x123") is False
    
    def test_normalize_removes_all_formatting(self):
        """Test normalization removes all common formatting characters."""
        result = PhoneNumberValidator.normalize("(415) 555-2671")
        assert result == "+14155552671"
        assert " " not in result
        assert "-" not in result
        assert "(" not in result
        assert ")" not in result
        assert "." not in result



class TestInputSanitizer:
    """Test suite for InputSanitizer class."""
    
    # sanitize_string tests - HTML tag removal
    def test_sanitize_string_removes_script_tags(self):
        """Test that script tags are removed (content is kept by bleach)."""
        result = InputSanitizer.sanitize_string("<script>alert('xss')</script>Hello")
        # bleach.clean with strip=True removes tags but keeps content
        assert result == "alert('xss')Hello"
    
    def test_sanitize_string_removes_html_tags(self):
        """Test that HTML tags are removed."""
        result = InputSanitizer.sanitize_string("<b>Bold</b> <i>Italic</i>")
        assert result == "Bold Italic"
    
    def test_sanitize_string_removes_nested_tags(self):
        """Test that nested HTML tags are removed."""
        result = InputSanitizer.sanitize_string("<div><p><span>Text</span></p></div>")
        assert result == "Text"
    
    def test_sanitize_string_removes_img_tags(self):
        """Test that img tags are removed."""
        result = InputSanitizer.sanitize_string('<img src="evil.jpg" onerror="alert(1)">Text')
        assert result == "Text"
    
    def test_sanitize_string_removes_link_tags(self):
        """Test that link tags are removed."""
        result = InputSanitizer.sanitize_string('<a href="http://evil.com">Click</a>')
        assert result == "Click"
    
    def test_sanitize_string_removes_style_tags(self):
        """Test that style tags are removed (content is kept by bleach)."""
        result = InputSanitizer.sanitize_string("<style>body{display:none}</style>Text")
        assert result == "body{display:none}Text"
    
    def test_sanitize_string_removes_iframe_tags(self):
        """Test that iframe tags are removed."""
        result = InputSanitizer.sanitize_string('<iframe src="evil.com"></iframe>Safe')
        assert result == "Safe"
    
    # sanitize_string tests - whitespace handling
    def test_sanitize_string_strips_leading_whitespace(self):
        """Test that leading whitespace is stripped."""
        result = InputSanitizer.sanitize_string("   Hello")
        assert result == "Hello"
    
    def test_sanitize_string_strips_trailing_whitespace(self):
        """Test that trailing whitespace is stripped."""
        result = InputSanitizer.sanitize_string("Hello   ")
        assert result == "Hello"
    
    def test_sanitize_string_strips_both_whitespace(self):
        """Test that both leading and trailing whitespace is stripped."""
        result = InputSanitizer.sanitize_string("   Hello World   ")
        assert result == "Hello World"
    
    def test_sanitize_string_preserves_internal_whitespace(self):
        """Test that internal whitespace is preserved."""
        result = InputSanitizer.sanitize_string("Hello   World")
        assert result == "Hello   World"
    
    # sanitize_string tests - length truncation
    def test_sanitize_string_truncates_long_string(self):
        """Test that strings exceeding max_length are truncated."""
        long_string = "A" * 2000
        result = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) == 100
        assert result == "A" * 100
    
    def test_sanitize_string_default_max_length(self):
        """Test that default max_length is 1000."""
        long_string = "B" * 1500
        result = InputSanitizer.sanitize_string(long_string)
        assert len(result) == 1000
        assert result == "B" * 1000
    
    def test_sanitize_string_custom_max_length(self):
        """Test that custom max_length is respected."""
        result = InputSanitizer.sanitize_string("Hello World", max_length=5)
        assert result == "Hello"
    
    def test_sanitize_string_no_truncation_when_under_limit(self):
        """Test that strings under max_length are not truncated."""
        result = InputSanitizer.sanitize_string("Short", max_length=100)
        assert result == "Short"
    
    # sanitize_string tests - edge cases
    def test_sanitize_string_empty_string(self):
        """Test sanitization of empty string."""
        result = InputSanitizer.sanitize_string("")
        assert result == ""
    
    def test_sanitize_string_only_whitespace(self):
        """Test sanitization of whitespace-only string."""
        result = InputSanitizer.sanitize_string("   ")
        assert result == ""
    
    def test_sanitize_string_only_html_tags(self):
        """Test sanitization of string with only HTML tags."""
        result = InputSanitizer.sanitize_string("<div></div><span></span>")
        assert result == ""
    
    def test_sanitize_string_non_string_input(self):
        """Test that non-string inputs are converted to strings."""
        result = InputSanitizer.sanitize_string(12345)
        assert result == "12345"
    
    def test_sanitize_string_none_input(self):
        """Test that None input is converted to string."""
        result = InputSanitizer.sanitize_string(None)
        assert result == "None"
    
    def test_sanitize_string_unicode_characters(self):
        """Test that unicode characters are preserved."""
        result = InputSanitizer.sanitize_string("Hello 世界 🌍")
        assert result == "Hello 世界 🌍"
    
    def test_sanitize_string_special_characters(self):
        """Test that special characters are preserved."""
        result = InputSanitizer.sanitize_string("Price: $100.50 (50% off!)")
        assert result == "Price: $100.50 (50% off!)"
    
    def test_sanitize_string_newlines_preserved(self):
        """Test that newlines are preserved."""
        result = InputSanitizer.sanitize_string("Line 1\nLine 2\nLine 3")
        assert result == "Line 1\nLine 2\nLine 3"
    
    def test_sanitize_string_sql_injection_attempt(self):
        """Test that SQL injection attempts are handled safely."""
        result = InputSanitizer.sanitize_string("'; DROP TABLE users; --")
        assert result == "'; DROP TABLE users; --"
        # Note: This doesn't prevent SQL injection - that's handled by parameterized queries
        # This just ensures the string is cleaned of HTML
    
    def test_sanitize_string_javascript_injection_attempt(self):
        """Test that JavaScript injection attempts are cleaned (tags removed, content kept)."""
        result = InputSanitizer.sanitize_string("<script>document.cookie</script>")
        assert result == "document.cookie"
    
    def test_sanitize_string_event_handler_injection(self):
        """Test that event handler injection is cleaned."""
        result = InputSanitizer.sanitize_string('<div onclick="alert(1)">Click</div>')
        assert result == "Click"
    
    # sanitize_tool_parameters tests - basic functionality
    def test_sanitize_tool_parameters_string_values(self):
        """Test sanitization of dictionary with string values."""
        params = {
            'name': '<b>John Doe</b>',
            'email': '<script>alert()</script>john@example.com'
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'name': 'John Doe',
            'email': 'alert()john@example.com'
        }
    
    def test_sanitize_tool_parameters_mixed_types(self):
        """Test sanitization preserves non-string types."""
        params = {
            'name': '<b>John</b>',
            'age': 25,
            'height': 5.9,
            'active': True,
            'notes': None
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'name': 'John',
            'age': 25,
            'height': 5.9,
            'active': True,
            'notes': None
        }
    
    def test_sanitize_tool_parameters_empty_dict(self):
        """Test sanitization of empty dictionary."""
        result = InputSanitizer.sanitize_tool_parameters({})
        assert result == {}
    
    # sanitize_tool_parameters tests - nested structures
    def test_sanitize_tool_parameters_nested_dict(self):
        """Test sanitization of nested dictionaries."""
        params = {
            'user': {
                'name': '<b>John</b>',
                'address': {
                    'street': '<script>alert()</script>Main St',
                    'city': '<i>Boston</i>'
                }
            }
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'user': {
                'name': 'John',
                'address': {
                    'street': 'alert()Main St',
                    'city': 'Boston'
                }
            }
        }
    
    def test_sanitize_tool_parameters_list_of_strings(self):
        """Test sanitization of list containing strings."""
        params = {
            'tags': ['<b>tag1</b>', '<script>tag2</script>', 'tag3']
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'tags': ['tag1', 'tag2', 'tag3']
        }
    
    def test_sanitize_tool_parameters_list_of_mixed_types(self):
        """Test sanitization of list with mixed types."""
        params = {
            'items': ['<b>text</b>', 123, True, None, 45.6]
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'items': ['text', 123, True, None, 45.6]
        }
    
    def test_sanitize_tool_parameters_list_of_dicts(self):
        """Test sanitization of list containing dictionaries."""
        params = {
            'students': [
                {'name': '<b>Alice</b>', 'age': 20},
                {'name': '<i>Bob</i>', 'age': 22}
            ]
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'students': [
                {'name': 'Alice', 'age': 20},
                {'name': 'Bob', 'age': 22}
            ]
        }
    
    def test_sanitize_tool_parameters_deeply_nested(self):
        """Test sanitization of deeply nested structures."""
        params = {
            'level1': {
                'level2': {
                    'level3': {
                        'data': '<script>evil</script>safe',
                        'items': ['<b>a</b>', '<i>b</i>']
                    }
                }
            }
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'level1': {
                'level2': {
                    'level3': {
                        'data': 'evilsafe',
                        'items': ['a', 'b']
                    }
                }
            }
        }
    
    # sanitize_tool_parameters tests - edge cases
    def test_sanitize_tool_parameters_non_dict_input(self):
        """Test that non-dict input is returned unchanged."""
        result = InputSanitizer.sanitize_tool_parameters("not a dict")
        assert result == "not a dict"
    
    def test_sanitize_tool_parameters_none_input(self):
        """Test that None input is returned unchanged."""
        result = InputSanitizer.sanitize_tool_parameters(None)
        assert result is None
    
    def test_sanitize_tool_parameters_empty_list(self):
        """Test sanitization with empty list value."""
        params = {'items': []}
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {'items': []}
    
    def test_sanitize_tool_parameters_empty_nested_dict(self):
        """Test sanitization with empty nested dictionary."""
        params = {'data': {}}
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {'data': {}}
    
    # sanitize_tool_parameters tests - real-world scenarios
    def test_sanitize_tool_parameters_student_registration(self):
        """Test sanitization of student registration parameters."""
        params = {
            'name': '<script>alert("xss")</script>John Doe',
            'phone_number': '+14155552671',
            'email': 'john@example.com',
            'training_goal': '<b>Lose weight</b> and <i>build muscle</i>'
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'name': 'alert("xss")John Doe',
            'phone_number': '+14155552671',
            'email': 'john@example.com',
            'training_goal': 'Lose weight and build muscle'
        }
    
    def test_sanitize_tool_parameters_session_scheduling(self):
        """Test sanitization of session scheduling parameters."""
        params = {
            'student_name': '<div>Alice Smith</div>',
            'date': '2024-01-20',
            'time': '14:00',
            'duration_minutes': 60,
            'location': '<a href="evil.com">Gym Downtown</a>'
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'student_name': 'Alice Smith',
            'date': '2024-01-20',
            'time': '14:00',
            'duration_minutes': 60,
            'location': 'Gym Downtown'
        }
    
    def test_sanitize_tool_parameters_notification_broadcast(self):
        """Test sanitization of notification broadcast parameters."""
        params = {
            'message': '<script>steal()</script>Session reminder: Tomorrow at 2 PM',
            'recipients': ['all'],
            'metadata': {
                'sender': '<b>Trainer</b>',
                'priority': 'high'
            }
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert result == {
            'message': 'steal()Session reminder: Tomorrow at 2 PM',
            'recipients': ['all'],
            'metadata': {
                'sender': 'Trainer',
                'priority': 'high'
            }
        }
    
    def test_sanitize_tool_parameters_preserves_structure(self):
        """Test that sanitization preserves the original structure."""
        params = {
            'string': 'text',
            'number': 42,
            'float': 3.14,
            'bool': True,
            'none': None,
            'list': [1, 2, 3],
            'dict': {'key': 'value'}
        }
        result = InputSanitizer.sanitize_tool_parameters(params)
        assert list(result.keys()) == list(params.keys())
        assert isinstance(result['string'], str)
        assert isinstance(result['number'], int)
        assert isinstance(result['float'], float)
        assert isinstance(result['bool'], bool)
        assert result['none'] is None
        assert isinstance(result['list'], list)
        assert isinstance(result['dict'], dict)
