from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.db import get_db
from app.modules.auth import repository


def get_current_user(request: Request, conn=Depends(get_db)) -> dict:
    """Return the user for the session cookie, or raise 401 if it is missing, unknown, expired or revoked."""
    raw_token = request.cookies.get(settings.session_cookie_name)
    user = repository.get_session_user(conn, raw_token) if raw_token else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
