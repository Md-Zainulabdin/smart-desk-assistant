-- add google refresh token
-- depends: 20261116_01_nT4qK-create-notes

-- Google refresh token from sign-in, used to book Calendar events.
-- Fernet-encrypted with TOKEN_ENCRYPTION_KEY, which is never stored in the database.
-- NULL means Calendar access was not granted.
ALTER TABLE users ADD COLUMN google_refresh_token_encrypted TEXT;
