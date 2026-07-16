# ADR-002-027 — Safety Incident Declaration, Containment, Controlled Shutdown, and Closure Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Version:** 0.2
- **Last Updated:** 2026-07-17
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Safety-incident detection and declaration, exact affected scope, restrictive escalation, containment coordination, controlled shutdown, demotion, external emergency activity, investigation, closure, recovery handoff, evidence, currentness, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 §§3, 7.1–7.5, 8, and SAFE-001, SAFE-002, SAFE-010, SAFE-011, SAFE-013, SAFE-014, SAFE-021 through SAFE-025, SAFE-040 through SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§4.5, 7.5, 9.1, 10.11, 10.16–10.19, 10.26–10.28, 14.4–14.6, 15, 17, 20, and 22–24; VER-002-001 §§5, 326–337, 374, and 377–381
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-026

---

## 1. Decision

Safety-incident response SHALL be governed as a monotonic, restrictive, exact-scope, dependency-complete, generation-fenced, non-authorizing protocol. Detection, declaration, triage, communication, containment planning, shutdown planning, investigation, evidence, and closure artifacts do not create economic authority.

One active ADR-002-014 governed **Safety Incident Policy** SHALL define authoritative incident signals, severity and scope rules, required restriction, escalation and notification paths, controlled-shutdown rules, evidence obligations, independence requirements, closure conditions, and failure behavior. Missing, stale, ambiguous, conflicting, or incompletely classified incident state is restrictive for the greatest credible affected scope.

A material safety signal SHALL create or update an immutable **Safety Incident Record** and advance the **Incident Generation** before later dependent permission can be treated as current. Formal ticket creation, human availability, or classification completion SHALL NOT delay an independently available Human HALT, Safety Authority restriction, ADR-002-024 Restrictive Fence Record, or final-egress deny latch.

The **Active Safety Incident Set** SHALL be the canonical dependency-complete union of every open, suspected, overlapping, parent, child, and common-mode incident applicable to an exact Safety Cell and scope. A consumer SHALL NOT select a favorable subset, close one child while a shared unresolved cause remains, or union narrow closure decisions into broader permission.

An **Incident Containment Plan**, including its controlled-shutdown procedure where required, coordinates separately authorized restrictive and protective work. It may not mutate Risk Capacity Ledger state, classify an action as protective, issue Live Authorization or Transmission Capability, clear HALT, reach the broker, or re-arm. Every broker-directed containment action remains subject to exact protective classification, RCL capacity, broker and venue constraints, current authority, currentness, and the Broker Adapter / Egress Gateway final gate.

Controlled shutdown means stopping or fencing new economic action while preserving the safety functions and evidence needed to manage existing economic effect. Process termination, deployment scale-to-zero, connection closure, credential disablement, or strategy stop is not proof that an order was not accepted, that a broker order is final, that exposure is absent, or that capacity may be released. Shutdown SHALL NOT blindly cancel required protection, assume exit availability, force blanket liquidation, or discard unresolved obligations.

Unknown broker, order, fill, exposure, account, external-activity, protection, containment, incident-scope, or shutdown state consumes conservative capacity where economic effect may exist and blocks new risk. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Incident, authority, plan, task, credential, session, or evidence expiry does not expire economic effect.

An **Incident Closure Decision** records only that the exact current incident investigation and containment obligations meet the policy-defined administrative closure contract. It is not a safe-state assertion, evidence `PASS`, HALT clear, configuration activation, recovery-readiness decision, production-scope decision, or re-arm approval. Open economic effects may be transferred only to explicit current RCL-backed obligations with owners and evidence; closure never releases them by implication.

Recovery after an incident SHALL begin behind ADR-002-017's closed Recovery Barrier. Incident closure, service recovery, root-cause identification, remediation deployment, passing replay, quiet time, or operator return cannot revive prior authority, resume a trial, restore a production scope, clear a restrictive latch, or automatically re-arm. A fresh ADR-002-007/015 governed chain remains mandatory.

---

## 2. Context

RFC-001 includes incident response in scope and requires independent containment, conservative uncertainty, exit-unavailable handling, evidence, replay, and no automatic re-arm. Existing ADRs define the necessary control owners: Human HALT, Safety Authority, RCL, final egress, evidence integrity, recovery barrier, currentness, progressive demotion, and non-waivable deviation governance.

Those decisions do not yet assign one architecture-wide owner for incident declaration, exact dependency scope, overlapping incidents, controlled shutdown, closure, and the handoff between containment and recovery. Without a normative protocol, an implementation could:

- wait for a ticket, severity meeting, or incident commander before denying new risk;
- treat a strategy stop, process exit, disconnected socket, or revoked credential as proof that broker effect is absent;
- terminate the only protection, reconciliation, evidence, or restrictive-egress path during shutdown;
- cancel every order during shutdown, including safety-owned protection, without Final Quantity Proof or replacement analysis;
- label an incident action as protective and bypass normal classification, capacity, venue, authority, or egress checks;
- treat priority or an incident queue as reserved broker or RCL protective capacity;
- close one incident while an overlapping cause, account, credential, route, or broker session remains unresolved;
- treat elapsed quiet time, no new alerts, a root-cause document, or passing replay as closure proof;
- let an incident workflow or commander mutate capacity, issue authority, or call a broker directly;
- release capacity when an incident record, shutdown task, approval, or credential expires;
- interpret missing ACK as non-acceptance or Cancel ACK as Final Quantity Proof;
- hide a stale incident generation in cache after restriction, scope expansion, or closure invalidation;
- use emergency broker-portal activity as retroactive evidence of a compliant TOS action;
- let workflow, monitoring, identity, or control-plane recovery restore prior scope automatically;
- create a post-hoc deviation that authorizes an effect already produced.

This ADR closes those paths without assigning permissive authority to the incident-management plane.

---

## 3. Decision Drivers

