# AGENTS.md

Rules and plan for the Smart Desk Assistant PWA in `apps/mobile`.

## Overview

`apps/mobile` is the Next.js PWA. It talks to the FastAPI backend in `apps/api`, shares data contracts with `packages/shared-types`, and shares validation with `packages/validation`. Routes stay thin and delegate to feature code, the same way `router.py` delegates to `service.py` on the backend.

## Branch Strategy

All PWA work lives on one long-lived branch, `feature/pwa`, based on `develop`.

```powershell
git switch develop
git pull
git switch -c feature/pwa
git push -u origin feature/pwa
```

Open it as a draft pull request into `develop` right away so CI runs and the team can follow progress. Never push code without permission.

## Rules

1. Merge, never rebase. Once the branch is pushed, `git rebase` rewrites shared history and needs a force-push. Pull `develop` in with a merge instead, every time a backend PR lands.
   ```powershell
   git switch feature/pwa
   git fetch origin
   git merge origin/develop
   ```
2. Merge into `develop` at checkpoints, not only at the end. `develop` should not wait weeks for the PWA. Merge at two or three milestones, then keep working on the same branch. This also keeps the final pull request reviewable.
3. One concern per commit. Stage the work so history reads cleanly: scaffold, then auth, then notes, and so on. No single commit that adds everything.
4. One API client file. Put every backend call in `apps/mobile/lib/api.ts`. When another branch changes an endpoint, fix it in one place instead of many components.
5. Never commit `.env.local`. Ship `apps/mobile/.env.example` and list variable names only.
6. Never commit to `develop` or `main` directly.

## Commit Stages

| stage | scope | merge to develop? |
|---|---|---|
| 1 | Next.js scaffold: `tsconfig`, `next.config`, `app/`, styling, lint, env, npm deps, wire `shared-types` and `validation` | yes, checkpoint |
| 2 | Shared shell: layout, nav, API client, loading and error states | yes, with checkpoint 1 |
| 3 | Auth screens and Google callback | yes, checkpoint 2 |
| 4 | Notes and checklists | checkpoint 3 |
| 5 | Reminders with snooze and dismiss | with checkpoint 3 |
| 6 | Calendar upcoming and create | end |
| 7 | Device and context status, notifications | end |

## Folder Layout

Keep it feature based, mirroring the backend:

```text
apps/mobile/
├── app/                 # routes only, thin pages
├── components/          # shared UI
├── lib/
│   ├── api.ts           # the one place that talks to FastAPI
│   └── env.ts           # NEXT_PUBLIC_API_URL
├── features/
│   ├── auth/
│   ├── notes/
│   ├── reminders/
│   ├── calendar/
│   └── device/
├── .env.example
└── AGENTS.md
```

## Environment

- `NEXT_PUBLIC_API_URL` points at the backend.
- `.env.example` lists names only, no secrets.
- `.env.local` stays local and gitignored.

## Backend Contracts

The PWA is built against the backend API contracts. The main one so far:

```text
POST /api/v1/command
{ "text": "remind me to call mom tomorrow", "request_id": "optional" }
-> 200 { "text": "...", "intent": "CREATE_REMINDER", "slots": { "text": "...", "when": "tomorrow" } }
```

Import the matching types from `packages/shared-types` rather than redeclaring them.

## Integration

Merge order before the PWA screens depend on the backend:

1. `feature/command-intent` -> `develop`
2. `feature/google-auth` -> `develop`

Then pull `develop` into `feature/pwa` so the API client is built against real contracts.

Shared-file hotspots between the PWA branch and the API branches:

- `packages/shared-types/src/index.ts` and `packages/shared-types/package.json`
- root `package-lock.json` when new npm dependencies are added

Everything under `apps/api` and `apps/mobile` is disjoint, so merges stay simple as long as `develop` is pulled in right after those pull requests land.
