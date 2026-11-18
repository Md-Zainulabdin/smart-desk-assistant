-- Databases created by the early 001_users.sql have no refresh_token column.
ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token TEXT;
