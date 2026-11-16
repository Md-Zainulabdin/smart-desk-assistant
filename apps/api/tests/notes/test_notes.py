from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.notes import repository
from app.modules.notes.schemas import Note


@pytest.fixture
def notes_api(monkeypatch):
    app = create_app()
    conn = Mock()
    user = {"id": uuid4(), "email": "notes@example.com", "name": None, "picture_url": None}
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user
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

    # A client-supplied user_id must be ignored; the owner comes from the session.
    created = client.post("/api/v1/notes", json={"content": " Buy milk ", "user_id": str(uuid4())})
    assert created.status_code == 201
    assert created.json()["id"] == str(note.id)
    assert client.get("/api/v1/notes").json()[0]["id"] == str(note.id)
    url = f"/api/v1/notes/{note.id}"
    assert client.get(url).json()["content"] == "Buy milk"
    assert client.patch(url, json={"content": "Buy oat milk"}).json()["content"] == "Buy oat milk"
    assert client.delete(url).status_code == 204

    methods["create_note"].assert_called_once_with(conn, user["id"], "Buy milk")
    methods["list_notes"].assert_called_once_with(conn, user["id"])
    methods["get_note"].assert_called_once_with(conn, user["id"], note.id)
    methods["update_note"].assert_called_once_with(conn, user["id"], note.id, "Buy oat milk")
    methods["delete_note"].assert_called_once_with(conn, user["id"], note.id)


def test_missing_note_returns_404(notes_api):
    client, _, _, _, methods = notes_api
    methods["get_note"].return_value = None
    methods["update_note"].return_value = None
    methods["delete_note"].return_value = False
    url = f"/api/v1/notes/{uuid4()}"

    assert client.get(url).status_code == 404
    assert client.patch(url, json={"content": "x"}).status_code == 404
    assert client.delete(url).status_code == 404


@pytest.mark.parametrize("content", ["", "   ", "bad\x00byte"])
def test_invalid_note_content_is_rejected(notes_api, content):
    client, _, _, _, methods = notes_api

    assert client.post("/api/v1/notes", json={"content": content}).status_code == 422
    methods["create_note"].assert_not_called()


def test_notes_require_sign_in(notes_api):
    client, app, _, _, methods = notes_api
    del app.dependency_overrides[get_current_user]

    assert client.get("/api/v1/notes").status_code == 401
    assert client.post("/api/v1/notes", json={"content": "Buy milk"}).status_code == 401
    methods["list_notes"].assert_not_called()
    methods["create_note"].assert_not_called()
