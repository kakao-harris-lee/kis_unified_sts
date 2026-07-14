# ADR-002-025 — Restricted-Live Verification, Progressive Scope Promotion, and Production Authorization Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** EV-L5 restricted-live trial governance, exact trial scope, pre-registration, bounded economic effect, trial authorization prerequisites, abort and demotion, evidence validity, independent review, progressive promotion, production authorization, continuous conformance, recovery, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-021, SAFE-024, SAFE-025, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§9.1, 11, 20, 23, and 28–29; VER-002-001 §§5, 317, and 320–321
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-024

---

## 1. Decision

Restricted-live operation SHALL be treated as a safety-critical, pre-registered, exact-scope experiment under real broker and economic semantics. It is not a softer production mode, an informal canary, an operator convenience, or a source of automatic authority.

Every restricted-live trial SHALL be governed by an active immutable **Restricted-Live Trial Policy** and one exact **Restricted-Live Trial Plan**. The plan binds the complete code, configuration, broker, account, credential, route, session, strategy, instrument, action, capacity, duration, count, evidence, operator, abort, recovery, and residual-risk scope. Unknown or omitted scope is denial.

A Trial Plan, review, schedule, deployment, successful dry run, evidence package, or promotion decision SHALL NOT create capacity, Live Authorization, Transmission Capability, broker permission, protective classification, HALT clear, or re-arm authority. A trial may start only through the complete ADR-002-007/015 governed authorization chain after every applicable architecture decision is Accepted for that exact scope and all pre-trial gates pass.

The Risk Capacity Ledger remains the sole capacity mutation and serialization authority. Before a risk-increasing trial, it SHALL cover the worst credible union of every planned action, partially executed action, potentially-live attempt, existing exposure, protective obligation, external activity window, and abort/recovery overlap. A trial budget is a ceiling and evidence binding; it is not capacity and cannot make UNKNOWN permissible.

Every restricted-live broker transmission SHALL pass the normal final-egress gate. The exact Trial Policy and Plan generations, trial-run identity, remaining authorized count/effect envelope, Live Authorization, capacity and flow commitments, and complete ADR-002-024 currentness proof SHALL be bound at each send. No trial flag, canary label, operator presence, low notional, or monitoring coverage may bypass a normal safety control.

Any Critical invariant violation, unknown economic or broker state, evidence gap, currentness gap, profile drift, unapproved scope change, bound breach, external activity, abort-path failure, or loss of required supervision SHALL trigger monotonic restriction. Restriction may be automatic; permission restoration and scope promotion may not. Abort, expiry, or authorization revocation limits future action only and never erases economic effect or releases capacity.

Trial completion produces one immutable **Restricted-Live Trial Evidence Package**. The package is evidence, not permission. A **Production Scope Promotion Decision** may declare only that one exact evidence-backed scope is eligible to request a fresh configuration activation and Live Authorization. It cannot be unioned, widened, reused, or consumed more than once, and it never activates production itself.

Promotion SHALL be progressive, independently reviewed, explicit, generation-fenced, and break-before-make. No success count, elapsed time, absence of incidents, statistical score, dashboard state, deployment health, commercial urgency, or operator judgement may automatically increase scope. Recovery never resumes an invalidated trial or re-arms a promoted scope.

---

## 2. Context

VER-002-001 defines EV-L5 as restricted production verification and currently lists broad prerequisites for a Production Restricted Live Gate. RFC-002 leaves the exact restricted-production evidence mechanism open. Existing ADRs define capacity, authority, configuration, evidence, recovery, broker constraints, command construction, aggregate risk, action flow, independent approval, and per-send currentness, but do not define how real-capital evidence may be collected without turning the evidence process into an authority-escalation path.

Without a normative promotion protocol, an implementation could:

- deploy a “small canary” whose maximum credible effect is not actually bounded;
- interpret a quiet observation window as proof that unexercised failure modes are safe;
- keep a trial running after an evidence gap or safety-bound breach to collect more data;
- reuse one account or instrument result across unrelated brokers, routes, products, or software generations;
- union several narrow successful trials into a broader production scope;
- let an automated controller increase notional, symbols, strategies, or duration after success;
- treat a promotion review or dashboard approval as Live Authorization;
- release capacity because the trial ended or the authorization expired;
- resume a partially observed trial after restart, failover, reconciliation, or time recovery;
- discard failed or inconclusive runs and promote from a selected passing subset;
- claim EV-L5 completion before exact evidence is retained and independently reviewed;
- claim EV-L6 monitoring compensates for an unproven preventive control.

This ADR closes those paths while keeping all existing authority ownership intact.

---

## 3. Decision Drivers

1. Real broker semantics may require bounded production evidence, but evidence collection must never become self-authorizing.
2. Maximum credible trial effect must be bounded before the first broker byte.
3. Trial scope, baseline, hypotheses, stop conditions, and evidence must be pre-registered.
4. Abort and demotion must dominate availability and evidence collection.
5. Success in one scope must not extrapolate to another scope or generation.
6. Promotion must be independent, explicit, single-use, and non-authorizing.
7. UNKNOWN, missing evidence, and broker ambiguity must remain capacity-consuming and restrictive.
8. Recovery and time passage must not resume or promote a trial.
9. Negative and inconclusive evidence must be retained without selection bias.
10. The design must separate acceptance of this governance mechanism from authorization of any future EV-L5 trial.

