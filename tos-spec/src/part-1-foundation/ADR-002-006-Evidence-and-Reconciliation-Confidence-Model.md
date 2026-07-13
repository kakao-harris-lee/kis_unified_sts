# ADR-002-006 — Evidence and Reconciliation Confidence Model

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Representation of safety-relevant knowledge as per-field evidence with conservative bounds; corroboration and independence rules; conflict, negative-evidence, and freshness handling; the conditions under which knowledge may become `RECONCILED`; and reconciliation triggers
- **Supersedes:** None
- **Amends:** RFC-002 §15 (Reconciliation) and §31 reconciliation amendments (makes the confidence model normative)
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-034; ADR-002-005 (Knowledge dimension), ADR-002-002 (capacity coupling), ADR-002-004 (broker evidence + Final Quantity Proof), ADR-002-003 (time/authority currentness)

---

## 1. Decision

Safety-relevant state SHALL be represented as **per-field evidence with conservative bounds**, not as a single blended confidence score and not as an optimistic point estimate. The Knowledge/Evidence dimension of ADR-002-005 SHALL, for each safety-relevant field, carry:

```text
- a conservative bound usable for risk decisions;
- the contributing evidence paths and their provenance;
- a freshness/validity marker tied to the trustworthy-time model;
- a confidence class (see §5) sufficient to gate transitions.
```

No single source SHALL be treated as unconditional truth where a single-source error could cause Critical or Catastrophic exposure. Absence of evidence SHALL NOT be treated as proof of non-existence. Knowledge SHALL become `RECONCILED` for a field only when corroborating evidence satisfies that field's proof rule; otherwise it remains `CONFLICTED`/`QUARANTINED` and blocks new risk in scope.

---

## 2. Context

RFC-002 §31 (reconciliation amendments) requires per-field confidence and forbids a single blended score for risk release. ADR-002-002 §22 requires conservative-bound use and forbids optimistically freeing capacity. ADR-002-005 defines the Knowledge dimension but not how confidence is computed or when `RECONCILED` is justified. This ADR fills that gap.

The failure this prevents: a system that reduces many independent uncertainties (does the order exist? what quantity filled? what is the position? is margin sufficient?) to one number will release capacity or authorize risk when the *aggregate* number looks acceptable while a *specific* field is dangerously wrong.

---

## 3. Decision Drivers

1. Capital preservation under conflicting or partial evidence.
2. Correct at-most-authorized exposure: release requires field-specific proof (fill quantity, remaining quantity), not overall optimism.
3. Robustness to a single wrong or missing external source (broker, feed, query).
4. Deterministic, auditable reconciliation that a restarted or independent reviewer can reproduce.

---

## 4. Scope

**Decides:** the per-field evidence structure, corroboration/independence rules, conflict and negative-evidence handling, freshness handling, the generic proof-rule contract for `RECONCILED`, and reconciliation triggers.

**Does not decide:** broker-specific Final Quantity Proof or evidence semantics (ADR-002-004); numeric freshness/detection bounds (Verification Profile); the persistence mechanism; the trustworthy-time mechanism (ADR-002-008). Those SHALL conform to this model.

---

## 5. Per-Field Evidence

Reconciliation SHALL maintain independent evidence for at least these safety-relevant fields (RFC-002 §31; ADR-002-002 §22.1):

```text
order existence            broker order identity
cumulative filled quantity remaining executable quantity
position quantity          cash / margin / collateral
protective coverage        instrument identity
external / unattributed activity
```

Each field carries a **confidence class**:

```text
UNKNOWN        — no usable evidence; treat at maximum conservative bound
SINGLE_SOURCE  — one source only; usable only under a recorded, independently
                 accepted single-source residual (ADR-002-004; SAFE-023)
CORROBORATED   — >=2 sufficiently independent paths agree within tolerance
CONFLICTED     — independent paths disagree beyond tolerance
STALE          — previously sufficient, now older than the approved freshness bound
```

For risk decisions the system SHALL use the **conservative bound** of a field:

- upper bound for any adverse quantity (potential exposure, potential remaining executable quantity, potential external activity);
- lower bound only where a lower value cannot understate risk;
- never a midpoint, average, or blended score.

---

## 6. Corroboration and Independence

- A **Corroborating Evidence Path** (RFC-002 §31; ADR-002-002 definitions) is one sufficiently independent from another that a single defect is not expected to corrupt both in the same way (e.g., outbound send record vs. broker order-status query vs. fill stream vs. position query vs. independently retained audit).
- `CORROBORATED` requires ≥2 such paths agreeing within an approved tolerance.
- Where only one path exists (`SINGLE_SOURCE`), the dependency and residual risk SHALL be explicitly recorded, independently reviewed, and constrained to conservative operating authority (SAFE-023). A proposing component SHALL NOT unilaterally declare corroboration infeasible.
- The required degree of independence SHALL scale with hazard severity.

---

## 7. Conflict, Negative Evidence, and Freshness

