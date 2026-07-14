# ADR-002-030 — Post-Trade Economic Obligations, Settlement Finality, and Conservative Account-State Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Post-trade economic-obligation identity and lifecycle, fill-created obligations, fees, tax, interest, financing, settlement, cash availability, margin and collateral, borrow and recall, exercise and assignment, corporate-action obligations, custody and transfers, statement coverage, breaks and corrections, field-specific finality, capacity coupling, currentness, evidence, recovery, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-004, SAFE-010 through SAFE-015, SAFE-020 through SAFE-025, SAFE-030 through SAFE-035, SAFE-040 through SAFE-044, SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§3.1, 9.1, 10.4–10.10, 11–15, 17, 20, 22–24, and 29; VER-002-001 §§5, 362–373, 374, and 377–381
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-029

---

## 1. Decision

The Trading Operating System SHALL represent every safety-relevant post-trade economic effect as an exact, immutable, versioned set of **Economic Obligation Records**. This applies to full and partial fills, fees, tax, interest, financing, settlement, cash and collateral movement, margin calls and releases, borrow and recall, exercise and assignment, corporate actions, custody and transfers, breaks, corrections, reversals, and broker, clearing, or custodian statement facts.

One active ADR-002-014 governed **Post-Trade Finality Policy** SHALL define supported obligation classes, exact leg construction, identity and scope, source-authority rules, field-specific evidence, finality proof recipes, statement coverage, netting and availability rules, correction behavior, dependency closure, invalidation, conservative failure response, currentness, evidence, and recovery.

The **Post-Trade Obligation Ledger** (PTOL) SHALL be the sole serialization authority for the TOS obligation-lifecycle dimension. It SHALL append and order obligation identities, versions, lifecycle transitions, breaks, supersessions, finality-proof bindings, and the monotonic **Post-Trade Obligation Generation**. It does not create external economic truth, cash, collateral, legal title, settled assets, risk capacity, live authority, or transmission permission.

The Risk Capacity Ledger remains the sole capacity mutation and serialization authority. An obligation compiler, Reconciliation Service, PTOL, position or cash projection, statement processor, evidence service, recovery workflow, operator, or finality proof SHALL NOT create, change, quarantine, transfer, remap, or release capacity. PTOL state may support an evidence-bound RCL command, but only the RCL may perform the transition.

Execution finality, trade-capture finality, settlement-instruction acceptance, settlement completion, cash availability, collateral eligibility, custody or legal-title finality, fee or tax finality, borrow discharge, and corporate-action finality are orthogonal facts. Final Quantity Proof establishes only final cumulative filled quantity and zero remaining executable quantity for the applicable broker order. It does not prove any post-trade obligation final.

Missing, stale, conflicting, ambiguous, incomplete, common-mode, unbounded, or unverifiable post-trade state SHALL remain UNKNOWN for the greatest credible dependency closure. It consumes conservative capacity and blocks affected new risk. A broker or custodian statement, API status, portal display, transfer acknowledgement, quiet interval, cutoff, calendar date, operator statement, or absence of a correction cannot convert UNKNOWN into finality or permission.

Capacity SHALL transfer conservatively across order, position, and post-trade-obligation usage without creating headroom during an uncertain transition. A flat position, closed order, passed settlement date, `FINALITY_PROVEN` artifact, favorable receivable, or statement balance SHALL NOT release capacity by itself. Existing or possible economic effect survives policy, authority, proof, workflow, statement, session, credential, incident, and recovery expiry.

Every material obligation, source, statement, break, correction, finality, mapping, account, cash, collateral, margin, borrow, custody, or policy change SHALL advance or invalidate the affected Post-Trade Obligation Generation. Stale PTOL writers and consumers, stale authority and writer epochs, restored instances, and older finality proofs SHALL be fenced before RCL mutation, authority issuance, or future broker-directed transmission.

Any broker-, clearing-, custodian-, bank-, or transfer-directed economic instruction SHALL use a separately governed exact Intent, approval, conservative effect, capacity commitment, current authority, and the ADR-002-013 Final Egress Trust Boundary. The Broker Adapter / Egress Gateway remains the final transmission enforcement point. PTOL, reconciliation, statement, evidence, dashboard, recovery, and operator identities SHALL NOT hold a usable external-economic credential and route or bypass final egress.

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Priority is not reserved protective capacity. Documentation, statements, audit, monitoring, replay, postmortems, and written verification cases do not substitute for prevention, field-specific finality, or executed evidence. Recovery, statement arrival, break repair, service health, and replay cannot revive prior authority or automatically re-arm.

---

## 2. Context

ADR-002-002 governs exclusive capacity, order-to-position transfer, and proof-gated release. ADR-002-004 defines broker-specific Final Quantity Proof. ADR-002-006 defines generic per-field confidence. ADR-002-010 defines corporate and non-trade event identity and conservative transition envelopes. ADR-002-016 governs evidence custody. ADR-002-017 governs recovery. ADR-002-019 governs pre-send account, margin, borrow, and settlement constraints. ADR-002-021 governs aggregate risk projection.

Those decisions mention post-trade effects but do not define one complete obligation and finality protocol. In particular, they do not define:

- the exact obligation legs created by an ordinary fill or partial fill;
- a lifecycle independent from order, position, knowledge, capacity, and instruction state;
- field- and class-specific economic finality proof;
- the distinction among settled, withdrawable, buying-power, and collateral-eligible cash;
- collateral encumbrance, haircut, and double-use prevention;
- borrow, loan, recall, return, forced buy-in, and fee obligations;
- custody transfer and legal-title ambiguity;
- broker, clearing, and custodian statement coverage and restatement semantics;
- correction or break propagation that reopens an earlier finality claim; or
- active generation fencing from obligation change through RCL, authority, and final egress.

