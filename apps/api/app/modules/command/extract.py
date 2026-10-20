"""Date, time and detail extraction for text commands.

Pure functions with an injected clock, so tests never depend on the real time.
Everything is resolved in a caller supplied timezone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

DEFAULT_EVENT_MINUTES = 60

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

WORD_NUMBERS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

NAMED_TIMES = {
    "morning": time(9, 0),
    "afternoon": time(14, 0),
    "evening": time(19, 0),
    "night": time(20, 0),
}

_UNIT_SECONDS = {
    "minute": 60,
    "min": 60,
    "hour": 3600,
    "hr": 3600,
    "day": 86400,
    "week": 604800,
}

_WEEKDAY_ALT = "|".join(WEEKDAYS)
_MONTH_ALT = "|".join(MONTHS)
_ORDINAL = r"(?:st|nd|rd|th)?"
_MER = r"(?:a\.?m\.?|p\.?m\.?)"

_DATE_EXPR = (
    r"day after tomorrow|today|tomorrow|yesterday"
    r"|this week|next week|last week"
    rf"|(?:this|next) (?:{_WEEKDAY_ALT})"
    rf"|(?:{_MONTH_ALT})\s+\d{{1,2}}{_ORDINAL}(?:,?\s+\d{{4}})?"
    rf"|\d{{1,2}}{_ORDINAL}\s+(?:{_MONTH_ALT})(?:,?\s+\d{{4}})?"
    r"|\d{4}-\d{2}-\d{2}"
    rf"|{_WEEKDAY_ALT}"
)

DATE_PATTERN = re.compile(rf"\b({_DATE_EXPR})\b", re.IGNORECASE)

PAST_RANGE_PATTERN = re.compile(r"\b(?:past|last)\s+(\d+)\s+(days?|weeks?)\b", re.IGNORECASE)

RELATIVE_PATTERN = re.compile(
    r"\bin\s+(?P<num>\d+|[a-z]+)\s*(?P<unit>minutes?|mins?|hours?|hrs?|days?|weeks?)\b",
    re.IGNORECASE,
)

DURATION_PATTERN = re.compile(
    r"\bfor\s+(?:an?\s+hour\s+and\s+a\s+half|half\s+an?\s+hour"
    r"|(?P<num>\d+|[a-z]+)\s*(?P<unit>minutes?|mins?|hours?|hrs?))\b",
    re.IGNORECASE,
)

_TIME_LOOSE = rf"\d{{1,2}}(?::[0-5]\d)?\s*(?:{_MER})?"
_TIME_END = rf"(?:\d{{1,2}}:[0-5]\d\s*(?:{_MER})?|\d{{1,2}}\s*{_MER})(?!\w)"

RANGE_PATTERN = re.compile(
    rf"\b(?:from\s+|between\s+)?(?P<start>{_TIME_LOOSE})\s*"
    rf"(?:to|until|till|and|-|–)\s*(?P<end>{_TIME_END})",
    re.IGNORECASE,
)

TIME_PATTERN = re.compile(
    rf"\b(?P<h24>[01]?\d|2[0-3]):(?P<m24>[0-5]\d)\s*(?P<mer24>{_MER})?"
    rf"|\b(?P<h12>\d{{1,2}})\s*(?P<mer12>{_MER})(?!\w)"
    rf"|\b(?P<named>noon|midnight)\b"
    rf"|\b(?P<named2>morning|afternoon|evening|night)\b",
    re.IGNORECASE,
)

_MONTH_DATE_RE = re.compile(
    rf"({_MONTH_ALT})\s+(\d{{1,2}}){_ORDINAL}(?:,?\s+(\d{{4}}))?", re.IGNORECASE
)
_DAY_MONTH_RE = re.compile(
    rf"(\d{{1,2}}){_ORDINAL}\s+({_MONTH_ALT})(?:,?\s+(\d{{4}}))?", re.IGNORECASE
)
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

_EVENT_LEAD = re.compile(
    r"^(?:the\s+)?(?:please\s+)?(?:can you\s+)?"
    r"(?:schedule|book|set\s+up|setup|create|add|make|organize|arrange|plan|new)\b\s*",
    re.IGNORECASE,
)

_REMINDER_LEAD = re.compile(
    r"^(?:the\s+)?(?:please\s+)?"
    r"(?:remind\s+me(?:\s+(?:to|about|that))?"
    r"|set\s+(?:an?\s+)?alarm(?:\s+(?:for|at))?"
    r"|wake\s+me(?:\s+up)?(?:\s+(?:at|in))?"
    r"|remember\s+to)\b\s*",
    re.IGNORECASE,
)

_NOTE_LEAD = re.compile(
    r"^(?:please\s+)?(?:"
    r"(?:take|make|create|add|write)\s+(?:a\s+|an\s+|the\s+|this\s+|that\s+|down\s+)*notes?"
    r"|note|notes?|write\s+down|jot\s+down|remember"
    r")\s*[:,\-]?\s*(?:that|down|this|about)?\s*",
    re.IGNORECASE,
)

_STYLE_STRIP = re.compile(
    r"\b(?:briefs?|briefly|short|overview|summary|summaries|summari[sz]e|quick(?:ly)?|concise)\b",
    re.IGNORECASE,
)

_STYLE_BRIEF = re.compile(
    r"\b(?:brief|briefly|short|overview|summary|summaries|summari[sz]e|concise)\b",
    re.IGNORECASE,
)

BARE_HOUR_PATTERN = re.compile(
    r"\b(?:at|around|by)\s+(\d{1,2})\b(?!\s*(?::|[ap]\.?m))", re.IGNORECASE
)

_SEARCH_LEAD = re.compile(
    r"^(?:the\s+)?(?:please\s+)?(?:can you\s+)?"
    r"(?:search(?:\s+for)?|look\s+up|google|find(?:\s+out)?|tell\s+me|show\s+me"
    r"|give\s+me|get\s+me|what(?:'s|\s+is)?|which|any|latest|newest|recent|updates?\s+on)\b\s*",
    re.IGNORECASE,
)

_SEARCH_TAIL = re.compile(
    r"\s*\b(?:came\s+out|come\s+out|came\s+in|happened|going\s+on|released|out)\b\s*[?.!,]*$",
    re.IGNORECASE,
)

_CONNECTORS = {"for", "from", "to", "at", "on", "in", "by", "about", "and", "please", "of"}
_ARTICLES = {"the", "a", "an"}
_FILLERS = {"it", "that", "this", "them", "these", "those"}

_TIME_NOISE = (
    RELATIVE_PATTERN,
    RANGE_PATTERN,
    DURATION_PATTERN,
    DATE_PATTERN,
    TIME_PATTERN,
    BARE_HOUR_PATTERN,
)


@dataclass
class When:
    day: date | None = None
    start: time | None = None
    end: time | None = None
    duration_minutes: int | None = None
    relative_at: datetime | None = None
    ambiguous_hour: int | None = None


@dataclass
class Parts:
    title: str = ""
    task: str = ""
    content: str = ""
    query: str = ""
    style: str = ""
    when: When = field(default_factory=When)
    date_range: tuple[date, date] | None = None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered.isdigit():
        return int(lowered)
    return WORD_NUMBERS.get(lowered)


def _apply_meridiem(hour: int, minute: int, meridiem: str | None) -> time:
    if meridiem:
        low = meridiem.lower().replace(".", "").strip()
        if low.startswith("p") and hour < 12:
            hour += 12
        elif low.startswith("a") and hour == 12:
            hour = 0
    return time(hour % 24, minute)


def _parse_time_token(token: str) -> time | None:
    match = re.match(rf"\s*(\d{{1,2}})(?::(\d{{2}}))?\s*({_MER})?", token, re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    return _apply_meridiem(hour, minute, match.group(3))


def _has_meridiem(token: str) -> bool:
    return re.search(_MER, token, re.IGNORECASE) is not None


def _time_from_match(match: re.Match[str]) -> time | None:
    if match.group("h24") is not None:
        return _apply_meridiem(int(match.group("h24")), int(match.group("m24")), match.group("mer24"))
    if match.group("h12") is not None:
        return _apply_meridiem(int(match.group("h12")), 0, match.group("mer12"))
    if match.group("named") is not None:
        name = match.group("named").lower()
        return time(12, 0) if name == "noon" else time(0, 0)
    if match.group("named2") is not None:
        return NAMED_TIMES[match.group("named2").lower()]
    return None


def _relative_delta(match: re.Match[str]) -> timedelta | None:
    amount = _to_int(match.group("num"))
    unit = match.group("unit").lower().rstrip("s")
    seconds = _UNIT_SECONDS.get(unit)
    if amount is None or seconds is None:
        return None
    return timedelta(seconds=amount * seconds)


def _duration_minutes(match: re.Match[str]) -> int | None:
    raw = match.group(0).lower()
    if "hour and a half" in raw:
        return 90
    if "half an hour" in raw:
        return 30
    amount = _to_int(match.group("num"))
    unit = (match.group("unit") or "").lower().rstrip("s")
    if amount is None:
        return None
    if unit.startswith("hour") or unit == "hr":
        return amount * 60
    if unit.startswith("min"):
        return amount
    return None


def _soonest_weekday(target: int, today: date) -> date:
    return today + timedelta(days=(target - today.weekday()) % 7)


def _this_week_weekday(target: int, today: date) -> date:
    result = today + timedelta(days=target - today.weekday())
    if result < today:
        result += timedelta(days=7)
    return result


def _next_week_weekday(target: int, today: date) -> date:
    next_monday = today + timedelta(days=7 - today.weekday())
    return next_monday + timedelta(days=target)


def _explicit_day(expr: str, today: date) -> date | None:
    if _ISO_RE.fullmatch(expr):
        try:
            return date.fromisoformat(expr)
        except ValueError:
            return None

    month: int | None = None
    day: int | None = None
    year: int | None = None

    if match := _MONTH_DATE_RE.fullmatch(expr):
        month = MONTHS[match.group(1).lower()]
        day = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else None
    elif match := _DAY_MONTH_RE.fullmatch(expr):
        day = int(match.group(1))
        month = MONTHS[match.group(2).lower()]
        year = int(match.group(3)) if match.group(3) else None
    else:
        return None

    if year is not None:
        try:
            return date(year, month, day)
        except ValueError:
            return None

    try:
        result = date(today.year, month, day)
    except ValueError:
        return None
    if result < today:
        try:
            result = date(today.year + 1, month, day)
        except ValueError:
            return None
    return result


def _day_from_expr(expr: str, today: date) -> date | None:
    lowered = expr.lower().strip().rstrip(",")
    if lowered == "today":
        return today
    if lowered == "tomorrow":
        return today + timedelta(days=1)
    if lowered == "yesterday":
        return today - timedelta(days=1)
    if lowered == "day after tomorrow":
        return today + timedelta(days=2)
    if lowered.startswith("this "):
        target = WEEKDAYS.get(lowered[5:])
        return _this_week_weekday(target, today) if target is not None else None
    if lowered.startswith("next "):
        target = WEEKDAYS.get(lowered[5:])
        return _next_week_weekday(target, today) if target is not None else None
    if lowered in WEEKDAYS:
        return _soonest_weekday(WEEKDAYS[lowered], today)
    return _explicit_day(lowered, today)


def resolve_date(text: str, today: date) -> date | None:
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    return _day_from_expr(match.group(1), today)


def resolve_date_range(text: str, today: date) -> tuple[date, date] | None:
    lowered = text.lower()
    if "last week" in lowered:
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if "this week" in lowered:
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if "next week" in lowered:
        start = today + timedelta(days=7 - today.weekday())
        return start, start + timedelta(days=6)

    if match := PAST_RANGE_PATTERN.search(text):
        amount = int(match.group(1))
        days = amount * 7 if match.group(2).lower().startswith("week") else amount
        return today - timedelta(days=max(days - 1, 0)), today

    day = resolve_date(text, today)
    if day:
        return day, day
    return None


def resolve_when(text: str, today: date, now: datetime) -> When:
    when = When()

    if match := RELATIVE_PATTERN.search(text):
        delta = _relative_delta(match)
        if delta:
            moment = now + delta
            when.relative_at = moment.replace(second=0, microsecond=0)
            when.day = when.relative_at.date()
            when.start = when.relative_at.time()

    if match := RANGE_PATTERN.search(text):
        start = _parse_time_token(match.group("start"))
        end = _parse_time_token(match.group("end"))
        if start and end:
            if not _has_meridiem(match.group("start")) and _has_meridiem(match.group("end")):
                meridiem = re.search(_MER, match.group("end"), re.IGNORECASE).group(0)
                start = _apply_meridiem(start.hour, start.minute, meridiem)
            when.start, when.end = start, end

    if match := DURATION_PATTERN.search(text):
        minutes = _duration_minutes(match)
        if minutes:
            when.duration_minutes = minutes

    if when.start is None and when.relative_at is None:
        bare = BARE_HOUR_PATTERN.search(text)
        if bare:
            hour = int(bare.group(1))
            if 1 <= hour <= 12:
                when.ambiguous_hour = hour
                when.start = None
            elif hour < 24:
                when.start = time(hour, 0)
        if when.start is None and when.ambiguous_hour is None:
            match = TIME_PATTERN.search(text)
            if match:
                when.start = _time_from_match(match)
    if when.day is None:
        when.day = resolve_date(text, today)

    return when


def _remove(text: str, patterns) -> str:
    result = text
    for pattern in patterns:
        result = pattern.sub(" ", result)
    return result


def _tidy(text: str, *, articles: bool = False) -> str:
    words = text.split()
    strip = _CONNECTORS | _ARTICLES | _FILLERS if articles else _CONNECTORS
    while words and words[0].lower().strip(".,!?:") in strip:
        words.pop(0)
    while words and words[-1].lower().strip(".,!?:") in strip:
        words.pop()
    return " ".join(words).strip(" .,!?:")


def _sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _strip_lead(pattern: re.Pattern[str], text: str) -> str:
    for _ in range(3):
        stripped = pattern.sub("", text, count=1)
        if stripped == text:
            break
        text = stripped
    return text


def extract(text: str, now: datetime) -> Parts:
    today = now.date()
    cleaned = _remove(text, _TIME_NOISE)

    title = _tidy(_strip_lead(_EVENT_LEAD, cleaned), articles=True)
    task = _tidy(_strip_lead(_REMINDER_LEAD, cleaned), articles=True)
    if not task and re.search(r"\b(alarm|wake me)\b", text, re.IGNORECASE):
        task = "Wake up"

    content = _tidy(_strip_lead(_NOTE_LEAD, text))

    query_source = _STYLE_STRIP.sub(" ", cleaned)
    query = (
        _tidy(_SEARCH_TAIL.sub("", _strip_lead(_SEARCH_LEAD, query_source)), articles=True)
        or _tidy(query_source, articles=True)
    )

    return Parts(
        title=_sentence_case(title),
        task=_sentence_case(task),
        content=content,
        query=query,
        style="brief" if _STYLE_BRIEF.search(text) else "",
        when=resolve_when(text, today, now),
        date_range=resolve_date_range(text, today),
    )
