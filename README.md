# Smart Desk Assistant

A context-aware IoT desk companion: an ESP32-S3 device, a Next.js PWA, a FastAPI
backend, and PostgreSQL. See [CONTEXT.md](CONTEXT.md) for the project scope and
working rules.

## Repository layout

```
app/                FastAPI backend (Python package)
  main.py           app entry point
  config.py         settings loaded from .env
  db.py             database pool + migration runner
  auth/             authentication module
  migrations/       SQL migration files (applied automatically on startup)
app/mobile/         Next.js PWA (not scaffolded yet)
packages/           shared TypeScript packages
firmware/esp32/     ESP32-S3 firmware
docs/               design docs and workflows
docker-compose.yml  local PostgreSQL
pyproject.toml      Python dependencies (managed with uv)
```

## Prerequisites

Install these once:

| Tool | Why | Install |
|---|---|---|
| Git | clone the repo | https://git-scm.com/downloads |
| uv | Python and dependency manager | see below |
| Docker Desktop | local PostgreSQL | https://www.docker.com/products/docker-desktop |
| Node.js 20+ | PWA (later) | https://nodejs.org |

You do **not** need to install Python yourself. uv downloads the version in
`.python-version` automatically.

Install uv:

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal afterwards, then check with `uv --version`.

## Setup

All commands run from the repository root.

### 1. Clone

```bash
git clone https://github.com/Md-Zainulabdin/smart-desk-assistant.git
cd smart-desk-assistant
```

### 2. Install Python dependencies

```bash
uv sync
```

This creates `.venv/` and installs the exact versions pinned in `uv.lock`.

### 3. Start the database

Make sure Docker Desktop is running, then:

```bash
docker compose up -d
```

This starts PostgreSQL 17 on `localhost:5432` (user `smartdesk`, password
`smartdesk_dev`, database `smartdesk`). Data persists in a Docker volume across
restarts.

### 4 Run the API

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## Everyday commands

| Task | Command |
|---|---|
| Run the API | `uv run uvicorn app.main:app --reload --port 8000` |
| Add a Python package | `uv add <package>` |
| Remove a Python package | `uv remove <package>` |
| Sync after pulling changes | `uv sync` |
| Start / stop the database | `docker compose up -d` / `docker compose down` |
| Open a SQL shell | `docker exec -it smart-desk-db psql -U smartdesk -d smartdesk` |

After `git pull`, run `uv sync` if `pyproject.toml` or `uv.lock` changed.
Commit both files whenever you add or remove a package.

## Database migrations

Migrations are plain SQL files in `app/migrations/`, applied in filename order
by [yoyo-migrations](https://ollycope.com/software/yoyo/latest/) every time the
server starts. Each file runs once; applied files are tracked in the database.

To add one, create `app/migrations/<timestamp>_<name>.sql`, where the timestamp
is the current time in milliseconds, for example
`1791900000000_create-users.sql`:

```sql
-- Up Migration
CREATE TABLE IF NOT EXISTS users (
    ...
);
```

Get a timestamp with:

```bash
uv run python -c "import time; print(int(time.time() * 1000))"
```

Rules:

- Never edit a migration after it has been pushed. Add a new file instead.
- Keep the SQL plain PostgreSQL so it also runs on Neon in production.

## Troubleshooting

**`uv` is not recognized.** Reopen the terminal after installing uv. In VS Code,
restart VS Code, because its terminals keep the old PATH.

**`No module named 'app'`.** You are not in the repository root. `cd` there and
run the command again.

**`validation errors for Settings` / `Field required`.** `.env` is missing or a
value is empty. Check step 4.

**`connection refused` on port 5432.** Docker Desktop is not running, or the
database container is stopped. Run `docker compose up -d`.

**Port 5432 already in use.** Another PostgreSQL is installed locally. Stop it,
or change the left side of the port mapping in `docker-compose.yml` (for example
`"5433:5432"`) and the port in `DATABASE_URL`.

**`redirect_uri_mismatch` from Google.** The API must run on port 8000 to match
the redirect URIs registered in Google Cloud Console.

**Activating the virtual environment manually** (optional; `uv run` does it for you):

- PowerShell: `.venv\Scripts\Activate.ps1`
- Git Bash: `source .venv/Scripts/activate`
- macOS / Linux: `source .venv/bin/activate`
