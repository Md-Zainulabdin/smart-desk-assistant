from app.config import settings
from app.core.security import encrypt_token
from app.modules.auth import repository
from app.modules.auth.oauth import CALENDAR_EVENTS_SCOPE


class SignInRejected(Exception):
    """Sign-in refused. `code` is the short reason sent to the PWA."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _is_allowed(email: str) -> bool:
    """Enforce ALLOWED_GOOGLE_EMAILS. An empty allowlist allows any verified account."""
    allowed = [e.strip().lower() for e in settings.allowed_google_emails.split(",") if e.strip()]
    return not allowed or email.lower() in allowed


def sign_in_with_google(
    conn,
    claims: dict,
    user_agent: str | None,
    old_token: str | None = None,
    google_token: dict | None = None,
) -> str:
    """Create or find the user for verified Google claims and return a new session token.

    If the user granted Calendar access, the Google refresh token is stored encrypted.
    """
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise SignInRejected("google_error")
    if claims.get("email_verified") is not True:
        raise SignInRejected("email_unverified")
    if not _is_allowed(email):
        raise SignInRejected("not_allowed")

    user = repository.upsert_google_user(
        conn, sub, email, True, claims.get("name"), claims.get("picture")
    )
    google_token = google_token or {}
    refresh_token = google_token.get("refresh_token")
    # The user can untick Calendar on the consent screen; sign-in still works without it.
    if refresh_token and CALENDAR_EVENTS_SCOPE in google_token.get("scope", "").split():
        repository.save_google_refresh_token(conn, user["id"], encrypt_token(refresh_token))
    if old_token:
        repository.revoke_session(conn, old_token)
    return repository.create_session(conn, user["id"], user_agent)


def sign_out(conn, raw_token: str | None) -> None:
    if raw_token:
        repository.revoke_session(conn, raw_token)
