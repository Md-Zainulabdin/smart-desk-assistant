from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.modules.command.schemas import MAX_COMMAND_CHARS, Intent


class AssistantRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_COMMAND_CHARS)
    # Send the same request_id when retrying, so the action is not done twice.
    request_id: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"^[^\x00]+$")
    timezone: str | None = None


class Outcome(str, Enum):
    DONE = "done"  # the action was carried out
    NEEDS_CLARIFICATION = "needs_clarification"  # `reply` is a question; answer it next
    UNSUPPORTED = "unsupported"  # not understood, or not built yet
    FAILED = "failed"  # understood, but the action failed; `reply` says why


class AssistantResponse(BaseModel):
    outcome: Outcome
    intent: Intent
    # One sentence to show or speak to the user.
    reply: str
    # What was created or found, e.g. {"note_id": ...}, {"event_id", "link", "meet_link"}
    # or {"query", "results": [{"title", "url", "snippet"}]}.
    result: dict[str, Any] = Field(default_factory=dict)
