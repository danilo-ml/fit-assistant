"""
Phone number validation utilities for FitAgent.

This module provides phone number validation and normalization
to ensure all phone numbers conform to E.164 format.
"""

import re
from typing import Optional


class PhoneNumberValidator:
    """
    Validates and normalizes phone numbers to E.164 format.
    
    E.164 format: +[country code][number]
    Example: +14155552671
    
    Rules:
    - Must start with '+'
    - Followed by 1-3 digit country code
    - Followed by up to 15 digits total (including country code)
    - No spaces, dashes, or other characters
    """
    
    # E.164 format: + followed by 1-15 digits
    E164_PATTERN = re.compile(r'^\+[1-9]\d{1,14}$')
    
    # Common formats to normalize
    # Matches: (123) 456-7890, 123-456-7890, 123.456.7890, 123 456 7890
    COMMON_FORMAT_PATTERN = re.compile(r'[\s\-\.\(\)]')
    
    @classmethod
    def validate(cls, phone_number: str) -> bool:
        """
        Validate if a phone number is in E.164 format.
        
        Args:
            phone_number: Phone number string to validate
            
        Returns:
            bool: True if valid E.164 format, False otherwise
            
        Examples:
            >>> PhoneNumberValidator.validate("+14155552671")
            True
            >>> PhoneNumberValidator.validate("4155552671")
            False
            >>> PhoneNumberValidator.validate("+1 415 555 2671")
            False
        """
        if not phone_number or not isinstance(phone_number, str):
            return False
        
        return bool(cls.E164_PATTERN.match(phone_number))
    
    @classmethod
    def normalize(cls, phone_number: str, default_country_code: str = "1") -> Optional[str]:
        """
        Normalize a phone number to E.164 format.
        
        Handles common phone number formats:
        - Removes spaces, dashes, dots, parentheses
        - Adds '+' prefix if missing
        - Adds country code if missing (defaults to US: +1)
        
        Args:
            phone_number: Phone number string to normalize
            default_country_code: Country code to use if not present (default: "1" for US)
            
        Returns:
            Optional[str]: Normalized phone number in E.164 format, or None if invalid
            
        Examples:
            >>> PhoneNumberValidator.normalize("(415) 555-2671")
            '+14155552671'
            >>> PhoneNumberValidator.normalize("415-555-2671")
            '+14155552671'
            >>> PhoneNumberValidator.normalize("+1 415 555 2671")
            '+14155552671'
            >>> PhoneNumberValidator.normalize("14155552671")
            '+14155552671'
            >>> PhoneNumberValidator.normalize("4155552671")
            '+14155552671'
        """
        if not phone_number or not isinstance(phone_number, str):
            return None
        
        # Remove all common formatting characters
        cleaned = cls.COMMON_FORMAT_PATTERN.sub('', phone_number)
        
        # If already in E.164 format, validate and return
        if cleaned.startswith('+'):
            if cls.validate(cleaned):
                return cleaned
            return None
        
        # Add '+' prefix
        if not cleaned.startswith('+'):
            # If number doesn't start with country code, add default
            if not cleaned.startswith(default_country_code):
                cleaned = default_country_code + cleaned
            cleaned = '+' + cleaned
        
        # Validate the normalized number
        if cls.validate(cleaned):
            return cleaned
        
        return None
    
    @classmethod
    def is_valid_e164(cls, phone_number: str) -> bool:
        """
        Alias for validate() method for clarity.
        
        Args:
            phone_number: Phone number string to validate
            
        Returns:
            bool: True if valid E.164 format, False otherwise
        """
        return cls.validate(phone_number)


import bleach
from typing import Any, Dict, List, Union


