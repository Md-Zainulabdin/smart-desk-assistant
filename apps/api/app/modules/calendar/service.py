import logging

from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.core.exceptions import ApiError
from app.database.models import User
from app.integrations.google_calendar import create_meeting
from app.modules.calendar.schemas import MeetingIn, MeetingOut

logger = logging.getLogger(__name__)


def book_meeting(user: User, meeting: MeetingIn) -> MeetingOut:
    """Create a meeting in the user's Google Calendar, mapping Google errors to API errors."""
    if not user.refresh_token:
        raise ApiError(
            "Google Calendar is not connected. Sign in with Google again.",
            "calendar_not_connected",
            401,
        )

    try:
        return MeetingOut(**create_meeting(user.refresh_token, meeting))
    except RefreshError:
        # Token revoked, or expired (Testing-mode tokens last 7 days).
        logger.warning("Calendar refresh token rejected for user %s", user.id)
        raise ApiError(
            "Google access expired. Sign in with Google again.", "google_access_expired", 401
        ) from None
    except HttpError as e:
        logger.warning("Google Calendar returned %s for user %s", e.status_code, user.id)
        if e.status_code == 403:
            raise ApiError(
                "Calendar permission was not granted. Sign in again.",
                "calendar_permission_denied",
                403,
            ) from None
        raise ApiError(
            "Google Calendar rejected the request.", "calendar_request_failed", 502
        ) from None
