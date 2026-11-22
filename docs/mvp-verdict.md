# MVP Verdict

Backend notes, parser, web search, and auth primitives work. The parser chain is ESP → backend → orchestrator → action. The MVP is not demo-ready until the calendar live flow and the remaining PWA reliability issues are resolved.

## Must resolve

1. **Google Calendar is not verified end-to-end.**
   - Live `GET /api/v1/calendar/meetings` and `POST /api/v1/calendar/meetings` return `403 calendar_not_connected`; the database has no user with a Google refresh token.
   - Resolve: sign in with a real Google account, enable the Google Calendar API, add the account as an OAuth test user, grant the Calendar scope, then create and list one meeting.
   - Refs: `apps/api/app/modules/calendar/`, `apps/api/app/integrations/google_calendar.py`, `apps/mobile/features/calendar/calendar-view.tsx`.

2. **Failed Google sign-in is silent in the PWA.**
   - The callback redirects to `/?auth_error=...`, but `SessionGate` redirects to `/login` and drops the code.
   - Resolve: redirect failures to `/login?auth_error=...` and display the short error on the login screen.
   - Refs: `apps/api/app/modules/auth/router.py`, `apps/mobile/features/auth/session.tsx`, `apps/mobile/app/login/page.tsx`.

3. **Calendar retries can create duplicate events.**
   - `calendar-view.tsx` generates a new `request_id` on every submit, so a manual retry after a timeout does not reuse the backend idempotency key.
   - Resolve: keep one `request_id` for a submission and reuse it when retrying.
   - Refs: `apps/mobile/features/calendar/calendar-view.tsx`, `apps/api/app/modules/calendar/service.py`.

4. **Direct note creation is not idempotent.**
   - `POST /api/v1/notes` does not pass `request_id` to `repository.create_note`, and `createNote()` in the PWA does not send one.
   - Resolve: send a `request_id` from the client and pass it through the notes route to the repository.
   - Refs: `apps/mobile/lib/api.ts`, `apps/api/app/modules/notes/router.py`, `apps/api/app/modules/notes/repository.py`.
