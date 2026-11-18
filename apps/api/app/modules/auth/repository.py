from app.config import settings
from app.core.security import hash_token, new_session_token


def upsert_google_user(
    conn, google_sub: str, email: str, email_verified: bool, name: str | None, picture_url: str | None
) -> dict:
    """Create the user for this Google account, or refresh the existing one."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (google_sub, email, email_verified, name, picture_url, last_login_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (google_sub) DO UPDATE
            SET email = EXCLUDED.email,
                email_verified = EXCLUDED.email_verified,
                name = EXCLUDED.name,
                picture_url = EXCLUDED.picture_url,
                updated_at = now(),
                last_login_at = now()
            RETURNING id, email, name, picture_url
            """,
            (google_sub, email, email_verified, name, picture_url),
        )
        return cur.fetchone()


def get_user_by_id(conn, user_id) -> dict | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id, email, name, picture_url FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def create_session(conn, user_id, user_agent: str | None) -> str:
    """Store a new session and return the raw token for the cookie."""
    raw_token = new_session_token()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions (user_id, token_hash, expires_at, user_agent)
            VALUES (%s, %s, now() + make_interval(days => %s), %s)
            """,
            (user_id, hash_token(raw_token), settings.session_ttl_days, user_agent),
        )
    return raw_token


def get_session_user(conn, raw_token: str) -> dict | None:
    """Return the user for a valid session token, or None if it is unknown, expired or revoked."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions s
            SET last_seen_at = now()
            FROM users u
            WHERE s.token_hash = %s
              AND s.user_id = u.id
              AND s.revoked_at IS NULL
              AND s.expires_at > now()
            RETURNING u.id, u.email, u.name, u.picture_url
            """,
            (hash_token(raw_token),),
        )
        return cur.fetchone()


def revoke_session(conn, raw_token: str) -> None:
    """Revoke the session so its cookie stops working immediately."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET revoked_at = now() WHERE token_hash = %s AND revoked_at IS NULL",
            (hash_token(raw_token),),
        )
