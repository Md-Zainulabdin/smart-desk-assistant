"""Google Calendar API client. External calls only: no database access, no business rules."""

import logging

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from app.modules.auth.oauth import CALENDAR_EVENTS_SCOPE

logger = logging.getLogger(__name__)

TOKEN_URI = "https://oauth2.googleapis.com/token"
NUM_RETRIES = 2


class CalendarAuthError(Exception):
    """Google refused the stored grant: revoked, expired, or missing the Calendar scope."""


class CalendarApiError(Exception):
    """Google Calendar failed or rejected the request for a non-auth reason."""


class EventAlreadyExists(Exception):
    """An event with this id already exists (a retried request)."""


def _service(refresh_token: str):
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri=TOKEN_URI,
        scopes=[CALENDAR_EVENTS_SCOPE],
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def _translate(error: HttpError) -> Exception:
    status = error.status_code
    if status == 409:
        return EventAlreadyExists()
    if status == 401:
        return CalendarAuthError()
    if status == 403 and "ratelimit" not in str(error.reason or "").replace(" ", "").lower():
        return CalendarAuthError()
    logger.warning("google calendar request failed: status=%s", status)
    return CalendarApiError()


def _execute(request):
    try:
        return request.execute(num_retries=NUM_RETRIES)
    except RefreshError:
        raise CalendarAuthError() from None
    except HttpError as error:
        raise _translate(error) from None


def insert_event(refresh_token: str, body: dict) -> dict:
    """Insert an event on the user's primary calendar and email the attendees."""
    events = _service(refresh_token).events()
    return _execute(
        events.insert(calendarId="primary", body=body, conferenceDataVersion=1, sendUpdates="all")
    )


def get_event(refresh_token: str, event_id: str) -> dict:
    events = _service(refresh_token).events()
    return _execute(events.get(calendarId="primary", eventId=event_id))


def list_events(
    refresh_token: str,
    time_min: str,
    time_max: str,
    max_results: int,
) -> list[dict]:
    """List timed events on the primary calendar in the given RFC 3339 range."""
    events = _service(refresh_token).events()
    result = _execute(
        events.list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=max_results,
        )
    )
    return result.get("items", [])
