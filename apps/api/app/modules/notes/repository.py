from uuid import UUID

from psycopg import Connection

from app.modules.notes.schemas import Note


def create_note(
    conn: Connection, user_id: UUID, content: str, request_id: str | None = None
) -> Note:
    row = conn.execute(
        """
        INSERT INTO notes (user_id, content, command_request_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id, command_request_id)
        DO UPDATE SET command_request_id = EXCLUDED.command_request_id
        RETURNING id, content, created_at
        """,
        (user_id, content, request_id),
    ).fetchone()
    conn.commit()
    return Note.model_validate(row)


def list_notes(conn: Connection, user_id: UUID) -> list[Note]:
    rows = conn.execute(
        """
        SELECT id, content, created_at FROM notes
        WHERE user_id = %s
        ORDER BY created_at DESC, id DESC
        """,
        (user_id,),
    ).fetchall()
    return [Note.model_validate(row) for row in rows]


def get_note(conn: Connection, user_id: UUID, note_id: UUID) -> Note | None:
    row = conn.execute(
        "SELECT id, content, created_at FROM notes WHERE user_id = %s AND id = %s",
        (user_id, note_id),
    ).fetchone()
    return Note.model_validate(row) if row else None


def update_note(conn: Connection, user_id: UUID, note_id: UUID, content: str) -> Note | None:
    row = conn.execute(
        """
        UPDATE notes SET content = %s WHERE user_id = %s AND id = %s
        RETURNING id, content, created_at
        """,
        (content, user_id, note_id),
    ).fetchone()
    conn.commit()
    return Note.model_validate(row) if row else None


def delete_note(conn: Connection, user_id: UUID, note_id: UUID) -> bool:
    result = conn.execute(
        "DELETE FROM notes WHERE user_id = %s AND id = %s",
        (user_id, note_id),
    )
    conn.commit()
    return result.rowcount == 1