- **Conflict:** independent paths disagreeing beyond tolerance set the field `CONFLICTED`, force the affected Capacity allocation to `QUARANTINED_UNKNOWN` (CPL-5), and block new risk in scope until resolved. Conflict resolution requires evidence, never selection of the most convenient source (ADR-002-002 §12 INV-012).
- **Negative evidence:** absence from one query, page, session, or stream is NOT proof of non-existence. It may lower a field's confidence but SHALL NOT establish `NONE`/`CANCELLED`/`released`. Pagination, eventual consistency, history windows, and session scope SHALL be accounted for (handoff §12; ADR-002-004).
- **Freshness:** every field's evidence has a validity horizon evaluated against the Trustworthy Time model (ADR-002-003/008). Beyond it the field is `STALE` and SHALL NOT authorize new risk; if time confidence itself is lost, all time-dependent freshness fails closed.

---

## 8. Proof Rule for `RECONCILED`

A field may transition to `RECONCILED` (ADR-002-005 §8) only when a field-specific **proof rule** is satisfied. The generic contract:

```text
RECONCILED(field) requires:
  - corroborating evidence sufficient for the field's hazard severity; AND
  - for capacity-releasing fields (final filled quantity, remaining executable
    quantity): Final Quantity Proof per the approved Broker Capability Profile
    (ADR-002-004), including the broker's late-fill / correction semantics; AND
  - freshness within the approved bound; AND
  - no unresolved conflict on the same field.
```

Reconciliation MAY provide evidence for a defined capacity transition but SHALL NOT overwrite the Ledger with an optimistic snapshot or free capacity because one source omits an order (ADR-002-002 INV-012). Reducing conservatism requires stronger proof than increasing it (ADR-002-002 §27).

---

## 9. Reconciliation Triggers

Reconciliation SHALL run (RFC-002 §15.4):

```text
at startup, restart, reconnect;
after execution timeout or UNKNOWN order state;
after detected external / unattributed activity;
after any evidence conflict;
periodically during live operation (within the approved cadence);
before restoring authority after material divergence.
```

External/unattributed activity detection SHALL occur within the approved external-activity detection bound (Verification Profile); new-action size and retained headroom SHALL be constrained so plausible activity within that window cannot breach the Hard Safety Envelope (ADR-002-002 §23.4).

---

## 10. Transition Authority

The **Reconciliation Service** is the sole owner of the Knowledge dimension (ADR-002-005 §12). It:

- collects and evaluates evidence and produces per-field confidence + bounds;
- requests defined Ledger/capacity transitions through the owning authority (it cannot mutate capacity directly);
- creates or requests `QUARANTINE` for unknown, unattributed, or conflicting state;
- SHALL NOT release capacity or declare `RECONCILED` outside these rules.

---

## 11. Alternatives Considered

- **Single blended confidence score. Rejected.** Masks a dangerous single-field error behind an acceptable aggregate (RFC-002 §31).
- **Broker query as absolute truth. Rejected.** A single external response may be delayed, incomplete, inconsistent, or wrong (ADR-002-002 §30.5).
- **Optimistic midpoint estimates. Rejected.** Understates adverse exposure; violates conservative-bound use.
- **Absence as proof of non-existence. Rejected.** Ignores pagination, eventual consistency, and query omission.

---

## 12. Consequences

**Positive:** a wrong or missing single source cannot silently authorize risk or release capacity; reconciliation is auditable and reproducible; the model composes with the capacity, state, broker, and time ADRs.

**Negative:** more evidence must be collected and stored; some fields remain `CONFLICTED`/`QUARANTINED` longer, delaying actions; corroboration may be infeasible for some brokers, forcing reduced live scope rather than weaker proof. These costs are accepted.

---

## 13. Verification and Acceptance Criteria

Under VER-002-001 (EV-L2/L3; RC-EV-005/007/010/011, SA-EV-011):

- **AC-006-1:** injected corruption of any single evidence path does not cause an unsafe state to be accepted as `RECONCILED`.
- **AC-006-2:** a hidden-then-reappearing order (query omission) never releases capacity from absence alone.
- **AC-006-3:** conflicting fill-quantity evidence holds the field at its conservative upper bound and quarantines capacity.
- **AC-006-4:** freshness expiry moves a field to `STALE` and blocks new risk; loss of time confidence fails closed.
- **AC-006-5:** capacity release occurs only after the field-specific proof rule (incl. Final Quantity Proof) is met.

A written test is not evidence; execution, artifacts, and independent review are required.

---

## 14. Dependencies and Follow-Up

Depends on ADR-002-005 (Knowledge dimension) and ADR-002-004 (Final Quantity Proof); consumed by ADR-002-002 (capacity release), ADR-002-007 (re-arm reads reconciled state), ADR-002-011 (protection-gap coverage confidence). Numeric tolerances, freshness horizons, and detection bounds belong in the Verification/Safety Profiles, not this ADR.

---

## 15. Approval Gate

ADR-002-006 may move from **Proposed** to **Accepted** only when:

- per-field evidence, confidence classes, and conservative-bound use are implemented and evidenced;
- single-source-corruption, query-omission, conflict, and freshness cases pass under fault injection;
- no implementation uses a blended score or optimistic estimate to release capacity or authorize risk;
- the `RECONCILED` proof rule (including broker Final Quantity Proof) is demonstrated;
- independent review confirms conformance to RFC-001 SAFE-022/023/024/025 and ADR-002-002.

Until then, this ADR authorizes design and implementation-planning work only; it does not authorize live trading.
