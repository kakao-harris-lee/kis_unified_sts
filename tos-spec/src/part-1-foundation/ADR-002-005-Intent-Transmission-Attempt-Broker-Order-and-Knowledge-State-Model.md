# ADR-002-005 — Intent, Transmission Attempt, Broker Order, and Knowledge State Model

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** The orthogonal state dimensions of the trading-action lifecycle; per-dimension states, transitions, transition ownership, cross-dimension coupling invariants, conservative-direction rules, persistence, and restart semantics
- **Supersedes:** None
- **Amends:** RFC-002 §12 Orthogonal Trading State Model (makes the dimension model normative and complete)
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-020, SAFE-021, SAFE-022, SAFE-024, SAFE-025, SAFE-030; ADR-002-002 (Capacity dimension), ADR-002-003 (authority epochs), ADR-002-004 (broker evidence semantics), ADR-002-001 v0.2 (protective actions)

---

## 1. Decision

The trading-action lifecycle SHALL be represented as **five orthogonal state dimensions**, never as a single order-status enumeration:

```text
1. Intent State              — business/authorization lifecycle of a decision
2. Transmission Attempt State — local send preparation and transport uncertainty
3. Broker Order State         — broker-side order lifecycle, established only from broker evidence
4. Knowledge / Evidence State — the system's confidence about the above
5. Capacity State             — reservation/consumption (defined by ADR-002-002)
```

Each dimension has an independent state, an exclusive transition authority, and a defined conservative direction. The dimensions MAY disagree temporarily; the system SHALL represent that disagreement rather than collapse it. No dimension SHALL be advanced to a less-conservative state from timeout, absence of evidence, local assumption, or operator convenience.

`RECONCILED` is a value of the Knowledge dimension, not of the Broker Order dimension. `UNKNOWN` is a first-class, capacity-consuming condition and never means rejected, cancelled, unfilled, or safe to retry.

---

## 2. Context

RFC-002 §12 requires orthogonal state modeling; this ADR makes it complete and normative. A single enum forces false coupling: e.g., marking an order `CANCELLED` in one field implicitly asserts the broker cannot fill it, that no capacity is consumed, and that state is known — three independent claims that can each be false. Real execution routinely produces states such as:

```text
Intent:      APPROVED
Attempt:     SENT_UNCONFIRMED
Broker Order: UNKNOWN
Knowledge:   CONFLICTED
Capacity:    POTENTIALLY_LIVE
```

A model that cannot hold this combination will either fabricate certainty (unsafe) or block correct handling. The safety properties in RFC-001 (at-most-authorized exposure, reconciliation before exposure, partial-fill integrity, conservative UNKNOWN) depend on keeping these dimensions distinct.

---

## 3. Decision Drivers

