from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service
from app.modules.calendar.schemas import MeetingOut, MeetingSummary

MEETING = {
    "title": "Design review",
    "start": "2026-11-20T10:00:00+05:00",
    "end": "2026-11-20T11:00:00+05:00",
}


@pytest.fixture
def api(monkeypatch):
    app = create_app()
    conn = Mock()
    user = {"id": uuid4(), "email": "owner@example.com", "name": None, "picture_url": None}
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user
    book = Mock(return_value=MeetingOut(id="abc", link="https://c/abc", meet_link=None))
    upcoming = Mock(
        return_value=[
            MeetingSummary(
                id="evt",
                title="Design review",
                start="2026-11-20T10:00:00+05:00",
                end="2026-11-20T11:00:00+05:00",
                link="https://c/evt",
            )
        ]
    )
    monkeypatch.setattr(service, "book_meeting", book)
    monkeypatch.setattr(service, "list_meetings", upcoming)
    return TestClient(app), app, conn, user, book, upcoming


def test_create_meeting_books_for_the_signed_in_user(api):
    client, _, conn, user, book, _ = api

    response = client.post("/api/v1/calendar/meetings", json=MEETING)

    assert response.status_code == 201
    assert response.json() == {"id": "abc", "link": "https://c/abc", "meet_link": None}
    used_conn, user_id, meeting = book.call_args.args
    assert (used_conn, user_id) == (conn, user["id"])
    assert meeting.title == "Design review"


def test_invalid_meeting_is_a_validation_error(api):
    client, _, _, _, book, _ = api
    response = client.post("/api/v1/calendar/meetings", json={**MEETING, "end": MEETING["start"]})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    book.assert_not_called()


def test_create_meeting_requires_sign_in(api):
    client, app, _, _, book, _ = api
    del app.dependency_overrides[get_current_user]

    assert client.post("/api/v1/calendar/meetings", json=MEETING).status_code == 401
    book.assert_not_called()


def test_list_meetings_returns_upcoming_events(api):
    client, _, conn, user, _, upcoming = api

    response = client.get("/api/v1/calendar/meetings")

    assert response.status_code == 200
    assert response.json()[0]["title"] == "Design review"
    used_conn, user_id, start, end, max_results = upcoming.call_args.args
    assert (used_conn, user_id, max_results) == (conn, user["id"], 10)
    assert end > start


def test_list_meetings_rejects_an_inverted_range(api):
    client, _, _, _, _, upcoming = api

    response = client.get(
        "/api/v1/calendar/meetings",
        params={
            "start": "2026-11-21T10:00:00+00:00",
            "end": "2026-11-20T10:00:00+00:00",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_date_range"
    upcoming.assert_not_called()


def test_list_meetings_requires_sign_in(api):
    client, app, _, _, _, upcoming = api
    del app.dependency_overrides[get_current_user]

    assert client.get("/api/v1/calendar/meetings").status_code == 401
    upcoming.assert_not_called()
