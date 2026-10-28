import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """A row of the `users` table (see migrations/001_users.sql)."""

    id: uuid.UUID
    email: str
    name: str | None = None
    picture_url: str | None = None
    # Secret: never return it from the API or write it to logs.
    refresh_token: str | None = None
    google_sub: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
