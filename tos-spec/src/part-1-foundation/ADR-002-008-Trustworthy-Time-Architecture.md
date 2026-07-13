# ADR-002-008 — Trustworthy Time Architecture

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Time domains, time-health state, confidence and uncertainty, freshness, ordering, session evaluation, monotonic holdover, restart and suspension behavior, failure containment, recovery, and evidence
- **Supersedes:** None
- **Amends:** RFC-002 §16 Trustworthy Time Architecture and the time prerequisites in §15.5, §17, and §23
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-030, SAFE-031, SAFE-035, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-003 authority epochs and degraded leases; ADR-002-004 broker-time capability; ADR-002-005 orthogonal state; ADR-002-006 per-field evidence confidence

---

## 1. Decision

The Trading Operating System SHALL treat trustworthy time as a safety-critical, evidence-backed state produced by a dedicated **Trustworthy Time Service**, not as direct access to a system clock.

No single clock, timestamp, synchronization daemon, broker timestamp, or network response is unconditional truth.

Every time-dependent safety decision SHALL identify:

1. the time domain used;
2. the evidence establishing that domain's current health;
3. the conservative uncertainty bound;
4. the continuity identity under which elapsed time is valid;
5. the approved bound governing freshness, expiry, or session state.

New risk-increasing authority requires `TRUSTED` time health for every time domain on which the decision depends.

Loss or uncertainty of the required time basis SHALL fail closed before it can authorize new risk. It SHALL NOT release capacity, erase potentially-live quantity, declare an order terminal, or revive expired authority.

Bounded degraded protective operation MAY use a pre-established local monotonic holdover only when ADR-002-003 and this ADR both prove continuity, remaining lifetime, exclusive ownership, and conservative uncertainty. Wall-clock comparison alone is insufficient.

Restoration of synchronization does not reactivate an expired, revoked, superseded, or previously invalidated authorization. Recovery and re-arm remain governed by ADR-002-007.

---

## 2. Context

Time affects market-data freshness, account-state freshness, event ordering, venue sessions, configuration validity, authority expiry, protective leases, reconciliation bounds, retries, recovery, and re-arm.

Unsafe failures include:

- wall-clock rollback making expired authority appear current;
- wall-clock jump making fresh evidence appear stale or changing session state incorrectly;
- frozen time preventing expiry;
- source disagreement hidden by a single synchronization status;
- a suspended process resuming with an apparently valid lease;
- process or host restart reusing an invalid monotonic anchor;
- broker timestamps being treated as a total order despite weak broker guarantees;
- timezone or market-calendar error opening authority outside the intended session;
- restored clock health reviving an authorization invalidated during the outage.

The architecture therefore requires explicit time domains, conservative uncertainty, continuity fencing, observable time-health transitions, and a recovery barrier.

---

## 3. Decision Drivers

1. Stale data or expired authority must never appear valid because a clock is wrong.
2. Event ordering must not depend on wall time when stronger sequence evidence exists.
3. Authority and lease expiry must fail closed under rollback, drift, freeze, suspension, and restart.
4. Broker and source timestamps must retain their provenance and capability limits.
5. Time recovery must be explicit and must not auto-re-arm live operation.
6. Numeric bounds must remain configuration-governed and independently approved.
7. Every time-based decision must be reconstructable from retained evidence.

Availability is subordinate to these requirements.

---

## 4. Time Domains

The system SHALL keep the following domains distinct.

### 4.1 Local Monotonic Time

Used for elapsed-time measurement within one proven continuity identity.

It has no calendar meaning and SHALL NOT be compared across process or host identities unless a stronger continuity mechanism is approved.

### 4.2 Local Wall Time

Used for human-readable audit correlation and as one input to calendar or session evaluation.

It SHALL NOT be the sole basis for permissive expiry, freshness, ordering, or degraded-lease validity.

### 4.3 Reference Time

Time obtained from independently identified synchronization references. Reference sources, paths, quality indicators, and common-mode dependencies SHALL be recorded.

### 4.4 Source Event Time

