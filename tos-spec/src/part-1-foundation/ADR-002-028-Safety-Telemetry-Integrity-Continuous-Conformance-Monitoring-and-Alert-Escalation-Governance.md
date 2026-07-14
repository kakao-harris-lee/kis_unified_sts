# ADR-002-028 — Safety Telemetry Integrity, Continuous Conformance Monitoring, and Alert Escalation Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Safety telemetry classification and provenance, monitor coverage, continuous conformance, detection and restriction, monitoring gaps, suppression and maintenance, alert correlation and delivery, escalation, final-egress currentness, evidence, recovery, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 §6, §§7.1–7.5, §§11.3–11.5, §§13.4–13.6, Appendix B, and SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013 through SAFE-015, SAFE-022 through SAFE-025, SAFE-030, SAFE-031, SAFE-035, SAFE-040 through SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§4.2, 4.4–4.7, 7.4–7.5, 8, 9.1, 10.16–10.19, 10.21, 10.26–10.29, 15, 16, 17, 20, and 22–24; VER-002-001 §§5, 338–349, 350, and 353–357
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-027

---

## 1. Decision

Safety telemetry and continuous conformance monitoring SHALL be governed as an exact-scope, provenance-preserving, coverage-complete, trustworthy-time-bound, generation-fenced, fail-closed, and non-authorizing safety protocol.

One active ADR-002-014 governed **Safety Monitoring Policy** SHALL define Critical Telemetry classes, approved sources and derivations, coverage requirements, deterministic detection rules, approved bounds, independence requirements, suppression rules, restrictive dispositions, alert delivery and escalation, evidence, recovery, and failure behavior. Missing, stale, conflicting, ambiguous, unapproved, or incompletely covered monitoring state is restrictive for the greatest credible affected scope.

Every applicable Critical requirement, hazard control, approved bound, production prerequisite, restricted-live abort condition, incident signal, Recovery Obligation, and final-egress dependency SHALL be represented in one immutable **Monitor Coverage Manifest**. The manifest SHALL bind the exact responsible owner, Critical Telemetry, monitor logic, scope, failure domains, detection and containment bounds, restrictive path, alert and escalation path, evidence path, and currentness rule. A component SHALL NOT self-exempt a safety obligation because a metric is inconvenient, unavailable, noisy, or common-mode.

Critical Telemetry SHALL preserve exact identity, scope, units, semantics, source continuity, derivation lineage, trustworthy-time basis, completeness, and **Monitor Generation**. Dashboard labels, aggregate scores, heartbeats, service health, cached green state, elapsed quiet time, page acknowledgement, or absence of a new alert are not proof that the monitored fact is safe or current.

A **Continuous Conformance Snapshot** is a non-authorizing consistency cut of the exact coverage manifest and current monitor results. `CONFORMING` means only that the declared monitoring contract observed no unresolved violation within its proven scope and time basis. It does not approve an action, create headroom, mark an RFC requirement `PASS`, satisfy preventive control, establish broker finality, activate configuration, issue authority, permit transmission, close an incident, establish recovery readiness, restore scope, or re-arm.

Missing telemetry, continuity gaps, stale or mixed generations, coverage omissions, parser or unit ambiguity, common-mode loss, rule-evaluation failure, queue overflow, suppressed Critical detections, unproven delivery, and inability to establish current monitoring state SHALL create an immutable **Safety Monitoring Gap**, advance the Monitor Generation, and trigger the policy-defined restrictive path. Unknown scope expands to the greatest credible dependency closure. Monitoring failure SHALL NOT be converted into permission by fallback thresholds, local defaults, majority vote, a favorable dashboard, operator acknowledgement, or a still-reachable broker.

Monitoring may publish authenticated restrictive facts, **Safety Alert Records**, and **Alert Escalation Records** and may request ADR-002-024 fences or ADR-002-027 incident classification. It SHALL NOT own the underlying business fact, mutate or release Risk Capacity Ledger capacity, classify an action as protective, clear UNKNOWN, activate configuration, issue Safety Authority, Live Authorization, or Transmission Capability, transmit to a broker, clear HALT or a Local Restrictive Latch, close an incident, establish recovery readiness, restore production scope, or re-arm.

For any scope whose continued operation requires active monitoring, final egress SHALL actively verify the exact current Safety Monitoring Policy, Monitor Generation, Monitor Coverage Manifest, absence of applicable unresolved Monitoring Gaps, and required restrictive disposition as part of the ADR-002-024 currentness transaction. Cached `HEALTHY`, TTL, heartbeat, page-delivery status, eventual consistency, or absence of a restrictive event is not currentness proof. Verification failure denies dependent new risk; a successful result remains only a negative gate and never creates permission.

Monitoring, alert, workflow, dashboard, paging, evidence, or operator recovery cannot revive prior authority or automatically resume a trial, restore production scope, clear a restriction, or re-arm. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Monitoring or alert expiry does not expire economic effect or release capacity. Documentation, audit, replay, pages, and postmortems do not substitute for prevention or containment.

---

## 2. Context

RFC-001 SC-001 permits real capital only when applicable Critical requirements are demonstrated, independently reviewed, accepted, and continuously monitored. Limited-capital operation requires active monitoring, production loses readiness when a prerequisite is no longer maintained, and Appendix B explicitly requires an operational-monitoring specification.

Existing ADRs define trustworthy input provenance, evidence integrity, currentness ordering, restricted-live abort and demotion, and incident declaration. They do not assign one owner to the completeness and integrity of safety telemetry, the mapping from accepted obligations to active monitors, monitor continuity and generation, suppression and maintenance behavior, alert delivery and escalation semantics, or monitoring failure at final egress.

