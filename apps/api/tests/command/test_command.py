from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def post_command(text: str, **extra):
    return client.post("/api/v1/command", json={"text": text, **extra})


def test_reminder_command():
    res = post_command("remind me to call mom tomorrow")
    assert res.status_code == 200
    body = res.json()
    assert body["text"] == "remind me to call mom tomorrow"
    assert body["intent"] == "CREATE_REMINDER"
    assert body["slots"]["when"] == "tomorrow"


def test_checklist_command():
    res = post_command("add milk to shopping list")
    assert res.status_code == 200
    assert res.json() == {
        "text": "add milk to shopping list",
        "intent": "CREATE_CHECKLIST",
        "slots": {
            "text": "add milk to shopping list",
            "item": "milk",
            "list": "shopping",
        },
    }


def test_unknown_command():
    res = post_command("hello there")
    assert res.status_code == 200
    assert res.json()["intent"] == "UNKNOWN"


def test_request_id_is_accepted():
    res = post_command("note that the plants need water", request_id="req-1")
    assert res.status_code == 200
    assert res.json()["intent"] == "CREATE_NOTE"


def test_whitespace_is_trimmed():
    res = post_command("  note that the plants need water  ")
    assert res.status_code == 200
    assert res.json()["text"] == "note that the plants need water"


def test_whitespace_only_is_rejected():
    res = post_command("   ")
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_command"


def test_empty_text_is_rejected():
    res = post_command("")
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_missing_text_is_rejected():
    res = client.post("/api/v1/command", json={"request_id": "abc"})
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"


def test_oversize_text_is_rejected():
    res = post_command("a" * 2001)
    assert res.status_code == 422
    assert res.json()["code"] == "validation_error"
