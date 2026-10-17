from fastapi import Depends, HTTPException, Request, status

from app.db import get_db
from app.users.model import User
from app.users.repo import get_user_by_id


def current_user(request: Request, conn=Depends(get_db)) -> User:
    """Dependency for protected routes: the signed-in user, or 401."""

    user_id = request.session.get("user_id")
    user = get_user_by_id(conn, user_id) if user_id else None
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user