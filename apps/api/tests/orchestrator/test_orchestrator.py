from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ApiError
from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service as calendar_service
from app.modules.calendar.schemas import MeetingOut
from app.modules.notes import repository as notes_repository
from app.modules.notes.schemas import Note
from app.modules.orchestrator import repository
from app.modules.orchestrator import service as orchestrator_service
from app.modules.orchestrator.schemas import AssistantRequest, Outcome
from app.modules.orchestrator.service import handle

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
    monkeypatch.setattr(notes_repository, "create_note", create_note)
    monkeypatch.setattr(calendar_service, "book_meeting", book_meeting)
    return {"pending": pending, "create_note": create_note, "book_meeting": book_meeting}


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
    response = say("What meetings do I have tomorrow")
    assert response.outcome is Outcome.UNSUPPORTED
    assert response.reply == "Reading your calendar isn't available yet."


def test_reminders_are_refused_without_a_follow_up_question(world):
    response = say("Remind me to call mom")

    assert response.outcome is Outcome.UNSUPPORTED
    assert response.reply == "Sorry, I can't help with that."
    assert USER_ID not in world["pending"]


def found(results, answer=None):
    data = {"query": "python news", "results": results}
    if answer is not None:
        data["answer"] = answer
    return {"success": True, "data": data, "error": None}


def test_web_search_reply_is_the_top_result_as_plain_speakable_text(world, monkeypatch):
    results = [
        {
            "title": "Weather in Karachi",
            "url": "https://a",
            "snippet": "## Today\n**Karachi** is 32 degrees and sunny. See [details](https://x.com/y) "
            "or https://example.com now. Humidity is 40 percent.",
        },
        {"title": "Other", "url": "https://b", "snippet": "b"},
    ]
    search = Mock(return_value=found(results))
    monkeypatch.setattr(orchestrator_service, "search_web", search)

    response = say("Search for python news")

    assert response.outcome is Outcome.DONE
    assert response.reply == (
        "Weather in Karachi. Today Karachi is 32 degrees and sunny. See details or now. "
        "Humidity is 40 percent."
    )
    assert response.result["results"] == results
    assert search.call_args.args[0] == "python news"


def test_web_search_reply_prefers_the_written_answer(world, monkeypatch):
    results = [{"title": "Everest", "url": "https://a", "snippet": "A mountain page."}]
    answer = "Mount Everest is **8,849 metres** tall, see https://x.com for more."
    search = Mock(return_value=found(results, answer))
    monkeypatch.setattr(orchestrator_service, "search_web", search)

    response = say("Search for python news")

    assert response.reply == "Mount Everest is 8,849 metres tall, see for more."
    assert response.result["answer"] == answer
    assert search.call_args.kwargs["include_answer"] is True


def test_web_search_reply_is_cut_at_a_sentence_and_stays_short(world, monkeypatch):
    snippet = " ".join(f"Sentence number {i} is here." for i in range(40))
    results = [{"title": "Long", "url": "https://a", "snippet": snippet}]
    monkeypatch.setattr(orchestrator_service, "search_web", Mock(return_value=found(results)))

    response = say("Search for python news")

    assert len(response.reply) <= orchestrator_service.SPOKEN_MAX_CHARS
    assert response.reply.endswith("here.")


def test_web_search_result_without_text_falls_back_to_the_title(world, monkeypatch):
    results = [{"title": "Weather in Karachi", "url": "https://a", "snippet": ""}]
    monkeypatch.setattr(orchestrator_service, "search_web", Mock(return_value=found(results)))

    response = say("Search for python news")

    assert response.reply == "The top result is Weather in Karachi."


def test_web_search_without_results_says_so(world, monkeypatch):
    monkeypatch.setattr(orchestrator_service, "search_web", Mock(return_value=found([])))
    response = say("Search for python news")
    assert response.outcome is Outcome.DONE
    assert response.reply == "I couldn't find anything for python news."


def test_web_search_failure_becomes_a_spoken_failure(world, monkeypatch):
    failed = {
        "success": False,
        "data": None,
        "error": {"code": "SEARCH_FAILED", "message": "Web search could not be completed."},
    }
    monkeypatch.setattr(orchestrator_service, "search_web", Mock(return_value=failed))

    response = say("Search for python news")

    assert response.outcome is Outcome.FAILED
    assert response.reply == "Web search could not be completed."


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
