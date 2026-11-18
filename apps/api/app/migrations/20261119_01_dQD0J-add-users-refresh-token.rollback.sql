-- add users refresh token (rollback)

ALTER TABLE users DROP COLUMN refresh_token;