Without this contract, an implementation can appear operational while permitting unsafe sequences such as:

- treat absence of alerts as proof that controls are healthy;
- render stale cached state as green after a monitor or source restart;
- count two monitors sharing one collector, parser, clock, administrator, or datastore as independent;
- silently widen a threshold or replace a hard bound with a percentile;
- suppress a Critical signal during maintenance while allowing new risk;
- merge distinct alert scopes and lose the more restrictive obligation;
- drop negative events under queue pressure while preserving health heartbeats;
- treat page acknowledgement as containment or incident closure;
- let a monitoring-plane partition coexist with broker-reachable egress;
- accept a stale Monitor Generation at authority issuance or final egress;
- let a dashboard or alerting identity reach a broker route; or
- let monitoring recovery restore previous authority automatically.

This ADR closes those paths while keeping observation separate from prevention, incident authority, capacity authority, broker transmission, evidence custody, and recovery governance.

---

## 3. Decision Drivers

1. Continuous monitoring is a safety prerequisite, not an optional operational convenience.
2. A green or quiet monitor is meaningful only with complete, current, exact-scope coverage.
3. Telemetry corruption, omission, delay, substitution, unit drift, and common mode are safety failures.
4. Monitoring must fail closed without becoming a second business-authority plane.
5. Detection and alerting must preserve the approved numeric bound semantics and trustworthy-time basis.
6. Suppression and maintenance must never silence the underlying preventive or restrictive control.
7. Alert delivery, acknowledgement, escalation, containment, incident closure, and recovery are distinct facts.
8. The final egress boundary must reject required monitoring currentness gaps without treating monitoring health as permission.
9. Monitoring recovery must not revive authority or automatically re-arm.
10. Verification evidence must demonstrate failure behavior; written cases and registered items are not completed evidence.

---

## 4. Scope and Non-Scope

This ADR governs:

- Critical Telemetry classification and registry;
- monitor coverage and dependency completeness;
- telemetry identity, provenance, continuity, units, semantics, time, and derivation;
- deterministic monitor evaluation and bound binding;
- continuous conformance state and Monitor Generation;
- monitoring gaps and restrictive response;
- multi-path independence and common-mode disclosure;
- suppression, inhibition, maintenance, and test modes;
- alert correlation, deduplication, delivery, acknowledgement, escalation, and handoff;
- restricted-live and production continuous-conformance integration;
- incident-signal and restrictive-fence handoff;
- final-egress monitoring currentness;
- partition, compromise, recovery, evidence, and acceptance.

It does not select:

- a metrics database, collector, message bus, paging vendor, dashboard, on-call product, or observability stack;
- the business truth owned by RCL, Safety Authority, Trustworthy Time, broker reconciliation, Critical Input, venue, risk, action-flow, approval, currentness, trial, deviation, or incident owners;
- concrete monitoring thresholds or numeric bounds;
- organizational on-call rosters or employment policy;
- a broker-specific Final Quantity Proof;
- automatic corrective trading; or
- production authorization.

---

## 5. Definitions

### 5.1 Safety Monitoring Policy

The immutable governed policy defining Critical Telemetry, coverage, approved monitors, semantics, bounds, independence, restrictive response, suppression, alerting, escalation, evidence, currentness, and recovery behavior.

### 5.2 Critical Telemetry

Any measurement, event, state transition, continuity fact, coverage fact, derived result, or delivery fact whose corruption, omission, delay, substitution, mis-scoping, or misinterpretation can hide a Critical safety violation, delay required containment, or falsely preserve live eligibility.

### 5.3 Critical Telemetry Manifest

The immutable registry of exact telemetry identities, owners, source identities, scopes, units, schemas, semantics, continuity rules, derivations, time bases, freshness rules, failure domains, and consumers. It grants no authority.

### 5.4 Monitor Coverage Manifest

The immutable mapping from every applicable Critical requirement, hazard, accepted control, bound, live prerequisite, and failure mode to its exact telemetry, evaluator, dependency closure, restrictive response, alert path, evidence path, and currentness rule.

### 5.5 Monitor Generation

A monotonic generation identifying the current Safety Monitoring Policy, manifests, approved monitor logic, owners, and active restrictive state for one exact scope. Restore, rollback, failover, replacement, or policy change cannot reuse a superseded generation.

### 5.6 Continuous Conformance Snapshot

A non-authorizing consistency cut of coverage, exact monitor results, unresolved violations, gaps, suppressions, delivery state, and generation for one scope and time basis.

### 5.7 Safety Monitoring Gap

An immutable record of missing, stale, conflicting, ambiguous, discontinuous, incomplete, unverified, common-mode, failed, or suppressed monitoring coverage and its greatest credible affected scope and restrictive disposition. The shortened term **Monitoring Gap** refers only to this artifact.

### 5.8 Safety Alert Record

An immutable non-authorizing record of one alert identity, signal lineage, exact scope, severity proposal, correlation facts, required delivery and escalation policy, and linkage to restrictive and incident workflows.

### 5.9 Alert Escalation Record

An immutable non-authorizing record bound to exactly one Safety Alert Record and one policy and Monitor Generation. It records ordered delivery attempts, acknowledgements, escalation stages, failures, alternate paths, handoffs, and retirement criteria. One alert may have multiple records for independent paths or successive escalation generations, but records cannot be unioned, substituted, or used to narrow the alert scope or reset its first-observed time.

### 5.10 Restrictive Monitoring Signal

An authenticated request or fact that can only preserve or reduce future authority through the separately owned ADR-002-024/027 path. It cannot clear a restriction or create permission.

