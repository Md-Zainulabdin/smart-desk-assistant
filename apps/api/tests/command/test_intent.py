import pytest

from app.modules.command import intent
from app.modules.command.intent import classify
from app.modules.command.schemas import Intent


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # calendar reads
        ("what meetings do i have tomorrow", Intent.READ_EVENTS),
        ("show my upcoming events", Intent.READ_EVENTS),
        ("am i free tomorrow", Intent.READ_EVENTS),
        ("any meetings today", Intent.READ_EVENTS),
        ("tell me about the meeting", Intent.READ_EVENTS),
        ("do i have anything on friday", Intent.READ_EVENTS),
        # web search
        ("what ai news came out yesterday", Intent.WEB_SEARCH),
        ("search for ai news", Intent.WEB_SEARCH),
        ("look up the weather", Intent.WEB_SEARCH),
        ("latest tech headlines", Intent.WEB_SEARCH),
        # calendar creates
        ("schedule a meeting tomorrow", Intent.CREATE_EVENT),
        ("book an appointment day after tomorrow", Intent.CREATE_EVENT),
        ("set up a calendar event tomorrow", Intent.CREATE_EVENT),
        ("create an event next monday", Intent.CREATE_EVENT),
        ("meeting with ali tomorrow", Intent.CREATE_EVENT),
        # reminders
        ("remind me to call mom tomorrow", Intent.CREATE_REMINDER),
        ("set an alarm for 7 am", Intent.CREATE_REMINDER),
        ("wake me up in 10 minutes", Intent.CREATE_REMINDER),
        ("remember to water the plants", Intent.CREATE_REMINDER),
        # notes
        ("note that the plants need water", Intent.CREATE_NOTE),
        ("write down my gym routine", Intent.CREATE_NOTE),
        ("remember the wifi password", Intent.CREATE_NOTE),
        ("note my meeting moved to friday", Intent.CREATE_NOTE),
        # unsupported
        ("cancel my meeting tomorrow", Intent.UNKNOWN),
        ("delete that note", Intent.UNKNOWN),
        ("snooze my reminder", Intent.UNKNOWN),
        ("add milk to shopping list", Intent.UNKNOWN),
        ("hello there", Intent.UNKNOWN),
        ("play some music", Intent.UNKNOWN),
    ],
)
def test_classify(text: str, expected: Intent):
    assert classify(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # the graded basic commands
        ("Write a note: buy a new microphone for the project.", Intent.CREATE_NOTE),
        ("Add bread, eggs, and milk to my shopping checklist.", Intent.UNKNOWN),
        ("Give me a brief overview of AI papers released yesterday.", Intent.WEB_SEARCH),
        # information request about a topic, not an event creation
        ("Tell me about Google Calendar.", Intent.READ_EVENTS),
        # a bare calendar noun with no date never triggers an event
        ("We need to finish the calendar integration.", Intent.UNKNOWN),
        ("Turn off the bedroom lights.", Intent.UNKNOWN),
        ("Snooze it for ten minutes.", Intent.UNKNOWN),
        # multi request: note plus event
        ("Create a note and schedule a meeting tomorrow at 3 PM.", Intent.CREATE_NOTE),
    ],
)
def test_classify_graded_cases(text: str, expected: Intent):
    assert classify(text) == expected


def test_classify_all_multi_request():
    assert intent.classify_all("Create a note and schedule a meeting tomorrow at 3 PM.") == [
        Intent.CREATE_NOTE,
        Intent.CREATE_EVENT,
    ]
    assert intent.classify_all("remind me to call mom tomorrow") == [Intent.CREATE_REMINDER]
    assert intent.classify_all("Note that we need bread and milk") == [Intent.CREATE_NOTE]
