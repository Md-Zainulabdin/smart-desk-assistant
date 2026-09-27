import re

from app.modules.voice.schemas import Intent

WHEN_PATTERN = re.compile(
    r"\b(tomorrow|today|tonight|day after tomorrow"
    r"|this (morning|afternoon|evening|week)|next week|on \w+day"
    r"|(?:at|for) \d{1,2}(:\d{2})?\s?([ap]\.?m\.?\.?)?"
    r"|in \d+ (minutes?|hours?|days?)|in an? (minute|hour|day|week))(?!\w)",
    re.IGNORECASE,
)

CHECKLIST_PATTERN = re.compile(
    r"(?:add|put) (.+?) (?:to|on) (?:my |the )?(\w[\w ]*?) ?list\b",
    re.IGNORECASE,
)

AVAILABILITY_PATTERN = re.compile(
    r"\b(am i|are we)\b.{0,20}\b(free|busy|available)\b",
    re.IGNORECASE,
)

READ_QUESTIONS = {
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

# Destructive / later-scope verbs: never misfire these as creations in v1.
OUT_OF_SCOPE_VERBS = {
    "cancel",
    "cancelled",
    "delete",
    "remove",
    "snooze",
    "dismiss",
}


def _when_slot(text: str, slots: dict[str, str]) -> None:
    if match := WHEN_PATTERN.search(text):
        slots["when"] = match.group(1).strip()


def parse_intent(text: str) -> tuple[Intent, dict[str, str]]:
    """Rule-based intent parsing. Ordered rules, first match wins."""
    lowered = text.lower()
    slots: dict[str, str] = {"text": text.strip()}
    _when_slot(text, slots)

    if any(verb in lowered for verb in OUT_OF_SCOPE_VERBS):
        return Intent.UNKNOWN, slots
    if "remind" in lowered or "alarm" in lowered or "wake me" in lowered:
        return Intent.CREATE_REMINDER, slots
    if "remember to" in lowered:
        return Intent.CREATE_REMINDER, slots
    if match := CHECKLIST_PATTERN.search(text):
        slots["item"] = match.group(1).strip()
        slots["list"] = match.group(2).strip()
        return Intent.CREATE_CHECKLIST, slots
    if "checklist" in lowered:
        return Intent.CREATE_CHECKLIST, slots
    if AVAILABILITY_PATTERN.search(text):
        return Intent.READ_EVENTS, slots
    if "do i have" in lowered or (
        any(q in lowered for q in READ_QUESTIONS)
        and any(n in lowered for n in CALENDAR_NOUNS)
    ):
        return Intent.READ_EVENTS, slots
    if "note" in lowered or "write down" in lowered or "remember" in lowered:
        return Intent.CREATE_NOTE, slots
    if any(n in lowered for n in CALENDAR_NOUNS):
        return Intent.CREATE_EVENT, slots
    return Intent.UNKNOWN, slots