Without this contract, a system can close a position and release capacity while a settlement payable, fee, margin call, borrow recall, delivery, or transfer obligation remains. It can also treat a preliminary or incomplete statement as proof, double-use pending cash or collateral, destroy correction history, or let post-trade infrastructure become an alternate economic-action route.

---

## 3. Decision Drivers

1. Order and position state do not fully describe economic obligations.
2. Finality is class-, field-, source-, account-, and legal-context-specific.
3. Favorable receivables and apparent offsets must not create unproven headroom.
4. Corrections, busts, restatements, and delayed notices can reopen earlier conclusions.
5. Statements require exact completeness and revision evidence.
6. Post-trade processing must remain separate from risk, capacity, authority, and transmission.
7. Obligation changes must invalidate future permission through a fenced generation.
8. Recovery and replay must preserve obligations without reviving authority.
9. Unknown state must consume conservatively and block new risk.
10. Written cases and registered evidence must never be mistaken for completed verification.

---

## 4. Scope and Non-Scope

This ADR governs:

- Post-Trade Finality Policy and Post-Trade Obligation Generation;
- exact obligation identities, legs, lifecycle, and dependency closure;
- fill-created settlement, fee, tax, financing, and cash legs;
- settlement, cash availability, margin, collateral, borrow, recall, exercise, assignment, delivery, custody, and transfer obligations;
- statement coverage, source common modes, breaks, corrections, reversals, and restatements;
- class-specific finality proof and invalidation;
- conservative PTOL, Aggregate Risk Authority, RCL, authority, and final-egress coupling;
- partition, compromise, recovery, evidence, and acceptance behavior.

It does not decide:

- broker-order Final Quantity Proof, which remains ADR-002-004;
- generic evidence confidence, which remains ADR-002-006;
- corporate-action or non-trade-event classification and transformation, which remain ADR-002-010;
- evidence custody and replay, which remain ADR-002-016;
- recovery readiness, which remains ADR-002-017;
- pre-send order admissibility, which remains ADR-002-019;
- aggregate-risk amount or capacity need, which remains ADR-002-021;
- capacity mutation, which remains exclusively with the RCL;
- concrete accounting, clearing, settlement, custody, banking, or broker products;
- tax or legal advice; or
- production authorization.

Unsupported external economic instructions remain prohibited from live use. This ADR does not create a general-purpose cash, custody, exercise, transfer, or broker-order transmission method.

---

## 5. Definitions

### 5.1 Post-Trade Finality Policy

The immutable policy defining supported obligation classes, exact leg semantics, source authority, field evidence, finality recipes, statement coverage, netting, availability, breaks, corrections, invalidation, currentness, evidence, and failure response.

### 5.2 Economic Obligation Record

An immutable versioned record of one exact payable, receivable, asset-delivery, cash, collateral, margin, borrow, custody, fee, tax, financing, exercise, assignment, corporate-action, or transfer obligation and its causal lineage. It grants no authority.

### 5.3 Obligation Leg

One exact economic debit, credit, delivery, receipt, encumbrance, release, return, or contingent effect bound to account, legal entity, asset or instrument, currency, quantity or amount, value date, settlement or custody location, source event, and uncertainty.

### 5.4 Post-Trade Obligation Ledger

The fenced append-only serializer for obligation identities, versions, lifecycle transitions, breaks, supersessions, proof bindings, and Post-Trade Obligation Generation. It is not the Risk Capacity Ledger and cannot move external assets or money.

### 5.5 Post-Trade Obligation Generation

A monotonic generation identifying the current policy-compatible active obligation set, source and statement revisions, breaks, corrections, proofs, writer ownership, and restrictive state for an exact dependency scope.

### 5.6 Active Economic Obligation Set

An immutable exact-scope consistency cut of all potential, recognized, due, in-flight, partially satisfied, finality-pending, disputed, corrected, trapped, and otherwise unresolved obligations. A favorable subset or union of narrower sets is invalid.

### 5.7 Post-Trade Finality Proof

A non-authorizing field- and obligation-class-specific proof that the exact declared obligation leg reached the declared finality state under the current policy, source capability, evidence, coverage, correction, time, and generation rules.

### 5.8 Post-Trade Break Record

An immutable restrictive record of any mismatch, omission, duplicate, timing conflict, failed settlement, failed delivery, statement disagreement, correction, or inability to establish obligation identity, amount, state, or finality.

### 5.9 Statement Coverage Manifest

An immutable record of exact source, account, period, cutoff, timezone, pages or cursors, scope, issue and revision identity, preliminary or final class, exclusions, correction semantics, completeness result, and common modes for one statement set.

### 5.10 Economic Finality

The field-specific evidenced completion of an obligation under one approved proof recipe. It is not a universal trade-level boolean and does not itself release capacity or prove resulting assets are available for a different use.

---

## 6. Safety Invariants

### PTF-INV-001 — Complete Exact Obligation Set

Every safety-relevant effect has an exact policy-owned obligation classification and complete greatest-credible leg set. Missing applicability or scope is included conservatively, never self-exempted.

### PTF-INV-002 — Finality Dimensions Are Orthogonal

Order FQP, trade capture, instruction acceptance, settlement, cash availability, collateral eligibility, custody title, fee finality, borrow discharge, and corporate-action finality do not imply one another.

### PTF-INV-003 — Identity and Lineage Are Exact

Every obligation binds exact source event, account, legal entity, instrument or asset, quantity or amount, currency, value date, location, source continuity, generation, and supersession lineage.

### PTF-INV-004 — Absence Is Not Finality

Silence, quiet time, cutoff passage, missing page, absent correction, empty query, flat position, zero statement balance, or missing ACK never proves that an obligation does not exist or is final.

### PTF-INV-005 — Finality Proof Is Class-Specific

