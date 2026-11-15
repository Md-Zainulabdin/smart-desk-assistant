from app.modules.auth import repository


class SignInRejected(Exception):
    """Sign-in refused. `code` is the short reason sent to the PWA."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def sign_in_with_google(conn, claims: dict, user_agent: str | None, old_token: str | None = None) -> str:
    """Create or find the user for verified Google claims and return a new session token."""
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise SignInRejected("google_error")
    if claims.get("email_verified") is not True:
        raise SignInRejected("email_unverified")

    user = repository.upsert_google_user(
        conn, sub, email, True, claims.get("name"), claims.get("picture")
    )
    if old_token:
        repository.revoke_session(conn, old_token)
    return repository.create_session(conn, user["id"], user_agent)


def sign_out(conn, raw_token: str | None) -> None:
    if raw_token:
        repository.revoke_session(conn, raw_token)
