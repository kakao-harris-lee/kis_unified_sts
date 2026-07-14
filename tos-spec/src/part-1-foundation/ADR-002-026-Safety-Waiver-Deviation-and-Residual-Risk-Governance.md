# ADR-002-026 — Safety Waiver, Deviation, and Residual-Risk Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Safety waivers, deviations, exceptions, residual-risk acceptance, non-waivable boundaries, compensating controls, exact scope, independent approval, configuration activation, currentness, expiry, revocation, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 §14 and SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-021, SAFE-023, SAFE-024, SAFE-025, SAFE-034, SAFE-035, SAFE-041, SAFE-042, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§2, 9.1, 10, 20, 23, and 28–29; VER-002-001 §§5, 314–325, and 354–357
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-025

---

## 1. Decision

Safety waivers, deviations, exceptions, and residual-risk acceptances SHALL be governed as explicit, immutable, exact-scope, time-bounded, independently approved, non-authorizing safety artifacts. They are not configuration shortcuts, emergency broker permissions, evidence substitutes, or mechanisms for redefining a failed requirement as satisfied.

One active ADR-002-014 governed **Safety Deviation Policy** SHALL classify every proposed deviation, define the non-waivable boundary, require exact dependency closure, specify mandatory compensating controls and evidence, and identify the independent approval quorum. Missing, stale, ambiguous, conflicting, unsupported, or incompletely classified deviation state is denial for new risk.

A **Safety Deviation Request** SHALL identify the exact requirement, hazard, cause, scope, duration, missing or degraded control, residual risk, compensating controls, evidence status, recovery behavior, and requested restricted operating envelope. A request, review, approval, ticket, dashboard state, executive instruction, or deadline creates no capacity, Safety Authority, Live Authorization, Transmission Capability, broker permission, protective classification, HALT clear, production scope, or re-arm authority.

No deviation is permitted from RFC-000, from RFC-001's explicit no-waiver set, or from the architecture invariants that keep uncertainty and irreversible economic effect conservative. In particular, no deviation may weaken Risk Capacity Ledger exclusivity, final-egress enforcement, stale-generation fencing, live/non-live segregation, independent HALT, UNKNOWN-state conservatism, broker-finality rules, economic-effect continuity, or the prohibition on automatic re-arm.

An eligible **Safety Deviation Decision** may state only `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` for one exact reduced scope. It does not activate configuration or satisfy the affected requirement. The affected verification item remains visibly incomplete or `WAIVED_WITH_RESIDUAL_RISK`; it never becomes `PASS` because of the decision.

Any allowed deviation SHALL be activated only through a new immutable Safety Configuration Bundle and Profile Generation under ADR-002-014. The exact active deviation-set digest and **Deviation Generation** SHALL be bound into currentness and checked before dependent new-risk authority or final-egress admission. Break-before-make activation, fresh governed re-arm, RCL capacity, independent approval, and every unaffected safety control remain mandatory.

Deviation expiry, revocation, evidence loss, compensating-control loss, scope drift, or a newer generation SHALL restrict future authority monotonically. Expiry never cancels a broker order, proves non-acceptance, proves Final Quantity, erases exposure, releases capacity, clears UNKNOWN, restores a predecessor profile, or automatically re-arms.

Documentation, monitoring, audit, replay, operator vigilance, low notional, commercial importance, incident absence, or priority SHALL NOT substitute for an enforceable preventive or containment control. If the residual risk cannot be bounded conservatively inside the Hard Safety Envelope, the request is denied.

---

## 2. Context

RFC-001 §14 permits explicitly governed waivers or deviations for some requirements while forbidding them for fundamental safety properties. Existing ADRs repeatedly require residual-risk approval when true independence, broker evidence, protective resources, or other safety mechanisms are limited. They do not yet define one architecture-wide protocol that prevents those local references from becoming an informal bypass system.

Without a normative contract, an implementation could:

- mark a failed Critical case as `PASS` after management approval;
- use one narrow exception across unrelated accounts, brokers, strategies, products, or software generations;
- stack several individually narrow deviations into a broader unreviewed risk;
- treat a waiver ticket as configuration activation, live authorization, or final-egress permission;
- approve the same person's request through multiple accounts or delegated identities;
- claim logging, alerts, dashboards, or operator supervision as compensating prevention;
- use reserved capacity to make UNKNOWN broker or exposure state permissible;
- let an exception expire and infer that its economic effect or capacity obligation expired;
- restore a predecessor profile automatically after exception expiry;
- use break-glass or an external broker portal to bypass the normal authority chain;
- retain a stale exception in cache after revocation or policy change;
- reinterpret missing ACK as non-acceptance or Cancel ACK as Final Quantity Proof;
- waive the safety controls that govern the waiver process itself;
- approve a residual risk whose worst credible effect is unbounded;
- treat absence of an incident as evidence that the deviation is safe.

This ADR closes those paths while preserving RFC-001's explicit, narrow residual-risk governance mechanism.

---

## 3. Decision Drivers