The timestamp supplied by a market-data, account-data, or other event source. It remains source-scoped evidence and SHALL retain source identity, sequence, precision, and uncertainty.

### 4.5 Broker or Venue Time

Time supplied by the broker or venue. Its permitted safety use is limited by the active Broker Capability Profile. It is not automatically suitable for attribution, ordering, expiry, or Final Quantity Proof.

### 4.6 Authorization Validity Time

The time basis and interval attached to Safety Authority capabilities, Live Authorization, Runtime Safety Profiles, and protective leases.

### 4.7 Trading Session Time

The timezone, calendar, holiday, auction, halt, and session-phase interpretation used to decide whether an action is permitted.

These domains MAY disagree. The disagreement SHALL be represented as evidence and SHALL NOT be collapsed into one timestamp.

---

## 5. Continuity and Time-Evidence Identity

Every elapsed-time or time-health assertion SHALL be bound to a **Time Continuity Identity** containing at least:

- host or runtime identity;
- boot identity;
- process identity where process-local continuity matters;
- monotonic anchor identity and value;
- Trustworthy Time Service generation;
- active reference-source set and path identity;
- timezone database and trading-calendar versions;
- approved Verification Profile version.

A process restart, host reboot, monotonic reset, discontinuity, unbounded suspension, or continuity-identity change invalidates every local anchor that cannot be proven continuous across that event.

The system SHALL NOT reconstruct a monotonic anchor from wall time.

---

## 6. Time-Health State Model

The Trustworthy Time Service SHALL publish one state per governed time scope:

```text
UNINITIALIZED
    -> SYNCHRONIZING
    -> TRUSTED

TRUSTED -> DEGRADED_HOLDOVER
TRUSTED -> UNTRUSTED
DEGRADED_HOLDOVER -> UNTRUSTED
DEGRADED_HOLDOVER -> SYNCHRONIZING
UNTRUSTED -> SYNCHRONIZING
SYNCHRONIZING -> TRUSTED
```

### 6.1 `TRUSTED`

All required sources, uncertainty, progression, continuity, and configuration checks pass within approved bounds.

### 6.2 `DEGRADED_HOLDOVER`

Online reference confidence is lost, but an approved local monotonic anchor remains continuous and within its conservative holdover budget.

This state never authorizes new normal risk. It may support only a pre-issued degraded protective lease that independently satisfies ADR-002-001 and ADR-002-003.

### 6.3 `UNTRUSTED`

Required time correctness, progression, continuity, or remaining uncertainty cannot be proven.

No time-dependent permissive action may be newly authorized.

### 6.4 Conservative Transitions

Transitions toward less trust may be applied immediately. A transition back to `TRUSTED` requires a new health generation and complete re-establishment; it SHALL NOT retroactively validate actions or evidence from the untrusted interval.

---

## 7. Establishing `TRUSTED` Time

The Trustworthy Time Service SHALL validate at least:

- monotonic progression and absence of discontinuity;
- local wall-clock progression;
- reference-source reachability and health;
- offset and drift against approved bounds;
- disagreement among sufficiently independent sources;
- synchronization path and source identity;
- leap, timezone, and calendar interpretation;
- process and host suspension evidence;
- freshness of its own health observation;
- active Verification Profile and Safety Profile versions.

Where Critical authority depends on reference time, the design SHALL use corroborating sources or record a reviewed single-source residual risk under ADR-002-006. Multiple names served by one clock, network path, hypervisor, or synchronization daemon SHALL NOT be claimed as independent.

If any required check is missing, stale, conflicting, or unverifiable, the state is not `TRUSTED`.

---

## 8. Time Health Snapshot

Every safety consumer SHALL use an immutable, versioned **Time Health Snapshot** containing at least:

- snapshot identity and Trustworthy Time Service generation;
- Time Continuity Identity;
- health state;
- evaluated monotonic anchor;
- wall-clock observation for audit;
- active reference-source identities and quality;
- offset, drift, uncertainty, and source-disagreement bounds;
- suspension and discontinuity status;
- timezone database and trading-calendar versions;
- issuer continuity identity, issue monotonic value, and maximum consumer age;
- applicable Verification Profile and Safety Profile versions;
- reason codes for degradation or denial;
- integrity evidence.

