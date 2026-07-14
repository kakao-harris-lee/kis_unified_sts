# ADR-002-015 — Human Safety Authority, Dual Control, and Break-Glass Governance

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Effective human principal identity, approval policy, quorum independence, approval attestations and sets, separation of duties, delegation, authentication, emergency HALT, break-glass containment, re-arm, approval revocation, compromise response, availability, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 §§7.5–7.6, SAFE-041, SAFE-042, SAFE-046, and SAFE-050; RFC-002 §§9.1, 10.17, 23, and 28; ADR-002-003 §§9, 16, and 18; ADR-002-007 §§5, 12–13, and 25; ADR-002-013 §§7, 16, and 25; ADR-002-014 §§8, 13–14, and 26
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-034, SAFE-035, SAFE-041, SAFE-042, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-014

---

## 1. Decision

The TOS SHALL implement human safety authority through explicit, immutable, authenticated, scope-bound artifacts evaluated against an approved **Human Authority Policy**. Role labels, chat messages, tickets, shared accounts, possession of an administrative credential, or successful login are not human approval authority.

The architecture SHALL distinguish four authority directions:

1. **HALT or deny** — one current authorized Human Safety Principal may invoke an authenticated restrictive latch for the permitted scope without waiting for an expansion quorum;
2. **request containment or protection** — a human may request only an approved action class, while classification, exclusive capacity, state, time, egress, and broker rules remain mandatory;
3. **approve authority increase or re-arm** — requires an approved quorum containing at least two distinct effective Human Safety Principals, exact context binding, current independent evidence, and single-use consumption where specified;
4. **mutate capacity or transmit** — no human approval, operator session, or break-glass credential may directly perform either action; RCL and final egress remain the exclusive authorities.

Emergency authority is asymmetric: it SHALL be easier to reduce authority than to create or restore it. A break-glass path may HALT, deny, narrow, or request separately authorized containment. It SHALL NOT enlarge the Hard Safety Envelope, broaden a Runtime Safety Profile, issue Live Authorization, create or release capacity, clear UNKNOWN, cancel required protection, submit directly to a broker, or automatically re-arm after recovery.

Every risk-increasing re-arm approval SHALL use at least two distinct authenticated natural persons whose effective control paths satisfy the active separation policy. Multiple accounts, credentials, devices, service identities, delegated bots, or sessions controlled by the same natural person count as one principal.

Approval attests to one exact decision context, including the ADR-002-018 Decision Context Capsule identity and digest, the ADR-002-019 Venue Constraint Snapshot and Order Admissibility Decision identities and digests, and the ADR-002-020 Intent proposal, Authorized Construction Envelope, and candidate Canonical Broker Command identities and digests where the action is broker-directed. Any material change to input, source continuity, Capsule, venue/session/tradability/account/order constraint, Intent, construction envelope, candidate command, evidence, scope, artifact digest, generation, software, deployment, broker, credential, route, time, residual risk, or approval policy invalidates the affected approval before authority issuance. Approval expiry, revocation, service recovery, venue reopen, compiler recovery, or credential recovery never expires economic effect and never re-arms authority.

---

## 2. Context

RFC-001 requires independent Safety Authority, authenticated human emergency authority, explicit live arming, and safety-configuration governance. RFC-002 and ADR-002-007 require separated human control for re-arm and prohibit one identity from enlarging limits and arming live scope.

Those rules do not yet define how the system determines whether two approvals are truly independent or what an approval proves. Unsafe implementations include:

- one person approving twice through two accounts;
- a shared team account satisfying a two-person rule;
- a workflow administrator adding themselves to every approval role;
- a profile author approving the change and then arming it through a different service account they control;
- a stale approval being replayed after evidence or profile changes;
- a broad “approve production” ticket being applied to another account, strategy, broker, or deployment;
- delegated approval remaining valid after the delegator or delegate loses authority;
- an expired operator session continuing to issue HALT or re-arm commands;
- break-glass credentials providing a direct broker-order route;
- emergency containment bypassing RCL capacity, protective classification, or final egress;
- a dual-control service outage being bypassed by a single administrator;
- a human HALT waiting for the failed strategy or ordinary control plane;
- recovery of the identity or approval service silently restoring old live authority;
- approval evidence being treated as prevention without an enforcing consumer.

Human governance is a safety protocol, not merely an organizational procedure. This ADR defines its mechanism-independent contract.

---

## 3. Decision Drivers

1. Human HALT must remain available independently of strategy and ordinary arming paths.
2. Authority increase and re-arm must require genuinely distinct effective human control.
3. Every approval must bind the exact decision, evidence, scope, artifacts, and validity interval.
4. Approval replay, delegation drift, role drift, and credential compromise must fail closed.
5. Break-glass authority must be directionally restrictive and incapable of broker bypass.
6. Human approval must not collapse configuration, evidence, capacity, Live Authorization, and egress authorities.
7. Unavailable approval infrastructure must reduce availability, not safety.
8. Compromise and recovery must not revive prior authority or erase economic effect.
9. Evidence must support independent reconstruction without becoming approval or enforcement.

---

## 4. Scope and Non-Scope

This ADR decides:

