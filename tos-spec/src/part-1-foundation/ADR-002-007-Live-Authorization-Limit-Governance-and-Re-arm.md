# ADR-002-007 — Live Authorization, Limit Governance, and Re-arm

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Default non-live state, Hard Safety Envelope and Runtime Safety Profile governance, live-scope authorization, continuous validity, suspension and revocation, recovery readiness, human dual control, partial re-arm, and final egress enforcement
- **Supersedes:** None
- **Amends:** RFC-002 §19 Safety Configuration Architecture and §23 Recovery and Re-Arming
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-022, SAFE-024, SAFE-025, SAFE-035, SAFE-041, SAFE-042, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-006; ADR-002-008 Trustworthy Time Architecture

---

## 1. Decision

The default operational state of every TOS deployment SHALL be non-live.

Risk-increasing live operation requires the continuous intersection of five independently governed layers:

```text
Hard Safety Envelope
    ∩ Validated Runtime Safety Profile
    ∩ Current Live Authorization
    ∩ Current Safety Authority / Transmission Capability
    ∩ Current reconciled economic and operational state
```

No lower layer may expand a higher layer. The most restrictive applicable scope and limit always governs.

The system SHALL distinguish:

1. **Recovery Readiness Decision** — evidence that recovery prerequisites have been evaluated; it grants no trading authority;
2. **Re-arm Approval** — explicit separated human approval to request a defined live scope;
3. **Live Authorization** — a new, authenticated, revocable, time-bounded authorization issued for that exact scope and current epoch;
4. **Per-Action Transmission Capability** — the final single-use or bounded-use authority checked at broker egress.

No health signal, timeout, restart, failover, reconciliation-complete event, configuration reload, deployment success, or restored dependency may automatically create any of these permissive artifacts.

Re-arm always issues a new Live Authorization and new capabilities. A revoked, expired, suspended, superseded, or stale authorization SHALL NOT be revived.

UNKNOWN broker, order, exposure, reconciliation, time, configuration, or fencing state consumes conservative capacity and blocks re-arm to any scope that permits new risk.

---

## 2. Context

Live operation can become unsafe even when every component is individually healthy. Examples include:

- an authorization scoped to the wrong account or software version;
- a Runtime Safety Profile valid in syntax but outside the Hard Safety Envelope;
- a partially applied limit update;
- an old authorization surviving a safety halt or epoch change;
- a rollback restoring broader historical limits;
- reconciliation completing while an UNKNOWN order remains capacity-consuming;
- clock recovery making an old token appear valid;
- a single operator both enlarging limits and arming live scope;
- a broker-capability downgrade not invalidating the active live scope;
- a deployment or credential change silently inheriting authorization.

Safe recovery therefore requires explicit separation between readiness, approval, authorization, and per-action enforcement, with continuous invalidation when any prerequisite changes.

---

## 3. Decision Drivers

1. Non-live is the default and failure state.
2. Live scope must be explicit, narrow, current, attributable, and revocable.
3. Safety limits must not be expanded by runtime strategy or live-arming identities.
4. Configuration activation must be atomic and semantically validated.
5. Reconciliation or service recovery must never auto-re-arm.
6. Stale epochs, versions, identities, and approvals must be fenced at final egress.
7. Re-arm must permit narrower scope without requiring restoration of prior authority.
8. Every decision and denial must produce durable evidence.

---

## 4. Governed Artifacts

### 4.1 Hard Safety Envelope

The independently governed maximum authority the system can ever grant.

It SHALL be immutable by normal trading identities, versioned, authenticated, and activated through its own governance process.

### 4.2 Runtime Safety Profile

A versioned set of runtime limits and constraints strictly inside the Hard Safety Envelope.

It SHALL be semantically validated and atomically activated by the Safety Profile Validator. Syntax validity alone is insufficient.

### 4.3 Recovery Evidence Package

The immutable, generation-bound manifest defined by ADR-002-017. It records the exact Recovery Session, Recovery Scope, Inventory Cut, obligations, uncertainty, and readiness or denial evaluated by the Recovery Coordinator, but grants no authority.

### 4.4 Re-arm Approval Record

The separated human approvals, requested scope, reason, residual-risk acknowledgements, and evidence-package identity used to authorize issuance of a new Live Authorization.

### 4.5 Live Authorization

An authenticated, revocable, time-bounded authorization for one exact live scope under one current Authority Epoch.

### 4.6 Transmission Capability

The per-action authorization enforced by the Broker Adapter / Egress Gateway under RFC-002, ADR-002-002, and ADR-002-003.

### 4.7 Currentness Sequencer

The linearizable ordering interface through which the Safety Authority records normal Transmission Capability issuance and restrictive generation transitions for a Safety Cell. It is an implementation function of the existing Safety Authority boundary, not a separate policy authority. It SHALL NOT grant Live Authorization, invent scope, mutate capacity, or hold broker transmission credentials.

Possession of one artifact SHALL NOT imply possession of another.

---

## 5. Authority and Separation of Duties

