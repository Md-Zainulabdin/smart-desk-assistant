from enum import Enum

from pydantic import BaseModel, Field

MAX_COMMAND_CHARS = 2000


class Intent(str, Enum):
    CREATE_NOTE = "CREATE_NOTE"
    CREATE_REMINDER = "CREATE_REMINDER"
    CREATE_EVENT = "CREATE_EVENT"
    READ_EVENTS = "READ_EVENTS"
    WEB_SEARCH = "WEB_SEARCH"
    UNKNOWN = "UNKNOWN"


class Status(str, Enum):
    READY = "ready"
    NEEDS_CLARIFICATION = "needs_clarification"
    UNSUPPORTED = "unsupported"


class CommandContext(BaseModel):
    """Pending instruction sent back by the orchestrator for a follow-up reply."""

    intent: Intent
    slots: dict[str, str] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_COMMAND_CHARS)
    request_id: str | None = None
    timezone: str | None = None
    context: CommandContext | None = None


class CommandResponse(BaseModel):
    text: str
    intent: Intent
    status: Status
    slots: dict[str, str] = Field(default_factory=dict)
    missing: list[str] = Field(default_factory=list)
    clarification: str | None = None