One global `SETTLED`, `CLOSED`, confidence score, statement flag, or operator decision cannot replace exact per-field proof under the active policy and source capability.

### PTF-INV-006 — UNKNOWN Is Restrictive

Unknown, stale, conflicting, incomplete, common-mode, unbounded, or unverifiable post-trade state consumes conservative capacity and blocks affected new risk.

### PTF-INV-007 — No Unproven Netting or Reuse

An uncertain receivable cannot fund a payable, pending proceeds cannot become available cash, and an unproven offset cannot create headroom. Netting and reuse require exact current positive proof.

### PTF-INV-008 — RCL Is the Sole Capacity Authority

Only the RCL may create, change, quarantine, transfer, remap, or release capacity. PTOL and finality artifacts create no capacity transition.

### PTF-INV-009 — Obligation Transition Transfers, Not Releases, Risk

Order or position closure transfers applicable consumption to post-trade obligations. It does not release usage while any resulting economic effect or uncertainty remains.

### PTF-INV-010 — Cash Semantics Are Exact

Ledger cash, pending cash, settled cash, withdrawable cash, buying power, and collateral-eligible cash remain distinct and cannot be silently substituted.

### PTF-INV-011 — Collateral Encumbrance Is Conserved

Pledge, haircut, eligibility, FX, location, substitution, release, and shared-pool state are exact. The same collateral cannot be counted available or pledged twice.

### PTF-INV-012 — Borrow Lifecycle Is Exact

Locate, availability, executed loan, utilization, recall, return instruction, confirmed return, buy-in, fee, and closeout are distinct. Recall silence and return ACK are not discharge.

### PTF-INV-013 — Correction Reopens Affected Finality

Breaks, busts, corrections, reversals, and restatements append new versions, preserve old and new credible effects, advance generation, and invalidate affected proof and future permission.

### PTF-INV-014 — Statement Coverage and Independence Are Proven

Statements are evidence only when exact coverage and revision are proven. Broker API and broker statement, or broker and custodian records sharing one book, parser, administrator, or transport, do not count as independent paths.

### PTF-INV-015 — Active Generation Is a Negative Gate

RCL mutation, authority issuance, and final egress actively verify current policy, Post-Trade Obligation Generation, active-set completeness, breaks, proof, and invalidation. Success only avoids denial and never creates permission.

### PTF-INV-016 — External Economic Egress Is Non-Bypassable

PTOL, reconciliation, statement, evidence, dashboard, recovery, and operator identities cannot hold or obtain a usable external-economic credential and route. Every transmitted instruction uses the final egress boundary.

### PTF-INV-017 — Economic Effect Outlives Artifacts

Policy, proof, statement, session, credential, authority, incident, workflow, or evidence expiry never expires an obligation, settlement effect, asset claim, cash effect, borrow, UNKNOWN, or capacity commitment.

### PTF-INV-018 — Evidence and Recovery Do Not Revive

Documentation, statements, audit, monitoring, replay, break repair, recovery, backlog drain, or operator acknowledgement does not substitute for prevention or proof, restore prior authority, or automatically re-arm.

---

## 7. Authority Ownership and Separation

| Function | Owning authority | Prohibited collapse |
|---|---|---|
| Publish broker order/fill fact | broker evidence path under ADR-002-004/006 | observation cannot declare settlement or cash finality |
| Classify corporate/non-trade event | ADR-002-010 and Reconciliation Service | event classification cannot release capacity or close obligations |
| Govern post-trade semantics | Post-Trade Finality Policy governance under ADR-002-014 | compiler, PTOL, statement processor, or operator cannot self-activate a permissive rule |
| Compile candidate obligation legs | Post-Trade Obligation Service | produces non-authorizing candidate records only |
| Evaluate per-field confidence and finality | Reconciliation Service under ADR-002-006 | cannot mutate PTOL or RCL outside evidence-bound commands |
| Serialize obligation lifecycle | PTOL only | cannot invent external truth, assess aggregate risk, mutate capacity, or transmit |
| Produce projections | position, cash, collateral, custody, and obligation read models | projections cannot overwrite PTOL or reconciliation truth |
| Evaluate aggregate risk | Aggregate Risk Authority under ADR-002-021 | cannot declare finality or mutate capacity |
| Mutate or release capacity | RCL only | no obligation or proof status performs an implicit transition |
| Issue live authority | Safety Authority / Live Authorization Service | favorable post-trade state is only an input |
| Transmit external instruction | Broker Adapter / Egress Gateway inside ADR-002-013 boundary | no direct PTOL, reconciliation, statement, UI, or recovery route |
| Preserve evidence and replay | ADR-002-016 services | custody and replay create no finality or authority |
| Recover and re-arm | ADR-002-017/007/015 workflow | recovery cannot self-prove finality or auto re-arm |

An identity that can alter obligation policy, source mapping, statement coverage, finality rules, PTOL state, or proofs SHALL NOT also release RCL capacity or control a usable external-economic route. Effective control and recovery paths, not service names, determine separation.

---

## 8. Post-Trade Finality Policy and Registry

The policy SHALL bind at minimum:

- supported obligation classes, environments, accounts, legal entities, brokers, clearing systems, custodians, settlement locations, currencies, and instruments;
- exact obligation-leg schemas, units, signs, rounding, balancing, attribution, materiality, and dependency closure;
- approved event, broker, clearing, custody, banking, statement, and reference sources;
- source continuity, field confidence, common-mode, freshness, correction, and finality recipes;
- availability, encumbrance, netting, setoff, settlement, cash, margin, collateral, borrow, custody, and transfer rules;
- PTOL writer fencing, Post-Trade Obligation Generation, active-set construction, RCL coupling, invalidation, and final-egress currentness;
- break, incident, evidence, retention, recovery, and failure responses.