### 5.11 Monitoring Suppression

A governed temporary change to presentation or duplicate notification behavior. It SHALL NOT disable source collection, invariant evaluation, restrictive signaling, evidence, generation advancement, or final-egress denial for a Critical condition.

---

## 6. Safety Invariants

### STM-INV-001 — Monitoring Artifacts Are Not Authority

No policy, manifest, snapshot, gap, alert, acknowledgement, page, dashboard, or monitoring workflow creates capacity, approval, live authority, transmission permission, incident closure, readiness, or re-arm.

### STM-INV-002 — Coverage Is Complete and Exact

Every applicable Critical obligation has a policy-owned monitor mapping over the greatest credible dependency scope. Missing or unknown coverage is a gap, not an exemption.

### STM-INV-003 — Telemetry Semantics Are Exact

Identity, scope, source, units, schema, meaning, derivation, continuity, and time basis are immutable and verified. A consumer cannot reinterpret or silently default them.

### STM-INV-004 — Absence Is Not Health

No alert, repeated health heartbeat, quiet time, successful scrape, empty query, or green dashboard proves safety, completeness, currentness, or containment.

### STM-INV-005 — UNKNOWN Is Restrictive

Missing, stale, conflicting, ambiguous, discontinuous, mixed-generation, or unverifiable monitoring state blocks dependent new risk and expands to the greatest credible scope.

### STM-INV-006 — Common Mode Is Not Independence

Shared sources, collectors, parsers, clocks, datastores, networks, administrators, identities, deployments, notification routes, or vendors do not count as independent paths.

### STM-INV-007 — Approved Bound Semantics Are Preserved

Hard maxima, units, scope, trigger, start and stop events, composition, uncertainty, and failure response cannot be replaced by a percentile, average, local threshold, hidden grace period, or favorable sampling rule.

### STM-INV-008 — Suppression Cannot Suppress Safety

Maintenance, inhibition, mute, deduplication, test, or operator acknowledgement cannot disable a required restrictive path, hide an unresolved Critical state, or create permission.

### STM-INV-009 — Alert State Is Orthogonal

Detection, delivery, acknowledgement, escalation, containment, incident lifecycle, recovery, and economic finality are independent states. Advancement of one never implies another.

### STM-INV-010 — Loss and Backpressure Preserve Negative Facts

Overflow, queue pressure, retry, correlation, deduplication, or delivery failure cannot preferentially discard adverse state or reset elapsed detection and escalation time.

### STM-INV-011 — Authority Ownership Remains Separate

Monitoring may request restriction and incident evaluation only. Existing owners retain capacity, authority, protection, configuration, broker transmission, incident, and recovery transitions.

### STM-INV-012 — Current Monitor Generation Is a Negative Gate

Required monitoring currentness is actively verified at authority and final egress. A successful check can only avoid denial; it never supplies permission.

### STM-INV-013 — Broker Finality and Economic Continuity Do Not Change

Missing ACK remains ambiguous, Cancel ACK is not Final Quantity Proof, UNKNOWN effect stays capacity-consuming, and monitor or alert expiry never expires economic effect.

### STM-INV-014 — Evidence Is Not Prevention

Metrics, logs, alerts, dashboards, pages, audit, replay, reports, and postmortems cannot replace a preventive or restrictive enforcement point.

### STM-INV-015 — Monitoring Recovery Does Not Revive

Restart, reconnect, failover, restore, replay, backlog drain, source recovery, alert delivery, operator return, or quiet time cannot restore prior authority or automatically re-arm.

### STM-INV-016 — Stale Writers and Consumers Are Fenced

Superseded monitor publishers, evaluators, manifests, dashboards, and consumers cannot publish or accept a prior Monitor Generation after replacement, rollback, or restore.

---

## 7. Authority Ownership and Separation

| Action | Owner | Monitoring limitation |
|---|---|---|
| Publish underlying safety fact | Existing authoritative component | monitor cannot invent or widen the fact |
| Govern telemetry and coverage semantics | Safety Monitoring Policy governance | cannot activate configuration or arm live scope |
| Publish telemetry | Fenced source owner under Critical Telemetry Manifest | cannot self-declare completeness or independence |
| Evaluate monitor rule | Safety Monitoring Service | produces non-authorizing result only |
| Record monitoring evidence | ADR-002-016 Evidence Store | custody does not create permission |
| Request restrictive fence | Monitoring service via authenticated restrictive ingress | ADR-002-024 owns ordering and latch behavior |
| Classify and declare incident | ADR-002-027 incident governance | monitoring supplies a signal, not incident authority |
| Revoke or issue Safety Authority | Safety Authority | monitor health cannot issue authority |
| Mutate or release capacity | Risk Capacity Ledger | monitoring never writes capacity |
| Classify protective action | Protective Action Controller | alert severity is not protective classification |
| Transmit | Broker Adapter / Egress Gateway | monitoring and alert identities hold no usable credential and route |
| Establish recovery readiness | Recovery Coordinator | monitor recovery is only an obligation input |
| Re-arm | ADR-002-007/015 governed chain | no automatic path from green state or acknowledgement |

No monitoring, alert, dashboard, paging, ticket, incident-notification, analytics, or replay identity may hold a usable live-order credential and broker route. If an unavoidable combined read/trade credential exists, ADR-002-013 confinement applies and live scope is reduced or prohibited until bypass is disproven.

---

## 8. Critical Telemetry Classification and Registry