1. A material signal must restrict before administrative coordination completes.
2. Incident scope must follow the greatest credible dependency closure, not team or service ownership.
3. Incident artifacts must never become a parallel capacity, authority, protection, or transmission path.
4. Controlled shutdown must preserve economic-state, protection, evidence, reconciliation, and capacity obligations.
5. Stopping software or connectivity must never be mistaken for broker finality or exposure removal.
6. Containment actions must use the normal conservative action-classification and final-egress chain.
7. Overlapping incidents and common modes must be evaluated as one active set.
8. Closure must be independently reviewed, exact, non-authorizing, and reversible only toward restriction.
9. Incident expiry and administrative completion must not expire economic effect.
10. Recovery and remediation must not revive prior authority or automatically re-arm.

---

## 4. Scope and Non-Scope

This ADR decides:

- Safety Incident Policy, signal, record, state, generation, and active-set contracts;
- severity, affected-scope, dependency-closure, and common-mode rules;
- monotonic restrictive declaration, escalation, demotion, and containment coordination;
- controlled-shutdown ordering and preserved obligations;
- external/manual broker emergency-activity treatment;
- incident evidence, investigation, closure, and recovery handoff;
- currentness, partition, stale-writer, compromise, and non-revival behavior;
- acceptance cases and operational gates.

This ADR does not select:

- an incident-management vendor, ticketing system, paging product, chat system, database, or workflow engine;
- numeric detection, restriction, scope-expansion, fencing, status-age, or closure-evidence bounds;
- a broker-side emergency procedure or permission to use one;
- a specific incident severity, commander, responder roster, or organizational escalation tree;
- a new capacity, Safety Authority, protective-classification, live-arming, or broker-transmission authority;
- permission to accept an ADR, run restricted-live, operate production, or automatically re-arm.

---

## 5. Definitions

### 5.1 Safety Incident Policy

An immutable ADR-002-014 governed policy defining authoritative signals, classification, severity, scope closure, required restrictions, containment and shutdown obligations, independence, evidence, currentness, escalation, closure, and recovery behavior.

### 5.2 Safety Signal

An authenticated observation or conservative inference that a safety invariant, authority boundary, economic-state assumption, broker contract, protective obligation, currentness fact, evidence path, or operational gate may be violated, unavailable, stale, bypassed, or unverifiable.

ADR-002-028 governs the integrity, coverage, continuity, deterministic evaluation, suppression, delivery, and escalation of operational telemetry that produces such signals. Monitoring severity remains a proposal; this ADR retains incident classification, greatest-credible scope, Incident Generation, containment, closure, and recovery ownership.

### 5.3 Safety Incident Record

An immutable versioned record of one incident identity, current Incident Generation, signals, severity, scope, dependency closure, restrictions, actions, obligations, evidence gaps, external activity, owners, and lifecycle state. It grants no authority.

### 5.4 Incident Generation

A monotonic generation fencing earlier incident scope, state, plans, closure eligibility, recovery handoff, configuration requests, authority requests, and consumers after any material signal, scope, severity, restriction, obligation, evidence, cause, plan, owner, policy, or recovery change.

ADR-002-029 source, builder, dependency/toolchain, signer/key, registry, admission, deployment, runtime-artifact, compatibility, or Release Generation compromise, contradiction, substitution, drift, or stale restore is a Safety Signal for the greatest credible dependent scope. Incident closure never readmits an artifact, clears a release restriction, restores a deployment, or reuses a prior generation.

### 5.5 Active Safety Incident Set

One immutable canonical set of every suspected or open incident and shared dependency applicable to an exact Safety Cell and scope. It is restrictive input to separately owned authority and currentness controls, not authority itself.

### 5.6 Incident Dependency Closure

Every Safety Cell, Capacity Domain, legal portfolio, account, broker, venue, instrument, strategy, order, position, commitment, protection, credential, route, session, generation, component, artifact, failure domain, evidence path, external activity, and downstream consumer that may be affected by the signal or response.

### 5.7 Incident Containment Plan

An immutable non-authorizing plan that orders restrictions, hard fences, reconciliation, protection review, capacity quarantine, evidence preservation, external-activity handling, notifications, and recovery prerequisites for one exact Incident Generation.

### 5.8 Controlled Shutdown Procedure

The ordered non-authorizing section of an Incident Containment Plan that defines how new economic action is denied and components are fenced or stopped while required protection, RCL, reconciliation, evidence, currentness, notification, and external-obligation functions remain safe.

### 5.9 Incident Recovery Handoff Package

An immutable non-authorizing package binding the exact incident and Active Safety Incident Set generation to every unresolved economic, protection, capacity, evidence, external-activity, fencing, and recovery obligation. No obligation transfers until one current ADR-002-017 Recovery Session explicitly accepts the exact package.

### 5.10 Incident Closure Decision

An immutable independent result of `DENY`, `HOLD`, or `CLOSE_ADMINISTRATIVELY` for one exact current incident and Active Safety Incident Set digest. It creates no permissive state.

### 5.11 Ongoing Safety Obligation

An unresolved position, potentially-live order, unknown broker effect, protection duty, capacity commitment, reconciliation gap, evidence gap, external activity, settlement duty, recovery task, or monitoring/fencing duty that survives incident workflow state.

---

## 6. Safety Invariants

### SIR-INV-001 — Incident Artifacts Are Not Authority

Policy, signal, record, severity, plan, task, message, timeline, evidence, review, and closure artifacts create no capacity, protection, Safety Authority, Live Authorization, Transmission Capability, broker permission, HALT clear, production scope, or re-arm authority.

### SIR-INV-002 — Declaration Is Restrictive and Asymmetric

Any authenticated safety owner, detector, or Human Safety Principal may request or invoke the separately owned restriction allowed by policy. Declaration and restriction do not wait for a permissive quorum, while closure and authority increase require full independent governance.

### SIR-INV-003 — Exact Greatest-Credible Scope

Incident scope is the complete greatest credible dependency closure. Unknown, stale, conflicting, incomplete, wildcard, patched, or self-selected scope expands containment; it never narrows permission.

### SIR-INV-004 — Combined Incidents, No Favorable Subset

Overlapping incidents, children, parents, shared causes, common modes, and response interactions are evaluated as one Active Safety Incident Set. A consumer cannot select, union, or close artifacts to create broader permission.