Unknown materiality is material. A producer, compiler, account projection, strategy, operator, or consumer SHALL NOT self-exempt an obligation class because its amount appears small, favorable, operational, or inconvenient.

Policy activation creates no obligation fact, finality, capacity, authority, settled asset, cash availability, or broker permission.

---

## 9. Economic Obligation Identity and Exact Leg Model

Each Economic Obligation Record SHALL contain:

- obligation identity, type, version, canonical digest, status, and Post-Trade Obligation Generation;
- exact causal source event identities and digests;
- account, subaccount, legal entity, beneficial owner where relevant, broker, clearing member, custodian, bank, venue, and settlement location;
- instrument, asset, currency, quantity, amount, unit, sign, multiplier, price basis, FX basis, rounding, and tolerance;
- trade, record, ex, due, value, settlement, recall, delivery, payable, and observation dates where applicable;
- debit, credit, delivery, receipt, encumbrance, release, return, and contingent legs;
- source continuity, statement and correction bindings, confidence and conservative bounds;
- lifecycle, finality, break, supersession, invalidation, capacity, and evidence bindings.

A partial fill creates proportionate and independently identifiable obligations. Different events, accounts, currencies, value dates, legal entities, settlement systems, or custody locations cannot be merged because they appear economically similar.

Where balanced accounting legs cannot be positively established, the missing counterleg remains explicit and the greatest credible adverse union is used. A consumer cannot construct a favorable balancing entry locally.

---

## 10. Obligation Lifecycle and Orthogonal State

An obligation lifecycle MAY use:

```text
POTENTIAL
    -> RECOGNIZED
    -> DUE
    -> IN_FLIGHT
    -> PARTIALLY_SATISFIED
    -> SATISFIED_PENDING_FINALITY
    -> FINALITY_PROVEN
    -> CLOSED

Any state -> BREAK_OPEN
Any state -> CORRECTION_PENDING
Any state -> FAILED_OR_TRAPPED
Any state -> SUPERSEDED
```

The lifecycle remains orthogonal to:

- ADR-002-006 Knowledge/Evidence State;
- Post-Trade Finality Proof state;
- Post-Trade Break state;
- RCL Capacity State;
- broker, clearing, custodian, or bank instruction state;
- position, cash, margin, collateral, borrow, and custody projections.

`SATISFIED_PENDING_FINALITY` is not final. `FINALITY_PROVEN` proves only the exact declared leg and proof class. `CLOSED` preserves immutable lineage and can be superseded by a later correction without destructive overwrite. No lifecycle state creates capacity release, available cash, legal title, or permission.

---

## 11. Field-Specific Finality Proof

A Post-Trade Finality Proof SHALL bind:

- exact obligation identity, version, leg, scope, amount or quantity, account, currency, value date, and generation;
- Post-Trade Finality Policy and applicable Broker, Clearing, Custodian, or Banking Capability Profile;
- source-native identifiers, revisions, statement coverage, page/cursor completeness, continuity, and raw evidence;
- applicable acknowledgement, booking, settlement, custody, return, correction, and legal-finality semantics;
- per-field confidence, corroboration or accepted single-source residual, time evidence, correction horizon, and unresolved common modes;
- exact finality class and what it does not prove;
- invalidation conditions, dependency closure, evidence receipts, and explicit non-authorizing flags.

The proof SHALL be non-transferable and non-unionable. A proof for one leg, account, currency, value date, source revision, or finality class cannot be patched or reused for another.

Proof expiry may deny its use for future authority, but it never expires the underlying economic effect. A later correction supersedes the proof, advances generation, and invokes conservative transition; it does not erase history.

---

## 12. Fills and the Execution-Finality Boundary

Every confirmed full or partial fill SHALL create or update exact trade-capture, settlement, asset, cash, fee, tax, financing, margin, and borrow obligation legs applicable under policy. The fill-to-obligation commit SHALL be idempotent and causally linked to the originating Intent, attempt, broker order, fill revision, position transfer, and RCL allocation.

Final Quantity Proof establishes the broker order's final cumulative fill and zero remaining executable quantity. It does not prove:

- trade capture is free from later bust or correction;
- cash or securities settled;
- proceeds are withdrawable or collateral-eligible;
- fees, tax, interest, or financing are final;
- borrow or delivery obligations are discharged;
- custody or legal title is final.

Missing ACK remains possible acceptance. Cancel ACK remains insufficient for Final Quantity Proof. A fill discovered after a claimed terminal outcome is applied idempotently, creates or corrects obligations, advances generation, preserves capacity, and triggers incident or profile review where required.

---

## 13. Fees, Tax, Interest, and Financing

Fee, commission, levy, tax, withholding, interest, financing, borrow fee, custody charge, and other monetary adjustments SHALL be exact obligation legs with source, calculation basis, currency, period, effective time, due date, provisional/final status, and correction behavior.

Estimated or accrued amounts remain distinct from broker-booked and legally final amounts. A missing line item or zero estimate is not proof of zero. Favorable rebates or credits cannot offset confirmed adverse obligations unless exact enforceable netting is positively proven.

Corrections and backdated charges SHALL preserve prior observations, create superseding records, recompute the greatest credible account and aggregate effect, and invalidate affected cash, margin, risk, and authority state. A small expected amount does not authorize silent omission.

---

## 14. Settlement and Cash Availability

The system SHALL distinguish at minimum:

- trade-date payable or receivable;
- settlement instruction created, accepted, matched, failed, or pending;
- partial settlement;
- debit or credit booked;
- settled ledger cash;
- withdrawable cash;
- buying power;
- collateral-eligible cash;
- restricted, reserved, disputed, reversed, or trapped cash.

