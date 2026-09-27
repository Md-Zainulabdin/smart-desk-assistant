from fastapi import APIRouter, Form, UploadFile

from app.modules.voice import service
from app.modules.voice.schemas import SttResponse

router = APIRouter(prefix="/api/v1", tags=["voice"])


@router.post("/stt", response_model=SttResponse)
async def speech_to_text(
    file: UploadFile,
    language: str | None = Form(default=None),
) -> SttResponse:
    data = await file.read()
    return service.process_voice_command(
        data, file.filename or "audio.webm", file.content_type, language
    )
