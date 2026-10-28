import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.core.exceptions import ApiError
from app.database.models import User
from app.dependencies import current_user
from app.main import create_app
from app.modules.calendar.schemas import MeetingIn
from app.modules.calendar.service import book_meeting

START = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)


def make_user(refresh_token: str | None = "refresh") -> User:
    return User(id=uuid.uuid4(), email="owner@example.com", refresh_token=refresh_token)


def make_meeting() -> MeetingIn:
    return MeetingIn(title="Standup", start=START, end=START + timedelta(minutes=30))


def http_error(status: int) -> HttpError:
    return HttpError(MagicMock(status=status, reason="err"), b"{}")


def test_book_meeting_returns_created_event():
    created = {"id": "evt", "link": "https://cal/evt", "meet_link": "https://meet/abc"}
    with patch("app.modules.calendar.service.create_meeting", return_value=created):
        result = book_meeting(make_user(), make_meeting())
    assert result.id == "evt"
    assert result.meet_link == "https://meet/abc"


def test_book_meeting_without_refresh_token_is_401():
    with pytest.raises(ApiError) as exc:
        book_meeting(make_user(refresh_token=None), make_meeting())
    assert exc.value.status == 401


@pytest.mark.parametrize(
    ("error", "status"),
    [(RefreshError("revoked"), 401), (http_error(403), 403), (http_error(500), 502)],
)
def test_book_meeting_maps_google_errors(error, status):
    with (
        patch("app.modules.calendar.service.create_meeting", side_effect=error),
        pytest.raises(ApiError) as exc,
    ):
        book_meeting(make_user(), make_meeting())
    assert exc.value.status == status


def test_meeting_route_rejects_end_before_start():
    app = create_app()
    app.dependency_overrides[current_user] = make_user
    body = {"title": "x", "start": START.isoformat(), "end": START.isoformat()}
    res = TestClient(app).post("/calendar/meetings", json=body)
    assert res.status_code == 422
