from datetime import datetime, timedelta
from json import loads
from zoneinfo import ZoneInfo

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.command import service as command_service
from app.modules.web_search import services as web_search

app = create_app()
app.dependency_overrides[get_current_user] = lambda: {"id": "test-user"}
client = TestClient(app)


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "test-key")


def test_search_requires_sign_in():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    response = TestClient(app).post("/api/v1/search", json={"query": "hello"})

    assert response.status_code == 401


def test_search_success_returns_standard_envelope(monkeypatch):
    monkeypatch.setattr(
        web_search,
        "_fetch_results",
        lambda query, max_results, api_key: [
            {"title": "Example article", "url": "https://example.com/a", "snippet": "Short"}
        ],
    )

    res = client.post(
        "/api/v1/search", json={"query": "latest AI developments", "max_results": 3}
    )

    assert res.status_code == 200
    assert res.json() == {
        "success": True,
        "data": {
            "query": "latest AI developments",
            "results": [
                {"title": "Example article", "url": "https://example.com/a", "snippet": "Short"}
            ],
        },
        "error": None,
    }


def test_search_zero_results_is_success(monkeypatch):
    monkeypatch.setattr(web_search, "_fetch_results", lambda *args, **kwargs: [])

    res = client.post("/api/v1/search", json={"query": "nothing matches"})

    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["results"] == []
    assert body["error"] is None


def test_search_forwards_query_and_limit(monkeypatch):
    captured = {}

    def fake_fetch(query, max_results, api_key):
        captured["query"] = query
        captured["max_results"] = max_results
        return []

    monkeypatch.setattr(web_search, "_fetch_results", fake_fetch)

    client.post("/api/v1/search", json={"query": "  spaced  ", "max_results": 7})

    assert captured == {"query": "spaced", "max_results": 7}


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "ok", "max_results": 0},
        {"query": "ok", "max_results": 11},
        {"query": "ok", "max_results": "abc"},
        {"query": 123},
        {"max_results": 5},
        {"query": "weather", "text": "look up the weather"},
        {"query": "weather", "date_from": "yesterday"},
        {"query": "weather", "date_from": "2026-10-20", "date_to": "2026-10-19"},
        {"text": "look up the weather", "date_from": "2026-10-19"},
    ],
)
def test_invalid_requests_return_422_envelope(payload):
    res = client.post("/api/v1/search", json=payload)

    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "validation_error"


def test_invalid_request_does_not_call_provider(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("provider must not be called for invalid input")

    monkeypatch.setattr(web_search, "_fetch_results", fail)

    res = client.post("/api/v1/search", json={"query": ""})

    assert res.status_code == 422


def test_missing_api_key_returns_config_error(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "")

    res = client.post("/api/v1/search", json={"query": "hello"})

    assert res.status_code == 500
    body = res.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_API_KEY"


def test_provider_failure_returns_502(monkeypatch):
    def fail(*args, **kwargs):
        raise web_search.SearchProviderError("provider exploded")

    monkeypatch.setattr(web_search, "_fetch_results", fail)

    res = client.post("/api/v1/search", json={"query": "hello"})

    assert res.status_code == 502
    body = res.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "SEARCH_FAILED"
    assert body["error"]["message"] == "Web search could not be completed."


def test_error_response_does_not_leak_secret(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "super-secret-key")

    def fail(*args, **kwargs):
        raise web_search.SearchProviderError("super-secret-key leaked")

    monkeypatch.setattr(web_search, "_fetch_results", fail)

    res = client.post("/api/v1/search", json={"query": "hello"})

    assert "super-secret-key" not in res.text



def test_search_command_sends_extracted_query_and_dates_to_tavily(monkeypatch):
    send = httpx.Client.send

    def fake_send(self, request, **kwargs):
        if str(request.url) != web_search.TAVILY_SEARCH_URL:
            return send(self, request, **kwargs)
        yesterday = (datetime.now(ZoneInfo("Asia/Karachi")).date() - timedelta(days=1)).isoformat()
        assert loads(request.content) == {
            "query": "AI news",
            "max_results": 3,
            "search_depth": "basic",
            "start_date": yesterday,
            "end_date": yesterday,
            "filter_by_published_date": True,
        }
        return httpx.Response(200, request=request, json={"results": []})

    monkeypatch.setattr(httpx.Client, "send", fake_send)
    response = client.post(
        "/api/v1/search",
        json={
            "text": "Search for AI news from yesterday",
            "timezone": "Asia/Karachi",
            "max_results": 3,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"query": "AI news", "results": []}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Remind me to look up the weather at 3 pm", "SEARCH_INTENT_REQUIRED"),
        ("Search for", "SEARCH_NEEDS_CLARIFICATION"),
        ("Search for AI news and write a note", "SEARCH_NEEDS_CLARIFICATION"),
    ],
)
def test_unready_search_commands_skip_tavily(monkeypatch, text, code):
    def fail(*args, **kwargs):
        pytest.fail("Tavily must only run for a ready web search")

    monkeypatch.setattr(web_search, "_fetch_results", fail)
    response = client.post("/api/v1/search", json={"text": text})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_search_command_uses_follow_up_context(monkeypatch):
    monkeypatch.setattr(web_search, "_fetch_results", lambda *args, **kwargs: [])
    pending = client.post("/api/v1/command", json={"text": "Search for"}).json()
    assert pending["status"] == "needs_clarification"
    context = {key: pending[key] for key in ("intent", "slots", "missing")}

    response = client.post("/api/v1/search", json={"text": "Python tutorials", "context": context})

    assert response.status_code == 200
    assert response.json()["data"]["query"] == "Python tutorials"



