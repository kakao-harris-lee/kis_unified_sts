# ADR-002-003 — Safety Authority Validity, Epoch Fencing, and Partition Behavior

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Safety Authority leadership, epochs, capability validity, stale-instance fencing, partition behavior, degraded protective leases, halt precedence, failover, recovery, and re-arm
- **Supersedes:** None
- **Amends:** RFC-002 Safety Authority and partition semantics
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-011, SAFE-035, SAFE-041, SAFE-048; ADR-002-001 v0.2; ADR-002-002

---

## 1. Decision

The Trading Operating System SHALL maintain exactly one current **Safety Authority epoch** for every live authority domain.

A Safety Authority instance may calculate or sign a decision, but an execution path may accept a permissive decision only when it can prove that:

1. the decision was issued by an authorized Safety Authority identity;
2. the decision belongs to the current authority domain and current epoch;
3. its capability scope matches the requested economic action;
4. its validity remains positively established using trustworthy time or a specifically authorized monotonic holdover rule;
5. it has not been consumed, superseded, revoked, or invalidated by a safer state;
6. the Broker Adapter or final broker-egress gateway independently verifies the same facts.

A stale epoch SHALL have no authority to create new risk, enlarge existing authority, re-arm live mode, renew a lease, or transmit through broker egress.

Loss of proof is treated as loss of authority. The system SHALL NOT infer permissive authority from silence, cached success, prior health, or an unavailable control plane.

Risk-increasing authority requires online current-epoch verification. Offline operation is limited to a pre-issued, exclusive, narrowly scoped degraded protective lease whose maximum lifetime and overlap behavior are proven before the partition.

A transition to a safer state may be accepted through a broader and more redundant path than a transition to a less safe state. `HALT` and restrictive state transitions dominate permissive grants.

---

## 2. Context

A Safety Authority may fail in ways that do not stop its process:

- network partition;
- GC pause followed by recovery;
- host suspension;
- stale container or VM resuming;
- duplicated deployment;
- failover while the former leader remains connected to the broker path;
- delayed or replayed authority messages;
- clock drift or clock discontinuity;
- partial credential revocation;
- control-plane recovery while an old degraded lease remains locally valid.

Leader election alone does not prevent the former leader from continuing to act. A lease alone does not provide immediate revocation. A digital signature proves origin, not current authority. A wall-clock expiration is unsafe when time trust is degraded. A control-plane failover can create overlapping protective owners unless the previous offline authority is fenced or allowed to expire before a replacement receives the same scope.

The architecture therefore requires an explicit authority epoch, an enforceable egress fence, conservative time validity, non-overlapping protective delegation, and asymmetric safer-state precedence.

---

## 3. Decision Drivers

The decision is driven by the following priorities:

1. no stale or duplicated authority may create new economic risk;
2. loss of current authority must fail closed;
3. a control-plane partition must not preserve an unbounded permissive grant;
4. limited protective operation may continue only when its exclusivity and validity remain provable;
5. halting and containment must remain available under broader failure conditions than re-arming;
6. failover must not create overlapping authority;
7. authority decisions must be independently enforceable at broker egress;
8. recovery and re-arm must be explicit, reviewable, and evidence-backed.

Availability is subordinate to these properties.

---

## 4. Scope

This ADR decides:

- Safety Authority domains and single-active semantics;
- epoch creation and advancement;
- fencing behavior;
- capability types and required claims;
- currentness verification at execution and broker egress;
- partition behavior for normal and degraded operation;
- offline protective lease exclusivity;
- time-validity and monotonic holdover rules;
- halt, containment, failover, and re-arm behavior;
- audit and verification obligations.

This ADR does not select:

- a consensus product;
- a database vendor;
- exact lease durations;
- exact clock-drift thresholds;
- broker-specific credential-revocation mechanisms;
- the complete risk-capacity state machine;
- broker capability classifications.

Those implementation choices must conform to this ADR and the Broker Capability ADR.

---

## 5. Definitions

### 5.1 Authority Domain

The scope within which one Safety Authority epoch is exclusive.

An Authority Domain SHALL be no broader than the failure and serialization boundary that can be fenced. A domain may be account-scoped, portfolio-scoped, or another approved scope, but overlapping domains that can authorize the same economic action are prohibited.