1. A safety exception must never become an untracked alternate authority path.
2. Non-waivable constitutional and architecture invariants must be explicit and machine-enforceable.
3. The affected requirement must remain honestly incomplete; approval is not verification.
4. Scope, time, dependency closure, residual risk, and compensating controls must be exact.
5. Multiple deviations and common modes must be evaluated as one combined risk set.
6. Compensating controls must be preventive or containment-capable, not merely observational.
7. Effective-person independence and single-use consumption must prevent self-approval and replay.
8. Revocation and expiry must reach authority and final egress without permissive caching.
9. UNKNOWN and existing economic effects must remain conservative and capacity-covered.
10. Recovery, rollback, and time passage must not revive deviation-dependent authority.

---

## 4. Scope and Non-Scope

This ADR decides:

- the Safety Deviation Policy and non-waivable boundary;
- exact request, decision, residual-risk, and active-set contracts;
- deviation classification, dependency closure, and combined-risk evaluation;
- compensating-control eligibility and evidence;
- effective-person independence and approval consumption;
- configuration activation and currentness binding;
- expiry, revocation, containment, recovery, and non-revival;
- evidence status and acceptance obligations.

This ADR does not select:

- an organization, workflow product, registry, database, signer, or ticketing system;
- numeric deviation durations, review ages, or revocation bounds;
- a specific deviation or residual risk to approve;
- a new capacity, Safety Authority, configuration, live-arming, or transmission authority;
- permission to weaken RFC-000 or RFC-001;
- permission to operate restricted-live or production scope.

---

## 5. Definitions

### 5.1 Safety Deviation Policy

An immutable ADR-002-014 governed policy defining eligible deviation classes, the non-waivable boundary, scope and dependency rules, compensating-control requirements, approval independence, duration, currentness, invalidation, evidence, and failure behavior.

### 5.2 Safety Deviation Request

An immutable proposal to accept one identified unmet or degraded requirement for one exact reduced scope and duration under specified compensating controls. It grants no authority.

### 5.3 Safety Deviation Decision

An immutable independent result of `DENY`, `HOLD`, or `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` for one exact request digest. Eligibility permits only a single request to the separate safety-configuration workflow.

### 5.4 Residual-Risk Acceptance Record

An immutable record of the bounded risk, assumptions, compensating controls, reviewers, expiry, evidence status, and explicit scope accepted by the authorized quorum. It is not proof that the underlying requirement passed and grants no authority.

### 5.5 Compensating Control

An independently governed, enforceable preventive or containment mechanism that reduces the exact added risk of an allowed deviation. A document, alert, dashboard, audit, replay, priority label, or operator promise is not by itself a compensating control.

### 5.6 Non-Waivable Boundary

The union of RFC-000, RFC-001's explicit no-waiver set, this ADR's §8 prohibitions, and any stricter active Safety Deviation Policy rule. Policy may add prohibitions but cannot remove them.

### 5.7 Deviation Scope

The complete environment, Safety Cell, Capacity Domain, legal portfolio, account, broker, venue, instrument, strategy, action class, software, configuration, identity, route, session, failure-domain, time, evidence, requirement, hazard, and dependency closure to which one decision applies.

### 5.8 Deviation Generation

A monotonic generation fencing previous policies, active sets, decisions, acceptance records, configuration requests, authority requests, and consumers after any material deviation, scope, control, evidence, reviewer, policy, or recovery change.

### 5.9 Active Deviation Set

One immutable canonical set of every deviation and residual risk applicable to an exact Safety Configuration Bundle. It is evaluated as a combined risk set and cannot be assembled by permissive union at a consumer.

### 5.10 Deviation Dependency Closure

Every component, artifact, account, shared limit, authority, capacity, credential, route, failure domain, economic effect, verification claim, and downstream consumer that may be affected by the missing control or its compensating controls.

---

## 6. Safety Invariants

### WDR-INV-001 — Deviation Artifacts Are Not Authority

Policy, request, decision, acceptance, review, ticket, evidence, and active-set artifacts create no capacity, protection, Safety Authority, Live Authorization, capability, transmission, HALT clear, production scope, or re-arm authority.

### WDR-INV-002 — Non-Waivable Means Prohibited

No principal, quorum, emergency process, configuration, or residual-risk decision may approve a deviation inside the Non-Waivable Boundary.

### WDR-INV-003 — Exact Reduced Scope Only

Every decision binds one complete exact reduced scope and dependency closure. Missing, wildcard, inferred, patched, widened, stale, conflicting, or wrong-environment scope is denial.

### WDR-INV-004 — Approval Does Not Equal Verification

An accepted residual risk does not convert an unmet, failed, missing, inconclusive, or expired verification item to `PASS` and does not establish implementation completion.

### WDR-INV-005 — Enforceable Compensation

Every permitted deviation has independently verified preventive or containment compensation for the exact added risk. Observation alone is insufficient.

### WDR-INV-006 — Combined Risk, No Permissive Union

Multiple deviations, compensating controls, and common modes are evaluated as one Active Deviation Set. Separate approvals cannot be unioned to create broader permission.

### WDR-INV-007 — Independent Effective-Person Approval

The requester, control owner, performance beneficiary, implementer, evidence producer, and live armer cannot collectively satisfy approval through one Effective Principal or shared administrative control.

### WDR-INV-008 — Configuration and Re-arm Remain Separate

An eligible decision may be consumed once only to request exact restricted configuration. Activation, reconciliation, fresh governed re-arm, capacity, and final-egress admission remain separate.

### WDR-INV-009 — Revocation Dominates Permission

