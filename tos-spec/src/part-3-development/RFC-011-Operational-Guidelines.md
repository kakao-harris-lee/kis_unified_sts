# RFC-011 — Operational Guidelines

**Document ID:** RFC-011
**Title:** Operational Guidelines
**Version:** 0.1 Review Draft
**Status:** Review Draft — Development
**Classification:** Implementation-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Decision Authority:** Constrained by RFC-003 — Decision Framework
**Authoring Lifecycle:** Follows RFC-008 — Strategy DSL, RFC-009 — Agent Guide, RFC-010 — Testing Strategy
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-15

---

## 1. Abstract

This document defines the **Operational Guidelines**: the discipline that governs
how an operator runs an admitted strategy in production — monitoring it, responding
to degraded states, controlling re-arming, and coordinating recovery. Per RFC-000
§9 Implementation defines HOW SOFTWARE IS BUILT; RFC-011 occupies that layer as the
operational companion that closes the lifecycle RFC-008 (author the surface),
RFC-009 (author the strategy), and RFC-010 (test it) begin. RFC-011 is an
Implementation-layer specification that governs the distinct Operational Procedures
layer (RFC-000 §12); it constrains how operational procedures are conducted and does
not itself operate the system or become an operational authority.

RFC-011 is subordinate to RFC-000, RFC-001, RFC-002, every accepted ADR-002-xxx,
and RFC-003. Its governing thesis is inherited from philosophy §22 and RFC-002
§4.7: **operation is the exercise of bounded, revocable authority, never its
creation**, and **recovery is a new safety decision, never a side effect of
reconnecting** (philosophy §23). An operator may observe, halt, withhold re-arming,
invoke approved containment, and accept residual risk within an authenticated,
scoped, attributable, auditable envelope — and may not, through any operational
act, manufacture authority, silently bypass a safety control, or convert a restored
dependency into restored live authority.

RFC-011 defines an operational discipline. It selects no strategy, grants no
authority, and its acceptance does not authorize live operation.

---

## 2. Normative Authority

RFC-011's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document. RFC-011 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document. No operational procedure,
  runbook, or convenience defined here may weaken, bypass, or reinterpret any
  SAFE-xxx requirement, and an operator action never becomes a silent bypass of a
  constitutional safety control.
* **RFC-002 — Architecture** and the accepted **ADR-002-xxx** series own the
  authority, containment, re-arm, recovery, incident, and monitoring mechanisms
  RFC-011 operates. RFC-011 describes operating *within* them and defines none of
  them. The owners it operates within include, but are not limited to: live
  authorization and re-arm (ADR-002-007); human authority, dual control, and
  break-glass (ADR-002-015); safe startup and conservative resume (ADR-002-017);
  protective-order replacement and protection-gap control (ADR-002-011); safety
  waiver, deviation, and residual-risk governance (ADR-002-026 and its RFC-002
  §10.28 component); restricted-live promotion (ADR-002-025); incident containment
  and controlled shutdown (ADR-002-027); and continuous conformance monitoring
  (ADR-002-028).
* **RFC-003 — Decision Framework** and the model RFCs (RFC-004–007) define what the
  operated system decides; RFC-011 operates the running system and inherits every
  RFC-003 boundary.
* **RFC-008/009/010** define how a strategy is authored and tested; RFC-011 begins
  where an admitted, tested strategy is put into operation and does not re-open
  their concerns.
* Where RFC-011 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance, not resolved by a
  local operational convention.

RFC-011 defines an operational discipline. It creates no capacity, authority,
configuration, transmission permission, or protective status, and its acceptance
does not authorize live operation.

---

## 3. Scope and Non-Scope

This document governs:

* the operator's role and the bounded, revocable nature of operational authority;
* observing operational state — authority, capacity, exposure, reconciliation,
  degraded mode, evidence completeness;
* responding to degraded states within approved, exposure-aware procedures;
* controlling re-arming as an explicit human decision, never an automatic one;
* coordinating recovery as a new safety assessment, never a reversal of failure;
* the discipline of authenticated, scoped, attributable, auditable human action;
* the boundary between operating the system and every safety-enforcement, authority,
  and containment owner.

This document does not decide:

* how a strategy is authored (RFC-008/009) or tested (RFC-010);
* the decision process (RFC-003) or any model (RFC-004–007);
* live authorization, limit governance, or re-arm mechanics — ADR-002-007 owns
  those;
