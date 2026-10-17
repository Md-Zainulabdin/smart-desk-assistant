from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.db import get_db
from app.users.controller import current_user
from app.users.repo import save_google_user

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
async def google_callback(request: Request, conn=Depends(get_db)):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(f"{settings.PWA_ORIGIN}/?auth_error=google_error")

    info = token["userinfo"]
    allowed = [e.strip().lower() for e in settings.ALLOWED_GOOGLE_EMAILS.split(",")]
    if not info.get("email_verified") or info["email"].lower() not in allowed:
        return RedirectResponse(f"{settings.PWA_ORIGIN}/?auth_error=not_allowed")

    user = save_google_user(conn, info, token.get("refresh_token"))
    request.session.clear()
    request.session["user_id"] = str(user.id)
    return RedirectResponse(settings.PWA_ORIGIN)


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
