import uuid

from pydantic import BaseModel


class User(BaseModel):
    """A user as the API returns it. Deliberately has no refresh_token field."""
    id: uuid.UUID
    email: str
    name: str | None
    picture_url: str | None