- effective Human Safety Principal identity and independence;
- Human Authority Policy content and governance;
- approval request, attestation, set, consumption, expiry, and revocation contracts;
- separation of duties and conflict-of-interest rules;
- delegation and roster-change behavior;
- authentication, session, device, and recovery constraints;
- emergency HALT and break-glass containment authority;
- human roles in authority increase, safety-profile governance, and re-arm;
- compromise, partition, recovery, evidence, and acceptance behavior.

This ADR does not select:

- an identity provider, hardware authenticator, PKI, workflow product, pager, or operator UI;
- named personnel or organization-specific titles;
- the final quorum size for every envelope, profile, deployment, or residual-risk decision beyond ADR-002-007's minimum two humans for risk-increasing re-arm;
- labor policy, on-call scheduling, or general corporate access management;
- a direct manual trading procedure;
- a broker or credential product.

Human authority under this ADR is TOS safety authority. Broker portal, support desk, dealer, or other external manual authority remains external activity under ADR-002-004, ADR-002-006, and ADR-002-013.

ADR-002-023 separately governs automated per-proposal independent approval and its single-use Intent Registry consumption. A Human Approval Set may approve governance, residual risk, or re-arm where policy requires, but it cannot substitute for the ADR-002-023 independent automated decision; conversely an automated `APPROVE` cannot satisfy a human quorum.

---

## 5. Definitions

### 5.1 Human Safety Principal

One verified natural person acting through one or more authenticated identities and devices under an approved safety role.

### 5.2 Effective Principal

The equivalence class of accounts, credentials, devices, sessions, service identities, recovery factors, and administrative control paths that one natural person or controller can use to exercise safety authority.

Two labels are not independent when one effective controller can authenticate, recover, impersonate, approve for, or change the authorization of both.

### 5.3 Human Authority Policy

An ADR-002-014 governed immutable artifact defining roles, allowed authority directions, quorum and independence rules, conflicts, scopes, authentication strength, validity, delegation, recovery, revocation, and emergency behavior.

### 5.4 Approval Request

An immutable request for one exact approval type, action, scope, evidence package, artifact and generation set, maximum authority, reason, expiry, and consumption rule.

### 5.5 Approval Attestation

One Human Safety Principal's authenticated decision to approve, deny, or abstain on one exact Approval Request after reviewing the required independent inputs.

### 5.6 Approval Set

A verified collection of current Approval Attestations that satisfies one exact Human Authority Policy and request. An Approval Set is not Live Authorization and grants no broker or capacity authority.

### 5.7 Break-Glass Authority

A separately protected emergency authority limited to HALT, deny, narrow, or request pre-defined containment. It is not a permissive override.

### 5.8 Approval Consumption

The authoritative binding of an Approval Set to the one activation, issuance, re-arm, or exception decision it permits. A single-use set cannot be consumed again.

### 5.9 Human HALT Command

An authenticated, monotonic, scope-bound restrictive command that final egress and the Safety Authority may accept without waiting for the normal risk-increasing approval path.

---

## 6. Safety Invariants

### HAG-INV-001 — Effective-Person Distinctness

Two required human approvals come from two distinct effective natural persons, not merely two accounts, sessions, credentials, devices, or role labels.

### HAG-INV-002 — Exact Context Binding

Every approval binds one exact request, scope, evidence generation, profile and envelope generation, software/deployment identity, broker/egress context, reason, policy, and validity interval.

### HAG-INV-003 — No Self-Approval Chain

No strategy, author, implementer, validator, evidence producer, workflow administrator, or live armer may unilaterally satisfy the independent approvals governing its own authority increase.

### HAG-INV-004 — Approval Is Not Authority

An Approval Attestation or Approval Set cannot mutate capacity, activate configuration, issue Live Authorization, clear a deny latch, or transmit to a broker.

### HAG-INV-005 — HALT Is Asymmetrically Available

One authorized Human Safety Principal can invoke a restrictive HALT without requiring the proposer, strategy, ordinary dual-control quorum, or live-arming service.

### HAG-INV-006 — Break Glass Cannot Expand

Break-glass authority cannot create, restore, broaden, or prolong new-risk authority and cannot automatically revert a restriction.

### HAG-INV-007 — Protective Request Is Not Protective Authority

A human label or emergency request cannot classify an action as protective, create reserved capacity, bypass an exclusive lease, or skip final egress.

### HAG-INV-008 — Changed Context Invalidates

Any material bound context change invalidates prior unconsumed approval. A broader or different request requires a new request and current approval set.

### HAG-INV-009 — Delegation Does Not Multiply Authority

Delegation is explicit, non-transitive, bounded, revocable, and cannot make one effective principal count more than once or delegate authority the grantor lacks.

### HAG-INV-010 — Compromise Fails Closed

Suspected compromise of an approver, authenticator, device, workflow, roster, or recovery path invalidates affected pending authority, suspends affected live scope where necessary, and requires fresh governed recovery.

### HAG-INV-011 — Unavailability Does Not Reduce Quorum

Unavailable humans, identity services, workflow services, or authenticators do not lower the approval quorum or permit a single-principal bypass. HALT remains independently available.

### HAG-INV-012 — Approval Expiry Does Not Expire Economic Effect

Expiry, revocation, or consumption of approval does not cancel orders, release capacity, resolve UNKNOWN, prove broker non-acceptance, or prove final quantity.

