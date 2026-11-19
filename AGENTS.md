# AGENTS.md

Project-wide rules for **Smart Desk Assistant**, a production-quality, context-aware voice assistant. This file is the single source of truth for how the repo is organized and how code is written. It applies to the whole monorepo: read it before adding a feature, and change it only in its own pull request — never inside a feature branch.

## Project Overview

Smart Desk Assistant is a voice-activated IoT desk companion. It uses an ESP32-S3 device, a Next.js PWA, a FastAPI backend, and PostgreSQL.

It helps one primary user create notes, reminders, and Google Calendar events by voice, and it decides whether a reminder should be spoken, shown silently, delayed, or sent to the phone. Decisions use radar presence, Bluetooth phone proximity, calendar state, and user preferences.

Core system flow:

1. The ESP32 detects a wake word and records a voice command.
2. The device transcribes the audio to text on-device.
3. The device sends the text command to the FastAPI backend.
4. Intent parsing turns the text into a structured result: intent, details, and any missing information.
5. When information is missing, the backend asks a clarification question and keeps the pending command.
6. The user's follow-up reply is merged into the pending command to complete its details.
7. When the parser status is `ready`, the backend performs the action.
8. The result is stored in PostgreSQL.
9. The backend sends a response to the ESP32 and PWA.
10. The context layer decides whether reminders should be spoken, shown silently, delayed, or sent to the mobile app.

The backend is the source of truth for users, notes, reminders, calendar events, context states, notifications, command history, and device data.

## Repository Structure

```text
smart-desk-assistant/
├── apps/
│   ├── api/                 # FastAPI backend (Python, uv)
│   └── mobile/              # Next.js PWA
├── firmware/
│   └── esp32/               # ESP32-S3 firmware (ESP-IDF, PlatformIO, Slint UI)
├── packages/
│   ├── shared-types/        # Shared TypeScript types
│   └── validation/          # Shared validation rules
├── docs/                    # SRS, architecture, research, testing, hardware
├── AGENTS.md                # This file: project-wide rules and structure
├── README.md                # Setup and run instructions for the whole repo
├── CONTEXT.md               # Product context and constraints
└── docker-compose.yml       # Local PostgreSQL
```

Division of responsibility:

- **ESP32** — sensors, display, Bluetooth, Wi-Fi, audio capture/playback, speech-to-text, communication. Nothing else.
- **Backend** — command parsing, notes, reminders, calendar, context decisions, storage, notifications.
- **PWA** — user-facing screens and settings. It talks only to the backend API.

## Tech Stack

- Python, FastAPI
- uv for Python dependency and environment management
- PostgreSQL: Neon in production, Docker Compose Postgres locally (set `DATABASE_URL`)
- psycopg 3 with a connection pool (`app/db.py`) for database access; plain SQL, no ORM
- yoyo-migrations for schema changes: SQL files in `app/migrations/`, applied on API startup (`yoyo.ini`)
- Authlib for Google sign-in; app sessions are opaque random tokens in an HttpOnly cookie, stored hashed in the `sessions` table (no JWT)
- Google Calendar API with OAuth 2.0
- Speech-to-text on the ESP32 device (the backend receives text commands)
- Rule-based command parser for intent parsing (no AI/LLM for parsing in the first version)
- Redis and worker/scheduler only when background processing is needed

## Commands

```text
docker compose up -d                          # local Postgres (run from the repo root)
cd apps/api
uv sync                                       # install dependencies
uv run uvicorn app.main:app --reload          # run the API (applies migrations on startup)
uv run yoyo new --sql -m "<name>"             # create a migration
uv run pytest                                 # run tests
uv run ruff check app tests                   # lint
```

## Core Rules

- Keep important state in PostgreSQL, never only in application memory.
- Keep routes thin; business logic belongs in `service.py`.
- Database access belongs in `repository.py`.
- API request and response models belong in `schemas.py`.
- Schema changes are yoyo SQL migrations (`uv run yoyo new --sql -m "<name>"`), each with a `.rollback.sql` file. Do not add Alembic or SQLAlchemy.
- Use feature-based modules; do not place all logic in one large folder or file.
- Use clear names and small functions.
- Validate all external input.
- Do not expose secrets, tokens, passwords, or private user data in logs or responses.
- Do not commit `.env` files, API keys, OAuth tokens, or database URLs.
- Use environment variables for all credentials and external service configuration.
- Return clear, user-friendly error messages. Exception: auth redirects to the PWA carry short error codes only (for example `auth_error=access_denied`), never stack traces or raw Google error text.
- Sign-in is restricted by `ALLOWED_GOOGLE_EMAILS`. An empty value allows any verified Google account and is for development only; set it in production.
- Add tests for important business rules and failure cases.
- Prefer simple rule-based context logic in the first version.
- Do not add camera tracking, emotion detection, multi-user device support, or complex machine learning in the first version. The system has one primary user who signs in with Google; "device ownership" means each device belongs to that user.

## Backend Folder Structure

The backend lives in `apps/api/`. Run all `uv` and `pytest` commands from that folder. Feature modules live in `app/modules/<feature>/` and use `router.py`, `service.py`, `repository.py` and `schemas.py`. Database access is raw SQL through psycopg (`app/db.py`), so there is no `database/` package.

