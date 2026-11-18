import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db import pool, run_migrations
from app.integrations.google_calendar import start_reminder_loop
from app.modules.auth.router import router as auth_router
from app.modules.calendar.router import router as calendar_router
from app.modules.command.router import router as command_router
from app.routers.health import router as health_router


def start_reminder_thread() -> None:
    """Desk reminders run in a background thread so FastAPI doesn't freeze."""
    if not (settings.mqtt_host and settings.esp_device_id):
        logging.getLogger(__name__).warning(
            "Desk reminders are off: set MQTT_HOST and ESP_DEVICE_ID in .env"
        )
        return
    threading.Thread(
        target=start_reminder_loop,
        args=(settings.esp_device_id,),
        name="calendar-reminders",
        daemon=True,
    ).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    pool.open()
    start_reminder_thread()  # once per server, after migrations
    yield
    pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Smart Desk Assistant API", lifespan=lifespan)
    register_exception_handlers(app)

    # Short-lived cookie for the OAuth handshake only (state + nonce), not the app session.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="sd_oauth",
        same_site="lax",
        https_only=settings.cookie_secure,
        max_age=600,
    )
    # Added last so CORS is the outermost layer.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.pwa_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(auth_router)
    app.include_router(calendar_router)
    return app


app = create_app()
