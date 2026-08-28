# ADR-DEV-003 — Externally-Sourced / LLM-Derived Value: Capture, Staleness, and Re-Authoring

**ADR ID:** ADR-DEV-003
**Title:** Externally-Sourced / LLM-Derived Value — Capture, Staleness, and Re-Authoring
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-008 — Strategy DSL (with RFC-009 — Agent Guide)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-008 §14 Q3 (staleness/side-channel clause) and RFC-009 §14 Q6
**Date:** 2026-07-16
**Version:** 0.2 Review Draft
**Last Updated:** 2026-07-17
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

An externally-sourced or LLM-derived value a strategy consumes SHALL be governed as a
captured Critical Input with a bounded staleness discipline:

* **Captured, not called.** It is produced *outside and before* DSL evaluation and
  delivered into the Decision Context Capsule as Critical Input, with its provenance,
  seed, and captured response recorded; DSL evaluation performs no live fetch (RFC-008
  §9, §11 items 12/17; ADR-DEV-001 DCE-INV-003; RFC-009 §9).
* **Staleness is bounded and restrictive.** Each captured value carries an explicit
  validity/currentness window; beyond it the value is `STALE` and blocks new risk in its
  dependency closure — a TTL, cache, or last-known-good never converts staleness into
  permission (ADR-002-018 CII-INV-005/006).
* **Stale requires re-authoring, not reuse.** A stale value is re-captured as a new
  Critical Input; where it is a configuration binding, re-authoring is a Versioned
  Substitution producing a new Artifact Identity (ADR-DEV-004; ADR-DEV-002).
* **Correction invalidates.** A material correction or source-continuity change to the
  source invalidates the captured value and every dependent artifact before new-risk
  transmission (ADR-002-018 CII-INV-008).

This closes the staleness and no-live-side-channel clause of RFC-008 §14 Q3 and the
staleness/re-authoring question of RFC-009 §14 Q6. It defines no Critical Input
currentness *mechanism* — that remains owned by ADR-002-018 (and per-send ordering by
ADR-002-024). It grants no authority and authorizes no live operation.

---

## 2. Context

RFC-008 §9 already requires a stochastic or externally-sourced value (a Monte Carlo
estimate, an LLM-derived interpretation) to be "produced outside and before DSL
evaluation and delivered into the Decision Context Capsule as Critical Input … together
with its seed and recorded response," so DSL evaluation "reads the captured value … and
never reaches a network, model endpoint, or other ambient source." ADR-DEV-001
(DCE-INV-003) makes a live fetch during evaluation unexpressible. RFC-009 §9 says the
authoring pipeline records the seed and response.

What remains open (RFC-008 §14 Q3, RFC-009 §14 Q6) is the *staleness* discipline between
authoring time and runtime: how long a captured value stays valid, what happens when it
goes stale, and how it is re-authored — so it "remains reproducible and cannot become a
live side channel." ADR-002-018 already governs Critical Input freshness, staleness, and
correction/invalidation (CII-INV-005/006/008) and defines the
`STALE`/`UNKNOWN`/`CONFLICTED`/`INVALID` states. This ADR binds the external-value authoring discipline to that
governance; it defines none of the Critical Input mechanism.

---

## 3. Decision Drivers

1. **A live fetch during evaluation is a prohibited side channel** — it breaks purity,
   reproducibility, and containment (RFC-008 §9, §11 items 12/17; DCE-INV-003).
2. **A stale external value is uncertainty, and uncertainty is restrictive** — it must
   never default to a permissive value (ADR-002-018 CII-INV-005; philosophy §8).
3. **Silent reuse hides staleness.** A TTL or cache that keeps serving an expired value
   converts staleness into false permission (ADR-002-018 line 27).
4. **A refreshed value is a new input.** Re-authoring, not in-place mutation, keeps the
   record and identity honest (ADR-DEV-002, ADR-DEV-004).
5. **Corrections must fan out.** A retracted or corrected source value must invalidate
   what depended on it before it can move capital (ADR-002-018 CII-INV-008).

