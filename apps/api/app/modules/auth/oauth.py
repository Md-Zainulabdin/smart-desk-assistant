from authlib.integrations.starlette_client import OAuth

from app.config import settings

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
# One consent at sign-in: profile + permission to create Calendar events.
SIGN_IN_SCOPES = f"openid email profile {CALENDAR_EVENTS_SCOPE}"

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=GOOGLE_DISCOVERY_URL,
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={"scope": SIGN_IN_SCOPES},
)
