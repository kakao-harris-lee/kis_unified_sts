# ADR-DEV-012 — Re-Arm Reconciled-State Checklist and Barrier Binding

**ADR ID:** ADR-DEV-012
**Title:** Re-Arm Reconciled-State Checklist and Barrier Binding
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-011 — Operational Guidelines (with ADR-002-007 and ADR-002-017)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-011 §14 Q1
**Date:** 2026-07-16
**Version:** 0.3 Review Draft
**Last Updated:** 2026-07-17
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

Before requesting a Re-arm Decision, an operator SHALL confirm a **minimum
reconciled-state checklist**: valid configuration, trustworthy time, valid Live
Authorization, reconciled positions, reconciled open orders, valid safety authority,
known aggregate risk, a single active instance, and reconciled account/venue/critical-
input state (Vision §7.4; RFC-011 §10; ADR-002-017). If any item is `UNKNOWN` or
unreconciled, the operator SHALL **withhold** the request. The checklist is the
operator-facing precondition for *requesting* re-arm; it is **not** the Re-arm Decision
(owned by ADR-002-007) and it does **not** lower or replace the **recovery barrier**
owned by ADR-002-017 (Readiness Is Not Authority; Start Closed). Confirming the
checklist is necessary operator evidence toward re-arm; it grants no authority.

This ADR grants no authority, issues no live authorization, and re-arms nothing.

---

## 2. Context

RFC-011 §10 makes re-arming an explicit human Re-arm Decision, withheld until its
prerequisites hold, and lists them (from Vision §7.4): "valid configuration,
trustworthy time, live authorization, reconciled positions, reconciled open orders,
valid safety authority, and known aggregate risk," plus resolving any possible
duplicate-instance or unknown-order condition. RFC-002 §4.7 forbids recovery from
automatically restoring live authority, and §9.1 bars non-owners (operator, dashboard,
evidence) from re-arming.
ADR-002-007 owns the live-authorization and re-arm mechanism; ADR-002-017 owns the safe
startup, recovery barrier, and conservative resume (Start Closed, Restriction Before
Observation, Readiness Is Not Authority, No Snapshot Optimism, Complete Economic
Inventory, UNKNOWN Remains Conservative).

RFC-011 §14 Q1 leaves open the *minimum reconciled-state checklist* an operator must
confirm before requesting a Re-arm Decision, and where that checklist binds relative to
the ADR-002-017 recovery barrier. This ADR fixes the checklist and its binding. It
defines neither the re-arm mechanism (ADR-002-007) nor the recovery barrier
(ADR-002-017) — it fixes the operator discipline that precedes them.

---

## 3. Decision Drivers

1. **Recovery is a new safety decision** (philosophy §23; RFC-002 §4.7). Re-arming
   requires a fresh, positively-established state, not a reversal of failure.
2. **A checklist makes the operator's precondition explicit and auditable** rather than
   trusting judgment under stress (RFC-011 §7; philosophy §22).
3. **Any unreconciled item is restrictive** (philosophy §8; ADR-002-017 SBR-INV-006).
4. **Readiness is not authority** (ADR-002-017 SBR-INV-003). Confirming the checklist
   requests re-arm; it does not grant it or bypass the barrier.
5. **No snapshot optimism** (ADR-002-017 SBR-INV-007). Cached/last-known-good/heartbeat
   state is not reconciliation.

---

## 4. Scope and Non-Scope

**In scope:**

* the minimum reconciled-state checklist the operator confirms before requesting re-arm;
* the withholding rule under any unreconciled item;
* the binding of the checklist relative to the ADR-002-017 recovery barrier and the
  ADR-002-007 re-arm grant.

**Not in scope (owned elsewhere):**

* the Live Authorization and Re-arm mechanism — ADR-002-007;
* the safe-startup, recovery-barrier, conservative-resume mechanics and their
  invariants — ADR-002-017;
* Critical Input reconciliation, freshness, and currentness — ADR-002-018;
* the RCL and aggregate-risk state — ADR-002-002/021;
* human-authority/dual-control mechanics — ADR-002-015;
* concrete reconciliation thresholds and item encodings, which are approved
  configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-011 §5 (**Operator**, **Re-arm Decision**),
RFC-002 §3.1, and the ADR series (ADR-002-017 recovery barrier; ADR-002-007 Live
Authorization), and SHALL NOT introduce synonyms. The following terms are scoped to
this decision and are non-authorizing.

* **Reconciled-State Checklist** — the minimum set of operational-state items an
  operator positively confirms before requesting a Re-arm Decision (§7). Confirming it
  is evidence toward re-arm, not the grant.
* **Withhold** — the conforming operator outcome of not requesting re-arm because a
  checklist item is `UNKNOWN` or unreconciled (RFC-011 §10; represented as a first-class
  outcome by ADR-DEV-014).

