"""Intent classification. Ordered rules, first match wins."""

from __future__ import annotations

import re

from app.modules.command.extract import DATE_PATTERN, RANGE_PATTERN, RELATIVE_PATTERN, TIME_PATTERN
from app.modules.command.schemas import Intent

CALENDAR_NOUNS = {
    "meeting",
    "meetings",
    "event",
    "events",
    "calendar",
    "schedule",
    "appointment",
    "appointments",
    "agenda",
}

READ_WORDS = {
    "what",
    "when",
    "show",
    "list",
    "tell",
    "upcoming",
    "agenda",
    "any",
    "free",
    "busy",
    "available",
}

SEARCH_CUES = {
    "search",
    "look up",
    "google",
    "news",
    "headline",
    "headlines",
    "latest",
    "update",
    "updates",
    "research",
    "papers",
    "released",
    "overview",
    "summary",
    "summaries",
    "brief",
    "briefing",
    "what happened",
    "find out",
    "give me",
}

REMINDER_CUES = {"remind", "alarm", "wake me", "remember to"}

NOTE_CUES = {"note", "notes", "write down", "jot", "remember"}

CREATE_CUES = {
    "schedule",
    "book",
    "set up",
    "create",
    "organize",
    "arrange",
    "make",
    "plan",
}

# Destructive verbs are out of scope for v1 and must never misfire as creations.
OUT_OF_SCOPE_VERBS = {"cancel", "cancelled", "delete", "remove", "snooze", "dismiss"}

AVAILABILITY_PATTERN = re.compile(
    r"\b(am i|are we)\b.{0,20}\b(free|busy|available)\b", re.IGNORECASE
)

LEAD_NOTE = re.compile(
    r"^(?:please\s+)?(?:"
    r"notes?"
    r"|write\s+(?:a\s+|an\s+|the\s+|this\s+|that\s+|down\s+)*notes?"
    r"|jot\s+(?:down\s+)?"
    r"|(?:take|make|create|add)\s+(?:a\s+|an\s+|the\s+|this\s+|that\s+)*notes?"
    r")\b",
    re.IGNORECASE,
)

LEAD_REMINDER = re.compile(
    r"^(?:please\s+)?(?:"
    r"remind\s+me"
    r"|set\s+(?:an?\s+)?alarm"
    r"|wake\s+me\b"
    r"|remember\s+to"
    r")\b",
    re.IGNORECASE,
)

LEAD_EVENT = re.compile(
    r"^(?:please\s+)?(?:"
    r"schedule|book|set\s+up|create|organize|arrange|plan|make|add"
    r")\b",
    re.IGNORECASE,
)

_SPLITTER = re.compile(r"\s+and\s+|\s+then\s+|;", re.IGNORECASE)


def _has_any(text: str, cues) -> bool:
    return any(re.search(rf"\b{re.escape(cue)}\b", text) for cue in cues)


def _has_when(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in (DATE_PATTERN, TIME_PATTERN, RANGE_PATTERN, RELATIVE_PATTERN)
    )


def is_out_of_scope(text: str) -> bool:
    return _has_any(text.lower(), OUT_OF_SCOPE_VERBS)


def _is_read(text: str, has_calendar_noun: bool) -> bool:
    if "do i have" in text or AVAILABILITY_PATTERN.search(text):
        return True
    return _has_any(text, READ_WORDS) and has_calendar_noun


def classify(text: str) -> Intent:
    lowered = text.lower()
    has_calendar_noun = _has_any(lowered, CALENDAR_NOUNS)

    if _has_any(lowered, OUT_OF_SCOPE_VERBS):
        return Intent.UNKNOWN
    if LEAD_NOTE.match(text.strip()):
        return Intent.CREATE_NOTE
    if LEAD_REMINDER.match(text.strip()):
        return Intent.CREATE_REMINDER
    if LEAD_EVENT.match(text.strip()) and has_calendar_noun:
        return Intent.CREATE_EVENT
    if not has_calendar_noun and _has_any(lowered, SEARCH_CUES):
        return Intent.WEB_SEARCH
    if _has_any(lowered, REMINDER_CUES):
        return Intent.CREATE_REMINDER
    if _is_read(lowered, has_calendar_noun):
        return Intent.READ_EVENTS
    if _has_any(lowered, NOTE_CUES):
        return Intent.CREATE_NOTE
    if _has_any(lowered, CREATE_CUES) and has_calendar_noun:
        return Intent.CREATE_EVENT
    if has_calendar_noun and _has_when(text):
        return Intent.CREATE_EVENT
    return Intent.UNKNOWN


def classify_all(text: str) -> list[Intent]:
    """Detect whether one command asks for more than one thing."""
    parts = [part.strip() for part in _SPLITTER.split(text) if part.strip()]
    if len(parts) <= 1:
        single = classify(text)
        return [] if single is Intent.UNKNOWN else [single]

    found: list[Intent] = []
    for part in parts:
        detected = classify(part)
        if detected is not Intent.UNKNOWN and detected not in found:
            found.append(detected)
    return found
