-- create pending commands
-- depends: 20261116_02_Gc7Wp-add-google-refresh-token

-- The one command per user that is waiting for a clarification reply.
-- The orchestrator sends it back to the parser as `context` with the next sentence.
CREATE TABLE pending_commands (
    user_id     UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    intent      TEXT NOT NULL,
    slots       JSONB NOT NULL,
    missing     JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