A consumer SHALL reject a snapshot from the wrong environment, scope, generation, or configuration version, or whose issuer continuity identity is inconsistent with the declared issuer and signed snapshot provenance. A consumer having a different continuity identity is not itself a mismatch; it activates the cross-domain age rules below.

Snapshot signature or syntax alone does not prove current health. Consumers SHALL enforce the maximum snapshot age using a valid local monotonic basis.

When producer and consumer share the same proven Time Continuity Identity, elapsed age MAY be calculated from that shared monotonic domain. When they do not share one continuity identity, the consumer SHALL NOT subtract the issuer's monotonic value from its own clock. Instead, the consumer SHALL:

1. validate the issuer's signed age and uncertainty bound at emission;
2. record receipt using the consumer's own monotonic clock and continuity identity;
3. add the approved transport, queueing, and clock-domain-conversion uncertainty bounds;
4. add elapsed consumer-local monotonic time since receipt;
5. reject the snapshot if any bound is missing, stale, contradictory, or exceeds the approved maximum age.

The issuer monotonic value remains provenance; it is not a cross-host timestamp. Consumer restart, monotonic discontinuity, or loss of the receipt anchor invalidates the cached snapshot for permissive use.

A transition to a less-trusted Time Health generation SHALL become effective at every final egress within `B_time_health_to_egress`. An egress proof older than `MAX_time_health_snapshot_age` or one whose current generation cannot be positively established is denial. The concrete propagation mechanism remains an implementation choice, but unsafe cache lifetime or transport delay SHALL NOT exceed either approved bound.

---

## 9. Freshness and Age Evaluation

Freshness SHALL be evaluated using a conservative upper bound, not a raw subtraction of wall timestamps.

The bound SHALL include, where applicable:

- source timestamp precision and uncertainty;
- source-to-receipt transport delay bound;
- local receive monotonic time;
- current monotonic elapsed time;
- drift and holdover uncertainty;
- queueing, buffering, replay, and batching bounds;
- source sequence gaps;
- clock-domain conversion uncertainty.

If the upper bound cannot be established, the evidence is `STALE` or `UNKNOWN` for permissive use.

A negative calculated age, timestamp from the future outside tolerance, missing source time, or unbounded transport path SHALL NOT be coerced to zero or accepted as fresh.

Freshness thresholds belong in an approved Safety Profile or Verification Profile.

---

## 10. Event Ordering

Ordering SHALL prefer, in order of evidentiary strength:

1. authoritative source sequence or broker sequence;
2. durable local send or receive sequence;
3. local monotonic order within one continuity identity;
4. corroborated source event time within its uncertainty;
5. wall time for audit correlation only.

Wall timestamps SHALL NOT establish a total order across processes or external systems when uncertainty intervals overlap.

Conflicting or ambiguous order SHALL remain represented in the Knowledge / Evidence dimension and SHALL block any safety transition requiring resolved order.

---

## 11. Authorization, Configuration, and Lease Validity

### 11.1 Normal Authority

Normal risk-increasing authority requires a current `TRUSTED` Time Health Snapshot and online currentness proof under ADR-002-003.

### 11.2 Degraded Protective Holdover

A degraded protective lease may use local monotonic holdover only when:

- the anchor was established while time was `TRUSTED`;
- the same continuity identity remains active;
- monotonic progression and suspension remain within approved bounds;
- the lease was issued before loss of online authority;
- its exclusive owner and remaining capacity are proven;
- the usable lifetime remains positive after all uncertainty and safety margins;
- final egress verifies the same facts.

The conservative usable lifetime SHALL be no greater than:

```text
issued lifetime
- elapsed local monotonic time
- source and transport uncertainty
- maximum drift error
- suspension uncertainty
- approved safety margin
```

If any term is unknown or the result is non-positive, the lease is invalid for new transmission.