### 5.2 Safety Authority Epoch

A monotonically increasing, durable generation number identifying the only current permissive authority for an Authority Domain.

An epoch is not a timestamp.

### 5.3 Current Epoch Proof

Evidence available to an enforcement point that a capability belongs to the currently accepted epoch.

A signature alone is not Current Epoch Proof.

### 5.4 Fencing

A mechanism that prevents an authority from mutating safety-critical state or transmitting economic actions after it loses current authority.

Fencing must be enforced by the receiving state authority or final broker-egress path, not merely by the stale process voluntarily stopping.

### 5.5 Permissive Capability

A capability that permits an action which may increase, preserve, or transform economic exposure.

Examples include live risk-increasing execution, protective-order placement, capacity consumption, lease renewal, and re-arm.

### 5.6 Restrictive Capability

A capability whose only permitted effect is to move the system to an equal or safer authority state.

Examples include halt, deny, contain, revoke, or reduce an authorization scope. An order labelled “sell” is not automatically restrictive.

### 5.7 Degraded Protective Lease

A pre-issued, exclusive, bounded delegation permitting a defined protective action class during loss of the online Safety Authority path.

It is not a general cached authority grant.

### 5.8 Hard Fence

Proof that a former authority can no longer reach the broker or mutate the relevant authoritative state.

Examples may include enforced epoch rejection at a reachable egress gateway, broker-session revocation, credential invalidation, or another mechanism demonstrated to stop the old path.

### 5.9 Lease-Expiry Fence

A conservative waiting barrier that prevents reassignment of an offline-capable scope until every previously issued lease for that scope must have expired under maximum duration, clock-drift, process-suspension, and communication-delay assumptions.

### 5.10 Authority Holdover Budget

The maximum interval during which a specific degraded protective lease may remain valid using local monotonic time after online currentness verification becomes unavailable.

---

## 6. Safety Invariants

### SA-INV-001 — One Current Permissive Epoch

For each Authority Domain, exactly one epoch may be accepted for new permissive actions.

### SA-INV-002 — Stale Epoch Rejection

An execution path, Broker Adapter, Risk Capacity Ledger, protective sub-ledger, or Live Authorization Service SHALL reject every new permissive operation carrying an epoch lower than the current accepted epoch.

### SA-INV-003 — Unknown Currentness Is Denial

If an enforcement point cannot positively establish current epoch and capability validity, it SHALL reject risk-increasing action.

### SA-INV-004 — Epoch Advance Does Not Release Economic Effect

Advancing the Safety Authority epoch revokes future authority. It does not release capacity, cancel broker orders, erase potentially-live quantity, or prove that old economic effects no longer exist.

### SA-INV-005 — No Cached Risk-Increasing Authority During Partition

A cached normal live grant SHALL NOT authorize a new risk-increasing transmission after online current-epoch verification is lost.

### SA-INV-006 — Exclusive Offline Protective Scope

At most one locally executable Degraded Protective Lease may own the same protective scope and underlying committed capacity at any instant.

### SA-INV-007 — No Overlapping Failover Lease

A replacement degraded lease SHALL NOT be issued for a scope until the former lease is hard-fenced or its conservative lease-expiry fence has completed.

### SA-INV-008 — Monotonic Validity Must Be Positive

A degraded lease is valid only while remaining lifetime can be positively established from a healthy local monotonic basis within the approved holdover budget.

### SA-INV-009 — Restart Invalidates Offline Holdover

A process restart, host reboot, monotonic-clock discontinuity, unbounded suspension, or loss of local time-health evidence SHALL invalidate the degraded lease unless a stronger continuity mechanism has been independently approved.

### SA-INV-010 — Safer State Dominates

A valid transition to a safer state SHALL dominate any outstanding capability permitting a less safe state.

### SA-INV-011 — Halt Is Monotonic Until Explicit Re-arm

Once `HALTED` is applied, no previously issued permissive capability may restore live operation. Re-arm requires a new authorization sequence and current epoch.

### SA-INV-012 — Egress Is Final Authority Gate

No risk-relevant broker request may bypass current-epoch and capability verification at the final Broker Adapter or broker-egress gateway.

### SA-INV-013 — Re-arm Cannot Be Automatic

