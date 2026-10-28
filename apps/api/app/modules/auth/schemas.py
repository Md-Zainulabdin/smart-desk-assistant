import uuid

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    """A user as the API returns it. Deliberately has no refresh_token field."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    picture_url: str | None


class LogoutOut(BaseModel):
    ok: bool
