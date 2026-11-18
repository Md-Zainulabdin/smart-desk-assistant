def get_refresh_token(conn, user_id) -> str | None:
    """The Google refresh token saved for this user, if Calendar was connected."""
    with conn.cursor() as cur:
        cur.execute("SELECT refresh_token FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return row["refresh_token"] if row else None


def latest_refresh_token(conn) -> str | None:
    """The most recently saved refresh token (one user per desk)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT refresh_token FROM users
            WHERE refresh_token IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
    return row["refresh_token"] if row else None