### HAG-INV-013 — External Manual Activity Is Not Approval

Broker portal, support, dealer, phone, chat, email, ticket, or other manual activity is not TOS approval or compliant egress unless it passes the complete governed protocol; external broker effect remains unattributed/external and conservative.

### HAG-INV-014 — No Automatic Re-arm

Recovery of a human, credential, device, identity provider, workflow, approval service, or control plane cannot reuse approval or restore live authority automatically.

---

## 7. Authority Classes and Direction

| Class | Direction | Minimum TOS effect | May create broker effect? |
|---|---|---|---|
| `HALT` | strictly restrictive | set monotonic deny/restrictive generation | no direct order mutation |
| `NARROW` | proven restrictive | reduce future scope after validation | no direct order mutation |
| `REQUEST_PROTECTIVE` | proposal only | enter ordinary protective classification and capacity workflow | only after independent protective authority and egress |
| `APPROVE_PROFILE_OR_ENVELOPE` | may increase | approve exact ADR-002-014 artifact request | no |
| `APPROVE_REARM` | may increase | permit one exact Live Authorization issuance request after all gates | no |
| `ACCEPT_RESIDUAL_RISK` | may increase | accept one exact bounded limitation under policy | no |
| `CAPACITY_MUTATION` | economic authority | RCL-only transition | not human authority |
| `TRANSMIT` | irreversible boundary | ADR-002-013 final egress | not human authority |

Any action whose direction cannot be proven is authority increasing. No UI label such as “emergency,” “close,” “hedge,” “safe,” or “temporary” changes that classification.

---

## 8. Effective Principal and Independence Model

The identity system SHALL maintain an authenticated **Effective Principal Graph** including:

- natural-person identity and employment/authorization state;
- human accounts and aliases;
- authenticators, recovery factors, devices, and sessions;
- service accounts, bots, API credentials, and signing keys the person controls;
- role and group memberships;
- delegated authority and its grantor chain;
- identity-provider, workflow, repository, signer, and roster administrative control;
- emergency credentials and custody;
- conflicts of interest and scope restrictions.

Quorum evaluation SHALL collapse all nodes under common effective control before counting principals. Independence is absent when one person can reset, impersonate, mint credentials for, approve as, or change the role of another counted principal within the decision path.

Organizational separation, reporting line, geographic location, or different devices MAY strengthen independence but do not replace proof of distinct natural persons and control paths.

The graph and policy generation SHALL be bound into every Approval Set. Unknown, stale, contradictory, or incompletely resolved effective-control state is denial for authority increase.

---

## 9. Human Authority Policy

The Human Authority Policy SHALL define for every approval type:

- exact action and authority direction;
- minimum quorum and required distinct roles;
- effective-principal independence constraints;
- author, implementer, validator, evidence-owner, reviewer, deployer, administrator, credential, egress, and live-armer conflicts;
- permitted environment, Safety Cell, account, strategy, instrument, broker, action, and capacity scope;
- required evidence and independent recomputation;
- authentication, device, session, and presence requirements;
- validity, review, expiry, revocation, and single-use rules;
- delegation and recovery restrictions;
- escalation and unavailable-quorum behavior;
- emergency HALT and containment rules;
- notification, evidence, and independent-review obligations.

The policy is a Critical safety artifact governed by ADR-002-014. Policy change cannot approve itself, lower the quorum for a pending request, validate against a stale predecessor, or preserve prior re-arm authority. An authority-increasing policy change requires independent approval under the predecessor policy or a stricter separately approved transition policy.

No wildcard role, “any administrator,” “team approval,” “on-call approval,” or unbounded group membership may create authority without resolving exact current Human Safety Principals.

---

## 10. Approval Request and Attestation Contract

Every Approval Request SHALL bind at least:

- request identity, type, nonce, predecessor, and creation generation;
- exact requested action and maximum authority;
- environment, Safety Cell, account, portfolio, strategy, instrument, venue, broker, order/action class, and time scope;
- Recovery Evidence Package and readiness decision identities;
- Hard Safety Envelope, Runtime Safety Profile, Human Authority Policy, Broker Capability Profile, Verification Profile, and Failure-Domain Allocation Matrix identities and digests;
- software, deployment, workload, credential, route, egress, trust-bundle, RCL, writer, authority, time, revocation, and HALT generations;
- unresolved state, exact ADR-002-026 Safety Deviation Policy/Request/Decision/Residual-Risk Acceptance Record/Active Deviation Set/Deviation Generation identities and digests where applicable, residual risks, exceptions, and scope reductions;
- reason, requested validity, consumption rule, and invalidation conditions;
- required independent inputs and reviewer roles.

Every Approval Attestation SHALL bind the exact request digest, principal, effective-principal graph generation, role, decision, reviewed inputs, independent recomputation result, authenticator/session context, issue time, expiry, and signature.

An approver SHALL explicitly deny or abstain when required evidence is missing, contradictory, stale, outside competence, or controlled by the proposing component without approved independent corroboration. Silence, timeout, absence, emoji, chat acknowledgement, ticket state, or meeting attendance is not approval.

---

## 11. Approval Set Validation and Consumption