Expiry, revocation, control failure, evidence loss, policy change, conflict, or newer generation restricts future authority before later dependent new-risk send. Ambiguity is denial.

### WDR-INV-010 — UNKNOWN Never Becomes Permission

Unknown applicability, broker state, order state, exposure, residual risk, compensating-control state, evidence, scope, or currentness blocks new risk and consumes worst-credible capacity where economic effect may exist.

### WDR-INV-011 — Broker Finality Is Unchanged

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. A deviation cannot change those meanings or authorize blind retry or release.

### WDR-INV-012 — Economic Effect Outlives Deviation State

Request withdrawal, decision expiry, revocation, active-set change, profile rollback, or authorization expiry cannot erase positions, orders, attempts, fills, external activity, obligations, or capacity.

### WDR-INV-013 — RCL and Egress Exclusivity

Only RCL mutates and serializes capacity. Only the Broker Adapter / Egress Gateway is the final transmission enforcement point. Deviation services hold neither authority.

### WDR-INV-014 — Recovery Does Not Revive

Restart, reconnect, failover, restore, rollback, replay, reconciliation, trustworthy-time recovery, workflow recovery, reviewer return, or control recovery cannot revive a decision, profile, authority, or active set and cannot auto re-arm.

### WDR-INV-015 — Restriction Does Not Self-Revert

Deviation expiry or revocation causes a restrictive transition. It never automatically restores a predecessor configuration or broader scope; a fresh full governance chain is required.

---

## 7. Authority Ownership and Separation

| Action | Owner | Enforcement | Explicit prohibition |
|---|---|---|---|
| Govern Safety Deviation Policy | safety-configuration governance | ADR-002-014 activation | policy activation creates no deviation or live permission |
| Propose deviation | designated requester | immutable request registry | requester cannot self-classify or self-approve |
| Classify non-waivable eligibility | independent policy evaluator | exact policy and requirement registry | evaluator cannot create an exception to the boundary |
| Evaluate residual risk | independent safety/risk reviewers | deterministic scope and risk contract | result creates no capacity or authority |
| Approve exact residual risk | ADR-002-015 effective-principal quorum | single-use decision registry | approval cannot activate configuration or arm live scope |
| Mutate capacity | none | RCL only | deviation budget or accepted risk is never capacity |
| Activate exact restricted configuration | safety-configuration governance | ADR-002-014 break-before-make | activation remains non-authorizing |
| Issue Live Authorization | Live Authorization Service | ADR-002-007/015 | deviation artifacts cannot issue or clear it |
| Transmit | Broker Adapter / Egress Gateway | complete normal final gate | no exception route or bypass method |
| Revoke or narrow | Safety Authority, policy owner, control owner, or Human HALT | currentness fence and local latch | restriction does not require permissive quorum |
| Record evidence | source owners and Evidence Store | ADR-002-016 | evidence cannot authorize or relabel a failure as PASS |

The deviation registry, evaluator, workflow, dashboard, ticketing system, and residual-risk service SHALL NOT possess a usable live-order credential, signer, session, or route. Any component that does possess usable live-order authority plus a route is inside the ADR-002-013 Final Egress Trust Boundary and must enforce the full gate.

---

## 8. Non-Waivable Boundary

At minimum, no deviation may waive, reinterpret, or bypass:

1. any RFC-000 constitutional requirement;
2. RFC-001's explicit no-waiver set: independent halt authority, live/non-live segregation, a valid Safety Profile, reconciled authoritative position state, bounded single-action risk, bounded aggregate risk, and prevention of known duplicate-exposure paths;
3. fail-closed treatment of missing, stale, conflicting, unverifiable, or UNKNOWN safety state;
4. Risk Capacity Ledger exclusivity for capacity mutation and serialization;
5. Broker Adapter / Egress Gateway final enforcement and broker-route confinement;
6. stale writer, authority, profile, recovery, currentness, deviation, and egress generation fencing;
7. missing ACK and Cancel ACK broker-finality semantics;
8. economic-effect and capacity continuity after artifact or authority expiry;
9. exact current Hard Safety Envelope and Runtime Safety Profile enforcement;
10. independent Human HALT and restrictive break-glass behavior;
11. live/non-live identity, credential, route, and environment segregation;
12. the rule that priority is not reserved protective capacity;
13. the rule that documentation, monitoring, audit, replay, and incident reconstruction do not substitute for prevention;
14. the prohibition on automatic re-arm or recovery-based authority revival;
15. this ADR's policy, independence, currentness, evidence-honesty, and non-authority rules.

The Safety Deviation Policy may declare additional requirements non-waivable for a product, broker, account, strategy, or failure domain. It cannot make this list smaller.

If requirement identity or applicability is unresolved, it is treated as non-waivable until positively classified otherwise by the current policy and independent review.

---

## 9. Safety Deviation Policy

The policy SHALL define:

- requirement and hazard registries with non-waivable classification;
- eligible and prohibited deviation classes;
- exact scope, dependency-closure, materiality, and combined-risk rules;
- required residual-risk model and worst-credible-effect analysis;
- eligible compensating-control classes and minimum independence;
- required evidence levels, freshness, confidence, and common-mode analysis;
- effective-principal quorum, conflicts, mandatory roles, and consumption rules;
- maximum duration, decision age, review interval, and renewal prohibition;
- configuration, currentness, invalidation, expiry, revocation, and recovery rules;
- evidence-register status and retained-history rules;
- restricted-live, production, and promotion constraints;
- mandatory denial and containment behavior.

