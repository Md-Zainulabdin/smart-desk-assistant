from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from app.modules.notes import repository
from app.modules.notes.schemas import Note
from app.users.controller import current_user
from app.users.model import User


@pytest.fixture
def notes_api(monkeypatch):
    app = create_app()
    conn = Mock()
    user = User(id=uuid4(), email="notes@example.com", name=None, picture_url=None)
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[current_user] = lambda: user
    methods = {}
    for name in ("create_note", "list_notes", "get_note", "update_note", "delete_note"):
        method = Mock()
        monkeypatch.setattr(repository, name, method)
        methods[name] = method
    return TestClient(app), app, conn, user, methods


def test_notes_crud_uses_the_signed_in_owner(notes_api):
    client, _, conn, user, methods = notes_api
    note = Note(id=uuid4(), content="Buy milk", created_at=datetime.now(UTC))
    methods["create_note"].return_value = note
    methods["list_notes"].return_value = [note]
    methods["get_note"].return_value = note
    methods["update_note"].return_value = note.model_copy(update={"content": "Buy oat milk"})
    methods["delete_note"].return_value = True

    created = client.post("/api/v1/notes", json={"content": " Buy milk ", "user_id": str(uuid4())})
    assert created.status_code == 201
    assert created.json()["id"] == str(note.id)
    assert client.get("/api/v1/notes").json()[0]["id"] == str(note.id)
    url = f"/api/v1/notes/{note.id}"
    assert client.get(url).json()["content"] == "Buy milk"
    assert client.patch(url, json={"content": "Buy oat milk"}).json()["content"] == "Buy oat milk"
    assert client.delete(url).status_code == 204

    methods["create_note"].assert_called_once_with(conn, user.id, "Buy milk")
    methods["list_notes"].assert_called_once_with(conn, user.id)
    methods["get_note"].assert_called_once_with(conn, user.id, note.id)
    methods["update_note"].assert_called_once_with(conn, user.id, note.id, "Buy oat milk")
    methods["delete_note"].assert_called_once_with(conn, user.id, note.id)


def test_ready_note_command_saves_and_clarification_does_not(notes_api):
    client, _, conn, user, methods = notes_api
    note = Note(id=uuid4(), content="Buy milk", created_at=datetime.now(UTC))
    methods["create_note"].return_value = note

    response = client.post("/api/v1/command", json={"text": "Create a note."})
    assert response.status_code == 200
    pending = response.json()
    assert pending["status"] == "needs_clarification"
    methods["create_note"].assert_not_called()

    context = {key: pending[key] for key in ("intent", "slots", "missing")}
    response = client.post(
        "/api/v1/command",
        json={"text": "Buy milk", "context": context, "request_id": "note-123"},
    )
    assert response.status_code == 200
    assert response.json()["slots"]["note_id"] == str(note.id)
    methods["create_note"].assert_called_once_with(conn, user.id, "Buy milk", "note-123")


def test_notes_and_commands_require_sign_in(notes_api):
    client, app, _, _, methods = notes_api
    del app.dependency_overrides[current_user]

    assert client.get("/api/v1/notes").status_code == 401
    assert client.post("/api/v1/command", json={"text": "Note that we need milk"}).status_code == 401
    methods["list_notes"].assert_not_called()
    methods["create_note"].assert_not_called()


def test_explicit_note_command_saves_its_content(notes_api):
    client, _, conn, user, methods = notes_api
    note = Note(id=uuid4(), content="delete old files", created_at=datetime.now(UTC))
    methods["create_note"].return_value = note

    response = client.post("/api/v1/command", json={"text": "Take a note: delete old files"})
    assert response.json()["slots"]["note_id"] == str(note.id)
    methods["create_note"].assert_called_once_with(conn, user.id, "delete old files", None)


def test_list_and_edit_commands_do_not_create_notes(notes_api):
    client, _, _, _, methods = notes_api

    for text in ("Show my notes", "Edit my note"):
        response = client.post("/api/v1/command", json={"text": text})
        assert response.json()["status"] == "unsupported"
    methods["create_note"].assert_not_called()
