from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from app.jobs import mqtt_bridge
from app.jobs.mqtt_bridge import MqttBridge
from app.modules.device import repository, service
from app.modules.device.schemas import DeviceReply, ReplyTopic


class FakeClient:
    def __init__(self):
        self.published = []
        self.accept = True

    def start(self, on_message):
        self.on_message = on_message

    def stop(self):
        pass

    def publish(self, topic, payload):
        self.published.append((topic, payload))
        return self.accept


@pytest.fixture
def bridge(monkeypatch):
    conn = Mock()

    @contextmanager
    def connection():
        yield conn

    monkeypatch.setattr(mqtt_bridge.pool, "connection", connection)
    client = FakeClient()
    return MqttBridge(client, "nova"), client, conn


def reply(message_id="m-1"):
    return DeviceReply(
        device_id="cee330",
        topic=ReplyTopic.RESPONSE,
        text="Saved your note.",
        id=f"r-{message_id}",
        message_id=message_id,
    )


def test_transcript_reply_is_published_to_the_device_response_topic(bridge, monkeypatch):
    bridge_, client, conn = bridge
    monkeypatch.setattr(service, "handle_transcript", Mock(return_value=reply()))
    mark_published = Mock()
    monkeypatch.setattr(repository, "mark_published", mark_published)

    bridge_.handle_transcript("cee330", b"{}")

    assert client.published == [
        ("nova/cee330/response", {"text": "Saved your note.", "id": "r-m-1"})
    ]
    mark_published.assert_called_once_with(conn, "cee330", "m-1")


def test_failed_publish_is_not_marked_published(bridge, monkeypatch):
    bridge_, client, _ = bridge
    client.accept = False
    monkeypatch.setattr(service, "handle_transcript", Mock(return_value=reply()))
    mark_published = Mock()
    monkeypatch.setattr(repository, "mark_published", mark_published)

    bridge_.handle_transcript("cee330", b"{}")

    mark_published.assert_not_called()


def test_silent_result_publishes_nothing(bridge, monkeypatch):
    bridge_, client, _ = bridge
    monkeypatch.setattr(service, "handle_transcript", Mock(return_value=None))

    bridge_.handle_transcript("cee330", b"{}")

    assert client.published == []


def test_messages_are_routed_by_topic(bridge, monkeypatch):
    bridge_, _, _ = bridge
    submit = Mock()
    monkeypatch.setattr(bridge_._executor, "submit", submit)

    bridge_.on_message("nova/cee330/transcript", b"t")
    bridge_.on_message("nova/cee330/status", b"online")
    bridge_.on_message("nova/cee330/response", b"ignored")
    bridge_.on_message("other/cee330/transcript", b"ignored")
    bridge_.on_message("nova/NOT-HEX/transcript", b"ignored")

    assert [call.args for call in submit.call_args_list] == [
        (bridge_.handle_transcript, "cee330", b"t"),
        (bridge_.handle_status, "cee330", b"online"),
    ]


def test_bridge_stays_off_without_mqtt_host(monkeypatch):
    monkeypatch.setattr(mqtt_bridge.settings, "mqtt_host", "")
    build = Mock()
    monkeypatch.setattr(mqtt_bridge, "build_bridge", build)

    assert mqtt_bridge.start_bridge() is None
    build.assert_not_called()


def test_bridge_subscribes_to_shared_transcripts_and_status(monkeypatch):
    monkeypatch.setattr(mqtt_bridge.settings, "mqtt_host", "broker.example")
    created = {}

    class Recorder:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr(mqtt_bridge, "MqttClient", Recorder)

    mqtt_bridge.build_bridge()

    assert created["subscriptions"] == ["$share/desk-api/nova/+/transcript", "nova/+/status"]
