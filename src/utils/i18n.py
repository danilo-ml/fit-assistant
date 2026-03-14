"""
Internationalization (i18n) utilities for FitAgent.

This module provides language detection and text translation for multi-language support.
Currently supports Portuguese (pt-BR) as the primary language with English (en-US) fallback.

The language is detected from phone number country codes:
- +55 (Brazil) → pt-BR
- +1 (US/Canada) → en-US
- Others → pt-BR (default)

Usage:
    from src.utils.i18n import get_text, get_language_from_phone
    
    language = get_language_from_phone("+5511999999999")  # Returns "pt-BR"
    message = get_text("welcome_message", language)
"""

from typing import Dict, Optional


# Language detection based on country codes
COUNTRY_CODE_TO_LANGUAGE = {
    "55": "pt-BR",  # Brazil
    "1": "en-US",   # US/Canada
    "351": "pt-PT", # Portugal
    "34": "es-ES",  # Spain
    "52": "es-MX",  # Mexico
}

# Default language
DEFAULT_LANGUAGE = "pt-BR"


# Translation strings
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # Welcome messages
    "welcome_message": {
        "pt-BR": "Bem-vindo ao FitAgent! 👋",
        "en-US": "Welcome to FitAgent! 👋",
    },
    
    # Success messages
    "success_processed": {
        "pt-BR": "Processado com sucesso!",
        "en-US": "Successfully processed!",
    },
    
    # Error messages
    "error_processing": {
        "pt-BR": "Erro ao processar sua solicitação. Por favor, tente novamente.",
        "en-US": "Error processing your request. Please try again.",
    },
    
    "error_not_found": {
        "pt-BR": "Não encontrado.",
        "en-US": "Not found.",
    },
    
    "error_invalid_input": {
        "pt-BR": "Entrada inválida. Por favor, verifique os dados fornecidos.",
        "en-US": "Invalid input. Please check the provided data.",
    },
    
    # Session messages
    "session_scheduled": {
        "pt-BR": "Sessão agendada com sucesso!",
        "en-US": "Session scheduled successfully!",
    },
    
    "session_cancelled": {
        "pt-BR": "Sessão cancelada.",
        "en-US": "Session cancelled.",
    },
    
    "session_rescheduled": {
        "pt-BR": "Sessão reagendada com sucesso!",
        "en-US": "Session rescheduled successfully!",
    },
    
    # Student messages
    "student_registered": {
        "pt-BR": "Aluno registrado com sucesso!",
        "en-US": "Student registered successfully!",
    },
    
    "student_updated": {
        "pt-BR": "Informações do aluno atualizadas!",
        "en-US": "Student information updated!",
    },
    
    # Payment messages
    "payment_registered": {
        "pt-BR": "Pagamento registrado com sucesso!",
        "en-US": "Payment registered successfully!",
    },
    
    # Calendar messages
    "calendar_connected": {
        "pt-BR": "Calendário conectado com sucesso!",
        "en-US": "Calendar connected successfully!",
    },
    
    "calendar_disconnected": {
        "pt-BR": "Calendário desconectado.",
        "en-US": "Calendar disconnected.",
    },
    
    # Notification messages
    "notification_sent": {
        "pt-BR": "Notificação enviada!",
        "en-US": "Notification sent!",
    },
}


def get_language_from_phone(phone_number: str) -> str:
    """
    Detect language from phone number country code.
    
    Extracts the country code from E.164 formatted phone number
    and maps it to a language code.
    
    Args:
        phone_number: Phone number in E.164 format (e.g., "+5511999999999")
    
    Returns:
        str: Language code (e.g., "pt-BR", "en-US")
    
    Examples:
        >>> get_language_from_phone("+5511999999999")
        'pt-BR'
        >>> get_language_from_phone("+14155552671")
        'en-US'
        >>> get_language_from_phone("+447700900123")
        'pt-BR'  # Default for unknown country codes
    """
    if not phone_number or not phone_number.startswith("+"):
        return DEFAULT_LANGUAGE
    
    # Remove '+' prefix
    number = phone_number[1:]
    
    # Try to match country codes (1-3 digits)
    for length in [3, 2, 1]:
        country_code = number[:length]
        if country_code in COUNTRY_CODE_TO_LANGUAGE:
            return COUNTRY_CODE_TO_LANGUAGE[country_code]
    
    return DEFAULT_LANGUAGE


def get_text(key: str, language: Optional[str] = None) -> str:
    """
    Get translated text for a given key and language.
    
    If the key or language is not found, returns the key itself
    as a fallback to prevent breaking the application.
    
    Args:
        key: Translation key (e.g., "welcome_message")
        language: Language code (e.g., "pt-BR"). If None, uses default.
    
    Returns:
        str: Translated text or the key itself if not found
    
    Examples:
        >>> get_text("welcome_message", "pt-BR")
        'Bem-vindo ao FitAgent! 👋'
        >>> get_text("welcome_message", "en-US")
        'Welcome to FitAgent! 👋'
        >>> get_text("unknown_key", "pt-BR")
        'unknown_key'
    """
    if language is None:
        language = DEFAULT_LANGUAGE
    
    # Get translation dict for key
    translations = TRANSLATIONS.get(key)
    if not translations:
        return key
    
    # Get translation for language, fallback to default language, then key
    return translations.get(language) or translations.get(DEFAULT_LANGUAGE) or key


def add_translation(key: str, translations: Dict[str, str]) -> None:
    """
    Add or update a translation entry.
    
    This function allows dynamic addition of translations at runtime,
    useful for plugins or extensions.
    
    Args:
        key: Translation key
        translations: Dict mapping language codes to translated strings
    
    Examples:
        >>> add_translation("custom_message", {
        ...     "pt-BR": "Mensagem personalizada",
        ...     "en-US": "Custom message"
        ... })
    """
    TRANSLATIONS[key] = translations


def get_supported_languages() -> list:
    """
    Get list of supported language codes.
    
    Returns:
        list: List of language codes (e.g., ["pt-BR", "en-US"])
    """
    languages = set()
    for translations in TRANSLATIONS.values():
        languages.update(translations.keys())
    return sorted(list(languages))
