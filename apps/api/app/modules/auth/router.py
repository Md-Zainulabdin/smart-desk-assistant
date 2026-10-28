import logging

import asyncpg
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.core.security import end_session, start_session
from app.database.models import User
from app.dependencies import current_user, get_db
from app.modules.auth.schemas import LogoutOut, UserOut
from app.modules.auth.service import SignInRejected, sign_in_google_user

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/calendar.events"},
)


@router.get("/google/start")
async def google_start(request: Request):
    # offline + consent: Google always sends a refresh token, needed for Calendar later.
    return await oauth.google.authorize_redirect(
        request, settings.GOOGLE_REDIRECT_URI, access_type="offline", prompt="consent"
    )


@router.get("/google/callback")
async def google_callback(request: Request, db: asyncpg.Connection = Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logger.warning("Google OAuth failed: %s", e.error)
        return RedirectResponse(f"{settings.PWA_ORIGIN}/?auth_error=google_error")

    try:
        user = await sign_in_google_user(db, token)
    except SignInRejected as e:
        return RedirectResponse(f"{settings.PWA_ORIGIN}/?auth_error={e.reason}")

    start_session(request, user.id)
    return RedirectResponse(settings.PWA_ORIGIN)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", response_model=LogoutOut)
def logout(request: Request):
    end_session(request)
    return LogoutOut(ok=True)