Unknown materiality is material. Unknown applicability expands dependency closure or denies the request. A requester, component owner, strategy, operator, reviewer, or commercial owner cannot self-exempt a requirement or affected dependency.

Policy activation follows ADR-002-014, advances the Deviation Generation, and invalidates incompatible pending requests and decisions. Activation is configuration only and creates no eligibility, capacity, authority, currentness proof, or live permission.

---

## 10. Exact Safety Deviation Request

Every request SHALL bind at least:

- policy identity, generation, digest, and compatibility manifest;
- request identity, immutable version, canonical digest, and predecessor;
- exact requirement IDs, hazard IDs, ADR/RFC citations, and verification IDs;
- current requirement and evidence status without relabeling;
- exact Deviation Scope and dependency closure;
- technical cause, why the normal control is unavailable, and remediation plan;
- requested start, hard expiry, review interval, and trustworthy-time basis;
- worst credible added economic, broker, operational, security, and common-mode risk;
- every assumption, uncertainty, unsupported semantic, and failure mode;
- proposed compensating controls, their owners, evidence, independence, and currentness;
- Hard Safety Envelope and requested reduced Runtime Safety Profile;
- capacity, protective, action-flow, supervision, evidence, and recovery constraints;
- revocation, HALT, egress-deny, rollback, reconciliation, and trapped-exposure behavior;
- requester, implementer, beneficiaries, evidence owners, reviewers, and conflict graph;
- explicit prohibited inferences and non-waivable classification result.

A request with missing, wildcard, inferred, stale, conflicting, unbounded, wrong-environment, or post-review fields is ineligible. Request fields cannot be patched after approval; any material change creates a new request and Deviation Generation.

Availability pressure, P&L, deadline, market opportunity, low expected use, prior success, monitoring coverage, or implementation difficulty is not a safety justification.

---

## 11. Residual Risk and Compensating Controls

Residual risk SHALL be evaluated against the worst credible combined effect, not the expected outcome. The evaluation SHALL include:

- the missing or degraded control's full failure envelope;
- existing, potentially-live, UNKNOWN, external, protective, and trapped exposure;
- partial fill, duplicate, late, corrected, busted, and unattributed broker events;
- missing acknowledgement, cancellation uncertainty, replacement overlap, and reversal;
- common-mode failure between the missing control and every compensation;
- shared accounts, credentials, routes, limits, data, clocks, administrators, deployments, and vendors;
- interaction with every other active or pending deviation;
- expiration, revocation, partition, restore, rollback, and recovery races;
- loss or degradation of the compensating control itself;
- margin, collateral, settlement, liquidity, concentration, basis, and correlated effects.

A compensating control SHALL:

1. be enforceable on the hazardous path or provide independently available containment;
2. have an exact owner, scope, state machine, currentness rule, and failure response;
3. have objective non-live evidence at the required level;
4. fail closed when missing, stale, conflicting, or unverifiable;
5. remain independent of the failed control to the extent claimed;
6. preserve RCL and final-egress ownership;
7. trigger bounded restriction when unavailable;
8. not rely solely on documentation, alerting, replay, operator attention, expected broker rejection, or priority.

Capacity reservation may bound an already permitted credible effect. It cannot turn UNKNOWN into permission, prove a broker action executable, or compensate for a non-waivable control. Protective priority does not create broker or RCL protective capacity.

If the combined residual risk cannot be bounded inside the Hard Safety Envelope under loss of the compensating control, the request is denied.

---

## 12. Independent Review and Decision

Review SHALL use ADR-002-015 Effective Principal collapse before quorum counting. Independence is based on effective control and failure path, not account, role, organization, process, or service labels.

At minimum:

- the requester cannot approve;
- the control owner or implementer cannot be the sole safety reviewer;
- the evidence producer cannot be the sole evidence reviewer;
- a performance beneficiary cannot be the sole risk acceptor;
- the configuration activator cannot be the sole approver;
- the live armer cannot approve a broader scope than independently decided;
- an identity administrator able to impersonate all reviewers is a declared common mode;
- delegation cannot multiply quorum or cross a conflict boundary.

The evaluator first proves the request is outside the Non-Waivable Boundary. Failure or ambiguity produces `DENY`.

An `ELIGIBLE_FOR_RESTRICTED_CONFIGURATION` decision SHALL bind the exact request digest, accepted residual-risk record, reduced scope, controls, evidence, reviewers, expiry, policy, Deviation Generation, and one allowed configuration-request consumption. Decisions cannot be unioned, partially consumed, widened, renewed in place, or replayed.

Approval of the decision means only that RFC-001 permits the exact residual risk to enter the separate configuration workflow. It does not mean the affected requirement passed, the deviation is active, or live operation is authorized.

---

## 13. Active Deviation Set and Configuration Activation

Every Safety Configuration Bundle SHALL bind either an explicit empty Active Deviation Set or one complete canonical set containing all applicable deviations. Absence of the set, an omitted applicable deviation, mixed generation, or conflicting digest is invalid configuration.

