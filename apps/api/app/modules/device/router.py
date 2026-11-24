from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from psycopg import Connection

from app.db import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.device import repository, service
from app.modules.device.schemas import DEVICE_ID_PATTERN, Device, DeviceClaim, DeviceOut

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

SignedInUser = Annotated[dict, Depends(get_current_user)]
Database = Annotated[Connection, Depends(get_db)]
DeviceIdPath = Annotated[str, Path(pattern=DEVICE_ID_PATTERN)]


def _out(device: Device) -> DeviceOut:
    return DeviceOut.model_validate(device.model_dump())


@router.post("", status_code=status.HTTP_201_CREATED)
def claim_device(payload: DeviceClaim, user: SignedInUser, conn: Database) -> DeviceOut:
    """Link a Nova device (the 6-character id in its MQTT topics) to your account."""
    try:
        device = service.claim(conn, user["id"], payload.device_id, payload.name)
    except service.DeviceAlreadyClaimed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This device is already linked to another account."
        ) from None
    return _out(device)


@router.get("")
def list_devices(user: SignedInUser, conn: Database) -> list[DeviceOut]:
    return [_out(device) for device in repository.list_devices(conn, user["id"])]


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_device(device_id: DeviceIdPath, user: SignedInUser, conn: Database) -> None:
    if not repository.unlink_device(conn, user["id"], device_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