No timeout, service recovery, leader election, reconciliation completion event, or system restart may automatically re-arm live mode.

### SA-INV-014 — Limit Change and Live Arming Are Separated

No single principal or credential may both enlarge active limits and arm the enlarged scope without the approved dual-control process.

---

## 7. Authority State Precedence

The system SHALL apply the following safety precedence unless RFC-000 requires a stricter interpretation:

```text
HALTED
    > CONTAINED
    > DEGRADED_PROTECTIVE
    > LIVE_RESTRICTED
    > LIVE_NORMAL
```

The symbol `>` means “takes precedence over.”

A transition toward the left is a safer-state transition. A transition toward the right is a permissive transition.

Safer-state transitions may be triggered by multiple authenticated components when their action is monotonic and cannot enlarge authority. Permissive transitions require the current Safety Authority, required reconciliation gates, live authorization, and operator controls.

A stale but authentic `HALT` message may be conservatively applied. A stale permissive grant may not be applied.

---

## 8. Safety Authority Roles

### 8.1 Safety Authority Leader

The current leader may:

- evaluate safety state;
- issue or deny scoped capabilities;
- advance to safer modes;
- request epoch advancement through the authoritative epoch mechanism;
- approve bounded protective lease issuance when all prerequisites hold.

The leader SHALL NOT directly transmit broker orders or mutate risk capacity outside defined authoritative interfaces.

### 8.2 Authority Epoch Registry

A linearizable authority or equivalent mechanism SHALL:

- allocate monotonically increasing epochs;
- record the current epoch by Authority Domain;
- serialize epoch advancement;
- expose verifiable current-epoch evidence to enforcement points;
- reject stale mutations;
- retain durable transition evidence.

The Registry may be implemented with the same consensus substrate as another safety-critical registry only if failure-domain and authorization analysis show that no bypass or circular dependency is created.

### 8.3 Broker Adapter / Egress Gateway

The final egress point SHALL verify:

- capability signature and issuer identity;
- Authority Domain;
- authority epoch;
- currentness or allowed degraded-lease mode;
- capability type;
- account, instrument, action, quantity, and risk-effect scope;
- live authorization scope;
- capacity reservation or protective consumption;
- single-use or idempotent transmission identity;
- expiration and monotonic holdover validity;
- absence of a dominating safer state.

Failure of any check results in rejection before broker transmission.

### 8.4 Recovery Coordinator

The Recovery Coordinator assembles re-arm prerequisites but does not grant live authority.

It SHALL provide evidence that:

- current epoch is established;
- trustworthy time is restored;
- reconciliation barriers are complete;
- UNKNOWN and external activity are resolved or conservatively contained;
- capacity state is consistent;
- configuration and identity checks pass.

### 8.5 Operator Control Interface

The interface may request halt, containment, or re-arm. It does not itself become the Safety Authority.

Operator identity, role, reason, and approval evidence SHALL be recorded.

---

## 9. Capability Model

### 9.1 Required Claims

Every permissive capability SHALL include at least:

- capability identity;
- capability type;
- issuer identity;
- Authority Domain;
- Safety Authority epoch;
- subject service identity;
- environment and live/paper mode;
- account scope;
- instrument or instrument-class scope;
- permitted action class;
- maximum quantity;
- maximum risk-vector effect or linked reservation identity;
- Hard Safety Envelope version;
- Runtime Safety Profile version;
- issue sequence;
- validity rule;
- single-use, bounded-use, or idempotency semantics;
- parent authorization or protective-lease identity;
- cryptographic integrity evidence.

Missing claims are denial, not defaults.

### 9.2 Capability Types

At minimum, the system SHALL distinguish:

```text
NORMAL_RISK_INCREASING
NORMAL_RISK_REDUCING
DEGRADED_PROTECTIVE
CANCEL_REQUEST
PROTECTIVE_CANCEL_OR_REPLACE
HALT
CONTAIN
RECONCILIATION_ONLY
REARM
LIMIT_ACTIVATION
```

The names do not determine economic safety. The receiving enforcement point still validates the permitted effect.

### 9.3 Single-Use Semantics

A capability bound to one economic attempt SHALL be single-use unless the Broker Capability Profile proves deterministic idempotent retry of the same broker-side order identity.