| Action | Required authority | Prohibited combination |
|---|---|---|
| Govern Hard Safety Envelope | Independent envelope governance | Runtime trading identity or sole live armer |
| Author Runtime Safety Profile | Authorized profile author | Strategy modifying its own live limits |
| Approve authority-increasing profile change | Independent limit approver | Sole live armer for the enlarged scope |
| Validate and activate profile | Safety Profile Validator | Expanding the Hard Safety Envelope |
| Assemble recovery readiness | Recovery Coordinator | Issuing Live Authorization or approving itself |
| Approve re-arm request | Authenticated separated human control | One principal unilaterally enlarging and arming scope |
| Issue Live Authorization | Live Authorization Service | Changing limits or bypassing readiness evidence |
| Issue current Safety Authority capability | Safety Authority | Holding broker transmission credentials |
| Order capability issuance and restrictive generations | Currentness Sequencer within the Safety Authority boundary | Independent policy grant, capacity mutation, or broker transmission |
| Enforce transmission | Broker Adapter / Egress Gateway | Inventing missing scope or accepting stale versions |
| Halt or reduce scope | Safety Authority or authenticated emergency path | Automatically restoring authority later |

No service account shared across these roles may defeat the intended separation.

---

## 6. Limit Governance

### 6.1 Layering Invariant

For every governed dimension:

```text
per-action authority
    <= Live Authorization
    <= Runtime Safety Profile
    <= Hard Safety Envelope
```

The comparison SHALL include account, strategy, instrument, venue, order type, action class, quantity, notional, risk vector, margin, concentration, rate, session, and time scope as applicable.

### 6.2 Authority-Increasing Change

A change is authority increasing if any credible interpretation permits an action, scope, limit, duration, identity, broker capability, or risk vector that was previously denied or more constrained.

Authority-increasing changes require:

1. a new immutable profile or envelope version;
2. semantic validation against units, multipliers, currencies, scope, plausibility, and the Hard Safety Envelope;
3. independent approval;
4. atomic activation;
5. new Recovery Coordinator evaluation where the live safety basis changes;
6. a new Live Authorization for the enlarged scope;
7. separated human re-arm approval.

### 6.3 Authority-Reducing Change

A valid restrictive change may take effect immediately and monotonically. Existing orders and positions remain economic facts and SHALL be reconciled and contained; reduction of future authority does not erase them.

### 6.4 Atomic Activation

A profile or envelope version is either completely active for its defined scope or not active. Partial distribution, mixed versions, missing values, incompatible units, or unverifiable activation state SHALL fail closed.

### 6.5 Rollback

A rollback is not inherently safer. Restoring an older version that is broader, incompatible with current software, or outside the current envelope is authority increasing and requires the full approval path.

### 6.6 Expiry

Expired or time-unverifiable configuration cannot authorize new risk. Expiry does not release capacity or economic effect.

---

## 7. Live Authorization Claims

Every Live Authorization SHALL bind at least:

- authorization identity and version;
- issuer identity and approval-record identity;
- environment and deployment identity;
- Authority Domain and current Safety Authority epoch;
- account and portfolio scope;
- strategy set;
- instrument or instrument-class set;
- broker, API, market, venue, session, order-type, and action-class scope;
- maximum quantity, notional, risk-vector, margin, concentration, and rate constraints;
- Hard Safety Envelope version;
- Runtime Safety Profile version;
- Broker Capability Profile version and conformance class;
- software artifact digest, configuration digest, and deployment provenance;
- credential and broker-egress identity;
- Recovery Evidence Package identity and evidence generation;
- Critical Input Policy, Context Generation, Critical Input Snapshot, and exact Decision Context Capsule identities and digests under ADR-002-018;
- Venue Constraint Policy, Constraint Generation, Venue Constraint Snapshot, and exact Order Admissibility Decision identities and digests under ADR-002-019;
- Trustworthy Time generation and validity rule;
- issue identity, issue sequence, activation condition, and maximum validity;
- revocation generation;
- residual-risk approvals and restricted-scope conditions;
- cryptographic integrity evidence.

Missing, empty, wildcarded, defaulted, stale, or conflicting Critical claims SHALL be denial.

Live Authorization SHALL NOT contain implicit “all accounts,” “all instruments,” “latest version,” or equivalent open-ended scope.

Renewal, extension, or scope expansion SHALL be treated as issuance of a new authorization under the full current gate. Automatic rollover is prohibited.

---

## 8. Live Authorization State Model

The authorization artifact SHALL use an explicit lifecycle separate from the trading operating mode:

```text
REQUESTED
    -> VALIDATED
    -> APPROVED
    -> ISSUED
    -> ACTIVE

{REQUESTED, VALIDATED, APPROVED} -> DENIED
{ISSUED, ACTIVE}                -> SUSPENDED
{ISSUED, ACTIVE}                -> REVOKED
{ISSUED, ACTIVE}                -> EXPIRED
{ISSUED, ACTIVE}                -> SUPERSEDED
```

### 8.1 `ACTIVE`

