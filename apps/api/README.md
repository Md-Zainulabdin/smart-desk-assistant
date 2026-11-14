# desk-api

FastAPI backend for Smart Desk Assistant.

## Setup

```powershell
Set-Location apps/api
uv sync
Copy-Item .env.example .env
```

## Database migrations

Database access is raw SQL through `asyncpg` (no ORM). Schema changes are plain SQL files in
`migrations/`, named `NNN_description.sql`. On startup the app applies any file not yet listed
in the `schema_migrations` table, in filename order, each in its own transaction.

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
