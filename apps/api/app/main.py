from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.db import pool, run_migrations
from app.modules.auth.router import router as auth_router
from app.modules.calendar.router import router as calendar_router
from app.modules.command.router import router as command_router
from app.modules.notes.router import router as notes_router
from app.modules.orchestrator.router import router as orchestrator_router
from app.routers.health import router as health_router

PLAYGROUND_DIR = Path(__file__).resolve().parent.parent / "playground"


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    pool.open()
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
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(auth_router)
    app.include_router(notes_router)
    app.include_router(calendar_router)
    app.include_router(orchestrator_router)

    # Dev-only test page at "/". Mounted last so every API route above wins.
    if settings.env == "dev":
        app.mount("/", StaticFiles(directory=PLAYGROUND_DIR, html=True), name="playground")
    return app


app = create_app()
