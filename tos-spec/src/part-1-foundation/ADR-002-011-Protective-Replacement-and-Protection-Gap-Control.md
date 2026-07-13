# ADR-002-011 — Protective Replacement and Protection-Gap Control

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Protective-order replacement, cancellation authority, non-atomic replace, overlap and gap capacity, proof of protection, Final Quantity Proof, partial fills, broker-resource scarcity, failure containment, recovery, and evidence
- **Supersedes:** None
- **Amends:** RFC-002 §13.3 Cancel/Replace Semantics, §21 Protective Control, and the capacity and reconciliation prerequisites in §10, §15, and §19
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-002, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-025, SAFE-032, SAFE-040, SAFE-041, SAFE-043, SAFE-048, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-009

---

## 1. Decision

The Trading Operating System SHALL treat replacement of safety-owned or safety-required protection as one safety-critical workflow whose economic effects include both the old and new orders throughout uncertainty.

Protective replacement is not safely represented as an ordinary cancel followed by an ordinary submission.

The **Cancellation Arbiter** is the sole authority that may authorize removal, reduction, or weakening of required protection. The **Protective Action Controller** coordinates the replacement workflow. The **Risk Capacity Ledger** is the sole authority that reserves, commits, remaps, and releases capacity. The **Broker Adapter/Egress Gateway** is the final transmission enforcement point.

Before any replacement step is transmitted, the system SHALL determine and reserve for the worst credible intermediate state, including:

- both old and new protection being live and fillable;
- the old protection being absent while the new protection is not yet effective;
- partial or late fills on either order;
- cancellation, replacement, or query uncertainty;
- broker session, order-count, rate-limit, or cancel-capacity exhaustion;
- reduced protection caused by market state or instrument constraints.

An old protective order remains potentially live until Final Quantity Proof establishes otherwise. A cancel request, cancel ACK, timeout, missing query result, or lease expiry is not Final Quantity Proof.

A new protective order does not count as effective protection merely because a request was emitted or transport ACK was received. Its identity, quantity, side, price or trigger semantics, remaining quantity, venue state, broker capability, and relation to current exposure SHALL be positively established within approved freshness and confidence bounds.

If safe replacement cannot be proven, the system SHALL preserve conservative capacity, block new risk, retain UNKNOWN order and exposure state, and enter bounded protective recovery or HALT. It SHALL NOT weaken the protection requirement for implementation convenience.

---

## 2. Context

Protective orders may need replacement because of partial fills, exposure changes, price movement, session changes, broker restrictions, symbol or contract changes, protective-policy changes, or loss of confidence in the current order.

Most broker APIs do not provide a globally atomic replacement across the Trading Operating System, broker, and venue. Even when an API calls an operation “replace,” the observable economic behavior may include:

- cancel-old then accept-new;
- accept-new then cancel-old;
- transient coexistence;
- rejected replacement while old remains live;
- accepted replacement whose quantity differs;
- partial fill between broker observations;
- late fill on the old order after cancel ACK;
- session or rate-limit failure between legs;
- broker-side adjustment not reflected locally.

The unsafe outcomes are not limited to an unprotected position. Overlapping protective orders can also over-close, reverse, or create new exposure. The architecture must therefore control both the protection gap and the overlap state.

---

## 3. Decision Drivers

1. Required protection must not be silently removed during replacement.
2. Overlapping protection must not create an unbounded over-exit or reversal risk.
3. UNKNOWN old-order state must consume conservative capacity and block new risk.
4. Missing ACK and cancel ACK must retain their limited evidence meaning.
5. Broker-specific atomicity claims must be capability-profiled and evidenced.
6. Protective priority must not be represented as reserved protective capacity.
7. Every intermediate state must remain inside the aggregate hard envelope or fail safely.
8. Crash, partition, restart, and failover must resume from durable workflow and economic evidence.

---

## 4. Definitions

### 4.1 Protective Obligation

The versioned requirement to maintain a specified protective effect for a governed exposure. It includes scope, side, protected quantity, trigger or price semantics, duration, venue constraints, maximum gap, maximum overlap, ownership, and policy identity.

### 4.2 Protective Replacement Workflow

A durable workflow binding one protective obligation to the old protection, proposed new protection, capacity commitments, cancellation authorization, broker evidence, and completion proof.

### 4.3 Protection Sufficiency Proof

Current evidence that a protective order or approved set of orders provides the required effect for the current exposure under the active Broker Capability Profile and Safety Profile.

It is not a claim of guaranteed execution or liquidity.

### 4.4 Protection Gap

An interval in which required current exposure is not covered by sufficient, authoritatively live protection.

