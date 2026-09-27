from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.exceptions import ApiError
from app.main import create_app
from app.modules.voice.service import MAX_AUDIO_BYTES

client = TestClient(create_app())

AUDIO = ("cmd.webm", b"fake-audio-bytes", "audio/webm")


def fake_transcribe(text: str, language: str = "en"):
    def _fake(data: bytes, filename: str, lang: str | None = None):
        return {"text": text, "language": language}

    return _fake


def test_stt_reminder_happy_path():
    with patch(
        "app.modules.voice.service.speech_to_text.transcribe",
        side_effect=fake_transcribe("remind me to drink water"),
    ):
        res = client.post("/api/v1/stt", files={"file": AUDIO})

    assert res.status_code == 200
    body = res.json()
    assert body["transcript"] == "remind me to drink water"
    assert body["language"] == "en"
    assert body["intent"] == "CREATE_REMINDER"
    assert body["slots"]["text"] == "remind me to drink water"
    assert body["model"] == "whisper-large-v3-turbo"


def test_stt_checklist_happy_path():
    with patch(
        "app.modules.voice.service.speech_to_text.transcribe",
        side_effect=fake_transcribe("add milk to shopping list"),
    ):
        res = client.post("/api/v1/stt", files={"file": AUDIO})

    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "CREATE_CHECKLIST"
    assert body["slots"] == {
        "text": "add milk to shopping list",
        "item": "milk",
        "list": "shopping",
    }


def test_stt_empty_transcript():
    with patch(
        "app.modules.voice.service.speech_to_text.transcribe",
        side_effect=fake_transcribe("   "),
    ):
        res = client.post("/api/v1/stt", files={"file": AUDIO})

    assert res.status_code == 400
    assert res.json()["code"] == "invalid_audio"


def test_stt_invalid_mime():
    res = client.post(
        "/api/v1/stt", files={"file": ("cmd.txt", b"not audio", "text/plain")}
    )
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_audio"


def test_stt_empty_file():
    res = client.post("/api/v1/stt", files={"file": ("cmd.webm", b"", "audio/webm")})
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_audio"


def test_stt_too_large():
    big = b"x" * (MAX_AUDIO_BYTES + 1)
    res = client.post("/api/v1/stt", files={"file": ("cmd.webm", big, "audio/webm")})
    assert res.status_code == 413
    assert res.json()["code"] == "too_large"


def test_stt_upstream_failure():
    def _fail(data: bytes, filename: str, lang: str | None = None):
        raise ApiError("speech provider failed", "upstream_error", 502)

    with patch(
        "app.modules.voice.service.speech_to_text.transcribe", side_effect=_fail
    ):
        res = client.post("/api/v1/stt", files={"file": AUDIO})

    assert res.status_code == 502
    assert res.json()["code"] == "upstream_error"


def test_stt_not_configured():
    from app.integrations import speech_to_text

    with patch.object(
        speech_to_text,
        "get_settings",
        return_value=type("S", (), {"GROQ_API_KEY": ""})(),
    ):
        res = client.post("/api/v1/stt", files={"file": AUDIO})

    assert res.status_code == 500
    assert res.json()["code"] == "stt_not_configured"
