import logging

import asyncpg

from app.config import get_settings
from app.database.models import User
from app.modules.auth.repository import save_google_user

logger = logging.getLogger(__name__)


class SignInRejected(Exception):
    """The Google account may not sign in; `reason` is the code sent to the PWA."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def allowed_emails() -> set[str]:
    raw = get_settings().ALLOWED_GOOGLE_EMAILS
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def sign_in_google_user(db: asyncpg.Connection, token: dict) -> User:
    """Check the Google account against the allowlist and save it."""
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not info.get("email_verified") or email not in allowed_emails():
        logger.info("Google sign-in rejected: account not allowed")
        raise SignInRejected("not_allowed")

    user = await save_google_user(db, info, token.get("refresh_token"))
    logger.info("Google sign-in succeeded for user %s", user.id)
    return user
