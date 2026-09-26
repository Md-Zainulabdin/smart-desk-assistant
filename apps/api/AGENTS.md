# AGENTS.md

You are an expert FastAPI and Python backend engineer helping build **Smart Desk Assistant**, a production-quality, context-aware voice assistant system. You write clean, simple, maintainable code. Prioritize clarity over unnecessary abstraction. This backend should be easy to build feature by feature and easy for another developer to understand.

## Project Overview

Smart Desk Assistant is a voice-activated IoT assistant connected to an ESP32 device and a Next.js PWA. It helps users create notes, checklists, reminders, and Google Calendar events using voice commands.

Core system flow:

1. The ESP32 detects a wake word and records a voice command.
2. The device sends audio to the FastAPI backend.
3. Speech-to-text converts audio into text.
4. Intent parsing identifies the requested action.
5. The backend validates the command and performs the action.
6. The result is stored in Neon PostgreSQL.
7. The backend sends a response to the ESP32 and PWA.
8. The context layer decides whether reminders should be spoken, shown silently, delayed, or sent to the mobile app.

The backend is the source of truth for users, notes, reminders, calendar events, context states, notifications, command history, and device data.

## Tech Stack

- Python
- FastAPI
- uv for Python dependency and environment management
- Neon PostgreSQL
- SQLAlchemy / Alembic for database access and migrations
- Google Calendar API with OAuth 2.0
- Speech-to-text provider
- AI/NLP provider for intent parsing and briefings
- Redis and worker/scheduler only when background processing is needed

## Core Rules

- Keep important state in PostgreSQL, never only in application memory.
- Keep routes thin; business logic belongs in `service.py`.
- Database access belongs in `repository.py`.
- API request and response models belong in `schemas.py`.
- Use feature-based modules; do not place all logic in one large folder or file.
- Use clear names and small functions.
- Validate all external input.
- Do not expose secrets, tokens, passwords, or private user data in logs or responses.
- Do not commit `.env` files, API keys, OAuth tokens, or database URLs.
- Use environment variables for all credentials and external service configuration.
- Return clear, user-friendly error messages.
- Add tests for important business rules and failure cases.
- Prefer simple rule-based context logic in the first version.
- Do not add camera tracking, emotion detection, multi-user device support, or complex machine learning in the first version.

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
Audio received
→ Speech-to-text
→ Intent parsing
→ Validate required information
→ Ask for clarification if needed
→ Execute action
→ Save result
→ Send confirmation
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
- Temporary audio should be deleted after processing unless explicit storage is enabled.

## Folder Structure

```text
apps/api/
├── app/
│   ├── main.py                    # FastAPI app setup and router registration
│   ├── config.py                  # Environment configuration
│   ├── dependencies.py            # Shared dependencies
│   │
│   ├── core/
│   │   ├── security.py            # JWT, auth helpers, token handling
│   │   ├── exceptions.py          # Common application errors
│   │   ├── constants.py           # Context and notification constants
│   │   └── logging.py             # Logging setup
│   │
│   ├── database/
│   │   ├── connection.py          # Neon PostgreSQL connection
│   │   ├── models.py              # Database models
│   │   └── base.py                # Shared database base/model setup
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── notes/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── reminders/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── calendar/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── voice/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── context/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   ├── notifications/
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   └── schemas.py
│   │   │
│   │   └── device/
│   │       ├── router.py
│   │       ├── service.py
│   │       └── schemas.py
│   │
│   ├── integrations/
│   │   ├── google_calendar.py     # Google Calendar API client
│   │   ├── speech_to_text.py      # Speech-to-text provider client
│   │   ├── text_to_speech.py      # Text-to-speech provider client
│   │   └── ai_provider.py         # AI/NLP provider client
│   │
│   └── jobs/
│       ├── reminder_worker.py     # Due reminder processing
│       ├── calendar_sync.py       # Calendar synchronization
│       ├── context_worker.py      # Context evaluation
│       └── cleanup_worker.py      # Temporary audio cleanup
│
├── tests/
│   ├── auth/
│   ├── notes/
│   ├── reminders/
│   ├── calendar/
│   ├── voice/
│   ├── context/
│   ├── notifications/
│   └── device/
│
├── alembic/                       # Database migrations
├── pyproject.toml                 # uv/Python dependencies and project configuration
├── uv.lock                        # Locked dependency versions
├── .env.example                   # Variable names only, no secrets
└── README.md                      # Backend setup and run instructions
```

## File Responsibilities

- `router.py` — API endpoints only.
- `service.py` — Business logic and workflow handling.
- `repository.py` — Database reads and writes only.
- `schemas.py` — Pydantic request and response models.
- `integrations/` — External API clients only.
- `jobs/` — Scheduled, retried, or long-running background work.
- `tests/` — Tests for success cases, validation errors, and service failures.

## First Release Scope

Build these features first:

- Authentication and device ownership.
- Notes and checklist items.
- Time-based reminders with snooze and dismiss.
- Google Calendar event creation and upcoming-event reading.
- Audio upload, speech-to-text, and simple intent parsing.
- Context-aware reminder decisions using radar status, Bluetooth status, Calendar state, and manual preferences.
- ESP32 device status, heartbeat, and notification polling.
- PWA APIs for notes, reminders, settings, and current context.

Keep AI briefings, advanced personalization, news, automatic routine learning, and complex notification intelligence as later features.
