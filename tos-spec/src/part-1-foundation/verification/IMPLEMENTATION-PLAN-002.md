# IMPLEMENTATION-PLAN-002 — Safety Architecture Implementation & Verification Plan

- **Status:** PROPOSED PLAN — not approved; no implementation code has been written.
- **Date:** 2026-07-13
- **Covers:** ARCHITECTURE-GATE-STATUS §6 steps 3–11 (implementation, fault injection, evidence execution, independent review).
- **Governed by:** RFC-000, RFC-001, RFC-002 v0.2, ADR-002-001..004, VER-002-001.
- **Authorization:** This plan authorizes nothing. Production, live, and ADR-Accepted status remain NO.

---

## 0. Why this is a plan and not code

The remaining gate steps cannot be executed unilaterally without defeating the
safety model they implement:

- numeric bounds require **human approval** (VER-002-001 §6; separation of duties);
- owners and the **independent reviewer** must be assigned — the reviewer SHALL NOT
  be the author/integrator of this architecture (RFC-001 §11.4);
- implementation must follow **plan-first** approval (project workflow);
- EV-L1..L3 evidence cannot be "declared" — it must be produced by real tests,
  fault injection, and captured artifacts (VER-002-001 §5, ARCHITECTURE-GATE-STATUS §5);
- EV-L4 needs a **KIS sandbox**; EV-L5/L6 need production authority that does not exist.

This document exists so those gates are explicit and ratifiable, not bypassed.

---

## 1. Phase 0 — Blocking human inputs (required before Phase 1 code)

| Input | Owner | Why it blocks |
|---|---|---|
| Approve/replace bounds in `VERIFICATION-PROFILE-002.yaml` | Safety/Risk authority | Tests need pass/fail thresholds; unapproved bounds are not bounds |
| Measure broker-specific bounds from a KIS Capability Profile | Broker/Exec eng | `B_final_quantity_proof`, `B_late_fill_observation`, rate/session, query consistency |
| Assign implementation owner + evidence owner + **independent reviewer** per evidence item | System owner | `EVIDENCE-REGISTER-002.csv` (67 items); independence is mandatory |
| Approve this plan and the scoping decision (§2) | Architecture board | Determines what code is written and where |

I will not fabricate any of these. I can *draft candidates* (done for bounds; role scheme in §3) for you to ratify.

---

## 2. Scoping decision required first

RFC-002's components (Risk Capacity Ledger, Safety Authority, Broker Adapter/egress,
Reconciliation, Recovery Coordinator, Protective Action Controller, Safety Profile
Validator) must be reconciled with the **existing `kis_unified_sts` code**, which
already has overlapping pieces: `shared/execution/` (executor, venue_router,
rate_limiter, pseudo_oco, live_mode_guard), `services/order_router`, `services/risk_filter`,
`services/kill_switch`, `shared/kis/` (auth/client/token).

**Decision needed:** (A) build the TOS safety core as a **new subsystem** that the
existing pipeline is migrated onto, or (B) **refactor** the existing execution/risk/
kill-switch modules to satisfy the ADRs in place. This is an architecture-board call
and changes the plan materially. Recommendation: a thin **new** Risk Capacity Ledger +
Safety Authority + egress gate (they have no adequate equivalent today), while
*mapping* existing executor/venue_router/rate_limiter behind the new egress boundary.

---

## 3. Proposed roles & separation of duties (draft — assign real people)

Role placeholders for `EVIDENCE-REGISTER-002`; a single person may hold several,
subject to the exclusions:

- **RC-Impl / SA-Impl / BC-Impl** — implement Risk Capacity, Safety Authority, Broker layers.
- **Harness-Eng** — deterministic fault injection + evidence capture.
- **Evidence-Owner** — runs a case, produces the manifest + artifacts.
- **Independent-Safety-Reviewer** — signs evidence; MUST NOT be any Impl role or the architecture author.
- **Bounds-Approver** — ratifies `VERIFICATION-PROFILE-002`; MUST NOT arm live trading.
- **Live-Armer** — separate identity; MUST NOT enlarge limits (ADR-002-002 §29.3).

Exclusions (hard): Impl ≠ Independent-Reviewer; Bounds-Approver ≠ Live-Armer; author/integrator of RFC-002/ADRs ≠ Independent-Reviewer.

---

## 4. Phased implementation → evidence

Each phase gates the next. No phase claims completion without the VER-002-001 evidence.

### Phase 1 — Model & property verification (EV-L1)
- Implement the **capacity state machine** (ADR-002-002 §10: COMMITTED_UNBOUND … RELEASED)
  and **authority epoch/lease** model (ADR-002-003) as pure, non-transmitting models.
- Property/model tests for INV-001..012 and AC-001..018 (concurrency, crash points,
  cancel-crossing-fill, replace overlap, TTL, UNKNOWN, protective lease partition).
- Deliverable: EV-L1 evidence for RC-EV/SA-EV items marked EV-L1-reachable.

### Phase 2 — Component fault tests (EV-L2)
- Durable **single-writer Risk Capacity Ledger** with compare-and-set + monotonic
  fencing epoch; **Safety Authority epoch registry**; durable evidence identities +
  write-ahead `SEND_STARTED`.
- Component-level fault injection (missing input, stale epoch, crash-at-boundary).
- Deliverable: EV-L2 evidence (e.g., RC-EV-009, RC-EV-018, SA-EV-005/015).

### Phase 3 — Integrated system fault tests (EV-L3)
- Wire the **final broker-egress gate** (Transmission Capability validation) in front
  of a *simulated* broker; real persistence + network boundaries; duplicate-instance /
  split-brain / partition / restart harness.
- Execute the EV-L3 RC-EV / SA-EV set; measure `B_*` bounds against `VERIFICATION-PROFILE-002`.
- Deliverable: EV-L3 evidence; measured detection/containment bounds.

### Phase 4 — Broker Capability Profile & sandbox (EV-L4)
- Complete the first **KIS Broker Capability Profile** (`BROKER-CAPABILITY-PROFILE-template.yaml`):
  order identity/idempotency, cancel semantics, query completeness, rate/session, late-fill.
- KIS **sandbox** probes; derive broker-specific bounds; run BC-EV items.
- Deliverable: EV-L4 evidence + a versioned Capability Profile.

### Phase 5 — Independent review & ADR re-evaluation
- **Independent** reviewer (not me, not an Impl role) signs each evidence run.
- Only then may ADR-002-001..004 be re-evaluated toward `Accepted`, and only within the
  proven scope. Restricted live (EV-L5) is a separate, later, human-authorized gate.

---

## 5. What I will do vs. will not do

**Will do (on your go):** write Phase 1–3 code and harness in this repo per the approved
scoping decision; keep everything non-transmitting/simulated; produce EV-L1..L3 evidence
artifacts; keep status Proposed.

**Will not do (safety model forbids):** approve bounds; assign real owners or sign as the
independent reviewer; execute against a live KIS account; declare any ADR Accepted; write
implementation code before this plan and the scoping decision are approved.

---

## 6. Immediate decision requested

1. Approve (or amend) `VERIFICATION-PROFILE-002.yaml` proposed bounds, and provide the KIS-measured ones.
2. Choose the scoping option in §2 (new subsystem vs. refactor).
3. Approve this plan so Phase 1 (EV-L1 models + property tests, non-transmitting) can begin.
4. Name the independent reviewer (or confirm it is external to this work).