---

## 4. Scope and Non-Scope

This ADR decides:

- restricted-live policy and trial-plan contracts;
- exact trial scope and maximum credible effect;
- pre-registration and pre-trial gates;
- trial-run state and final-egress binding;
- abort, restriction, demotion, and ambiguity behavior;
- trial evidence-package validity;
- progressive scope-promotion and production-authorization handoff;
- continuous conformance and recovery rules;
- evidence and acceptance obligations.

This ADR does not select:

- a broker, venue, account, product, strategy, deployment, database, workflow, monitoring, or statistical product;
- numeric trial bounds;
- the underlying business strategy or safety-control implementation;
- a new capacity, configuration, Live Authorization, Human Authority, or transmission authority;
- permission to execute a restricted-live trial;
- permission to promote any scope to production.

---

## 5. Definitions

### 5.1 Restricted-Live Trial Policy

An ADR-002-014 governed immutable policy defining eligible trial classes, scope dimensions, preconditions, maximum effect rules, required evidence, coverage rules, abort triggers, promotion steps, independent-review rules, and failure responses.

### 5.2 Restricted-Live Trial Plan

An immutable pre-registered proposal for one exact trial scope, baseline, hypothesis set, action envelope, capacity envelope, observation horizon, evidence plan, operators, abort protocol, and recovery disposition. It grants no authority.

### 5.3 Trial Scope

The complete environment, Safety Cell, Capacity Domain, legal portfolio, account, broker, venue, instrument, strategy, action class, order shape, software, configuration, identity, credential, route, session, time interval, and failure-domain set to which trial evidence applies.

### 5.4 Trial Budget

The maximum planned action count, broker-resource use, duration, and credible economic-effect envelope for a trial. It constrains authorization requests but is not RCL capacity or broker permission.

### 5.5 Trial Run

One execution instance of one exact Trial Plan and baseline under one fresh trial-run identity and one fresh Live Authorization chain.

### 5.6 Trial Abort Trigger

A pre-registered condition requiring immediate restriction, including invariant failure, bound breach, evidence gap, scope drift, currentness loss, broker contradiction, external activity, supervision loss, or unknown economic state.

### 5.7 Restricted-Live Trial Evidence Package

An immutable, gap-checked, causally complete package containing the exact plan, baseline, approvals, authorization, actions, broker effects, capacity state, faults, aborts, deviations, negative results, coverage, and independent review for one Trial Run. It grants no authority.

### 5.8 Coverage Claim

A conservative mapping from evidence to the exact policy, control, broker semantic, action class, scope, generation, and failure condition actually exercised. Unexercised or ambiguously observed behavior is uncovered.

### 5.9 Production Scope Promotion Decision

A single-use, non-authorizing independent decision of `DENY`, `HOLD`, or `ELIGIBLE_TO_REQUEST_NEW_SCOPE` for one exact promotion delta and baseline. Eligibility still requires new configuration activation, governed re-arm, Live Authorization, and per-action enforcement.

### 5.10 Promotion Generation

A monotonic generation fencing prior Trial Plans, evidence packages, promotion decisions, and authorization requests after any scope, baseline, policy, reviewer, residual-risk, or safety-relevant change.

### 5.11 Progressive Promotion

Movement through explicitly approved scope deltas where each step is independently evidenced and authorized. Multiple narrow scopes cannot be unioned into a broader step without an approved combined-scope trial.

---

## 6. Safety Invariants

### RLP-INV-001 — Trial Artifacts Are Not Authority

Policy, plan, run state, evidence, review, and promotion artifacts create no capacity, protection, Live Authorization, capability, transmission, HALT clear, or re-arm authority.

### RLP-INV-002 — Exact Scope Only

Every trial and promotion binds one complete exact scope and baseline. Missing, wildcard, inferred, patched, unioned, stale, or conflicting scope is denial.

### RLP-INV-003 — Worst-Credible Effect Is Pre-Covered

Before risk-increasing trial action, RCL capacity covers the worst credible union of existing, planned, potentially-live, partial, external, protective, abort, and recovery effects.

### RLP-INV-004 — No Safety-Control Waiver

Restricted-live status, low notional, supervision, canary naming, or evidence collection never bypasses a normal safety check or final-egress enforcement.

### RLP-INV-005 — Abort Dominates Evidence Collection

A Trial Abort Trigger restricts future action immediately. The trial cannot continue merely to increase sample size, diagnose, hedge a metric, or complete a schedule.

### RLP-INV-006 — UNKNOWN Is Restrictive and Capacity-Consuming

Unknown trial, broker, order, claim, send, fill, exposure, evidence, coverage, or abort state blocks new risk and preserves the worst credible capacity obligation.

### RLP-INV-007 — Completion Is Not Promotion

