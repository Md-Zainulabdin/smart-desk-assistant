import uuid

from pydantic import BaseModel


class UserOut(BaseModel):
    """What the API returns about a user. Never includes google_sub or tokens."""

    id: uuid.UUID
    email: str
    name: str | None
    picture_url: str | None
