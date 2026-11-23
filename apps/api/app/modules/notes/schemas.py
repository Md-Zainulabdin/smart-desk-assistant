from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints


class NoteInput(BaseModel):
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[^\x00]+$")
    ]


class Note(BaseModel):
    id: UUID
    content: str
    created_at: datetime
