from uuid import UUID

from psycopg import Connection

from app.modules.device.schemas import Device, DeviceMessage, MessageStatus

DEVICE_COLUMNS = "device_id, user_id, name, online, last_seen_at, created_at"


def get_device(conn: Connection, device_id: str) -> Device | None:
    row = conn.execute(
        f"SELECT {DEVICE_COLUMNS} FROM devices WHERE device_id = %s", (device_id,)
    ).fetchone()
    return Device.model_validate(row) if row else None


def claim_device(conn: Connection, user_id: UUID, device_id: str, name: str | None) -> Device | None:
    """Link a device to the user. Returns None if another user already owns it."""
    row = conn.execute(
        f"""
        INSERT INTO devices (device_id, user_id, name)
        VALUES (%s, %s, %s)
        ON CONFLICT (device_id) DO UPDATE
        SET name = COALESCE(EXCLUDED.name, devices.name)
        WHERE devices.user_id = EXCLUDED.user_id
        RETURNING {DEVICE_COLUMNS}
        """,
        (device_id, user_id, name),
    ).fetchone()
    conn.commit()
    return Device.model_validate(row) if row else None


def list_devices(conn: Connection, user_id: UUID) -> list[Device]:
    rows = conn.execute(
        f"SELECT {DEVICE_COLUMNS} FROM devices WHERE user_id = %s ORDER BY created_at",
        (user_id,),
    ).fetchall()
    return [Device.model_validate(row) for row in rows]


def unlink_device(conn: Connection, user_id: UUID, device_id: str) -> bool:
    result = conn.execute(
        "DELETE FROM devices WHERE user_id = %s AND device_id = %s", (user_id, device_id)
    )
    conn.commit()
    return result.rowcount == 1


def set_status(conn: Connection, device_id: str, online: bool) -> None:
    conn.execute(
        "UPDATE devices SET online = %s, last_seen_at = now() WHERE device_id = %s",
        (online, device_id),
    )
    conn.commit()


def begin_message(conn: Connection, device_id: str, message_id: str) -> bool:
    """Record a new transcript. False if this (device, message) was seen before."""
    row = conn.execute(
        """
        INSERT INTO device_messages (device_id, message_id)
        VALUES (%s, %s)
        ON CONFLICT (device_id, message_id) DO NOTHING
        RETURNING message_id
        """,
        (device_id, message_id),
    ).fetchone()
    conn.commit()
    return row is not None


def get_message(conn: Connection, device_id: str, message_id: str) -> DeviceMessage | None:
    row = conn.execute(
        """
        SELECT device_id, message_id, status, reply, published_at FROM device_messages
        WHERE device_id = %s AND message_id = %s
        """,
        (device_id, message_id),
    ).fetchone()
    return DeviceMessage.model_validate(row) if row else None


def finish_message(
    conn: Connection,
    device_id: str,
    message_id: str,
    status: MessageStatus,
    reply: str,
    outcome: str | None = None,
    intent: str | None = None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE device_messages
        SET status = %s, reply = %s, outcome = %s, intent = %s, error = %s
        WHERE device_id = %s AND message_id = %s
        """,
        (status.value, reply, outcome, intent, error, device_id, message_id),
    )
    conn.commit()


def mark_published(conn: Connection, device_id: str, message_id: str) -> None:
    conn.execute(
        """
        UPDATE device_messages SET published_at = now()
        WHERE device_id = %s AND message_id = %s
        """,
        (device_id, message_id),
    )
    conn.commit()