### 4.5 Protection Overlap

An interval in which old and new protective orders may both execute. Overlap may improve downside protection while increasing over-exit, reversal, order-count, or broker-resource risk.

### 4.6 Final Quantity Proof

The evidence required by ADR-002-004 and ADR-002-006 to establish the final executable or filled quantity of an order with sufficient confidence for a capacity or protection transition.

Cancel ACK alone is not Final Quantity Proof.

---

## 5. Orthogonal State

The replacement workflow SHALL NOT collapse order state, transmission state, knowledge confidence, capacity state, and protection state into one enum.

At minimum it SHALL retain independently:

- old and new Intent IDs;
- old and new transmission Attempt IDs;
- broker order identities and lineage;
- knowledge and evidence confidence for each order;
- Risk Capacity Ledger reservation and commitment identities;
- protective obligation version;
- cancellation authorization identity;
- current overlap or gap assessment;
- current exposure and protected-quantity basis;
- workflow generation and owner epoch.

The workflow coordination state MAY use the following lifecycle, provided those dimensions remain orthogonal:

```text
PLANNED
    -> CAPACITY_COMMITTED
    -> FIRST_LEG_SENT
    -> INTERMEDIATE_STATE
    -> NEW_PROTECTION_PROVEN
    -> OLD_FINALITY_PENDING
    -> COMPLETED

Any state -> FAILED_CONTAINED
Any uncertain state -> RECOVERY_REQUIRED
```

No lifecycle label by itself authorizes capacity release or removal of protection.

---

## 6. Replacement Modes

### 6.1 Broker-Proven Atomic Replace

An operation MAY be treated as atomic only when the active Broker Capability Profile specifies exact semantics and executed evidence proves them for the relevant order type, venue, session, partial-fill state, and failure mode.

An API method name or successful happy-path test is insufficient.

If any prerequisite is absent, stale, or contradicted, the operation SHALL be modeled as non-atomic.

### 6.2 Overlap-First Replacement

The new protection is established before removal of the old protection.

This mode is preferred when it can keep every intermediate state within the aggregate hard envelope. Before transmission it requires capacity for the worst credible simultaneous executions and broker resources for both orders.

The old order SHALL NOT be cancelled until the new Protection Sufficiency Proof is current and the Cancellation Arbiter determines that removal will not reduce required protection.

### 6.3 Cancel-First Replacement

The old protection is removed before the new protection is established.

This mode creates or may create a Protection Gap. It MAY be authorized only when all of the following hold:

1. no safer proven replacement mode is available;
2. the active Safety Profile explicitly permits the mode for the scope;
3. the gap's worst credible exposure remains within the aggregate hard envelope;
4. capacity for unprotected risk, late old-order fills, and the new order is committed in advance;
5. an approved maximum gap bound and containment action exist;
6. the necessary broker session, route, rate limit, and order capacity are positively available or conservatively accounted;
7. the current time basis is trustworthy;
8. the action has current Safety Authority and final egress approval.

If any condition is unknown, cancel-first replacement is denied.

### 6.4 No Safe Replacement Mode

If neither atomic, overlap-first, nor bounded cancel-first replacement is safe, the system SHALL not represent replacement as available. It SHALL retain or escalate the safest existing protection, block new risk, preserve capacity, and enter containment.

---

## 7. Replacement Authorization

Every replacement authorization SHALL bind at least:

- authorization and workflow identities;
- Safety Cell, account, portfolio, strategy, broker, and environment;
- old and new Intent IDs and order lineage;
- protective obligation and current exposure versions;
- replacement mode;
- maximum permitted overlap and gap;
- committed capacity identities and upper bounds;
- approved broker capability and session profile;
- writer epoch, authority epoch, revocation generation, and egress identity;
- time-health generation and validity bound;
- artifact, configuration, Safety Profile, and Verification Profile versions;
- completion, failure, and containment conditions.

Any material change invalidates the authorization and requires re-evaluation. Invalidating changes include exposure, fill, order state, capability, session, time health, capacity, profile, epoch, instrument identity, market state, or deployment generation.

Authorization expiry blocks further transmission. It does not expire the economic effect of an already transmitted old or new order.

---

## 8. Cancellation Arbiter Rules

The Cancellation Arbiter SHALL deny cancellation, reduction, or weakening when it cannot prove that the resulting intermediate state is safe.

For every request it SHALL evaluate:

