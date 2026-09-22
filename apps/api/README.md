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

## Test / Lint

```powershell
Set-Location apps/api
uv run pytest
uv run ruff check app tests
```
