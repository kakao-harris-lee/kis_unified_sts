# Quant Gap Execution Board - 2026-06-28

## Review Cadence

- Daily review: 08:20 KST before futures/stock regular sessions.
- End-of-day evidence review: 16:30 KST after stock close and futures regular close.
- Live-gate decisions require explicit operator approval in writing.

## Decision Gates

| Gate | Owner | Required Input | Decision | Status |
|---|---|---|---|---|
| G0 Stock venue policy | Market-structure policy expert | KRX-only vs ATS/SOR memo | KRX-only until explicit ATS/SOR approval | Verified 2026-06-28 |
| G1 Futures session policy | Market-structure policy expert | 08:45 regular + night session policy | Keep 09:00 regular-session default; keep night disabled | Verified 2026-06-28 |
| G2 Futures product policy | Futures platform engineer | Mini vs full KOSPI 200 contract policy | Product/symbol/tick-size contract tooling validated; Mini vs full promotion policy remains pending operator decision | Tooling verified; policy pending |
| G3 Setup C/D promotion evidence | Futures strategy researcher | Paper evidence reports | Evidence observers validated; real paper evidence still required | Verified 2026-06-28 |
| G4 Stock strategy/theme evidence | Stock strategy + theme researcher | Readiness and theme quality reports | Theme/fusion quality tooling validated; real operator evidence still required | Verified 2026-06-28 |

## Active Lanes

| Lane | Expert | Status | Blocked By | Next Evidence |
|---|---|---|---|---|
| 1 Market structure policy | Market-structure policy expert | Complete | None | `docs/runbooks/market-structure-policy.md` |
| 2 Futures platform | Futures platform engineer | Tooling complete | Operator product policy | Focused product/session contract pytest bundle; Mini vs full promotion decision still pending |
| 3 Futures strategy evidence | Futures strategy researcher | Complete | None | Setup C/D observer and evidence-bundle tests |
| 4 Stock venue / ATS | Stock venue / ATS engineer | Complete | None | KRX-only policy and ATS-routing integration test |
| 5 Stock strategy / theme | Stock strategy + theme researcher | Complete | None | Theme/fusion quality-report tests |
| 6 Workbench evidence UX | Workbench UX/observability engineer | Complete | None | `/evidence` backend/frontend verification |
| 7 Ops/QA | Ops/QA lead | Complete | None | `docs/testing/quant-gap-execution-2026-06-28.md` |

## Evidence Links

- Gap research: `docs/investigations/2026-06-28-quant-system-gap-research.md`
- Roadmap: `docs/ROADMAP.md`
- Runtime status: `docs/PROJECT_STATUS.md`
- Final QA evidence: `docs/testing/quant-gap-execution-2026-06-28.md`
