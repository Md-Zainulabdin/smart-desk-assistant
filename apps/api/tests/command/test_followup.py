from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
UTC = ZoneInfo("UTC")


def today() -> date:
    return datetime.now(UTC).date()


def post_command(text: str, context: dict | None = None):
    payload: dict = {"text": text, "timezone": "UTC"}
    if context is not None:
        payload["context"] = context
    return client.post("/api/v1/command", json=payload)


def pending_context(body: dict) -> dict:
    """Shape the orchestrator stores and sends back on the next turn."""
    return {
        "intent": body["intent"],
        "slots": body["slots"],
        "missing": body["missing"],
    }


def test_follow_up_completes_a_pending_meeting():
    first = post_command("schedule a meeting tomorrow").json()
    assert first["status"] == "needs_clarification"

    second = post_command("at 2 pm for one hour", pending_context(first)).json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert second["intent"] == "CREATE_EVENT"
    assert second["status"] == "ready"
    assert second["missing"] == []
    assert second["slots"]["title"] == "Meeting"
    assert second["slots"]["date"] == tomorrow
    assert second["slots"]["start_at"] == f"{tomorrow}T14:00:00+00:00"
    assert second["slots"]["end_at"] == f"{tomorrow}T15:00:00+00:00"


def test_follow_up_with_time_range():
    first = post_command("schedule a meeting tomorrow").json()
    second = post_command("from 2 to 4 pm", pending_context(first)).json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert second["status"] == "ready"
    assert second["slots"]["start_at"] == f"{tomorrow}T14:00:00+00:00"
    assert second["slots"]["end_at"] == f"{tomorrow}T16:00:00+00:00"


def test_follow_up_for_a_missing_date():
    first = post_command("schedule a meeting").json()
    assert first["missing"] == ["date"]

    second = post_command("tomorrow at 3 pm", pending_context(first)).json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert second["status"] == "ready"
    assert second["slots"]["title"] == "Meeting"
    assert second["slots"]["start_at"] == f"{tomorrow}T15:00:00+00:00"


def test_follow_up_can_change_the_time():
    first = post_command("schedule a meeting tomorrow at 2 pm").json()
    assert first["status"] == "ready"

    second = post_command("make it 4 pm", pending_context(first)).json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert second["status"] == "ready"
    assert second["slots"]["title"] == "Meeting"
    assert second["slots"]["start_at"] == f"{tomorrow}T16:00:00+00:00"
    assert second["slots"]["end_at"] == f"{tomorrow}T17:00:00+00:00"


def test_new_intent_drops_the_pending_context():
    first = post_command("schedule a meeting tomorrow").json()
    second = post_command("what meetings do i have tomorrow", pending_context(first)).json()
    assert second["intent"] == "READ_EVENTS"
    assert "title" not in second["slots"]


def test_follow_up_without_context_stays_unknown():
    res = post_command("at 2 pm for one hour").json()
    assert res["intent"] == "UNKNOWN"
    assert res["status"] == "unsupported"


def test_follow_up_completes_a_pending_reminder():
    first = post_command("remind me to call mom tomorrow").json()
    assert first["missing"] == ["remind_at"]

    second = post_command("at 8 pm", pending_context(first)).json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert second["intent"] == "CREATE_REMINDER"
    assert second["status"] == "ready"
    assert second["slots"]["task"] == "Call mom"
    assert second["slots"]["remind_at"] == f"{tomorrow}T20:00:00+00:00"

def test_note_follow_up_uses_the_reply_as_content():
    first = post_command("Create a note.").json()
    assert first["missing"] == ["content"]

    second = post_command("We need to finish the calendar integration.", pending_context(first)).json()
    assert second["intent"] == "CREATE_NOTE"
    assert second["status"] == "ready"
    assert second["slots"]["content"] == "We need to finish the calendar integration"


def test_snooze_with_context_stays_unsupported():
    first = post_command("remind me to take my medicine at 9 pm").json()
    context = pending_context(first)
    context["missing"] = []

    second = post_command("snooze it for ten minutes", context).json()
    assert second["intent"] == "UNKNOWN"
    assert second["status"] == "unsupported"