### SIR-INV-005 — Containment Uses Normal Authority

Incident labels, severity, priority, commander approval, or emergency status cannot classify protection, reserve capacity, waive broker/venue constraints, issue authority, or bypass final egress. Every broker-directed action follows the normal exact chain.

### SIR-INV-006 — RCL and Egress Exclusivity

Only the RCL mutates and serializes capacity. Only the Broker Adapter / Egress Gateway is the final transmission enforcement point. Incident systems hold neither a usable live-order credential nor an independent broker route.

### SIR-INV-007 — Controlled Shutdown Is Not Broker Finality

Process stop, scale-to-zero, disconnect, session close, credential revocation, route removal, or deployment shutdown does not prove non-acceptance, Final Quantity, absence of fills, or absence of external economic effect.

### SIR-INV-008 — Protection and Obligations Survive Shutdown

Shutdown preserves or deliberately transfers required protection, RCL commitments, currentness fences, reconciliation, evidence, notification, settlement, external-activity, trapped-exposure, and recovery obligations. It does not blindly cancel, liquidate, abandon, or report them complete.

### SIR-INV-009 — UNKNOWN Remains Conservative

Unknown incident scope, broker/order/fill/exposure state, containment outcome, protection, external activity, shutdown result, evidence, or currentness blocks new risk and consumes worst-credible capacity where economic effect may exist.

### SIR-INV-010 — Broker Finality Rules Do Not Change

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Incident handling cannot authorize blind retry, premature release, or optimistic reconciliation.

### SIR-INV-011 — Incident Generation Is Current at Egress

Stale incident owners, records, active sets, plans, closure decisions, recovery handoffs, authority, capabilities, and egress consumers are fenced. Cache, TTL, heartbeat, workflow health, quiet time, or absence of a newer event is not currentness proof.

### SIR-INV-012 — Closure Is Administrative and Non-Permissive

Closure records evidence-complete administrative disposition for one exact generation. It does not establish safe state, release capacity, clear UNKNOWN or HALT, validate configuration, restore scope, satisfy recovery, or authorize transmission.

### SIR-INV-013 — Economic Effect Outlives Incident State

Signal dismissal, record expiry, task completion, incident closure, credential expiry, authority expiry, evidence retention change, or workflow deletion cannot erase orders, attempts, fills, positions, obligations, external activity, or capacity consumption.

### SIR-INV-014 — Evidence and Communication Are Not Prevention

Tickets, pages, chat, dashboards, status reports, timelines, postmortems, audit, replay, root-cause analysis, and notification support response and learning but do not substitute for preventive or containment enforcement.

### SIR-INV-015 — Recovery Does Not Revive

Restart, reconnect, restore, rollback, remediation deployment, root-cause completion, evidence repair, replay match, reconciliation, time recovery, workflow recovery, quiet time, or operator return cannot revive prior incident-dependent authority, resume a trial, restore production scope, or automatically re-arm.

### SIR-INV-016 — Closure Independence and Non-Self-Exemption

The detector, affected service owner, response implementer, evidence producer, performance beneficiary, and live armer cannot collapse into one Effective Principal for closure. Unknown independence denies closure. Where two distinct natural persons are unavailable, the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001 SAFE-053) MAY supply the second independent effective principal for closure within its reduced bound scope; this adds a satisfaction path and does not relax the independence obligation or the fail-closed default on unknown independence.

---

## 7. Authority Ownership and Separation

| Action | Owner | Enforcement | Explicit prohibition |
|---|---|---|---|
| Govern Safety Incident Policy | safety-configuration governance | ADR-002-014 activation | policy activation creates no incident or live permission |
| Detect safety signal | authoritative source owner or independent detector | source identity and evidence contract | detector cannot create permissive authority |
| Declare or expand incident | incident classifier under policy; Human HALT remains separately available | immutable Incident Generation and restrictive ingress | classification cannot wait for business approval to preserve risk |
| Deny or narrow future authority | Safety Authority, Human HALT, owner restriction, or currentness fence | ADR-002-003/015/024 and final-egress latch | incident workflow cannot clear the restriction |
| Mutate capacity | none | RCL only | incident reserve, severity, priority, or plan is never capacity |
| Classify protective action | Protective Action Controller | ADR-002-001 and aggregate-risk proof | responder cannot self-label an action protective |
| Request broker-directed containment | authorized responder or controller | complete normal Intent/action chain | request cannot bypass venue, capacity, authority, or currentness |
| Transmit | Execution Coordinator requests | Broker Adapter / Egress Gateway only | incident coordinator and break-glass hold no direct route |
| Execute controlled shutdown | deployment/operations authority within approved plan | hard-fence, component, and obligation checkpoints | process termination cannot stand in for broker/economic proof |
| Collect incident evidence | source owners and Evidence Store | ADR-002-016 | evidence cannot authorize, release, or close by itself |
| Approve administrative closure | independent ADR-002-015 Effective Principal quorum | exact current closure contract | closure cannot clear HALT or re-arm |
| Establish recovery readiness | Recovery Coordinator | ADR-002-017 | incident closure cannot declare readiness |
| Re-arm | ADR-002-007/015 governance | fresh Live Authorization and final egress | automatic or incident-driven re-arm prohibited |

Incident coordinators may coordinate work but SHALL NOT accumulate the authorities of the components they coordinate.

Where a second natural person is unavailable, the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001 SAFE-053) MAY satisfy the independent Effective Principal quorum for administrative closure within its reduced bound scope, without lowering any gate in this table or clearing a HALT.

---

## 8. Incident Classification and Restrictive Declaration

The Safety Incident Policy SHALL classify at least:

- suspected or actual Hard Safety Envelope violation;
- RCL, writer-fence, capacity, currentness, authority, credential, route, or final-egress bypass;
- broker/order/fill/exposure state that is missing, contradictory, stale, or externally changed;
- protection loss, replacement gap, action-flow exhaustion, venue restriction, or trapped exposure;
- Critical Input, configuration, identity, time, evidence, recovery, or failure-domain compromise;
- unauthorized live/non-live crossover or external broker activity;
- failed bound, security control, independent approval, or restricted-live gate;
- any condition whose scope or severity cannot yet be established conservatively.