### 11.3 Economic Effect Survives Expiry

Authority, configuration, profile, or lease expiry revokes future use only. It SHALL NOT release Capacity Commitments, cancel broker orders, erase fills, or prove that potentially-live economic effect has ended.

### 11.4 Configuration Expiry

An expired or time-unverifiable Runtime Safety Profile SHALL fail closed. Restoration of time health SHALL NOT reactivate an expired version without the activation rules in ADR-002-007.

---

## 12. Trading Session Evaluation

Session evaluation SHALL bind:

- market and venue;
- account and instrument scope;
- canonical timezone identifier;
- timezone database version;
- market-calendar version;
- holiday, auction, halt, and exceptional-session data;
- current Time Health Snapshot;
- Broker Capability Profile session semantics.

Ambiguous local time, missing calendar data, unknown session phase, timezone-version conflict, or a boundary inside the current uncertainty interval SHALL deny actions that require a positively open session.

Session restoration does not auto-submit deferred or previously denied orders. A new decision and current authority are required.

---

## 13. Failure Responses

| Failure | Required response |
|---|---|
| Wall-clock rollback, jump, or freeze | mark affected domains untrusted; revoke new risk; preserve economic state |
| Reference source unavailable | enter bounded holdover only if every holdover prerequisite passes; otherwise `UNTRUSTED` |
| Reference sources disagree | use the conservative uncertainty bound; deny permissive use when outside tolerance |
| Drift exceeds approved bound | `UNTRUSTED`; revoke time-dependent permissive authority |
| Monotonic discontinuity | invalidate local anchors and degraded leases for new actions |
| Process or host restart | establish a new continuity identity; old anchors do not survive by assumption |
| Suspension exceeds bound or is unknown | invalidate holdover and affected snapshot freshness |
| Broker time conflicts with local evidence | mark affected broker evidence `CONFLICTED`; reconcile under ADR-002-006 |
| Timezone or calendar unavailable | deny session-dependent action |
| Time health recovers | remain non-live until recovery gates and explicit re-arm complete |

Every failure SHALL create evidence and an operational alert within the approved bound.

---

## 14. Component Responsibilities

### 14.1 Trustworthy Time Service

Sole owner of Time Health Snapshot creation and time-health state transitions. It SHALL NOT issue live authority or classify economic risk.

### 14.2 Context Integrity Service

Uses time evidence to calculate conservative data freshness and exposes `STALE` or `UNKNOWN` rather than hiding uncertainty.

### 14.3 Reconciliation Service

Uses time evidence to determine per-field freshness and ordering under ADR-002-006. It does not alter time health.

### 14.4 Safety Profile Validator

Validates time-related bounds, calendars, timezone versions, and compatibility without expanding the Hard Safety Envelope.

### 14.5 Safety Authority and Live Authorization Service

Bind capabilities and authorization to the required Time Health Snapshot generation and reject untrusted or stale time.

### 14.6 Broker Adapter / Egress Gateway

Final enforcement point for current snapshot, accepted Time Health generation, continuity, expiry, session, and degraded-holdover checks before transmission. It SHALL reject when the current generation cannot be positively established or the snapshot/currentness proof exceeds its approved age.

### 14.7 Recovery Coordinator

Requires a newly established `TRUSTED` generation as one ADR-002-017 Recovery Obligation for re-arm readiness. It SHALL NOT treat source recovery alone as sufficient, publish readiness for a stale Recovery Generation, or bypass the closed Recovery Barrier.

---

## 15. Failure-Domain Requirements

ADR-002-009 governs the Failure-Domain Allocation Matrix and acceptance of every time-source, synchronization, host, network, hypervisor, calendar, and shared egress dependency described in this section.

The implementation SHALL document whether the following are independent or common-mode:

- reference clocks and upstream operators;
- DNS and network paths;
- host clock and hypervisor clock;
- synchronization daemon and Trustworthy Time Service;
- operating-system clock APIs;
- monotonic clock source;
- container or VM suspension behavior;
- timezone and calendar distribution;
- configuration distribution;
- the libraries used by time validation and authority validation.