1. Long-term survivability and capital preservation.
2. Conservative behavior under incomplete or conflicting evidence (RFC-001 §7.3).
3. Correct at-most-authorized exposure across acknowledgement loss, partial fill, cancel/replace, and restart.
4. Enforceable transition ownership (no component silently rewriting another's truth).
5. Deterministic recovery: a restarted system reconstructs a conservative, not optimistic, view.

---

## 4. Scope

**This ADR decides:** the dimensions, their states, transition directions, transition ownership, cross-dimension coupling invariants, and restart semantics.

**This ADR does not decide:** the persistence technology, the Capacity-dimension internals (ADR-002-002), the authority-epoch mechanism (ADR-002-003), broker-specific evidence rules or Final Quantity Proof (ADR-002-004), the reconciliation confidence model (ADR-002-006), or numeric bounds (Verification Profile). Those SHALL conform to this model.

---

## 5. Dimension: Intent State

Owned by the **Intent Registry**, advanced by Decision/Approval/Aggregate-Risk authorities per RFC-002 §11.

```text
PROPOSED -> APPROVED -> AUTHORIZED_FOR_CAPACITY -> ACTIVE -> CLOSED
                     \-> DENIED
ACTIVE -> WITHDRAWN            (only if no attempt may be live; see §11)
```

- `AUTHORIZED_FOR_CAPACITY` means Approval + Aggregate-Risk policy granted; it does **not** mean capacity is committed (that is the Capacity dimension) or that anything was transmitted.
- Intent identity is immutable and globally unique (SAFE-020); every attempt, order, fill, and evidence record links to it. A terminal Intent identity SHALL NOT be reused.
- `CLOSED`/`WITHDRAWN` are permitted only when the Capacity and Knowledge dimensions prove no potentially-live effect remains (§11).

---

## 6. Dimension: Transmission Attempt State

Owned by the **Execution Coordinator** for preparation and by the **Broker Adapter / Egress Gateway** for the send boundary. One Intent MAY have multiple attempts (retry after proven rejection, replacement); each attempt has an immutable attempt identity bound to one reservation (ADR-002-002).

```text
NONE
  -> PREPARED
  -> CAPABILITY_ISSUED        (single-use Transmission Capability bound; ADR-002-002 §12)
  -> SEND_STARTED             (durably recorded BEFORE the network call; write-ahead boundary)
  -> SENT_UNCONFIRMED         (network call issued; outcome not yet proven)
  -> {ACK_OBSERVED | SEND_FAILED_PROVEN | SUPERSEDED}
```

Conservative rules:

- The transition into `SEND_STARTED` SHALL be durable before the external call, so a crash between `SEND_STARTED` and broker receipt is treated as potentially live (ADR-002-002 §11.4).
- `SEND_FAILED_PROVEN` requires positive evidence that the broker did not and cannot accept the attempt. Timeout, missing ACK, connection reset, or process restart SHALL NOT reach `SEND_FAILED_PROVEN`.
- Once an attempt reaches `SEND_STARTED`, no TTL, restart, or authority expiry may retire it to a state that releases capacity (ADR-002-002 INV-005).

---

## 7. Dimension: Broker Order State

Established **only from broker/venue evidence** evaluated under the approved Broker Capability Profile (ADR-002-004). No internal component may set this dimension from assumption.

```text
NONE_OBSERVED
WORKING
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
REJECTED
EXPIRED
UNKNOWN                       (broker state cannot currently be determined)
```

Conservative rules:

- Absence of an order from one query, page, session, or stream is **not** proof of `NONE_OBSERVED`/`CANCELLED` (ADR-002-004; handoff §12). It may only lower the broker-state confidence, which is the Knowledge dimension.
- A later valid fill SHALL be accepted even after a locally observed `CANCELLED`/`REJECTED`; the Broker Order dimension is corrected and the event is not discarded (ADR-002-002 §15.2).
- `UNKNOWN` here forces `QUARANTINED_UNKNOWN` in the Capacity dimension until resolved.

---

## 8. Dimension: Knowledge / Evidence State

Owned by the **Reconciliation Service** (ADR-002-006 will define the confidence representation). It expresses how well the other dimensions are known.

```text
UNOBSERVED -> CONSISTENT
UNOBSERVED -> CONFLICTED
CONSISTENT -> CONFLICTED       (new evidence disagrees)
CONFLICTED -> RECONCILING -> {RECONCILED | QUARANTINED}
STALE                          (prior knowledge older than its approved freshness bound)
```

Conservative rules:

- `RECONCILED` requires positive corroborating evidence per ADR-002-006 and, where a broker order is involved, Final Quantity Proof per ADR-002-004. It is never inferred from a single source or from silence.
- Loss of freshness (time model, ADR-002-003/008) moves knowledge to `STALE`, which SHALL NOT authorize new risk.
- `QUARANTINED` is a stable conservative state; escaping it requires evidence, never assertion (ADR-002-002 §18.6).

---

## 9. Dimension: Capacity State

Defined by **ADR-002-002 §10** (`COMMITTED_UNBOUND`, `ATTEMPT_BOUND`, `POTENTIALLY_LIVE`, `PARTIALLY_CONSUMED`, `POSITION_CONSUMED`, `RELEASE_PENDING_PROOF`, `QUARANTINED_UNKNOWN`, `TRAPPED_CONSUMED`, `RELEASED`) and owned solely by the **Risk Capacity Ledger**. This ADR governs only how the Capacity dimension couples to the other four.

---

## 10. Cross-Dimension Coupling Invariants

The dimensions are orthogonal but not unconstrained. The following couplings are safety-normative.

- **CPL-1 (potential effect ⇒ capacity):** If Attempt ∈ {`SEND_STARTED`, `SENT_UNCONFIRMED`} or Broker Order = `UNKNOWN`, then Capacity SHALL be at least as conservative as `POTENTIALLY_LIVE`.
- **CPL-2 (no release without proof):** Capacity SHALL NOT reach `RELEASED` unless Knowledge = `RECONCILED` (or `CONSISTENT` with the applicable proof rule) **and** Broker Order ∈ {`CANCELLED`, `REJECTED`, `EXPIRED`, `FILLED`} with Final Quantity Proof where required.
- **CPL-3 (fill transfer):** A confirmed fill in the Broker Order dimension SHALL atomically transfer the filled quantity from open-order reservation to `POSITION_CONSUMED`, leaving remaining executable quantity `POTENTIALLY_LIVE` (ADR-002-002 §15.1).
- **CPL-4 (cancel is not release):** Broker Order = `CANCEL_PENDING` or a bare cancel acknowledgement SHALL NOT move Capacity toward `RELEASED`; at most `RELEASE_PENDING_PROOF` (ADR-002-002 §16.2).
- **CPL-5 (unknown quarantine):** Broker Order = `UNKNOWN` or Knowledge = `CONFLICTED`/`QUARANTINED` SHALL force Capacity `QUARANTINED_UNKNOWN` and block new risk in scope.
- **CPL-6 (authority gate on transmission):** An attempt SHALL NOT advance to `SEND_STARTED` unless the current authority epoch and live scope are verifiable at final egress (ADR-002-003); a stale epoch SHALL fail closed.
- **CPL-7 (trapped exposure):** Confirmed non-reducible exposure SHALL be `TRAPPED_CONSUMED` regardless of any pending exit Intent or Attempt (ADR-002-002 §24).

A composite state is valid only if all applicable coupling invariants hold. An invariant violation is a Critical incident and an immediate new-risk halt condition (ADR-002-002 §34).

---

## 11. Conservative-Direction Rule

Every dimension has a conservative direction (more uncertainty / more assumed exposure / less authority). The following are prohibited:

- advancing any dimension to a less-conservative value on the basis of timeout, absence, local cache, or operator assertion;
- collapsing `UNKNOWN` to `NONE`/`CANCELLED`/`UNFILLED`;
- treating a cancel request or ACK as terminal for capacity;
- treating recovery/reconnect as knowledge of a specific state.

Reducing conservatism requires the specific proof rule for that transition. Increasing conservatism (e.g., a fresh conflict re-opening `RECONCILED` → `CONFLICTED`) is always permitted and never blocked.

---

## 12. Transition Authority

| Dimension | Sole transition authority | May be read by |
|---|---|---|
| Intent | Intent Registry (advanced by Decision/Approval/Aggregate-Risk) | all |
| Transmission Attempt | Execution Coordinator (prep) + Broker Adapter/Egress (send boundary) | all |
| Broker Order | Broker evidence via Broker Adapter, under the Broker Capability Profile | all |
| Knowledge/Evidence | Reconciliation Service | all |
| Capacity | Risk Capacity Ledger only | all |

No component SHALL write a dimension it does not own. Cross-dimension effects occur only through the owning authority's defined transition (e.g., a broker fill event is presented as evidence; the Ledger performs the CPL-3 transfer).

---

## 13. Persistence and Restart

- All five dimensions SHALL be durable and reconstructable after crash, restart, or failover.
- On restart, any Attempt that reached `SEND_STARTED` and any Broker Order that is not provably terminal SHALL be treated as `POTENTIALLY_LIVE`/`UNKNOWN` until reconciled (ADR-002-002 §21; handoff §8.2).
- Knowledge SHALL be re-derived from evidence, defaulting to `UNOBSERVED`/`CONFLICTED`, never to `RECONCILED`.
- No new risk SHALL be authorized until the Recovery Coordinator clears the startup barrier (RFC-002 §15.5 and §23; ADR-002-002 §21.6).

---

## 14. Composite Examples (all valid)

```text
Intent=APPROVED  Attempt=CAPABILITY_ISSUED  Broker=NONE_OBSERVED  Knowledge=CONSISTENT  Capacity=ATTEMPT_BOUND
Intent=ACTIVE    Attempt=SENT_UNCONFIRMED   Broker=UNKNOWN        Knowledge=CONFLICTED  Capacity=POTENTIALLY_LIVE
Intent=ACTIVE    Attempt=ACK_OBSERVED       Broker=PARTIALLY_FILLED Knowledge=CONSISTENT Capacity=PARTIALLY_CONSUMED
Intent=ACTIVE    Attempt=SUPERSEDED         Broker=CANCEL_PENDING  Knowledge=CONFLICTED  Capacity=RELEASE_PENDING_PROOF
Intent=ACTIVE    Attempt=ACK_OBSERVED       Broker=FILLED          Knowledge=RECONCILED  Capacity=POSITION_CONSUMED
```

---

## 15. Alternatives Considered

- **Single order-status enum. Rejected.** Forces false coupling and cannot represent legitimate disagreement; drives fabricated certainty.
- **Two dimensions (internal vs broker). Rejected.** Conflates transport uncertainty, broker truth, and knowledge; loses the write-ahead send boundary and the reconciliation confidence distinction.
- **Deriving capacity from broker status. Rejected.** Makes a fallible external source the safety serialization point, contradicting ADR-002-002.
- **Knowledge folded into broker state (`RECONCILED` as an order status). Rejected.** Confidence is not a broker lifecycle fact; it changes without any broker event.

---

## 16. Consequences

**Positive:** legitimate disagreement is representable; conservative direction is enforceable; transition ownership prevents silent rewrites; restart is deterministic and conservative; the model composes cleanly with capacity, authority, and broker ADRs.

**Negative:** more state to persist and reason about; more evidence required to reduce conservatism; some actions are blocked longer while a dimension remains `UNKNOWN`/`CONFLICTED`. These costs are accepted; they are the mechanism by which uncertainty does not become unbounded economic effect.

---

## 17. Verification and Acceptance Criteria

Demonstrated via model/property tests (EV-L1) and fault tests (EV-L2/L3) under VER-002-001. The following criteria map one-to-one to STATE-EV-001 through STATE-EV-005 and may additionally rely on the listed cross-domain evidence:

- **AC-005-1 — Orthogonality:** the composite states in §14 are all representable and persisted; no dimension is forced by another except through the CPL invariants (`STATE-EV-001`).
- **AC-005-2 — Conservative direction:** no injected timeout/absence/restart advances any dimension to a less-conservative value (`STATE-EV-002`; additionally RC-EV-003/004 and RC-EV-011).
- **AC-005-3 — Coupling:** every CPL invariant holds under partial fill, cancel-crossing-fill, replace overlap, and UNKNOWN (`STATE-EV-003`; additionally RC-EV-006/007/008/010).
- **AC-005-4 — Restart:** post-restart, `SEND_STARTED`/non-terminal orders are `POTENTIALLY_LIVE`/`UNKNOWN`; knowledge is never `RECONCILED` without re-derivation (`STATE-EV-004`; additionally RC-EV-017 and SA-EV-006).
- **AC-005-5 — Ownership:** an attempt to transition a dimension by a non-owner is rejected and evidenced (`STATE-EV-005`).

Registration is not execution. A written test is not evidence (VER-002-001 §5); execution, artifacts, and independent review are required.

---

## 18. Dependencies and Follow-Up

Consumed by: ADR-002-006 (evidence/confidence attaches to the Knowledge dimension), ADR-002-007 (re-arm reads all dimensions), ADR-002-002 (Capacity coupling), ADR-002-004 (Broker Order evidence rules), ADR-002-011 (protection-gap uses Attempt/Broker/Knowledge). Numeric freshness bounds (`STALE` thresholds) belong in the Verification Profile / Safety Profile.

---

## 19. Approval Gate

ADR-002-005 may move from **Proposed** to **Accepted** only when:

- the five dimensions, their transitions, and ownership are implemented and evidenced;
- all CPL coupling invariants are demonstrated under fault injection;
- restart reconstructs a conservative composite state in tests;
- no implementation collapses dimensions or advances conservatism-reducing transitions without the defined proof;
- ADR-002-016 immutable causal evidence preserves each dimension owner and transition independently, detects gaps, and replays without mutating live state;
- independent review confirms the model against RFC-001 SAFE-020/021/022/024/025 and ADR-002-002.

Until then, this ADR authorizes design and implementation-planning work only; it does not authorize live trading.