On a material signal:

1. the signal is preserved with source identity and trustworthy-time evidence;
2. the greatest credible affected dependency scope is calculated conservatively;
3. the required restrictive owner commits a HALT, deny, demotion, quarantine, or fence without waiting for ordinary workflow;
4. the Incident Generation advances and the Active Safety Incident Set is replaced atomically or treated as unknown;
5. every affected authority issuer, currentness sequencer, RCL consumer, and final egress receives or actively establishes the new restrictive fact;
6. unresolved or unreachable consumers remain non-live and potentially affected until hard fencing is proven;
7. incident coordination, notification, and evidence capture proceed without delaying the restriction.

A low-severity label cannot override a Critical invariant or make unknown scope narrow. Reclassification may expand or preserve containment immediately. Narrowing requires current evidence and the independent policy-defined decision; it never restores live authority.

---

## 9. Incident Lifecycle

The lifecycle is:

```text
SUSPECTED
  -> DECLARED
  -> CONTAINING
  -> STABILIZED_NON_LIVE
  -> INVESTIGATING
  -> REMEDIATION_PENDING
  -> ELIGIBLE_FOR_CLOSURE
  -> CLOSED
```

Rules:

1. `SUSPECTED` is restrictive for the greatest credible scope; it is not permission to wait.
2. Any material new signal, scope expansion, evidence gap, failed action, or common mode may return a pre-closure state to `CONTAINING` under a newer Incident Generation.
3. `STABILIZED_NON_LIVE` means no later new-risk effect is currently authorized and required obligations are tracked; it does not mean exposure is zero or broker state is known.
4. `INVESTIGATING` and `REMEDIATION_PENDING` remain non-live unless a separately approved unaffected scope proves complete isolation and receives fresh authorization.
5. `ELIGIBLE_FOR_CLOSURE` is a review input, not closure.
6. `CLOSED` is administrative only and does not transition to `ACTIVE`, `ARMED`, `READY`, or any live state.
7. A material post-closure signal creates a new Incident Generation and a new or reopened immutable record; it does not edit history.
8. No timer, task count, message acknowledgement, absence of alerts, or human status automatically advances the lifecycle.

---

## 10. Exact Scope, Dependency Closure, and Multiple Incidents

Incident scope SHALL be policy-owned and include every possibly affected upstream, downstream, shared, and external dependency. The affected component cannot self-exempt itself or declare a failure local.

If two incidents share an account, Capacity Domain, broker session, credential, route, currentness owner, authority generation, evidence path, failure domain, configuration, protection, or remediation, the Active Safety Incident Set SHALL represent the common mode and combined response risk.

Closing or narrowing one incident requires proof that:

- its exact effects and obligations are resolved or explicitly transferred;
- no shared unresolved parent, child, cause, or dependency can invalidate that disposition;
- the remaining Active Safety Incident Set is complete and current;
- closure does not create a more permissive configuration, authority, capacity, or egress result.

Unknown dependency closure means the broader plausible set remains contained.

---

## 11. Containment Plan and Action Confinement

An Incident Containment Plan SHALL bind:

- exact incident and Active Safety Incident Set digests and Incident Generation;
- scope, severity, signals, hazards, and dependency closure;
- committed restrictions, local latches, hard fences, and stale-owner disposition;
- positions, orders, Potentially-Live Quantity, external activity, RCL commitments, and protection obligations;
- proposed protective, cancellation, replacement, reconciliation, query, credential, route, configuration, and deployment actions;
- each action's separately owned classifier, authority, capacity, currentness, and final-egress prerequisites;
- evidence, notification, handoff, escalation, and failure behavior;
- controlled-shutdown and recovery-barrier triggers.

The plan cannot authorize its actions. An action that is missing exact current context, admissibility, construction proof, aggregate-risk proof, action-flow permit, RCL commitment, Safety Authority, Live Authorization where applicable, currentness proof, or final-egress validation is denied.

An action described as `exit`, `reduce-only`, `cancel`, `replace`, `protective`, `emergency`, or `incident-critical` is not assumed executable or risk reducing. Priority affects scheduling only; it creates no Protective Flow Reserve, broker resource, or capacity.

Failure or ambiguity of a containment action expands or preserves containment and retains worst-credible capacity. It never authorizes a blind retry or a more permissive alternate route.

---

## 12. Controlled Shutdown

For an incident requiring operational shutdown, the Incident Containment Plan's Controlled Shutdown Procedure SHALL order the following for the exact scope:

1. latch or commit denial of new risk before stopping ordinary producers;
2. revoke or fence stale Safety Authority, Live Authorization, capability, currentness, configuration, writer, credential, session, route, and deployment generations;
3. establish the disposition of every pending, claimed, `SEND_STARTED`, potentially-live, acknowledged, partial, cancel-pending, replace-pending, external, and UNKNOWN action;
4. preserve RCL commitments and quarantine uncertainty until applicable release proof exists;
5. inventory current positions, orders, fills, cash, margin, settlement, external activity, trapped exposure, and protection obligations;
6. preserve necessary protection and obtain Cancellation Arbiter approval before changing safety-owned protection;
7. preserve independently available Human HALT, restrictive egress latches, reconciliation, trustworthy time or safe time-failure behavior, evidence ingress, notification, and recovery-barrier functions;
8. hard-fence paths that cannot be observed or safely kept available;
9. record every component stop, fence, credential/session/route change, broker interaction, ambiguity, and transfer of obligation;
10. leave the scope non-live behind the Recovery Barrier.

Shutdown SHALL NOT:

- infer broker finality from process or connection state;
- cancel every order without protection and late-fill analysis;
- force liquidation when exit feasibility or projected aggregate reduction is unproven;
- stop the only surviving protective, evidence, reconciliation, or restrictive-control path without an equal or stronger proven replacement;
- release capacity because a task, lease, plan, credential, session, or process expired;
- delete queues, journals, records, or identities needed to resolve a potentially-live effect;
- treat a clean deployment shutdown as incident closure or recovery readiness.

