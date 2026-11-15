ALTER TABLE auth
    ADD COLUMN command_request_id TEXT,
    ADD CONSTRAINT auth_user_command_request_id_key UNIQUE (user_id, command_request_id);
