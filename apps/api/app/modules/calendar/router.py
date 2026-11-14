from fastapi import APIRouter, Depends

from app.database.models import User
from app.dependencies import current_user
from app.modules.calendar.schemas import MeetingIn, MeetingOut
from app.modules.calendar.service import book_meeting

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/meetings", response_model=MeetingOut)
def create_calendar_meeting(meeting: MeetingIn, user: User = Depends(current_user)):
    return book_meeting(user, meeting)