Before exact restricted configuration activation:

1. the eligible decision is current and consumed exactly once;
2. the Active Deviation Set includes all active and interacting deviations;
3. combined residual risk remains inside the Hard Safety Envelope;
4. every compensating control is current and evidenced;
5. the Runtime Safety Profile is no broader than the approved reduced scope;
6. every consumer compatibility manifest covers the new policy and set;
7. activation is break-before-make under ADR-002-014;
8. predecessor configuration and deviation consumers are fenced;
9. affected live scope remains unarmed pending reconciliation and fresh authorization.

Repository merge, signature, approval, decision consumption, deployment, distribution, health, or Activation Record creation alone does not make the deviation active or authorize trading.

No consumer may locally combine decisions, ignore an active deviation, restore a predecessor set, or choose a more permissive interpretation.

---

## 14. Currentness, Invalidation, and Final Egress

The Deviation Generation, policy digest, Active Deviation Set digest, and exact configuration/profile generation SHALL be owner facts in the ADR-002-024 Safety Currentness Vector for every dependent new-risk action.

Final egress SHALL positively verify, without a permissive cache:

- the exact current policy and Deviation Generation;
- the exact active-set and configuration/profile digests;
- that no applicable decision, control, evidence, scope, or review invalidation is active;
- that the request is within the exact reduced scope;
- that every independent normal safety, capacity, authority, action-flow, command, venue, and currentness prerequisite still passes.

A TTL, heartbeat, service health, last-known generation, dashboard, cached decision, eventual consistency, or absence of a revocation event is not currentness proof. Failure to prove currentness is denial.

Revocation, expiry, control loss, evidence invalidation, requirement change, newly discovered dependency, common-mode discovery, scope drift, profile change, compromise, or policy change SHALL advance a restrictive floor for the complete affected dependency closure.

If a restrictive event races an authority claim, `SEND_STARTED`, or first broker byte and ordering cannot be proved, the attempt remains potentially live, capacity-covered, and non-retriable without fresh evidence and authorization. No deviation changes the ADR-002-024 race rule.

---

## 15. Expiry, Revocation, and Renewal

Every permitted deviation SHALL have a hard expiry and review interval based on trustworthy time. `null`, unknown, future-inconsistent, crossed-host-uncomparable, stale, or unverifiable time denies future dependent new risk.

Expiry and revocation SHALL:

- invalidate unused decisions and configuration requests;
- advance the Deviation Generation and restrictive currentness floor;
- revoke or fence dependent future authority and final-egress admission;
- preserve current broker, order, exposure, protection, and capacity state;
- require reconciliation and governed disposition of existing effects;
- require a new request for any continued deviation.

There is no automatic renewal, grace-period permission, rolling extension, silent predecessor restoration, or “temporary” exception without an approved end.

A new request cannot inherit approval, evidence freshness, currentness, or authority from an expired request. Repeated renewal is treated as a new combined architectural risk and may be prohibited by policy.

---

## 16. UNKNOWN, Broker Ambiguity, and Economic Continuity

Deviation governance never changes the meaning of broker or economic state.

- Unknown order acceptance remains potentially live.
- Missing ACK is not non-acceptance.
- Cancel ACK is not Final Quantity Proof.
- Partial, late, corrected, busted, external, and non-trade effects remain represented.
- Unknown exposure consumes the worst credible RCL capacity.
- Expiry or invalidation of a deviation, profile, approval, authority, or currentness proof affects future permission only.
- Capacity release still requires the normal proof-gated RCL transition.
- A favorable estimate, operator assertion, expected broker rejection, or accepted residual risk cannot free UNKNOWN capacity.

Where the exact affected dependency closure is unknown, containment expands conservatively. Capacity may be reserved for existing or uncertain effect, but that reservation cannot authorize new risk.

---

## 17. Protective, Emergency, and Break-Glass Behavior

A protective, exit, hedge, close, cancel, replace, recovery, emergency, or containment label does not bypass the Non-Waivable Boundary or exact venue, broker, economic-effect, aggregate-risk, capacity, action-flow, authority, and final-egress checks.

Break-glass may invoke HALT, deny, narrow, or request separately authorized containment. It SHALL NOT:

- approve or activate a deviation;
- expand Runtime Safety Profile scope;
- mutate or release capacity;
- classify an action as protective;
- obtain a broker credential or route;
- transmit directly;
- clear UNKNOWN or HALT;
- re-arm.

An emergency external broker-portal action is external activity. It is not retroactively made compliant by a later deviation record. The system preserves conservative capacity, reconciliation, evidence, and incident treatment.

ADR-002-027 governs incident declaration, containment, controlled shutdown, recovery handoff, and closure for that activity. Incident state, response success, closure, or absence of later loss does not make a post-hoc deviation eligible and cannot relabel failed or missing evidence as `PASS`.

If an approved protective path is unavailable, the result is trapped exposure, containment, or HALT. Priority or residual-risk acceptance does not manufacture protective capacity or executability.

---

## 18. Recovery, Rollback, and Non-Revival

Restart, failover, reconnect, quorum recovery, datastore restore, workflow recovery, identity recovery, evidence repair, clock recovery, broker recovery, operator return, or successful reconciliation may provide recovery evidence only.

After recovery:

