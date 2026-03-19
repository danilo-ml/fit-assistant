"""
Calendar sync service for bidirectional synchronization with external calendar providers.

This service handles creating, updating, and deleting calendar events in both
Google Calendar (via Google Calendar API v3) and Microsoft Outlook (via Microsoft Graph API).

Features:
- OAuth2 token management with automatic refresh
- Retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
- Graceful degradation (failures don't block session operations)
- Support for both Google Calendar and Microsoft Outlook

Requirements: 4.3, 4.4, 4.5, 4.6, 4.7
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import requests
from requests.exceptions import RequestException

from config import settings
from models.dynamodb_client import DynamoDBClient
from utils.encryption import decrypt_oauth_token_base64, encrypt_oauth_token_base64
from utils.retry import retry_with_backoff, ExternalServiceError
from utils.logging import get_logger

logger = get_logger(__name__)


class CalendarSyncError(Exception):
    """Base exception for calendar sync errors."""
    pass


class TokenRefreshError(CalendarSyncError):
    """Exception raised when OAuth token refresh fails."""
    pass


class CalendarSyncService:
    """
    Service for synchronizing session events with external calendar providers.

    Supports:
    - Google Calendar API v3
    - Microsoft Graph API (Outlook Calendar)

    Features:
    - Automatic OAuth token refresh on 401 Unauthorized
    - Retry logic with exponential backoff (3 attempts: 1s, 2s, 4s)
    - Graceful degradation (logs errors but doesn't block operations)
    """

    def __init__(
        self,
        dynamodb_client: Optional[DynamoDBClient] = None,
        aws_endpoint_url: Optional[str] = None,
    ):
        """
        Initialize calendar sync service.

        Args:
            dynamodb_client: DynamoDB client for accessing calendar config
            aws_endpoint_url: AWS endpoint URL for LocalStack (optional)
        """
        self.dynamodb_client = dynamodb_client or DynamoDBClient(
            table_name=settings.dynamodb_table,
            endpoint_url=aws_endpoint_url or settings.aws_endpoint_url,
        )

        logger.info("CalendarSyncService initialized")

    def _get_calendar_config(self, trainer_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve calendar configuration for a trainer.

        Args:
            trainer_id: Trainer identifier

        Returns:
            dict: Calendar config with provider, encrypted_refresh_token, etc.
            None: If no calendar is connected
        """
        try:
            config = self.dynamodb_client.get_calendar_config(trainer_id)
            
            if not config:
                logger.info("No calendar config found", trainer_id=trainer_id)
                return None

            return config

        except Exception as e:
            logger.error(
                "Failed to retrieve calendar config",
                trainer_id=trainer_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _update_calendar_config(
        self, trainer_id: str, encrypted_refresh_token: str
    ) -> None:
        """
        Update calendar configuration with new refresh token.

        Args:
            trainer_id: Trainer identifier
            encrypted_refresh_token: New encrypted refresh token
        """
        try:
            self.dynamodb_client.dynamodb.update_item(
                TableName=settings.dynamodb_table,
                Key={"PK": {"S": f"TRAINER#{trainer_id}"}, "SK": {"S": "CALENDAR_CONFIG"}},
                UpdateExpression="SET encrypted_refresh_token = :token, updated_at = :updated",
                ExpressionAttributeValues={
                    ":token": {"S": encrypted_refresh_token},
                    ":updated": {"S": datetime.utcnow().isoformat()},
                },
            )
            logger.info("Calendar config updated with new token", trainer_id=trainer_id)

        except Exception as e:
            logger.error(
                "Failed to update calendar config",
                trainer_id=trainer_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    def _refresh_google_token(self, refresh_token: str) -> str:
        """
        Refresh Google OAuth access token.

        Args:
            refresh_token: OAuth refresh token

        Returns:
            str: New access token

        Raises:
            TokenRefreshError: If token refresh fails
        """
        try:
            creds = settings.get_google_oauth_credentials()
            response = requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=10,
            )
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise TokenRefreshError("No access token in refresh response")

            logger.info("Google access token refreshed successfully")
            return access_token

        except RequestException as e:
            logger.error("Failed to refresh Google token", error=str(e))
            raise TokenRefreshError(f"Google token refresh failed: {str(e)}") from e

    def _refresh_outlook_token(self, refresh_token: str, trainer_id: str) -> str:
        """
        Refresh Microsoft Outlook OAuth access token.

        Args:
            refresh_token: OAuth refresh token
            trainer_id: Trainer identifier (for updating stored token if new refresh token provided)

        Returns:
            str: New access token

        Raises:
            TokenRefreshError: If token refresh fails
        """
        try:
            creds = settings.get_outlook_oauth_credentials()
            response = requests.post(
                "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                data={
                    "client_id": creds["client_id"],
                    "client_secret": creds["client_secret"],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "scope": "Calendars.ReadWrite offline_access",
                },
                timeout=10,
            )
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")

            if not access_token:
                raise TokenRefreshError("No access token in refresh response")

            # Microsoft may return a new refresh token
            new_refresh_token = token_data.get("refresh_token")
            if new_refresh_token and new_refresh_token != refresh_token:
                logger.info("New refresh token received from Microsoft, updating config")
                encrypted_token = encrypt_oauth_token_base64(new_refresh_token)
                self._update_calendar_config(trainer_id, encrypted_token)

            logger.info("Outlook access token refreshed successfully")
            return access_token

        except RequestException as e:
            logger.error("Failed to refresh Outlook token", error=str(e))
            raise TokenRefreshError(f"Outlook token refresh failed: {str(e)}") from e

    def _get_access_token(self, trainer_id: str, config: Dict[str, Any]) -> str:
        """
        Get valid access token, refreshing if necessary.

        Args:
            trainer_id: Trainer identifier
            config: Calendar configuration dict

        Returns:
            str: Valid access token

        Raises:
            TokenRefreshError: If token refresh fails
        """
        provider = config["provider"]
        encrypted_token = config["encrypted_refresh_token"]

        # Decrypt refresh token
        refresh_token = decrypt_oauth_token_base64(encrypted_token)

        # Refresh access token based on provider
        if provider == "google":
            return self._refresh_google_token(refresh_token)
        elif provider == "outlook":
            return self._refresh_outlook_token(refresh_token, trainer_id)
        else:
            raise CalendarSyncError(f"Unsupported provider: {provider}")

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _google_create_event(
        self, access_token: str, calendar_id: str, event_data: Dict[str, Any]
    ) -> str:
        """
        Create event in Google Calendar with retry logic.

        Args:
            access_token: OAuth access token
            calendar_id: Calendar ID (usually 'primary')
            event_data: Event data dict

        Returns:
            str: Calendar event ID

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data,
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Google Calendar", "create_event", "Unauthorized - token may be expired"
                )

            response.raise_for_status()
            event = response.json()
            return event["id"]

        except RequestException as e:
            logger.error("Google Calendar create_event failed", error=str(e))
            raise ExternalServiceError("Google Calendar", "create_event", str(e)) from e

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _google_update_event(
        self,
        access_token: str,
        calendar_id: str,
        event_id: str,
        event_data: Dict[str, Any],
    ) -> None:
        """
        Update event in Google Calendar with retry logic.

        Args:
            access_token: OAuth access token
            calendar_id: Calendar ID (usually 'primary')
            event_id: Calendar event ID
            event_data: Updated event data dict

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.put(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data,
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Google Calendar", "update_event", "Unauthorized - token may be expired"
                )

            response.raise_for_status()

        except RequestException as e:
            logger.error("Google Calendar update_event failed", error=str(e))
            raise ExternalServiceError("Google Calendar", "update_event", str(e)) from e

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _google_delete_event(
        self, access_token: str, calendar_id: str, event_id: str
    ) -> None:
        """
        Delete event from Google Calendar with retry logic.

        Args:
            access_token: OAuth access token
            calendar_id: Calendar ID (usually 'primary')
            event_id: Calendar event ID

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.delete(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Google Calendar", "delete_event", "Unauthorized - token may be expired"
                )

            # 404 is acceptable - event may already be deleted
            if response.status_code != 404:
                response.raise_for_status()

        except RequestException as e:
            logger.error("Google Calendar delete_event failed", error=str(e))
            raise ExternalServiceError("Google Calendar", "delete_event", str(e)) from e

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _outlook_create_event(
        self, access_token: str, event_data: Dict[str, Any]
    ) -> str:
        """
        Create event in Outlook Calendar with retry logic.

        Args:
            access_token: OAuth access token
            event_data: Event data dict

        Returns:
            str: Calendar event ID

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.post(
                "https://graph.microsoft.com/v1.0/me/events",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data,
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Outlook Calendar", "create_event", "Unauthorized - token may be expired"
                )

            response.raise_for_status()
            event = response.json()
            return event["id"]

        except RequestException as e:
            logger.error("Outlook Calendar create_event failed", error=str(e))
            raise ExternalServiceError("Outlook Calendar", "create_event", str(e)) from e

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _outlook_update_event(
        self, access_token: str, event_id: str, event_data: Dict[str, Any]
    ) -> None:
        """
        Update event in Outlook Calendar with retry logic.

        Args:
            access_token: OAuth access token
            event_id: Calendar event ID
            event_data: Updated event data dict

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.patch(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                json=event_data,
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Outlook Calendar", "update_event", "Unauthorized - token may be expired"
                )

            response.raise_for_status()

        except RequestException as e:
            logger.error("Outlook Calendar update_event failed", error=str(e))
            raise ExternalServiceError("Outlook Calendar", "update_event", str(e)) from e

    @retry_with_backoff(max_attempts=3, initial_delay=1.0, backoff_factor=2.0)
    def _outlook_delete_event(self, access_token: str, event_id: str) -> None:
        """
        Delete event from Outlook Calendar with retry logic.

        Args:
            access_token: OAuth access token
            event_id: Calendar event ID

        Raises:
            ExternalServiceError: If API call fails after retries
        """
        try:
            response = requests.delete(
                f"https://graph.microsoft.com/v1.0/me/events/{event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if response.status_code == 401:
                raise ExternalServiceError(
                    "Outlook Calendar", "delete_event", "Unauthorized - token may be expired"
                )

            # 404 is acceptable - event may already be deleted
            if response.status_code != 404:
                response.raise_for_status()

        except RequestException as e:
            logger.error("Outlook Calendar delete_event failed", error=str(e))
            raise ExternalServiceError("Outlook Calendar", "delete_event", str(e)) from e

    def create_event(
        self,
        trainer_id: str,
        session_id: str,
        student_name: str,
        session_datetime: datetime,
        duration_minutes: int,
        location: Optional[str] = None,
        student_email: Optional[str] = None,
        attendee_emails: Optional[list] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Create calendar event for a training session.

        This method implements graceful degradation - if calendar sync fails,
        it logs the error but returns None instead of raising an exception,
        allowing the session creation to proceed.

        Args:
            trainer_id: Trainer identifier
            session_id: Session identifier
            student_name: Student name for event title
            session_datetime: Session start datetime
            duration_minutes: Session duration in minutes
            location: Optional session location

        Returns:
            dict: {'calendar_event_id': str, 'calendar_provider': str} on success
            None: If calendar sync fails or no calendar is connected

        Example:
            >>> service = CalendarSyncService()
            >>> result = service.create_event(
            ...     trainer_id='trainer-123',
            ...     session_id='session-456',
            ...     student_name='John Doe',
            ...     session_datetime=datetime(2024, 1, 20, 14, 0),
            ...     duration_minutes=60,
            ...     location='Gym A'
            ... )
            >>> print(result)
            {'calendar_event_id': 'abc123xyz', 'calendar_provider': 'google'}
        """
        try:
            # Get calendar configuration
            config = self._get_calendar_config(trainer_id)
            if not config:
                logger.info(
                    "No calendar connected, skipping sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
                return None

            provider = config["provider"]
            calendar_id = config.get("calendar_id", "primary")

            logger.info(
                "Creating calendar event",
                trainer_id=trainer_id,
                session_id=session_id,
                provider=provider,
            )

            # Get access token (with automatic refresh)
            access_token = self._get_access_token(trainer_id, config)

            # Calculate end time
            end_datetime = session_datetime + timedelta(minutes=duration_minutes)

            # Create event based on provider
            if provider == "google":
                event_data = {
                    "summary": f"Training Session with {student_name}",
                    "description": f"Session ID: {session_id}",
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                }
                if location:
                    event_data["location"] = location

                # Build attendees list
                google_attendees = []
                if student_email:
                    google_attendees.append({"email": student_email})
                if attendee_emails:
                    for email in attendee_emails:
                        if not any(a["email"] == email for a in google_attendees):
                            google_attendees.append({"email": email})
                if google_attendees:
                    event_data["attendees"] = google_attendees

                event_id = self._google_create_event(access_token, calendar_id, event_data)

            elif provider == "outlook":
                event_data = {
                    "subject": f"Training Session with {student_name}",
                    "body": {
                        "contentType": "Text",
                        "content": f"Session ID: {session_id}",
                    },
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                }
                if location:
                    event_data["location"] = {"displayName": location}

                # Build attendees list
                outlook_attendees = []
                if student_email:
                    outlook_attendees.append({
                        "emailAddress": {"address": student_email, "name": student_name},
                        "type": "required",
                    })
                if attendee_emails:
                    for email in attendee_emails:
                        if not any(a["emailAddress"]["address"] == email for a in outlook_attendees):
                            outlook_attendees.append({
                                "emailAddress": {"address": email, "name": email},
                                "type": "required",
                            })
                if outlook_attendees:
                    event_data["attendees"] = outlook_attendees

                event_id = self._outlook_create_event(access_token, event_data)

            else:
                logger.error("Unsupported calendar provider", provider=provider)
                return None

            logger.info(
                "Calendar event created successfully",
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=event_id,
                provider=provider,
            )

            return {"calendar_event_id": event_id, "calendar_provider": provider}

        except Exception as e:
            # Graceful degradation - log error but don't block session creation
            logger.error(
                "Calendar sync failed, continuing without sync",
                trainer_id=trainer_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def create_recurring_event(
        self,
        trainer_id: str,
        student_name: str,
        session_datetime: datetime,
        duration_minutes: int,
        weekday_codes: list,
        count: int,
        location: Optional[str] = None,
        student_email: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """
        Create a recurring calendar event using RRULE.

        Creates a single recurring event in Google Calendar or Outlook
        instead of multiple individual events.

        Args:
            trainer_id: Trainer identifier
            student_name: Student name for event title
            session_datetime: First session start datetime
            duration_minutes: Session duration in minutes
            weekday_codes: List of RRULE day codes (e.g., ["TU", "TH"])
            count: Total number of occurrences
            location: Optional session location
            student_email: Optional student email for invite

        Returns:
            dict with calendar_event_id and calendar_provider, or None
        """
        try:
            config = self._get_calendar_config(trainer_id)
            if not config:
                logger.info(
                    "No calendar connected, skipping recurring sync",
                    trainer_id=trainer_id,
                )
                return None

            provider = config["provider"]
            calendar_id = config.get("calendar_id", "primary")
            access_token = self._get_access_token(trainer_id, config)
            end_datetime = session_datetime + timedelta(minutes=duration_minutes)

            # Build RRULE string
            byday = ",".join(weekday_codes)
            rrule = f"RRULE:FREQ=WEEKLY;BYDAY={byday};COUNT={count}"

            if provider == "google":
                event_data = {
                    "summary": f"Treino com {student_name}",
                    "description": f"Sessão recorrente - {student_name}",
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "recurrence": [rrule],
                }
                if location:
                    event_data["location"] = location
                if student_email:
                    event_data["attendees"] = [{"email": student_email}]

                event_id = self._google_create_event(access_token, calendar_id, event_data)

            elif provider == "outlook":
                # Outlook uses a different recurrence format
                # Map RRULE day codes to Outlook day names
                outlook_days = {
                    "MO": "monday", "TU": "tuesday", "WE": "wednesday",
                    "TH": "thursday", "FR": "friday", "SA": "saturday", "SU": "sunday",
                }
                days_of_week = [outlook_days[code] for code in weekday_codes if code in outlook_days]

                event_data = {
                    "subject": f"Treino com {student_name}",
                    "body": {
                        "contentType": "Text",
                        "content": f"Sessão recorrente - {student_name}",
                    },
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "recurrence": {
                        "pattern": {
                            "type": "weekly",
                            "interval": 1,
                            "daysOfWeek": days_of_week,
                        },
                        "range": {
                            "type": "numbered",
                            "startDate": session_datetime.strftime("%Y-%m-%d"),
                            "numberOfOccurrences": count,
                        },
                    },
                }
                if location:
                    event_data["location"] = {"displayName": location}
                if student_email:
                    event_data["attendees"] = [
                        {
                            "emailAddress": {"address": student_email, "name": student_name},
                            "type": "required",
                        }
                    ]

                event_id = self._outlook_create_event(access_token, event_data)

            else:
                return None

            logger.info(
                "Recurring calendar event created",
                trainer_id=trainer_id,
                calendar_event_id=event_id,
                provider=provider,
                weekdays=weekday_codes,
                count=count,
            )

            return {"calendar_event_id": event_id, "calendar_provider": provider}

        except Exception as e:
            logger.error(
                "Recurring calendar sync failed",
                trainer_id=trainer_id,
                error=str(e),
            )
            return None

    def update_event(
        self,
        trainer_id: str,
        session_id: str,
        calendar_event_id: str,
        calendar_provider: str,
        student_name: str,
        session_datetime: datetime,
        duration_minutes: int,
        location: Optional[str] = None,
        student_email: Optional[str] = None,
        attendee_emails: Optional[list] = None,
    ) -> bool:
        """
        Update calendar event for a rescheduled training session.

        This method implements graceful degradation - if calendar sync fails,
        it logs the error but returns False instead of raising an exception,
        allowing the session update to proceed.

        Args:
            trainer_id: Trainer identifier
            session_id: Session identifier
            calendar_event_id: Existing calendar event ID
            calendar_provider: Calendar provider ('google' or 'outlook')
            student_name: Student name for event title
            session_datetime: New session start datetime
            duration_minutes: Session duration in minutes
            location: Optional session location

        Returns:
            bool: True if sync succeeded, False if it failed

        Example:
            >>> service = CalendarSyncService()
            >>> success = service.update_event(
            ...     trainer_id='trainer-123',
            ...     session_id='session-456',
            ...     calendar_event_id='abc123xyz',
            ...     calendar_provider='google',
            ...     student_name='John Doe',
            ...     session_datetime=datetime(2024, 1, 21, 14, 0),
            ...     duration_minutes=60
            ... )
            >>> print(success)
            True
        """
        try:
            # Get calendar configuration
            config = self._get_calendar_config(trainer_id)
            if not config:
                logger.warning(
                    "No calendar connected, skipping sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
                return False

            calendar_id = config.get("calendar_id", "primary")

            logger.info(
                "Updating calendar event",
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=calendar_event_id,
                provider=calendar_provider,
            )

            # Get access token (with automatic refresh)
            access_token = self._get_access_token(trainer_id, config)

            # Calculate end time
            end_datetime = session_datetime + timedelta(minutes=duration_minutes)

            # Update event based on provider
            if calendar_provider == "google":
                event_data = {
                    "summary": f"Training Session with {student_name}",
                    "description": f"Session ID: {session_id}",
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                }
                if location:
                    event_data["location"] = location

                # Build attendees list
                google_attendees = []
                if student_email:
                    google_attendees.append({"email": student_email})
                if attendee_emails:
                    for email in attendee_emails:
                        if not any(a["email"] == email for a in google_attendees):
                            google_attendees.append({"email": email})
                if google_attendees:
                    event_data["attendees"] = google_attendees

                self._google_update_event(
                    access_token, calendar_id, calendar_event_id, event_data
                )

            elif calendar_provider == "outlook":
                event_data = {
                    "subject": f"Training Session with {student_name}",
                    "body": {
                        "contentType": "Text",
                        "content": f"Session ID: {session_id}",
                    },
                    "start": {
                        "dateTime": session_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                    "end": {
                        "dateTime": end_datetime.isoformat(),
                        "timeZone": "America/Sao_Paulo",
                    },
                }
                if location:
                    event_data["location"] = {"displayName": location}

                # Build attendees list
                outlook_attendees = []
                if student_email:
                    outlook_attendees.append({
                        "emailAddress": {"address": student_email, "name": student_name},
                        "type": "required",
                    })
                if attendee_emails:
                    for email in attendee_emails:
                        if not any(a["emailAddress"]["address"] == email for a in outlook_attendees):
                            outlook_attendees.append({
                                "emailAddress": {"address": email, "name": email},
                                "type": "required",
                            })
                if outlook_attendees:
                    event_data["attendees"] = outlook_attendees

                self._outlook_update_event(access_token, calendar_event_id, event_data)

            else:
                logger.error("Unsupported calendar provider", provider=calendar_provider)
                return False

            logger.info(
                "Calendar event updated successfully",
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=calendar_event_id,
            )

            return True

        except Exception as e:
            # Graceful degradation - log error but don't block session update
            logger.error(
                "Calendar sync failed, continuing without sync",
                trainer_id=trainer_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    def delete_event(
        self,
        trainer_id: str,
        session_id: str,
        calendar_event_id: str,
        calendar_provider: str,
    ) -> bool:
        """
        Delete calendar event for a cancelled training session.

        This method implements graceful degradation - if calendar sync fails,
        it logs the error but returns False instead of raising an exception,
        allowing the session cancellation to proceed.

        Args:
            trainer_id: Trainer identifier
            session_id: Session identifier
            calendar_event_id: Calendar event ID to delete
            calendar_provider: Calendar provider ('google' or 'outlook')

        Returns:
            bool: True if sync succeeded, False if it failed

        Example:
            >>> service = CalendarSyncService()
            >>> success = service.delete_event(
            ...     trainer_id='trainer-123',
            ...     session_id='session-456',
            ...     calendar_event_id='abc123xyz',
            ...     calendar_provider='google'
            ... )
            >>> print(success)
            True
        """
        try:
            # Get calendar configuration
            config = self._get_calendar_config(trainer_id)
            if not config:
                logger.warning(
                    "No calendar connected, skipping sync",
                    trainer_id=trainer_id,
                    session_id=session_id,
                )
                return False

            calendar_id = config.get("calendar_id", "primary")

            logger.info(
                "Deleting calendar event",
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=calendar_event_id,
                provider=calendar_provider,
            )

            # Get access token (with automatic refresh)
            access_token = self._get_access_token(trainer_id, config)

            # Delete event based on provider
            if calendar_provider == "google":
                self._google_delete_event(access_token, calendar_id, calendar_event_id)

            elif calendar_provider == "outlook":
                self._outlook_delete_event(access_token, calendar_event_id)

            else:
                logger.error("Unsupported calendar provider", provider=calendar_provider)
                return False

            logger.info(
                "Calendar event deleted successfully",
                trainer_id=trainer_id,
                session_id=session_id,
                calendar_event_id=calendar_event_id,
            )

            return True

        except Exception as e:
            # Graceful degradation - log error but don't block session cancellation
            logger.error(
                "Calendar sync failed, continuing without sync",
                trainer_id=trainer_id,
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return False
