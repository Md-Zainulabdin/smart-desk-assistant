from typing import Any

from fastapi import APIRouter

from app.core.exceptions import ServiceError
from app.modules.web_search.schemas import SearchRequest, SearchResponse
from app.modules.web_search.services import search_web, search_web_command
from app.services.response import ErrorCode

router = APIRouter(prefix="/api/v1", tags=["search"])

_ERROR_STATUS: dict[str, int] = {
    ErrorCode.INVALID_QUERY: 422,
    ErrorCode.INVALID_MAX_RESULTS: 422,
    ErrorCode.SEARCH_INTENT_REQUIRED: 422,
    ErrorCode.SEARCH_NEEDS_CLARIFICATION: 422,
    ErrorCode.MISSING_API_KEY: 500,
    ErrorCode.SEARCH_FAILED: 502,
}


@router.post("/search", response_model=SearchResponse)
def web_search(payload: SearchRequest) -> dict[str, Any]:
    """Run a web search and return the standardized response envelope."""
    if payload.text is not None:
        result = search_web_command(
            payload.text, payload.max_results, timezone=payload.timezone, context=payload.context
        )
    else:
        result = search_web(
            payload.query,
            payload.max_results,
            start_date=payload.date_from.isoformat() if payload.date_from else None,
            end_date=payload.date_to.isoformat() if payload.date_to else None,
        )
    if not result["success"]:
        error = result["error"]
        raise ServiceError(
            code=error["code"],
            message=error["message"],
            status=_ERROR_STATUS.get(error["code"], 500),
        )
    return result