Multiple logical services using the same clock, library, host, or network path are not physically independent.

---

## 16. Recovery

Recovery from `UNTRUSTED` or `DEGRADED_HOLDOVER` SHALL require:

1. a new Trustworthy Time Service generation;
2. a valid Time Continuity Identity;
3. source synchronization and disagreement checks passing for the approved stabilization interval;
4. current timezone, calendar, Verification Profile, and Safety Profile versions;
5. affected freshness and session assumptions re-evaluated;
6. authority and protective leases revalidated or replaced rather than revived;
7. Recovery Coordinator evidence recorded.

This establishes time readiness only within the current ADR-002-017 Recovery Evidence Package. It does not open the Recovery Barrier, issue Live Authorization, or re-arm.

---

## 17. Evidence, Metrics, and Alerts

Evidence SHALL retain:

- every time-health transition and reason;
- source identities, quality, offset, drift, disagreement, and uncertainty;
- continuity identity and monotonic anchors;
- suspension, restart, and discontinuity evidence;
- snapshots consumed by safety decisions and egress;
- freshness and session calculations;
- denied actions and invalidated capabilities;
- recovery stabilization evidence;
- exact code, timezone database, calendar, and profile versions.

Required metrics include current state, snapshot age, offset and drift bounds, source disagreement, continuity generation, holdover remaining, suspension detection, stale-data decisions, session ambiguity, and time-caused egress denials.

Critical alerts include monotonic discontinuity, rollback or freeze, unbounded source disagreement, degraded lease active with unknown time health, stale snapshot accepted, or live transmission without a valid time proof.

Evidence and alerting do not substitute for runtime denial.

---

## 18. Alternatives Rejected

- **System wall clock is authoritative.** Rejected because it can step, freeze, drift, and be misconfigured.
- **NTP synchronized means trusted.** Rejected because daemon status alone does not prove source independence, bounded error, or current consumer evidence.
- **Broker time is authoritative.** Rejected because its ordering, precision, and semantics are broker-specific.
- **Wall-clock-only expiry.** Rejected because rollback or disagreement can extend permissive authority.
- **Monotonic time survives restart by assumption.** Rejected because continuity is not proven across process, host, or suspension boundaries.
- **Recovered clock revives old authority.** Rejected because restored time does not restore operator intent, state reconciliation, or current authorization.
- **Clamp negative age to zero.** Rejected because it converts conflict into false freshness.

---

## 19. Verification and Acceptance Criteria

ADR-002-008 SHALL remain Proposed until executed evidence demonstrates at least:

- **TIME-AC-001 — Wall rollback and jump:** expired authority and stale evidence never become valid.
- **TIME-AC-002 — Clock freeze:** expiry and freshness fail closed before new risk.
- **TIME-AC-003 — Source disagreement:** uncertainty widens conservatively and authority is denied outside the approved bound.
- **TIME-AC-004 — Monotonic discontinuity:** degraded lease and local anchors are invalidated.
- **TIME-AC-005 — Restart and suspension:** old holdover cannot authorize a new action after restart or excessive suspension.
- **TIME-AC-006 — Holdover boundary:** use is allowed only inside the conservative remaining lifetime and only for the pre-issued protective scope.
- **TIME-AC-007 — Freshness:** future, missing, delayed, and reordered events become `STALE`, `UNKNOWN`, or `CONFLICTED`, never optimistically fresh.
- **TIME-AC-008 — Session boundary:** ambiguous timezone, calendar, and uncertainty-window cases deny session-dependent action.
- **TIME-AC-009 — Time recovery:** recovery creates a new generation but does not revive capability or auto-re-arm.
- **TIME-AC-010 — Egress enforcement:** no live path can transmit without the required current Time Health Snapshot; less-trusted generations reach egress within `B_time_health_to_egress`, cross-host age is calculated without direct monotonic subtraction, and stale currentness proof is denied.

