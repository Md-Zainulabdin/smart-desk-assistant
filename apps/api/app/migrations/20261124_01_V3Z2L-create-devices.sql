-- create devices
-- depends: 20261116_03_Pq8Ld-create-pending-commands

-- One Nova device and the user who owns it. device_id is the last 3 MAC bytes
-- the firmware uses in its MQTT topics (nova/<device_id>/...).
CREATE TABLE devices (
    device_id     TEXT PRIMARY KEY CHECK (device_id ~ '^[0-9a-f]{6}$'),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          TEXT,
    online        BOOLEAN NOT NULL DEFAULT false,
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX devices_user_id_idx ON devices(user_id);