`ACTIVE` means every continuous validity condition currently passes. It is not inferred from the artifact merely being issued.

### 8.2 `SUSPENDED`

Suspension is restrictive. It denies new risk while preserving the artifact and evidence for investigation. Suspension SHALL NOT automatically clear.

### 8.3 Non-Permissive Authorization States

`DENIED`, `SUSPENDED`, `REVOKED`, `EXPIRED`, and `SUPERSEDED` authorizations cannot return to `ACTIVE`. Re-arm requires a new workflow and issues a new authorization identity.

---

## 9. Continuous Validity

Live Authorization is valid for new risk only while all of the following remain true:

- Safety Authority epoch and currentness are valid;
- Trustworthy Time is `TRUSTED` under ADR-002-008;
- authorization validity and snapshot age remain positively established;
- account-wide state required for the scope remains reconciled;
- the ADR-002-017 Recovery Generation, barrier state, Recovery Evidence Package, and Recovery Readiness Decision remain current and valid for the exact scope;
- the ADR-002-018 Critical Input Policy, Context Generation, source continuity, exact Decision Context Capsule, age, and invalidation state remain current and valid for the exact scope;
- the ADR-002-019 Venue Constraint Policy, Constraint Generation, exact Snapshot and Order Admissibility Decision, session/tradability/account/broker scope, age, and invalidation state remain current and valid for the exact order;
- no unresolved UNKNOWN or unattributed activity affects the scope;
- Risk Capacity Ledger and protective capacity remain consistent;
- Hard Safety Envelope and Runtime Safety Profile versions match and remain valid;
- Broker Capability Profile remains current and sufficient;
- deployment, software, configuration, identity, credential, and egress digests match;
- protective coverage and venue/session prerequisites remain valid;
- no dominating `CONTAINED` or `HALTED` state exists;
- no Critical alert or invalidation event blocks the scope.

Loss of any required predicate SHALL suspend or revoke new-risk authority within the approved containment bound.

Continuous validity is checked by the Live Authorization Service and independently at final broker egress. A cached `ACTIVE` state is not sufficient proof.

Every restrictive authorization transition SHALL advance an authenticated, monotonically ordered revocation or restriction generation. The authoritative transition SHALL reach every final egress within `B_revocation_to_egress`. At egress, the age of any cached normal capability or currentness proof SHALL be no greater than `MAX_normal_capability_age` and SHALL also remain within the artifact's own validity interval. If the current accepted generation cannot be positively established, the action is denied.

`B_risk_increase_revoke` governs detection-to-authoritative-revocation behavior; `B_revocation_to_egress` governs authoritative-revocation-to-egress-denial behavior. Neither bound may be hidden inside an unmeasured cache TTL or retry interval.

### 9.1 Selected Fenced Egress Currentness Protocol

This ADR selects a **fenced single-use capability protocol** for normal risk-relevant transmission. The protocol is an architectural requirement; its storage, consensus, transport, and cryptographic implementation remain subject to approval and evidence.

For a normal risk-relevant action, the Safety Authority SHALL issue one authenticated Transmission Capability through the Currentness Sequencer only after the sequencer has ordered the issuance against the current restrictive generation vector and positively verified the referenced Risk Capacity Ledger commitment. The Currentness Sequencer does not create, mutate, transfer, or release capacity. The Risk Capacity Ledger remains the sole capacity mutation and serialization authority.

The issuance decision and every restrictive transition SHALL be serialized in one linearizable ordering domain for the affected Safety Cell. The concrete consensus substrate may differ from the Risk Capacity Ledger substrate only if their coupling prevents capability issuance against stale or uncommitted capacity and is proven under partition and failover. Redis cache state, eventual event delivery, process-local leader belief, or a broker-reachable heartbeat alone cannot provide this ordering.

### 9.2 Single-Use Transmission Capability

Every normal Transmission Capability SHALL be single-use and bind at least:

- capability identity, nonce, issue sequence, and action class;
- exact intent lineage and transmission-attempt identity;
- exact environment, Safety Cell, account, portfolio, broker, venue, session, instrument, side, order type, quantity, price constraints, and worst-case economic effect;
- exact Broker Adapter / Egress Gateway, deployment, workload, credential, software, and configuration identities;
- current writer epoch, Safety Authority epoch, Live Authorization identity, revocation generation, HALT generation, Time Health generation, and profile generations;
- current Recovery Generation and exact Recovery Evidence Package and Recovery Readiness Decision identities;
- the exact active Capacity Commitment or valid protective-capacity consumption proof;
- consumer-verifiable issue and expiry evidence whose age is bounded by `MAX_normal_capability_age`;
- cryptographic integrity and issuer identity.

A retry, replacement, scope change, credential change, route change, or economic-effect change requires a new transmission-attempt identity and a new capability. Missing broker ACK does not permit reuse or blind retry. It creates or preserves potentially-live `UNKNOWN` state and conservative capacity under ADR-002-002, ADR-002-004, and ADR-002-005.

### 9.3 Egress Currentness Session and Monotonic Deny Latch