Trial completion, elapsed time, success count, absence of incidents, or evidence-package creation never promotes scope or creates permission.

### RLP-INV-008 — Evidence Does Not Extrapolate

Evidence applies only to the exact exercised scope, generation, broker semantics, and failure conditions. Silence and unexercised coverage do not prove safety.

### RLP-INV-009 — Negative Evidence Is Durable

Failed, aborted, conflicting, incomplete, and inconclusive trials remain retained and gate later promotion. Passing subsets cannot erase them.

### RLP-INV-010 — Promotion Is Progressive and Single Use

Each scope increase is one explicit independently reviewed delta. Promotion decisions cannot be replayed, unioned, widened, partially consumed, or automatically chained.

### RLP-INV-011 — Restriction Is Faster Than Expansion

HALT, abort, demotion, profile reduction, and evidence invalidation may reduce future authority immediately; expansion requires the complete fresh governance chain.

### RLP-INV-012 — Economic Effect Outlives Trial State

Trial completion, abort, expiry, invalidation, or promotion-decision consumption cannot cancel orders, prove non-acceptance or Final Quantity, erase positions, or release capacity.

### RLP-INV-013 — Recovery Does Not Resume or Re-arm

Restart, reconnect, restore, replay, reconciliation, quorum recovery, trustworthy-time recovery, monitoring recovery, or operator return cannot resume an invalidated Trial Run, promote scope, or re-arm.

### RLP-INV-014 — Independent Acceptance

Trial implementers, strategy owners, evidence producers, and performance beneficiaries cannot be the sole reviewers or production authorizers of their trial.

### RLP-INV-015 — Continuous Monitoring Is Not Preventive Proof

EV-L6 monitoring detects drift and triggers restriction; it does not compensate for a missing pre-trade control, failed EV-L5 gate, or unapproved scope.

---

## 7. Authority Ownership and Separation

| Action | Owner | Enforcement | Explicit prohibition |
|---|---|---|---|
| Govern Trial Policy | safety-configuration governance | ADR-002-014 activation | activation does not authorize a trial |
| Propose Trial Plan | designated trial proposer | plan registry validates schema | proposer cannot self-authorize |
| Review trial eligibility | independent safety and broker reviewers | Human Authority workflow | review creates no capacity or Live Authorization |
| Mutate capacity | none | RCL only | plan, budget, evidence, and promotion cannot reserve or release |
| Issue trial Live Authorization | Live Authorization Service after ADR-002-015 approval | ADR-002-007 and final egress | trial artifacts cannot issue it |
| Transmit trial action | Execution Coordinator requests | Broker Egress Gateway only | trial label cannot bypass normal gate |
| Abort or narrow trial | authenticated safety owner, abort detector, or Human HALT | currentness fence and egress latch | restriction cannot auto-revert |
| Assemble evidence package | Evidence and Replay Service from source-owner records | ADR-002-016 integrity rules | package cannot select away failures or create permission |
| Decide promotion eligibility | independent production-authorization quorum | single-use promotion registry | decision cannot activate configuration or arm live scope |
| Activate promoted configuration | safety-configuration governance | ADR-002-014 | requires new generation and remains non-authorizing |
| Re-arm promoted scope | ADR-002-007/015 workflow | fresh Live Authorization and final egress | no automatic promotion or re-arm |

No trial planner, evidence service, promotion workflow, dashboard, monitor, or statistical evaluator may possess usable live broker authority plus an order route unless it is inside the ADR-002-013 Final Egress Trust Boundary and enforces the complete normal gate.

---

## 8. Restricted-Live Trial Policy

The policy SHALL define:

- eligible and prohibited trial classes;
- exact scope and baseline dimensions;
- maximum credible economic and broker-resource effect rules;
- required pre-trial ADR, SAFE, evidence, broker-profile, and security states;
- pre-registration and materiality rules;
- mandatory action, fault, observation, and coverage classes;
- abort, HALT, demotion, invalidation, and notification triggers;
- required operators, reviewers, and separation of duties;
- evidence durability, package completeness, and review rules;
- promotion ladder, maximum delta, and non-extrapolation rules;
- continuous-conformance and expiry rules;
- residual-risk and failure responses.

Unknown materiality is material. Unknown applicability expands the required scope or denies the trial. The proposer, strategy, operator, reviewer, or performance owner cannot self-exempt a control or evidence class.

Policy activation follows ADR-002-014 and advances Trial Policy Generation. Activation is configuration only and creates no trial eligibility, authorization, currentness proof, or production permission.

---

## 9. Exact Trial Plan Contract

Every plan SHALL bind at least:

- policy identity, generation, digest, and compatibility manifest;
- plan identity, immutable version, canonical digest, and predecessor;
- exact Trial Scope and complete baseline artifact digests;
- targeted safety claims and evidence IDs;
- pre-registered actions, order shapes, failure injections, observations, and coverage claims;
- maximum action count, duration, concurrent attempts, broker-resource vector, and credible economic-effect envelope;
- existing exposure, external-activity window, protective obligation, abort overlap, and recovery assumptions;
- RCL capacity request and protection/flow-reserve prerequisites;
- start window, expiry, trustworthy-time requirements, and consumer receipt anchors;
- required human principals, operators, independent reviewers, and observers;
- evidence sources, pre-effect durability, package schema, and retention;
- abort triggers, HALT scope, egress-latch behavior, reconciliation, and recovery disposition;
- residual risks and explicit prohibited inferences.

