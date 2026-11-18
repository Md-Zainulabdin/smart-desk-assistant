-- add users refresh token
-- depends: 20261114_02_cD172-create-sessions

ALTER TABLE users ADD COLUMN refresh_token TEXT;
