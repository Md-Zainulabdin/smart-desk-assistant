from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import Connection

from app.db import get_db
from app.modules.notes import repository
from app.modules.notes.schemas import Note, NoteInput
from app.users.controller import current_user
from app.users.model import User

router = APIRouter(prefix="/api/v1/notes", tags=["notes"])

SignedInUser = Annotated[User, Depends(current_user)]
Database = Annotated[Connection, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_note(payload: NoteInput, user: SignedInUser, conn: Database) -> Note:
    return repository.create_note(conn, user.id, payload.content)


@router.get("")
def list_notes(user: SignedInUser, conn: Database) -> list[Note]:
    return repository.list_notes(conn, user.id)


@router.get("/{note_id}")
def get_note(note_id: UUID, user: SignedInUser, conn: Database) -> Note:
    note = repository.get_note(conn, user.id, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.patch("/{note_id}")
def update_note(note_id: UUID, payload: NoteInput, user: SignedInUser, conn: Database) -> Note:
    note = repository.update_note(conn, user.id, note_id, payload.content)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: UUID, user: SignedInUser, conn: Database) -> None:
    if not repository.delete_note(conn, user.id, note_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
