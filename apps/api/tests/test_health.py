from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health_ok():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_not_found_error_shape():
    res = client.get("/nope")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "http_error"
    assert "detail" in body