The plan result is `INELIGIBLE`, `HOLD`, or `ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION`. The last result is non-authorizing. A missing, stale, incomplete, changed, conflicting, unreviewed, or wrong-environment plan is `INELIGIBLE`.

Any material change creates a new plan and Promotion Generation. Plans cannot be patched after review or unioned across accounts, brokers, venues, products, strategies, action classes, software, configuration, routes, sessions, or time windows.

---

## 10. Maximum Credible Trial Effect and Capacity

The trial's maximum credible effect SHALL include:

- full and partial execution of every planned action;
- every committed or potentially-live attempt;
- duplicate, delayed, reordered, corrected, or busted broker events;
- missing acknowledgement and uncertain submission;
- cancellation and replacement crossings;
- position reversal and reduce-only failure;
- existing positions, orders, trapped exposure, and protective ownership;
- external or manual activity during the approved detection window;
- abort latency, protection gap/overlap, and recovery uncertainty;
- correlated concurrent trial and non-trial activity in shared scopes.

The plan's Trial Budget is an upper request envelope. Only RCL may commit capacity. Unused plan budget creates no headroom and cannot be transferred. Trial expiry or abort does not release any committed or possibly consumed capacity; normal proof-gated RCL transitions remain required.

If the credible effect cannot be finitely bounded inside the Hard Safety Envelope, the trial is prohibited. “Small order”, expected rejection, operator supervision, broker limit, or stop order is not a bound without the applicable proof.

---

## 11. Pre-Trial Eligibility Gate

Before a Trial Plan may become eligible to request Live Authorization:

1. RFC-001 and every applicable ADR are Accepted for the exact trial scope;
2. this ADR's governance mechanism is Accepted from non-live EV-L1–EV-L3 evidence;
3. no applicable Critical evidence is failed, inconclusive, expired, or missing;
4. the Verification Profile and Broker Capability Profile are approved and current;
5. Hard Safety Envelope, Runtime Safety Profile, Trial Policy, configuration bundle, software, identity, credential, route, session, and currentness schemas are exact and compatible;
6. the Trial Plan is complete, immutable, pre-registered, independently reviewed, and within every approved bound;
7. RCL capacity, Action Flow Permit/reserve, protective capacity, and abort/recovery overlap are positively available for the requested action envelope;
8. broker/order/exposure state is reconciled and no blocking UNKNOWN, Evidence Gap, obligation, or external activity remains;
9. abort, HALT, hard-fence, local-latch, evidence, reconciliation, and operator paths have passed current exercises;
10. required human quorum and conflict-of-interest rules are satisfied;
11. residual risk is explicitly approved only within the exact reduced scope;
12. ARCHITECTURE-GATE-STATUS records restricted-live authorization as still requiring a separate fresh Live Authorization.

Eligibility failure is denial. No waiver, urgency, deadline, low notional, or executive instruction can silently lower a Critical precondition.

---

## 12. Trial Authorization and Start

An eligible plan proceeds through the complete ADR-002-015 human approval and ADR-002-007 re-arm workflow. The resulting Live Authorization SHALL be equal to or narrower than the intersection of:

- Hard Safety Envelope;
- active Runtime Safety Profile;
- active Broker Capability Profile;
- exact Trial Policy and Plan;
- RCL and Action Flow commitments;
- approved residual-risk scope;
- current reconciled operational state.

The authorization binds one Trial Run identity, plan digest, baseline, Promotion Generation, maximum action/effect/count/duration envelope, start/expiry window, and abort generation. It cannot be reused for another run or resumed after invalidation.

Before the first trial byte, a fresh Recovery Generation, complete currentness vector, exact authorization, capacity and flow commitments, evidence durability, and final-egress path SHALL be positively established. Trial start is a governed state transition, not a deployment-health event.

---

## 13. Per-Action Trial Enforcement

Every trial action passes all ordinary proposal, approval, Intent, construction, venue, risk, capacity, flow, authority, currentness, evidence, and egress controls.

The final egress SHALL additionally verify:

- exact active Trial Policy and Plan identity, generation, digest, and compatibility;
- current Trial Run, Promotion Generation, authorization, and non-aborted state;
- exact action is pre-registered and within remaining count, duration, scope, effect, and broker-resource envelopes;
- actual outbound representation remains inside the exact approved trial action;
- evidence ingress and abort paths are current without treating monitoring health as permission;
- no Critical deviation, external activity, Evidence Gap, currentness gap, or invalidation is active.

These facts SHALL be dimensions in the ADR-002-024 Safety Currentness Vector and Egress Currentness Proof. Cached trial state, dashboard status, local counters, TTL, heartbeat, operator presence, or absence of an abort event is not active-currentness proof.

---

## 14. Trial Run State and Serialization

