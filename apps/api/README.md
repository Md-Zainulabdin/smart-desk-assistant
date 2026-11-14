# desk-api

FastAPI backend for Smart Desk Assistant.

## Setup

```powershell
Set-Location apps/api
uv sync
Copy-Item .env.example .env
```

## Run

```powershell
Set-Location apps/api
uv run uvicorn app.main:app --reload
```

Health: `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`

## Web Search

The web search service (`app/modules/web_search/services.py`) queries Tavily.
It accepts a direct query or a natural-language command.

Configuration:

1. Create `.env` from `.env.example`.
2. Set your Tavily key:

   ```text
   TAVILY_API_KEY=your_tavily_api_key_here
   ```

Usage without STT or intent:

```python
from app.modules.web_search.services import search_web

response = search_web("latest AI developments", max_results=5)
# {
#   "success": True,
#   "data": {"query": "...", "results": [{"title": ..., "url": ..., "snippet": ...}]},
#   "error": None,
# }
```

Failures return `{"success": False, "data": None, "error": {"code": ..., "message": ...}}`.
A search with zero results is still a success.

## Web Search API

`POST /api/v1/search`

Request:

```json
{ "query": "latest AI developments", "max_results": 5 }
```

To search from a spoken or typed command, send `text` instead of `query`.

```json
{ "text": "Search for AI news from yesterday", "timezone": "Asia/Karachi" }
```

The command parser must return a ready `WEB_SEARCH` intent. Tavily receives the
extracted query and any publication date range. If the command is incomplete,
the endpoint returns `SEARCH_NEEDS_CLARIFICATION` with the parser's question.
Other intents return `SEARCH_INTENT_REQUIRED`. For a clarification flow, use
`POST /api/v1/command` to obtain the pending `intent`, `slots`, and `missing`
fields, then send them as `context` with the follow-up `text` to the search endpoint.

`max_results` is optional (default `5`) and must be between `1` and `10`.
Response:

```json
{
  "success": true,
  "data": { "query": "latest AI developments", "results": [] },
  "error": null
}
```

Status codes are `200` for success, `400` for an invalid command or timezone,
`422` for validation, clarification, or a different intent, `500` for missing
configuration, and `502` for a search provider failure.

## Test / Lint

```powershell
Set-Location apps/api
uv run pytest
uv run ruff check app tests
```

## Run a command through the parser and web search

With the API running and `TAVILY_API_KEY` set, paste this into a second PowerShell terminal.

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$command = @{ text = 'Give me a brief overview of AI papers released yesterday.'; timezone = 'Asia/Karachi' }
$parsed = Invoke-RestMethod -Method Post -Uri "$api/command" -ContentType 'application/json' -Body ($command | ConvertTo-Json)
if ($parsed.intent -eq 'WEB_SEARCH' -and $parsed.status -eq 'ready') {
    $search = @{ query = $parsed.slots.query }
    if ($parsed.slots.date_from) { $search.date_from = $parsed.slots.date_from }
    if ($parsed.slots.date_to) { $search.date_to = $parsed.slots.date_to }
    Invoke-RestMethod -Method Post -Uri "$api/search" -ContentType 'application/json' -Body ($search | ConvertTo-Json) |
        ConvertTo-Json -Depth 6
} else {
    $parsed | ConvertTo-Json -Depth 6
}
```

The parser extracts `AI papers` and resolves “yesterday” in the given timezone.
The search endpoint accepts `date_from` and `date_to` alongside the extracted query.