The Safety Monitoring Policy SHALL classify as Critical Telemetry every fact needed to detect loss of an applicable Critical requirement, Hard Safety Envelope rule, Runtime Safety Profile rule, authority or currentness dependency, capacity invariant, broker-finality assumption, evidence obligation, recovery obligation, trial prerequisite, deviation control, or incident restriction.

Unknown materiality is Critical. A producer, monitor owner, dashboard owner, or consumer SHALL NOT self-classify a telemetry item as non-Critical merely because the underlying preventive control exists elsewhere.

The Critical Telemetry Manifest SHALL bind at minimum:

- canonical telemetry and semantic identity;
- owner and publisher identity and epoch;
- exact environments, Safety Cells, Capacity Domains, accounts, brokers, venues, instruments, strategies, action classes, and control scopes;
- value type, units, scale, sign, cardinality, allowed states, and missing-value semantics;
- source identities, continuity, sequence, schema, and transformation lineage;
- trustworthy-time basis, event time, observation time, receipt anchor, age, skew, and uncertainty;
- expected cadence, completeness, aggregation, sampling, and loss rules;
- approved derivation and invariant evaluator identities and digests;
- dependency closure, consumers, restrictive response, and evidence class;
- failure domains, common modes, access, retention, and security classification.

Hash equality, metric name, topic, label, dashboard panel, or source health alone does not establish semantic equivalence.

---

## 9. Monitor Coverage Manifest

Coverage SHALL begin from the normative requirement and hazard registry, not from whichever metrics happen to exist. For every applicable item the manifest SHALL identify:

1. exact requirement, hazard, invariant, gate, bound, or obligation;
2. scope and dependency closure;
3. underlying preventive or restrictive owner;
4. required telemetry and source continuity;
5. deterministic evaluator and expected states;
6. detection trigger, bound, measurement start and stop, and uncertainty treatment;
7. required restrictive action and containment owner;
8. alert delivery and escalation stages;
9. evidence and independent-review obligations;
10. failure-domain and common-mode analysis;
11. final-egress or recovery currentness dependency where applicable;
12. approved exclusions with proof that corruption or omission cannot affect safety.

An exclusion is valid only when independent policy governance proves that telemetry corruption or omission cannot affect a safety decision, delay containment, weaken evidence, or falsely preserve live eligibility. Unknown scope or impact is included.

Coverage percentages, monitor counts, or dashboard completeness scores cannot replace item-level closure. A favorable union of narrow manifests cannot create broader coverage.

---

## 10. Telemetry Provenance, Continuity, and Trustworthy Time

Critical Telemetry is governed by ADR-002-018 source identity, continuity, schema, unit, mapping, derivation, common-mode, and correction rules and by ADR-002-008 trustworthy-time rules.

Publisher restart, failover, restore, sequence reset, endpoint change, credential change, parser change, schema change, clock discontinuity, ownership change, or data-history truncation creates a new continuity fact or explicit gap. Identical values before and after a discontinuity do not prove continuity.

Cross-host monotonic values SHALL NOT be directly subtracted. A consumer measures receipt age on its own monotonic basis and includes transport uncertainty under the approved protocol. Future, negative, unknown, or unbounded age cannot be clamped into freshness.

Sampling, aggregation, downsampling, cardinality limiting, retention compaction, and late-event policies SHALL be explicit. They may not erase a short-lived Critical violation, transform a hard maximum into an average, or discard only adverse observations.

A correction or retraction preserves the original observation and advances every dependent result, snapshot, gap, evidence, restriction, trial, incident, and Monitor Generation required by its dependency closure.

---

## 11. Deterministic Evaluation and Bound Semantics

Monitor logic SHALL be immutable, versioned, canonical, deterministic for identical inputs, and independently testable. The policy binds the evaluator digest, exact inputs, units, states, thresholds, hysteresis, debounce, aggregation, windowing, uncertainty, and failure response.

An approved hard maximum cannot be implemented as a percentile, average, best-effort target, or window that permits an individual exceedance. Debounce, grace, hysteresis, and confirmation windows count inside the applicable detection or containment bound unless the approved Verification Profile explicitly defines otherwise.

Unknown numeric input, NaN, infinity, overflow, underflow, non-convergence, unit mismatch, parser differential, missing sample, insufficient history, or evaluator disagreement yields `UNKNOWN` or a restrictive result. It never yields `CONFORMING` by default.

Multiple monitors may corroborate a result only under an approved source-authority and independence rule. Majority or newest-arrival selection is not automatically authoritative.

---

## 12. Continuous Conformance State and Monitor Generation

For each exact scope, one fenced owner SHALL publish a monotonic Monitor Generation and immutable Continuous Conformance Snapshot. The snapshot SHALL bind:

- Safety Monitoring Policy and both manifest digests;
- exact scope and dependency closure;
- owner epoch and Monitor Generation;
- every required monitor and result;
- source continuity, age, time confidence, completeness, and common-mode state;
- active violations, unknowns, gaps, suppressions, and delivery failures;
- restrictive signals, fences, incidents, trial aborts, and unresolved handoffs;
- evidence references and Snapshot validity.

Allowed aggregate results are `CONFORMING`, `RESTRICTED`, `NON_CONFORMING`, and `UNKNOWN`. `CONFORMING` requires every required item to be current, complete, and independently valid under policy. `RESTRICTED`, `NON_CONFORMING`, or `UNKNOWN` denies dependent new risk for the affected scope.

Any material policy, manifest, monitor, dependency, scope, source, evaluator, bound, suppression, failure-domain, or owner change advances the generation and invalidates affected snapshots. A stale owner is treated as potentially active until hard fencing is proven.

---

## 13. Monitoring Gaps and Restrictive Response