Trial Run state is one of:

```text
NOT_STARTED
AUTHORIZED_NOT_STARTED
RUNNING
ABORTING
TERMINATED
COMPLETED_PENDING_REVIEW
INVALIDATED
```

Only the governed trial state machine may transition the run. `RUNNING` requires current Live Authorization and does not itself grant transmission permission.

Action-count, maximum-effect, duration, abort-generation, and terminal transitions SHALL be ordered against the same authoritative trial scope used by final egress. Concurrent action admission cannot overspend the plan envelope. Process-local counters and eventually consistent dashboards are not serialization authority.

`ABORTING`, `TERMINATED`, `COMPLETED_PENDING_REVIEW`, and `INVALIDATED` are non-permissive. No terminal state returns to `RUNNING`; a later trial requires a new plan/run identity, current baseline, approvals, capacity, and Live Authorization.

---

## 15. Abort, HALT, and Demotion

Abort triggers include at least:

- any invariant or Hard Safety Envelope violation;
- actual or potential trial-scope, count, duration, effect, or broker-resource breach;
- UNKNOWN broker/order/exposure, missing ACK ambiguity, or cancel acknowledgement without Final Quantity Proof;
- Evidence Gap, evidence durability loss, baseline mismatch, or unexplained event;
- Critical Input, trustworthy-time, venue, construction, risk, flow, approval, currentness, configuration, identity, credential, route, session, or broker-profile invalidation;
- external/manual activity or attribution conflict;
- failed, delayed, ambiguous, or bypassable abort/HALT/fence path;
- required operator, reviewer, supervision, or failure-domain loss;
- recovery, restart, failover, restore, or common-mode condition outside the plan.

On trigger:

1. local egress restriction is latched `DENY_LATCHED`;
2. a restrictive currentness fence and trial abort generation are committed;
3. new trial and dependent risk-increasing actions are denied;
4. existing economic effects remain capacity-covered;
5. only newly authorized HALT-compatible containment may proceed;
6. evidence gaps and ambiguity are preserved;
7. the run becomes `ABORTING` or `INVALIDATED` and cannot resume.

Abort does not blindly cancel necessary protection. Abort acknowledgement is not Final Quantity Proof. A lost abort response is treated as possibly applied and does not authorize further actions.

---

## 16. Evidence Collection and Package Integrity

The Trial Evidence Package SHALL preserve:

- exact pre-registered plan, policy, scope, hypotheses, baseline, approvals, and authorizations;
- every proposed, denied, committed, transmitted, acknowledged, filled, cancelled, corrected, external, protective, abort, and recovery event;
- RCL and action-flow transitions, potentially-live intervals, and final quantity evidence;
- every fault, boundary condition, coverage claim, unexercised condition, deviation, and common mode;
- raw and normalized broker evidence with source continuity and gaps;
- measured detection, containment, abort, fence, evidence, reconciliation, and recovery bounds;
- negative, failed, inconclusive, aborted, superseded, and conflicting results;
- exact software, configuration, broker profile, identities, generations, and reviewer decisions;
- independent reproduction and review results.

The trial plan fixes evidence-selection and stop rules before start. Post-hoc metric changes, optional stopping, discarded runs, selected time windows, selected accounts, or removal of adverse results invalidate the promotion claim.

An Evidence Commit Receipt proves custody only. A complete package proves what occurred under the exact scope; it does not prove that untested behavior is safe or that preventive controls exist.

---

## 17. Coverage and Non-Extrapolation

Every promotion claim SHALL map evidence to:

- exact requirement and invariant;
- exact component and safety-control generation;
- exact broker/account/venue/instrument/action/order semantics;
- exact software/configuration/profile/currentness generation;
- nominal, boundary, missing, stale, duplicate, delayed, crash, restart, partition, broker-rejection, partial-fill, UNKNOWN, and conflict conditions actually exercised;
- observed sample and time horizon;
- unexercised conditions and residual risk.

No inference may broaden evidence across a different broker, account type, venue, instrument class, strategy, order type, credential, route, session, software, configuration, failure domain, market regime, or concurrency envelope unless the active policy supplies approved equivalence evidence. Unknown equivalence is non-equivalence.

Multiple narrow passing packages cannot be unioned into a broad coverage claim. An aggregate scope requires its own combined-scope concurrency and common-mode evidence.

---

## 18. Production Scope Promotion

A promotion review SHALL evaluate the complete current package and all prior related negative evidence. The decision binds:

- exact source Trial Run and package;
- exact baseline and Promotion Generation;
- exact current scope and requested next-scope delta;
- evidence coverage and uncovered conditions;
- approved residual risks and maximum effect;
- configuration/profile changes required for the next scope;
- required additional evidence and expiry;
- independent reviewer and effective-principal quorum;
- single-use consumption identity.

Only `ELIGIBLE_TO_REQUEST_NEW_SCOPE` may be consumed, once, to request a new Safety Configuration activation and ADR-002-007/015 re-arm. It is not approval of an order or production permission.

