from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.orchestrator import service
from app.modules.orchestrator.schemas import AssistantRequest, AssistantResponse

router = APIRouter(prefix="/api/v1", tags=["assistant"])


@router.post("/assistant")
def assistant(
    request: AssistantRequest,
    user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_db)],
) -> AssistantResponse:
    """Say one sentence; get back what happened and what to tell the user."""
    return service.handle(conn, user["id"], request)