A Safety Monitoring Gap is mandatory when any required coverage cannot be positively established. It SHALL record exact scope, first observation, credible start interval, source and evaluator state, missing evidence, common modes, greatest credible impact, required restrictions, alert state, owner, current generation, and closure proof.

Gap detection SHALL not wait for a page, ticket, human acknowledgement, or root-cause classification before an independently available restrictive path acts. The restriction may be issued through ADR-002-024 or classified by ADR-002-027, but those owners retain the transition authority.

If gap scope is unknown, the scope expands across shared accounts, Capacity Domains, Safety Cells, broker sessions, credentials, routes, datastores, clocks, deployments, policies, or failure domains until isolation is positively proven.

Monitoring recovery does not close the gap by itself. Closure requires continuity re-established under a new or current fenced generation, loss interval bounded, missed violations conservatively reconstructed, dependent state re-evaluated, evidence gaps resolved or explicitly restrictive, and every required owner handoff accepted.

---

## 14. Independence and Common-Mode Analysis

Independent monitoring requires independent effective control and failure paths, not different process names or dashboards. Shared source, collector, exporter, parser, schema registry, library, time source, message bus, datastore, network, region, credential, administrator, CI pipeline, deployment, notification provider, or policy owner is a disclosed common mode.

Where one authoritative source exists, the design SHALL not invent independence. It may use independent transport, raw capture, invariant checks, broker/account comparisons, or externally controlled observation, but remaining common mode is recorded as residual risk and may reduce or prohibit live scope.

A monitor SHALL NOT approve its own omission, validate its own source continuity using only its output, or treat its own health endpoint as proof of semantic correctness.

---

## 15. Suppression, Inhibition, Maintenance, and Test Modes

Critical monitoring suppression SHALL be deny-by-default, immutable, exact-scope, purpose-bound, short-lived, independently approved, generation-bound, visible, evidenced, and automatically restrictive on expiry or uncertainty. Suppression approval is not a Safety Deviation Decision unless ADR-002-026 separately authorizes an eligible exact deviation; non-waivable controls remain unsuppressible.

Suppression may reduce duplicate human notifications only when all of the following remain active:

- telemetry collection and continuity;
- monitor evaluation and violation state;
- Monitoring Gap creation;
- restrictive signaling and local deny latching;
- incident-signal handoff;
- evidence capture and audit;
- escalation on suppression failure or expiry;
- final-egress currentness and denial.

Maintenance and testing SHALL use explicit non-live or restricted scopes. A maintenance window cannot widen a threshold, reinterpret missing data as healthy, stop a required fence, reuse a prior acknowledgement, or permit live operation because operators expect noise.

---

## 16. Alert Correlation, Delivery, Acknowledgement, and Escalation

Every Critical detection and Monitoring Gap SHALL create a stable Safety Alert Record bound to signal lineage, exact scope, Monitor Generation, first-known time, severity proposal, required restriction, and incident-classification rule. Each required delivery or escalation path SHALL create or advance an Alert Escalation Record bound to exactly that alert; multiple paths preserve distinct records and cannot be combined to widen, narrow, or reset the alert.

Correlation and deduplication may link related records but SHALL preserve each distinct source, scope, trigger, first-observed time, bound, restrictive state, and evidence lineage. It cannot collapse a broader or more severe condition into a favorable parent or reset elapsed time.

Delivery is positively evidenced per required channel and recipient class. Queue acceptance, webhook success, email submission, page creation, or UI rendering is not recipient acknowledgement. Recipient acknowledgement means only that the exact alert was received by an authenticated effective person or approved automated endpoint. It is not containment, remediation, broker finality, incident closure, recovery readiness, or re-arm.

Failure or uncertainty at any delivery or escalation stage advances the applicable Alert Escalation Record, preserves the original deadline, invokes the next independent route where policy permits, and may widen restriction. Retries are attributable and bounded; retry storms remain subject to ADR-002-022 and may not consume proven protective capacity.

No alerting or escalation route may directly send a broker action. A requested protective or containment action enters the normal separately authorized path.

---

## 17. Restrictive Fast Path and Incident Handoff

Monitoring SHALL support an independently available authenticated restrictive path whose failure domain does not collapse with the monitored producer or ordinary dashboard. Applicable Critical detections and monitoring gaps request an ADR-002-024 Restrictive Fence or Human/Safety HALT without waiting for the alert workflow.

The monitoring service proposes a Safety Signal with exact lineage, scope, confidence, common modes, Monitor Generation, and evidence. ADR-002-027 remains responsible for materiality, severity, greatest-credible incident scope, Incident Generation, active incident set, containment, shutdown, handoff, and closure.

No monitor or alert may downgrade an existing fence or incident, select a narrower scope, clear a local latch, or publish `NO_INCIDENT`. Conflicting monitoring and incident state resolves to the more restrictive state.

---

## 18. Final-Egress Active Currentness

Where a Monitoring Policy declares continuous monitoring mandatory for the exact action scope, the Broker Egress Gateway SHALL include these facts in the ADR-002-024 Safety Currentness Vector:

1. exact Safety Monitoring Policy identity, generation, and digest;
2. exact Critical Telemetry and Monitor Coverage Manifest digests;
3. current Monitor Generation and fenced owner epoch;
4. action-scope coverage completeness;
5. current conformance result and absence of applicable unresolved gaps;
6. active suppression state and proof that it does not disable safety;
7. applicable restrictive signal, fence, incident, and trial-abort generations;
8. required Snapshot age, trustworthy-time, and invalidation state.