* human-authority, dual-control, or break-glass mechanics — ADR-002-015 owns those;
* safe-startup, recovery-barrier, or conservative-resume mechanics — ADR-002-017
  owns those;
* incident declaration, containment, controlled shutdown, or closure — ADR-002-027
  owns those;
* protective-order replacement, cancellation, or protection-gap control — the
  Cancellation Arbiter and Protective Action Controller under ADR-002-011 (RFC-002
  §9.1) own those;
* safety-waiver, deviation, or residual-risk-acceptance governance — ADR-002-026
  (and its RFC-002 §10.28 component) owns those;
* continuous conformance monitoring, telemetry, or alert escalation — ADR-002-028
  owns those;
* restricted-live promotion or production authorization — ADR-002-025 owns those;
* numeric limits, thresholds, schedules, ports, or capacities, which are approved
  configuration and the Verification Profile.

An operational practice that reaches beyond this scope — or that treats operating
the system as a source of authority — is non-conforming regardless of urgency.

---

## 4. Relationship to Vision and Philosophy

RFC-011 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Human authority is necessary but bounded** (philosophy §22, Vision §6.9). An
  operator may halt, withhold re-arming, invoke emergency procedures, accept
  residual risk, and investigate unknown state — and may not exercise unrestricted
  override; human action is authenticated, scoped, attributable, reviewable, and
  auditable.
* **Recovery is a new safety decision** (philosophy §23, RFC-002 §4.7). A restored
  dependency does not imply a safe system or restored live authority; re-arming is
  an explicit decision, not a side effect of reconnecting.
* **Explicit and revocable authority** (Vision §6.6, philosophy §14). Operational
  authority is explicit, scoped, time-bounded where appropriate, attributable, and
  revocable, and does not persist merely because it was valid in the past.
* **Exposure-aware safe operation** (Vision §6.4). Safe operation is not shutting
  down every action; it preserves control over existing exposure while preventing
  unverified new risk, and the operator distinguishes new-risk from
  risk-reducing from apparently-protective actions.
* **Observable and prevention-first** (Vision §9.3, philosophy §11). A hidden
  safety state is not a useful one; operation surfaces authority, capacity, trapped
  exposure, reconciliation, and degraded mode, and prioritizes preventing unsafe
  action over explaining it afterward.

Where an operational practice would contradict a Vision or Philosophy principle,
that practice is non-conforming.

---

## 5. Definitions

RFC-011 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, the
ADR series, and the RFC-003/008/009/010 framework terms. It SHALL NOT introduce
synonyms for any of them. The following terms are scoped to the operational
discipline and are non-authorizing.

* **Operator** — the authenticated human role responsible for monitoring live
  operation, responding to degraded states, and controlling re-arming (Vision
  §12.6). An Operator exercises bounded, revocable authority; the role holds no
  power to create authority or bypass a safety control.
* **Operational Act** — an authenticated, scoped, attributable, auditable action
  an Operator takes on the running system (observe, halt, withhold re-arm, invoke
  approved containment, accept residual risk). An Operational Act exercises
  existing authority; it does not manufacture it.
* **Re-arm Decision** — the explicit human decision to restore live authority
  after a halt, degradation, or recovery. A Re-arm Decision is never automatic and
  is owned by ADR-002-007; RFC-011 governs the operator discipline around
  requesting it, not the mechanism that grants it.

These terms describe an operational discipline. None grants authority, mutates
capacity, or authorizes live operation.

---

## 6. Operational Principles

A conforming operational discipline SHALL satisfy the following. They are
obligations on how the system is operated, not new enforcement; the enforcement,
authority, and containment points remain owned by RFC-002 and the ADR series.

1. **Operate authority; never create it.** An Operational Act exercises existing,
   bounded, revocable authority. No operational act, urgency, or convenience
   creates authority, capacity, live scope, or protective status (Vision §6.6;
   RFC-002 §9.1).
2. **Re-arming is an explicit decision.** Restoring live authority is a deliberate
   human Re-arm Decision through ADR-002-007, never an automatic consequence of a
   restart, reconnect, failover, or restored dependency (RFC-002 §4.7; philosophy
   §23).
3. **Recovery is a new assessment.** After failure, state may be stale, orders may
   be live, fills may have occurred, configuration may have changed, another
   instance may be active, or time may be invalid; recovery requires a fresh safety
   assessment, not a reversal of failure (philosophy §23; ADR-002-017).
