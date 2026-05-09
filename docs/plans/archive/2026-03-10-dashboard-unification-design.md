# Dashboard Unification: React SPA + FastAPI

## Problem

Two separate dashboards exist:
1. **FastAPI inline HTML** (`app.py`, ~230 lines) — deployed in Docker, serves basic dashboard summary
2. **React frontend** (`dashboard-frontend/`, 4,200 lines) — 8 pages including StrategyConfig, never built or deployed

The React app already implements every feature the inline HTML provides plus six additional pages. Maintaining both is wasteful and the Strategy Configuration page is inaccessible.

## Decision

Unify into a single React SPA served by FastAPI as static files.

## Architecture

```
[Vite Build] dashboard-frontend/ → dist/
     ↓
[FastAPI] services/dashboard/app.py
  ├── GET /api/*       → API endpoints (unchanged)
  ├── GET /ws          → WebSocket (unchanged)
  ├── GET /health      → Health check (unchanged)
  ├── GET /assets/*    → Static files (JS/CSS from React build)
  └── GET /*           → dist/index.html (SPA catch-all)
```

## Changes

### 1. React build (`dashboard-frontend/`)
- `bun install && bun run build` → produces `dist/`
- Add `vite.config.ts` proxy for dev mode (`/api` → `localhost:8001`)

### 2. FastAPI static serving (`services/dashboard/app.py`)
- Remove `_DASHBOARD_HTML` inline HTML (~230 lines)
- Mount `StaticFiles` for `dist/assets/`
- Add SPA catch-all route: any non-API path → `dist/index.html`
- API routes registered first (take priority over catch-all)

### 3. Dockerfile multi-stage (`Dockerfile.dashboard`)
- Stage 1: Node.js — install deps, build React
- Stage 2: Python — existing setup + `COPY --from=frontend dist/ → /app/static/`

### 4. No changes to
- All API routes (`routes/*.py`)
- All React pages and components
- WebSocket endpoint
- Docker port (8001)
- Authentication/CORS/rate-limit middleware

## Implementation Steps

1. Build React frontend and verify it works
2. Modify `app.py`: remove inline HTML, add static file serving + SPA fallback
3. Update `Dockerfile.dashboard` to multi-stage build
4. Rebuild and restart Docker container
5. Verify all pages work through Docker
