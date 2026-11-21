from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.response import error_response


class ApiError(Exception):
    def __init__(self, detail: str, code: str, status: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.code = code
        self.status = status


class ServiceError(Exception):
    """An expected service failure that maps to a standardized API error response."""

    def __init__(self, code: str, message: str, status: int = 500):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=error_response(exc.code, exc.message),
        )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={"detail": exc.detail, "code": exc.code},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": "http_error"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        message = _first_validation_message(exc)
        if request.url.path == app.url_path_for("parse_command"):
            return JSONResponse(
                status_code=422,
                content={"detail": message, "code": "validation_error"},
            )
        return JSONResponse(
            status_code=422,
            content=error_response("validation_error", message),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_response("internal_error", "internal error"),
        )


def _first_validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "invalid request"

    first = errors[0]
    field = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = str(first.get("msg", "invalid request"))
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")

    return f"{field}: {message}" if field else message
