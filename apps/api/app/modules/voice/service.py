from app.core.exceptions import ApiError
from app.integrations import speech_to_text
from app.integrations.speech_to_text import MODEL
from app.modules.voice.intent import parse_intent
from app.modules.voice.schemas import SttResponse

MAX_AUDIO_BYTES = 10 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "audio/webm",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
}

ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}


def process_voice_command(
    data: bytes,
    filename: str,
    content_type: str | None,
    language: str | None = None,
) -> SttResponse:
    if not data:
        raise ApiError("empty audio file", "invalid_audio", 400)

    if len(data) > MAX_AUDIO_BYTES:
        raise ApiError("audio file too large", "too_large", 413)

    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if content_type not in ALLOWED_MIME_TYPES and suffix not in ALLOWED_EXTENSIONS:
        raise ApiError("unsupported audio type", "invalid_audio", 400)

    result = speech_to_text.transcribe(data, filename, language)
    transcript = result["text"].strip()
    if not transcript:
        raise ApiError("no speech detected", "invalid_audio", 400)

    intent, slots = parse_intent(transcript)
    return SttResponse(
        transcript=transcript,
        language=result["language"],
        intent=intent,
        slots=slots,
        model=MODEL,
    )