- old policy, decision, active-set, configuration, authority, capability, and currentness artifacts remain invalid;
- restored registries prove history only after continuity and generation are reconciled;
- a stale deviation publisher or consumer is treated as potentially active until hard-fenced;
- the Recovery Barrier remains closed for the affected dependency closure;
- fresh inventory, active-set, configuration, currentness, approval, and re-arm are required;
- no predecessor profile is restored automatically.

Recovery readiness cannot accept residual risk, consume a decision, activate configuration, release capacity, clear HALT, issue authority, or transmit.

---

## 19. Evidence, Status Honesty, and Audit

Every request, decision, denial, hold, reviewer conflict, common mode, assumption, compensating-control state, configuration consumption, currentness proof, expiry, revocation, race, recovery, and economic disposition SHALL be retained under ADR-002-016.

An evidence item covered by an allowed deviation SHALL remain one of:

- `NOT_IMPLEMENTED` when no implementation evidence exists;
- `FAIL`, `INCONCLUSIVE`, `BLOCKED`, or `EXPIRED` when that is the measured result;
- `WAIVED_WITH_RESIDUAL_RISK` only when RFC-001 explicitly permits it and the exact current decision, reduced scope, compensation, and review record exist.

It SHALL NOT be relabeled `PASS`, `ACCEPTED`, or completed merely because a deviation exists. Historical failures, expired decisions, superseded scopes, and negative evidence remain visible.

Documentation, audit, replay, incident reconstruction, and post-hoc explanation are evidence. They do not prevent the hazardous action and cannot be the sole compensating control.

---

## 20. Failure-Domain and Security Requirements

The architecture SHALL identify common modes among:

- requester, evaluator, reviewers, configuration activator, live armer, and egress operator;
- identity provider, recovery administrator, devices, authenticators, and delegated principals;
- policy, requirement, evidence, decision, active-set, configuration, and currentness stores;
- signer, key management, deployment, clock, network, cache, and event transport;
- compensating control and the control it claims to replace;
- deviation revocation path and the ordinary permission path;
- final egress and any alternate credential, route, broker portal, proxy, or session.

The restrictive revocation path SHALL remain available under the declared failures. Compromise or unavailability of the deviation workflow cannot broaden authority; it denies new deviations and restricts affected active scope.

Any principal or service able to alter policy classification, active-set contents, decision consumption, configuration binding, currentness, or expiry SHALL be security-reviewed and generation-fenced. No alternate route may treat a deviation as permission.

---

## 21. State and Transition Model

Safety Deviation Request state:

```text
DRAFT
  -> SUBMITTED
  -> UNDER_REVIEW
  -> DENIED | HOLD | ELIGIBLE_FOR_RESTRICTED_CONFIGURATION
  -> CONSUMED | SUPERSEDED | REVOKED | EXPIRED
```

Active deviation applicability:

```text
NOT_ACTIVE
  -> CONFIGURATION_STAGED
  -> ACTIVE_RESTRICTED
  -> RESTRICTION_PENDING
  -> REVOKED | EXPIRED | SUPERSEDED
```

Only ADR-002-014 activation may move `CONFIGURATION_STAGED` to `ACTIVE_RESTRICTED`, and that state still creates no live authority. Any invalidation may move monotonically to `RESTRICTION_PENDING` or a terminal restrictive state.

No transition from `REVOKED`, `EXPIRED`, or `SUPERSEDED` returns to `ACTIVE_RESTRICTED`. Continued use requires a new request, decision, configuration generation, reconciliation, and governed re-arm.

---

## 22. Interaction with Existing Decisions

- ADR-002-002 and ADR-002-012 keep RCL as sole capacity authority; deviations never reserve, mutate, or release capacity.
- ADR-002-003, ADR-002-007, and ADR-002-024 fence stale authority, Deviation Generations, and dependent sends.
- ADR-002-004 broker evidence may expose residual risk but cannot weaken broker-finality semantics.
- ADR-002-006 confidence and reconciliation remain conservative; acceptance does not convert low confidence to fact.
- ADR-002-008 supplies trustworthy-time and cross-host age rules.
- ADR-002-009 supplies failure-domain and common-mode allocation.
- ADR-002-013 confines every usable broker credential and route to full final-egress enforcement.
- ADR-002-014 exclusively activates the exact restricted configuration and Active Deviation Set.
- ADR-002-015 supplies Effective Principal, conflict, quorum, HALT, and break-glass governance.
- ADR-002-016 supplies immutable evidence and non-authorizing replay.
- ADR-002-017 keeps recovery non-authorizing and requires fresh re-arm.
- ADR-002-018 through ADR-002-023 retain input, venue, construction, risk, flow, and approval requirements; a deviation cannot cause their evaluators to invent permission.
- ADR-002-025 prevents a trial or promotion process from silently waiving controls and requires residual risk to stay inside exact reduced scope.

---

## 23. Rejected Alternatives

### 23.1 Ticket Equals Authorization

Rejected. A ticket is evidence of a request, not enforcement or authority.

### 23.2 Temporary Code Bypass

Rejected. “Temporary” code paths evade exact configuration, currentness, expiry, and independent review.

### 23.3 Monitoring as Compensation

Rejected. Detection after irreversible action does not replace prevention or containment.

