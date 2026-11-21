import re
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.exceptions import ApiError
from app.core.security import encrypt_token
from app.integrations import google_calendar
from app.modules.calendar import repository, service
from app.modules.calendar.schemas import MeetingIn

USER_ID = uuid4()
EVENT = {"id": "abc", "htmlLink": "https://calendar/abc", "hangoutLink": "https://meet/abc"}


@pytest.fixture
def stored_token(monkeypatch):
    mock = Mock(return_value=encrypt_token("refresh-1"))
    monkeypatch.setattr(repository, "get_refresh_token_encrypted", mock)
    return mock


@pytest.fixture
def google(monkeypatch):
    mocks = {"insert_event": Mock(return_value=EVENT), "get_event": Mock()}
    for name, mock in mocks.items():
        monkeypatch.setattr(google_calendar, name, mock)
    return mocks


def meeting(**overrides) -> MeetingIn:
    data = {
        "title": "Design review",
        "start": "2026-11-20T10:00:00+05:00",
        "end": "2026-11-20T11:00:00+05:00",
    }
    return MeetingIn(**{**data, **overrides})


def test_event_id_is_stable_per_request_and_valid_for_google():
    first = service.event_id_for(USER_ID, "req-1")
    assert first == service.event_id_for(USER_ID, "req-1")
    assert first != service.event_id_for(USER_ID, "req-2")
    assert first != service.event_id_for(uuid4(), "req-1")
    assert re.fullmatch(r"[0-9a-v]{5,1024}", first)


def test_booking_creates_event_with_meet_link(stored_token, google):
    result = service.book_meeting(None, USER_ID, meeting(attendees=["a@example.com"]))

    assert result.model_dump() == {
        "id": "abc", "link": "https://calendar/abc", "meet_link": "https://meet/abc"
    }
    token, body = google["insert_event"].call_args.args
    assert token == "refresh-1"
    assert "id" not in body  # no request_id: Google picks the id
    assert body["attendees"] == [{"email": "a@example.com"}]
    assert body["start"] == {"dateTime": "2026-11-20T10:00:00+05:00", "timeZone": "UTC"}
    assert body["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {
        "type": "hangoutsMeet"
    }


def test_booking_uses_requested_timezone(stored_token, google):
    service.book_meeting(None, USER_ID, meeting(timezone="Asia/Karachi"))
    body = google["insert_event"].call_args.args[1]
    assert body["start"]["timeZone"] == body["end"]["timeZone"] == "Asia/Karachi"


def test_request_id_sets_a_stable_event_id(stored_token, google):
    service.book_meeting(None, USER_ID, meeting(request_id="req-1"))
    body = google["insert_event"].call_args.args[1]
    event_id = service.event_id_for(USER_ID, "req-1")
    assert body["id"] == event_id
    assert body["conferenceData"]["createRequest"]["requestId"] == event_id


def test_retried_request_returns_the_existing_event(stored_token, google):
    google["insert_event"].side_effect = google_calendar.EventAlreadyExists()
    google["get_event"].return_value = {**EVENT, "status": "confirmed"}

    assert service.book_meeting(None, USER_ID, meeting(request_id="req-1")).id == "abc"
    google["get_event"].assert_called_once_with("refresh-1", service.event_id_for(USER_ID, "req-1"))


def test_retry_of_a_cancelled_event_is_reported(stored_token, google):
    google["insert_event"].side_effect = google_calendar.EventAlreadyExists()
    google["get_event"].return_value = {**EVENT, "status": "cancelled"}

    with pytest.raises(ApiError) as error:
        service.book_meeting(None, USER_ID, meeting(request_id="req-1"))
    assert (error.value.code, error.value.status) == ("calendar_event_cancelled", 409)


def test_booking_without_calendar_access_is_refused(stored_token, google):
    stored_token.return_value = None
    with pytest.raises(ApiError) as error:
        service.book_meeting(None, USER_ID, meeting())
    assert (error.value.code, error.value.status) == ("calendar_not_connected", 403)
    google["insert_event"].assert_not_called()


@pytest.mark.parametrize(
    ("raised", "code", "status"),
    [
        (google_calendar.CalendarAuthError(), "google_access_expired", 403),
        (google_calendar.CalendarApiError(), "calendar_request_failed", 502),
    ],
)
def test_google_failures_become_clear_errors(stored_token, google, raised, code, status):
    google["insert_event"].side_effect = raised
    with pytest.raises(ApiError) as error:
        service.book_meeting(None, USER_ID, meeting())
    assert (error.value.code, error.value.status) == (code, status)


def test_undecryptable_token_asks_to_sign_in_again(stored_token, google):
    stored_token.return_value = "garbage"
    with pytest.raises(ApiError) as error:
        service.book_meeting(None, USER_ID, meeting())
    assert error.value.code == "google_access_expired"
    google["insert_event"].assert_not_called()