1. whether the order is safety-owned, strategy-owned, or externally owned;
2. which protective obligation it satisfies;
3. current protected exposure and remaining required quantity;
4. current broker and reconciliation evidence for all related orders;
5. late-fill and partial-fill possibilities;
6. overlap and gap capacity commitments;
7. broker resource availability and capability;
8. HALT, revocation, authority, and time state;
9. the approved replacement mode and bounds.

Ordinary strategy or administrative code SHALL NOT cancel a safety-owned order by addressing the broker directly or by changing ownership metadata.

HALT dominates ordinary replacement initiation. Only a HALT-compatible protective or containment workflow with new, explicitly scoped Safety Authority and capacity MAY proceed. A protective order already necessary to contain existing exposure SHALL not be blindly cancelled merely because HALT is active; the Cancellation Arbiter SHALL choose the safest containment action under current evidence.

---

## 9. Risk Capacity Accounting

Before the first externally effective step, the Risk Capacity Ledger SHALL atomically commit capacity for the maximum aggregate risk over all credible intermediate outcomes.

The model SHALL include at least:

- current exposure without sufficient protection;
- old-order remaining executable quantity;
- new-order remaining executable quantity;
- simultaneous old and new fills;
- partial fills in every relevant ordering;
- over-close and reversal exposure;
- temporary loss of trigger, price, or venue protection;
- commissions, margin, multiplier, currency, and market-movement bounds;
- broker order-count, cancel, and rate-limit scarcity where it can prevent protection.

Capacity MAY be reduced only after evidence proves that the relevant risk can no longer occur. Workflow completion, timeout, authority expiry, cancel ACK, or local terminal state is insufficient.

Priority classification affects scheduling only. It does not create capacity or reserve broker resources.

---

## 10. Protection Sufficiency Proof

Protection Sufficiency Proof SHALL be evaluated per field under ADR-002-006 and contain at least:

- broker order identity and relation to the intended replacement;
- current broker status and leaves quantity;
- side, instrument, account, order type, price, and trigger semantics;
- current protected exposure and required quantity;
- session, venue, tradability, and order-eligibility state;
- Broker Capability Profile version and capability health;
- source sequence, timestamps, receipt anchors, freshness, and uncertainty;
- evidence confidence and contradiction status;
- proof generation and expiration bound.

Broker acceptance may establish that an order is live under a proven profile. It does not prove future fill, liquidity, trigger execution, or immunity from broker-side cancellation.

If the proof becomes stale, contradicted, or insufficient, the protection state becomes `UNKNOWN` or gap-exposed for conservative risk accounting. It does not remain sufficient by inertia.

---

## 11. Final Quantity Proof and Old-Order Retirement

The old order remains in the worst-case executable set until Final Quantity Proof establishes its remaining economic possibilities.

The proof SHALL account for:

- fills received before, during, and after cancellation;
- broker query results and source sequence;
- replacement or cancel semantics from the active capability profile;
- duplicate, delayed, missing, or reordered reports;
- session transition and broker reconnect;
- external broker adjustments;
- current account and position reconciliation.

If Final Quantity Proof cannot be obtained within the approved bound, the workflow enters `RECOVERY_REQUIRED`. Capacity remains conservative, new risk remains blocked, and recovery MAY use protective or offsetting action only with new authority and capacity.

---

## 12. Partial Fills and Exposure Changes

Every fill or recognized exposure change invalidates stale quantity calculations and triggers atomic re-evaluation of:

- the remaining protective obligation;
- old and new executable quantities;
- overlap and gap risk;
- capacity commitments;
- cancellation authorization;
- whether any pending transmission remains conformant.

A replacement that would become risk-increasing because exposure changed SHALL be denied at final egress or contained if already transmitted.

Protective quantities SHALL NOT be rounded or clamped in a way that hides uncovered or reversing quantity. Lot-size, fractional, multiplier, and instrument constraints require explicit conservative treatment.

---

## 13. Broker and Market Resource Failure

The replacement plan SHALL treat the following as safety-relevant dependencies:

- broker session and authentication state;
- order-count and open-order limits;
- submission, cancellation, and query rate limits;
- per-instrument and per-side restrictions;
- market session, auction, halt, and tradability state;
- liquidity and price-protection constraints;
- shared resource contention with normal traffic.

If the broker exposes one shared path, protective traffic is at most `PRIORITIZED_ONLY` or `BEST_EFFORT` unless a dedicated reservation is evidenced.

Resource unavailability SHALL not cause blind cancellation of existing protection or repeated unbounded transmission.

---

## 14. Missing ACK, Retry, and Idempotency

Missing ACK leaves acceptance unknown. The system SHALL NOT infer that the broker did not accept the action.

Retry requires current evidence, stable Intent identity, a Broker Capability Profile-supported idempotency mechanism, current capacity commitment, and final egress approval.