### 23.4 Capacity Makes UNKNOWN Safe

Rejected. Capacity covers possible effect; it does not create permission for new risk.

### 23.5 Operator or Executive Override

Rejected. Human status does not bypass the Non-Waivable Boundary or normal authority ownership.

### 23.6 Automatic Expiry Rollback

Rejected. Restoring a predecessor profile can revive stale authority and ignore current state.

### 23.7 Approval Stacking or Union

Rejected. Individually narrow deviations may interact into broader unreviewed risk.

### 23.8 Post-Hoc Waiver

Rejected. A broker effect cannot be retroactively authorized by documentation.

### 23.9 Performance Exception

Rejected. Latency or opportunity cost does not justify bypassing safety checks.

### 23.10 Incident-Free Means Safe

Rejected. Absence of observed failure is not evidence for unexercised conditions.

### 23.11 Priority Equals Protective Reserve

Rejected. Scheduling priority creates neither broker resource nor RCL capacity.

### 23.12 Recovery Restores the Exception

Rejected. Recovery evidence cannot revive an expired or invalidated decision, profile, or authority.

---

## 24. Consequences

### 24.1 Positive

- RFC-001 §14 gains one architecture-wide non-authorizing protocol;
- non-waivable safety invariants become explicit and machine-testable;
- residual-risk acceptance cannot masquerade as verification completion;
- exception scope, duration, compensation, and combined risk become exact;
- expiry and revocation reach authority and final egress monotonically;
- multiple local residual-risk references cannot form an informal bypass network;
- recovery and rollback cannot revive exception-dependent authority.

### 24.2 Negative

- many operational exceptions will be denied;
- permitted deviations require substantial independent review and evidence;
- combining deviations may force a smaller live scope than each alone;
- expiry can halt new risk until a fresh configuration is activated;
- workflow, registry, currentness, and failure-domain complexity increase;
- commercial and operational urgency cannot shorten the safety chain.

These costs are accepted because an exception system that can silently create authority is itself a safety hazard.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `WDR-EV-001` through `WDR-EV-012`. Written cases are not completed evidence.

### WDR-AC-001 — Non-Waivable Boundary

Every RFC-000, RFC-001 prohibited, RCL, egress, UNKNOWN, broker-finality, economic-continuity, fencing, segregation, independent-HALT, evidence-honesty, and no-auto-rearm deviation is deterministically denied.

### WDR-AC-002 — Exact Scope and Dependency Closure

Missing, wildcard, patched, stale, conflicting, wrong-environment, under-scoped, or independently unioned requests and decisions cannot become eligible or active.

### WDR-AC-003 — Compensating-Control Effectiveness

Documentation, monitoring, alerting, operator presence, priority, expected broker rejection, or common-mode compensation cannot satisfy the preventive/containment requirement.

### WDR-AC-004 — Independent Effective-Person Approval

One person, shared administrator, delegated identity, recovery path, or compromised workflow cannot satisfy requester, reviewer, risk acceptor, activator, and armer independence.

### WDR-AC-005 — Non-Authorizing Single-Use Activation

A request, decision, acceptance record, or active-set artifact cannot mutate capacity, activate configuration, issue authority, classify protection, transmit, clear HALT, or re-arm; decision consumption is exact and single use.

### WDR-AC-006 — Currentness, Revocation, and Send Race

Stale/cached policy, decision, control, active-set, or Deviation Generation is denied; revocation races fence later sends and ambiguous attempts remain potentially live and capacity-covered.

### WDR-AC-007 — UNKNOWN, Capacity, and Protective Confinement

Unknown applicability, residual risk, broker/order/exposure/control/evidence state blocks new risk; capacity and priority cannot turn uncertainty or a protective label into permission.

### WDR-AC-008 — Broker Finality and Economic Continuity

Missing ACK remains potentially accepted, Cancel ACK is not Final Quantity Proof, and deviation/authority/configuration expiry cannot erase effect or release RCL capacity.

### WDR-AC-009 — Expiry, Renewal, Recovery, and Non-Revival

Expiry, restart, reconnect, restore, rollback, replay, time recovery, evidence repair, reviewer return, or reconciliation cannot renew, restore, or auto re-arm exception-dependent scope.

### WDR-AC-010 — Evidence and Status Honesty

Failed, missing, incomplete, inconclusive, expired, or waived evidence remains visibly non-PASS; documentation, audit, replay, and incident absence cannot establish prevention or completion.

### WDR-AC-011 — Security, Alternate Route, and Emergency Behavior

Deviation services and break-glass cannot obtain broker authority or route around final egress; workflow compromise or outage restricts scope rather than broadening it.

### WDR-AC-012 — Combined Deviations and Gate Separation

Interacting deviations are assessed as one canonical set; ADR acceptance, deviation eligibility, configuration activation, Live Authorization, restricted-live readiness, and production readiness remain distinct states.

---

## 26. Requirements Traceability

