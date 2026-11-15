from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import Connection
from pydantic import ValidationError

from app.core.exceptions import ApiError
from app.db import get_db
from app.modules.command import service
from app.modules.command.schemas import CommandRequest, CommandResponse, Intent, Status
from app.modules.notes import repository
from app.modules.notes.schemas import NoteInput
from app.users.controller import current_user
from app.users.model import User

router = APIRouter(prefix="/api/v1", tags=["command"])


@router.post("/command", response_model=CommandResponse)
def parse_command(
    payload: CommandRequest,
    user: Annotated[User, Depends(current_user)],
    conn: Annotated[Connection, Depends(get_db)],
) -> CommandResponse:
    result = service.parse_command(
        payload.text,
        payload.request_id,
        payload.timezone,
        payload.context,
    )
    if result.intent is Intent.CREATE_NOTE and result.status is Status.READY:
        try:
            note_input = NoteInput(content=result.slots["content"])
        except ValidationError:
            raise ApiError("Invalid note content", "invalid_note_content", 422) from None
        note = repository.create_note(conn, user.id, note_input.content, payload.request_id)
        result.slots["note_id"] = str(note.id)
        result.slots["content"] = note.content
    return result
