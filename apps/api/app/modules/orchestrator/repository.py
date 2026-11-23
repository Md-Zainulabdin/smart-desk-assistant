from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.modules.command.schemas import CommandContext

# A question left unanswered this long is dropped, so an old one never merges
# with an unrelated new sentence.
PENDING_TTL_MINUTES = 10


def get_pending(conn: Connection, user_id: UUID) -> CommandContext | None:
    row = conn.execute(
        """
        SELECT intent, slots, missing FROM pending_commands
        WHERE user_id = %s AND updated_at > now() - make_interval(mins => %s)
        """,
        (user_id, PENDING_TTL_MINUTES),
    ).fetchone()
    return CommandContext.model_validate(row) if row else None


def save_pending(conn: Connection, user_id: UUID, context: CommandContext) -> None:
    conn.execute(
        """
        INSERT INTO pending_commands (user_id, intent, slots, missing)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE
        SET intent = EXCLUDED.intent,
            slots = EXCLUDED.slots,
            missing = EXCLUDED.missing,
            updated_at = now()
        """,
        (user_id, context.intent.value, Jsonb(context.slots), Jsonb(context.missing)),
    )
    conn.commit()


def clear_pending(conn: Connection, user_id: UUID) -> None:
    conn.execute("DELETE FROM pending_commands WHERE user_id = %s", (user_id,))
    conn.commit()