Each approved final egress SHALL maintain a mutually authenticated currentness session with the Currentness Sequencer. The session carries the highest accepted restrictive generation vector and a short maximum age measured from a consumer-local monotonic receipt anchor. Issuer and consumer monotonic values SHALL NOT be directly compared.

The session is a bounded proof, not an allow cache. Loss, expiry, generation conflict, failed authentication, local suspension beyond the approved bound, or inability to renew before maximum age SHALL set a monotonic deny latch for the affected scope before any later normal broker send. Authenticated restrictive pushes MAY set the latch earlier, but absence of a push is never proof of permission. Separately pre-authorized degraded protective behavior follows §9.5 and cannot inherit normal authority from this exception.

The deny latch SHALL NOT clear because connectivity, time, Redis, process health, or the sequencer recovers. Clearing it requires a newer authenticated currentness generation, reconstruction of every prerequisite, and fresh capability issuance; if the Live Authorization became `SUSPENDED`, `REVOKED`, `EXPIRED`, or `SUPERSEDED`, ADR-002-007 re-arm governance requires a new Live Authorization. Recovery alone never re-arms.

### 9.4 Fenced Claim-to-Send Boundary

The Egress Gateway SHALL be the only holder of a usable live order credential and broker-order route. Immediately before transmitting the first broker-directed byte it SHALL, within one egress serialization boundary:

1. validate the complete capability and currentness-session generation vector;
2. check the local monotonic deny latch and the latest locally accepted restrictive generation;
3. durably claim the capability nonce exactly once and append `SEND_STARTED` with the same generation vector, capacity identity, attempt identity, and broker-request identity;
4. begin the broker socket write within `B_capability_claim_to_send` without an intervening unfenced queue, proxy, credential holder, or retry layer.

Under ADR-002-012 §12, the durable claim and `SEND_STARTED` are one quorum-committed `ClaimCapabilityAndMarkSendStarted` Safety Commit Log transition and produce consumer-verifiable Commit Proof before the broker write. A host-local journal, local database transaction, or evidence append cannot satisfy this claim.

If durable claim, evidence persistence, currentness, or local ordering is unavailable or ambiguous, no send is permitted. A crash or ambiguity after durable `SEND_STARTED` and before Final Quantity Proof is treated as potentially transmitted: the attempt remains `UNKNOWN`, its worst-case economic effect remains capacity-covered, and the capability is never reusable. Capability expiry or authority expiry after `SEND_STARTED` does not expire economic effect.

### 9.5 Restrictive Races and Protective Exception

Revocation or HALT commit SHALL stop issuance of later normal capabilities. An already issued capability can race a restrictive transition only inside the approved `B_revocation_to_egress` or `B_halt_to_egress`, `MAX_normal_capability_age`, and `B_capability_claim_to_send` bounds. Once the egress accepts the restrictive generation or its bounded proof expires, the deny latch dominates. Any send whose ordering cannot be proven remains potentially live and capacity-covered; audit classification does not convert it into a denied economic effect.

Degraded protective operation does not use normal-risk issuance during partition. It follows ADR-002-001 and ADR-002-003: an exclusive pre-issued protective lease may authorize only bounded, non-expanding, single-use protective capabilities from its monotonic local budget. The same nonce claim, `SEND_STARTED`, identity binding, egress confinement, and conservative ambiguity rules still apply. Priority is not reserved protective capacity.

---

## 10. Invalidation and Revocation Triggers

At minimum, new-risk authority SHALL be suspended or revoked upon:

- Safety Authority epoch change, loss, or unverifiability;
- Trustworthy Time degradation outside normal-live requirements;
- authorization or profile expiry;
- reconciliation loss, evidence conflict, or UNKNOWN order/exposure;
- unattributed external activity;
- Risk Capacity Ledger inconsistency;
- Hard Safety Envelope, Runtime Safety Profile, or Broker Capability Profile change;
- broker capability contradiction or scope downgrade;
- software, configuration, deployment, workload identity, credential, network route, or egress change;
- account, strategy, instrument, venue, session, or order-type scope change;
- protective coverage failure;
- Critical safety alert, security incident, or operator halt;
- inability to prove current fencing of stale writers or authority.

Revocation of future authority does not cancel orders, release capacity, or expire economic effect. Those actions follow their own safety-controlled lifecycles.

---

## 11. Recovery Readiness Decision

The Recovery Coordinator SHALL produce an immutable decision bound to one evidence generation and requested re-arm scope.

The package SHALL include at least:

- current Safety Authority epoch and stale-fence evidence;
- ADR-002-008 Time Health Snapshot and stabilization evidence;
- all five ADR-002-005 state dimensions for the requested scope;
- ADR-002-006 per-field reconciliation confidence and conservative bounds;
- open orders, attempts, fills, positions, cash, margin, and collateral;
- Risk Capacity Ledger commitments, quarantine, trapped exposure, and protective pools;
- external, unattributed, and recognized non-trade activity;
- protective-order coverage and Protection Gaps;
- Hard Safety Envelope, Runtime Safety Profile, Broker Capability Profile, and verification-profile versions;
- software, configuration, deployment, identity, credential, route, and egress digests;
- active alerts, exceptions, residual risks, and their approvals;
- requested live scope and the narrower safe scope, if different;
- decision identity, issue generation, maximum age, and invalidation conditions.