These facts are actively established inside the ordered per-send currentness transaction. Cached green state, TTL, heartbeat, dashboard reachability, alert acknowledgement, last-known generation, eventual consistency, or absence of a negative event is not proof.

If a gap or restriction is ordered before the capability claim, the send is denied. If ordering between a material monitoring invalidation and first broker-directed byte cannot be proven, the attempt remains potentially live, capacity-covered, and ineligible for blind retry. Monitoring success never overrides another denial or creates a Transmission Capability.

---

## 19. UNKNOWN, Capacity, and Economic Continuity

Monitoring is not the owner of broker, order, fill, position, exposure, capacity, account, or settlement truth. A monitor result may invalidate confidence or request restriction but cannot set an order to rejected, a position to zero, an obligation to settled, or a capacity commitment to released.

Missing broker ACK remains possible acceptance. Cancel ACK is not Final Quantity Proof. A lost or failed monitor covering broker evidence expands UNKNOWN and preserves the worst credible economic effect in RCL capacity. Capacity availability cannot turn unknown monitoring state into permission.

Policy, telemetry, snapshot, alert, acknowledgement, suppression, page, incident, workflow, credential, or session expiry only restricts future authority. It never expires existing economic effect, protective obligation, external activity, or capacity commitment.

Priority and escalation do not create reserved protective capacity. Any broker-directed protective response still requires a proven protective classification and pre-committed capacity and action-flow resources.

---

## 20. Restricted-Live and Production Continuous Conformance

ADR-002-025 EV-L6 monitoring SHALL use this protocol. A Restricted-Live Trial Policy and Production Scope Promotion Decision SHALL bind the exact current Safety Monitoring Policy, manifests, Monitor Generation, required evidence, abort rules, and gap dispositions.

Trial or production scope is demoted or restricted when required coverage is lost, a monitor becomes stale or conflicting, a bound is exceeded, a common mode invalidates claimed independence, negative evidence is missing, a suppression is unapproved or expired, or delivery/escalation fails beyond policy.

Incident-free time, favorable P&L, low notional, operator presence, stable dashboards, high uptime, monitor recovery, or completed evidence packages cannot compensate for an unproven preventive control, restore a demoted scope, or automatically promote or re-arm.

---

## 21. Partition, Backpressure, and Failure Behavior

| Failure | Mandatory result |
|---|---|
| telemetry source or continuity lost | create gap; restrict greatest credible dependent scope |
| collector, parser, evaluator, or registry unavailable | deny dependent new risk; preserve raw evidence and generation |
| monitor owner or generation conflict | fence writers; treat both as potentially active until resolved |
| monitoring plane partitioned while broker egress is reachable | deny unless exact current state is independently proven through the approved fenced protocol |
| queue overflow or backpressure | preserve adverse records; restrict; never sample them away |
| alert delivery or escalation unproven | maintain restriction and escalate through an independent path |
| common-mode independence claim fails | remove independence benefit and reduce or prohibit scope |
| suppression state missing, stale, or expired | treat monitoring state as restricted and unsuppressed |
| time confidence or receipt-age proof lost | results become stale/UNKNOWN; deny dependent new risk |
| evidence path unavailable | enforcement continues; create Evidence Gap and restrict per policy |
| dashboard or paging system compromised | isolate it; preserve restrictions; no authority through alternate route |
| recovery or backlog drain completes | no authority revival; closed Recovery Barrier and fresh governed chain remain |

No retry, failover, majority vote, cache, local threshold, or alternate notification route may select a more permissive result when the authoritative ordering or scope is unknown.

---

## 22. Security and Identity

The design SHALL protect:

- telemetry publishers, collector admission, schema and mapping registries;
- monitor policy, manifests, evaluator artifacts, and generation registry;
- raw and derived telemetry integrity and continuity;
- restrictive signal and incident handoff identities;
- gap, alert, delivery, acknowledgement, escalation, and suppression records;
- monitor and dashboard query boundaries;
- operator and service authentication, authorization, and effective-control independence;
- backups, restore generations, and stale-writer fences.

Compromise or suspected compromise of any component expands to its greatest credible shared scope, creates a Monitoring Gap, advances or fences the Monitor Generation, and invokes restriction. A compromised monitor cannot clear its own gap or attest its own recovery.

Read-only telemetry access does not justify possession of a live-order route. Combined read/trade credentials are an ADR-002-013 common-mode exception and may make the affected live scope non-conforming.

---

## 23. Evidence and Status Honesty

Evidence SHALL preserve:

- policies, manifests, evaluator and deployment digests;
- raw telemetry, transformations, corrections, sequence and continuity;
- exact monitor inputs, deterministic outputs, uncertainty, and time basis;
- generation transitions, owner fencing, gaps, suppressions, and restrictions;
- alert correlation, delivery, acknowledgement, escalation, and failures;
- currentness proofs, send races, incident handoffs, and recovery;
- negative, missing, conflicting, late, dropped, duplicated, and inconclusive outcomes.

Dashboards SHALL distinguish at minimum `CURRENT_CONFORMING`, `RESTRICTED`, `NON_CONFORMING`, `UNKNOWN`, `STALE`, `GAP`, and `UNVERIFIED`. Rendering failures or unknown state SHALL NOT default to green.

An EV-L0 document review, registered evidence item, monitor definition, deployed dashboard, successful page, passing replay, or absence of recorded violations is not executed EV-L1 through EV-L6 evidence and does not make an ADR Accepted or a system live-ready.

---

## 24. Recovery and Non-Revival

Startup, restart, reconnect, failover, restore, policy activation, monitor deployment, source recovery, queue drain, alert acknowledgement, replay, or operator return occurs behind the ADR-002-017 Recovery Barrier for the affected dependency scope.

