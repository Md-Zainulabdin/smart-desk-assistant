-- create users
-- depends: 

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_sub      TEXT NOT NULL UNIQUE,
    email           TEXT NOT NULL,
    email_verified  BOOLEAN NOT NULL,
    name            TEXT,
    picture_url     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);