The decision is `READY`, `READY_RESTRICTED`, or `NOT_READY`.

`READY_RESTRICTED` may authorize only a scope whose safety is proven. It SHALL NOT turn unresolved UNKNOWN state into permission for new risk. A recovery-only scope may remain available for reconciliation or approved protective action while new risk stays blocked.

Any material evidence or version change after decision creation invalidates the readiness decision.

Recovery readiness SHALL NOT infer non-acceptance from a missing broker ACK or terminal quantity from a cancellation ACK. Unresolved broker acceptance or fill state remains `UNKNOWN`, continues to consume conservative capacity, and blocks risk-increasing re-arm until Final Quantity Proof or the applicable stronger proof rule is satisfied.

The Recovery Coordinator, Live Authorization Service, and human approvers SHALL NOT mutate or release capacity. The Risk Capacity Ledger remains the sole capacity serialization and mutation authority. Broker priority or rate-limit preference is not reserved protective capacity and SHALL NOT be counted as recovery coverage.

---

## 12. Re-arm Workflow

Re-arm SHALL execute in this order:

1. remain `NON_LIVE`, `HALTED`, `CONTAINED`, or `RECOVERY`; deny new risk;
2. establish the current Safety Authority epoch and fence stale epochs and writers;
3. establish a new `TRUSTED` time generation under ADR-002-008;
4. reconcile account-wide orders, attempts, fills, positions, cash, margin, collateral, and non-trade changes;
5. resolve UNKNOWN and unattributed activity for every risk-increasing scope;
6. verify Risk Capacity Ledger consistency and proof-gated release behavior;
7. reconcile protective leases, protective orders, and coverage;
8. validate the Hard Safety Envelope and atomically active Runtime Safety Profile;
9. validate the Broker Capability Profile and supported live conformance class;
10. verify software, configuration, deployment, identity, credential, network, and final-egress confinement;
11. verify no blocking Critical alert or unapproved residual risk remains;
12. under ADR-002-017, have the current fenced Recovery Coordinator issue a current readiness decision bound to the exact Recovery Generation, dependency-complete scope, Inventory Cut, obligations, and immutable Recovery Evidence Package;
13. construct and independently validate a fresh ADR-002-018 Decision Context Capsule under current source continuity and bind it to the requested scope;
14. obtain explicit separated human approvals bound to that package, Capsule, and scope;
15. have the Live Authorization Service issue a new Live Authorization under the current epoch;
16. distribute and confirm the authorization and context currentness at final egress without bypass;
17. transition only the authorized scope to its approved live mode;
18. continue continuous validity monitoring.

Failure or uncertainty at any step leaves the scope non-live or more restricted. A later step SHALL NOT compensate for a failed earlier step.

---

## 13. Human Dual Control

Re-arm approval SHALL require authenticated human identities with roles defined by policy.

At minimum:

- every risk-increasing re-arm requires approval by at least two distinct authenticated human principals under the approved quorum policy;
- the principal who approves an authority-increasing limit change SHALL NOT be the sole principal who arms that enlarged scope;
- the Recovery Coordinator, Live Authorization Service, and implementation author SHALL NOT act as the independent human reviewer of their own evidence;
- approvals SHALL be bound to the exact evidence package, versions, requested scope, reason, and expiry;
- changed evidence or scope invalidates prior approvals;
- emergency halt authority SHALL remain broader and easier to invoke than re-arm authority.

Operator convenience, shared credentials, generic team accounts, or chat approval without authenticated binding are insufficient.

---

## 14. Partial and Staged Re-arm

Re-arm SHOULD restore the smallest proven scope.

The system MAY re-arm one account, strategy, instrument set, broker conformance class, action class, or capacity band while others remain halted.

Partial re-arm SHALL:

- use a distinct Live Authorization identity and scope;
- reserve capacity independently;
- prevent fallback to a broader prior scope;
- retain unresolved scopes in `RECOVERY`, `CONTAINED`, or `HALTED`;
- define promotion gates for any later expansion;
- require a new authorization for every authority increase.

Successful operation of a narrow scope is evidence for review, not automatic authorization for expansion.

---

## 15. Startup, Restart, Failover, and Deployment

Cold start, warm restart, failover, rollback, scaling, or deployment SHALL default to non-live.

Live Authorization SHALL be bound to the approved software and deployment identity. A replacement instance SHALL NOT inherit authority merely because it uses the same service name, account, configuration path, or credential.

After restart or failover:

- prior potentially-live economic effects remain represented;
- stale epochs and instances are fenced;
- time and reconciliation gates are re-established;
- the Recovery Coordinator produces a new readiness decision where required;
- a new Live Authorization is issued before new risk.