Recovery obligations include complete manifests, current policy and Monitor Generation, source continuity, loss-interval reconstruction, all active gaps and suppressions, current restrictive signals/fences/incidents, delivery and escalation state, evidence completeness, owner fencing, and final-egress currentness.

Prior `CONFORMING` snapshots, alert acknowledgements, suppressions, trial state, production scope, authority, capabilities, or pages are not reusable. Recovery readiness is non-authorizing and a fresh ADR-002-007/015 governed re-arm chain remains mandatory.

---

## 25. Rejected Alternatives

### 25.1 “No alerts means healthy”

Rejected because source, monitor, delivery, or dashboard failure can produce silence.

### 25.2 “A green dashboard is the safety gate”

Rejected because dashboards are lossy views, not authoritative enforcement or currentness proof.

### 25.3 “Monitoring compensates for missing prevention”

Rejected because documentation, detection, audit, and replay do not substitute for pre-effect prevention.

### 25.4 “Two dashboards are independent”

Rejected unless their complete effective-control and failure paths are independent.

### 25.5 “Maintenance may mute Critical checks”

Rejected. Presentation may be reduced only while evaluation, restriction, evidence, and escalation remain active.

### 25.6 “Page acknowledgement means contained”

Rejected because acknowledgement, containment, finality, closure, and recovery are orthogonal states.

### 25.7 “Use percentiles for every safety bound”

Rejected because a percentile cannot demonstrate a hard maximum unless the approved requirement explicitly says so.

### 25.8 “Drop duplicate alerts under pressure”

Rejected when deduplication loses distinct scope, lineage, first occurrence, bound, or restrictive state.

### 25.9 “Monitoring may directly trade to contain”

Rejected because this creates a broker-route bypass and collapses observation with economic authority.

### 25.10 “Cached conformance is enough at egress”

Rejected because stale green state cannot prove active currentness.

### 25.11 “Monitoring recovery restores production”

Rejected because recovery never revives prior authority or automatically re-arms.

### 25.12 “A written monitor test is evidence”

Rejected because cases and registrations are obligations until executed and independently reviewed.

---

## 26. Consequences

### 26.1 Positive

- Continuous monitoring becomes an explicit safety contract rather than dashboard convention.
- Critical coverage omissions and monitor failures fail closed.
- Telemetry meaning, time, lineage, and common modes become reviewable.
- Alert acknowledgement can no longer be mistaken for containment or closure.
- Suppression cannot silently disable restrictive safety behavior.
- ADR-002-025 EV-L6 and ADR-002-027 signals receive a trustworthy substrate.
- Final egress rejects required monitoring gaps without treating monitoring as authority.
- Recovery and incident workflows preserve non-revival.

### 26.2 Negative

- Complete coverage and source registries add governance and operational cost.
- Telemetry volume, raw retention, deterministic evaluation, and independent paths increase infrastructure cost.
- Conservative failure behavior can halt trading during monitoring or paging faults.
- Common-mode analysis can reduce allowable live scope.
- Numeric bounds, delivery guarantees, suppression policy, and recovery reconstruction require broker- and deployment-scoped evidence.

These costs are accepted because availability cannot justify unobserved loss of a Critical safety prerequisite.

---

## 27. Acceptance Cases

Written cases define obligations only. They are not completed evidence.

### STM-AC-001 — Complete Critical Coverage

Every applicable Critical requirement, hazard, invariant, bound, and live prerequisite maps to exact current monitors and a restrictive failure path; an omitted or self-exempted item blocks the scope.

### STM-AC-002 — Provenance, Continuity, Semantics, and Time

Publisher restart, sequence gap, schema/unit drift, derivation change, or time discontinuity cannot preserve a falsely current result.

### STM-AC-003 — UNKNOWN, Silence, and Stale Green State

Missing telemetry, quiet time, health heartbeats, cache, empty query, or stale dashboard cannot produce `CONFORMING` or permission.

### STM-AC-004 — Independence and Common Mode

Shared collector, parser, clock, datastore, administrator, deployment, or notification route is disclosed and cannot count as independent corroboration.

### STM-AC-005 — Bound and Evaluator Integrity

Hard maximum, units, trigger, uncertainty, hysteresis, debounce, and failure response are exact; parser differential, NaN, overflow, or local threshold change fails closed.

### STM-AC-006 — Suppression and Maintenance Safety

Mute, inhibition, maintenance, testing, expiry, or unknown suppression state cannot disable evaluation, restriction, evidence, escalation, or final-egress denial.

### STM-AC-007 — Alert Correlation, Delivery, and Escalation

Deduplication preserves scope and lineage; backpressure and delivery failure preserve adverse facts and deadlines; acknowledgement never implies containment.

### STM-AC-008 — Restrictive and Incident Handoff

A material monitor result reaches an independently available restrictive path and ADR-002-027 with exact lineage without giving monitoring incident, capacity, or broker authority.

### STM-AC-009 — Active Currentness and Send Race

Stale Monitor Generation, unresolved gap, permissive cache, monitoring-plane partition, or invalidation-versus-first-byte ambiguity cannot authorize new risk and remains potentially live and capacity-covered where a send may have occurred.

### STM-AC-010 — UNKNOWN, Broker Finality, and Economic Continuity

Missing ACK, Cancel ACK, unknown exposure, alert expiry, and available capacity cannot be converted into non-acceptance, FQP, released effect, or new-risk permission.

### STM-AC-011 — Compromise, Fencing, and Failure Domains