If orderly component shutdown conflicts with preservation of a required safety function, denial and hard fencing of new risk dominate; the function remains in its narrow non-permissive role or is replaced through a proven break-before-make handoff.

---

## 13. Broker Ambiguity, Capacity, and Economic Continuity

During incident response:

- missing ACK remains potentially accepted;
- Cancel ACK remains insufficient for Final Quantity Proof;
- a broker query omission is not proof that an order or fill is absent;
- retry, cancel, replace, and query traffic remains governed by action-flow capacity and broker constraints;
- a potentially-live attempt remains capacity-covered until the normal release rule passes;
- incident, plan, authority, capability, credential, session, or record expiry does not release capacity;
- account disablement, venue halt, broker rejection, or route closure does not prove economic effect is zero;
- unknown external activity consumes conservative capacity and blocks new risk;
- RCL remains the sole capacity mutation and serialization authority.

An incident budget, severity, responder priority, shutdown plan, executive decision, or accepted residual risk is never headroom.

---

## 14. Protective and Exit Obligations

Existing protection SHALL NOT be blindly cancelled merely because ordinary trading is halted or shutdown is requested. The Protective Action Controller and Cancellation Arbiter retain their normal ownership.

If protection is missing, degraded, rejected, uncertain, or unavailable:

- the exposure remains represented and capacity-consuming;
- new risk remains denied;
- the incident scope includes every dependent portfolio and shared resource;
- only separately authorized HALT-compatible containment may proceed;
- failed protection is recorded as an ongoing obligation and may require wider shutdown or external escalation;
- the system SHALL NOT report the exposure safely closed.

Protective ordering priority is not proof of capacity, queue space, broker rate, credential, session, route, venue, borrow, or liquidity availability.

---

## 15. External and Manual Emergency Activity

An operator may request broker-side emergency action outside the TOS only under a separately approved external incident procedure and human authority. Such activity:

- is recorded as unattributed or attributed external activity under conservative evidence rules;
- does not become retroactively compliant TOS transmission;
- does not prove execution, reduction, cancellation, or Final Quantity until normal evidence rules pass;
- cannot release RCL capacity by operator statement;
- cannot clear HALT, close the incident, or re-arm;
- expands reconciliation and dependency closure to every possibly affected account and order.

Incident systems, chat bots, ticketing tools, paging tools, dashboards, and postmortem systems SHALL NOT hold a usable live-order credential and route. An unavoidable combined read/trade credential is confined by ADR-002-013 and may force narrower or prohibited live scope.

---

## 16. Incident Currentness and Final Egress

Every dependent new-risk authority issuance and final-egress decision SHALL actively establish:

- current Safety Incident Policy identity, generation, and digest;
- current Incident Generation and exact Active Safety Incident Set digest;
- exact action scope and absence of an applicable open or suspected restriction;
- current incident-scope and dependency-closure result;
- current local restrictive latch and Restrictive Fence Records;
- absence of a newer declaration, scope expansion, demotion, shutdown, compromise, or closure invalidation ordered before the claim/send boundary.

Cached `NO_INCIDENT`, stale status pages, TTL, heartbeat, service health, workflow reachability, quiet time, absence of alerts, or absence of a new event is not currentness proof. Failure to prove current incident state is denial.

If an incident restriction or scope expansion races a capability claim or first broker byte and ordering cannot be proven, the attempt is potentially live, remains capacity-covered, cannot be blindly retried, and the incident scope includes the possible effect.

The incident service does not calculate strategy intent or transmit. It publishes or signs non-authorizing owner facts consumed through ADR-002-024's currentness protocol.

---

## 17. Partition, Failure, and Compromise

| Condition | Required response |
|---|---|
| Signal source unavailable or contradictory | declare scope unknown; restrict greatest credible dependency closure |
| Incident registry or active-set unavailable | no new dependent risk; local restrictive latches remain set |
| Incident coordinator unavailable | preserve restrictions and obligations; coordination outage grants nothing |
| Control plane partition while broker route is alive | final egress denies normal new risk unless exact current non-incident state is proven through the approved fenced protocol |
| Stale coordinator or restored database | reject stale Incident Generation; treat affected scope as potentially open until hard fence and lineage are proven |
| Conflicting incident histories | contain the union; no closure or recovery handoff |
| Notification or status system fails | enforcement remains; use alternate evidence-backed notification without granting authority |
| Evidence path fails | preserve emergency evidence where possible, declare Evidence Gap, expand containment, no closure |
| Closure workflow or signer compromised | invalidate pending closure, restrict affected scope, require fresh independent governance |
| Incident system attempts broker access | reject, hard-fence identity/route, expand incident, security review |
| Shutdown step result ambiguous | assume not completed where that is safer; preserve obligations and hard fence |

Incident-management availability is subordinate to enforcement availability. Its failure cannot broaden authority.

---

## 18. Evidence, Communications, and Investigation

ADR-002-016 governs incident evidence integrity. Evidence SHALL cover:

- every signal, source identity, continuity, timestamp, classifier input, and severity result;
- Incident Generation, Active Safety Incident Set, scope, dependency closure, and every change;
- HALT, deny, demotion, fence, local latch, authority revocation, and egress receipt;
- positions, orders, attempts, fills, capacity, protection, external activity, and reconciliation state;
- containment and shutdown plan versions, action requests, approvals, denials, broker effects, failures, and ambiguities;
- credentials, sessions, routes, deployments, owners, handoffs, and common modes;
- Evidence Gaps, notification delivery, escalation, independent review, root cause, remediation, and closure;
- Recovery Barrier, recovery obligations, readiness, re-arm request, and any later authorization.

Immediate restrictive action SHALL NOT wait for the ordinary evidence pipeline when an approved emergency evidence path exists. Evidence loss remains an incident and blocks closure; it does not justify suppressing a necessary HALT.

