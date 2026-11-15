from authlib.integrations.starlette_client import OAuth

from app.config import settings

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

# Sign-in only. Calendar scopes are requested by a separate flow (Phase 3).
SIGN_IN_SCOPES = "openid email profile"

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url=GOOGLE_DISCOVERY_URL,
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    client_kwargs={"scope": SIGN_IN_SCOPES},
)