class InputSanitizer:
    """
    Sanitizes user inputs to prevent injection attacks.
    
    This class provides methods to clean user-provided strings by:
    - Removing HTML tags
    - Preventing script injection
    - Truncating to safe lengths
    - Handling nested data structures (dicts, lists)
    
    Used to sanitize WhatsApp messages and tool parameters before processing.
    """
    
    # Default maximum length for string inputs
    DEFAULT_MAX_LENGTH = 1000
    
    # Allowed HTML tags (empty list = strip all tags)
    ALLOWED_TAGS: List[str] = []
    
    # Allowed HTML attributes (empty dict = strip all attributes)
    ALLOWED_ATTRIBUTES: Dict[str, List[str]] = {}
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = DEFAULT_MAX_LENGTH) -> str:
        """
        Sanitize a string input to prevent injection attacks.
        
        This method:
        1. Removes all HTML tags using bleach
        2. Strips leading/trailing whitespace
        3. Truncates to maximum length
        
        Args:
            value: String to sanitize
            max_length: Maximum allowed length (default: 1000)
            
        Returns:
            str: Sanitized string
            
        Examples:
            >>> InputSanitizer.sanitize_string("<script>alert('xss')</script>Hello")
            'Hello'
            >>> InputSanitizer.sanitize_string("  Normal text  ")
            'Normal text'
            >>> InputSanitizer.sanitize_string("A" * 2000, max_length=100)
            'AAAA...' (100 characters)
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove HTML tags and attributes
        cleaned = bleach.clean(
            value,
            tags=InputSanitizer.ALLOWED_TAGS,
            attributes=InputSanitizer.ALLOWED_ATTRIBUTES,
            strip=True
        )
        
        # Strip whitespace
        cleaned = cleaned.strip()
        
        # Truncate to max length
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
        
        return cleaned
    
    @staticmethod
    def sanitize_tool_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize all string parameters in a tool input dictionary.
        
        Recursively processes nested dictionaries and lists, sanitizing
        all string values while preserving the structure and non-string values.
        
        Args:
            params: Dictionary of tool parameters to sanitize
            
        Returns:
            Dict[str, Any]: Dictionary with sanitized string values
            
        Examples:
            >>> InputSanitizer.sanitize_tool_parameters({
            ...     'name': '<b>John</b>',
            ...     'age': 25,
            ...     'address': {'street': '<script>alert()</script>Main St'}
            ... })
            {'name': 'John', 'age': 25, 'address': {'street': 'Main St'}}
        """
        if not isinstance(params, dict):
            return params
        
        sanitized = {}
        for key, value in params.items():
            sanitized[key] = InputSanitizer._sanitize_value(value)
        
        return sanitized
    
    @staticmethod
    def _sanitize_value(value: Any) -> Any:
        """
        Sanitize a single value, handling different types recursively.
        
        Args:
            value: Value to sanitize (can be str, dict, list, or other)
            
        Returns:
            Any: Sanitized value with same type as input
        """
        if isinstance(value, str):
            return InputSanitizer.sanitize_string(value)
        elif isinstance(value, dict):
            return InputSanitizer.sanitize_tool_parameters(value)
        elif isinstance(value, list):
            return [InputSanitizer._sanitize_value(item) for item in value]
        else:
            # Return non-string types unchanged (int, float, bool, None, etc.)
            return value



class ValidationMessages:
    """
    Portuguese (pt-BR) validation error messages for user-facing errors.
    
    These messages are used throughout the application to provide
    culturally appropriate error feedback to Brazilian users.
    
    Note: Code, comments, logs, and documentation remain in English.
    """
    
    # Phone number validation
    INVALID_PHONE_FORMAT = "Formato de número de telefone inválido. Use o formato internacional (ex: +5511999999999)."
    PHONE_REQUIRED = "Número de telefone é obrigatório."
    
    # Email validation
    INVALID_EMAIL_FORMAT = "Endereço de e-mail inválido. Por favor, forneça um e-mail válido (ex: usuario@exemplo.com)."
    EMAIL_REQUIRED = "Endereço de e-mail é obrigatório."
    
    # Date and time validation
    INVALID_DATE_FORMAT = "Formato de data inválido. Use o formato AAAA-MM-DD (ex: 2024-12-25)."
    INVALID_TIME_FORMAT = "Formato de hora inválido. Use o formato HH:MM (ex: 14:30)."
    DATE_IN_PAST = "A data não pode estar no passado."
    DATE_REQUIRED = "Data é obrigatória."
    TIME_REQUIRED = "Hora é obrigatória."
    
    # Name validation
    NAME_TOO_SHORT = "Nome muito curto. Por favor, forneça pelo menos 2 caracteres."
    NAME_REQUIRED = "Nome é obrigatório."
    
    # Amount validation
    INVALID_AMOUNT = "Valor inválido. O valor deve ser maior que zero."
    AMOUNT_REQUIRED = "Valor é obrigatório."
    
    # Duration validation
    INVALID_DURATION = "Duração inválida. A duração deve estar entre 15 e 480 minutos."
    DURATION_REQUIRED = "Duração é obrigatória."
    
    # General validation
    FIELD_REQUIRED = "Este campo é obrigatório."
    INVALID_INPUT = "Entrada inválida. Por favor, verifique os dados fornecidos."
    
    # Session validation
    SESSION_NOT_FOUND = "Sessão não encontrada."
    SESSION_CONFLICT = "Conflito de horário. Já existe uma sessão agendada neste horário."
    
    # Student validation
    STUDENT_NOT_FOUND = "Aluno não encontrado."
    STUDENT_ALREADY_EXISTS = "Aluno já está registrado."
    
    # Payment validation
    PAYMENT_NOT_FOUND = "Pagamento não encontrado."
    INVALID_CURRENCY = "Código de moeda inválido."
    
    # Calendar validation
    INVALID_PROVIDER = "Provedor de calendário inválido. Use 'google' ou 'outlook'."
    CALENDAR_NOT_CONNECTED = "Calendário não conectado. Por favor, conecte seu calendário primeiro."
    
    # Generic errors
    SOMETHING_WENT_WRONG = "Algo deu errado. Por favor, tente novamente."
    TRY_AGAIN_LATER = "Por favor, tente novamente em alguns instantes."
    CONTACT_SUPPORT = "Se o problema persistir, entre em contato com o suporte."