Promotion cannot skip a policy-defined step, exceed the approved delta, combine decisions, reuse old evidence after material change, or remain valid after negative evidence, drift, compromise, incident, profile expiry, or a newer Promotion Generation.

The new scope starts non-live. Break-before-make configuration activation, predecessor fencing, reconciliation, currentness, and a fresh Live Authorization are mandatory. No controller may automatically promote based on counters, metrics, elapsed time, P&L, or incident absence.

---

## 19. Production Authorization and Continuous Conformance

Production authorization is a separate explicit human-governed decision after the promotion eligibility, configuration activation, and re-arm prerequisites pass. It binds the exact production scope and creates no authority beyond the resulting Live Authorization.

EV-L6 monitoring SHALL continuously detect:

- scope, software, configuration, profile, broker, route, identity, session, and generation drift;
- invariant, bound, evidence, reconciliation, external-activity, and currentness failures;
- unexercised or changed broker semantics;
- capacity, action-flow, protection, abort, and recovery degradation;
- common-mode or independence assumption failure.

Drift invalidates affected evidence and restricts future authority. Monitoring recovery does not restore validity or re-arm. A production incident may require demotion to a previously proven narrower scope, but that narrower scope still requires current configuration, reconciliation, authority, and hard fencing; historical promotion is not a reusable authorization.

---

## 20. Expiry, Invalidation, and Economic Continuity

Trial Plan, Trial Run, evidence package, promotion decision, profile, and authorization expiry affects future use only. It SHALL NOT:

- cancel or prove cancellation of an order;
- prove a missing acknowledgement was non-acceptance;
- treat cancel acknowledgement as Final Quantity Proof;
- erase a fill, position, external activity, trapped exposure, or obligation;
- release or reduce RCL capacity;
- authorize retry, alternate routing, promotion, resume, or re-arm.

Material correction or invalidation advances Promotion Generation, invalidates dependent future eligibility, and expands containment to every possibly affected scope. Existing economic effects remain conservatively covered.

---

## 21. Restart, Failover, and Recovery

Restart, failover, reconnect, restore, evidence repair, reconciliation completion, time recovery, broker recovery, or operator return SHALL NOT resume a prior Trial Run.

After any such event:

- the prior run is `INVALIDATED` unless the approved plan positively proves an interruption class with no ambiguity and still forbids automatic action resumption;
- queued or delayed actions are rejected;
- old authorizations, capabilities, proofs, counters, and promotion decisions are fenced;
- broker/order/exposure and evidence state are reconciled conservatively;
- a new plan/run identity and fresh governance chain are required for later action.

Recovery evidence may support a later review but never creates promotion eligibility or live authority.

---

## 22. Security and Common-Mode Requirements

The design SHALL resist:

- proposer, implementer, operator, reviewer, evidence owner, and production authorizer collapsing to one effective principal;
- trial-plan, scope, baseline, counter, evidence, package, coverage, or promotion substitution;
- dashboard, workflow, CI/CD, registry, or monitoring compromise causing automatic expansion;
- deleted or hidden negative runs and post-hoc metric selection;
- reused promotion decisions, stale generations, partial consumption, and scope union;
- live credential or route exposure to test, replay, analytics, or evidence identities;
- abort suppression, local-latch bypass, alternate broker route, and delayed queue/session flush;
- common broker account, credential, route, infrastructure, data, or administrator being falsely treated as independent evidence;
- old deployment or credential continuing after demotion or promotion.

Trial and production identities, evidence paths, abort paths, final egress, reviewers, and administrators require an approved Failure-Domain Allocation Matrix. Unknown effective control or common mode denies promotion.

---

## 23. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Incomplete or changed Trial Plan | `INELIGIBLE`; new plan generation required |
| Capacity or maximum effect unproven | deny risk-increasing trial |
| Trial count/duration/effect serialization unavailable | deny action; latch restriction if ambiguity exists |
| Evidence ingress or package gap | abort; preserve gap; no promotion |
| Broker/order/exposure UNKNOWN | block new risk; retain conservative capacity |
| External/manual activity | abort or contain complete affected account scope |
| Abort response lost | treat abort as possibly applied; no further trial action |
| Trial action may have been sent | potentially live; no blind retry; retain capacity |
| Run restarts or fails over | invalidate run; reject queued work |
| Negative or inconclusive result | retain and block dependent promotion |
| Scope-equivalence unknown | no extrapolation |
| Multiple narrow packages proposed for union | reject; require combined-scope trial |
| Promotion decision replay or widening | reject and investigate |
| Profile/configuration/software/broker drift | invalidate evidence and restrict scope |
| Production monitor unavailable | deny new dependent risk; monitoring recovery does not re-arm |

---

## 24. Rejected Alternatives

### 24.1 Low Notional Is Safe Enough

Quantity is only one risk dimension. Unit, leverage, duplication, overlap, margin, external activity, and reversal can make a nominally small trial unsafe.

### 24.2 No Incident Means PASS

Absence of observed failure does not prove an unexercised preventive property or broker semantic.

### 24.3 Automatically Increase Limits After Success

Automation turns evidence into authority and bypasses independent approval, configuration activation, capacity, and re-arm.