Where duplicate prevention cannot be proven, retry SHALL account for multiple accepted effects or shall be denied. A new client order ID does not make a repeated economic action safe.

Query and reconciliation are required before release or conflicting follow-up action when acceptance remains unknown.

---

## 15. Gap and Overlap Bounds

The Verification Profile SHALL define approved upper bounds for at least:

- authorization-to-first-leg transmission;
- first-leg-to-intermediate-state evidence;
- maximum Protection Gap duration;
- maximum overlap duration;
- restrictive-state propagation to egress;
- Final Quantity Proof acquisition;
- replacement completion or containment;
- broker-query and reconciliation staleness.

Every measured duration SHALL use ADR-002-008 trustworthy time.

Exceeding a bound SHALL trigger the pre-authorized containment action. It SHALL NOT extend authority automatically, silently widen capacity, or declare the replacement complete.

Numeric values remain unapproved until human approval and executed evidence are recorded.

---

## 16. Crash, Partition, and Recovery

The workflow, orders, commitments, proof generations, and authority identities SHALL be durably recoverable.

After crash, restart, failover, partition, or broker reconnect, recovery SHALL:

1. fence stale workflow and ledger writers;
2. block new risk in the affected aggregate scope;
3. restore committed capacity without inferring release;
4. reconcile old and new order identities and quantities with the broker;
5. reconcile current exposure and recognized non-trade changes;
6. classify unresolved state as UNKNOWN and capacity-consuming;
7. reassess protection sufficiency and gap or overlap risk;
8. obtain new authority for any further external action;
9. require governed re-arm before normal live authority resumes.

An unavailable prior owner is potentially active until hard fencing proves otherwise. Recovery tooling does not gain cancellation or transmission authority by being a recovery component.

---

## 17. Failure Containment

If the replacement deviates from the authorized plan, evidence becomes contradictory, or a bound is exceeded, the affected scope SHALL:

- deny new risk;
- preserve worst-case capacity;
- prevent unauthorized further cancellation or transmission;
- retain both old and new orders as potentially effective where evidence requires;
- escalate to protective recovery or HALT;
- broaden containment if aggregate risk or shared broker resources cannot be bounded;
- require reconciliation and new authorization before continuing.

Containment MAY include maintaining an existing order, issuing a newly authorized protective or offsetting order, or escalating operator intervention. It SHALL not assume that a requested cancel or offset succeeded.

---

## 18. Evidence and Observability

The system SHALL retain:

- replacement workflow and protective obligation versions;
- old and new intent, attempt, and broker-order lineage;
- Cancellation Arbiter inputs, decision, and reason codes;
- Risk Capacity Ledger commitments and every mutation proof;
- broker capability, session, rate-limit, and resource evidence;
- Protection Sufficiency Proof and Final Quantity Proof inputs;
- gap and overlap start, end, upper bound, and measured duration;
- fill and exposure-change re-evaluations;
- egress decisions and rejected stale generations;
- containment, recovery, operator, and re-arm actions.

Required metrics include gap duration, overlap duration, unknown-old-order duration, proof staleness, capacity held for replacement, denied unsafe cancellations, late fills after cancel ACK, duplicate-attempt containment, and shared protective-resource exhaustion.

Written cases and logs are not completed evidence. Acceptance requires registered, executed, retained, and independently reviewed evidence under VER-002-001.

---

## 19. Acceptance Cases

The following cases are mandatory and map one-to-one to `PR-EV-001` through `PR-EV-012`. Registration is not execution; every item remains incomplete until its required evidence is executed, retained, and independently reviewed:

| ID | Required demonstration |
|---|---|
| `PR-AC-001` | Overlap-first replacement reserves for simultaneous old/new execution and prevents unbounded reversal |
| `PR-AC-002` | Cancel-first replacement is denied unless every gap, capacity, time, and broker-resource prerequisite is proven |
| `PR-AC-003` | Missing ACK leaves acceptance UNKNOWN and cannot trigger an unsafe duplicate replacement |
| `PR-AC-004` | Cancel ACK does not release old-order capacity or establish Final Quantity Proof |
| `PR-AC-005` | Partial fills in every relevant ordering recompute obligation, capacity, cancellation, and egress authority |
| `PR-AC-006` | A new broker ACK alone cannot establish sufficient current protection without field-level proof |
| `PR-AC-007` | Broker rate-limit, session, and order-count exhaustion does not cause blind removal of existing protection |
| `PR-AC-008` | Replacement authorization expiry blocks new transmission but preserves all possible economic effects |
| `PR-AC-009` | Crash or owner failover restores commitments, fences stale writers, and reconciles both orders before action |
| `PR-AC-010` | Control-plane or broker partition blocks new risk and retains conservative gap/overlap capacity |
| `PR-AC-011` | HALT blocks ordinary workflow initiation while only newly authorized HALT-compatible containment may proceed and necessary existing protection is not blindly cancelled |
| `PR-AC-012` | Broker-provided atomic replace is used as atomic only for evidenced profile, order, session, and failure semantics |

