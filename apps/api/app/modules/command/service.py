from app.core.exceptions import ApiError
from app.modules.command.intent import parse_intent
from app.modules.command.schemas import CommandResponse


def parse_command(text: str, request_id: str | None = None) -> CommandResponse:
    """Validate incoming command text and map it to an intent."""
    cleaned = text.strip()
    if not cleaned:
        raise ApiError("empty command", "invalid_command", 400)

    intent, slots = parse_intent(cleaned)
    return CommandResponse(text=cleaned, intent=intent, slots=slots)
