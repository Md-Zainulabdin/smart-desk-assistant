"""Device messages: one spoken command in over MQTT, one reply out.

transcript -> validate -> owner lookup -> record (drop redeliveries)
-> orchestrator -> record result -> reply for nova/<id>/response.
"""

import json
import logging
import re
from uuid import UUID

from psycopg import Connection
from pydantic import ValidationError

from app.modules.device import repository
from app.modules.device.schemas import (
    DEVICE_ID_PATTERN,
    Device,
    DeviceReply,
    MessageStatus,
    ReplyTopic,
    TranscriptMessage,
)
from app.modules.orchestrator import service as orchestrator
from app.modules.orchestrator.schemas import AssistantRequest

logger = logging.getLogger(__name__)

NOT_LINKED_REPLY = "This device isn't linked to an account yet. Link it from the app."
FAILED_REPLY = "Sorry, something went wrong."


class DeviceAlreadyClaimed(Exception):
    """The device belongs to another user."""


def claim(conn: Connection, user_id: UUID, device_id: str, name: str | None) -> Device:
    device = repository.claim_device(conn, user_id, device_id, name)
    if device is None:
        raise DeviceAlreadyClaimed(device_id)
    return device


def parse_transcript(topic_device_id: str, payload: bytes) -> TranscriptMessage | None:
    """The validated transcript, or None. Never logs the text."""
    try:
        message = TranscriptMessage.model_validate(json.loads(payload))
    except (ValueError, ValidationError):
        logger.warning("mqtt transcript rejected: invalid payload from %s", topic_device_id)
        return None
    if message.device != topic_device_id:
        logger.warning("mqtt transcript rejected: device mismatch on %s", topic_device_id)
        return None
    return message


def handle_transcript(conn: Connection, topic_device_id: str, payload: bytes) -> DeviceReply | None:
    """Run one spoken command. Returns the reply to publish, or None to stay silent."""
    message = parse_transcript(topic_device_id, payload)
    if message is None:
        return None

    device = repository.get_device(conn, message.device)
    if device is None:
        logger.info("mqtt transcript from unlinked device %s", message.device)
        return _reply(message.device, NOT_LINKED_REPLY, message.id, recorded=False)

    if not repository.begin_message(conn, device.device_id, message.id):
        return _replay(conn, device.device_id, message.id)

    return _run(conn, device, message)


def _run(conn: Connection, device: Device, message: TranscriptMessage) -> DeviceReply:
    request = AssistantRequest(
        text=message.text, request_id=f"mqtt:{device.device_id}:{message.id}"
    )
    try:
        response = orchestrator.handle(conn, device.user_id, request)
    except Exception as error:  # any failure must still answer the device
        conn.rollback()
        logger.exception("mqtt transcript %s/%s failed", device.device_id, message.id)
        repository.finish_message(
            conn,
            device.device_id,
            message.id,
            MessageStatus.FAILED,
            FAILED_REPLY,
            error=type(error).__name__,
        )
        return _reply(device.device_id, FAILED_REPLY, message.id)

    repository.finish_message(
        conn,
        device.device_id,
        message.id,
        MessageStatus.DONE,
        response.reply,
        outcome=response.outcome.value,
        intent=response.intent.value,
    )
    return _reply(device.device_id, response.reply, message.id)


def _replay(conn: Connection, device_id: str, message_id: str) -> DeviceReply | None:
    """A QoS 1 redelivery: re-send the stored reply, never re-run the action."""
    stored = repository.get_message(conn, device_id, message_id)
    if stored is None or stored.status is MessageStatus.PROCESSING or not stored.reply:
        logger.info("mqtt transcript %s/%s already in progress", device_id, message_id)
        return None
    logger.info("mqtt transcript %s/%s is a duplicate; re-sending reply", device_id, message_id)
    return _reply(device_id, stored.reply, message_id)


def _reply(device_id: str, text: str, message_id: str, *, recorded: bool = True) -> DeviceReply:
    # "r-" keeps reply ids apart from transcript ids in the firmware's duplicate check.
    return DeviceReply(
        device_id=device_id,
        topic=ReplyTopic.RESPONSE,
        text=text,
        id=f"r-{message_id}",
        message_id=message_id if recorded else None,
    )


def reminder_reply(device_id: str, reminder_id: str, text: str) -> DeviceReply:
    """A due reminder for nova/<id>/reminder. Hook for the future reminders scheduler."""
    return DeviceReply(
        device_id=device_id, topic=ReplyTopic.REMINDER, text=text, id=f"rem-{reminder_id}"
    )


def handle_status(conn: Connection, device_id: str, payload: bytes) -> None:
    """nova/<id>/status: retained "online" / "offline" (Last Will)."""
    state = payload.decode("utf-8", errors="replace").strip().lower()
    if state not in ("online", "offline"):
        logger.warning("mqtt status ignored: unknown value from %s", device_id)
        return
    repository.set_status(conn, device_id, state == "online")


def is_device_id(value: str) -> bool:
    return re.fullmatch(DEVICE_ID_PATTERN, value) is not None
