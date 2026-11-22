import logging

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from starlette.responses import RedirectResponse

from app.config import settings
from app.core.security import clear_session_cookie, set_session_cookie
from app.db import pool
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.oauth import oauth
from app.modules.auth.schemas import UserOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(f"{settings.pwa_origin}/?auth_error={code}", status_code=status.HTTP_303_SEE_OTHER)


def _sign_in(claims: dict, user_agent: str | None, old_token: str | None, token: dict) -> str:
    with pool.connection() as conn:
        return service.sign_in_with_google(conn, claims, user_agent, old_token, token)


def _sign_out(raw_token: str | None) -> None:
    with pool.connection() as conn:
        service.sign_out(conn, raw_token)


@router.get("/google/start")
async def google_start(request: Request):
    # offline + consent: Google returns a refresh token, so Calendar bookings work later.
    return await oauth.google.authorize_redirect(
        request, settings.google_redirect_uri, access_type="offline", prompt="consent select_account"
    )


@router.get("/google/callback")
async def google_callback(request: Request):
    # Google sends ?error=... when the user cancels. Only our own short codes go to the PWA.
    if request.query_params.get("error"):
        code = "access_denied" if request.query_params["error"] == "access_denied" else "google_error"
        logger.warning("google sign-in failed: %s", code)
        return _error_redirect(code)

    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        logger.warning("google sign-in failed: state_mismatch")
        return _error_redirect("state_mismatch")

    claims = token.get("userinfo")
    if not claims:
        logger.warning("google sign-in failed: google_error")
        return _error_redirect("google_error")

    try:
        raw_token = await run_in_threadpool(
            _sign_in,
            dict(claims),
            request.headers.get("user-agent"),
            request.cookies.get(settings.session_cookie_name),
            dict(token),
        )
    except service.SignInRejected as rejected:
        logger.warning("google sign-in failed: %s", rejected.code)
        return _error_redirect(rejected.code)

    request.session.clear()  # drop the temporary OAuth state
    response = RedirectResponse(settings.pwa_origin, status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, raw_token)
    return response


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request):
    # CSRF check: the PWA, or this API's own pages (the dev playground), may sign out.
    origin = request.headers.get("origin")
    if origin is not None and origin not in {settings.pwa_origin, settings.api_base_url}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")

    await run_in_threadpool(_sign_out, request.cookies.get(settings.session_cookie_name))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookie(response)
    return response