4. **Human action is bounded.** Every Operational Act is authenticated, scoped,
   attributable, reviewable, and auditable, and SHALL NOT be an uncontrolled manual
   bypass of a safety control (philosophy §22; RFC-002 §7.5).
5. **Exposure-aware, not all-or-nothing.** Degraded response preserves control over
   existing exposure while preventing unverified new risk; the operator distinguishes
   new-risk from risk-reducing from apparently-protective actions (Vision §6.4).
6. **Uncertainty restricts operation.** Under unknown or unreconciled state the
   conforming operational posture narrows authority and withholds new risk, never
   expands it to preserve availability (philosophy §8; Vision §6.3, §11.8).
7. **Observe before acting.** An Operational Act follows from observed operational
   state — authority, capacity, exposure, reconciliation, degraded mode — not from
   assumption or component health (Vision §9.3; philosophy §16).

---

## 7. The Operator and Bounded Authority

The operator is part of the safety model, not an override of it. Operational
authority is real but strictly bounded, and RFC-011 exists to keep the exercise of
that authority inside the envelope the architecture defines.

* **Authority is exercised, not minted.** An Operator halts, withholds re-arming,
  invokes approved containment, and accepts residual risk using authority that was
  granted explicitly and remains revocable (Vision §6.6). Operating the system does
  not enlarge that authority.
* **Bounded by many dimensions.** Operational authority is limited by account,
  strategy, instrument, venue, operating mode, software version, safety
  configuration, risk capacity, and current safety state (Vision §6.6); an operator
  SHALL NOT act outside the dimension its authority is scoped to.
* **Human error is anticipated.** An operator can select the wrong account, misread
  exposure, apply the wrong configuration, or act under stress (philosophy §22);
  the discipline therefore keeps human action authenticated, scoped, attributable,
  and auditable, and defers to dual control and break-glass governance (ADR-002-015)
  where the architecture requires it.
* **Not a bypass path.** A human command SHALL NOT silently bypass a constitutional
  safety control (RFC-002 §7.5); an operator confronting a blocking control raises
  it through governance or approved break-glass (ADR-002-015), never by disabling
  the control.

The distinction the whole document turns on is philosophy §22's: human *authority*
is part of the model; uncontrolled manual *bypass* is not.

---

## 8. Monitoring and Observing Operational State

Operation depends on seeing the system honestly. RFC-011 requires the operator to
act on observed state, and defers the monitoring machinery itself to its owner.

* **Observe the load-bearing states.** The operator observes current authority,
  risk capacity, open and potentially live orders, trapped exposure, reconciliation
  status, safety configuration, degraded mode, and evidence completeness (Vision
  §9.3).
* **Monitoring is owned elsewhere.** Continuous conformance monitoring, telemetry
  integrity, and alert escalation are architecturally owned by ADR-002-028 (and its
  RFC-002 §10.30 component); RFC-011 governs the operator's response to what that
  monitoring surfaces, and SHALL NOT redefine the monitoring protocol or treat a
  `CONFORMING` snapshot as authority.
* **Health is not validity.** The operator SHALL NOT infer state validity, source
  continuity, or authority from component health, uptime, or last-known-good state
  (philosophy §16; ADR-002-018 §9); an observation is evidence, not permission.
* **Unknown is explicit.** Unknown or unreconciled state is treated as unknown, not
  optimistically resolved to keep operating; a visible failure is still a failure
  (philosophy §37.3; Vision §6.8, §11.8).

A hidden safety state is not an operationally useful safety state; operation begins
with honest observation.

---

## 9. Degraded Operation and Containment

Degraded operation is where operational discipline matters most, because the
temptation to restore availability is strongest exactly when the system is least
trustworthy.

* **Exposure-aware response.** Safe operation preserves control over existing
  positions, open orders, and margin obligations while preventing unverified new
  risk (Vision §6.4); the operator distinguishes actions that create new risk,
  preserve existing protection, reduce aggregate risk, or only appear protective
  while increasing margin/basis/liquidity/concentration risk.
* **Containment is separately owned.** Incident declaration, containment, controlled
  shutdown, and closure are owned by ADR-002-027; the independent Safety Authority's
  ability to suspend autonomous trading is constitutional (RFC-000 CONST-011). The
  operator invokes approved containment; it does not itself classify protection or
  clear a containment state.