### 9.4 Capability Caching

Capability material may be cached for verification performance. Cached data SHALL NOT be interpreted as proof that its epoch is still current.

Normal risk-increasing capabilities require an online currentness witness within the approved containment bound.

---

## 10. Epoch Lifecycle

### 10.1 Initial Establishment

Before live arming, the system SHALL:

1. establish the current Authority Domain;
2. allocate or confirm the current epoch;
3. fence every prior epoch at authoritative state mutation points and broker egress;
4. complete startup reconciliation;
5. verify trustworthy time;
6. verify live authorization and identity boundaries.

### 10.2 Epoch Advancement

Epoch advancement is required after at least:

- Safety Authority failover;
- detected duplicate active authority;
- loss of leader ownership;
- uncertain leader termination;
- safety-critical credential change;
- recovery from a partition where former authority reachability is unknown;
- security incident affecting authority integrity;
- explicit administrative revocation.

### 10.3 Advancement Barrier

The new epoch SHALL NOT issue overlapping offline-capable protective leases until the former lease scope is hard-fenced or the lease-expiry fence completes.

Normal online risk-increasing capabilities may be issued only after broker egress and state authorities reject the old epoch.

### 10.4 Epoch Persistence

Epoch state SHALL survive process restart and failover. It SHALL NOT be reconstructed from the highest epoch observed in an asynchronous event stream without authoritative proof.

### 10.5 Epoch Wraparound or Reset

Epoch reuse, reset, or wraparound is prohibited within the lifetime of retained evidence and live broker effects.

---

## 11. Fencing Model

### 11.1 Required Enforcement Points

Stale epochs SHALL be rejected by every component capable of creating or enlarging authority or economic effect, including:

- Authority Epoch Registry;
- Live Authorization Service;
- Risk Capacity Ledger;
- protective sub-ledger;
- Transmission Capability issuer;
- Broker Adapter or egress gateway;
- limit activation path;
- re-arm path.

### 11.2 Voluntary Shutdown Is Not Fencing

A stale process logging an error, losing a leadership lock, or receiving a shutdown signal is not sufficient evidence that it cannot act.

ADR-002-027 controlled shutdown therefore orders restrictive authority and egress fencing before ordinary process termination and preserves UNKNOWN and economic-effect obligations afterward. Incident declaration, shutdown completion, or administrative closure cannot clear a HALT generation or stand in for a hard fence.

### 11.3 Egress Reachability

If the stale instance can still reach the broker directly with a valid credential, safety fencing is incomplete even if internal services reject it.

The architecture SHALL either:

- force every live order through a fenced egress gateway; or
- demonstrate broker-side credential/session fencing that prevents stale direct transmission.

### 11.4 Credential Scope

Strategy, research, simulation, and general operator components SHALL NOT possess credentials capable of bypassing the fenced live egress path.

### 11.5 Failure of Fencing Proof

If current fencing cannot be proven, the Authority Domain enters at least `CONTAINED`. New risk is prohibited.

---

## 12. Normal Online Authority

### 12.1 Currentness Check

Before normal risk-increasing transmission, the final egress point SHALL obtain a currentness witness within an approved freshness and containment bound.

### 12.2 Witness Failure

If the witness is missing, stale, conflicting, or unverifiable:

- no new risk-increasing request is transmitted;
- existing potentially-live orders remain represented and reconciled;
- bounded cancellation or protective handling follows its own capability rules;
- the system transitions to an appropriate safer mode.

### 12.3 No Grace Period for New Risk

A permissive capability may have a validity interval for normal operation, but loss of required online currentness does not create an additional grace period for risk-increasing execution.

---

## 13. Partition Behavior

### 13.1 Safety Control Plane Unreachable

When the execution path cannot verify current Safety Authority state:

```text
New normal risk-increasing action: DENIED
New aggregate capacity commitment: DENIED
Normal capability renewal: DENIED
Live re-arm: DENIED
Limit enlargement: DENIED
```

Existing orders, fills, positions, and reservations continue to be tracked conservatively.

### 13.2 Degraded Protective Operation

A degraded protective action may proceed only when:

