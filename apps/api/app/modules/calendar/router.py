from fastapi import APIRouter, Depends

from app.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.calendar.schemas import MeetingIn, MeetingOut
from app.modules.calendar.service import book_meeting

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/meetings", response_model=MeetingOut)
def create_calendar_meeting(
    meeting: MeetingIn, user: dict = Depends(get_current_user), conn=Depends(get_db)
):
    return book_meeting(conn, user, meeting)