Rolling deployment SHALL NOT temporarily create multiple egress paths or mixed safety versions.

ADR-002-009 governs the required deployment identity, hard fencing, Failure-Domain Allocation Matrix, and common-mode evidence for these claims.

---

## 16. Final Egress Enforcement

Before every risk-relevant live transmission, the Broker Adapter / Egress Gateway SHALL verify:

- current and unused Transmission Capability;
- current Safety Authority epoch and no dominating safer state;
- current Live Authorization identity, scope, state, and revocation generation;
- current `TRUSTED` Time Health Snapshot;
- matching Hard Safety Envelope, Runtime Safety Profile, and Broker Capability Profile versions;
- matching account, strategy, instrument, venue, session, order type, action class, quantity, and economic effect;
- matching software, deployment, workload, credential, and environment identity;
- active Capacity Commitment or valid protective consumption;
- absence of a blocking reconciliation, UNKNOWN, external-activity, or Critical-alert condition.

Any missing, stale, conflicting, unverifiable, or out-of-scope fact is denial before broker transmission.

The complete validation decision and the irreversible broker-send boundary SHALL be fenced against the same authority, revocation, and HALT generations accepted by that egress. If that egress accepted a restrictive generation before the send boundary, the transmission SHALL be denied. If their local race ordering cannot be positively established, the safer restrictive state wins and the transmission SHALL be denied. Every final egress SHALL accept the restrictive generation within the applicable propagation bound; a transmission occurring before local acceptance remains potentially live, capacity-covered, measured against that bound, and retained as evidence. A successful check followed by an unfenced queue, proxy, or credential holder is not final egress enforcement.

The fenced single-use capability protocol in §§9.1–9.5 is the required mechanism for this decision. A direct call to a broker client, adapter-private send method, retry queue, or alternate credential path outside that boundary is a bypass even if an upstream live-mode guard passed.

No internal control is sufficient if an identity can bypass this final gate and reach the broker directly.

ADR-002-009 governs the physical and logical isolation of this path. ADR-002-011 governs protective replacement at this gate, and ADR-002-010 governs any transmitted action required by a non-trade event.

---

## 17. Emergency Halt and Restriction

Authenticated emergency halt and authority-reducing actions MAY use broader paths than re-arm when they are monotonic and cannot enlarge economic authority.

HALT SHALL dominate outstanding permissive capabilities and Live Authorization. It does not mean blind cancel-all; protective ownership and aggregate-risk evaluation still govern order cancellation.

Acceptance of HALT SHALL advance a monotonic restrictive generation. Every final egress SHALL deny later risk-increasing transmissions within `B_halt_to_egress`; a transmission racing HALT SHALL be ordered at the fenced send boundary defined in §16. HALT may preserve separately authorized protective action, but it SHALL NOT preserve an ordinary permissive capability merely because that capability was checked earlier.

No halt acknowledgement, service recovery, or elapsed cooldown may schedule automatic re-arm.

---

## 18. Evidence, Metrics, and Alerts

The system SHALL retain:

- every envelope and profile version, validation, approval, activation, and rejection;
- every Recovery Evidence Package and readiness decision;
- every re-arm request, human approval, denial, and reason;
- every Live Authorization lifecycle transition;
- continuous-validity inputs and invalidation events;
- epoch, time-health, reconciliation, broker-profile, deployment, and egress evidence;
- every egress acceptance or denial with the evaluated artifact identities;
- all partial re-arm scopes and later expansion requests.

Metrics SHALL include active authorization count and scope, authorization age, current versions, suspended/revoked/expired counts, re-arm attempts and denials, readiness age, dual-control completion, egress version mismatch, and automatic-re-arm prevention events.

Critical alerts include live transmission without current authorization, stale authorization accepted, version mismatch accepted, single-principal authority increase and arm, auto-rearm attempt, or direct broker-egress bypass.

Audit and replay do not substitute for enforcement.

---

## 19. Failure Responses

| Failure | Required response |
|---|---|
| Missing or invalid Hard Safety Envelope | non-live; reject profile activation and new risk |
| Partial profile activation | fail closed; do not combine versions |
| Live Authorization service unavailable | no new authorization or renewal; if online currentness cannot be positively established, no new risk is permitted |
| Recovery evidence changes after approval | invalidate readiness and approvals; restart evaluation |
| UNKNOWN order or exposure | conservative capacity; block risk-increasing re-arm in affected scope |
| Time becomes degraded or untrusted | suspend normal-live authority; protective behavior follows ADR-002-001/008 |
| Broker capability downgrades | suspend unsupported scope; issue no broader fallback |
| Deployment or code digest changes | suspend authorization; require scoped re-evaluation |
| Operator halt races with transmission | order the race at each fenced send boundary; locally accepted HALT dominates later sends, all egress accept it within `B_halt_to_egress`, and any propagation-window send remains potentially live and capacity-covered |
| Old authorization replayed | reject by identity, epoch, revocation generation, version, and use semantics |
| Dual-control system unavailable | remain non-live; no single-principal bypass |

---

