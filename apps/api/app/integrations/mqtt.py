"""MQTT client (HiveMQ Cloud, TLS, MQTT v5). Transport only, no business logic.

paho runs its own network thread (loop_start), so nothing here touches the
FastAPI event loop. Subscriptions are (re)made on every connect.
"""

import json
import logging
from collections.abc import Callable

import paho.mqtt.client as paho
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

logger = logging.getLogger(__name__)

# Keep the broker-side session (and its queued QoS 1 messages) across a short restart.
SESSION_EXPIRY_SECONDS = 3600
KEEPALIVE_SECONDS = 30

MessageHandler = Callable[[str, bytes], None]


class MqttClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        client_id: str,
        subscriptions: list[str],
    ):
        self._host = host
        self._port = port
        self._subscriptions = subscriptions
        self._on_message: MessageHandler | None = None
        self._client = paho.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=paho.MQTTv5,
        )
        if username:
            self._client.username_pw_set(username, password)
        if port != 1883:
            self._client.tls_set()  # system CA store; HiveMQ Cloud uses Let's Encrypt
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.on_connect = self._handle_connect
        self._client.on_disconnect = self._handle_disconnect
        self._client.on_message = self._handle_message

    def start(self, on_message: MessageHandler) -> None:
        self._on_message = on_message
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = SESSION_EXPIRY_SECONDS
        self._client.connect_async(
            self._host,
            self._port,
            keepalive=KEEPALIVE_SECONDS,
            clean_start=False,
            properties=properties,
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def publish(self, topic: str, payload: dict) -> bool:
        """Queue a QoS 1 message. True if paho accepted it (it retries until the broker acks)."""
        info = self._client.publish(topic, json.dumps(payload), qos=1, retain=False)
        if info.rc != paho.MQTT_ERR_SUCCESS:
            logger.warning("mqtt publish to %s failed: rc=%s", topic, info.rc)
            return False
        return True

    def _handle_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.warning("mqtt connect refused: %s", reason_code)
            return
        logger.info("mqtt connected to %s:%s", self._host, self._port)
        client.subscribe([(topic, 1) for topic in self._subscriptions])
        logger.info("mqtt subscribed to %s", ", ".join(self._subscriptions))

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code != 0:
            logger.warning("mqtt disconnected (%s); reconnecting", reason_code)

    def _handle_message(self, client, userdata, message) -> None:
        if self._on_message is None:
            return
        try:
            self._on_message(message.topic, message.payload)
        except Exception:
            logger.exception("mqtt message handler failed for %s", message.topic)
