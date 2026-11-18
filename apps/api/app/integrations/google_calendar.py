import asyncio
import json
import logging
import math
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import paho.mqtt.client as mqtt
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import get_settings
from app.modules.auth.repository import latest_refresh_token
from app.modules.calendar.schemas import MeetingIn

logger = logging.getLogger(__name__)


def calendar_service(refresh_token: str):
    settings = get_settings()
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
    )
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service

def create_meeting(refresh_token: str, meeting: MeetingIn):
    service = calendar_service(refresh_token)
    event = {
        "summary": meeting.title,
        "description": meeting.description,
        "start": {"dateTime": meeting.start.isoformat(), "timeZone": meeting.timezone},
        "end": {"dateTime": meeting.end.isoformat(), "timeZone": meeting.timezone},
        "attendees": [{"email": email} for email in meeting.attendees],
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    created_event = service.events().insert(calendarId="primary", body=event, conferenceDataVersion=1, sendUpdates="all").execute()
    return {"id": created_event["id"], "link": created_event["htmlLink"], "meet_link": created_event.get("hangoutLink")}


# ---------------------------------------------------------- desk reminders ----

SENT_FILE = Path(__file__).resolve().parents[2] / "sent.json"  # apps/api/sent.json
REMINDER_POLL_SECONDS = 60  # use 10-15 for the live demo
# Used when the token was granted before the calendarlist.readonly scope was added.
FALLBACK_REMINDERS = [{"method": "popup", "minutes": 10}]


def load_sent() -> set[str]:
    try:
        return set(json.loads(SENT_FILE.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return set()
    except ValueError:
        logger.warning("sent.json is unreadable, starting with an empty list")
        return set()


def save_sent(sent: set[str]) -> None:
    tmp = SENT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(sent)), encoding="utf-8")
    tmp.replace(SENT_FILE)  # rename, so a crash never leaves a half-written file


def read_refresh_token() -> str | None:
    """The token saved by the latest Google sign-in. Runs in the loop's own thread."""

    async def fetch() -> str | None:
        conn = await asyncpg.connect(get_settings().DATABASE_URL)
        try:
            return await latest_refresh_token(conn)
        finally:
            await conn.close()

    return asyncio.run(fetch())


def on_mqtt_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code.is_failure:
        logger.warning("MQTT connect refused: %s", reason_code)  # e.g. "Not authorized" = bad credentials
    else:
        logger.info("MQTT connected")


def on_mqtt_disconnect(client, userdata, flags, reason_code, properties) -> None:
    logger.warning("MQTT disconnected: %s", reason_code)


def connect_mqtt() -> mqtt.Client:
    settings = get_settings()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"desk-backend-{uuid.uuid4().hex[:6]}"
    )
    client.tls_set()
    if settings.MQTT_USERNAME:  # public brokers take no login
        client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    # connect_async + loop_start: keeps (re)connecting in the background instead of raising.
    client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT)
    client.loop_start()
    return client


def publish_json(client: mqtt.Client, topic: str, payload: dict) -> bool:
    """QoS 1 publish; True once the broker has confirmed it."""
    try:
        info = client.publish(topic, json.dumps(payload), qos=1)
        info.wait_for_publish(timeout=5)
        return info.is_published()
    except (RuntimeError, ValueError) as e:  # not connected / queue full
        logger.warning("MQTT publish failed: %s", e)
        return False


def send_due_reminders(service, client: mqtt.Client, topic: str, sent: set[str]) -> None:
    now = datetime.now(UTC)
    try:
        calendar = service.calendarList().get(calendarId="primary").execute()
        default_reminders = calendar.get("defaultReminders", [])
    except HttpError as e:
        if e.status_code != 403:
            raise
        default_reminders = FALLBACK_REMINDERS

    events = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=(now + timedelta(days=1)).isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )

    for event in events:
        if "date" in event.get("start", {}) or event.get("status") == "cancelled":
            continue
        attendees = event.get("attendees", [])
        if any(a.get("self") and a.get("responseStatus") == "declined" for a in attendees):
            continue

        starts_at = datetime.fromisoformat(event["start"]["dateTime"])
        start_label = starts_at.strftime("%H:%M")  # in the calendar's own timezone
        title = event.get("summary") or "Meeting"

        reminders = event.get("reminders", {})
        alerts = default_reminders if reminders.get("useDefault", True) else reminders.get("overrides", [])

        for alert in (a for a in alerts if a.get("method") == "popup"):
            minutes = alert.get("minutes", 0)
            remind_at = starts_at - timedelta(minutes=minutes)
            reminder_id = f"{event['id']}:{int(starts_at.timestamp())}:{minutes}"
            if not (remind_at <= now < starts_at) or reminder_id in sent:
                continue

            minutes_left = max(1, math.ceil((starts_at - now).total_seconds() / 60))
            unit = "minute" if minutes_left == 1 else "minutes"
            payload = {
                "id": reminder_id,
                "text": f"{title} at {start_label}, in {minutes_left} {unit}",
                # For the ESP reminder screen
                "title": title,
                "at": start_label,
                "starts_at": int(starts_at.timestamp()),
            }
            if not publish_json(client, topic, payload):
                continue  # not marked sent: retried on the next pass

            sent.add(reminder_id)
            save_sent(sent)
            logger.info("Reminder sent to the desk: %s at %s", title, start_label)


def start_reminder_loop(esp_device_id: str) -> None:
    """Runs forever in a background thread: poll Google Calendar, push due reminders over MQTT."""
    client = connect_mqtt()
    topic = f"jarvis/{esp_device_id}/reminder"
    sent = load_sent()
    token, service = None, None
    logger.info("Calendar reminder loop started, publishing to %s", topic)

    while True:
        try:
            latest = read_refresh_token()
            if not latest:
                logger.info("No Google sign-in yet: open /auth/google/start")
            else:
                if latest != token:  # first run, or the user signed in again
                    token, service = latest, calendar_service(latest)
                send_due_reminders(service, client, topic, sent)
        except Exception as e:  # noqa: BLE001 - one bad pass must never stop the loop
            logger.warning("Reminder loop error: %s", e)
        time.sleep(REMINDER_POLL_SECONDS)