Before an Approval Set becomes eligible for use, the verifier SHALL:

1. load one exact active Human Authority Policy and Effective Principal Graph generation;
2. verify request completeness, canonical digest, freshness, and current context;
3. verify every attestation signature, human identity, role, scope, session, device, issue time, and expiry;
4. collapse common effective principals and reject duplicate natural persons;
5. enforce conflict-of-interest and independence rules;
6. verify the required quorum and mandatory roles;
7. revalidate every bound artifact and evidence generation;
8. reject revoked, superseded, consumed, replayed, broader, stale, or policy-mismatched attestations;
9. commit or otherwise authoritatively bind the Approval Set identity to the exact downstream decision;
10. consume single-use approval atomically with the permitted activation or Live Authorization issuance request.

Approval Set verification and consumption SHALL be ordered through ADR-002-012 or a transactionally coupled linearizable namespace. Ordering does not grant the approval service capacity, configuration, Live Authorization, or broker authority.

An approval for one narrower scope cannot be unioned with another approval set to construct a broader scope unless the active policy explicitly requires and validates that exact combined request.

ADR-002-025 trial eligibility and production-scope promotion SHALL collapse identities through the same current Effective Principal Graph before quorum counting. A Trial Plan, Trial Evidence Package, or Production Scope Promotion Decision cannot count as a principal, multiply quorum, approve itself, activate configuration, issue Live Authorization, or substitute for the complete ADR-002-007 re-arm workflow.

---

## 12. Separation of Duties

At minimum, the following combinations are prohibited for the same effective principal and decision scope. A policy may add conflicts or require stronger organizational separation, but it SHALL NOT waive these minimum prohibitions:

- trading proposer and independent trade approver;
- Hard Safety Envelope or Runtime Safety Profile author and sole approver;
- authority-increasing limit approver and sole live armer;
- implementation author or evidence producer and independent evidence reviewer;
- Recovery Coordinator decision producer and sole re-arm approver;
- Human Authority Policy author/administrator and sole beneficiary or approver of its change;
- identity/roster/recovery administrator and all counted members of the approval quorum;
- credential/route/egress administrator and sole approver of the resulting live scope;
- Approval Set verifier and unilateral downstream authority issuer;
- break-glass custodian and authority-increasing bypass approver.

A person MAY perform multiple non-conflicting roles for disjoint scope only when the policy, failure-domain analysis, effective-control graph, and retained evidence prove independence. Staffing convenience is not proof.

Automation may route requests, validate signatures, compute conflicts, enforce policy, and deny. Automation SHALL NOT count as a required human principal.

---

## 13. Delegation, Roster, and Recovery

Delegation SHALL be:

- issued by a currently authorized principal under a policy that permits delegation;
- limited to one role, scope, environment, purpose, and validity interval;
- accepted by one exact delegate;
- non-transitive unless every link and total chain is explicitly allowed;
- no broader or longer than the grantor's current authority;
- revocable and invalidated by grantor, delegate, role, policy, scope, or employment change;
- incapable of allowing grantor and delegate to count as independent approvals for the same request when effective control or conflict remains.

Roster and role changes create a new policy or identity generation and invalidate affected pending approvals. Removing a principal, authenticator, device, or recovery factor SHALL prevent future use and revoke affected unconsumed attestations.

Account recovery, authenticator reset, device replacement, identity-provider migration, or emergency credential retrieval creates a new identity/session generation. Prior approvals and live authority do not transfer automatically.

Shared, escrowed, generic, or team credentials SHALL NOT count as human approval identity. Emergency credential custody may be shared operationally only when each use resolves to one authenticated natural person and the credential cannot grant permissive authority.

---

## 14. Authentication and Session Requirements

Safety-critical human actions SHALL require phishing-resistant, replay-resistant authentication appropriate to the approved assurance level, plus exact environment and action confirmation.

The authenticated command SHALL bind:

- Human Safety Principal and effective-principal generation;
- role and policy generation;
- trusted device or approved emergency authenticator identity;
- session creation, authentication strength, maximum age, and current revocation state;
- exact command/request digest, scope, and environment;
- trustworthy-time generation and nonce;
- user-presence or equivalent confirmation where required.

Authentication success does not prove approval authority. The policy and exact request remain mandatory.

Session renewal, SSO recovery, device unlock, network reconnection, or application restart SHALL NOT replay a command, extend approval, clear a HALT latch, or restore live authority. Session ambiguity or revocation uncertainty denies authority-increasing action.

---

## 15. Human HALT Path

The Human HALT path SHALL remain available independently of strategy, decision, approval quorum, ordinary profile workflow, and live-arming services.

One current authorized Human Safety Principal MAY issue a Human HALT Command for its permitted scope. The command SHALL:

1. be strongly authenticated and bound to exact scope, environment, nonce, policy, principal, and session generation;
2. be accepted only as a monotonic restrictive action;
3. set a local final-egress deny latch immediately where the command is received;
4. advance or request the authoritative HALT generation without waiting for normal permissive workflow;
5. reach every affected final egress within `B_human_halt_to_commit` plus `B_halt_to_egress`, with overlapping measurement defined by the Verification Profile;
6. preserve open orders, fills, positions, UNKNOWN, capacity, and protective ownership;
7. produce evidence and independent notification through a path not controlled solely by the operator;
8. remain latched until full governed recovery and re-arm.

