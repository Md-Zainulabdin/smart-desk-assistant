from fastapi import Response

from app.config import settings
from app.core.security import (
    clear_session_cookie,
    hash_token,
    new_session_token,
    set_session_cookie,
)


def test_tokens_are_random_and_hash_is_stable():
    first, second = new_session_token(), new_session_token()
    assert first != second
    assert hash_token(first) == hash_token(first)
    assert hash_token(first) != hash_token(second)
    assert first.encode() not in hash_token(first)


def test_session_cookie_is_http_only_and_lax():
    response = Response()
    set_session_cookie(response, "raw-token")
    header = response.headers["set-cookie"].lower()
    assert f"{settings.session_cookie_name}=raw-token" in header
    assert "httponly" in header
    assert "samesite=lax" in header


def test_clear_session_cookie_expires_it():
    response = Response()
    clear_session_cookie(response)
    assert "max-age=0" in response.headers["set-cookie"].lower()
