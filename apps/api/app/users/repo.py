import psycopg

from app.users.model import User


def save_google_user(
    conn,
    info: dict,
    refresh_token: str | None
) -> User:
    """Create the user, or update them if this Google account signed in before."""
    row = conn.execute(
        """
        INSERT INTO users (google_sub, email, name, picture_url, refresh_token)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (google_sub) DO UPDATE
        SET email = EXCLUDED.email,
            name = EXCLUDED.name,
            picture_url = EXCLUDED.picture_url,
            -- Google does not always send a refresh token; keep the stored one then.
            refresh_token = COALESCE(EXCLUDED.refresh_token, users.refresh_token),
            updated_at = now()
        RETURNING id, email, name, picture_url
        """,
        (info.get("sub"), info.get("email"), info.get("name"), info.get("picture"), refresh_token),
    ).fetchone()
    conn.commit()
    return User.model_validate(row)


def get_user_by_id(conn: psycopg.Connection, user_id: str) -> User | None:
    row = conn.execute("SELECT id, email, name, picture_url FROM users WHERE id = %s", (user_id,)).fetchone()
    return User.model_validate(row) if row else None


def get_refresh_token(conn: psycopg.Connection, user: User) -> str | None:
    """Only for the Google Calendar integration (Step 7)."""
    row = conn.execute("SELECT refresh_token FROM users WHERE id = %s", (user.id,)).fetchone()
    return row["refresh_token"] if row else None
