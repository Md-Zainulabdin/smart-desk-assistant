from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())
UTC = ZoneInfo("UTC")


def post_command(text: str, **extra):
    return client.post("/api/v1/command", json={"text": text, "timezone": "UTC", **extra})


def today() -> date:
    return datetime.now(UTC).date()


def test_read_events_tomorrow_flow():
    res = post_command("what meetings do i have tomorrow")
    assert res.status_code == 200
    body = res.json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert body["intent"] == "READ_EVENTS"
    assert body["status"] == "ready"
    assert body["slots"]["date_from"] == tomorrow
    assert body["slots"]["date_to"] == tomorrow
    assert body["missing"] == []
    assert body["clarification"] is None


def test_read_events_without_date_defaults_to_a_week():
    res = post_command("show my upcoming events")
    body = res.json()
    assert body["slots"]["date_from"] == today().isoformat()
    assert body["slots"]["date_to"] == (today() + timedelta(days=7)).isoformat()


def test_web_search_yesterday_flow():
    res = post_command("What AI news came out yesterday?")
    assert res.status_code == 200
    body = res.json()
    yesterday = (today() - timedelta(days=1)).isoformat()
    assert body["intent"] == "WEB_SEARCH"
    assert body["status"] == "ready"
    assert body["slots"]["query"] == "AI news"
    assert body["slots"]["date_from"] == yesterday
    assert body["slots"]["date_to"] == yesterday


def test_event_without_time_asks_for_clarification():
    res = post_command("schedule a meeting tomorrow")
    body = res.json()
    assert body["intent"] == "CREATE_EVENT"
    assert body["status"] == "needs_clarification"
    assert body["missing"] == ["start_at"]
    assert body["clarification"] == "What time should the meeting start, and how long should it be?"
    assert body["slots"]["title"] == "Meeting"
    assert body["slots"]["date"] == (today() + timedelta(days=1)).isoformat()
    assert "start_at" not in body["slots"]


def test_event_without_date_asks_for_the_date():
    body = post_command("schedule a meeting").json()
    assert body["missing"] == ["date"]
    assert body["clarification"] == "When should the meeting be?"


def test_complete_event_flow():
    res = post_command("schedule a project meeting tomorrow from 2 to 4 pm")
    body = res.json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert body["status"] == "ready"
    assert body["missing"] == []
    assert body["slots"]["title"] == "Project meeting"
    assert body["slots"]["date"] == tomorrow
    assert body["slots"]["start_at"] == f"{tomorrow}T14:00:00+00:00"
    assert body["slots"]["end_at"] == f"{tomorrow}T16:00:00+00:00"


def test_event_with_start_only_defaults_to_one_hour():
    body = post_command("schedule a meeting tomorrow at 2 pm").json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert body["status"] == "ready"
    assert body["slots"]["start_at"] == f"{tomorrow}T14:00:00+00:00"
    assert body["slots"]["end_at"] == f"{tomorrow}T15:00:00+00:00"


def test_reminder_without_time_asks_for_the_time():
    body = post_command("remind me to call mom tomorrow").json()
    assert body["intent"] == "CREATE_REMINDER"
    assert body["missing"] == ["remind_at"]
    assert body["slots"]["task"] == "Call mom"
    assert body["clarification"] == "When should I remind you?"


def test_complete_reminder_flow():
    body = post_command("remind me to call mom tomorrow at 8 pm").json()
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert body["status"] == "ready"
    assert body["slots"]["task"] == "Call mom"
    assert body["slots"]["remind_at"] == f"{tomorrow}T20:00:00+00:00"


def test_note_flow():
    body = post_command("note that the plants need water").json()
    assert body["intent"] == "CREATE_NOTE"
    assert body["status"] == "ready"
    assert body["slots"]["content"] == "the plants need water"


def test_unsupported_command():
    body = post_command("hello there").json()
    assert body["intent"] == "UNKNOWN"
    assert body["status"] == "unsupported"
    assert body["slots"] == {}


def test_timezone_defaults_to_utc():
    res = client.post("/api/v1/command", json={"text": "schedule a meeting tomorrow at 2 pm"})
    assert res.json()["slots"]["timezone"] == "UTC"


def test_timezone_is_used():
    res = client.post(
        "/api/v1/command",
        json={
            "text": "schedule a meeting tomorrow at 2 pm",
            "timezone": "Asia/Karachi",
        },
    )
    assert res.json()["slots"]["start_at"].endswith("+05:00")


def test_invalid_timezone_is_rejected():
    res = post_command("schedule a meeting tomorrow", timezone="Mars/Olympus")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_timezone"


def test_request_id_is_accepted():
    res = post_command("note that the plants need water", request_id="req-1")
    assert res.status_code == 200
    assert res.json()["intent"] == "CREATE_NOTE"


def test_whitespace_is_trimmed():
    res = post_command("  note that the plants need water  ")
    assert res.status_code == 200
    assert res.json()["text"] == "note that the plants need water"


def test_whitespace_only_is_rejected():
    res = post_command("   ")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_command"


def test_empty_text_is_rejected():
    res = post_command("")
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_missing_text_is_rejected():
    res = client.post("/api/v1/command", json={"request_id": "abc"})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_oversize_text_is_rejected():
    res = post_command("a" * 2001)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"

def test_write_note_prefix():
    body = post_command("Write a note: remind me to buy milk").json()
    assert body["intent"] == "CREATE_NOTE"
    assert body["status"] == "ready"
    assert body["slots"]["content"] == "remind me to buy milk"


def test_ambiguous_hour_asks_am_or_pm():
    body = post_command("Schedule a meeting tomorrow at 2").json()
    assert body["status"] == "needs_clarification"
    assert body["missing"] == ["start_at_meridiem"]
    assert body["clarification"] == "Did you mean 2 AM or 2 PM?"
    assert body["slots"]["ambiguous_hour"] == "2"
    assert "start_at" not in body["slots"]


def test_end_before_start_is_flagged():
    body = post_command("Schedule a meeting tomorrow from 4 PM to 2 PM").json()
    assert body["status"] == "needs_clarification"
    assert body["missing"] == ["end_at"]
    assert body["clarification"] == "The end time 14:00 is before the start. When should the meeting end?"
    tomorrow = (today() + timedelta(days=1)).isoformat()
    assert body["slots"]["start_at"] == f"{tomorrow}T16:00:00+00:00"
    assert "end_at" not in body["slots"]


def test_multiple_requests_ask_for_one_command():
    body = post_command("Create a note and schedule a meeting tomorrow at 3 PM").json()
    assert body["status"] == "needs_clarification"
    assert body["missing"] == ["single_command"]
    assert body["clarification"] == "Please give me one command at a time."
    assert body["slots"]["detected_intents"] == "CREATE_NOTE, CREATE_EVENT"


def test_snooze_is_unsupported():
    body = post_command("snooze it for ten minutes").json()
    assert body["intent"] == "UNKNOWN"
    assert body["status"] == "unsupported"


def test_brief_summary_preference_slot():
    body = post_command("Give me a brief overview of AI papers released yesterday").json()
    assert body["slots"]["style"] == "brief"
    assert body["slots"]["query"] == "AI papers"
    assert body["slots"]["date_from"] == body["slots"]["date_to"] == (today() - timedelta(days=1)).isoformat()
