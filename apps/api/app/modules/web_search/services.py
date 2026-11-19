import logging
from typing import Any

import httpx

from app.config import get_settings
from app.modules.command.schemas import CommandContext, Intent, Status
from app.modules.command.service import parse_command
from app.services.response import ErrorCode, error_response, success_response

logger = logging.getLogger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
MIN_MAX_RESULTS = 1
MAX_MAX_RESULTS = 10
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 2


class SearchProviderError(Exception):
    """Raised when the search provider cannot return usable results."""


def search_web_command(
    text: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    timezone: str | None = None,
    context: CommandContext | None = None,
) -> dict[str, Any]:
    command = parse_command(text, timezone=timezone, context=context)
    if command.status is Status.NEEDS_CLARIFICATION:
        return error_response(
            ErrorCode.SEARCH_NEEDS_CLARIFICATION,
            command.clarification or "Please clarify what you want to search for.",
        )
    if command.intent is not Intent.WEB_SEARCH or command.status is not Status.READY:
        return error_response(ErrorCode.SEARCH_INTENT_REQUIRED, "Enter a web search command.")

    date_filters = {
        field: command.slots[slot]
        for field, slot in (("start_date", "date_from"), ("end_date", "date_to"))
        if slot in command.slots
    }
    return search_web(command.slots["query"], max_results, **date_filters)


def search_web(
    query: str | None,
    max_results: int = DEFAULT_MAX_RESULTS,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    validation_error = _validate_input(query, max_results)
    if validation_error is not None:
        return validation_error

    api_key = get_settings().tavily_api_key
    if not api_key:
        return error_response(ErrorCode.MISSING_API_KEY, "Web search is not configured.")

    cleaned_query = query.strip()
    date_filters = {
        field: value
        for field, value in (("start_date", start_date), ("end_date", end_date))
        if value is not None
    }
    try:
        results = _fetch_results(cleaned_query, max_results, api_key, **date_filters)
    except SearchProviderError:
        logger.warning("Web search provider call failed")
        return error_response(ErrorCode.SEARCH_FAILED, "Web search could not be completed.")

    return success_response({"query": cleaned_query, "results": results})


def _validate_input(query: Any, max_results: Any) -> dict[str, Any] | None:
    if not isinstance(query, str) or not query.strip():
        return error_response(ErrorCode.INVALID_QUERY, "A non-empty search query is required.")
    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return error_response(ErrorCode.INVALID_MAX_RESULTS, "max_results must be an integer.")
    if not MIN_MAX_RESULTS <= max_results <= MAX_MAX_RESULTS:
        return error_response(
            ErrorCode.INVALID_MAX_RESULTS,
            f"max_results must be between {MIN_MAX_RESULTS} and {MAX_MAX_RESULTS}.",
        )
    return None


def _fetch_results(
    query: str, max_results: int, api_key: str, **date_filters: str
) -> list[dict[str, str]]:
    payload = {"query": query, "max_results": max_results, "search_depth": "basic", **date_filters}
    headers = {"Authorization": f"Bearer {api_key}"}
    last_error: Exception | None = None

    for _ in range(MAX_ATTEMPTS):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(TAVILY_SEARCH_URL, json=payload, headers=headers)
            response.raise_for_status()
            return _normalize_results(response.json())
        except httpx.HTTPStatusError as exc:
            raise SearchProviderError(
                f"provider responded with status {exc.response.status_code}"
            ) from exc
        except httpx.TransportError as exc:
            last_error = exc
        except (ValueError, TypeError) as exc:
            raise SearchProviderError("provider returned malformed data") from exc

    raise SearchProviderError("provider is unreachable") from last_error


def _normalize_results(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        raise SearchProviderError("unexpected provider payload")
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise SearchProviderError("provider payload is missing the results list")
    return [
        {
            "title": _as_text(item.get("title")),
            "url": _as_text(item.get("url")),
            "snippet": _as_text(item.get("content")),
        }
        for item in raw_results
        if isinstance(item, dict)
    ]


def _as_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