* **Protective classification is not the operator's.** An operator SHALL NOT label
  an action protective to obtain protective treatment; protective classification is
  owned exclusively by the Protective Action Controller under ADR-002-001 §6.
* **Do not optimize away safety capacity.** Reserved capacity, margin headroom, and
  conservative limits are not waste to be reclaimed under pressure; they preserve
  containment capability (Vision §11.7).

Degraded operation narrows what the system may do; the operator's job is to keep it
narrowed until safety is re-established, not to widen it for convenience.

---

## 10. Re-arming and Recovery

This section is the operational heart of RFC-011: the point where a stopped or
degraded system is returned to live operation. It is where the "recovery is a new
safety decision" thesis is enforced in practice.

* **No automatic re-arm.** Restart, reconnect, failover, or restored connectivity
  SHALL NOT automatically restore live trading authority (RFC-002 §4.7); re-arming
  is an explicit human Re-arm Decision through ADR-002-007, withheld until its
  prerequisites hold.
* **Recovery is reassessment, not reversal.** When a dependency returns, the
  operator treats state as possibly stale, orders as possibly live, fills as
  possibly occurred, configuration as possibly changed, another instance as
  possibly active, and time as possibly invalid, and requires a fresh assessment
  (philosophy §23; ADR-002-017).
* **Prerequisites before authority.** The system restores authority only after
  re-establishing valid configuration, trustworthy time, live authorization,
  reconciled positions, reconciled open orders, valid safety authority, and known
  aggregate risk (Vision §7.4); the operator withholds the Re-arm Decision until
  these hold, and the safe-startup/recovery-barrier mechanics remain owned by
  ADR-002-017.
* **Recovery does not duplicate exposure.** Recovery SHALL NOT silently create a
  second execution path or duplicate exposure; retries, reconnects, restarts, and
  duplicated events SHALL NOT multiply authorized exposure (Vision §7.4; RFC-001
  SC-030 Execution Integrity Claim). Resolving a possible duplicate-instance or
  unknown-order condition precedes any re-arm.
* **Withholding is a valid outcome.** Choosing not to re-arm is a conforming
  operational decision; missed trading opportunity is an acceptable consequence of
  unresolved critical uncertainty (Vision §9.6; philosophy §8).

Re-arming is a decision the operator makes deliberately, on evidence, through the
owning authority — never a state the system drifts back into on its own.

---

## 11. The Operations↔Safety Boundary

This section is the load-bearing safety content of RFC-011. It restates, at the
operational layer, the separation that RFC-002 §9.1, §7.5, the ADR series, and
philosophy §22 enforce. Every item is a hard boundary.

An operator, runbook, operational tool, or Operational Act SHALL NOT:

1. create, enlarge, or self-grant trading authority, capacity, or live scope; these
   are issued only by their owners and remain revocable (Vision §6.6; RFC-002
   §9.1);
2. silently bypass, disable, or degrade a constitutional safety control or the
   independent Safety Authority (RFC-000 CONST-011; RFC-002 §7.5; philosophy §22);
3. automatically re-arm live authority on restart, reconnect, failover, or restored
   connectivity; re-arming is an explicit human decision (RFC-002 §4.7;
   ADR-002-007);
4. treat a restored dependency, a green monitor, or restored connectivity as a
   safe system or as restored live authority (philosophy §23; ADR-002-028);
5. commit, reserve, mutate, or release risk capacity by operational action; only
   the RCL mutates capacity (ADR-002-002; RFC-002 §9.1);
6. classify an action as protective, or obtain protective treatment by labeling;
   protective classification is owned by the Protective Action Controller
   (ADR-002-001 §6; RFC-002 §9.1);
7. clear a HALT, containment state, incident, monitoring gap, or restrictive latch
   that its owner has not cleared (ADR-002-027; ADR-002-028);
8. issue Live Authorization or a Transmission Capability, or transmit an order, by
   operational action (ADR-002-007; RFC-002 §9.1 — Arm live scope, Transmit);
9. re-arm or restore production scope while position, open-order, account,
   configuration, venue, or critical-input state is unknown or unreconciled
   (Vision §7.4; RFC-001 SC-040 State Integrity Claim);
10. act as an uncontrolled manual bypass rather than an authenticated, scoped,
    attributable, auditable action, or use break-glass outside its governance
    (philosophy §22; RFC-002 §7.5; ADR-002-015);
