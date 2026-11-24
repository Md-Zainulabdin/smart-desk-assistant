from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.device import repository
from app.modules.device.schemas import Device


@pytest.fixture
def devices_api(monkeypatch):
    app = create_app()
    conn = Mock()
    user = {"id": uuid4(), "email": "owner@example.com", "name": None, "picture_url": None}
    app.dependency_overrides[get_db] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: user
    methods = {}
    for name in ("claim_device", "list_devices", "unlink_device"):
        method = Mock()
        monkeypatch.setattr(repository, name, method)
        methods[name] = method
    return TestClient(app), app, conn, user, methods


def device(user_id, device_id="cee330"):
    return Device(
        device_id=device_id,
        user_id=user_id,
        name="Desk",
        online=False,
        last_seen_at=None,
        created_at=datetime.now(UTC),
    )


def test_claim_links_the_device_to_the_signed_in_user(devices_api):
    client, _, conn, user, methods = devices_api
    methods["claim_device"].return_value = device(user["id"])

    response = client.post("/api/v1/devices", json={"device_id": " CEE330 ", "name": "Desk"})

    assert response.status_code == 201
    assert response.json() == {
        "device_id": "cee330",
        "name": "Desk",
        "online": False,
        "last_seen_at": None,
    }
    methods["claim_device"].assert_called_once_with(conn, user["id"], "cee330", "Desk")


def test_claiming_another_users_device_is_a_conflict(devices_api):
    client, _, _, _, methods = devices_api
    methods["claim_device"].return_value = None

    response = client.post("/api/v1/devices", json={"device_id": "cee330"})

    assert response.status_code == 409


@pytest.mark.parametrize("device_id", ["cee33", "cee3300", "zzzzzz", ""])
def test_device_id_must_be_six_hex_characters(devices_api, device_id):
    client, _, _, _, methods = devices_api

    response = client.post("/api/v1/devices", json={"device_id": device_id})

    assert response.status_code == 422
    methods["claim_device"].assert_not_called()


def test_list_and_unlink_are_scoped_to_the_user(devices_api):
    client, _, conn, user, methods = devices_api
    methods["list_devices"].return_value = [device(user["id"])]
    methods["unlink_device"].side_effect = [True, False]

    assert [d["device_id"] for d in client.get("/api/v1/devices").json()] == ["cee330"]
    assert client.delete("/api/v1/devices/cee330").status_code == 204
    assert client.delete("/api/v1/devices/cee330").status_code == 404
    methods["unlink_device"].assert_called_with(conn, user["id"], "cee330")


def test_devices_require_sign_in(devices_api):
    _, app, _, _, _ = devices_api
    del app.dependency_overrides[get_current_user]
    client = TestClient(app)

    assert client.get("/api/v1/devices").status_code == 401
    assert client.post("/api/v1/devices", json={"device_id": "cee330"}).status_code == 401