If the Safety Commit Log or normal control plane is unavailable, authenticated final egress MAY accept the restrictive command into a monotonic local deny latch and later reconcile it. It SHALL NOT accept any permissive command through this degraded path.

A duplicate HALT is idempotent. An ambiguous HALT result is treated as possibly applied and cannot justify re-arm.

---

## 16. Break-Glass Containment and Protective Requests

Break-glass may authorize only pre-defined restrictive commands and requests. It SHALL NOT hold or obtain a general broker client, credential, signer, session, or route.

A human request to cancel, close, hedge, replace, exercise, or otherwise contain exposure is a proposal. It proceeds only when:

- Protective Action Controller or ordinary policy independently classifies the action;
- every credible intermediate state is within the Hard Safety Envelope;
- RCL or an exclusive pre-issued protective sub-ledger authorizes exact capacity;
- protective ownership and Cancellation Arbiter rules are satisfied;
- trustworthy time and broker capability permit it;
- ADR-002-013 final egress validates exact current capability and request.

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Break-glass cannot recycle UNKNOWN capacity, renew an expired lease, reassign protective ownership, or treat priority as reserved protective capacity.

If the proposed action cannot be proven protective, it is risk increasing and requires the ordinary approval, capacity, and live-authority path or is denied.

---

## 17. Authority Increase and Re-arm

Every risk-increasing re-arm SHALL use at least two distinct effective Human Safety Principals and the complete ADR-002-007 workflow.

The sequence is:

1. create one exact Approval Request from a current, non-invalidated ADR-002-017 Recovery Evidence Package and Recovery Readiness Decision for the exact Recovery Generation and requested narrow scope;
2. independently authenticate and validate each approver and required input;
3. construct and verify the Approval Set under the current Human Authority Policy;
4. atomically consume the set for one exact Live Authorization issuance request;
5. have the Live Authorization Service issue a fresh, scoped, revocable, time-bounded authorization;
6. have final egress verify the current approval-set reference, authorization, generations, capability, capacity, and deny state.

The approval quorum cannot waive a Hard Safety Envelope, RCL capacity, UNKNOWN, reconciliation, time, broker, failure-domain, egress, or verification gate. Human acceptance of residual risk applies only through the exact ADR-002-026 contract where RFC-000/RFC-001 and the active policy permit it, remains non-authorizing and non-PASS, and cannot waive the Non-Waivable Boundary or a Critical invariant.

Partial re-arm restores only the exact approved scope. Expansion, renewal, extension, fallback, or reuse requires a new current request and approval set.

---

## 18. Approval Lifecycle

```text
REQUESTED -> REVIEWABLE -> ATTESTING -> QUORUM_SATISFIED -> CONSUMED

{REQUESTED, REVIEWABLE, ATTESTING, QUORUM_SATISFIED} -> DENIED
{REQUESTED, REVIEWABLE, ATTESTING, QUORUM_SATISFIED} -> EXPIRED
{REQUESTED, REVIEWABLE, ATTESTING, QUORUM_SATISFIED} -> INVALIDATED
{REQUESTED, REVIEWABLE, ATTESTING, QUORUM_SATISFIED} -> REVOKED
QUORUM_SATISFIED -> SUPERSEDED
```

Only `QUORUM_SATISFIED` may become `CONSUMED`, and only through the exact permitted downstream transition. No terminal or invalid state returns to a permissive state.

Individual attestations use `APPROVE`, `DENY`, or `ABSTAIN`. A later `APPROVE` does not erase a retained denial; policy determines whether a new request is required. Changed material context always requires re-evaluation.

Consumption, expiry, revocation, or invalidation of approval does not reverse the downstream economic effects already created. It may suspend future authority, but orders and capacity follow their own proof-governed lifecycles.

---

## 19. Compromise, Revocation, and Incident Response

Suspected compromise of a Human Safety Principal, authenticator, device, session, identity provider, roster, workflow, signing key, approval verifier, recovery path, or break-glass custody SHALL trigger:

1. revocation of affected sessions, delegations, pending attestations, and unconsumed Approval Sets;
2. HALT or the narrowest sufficient restriction for affected live scope;
3. identity, policy, credential, route, deployment, and approval-history review;
4. preservation of every potentially-live order and economic effect in capacity;
5. detection and reconciliation of external or unattributed activity;
6. generation advancement and hard fencing of old identity/control paths;
7. fresh evidence, approvals, and governed re-arm before authority restoration.

An approval already consumed before compromise discovery does not prove that resulting authority remains safe. The affected scope SHALL be conservatively suspended until the decision lineage and economic state are established.

Unknown revocation or unknown impersonation scope blocks authority increase. Deleting an account, ticket, alert, or audit record is not proof that the old control path is fenced.

---

## 20. Availability, Partition, and Recovery

Loss of quorum, approval workflow, identity provider, policy registry, effective-principal graph, authenticator validation, or current time blocks new authority increase and re-arm.

The Human HALT path SHALL use failure-domain separation sufficient to remain available when ordinary strategy and approval services fail. Where online identity validation is unavailable, a pre-provisioned emergency authenticator MAY issue only a finite, current, scope-bound restrictive command whose key, principal, policy generation, and expiry are locally verifiable. It cannot approve, protectively transmit, or re-arm.

