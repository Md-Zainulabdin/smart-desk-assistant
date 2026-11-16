from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.security import decrypt_token
from app.modules.auth import repository, service
from app.modules.auth.oauth import CALENDAR_EVENTS_SCOPE, SIGN_IN_SCOPES

USER_ID = uuid4()
CLAIMS = {"sub": "google-sub", "email": "owner@example.com", "email_verified": True}


@pytest.fixture
def repo(monkeypatch):
    mocks = {
        "upsert_google_user": Mock(return_value={"id": USER_ID}),
        "save_google_refresh_token": Mock(),
        "revoke_session": Mock(),
        "create_session": Mock(return_value="session-token"),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(repository, name, mock)
    return mocks


def test_sign_in_asks_for_calendar_consent():
    assert CALENDAR_EVENTS_SCOPE in SIGN_IN_SCOPES.split()


def test_granted_calendar_access_stores_encrypted_refresh_token(repo):
    token = {"scope": f"openid email {CALENDAR_EVENTS_SCOPE}", "refresh_token": "refresh-1"}

    assert service.sign_in_with_google(None, CLAIMS, None, google_token=token) == "session-token"

    _, user_id, stored = repo["save_google_refresh_token"].call_args.args
    assert user_id == USER_ID
    assert stored != "refresh-1"
    assert decrypt_token(stored) == "refresh-1"


@pytest.mark.parametrize(
    "token",
    [
        {"scope": "openid email profile", "refresh_token": "refresh-1"},  # Calendar unticked
        {"scope": f"openid {CALENDAR_EVENTS_SCOPE}"},  # no refresh token sent
        None,
    ],
)
def test_sign_in_works_without_calendar_and_keeps_any_stored_token(repo, token):
    assert service.sign_in_with_google(None, CLAIMS, None, google_token=token) == "session-token"
    repo["save_google_refresh_token"].assert_not_called()
