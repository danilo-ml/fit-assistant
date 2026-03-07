"""
Structured logging module for FitAgent.

This module provides JSON-formatted logging with automatic phone number masking
and support for contextual fields like request_id. Designed for CloudWatch Insights
queries and privacy compliance.

Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional


class StructuredLogger:
    """
    Logger that outputs JSON-formatted logs with automatic phone number masking.
    
    Features:
    - JSON formatting for CloudWatch Insights compatibility
    - Automatic phone number masking (shows last 4 digits only)
    - Support for request_id and custom fields
    - Standard log levels (INFO, WARNING, ERROR)
    
    Example:
        logger = StructuredLogger(__name__)
        logger.info(
            'Tool executed',
            request_id='abc-123',
            phone_number='+1234567890',
            tool_name='schedule_session'
        )
    """
    
    def __init__(self, name: str):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name (typically __name__ of the module)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Configure handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
    
    def _mask_phone_number(self, phone_number: str) -> Optional[str]:
        """
        Mask phone number for privacy compliance.
        
        Shows only the last 4 digits, masks the rest with asterisks.
        
        Args:
            phone_number: Phone number in any format
            
        Returns:
            Masked phone number (e.g., '***1234') or None if empty
        """
        if not phone_number:
            return None
        if len(phone_number) < 4:
            return '***'
        return f'***{phone_number[-4:]}'
    
    def _format_log(
        self,
        level: str,
        message: str,
        request_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Format log entry as JSON.
        
        Args:
            level: Log level (INFO, WARNING, ERROR)
            message: Log message
            request_id: Optional request identifier for tracing
            phone_number: Optional phone number (will be masked automatically)
            **kwargs: Additional custom fields to include in log
            
        Returns:
            JSON-formatted log string
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': level,
            'message': message,
            'service': 'fitagent'
        }
        
        if request_id:
            log_entry['request_id'] = request_id
        
        if phone_number:
            masked = self._mask_phone_number(phone_number)
            if masked:
                log_entry['phone_number'] = masked
        
        # Add any additional custom fields
        log_entry.update(kwargs)
        
        return json.dumps(log_entry)
    
    def info(self, message: str, **kwargs):
        """
        Log INFO level message.
        
        Args:
            message: Log message
            **kwargs: Optional fields (request_id, phone_number, custom fields)
        """
        self.logger.info(self._format_log('INFO', message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """
        Log WARNING level message.
        
        Args:
            message: Log message
            **kwargs: Optional fields (request_id, phone_number, custom fields)
        """
        self.logger.warning(self._format_log('WARNING', message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """
        Log ERROR level message.
        
        Args:
            message: Log message
            **kwargs: Optional fields (request_id, phone_number, custom fields)
        """
        self.logger.error(self._format_log('ERROR', message, **kwargs))


def get_logger(name: str) -> StructuredLogger:
    """
    Factory function to create a StructuredLogger instance.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        StructuredLogger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info('Application started')
    """
    return StructuredLogger(name)