Recovery of any human-control dependency creates no authority. Pending requests and approvals are revalidated against current evidence, policy, graph, time, identity, and generation state; stale items are invalidated.

Unavailable required humans or roles do not reduce quorum. Planned absence must be addressed through pre-approved delegation or staffing, not runtime policy weakening.

---

## 21. External Manual and Broker Authority

Broker portal, dealer, support desk, phone, email, emergency API key, or other manual broker path SHALL NOT be represented as Human Safety Approval or compliant TOS egress.

If such authority exists:

- it is inventoried in the Broker Capability Profile and ADR-002-013 boundary analysis;
- its activity is external or unattributed until reconciled;
- possible orders, fills, cancellations, and positions consume conservative capacity;
- missing broker evidence blocks new risk;
- it cannot satisfy a re-arm approval or clear a TOS HALT;
- recovery requires current reconciliation and governed re-arm.

An operator may request broker-side emergency containment outside the TOS only under an approved external incident procedure. The resulting economic effects remain external activity and do not become retroactively compliant TOS actions.

ADR-002-027 defines that incident procedure's architectural boundary. One authorized human may invoke restrictive HALT or incident scope expansion, but incident closure, recovery handoff, production-scope restoration, and any later re-arm remain separately governed. The detector, responder, evidence producer, remediator, closer, and live armer are evaluated through this ADR's Effective Principal and conflict rules.

---

## 22. Evidence, Metrics, and Alerts

The system SHALL retain:

- Human Authority Policy and Effective Principal Graph generations and digests;
- human identity proof, role, authenticator, device, session, recovery, delegation, and revocation lineage;
- every Approval Request, attestation, denial, abstention, set validation, conflict, expiry, revocation, and consumption;
- exact evidence, artifacts, scope, reasons, residual risks, and independent computations reviewed;
- Human HALT command, local latch, authoritative commit, propagation, egress receipt, and recovery lineage;
- break-glass custody, retrieval, use, denial, notification, and rotation;
- authority issuance, restriction, compromise, and re-arm lineage;
- failed, duplicate, stale, replayed, out-of-scope, and bypass attempts;
- external/manual broker activity and reconciliation.

Metrics SHALL include current policy and graph generations, active principals and roles, pending approval age, quorum satisfaction and invalidation counts, effective-principal collapses, conflict denials, delegation age, authentication failures, stale-session denials, HALT authentication-to-commit and commit-to-egress latency, break-glass use, compromised-principal scope, and approval-replay attempts.

Critical alerts include one effective principal counted twice, self-approval chain, unbound or replayed approval, quorum reduction, break-glass expansion attempt, direct broker route, approval-driven capacity release, HALT path failure, stale approval consumed, compromised approver still active, or automatic re-arm.

Evidence and notification do not substitute for enforcement. ADR-002-016 governs immutable custody, causal completeness, gap containment, redaction, and isolated replay of these records; the Evidence Store and replay system receive no human-approval, HALT, capacity, or transmission authority.

---

## 23. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Two accounts resolve to one natural person | count once; deny quorum if insufficient |
| Effective-control graph incomplete or stale | deny authority increase; preserve HALT |
| Shared or generic approval credential | reject as Human Safety Principal |
| Approver role or scope changed after attestation | invalidate attestation and affected set |
| Evidence or requested scope changed | invalidate request/set; require fresh review |
| Approval service or identity provider unavailable | no authority increase or re-arm; HALT remains available |
| Stale or replayed Approval Set | reject; retain security evidence |
| Approval consumed twice | reject duplicate; investigate authority and state |
| Break-glass tries to arm or transmit | reject, HALT affected scope, investigate bypass |
| Human HALT cannot reach authoritative plane | latch denial at receiving egress; remain restrictive and reconcile later |
| Human HALT result ambiguous | treat as possibly applied; no re-arm until reconciled |
| Emergency protective request lacks capacity/proof | deny transmission; do not reinterpret priority as reserve |
| Approver or authenticator compromised | revoke, restrict, fence, reconcile, fresh governance |
| Approval expires with live orders open | future issuance denied; orders/effects/capacity remain |
| Manual broker action detected | external/unattributed; conservative capacity and reconciliation |
| Workflow recovery finds old approvals | invalidate unless every current binding is positively revalidated; never auto re-arm |

---

## 24. Rejected Alternatives

### 24.1 Two Accounts Equal Two People

Rejected because one person or administrator may control both identities.

### 24.2 Shared Team or Emergency Account

Rejected as approval identity because it is not attributable to one natural person and defeats quorum counting.

### 24.3 Ticket, Chat, or Meeting Approval

Rejected unless converted into an authenticated attestation bound to the exact request and policy.

### 24.4 Administrator May Bypass Quorum During Outage

Rejected because approval-service unavailability must reduce authority, not independence.

### 24.5 Break Glass Means Full Operator Access

Rejected because a general credential, broker route, or live arming path turns compromise into economic authority.

### 24.6 Human “Close” Is Automatically Protective

Rejected because label and intent do not prove aggregate risk reduction, capacity, broker state, or safe intermediate execution.