Sale proceeds, expected dividends, pending FX, receivables, or broker buying power are not settled or reusable cash by default. A confirmed settlement can transfer risk into a resulting asset, cash, tax, financing, or custody state; it does not necessarily release aggregate capacity.

Different currencies, accounts, legal entities, value dates, settlement systems, or counterparties cannot be netted unless the active policy proves legal enforceability, operational finality, timing, amount, common-mode independence, and current availability. Unknown or failed settlement blocks new risk for the affected dependency scope.

---

## 15. Margin, Collateral, and Encumbrance

Margin and collateral state SHALL bind exact account and legal entity, owner, asset, currency, quantity, valuation, haircut, eligibility, concentration, location, pledgee, encumbrance, substitution, release, settlement, and effective time.

The TOS SHALL distinguish a margin observation, margin call, collateral request, instruction acknowledgement, pledged collateral, accepted collateral, available excess, and confirmed release. No one state implies another.

The same collateral unit SHALL NOT be counted as both free and encumbered, pledged to two obligations, or reusable before confirmed release. A broker's favorable margin, buying-power, or collateral figure is a Critical Input and ceiling/observation, not unconditional proof.

Haircut, eligibility, FX, valuation, margin-model, call, settlement, or custody change is material and invalidates dependent risk, obligation, authority, and egress decisions. Unknown encumbrance or common pool scope expands conservatively.

---

## 16. Borrow, Recall, Return, and Buy-In

The system SHALL distinguish:

- locate or indicative availability;
- approved borrow allocation;
- executed loan and utilized quantity;
- fees, collateral, mark-to-market, and contractual terms;
- recall notice and effective deadline;
- return instruction and acknowledgement;
- confirmed return or closeout;
- forced buy-in, replacement borrow, failure, and residual obligation.

A locate is not an executed loan. Borrow availability is not proof that a recall does not exist. Silence, provider health, missed notice, or cutoff passage is not proof of no recall. Return request or ACK is not proof of discharged quantity.

Recall, fee, collateral, buy-in, return, or source-continuity uncertainty consumes conservative capacity, blocks affected new risk, and may require containment. A planned purchase or return does not reduce an obligation until the required evidence is final.

---

## 17. Exercise, Assignment, Delivery, and Corporate-Action Obligations

ADR-002-010 owns lifecycle and non-trade event identity and transformation. This ADR owns the resulting obligation legs and their finality.

Exercise, assignment, expiry, delivery, cash settlement, conversion, redemption, distribution, tender, rights, and corporate-action events SHALL model every credible asset, cash, fee, tax, financing, margin, borrow, custody, and delivery leg.

An ADR-002-010 event state such as `APPLIED_LOCAL` or `RECONCILED` does not prove its resulting obligations final. Absence of an exercise, assignment, delivery, or corporate-action report at a local deadline is not proof that no obligation exists.

Voluntary elections or required instructions use the complete separately governed external-economic action path. UI selection, event status, priority, or operator label creates no intent, capacity, authority, protective classification, or transmission permission.

---

## 18. Custody, Transfers, and Legal Title

Custody and transfer state SHALL bind exact source and destination account, beneficial and legal owner where relevant, asset, quantity, currency, location, custodian, settlement system, instruction, status, value date, encumbrance, evidence, and common modes.

The system SHALL distinguish instruction acceptance, source debit, in-flight state, destination credit, custody booking, availability, and legal-title or beneficial-entitlement finality. Transfer ACK, source disappearance, destination display, or matching quantity alone does not prove the complete chain.

During uncertainty, the asset or cash SHALL NOT disappear from aggregate risk or become available twice. The greatest credible source, destination, in-flight, loss, delay, reversal, fee, and encumbrance union remains represented and capacity-consuming.

Custody or transfer read identities SHALL NOT possess a usable write credential and external route. If a combined credential is unavoidable, ADR-002-013 confinement applies and affected live scope is reduced or prohibited until bypass is disproven.

---

## 19. Broker, Clearing, and Custodian Statements

A Statement Coverage Manifest SHALL establish at minimum:

- exact source, endpoint or delivery method, account and subaccount, legal entity, and statement type;
- reporting period boundaries, inclusive/exclusive semantics, cutoff, timezone, business calendar, and value-date treatment;
- source continuity, issue identity, revision, preliminary/final classification, restatement and correction horizon;
- expected and received pages, files, sections, cursors, checksums, record counts, exclusions, and missing intervals;
- covered instruments, assets, currencies, obligation classes, custody locations, and external/manual channels;
- common modes with APIs, portals, custodians, clearing systems, parsers, administrators, and transports;
- completeness result, uncertainty, evidence, and restrictive disposition.

A statement is one evidence path. `FINAL`, contractual, signed, or independently delivered does not make it unconditional truth outside the approved proof recipe. Absence of a line item is negative evidence only when exact coverage, correction semantics, and source capability positively support that interpretation.

Preliminary, incomplete, stale, conflicting, revised, missing, or unbounded statement coverage creates a Post-Trade Break and blocks affected new risk. A favorable statement cannot silently replace a more adverse current source.

---

## 20. Breaks, Busts, Corrections, Reversals, and Restatements

A Post-Trade Break Record is mandatory for any source mismatch, amount or quantity difference, duplicate, omission, timing conflict, unmatched leg, failed settlement, failed delivery, unresolved cash or collateral change, borrow discrepancy, incomplete statement, or finality conflict.

The record SHALL contain exact scope, first observation, credible start interval, source and statement revisions, old and new obligation versions, conservative economic union, required RCL and authority restrictions, owner, evidence, correction, finality, incident, and closure conditions.

Corrections, busts, reversals, and restatements append facts and compensating or superseding obligations. They SHALL NOT destructively rewrite fill, event, cash, position, obligation, statement, capacity, or evidence history.

