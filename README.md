# Smart Desk Assistant

A context-aware IoT desk companion: an ESP32-S3 device, a Next.js PWA, a FastAPI
backend, and PostgreSQL. See [CONTEXT.md](CONTEXT.md) for the project scope and
working rules.

## Repository layout

```
apps/api/           FastAPI backend (see AGENTS.md for the structure)
  app/main.py       app entry point
  app/config.py     settings loaded from apps/api/.env
  app/db.py         database pool + migration runner
  app/modules/      feature modules (auth, ...)
  app/migrations/   SQL migration files (applied automatically on startup)
  tests/            backend tests
  pyproject.toml    Python dependencies (managed with uv)
  .env.example      copy to .env and fill in
apps/mobile/        Next.js PWA (not scaffolded yet)
packages/           shared TypeScript packages
firmware/esp32/     ESP32-S3 firmware
docs/               design docs and workflows
docker-compose.yml  local PostgreSQL
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
`apps/api/.python-version` automatically.

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

Run the Docker command from the repository root and every `uv` command from `apps/api/`.

### 1. Clone

```bash
git clone https://github.com/Md-Zainulabdin/smart-desk-assistant.git
cd smart-desk-assistant
```

### 2. Install Python dependencies

```bash
cd apps/api
uv sync
cp .env.example .env    # then fill in the values
```

This creates `apps/api/.venv/` and installs the exact versions pinned in `uv.lock`.

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
| Run the API (from `apps/api`) | `uv run uvicorn app.main:app --reload --port 8000` |
| Add a Python package | `uv add <package>` |
| Remove a Python package | `uv remove <package>` |
| Sync after pulling changes | `uv sync` |
| Start / stop the database | `docker compose up -d` / `docker compose down` |
| Open a SQL shell | `docker exec -it smart-desk-db psql -U smartdesk -d smartdesk` |
| Create a migration | `uv run yoyo new --sql -m "<description>"` |

After `git pull`, run `uv sync` if `pyproject.toml` or `uv.lock` changed.
Commit both files whenever you add or remove a package.

## Database migrations

Migrations are plain SQL files in `apps/api/app/migrations/`, applied in filename order
by [yoyo-migrations](https://ollycope.com/software/yoyo/latest/) every time the
server starts. Each file runs once; applied files are tracked in the database.

To add one, let yoyo generate the file:

```bash
uv run yoyo new --sql -m "create users"
```

This creates a file such as `apps/api/app/migrations/20261014_01_tYC6D-create-users.sql`.
The name is made of the date, a sequence number, a random ID and your message.
The folder comes from `apps/api/yoyo.ini`. Open the file and write your SQL under the
header:

```sql
-- create users
-- depends: 20261013_01_AbCdE-previous-migration

CREATE TABLE IF NOT EXISTS users (
    ...
);
```

yoyo fills in the `-- depends:` line with the previous migration. Leave it in
place, because yoyo uses it to decide the order. Restart the API to apply the
new migration.

### Up and down

The `.sql` file is the **up** migration. For a **down** migration, add a file
with the same name ending in `.rollback.sql`, next to it:

```
apps/api/app/migrations/20261014_01_tC7nu-create-users.sql            # up
apps/api/app/migrations/20261014_01_tC7nu-create-users.rollback.sql   # down
```

To run migrations by hand, pass the database with `-d`. The API applies them on
startup anyway:

```bash
# PowerShell: $DB = "postgresql+psycopg://smartdesk:smartdesk_dev@localhost:5432/smartdesk"
DB=postgresql+psycopg://smartdesk:smartdesk_dev@localhost:5432/smartdesk

uv run yoyo list -d $DB              # show status: A = applied, U = unapplied
uv run yoyo apply -d $DB             # up: apply all pending migrations
uv run yoyo rollback -d $DB          # down: undo the most recent migration
uv run yoyo rollback --all -d $DB    # down: undo every migration
uv run yoyo reapply -d $DB           # down + up the most recent migration
```

The `postgresql+psycopg://` prefix tells yoyo to use psycopg 3. Use rollback
only on your local database. To undo something in production, add a new
migration.

Rules:

- Never edit a migration after it has been pushed. Add a new file instead.
- Keep the SQL plain PostgreSQL so it also runs on Neon in production.

## Troubleshooting

**`uv` is not recognized.** Reopen the terminal after installing uv. In VS Code,
restart VS Code, because its terminals keep the old PATH.

**`No module named 'app'`.** You are not in `apps/api/`. `cd` there and
run the command again.

**`validation errors for Settings` / `Field required`.** `apps/api/.env` is missing or a
value is empty. Check step 2.

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
