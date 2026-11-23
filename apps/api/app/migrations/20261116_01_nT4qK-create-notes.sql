-- create notes
-- depends: 20261114_02_cD172-create-sessions

CREATE TABLE notes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    -- Idempotency key: a retried voice command must not create a second note.
    command_request_id  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT notes_user_command_request_id_key UNIQUE (user_id, command_request_id)
);

CREATE INDEX notes_user_id_created_at_idx ON notes(user_id, created_at DESC);