---

## 4. Scope and Non-Scope

**In scope:**

* the capture-before-evaluation discipline for externally-sourced / LLM-derived values;
* the staleness bound and its restrictive effect;
* the re-authoring (not reuse) obligation when a value goes stale;
* correction/invalidation fan-out for such values.

**Not in scope (owned elsewhere):**

* the Critical Input classification, freshness, currentness, and invalidation *mechanism*
  — ADR-002-018; per-send ordering — ADR-002-024;
* the Decision Context Capsule contract — ADR-002-018;
* reproducibility/identity granularity of the captured value — ADR-DEV-002;
* the provenance record of the authoring act that captured the value — ADR-DEV-004;
* the DSL's no-live-fetch enforcement — ADR-DEV-001;
* concrete validity windows and thresholds, which are approved configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-008 §5, RFC-009 §5, and ADR-002-018
(**Critical Input**, **Snapshot**, **Decision Context Capsule**,
`STALE`/`UNKNOWN`/`CONFLICTED`/`INVALID`), and SHALL NOT introduce synonyms. The following terms are scoped to this
decision and are non-authorizing.

* **External Value** — an externally-sourced or model-/LLM-derived value an Authored
  Strategy consumes as evidence (for example a model-derived parameter or an LLM
  interpretation). It is Critical Input regardless of what the DSL calls it (RFC-008 §10;
  ADR-002-018 §1).
* **Capture** — the production of an External Value outside and before DSL evaluation and
  its delivery into the Capsule as Critical Input with provenance, seed, and response
  (RFC-008 §9).
* **Validity Window** — the explicit currentness bound, measured from the value's
  as-of/production time, within which a captured External Value may be used for new
  risk; beyond it the value is `STALE`. It is an external-value-scoped *alias* (not a new
  synonym) for the ADR-002-018 currentness/maximum-age bound (CII-INV-006) and introduces
  no new mechanism.
* **Re-Authoring** — replacing a stale captured External Value with a freshly captured
  one as a new Critical Input, never an in-place mutation (ADR-DEV-004).

These terms describe an authoring-and-staleness discipline. None grants authority or
defines Critical Input governance.

---

## 6. Safety Invariants

* **EXV-INV-001 — Captured, Not Called.** An External Value SHALL be produced before
  evaluation and delivered through the Capsule as Critical Input; DSL evaluation performs
  no live fetch of it (RFC-008 §9, §11 items 12/17; ADR-DEV-001 DCE-INV-003; RFC-009 §9).
* **EXV-INV-002 — Staleness Is Bounded and Restrictive, Anchored to Production Time.**
  Each captured External Value carries an explicit Validity Window **anchored to the
  value's recorded as-of/production time** (its capture provenance under ADR-002-018 and
  §7 — this ADR owns the external-value as-of record; it is not a field of the ADR-DEV-004
  authored-artifact minimum record), not to the time it is placed in a Capsule; re-wrapping a value in a newer Capsule SHALL NOT
  reset its currentness. Once `STALE` — past the window measured from its production
  time — it blocks new risk in its dependency closure; a TTL, cache, or last-known-good
  does not convert staleness into permission (ADR-002-018 CII-INV-005/006). An External
  Value with no positively-established Validity Window is `UNKNOWN` and blocks new risk
  (ADR-002-018 CII-INV-005/006); staleness cannot be escaped by omitting the window. The
  Validity Window SHALL further be **adequate** to the source's actual currentness
  characteristics: a window that merely exists and is honored is insufficient if it exceeds
  the source's real freshness. Adequacy of the currentness bound is owned by ADR-002-018
  (CII-INV-005/006); this ADR requires that the captured External Value's window not exceed it.
* **EXV-INV-003 — Stale Requires Re-Authoring, Not Reuse.** A stale External Value SHALL
  be re-captured as a new Critical Input; where it is a configuration binding,
  Re-Authoring is a Versioned Substitution producing a new Artifact Identity (ADR-DEV-004
  APA-INV-005; ADR-DEV-002 ARI-INV-001).