11. infer state validity, source continuity, or authority from component health,
    uptime, or last-known-good state (ADR-002-018 §9; philosophy §16);
12. reclaim reserved protective capacity, margin headroom, or conservative limits
    for throughput under operational pressure (Vision §11.7; philosophy §21);
13. accept, record, or act on residual risk outside ADR-002-026 governance, or
    treat an operator's acceptance of residual risk as a waiver of a Critical or
    Non-Waivable safety requirement, as satisfaction of a failed requirement, or as
    an enlargement of scope; residual-risk acceptance is an independently approved,
    exact-scope, non-authorizing safety artifact (ADR-002-026; RFC-002 §10.28);
14. cancel, remove, reduce, replace, or weaken a required protective order, or
    create a protection gap, by operational action; the protective-order lifecycle
    is owned by the Cancellation Arbiter and the Protective Action Controller
    (ADR-002-011; RFC-002 §9.1).

The single generalizing rule (RFC-002 §9.1; philosophy §22): human authority is
part of the safety model, but it is bounded, authenticated, and auditable — never
an uncontrolled override. RFC-011 occupies only the operating role: it exercises
authority the architecture grants and keeps that exercise inside the envelope,
never widening it.

---

## 12. Relationship to RFC-008, RFC-009, RFC-010, and the ADR Owners

RFC-011 is the operational companion that closes the Part 3 lifecycle. The pointers
below are non-normative scope markers; RFC-011 SHALL NOT define their content.

* **RFC-008 — Strategy DSL / RFC-009 — Agent Guide / RFC-010 — Testing Strategy.**
  The strategy RFC-011 operates was authored within RFC-008's surface under
  RFC-009's discipline and demonstrated under RFC-010; RFC-011 begins at an
  admitted, tested strategy and does not re-open authoring or testing.
* **ADR-002-007 (Live Authorization and Re-arm).** Owns the re-arm and
  live-authorization mechanism the operator's Re-arm Decision requests.
* **ADR-002-015 (Human Safety Authority, Dual Control, Break-Glass).** Owns the
  human-authority mechanics RFC-011's operator discipline works within.
* **ADR-002-017 (Safe Startup, Recovery Barrier, Conservative Resume).** Owns the
  recovery-barrier and conservative-resume mechanics RFC-011's recovery discipline
  defers to.
* **ADR-002-027 (Incident, Containment, Controlled Shutdown).** Owns the incident
  and containment lifecycle the operator invokes.
* **ADR-002-011 (Protective Replacement and Protection-Gap Control).** Owns the
  protective-order lifecycle — the Cancellation Arbiter and Protective Action
  Controller — that an operator invokes but never overrides or bypasses.
* **ADR-002-026 (Safety Waiver, Deviation, and Residual-Risk Governance).** Owns
  the waiver, deviation, and residual-risk-acceptance governance within which any
  operator acceptance of residual risk SHALL occur.
* **ADR-002-028 (Continuous Conformance Monitoring).** Owns the runtime monitoring
  the operator observes and responds to.
* **ADR-002-025 (Restricted-Live Promotion).** Owns the promotion that precedes
  full-scope operation.

RFC-011 operates the system these owners define; it defines none of them and
SHALL NOT be read to grant what they alone can grant.

---

## 13. Requirements Traceability

RFC-011 discharges implementation-layer operational obligations that RFC-000,
RFC-001, RFC-002, and RFC-003 assign to the operating discipline. This table is an
initial allocation.

