from uuid import UUID

from psycopg import Connection


def get_refresh_token_encrypted(conn: Connection, user_id: UUID) -> str | None:
    """The user's encrypted Google refresh token, or None if Calendar was not granted."""
    row = conn.execute(
        "SELECT google_refresh_token_encrypted FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    return row["google_refresh_token_encrypted"] if row else None