## 20. Alternatives Rejected

- **Environment variable or deployment flag means live.** Rejected because it lacks scope, governance, revocation, and evidence.
- **Health checks automatically re-arm.** Rejected because technical health does not prove economic state or operator intent.
- **Reuse the prior authorization after recovery.** Rejected because epochs, state, versions, and approvals may have changed.
- **Recovery Coordinator issues authorization.** Rejected because readiness and authority must remain separate.
- **One operator changes limits and arms live.** Rejected because it defeats separation of duties.
- **Apply profile fields independently.** Rejected because mixed versions can create unintended authority.
- **Rollback is always safer.** Rejected because older versions can be broader or incompatible.
- **UNKNOWN is acceptable when capacity is reserved.** Rejected for risk-increasing re-arm; reservation contains uncertainty but does not prove state.
- **Dashboard status is enforcement.** Rejected because documentation and observability do not prevent transmission.

---

## 21. Verification and Acceptance Criteria

ADR-002-007 SHALL remain Proposed until executed evidence demonstrates at least:

- **REARM-AC-001 — Default non-live:** startup, restart, failover, deployment, and rollback cannot create live authority.
- **REARM-AC-002 — Full gate:** removing any one re-arm prerequisite denies authorization.
- **REARM-AC-003 — No automatic re-arm:** health recovery, reconciliation completion, timeout, and leader election never arm live scope.
- **REARM-AC-004 — Fresh identity:** revoked, expired, suspended, superseded, or stale authorization cannot be revived or replayed.
- **REARM-AC-005 — Dual control:** one principal cannot both enlarge limits and arm the enlarged scope.
- **REARM-AC-006 — Atomic configuration:** partial and mixed-version profile activation fails closed.
- **REARM-AC-007 — UNKNOWN:** unresolved order, exposure, or external activity blocks risk-increasing re-arm while remaining conservatively capacity-covered.
- **REARM-AC-008 — Continuous invalidation:** loss of time, reconciliation, authority, broker capability, identity, or profile validity creates an authoritative restrictive generation and suspends new risk within `B_risk_increase_revoke` plus `B_revocation_to_egress`.
- **REARM-AC-009 — Partial re-arm:** only the explicitly narrower scope becomes active; broader prior scope remains denied.
- **REARM-AC-010 — Final egress:** stale, wrong-scope, wrong-version, over-age, wrong-generation, reused, post-latch, or bypassed authorization is rejected at the fenced capability-claim and irreversible-send boundary; any ambiguous post-claim attempt remains potentially live and capacity-covered.
- **REARM-AC-011 — Restrictive precedence:** HALT advances a restrictive generation, reaches all final egress within `B_halt_to_egress`, and dominates a racing permissive authorization without blindly cancelling required protection.
- **REARM-AC-012 — Evidence replay:** an independent reviewer can reconstruct every readiness, approval, authorization, invalidation, and egress decision.

These criteria map one-to-one to REARM-EV-001 through REARM-EV-012 and additionally to SA-EV-009, SA-EV-010, SA-EV-013, BC-EV-015, BC-EV-020, BC-EV-021, X-EV-007, X-EV-009, and X-EV-012. Registration is not execution; every applicable evidence item must pass at its required level before this ADR can be accepted.

A written case is not completed evidence.

---

## 22. Consequences

**Positive:** live authority is narrow, current, attributable, and continuously revocable; recovery cannot silently restore risk; limit changes are atomic and separated from arming; partial re-arm reduces blast radius; final egress enforces the complete chain.

**Negative:** recovery takes longer; operator workflow is heavier; configuration and deployment changes often require new authorization; unavailable dual control or evidence services reduce availability; narrow re-arm may leave profitable scope disabled.

These costs are accepted because live availability and opportunity are subordinate to capital preservation and operational safety.

---

## 23. Requirements Traceability

| Requirement | ADR-002-007 allocation |
|---|---|
| SAFE-003, SAFE-004, SAFE-050 | Runtime profiles remain inside the independently governed Hard Safety Envelope; invalid, partial, stale, or mixed activation fails closed (§4, §6) |
| SAFE-011 | Live limits and authority are independently checked and cannot be bypassed at final broker egress (§5, §16) |
| SAFE-013, SAFE-015 | Re-arm reads aggregate risk and exclusive commitments but cannot mutate capacity outside the Risk Capacity Ledger (§11–§12) |
| SAFE-021, SAFE-022, SAFE-024, SAFE-025 | Missing ACK, cancellation ambiguity, partial fills, external activity, and UNKNOWN state remain capacity-covered and block risk-increasing re-arm (§9–§12) |
| SAFE-035 | Live Authorization requires current `TRUSTED` time and is invalidated when that basis is lost (§7, §9–§12) |
| SAFE-041, SAFE-048 | Current Safety Authority and writer epochs are prerequisites and stale authority is rejected at final egress (§9–§12, §16) |
| SAFE-042 | Authenticated emergency halt is monotonic, dominates permissive authority, and never schedules re-arm (§17) |
| SAFE-044 | Recovery readiness is separate from approval and authority; start, resume, and recovery remain non-live until the complete gate passes (§11–§15) |
| SAFE-045, SAFE-046, SAFE-047 | Deployments default non-live; live scope is explicitly armed, identity-bound, narrow, and non-transferable (§1, §7, §14–§16) |
| SAFE-051, SAFE-052 | Limit changes, readiness, human approvals, authorization transitions, and egress decisions are retained for independent reconstruction (§18, §21) |