Repair, matching totals, operator acknowledgement, statement arrival, timeout, age, or source recovery does not close a break. Closure requires field-specific evidence, exact dependency re-evaluation, current generation, conservative RCL treatment, and independently reviewable proof. Closure creates no capacity release, authority, scope restoration, or re-arm.

---

## 21. Aggregate Risk and RCL Capacity Coupling

The ADR-002-021 Aggregate Risk State Snapshot SHALL include every potential, recognized, due, in-flight, partially satisfied, finality-pending, disputed, corrected, trapped, and UNKNOWN post-trade obligation across every applicable account, legal entity, currency, instrument, settlement, margin, collateral, borrow, custody, and global scope.

Risk benefit from receivable, settlement, collateral, netting, return, corporate action, or transfer requires positive proof. Unknown benefit is zero benefit. Unknown adverse obligation uses the greatest credible bound.

The safe transition order is:

```text
Immutable source event or observation
        ↓
Candidate exact obligation set and independent validation
        ↓
PTOL append / Post-Trade Obligation Generation advance
        ↓
Aggregate-risk evaluation of the conservative obligation union
        ↓
RCL independently commits, transfers, or quarantines capacity
        ↓
Later field-specific finality proof
        ↓
RCL independently verifies proof and performs any allowed transfer or release
```

For an internally controlled economic instruction, required capacity is committed before final egress. For an external effect observed after it occurred, PTOL records and RCL quarantine/restriction are ordered as one conservative safety transition; ambiguity assumes the obligation exists.

`FINALITY_PROVEN` is necessary only where policy requires it and is never sufficient for release. The RCL verifies current proof, policy, generation, scope, obligation set, resulting asset or cash state, risk decision, writer epoch, and all affected limits. It may transfer consumption rather than release it. If any check is missing or stale, capacity remains consumed.

---

## 22. Active Currentness, Authority, and Final Egress

ADR-002-024 SHALL include, where applicable, these dimensions in the Safety Currentness Vector:

1. exact Post-Trade Finality Policy identity, generation, digest, and approval state;
2. current Post-Trade Obligation Generation and fenced PTOL writer epoch;
3. exact Active Economic Obligation Set identity, digest, scope, completeness, and age;
4. applicable Post-Trade Breaks, correction and statement revisions, and unresolved UNKNOWN state;
5. exact finality-proof identities and invalidation status used by the decision;
6. current RCL capacity and aggregate-risk bindings;
7. source continuity, capability profile, trustworthy-time, recovery, and incident generations.

The RCL, new-risk authority issuers, and final egress SHALL actively establish these facts where dependent operation requires them. Cached favorable state, TTL, last statement, heartbeat, service health, previous generation, eventual consistency, or absence of correction is not currentness proof.

If a restrictive obligation change is ordered before capability claim, the send is denied. If ordering between a material obligation invalidation and first broker-directed byte cannot be proven, the attempt remains potentially live, all credible effects remain capacity-covered, and blind retry is prohibited.

Every external economic instruction SHALL bind exact obligation, policy, effect, approval, capacity, authority, capability, finality prerequisites, and currentness. Final egress verifies and enforces; it does not invent an instruction, declare finality, release capacity, or reinterpret a read-only status as permission.

---

## 23. Failure, Partition, Security, and Common-Mode Behavior

| Failure | Mandatory result |
|---|---|
| obligation source, compiler, PTOL, or reconciliation unavailable | block affected new risk; preserve greatest credible obligation union |
| PTOL writer or generation conflict | fence writers; treat both as potentially active until hard fencing is proven |
| statement missing, partial, stale, or conflicting | create break; no absence-based finality or favorable selection |
| broker/custodian API and statement share a common mode | remove independence benefit; restrict or prohibit scope |
| margin, collateral, borrow, cash, settlement, or custody state lost | retain conservative usage and deny dependent new risk |
| finality proof unavailable, stale, or invalidated | keep obligation and capacity conservative |
| post-trade plane partitioned while broker egress is reachable | deny dependent new risk without exact approved fenced currentness |
| correction races RCL or send | preserve old/new union; no release or blind retry |
| PTOL, statement, evidence, or operator credential compromised | restrict greatest credible shared scope; rotate and fence; no self-attested recovery |
| restore or backlog drain completes | new generation and closed recovery barrier remain; no authority revival |

Source, compiler, parser, policy, PTOL, RCL read model, statement, broker, clearing, custodian, bank, clock, message bus, datastore, administrator, identity, deployment, or network common modes SHALL be disclosed. Different service names do not prove independence.

No PTOL, reconciliation, statement, evidence, replay, support, custody-read, dashboard, or recovery principal may hold both usable external-economic authority and a route. An unavoidable combined read/write credential is a declared ADR-002-013 common-mode exception and may make the affected live scope non-conforming.

---

## 24. Evidence, Recovery, and Non-Revival

ADR-002-016 evidence SHALL preserve:

- raw fill, broker, clearing, custody, bank, statement, portal, support, and external records;
- exact obligation compilation, versions, legs, generation, writer, lifecycle, break, correction, and finality transitions;
- source continuity, page/cursor completeness, statement revisions, common modes, uncertainty, and time evidence;
- aggregate-risk and RCL admission, transfer, quarantine, rejection, and release decisions;
- currentness, egress, partition, compromise, incident, recovery, and re-arm evidence;
- negative, missing, conflicting, duplicate, late, revised, and inconclusive outcomes.

Evidence custody does not own obligation truth, finality, PTOL, capacity, authority, or transmission. A statement, registered item, dashboard, successful replay, matching projection, or absence of recorded breaks is not executed verification evidence.

ADR-002-017 Recovery Inventory Cuts and Obligation Graphs SHALL include the complete active obligation set, policy and generation, PTOL writer and restore state, breaks, statement coverage, finality proofs, source continuity, corrections, RCL bindings, external instructions, and greatest credible unresolved effects.

