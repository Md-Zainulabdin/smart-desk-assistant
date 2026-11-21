from typing import Any


class ErrorCode:
    INVALID_QUERY = "INVALID_QUERY"
    INVALID_MAX_RESULTS = "INVALID_MAX_RESULTS"
    MISSING_API_KEY = "MISSING_API_KEY"
    SEARCH_FAILED = "SEARCH_FAILED"
    SEARCH_INTENT_REQUIRED = "SEARCH_INTENT_REQUIRED"
    SEARCH_NEEDS_CLARIFICATION = "SEARCH_NEEDS_CLARIFICATION"


def success_response(data: dict[str, Any]) -> dict[str, Any]:
    """Build a standardized success response."""
    return {"success": True, "data": data, "error": None}


def error_response(code: str, message: str) -> dict[str, Any]:
    """Build a standardized error response with a stable machine-readable code."""
    return {"success": False, "data": None, "error": {"code": code, "message": message}}
