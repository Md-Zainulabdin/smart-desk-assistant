from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


class MeetingIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    start: datetime
    end: datetime
    # IANA name such as "Asia/Karachi". Defaults to DEFAULT_TIMEZONE.
    timezone: str | None = None
    attendees: list[Email] = Field(default_factory=list, max_length=50)
    description: Annotated[str, StringConstraints(max_length=5000)] = ""
    # Optional: send the same request_id on a retry and no second event is booked.
    request_id: Annotated[
        str | None, StringConstraints(min_length=1, max_length=255, pattern=r"^[^\x00]+$")
    ] = None

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown timezone") from None
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> MeetingIn:
        if (self.start.tzinfo is None) != (self.end.tzinfo is None):
            raise ValueError("start and end must both include a UTC offset, or both omit it")
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class MeetingOut(BaseModel):
    id: str
    link: str
    meet_link: str | None


class MeetingSummary(BaseModel):
    """One event read from the user's Google Calendar."""

    id: str
    title: str
    start: datetime
    end: datetime
    all_day: bool = False
    link: str
    meet_link: str | None = None