- ADR-002-001 classifies the action as protective across credible intermediate states;
- ADR-002-002 provides pre-committed protective capacity and exclusive sub-consumption;
- a valid Degraded Protective Lease already exists;
- local monotonic validity remains positively established;
- the lease scope is not known or suspected to overlap another live owner;
- Broker Capability Profile permits the action and fallback;
- broker egress validates the lease and action;
- no dominating safer state forbids transmission.

### 13.3 No Partition Renewal

A Degraded Protective Lease SHALL NOT be renewed, enlarged, reassigned, or replenished while the online authority path remains unavailable.

### 13.4 Loss of Lease Validity

When lease validity cannot be proven:

- no new protective order is transmitted under that lease;
- potentially-live prior attempts remain capacity-consuming;
- the system enters `CONTAINED` or `HALTED` as specified by the Safety Profile;
- operator escalation occurs within the approved bound.

### 13.5 Partition Rejoin

Rejoin does not automatically restore live mode.

The system SHALL:

1. establish the current epoch;
2. fence stale epochs;
3. reconcile all offline actions and broker effects;
4. reconcile protective lease consumption;
5. invalidate or close old leases;
6. complete Recovery Coordinator gates;
7. require explicit re-arm.

---

## 14. Degraded Protective Lease Validity

### 14.1 Issuance Preconditions

A lease may be issued only while:

- current online authority is verifiable;
- protective parent capacity is committed;
- lease scope is exclusive;
- broker capability supports the proposed degraded action;
- local monotonic time health is established;
- maximum holdover and drift assumptions are approved;
- the egress path can verify the lease without bypass.

### 14.2 Local Monotonic Anchor

On receipt, the execution-side owner SHALL durably associate the lease with:

- receipt process identity;
- host or runtime identity;
- local monotonic anchor;
- approved maximum duration;
- drift and suspension assumptions;
- authority epoch;
- capability digest.

### 14.3 Conservative Lifetime

The usable local lifetime SHALL be no greater than the signed lease duration reduced by approved uncertainty and safety margins.

If transport delay cannot be bounded, the local usable lifetime SHALL be reduced accordingly or the lease shall not support offline use.

### 14.4 Invalidating Events

The lease becomes invalid for new actions upon:

- process restart;
- host reboot;
- monotonic-clock reset or discontinuity;
- suspension exceeding the approved bound;
- loss of exclusive owner proof;
- exhausted protective capacity;
- Hard Safety Envelope incompatibility;
- broker capability profile revocation;
- dominating `CONTAINED` or `HALTED` state;
- expiry of the holdover budget.

### 14.5 Failover and Reassignment

Epoch advancement alone does not prove that the former offline lease can no longer transmit.

Before assigning overlapping scope to a new owner, one of the following SHALL be true:

1. a Hard Fence proves the former owner cannot transmit; or
2. the Lease-Expiry Fence has elapsed under worst-case assumptions.

---

## 15. Clock and Time Rules

### 15.1 Wall Clock

Wall clock may be used for audit and cross-system correlation but SHALL NOT be the sole basis for offline lease expiry.

### 15.2 Monotonic Clock

A local monotonic clock may support bounded holdover only when:

- monotonic continuity is monitored;
- drift assumptions are documented;
- process and host identity are stable;
- suspension detection exists or suspension is included in the bound;
- the maximum lease is short enough for the approved oscillator error.

### 15.3 Unknown Time Health

Unknown time health invalidates permissive offline capability.

### 15.4 Time Recovery

Restoration of a time source does not validate capabilities that expired or were invalidated while time health was unknown.

---

## 16. Halt and Containment

### 16.1 Halt Sources

`HALT` may be requested by:

- current Safety Authority;
- authenticated emergency operator path;
- approved automatic safety monitor;
- broker or account evidence indicating an uncontainable condition.

The exact source policy is defined by the Safety Profile.

### 16.2 Halt Acceptance

A valid halt or more restrictive state may be applied even when normal permissive currentness cannot be established, provided the message is authentic and cannot enlarge authority.

### 16.3 Halt Effects

HALT SHALL at least:

- deny new risk-increasing transmission;
- deny capability renewal and re-arm;
- preserve protective controls as allowed by the safe-state definition;
- preserve capacity for potentially-live and unknown effects;
- initiate reconciliation and evidence capture;
- prevent stale grants from restoring live mode.

