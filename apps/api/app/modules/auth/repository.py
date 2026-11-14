import uuid

import asyncpg

from app.database.models import User

USER_COLUMNS = "id, google_sub, email, name, picture_url, refresh_token, created_at, updated_at"


async def save_google_user(
    conn: asyncpg.Connection, info: dict, refresh_token: str | None
) -> User:
    """Create the user, or update them if this Google account signed in before."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO users (google_sub, email, name, picture_url, refresh_token)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (google_sub) DO UPDATE
        SET email = EXCLUDED.email,
            name = EXCLUDED.name,
            picture_url = EXCLUDED.picture_url,
            -- Google does not always send a refresh token; keep the stored one then.
            refresh_token = COALESCE(EXCLUDED.refresh_token, users.refresh_token),
            updated_at = now()
        RETURNING {USER_COLUMNS}
        """,
        info.get("sub"),
        info.get("email"),
        info.get("name"),
        info.get("picture"),
        refresh_token,
    )
    return User(**dict(row))


async def get_user_by_id(conn: asyncpg.Connection, user_id: uuid.UUID) -> User | None:
    row = await conn.fetchrow(f"SELECT {USER_COLUMNS} FROM users WHERE id = $1", user_id)
    return User(**dict(row)) if row else None