These terms describe an operator precondition discipline. None grants authority or
re-arms.

---

## 6. Safety Invariants

* **RRC-INV-001 — Minimum Reconciled-State Checklist.** Before requesting a Re-arm
  Decision the operator SHALL confirm: valid configuration, trustworthy time, valid
  Live Authorization, reconciled positions, reconciled open orders, valid safety
  authority, known aggregate risk, a single active instance, and reconciled
  account/venue/critical-input state (Vision §7.4; RFC-011 §10; RFC-001 SC-040 for the
  reconciliation items; ADR-002-017 SBR-INV-005 for the economic-inventory items).
* **RRC-INV-002 — Any Unreconciled Item Withholds the Request.** If any checklist item
  is `UNKNOWN`, unreconciled, conflicting, stale, or ambiguous, the operator SHALL
  withhold the Re-arm request; a missing or uncertain item narrows, never permits
  (RFC-011 §10; ADR-002-017 SBR-INV-006; philosophy §8).
* **RRC-INV-003 — The Checklist Is Operator Evidence, Not the Grant.** Confirming the
  checklist is necessary evidence toward re-arm; it is not the Re-arm Decision
  (ADR-002-007) and does not lower or replace the recovery barrier (ADR-002-017
  SBR-INV-003, Readiness Is Not Authority).
* **RRC-INV-004 — The Barrier Remains the Enforcement Point.** The recovery barrier and
  prerequisite enforcement are owned by ADR-002-017 (SBR-INV-001 Start Closed,
  SBR-INV-002 Restriction Before Observation); the operator checklist sits *before* it
  and never bypasses it.
* **RRC-INV-005 — Positively Established and Current.** A cached, last-known-good, or
  heartbeat-derived confirmation is not reconciliation; each item is positively
  established **and current at the time of the request** — a real reconciliation that has
  since gone stale does not satisfy it (ADR-002-017 SBR-INV-004 One Current Recovery
  Generation, SBR-INV-007; ADR-002-018).
* **RRC-INV-006 — Checklist Confirmation Grants No Authority.** Completing the checklist
  commits no capacity, issues no Live Authorization, and re-arms nothing (RFC-002 §9.1;
  ADR-002-007).

---

## 7. The Minimum Reconciled-State Checklist (RFC-011 §14 Q1, part 1)

The operator SHALL positively confirm each item before requesting re-arm — no new
exposure may be authorized while any of these is unknown or unreconciled (RFC-001 SC-040)
(RRC-INV-001, -005):

* **valid configuration** — the active configuration is the approved, current one;
* **trustworthy time** — time is valid and trustworthy (ADR-002-008);
* **valid Live Authorization** — a current live-authorization basis/governance exists (not
  an active grant, which re-arm itself issues) (ADR-002-007);
* **reconciled positions** — actual positions are reconciled, not assumed;
* **reconciled open orders** — open and potentially-live orders are reconciled;
* **valid safety authority** — the independent safety authority is present and valid
  (RFC-000 CONST-011);
* **known aggregate risk** — aggregate risk state is known (ADR-002-002/021);
* **single active instance** — no duplicate active instance holds authority (RFC-011
  §10; RFC-001 SC-030);
* **reconciled account/venue/critical-input state** — account, venue, and Critical
  Input state are current and reconciled (ADR-002-018/019).

In addition to the nine reconciliation confirmations above, the operator SHALL confirm one
representation requirement — a complementary check, not a tenth reconciliation item:

* **trapped exposure represented** — any trapped or irreducible exposure is represented at
  full conservative risk and does not release capacity (ADR-002-001 §15; conservative capacity
  consumption enforced by ADR-002-017 SBR-INV-006), and is included in the recovery inventory
  (ADR-002-017 SBR-INV-005, which requires it be included in the recovery inventory); an
  unreconciled or misrepresented trapped exposure withholds the request under RRC-INV-002.

Each item is positively established and current at the time of the request; a cache,
heartbeat, last-known-good, or a once-true-but-now-stale reconciliation does not satisfy
it (RRC-INV-005; ADR-002-017 SBR-INV-004).

---

## 8. Binding to the Barrier and the Grant (RFC-011 §14 Q1, part 2)

The checklist sits before, and never replaces, the owned mechanisms (RRC-INV-003, -004):

* the checklist is the operator's precondition for *requesting* a Re-arm Decision; the
  Re-arm Decision itself is issued by ADR-002-007, and the recovery barrier and
  prerequisite enforcement are owned by ADR-002-017;
* confirming the checklist does not lower the barrier or substitute for it — readiness is
  not authority (ADR-002-017 SBR-INV-003), and the system still starts closed and
  restricts before observing (SBR-INV-001, -002);
