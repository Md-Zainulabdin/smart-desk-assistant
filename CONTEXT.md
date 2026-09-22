# CONTEXT.md

## Project Context

Smart Desk Assistant is a context-aware IoT desk companion. It uses an ESP32-S3 device, a Next.js PWA, a FastAPI backend, and Neon PostgreSQL.

The system supports voice commands, notes, checklists, reminders, Google Calendar events, AI briefings, and context-aware notifications. It uses radar presence detection, Bluetooth phone proximity, calendar status, and user preferences to decide whether to speak, show silently, delay, or send a notification.

## Repository Structure

- `apps/api` — FastAPI backend
- `apps/mobile` — Next.js PWA
- `firmware/esp32` — ESP32-S3 firmware
- `packages/shared-types` — shared data types
- `packages/validation` — shared validation rules
- `docs` — SRS, architecture, research, testing, and hardware documentation

## Working Methodology

- Build features independently first, then integrate them through stable API contracts.
- Keep each feature inside its own module and avoid mixing unrelated logic.
- Use small feature branches and open a pull request before merging into `develop`.
- Keep `main` stable and deployable.
- Update documentation when a feature, API, or hardware behavior changes.
- Test important flows before merging: authentication, notes, reminders, calendar events, context decisions, and ESP32 communication.
- Use clear naming, simple functions, and meaningful error messages.
- Never commit `.env` files, API keys, OAuth tokens, database credentials, or private user data.

## Core Constraints

- The project supports one primary user and one paired phone per device.
- ESP32 handles sensors, display, Bluetooth, Wi-Fi, audio capture/playback, and communication only.
- Speech-to-text, AI/NLP, calendar integration, reminders, and context decisions run on the FastAPI backend.
- Google Calendar is the only supported calendar provider.
- Notes and checklists are stored in Neon PostgreSQL.
- Internet is required for AI, speech processing, Google Calendar, and news features.
- Radar detects room presence; Bluetooth is used as a supporting signal for the paired user’s proximity.
- A calendar event means “calendar indicates a meeting”; it does not prove the user is physically attending one.
- Context decisions must remain explainable and use these states only: `AVAILABLE`, `IN_MEETING`, `AWAY`, and `PRESENT_UNKNOWN`.
- Notification decisions must use only these modes: `SPEAK_AND_SHOW`, `SHOW_SILENTLY`, `DELAY`, and `MOBILE_ONLY`.
- Do not add camera tracking, emotion detection, multi-user support, or complex machine-learning behavior in the first release.
- Audio must be sent to the backend only after wake-word or manual activation, and the device must visibly indicate when it is listening.