| Requirement | Discharge in RFC-011 |
|---|---|
| RFC-000 §9 layering (Implementation defines HOW SOFTWARE IS BUILT) | RFC-011 confined to the operating discipline; defines no WHY/WHAT/HOW-DECISIONS content (§§1, 2) |
| RFC-000 CONST-011 (Independent Safety Authority) | operation never disables/bypasses the independent authority; containment stays separately owned (§§9, 11.2) |
| RFC-002 §4.7 (Recovery Without Automatic Trust) | no automatic re-arm on restart/reconnect/failover; explicit Re-arm Decision (§§6, 10, 11.3) |
| RFC-002 §7.5 (Human Operations Boundary) | operator action authenticated/scoped/attributable/auditable; no silent bypass (§§7, 11.2, 11.10) |
| RFC-002 §9.1 authority ownership | operation exercises but never creates authority/capacity/protection/live scope (§§6, 7, 11) |
| RFC-001 SC-040 (State Integrity Claim) | no re-arm/scope-restore while state is unknown/unreconciled (§§10, 11.9) |
| RFC-001 SC-030 (Execution Integrity Claim) | recovery does not multiply authorized exposure or create a second execution path (§10) |
| RFC-003 §6 (uncertainty restrictive) | degraded/unknown state narrows operational authority (§§6, 8, 9) |
| ADR-002-007 (live authorization / re-arm) | Re-arm Decision requests the owned mechanism; operator never issues live authority (§§5, 10, 11.8) |
| ADR-002-015 (human authority / dual control / break-glass) | operator discipline works within it; break-glass only under its governance (§§7, 11.10) |
| ADR-002-017 (safe startup / recovery barrier) | recovery is a new assessment; prerequisites before authority (§§6, 10) |
| ADR-002-027 (incident / containment / shutdown) | operator invokes; does not classify protection or clear containment (§§9, 11.7) |
| ADR-002-028 (continuous conformance monitoring) | operator observes/responds; does not own or redefine monitoring (§§8, 11.4, 11.7) |
| ADR-002-001 §6 (protective classification) | operator never labels an action protective (§§9, 11.6) |
| ADR-002-011 (protective replacement / protection-gap control) | operator never cancels/removes/weakens a required protective order or creates a protection gap (§§9, 11.14) |
| ADR-002-002 (Aggregate Risk-Capacity Commitment Model; RCL transition authority) | operation never mutates capacity; only the RCL mutates capacity (§11.5) |
| ADR-002-026 (safety waiver / deviation / residual-risk governance) | operator accepts residual risk only within ADR-002-026 governance, never as a self-waiver of a Critical/Non-Waivable requirement (§§3, 11.13) |
| ADR-002-025 (restricted-live promotion) | promotion precedes full-scope operation; the operator does not promote (§§2, 3, 12) |
| ADR-002-018 §9 (health is not validity) | operator infers no validity/authority from component health (§§8, 11.11) |
| Vision §6.4, §6.6, §6.9, §7.4, §9.3, §11.7; philosophy §§8, 11, 16, 21, 22, 23 | exposure-aware, revocable-authority, recovery-is-a-new-decision, observe-first operationalized (§§4, 6–10) |

RFC-011 introduces no SAFE-xxx requirement and no numeric bound. It relies entirely
on the enforcement, authority, and containment points already defined upstream.

---

## 14. Open Questions

These questions are open while RFC-011 is a Review Draft. They SHALL NOT be
resolved by informal operational convention.

1. What minimum reconciled-state checklist (positions, open orders, account,
   configuration, venue, critical input, time, single-instance) must an operator
   confirm before requesting a Re-arm Decision, and where is that checklist bound
   relative to ADR-002-017's recovery barrier? *(Resolved by ADR-DEV-012: a nine-item
   positively-confirmed checklist; any unreconciled item withholds; it sits before, and
   never replaces, the ADR-002-017 barrier and the ADR-002-007 grant.)*
2. How is the boundary drawn between an approved operator response to a degraded
   state and a break-glass action requiring ADR-002-015 dual-control governance?
   *(Resolved by ADR-DEV-013: the line is the operator's scoped authority — anything
   that would enlarge authority, act out of scope, or touch a control is break-glass
   under ADR-002-015 and cannot expand.)*
3. What operator-facing observability is required so that authority, capacity,
   trapped exposure, reconciliation, and degraded mode are visible without the
   dashboard itself becoming a trusted authority (Vision §9.3; ADR-002-028)? *(Resolved
   by ADR-DEV-014: the load-bearing state is observable, but the surface is evidence,
   not authority — validity is never inferred from a green dashboard/snapshot/health.)*
4. How does the operator discipline represent "withhold re-arm" as a first-class,
   recorded, auditable outcome rather than an absence of action (§10; philosophy
   §8)? *(Resolved by ADR-DEV-014: a withheld re-arm is a first-class, recorded,
   attributable, auditable outcome with its rationale, whose missed opportunity is
   acceptable.)*
5. What is the relationship between operator-initiated containment and the
   independently-owned Safety Authority / incident governance (ADR-002-027), so
   that operator action complements rather than pre-empts the owner? *(Resolved by
   ADR-DEV-013: the operator invokes restrictive containment using normal authority
   and complements — never declares, closes, clears, or pre-empts — the ADR-002-027
   lifecycle and the CONST-011 independent authority.)*
