import pytest
from pydantic import ValidationError

from app.modules.calendar.schemas import MeetingIn

BASE = {
    "request_id": "req-1",
    "title": "Design review",
    "start": "2026-11-20T10:00:00+05:00",
    "end": "2026-11-20T11:00:00+05:00",
}


def test_valid_meeting_normalizes_attendees():
    meeting = MeetingIn(**BASE, attendees=[" Alice@Example.com "])
    assert meeting.attendees == ["alice@example.com"]
    assert meeting.timezone is None


@pytest.mark.parametrize(
    "override",
    [
        {"end": "2026-11-20T10:00:00+05:00"},  # end == start
        {"end": "2026-11-20T09:00:00+05:00"},  # end before start
        {"end": "2026-11-20T11:00:00"},  # mixes offset and no offset
        {"timezone": "Mars/Olympus"},
        {"timezone": "../etc/passwd"},
        {"attendees": ["not-an-email"]},
        {"attendees": [f"user{i}@example.com" for i in range(51)]},
        {"title": "   "},
        {"request_id": ""},
        {"request_id": "bad\x00id"},
    ],
)
def test_invalid_meeting_is_rejected(override):
    with pytest.raises(ValidationError):
        MeetingIn(**{**BASE, **override})


def test_request_id_is_optional():
    data = {key: value for key, value in BASE.items() if key != "request_id"}
    assert MeetingIn(**data).request_id is None
