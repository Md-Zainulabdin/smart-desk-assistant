from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ApiError
from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service as calendar_service
from app.modules.calendar.schemas import MeetingOut, MeetingSummary
from app.modules.notes import repository as notes_repository
from app.modules.notes.schemas import Note
from app.modules.orchestrator import repository
from app.modules.orchestrator.schemas import AssistantRequest, Outcome
from app.modules.orchestrator.service import handle
from app.modules.web_search import services as web_search_service

USER_ID = uuid4()
NOTE = Note(id=uuid4(), content="buy milk", created_at=datetime.now(UTC))
BOOKED = MeetingOut(id="evt", link="https://cal/evt", meet_link="https://meet/evt")


@pytest.fixture
def world(monkeypatch):
    """The real parser, with pending storage, notes and calendar faked in memory."""
    pending = {}
    monkeypatch.setattr(repository, "get_pending", lambda conn, uid: pending.get(uid))
    monkeypatch.setattr(
        repository, "save_pending", lambda conn, uid, ctx: pending.__setitem__(uid, ctx)
    )
    monkeypatch.setattr(repository, "clear_pending", lambda conn, uid: pending.pop(uid, None))
    create_note = Mock(return_value=NOTE)
    book_meeting = Mock(return_value=BOOKED)
    list_meetings = Mock(
        return_value=[
            MeetingSummary(
                id="evt",
                title="Design review",
                start="2026-11-21T10:00:00+00:00",
                end="2026-11-21T11:00:00+00:00",
                link="https://cal/evt",
            )
        ]
    )
    search_web = Mock(
        return_value={
            "success": True,
            "data": {
                "query": "AI news",
                "results": [{"title": "A", "url": "https://a", "snippet": "S"}],
            },
            "error": None,
        }
    )
    monkeypatch.setattr(notes_repository, "create_note", create_note)
    monkeypatch.setattr(calendar_service, "book_meeting", book_meeting)
    monkeypatch.setattr(calendar_service, "list_meetings", list_meetings)
    monkeypatch.setattr(web_search_service, "search_web", search_web)
    return {
        "pending": pending,
        "create_note": create_note,
        "book_meeting": book_meeting,
        "list_meetings": list_meetings,
        "search_web": search_web,
    }


def say(text: str, request_id: str | None = None):
    return handle(None, USER_ID, AssistantRequest(text=text, request_id=request_id, timezone="UTC"))


def test_ready_note_is_saved(world):
    response = say("Take a note: buy milk", request_id="r1")

    assert response.outcome is Outcome.DONE
    assert response.reply == "Saved your note."
    assert response.result == {"note_id": str(NOTE.id)}
    world["create_note"].assert_called_once_with(None, USER_ID, "buy milk", "r1")


def test_ready_meeting_is_booked(world):
    response = say("Schedule a project meeting on 20 November 2026 from 2 PM to 4 PM", "r2")

    assert response.outcome is Outcome.DONE
    assert response.result == {
        "event_id": "evt", "link": "https://cal/evt", "meet_link": "https://meet/evt"
    }
    assert response.reply.startswith("Booked ")
    meeting = world["book_meeting"].call_args.args[2]
    assert meeting.start.isoformat() == "2026-11-20T14:00:00+00:00"
    assert meeting.end.isoformat() == "2026-11-20T16:00:00+00:00"
    assert meeting.request_id == "r2"


def test_clarification_is_remembered_and_completed_by_the_next_sentence(world):
    first = say("Create a note.")
    assert first.outcome is Outcome.NEEDS_CLARIFICATION
    assert first.reply  # the question to ask
    assert USER_ID in world["pending"]
    world["create_note"].assert_not_called()

    second = say("Buy milk")
    assert second.outcome is Outcome.DONE
    assert USER_ID not in world["pending"]
    world["create_note"].assert_called_once()
    assert world["create_note"].call_args.args[2] == "Buy milk"


def test_unsupported_reply_drops_the_pending_question(world):
    say("Create a note.")
    response = say("cancel that")

    assert response.outcome is Outcome.UNSUPPORTED
    assert USER_ID not in world["pending"]
    world["create_note"].assert_not_called()


def test_features_not_built_yet_say_so(world):
    response = say("Remind me to call mom tomorrow at 5 PM")
    assert response.outcome is Outcome.UNSUPPORTED
    assert response.reply == "Reminders isn't available yet."


def test_ready_search_returns_results(world):
    response = say("Search for AI news")

    assert response.outcome is Outcome.DONE
    assert response.result == {
        "query": "AI news",
        "results": [{"title": "A", "url": "https://a", "snippet": "S"}],
    }
    assert response.reply == "Found 1 results for AI news."
    world["search_web"].assert_called_once_with("AI news", start_date=None, end_date=None)


def test_search_failure_is_spoken(world):
    world["search_web"].return_value = {
        "success": False,
        "data": None,
        "error": {"code": "MISSING_API_KEY", "message": "Web search is not configured."},
    }

    response = say("Search for AI news")

    assert response.outcome is Outcome.FAILED
    assert response.reply == "Web search is not configured."


def test_ready_read_events_returns_the_calendar_list(world):
    response = say("What meetings do I have tomorrow")

    assert response.outcome is Outcome.DONE
    assert response.result["events"][0]["title"] == "Design review"
    start, end = world["list_meetings"].call_args.args[2:4]
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date()
    assert start.date() == tomorrow
    assert end.date() == tomorrow


def test_read_events_without_calendar_access_is_spoken(world):
    world["list_meetings"].side_effect = ApiError(
        "Google Calendar access was not granted. Sign in with Google again.",
        "calendar_not_connected",
        403,
    )

    response = say("What meetings do I have tomorrow")

    assert response.outcome is Outcome.FAILED
    assert response.reply.startswith("Google Calendar access was not granted")


def test_action_errors_become_a_spoken_failure(world):
    world["book_meeting"].side_effect = ApiError(
        "Google Calendar access was not granted. Sign in with Google again.",
        "calendar_not_connected",
        403,
    )
    response = say("Schedule a project meeting on 20 November 2026 from 2 PM to 4 PM")

    assert response.outcome is Outcome.FAILED
    assert response.reply.startswith("Google Calendar access was not granted")


def test_endpoint_requires_sign_in_and_returns_the_reply(world):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    client = TestClient(app)

    assert client.post("/api/v1/assistant", json={"text": "Take a note: x"}).status_code == 401

    app.dependency_overrides[get_current_user] = lambda: {"id": USER_ID}
    response = client.post("/api/v1/assistant", json={"text": "Take a note: buy milk"})
    assert response.status_code == 200
    assert response.json()["outcome"] == "done"
