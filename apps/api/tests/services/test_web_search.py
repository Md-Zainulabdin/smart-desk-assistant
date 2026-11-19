import json

import httpx
import pytest

from app.config import settings
from app.modules.web_search import services as web_search

SEARCH_URL = web_search.TAVILY_SEARCH_URL


def _response(payload, status_code=200):
    return httpx.Response(status_code, json=payload, request=httpx.Request("POST", SEARCH_URL))


def _patch_post(monkeypatch, result):
    calls = []

    def fake_post(self, url, **kwargs):
        calls.append({"url": url, "kwargs": kwargs})
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return calls


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")


def test_returns_normalized_results(monkeypatch):
    payload = {
        "results": [
            {
                "title": "Example article",
                "url": "https://example.com/a",
                "content": "A short description",
            },
            {"title": "Second", "url": "https://example.com/b", "content": "Another"},
        ]
    }
    calls = _patch_post(monkeypatch, _response(payload))

    result = web_search.search_web("latest AI developments")

    assert result == {
        "success": True,
        "data": {
            "query": "latest AI developments",
            "results": [
                {
                    "title": "Example article",
                    "url": "https://example.com/a",
                    "snippet": "A short description",
                },
                {"title": "Second", "url": "https://example.com/b", "snippet": "Another"},
            ],
        },
        "error": None,
    }
    assert len(calls) == 1
    assert calls[0]["url"] == SEARCH_URL
    assert calls[0]["kwargs"]["json"] == {
        "query": "latest AI developments",
        "max_results": web_search.DEFAULT_MAX_RESULTS,
        "search_depth": "basic",
    }


def test_trims_query_and_forwards_limit(monkeypatch):
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web("  spaced query  ", max_results=3)

    assert result["data"]["query"] == "spaced query"
    assert calls[0]["kwargs"]["json"]["max_results"] == 3


def test_zero_results_is_success(monkeypatch):
    _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web("nothing matches")

    assert result["success"] is True
    assert result["data"]["results"] == []
    assert result["error"] is None


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_empty_query_rejected_without_network(monkeypatch, query):
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web(query)

    assert result["success"] is False
    assert result["data"] is None
    assert result["error"]["code"] == "INVALID_QUERY"
    assert calls == []


@pytest.mark.parametrize("query", [None, 123, ["a"], {"q": "x"}])
def test_non_string_query_rejected_without_network(monkeypatch, query):
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web(query)

    assert result["error"]["code"] == "INVALID_QUERY"
    assert calls == []


@pytest.mark.parametrize("limit", [0, -1, 11, 100])
def test_max_results_out_of_range(monkeypatch, limit):
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web("query", max_results=limit)

    assert result["error"]["code"] == "INVALID_MAX_RESULTS"
    assert calls == []


@pytest.mark.parametrize("limit", ["5", 2.5, True, None])
def test_max_results_wrong_type(monkeypatch, limit):
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web("query", max_results=limit)

    assert result["error"]["code"] == "INVALID_MAX_RESULTS"
    assert calls == []


def test_missing_api_key_returns_config_error(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")
    calls = _patch_post(monkeypatch, _response({"results": []}))

    result = web_search.search_web("query")

    assert result["success"] is False
    assert result["error"]["code"] == "MISSING_API_KEY"
    assert calls == []


def test_provider_network_failure_retries_then_fails(monkeypatch):
    calls = _patch_post(monkeypatch, httpx.ConnectError("connection refused"))

    result = web_search.search_web("query")

    assert result["success"] is False
    assert result["error"]["code"] == "SEARCH_FAILED"
    assert len(calls) == web_search.MAX_ATTEMPTS


def test_provider_status_error_is_not_retried(monkeypatch):
    calls = _patch_post(monkeypatch, _response({"detail": "boom"}, status_code=500))

    result = web_search.search_web("query")

    assert result["error"]["code"] == "SEARCH_FAILED"
    assert len(calls) == 1


def test_malformed_json_is_provider_failure(monkeypatch):
    bad = httpx.Response(
        200, content=b"<html>oops</html>", request=httpx.Request("POST", SEARCH_URL)
    )
    _patch_post(monkeypatch, bad)

    result = web_search.search_web("query")

    assert result["error"]["code"] == "SEARCH_FAILED"


@pytest.mark.parametrize("payload", [["unexpected"], {"answer": "no results key"}, "text"])
def test_malformed_payload_shape_is_provider_failure(monkeypatch, payload):
    _patch_post(monkeypatch, _response(payload))

    result = web_search.search_web("query")

    assert result["error"]["code"] == "SEARCH_FAILED"


def test_missing_optional_fields_default_to_empty(monkeypatch):
    _patch_post(monkeypatch, _response({"results": [{"url": "https://example.com"}]}))

    result = web_search.search_web("query")

    assert result["data"]["results"] == [
        {"title": "", "url": "https://example.com", "snippet": ""}
    ]


def test_non_string_fields_default_to_empty(monkeypatch):
    _patch_post(
        monkeypatch,
        _response({"results": [{"title": 5, "url": None, "content": {"a": 1}}]}),
    )

    result = web_search.search_web("query")

    assert result["data"]["results"] == [{"title": "", "url": "", "snippet": ""}]


def test_error_response_shape(monkeypatch):
    result = web_search.search_web("")

    assert set(result) == {"success", "data", "error"}
    assert result["success"] is False
    assert result["data"] is None
    assert set(result["error"]) == {"code", "message"}
    assert isinstance(result["error"]["message"], str)


def test_failure_does_not_leak_secret_or_exception(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "super-secret-key")
    _patch_post(monkeypatch, httpx.ConnectError("connection refused"))

    result = web_search.search_web("query")
    serialized = json.dumps(result)

    assert "super-secret-key" not in serialized
    assert "connection refused" not in serialized