Startup, restart, reconnect, failover, restore, backlog drain, statement arrival, break repair, evidence repair, replay match, operator return, or Recovery Readiness Decision cannot reuse a prior proof, authority, capability, live scope, or re-arm decision. Fresh exact artifacts and the complete ADR-002-007/015 governed chain remain mandatory.

---

## 25. Rejected Alternatives

### 25.1 “Final Quantity Proof means the trade is economically final”

Rejected because order quantity finality does not prove settlement, fees, cash, custody, borrow, or delivery.

### 25.2 “The broker statement is the ledger of truth”

Rejected because statements can be preliminary, incomplete, revised, scoped, common-mode, delayed, or wrong.

### 25.3 “A flat position releases all capacity”

Rejected because settlement, cash, fee, margin, borrow, custody, tax, or delivery obligations can remain.

### 25.4 “Buying power is available cash”

Rejected because buying power, settled cash, withdrawable cash, and collateral eligibility have different semantics.

### 25.5 “Pending receivables may fund payables”

Rejected without exact enforceable netting, timing, source, and finality proof.

### 25.6 “Transfer acknowledgement proves legal title”

Rejected because instruction acceptance, source debit, destination credit, custody booking, availability, and title are distinct.

### 25.7 “No recall or assignment notice means none exists”

Rejected because source loss, delay, coverage gaps, and correction can produce silence.

### 25.8 “Corrections may update the old row in place”

Rejected because destructive rewrite hides prior decisions, capacity transitions, and unsafe intervals.

### 25.9 “PTOL may release capacity when finality is proven”

Rejected because the RCL is the sole capacity authority and resulting settled state may remain risk-consuming.

### 25.10 “Operations may directly send settlement or transfer instructions”

Rejected because it creates an external-economic egress bypass.

### 25.11 “Priority creates protective settlement capacity”

Rejected because scheduling priority is not reserved protective capacity or external resource guarantee.

### 25.12 “Recovery, replay, or a clean statement restores authority”

Rejected because evidence and recovery do not revive authority or automatically re-arm.

---

## 26. Consequences

### 26.1 Positive

- Economic obligations remain visible after order and position lifecycle changes.
- Finality becomes exact, source-aware, and reviewable rather than a global boolean.
- Cash, collateral, borrow, custody, and settlement availability cannot be silently conflated.
- Corrections and statements preserve history and conservative capacity.
- PTOL, RCL, risk, evidence, recovery, and final egress authorities remain separate.
- Recovery and currentness include the complete post-trade dependency closure.

### 26.2 Negative

- Obligation and statement schemas add material implementation and governance cost.
- Some brokers, custodians, and clearing arrangements may not provide sufficient finality or coverage evidence.
- Capacity may remain consumed for long settlement, transfer, correction, or dispute intervals.
- Common-mode disclosure may reduce supported account, instrument, or event scope.
- Automated external economic instructions may remain prohibited until a conforming route is proven.

These costs are accepted because operational convenience cannot weaken safety requirements or erase an economic obligation.

---

## 27. Acceptance Cases

Written cases define obligations only. They are not completed evidence.

### PTF-AC-001 — Fill/FQP vs Post-Trade Obligation Separation

Full, partial, corrected, and late fills create exact obligation legs; FQP cannot be treated as settlement, cash, fee, custody, borrow, or delivery finality.

### PTF-AC-002 — Fee/Tax/Interest/Financing Legs and Corrections

Estimated, booked, corrected, backdated, missing, and conflicting monetary legs remain exact, versioned, and conservative without favorable zero defaults.

### PTF-AC-003 — Settlement, Cash Availability, Partial/Failure Semantics

Instruction acceptance, partial settlement, booking, settled cash, withdrawable cash, buying power, and collateral eligibility remain distinct under delay, failure, reversal, and correction.

### PTF-AC-004 — Margin/Collateral/Encumbrance/Haircut/Double-Use

Margin calls, haircut and FX changes, pledge, substitution, eligibility, release, and shared pools cannot double-count or create unproven available collateral.

### PTF-AC-005 — Borrow/Recall/Return/Buy-In

Locate, loan, recall, return instruction, confirmed discharge, fee, collateral, replacement borrow, and buy-in are independently tracked and fail closed under silence or conflict.

### PTF-AC-006 — Exercise/Assignment/Delivery/Corporate-Action Obligations

Delayed or missing notice, partial assignment, cash or physical settlement, delivery, conversion, and event corrections preserve every credible obligation and never become zero risk from event status alone.

### PTF-AC-007 — Custody/Transfer/In-Flight/Legal-Title Behavior

Source, in-flight, destination, custody booking, availability, encumbrance, and title ambiguity cannot make an asset disappear or become available twice.

### PTF-AC-008 — Statement Coverage, Provenance, Conflict/Common-Mode

Preliminary, truncated, paginated, stale, revised, conflicting, and common-mode statements cannot prove completeness, zero obligation, or independent corroboration.

### PTF-AC-009 — Breaks/Busts/Corrections/Reversal/Finality Reopen

Breaks and later source revisions append immutable history, reopen affected proof, preserve the old/new credible union, advance generation, and invalidate future permission.

### PTF-AC-010 — RCL Transfer/Release + Generation Currentness/Send Race

PTOL never mutates capacity; RCL independently performs proof-bound transfers or release, stale generations are rejected, and invalidation-versus-first-byte ambiguity remains potentially live and capacity-covered.

### PTF-AC-011 — Partition/Compromise/Stale Writer/Route Bypass

Post-trade partition with broker reachability, compromised source or statement paths, stale PTOL writers, combined credentials, and alternate routes deny new risk and cannot bypass final egress.

### PTF-AC-012 — Evidence/Recovery/Non-Revival/Status Honesty

