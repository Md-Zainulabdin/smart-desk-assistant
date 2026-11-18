   # Google Sign-In and Calendar Implementation Workflow

   This workflow implements Google sign-in and authorization to book events on the
   signed-in user's Google Calendar. It does not include agent integration. Build
   and verify each phase before moving to the next.

   ## Recommended design

   Use two Google authorization steps:

   1. **Sign in with Google** using OpenID Connect scopes (`openid`, `email`,
      `profile`). This creates the user's app account and app session.
   2. **Connect Google Calendar** for the signed-in app user. Request Calendar
      permission, verify that the authorizing Google account has the same stable
      Google subject (`sub`) as the account used to sign in, and store the
      authorization on that user's account.

   Separating the steps means a user can still sign in if they decline Calendar
   access. Require a successful Calendar connection before allowing event booking.
   Do not request Calendar permission during ordinary sign-in.

   ## Phase 1: Establish configuration and contracts

   ### Google Cloud setup

   1. Create or select a Google Cloud project.
   2. Enable the Google Calendar API.
   3. Configure the OAuth consent screen, app name, support email, audience, and
      authorized domains.
   4. Create a Web application OAuth client.
   5. Add the FastAPI callback URL to its authorized redirect URIs. Use separate
      client configuration for local development and production.
   6. Keep the OAuth client secret and token-encryption key in backend environment
      configuration or a secret manager. Never place them in the PWA or commit
      them to Git.
   7. Plan for Google's consent-screen testing and verification requirements
      before inviting users beyond the test audience.

   ### Initial scopes

   - Sign-in: `openid`, `email`, `profile`
   - Event creation: `https://www.googleapis.com/auth/calendar.events`
   - Optional availability checks: `https://www.googleapis.com/auth/calendar.freebusy`

   Only request `calendar.freebusy` if the first release needs to check for
   conflicts. Do not request full Calendar access without a feature that needs it.

   ## Phase 2: Build Google sign-in and app sessions

   Implement the backend first, then connect the PWA to it.

   ### Backend

   Add an authentication module under `apps/api` with endpoints equivalent to:

   - `GET /auth/google/start` — generate a cryptographically random `state`,
   bind it to the login attempt, then redirect to Google's authorization page.
   - `GET /auth/google/callback` — validate `state`, exchange the code, validate
   the ID token's signature, issuer, audience, expiry, and verified email, then
   create or find the app user by Google `sub`.
   - `GET /auth/me` — return the current user's public profile.
   - `POST /auth/logout` — clear/revoke the app's session.

   Use a maintained OAuth/OpenID Connect library for the authorization flow and
   ID-token validation; do not implement token verification cryptography yourself.
   Issue an app session after successful sign-in. Use a secure, HttpOnly cookie and
   configure cookie and CORS settings for the PWA's actual origins.

   ### Persistence

   Create a Neon migration for the app user record. Store the Google `sub` as the
   stable identity key; do not identify an account by email alone. Keep only the
   profile fields the app needs.

   ### PWA

   Add a **Sign in with Google** button that navigates to the backend start
   endpoint. On return to the app, call `/auth/me` and render signed-in or
   signed-out state. Include credentials on API requests that use the session.

   ### Phase 2 acceptance checks

   - A first-time sign-in creates one app user.
   - Signing in again with the same Google account returns that same app user.
   - Invalid, missing, or reused `state` is rejected.
   - An unverified email or invalid ID token cannot establish an account.
   - Logout clears the app session; protected API requests then fail.
   - Sign-in succeeds without any Calendar permission being requested.

   ## Phase 3: Connect Calendar to the signed-in user

   ### Backend flow

   Add endpoints equivalent to:

   - `GET /auth/google/calendar/start` — require an app session; initiate Google
   authorization with the required Calendar scope and a fresh, one-time `state`.
   - `GET /auth/google/calendar/callback` — validate `state`, exchange the code,
   validate the Google identity, and confirm its `sub` matches the current app
   user's Google `sub` before saving the Calendar grant.
   - `DELETE /auth/google/calendar` — disconnect Calendar, revoke the grant with
   Google where possible, and remove the locally stored credentials.

   Request offline access when needed so the backend can refresh credentials after
   the user leaves. Ensure the OAuth library obtains and safely handles a refresh
   token; Google may not return a new refresh token on every authorization. Do not
   overwrite a valid stored refresh token with an absent value.

   If the user authorizes a different Google account, reject the link and explain
   that they must connect the account they used to sign in. Do not silently change
   the app user's identity or attach the other account's grant.

   ### Persistence and security

   Store the connected Google `sub`, granted scopes, and encrypted refresh token
   in a Calendar-authorization record associated with the app user. Encrypt tokens
   at rest using a key held outside the database. Never expose access or refresh
   tokens to the PWA, log them, or pass them to any AI service.

   Keep authorization and Google API calls in the FastAPI backend. Return clear
   errors for revoked consent, missing scopes, token refresh failures, and Google
   API errors. Do not report success when Google rejected an operation.

   ### PWA

   Add a **Connect Google Calendar** action for signed-in users, with connected
   status and a **Disconnect** action. If Calendar access is missing, explain that
   booking requires it; do not block app sign-in.

   ### Phase 3 acceptance checks

   - Calendar authorization requires a signed-in app user.
   - The authorization is stored only when the returned Google `sub` matches the
   signed-in Google identity.
   - Declining Calendar consent leaves the app sign-in/session intact.
   - A different Google account cannot be linked accidentally.
   - Disconnect removes the usable local grant and handles Google revocation
   failures explicitly.

   ## Phase 4: Implement and verify event creation

   Before any agent is involved, prove that the backend can book one event for the
   current signed-in user.

   Add a service that:

   1. Gets the current app user from the authenticated request, never from a
      user-supplied account ID.
   2. Loads that user's encrypted refresh token and obtains a valid access token.
   3. Validates the event title, start/end timestamps, timezone, and attendee
      addresses.
   4. Calls Google Calendar's events insert API using the user's primary calendar.
   5. Returns the created event's ID, URL, and normalized time information.
   6. Surfaces authorization, conflict, validation, quota, and API failures as
      explicit errors.

   Expose a protected endpoint such as `POST /calendar/events`. Require the user to
   confirm the proposed details in the UI before submitting the booking. Use an
   idempotency mechanism so a retried request does not create duplicate meetings.

   ### Phase 4 acceptance checks

   - A connected user can create an event on their own primary calendar.
   - A signed-out user or a user without a Calendar grant cannot book.
   - A user cannot select another user's Google credentials by changing request
   data.
   - Invalid timestamps and end-before-start are rejected.
   - A repeated idempotent request does not create a duplicate event.
   - Revoked/expired authorization produces a reconnect flow rather than a false
   success.
   - The PWA displays Google API failures and booking results clearly.

   ## Suggested repository layout

   The API directory is currently a placeholder. Adapt names to the framework and
   conventions chosen when scaffolding FastAPI:

   - `apps/api/app/auth/google.py` — OAuth start and callbacks
   - `apps/api/app/auth/session.py` — app-session creation and current-user access
   - `apps/api/app/calendar/google.py` — Google Calendar client operations
   - `apps/api/app/calendar/routes.py` — protected calendar endpoints
   - `apps/api/migrations/` — app-user and Google authorization schema
   - `apps/mobile/app/...` — sign-in, Calendar connect, and booking UI

   Keep OAuth state handling, token encryption, database access, and API routes
   behind small reusable services rather than mixing them into UI code.

   ## Start here

   Start with **Phase 1 and Phase 2 only**: decide the local and production
   callback URLs, configure the Google OAuth client, scaffold the FastAPI API, and
   complete sign-in/session/logout. Once those acceptance checks pass, implement
   the separate Calendar connection flow in Phase 3, then event creation in
   Phase 4. This isolates OAuth and account-linking problems before adding
   calendar side effects.

   Do not add Calendar permissions to the initial sign-in scopes, build agent
   tools, or send Google credentials to the browser. Agent integration can later
   call the same authenticated backend calendar service after these phases are
   working.
