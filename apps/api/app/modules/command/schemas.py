from enum import Enum

from pydantic import BaseModel, Field

MAX_COMMAND_CHARS = 2000


class Intent(str, Enum):
    CREATE_NOTE = "CREATE_NOTE"
    CREATE_CHECKLIST = "CREATE_CHECKLIST"
    CREATE_REMINDER = "CREATE_REMINDER"
    CREATE_EVENT = "CREATE_EVENT"
    READ_EVENTS = "READ_EVENTS"
    UNKNOWN = "UNKNOWN"


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_COMMAND_CHARS)
    request_id: str | None = None


class CommandResponse(BaseModel):
    text: str
    intent: Intent
    slots: dict[str, str]