### 24.7 Approval Remains Valid After Context Change

Rejected because approval of one evidence and scope cannot authorize another.

### 24.8 Approval Recovery Re-arms Live

Rejected because identity health does not prove economic readiness or current authority.

### 24.9 Audit Detects Abuse After the Fact

Rejected because attribution and replay do not prevent an unsafe authority path.

### 24.10 Quorum Can Waive Critical Invariants

Rejected because human acceptance cannot override RFC-000/RFC-001, the Hard Safety Envelope, RCL, UNKNOWN, or final-egress requirements.

---

## 25. Consequences

### 25.1 Positive

- human approvals become exact safety artifacts rather than informal organizational signals;
- dual control counts distinct effective natural persons;
- self-approval, shared-account, delegation, roster, and workflow-admin bypasses are explicit;
- HALT remains fast and independent while permissive authority remains quorum-gated;
- break-glass cannot become a broker, capacity, or re-arm bypass;
- changed context, expiry, revocation, compromise, and recovery fail closed;
- approval evidence is reconstructable and independently reviewable;
- external manual broker authority remains conservatively visible.

### 25.2 Negative

- identity, role, device, recovery, and administrative control paths become safety-critical;
- authority increases may wait for unavailable independent humans;
- approval requests are invalidated by material context changes;
- identity-provider or workflow compromise may suspend broad live scope;
- emergency credentials require strong custody, rotation, and failure-domain isolation;
- break-glass cannot solve broker or capacity problems by bypass;
- organizations must maintain effective-principal and conflict data, not only group membership.

These costs are accepted because nominal dual control without effective independence creates unilateral live authority.

---

## 26. Acceptance Cases

The following cases are mandatory and map one-to-one to `HAG-EV-001` through `HAG-EV-012`. Written cases are not completed evidence.

| ID | Required demonstration |
|---|---|
| `HAG-AC-001` | Multiple accounts, credentials, devices, sessions, aliases, delegated identities, and recovery paths controlled by one person count as one effective principal |
| `HAG-AC-002` | Approval binds exact request, evidence, artifacts, generations, scope, reason, validity, policy, and maximum authority; any material change invalidates it |
| `HAG-AC-003` | Author, implementer, validator, evidence owner, workflow/identity administrator, approver, deployer, credential/route administrator, and live armer cannot form a unilateral self-approval chain |
| `HAG-AC-004` | Stale, expired, revoked, duplicated, consumed, superseded, broader, policy-mismatched, or replayed attestations and Approval Sets cannot create authority |
| `HAG-AC-005` | One authenticated authorized human can HALT through an independent restrictive path during strategy, approval-service, and ordinary control-plane failures, and every egress denies within approved bounds |
| `HAG-AC-006` | Break-glass can only HALT, deny, narrow, or request separately authorized containment and cannot expand, mutate capacity, directly transmit, auto-revert, or re-arm |
| `HAG-AC-007` | Human-labelled cancel, close, hedge, replace, or emergency action cannot bypass protective classification, exclusive capacity, UNKNOWN, Final Quantity Proof, or egress rules |
| `HAG-AC-008` | Delegation, roster change, authenticator recovery, identity-provider migration, and unavailable personnel cannot multiply authority, reduce quorum, or transfer prior approvals automatically |
| `HAG-AC-009` | Compromised principal, device, session, workflow, signer, roster, or recovery path revokes affected pending authority, restricts scope, preserves economic effects, and requires fresh governance |
| `HAG-AC-010` | Risk-increasing re-arm requires at least two distinct effective humans, consumes an exact Approval Set once, restores only the approved narrow scope, and cannot waive any safety gate |
| `HAG-AC-011` | Approval expiry, revocation, outage, recovery, or ambiguous HALT cannot cancel orders, release capacity, resolve UNKNOWN, prove non-acceptance/final quantity, or automatically re-arm |
| `HAG-AC-012` | Independent replay reconstructs identity, effective control, policy, evidence review, approval, denial, HALT, consumption, compromise, external activity, and re-arm without treating evidence as authority |

---

## 27. Requirements Traceability

| Requirement | ADR-002-015 allocation |
|---|---|
| SAFE-010, SAFE-011, SAFE-034 | Approval uses independently validated exact inputs but cannot bypass preventive authorization (§§10–12, 17) |
| SAFE-035 | Sessions, approvals, delegations, and emergency authenticators use Trustworthy Time and fail closed on uncertainty (§§13–14, 20) |
| SAFE-041 | Safety authority remains independent from proposer, strategy, approval, and transmission paths (§§7, 12, 15) |
| SAFE-042 | One authenticated human retains independent monotonic HALT and bounded containment-request authority (§§15–16) |
| SAFE-045, SAFE-046, SAFE-047 | Approval and Live Authorization bind exact environment, scope, software, profile, and interval; recovery does not arm (§§10, 17–20) |
| SAFE-048 | Partitions block permissive authority while locally verifiable restrictive HALT remains available (§20) |
| SAFE-050 | Human policy, roles, approval artifacts, delegation, and changes are immutable, authenticated, attributable, and independently governed (§§8–13) |
| SAFE-051, SAFE-052 | Complete human decision, denial, command, compromise, and recovery lineage supports evidence and replay without replacing enforcement (§22) |

