from enum import Enum

from pydantic import BaseModel


class Intent(str, Enum):
    CREATE_NOTE = "CREATE_NOTE"
    CREATE_CHECKLIST = "CREATE_CHECKLIST"
    CREATE_REMINDER = "CREATE_REMINDER"
    CREATE_EVENT = "CREATE_EVENT"
    READ_EVENTS = "READ_EVENTS"
    UNKNOWN = "UNKNOWN"


class SttResponse(BaseModel):
    transcript: str
    language: str
    intent: Intent
    slots: dict[str, str]
    model: str