```text
apps/api/
├── app/
│   ├── main.py                    # FastAPI app factory, middleware, router registration
│   ├── config.py                  # Environment configuration (module-level `settings`)
│   ├── db.py                      # psycopg pool, get_db dependency, run_migrations
│   ├── migrations/                # yoyo SQL migrations (+ .rollback.sql files)
│   │
│   ├── core/
│   │   ├── security.py            # Session token and cookie helpers
│   │   ├── exceptions.py          # Common application errors + handlers
│   │   └── constants.py           # Context and notification constants
│   │
│   ├── routers/
│   │   └── health.py              # App-level route, not a feature module
│   │
│   ├── modules/
│   │   ├── auth/                  # Google sign-in, app sessions
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   ├── schemas.py
│   │   │   ├── oauth.py           # Authlib client registration
│   │   │   └── dependencies.py    # get_current_user
│   │   │
│   │   ├── command/               # Rule-based command parser
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── intent.py          # Intent classification rules
│   │   │   ├── extract.py         # Dates, times, titles, tasks, queries
│   │   │   ├── clarify.py         # Missing information and questions
│   │   │   └── schemas.py
│   │   │
│   │   ├── notes/                 # Planned
│   │   ├── reminders/             # Planned
│   │   ├── calendar/              # Planned (Phase 3, see docs/)
│   │   ├── context/               # Planned
│   │   ├── notifications/         # Planned
│   │   └── device/                # Planned
│   │
│   ├── integrations/              # Planned: external API clients only
│   └── jobs/                      # Planned: scheduled or long-running work
│
├── tests/
│   ├── auth/
│   └── command/
│
├── yoyo.ini                       # yoyo migration settings
├── pyproject.toml                 # uv/Python dependencies and project configuration
├── uv.lock                        # Locked dependency versions
└── .env.example                   # Variable names only, no secrets
```

## File Responsibilities

- `router.py` — API endpoints only.
- `service.py` — Business logic and workflow handling.
- `repository.py` — Database reads and writes only.
- `schemas.py` — Pydantic request and response models.
- `intent.py` — Intent classification rules (in the `command` module).
- `extract.py` — Date, time, and entity extraction from command text (in the `command` module).
- `clarify.py` — Missing information detection and clarification questions (in the `command` module).
- `integrations/` — External API clients only.
- `jobs/` — Scheduled, retried, or long-running background work.
- `tests/` — Tests for success cases, validation errors, and service failures.

## Command Parser

`POST /api/v1/command` turns one user sentence into a structured instruction. It is rule-based; do not replace it with an LLM in the first version.

- Intents: `CREATE_NOTE`, `CREATE_REMINDER`, `CREATE_EVENT`, `READ_EVENTS`, `WEB_SEARCH`, `UNKNOWN`.
- Statuses: `ready` (the orchestrator may execute), `needs_clarification` (send `clarification` to the user), `unsupported` (out of scope).
- A response is never `ready` while any required field is missing.
- Datetime slots are RFC 3339 strings with timezone offset; events default to 60 minutes when only a start time is given.
- The parser is stateless. The orchestrator stores `{intent, slots, missing}` after every response and sends it back as `context` with the user's follow-up reply.
- Checklist commands and destructive actions (cancel, delete, snooze) are out of scope and return `unsupported`.
- Multi-part sentences return `needs_clarification` with `missing: ["single_command"]`; ask for one command at a time.
- Orchestration duties stay outside the parser: authorization, confirmation, execution, and storage.

## Context States

Use only these availability states:

- `AVAILABLE`
- `IN_MEETING`
- `AWAY`
- `PRESENT_UNKNOWN`

Use only these notification modes:

- `SPEAK_AND_SHOW`
- `SHOW_SILENTLY`
- `DELAY`
- `MOBILE_ONLY`

A calendar event means **calendar indicates an active meeting**. It does not prove the user is physically attending a meeting.

Radar detects room presence. Bluetooth phone proximity is a supporting signal for identifying the paired user. If identity is uncertain, do not speak private reminder content.

## Workflow Rules

Every important request must follow this flow:

```text
Receive request
→ Validate user/device
→ Save request or state
→ Process action
→ Save result
→ Notify ESP32/PWA
→ Record final outcome
```

For voice commands:

```text
Text command received
→ Command parsing (intent, details, missing fields)
→ Ask the user for clarification if needed
→ Store the pending command and merge the follow-up reply into it
→ Execute only when the status is ready
→ Save result
→ Send structured confirmation
```

For reminders:

```text
Reminder becomes due
→ Read current context
→ Choose notification mode
→ Create notification record
→ Deliver notification
→ Record acknowledge, snooze, dismiss, or failure
```

Never create duplicate calendar events, notes, or reminders when a device retries a request. Use request IDs or idempotency keys for external actions.

## Fault Tolerance

- Save workflow state before calling external services.
- Retry temporary failures with limited retries and increasing delays.
- Record failures with a clear reason.
- Use safe defaults if radar, Bluetooth, Calendar, AI, or network data is unavailable.
- If user identity is uncertain, use silent display or delay instead of voice output.
- If the ESP32 is offline, store the notification and send it when the device reconnects.
- Do not mark a notification as delivered until delivery is confirmed or recorded.

## First Release Scope

Build these features first:

- Authentication and device ownership.
- Notes.
- Time-based reminders with snooze and dismiss.
- Google Calendar event creation and upcoming-event reading.
- Command parser with clarification loop and follow-up context (`POST /api/v1/command`).
- Context-aware reminder decisions using radar status, Bluetooth status, Calendar state, and manual preferences.
- ESP32 device status, heartbeat, and notification polling.
- PWA APIs for notes, reminders, settings, and current context.

Keep AI briefings, advanced personalization, news, automatic routine learning, and complex notification intelligence as later features.
