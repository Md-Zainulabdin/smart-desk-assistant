# Smart Desk Assistant PWA

Next.js PWA for the Smart Desk Assistant. Talks to the FastAPI backend in `apps/api` and
imports its data contracts from `packages/shared-types`.

Rules and the build plan live in [AGENTS.md](./AGENTS.md).

## Setup

```powershell
npm.cmd install
```

Run from the repository root. This is an npm workspace, so dependencies install once for
every package.

## Scripts

Run from the repository root:

```powershell
npm.cmd run dev:mobile    # next dev on http://localhost:3000
npm.cmd run build:mobile  # production build
```

Or from `apps/mobile`:

```powershell
npm.cmd run lint
npm.cmd run typecheck
```

## Environment

Copy `.env.example` to `.env.local` and fill in the values. `.env.local` is never committed.
