# Command Parser Contract

The command parser turns one user sentence into a structured instruction. It answers **what the user wants**; it never decides whether an action is allowed, confirmed, or executed. Those belong to the orchestration layer.

- Endpoint: `POST /api/v1/command`
- Code: `apps/api/app/modules/command`
- Types: `apps/api/app/modules/command/schemas.py` and `packages/shared-types/src/index.ts`
- Output fields are **frozen**: `text`, `intent`, `status`, `slots`, `missing`, `clarification`. Adding a field is a contract change for every consumer.

## Request

```json
{
  "text": "Schedule a project meeting this Thursday from 2 PM to 4 PM.",
  "request_id": null,
  "timezone": "Asia/Karachi",
  "context": null
}
```

| Field | Required | Nullable | Meaning |
|---|---|---|---|
| `text` | yes | no | One user sentence. Blank is rejected with `invalid_command` |
| `request_id` | no | yes | Caller's id for tracing and idempotency |
| `timezone` | no | yes | IANA name for date and time resolution. Unknown name is rejected with `invalid_timezone`. Defaults to `UTC` |
| `context` | no | yes | Pending instruction sent back with a follow-up reply. See Context merge |

## Response

```json
{
  "text": "Schedule a project meeting this Thursday from 2 PM to 4 PM.",
  "intent": "CREATE_EVENT",
  "status": "ready",
  "slots": {
    "title": "Project meeting",
    "date": "2026-10-22",
    "start_at": "2026-10-22T14:00:00+05:00",
    "end_at": "2026-10-22T16:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

| Field | Type | Meaning |
|---|---|---|
| `text` | string | Echo of the user's sentence |
| `intent` | enum | One of the six intents below |
| `status` | enum | `ready`, `needs_clarification`, or `unsupported` |
| `slots` | object, string values only | Extracted details |
| `missing` | array of string | Field names still needed. Always empty when `status` is `ready` |
| `clarification` | string or null | The single question to ask the user. Null when nothing is missing |

## Intents

| Intent | Meaning |
|---|---|
| `CREATE_EVENT` | Create a calendar meeting |
| `CREATE_REMINDER` | Create a time-based reminder |
| `CREATE_NOTE` | Save a note |
| `READ_EVENTS` | Read the user's calendar over a date range |
| `WEB_SEARCH` | Search the web, optionally as a brief summary |
| `UNKNOWN` | Not understood, or out of scope. Paired with `status: unsupported` |

## Statuses

| Status | Meaning | What the caller does |
|---|---|---|
| `ready` | Every required detail is present | May execute. The orchestrator decides whether to confirm first |
| `needs_clarification` | A required detail is missing | Ask `clarification`, store `{intent, slots, missing}`, send it back as `context`. **Do not execute** |
| `unsupported` | Out of scope, or not understood | Reply that it cannot do it. `intent` is `UNKNOWN`. **Do not execute** |

A response is never `ready` while `missing` is non-empty.

## Slots per intent

| Intent | Required | Optional / conditional |
|---|---|---|
| `CREATE_EVENT` | `title`, `date`, `start_at`, `end_at`, `timezone` | `ambiguous_hour` while the hour is unclear; `end_time_invalid` when the range end is before the start |
| `CREATE_REMINDER` | `task`, `remind_at`, `timezone` | `date` |
| `CREATE_NOTE` | `content` | none |
| `READ_EVENTS` | `date_from`, `date_to` | none |
| `WEB_SEARCH` | `query`, `timezone` | `style` (`brief`), `date_from`, `date_to` |
| `UNKNOWN` | none | `detected_intents`, set only for a multi-request sentence |

`end_at` is always present when `status` is `ready`, because a missing end time defaults to 60 minutes after the start. `ambiguous_hour` and `end_time_invalid` appear only while the parser is asking a question.

## Date and time format

- Datetime slots are **RFC 3339 strings with offset**: `2026-10-22T14:00:00+05:00`. Google Calendar accepts them without conversion.
- Date-only slots are `YYYY-MM-DD`: `2026-10-22`.
- `READ_EVENTS` and search ranges use date-only `date_from` and `date_to`.

**Reference date and timezone.** There is no date field in the request. The reference date is the server clock read in the requested `timezone`, so `timezone` is part of the input, not decoration. The same sentence resolves differently in `Asia/Karachi` and `UTC` near midnight.

- The timezone arrives per request, is validated against the IANA database, and defaults to `UTC`.
- Tests pin the clock and the timezone so results are reproducible. Every example below uses **20 October 2026, 09:00, `Asia/Karachi`**, which makes `tomorrow` = `2026-10-21` and `this Thursday` = `2026-10-22`.
- Restarting the server or changing the machine clock changes resolution. Only the caller's `timezone` and the server clock matter.

## Context merge

Clarification is a two-turn exchange. The caller stores the previous response and sends it back as `context` with the reply:

```json
{
  "text": "at 2 pm for one hour",
  "timezone": "Asia/Karachi",
  "context": {
    "intent": "CREATE_EVENT",
    "slots": { "title": "Meeting", "date": "2026-10-21", "timezone": "Asia/Karachi" },
    "missing": ["start_at"]
  }
}
```

```json
{
  "text": "at 2 pm for one hour",
  "intent": "CREATE_EVENT",
  "status": "ready",
  "slots": {
    "title": "Meeting",
    "date": "2026-10-21",
    "start_at": "2026-10-21T14:00:00+05:00",
    "end_at": "2026-10-21T15:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

Rules that the caller can rely on:

- Send `context` exactly as the previous response returned it: `intent`, `slots`, `missing`.
- The reply is merged when it carries no clear intent of its own, or when it classifies to the same intent as the pending instruction.
- A reply that clearly asks for something else starts a new instruction. The pending one is dropped.
- **A new value replaces the earlier value for the same slot.** The latest value always wins.
- A reply that provides a value for a slot already present replaces it. `"make it 4 pm"` after a 2 PM meeting moves the start and recomputes the end:

```json
{
  "text": "make it 4 pm",
  "intent": "CREATE_EVENT",
  "status": "ready",
  "slots": {
    "title": "Meeting",
    "date": "2026-10-21",
    "start_at": "2026-10-21T16:00:00+05:00",
    "end_at": "2026-10-21T17:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

- A correction that opens with a filler word keeps the earlier title. `"no, make it 3 pm"` changes only the time:

```json
{
  "text": "no, make it 3 pm",
  "intent": "CREATE_EVENT",
  "status": "ready",
  "slots": {
    "title": "Meeting",
    "date": "2026-10-21",
    "start_at": "2026-10-21T15:00:00+05:00",
    "end_at": "2026-10-21T16:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

- A reply that opens with a matching create verb may rename. `"actually schedule the design review tomorrow at 2 pm"` replaces the title:

```json
{
  "text": "actually schedule the design review tomorrow at 2 pm",
  "intent": "CREATE_EVENT",
  "status": "ready",
  "slots": {
    "title": "Design review",
    "date": "2026-10-21",
    "start_at": "2026-10-21T14:00:00+05:00",
    "end_at": "2026-10-21T15:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

- The lead verb must match the pending intent. "make" is an event lead, so it cannot rename a reminder task.
- Note content is never suppressed: when a note is waiting for its content, the reply **is** the content. "We need to finish the calendar integration." becomes the note body.

## Missing field names

| Name | Asks for |
|---|---|
| `date` | The day of a meeting |
| `start_at` | The start time of a meeting |
| `start_at_meridiem` | Whether an ambiguous hour is AM or PM |
| `end_at` | The end time when the given range cannot be trusted |
| `task` | What a reminder is about |
| `remind_at` | When to remind |
| `content` | What a note should say |
| `query` | What to search for |
| `single_command` | One command at a time |

## `single_command`

A sentence that asks for more than one thing is not split and not executed, even partially.

```json
{
  "text": "Create a note and schedule a meeting tomorrow at 3 PM.",
  "intent": "CREATE_NOTE",
  "status": "needs_clarification",
  "slots": { "detected_intents": "CREATE_NOTE, CREATE_EVENT" },
  "missing": ["single_command"],
  "clarification": "Please give me one command at a time."
}
```

`status` is `needs_clarification`, never `ready`, so no action can run from it. `intent` reports the first command found and `slots.detected_intents` lists every command detected.

## More examples

All use 20 October 2026, 09:00, `Asia/Karachi`.

Event that needs a time:

```json
{
  "text": "Schedule a meeting tomorrow",
  "intent": "CREATE_EVENT",
  "status": "needs_clarification",
  "slots": { "title": "Meeting", "date": "2026-10-21", "timezone": "Asia/Karachi" },
  "missing": ["start_at"],
  "clarification": "What time should the meeting start, and how long should it be?"
}
```

Ambiguous hour, never guessed:

```json
{
  "text": "Schedule a meeting tomorrow at 2.",
  "intent": "CREATE_EVENT",
  "status": "needs_clarification",
  "slots": { "title": "Meeting", "date": "2026-10-21", "ambiguous_hour": "2", "timezone": "Asia/Karachi" },
  "missing": ["start_at_meridiem"],
  "clarification": "Did you mean 2 AM or 2 PM?"
}
```

Reminder:

```json
{
  "text": "Remind me tomorrow at 9 AM to submit my assignment.",
  "intent": "CREATE_REMINDER",
  "status": "ready",
  "slots": {
    "task": "Submit my assignment",
    "date": "2026-10-21",
    "remind_at": "2026-10-21T09:00:00+05:00",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

Note:

```json
{
  "text": "Write a note: buy a new microphone for the project.",
  "intent": "CREATE_NOTE",
  "status": "ready",
  "slots": { "content": "buy a new microphone for the project" },
  "missing": [],
  "clarification": null
}
```

Search with a brief-summary preference:

```json
{
  "text": "Give me a brief overview of AI papers released yesterday.",
  "intent": "WEB_SEARCH",
  "status": "ready",
  "slots": {
    "query": "AI papers",
    "style": "brief",
    "date_from": "2026-10-19",
    "date_to": "2026-10-19",
    "timezone": "Asia/Karachi"
  },
  "missing": [],
  "clarification": null
}
```

Read:

```json
{
  "text": "What meetings do I have tomorrow?",
  "intent": "READ_EVENTS",
  "status": "ready",
  "slots": { "date_from": "2026-10-21", "date_to": "2026-10-21" },
  "missing": [],
  "clarification": null
}
```

Unsupported:

```json
{
  "text": "Turn off the bedroom lights.",
  "intent": "UNKNOWN",
  "status": "unsupported",
  "slots": {},
  "missing": [],
  "clarification": null
}
```

## TypeScript mirror

`packages/shared-types/src/index.ts` must match the API exactly, including optional and nullable fields. Optional in Python is not always optional in TypeScript.

```ts
export type Intent =
  | "CREATE_NOTE"
  | "CREATE_REMINDER"
  | "CREATE_EVENT"
  | "READ_EVENTS"
  | "WEB_SEARCH"
  | "UNKNOWN";

export type Status = "ready" | "needs_clarification" | "unsupported";

export interface CommandContext {
  intent: Intent;
  slots: Record<string, string>;
  missing: string[];
}

export interface CommandRequest {
  text: string;
  request_id?: string | null;
  timezone?: string | null;
  context?: CommandContext | null;
}

export interface CommandResponse {
  text: string;
  intent: Intent;
  status: Status;
  slots: Record<string, string>;
  missing: string[];
  clarification: string | null;
}
```

| Python field | TypeScript | Why |
|---|---|---|
| `text`, `intent`, `status`, `slots`, `missing` | required, non-null | Always present in a response |
| `clarification` | `string \| null` | Required field, null when nothing is missing |
| `request_id`, `timezone` | `?: string \| null` | May be omitted **or** explicitly null |
| `context` | `?: CommandContext \| null` | Same |

Change Python `schemas.py` and this file in the same commit, or the PWA compiles against a contract the API no longer serves.

## Out of parser scope

- Checklists
- Cancel, delete, snooze, and other destructive actions
- Confirmation words such as "yes", "no", "confirm", and "cancel that". These belong to the orchestrator, and the parser answers `unsupported` when it receives them alone
- Authorization, execution, storage, duplicate prevention, and user-facing wording beyond `clarification`

## Tests

`apps/api/tests/command` covers classification, extraction, clarification, follow-up merging, corrections, the endpoint contract, and error cases. Run `uv run pytest -q` in `apps/api`.
