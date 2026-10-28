import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_db
from app.main import create_app
from app.modules.auth.service import SignInRejected, sign_in_google_user


@pytest.fixture
def allow_only_owner(monkeypatch):
    monkeypatch.setattr(get_settings(), "ALLOWED_GOOGLE_EMAILS", "Owner@Example.com, other@x.io")


def google_token(email: str, verified: bool = True) -> dict:
    return {
        "userinfo": {"sub": "123", "email": email, "email_verified": verified},
        "refresh_token": "secret",
    }


def test_sign_in_rejects_email_not_on_allowlist(allow_only_owner):
    with pytest.raises(SignInRejected) as exc:
        asyncio.run(sign_in_google_user(db=None, token=google_token("stranger@example.com")))
    assert exc.value.reason == "not_allowed"


def test_sign_in_rejects_unverified_email(allow_only_owner):
    token = google_token("owner@example.com", verified=False)
    with pytest.raises(SignInRejected):
        asyncio.run(sign_in_google_user(db=None, token=token))


def test_sign_in_saves_allowed_user(allow_only_owner):
    saved = MagicMock()
    with patch("app.modules.auth.service.save_google_user", AsyncMock(return_value=saved)) as save:
        user = asyncio.run(sign_in_google_user(db="db", token=google_token("owner@example.com")))
    assert user is saved
    save.assert_called_once()
    assert save.call_args.args[2] == "secret"


def test_me_without_session_returns_401():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    res = TestClient(app).get("/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"] == "Not signed in"