Communications SHALL distinguish observed fact, conservative assumption, unresolved UNKNOWN, planned action, authorized action, transmitted attempt, broker evidence, verified result, and administrative decision. A message acknowledgement is never an enforcement acknowledgement.

Root-cause analysis, replay, and postmortem findings may improve future controls but cannot authorize past effects, mark preventive evidence complete, or permit current operation.

---

## 19. Demotion, Restricted-Live, and Deviation Interaction

A material incident during restricted-live or production SHALL trigger the policy-defined abort, HALT, demotion, or production-scope restriction under ADR-002-025. A previously proven narrower scope is not automatically reusable; it still requires current configuration, isolation, reconciliation, incident-set currentness, and fresh governed authority.

Incident response cannot create a Safety Deviation Decision. ADR-002-026 prohibits post-hoc waiver and preserves the Non-Waivable Boundary. A future deviation request may be evaluated only after the incident effect is represented honestly and cannot relabel the incident, failed evidence, or past broker effect as compliant.

Incident absence, low severity, small notional, successful containment, or complete root cause is not evidence that a trial or production scope is safe.

---

## 20. Closure Contract

Administrative closure requires all of the following for the exact current Incident Generation and Active Safety Incident Set:

1. authoritative signals, severity, affected scope, dependency closure, common modes, and chronology are complete or conservatively bounded;
2. every required restriction and hard fence is proven current;
3. every broker attempt and economic effect has Final Quantity Proof or remains an explicit current capacity-covered obligation;
4. positions, orders, fills, external activity, margin, settlement, trapped exposure, and protection are reconciled or explicitly retained as unresolved obligations;
5. every containment and shutdown action has evidence-backed disposition;
6. Evidence Gaps are resolved or explicitly prevent closure under policy;
7. root cause, contributing causes, control failures, and affected generations are recorded without substituting analysis for enforcement;
8. remediation and rollback effects are governed by fresh configuration and do not silently restore scope;
9. recovery obligations are transferred to ADR-002-017 behind a closed Recovery Barrier;
10. the closure request and evidence are current, exact, and independently reviewed by the required Effective Principals, or by the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001 SAFE-053) for the exact reduced scope;
11. no open parent, child, overlapping incident, shared cause, or common mode invalidates closure;
12. the closure decision explicitly states that it creates no capacity, readiness, HALT clear, authority, transmission, production scope, or re-arm.

Closure eligibility expires or invalidates on any new signal, scope change, evidence correction, obligation change, compromise, generation change, or currentness loss. A closure decision is single-use for record transition only and cannot be consumed by a live-authority path.

---

## 21. Recovery Handoff and Non-Revival

Incident containment hands off to recovery only after the exact scope and ongoing obligations are stable enough to create a dependency-complete Recovery Session. The Recovery Barrier remains closed.

Recovery SHALL independently establish current:

- safety configuration and Active Safety Incident Set;
- RCL, order, position, fill, account, external-activity, and protection state;
- authority, time, Critical Input, venue, construction, aggregate-risk, action-flow, approval, and currentness generations;
- hard fencing of stale incident, deployment, writer, authority, credential, route, and egress owners;
- evidence integrity and resolution or conservative treatment of every gap;
- complete recovery obligations and partial-scope isolation.

Incident closure is neither a recovery precondition substitute nor a readiness result. Recovery readiness cannot close the incident or issue authority. If a later fresh re-arm is requested, ADR-002-007/015 governs it and no prior approval, Trial Run, production scope, deviation, closure decision, or authorization is reused.

---

## 22. Security and Identity

Incident detection, registry, coordination, notification, evidence, investigation, and closure identities SHALL use least privilege and remain segregated from live broker credentials and routes.

Security controls SHALL prevent:

- signal suppression, forgery, downgrade, or reordering;
- scope, severity, dependency, active-set, plan, or closure substitution;
- stale coordinator, signer, database restore, or deployment continuing under an old generation;
- one Effective Principal satisfying incompatible detection, remediation, evidence, closure, configuration, and live-arming roles;
- incident closure replay or duplicate consumption;
- unauthorized deletion, redaction, or selective retention of negative evidence;
- alternate broker routes, portals, SDKs, proxies, or shared credentials bypassing final egress;
- workflow compromise from clearing restrictive state or triggering automatic recovery.

Suspected compromise is itself a safety signal and expands containment until the effective control and affected history are bounded.

---

## 23. Failure Response Matrix

| Failure | Safe default |
|---|---|
| Unclassified material signal | declare suspected; deny new risk in greatest credible scope |
| Unknown or incomplete incident scope | expand dependency closure and capacity conservatism |
| Incident Generation stale or unverifiable | deny dependent authority and send |
| Restriction propagation uncertain | local egress deny latch; treat unreachable path as potentially active until hard fenced |
| Containment action rejected or ambiguous | preserve exposure/capacity; no blind retry; widen containment as needed |
| Protection unavailable | trapped-exposure handling; no new risk; preserve obligation |
| Controlled shutdown incomplete | remain non-live; preserve components needed for narrow safety duties or hard fence them |
| Broker/order state unknown | Potentially-Live Quantity and worst-credible capacity remain |
| Evidence missing, forked, or corrected | Evidence Gap; no closure; restriction cannot auto-revert |
| Closure quorum unavailable | incident remains open; HALT remains available |
| Recovery or remediation succeeds | remain behind Recovery Barrier; fresh governance required |
| Status page says resolved but owner facts disagree | owner facts and restriction dominate |

---

## 24. Rejected Alternatives

### 24.1 Ticket-First Incident Declaration

Rejected. Administrative workflow latency cannot delay restrictive safety action.

### 24.2 Stop the Strategy and Declare Safe

Rejected. Orders, fills, exposure, broker sessions, and external effects survive strategy state.

### 24.3 Cancel Everything During Shutdown

Rejected. Blind cancellation can remove required protection and Cancel ACK is not Final Quantity Proof.

### 24.4 Liquidate Everything

Rejected. Exit may be impossible or risk increasing; every action needs conservative proof and authority.

### 24.5 Incident Commander as Emergency Broker Authority

