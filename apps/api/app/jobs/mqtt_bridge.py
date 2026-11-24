"""Long-running bridge between Nova devices (MQTT) and the orchestrator.

Subscribes to <root>/+/transcript (shared, so one worker handles each message)
and <root>/+/status. Work runs on a small thread pool, never on paho's network
thread, and each job takes its own pooled database connection.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings
from app.db import pool
from app.integrations.mqtt import MqttClient
from app.modules.device import repository, service
from app.modules.device.schemas import DeviceReply

logger = logging.getLogger(__name__)

SHARE_GROUP = "desk-api"
WORKERS = 2


class MqttBridge:
    def __init__(self, client: MqttClient, root: str):
        self.client = client
        self.root = root
        self._executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="mqtt-job")

    def start(self) -> None:
        self.client.start(self.on_message)

    def stop(self) -> None:
        self.client.stop()
        self._executor.shutdown(wait=True)

    def on_message(self, topic: str, payload: bytes) -> None:
        """Runs on paho's thread: route and hand off, nothing slow here."""
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != self.root or not service.is_device_id(parts[1]):
            logger.warning("mqtt message on unexpected topic ignored")
            return
        _, device_id, kind = parts
        if kind == "transcript":
            self._executor.submit(self.handle_transcript, device_id, payload)
        elif kind == "status":
            self._executor.submit(self.handle_status, device_id, payload)

    def handle_transcript(self, device_id: str, payload: bytes) -> None:
        try:
            with pool.connection() as conn:
                reply = service.handle_transcript(conn, device_id, payload)
                if reply is not None and self.publish(reply) and reply.message_id:
                    repository.mark_published(conn, reply.device_id, reply.message_id)
        except Exception:
            logger.exception("mqtt transcript job failed for %s", device_id)

    def handle_status(self, device_id: str, payload: bytes) -> None:
        try:
            with pool.connection() as conn:
                service.handle_status(conn, device_id, payload)
        except Exception:
            logger.exception("mqtt status job failed for %s", device_id)

    def publish(self, reply: DeviceReply) -> bool:
        topic = f"{self.root}/{reply.device_id}/{reply.topic.value}"
        return self.client.publish(topic, reply.payload())


_bridge: MqttBridge | None = None


def build_bridge() -> MqttBridge:
    root = settings.mqtt_topic_root
    client = MqttClient(
        host=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_username,
        password=settings.mqtt_password,
        client_id=settings.mqtt_client_id,
        subscriptions=[f"$share/{SHARE_GROUP}/{root}/+/transcript", f"{root}/+/status"],
    )
    return MqttBridge(client, root)


def start_bridge() -> MqttBridge | None:
    """Start the bridge if MQTT is configured. Returns it, or None when disabled."""
    global _bridge
    if not settings.mqtt_host:
        logger.info("mqtt bridge disabled (MQTT_HOST is empty)")
        return None
    _bridge = build_bridge()
    _bridge.start()
    return _bridge


def stop_bridge() -> None:
    global _bridge
    if _bridge is not None:
        _bridge.stop()
        _bridge = None


def get_bridge() -> MqttBridge | None:
    """The running bridge, for publishing reminders later."""
    return _bridge