### 16.4 Halt Does Not Mean Blind Cancel-All

The system SHALL NOT blindly cancel every protective order if cancellation could increase aggregate risk. Cancellation remains subject to protective ownership and aggregate-risk evaluation.

---

## 17. Re-arm Governance

### 17.1 Required Conditions

Re-arm requires all of the following:

- trustworthy time restored;
- current Safety Authority epoch established;
- stale epochs fenced;
- account-wide reconciliation completed;
- UNKNOWN orders resolved or conservatively contained under an explicit exception;
- unattributed external activity resolved;
- Risk Capacity Ledger consistency verified;
- protective leases reconciled and reissued if required;
- Hard Safety Envelope and Runtime Safety Profile versions verified;
- broker capability profile current;
- no unresolved Critical alert;
- Recovery Coordinator evidence complete;
- fresh Live Authorization issued;
- explicit human dual control completed.

### 17.2 Separation of Duties

The principal approving limit enlargement SHALL NOT be the sole principal arming that enlarged scope.

The Recovery Coordinator SHALL NOT issue its own re-arm approval.

### 17.3 New Capabilities

Re-arm SHALL issue new capabilities under the current epoch. Previously issued live capabilities are not revived.

### 17.4 Partial Re-arm

Re-arm may restore a narrower account, instrument, action, or capacity scope than existed before the halt. Full restoration is not required.

---

## 18. Security and Identity

### 18.1 Service Identity

Every authority decision and enforcement operation SHALL use authenticated workload identity bound to environment and role.

### 18.2 Key Management

Signing keys, verification keys, and rotation state SHALL be managed so that:

- stale or compromised issuers can be revoked;
- verification does not silently trust unknown keys;
- key rotation does not create overlapping permissive issuers without epoch controls;
- private signing material is unavailable to execution and strategy components.

### 18.3 Replay Protection

Capabilities SHALL carry identity and use semantics sufficient to detect unauthorized replay.

### 18.4 Cross-Environment Isolation

Paper, test, research, and simulation identities SHALL be cryptographically and operationally incapable of producing live-accepted capabilities.

---

## 19. Evidence and Audit

Every authority transition and capability decision SHALL record at least:

- Authority Domain;
- old and new epoch;
- leader identity;
- transition reason;
- currentness witness;
- capability digest and type;
- subject identity;
- scope;
- issue and validation evidence;
- local monotonic-anchor evidence for degraded leases;
- fencing result;
- egress acceptance or rejection;
- safer-state precedence applied;
- operator approvals;
- re-arm prerequisites and outcome.

Audit evidence is required for reconstruction but does not substitute for runtime prevention.

---

## 20. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| Duplicate Safety Authority instance | advance or confirm current epoch; fence stale instance; deny new risk until currentness proven |
| Old leader resumes after GC pause | stale epoch rejected by Registry, Ledger, and egress |
| Execution loses Authority path | deny normal risk increase; permit only valid degraded protective lease |
| Egress cannot verify current epoch | deny normal risk increase |
| Degraded lease owner restarts | invalidate lease for new actions |
| New leader cannot hard-fence old offline lease | wait through Lease-Expiry Fence before overlapping reassignment |
| Clock health becomes unknown | invalidate offline permissive holdover |
| HALT races with permissive grant | HALT dominates; permissive grant rejected |
| Authority key compromised | halt/contain domain; advance epoch; revoke key; reconcile |
| Reconciliation completes after halt | remain halted until explicit re-arm |
| Epoch Registry unavailable | no new permissive authority; existing effects remain tracked |
| Broker egress bypass detected | immediate halt; credential containment; incident review |

---

## 21. Alternatives Rejected

### 21.1 Leader Election Without Fencing

Rejected because the former leader may continue to execute after losing election.

### 21.2 Signed Token Without Epoch

Rejected because authenticity does not prove current authority.

### 21.3 Long-Lived Cached Live Grant

Rejected because a partition would preserve permissive authority beyond current control.

### 21.4 Wall-Clock-Only Expiration

Rejected because wall clock can step, drift, or become untrusted.

### 21.5 Immediate Protective-Lease Reassignment After Failover

Rejected because an old offline owner may still be able to reach the broker.

