"""Missing information detection and clarification questions."""

from __future__ import annotations

from app.modules.command.schemas import Intent

QUESTIONS = {
    "date": "When should the meeting be?",
    "start_at": "What time should the meeting start, and how long should it be?",
    "start_at_meridiem": "Did you mean AM or PM?",
    "end_at": "When should the meeting end?",
    "task": "What should I remind you about?",
    "remind_at": "When should I remind you?",
    "content": "What should the note say?",
    "query": "What should I search for?",
    "single_command": "Please give me one command at a time.",
}


def missing_slots(intent: Intent, slots: dict[str, str]) -> list[str]:
    if intent is Intent.CREATE_EVENT:
        if "date" not in slots:
            return ["date"]
        if "start_at" not in slots:
            return ["start_at_meridiem"] if slots.get("ambiguous_hour") else ["start_at"]
        if slots.get("end_time_invalid"):
            return ["end_at"]
        return []

    if intent is Intent.CREATE_REMINDER:
        missing = []
        if "task" not in slots:
            missing.append("task")
        if "remind_at" not in slots:
            missing.append("remind_at")
        return missing

    if intent is Intent.CREATE_NOTE:
        return [] if slots.get("content") else ["content"]

    if intent is Intent.WEB_SEARCH:
        return [] if slots.get("query") else ["query"]

    return []


def clarification_for(missing: list[str], slots: dict[str, str] | None = None) -> str | None:
    slots = slots or {}
    if not missing:
        return None
    key = missing[0]
    if key == "start_at_meridiem":
        hour = slots.get("ambiguous_hour")
        if hour:
            return f"Did you mean {hour} AM or {hour} PM?"
    if key == "end_at":
        bad = slots.get("end_time_invalid")
        if bad:
            return f"The end time {bad} is before the start. When should the meeting end?"
    return QUESTIONS.get(key)