* any `UNKNOWN`/unreconciled item withholds the request (RRC-INV-002), and withholding is
  a first-class recorded outcome (ADR-DEV-014);
* the checklist adds an operator-side discipline; it removes none of the barrier's
  enforcement.

The operator confirms readiness and requests; the barrier and the re-arm authority
decide and grant.

---

## 9. Alternatives Considered

* **9.1 Let a green dashboard imply the checklist.** Rejected: a snapshot is not
  reconciliation; readiness is not authority (RRC-INV-003, -005; ADR-002-017).
* **9.2 Confirm a subset of the items "to move faster."** Rejected: any unreconciled
  item is restrictive; a partial checklist is not reconciliation (RRC-INV-001, -002).
* **9.3 Treat checklist confirmation as the re-arm grant.** Rejected: re-arm is owned by
  ADR-002-007 behind the ADR-002-017 barrier (RRC-INV-003, -004).
* **9.4 Skip single-instance/aggregate-risk under time pressure.** Rejected: duplicate
  instance and unknown risk are exactly the conditions re-arm must resolve (RFC-011 §10;
  RFC-001 SC-030).
* **9.5 Define the recovery barrier here.** Rejected: owned by ADR-002-017 (§4).

---

## 10. Consequences

**Positive.**

* Makes the operator's re-arm precondition explicit, auditable, and conservative.
* Binds cleanly to ADR-002-017/007 without duplicating or weakening them.
* Any unreconciled item fails closed to a recorded withhold.

**Negative / costs.**

* Confirming every item positively is slower than trusting a dashboard — the intended,
  conservative cost.
* Reconciliation tooling must expose each item's positively-established state.
* A single unreconciled item blocks re-arm, accepting missed opportunity (Vision §9.6).

---

## 11. Failure Modes Introduced by This Decision

* **11.1 Snapshot-as-reconciliation.** A cached value confirms an item; forbidden by
  RRC-INV-005 and surfaced by ADR-002-018.
* **11.2 Partial checklist.** An item skipped under pressure; blocked by RRC-INV-001/002.
* **11.3 Checklist-as-grant.** Confirmation treated as re-arm; blocked by RRC-INV-003 and
  the ADR-002-017 barrier.
* **11.4 Duplicate-instance miss.** Single-instance not confirmed; blocked by RRC-INV-001
  (RFC-001 SC-030).

---

## 12. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010; enforcement owned by
ADR-002-017/007):

* **12.1** A re-arm request with any unreconciled checklist item is withheld
  (RRC-INV-001, -002).
* **12.2** A cached/last-known-good/heartbeat confirmation — and a once-true reconciliation
  that has since gone stale — does not satisfy an item (RRC-INV-005; ADR-002-017
  SBR-INV-004).
* **12.3** Checklist confirmation does not itself re-arm or lower the barrier
  (RRC-INV-003, -004).
* **12.4** A duplicate active instance blocks re-arm until resolved (RRC-INV-001).
* **12.5** Checklist confirmation commits no capacity and issues no live authority
  (RRC-INV-006).

---

## 13. Acceptance Criteria

ADR-DEV-012 is acceptable when:

* the minimum checklist is fixed and positively confirmed (RRC-INV-001, -005);
* any unreconciled item withholds the request (RRC-INV-002);
* the checklist binds before the barrier and grant without replacing them (RRC-INV-003,
  -004);
* confirmation grants no authority (RRC-INV-006);
* independent adversarial review (EV-L0) confirms every §12 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 14. Traceability

| Requirement | Discharge in ADR-DEV-012 |
|---|---|
| RFC-011 §14 Q1 (minimum reconciled-state checklist; barrier binding) | checklist (§7); binding to ADR-002-017/007 (§8) |
| RFC-011 §10 (no automatic re-arm; prerequisites) | operator withholds until reconciled (§§7, 8; RRC-INV-002) |
| Vision §7.4 (restore authority only after prerequisites) | checklist items (§7; RRC-INV-001) |
| RFC-002 §4.7 (recovery without automatic trust) | recovery is a fresh assessment (§3) |
| ADR-002-007 (live authorization / re-arm) | grant owned there; checklist is only the request precondition (§8; RRC-INV-003) |
| ADR-002-017 SBR-INV-001/002/003/004/005/006/007 (barrier; restriction-before-observation; readiness≠authority; one current recovery generation; inventory; UNKNOWN conservative; no snapshot optimism) | barrier is the enforcement point; positively-established and current items (§§7, 8; RRC-INV-003/004/005) |
| ADR-002-018/019 (Critical Input; venue/session) | account/venue/critical-input reconciled (§7) |
| RFC-001 SC-030 (execution integrity; single instance) | single active instance confirmed (§7; RRC-INV-001) |
| RFC-001 SC-040 (state integrity; no new exposure while unknown/unreconciled) | reconciliation items compelled; withhold until reconciled and current (§7; RRC-INV-001, -002) |
| RFC-000 CONST-011 (independent safety authority) | valid safety authority confirmed (§7) |
| RFC-002 §9.1 (authority ownership) | confirmation grants no authority (RRC-INV-006) |
| philosophy §8, §23 | uncertainty restrictive; recovery is a new decision (§3) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the operator
re-arm checklist and its binding and relies on ADR-002-007/017 for the grant and barrier.

