from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from psycopg import Connection

from app.core.exceptions import ApiError
from app.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar import service
from app.modules.calendar.schemas import MeetingIn, MeetingOut, MeetingSummary

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])


@router.get("/meetings", response_model=list[MeetingSummary])
def list_meetings(
    user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_db)],
    start: datetime | None = None,
    end: datetime | None = None,
    max_results: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MeetingSummary]:
    range_start = start or datetime.now(UTC)
    range_end = end or range_start + timedelta(days=7)
    if range_start.tzinfo is None or range_end.tzinfo is None:
        raise ApiError("start and end must include a UTC offset", "invalid_date_range", 422)
    if range_end <= range_start:
        raise ApiError("end must be after start", "invalid_date_range", 422)
    return service.list_meetings(conn, user["id"], range_start, range_end, max_results)


@router.post("/meetings", status_code=status.HTTP_201_CREATED)
def create_meeting(
    meeting: MeetingIn,
    user: Annotated[dict, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_db)],
) -> MeetingOut:
    return service.book_meeting(conn, user["id"], meeting)
