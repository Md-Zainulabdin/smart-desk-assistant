from collections.abc import AsyncIterator

import asyncpg
from fastapi import Depends, HTTPException, Request, status

from app.core.security import end_session, session_user_id
from app.database.connection import get_connection
from app.database.models import User
from app.modules.auth.repository import get_user_by_id


async def get_db() -> AsyncIterator[asyncpg.Connection]:
    async for conn in get_connection():
        yield conn


async def current_user(request: Request, db: asyncpg.Connection = Depends(get_db)) -> User:
    """Dependency for protected routes: the signed-in user, or 401."""
    user_id = session_user_id(request)
    user = await get_user_by_id(db, user_id) if user_id else None
    if user is None:
        end_session(request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    return user
