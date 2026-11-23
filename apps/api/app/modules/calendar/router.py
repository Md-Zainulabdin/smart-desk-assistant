from typing import Annotated

from fastapi import APIRouter, Depends, status
from psycopg import Connection

from app.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service
from app.modules.calendar.schemas import MeetingIn, MeetingOut

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.post("/meetings", status_code=status.HTTP_201_CREATED)
def create_meeting(
    meeting: MeetingIn,
    user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_db)],
) -> MeetingOut:
    return service.book_meeting(conn, user["id"], meeting)
