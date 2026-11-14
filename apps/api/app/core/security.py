import uuid

from starlette.requests import Request

# Auth uses a signed session cookie (SessionMiddleware) that holds only the user id.
# Tokens never go in the cookie.
SESSION_USER_KEY = "user_id"


def start_session(request: Request, user_id: uuid.UUID) -> None:
    request.session.clear()
    request.session[SESSION_USER_KEY] = str(user_id)


def end_session(request: Request) -> None:
    request.session.clear()


def session_user_id(request: Request) -> uuid.UUID | None:
    """The signed-in user's id, or None if missing or malformed."""
    value = request.session.get(SESSION_USER_KEY)
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None
