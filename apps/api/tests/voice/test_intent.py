import pytest

from app.modules.voice.intent import parse_intent
from app.modules.voice.schemas import Intent


@pytest.mark.parametrize(
    ("text", "intent", "slots"),
    [
        # reminders
        (
            "remind me to call mom tomorrow",
            Intent.CREATE_REMINDER,
            {"when": "tomorrow"},
        ),
        (
            "remember to water the plants",
            Intent.CREATE_REMINDER,
            {},
        ),
        (
            "set an alarm for 7 am",
            Intent.CREATE_REMINDER,
            {"when": "for 7 am"},
        ),
        (
            "wake me up in 10 minutes",
            Intent.CREATE_REMINDER,
            {"when": "in 10 minutes"},
        ),
        (
            "remind me in an hour to check the oven",
            Intent.CREATE_REMINDER,
            {"when": "in an hour"},
        ),
        (
            "remind me about the meeting at 8 p.m.",
            Intent.CREATE_REMINDER,
            {"when": "at 8 p.m."},
        ),
        (
            "wake me at 7 a.m.",
            Intent.CREATE_REMINDER,
            {"when": "at 7 a.m."},
        ),
        # notes (bare "remember" stays a note, "remember to" is a reminder)
        (
            "note that the plants need water",
            Intent.CREATE_NOTE,
            {},
        ),
        (
            "write down my gym routine",
            Intent.CREATE_NOTE,
            {},
        ),
        (
            "remember the meeting room code is 4410",
            Intent.CREATE_NOTE,
            {},
        ),
        (
            "note my meeting moved to Friday",
            Intent.CREATE_NOTE,
            {},
        ),
        # checklists
        (
            "add milk to shopping list",
            Intent.CREATE_CHECKLIST,
            {"item": "milk", "list": "shopping"},
        ),
        (
            "add eggs to my grocery list",
            Intent.CREATE_CHECKLIST,
            {"item": "eggs", "list": "grocery"},
        ),
        (
            "put bread on the shopping list",
            Intent.CREATE_CHECKLIST,
            {"item": "bread", "list": "shopping"},
        ),
        (
            "create a grocery checklist",
            Intent.CREATE_CHECKLIST,
            {},
        ),
        (
            "add meeting to shopping list",
            Intent.CREATE_CHECKLIST,
            {"item": "meeting", "list": "shopping"},
        ),
        # calendar events
        (
            "schedule a meeting on monday",
            Intent.CREATE_EVENT,
            {"when": "on monday"},
        ),
        (
            "set up a calendar event tomorrow",
            Intent.CREATE_EVENT,
            {"when": "tomorrow"},
        ),
        (
            "book an appointment day after tomorrow",
            Intent.CREATE_EVENT,
            {"when": "day after tomorrow"},
        ),
        # event reads (questions, not creations)
        (
            "what meetings do I have tomorrow",
            Intent.READ_EVENTS,
            {"when": "tomorrow"},
        ),
        (
            "show my upcoming events",
            Intent.READ_EVENTS,
            {},
        ),
        (
            "do I have anything on Friday",
            Intent.READ_EVENTS,
            {"when": "on Friday"},
        ),
        (
            "am I free tomorrow",
            Intent.READ_EVENTS,
            {"when": "tomorrow"},
        ),
        (
            "any meetings today?",
            Intent.READ_EVENTS,
            {"when": "today"},
        ),
        # out of scope / unknown — must never misfire as creations
        ("cancel my meeting tomorrow", Intent.UNKNOWN, {"when": "tomorrow"}),
        ("snooze my reminder", Intent.UNKNOWN, {}),
        ("delete that note", Intent.UNKNOWN, {}),
        ("hello there", Intent.UNKNOWN, {}),
        ("play some music", Intent.UNKNOWN, {}),
    ],
)
def test_intent_matrix(text: str, intent: Intent, slots: dict[str, str]):
    parsed, parsed_slots = parse_intent(text)
    assert parsed == intent
    assert parsed_slots["text"] == text
    for key, value in slots.items():
        assert parsed_slots.get(key) == value