---

## 20. Rejected Alternatives

### 20.1 “Cancel then submit is an ordinary two-step workflow”

Rejected. The intermediate gap is an economic safety state requiring prior capacity and authority.

### 20.2 “Submit then cancel is always safer”

Rejected. Simultaneous fills can over-close or reverse exposure and can exhaust broker resources.

### 20.3 “Cancel ACK means the old order is gone”

Rejected. Cancel ACK is not Final Quantity Proof.

### 20.4 “No ACK means retry with a new order ID”

Rejected. Missing ACK is not proof of non-acceptance, and a new ID can duplicate economic effect.

### 20.5 “Protective priority provides capacity”

Rejected. Priority is not reserved risk capacity or broker capacity.

### 20.6 “Protection can be restored after the gap”

Rejected. Documentation, audit, and later remediation do not prevent unsafe exposure during the gap.

### 20.7 “Recovery may clear the workflow and start again”

Rejected. Economic effects and committed capacity survive process and authority lifetime.

---

## 21. Consequences

### 21.1 Positive

- Protection gaps and overlaps become explicit, bounded economic states.
- Cancel, ACK, proof, capacity, and order semantics remain distinct.
- Broker-specific atomicity claims cannot leak into unsupported paths.
- Crash recovery preserves possible old and new effects.
- Strategy and administrative paths cannot bypass protective cancellation authority.

### 21.2 Negative

- More capacity may be held during replacement.
- Some replacements will be denied when broker semantics or resources are uncertain.
- Recovery and reconciliation become more complex.
- Evidence requirements expand across partial-fill and failure interleavings.

These costs are accepted because an unavailable replacement is safer than an unbounded or falsely completed replacement.

---

## 22. Traceability

| Requirement | ADR coverage |
|---|---|
| SAFE-002, SAFE-004, SAFE-013 | Unmanaged exposure, hard envelope, gap and overlap aggregate risk |
| SAFE-011 | Cancellation and final egress non-bypassability |
| SAFE-015 | RCL-only capacity mutation and conservative release |
| SAFE-020, SAFE-021 | Intent lineage, idempotency, duplicate-effect containment |
| SAFE-022, SAFE-023, SAFE-025 | Reconciliation, evidence, partial fills, and asynchronous outcomes |
| SAFE-032 | Session, venue, and tradability constraints |
| SAFE-040, SAFE-041, SAFE-043 | Protective fallback, safety authority, and exit unavailability |
| SAFE-048 | Partition and stale-owner behavior |
| SAFE-051, SAFE-052 | Executed evidence and replayable interleavings |

---

## 23. Open Questions

1. Which broker and order-type combinations can prove atomic replace semantics?
2. Which first restricted-live scopes can safely use overlap-first replacement without reversal risk?
3. Are any cancel-first modes admissible after numeric gap and capacity bounds are approved?
4. How will broker resource reservation, or its absence, be evidenced per profile?
5. Which event sequences satisfy Final Quantity Proof for each broker capability class?
6. Which numeric gap, overlap, proof, and containment bounds will be approved?

Open questions may only reduce replacement scope or block acceptance. They SHALL NOT permit an unevidenced mode.

---

## 24. Approval Gate

This ADR SHALL remain **Proposed** until all of the following are complete:

1. at least one concrete replacement mode and broker profile is approved;
2. numeric gap, overlap, proof, and containment bounds receive human approval;
3. dedicated evidence items are registered for every `PR-AC-*` case;
4. required EV-L1, EV-L2, and EV-L3 evidence covers partial-fill and failure interleavings;
5. Risk Capacity Ledger, Cancellation Arbiter, ADR-002-013 final egress and credential/route boundary, and recovery behavior receive independent review with applicable EGRESS evidence;
6. ADR-002-016 preserves request, old/new order, claim, first-byte, ACK, fill, cancel, gap, overlap, Final Quantity Proof, and recovery lineage without using missing evidence as release proof, and applicable ERI evidence passes;
7. residual broker-resource and market-liquidity risks are explicitly accepted;
8. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship of this ADR does not prove safe replacement and does not authorize restricted-live or production operation.
