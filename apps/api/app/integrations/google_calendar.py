import uuid

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.modules.calendar.schemas import MeetingIn


def calendar_service(refresh_token: str):
    settings = get_settings()
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service

def create_meeting(refresh_token: str, meeting: MeetingIn):
    service = calendar_service(refresh_token)
    event = {
        "summary": meeting.title,
        "description": meeting.description,
        "start": {"dateTime": meeting.start.isoformat(), "timeZone": meeting.timezone},
        "end": {"dateTime": meeting.end.isoformat(), "timeZone": meeting.timezone},
        "attendees": [{"email": email} for email in meeting.attendees],
        "conferenceData": {                           
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },                                                  
    }

    created_event = service.events().insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all").execute()
    return {"id": created_event["id"], "link": created_event["htmlLink"], "meet_link": created_event.get("hangoutLink")}

