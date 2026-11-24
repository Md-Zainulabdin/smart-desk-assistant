from datetime import datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.modules.command.schemas import MAX_COMMAND_CHARS

# The last 3 MAC bytes, lowercase hex, as the firmware puts in its topics.
DEVICE_ID_PATTERN = r"^[0-9a-f]{6}$"

DeviceId = Annotated[str, StringConstraints(pattern=DEVICE_ID_PATTERN)]


class TranscriptMessage(BaseModel):
    """Payload on nova/<id>/transcript."""

    device: DeviceId
    id: Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[^\x00]+$")]
    text: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=MAX_COMMAND_CHARS, pattern=r"^[^\x00]+$"
        ),
    ]
    audio_ms: int = Field(default=0, ge=0)


class DeviceClaim(BaseModel):
    device_id: DeviceId
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None = None

    @field_validator("device_id", mode="before")
    @classmethod
    def _normalize_device_id(cls, value: object) -> object:
        # Accept " CEE330 " as typed from the device screen or serial log.
        return value.strip().lower() if isinstance(value, str) else value


class Device(BaseModel):
    device_id: str
    user_id: UUID
    name: str | None
    online: bool
    last_seen_at: datetime | None
    created_at: datetime


class DeviceOut(BaseModel):
    device_id: str
    name: str | None
    online: bool
    last_seen_at: datetime | None


class MessageStatus(str, Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DeviceMessage(BaseModel):
    device_id: str
    message_id: str
    status: MessageStatus
    reply: str | None
    published_at: datetime | None


class ReplyTopic(str, Enum):
    RESPONSE = "response"  # the answer to a spoken command
    REMINDER = "reminder"  # a reminder that came due; pinned on the device's Home screen


class DeviceReply(BaseModel):
    """What to publish back to nova/<device_id>/<topic>."""

    device_id: str
    topic: ReplyTopic
    text: str
    id: str
    # The transcript this answers, so the bridge can record the publish. None for unclaimed devices.
    message_id: str | None = None

    def payload(self) -> dict[str, str]:
        return {"text": self.text, "id": self.id}
