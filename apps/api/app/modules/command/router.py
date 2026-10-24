from fastapi import APIRouter

from app.modules.command import service
from app.modules.command.schemas import CommandRequest, CommandResponse

router = APIRouter(prefix="/api/v1", tags=["command"])


@router.post("/command", response_model=CommandResponse)
async def parse_command(payload: CommandRequest) -> CommandResponse:
    return service.parse_command(
        payload.text,
        payload.request_id,
        payload.timezone,
        payload.context,
    )