---

## 15. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-012, resolving RFC-011 §14 Q1 (minimum reconciled-state checklist
  before a Re-arm Decision and its binding to the recovery barrier).
* Set the decision: a nine-item positively-confirmed checklist; any unreconciled item
  withholds the request; the checklist sits before, and never replaces, the ADR-002-017
  recovery barrier and the ADR-002-007 re-arm grant; confirmation grants no authority.
* Defined six invariants RRC-INV-001…006 and traced them to RFC-011 §10, Vision §7.4,
  RFC-002 §4.7/§9.1, ADR-002-007, ADR-002-017 (SBR-INV-001/003/005/006/007),
  ADR-002-018/019, RFC-001 SC-030, RFC-000 CONST-011, and philosophy §8/§23.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; the core attacks were blocked and the ADR confirmed correctly scoped
  (operator precondition only, never the ADR-002-007 grant or ADR-002-017 barrier). Two
  Major findings were resolved: (M1) confirmation had no currentness bound (a once-true
  reconciliation could go stale before the request, a TOCTOU gap) — RRC-INV-005 now
  requires each item to be positively established *and current at the time of the request*,
  anchored on ADR-002-017 SBR-INV-004 (One Current Recovery Generation), with a §12.2
  staleness test; (M2) RFC-001 SC-040 (State Integrity Claim — no new exposure while
  state is unknown/unreconciled), the most on-point safety-case anchor, was missing — now
  cited in §7 and §14. Minor fixes: SBR-INV-005 scoped to the economic-inventory items;
  §2's "automatic re-arm" prohibition re-anchored to RFC-002 §4.7 (with §9.1 for the
  non-owner bar); RRC-INV-002 widened to conflicting/stale/ambiguous state; the Live
  Authorization item clarified as a basis/governance, not an active grant; and SBR-INV-002
  added to RRC-INV-004. The review is EV-L0 only and confers no acceptance or
  live-readiness.

### v0.2 — Wave 7 (CORPUS-REVIEW-0001 mn-12)

* Added a **trapped-exposure representation** item to the §7 checklist as a complementary
  check — *not* a tenth reconciliation confirmation, so the nine reconciliation items
  (RRC-INV-001; RRC-EV-001) are preserved: any trapped or irreducible exposure is represented
  at full conservative risk and does not release capacity (ADR-002-001 §15; ADR-002-017
  SBR-INV-005, which enforces it independently), aligning the operator checklist with
  SBR-INV-005. Narrow-only and additive; no SAFE-xxx, no numeric bound, no new RRC-INV or EV.
  Independent EV-L0 review is owed, with reviewer provenance recorded per ADR-DEV-005 §7 /
  VER-002-001 §5 (M-18).

### v0.3 — SBR-INV-005 Citation Precision (CORPUS-REVIEW-0001 Wave 8, mn-1)

* **mn-1 (Wave-7 EV-L0 finding).** Split the §7 trapped-exposure citation, which had
  over-attributed the whole claim to ADR-002-017 SBR-INV-005 ("which enforces this
  independently"). SBR-INV-005 is Complete Economic Inventory (inventory completeness) — it
  requires that trapped/irreducible exposure be included in the recovery inventory. The
  "represented at full conservative risk and does not release capacity" property is owned by
  ADR-002-001 §15 (Trapped Exposure), with recovery-context conservative capacity consumption
  enforced by ADR-002-017 SBR-INV-006 (UNKNOWN Remains Conservative). §7 now cites §15 +
  SBR-INV-006 for conservative valuation and non-release, and SBR-INV-005 only for
  recovery-inventory inclusion. This supersedes the v0.2 phrasing "SBR-INV-005, which enforces
  it independently."
* Narrow-only and additive: citation precision only; the trapped-exposure item remains a
  complementary check, not a tenth reconciliation confirmation, so the "nine reconciliation
  items" (RRC-INV-001; RRC-EV-001) are preserved unchanged. No SAFE-xxx, no numeric bound, no
  new RRC-INV or EV (development-track count stays 98). Independent EV-L0 review is owed,
  reviewer provenance per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).
