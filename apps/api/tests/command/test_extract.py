from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.modules.command import extract
from app.modules.command.extract import resolve_date, resolve_date_range, resolve_when

UTC = ZoneInfo("UTC")

# Tuesday 20 October 2026.
TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2026, 10, 20)),
        ("tomorrow", date(2026, 10, 21)),
        ("yesterday", date(2026, 10, 19)),
        ("day after tomorrow", date(2026, 10, 22)),
        ("friday", date(2026, 10, 23)),
        ("this friday", date(2026, 10, 23)),
        ("next friday", date(2026, 10, 30)),
        ("monday", date(2026, 10, 26)),
        ("on monday", date(2026, 10, 26)),
        ("october 25", date(2026, 10, 25)),
        ("25 october", date(2026, 10, 25)),
        ("october 5", date(2027, 10, 5)),
        ("2026-11-03", date(2026, 11, 3)),
        ("meeting on monday at 3 pm", date(2026, 10, 26)),
    ],
)
def test_resolve_date(text: str, expected: date):
    assert resolve_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["25/10", "no date here", "next week"])
def test_resolve_date_returns_none(text: str):
    assert resolve_date(text, TODAY) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("last week", (date(2026, 10, 12), date(2026, 10, 18))),
        ("this week", (date(2026, 10, 19), date(2026, 10, 25))),
        ("next week", (date(2026, 10, 26), date(2026, 11, 1))),
        ("past 3 days", (date(2026, 10, 18), date(2026, 10, 20))),
        ("yesterday", (date(2026, 10, 19), date(2026, 10, 19))),
        ("what meetings do i have tomorrow", (date(2026, 10, 21), date(2026, 10, 21))),
    ],
)
def test_resolve_date_range(text: str, expected: tuple[date, date]):
    assert resolve_date_range(text, TODAY) == expected


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("from 2 to 4 pm", "14:00", "16:00"),
        ("2-4 pm", "14:00", "16:00"),
        ("2 pm to 4 pm", "14:00", "16:00"),
        ("between 2 and 4 pm", "14:00", "16:00"),
        ("9 to 11 am", "09:00", "11:00"),
        ("14:00 to 16:00", "14:00", "16:00"),
    ],
)
def test_resolve_time_range(text: str, start: str, end: str):
    when = resolve_when(text, TODAY, NOW)
    assert when.start is not None and when.start.strftime("%H:%M") == start
    assert when.end is not None and when.end.strftime("%H:%M") == end


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("at 2 pm", "14:00"),
        ("at 2pm", "14:00"),
        ("at 2:30 pm", "14:30"),
        ("at 14:00", "14:00"),
        ("at 7 am", "07:00"),
        ("at noon", "12:00"),
        ("at midnight", "00:00"),
        ("meeting in the morning", "09:00"),
        ("meeting tomorrow evening", "19:00"),
    ],
)
def test_resolve_single_time(text: str, expected: str):
    when = resolve_when(text, TODAY, NOW)
    assert when.start is not None and when.start.strftime("%H:%M") == expected


@pytest.mark.parametrize(
    ("text", "minutes"),
    [
        ("for one hour", 60),
        ("for 2 hours", 120),
        ("for 30 minutes", 30),
        ("for an hour", 60),
        ("for half an hour", 30),
        ("for an hour and a half", 90),
    ],
)
def test_resolve_duration(text: str, minutes: int):
    assert resolve_when(text, TODAY, NOW).duration_minutes == minutes


def test_relative_time():
    when = resolve_when("in 10 minutes", TODAY, NOW)
    assert when.relative_at == datetime(2026, 10, 20, 9, 10, tzinfo=UTC)


def test_relative_hours():
    when = resolve_when("in an hour", TODAY, NOW)
    assert when.relative_at == datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("schedule a project meeting tomorrow from 2 to 4 pm", "Project meeting"),
        ("schedule a meeting tomorrow", "Meeting"),
        ("book an appointment day after tomorrow", "Appointment"),
        ("set up a calendar event tomorrow", "Calendar event"),
        ("schedule a call with ali next friday at 3 pm", "Call with ali"),
    ],
)
def test_extract_event_title(text: str, title: str):
    assert extract.extract(text, NOW).title == title


@pytest.mark.parametrize(
    ("text", "task"),
    [
        ("remind me to call mom tomorrow", "Call mom"),
        ("remind me about the meeting at 8 p.m.", "Meeting"),
        ("remember to water the plants", "Water the plants"),
        ("set an alarm for 7 am", "Wake up"),
        ("wake me up in 10 minutes", "Wake up"),
    ],
)
def test_extract_reminder_task(text: str, task: str):
    assert extract.extract(text, NOW).task == task


@pytest.mark.parametrize(
    ("text", "content"),
    [
        ("note that the plants need water", "the plants need water"),
        ("write down my gym routine", "my gym routine"),
        ("remember the meeting room code is 4410", "the meeting room code is 4410"),
        ("take a note: the wifi password is hunter2", "the wifi password is hunter2"),
        ("note: buy milk", "buy milk"),
    ],
)
def test_extract_note_content(text: str, content: str):
    assert extract.extract(text, NOW).content == content


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("what ai news came out yesterday", "ai news"),
        ("what ai news came out yesterday?", "ai news"),
        ("What AI news came out yesterday?", "AI news"),
        ("search for ai news from yesterday", "ai news"),
        ("look up the latest ai news", "ai news"),
    ],
)
def test_extract_search_query(text: str, query: str):
    assert extract.extract(text, NOW).query == query
