from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def post_logout(origin: str | None):
    headers = {"Origin": origin} if origin else {}
    with patch("app.modules.auth.router._sign_out") as sign_out:
        response = TestClient(create_app()).post("/auth/logout", headers=headers)
    return response, sign_out


def test_logout_from_the_pwa_works():
    response, sign_out = post_logout(settings.pwa_origin)
    assert response.status_code == 204
    sign_out.assert_called_once()


def test_logout_from_the_api_own_page_works():
    response, _ = post_logout(settings.api_base_url)
    assert response.status_code == 204


def test_logout_from_another_site_is_rejected():
    response, sign_out = post_logout("https://evil.example")
    assert response.status_code == 403
    sign_out.assert_not_called()
