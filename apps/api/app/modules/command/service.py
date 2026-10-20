from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import get_settings
from app.core.exceptions import ApiError
from app.modules.command import clarify, extract
from app.modules.command import intent as intent_module
from app.modules.command.extract import DEFAULT_EVENT_MINUTES, Parts
from app.modules.command.schemas import CommandContext, CommandResponse, Intent, Status


def _timezone(name: str | None) -> ZoneInfo:
    resolved = name or get_settings().DEFAULT_TIMEZONE
    try:
        return ZoneInfo(resolved)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApiError(f"unknown timezone: {resolved}", "invalid_timezone", 400) from None


def _base_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _base_time(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).time()
    except ValueError:
        return None


def _base_range(base: dict[str, str]) -> tuple[date, date] | None:
    start = _base_date(base.get("date_from"))
    end = _base_date(base.get("date_to"))
    if start and end:
        return start, end
    return None


def _event_slots(parts: Parts, tz: ZoneInfo, base: dict[str, str]) -> dict[str, str]:
    when = parts.when
    title = parts.title or base.get("title", "")
    day = when.day or _base_date(base.get("date"))
    start = when.start or _base_time(base.get("start_at"))

    slots: dict[str, str] = {}
    if title:
        slots["title"] = title
    if day:
        slots["date"] = day.isoformat()

    if day and start:
        start_at = datetime.combine(day, start, tzinfo=tz)
        slots["start_at"] = start_at.isoformat()
        if when.duration_minutes:
            slots["end_at"] = (start_at + timedelta(minutes=when.duration_minutes)).isoformat()
            slots.pop("end_time_invalid", None)
        else:
            end = when.end or _base_time(base.get("end_at"))
            if end is not None:
                end_at = datetime.combine(day, end, tzinfo=tz)
                if end_at > start_at:
                    slots["end_at"] = end_at.isoformat()
                    slots.pop("end_time_invalid", None)
                elif not base.get("end_at"):
                    slots["end_time_invalid"] = end.strftime("%H:%M")
                else:
                    slots.pop("end_time_invalid", None)
                    slots["end_at"] = (start_at + timedelta(minutes=DEFAULT_EVENT_MINUTES)).isoformat()
            else:
                slots.pop("end_time_invalid", None)
                slots["end_at"] = (start_at + timedelta(minutes=DEFAULT_EVENT_MINUTES)).isoformat()

    if start is None and when.ambiguous_hour:
        slots["ambiguous_hour"] = str(when.ambiguous_hour)
    slots["timezone"] = str(tz)
    return slots


def _reminder_slots(parts: Parts, tz: ZoneInfo, now: datetime, base: dict[str, str]) -> dict[str, str]:
    when = parts.when
    task = parts.task or base.get("task", "")

    slots: dict[str, str] = {}
    if task:
        slots["task"] = task

    day = when.day or _base_date(base.get("date")) or _base_date(base.get("remind_at"))
    at = when.start or _base_time(base.get("remind_at"))

    moment = when.relative_at
    if moment is None and at is not None:
        if day is None:
            day = now.date()
        moment = datetime.combine(day, at, tzinfo=tz)
        if moment <= now:
            moment += timedelta(days=1)

    if day:
        slots["date"] = day.isoformat()
    if moment:
        slots["remind_at"] = moment.isoformat()
    slots["timezone"] = str(tz)
    return slots


def _note_slots(parts: Parts, base: dict[str, str]) -> dict[str, str]:
    content = parts.content or base.get("content", "")
    return {"content": content} if content else {}


def _search_slots(parts: Parts, tz: ZoneInfo, base: dict[str, str]) -> dict[str, str]:
    slots: dict[str, str] = {}
    query = parts.query or base.get("query", "")
    if query:
        slots["query"] = query
    style = parts.style or base.get("style", "")
    if style:
        slots["style"] = style
    day_range = parts.date_range or _base_range(base)
    if day_range:
        slots["date_from"] = day_range[0].isoformat()
        slots["date_to"] = day_range[1].isoformat()
    slots["timezone"] = str(tz)
    return slots


def _read_slots(parts: Parts, now: datetime, base: dict[str, str]) -> dict[str, str]:
    default = (now.date(), now.date() + timedelta(days=7))
    day_range = parts.date_range or _base_range(base) or default
    return {"date_from": day_range[0].isoformat(), "date_to": day_range[1].isoformat()}


def _build_slots(
    intent: Intent, parts: Parts, tz: ZoneInfo, now: datetime, base: dict[str, str]
) -> dict[str, str]:
    if intent is Intent.CREATE_EVENT:
        return _event_slots(parts, tz, base)
    if intent is Intent.CREATE_REMINDER:
        return _reminder_slots(parts, tz, now, base)
    if intent is Intent.CREATE_NOTE:
        return _note_slots(parts, base)
    if intent is Intent.WEB_SEARCH:
        return _search_slots(parts, tz, base)
    if intent is Intent.READ_EVENTS:
        return _read_slots(parts, now, base)
    return {}


def parse_command(
    text: str,
    request_id: str | None = None,
    timezone: str | None = None,
    context: CommandContext | None = None,
) -> CommandResponse:
    """Validate command text and turn it into a structured instruction."""
    cleaned = text.strip()
    if not cleaned:
        raise ApiError("empty command", "invalid_command", 400)

    tz = _timezone(timezone)
    now = datetime.now(tz)

    # more than one ask in a single command: never split silently in v1
    multi = intent_module.classify_all(cleaned)
    if len(multi) > 1:
        return CommandResponse(
            text=cleaned,
            intent=multi[0],
            status=Status.NEEDS_CLARIFICATION,
            slots={"detected_intents": ", ".join(item.value for item in multi)},
            missing=["single_command"],
            clarification=clarify.clarification_for(["single_command"]),
        )

    detected = intent_module.classify(cleaned)
    base: dict[str, str] = {}
    if (
        context is not None
        and not intent_module.is_out_of_scope(cleaned)
        and (detected is Intent.UNKNOWN or detected == context.intent)
    ):
        final_intent = context.intent
        base = dict(context.slots)
    else:
        final_intent = detected

    parts = extract.extract(cleaned, now)
    slots = _build_slots(final_intent, parts, tz, now, base)

    missing = clarify.missing_slots(final_intent, slots)
    if final_intent is Intent.UNKNOWN:
        status = Status.UNSUPPORTED
    else:
        status = Status.NEEDS_CLARIFICATION if missing else Status.READY

    return CommandResponse(
        text=cleaned,
        intent=final_intent,
        status=status,
        slots=slots,
        missing=missing,
        clarification=clarify.clarification_for(missing, slots),
    )