* **EXV-INV-004 — Correction Invalidates.** A material correction, retraction, or
  source-continuity change to the source SHALL invalidate the captured value and every
  dependent Snapshot, Capsule, and proposal before new-risk transmission (ADR-002-018
  CII-INV-008).
* **EXV-INV-005 — Captured Value Is in the Recorded Input Set.** The captured value, its
  provenance, seed, and response are part of the Recorded Input Set, so the outcome
  remains reproducible; the value is evidence, never authority (ADR-DEV-002 ARI-INV-003;
  RFC-008 §9).
* **EXV-INV-006 — Governance Is Owned Upstream.** The Critical Input classification,
  currentness, and invalidation mechanism is owned by ADR-002-018 (and per-send ordering
  by ADR-002-024); this ADR fixes only the external-value authoring-and-staleness
  discipline and defines none of that mechanism.

---

## 7. Capture Before Evaluation

An External Value SHALL be captured, never fetched live (EXV-INV-001):

* it is produced by the authoring pipeline or an upstream service *before* evaluation and
  delivered into the Capsule as Critical Input (RFC-008 §9; RFC-009 §9);
* DSL evaluation reads only the captured value; it reaches no network, model endpoint,
  clock, or other ambient source — a live fetch is unexpressible (ADR-DEV-001
  DCE-INV-003) and would be a prohibited side channel (RFC-008 §11 items 12, 17);
* the value's provenance, seed, and captured response are recorded, both as Authoring
  Provenance (ADR-DEV-004) and as part of the Recorded Input Set (ADR-DEV-002), so the
  outcome reproduces without any live call (EXV-INV-005).

Capture is what turns an inherently live, non-reproducible source into a fixed,
reviewable, replayable input.

---

## 8. Staleness and Re-Authoring

A captured External Value is fresh only within its Validity Window (EXV-INV-002, -003):

* the window is measured from the External Value's recorded as-of/production time
  (its capture provenance under ADR-002-018 and §7), never from the time the value is
  wrapped into a
  Capsule; re-delivering an authoring-time value in a fresh Capsule does not reset its
  currentness — otherwise a value produced once could read fresh forever, defeating the
  discipline this ADR exists to enforce;
* the window is an explicit currentness bound; beyond it the value is `STALE` and blocks
  new risk in its dependency closure (ADR-002-018 CII-INV-005/006). Absence of a
  correction, a cache hit, a heartbeat, or an unexpired TTL is not freshness (ADR-002-018
  line 27). A value with no positively-established window is `UNKNOWN` and blocks new
  risk — omitting the window is not a way to escape staleness; and the window SHALL be
  *adequate* to the source's real currentness (owned by ADR-002-018 CII-INV-005/006) — a
  window longer than the source's actual freshness does not make a stale value fresh;
* a stale value SHALL be **re-authored** — re-captured as a new Critical Input — never
  silently reused. Where the value is a configuration binding of the Authored Strategy,
  Re-Authoring is a Versioned Substitution producing a new Artifact Identity and a new
  admission candidate (ADR-DEV-004 APA-INV-005; ADR-DEV-002);
* a material correction or source-continuity change invalidates the captured value and
  its dependents before any new-risk send (EXV-INV-004; ADR-002-018 CII-INV-008), and
  never expires exposure or capacity already capable of economic effect (ADR-002-018
  CII-INV-009);
* under staleness the strategy's conforming outcomes narrow (more conservative or
  no-action); staleness never widens the action set (RFC-008 §10; ADR-DEV-008
  DCM-INV-001 where the stale value is a companion-model output).

Staleness is treated as uncertainty, and uncertainty restricts — the value is refreshed
by re-authoring, not extended by reuse.

---

## 9. Alternatives Considered

* **9.1 Allow a live fetch during evaluation for freshness.** Rejected: a live fetch is a
  prohibited side channel that breaks purity, reproducibility, and containment (RFC-008
  §9, §11; DCE-INV-003).