---

## 24. Open Implementation Questions

The following may remain open while Proposed but SHALL be resolved before acceptance:

1. Which conforming ADR-002-015 effective-principal, role, quorum, authentication, approval-expiry, consumption, delegation, and Human HALT mechanisms implement dual control?
2. Which ADR-002-017 Recovery Barrier Policy, ordered Recovery Generation and owner fence, dependency graph, obligation workflow, package signer, and readiness-verification mechanism provide current Recovery Evidence Packages without granting trading authority?
3. Which conforming ADR-002-012 consensus product and ADR-002-013 credential, route, principal, Quorum Commit Certificate, authenticated session, and hard-fence mechanisms implement the selected §§9.1–9.5 protocol while meeting `B_revocation_to_egress`, `B_halt_to_egress`, `MAX_normal_capability_age`, `B_capability_claim_to_send`, and `B_egress_hard_fence`?
4. Which ADR-002-018 Critical Input Policy, Context Generation, source-continuity, Capsule, invalidation, and active currentness mechanisms bind re-arm and final egress without a permissive cache?
5. What exact scope dimensions and risk vectors are supported by the first restricted-live profile?
6. Which canonical artifact, semantic validation, compatibility-manifest, approval, and ADR-002-012 ordering mechanisms implement ADR-002-014 atomic activation and rollback fencing across failure domains?
7. Which changes require full re-arm versus immediate scoped suspension and later re-evaluation?
8. What maximum readiness age, authorization duration, context age, and invalidation bounds are approved?
9. How are emergency operator credentials isolated from limit and live-arming credentials?
10. What evidence is required before partial scope may expand?

Unresolved answers reduce authority or keep the system non-live.

---

## 25. Approval Gate

ADR-002-007 may move from **Proposed** to **Accepted** only when:

- Hard Safety Envelope and Runtime Safety Profile governance is implemented with atomic activation;
- ADR-002-014 canonical artifacts, separated governance, committed Profile Generation, mixed-version denial, restrictive precedence, and rollback/restore fencing are implemented and their required SPG evidence passes;
- ADR-002-015 effective Human Safety Principal, exact Approval Set, one-human restrictive HALT, break-glass confinement, compromise, and approval non-revival are implemented and their required HAG evidence passes;
- all roles and separation-of-duty controls are defined and enforced;
- the ADR-002-017 Recovery Barrier Policy, Recovery Generation, owner fencing, dependency-complete inventory, obligation graph, Recovery Evidence Package, Recovery Readiness Decision, invalidation, and Live Authorization handoff contracts are implemented;
- ADR-002-018 Critical Input Policy, source continuity, Decision Context Capsule, exact binding, correction/invalidation fan-out, and active authority/egress currentness are implemented and their required CII evidence passes;
- ADR-002-019 exact venue/session/tradability and order/account/margin/settlement decision binding, restrictive invalidation, and active authority/egress currentness are implemented and their required VTG evidence passes;
- current time, epoch, reconciliation, capacity, broker capability, configuration, and deployment checks are enforced at final egress;
- the selected currentness distribution and fenced irreversible-send protocol in §§9.1–9.5 is implemented and independently security-reviewed;
- the applicable ADR-002-013 final-egress trust boundary, proof validation, credential/route confinement, and hard fencing are implemented and their required EGRESS evidence passes;
- ADR-002-016 exact approval, authority, invalidation, HALT, recovery, re-arm, pre-effect, and send evidence is durably captured, gap-contained, and replayable without creating or reviving permission, and applicable ERI evidence passes;
- `SBR-EV-001` through `SBR-EV-012` and applicable cross-ADR recovery evidence pass at required levels and receive independent review;
- every invalidation trigger fails closed within its approved bound;
- `B_risk_increase_revoke`, `B_revocation_to_egress`, `B_halt_to_egress`, `B_recovery_trigger_to_barrier`, `B_recovery_barrier_to_egress`, `MAX_recovery_readiness_age`, `MAX_normal_capability_age`, `B_capability_claim_to_send`, `B_egress_hard_fence`, `B_evidence_persist`, `B_evidence_gap_detect`, and `B_evidence_gap_contain` are approved, measured, and enforced at every applicable boundary;
- automatic re-arm and stale authorization replay are demonstrably impossible;
- partial re-arm cannot expand beyond its exact scope;
- VER-002-001 and the Evidence Register cover every Critical acceptance case;
- evidence is immutable and independently reviewed.

Until then, this ADR authorizes design and non-live implementation-planning work only. It does not authorize ADR acceptance, restricted-live operation, or production live trading.