6. How are operator authority scopes (account, strategy, instrument, venue, mode,
   software version, safety configuration) expressed and revoked, consistent with
   Vision §6.6 and ADR-002-015? *(Resolved by ADR-DEV-015: authority is expressed along
   explicit dimensions, an act must be within current scope on every applicable
   dimension, and revocation is immediate and complete.)*

Unresolved questions reduce, and do not expand, the conforming operational posture.

---

## 15. Review History

### v0.1 — Initial Draft

* Established RFC-011 as the Implementation-layer Operational Guidelines: the
  operational companion that closes the RFC-008 → RFC-009 → RFC-010 → RFC-011
  Part 3 lifecycle, governing how an admitted, tested strategy is operated.
* Set the governing thesis from philosophy §22 and RFC-002 §4.7 — **operation
  exercises bounded, revocable authority and never creates it; recovery is a new
  safety decision, never a side effect of reconnecting** (philosophy §23) — and
  distinguished bounded human authority from uncontrolled manual bypass (§7).
* Defined observation of load-bearing operational state deferring monitoring to
  ADR-002-028 (§8), exposure-aware degraded operation deferring containment to
  ADR-002-027 (§9), and the re-arm/recovery discipline deferring the mechanism to
  ADR-002-007/017 with no automatic re-arm (§10).
* Restated the boundary as twelve prohibitions on operational action (§11;
  expanded to fourteen by the independent review below), each traced to RFC-002
  §9.1/§7.5/§4.7, RFC-000 CONST-011, RFC-001 SC-030/SC-040, and
  ADR-002-001/002/007/011/015/017/018/026/027/028.
* Marked scope relationships back to RFC-008/009/010 and to the ADR owners without
  pre-empting them (§12).
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with
  no Critical finding, restoring RFC-011 to the EV-L0 standard applied to RFC-008
  and RFC-009 (the earlier self-review, run while the independent-reviewer dispatch
  was unavailable, is superseded). Twenty-three adversarial sequences were
  attempted — operator self-grant of authority/capacity/live scope, silent bypass
  of a constitutional safety control, automatic re-arm on reconnect/failover, a
  restored dependency or green monitor treated as restored live authority, capacity
  mutation by operational action, a protective self-label, clearing an owner's
  HALT/containment, issuing Live Authorization or transmitting by operational
  action, re-arm under unreconciled state, break-glass outside governance, authority
  inferred from component health, and reclaiming reserved protective capacity among
  them — and the twelve original boundary items were confirmed to block their
  targets; every load-bearing citation was verified against source, including
  CONST-011 as the Independent Safety Authority and SC-030/SC-040. Two Major
  findings were resolved. (M1) "Accept residual risk" was listed as an operator
  authority (§§1, 5, 7) with no architectural owner — now bound to ADR-002-026 and
  its RFC-002 §10.28 component in §§2, 3, 12, 13 and by a new boundary item (§11.13)
  forbidding residual-risk acceptance outside that governance or as a self-waiver of
  a Critical/Non-Waivable requirement. (M2) The boundary lacked an explicit
  prohibition on an operator cancelling or removing a required protective order —
  now §11.14 (protection-gap creation), owned by the Cancellation Arbiter and
  Protective Action Controller (ADR-002-011; RFC-002 §9.1), with §§2, 3, 12, 13
  pointers. Minor citation-precision fixes were applied: §11.8's operator
  transmission prohibition now cites RFC-002 §9.1 (Arm live scope, Transmit) rather
  than the strategy/environment-scoped §7.3/§7.6; the §13 ADR-002-002 label was made
  precise and ADR-002-025 gained a §13 row; and §1 now states that RFC-011 is an
  Implementation-layer specification governing the distinct Operational Procedures
  layer (RFC-000 §12). The review is EV-L0 only and confers no acceptance or
  live-readiness.
* Governance note (inherited citation imprecision — RESOLVED). As recorded from
  RFC-008 onward, §2's citation for "SHALL NOT redefine constitutional intent" now
  points to RFC-000 §9, where the literal phrase appears (§12 states the cognate
  "reinterpret higher-level intent"); the series-wide imprecision across RFC-003
  through RFC-011 was corrected consistently in a single companion change.
