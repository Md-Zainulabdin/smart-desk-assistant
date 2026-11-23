"""Orchestrator: turns one user sentence into a finished action.

parse -> ask a question (and remember it) | refuse | carry out the action.
The parser decides *what* the user wants; this module decides what happens next.
"""

import re
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from psycopg import Connection
from pydantic import ValidationError

from app.core.exceptions import ApiError
from app.modules.calendar import service as calendar_service
from app.modules.calendar.schemas import MeetingIn
from app.modules.command import service as command_service
from app.modules.command.schemas import CommandContext, Intent, Status
from app.modules.notes import repository as notes_repository
from app.modules.notes.schemas import NoteInput
from app.modules.orchestrator import repository
from app.modules.orchestrator.schemas import AssistantRequest, AssistantResponse, Outcome
from app.modules.web_search.services import search_web

NOT_BUILT_YET = {
    Intent.READ_EVENTS: "Reading your calendar",
}

# The parser still recognises these, but the assistant does not act on them.
NOT_SUPPORTED = {Intent.CREATE_REMINDER}


def _create_note(
    conn: Connection, user_id: UUID, slots: dict[str, str], request_id: str | None
) -> AssistantResponse:
    try:
        content = NoteInput(content=slots["content"]).content
    except (KeyError, ValidationError):
        return _failed(Intent.CREATE_NOTE, "I couldn't save that note.")
    note = notes_repository.create_note(conn, user_id, content, request_id)
    return AssistantResponse(
        outcome=Outcome.DONE,
        intent=Intent.CREATE_NOTE,
        reply="Saved your note.",
        result={"note_id": str(note.id)},
    )


def _create_event(
    conn: Connection, user_id: UUID, slots: dict[str, str], request_id: str | None
) -> AssistantResponse:
    try:
        meeting = MeetingIn(
            title=slots["title"],
            start=slots["start_at"],
            end=slots["end_at"],
            timezone=slots.get("timezone"),
            request_id=request_id,
        )
    except (KeyError, ValidationError):
        return _failed(Intent.CREATE_EVENT, "I couldn't understand the meeting details.")
    booked = calendar_service.book_meeting(conn, user_id, meeting)
    when = datetime.fromisoformat(slots["start_at"]).strftime("%a %d %b at %H:%M")
    return AssistantResponse(
        outcome=Outcome.DONE,
        intent=Intent.CREATE_EVENT,
        reply=f"Booked {meeting.title} for {when}.",
        result={"event_id": booked.id, "link": booked.link, "meet_link": booked.meet_link},
    )


SPOKEN_MAX_CHARS = 280  # the ESP32 speaks the reply and the app shows it, so keep it short


def _speakable(text: str) -> str:
    """Plain words only: no links, URLs or markdown symbols, which a speaker would read out."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[#*_`|>~]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _shorten(text: str, limit: int) -> str:
    """Cut at the last full sentence that fits, or at a word if there is none."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    last_stop = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
    if last_stop > 0:
        return head[: last_stop + 1]
    return head.rsplit(" ", 1)[0].rstrip(",;:-") + "."


def _spoken_answer(answer: str, results: list[dict]) -> str:
    """Tavily's written answer if there is one, else the top result's title and start of its text."""
    answer = _speakable(answer)
    if answer:
        return _shorten(answer, SPOKEN_MAX_CHARS)
    top = results[0]
    title = _speakable(top.get("title", "")).rstrip(".")
    snippet = _speakable(top.get("snippet", ""))
    if not snippet:
        return _shorten(f"The top result is {title}." if title else "I found a result.", SPOKEN_MAX_CHARS)
    reply = f"{title}. {snippet}" if title and not snippet.startswith(title) else snippet
    return _shorten(reply, SPOKEN_MAX_CHARS)


def _web_search(
    conn: Connection, user_id: UUID, slots: dict[str, str], request_id: str | None
) -> AssistantResponse:
    filters = {
        field: slots[slot]
        for field, slot in (("start_date", "date_from"), ("end_date", "date_to"))
        if slot in slots
    }
    found = search_web(slots.get("query"), include_answer=True, **filters)
    if not found["success"]:
        return _failed(Intent.WEB_SEARCH, found["error"]["message"])

    data = found["data"]
    results = data["results"]
    answer = data.get("answer") or ""
    if results or answer:
        reply = _spoken_answer(answer, results)
    else:
        reply = f"I couldn't find anything for {data['query']}."
    return AssistantResponse(
        outcome=Outcome.DONE,
        intent=Intent.WEB_SEARCH,
        reply=reply,
        result={"query": data["query"], "answer": answer, "results": results},
    )


ACTIONS: dict[Intent, Callable[..., AssistantResponse]] = {
    Intent.CREATE_NOTE: _create_note,
    Intent.CREATE_EVENT: _create_event,
    Intent.WEB_SEARCH: _web_search,
}


def _failed(intent: Intent, reply: str) -> AssistantResponse:
    return AssistantResponse(outcome=Outcome.FAILED, intent=intent, reply=reply)


def handle(conn: Connection, user_id: UUID, request: AssistantRequest) -> AssistantResponse:
    """Handle one sentence from the user and return what to say back."""
    pending = repository.get_pending(conn, user_id)
    parsed = command_service.parse_command(
        request.text, request.request_id, request.timezone, pending
    )

    if parsed.intent in NOT_SUPPORTED:
        # Do not ask follow-up questions for something that will not be done.
        if pending is not None:
            repository.clear_pending(conn, user_id)
        return AssistantResponse(
            outcome=Outcome.UNSUPPORTED, intent=parsed.intent, reply="Sorry, I can't help with that."
        )

    if parsed.status is Status.NEEDS_CLARIFICATION:
        context = CommandContext(intent=parsed.intent, slots=parsed.slots, missing=parsed.missing)
        repository.save_pending(conn, user_id, context)
        return AssistantResponse(
            outcome=Outcome.NEEDS_CLARIFICATION, intent=parsed.intent, reply=parsed.clarification
        )

    # Anything else ends the pending question, including "cancel that".
    if pending is not None:
        repository.clear_pending(conn, user_id)

    if parsed.status is Status.UNSUPPORTED:
        return AssistantResponse(
            outcome=Outcome.UNSUPPORTED, intent=parsed.intent, reply="Sorry, I can't help with that."
        )

    action = ACTIONS.get(parsed.intent)
    if action is None:
        feature = NOT_BUILT_YET.get(parsed.intent, "That")
        return AssistantResponse(
            outcome=Outcome.UNSUPPORTED,
            intent=parsed.intent,
            reply=f"{feature} isn't available yet.",
        )

    try:
        return action(conn, user_id, parsed.slots, request.request_id)
    except ApiError as error:
        # e.g. Calendar not granted: tell the user instead of failing the request.
        return _failed(parsed.intent, error.detail)
