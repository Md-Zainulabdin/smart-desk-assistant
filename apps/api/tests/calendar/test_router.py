from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service
from app.modules.calendar.schemas import MeetingOut

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
    monkeypatch.setattr(service, "book_meeting", book)
    return TestClient(app), app, conn, user, book


def test_create_meeting_books_for_the_signed_in_user(api):
    client, _, conn, user, book = api

    response = client.post("/api/v1/calendar/meetings", json=MEETING)

    assert response.status_code == 201
    assert response.json() == {"id": "abc", "link": "https://c/abc", "meet_link": None}
    used_conn, user_id, meeting = book.call_args.args
    assert (used_conn, user_id) == (conn, user["id"])
    assert meeting.title == "Design review"


def test_invalid_meeting_is_a_validation_error(api):
    client, _, _, _, book = api
    response = client.post("/api/v1/calendar/meetings", json={**MEETING, "end": MEETING["start"]})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    book.assert_not_called()


def test_create_meeting_requires_sign_in(api):
    client, app, _, _, book = api
    del app.dependency_overrides[get_current_user]

    assert client.post("/api/v1/calendar/meetings", json=MEETING).status_code == 401
    book.assert_not_called()