Documents, statements, registration, monitoring, audit, replay, break repair, recovery, and readiness cannot claim completed evidence, release effect, restore authority, or automatically re-arm.

---

## 28. Requirements Traceability

| Requirement | Discharge |
|---|---|
| SAFE-004, SAFE-012, SAFE-013 | complete conservative obligation effects remain inside the hard and aggregate envelope (§§9–21) |
| SAFE-010, SAFE-011, SAFE-014, SAFE-015 | post-trade processing never substitutes for prevention; capacity and external action remain non-bypassable (§§7, 21–23) |
| SAFE-020, SAFE-021 | exact origin, retry, acknowledgement, correction, and external-instruction lineage (§§9, 12, 22) |
| SAFE-022 through SAFE-025 | field-level reconciliation, continuous external-state detection, and partial/asynchronous/corrected effects (§§10–20) |
| SAFE-030, SAFE-031, SAFE-034, SAFE-035 | source provenance, independence, common mode, statement coverage, and trustworthy time (§§8, 11, 19, 23) |
| SAFE-032, SAFE-033 | current post-trade facts constrain exact future account/settlement admissibility and external instructions (§§21–22) |
| SAFE-040 through SAFE-044, SAFE-048 | trapped obligations, containment, partition behavior, recovery inventory, and no automatic re-arm (§§16–24) |
| SAFE-050 | immutable governed policy, exact schema, generation, and fail-closed activation (§§8, 22–23) |
| SAFE-051, SAFE-052 | complete causal evidence, statements, corrections, breaks, replay, and status honesty (§24) |

---

## 29. Open Implementation Questions

1. Which Post-Trade Finality Policy, obligation schemas, leg compiler, independent verifier, and PTOL mechanism are approved?
2. Which broker, clearing, custody, banking, statement, and reference sources and source-authority rules apply to each obligation class?
3. Which finality recipes distinguish instruction acceptance, settlement, cash availability, collateral eligibility, custody title, fee finality, borrow discharge, assignment, delivery, and corporate-action completion?
4. Which PTOL consensus, writer epoch, generation, restore, idempotency, correction, and RCL ordered-transition mechanisms are conforming?
5. Which statement coverage, pagination, cutoff, revision, preliminary/final, correction-horizon, and common-mode rules are approved?
6. Which legally enforceable netting, setoff, cash reuse, collateral reuse, and custody-availability rules are supported?
7. Which external economic instructions are in initial scope, and which remain prohibited pending a conforming exact construction and egress contract?
8. Which accounts, legal entities, currencies, settlement systems, custodians, brokers, instruments, borrow arrangements, and corporate-action classes are in initial restricted-live scope?
9. Which `B_post_trade_effect_to_obligation_commit`, `B_post_trade_change_detect`, `B_post_trade_break_to_restrict`, `B_post_trade_invalid_to_egress_deny`, `B_post_trade_generation_fence`, and `B_statement_coverage_gap_detect` values are approved and measured?
10. Which `MAX_post_trade_obligation_snapshot_age_ms`, `MAX_post_trade_finality_proof_age_ms`, `MAX_statement_coverage_manifest_age_ms`, `MAX_unresolved_post_trade_break_age_ms`, and `MAX_pending_external_transfer_age_ms` values are approved?
11. Which broker/custodian single-source and common-mode residuals require explicit reduced-scope acceptance?
12. Which failure-domain, compromise, partition, correction, restore, and recovery mechanisms prove non-bypass and non-revival?

Unresolved questions reduce or prohibit live scope. They never permit a weaker default, expire an obligation, or release capacity.

---

## 30. Approval and Operational Gates

ADR-002-030 remains `Proposed` until all of the following are satisfied:

1. canonical policy, obligation, active-set, finality-proof, break, and statement-coverage schemas are approved;
2. the obligation compiler, independent verifier, PTOL serializer, writer fencing, generation, restore, idempotency, and correction mechanisms are implemented and security-reviewed;
3. source-authority, source-continuity, statement-coverage, common-mode, and class-specific finality recipes are approved and independently reviewed;
4. fill, fee, tax, interest, financing, settlement, cash, collateral, margin, borrow, recall, exercise, assignment, corporate-action, custody, transfer, break, and correction paths are implemented fail-closed;
5. PTOL-to-Aggregate-Risk/RCL coupling proves conservative ordered transfer, quarantine, and release without making PTOL a capacity authority;
6. current Post-Trade Obligation Generation, active-set completeness, breaks, statements, proofs, and invalidation are actively fenced at the RCL, authority issuance, and final egress without permissive cache or circular trust;
7. every supported external economic instruction uses an exact governed chain and the ADR-002-013 Final Egress Trust Boundary; unsupported routes are physically or logically prohibited;
8. stale authority, PTOL writer, RCL writer, restore, source, statement, proof, and egress generations are fenced;
9. numeric bounds and age limits are approved in the Verification Profile and measured under fault injection;
10. PTF-EV-001 through PTF-EV-012 and every applicable upstream evidence item are executed at their required levels and independently reviewed;
11. partial fill, delayed settlement, statement truncation, common mode, margin/collateral change, borrow recall, assignment, transfer ambiguity, break, correction, partition, compromise, send race, restore, and non-revival tests pass;
12. no Critical or Major finding remains open, including finality, capacity, statement, source, correction, currentness, credential, route, or common-mode findings;
13. Architecture Gate acceptance remains explicit and acceptance, restricted-live, and production status remain `NO` until their own gates pass.

Authorship, EV-L0 review, policy approval, PTOL deployment, statement receipt, finality artifact, matching totals, break closure, successful replay, incident-free operation, recovery readiness, or evidence registration does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize live operation, capacity release, external economic transmission, scope promotion, production use, or automatic re-arm.