@pytest.mark.parametrize(
    ("text", "expected_query", "has_date_range"),
    [
        ("what ai news came out yesterday", "ai news", True),
        ("what ai news came out yesterday?", "ai news", True),
        ("What AI news came out yesterday?", "AI news", True),
        ("search for ai news from yesterday", "ai news", True),
        ("look up the latest ai news", "ai news", False),
        ("search for ai news", "ai news", False),
        ("look up the weather", "weather", False),
        ("latest tech headlines", "tech headlines", False),
        ("Give me a brief overview of AI papers released yesterday.", "AI papers", True),
    ],
)
def test_search_runs_for_upstream_parser_examples(monkeypatch, text, expected_query, has_date_range):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 20, 9, tzinfo=tz)

    calls = []

    def fake_fetch(query, max_results, api_key, **date_filters):
        calls.append((query, date_filters))
        return []

    monkeypatch.setattr(command_service, "datetime", FixedDatetime)
    monkeypatch.setattr(web_search, "_fetch_results", fake_fetch)
    parsed = client.post("/api/v1/command", json={"text": text, "timezone": "Asia/Karachi"})
    assert parsed.status_code == 200
    command = parsed.json()
    assert (command["intent"], command["status"]) == ("WEB_SEARCH", "ready")
    slots = command["slots"]
    payload = {key: slots[key] for key in ("query", "date_from", "date_to") if key in slots}
    response = client.post("/api/v1/search", json=payload)

    assert response.status_code == 200
    assert response.json()["data"]["query"] == expected_query
    expected_filters = {"start_date": "2026-10-19", "end_date": "2026-10-19"} if has_date_range else {}
    assert calls == [(expected_query, expected_filters)]


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("what meetings do i have tomorrow", "SEARCH_INTENT_REQUIRED"),
        ("show my upcoming events", "SEARCH_INTENT_REQUIRED"),
        ("Write a note: buy a new microphone for the project.", "SEARCH_INTENT_REQUIRED"),
        ("remind me to call mom tomorrow", "SEARCH_NEEDS_CLARIFICATION"),
        ("schedule a meeting tomorrow", "SEARCH_NEEDS_CLARIFICATION"),
        ("Create a note and schedule a meeting tomorrow at 3 PM.", "SEARCH_NEEDS_CLARIFICATION"),
        ("Add bread, eggs, and milk to my shopping checklist.", "SEARCH_INTENT_REQUIRED"),
        ("Snooze it for ten minutes.", "SEARCH_INTENT_REQUIRED"),
    ],
)
def test_upstream_non_search_commands_skip_tavily(monkeypatch, text, code):
    def fail(*args, **kwargs):
        pytest.fail("Provider called for an unrelated or incomplete command")

    monkeypatch.setattr(web_search, "_fetch_results", fail)
    response = client.post("/api/v1/search", json={"text": text})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
