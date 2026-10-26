from fastapi import APIRouter, Depends, HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.calendar.models import MeetingIn
from app.db import get_db
from app.integrations.google_calendar import create_meeting
from app.users.controller import current_user
from app.users.repo import get_refresh_token

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/meetings")
def create_calendar_meeting(meeting: MeetingIn, user=Depends(current_user), conn=Depends(get_db)):
    """Create a meeting in the user's Google Calendar."""
    refresh_token = get_refresh_token(conn, user)
    if not refresh_token:
        raise HTTPException(401, "Google Calendar is not connected. Sign in with Google again.")

    try:
        return create_meeting(refresh_token, meeting)
    except RefreshError:
        # Token revoked, or expired (Testing-mode tokens last 7 days).
        raise HTTPException(401, "Google access expired. Sign in with Google again.") from None
    except HttpError as e:
        if e.status_code == 403:
            raise HTTPException(403, "Calendar permission was not granted. Sign in again.") from None
        raise HTTPException(502, "Google Calendar rejected the request.") from None
