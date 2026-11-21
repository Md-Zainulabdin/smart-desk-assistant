-- add google refresh token (rollback)

ALTER TABLE users DROP COLUMN google_refresh_token_encrypted;