Rejected. Coordination authority is not capacity, protection, live authorization, or transmission authority.

### 24.6 Priority Equals Protective Capacity

Rejected. Scheduling priority proves neither RCL nor broker-resource reservation.

### 24.7 Quiet Time or No Alerts Means Resolved

Rejected. Absence of observation is not currentness, finality, reconciliation, or closure proof.

### 24.8 Postmortem or Replay Means Prevention Passed

Rejected. Detective explanation cannot replace preventive evidence.

### 24.9 Close Incident and Release Capacity

Rejected. Administrative state does not expire economic effect or satisfy RCL release rules.

### 24.10 Reopen Previous Production Scope After Remediation

Rejected. Remediation and recovery do not revive configuration, authority, trial, or scope.

### 24.11 Post-Hoc Safety Waiver

Rejected. A past broker effect cannot be retroactively authorized.

### 24.12 Cached No-Incident State at Egress

Rejected. Per-send active currentness is required and restrictive facts dominate.

---

## 25. Consequences

### 25.1 Positive

- material signals restrict before administrative coordination completes;
- incident scope follows economic and failure dependencies rather than team boundaries;
- containment and controlled shutdown cannot become alternate authority paths;
- process shutdown cannot masquerade as broker finality or capacity release;
- protection, evidence, reconciliation, and economic obligations survive shutdown;
- overlapping incidents and common modes remain visible as one canonical active set;
- closure is precise, independently reviewed, non-authorizing, and separate from recovery/re-arm;
- stale incident state is fenced through the existing currentness and final-egress protocol.

### 25.2 Negative

- uncertain incidents will contain broader scope than operations may prefer;
- controlled shutdown may retain narrowly scoped safety processes longer than a simple scale-to-zero procedure;
- closure requires substantial evidence and independent review;
- incident, currentness, RCL, evidence, recovery, and deployment systems require explicit integration;
- some incidents will remain administratively open while obligations or evidence gaps persist;
- commercial urgency cannot shorten the safety chain.

These costs are accepted because an incident system that can create permission or erase economic effect would amplify the failure it is meant to contain.

---

## 26. Acceptance Cases

The following cases are mandatory and map one-to-one to `SIR-EV-001` through `SIR-EV-012`. Written cases are not completed evidence.

### SIR-AC-001 — Restrictive Detection and Declaration

Material, ambiguous, conflicting, or unclassified signals restrict the greatest credible scope before ticketing, human quorum, or ordinary workflow, while declaration itself creates no economic authority.

### SIR-AC-002 — Exact Scope and Combined Incidents

Missing dependencies, self-exemption, child-only closure, overlapping incidents, shared causes, and favorable active-set subsets cannot narrow containment or create permission.

### SIR-AC-003 — Containment Authority Separation

Incident labels, severity, commander approval, priority, or plans cannot classify protection, mutate capacity, issue authority, or bypass exact venue/currentness/final-egress checks.

### SIR-AC-004 — Controlled Shutdown and Hard Fencing

Strategy/process stop, disconnect, scale-to-zero, credential/session/route change, or deployment shutdown cannot prove broker finality; stale and unreachable paths remain denied or potentially active until hard fenced.

### SIR-AC-005 — Protection and Ongoing Obligations

Shutdown preserves safety-owned protection, trapped exposure, RCL, evidence, reconciliation, settlement, notification, and recovery obligations and cannot blindly cancel or liquidate.

### SIR-AC-006 — UNKNOWN, Broker Finality, and Capacity

Unknown broker/order/fill/exposure/containment state blocks new risk and remains capacity-covered; missing ACK and Cancel ACK retain their conservative meanings and no expiry releases effect.

### SIR-AC-007 — Incident Currentness and Send Race

Stale/cached incident policy, generation, active set, scope, plan, closure, or recovery handoff is denied; restriction/send ambiguity remains potentially live, capacity-covered, and non-retryable.

### SIR-AC-008 — Partition, Common Mode, and Compromise

Broker-reachable control-plane partition, registry outage, conflicting restore, stale coordinator, shared failure, signer compromise, or incident-system broker access restricts scope and cannot create an alternate route.

### SIR-AC-009 — Evidence, Communication, and Status Honesty

Tickets, pages, dashboards, messages, timelines, replay, postmortems, quiet time, and root-cause reports cannot substitute for enforcement, finality, currentness, closure, or verification completion.

### SIR-AC-010 — Independent Non-Permissive Closure

Closure requires exact current evidence, obligations, active-set and Effective Principal independence; it cannot clear HALT/UNKNOWN, release capacity, establish readiness, restore scope, or authorize transmission.

### SIR-AC-011 — External Activity and Demotion

Broker-portal/manual actions remain external and conservatively reconciled; incident abort/demotion cannot auto-select an older scope or become a post-hoc deviation.

### SIR-AC-012 — Recovery and Non-Revival

Restart, restore, remediation, replay match, reconciliation, time/workflow recovery, closure, quiet time, or operator return cannot resume a trial, restore production scope, reuse authority, or auto-re-arm.

---

## 27. Requirements Traceability

| Requirement | ADR-002-027 allocation |
|---|---|
| RFC-001 §3 and SC-050 | Incident response is an explicit independent restrictive protocol whose coordinator has no economic authority (§§1, 7–8) |
| SAFE-001, SAFE-002 | Default state is restrictive and shutdown preserves managed exposure and obligations (§§8, 12–14) |
| SAFE-010, SAFE-011 | Incident work never bypasses the complete authorization and final-egress chain (§§7, 11, 16) |
| SAFE-013, SAFE-014 | Aggregate/action-flow effects and response amplification remain bounded and RCL-governed (§§11, 13–14) |
| SAFE-021 through SAFE-025 | Broker ambiguity, evidence-based state, external activity, partial fills, and Final Quantity remain conservative (§§12–15) |
| SAFE-040 through SAFE-043 | Degraded protection, independent containment, Human HALT, and exit-unavailable behavior survive incident and shutdown (§§8, 11–15) |
| SAFE-044 | Incident recovery begins behind the Recovery Barrier and cannot auto-resume (§21) |
| SAFE-045 through SAFE-047 | Incident identities have no live route; closure/demotion cannot restore production scope (§§15, 19, 22) |
| SAFE-048 | Incident restrictions and generations are partition-safe currentness facts at final egress (§§16–17) |
| SAFE-050 | Safety Incident Policy and artifact activation use normal non-authorizing configuration governance (§§5, 7) |
| SAFE-051, SAFE-052 | Complete incident, shutdown, containment, closure, and recovery evidence supports reconstruction without replacing prevention (§18) |

