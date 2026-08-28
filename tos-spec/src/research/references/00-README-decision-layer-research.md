# Decision-Layer Research References (RFC-003 – RFC-007)

> **NON-NORMATIVE — RESEARCH INPUT ONLY.**
> These documents are background/grounding material to inform the *future*
> authoring of the part-2 decision-layer specifications (RFC-003 Decision
> Framework, RFC-004 Market Model, RFC-005 Execution Model, RFC-006 Risk Model,
> RFC-007 Portfolio Hedge Model). They are **not** ratified specification, define
> **no** requirements, grant **no** authority, and make **no** normative
> decision. Nothing here promotes any status or licenses any implementation.
> When a part-2 RFC is eventually written, it — not these notes — is canonical.

## Why these exist

As of 2026-07-14, all five part-2 files
(`src/part-2-decision/RFC-003..007-*.md`) are **empty 0-byte stubs**, already
listed in `src/SUMMARY.md`. A request to "start part-2 first" was assessed and
**deliberately deferred** for two reasons found during investigation:

1. **The foundation layer is still growing.** `RFC-002-Architecture.md` already
   references decisions through **ADR-002-029** (software supply chain), and the
   Evidence Register carries **351 `NOT_IMPLEMENTED`** items. Fixing a layer that
   sits *on top* of a still-moving foundation would invite rework.
2. **The decision layer's contract is already heavily constrained** by ratified
   constitution (RFC-000), the drafted Safety Case (RFC-001), and drafted
   architecture (RFC-002 + ADRs). Authoring RFC-003–007 without first
   consolidating those constraints risks contradicting an existing gate.

So instead of drafting, this folder captures the grounding needed for accurate
future authoring.

## Contents

| File | Covers |
|---|---|
| `10-upstream-constraints-dossier.md` | What part-0/part-1 already say/imply that constrains the decision layer: intended role, the `Intent` object, inputs, the decision↔safety boundary (the load-bearing section), per-RFC upstream mapping, canonical terminology, and explicit research gaps. All claims cited to `file.md §section`/line. |
| `20-external-domain-survey.md` | Literature/practice survey for the five topics (decision framework, market microstructure, execution/TCA, risk measures, index-futures hedging), with citations and KRX/KOSPI200/KIS-specific notes. Includes a citation-verification-status table. |
| `30-per-rfc-starting-points.md` | Consolidated per-RFC (003–007) starting-point notes: the exact upstream sections/ADRs each future RFC must honor, the nearest existing architectural anchor, and the open questions to resolve — synthesizing the two sources above into an author-facing checklist. |

## Load-bearing findings (read these first)

- **The decision layer is a *proposer*, not an authority.** RFC-000 §9 fixes the
  layering `Constitution → Safety Case → Architecture RFCs → Decision Framework →
  Implementation`; RFC-002 §10.2 forbids the Decision Service from approving,
  transmitting, reserving capacity, or modifying safety config. RFC-003–007
  occupy only the "Decision Service" policy-authority role.
- **The pipeline is immutable.** RFC-000 §10 fixes
  `Observation → Context Construction → Interpretation → Decision → Approval →
  Execution → Audit`. The decision layer governs `Interpretation → Decision` and
  hands off to a separately-owned `Approval`.
- **`Intent` is not owned by the decision layer.** A proposal becomes an `Intent`
  only through ADR-002-023 (independent approval) + the Intent Registry; the
  binding Intent contract is ADR-002-020 §8.
- **Nearest existing anchors already exist** and must not be duplicated or
  weakened: RFC-006 ↔ ADR-002-021 (aggregate risk); RFC-007 ↔ ADR-002-001 /
  ADR-002-011 (protective capacity / replacement); RFC-005 ↔ ADR-002-020 /
  ADR-002-002 / ADR-002-022 / ADR-002-024; RFC-004 ↔ ADR-002-018 / ADR-002-019
  (Critical Input / venue-session).

## Known upstream gaps to carry forward (do NOT silently "fix")

These are pre-existing inconsistencies in part-0/part-1, verified against the
files. A future RFC author should route any correction through governance, not
patch them implicitly:

1. **`DEC-003` is a dangling traceability target** — referenced at
   `RFC-000-Trading-Constitution.md:747` (CONST-007 derived requirements) but
   defined nowhere; the `DEC-xxx` namespace does not exist in the corpus.
2. **CONST-002 (Capital Preservation) traceability omits RFC-006** even though
   capital preservation is semantically a risk-model concern (a reviewer already
   flagged this).
3. **CONST-003 (Positive Expectancy) is explicitly `NOT DISCHARGED BY RFC-001`**
   (`RFC-001-Safety-Case.md:1769`) and delegated to the Decision Framework —
   RFC-003/006 inherit that entire unmet obligation.
4. **No RFC-002 component is named "Market/Risk/Hedge Model" or "Decision
   Framework."** The decision layer's internal reasoning engine is an open
   architectural canvas *within* the Decision Service contract (RFC-002 §10.2).

## Provenance

Produced 2026-07-14 from two parallel research passes (one internal-corpus
grounding pass over part-0/part-1, one external literature survey). Numeric
Korean-market parameters (price limits, VI thresholds, tick bands, futures
price-limit bands) are **living values**: pull from KRX's current published
rulebook at spec-finalization time rather than trusting any figure quoted here.
