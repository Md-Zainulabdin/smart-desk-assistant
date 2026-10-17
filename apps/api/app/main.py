from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db import pool, run_migrations
from app.routers.calendar import router as calendar_router
from app.routers.google_auth import router as google_auth_route
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    pool.open()
    yield
    pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="desk-api", lifespan=lifespan)
    register_exception_handlers(app)
    # Login cookie: holds only user_id (signed, not encrypted), never tokens.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SESSION_SECRET,
        session_cookie="sd_session",
        same_site="lax",
        https_only=False,
        max_age=30 * 24 * 3600,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.PWA_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(google_auth_route)
    app.include_router(calendar_router)
    return app


app = create_app()