---

## 28. Open Implementation Questions

The architecture is selected. These mechanism and parameter choices remain open while Proposed:

1. Which canonical Safety Incident Policy, Incident Record, Active Safety Incident Set, Containment Plan with Controlled Shutdown Procedure, Incident Recovery Handoff Package, and Closure Decision schemas are approved?
2. Which authoritative signal registry and deterministic severity/scope classifier prevent suppression, downgrade, and self-exemption?
3. Which dependency graph and common-mode engine calculates greatest-credible scope and combined incidents?
4. Which Incident Generation registry, writer fence, canonical active-set transaction, and restore protocol prevent stale or conflicting state?
5. Which independent restrictive ingress, local latch, and final-egress currentness mechanism applies incident declaration and scope expansion without permissive cache?
6. Which controlled-shutdown orchestrator proves ordering among egress denial, stale-path hard fencing, broker ambiguity, RCL preservation, protection, evidence, reconciliation, and component stop?
7. Which responder roles, Effective Principal conflicts, quorum, delegation, handoff, and closure-consumption mechanisms are approved?
8. Which external/manual broker incident procedure, credential custody, reconciliation, and evidence model is approved without creating a TOS bypass?
9. Which evidence, emergency journal, notification, timeline, root-cause, remediation, and closure-retention systems satisfy ADR-002-016 without delaying HALT?
10. Which ADR-002-025 demotion and ADR-002-017 Recovery Barrier handoff mechanisms prevent previous-scope reuse and automatic re-arm?
11. Which security controls prevent signal/active-set/plan/closure substitution, evidence deletion, alternate route, workflow compromise, and stale restore?
12. What `B_incident_signal_to_restriction`, `B_incident_restriction_to_egress`, `B_incident_scope_expansion`, `B_incident_generation_fence`, `B_controlled_shutdown_hard_fence`, `MAX_incident_status_age_ms`, `MAX_incident_containment_plan_age_ms`, and `MAX_incident_closure_evidence_age_ms` values are approved?

Unresolved questions keep the affected scope contained or non-live. They never justify a permissive default.

---

## 29. Approval and Operational Gates

ADR-002-027 SHALL remain **Proposed** until all of the following are complete:

1. Safety Incident Policy, Incident Record, Active Safety Incident Set, Containment Plan with Controlled Shutdown Procedure, Incident Recovery Handoff Package, and Closure Decision schemas and canonicalization are approved.
2. Signal, severity, materiality, exact scope, dependency-closure, multiple-incident, and common-mode rules are deterministic and independently reviewed.
3. Restrictive declaration, Incident Generation, active-set publication, owner fencing, restore, and final-egress currentness mechanisms are implemented without permissive cache.
4. Human HALT and automated restrictive ingress remain available independently of incident workflow and ordinary control plane.
5. Incident coordinators, responders, workflow, evidence, notification, and closure identities cannot mutate capacity, create authority, classify protection, or reach the broker.
6. Controlled shutdown proves deny-before-stop, stale-path hard fencing, broker ambiguity preservation, RCL continuity, protection continuity, evidence/reconciliation continuity, and Recovery Barrier closure.
7. Broker-directed containment, cancellation, replacement, retry, query, and external activity preserve normal classification, capacity, currentness, Final Quantity, and final-egress rules.
8. Closure independence, exact obligations, currentness, evidence, single-use record transition, and non-permissive semantics are implemented and security-reviewed.
9. ADR-002-025 demotion, ADR-002-026 deviation separation, and ADR-002-017 recovery handoff cannot restore scope, authorize past effect, or auto-re-arm.
10. Partition, common-mode, stale-owner, conflicting restore, workflow compromise, evidence loss, send race, and alternate-route behavior pass fault injection.
11. `SIR-EV-001` through `SIR-EV-012` pass at required EV-L1/EV-L3 levels and receive independent review.
12. Numeric bounds needed to accept the governance mechanism are approved and measured under non-live fault injection.
13. Every ongoing economic effect remains conservatively represented and capacity-covered until its normal release proof passes.
14. No Critical or Major finding remains unresolved, and canonical RFC/ADR/VER/Evidence Register traceability is complete.
15. ARCHITECTURE-GATE-STATUS records an explicit ADR acceptance decision.

Acceptance of this governance mechanism closes no incident, authorizes no shutdown action, accepts no evidence item, and permits no live scope. Every actual incident remains governed by exact current artifacts and separately owned enforcement.

Authorship, EV-L0 review, a ticket, page, message, incident record, plan, dashboard, root-cause report, postmortem, replay, quiet time, remediation deployment, closure signature, configuration activation, or recovery status does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live or production operation, broker transmission, incident closure, scope restoration, or automatic re-arm.

---

## 30. Review History

### v0.1 — Initial Proposed Decision (2026-07-14)

Initial safety-incident declaration, containment, controlled shutdown, and closure governance decision.

### v0.2 — Single-Operator Re-Arm Recognition (2026-07-17)

- Recognized the approved Governed Single-Operator Re-Arm Variant (ADR-002-015 §17.1, RFC-001 SAFE-053) as an additional path to satisfy the second independent effective principal in administrative incident closure, within a reduced bound scope, adding a satisfaction path without relaxing the closure-independence obligation.
- Closure remains administrative and non-authorizing; the variant cannot clear a HALT or re-arm, and unknown independence still denies closure.
- Amended SIR-INV-016, §7, and §20 item 10.
- Recorded per DR-0001 — Single-Operator Live Governance (CORPUS-REVIEW-0001 CR-02, option (c)).