Compromised or stale publishers, evaluators, dashboards, registries, suppressions, and notification systems are fenced; alternate routes and shared dependencies cannot bypass restriction.

### STM-AC-012 — Evidence, Recovery, and Non-Revival

Documentation, registration, dashboard status, page delivery, replay, source recovery, queue drain, or operator return cannot claim verification completion, restore authority, or automatically re-arm.

---

## 28. Requirements Traceability

| Requirement | Discharge |
|---|---|
| RFC-001 SC-001, §§13.4–13.6, Appendix B | complete continuous monitoring, loss-of-prerequisite restriction, and operational-monitoring contract (§§8–24) |
| SAFE-003, SAFE-004, SAFE-050 | governed exact policy, manifests, evaluator semantics, bounds, and generation (§§8–12) |
| SAFE-010, SAFE-011, SAFE-013 through SAFE-015 | monitoring is a non-authorizing negative gate; RCL and final egress retain exclusive authority (§§7, 18–19) |
| SAFE-022 through SAFE-025 | gaps, broker ambiguity, economic continuity, and reconciliation handoff remain conservative (§§13, 19, 24) |
| SAFE-030, SAFE-031, SAFE-035 | provenance, continuity, semantics, source independence, and trustworthy time are explicit (§§8–11, 14) |
| SAFE-040 through SAFE-044 | restrictive fast path, alert escalation, incident handoff, protection, and recovery remain independently available (§§16–17, 21, 24) |
| SAFE-045 through SAFE-048 | live/non-live scope, current arming, production confinement, partition, and stale generation are monitored without becoming authority (§§18, 20–22) |
| SAFE-051, SAFE-052 | complete adverse telemetry, gaps, alerts, delivery, suppressions, recovery, and replay evidence are preserved without substituting for prevention (§23) |

---

## 29. Open Implementation Questions

1. Which Safety Monitoring Policy, Critical Telemetry Manifest, Monitor Coverage Manifest, and canonical registries are approved?
2. Which source, collector, transformation, continuity, schema, unit, label, cardinality, sampling, and raw-retention contracts cover each Critical telemetry class?
3. Which deterministic evaluator and independent verification mechanisms prevent threshold, parser, unit, window, and aggregation drift?
4. Which requirement/hazard/control registry establishes complete scope and prevents monitor-owner self-exemption?
5. Which Monitor Generation, owner fence, publication, restore, invalidation, and final-egress active-currentness mechanisms are conforming?
6. Which independent restrictive ingress and local latch remain available when ordinary monitoring, control, or alert planes fail?
7. Which common-mode taxonomy and failure-domain allocation establish independent detection and notification paths?
8. Which suppression, maintenance, test, approval, expiry, and emergency rules are allowed per scope?
9. Which correlation, deduplication, queue, backpressure, delivery, acknowledgement, escalation, on-call handoff, and retry protocols preserve exact adverse state?
10. Which ADR-002-027 signal handoff and severity/scope interface prevents suppression, downgrade, duplicate closure, or authority collapse?
11. Which loss-interval reconstruction and Recovery Obligations prove monitoring continuity after restart, failover, restore, or backlog drain?
12. Which `B_safety_telemetry_loss_detect`, `B_monitoring_gap_to_authority_restrict`, `B_monitoring_gap_to_egress_deny`, `B_critical_alert_delivery`, `B_alert_escalation`, `B_monitoring_generation_fence`, `MAX_critical_telemetry_age_ms`, `MAX_continuous_conformance_snapshot_age_ms`, `MAX_safety_alert_age_ms`, `MAX_monitoring_suppression_duration_ms`, and `MAX_alert_acknowledgement_age_ms` values are approved and measured?

Unresolved questions reduce or prohibit live scope. They do not permit a weaker default.

---

## 30. Approval and Operational Gates

ADR-002-028 remains `Proposed` until all of the following are satisfied:

1. canonical policy, telemetry, coverage, snapshot, gap, and alert-escalation schemas are approved;
2. the requirement/hazard/control registry and conservative coverage compiler are implemented and independently reviewed;
3. source continuity, semantic, unit, derivation, trustworthy-time, raw-retention, and correction paths are implemented and security-reviewed;
4. deterministic monitor evaluators and independent differential tests reject omission, stale state, parser drift, numeric failure, and threshold weakening;
5. Monitor Generation, owner fencing, invalidation, restrictive ingress, local latch, and final-egress currentness are implemented without permissive cache or circular trust;
6. suppression, maintenance, test, correlation, deduplication, backpressure, delivery, acknowledgement, escalation, and handoff protocols are implemented fail-closed;
7. monitoring, alert, dashboard, paging, ticket, evidence, and replay identities cannot reach a live broker route or mutate capacity/authority;
8. ADR-002-025 EV-L6 and ADR-002-027 incident handoff use the exact current monitoring contract without transferring authority;
9. numeric bounds and age/suppression limits are approved in the Verification Profile and measured under fault injection;
10. STM-EV-001 through STM-EV-012 and applicable upstream evidence are executed at their required levels and independently reviewed;
11. restart, failover, partition, common mode, suppression, queue overflow, notification failure, compromise, stale restore, send race, recovery, and non-revival tests pass;
12. no Critical or Major finding remains open, including coverage, source/semantic, numeric, currentness, broker-route, suppression, and escalation security findings;
13. Architecture Gate acceptance remains explicit; document review alone does not promote status.

Authorship, EV-L0 review, a monitor definition, dashboard, page, alert acknowledgement, passing replay, incident-free interval, policy approval, configuration activation, recovery status, or registered evidence item does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live or production operation, broker transmission, scope promotion, incident closure, capacity release, or automatic re-arm.