### 24.4 Continue After a Breach to Collect Evidence

Evidence collection is subordinate to containment. Breach-triggered restriction dominates the schedule and sample target.

### 24.5 Union Several Narrow Trials

Combined scope introduces concurrency and common modes not established by isolated trials.

### 24.6 Operator Supervision Replaces Controls

Human observation does not guarantee detection, containment, broker finality, capacity, or egress enforcement.

### 24.7 Monitoring Compensates for Missing Prevention

EV-L6 is detective. It cannot legalize an unverified pre-trade or final-egress path.

### 24.8 Resume After Recovery

Recovery changes continuity and may hide broker or evidence ambiguity. A fresh run and authorization are required.

### 24.9 Trial Expiry Releases Capacity

Artifact expiry limits future use only; economic effects require normal lifecycle proof.

### 24.10 Promotion Review Is Production Authorization

Eligibility, configuration activation, re-arm, Live Authorization, and final-egress enforcement remain separate.

---

## 25. Consequences

### 25.1 Positive

- EV-L5 gains an exact non-self-authorizing protocol;
- real-capital evidence is bounded before execution;
- trial success cannot silently widen production scope;
- abort and demotion remain faster than promotion;
- evidence coverage and negative results become explicit;
- promotion remains separate from configuration, capacity, and live authority;
- recovery cannot revive trials or promotion decisions.

### 25.2 Negative

- restricted-live trials require substantial pre-registration and independent review;
- many broker or strategy scopes will require separate trials;
- combined-scope promotion needs concurrency and common-mode evidence;
- evidence gaps or minor drift may invalidate a costly run;
- availability and rollout speed are intentionally reduced;
- EV-L6 monitoring and demotion paths require continuous governance.

These costs are accepted because a production canary that can silently expand authority is not a safety mechanism.

---

## 26. Acceptance Cases

The following cases are mandatory and map one-to-one to `RLP-EV-001` through `RLP-EV-012`. Written cases are not completed evidence.

### RLP-AC-001 — Exact Pre-Registered Scope

Omitted, wildcard, patched, unioned, stale, conflicting, wrong-environment, or post-review plan scope cannot become eligible or authorize action.

### RLP-AC-002 — Worst-Credible Effect and RCL Separation

Full/partial/duplicate/unknown/external/abort/recovery effects remain within RCL-committed capacity; Trial Budget never mutates capacity or creates headroom.

### RLP-AC-003 — No Trial Safety Bypass

Low notional, canary label, expected rejection, supervision, priority, or evidence collection cannot bypass any normal safety or final-egress control.

### RLP-AC-004 — Abort Dominance and Race

Every invariant, bound, evidence, external-activity, currentness, and scope trigger restricts before later action; ambiguous action remains potentially live and capacity-covered.

### RLP-AC-005 — Evidence Completeness and Negative-Result Retention

Missing, selected, altered, post-hoc, failed, aborted, conflicting, or inconclusive evidence cannot produce a promotion-eligible package.

### RLP-AC-006 — Coverage and Non-Extrapolation

Evidence cannot be generalized across unexercised broker, account, venue, product, strategy, action, order, version, route, session, failure-domain, or concurrency scope.

### RLP-AC-007 — Progressive Single-Use Promotion

Promotion cannot skip steps, union packages, widen deltas, replay decisions, auto-chain, or activate configuration/authority by itself.

### RLP-AC-008 — Independent Governance and Authority Separation

One effective principal or compromised workflow cannot propose, implement, produce evidence, review, promote, activate, arm, and transmit; trial components cannot assume RCL or egress authority.

### RLP-AC-009 — Expiry and Economic Continuity

Trial/plan/evidence/promotion/authorization expiry cannot release capacity, erase economic effect, prove non-acceptance or Final Quantity, or authorize retry.

### RLP-AC-010 — Restart, Recovery, and Non-Revival

Restart, failover, reconnect, restore, replay, reconciliation, time/broker/monitoring recovery, or operator return cannot resume a run, reuse promotion, or auto-re-arm.

### RLP-AC-011 — Continuous Conformance and Demotion

Production drift or monitor loss restricts affected future authority; recovery cannot restore scope without fresh evidence and governance.

### RLP-AC-012 — Gate Honesty and Status Separation

EV-L0 review, ADR acceptance, plan eligibility, EV-L5 completion, promotion eligibility, configuration activation, Live Authorization, restricted-live readiness, and production readiness remain distinct explicit states.

---

## 27. Requirements Traceability

