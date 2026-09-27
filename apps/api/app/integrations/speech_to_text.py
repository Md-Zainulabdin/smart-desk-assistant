from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq

from app.config import get_settings
from app.core.exceptions import ApiError

MODEL = "whisper-large-v3-turbo"


def transcribe(data: bytes, filename: str, language: str | None = None) -> dict[str, str]:
    """Send raw audio bytes to Groq Whisper. Returns {"text", "language"}."""
    api_key = get_settings().GROQ_API_KEY
    if not api_key:
        raise ApiError("stt not configured", "stt_not_configured", 500)

    try:
        client = Groq(api_key=api_key)
        result = client.audio.transcriptions.create(
            model=MODEL,
            file=(filename, data),
            response_format="verbose_json",
            **({"language": language} if language else {}),
        )
    except (APIConnectionError, APIStatusError, APITimeoutError) as exc:
        raise ApiError("speech provider failed", "upstream_error", 502) from exc

    return {"text": result.text or "", "language": result.language or ""}