* **9.2 Serve a stale value via TTL/cache until refreshed.** Rejected: that converts
  staleness into permission (ADR-002-018 CII-INV-005; EXV-INV-002).
* **9.3 Refresh a value in place under the same identity.** Rejected: an in-place mutation
  hides the change and breaks the record/identity; refresh is Re-Authoring (EXV-INV-003;
  ADR-DEV-004 APA-INV-005).
* **9.4 Treat a source correction as non-material unless proven material.** Rejected:
  unknown materiality is treated as material (ADR-002-018 §1 with §5.8; EXV-INV-004).
* **9.5 Define Critical Input currentness here.** Rejected: owned by ADR-002-018/024;
  duplicating it would create a divergent protocol (EXV-INV-006).

---

## 10. Consequences

**Positive.**

* Closes the live-side-channel and staleness edges of RFC-008 §14 Q3 / RFC-009 §14 Q6 on
  the existing Critical Input governance, without a new mechanism.
* Re-authoring keeps the record, identity, and replay honest across refreshes.
* Stale-is-restrictive fails closed on uncertainty.

**Negative / costs.**

* Every External Value needs an explicit Validity Window and a re-authoring path — more
  authoring-pipeline and configuration work.
* A stale configuration-bound value forces a Versioned Substitution and re-admission
  rather than a cheap refresh.
* Correction fan-out must reach every dependent artifact, which the authoring pipeline
  must support.

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Silent stale reuse.** A pipeline serves an expired value; forbidden by
  EXV-INV-002, surfaced when the `STALE` state blocks new risk (ADR-002-018).
* **11.2 In-place refresh.** A value refreshed under the same identity escapes review;
  prevented by EXV-INV-003 (Re-Authoring = new identity).
* **11.3 Missed correction.** A source correction does not invalidate dependents;
  contained by EXV-INV-004 and ADR-002-018 CII-INV-008, but a fan-out gap is a process
  risk owned by ADR-002-018.
* **11.4 Live-fetch smuggling.** An author routes a "feature" as a live call; unexpressible
  by DCE-INV-003 and caught by the containment suite (RFC-010 §8) via the ADR-DEV-009
  minimum-set ambient/network vector.

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **12.1** An External Value is captured before evaluation and no live fetch occurs during
  evaluation (EXV-INV-001; overlaps the ADR-DEV-009 ambient/network vector).
* **12.2** A value past its Validity Window is `STALE` and blocks new risk; no TTL/cache/
  last-known-good grants permission (EXV-INV-002).
* **12.3** A stale value is re-authored as a new Critical Input; a stale configuration
  binding yields a new Artifact Identity (EXV-INV-003).
* **12.4** A material source correction invalidates the captured value and dependents
  before new-risk transmission (EXV-INV-004).
* **12.5** The captured value and its seed/response reproduce the outcome from the Recorded
  Input Set (EXV-INV-005; ADR-DEV-002 §13.1).
* **12.6** An authoring-time value re-delivered in a newer Capsule, past its Validity
  Window measured from its production time, is `STALE`; and a value with no
  positively-established window is `UNKNOWN` — re-wrapping in a fresh Capsule does not
  reset currentness (EXV-INV-002).

---

## 13. Acceptance Criteria

ADR-DEV-003 is acceptable when:

* External Values are captured before evaluation with no live fetch (EXV-INV-001);
* staleness is bounded, restrictive, and never permissively reused (EXV-INV-002);
* stale values are re-authored, not reused, with identity consequences (EXV-INV-003);
* corrections invalidate dependents before new risk (EXV-INV-004);
* the captured value is a reproducible Recorded Input, evidence not authority (EXV-INV-005),
  and the Critical Input mechanism stays owned by ADR-002-018 (EXV-INV-006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-003 |
|---|---|
| RFC-008 §14 Q3 (staleness; no live side channel; reproducible) | capture-before-eval, staleness-restrictive, re-authoring (§§7, 8; EXV-INV-001/002/003) |
| RFC-009 §14 Q6 (staleness/re-authoring between authoring and runtime) | Validity Window + Re-Authoring (§8; EXV-INV-002/003) |
| RFC-008 §9 (captured before eval; seed/response recorded) | Capture with recorded provenance (§7; EXV-INV-001/005) |
| RFC-008 §11 items 12/17 (no ambient; no escape) | no live fetch (EXV-INV-001); ADR-DEV-001 DCE-INV-003 |
| RFC-009 §9 (external material captured, not called) | EXV-INV-001 |
| ADR-002-018 CII-INV-005/006 (ambiguity restrictive; freshness) | staleness bounded and restrictive (§8; EXV-INV-002) |
| ADR-002-018 CII-INV-008/009 (correction invalidates; effect outlives context) | correction fan-out; effect not expired (§8; EXV-INV-004) |
| ADR-002-024 (per-send currentness ordering) | mechanism deferred (EXV-INV-006) |
| ADR-DEV-001 DCE-INV-003 (no live fetch) | live fetch unexpressible (§7) |
| ADR-DEV-002 ARI-INV-001/003 (identity; recorded inputs) | re-authoring = new identity; captured value in Recorded Input Set (§8; EXV-INV-003/005) |
| ADR-DEV-004 APA-INV-005 (versioned substitution) | stale config-bound value → new identity/generation (EXV-INV-003) |
| philosophy §8 | uncertainty restrictive (§3) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
external-value authoring-and-staleness discipline and relies on ADR-002-018/024 for
Critical Input governance.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-003, resolving the staleness/side-channel clause of RFC-008 §14 Q3
  and RFC-009 §14 Q6.
* Set the decision: an External Value is captured before evaluation (never fetched live),
  bounded by a Validity Window beyond which it is `STALE` and restrictive, re-authored
  (not reused) when stale, and invalidated on source correction — all on the existing
  ADR-002-018 Critical Input governance.
* Defined six invariants EXV-INV-001…006 and traced them to RFC-008 §9/§10/§11,
  RFC-009 §9, ADR-002-018 (CII-INV-005/006/008/009), ADR-002-024, and
  ADR-DEV-001/002/004.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; all twelve attack sequences were blocked or correctly deferred and
  every citation verified. One Major finding was resolved: RFC-009 §14 Q6 is a
  two-timestamp problem (produce-at-authoring vs. wrap-at-runtime) and the Validity
  Window's anchor instant was unspecified, so an old authoring-time value re-wrapped in
  a fresh Capsule each cycle could read fresh forever — EXV-INV-002 and §8 now anchor the
  window to the value's recorded as-of/production time (Authoring Provenance,
  ADR-DEV-004), not the Capsule wrap time, with a §12.6 demonstration. Five Minor fixes:
  a missing Validity Window is now `UNKNOWN` and restrictive (fail-closed); the Validity
  Window is stated to be the external-value-scoped name for the ADR-002-018 currentness
  bound (no new synonym); the state enumeration now includes `CONFLICTED`; the §9.4
  materiality citation points to ADR-002-018 §1 (with §5.8); and the RFC-009 §14 Q6
  back-annotation was already added. The review is EV-L0 only and confers no acceptance
  or live-readiness.

### v0.2 — Wave 7 (CORPUS-REVIEW-0001 mn-11)

* Added an *adequacy* requirement to EXV-INV-002 (§6) and §8: the External Value's Validity
  Window SHALL be adequate to the source's actual currentness characteristics — a window that
  merely exists and is honored is insufficient if it exceeds the source's real freshness.
  Adequacy of the currentness bound is owned by ADR-002-018 (CII-INV-005/006); this ADR
  requires only that the captured value's window not exceed it. Narrow-only and additive; no
  SAFE-xxx, no numeric bound, no new EXV-INV or EV. Independent EV-L0 review is owed, with
  reviewer provenance recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).
