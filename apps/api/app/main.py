from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.database.connection import close_pool, open_pool, run_migrations
from app.modules.auth.router import router as auth_router
from app.modules.calendar.router import router as calendar_router
from app.modules.health.router import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_migrations()
    await open_pool()
    yield
    await close_pool()


def create_app() -> FastAPI:
    setup_logging()
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
    app.include_router(auth_router)
    app.include_router(calendar_router)
    return app


app = create_app()
