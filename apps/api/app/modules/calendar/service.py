import hashlib
import logging
import uuid
from datetime import date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import Connection

from app.config import settings
from app.core.exceptions import ApiError
from app.core.security import TokenEncryptionError, decrypt_token
from app.integrations import google_calendar
from app.modules.calendar import repository
from app.modules.calendar.schemas import MeetingIn, MeetingOut, MeetingSummary

logger = logging.getLogger(__name__)


def _sign_in_again(detail: str, code: str) -> ApiError:
    # 403, not 401: the app session is fine, only Google access needs renewing.
    return ApiError(f"{detail} Sign in with Google again.", code, 403)


def event_id_for(user_id: UUID, request_id: str) -> str:
    """Same user + request_id -> same Google event id, so a retry cannot double-book.

    Google event ids use base32hex (0-9, a-v), 5-1024 chars; a SHA-256 hex digest fits.
    """
    return hashlib.sha256(f"{user_id}:{request_id}".encode()).hexdigest()


def _refresh_token(conn: Connection, user_id: UUID) -> str:
    stored = repository.get_refresh_token_encrypted(conn, user_id)
    if stored is None:
        raise _sign_in_again("Google Calendar access was not granted.", "calendar_not_connected")
    try:
        return decrypt_token(stored)
    except TokenEncryptionError:
        logger.error("calendar: stored refresh token could not be decrypted")
        raise _sign_in_again("Google Calendar access expired.", "google_access_expired") from None


def _event_body(meeting: MeetingIn, event_id: str | None) -> dict:
    timezone = meeting.timezone or settings.default_timezone
    body = {
        "summary": meeting.title,
        "description": meeting.description,
        "start": {"dateTime": meeting.start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": meeting.end.isoformat(), "timeZone": timezone},
        "attendees": [{"email": email} for email in meeting.attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": event_id or uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if event_id:
        body["id"] = event_id
    return body


def _insert_or_fetch(refresh_token: str, body: dict) -> dict:
    try:
        return google_calendar.insert_event(refresh_token, body)
    except google_calendar.EventAlreadyExists:
        # A retry of a request that already succeeded: return that event.
        event = google_calendar.get_event(refresh_token, body["id"])
    if event.get("status") == "cancelled":
        raise ApiError(
            "This meeting was booked and then cancelled. Send a new request_id to book it again.",
            "calendar_event_cancelled",
            409,
        )
    return event


def book_meeting(conn: Connection, user_id: UUID, meeting: MeetingIn) -> MeetingOut:
    """Create a meeting with a Google Meet link on the user's primary calendar."""
    refresh_token = _refresh_token(conn, user_id)
    event_id = event_id_for(user_id, meeting.request_id) if meeting.request_id else None
    try:
        event = _insert_or_fetch(refresh_token, _event_body(meeting, event_id))
    except google_calendar.CalendarAuthError:
        raise _sign_in_again("Google Calendar access expired.", "google_access_expired") from None
    except google_calendar.CalendarApiError:
        raise ApiError(
            "Google Calendar could not create the meeting. Try again shortly.",
            "calendar_request_failed",
            502,
        ) from None
    return MeetingOut(id=event["id"], link=event["htmlLink"], meet_link=event.get("hangoutLink"))


def _event_times(event: dict) -> tuple[datetime, datetime, bool] | None:
    """Normalize Google's date or dateTime fields into aware datetimes."""
    start = event.get("start") or {}
    end = event.get("end") or {}

    if "dateTime" in start and "dateTime" in end:
        start_at = datetime.fromisoformat(str(start["dateTime"]))
        end_at = datetime.fromisoformat(str(end["dateTime"]))
        return start_at, end_at, False

    if "date" in start:
        timezone = ZoneInfo(start.get("timeZone") or settings.default_timezone)
        start_at = datetime.combine(date.fromisoformat(start["date"]), time.min, tzinfo=timezone)
        end_date = date.fromisoformat(end.get("date", start["date"]))
        return start_at, datetime.combine(end_date, time.min, tzinfo=timezone), True

    return None


def _summary(event: dict) -> MeetingSummary | None:
    times = _event_times(event)
    event_id = event.get("id")
    if times is None or not event_id:
        return None
    start_at, end_at, all_day = times
    return MeetingSummary(
        id=event_id,
        title=event.get("summary") or "Untitled event",
        start=start_at,
        end=end_at,
        all_day=all_day,
        link=event.get("htmlLink", ""),
        meet_link=event.get("hangoutLink"),
    )


def list_meetings(
    conn: Connection,
    user_id: UUID,
    start: datetime,
    end: datetime,
    max_results: int = 10,
) -> list[MeetingSummary]:
    """Read the user's upcoming meetings in the given time range."""
    refresh_token = _refresh_token(conn, user_id)
    try:
        events = google_calendar.list_events(
            refresh_token,
            start.isoformat(),
            end.isoformat(),
            max_results,
        )
    except google_calendar.CalendarAuthError:
        raise _sign_in_again("Google Calendar access expired.", "google_access_expired") from None
    except google_calendar.CalendarApiError:
        raise ApiError(
            "Google Calendar could not read your meetings. Try again shortly.",
            "calendar_request_failed",
            502,
        ) from None

    meetings = (_summary(event) for event in events)
    return [meeting for meeting in meetings if meeting is not None]
