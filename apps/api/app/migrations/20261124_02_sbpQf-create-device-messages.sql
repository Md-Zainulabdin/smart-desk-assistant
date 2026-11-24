-- create device messages
-- depends: 20261124_01_V3Z2L-create-devices

-- One row per transcript a device sent over MQTT. The primary key drops
-- QoS 1 redeliveries; the stored reply is re-sent instead of re-running the action.
-- The transcript text itself is not stored.
CREATE TABLE device_messages (
    device_id     TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    message_id    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing', 'done', 'failed')),
    outcome       TEXT,
    intent        TEXT,
    reply         TEXT,
    error         TEXT,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at  TIMESTAMPTZ,
    PRIMARY KEY (device_id, message_id)
);