### 21.6 Automatic Re-arm After Health Recovery

Rejected because service recovery does not prove economic-state reconciliation or operator intent.

### 21.7 Broker Credential in Every Execution Worker

Rejected because internal fencing cannot prevent stale direct broker access.

---

## 22. Consequences

### 22.1 Positive

- stale Safety Authority instances cannot create new risk;
- normal live authority fails closed during partition;
- degraded protection is bounded and exclusive rather than an unbounded cached grant;
- failover overlap is explicitly controlled;
- halt is stronger and more available than re-arm;
- broker egress becomes an enforceable trust boundary;
- authority decisions become replayable and auditable.

### 22.2 Negative

- availability decreases during authority uncertainty;
- failover may wait for old degraded leases to expire when hard fencing is unavailable;
- additional consensus, identity, and egress infrastructure is required;
- lease durations must be short and operationally conservative;
- some brokers cannot support safe degraded operation;
- recovery and re-arm become operationally heavier.

These costs are accepted because permissive availability is subordinate to safety.

---

## 23. Verification and Acceptance Criteria

ADR-002-003 SHALL remain Proposed until the following are demonstrated.

### SA-AC-001 — Duplicate Active Authority

Start two Safety Authority instances that both believe they are leader. Only the current epoch may produce an egress-accepted permissive capability.

### SA-AC-002 — Stale Leader Resume

Pause the leader, fail over, advance epoch, then resume the old leader. Every stale mutation and transmission attempt must be rejected.

### SA-AC-003 — Partition After Grant

Issue a normal live grant, partition the execution side from currentness verification, and attempt new risk. Transmission must be denied within the approved containment bound.

### SA-AC-004 — Degraded Protective Lease

Partition the normal authority path while a valid protective lease exists. Only in-scope protective actions within pre-committed capacity may pass.

### SA-AC-005 — Lease Expiry

Advance local monotonic time beyond the usable holdover. New actions must be rejected even if the signed wall-clock deadline appears valid.

### SA-AC-006 — Process Restart

Restart the degraded lease owner. The prior local holdover must not authorize new transmission.

### SA-AC-007 — Overlapping Failover

Attempt to assign the same protective scope to a new owner before hard fencing or lease-expiry fence completion. Assignment must fail.

### SA-AC-008 — Hard Fence

Demonstrate that a fenced old authority cannot mutate the Ledger, consume protective capacity, or reach broker transmission.

### SA-AC-009 — HALT Race

Race a valid halt against an already issued permissive capability. The halt must dominate before any later transmission.

### SA-AC-010 — Re-arm Gate

Attempt automatic re-arm after service recovery. Re-arm must fail until every prerequisite and dual-control approval is present.

### SA-AC-011 — Time Discontinuity

Inject wall-clock step, monotonic discontinuity, and long suspension. Offline permissive capability must fail closed.

### SA-AC-012 — Key Rotation and Revocation

Rotate or revoke authority signing identity. Old or unknown keys must not produce accepted permissive capabilities.

### SA-AC-013 — Egress Bypass

Verify that no strategy, research, operator UI, or stale execution identity can reach live broker ordering outside the fenced egress path.

### SA-AC-014 — Epoch Registry Failure

Make the epoch authority unavailable. No new permissive authority may be accepted; existing effects remain conserved.

### SA-AC-015 — Evidence Replay

Reconstruct the exact authority and fencing sequence for every test from durable evidence.

---

## 24. Required Metrics and Alerts

At minimum:

- current Safety Authority epoch by domain;
- active leader identity;
- epoch transition count and reason;
- stale-epoch rejection count;
- currentness-witness age;
- authority partition duration;
- normal risk denials caused by authority uncertainty;
- active degraded protective leases;
- remaining monotonic holdover per lease;
- overlapping-lease rejection count;
- hard-fence status;
- halt state and source;
- re-arm attempts and denials;
- egress capability-verification failures;
- authority key-rotation state;
- time-health status.

Critical alerts SHALL fire for:

- more than one apparent active leader;
- stale epoch accepted at any enforcement point;
- overlapping degraded lease ownership;
- live transmission without currentness proof;
- broker egress bypass;
- automatic or unauthorized re-arm;
- unknown time health while a degraded lease is active.

