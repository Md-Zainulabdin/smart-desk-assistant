from fastapi import FastAPI

from app.core.exceptions import register_exception_handlers
from app.modules.command.router import router as command_router
from app.modules.web_search.routes import router as web_search_router
from app.routers.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="desk-api")
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(command_router)
    app.include_router(web_search_router)
    return app


app = create_app()
