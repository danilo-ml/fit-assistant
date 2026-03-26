"""
Template Registry for WhatsApp Content API template management.

Provides centralized mapping of notification types to Twilio Content SIDs
and placeholder definitions. Loads configuration from environment variables
via Pydantic Settings.
"""

import re
import json
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class TemplateConfig:
    """Configuration for a single notification template."""
    content_sid: str
    variables: List[str]


class TemplateRegistry:
    """
    Manages mapping of notification types to Twilio Content API templates.

    Loads configuration from environment variables via Settings.
    Validates Content SID format on initialization.
    """

    VALID_NOTIFICATION_TYPES = {"session_reminder", "payment_reminder", "broadcast"}
    CONTENT_SID_PATTERN = r"^HX[0-9a-fA-F]{32}$"

    def __init__(self, config: Optional[Dict[str, Dict]] = None):
        """
        Initialize registry from config dict or environment settings.

        Args:
            config: Optional dict mapping notification_type ->
                    {"content_sid": str, "variables": list[str]}
        """
        self._templates: Dict[str, TemplateConfig] = {}

        if config is not None:
            self._load_from_config(config)
        else:
            self._load_from_settings()

    def _load_from_config(self, config: Dict[str, Dict]) -> None:
        """Load templates from an explicit config dict."""
        for notification_type, template_data in config.items():
            if notification_type not in self.VALID_NOTIFICATION_TYPES:
                logger.warning(
                    "Unknown notification type '%s', skipping",
                    notification_type,
                )
                continue

            content_sid = template_data.get("content_sid", "")
            if not self.validate_content_sid(content_sid):
                logger.warning(
                    "Invalid Content SID '%s' for notification type '%s', excluding",
                    content_sid,
                    notification_type,
                )
                continue

            variables = template_data.get("variables", [])
            self._templates[notification_type] = TemplateConfig(
                content_sid=content_sid,
                variables=variables,
            )

    def _load_from_settings(self) -> None:
        """Load templates from environment config via Settings."""
        mapping = {
            "session_reminder": (
                settings.template_session_reminder_sid,
                settings.template_session_reminder_vars,
            ),
            "payment_reminder": (
                settings.template_payment_reminder_sid,
                settings.template_payment_reminder_vars,
            ),
            "broadcast": (
                settings.template_broadcast_sid,
                settings.template_broadcast_vars,
            ),
        }

        for notification_type, (sid, vars_str) in mapping.items():
            if not sid:
                continue

            if not self.validate_content_sid(sid):
                logger.warning(
                    "Invalid Content SID '%s' for notification type '%s', excluding",
                    sid,
                    notification_type,
                )
                continue

            variables: List[str] = []
            if vars_str:
                variables = [v.strip() for v in vars_str.split(",") if v.strip()]

            self._templates[notification_type] = TemplateConfig(
                content_sid=sid,
                variables=variables,
            )

    def get_template(self, notification_type: str) -> Optional[TemplateConfig]:
        """
        Look up template for a notification type.

        Args:
            notification_type: One of "session_reminder", "payment_reminder",
                               "broadcast"

        Returns:
            TemplateConfig if configured and valid, None otherwise.
        """
        return self._templates.get(notification_type)

    def is_configured(self, notification_type: str) -> bool:
        """Check if a notification type has a valid template configured."""
        return notification_type in self._templates

    @staticmethod
    def validate_content_sid(content_sid: str) -> bool:
        """Validate Content SID matches Twilio format: HX + 32 hex chars."""
        return bool(re.match(TemplateRegistry.CONTENT_SID_PATTERN, content_sid))


def build_content_variables(
    template_config: TemplateConfig,
    context: Dict[str, str],
) -> Optional[str]:
    """
    Build content_variables JSON string from context data.

    Maps template_config.variables (ordered placeholder names) to
    1-indexed string keys: {"1": context[var1], "2": context[var2], ...}

    Args:
        template_config: Template configuration with ordered variable names
        context: Dict mapping variable names to string values

    Returns:
        JSON string like '{"1":"value1","2":"value2"}', or None if any
        required variable is missing.
    """
    result = {}
    for i, var_name in enumerate(template_config.variables, start=1):
        value = context.get(var_name)
        if value is None:
            logger.warning(
                "Missing template variable '%s', cannot build content variables",
                var_name,
            )
            return None
        result[str(i)] = value

    return json.dumps(result)
