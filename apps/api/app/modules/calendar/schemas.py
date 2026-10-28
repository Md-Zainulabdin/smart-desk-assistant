from datetime import datetime

from pydantic import BaseModel, model_validator


class MeetingIn(BaseModel):
    title: str
    start: datetime
    end: datetime
    timezone: str = "Asia/Karachi"
    attendees: list[str] = []
    description: str = ""

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class MeetingOut(BaseModel):
    id: str
    link: str
    meet_link: str | None