| Requirement | ADR-002-025 allocation |
|---|---|
| SAFE-004, SAFE-012 | Trial maximum credible effect remains inside the Hard Safety Envelope (§10) |
| SAFE-010, SAFE-011 | Every trial action passes the complete non-bypassable normal gate (§13) |
| SAFE-013 through SAFE-015 | Aggregate/action-flow evaluation and RCL-only capacity commitment govern trial effects (§§7, 10–13) |
| SAFE-021, SAFE-024, SAFE-025 | Attempt ambiguity, external state, partial fills, and broker finality remain conservative (§§10, 15, 20) |
| SAFE-035 | Trial timing, duration, age, and recovery use trustworthy time (§§9, 12, 21) |
| SAFE-041 | Trial abort and promotion cannot bypass independent Safety Authority (§§7, 15, 18) |
| SAFE-044 | Startup and recovery never resume a Trial Run (§21) |
| SAFE-045 | Trial, evidence, replay, and non-live identities remain segregated from live egress (§22) |
| SAFE-046, SAFE-047 | Fresh explicit Live Authorization binds the exact trial or promoted scope (§§12, 18–19) |
| SAFE-048 | Current authority and currentness remain required for every trial send (§13) |
| SAFE-050 | Trial Policy, plan schemas, promotion rules, and activation are governed configuration (§8) |
| SAFE-051, SAFE-052 | Complete evidence and replay support review without becoming permission (§16) |

---

## 28. Open Implementation Questions

The architecture is selected. These mechanism and parameter choices remain open while Proposed:

1. Which canonical Trial Policy, Trial Plan, Trial Evidence Package, and Production Scope Promotion Decision schemas are approved?
2. Which registry and ordering domain fence plan, run, abort, action-count, effect-envelope, and Promotion Generations?
3. Which deterministic method computes the worst credible trial effect and correlated shared-scope overlap?
4. Which workflow establishes independent effective-principal review without merging configuration, authority, capacity, and promotion roles?
5. Which final-egress mechanism actively verifies current plan/run/remaining-envelope state without permissive caches?
6. Which abort ingress, local-latch, HALT, route-fence, and evidence path remains available under declared failures?
7. Which evidence coverage model prevents extrapolation, optional stopping, selected runs, and hidden negative results?
8. Which promotion ladder and maximum scope-delta rules apply by broker, account, product, strategy, and action class?
9. Which production-monitoring and evidence-invalidation mechanism implements EV-L6 and bounded demotion?
10. Which dedicated or shared accounts, credentials, routes, sessions, and failure domains are allowed for trials?
11. Which recovery protocol invalidates queued work and proves old trial/promotion authority is hard-fenced?
12. What `B_trial_abort_to_authority_revoke`, `B_trial_abort_to_egress_deny`, `B_trial_evidence_gap_to_containment`, `B_scope_promotion_generation_fence`, `MAX_trial_authorized_economic_effect`, `MAX_trial_concurrent_potential_effect`, `MAX_trial_action_count`, `MAX_trial_duration_ms`, and `MAX_trial_evidence_age_ms` values are approved?

Unresolved questions reduce authority, prohibit the affected trial, or keep production scope unchanged. They never justify a permissive default.

---

## 29. Approval and Operational Gates

ADR-002-025 SHALL remain **Proposed** until all of the following are complete:

1. Trial Policy, Plan, Evidence Package, and Promotion Decision schemas and canonicalization are approved.
2. Plan/run/action/abort/promotion ordering and stale-generation fencing are implemented and fault-injected in non-live environments.
3. Worst-credible trial effect and RCL/action-flow binding are deterministic, conservative, and independently reviewed.
4. Per-action final-egress binding enforces exact plan, remaining envelope, authorization, and currentness without cache-based permission.
5. Abort/HALT/demotion paths are independent, monotonic, bounded, and non-bypassable.
6. Evidence capture retains complete negative and inconclusive histories and prevents selection, mutation, or extrapolation.
7. Promotion is progressive, single-use, exact-delta, independently governed, and non-authorizing.
8. Restart, failover, restore, recovery, queue drain, and monitoring recovery cannot resume, promote, or re-arm.
9. Trial, evidence, replay, and promotion identities cannot reach or create unauthorized broker effect.
10. `RLP-EV-001` through `RLP-EV-012` pass at required non-live EV-L1/EV-L3 levels and receive independent review.
11. All applicable security, failure-domain, currentness, capacity, authority, evidence, abort, and generation-fence reviews pass.
12. Numeric bounds needed to accept the governance mechanism are approved and measured under non-live fault injection.
13. No Critical or Major finding remains unresolved, and canonical RFC/ADR/VER/Evidence Register traceability is complete.
14. ARCHITECTURE-GATE-STATUS records an explicit ADR acceptance decision.

EV-L5 is not required to accept the non-self-authorizing governance mechanism; requiring a live trial before the trial gate exists would be circular. However, no specific restricted-live trial may start until this ADR and every applicable upstream ADR are Accepted, the §11 pre-trial gate passes, numeric scope is approved, and fresh ADR-002-007/015 Live Authorization is issued.

No production scope may be promoted until the exact EV-L5 Trial Evidence Package passes independent review, the §18 promotion decision is eligible and consumed once, configuration is activated break-before-make, predecessor paths are fenced, and a fresh re-arm/Live Authorization is completed. EV-L6 continuous conformance is additionally required for continued production scope.

Authorship, EV-L0 review, a passing simulation, plan approval, low notional, deployment, operator presence, trial completion, evidence-package creation, promotion eligibility, configuration activation, dashboard state, or incident-free time does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live operation, production operation, broker transmission, scope promotion, or automatic re-arm.