| Requirement | ADR-002-026 allocation |
|---|---|
| RFC-001 §14 | Exact, time-bounded, auditable deviation and residual-risk governance with explicit prohibited classes (§§8–15) |
| SAFE-003, SAFE-004, SAFE-050 | Deviations bind a valid reduced profile inside the Hard Safety Envelope through normal configuration governance (§§8, 13) |
| SAFE-010, SAFE-011 | No deviation bypasses the complete pre-trade or final-egress safety path (§§7, 14) |
| SAFE-012 through SAFE-015 | Bounded aggregate risk, aggregate/action-flow evaluation, and RCL-only commitment remain non-waivable (§§8, 11, 16) |
| SAFE-021, SAFE-023 through SAFE-025 | Broker ambiguity, evidence confidence, external state, and partial fills remain conservative (§16) |
| SAFE-034 | Residual-risk and compensating-control claims require true independent review and common-mode disclosure (§§11–12) |
| SAFE-035 | Duration, expiry, review age, and recovery use trustworthy time (§15) |
| SAFE-041, SAFE-042 | Independent Safety Authority and Human HALT cannot be waived or converted into permissive break-glass (§§8, 17) |
| SAFE-044 | Startup and recovery never restore a deviation-dependent profile or authority (§18) |
| SAFE-045 | Deviation identities, workflow, evidence, and non-live systems remain segregated from live egress (§§7, 20) |
| SAFE-046, SAFE-047 | Exact activation remains non-authorizing and every scope requires fresh explicit arming and confinement (§§13–14) |
| SAFE-048 | Revocation and Deviation Generation are partition-safe owner facts at final egress (§14) |
| SAFE-051, SAFE-052 | Complete status, decision, failure, and recovery evidence remains non-authorizing (§19) |

---

## 27. Open Implementation Questions

The architecture is selected. These mechanism and parameter choices remain open while Proposed:

1. Which canonical Safety Deviation Policy, Request, Decision, Residual-Risk Acceptance Record, and Active Deviation Set schemas are approved?
2. Which requirement/hazard registry establishes non-waivable classification and exact citations?
3. Which deterministic dependency-closure and combined-risk evaluator prevents under-scoping and approval union?
4. Which compensating-control taxonomy, evidence rules, and independence analysis are approved?
5. Which ADR-002-015 workflow enforces Effective Principal, conflicts, quorum, and single-use decision consumption?
6. Which Deviation Generation registry and currentness ordering mechanism fence policy, decision, active-set, configuration, authority, and egress consumers?
7. Which final-egress mechanism actively verifies current deviation state without permissive cache or circular dependency?
8. Which restrictive revocation ingress and local latch remain available during workflow, identity, registry, network, and control-plane failures?
9. Which policy limits repeated renewals and combined active deviations without treating a count limit as risk proof?
10. Which security controls prevent registry, signer, administrator, decision-consumption, active-set, or expiry manipulation?
11. How are external emergency actions, incident discovery, retroactive requests, and trapped exposure represented without post-hoc authorization?
12. What `B_deviation_revoke_to_authority`, `B_deviation_revoke_to_egress`, `B_deviation_generation_fence`, `MAX_deviation_duration_ms`, `MAX_deviation_decision_age_ms`, and `MAX_residual_risk_review_interval_ms` values are approved?

Unresolved questions deny the affected deviation or reduce scope. They never justify a permissive default.

---

## 28. Approval and Operational Gates

ADR-002-026 SHALL remain **Proposed** until all of the following are complete:

1. Policy, Request, Decision, Residual-Risk Acceptance Record, and Active Deviation Set schemas and canonicalization are approved.
2. The requirement/hazard registry and Non-Waivable Boundary classifier are complete and independently reviewed.
3. Exact scope, dependency closure, combined-risk, materiality, and common-mode evaluation are deterministic and conservative.
4. Compensating-control eligibility, independence, evidence, currentness, and failure behavior are approved.
5. Effective Principal quorum, conflict, delegation, single-use consumption, and role separation are implemented and security-reviewed.
6. ADR-002-014 activation binds one complete Active Deviation Set break-before-make and remains non-authorizing.
7. Deviation Generation, revocation, expiry, restrictive ingress, local latch, and final-egress active currentness are implemented without permissive cache.
8. UNKNOWN, broker finality, economic continuity, capacity, protective, and emergency invariants pass fault injection.
9. Restart, failover, restore, rollback, replay, workflow/time/evidence recovery, and renewal cannot revive or auto re-arm.
10. Deviation, workflow, registry, evidence, and reviewer identities cannot reach or create unauthorized broker effect.
11. `WDR-EV-001` through `WDR-EV-012` pass at required EV-L1/EV-L3 levels and receive independent review.
12. Numeric bounds needed to accept the governance mechanism are approved and measured under non-live fault injection.
13. All applicable security, failure-domain, currentness, configuration, authority, evidence, and recovery reviews pass.
14. No Critical or Major finding remains unresolved, and canonical RFC/ADR/VER/Evidence Register traceability is complete.
15. ARCHITECTURE-GATE-STATUS records an explicit ADR acceptance decision.

Acceptance of this governance mechanism accepts no specific deviation. Every future deviation requires its own exact independently reviewed artifacts and remains subject to RFC-001 §14, the stricter active policy, every unaffected safety requirement, and separate configuration and live-authorization gates.

Authorship, EV-L0 review, a ticket, request, decision, residual-risk signature, profile draft, deployment, dashboard state, monitoring, incident absence, configuration activation, or prior approval does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize an exception, mark evidence complete, accept any ADR, permit restricted-live or production operation, enable broker transmission, or allow automatic re-arm.