These criteria map one-to-one to TIME-EV-001 through TIME-EV-010 and additionally to SA-EV-005, SA-EV-006, SA-EV-011, X-EV-008, and the freshness/recovery cases in ADR-002-005/006. Registration is not execution; every applicable evidence item must pass at its required level before this ADR can be accepted.

A written case is not completed evidence.

---

## 20. Consequences

**Positive:** expired authority cannot be extended by clock faults; time uncertainty becomes explicit; degraded holdover is bounded and continuity-fenced; freshness and session decisions become reproducible; recovery cannot silently re-arm.

**Negative:** more actions fail closed near session boundaries or during source disagreement; holdover is shorter; deployment requires source and failure-domain analysis; clocks, calendars, and time libraries require governed lifecycle management.

These costs are accepted because time-dependent availability is subordinate to safety.

---

## 21. Requirements Traceability

| Requirement | ADR-002-008 allocation |
|---|---|
| SAFE-030 | Time-dependent Critical Inputs use conservative freshness and deny stale or unknown context (§9) |
| SAFE-031 | Source, broker, reference, continuity, calendar, and configuration provenance remains attached to every time assertion (§4–§8) |
| SAFE-035 | Explicit time domains, uncertainty, continuity, health state, holdover, and failure behavior define the trustworthy-time basis (§4–§13) |
| SAFE-044 | Recovery establishes a new time generation but grants no Live Authorization and performs no automatic re-arm (§16) |
| SAFE-048 | Partition-time protective use is limited to a pre-issued, exclusive, continuity-fenced monotonic lease (§6, §11.2) |
| SAFE-050 | Time bounds, calendars, timezone data, and profile versions are governed and fail closed when invalid (§7–§8, §11.4, §12) |
| SAFE-051 | Every time-health transition and safety decision retains its inputs, versions, result, and reason (§17) |
| SAFE-052 | Retained snapshots, calculations, and continuity evidence support independent incident reconstruction (§17, §19) |

---

## 22. Open Implementation Questions

The following may remain open while Proposed but SHALL be resolved before acceptance:

1. Which reference sources and independent paths are approved per deployment?
2. What platform provides continuity, suspension, and boot identity evidence?
3. What offset, drift, disagreement, snapshot-age, stabilization, and holdover bounds are approved?
4. Which market-calendar source and update process are governed?
5. What broker timestamps may be used for attribution or ordering per Broker Capability Profile?
6. Which mechanism distributes current Time Health generations and revocation evidence without unsafe caching or a circular dependency while meeting `B_time_health_to_egress` and `MAX_time_health_snapshot_age`?
7. Which common-mode time failures require physical isolation?
8. How do ADR-002-014 artifact, approval, activation, and compatibility validity intervals bind the Time Health generation without allowing time recovery to revive authority?

Unresolved answers reduce authority; they do not weaken the rules above.

---

## 23. Approval Gate

ADR-002-008 may move from **Proposed** to **Accepted** only when:

- the time domains, health states, continuity identity, and snapshot contract are implemented;
- approved numeric bounds replace all placeholders;
- `B_time_health_to_egress` and `MAX_time_health_snapshot_age` are approved and enforced at every final egress;
- reference-source and common-mode analysis is independently reviewed;
- freshness, ordering, session, holdover, restart, and recovery behaviors are demonstrated;
- the Time Health generation distribution and consumer receipt-anchor mechanism in §22.6 is selected, implemented, and independently reviewed;
- final egress rejects stale or untrusted time;
- ADR-002-014 profile and approval expiry, time-invalid activation, and time-recovery non-revival rules are implemented and their applicable SPG evidence passes;
- ADR-002-016 source continuity, trustworthy-time evidence, causal ordering, gap handling, and replay prohibit cross-host monotonic comparison and preserve uncertainty, and applicable ERI evidence passes;
- no recovery path revives old authority or automatically re-arms;
- VER-002-001 and the Evidence Register cover every Critical acceptance case;
- retained evidence is immutable and independently reviewed.

Until then, this ADR authorizes design and non-live implementation-planning work only. It does not authorize ADR acceptance, restricted-live operation, or production live trading.
