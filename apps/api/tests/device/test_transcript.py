import json
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.modules.command.schemas import Intent
from app.modules.device import repository, service
from app.modules.device.schemas import Device, DeviceMessage, MessageStatus, ReplyTopic
from app.modules.orchestrator.schemas import AssistantResponse, Outcome

OWNER = uuid4()
DEVICE = Device(
    device_id="cee330",
    user_id=OWNER,
    name=None,
    online=True,
    last_seen_at=None,
    created_at=datetime.now(UTC),
)


def transcript(text="take a note buy milk", msg_id="a1b2c3d4-1", device="cee330") -> bytes:
    return json.dumps({"device": device, "id": msg_id, "text": text, "audio_ms": 900}).encode()


@pytest.fixture
def world(monkeypatch):
    """Device storage in memory; the orchestrator is a Mock."""
    devices = {"cee330": DEVICE}
    messages: dict[tuple[str, str], dict] = {}

    def begin(conn, device_id, message_id):
        if (device_id, message_id) in messages:
            return False
        messages[(device_id, message_id)] = {"status": MessageStatus.PROCESSING, "reply": None}
        return True

    def get_message(conn, device_id, message_id):
        row = messages.get((device_id, message_id))
        if row is None:
            return None
        return DeviceMessage(
            device_id=device_id,
            message_id=message_id,
            status=row["status"],
            reply=row["reply"],
            published_at=None,
        )

    def finish(conn, device_id, message_id, status, reply, **extra):
        messages[(device_id, message_id)].update(status=status, reply=reply, **extra)

    monkeypatch.setattr(repository, "get_device", lambda conn, device_id: devices.get(device_id))
    monkeypatch.setattr(repository, "begin_message", begin)
    monkeypatch.setattr(repository, "get_message", get_message)
    monkeypatch.setattr(repository, "finish_message", finish)
    handle = Mock(
        return_value=AssistantResponse(
            outcome=Outcome.DONE, intent=Intent.CREATE_NOTE, reply="Saved your note."
        )
    )
    monkeypatch.setattr(service.orchestrator, "handle", handle)
    return {"messages": messages, "handle": handle, "conn": Mock()}


def test_claimed_device_gets_the_orchestrator_reply_on_response(world):
    reply = service.handle_transcript(world["conn"], "cee330", transcript())

    assert reply.topic is ReplyTopic.RESPONSE
    assert reply.payload() == {"text": "Saved your note.", "id": "r-a1b2c3d4-1"}
    assert reply.message_id == "a1b2c3d4-1"
    _conn, user_id, request = world["handle"].call_args.args
    assert user_id == OWNER
    assert request.text == "take a note buy milk"
    assert request.request_id == "mqtt:cee330:a1b2c3d4-1"
    stored = world["messages"][("cee330", "a1b2c3d4-1")]
    assert stored["status"] is MessageStatus.DONE
    assert stored["outcome"] == "done" and stored["intent"] == "CREATE_NOTE"


def test_redelivered_transcript_resends_the_reply_without_running_again(world):
    first = service.handle_transcript(world["conn"], "cee330", transcript())
    again = service.handle_transcript(world["conn"], "cee330", transcript())

    assert world["handle"].call_count == 1
    assert again.payload() == first.payload()


def test_redelivery_while_still_processing_stays_silent(world):
    world["messages"][("cee330", "a1b2c3d4-1")] = {"status": MessageStatus.PROCESSING, "reply": None}

    assert service.handle_transcript(world["conn"], "cee330", transcript()) is None
    world["handle"].assert_not_called()


def test_unlinked_device_is_told_to_link_and_nothing_runs(world):
    reply = service.handle_transcript(world["conn"], "abcdef", transcript(device="abcdef"))

    assert reply.text == service.NOT_LINKED_REPLY
    assert reply.message_id is None
    world["handle"].assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"[]",
        transcript(text="   "),
        transcript(msg_id=""),
        transcript(device="CEE330"),
        json.dumps({"device": "cee330", "id": "x"}).encode(),
    ],
)
def test_invalid_payload_is_dropped(world, payload):
    assert service.handle_transcript(world["conn"], "cee330", payload) is None
    world["handle"].assert_not_called()


def test_payload_device_must_match_the_topic(world):
    assert service.handle_transcript(world["conn"], "cee330", transcript(device="abcdef")) is None
    world["handle"].assert_not_called()


def test_orchestrator_failure_is_recorded_and_the_user_hears_a_short_apology(world):
    world["handle"].side_effect = RuntimeError("database went away")

    reply = service.handle_transcript(world["conn"], "cee330", transcript())

    assert reply.text == service.FAILED_REPLY
    world["conn"].rollback.assert_called_once()
    stored = world["messages"][("cee330", "a1b2c3d4-1")]
    assert stored["status"] is MessageStatus.FAILED
    assert stored["error"] == "RuntimeError"


def test_reminder_reply_goes_to_the_reminder_topic():
    reply = service.reminder_reply("cee330", "42", "Call mom")

    assert reply.topic is ReplyTopic.REMINDER
    assert reply.payload() == {"text": "Call mom", "id": "rem-42"}


@pytest.mark.parametrize(("payload", "online"), [(b"online", True), (b"offline", False)])
def test_status_updates_presence(monkeypatch, payload, online):
    set_status = Mock()
    monkeypatch.setattr(repository, "set_status", set_status)

    service.handle_status(Mock(), "cee330", payload)

    assert set_status.call_args.args[1:] == ("cee330", online)


def test_unknown_status_is_ignored(monkeypatch):
    set_status = Mock()
    monkeypatch.setattr(repository, "set_status", set_status)

    service.handle_status(Mock(), "cee330", b"rebooting")

    set_status.assert_not_called()