---

## 25. Implementation Constraints

A conforming implementation SHALL provide:

- linearizable epoch advancement;
- monotonic fencing tokens;
- final egress epoch enforcement;
- authenticated capability issuance and verification;
- replay protection;
- durable evidence;
- local monotonic lease invalidation rules;
- no direct live broker path outside the fence;
- deterministic safer-state precedence;
- explicit re-arm workflow.

An implementation based solely on heartbeat observation, Kubernetes leader election, a Redis lock without proven fencing, process-local booleans, or token signature validation without current-epoch proof is non-conforming.

---

## 26. Dependencies and Follow-Up Work

This ADR interfaces with:

1. ADR-002-001 — Degraded-Mode Protective Capacity;
2. ADR-002-002 — Aggregate Risk-Capacity Commitment Model;
3. ADR-002-004 — Broker Capability Requirements and Fallbacks;
4. ADR-002-008 — Trustworthy Time Architecture;
5. ADR-002-007 — Live Authorization, Limit Governance, and Re-arm;
6. ADR-002-005 — Intent, Transmission Attempt, Broker Order, and Knowledge State Model;
7. ADR-002-009 — Failure-Domain Isolation and Deployment Safety;
8. ADR-002-012 — Risk Capacity Ledger Persistence, Consensus, and Writer Fencing;
9. ADR-002-013 — Egress Gateway Credential, Route, and Commit-Proof Security;
10. ADR-002-014 — Hard Safety Envelope and Runtime Safety Profile Governance;
11. ADR-002-015 — Human Safety Authority, Dual Control, and Break-Glass Governance;
12. VER-002-001 — Safety Authority and Broker Capability Verification Evidence Specification.

---

## 27. Open Implementation Questions

The following may remain open while Proposed but must be resolved before Accepted:

1. What exact Authority Domain granularity is used?
2. Which conforming product and namespace allocation implement epoch ordering on ADR-002-012's Safety Commit Log without collapsing authority separation?
3. Which conforming ADR-002-013 credential, route, principal, and Commit-Proof mechanisms enforce currentness without a bypass or unsafe cache?
4. Which ADR-002-013 Hard Egress Fence is available per broker and credential model?
5. What is the maximum degraded lease duration per host time source?
6. What drift, suspension, and transport-delay assumptions are approved?
7. How is lease-exclusive scope represented and serialized?
8. How is a safer-state message authenticated when current permissive authority is unavailable?
9. How are authority keys rotated without overlapping permissive issuers?
10. Which ADR-002-015 effective-principal, quorum, authentication, delegation, approval-consumption, and Human HALT mechanisms implement re-arm dual control?

When a broker or runtime cannot meet the required fencing semantics, degraded or live scope must be reduced.

---

## 28. Approval Gate

ADR-002-003 may move from **Proposed** to **Accepted** only when:

- the Authority Domain is defined;
- epoch allocation and advancement are implemented and demonstrated;
- the applicable ADR-002-012 epoch-ordering and writer-fencing mechanism is implemented and its required RCLP evidence passes;
- the applicable ADR-002-013 final-egress confinement and Hard Egress Fence are implemented and their required EGRESS evidence passes;
- the applicable ADR-002-014 profile-generation, restrictive-precedence, compatibility, and rollback fences are implemented and their required SPG evidence passes;
- the applicable ADR-002-015 effective-human-principal, approval, Human HALT, break-glass, compromise, and recovery mechanisms are implemented and their required HAG evidence passes;
- ADR-002-016 authority, epoch, lease, partition, HALT, recovery, and denial evidence is durably captured, gap-detected, retained, and replayable without becoming authority, and applicable ERI evidence passes;
- stale-epoch rejection is enforced by Risk Capacity Ledger and broker egress;
- no direct live broker bypass exists;
- normal authority fails closed under partition;
- degraded protective lease overlap is prevented by hard fencing or expiry fencing;
- time holdover assumptions are documented and tested;
- halt precedence and explicit re-arm are demonstrated;
- all Critical acceptance criteria pass;
- VER-002-001 evidence entries are complete, immutable, and independently reviewed;
- residual broker-specific fencing limitations are recorded and approved.

Until then, the ADR authorizes implementation and verification work but not production live trading.