---

## 28. Open Implementation Questions

The architecture is selected. The following product, organization, policy, and parameter choices remain open while Proposed:

1. Which identity provider, natural-person proof, phishing-resistant authenticator, device attestation, and recovery mechanisms are approved?
2. Which system constructs and protects the Effective Principal Graph across human, service, workflow, repository, signer, roster, and recovery control paths?
3. What Human Authority Policy quorum and mandatory-role matrix applies to envelope, profile, residual-risk, deployment, credential/route, recovery, and re-arm decisions?
4. Which conflicts require organizational separation in addition to distinct effective natural persons?
5. Which approval workflow and canonical attestation/signature formats provide exact context binding and single-use consumption?
6. Which ADR-002-012 namespace orders Approval Set consumption without merging approval, Live Authorization, capacity, and egress authority?
7. What delegation, temporary-role, employment-change, leave, and succession policies are approved?
8. Which pre-provisioned Human HALT authenticators and failure domains remain available when online identity and control planes fail?
9. How is direct restrictive egress latching authenticated, bounded, replay-protected, reconciled, and revoked?
10. Which human-requested containment actions are pre-defined, and how are external/manual broker actions governed?
11. What compromise scope and previously consumed approvals require immediate suspension versus narrower containment?
12. What `B_human_halt_to_commit`, session-age, approval-age, delegation-age, notification, and review bounds are approved?
13. Which ADR-002-016 durable ordinary and emergency evidence paths, source identities, integrity anchors, gap detectors, protected raw tier, and replay isolation preserve human and break-glass history without delaying restrictive HALT behind the ordinary pipeline?
14. How does the approval verifier bind the ADR-002-017 Recovery Generation, package, readiness decision, dependency-complete scope, and invalidation set without letting a human force `READY`?
15. How does the verifier independently validate and bind ADR-002-018 Critical Input Policy, source continuity, exact Decision Context Capsule, common-mode analysis, age, and invalidation without relying solely on proposer-produced values?

Unresolved questions reduce authority or keep the affected scope non-live. They SHALL NOT lower quorum, expand break-glass, or create a permissive default.

---

## 29. Approval Gate

ADR-002-015 SHALL remain **Proposed** until all of the following are complete. Human HALT restrictive ingress and every final-egress latch SHALL conform to ADR-002-024 deny-first, monotonic, non-revival, and claim/fence ordering without granting the human workflow capacity or transmission authority:

1. Human Authority Policy, Effective Principal Graph, Approval Request, Approval Attestation, Approval Set, delegation, and Human HALT schemas are approved;
2. natural-person identity, phishing-resistant authentication, device/session, recovery, roster, and effective-control mechanisms are implemented and security-reviewed;
3. approval quorum, role, conflict, scope, delegation, expiry, revocation, and single-use consumption policies are approved for every authority-increasing decision;
4. one-human restrictive HALT remains independently available and reaches every final egress within approved bounds without exposing permissive authority;
5. break-glass and human containment requests cannot mutate capacity, classify themselves as protective, bypass final egress, directly reach the broker, auto-revert, or re-arm;
6. ADR-002-007 re-arm, ADR-002-012 ordering, ADR-002-013 egress, and ADR-002-014 configuration governance enforce exact current approval artifacts without collapsing authority;
7. compromise, delegation, roster, workflow, identity-provider, authenticator, rollback, partition, and recovery behavior is security-reviewed;
8. `HAG-EV-001` through `HAG-EV-012` and applicable SA, REARM, TIME, FD, RCLP, EGRESS, SPG, BC, and cross-system evidence pass at required levels and receive independent review;
9. ADR-002-016 ordinary and emergency evidence durability, human-record causal completeness, gap handling, retention, redaction, and replay isolation are implemented and their applicable ERI evidence passes;
10. ADR-002-017 exact current Recovery Generation, package, readiness decision, dependency scope, and invalidation set are verified before approval consumption, and applicable SBR evidence passes;
11. ADR-002-018 exact Decision Context Capsule, independent Critical Input validation, common-mode analysis, and current invalidation state are verified before approval consumption, and applicable CII evidence passes;
12. ADR-002-019 exact Venue Constraint Snapshot and Order Admissibility Decision, independent constraint validation, current generation, and invalidation state are verified before approval consumption, and applicable VTG evidence passes;
13. ADR-002-020 exact Intent proposal, Authorized Construction Envelope, candidate Canonical Broker Command, construction policy/generation, and non-authorizing semantics are bound before approval consumption, and applicable IOC evidence passes;
14. `B_human_halt_to_commit`, `B_halt_to_egress`, and applicable session, approval, delegation, revocation, evidence, identity-fence, recovery-barrier, Critical Input, venue-constraint, and conformance invalidation, context/decision/command/proof-age, and readiness-age bounds are approved and measured;
15. no unresolved shared-account, self-approval, false-input-independence, forced-readiness, effective-principal, direct broker, or automatic re-arm bypass remains;
16. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Authorship, policy drafting, two account names, ticket approval, successful authentication, audit logs, written cases, or document review do not satisfy this gate. This ADR does not authorize acceptance, restricted-live operation, production operation, direct human capacity mutation, direct broker transmission, or automatic re-arm.
