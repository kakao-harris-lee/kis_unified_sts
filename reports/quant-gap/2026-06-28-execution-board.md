# Quant Gap Execution Board - 2026-06-28

## Review Cadence

- Daily review: 08:20 KST before futures/stock regular sessions.
- End-of-day evidence review: 16:30 KST after stock close and futures regular close.
- Live-gate decisions require explicit operator approval in writing.

## Decision Gates

| Gate | Owner | Required Input | Decision | Status |
|---|---|---|---|---|
| G0 Stock venue policy | Market-structure policy expert | KRX-only vs ATS/SOR memo | Pending | Open |
| G1 Futures session policy | Market-structure policy expert | 08:45 regular + night session policy | Pending | Open |
| G2 Futures product policy | Futures platform engineer | Mini vs full KOSPI 200 contract policy | Pending | Open |
| G3 Setup C/D promotion evidence | Futures strategy researcher | Paper evidence reports | Pending | Open |
| G4 Stock strategy/theme evidence | Stock strategy + theme researcher | Readiness and theme quality reports | Pending | Open |

## Active Lanes

| Lane | Expert | Status | Blocked By | Next Evidence |
|---|---|---|---|---|
| 1 Market structure policy | Unassigned | Open | None | Policy memo |
| 2 Futures platform | Unassigned | Open | G1, G2 | Contract tests |
| 3 Futures strategy evidence | Unassigned | Open | None | Setup C/D reports |
| 4 Stock venue / ATS | Unassigned | Open | G0 | SOR or KRX-only implementation note |
| 5 Stock strategy / theme | Unassigned | Open | None | Strategy and theme quality reports |
| 6 Workbench evidence UX | Unassigned | Open | Report schemas from lanes 3/5 | Dashboard contract |
| 7 Ops/QA | Unassigned | Open | Lanes 1-6 | Verification bundle |

## Evidence Links

- Gap research: `docs/investigations/2026-06-28-quant-system-gap-research.md`
- Roadmap: `docs/ROADMAP.md`
- Runtime status: `docs/PROJECT_STATUS.md`
