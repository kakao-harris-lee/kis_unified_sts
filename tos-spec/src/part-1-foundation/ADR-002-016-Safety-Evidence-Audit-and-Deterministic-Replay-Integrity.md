# ADR-002-016 — Safety Evidence, Audit, and Deterministic Replay Integrity

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Safety-evidence identity, capture boundaries, durability, ordering, provenance, integrity, completeness, gap detection, retention, redaction, access, deterministic replay, incident reconstruction, failure behavior, recovery, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-031, SAFE-051, SAFE-052, and §11; RFC-002 §§4.2, 10.16, 15, 23, 25, and 29; VER-002-001 §§2–9 and 221–223
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-010, SAFE-011, SAFE-020 through SAFE-025, SAFE-030, SAFE-031, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-001 through ADR-002-015

---

## 1. Decision

The TOS SHALL preserve every safety-relevant proposal, decision, denial, authority transition, capacity transition, transmission attempt, broker observation, non-trade change, recovery action, and human action as an immutable, attributable, integrity-protected **Safety Evidence Record**. Records SHALL be connected by explicit causal identities and retained in a form from which an independent implementation can reconstruct the safety-relevant decision chain.

Evidence, audit, monitoring, and replay are detective and recovery controls. They SHALL NOT create approval, capacity, Live Authorization, protective classification, broker-transmission authority, reconciliation truth, or Final Quantity Proof. A valid Evidence Commit Receipt proves only that the identified record was durably accepted under the applicable Evidence Integrity Policy. It does not prove that the recorded decision was correct or authorized.

For a new risk-increasing broker transmission, final egress SHALL prove that the required pre-effect evidence and `SEND_STARTED` record are durably committed before the first broker-directed byte. An unavailable, stale, contradictory, or unverifiable evidence path cannot be bypassed by buffering in ordinary application memory, logging asynchronously, or assuming later recovery. It blocks new risk in the affected scope.

Restrictive HALT and already-authorized containment SHALL remain asymmetrically available through a separately bounded, durable emergency evidence path at the enforcing boundary. That path SHALL NOT create permissive authority. If an economic transmission cannot be durably recorded at any approved path, it SHALL NOT be initiated; existing protection SHALL NOT be blindly cancelled, and all uncertain prior attempts remain potentially live and conservatively capacity-covered.

Evidence-pipeline unavailability SHALL NEVER delay or reject a valid restrictive HALT. The enforcing monotonic deny latch or Hard Egress Fence is the preventive state and the primary source of its emergency evidence; if the durable emergency journal cannot accept the command, egress SHALL apply the restriction and hard-fence all new transmissions, raise a Critical Evidence Gap, and remain non-live through recovery. Later evidence reconciliation records the already-effective restriction and does not create it.

Missing evidence is not proof that an action did not occur. Missing broker acknowledgement is not proof of non-acceptance. Cancel acknowledgement is not Final Quantity Proof. Evidence expiry, compaction, store failover, restore, or replay does not expire economic effect, release capacity, clear UNKNOWN, or re-arm authority.

---

## 2. Context

RFC-001 SAFE-051 requires traceable evidence for every proposed, approved, rejected, transmitted, acknowledged, filled, cancelled, and recovered action. SAFE-052 requires replay and incident reconstruction. RFC-002 §10.16 assigns immutable retention and reconstruction to the Evidence Store, while VER-002-001 defines the artifacts required to claim verification.

Those rules do not yet decide:

- where evidence must be captured relative to irreversible economic effect;
- what a durable evidence receipt proves and, equally important, what it cannot prove;
- how duplicates, partial writes, delayed projections, schema changes, and source disagreement are represented;
- how causal ordering is reconstructed without trusting synchronized wall clocks;
- how deletion, replacement, rollback, backup restore, insider mutation, and split history are detected;
- how secrets and personal information are redacted without destroying verification value;
- when compaction is safe and which tombstones must outlive retry and economic-effect horizons;
- how a replay capsule binds code, configuration, broker, identity, authority, capacity, time, and fault inputs;
- how evidence gaps fail closed without making the Evidence Store an economic authority;
- how evidence infrastructure recovers without reviving prior permission.

Without a dedicated contract, an implementation can produce excellent-looking audit logs while losing the one rejected decision, pre-send record, late fill, external order, stale epoch, or recovery transition needed to prove safety. It can also make a logging service a hidden authorization service, or allow a replay system to overwrite live state. This ADR closes those paths.

---

## 3. Decision Drivers

1. Prevent any broker effect from outrunning the evidence required to reconstruct its authorization and capacity lineage.
2. Preserve failed, denied, contradictory, and inconclusive outcomes as faithfully as successful outcomes.
3. Detect omission, mutation, truncation, rollback, fork, and unauthorized deletion.
4. Reconstruct causality without treating cross-host wall time as a total order.
5. Keep evidence separate from preventive authority and economic truth ownership.
6. Preserve human, software, configuration, broker, deployment, time, and identity provenance.
7. Permit independent deterministic replay across software and schema evolution.
8. Protect credentials, signing material, personal data, and broker secrets while retaining verifiability.
9. Fail closed for new risk when evidence durability or completeness is unknown.
10. Prevent evidence recovery, restore, or replay from reviving authority or erasing economic effect.

---

## 4. Scope and Non-Scope

This ADR decides:

- the canonical Safety Evidence Envelope and Evidence Integrity Policy contracts;
- source identity, event identity, causation, correlation, and ordering requirements;
- pre-effect, post-effect, denial, observation, and recovery capture boundaries;
- durable commit receipt semantics and emergency evidence-path constraints;
- append-only integrity, anchoring, fork detection, gap detection, and chain of custody;
- raw versus normalized evidence and non-destructive correction;
- replay capsule, deterministic-boundary, comparison, and divergence rules;
- retention, legal hold, compaction, redaction, access, export, and deletion governance;
- partition, outage, compromise, backup, restore, and disaster-recovery behavior;
- acceptance cases and evidence obligations.

This ADR does not decide:

- whether a broker observation is sufficient Final Quantity Proof, which remains ADR-002-004 and ADR-002-006;
- per-field reconciliation confidence or conservative bounds, which remain ADR-002-006;
- capacity truth or mutation, which remain exclusively with the RCL under ADR-002-002 and ADR-002-012;
- broker transmission permission, which remains with ADR-002-007, ADR-002-012, and ADR-002-013;
- concrete storage, streaming, cryptographic, key-management, or archival products;
- numeric persistence, detection, recovery, retention, and replay bounds, which require an approved Verification Profile and Evidence Integrity Policy;
- authority to modify live state during replay. Replay is isolated and non-authorizing.

---

## 5. Definitions

### 5.1 Safety Evidence Record

One immutable record of a safety-relevant fact, proposal, decision, denial, transition, observation, command, transmission boundary, recovery step, or verification result, expressed in a canonical Safety Evidence Envelope.

### 5.2 Safety Evidence Envelope

The versioned canonical wrapper binding record identity, record class, source principal, source continuity, causation, subject identities, authority and configuration generations, payload digest, schema, trustworthy-time evidence, local ordering evidence, integrity data, and confidentiality classification.

### 5.3 Evidence Integrity Policy

The separately governed artifact defining required record classes, capture boundaries, durability class, integrity algorithm, anchor cadence, gap bounds, retention, access, redaction, export, key lifecycle, and replay requirements for one scope. A missing, expired, incompatible, or unapproved policy cannot authorize new risk.

### 5.4 Evidence Commit Receipt

Consumer-verifiable proof that one exact canonical record digest was durably accepted by an approved evidence path under one Evidence Integrity Policy generation and continuity identity. It grants no economic or operational authority.

### 5.5 Causal Link

An explicit typed edge from a record to a predecessor such as intent, approval, authority, capacity commit, capability claim, profile activation, transmission attempt, broker event, correction, HALT, or recovery action. A timestamp alone is not a Causal Link.

### 5.6 Evidence Gap

A missing, duplicated-with-conflict, truncated, unverifiable, out-of-policy, or unexplained record or sequence range that prevents complete reconstruction of a required safety chain.

### 5.7 Integrity Anchor

An authenticated commitment over an ordered record segment or Merkle-equivalent structure, bound to store continuity, policy generation, key generation, and predecessor anchor. An anchor detects mutation; it does not validate the safety decision.

### 5.8 Replay Capsule

An immutable manifest of the exact evidence set, baseline artifacts, deterministic inputs, allowed nondeterminism, software, schemas, configuration, identities, broker profile, time evidence, and comparison rules used by an isolated replay.

### 5.9 Normalized Evidence View

A derived, versioned interpretation of raw evidence. It SHALL reference raw record digests and transformation identity. It never overwrites or silently corrects raw evidence.

### 5.10 Redaction View

An access-controlled derived representation that removes or tokenizes prohibited data while retaining the original canonical digest, field-presence commitments, ordering, quantities, economic effect, and identities needed for the approved review purpose.

---

## 6. Safety Invariants

### ERI-INV-001 — Evidence Is Not Authority

No record, receipt, anchor, dashboard, audit result, replay result, or incident report creates approval, capacity, Live Authorization, protective classification, broker authority, or re-arm permission.

### ERI-INV-002 — Economic Effect Cannot Outrun Required Evidence

Every risk-increasing live transmission has durable pre-effect and `SEND_STARTED` evidence before the first broker-directed byte. Ambiguity after that boundary remains potentially live.

### ERI-INV-003 — Missing Evidence Is Conservative

Absence, lag, query omission, expired retention, or a broken causal chain never proves non-acceptance, cancellation, zero remaining quantity, capacity release, or no exposure.

### ERI-INV-004 — Denials and Failures Are First-Class

Rejected, failed, timed-out, contradictory, inconclusive, quarantined, and security-relevant actions are retained with the same integrity requirements as successful actions.

### ERI-INV-005 — Raw Evidence Is Append-Only

Correction, normalization, redaction, supersession, and schema migration create linked records or views. They never mutate or replace the original record.

### ERI-INV-006 — Causality Is Explicit

Safety-relevant ordering uses authority, ledger, egress, source-continuity, and causal sequence evidence. Cross-host wall-clock comparison alone never establishes order.

### ERI-INV-007 — Forks and Gaps Fail Closed

Unknown, conflicting, rolled-back, truncated, or forked evidence history blocks new risk for affected scope until conservatively reconciled and independently reviewed as required.

### ERI-INV-008 — Replay Is Isolated

Replay cannot call live broker routes, mutate authoritative state, consume live approval or capability, release capacity, clear HALT, or issue Live Authorization.

### ERI-INV-009 — Replay Divergence Cannot Pass

Missing inputs, unbounded nondeterminism, schema incompatibility, digest mismatch, or a different safety-relevant result is `INCONCLUSIVE` or `FAIL`, never `PASS`.

### ERI-INV-010 — Redaction Preserves Verifiability

Redaction cannot alter canonical identity or silently remove fields required to establish ordering, quantity, authority, economic effect, or reviewer independence.

### ERI-INV-011 — Retention Does Not Define Economic Lifetime

Evidence retention, expiry, compaction, archival, deletion approval, or legal-hold release never expires an order, attempt, exposure, UNKNOWN state, commitment, or other economic effect.

### ERI-INV-012 — Recovery Does Not Revive

Store failover, backup restore, key recovery, replay completion, gap repair, or evidence-service recovery cannot restore prior authority or automatically re-arm.

### ERI-INV-013 — Secret Safety

Evidence never stores usable broker credentials, signing keys, authentication secrets, or unrestricted bearer tokens. Necessary identifiers are non-authorizing references or protected commitments.

### ERI-INV-014 — Evidence Administration Is Not Trading Authority

Evidence writers, readers, administrators, retention operators, key custodians, and replay operators cannot mutate RCL capacity or reach a live broker route by virtue of those roles.

---

## 7. Authority Ownership and Separation

| Function | Sole or primary authority | Evidence-system limitation |
|---|---|---|
| Capacity mutation and release | RCL | records outcome; cannot request an ungoverned transition or overwrite state |
| Safety authority and Live Authorization | Safety Authority / Live Authorization Service | records issuance, denial, revocation, and generation; receipt creates no authority |
| Human approval | ADR-002-015 governed services and effective principals | records exact artifacts and consumption; cannot count principals or approve |
| Safety configuration activation | ADR-002-014 committed activation protocol | records artifact and transition lineage; cannot activate |
| Protective classification | Protective Action Controller | records proof inputs and result; cannot self-classify from an audit label |
| Broker transmission | Final Egress Trust Boundary | validates required durability and records send boundary; evidence service cannot transmit |
| Broker and account facts | Broker evidence evaluated under ADR-002-004/006 | stores provenance and conflict; cannot declare a single source true |
| Evidence integrity and retention | Evidence Store under Evidence Integrity Policy | owns record custody only; never owns economic truth |
| Replay comparison | isolated Replay and Evidence Service | produces non-authorizing results only |

No evidence administrator or replay principal may possess both usable live-order authority and a broker-order route. Separation SHALL be evaluated by effective control paths, not service names.

---

## 8. Canonical Safety Evidence Envelope

Every record SHALL bind at least:

- globally unique `evidence_record_id` and stable idempotency identity;
- record class and schema identity/version;
- Evidence Integrity Policy identity, generation, and digest;
- source workload or human principal, effective-control reference where applicable, workload identity, environment, deployment, process continuity, and key generation;
- account, broker, venue, instrument, strategy, Safety Cell, Capacity Domain, and authority scope where applicable;
- intent, attempt, broker order, fill, position, capacity allocation, command, approval, profile, HALT, and non-trade identities where applicable;
- exact previous and resulting local authoritative revisions where the source owns a state transition;
- typed Causal Links and correlation identities;
- raw payload digest, canonical payload digest, content type, byte length, and encryption/redaction classification;
- source-local monotonic sequence or authoritative log position;
- trustworthy-time snapshot identity, wall-time observation, uncertainty, and continuity identity where time is relevant;
- integrity key identity, signature or MAC where applicable, predecessor or segment commitment, and receipt identity;
- outcome class including accepted, denied, failed, ambiguous, quarantined, superseded, or observed;
- retention class and legal-hold references;
- explicit `creates_authority: false` and `may_mutate_live_state: false` semantics for evidence artifacts.

Unknown optional data SHALL be explicit. Missing mandatory data invalidates the record for its required use and creates an Evidence Gap; it SHALL NOT be filled from a convenient downstream projection without provenance.

---

## 9. Capture Boundaries and Required Record Classes

Evidence SHALL be captured at the component that owns the decision or irreversible boundary, not inferred solely from downstream analytics. At minimum:

1. **proposal boundary** — originating intent, context, requested scope, and source;
2. **input boundary** — critical input identities, units, source, time, and validation outcome;
3. **approval boundary** — request, attestation, quorum, denial, abstention, invalidation, and consumption;
4. **authority boundary** — grant, denial, restriction, epoch/generation, expiry, revocation, and HALT;
5. **capacity boundary** — every accepted and rejected RCL command, committed revision, state digest, and Commit Proof;
6. **protective boundary** — classification proof, lease, ownership, replacement gap/overlap, and denial;
7. **egress pre-effect boundary** — exact request bytes or protected canonical digest, capability, proof, principal, credential reference, route, and validation result;
8. **irreversible send boundary** — durable claim, `SEND_STARTED`, first-byte transition, ambiguity, and retry decision;
9. **broker observation boundary** — raw response/event/query page identity, session, completeness metadata, correction, and provenance;
10. **reconciliation boundary** — per-field evidence, conservative bound, conflict, confidence, proof rule, and owner transition request;
11. **configuration boundary** — artifact, canonical digest, approval, compatibility, activation, restriction, expiry, rollback, restore, and consumer result;
12. **recovery boundary** — startup barrier, inventory, UNKNOWN, external activity, gap, decision, and governed re-arm request;
13. **verification boundary** — baseline, fault injection, raw artifacts, invariant result, review, and supersession.

Rejection evidence SHALL be produced before returning or dropping the rejected request whenever the component remains available. A crash that prevents emission is detected as a gap by sequence, causal, or counterpart reconciliation.

---

## 10. Durability and Effect Ordering

### 10.1 Durability Classes

The Evidence Integrity Policy SHALL assign each record class one of:

```text
PRE_EFFECT_DURABLE     committed before the associated irreversible effect
POST_EFFECT_BOUNDED    committed within an approved bound after an observation
EMERGENCY_DURABLE      committed to an independent enforcing-boundary journal
DERIVED_REBUILDABLE    reproducible view whose raw inputs remain retained
```

Ordinary process memory, best-effort metrics, an unflushed file, a message producer acknowledgement without durable quorum or equivalent proof, and a downstream dashboard do not satisfy durable commitment.

### 10.2 Risk-Increasing Transmission

Final egress SHALL validate an Evidence Commit Receipt for the exact pre-effect request and SHALL durably record the capability claim and `SEND_STARTED` before the first broker-directed byte. The receipt is necessary but never sufficient: current authority, capacity, time, configuration, broker capability, principal, route, and request binding remain mandatory.

If persistence is unavailable or the receipt is stale, mismatched, unverifiable, or from an obsolete policy/store continuity, new risk is denied. Retrying evidence persistence does not extend authority validity or the capability claim-to-send bound.

### 10.3 HALT and Protective Containment

Authenticated restrictive HALT SHALL not depend solely on the ordinary evidence pipeline. The enforcing egress or Safety Cell SHALL have a monotonic `EMERGENCY_DURABLE` journal sufficient to record command identity, principal, scope, generation, local latch, and later reconciliation.

The restrictive latch is applied before waiting for ordinary evidence acknowledgement. If the emergency journal itself is unavailable or ambiguous, the receiver SHALL retain or apply the most restrictive local state, hard-fence new transmission, and create a gap for later reconciliation. It SHALL NOT reject HALT, clear an existing latch, or fall back to a permissive path.

An economic protective request still requires RCL, protective classification, authority, broker, and final-egress enforcement. Emergency evidence availability cannot convert a proposed action into protective authority. If no approved durable send journal remains, no new broker transmission is initiated; required existing protection is preserved and uncertainty triggers broader containment and escalation.

### 10.4 Post-Effect Observations

Broker events, query results, fills, corrections, corporate actions, external activity, and reconciliation outcomes SHALL be committed within their approved bounds. A missed bound creates a gap, reduces evidence confidence, and triggers the corresponding conservative response; it does not undo the external event.

---

## 11. Ordering, Time, and Causality

The architecture SHALL NOT invent a universal total order from wall-clock timestamps. Ordering proof SHALL use the strongest applicable source:

1. quorum commit index and generation for RCL and other selected authoritative logs;
2. final-egress journal sequence, capability claim identity, and first-byte boundary;
3. source-native broker sequence, revision, page/cursor, or correction identity where evidenced;
4. component continuity identity plus local monotonic sequence;
5. explicit typed Causal Links;
6. trustworthy-time intervals with bounded uncertainty only when logical order is otherwise unavailable.

Issuer and consumer monotonic clocks on different continuity identities SHALL never be directly subtracted. Overlapping time-uncertainty intervals mean order is ambiguous unless another proof establishes it. Ambiguous order is represented, not sorted into a convenient sequence.

Every process restart, restore, or sequence reset creates a new continuity identity. A gap or duplicate across continuity identities requires reconciliation; it cannot be hidden by renumbering.

---

## 12. Identity, Idempotency, and Causal Completeness

- Record identity SHALL be generated once and remain stable across retry, replication, indexing, export, and replay.
- Duplicate delivery of the same digest and identity is idempotent and retained as delivery metadata where useful.
- The same identity with different canonical bytes is a Critical integrity conflict.
- Different identities claiming the same exclusive state transition, capability consumption, or broker effect are a semantic conflict and trigger containment.
- Causal parents SHALL be referenced by immutable identity and digest, not mutable URL, filename, dashboard row, or “latest” alias.
- A child arriving before its parent is held as an incomplete chain; it does not prove the parent existed or was valid.
- Missing optional counterpart records MAY be repaired by adding provenance-linked records. Missing required pre-effect records cannot be retroactively used to claim that an unsafe live transmission was conforming.

The Evidence Store SHALL produce completeness indexes by account, Safety Cell, Capacity Domain, authority generation, profile generation, egress generation, source continuity, intent, attempt, order, and Evidence Integrity Policy generation.

---

## 13. Integrity, Authenticity, and Anchoring

Raw records SHALL be content-addressed and authenticated by the source or trusted ingestion boundary. Ordered segments SHALL be chained or Merkle-equivalent and periodically committed to an Integrity Anchor outside the failure domain of the primary evidence store.

The selected mechanism SHALL detect:

- record mutation, substitution, and deletion;
- prefix truncation and suffix loss;
- history fork or conflicting restore;
- source or ingestion key rollback;
- anchor rollback or skipped anchor interval;
- schema substitution and canonicalization disagreement;
- unauthorized policy or retention change;
- primary and replica common-mode corruption.

Key rotation is break-before-make for write authority unless an explicitly bounded overlap is required and both generations are independently attributable. Old verification keys may remain for historical verification but cannot write new records. Compromise triggers new key and store-continuity generations, scope restriction, gap analysis, and independent review. Successful signature verification alone does not prove completeness or correctness.

---

## 14. Gap Detection and Completeness Reconciliation

Evidence gaps SHALL be detected through multiple independent controls where hazard severity requires, including:

- source-local sequence and continuity checks;
- authoritative-log revision reconciliation;
- egress claim/send versus broker observation reconciliation;
- intent/attempt/order/fill/position/capacity causal-graph closure;
- producer/ingress receipt reconciliation;
- anchor cadence and segment cardinality checks;
- broker page/cursor/completeness metadata;
- external activity and non-trade source comparison;
- periodic independent inventory and replay.

Gap state is one of:

```text
SUSPECTED -> CONFIRMED -> CONTAINED -> REPAIRED -> INDEPENDENTLY_REVIEWED
```

Repair appends recovered evidence with source, method, uncertainty, and chain-of-custody. It does not rewrite the missing interval or automatically restore its former evidence strength. A gap affecting pre-effect authorization, capacity, egress, fills, UNKNOWN, external activity, or recovery blocks new risk in scope. Where affected scope cannot be bounded, containment expands.

No gap is closed because the final portfolio appears flat, a later broker query omits the order, an operator remembers the action, or replay produces a convenient result.

---

## 15. Deterministic Replay

Every replay SHALL execute in an isolated environment with no usable live credential, signer, session, order route, production mutation endpoint, live Approval Set, or consumable Live Authorization.

The Replay Capsule SHALL bind:

- all VER-002-001 baseline fields;
- ordered raw record identities and digests;
- normalized view and transformation versions;
- code, build, dependency, schema, canonicalization, and migration digests;
- Hard Safety Envelope, Runtime Safety Profile, Human Authority Policy, Effective Principal Graph, Broker Capability Profile, and Evidence Integrity Policy;
- authoritative snapshots and committed prefixes used as initial state;
- time snapshots, continuity identities, uncertainty, and clock behavior;
- random seeds, scheduling choices, fault schedule, broker stubs, and external inputs;
- documented nondeterministic boundaries and comparison tolerances;
- expected state, decisions, denials, transmissions, invariants, and conservative bounds.

Replay results are:

```text
MATCH
DIVERGED
INCONCLUSIVE
CORRUPT_INPUT
UNSUPPORTED_BASELINE
```

Only exact safety-relevant equivalence under the approved comparison rule is `MATCH`. A `MATCH` establishes reproducibility of the recorded behavior, not adequacy of preventive controls. `DIVERGED`, `INCONCLUSIVE`, `CORRUPT_INPUT`, and `UNSUPPORTED_BASELINE` block the applicable gate and cannot be waived into proof by manual interpretation.

Historical replay SHALL use historical artifacts. Re-evaluation under current rules is a separate named analysis and SHALL NOT overwrite the historical result.

---

## 16. Redaction, Access, and Secret Handling

Evidence access SHALL use least privilege, purpose limitation, strong authentication, immutable access audit, and separation between evidence administration and independent review.

The raw protected tier and review views SHALL be distinct:

- raw evidence is encrypted and restricted to approved custodians;
- review views reference raw digests and transformation identity;
- field removal is explicit and policy-governed;
- quantities, signs, units, scope, ordering, outcome, and economic-effect lineage required for review remain verifiable;
- reviewers can detect that a required field was redacted even when not authorized to see its value;
- exports are integrity manifests, never untracked copies.

Usable broker secrets, signing material, session cookies, MFA recovery material, private keys, unrestricted bearer tokens, and plaintext credentials SHALL NOT be recorded. Secret scrubbing occurs before durable evidence acceptance when possible, but the scrubbing result itself is deterministic and evidenced. Detection of a leaked secret triggers credential compromise handling; deleting the record alone is insufficient and cannot erase chain-of-custody evidence.

---

## 17. Retention, Supersession, Compaction, and Deletion

The Evidence Integrity Policy SHALL define retention by record class and the longest applicable:

- broker correction and late-fill horizon;
- idempotency and replay horizon;
- order, position, exposure, and capacity economic-effect horizon;
- safety-profile, authority, credential, and deployment review horizon;
- incident, regulatory, contractual, and legal-hold horizon;
- verification and ADR acceptance lifetime.

Records supporting an open order, potentially-live attempt, UNKNOWN state, open position, unreleased capacity, unresolved external activity, active incident, accepted evidence item, or live scope SHALL NOT be deleted or compacted below reconstructability.

Compaction may replace storage representation only when an independently verified snapshot plus retained commitments, tombstones, causal indexes, source continuity, and raw material preserve deterministic reconstruction. Superseded and failed records remain linked. Destructive deletion requires approved policy, effective-human dual control, scope proof, expired holds, integrity-preserving tombstone, and evidence that economic lifetime and acceptance obligations ended. Deletion approval creates no authority and cannot alter live state.

---

## 18. Availability, Partition, Compromise, and Recovery

| Condition | Required response |
|---|---|
| Primary Evidence Store unavailable | deny new risk requiring its receipt; use only approved restrictive emergency path; preserve existing protection |
| Ingress acknowledges but durable receipt cannot be verified | treat as not durably committed; no new risk |
| Producer partitioned from store | stop affected new risk before ordinary buffer exhaustion; no memory-only evidence claim |
| Evidence projection or dashboard unavailable | authoritative controls continue; no permission inferred; repair projection later |
| Emergency journal isolated or unavailable | apply or retain the restrictive latch, hard-fence all new transmission, declare a Critical gap, permit no permissive command, and reconcile before any re-arm |
| Record/anchor fork or conflicting restore | contain affected scope; preserve all branches; no last-write-wins merge |
| Evidence key or administrator compromise | rotate/fence, restrict scope, inventory gaps and access, retain economic state, require independent incident review |
| Backup older than current history restored | assign new restore/store generation, compare against every surviving branch and authority log, remain non-live |
| Replay infrastructure compromised | isolate and invalidate replay evidence; no effect on authoritative economic state and no automatic re-arm |
| Retention/archival service unavailable | prohibit destructive lifecycle actions; continue append path if proven safe; otherwise restrict new risk |

Under ADR-002-017, recovery SHALL inventory sources, receipts, anchors, authoritative logs, broker history, external activity, and gaps as explicit Recovery Obligations in the current Recovery Evidence Package. Recovered evidence is appended with provenance. Authority remains restricted until the normal ADR-002-007 and ADR-002-015 governed re-arm process completes with fresh evidence; recovery success itself grants nothing.

---

## 19. Incident Reconstruction and Chain of Custody

An incident package SHALL identify:

- incident and scope identities;
- immutable Evidence Gap and containment timeline;
- all raw record, anchor, export, and Replay Capsule digests;
- acquisition source, custodian, method, time evidence, and transfer history;
- every transformation, redaction, normalization, and analyst action;
- baseline artifacts and authority/configuration generations;
- broker, account, order, fill, position, capacity, and external-activity lineage;
- unknowns, conflicts, missing intervals, confidence limits, and alternative sequences;
- replay result and deterministic boundaries;
- economic exposure and conservative maximum effect;
- corrective controls, owner, reviewer, and gate impact.

The reconstruction SHALL distinguish observed fact, authenticated source claim, derived inference, conservative assumption, and unresolved unknown. Human narrative may explain evidence but cannot replace missing machine evidence or close a gap by assertion.

---

## 20. Broker, External, and Manual Activity

Broker responses and events SHALL retain raw protocol identity, endpoint, request correlation, account/session scope, page/cursor/completeness information, broker timestamps, local receipt anchors, corrections, and Broker Capability Profile identity. Normalization never discards raw semantics needed to reassess a profile.

An external portal, dealer, support, custodian, clearing, exercise, assignment, transfer, fee, financing, or corporate-action record is attributed as external or non-trade evidence under ADR-002-004/006/010. It SHALL NOT be rewritten as a TOS intent or compliant egress action. Missing portal/dealer records do not prove no external activity; detected activity consumes conservative capacity and blocks new risk until reconciled.

---

## 21. Continuous Conformance and Evidence Validity

Continuous controls SHALL detect at least:

- missing required record classes and causal parents;
- persistence and gap-detection bound misses;
- source sequence reset, duplicate conflict, or continuity drift;
- receipt, record, payload, segment, anchor, or export digest mismatch;
- store, key, policy, schema, canonicalization, or retention generation drift;
- unauthorized access, export, redaction, deletion, or replay execution;
- live credential, route, or mutation endpoint reachable from replay/evidence principals;
- replay divergence or unsupported baseline;
- evidence accepted from an incompatible software, profile, identity, or restore generation;
- failure or inconclusive results overwritten by later success;
- a record or receipt being used as capacity, reconciliation, approval, or broker authority.

A conformance violation invalidates the affected evidence claim and may set registered items to `INCONCLUSIVE`, `EXPIRED`, or `FAIL`. It never erases the underlying economic facts. New risk remains blocked until containment and independent review establish the safe scope.

---

## 22. Failure Modes and Required Responses

| Unsafe sequence | Required prevention or containment |
|---|---|
| Asynchronous logger loses a risk-increasing send | egress requires durable exact receipt and `SEND_STARTED` before first byte |
| Evidence receipt from another request is substituted | exact payload, scope, causation, policy, continuity, and principal binding rejects it |
| Same record ID carries different bytes | Critical integrity conflict; contain and preserve both observations |
| Store silently deletes denied decisions | append-only segment and external anchor reveal gap; gate fails |
| Backup restore hides later sends or fills | new restore generation, branch comparison, broker/RCL reconciliation, non-live recovery |
| Cross-host timestamps reorder HALT and send | use commit/egress sequences and uncertainty; ambiguity resolves restrictive |
| Normalizer changes sign, unit, instrument, or quantity | raw digest and versioned deterministic transform expose divergence |
| Redaction removes proof of scope or economic effect | view is insufficient; gate is `INCONCLUSIVE`, never inferred PASS |
| Retention expires while order is UNKNOWN | economic and tombstone retention dominates; capacity remains consumed |
| Replay reaches production endpoint | topology is non-conforming; fence credentials/routes and invalidate evidence |
| Later PASS replaces prior FAIL | immutable supersession link retains both; acceptance considers unresolved failure |
| Evidence recovery is treated as re-arm | fresh governed re-arm is mandatory; restored evidence creates no authority |

---

## 23. Rejected Alternatives

### 23.1 Best-Effort Application Logging

Rejected because buffers, crashes, backpressure, retries, and process compromise can lose the exact adverse path.

### 23.2 Database Row Updates as Audit History

Rejected because mutable current-state rows hide predecessor state, rejection, conflict, and correction.

### 23.3 Timestamp Sorting as Global Order

Rejected because clock error, source disagreement, suspension, and cross-host monotonic discontinuity can reverse safety-relevant causality.

### 23.4 Successful Actions Only

Rejected because denials, failures, ambiguity, and security attempts are required to establish both control behavior and attack history.

### 23.5 Evidence Receipt as Authorization

Rejected because durability proves custody, not safety validity, capacity, current authority, or broker permission.

### 23.6 Replay Result Repairs Live State

Rejected because replay is isolated detective/recovery analysis and cannot own authoritative state transitions.

### 23.7 Latest Passing Run Replaces Prior Failure

Rejected because this destroys negative evidence and can conceal an unresolved nondeterministic or intermittent unsafe path.

### 23.8 Delete Secrets and Rewrite the Chain

Rejected because chain mutation destroys integrity. Secret compromise requires credential response plus integrity-preserving quarantine and redaction.

### 23.9 Flat Portfolio Proves Complete Evidence

Rejected because open, late, external, correction, and UNKNOWN effects can exist despite a convenient snapshot.

### 23.10 Audit and Monitoring Substitute for Prevention

Rejected because post-effect visibility cannot stop an unauthorized or over-capacity broker effect.

---

## 24. Consequences

### 24.1 Positive

- Every live economic effect has reconstructable authority, capacity, configuration, identity, and egress lineage.
- Evidence omission, mutation, rollback, fork, and redaction defects become explicit gate failures.
- Replay remains reproducible across schema and software evolution without touching live state.
- Failed and inconclusive paths cannot disappear behind later success.
- Evidence outages reduce availability instead of silently reducing traceability.
- Reviewers can distinguish source facts, derivations, assumptions, and unknowns.

### 24.2 Negative

- Pre-effect durability adds latency and a restrictive dependency for new risk.
- Independent emergency journals, anchors, protected raw storage, replay isolation, and chain-of-custody increase operational cost.
- Long economic and verification horizons increase retention volume.
- Strict gap handling may keep scopes halted after the underlying control has recovered.
- Broker and external-source incompleteness may make deterministic reconstruction impossible, requiring reduced scope rather than a weaker evidence claim.

These costs are accepted. They SHALL be bounded and engineered; they are not grounds to weaken evidence completeness or preventive safety.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `ERI-EV-001` through `ERI-EV-012`. Written cases are not completed evidence.

| Acceptance case | Required result |
|---|---|
| `ERI-AC-001` | Every proposed, approved, denied, transmitted, observed, corrected, recovered, and failed action produces a causally complete immutable chain; missing mandatory classes create a gap |
| `ERI-AC-002` | A risk-increasing send cannot reach the first broker-directed byte before exact pre-effect and `SEND_STARTED` durability; receipt substitution and stale receipts are rejected |
| `ERI-AC-003` | Evidence-store outage, partition, backpressure, emergency-journal loss, and receipt ambiguity block new risk while valid restrictive HALT is still applied, existing protection remains preserved, and no emergency path creates permission |
| `ERI-AC-004` | Duplicate, delayed, reordered, partial, conflicting, and continuity-reset records cannot create false completeness or hide UNKNOWN |
| `ERI-AC-005` | Mutation, deletion, truncation, fork, anchor rollback, key rollback, and conflicting restore are detected and contain affected scope |
| `ERI-AC-006` | Causal reconstruction uses authoritative/local order and bounded uncertainty; cross-host timestamp manipulation cannot reorder HALT, capacity, claim, send, ACK, fill, cancel, or replace into a permissive result |
| `ERI-AC-007` | Isolated replay reproduces the safety-relevant result or returns a non-PASS state; it has no live credential, route, approval, capacity, authority, or mutation path |
| `ERI-AC-008` | Historical schema, software, canonicalization, configuration, broker profile, identity, and dependency changes are exactly bound; unsupported or altered baselines cannot PASS |
| `ERI-AC-009` | Redaction and export reveal field presence and preserve canonical digests, quantities, ordering, scope, and chain of custody without exposing usable secrets |
| `ERI-AC-010` | Retention, compaction, supersession, legal-hold release, and deletion cannot erase open economic effects, UNKNOWN, tombstones, failed runs, or required reconstructability |
| `ERI-AC-011` | Missing ACK, cancel ACK, query omission, broker correction, external/manual action, and non-trade change remain conservatively represented and cannot be rewritten as proof of non-effect |
| `ERI-AC-012` | Store/key/replay recovery and disaster restore preserve all branches and gaps, create no authority, do not auto re-arm, and support independent incident reconstruction |

---

## 26. Requirements Traceability

| Requirement | ADR-002-016 allocation |
|---|---|
| SAFE-010, SAFE-011 | Pre-effect durability and failure response never replace or weaken preventive controls (§§7, 10, 18) |
| SAFE-020, SAFE-021 | Intent, attempt, egress, ACK, fill, cancel, replacement, and ambiguity have explicit causal evidence (§§8–12) |
| SAFE-022, SAFE-023, SAFE-024, SAFE-025 | Broker, reconciliation, external, correction, and partial-state evidence remains raw, attributable, and conservative (§§14, 20) |
| SAFE-030, SAFE-031 | Critical input provenance, units, source, processing, time, and transformations are bound (§§8–9, 15) |
| SAFE-035 | Ordering uses trustworthy-time uncertainty without cross-host monotonic comparison (§11) |
| SAFE-041, SAFE-044, SAFE-048 | HALT, recovery, partition, gap, and non-revival evidence preserve restrictive precedence (§§10, 18) |
| SAFE-045 | Evidence and replay principals cannot reach live credentials, routes, or mutation endpoints (§§7, 15–16) |
| SAFE-050 | Evidence policy, schema, canonicalization, retention, and replay baselines are governed and versioned (§§8, 13, 15, 17) |
| SAFE-051 | Complete immutable action and decision evidence is captured at owning boundaries (§§8–14) |
| SAFE-052 | Replay and incident reconstruction are deterministic, isolated, attributable, and non-authorizing (§§15, 19) |

---

## 27. Open Implementation Questions

Open questions reduce authority and keep affected scope non-live; they do not weaken the rules above.

1. Which append-only durable store, replication mode, acknowledgement rule, and consistency level implement each durability class?
2. Which canonical serialization, schema registry, hashing, signing, and normalization mechanisms are approved?
3. Which independent anchor service and cadence detect primary-store rollback and history fork without creating a common mode?
4. Which source identities and local sequence mechanisms cover every required record producer and restart continuity?
5. What exact record-class matrix and causal-parent rules apply per Safety Cell, account, broker, and action class?
6. Which durable emergency journal supports Human HALT and containment independently of the ordinary evidence path?
7. Which bounded backpressure and containment protocol stops new risk before evidence durability is lost?
8. Which raw-data encryption, key custody, redaction, export, and reviewer-access model is approved?
9. Which retention, compaction, tombstone, legal-hold, and destructive-deletion periods are approved per record class?
10. Which isolated replay runtime, deterministic scheduler, broker simulator, dependency archive, and baseline resolver are conforming?
11. How are broker pages, cursors, corrections, external/manual activity, and source omissions inventoried independently?
12. What values for `B_evidence_persist`, `B_evidence_gap_detect`, `B_evidence_gap_contain`, and evidence retention/replay limits are approved and measured?

---

## 28. Approval Gate

ADR-002-016 SHALL remain **Proposed** until all of the following are complete:

1. Safety Evidence Envelope, Evidence Integrity Policy, Evidence Commit Receipt, Integrity Anchor, Evidence Gap, and Replay Capsule schemas and canonicalization are approved;
2. required record classes and causal-parent rules are complete for every safety-critical boundary;
3. pre-effect durability is enforced at final egress without treating evidence as authority;
4. independent emergency durability preserves restrictive HALT and containment semantics without a permissive bypass;
5. append-only storage, source authenticity, external anchoring, gap/fork detection, key rotation, backup, restore, and disaster recovery are implemented and independently security-reviewed;
6. replay is isolated from all live credential, route, approval, authority, capacity, and mutation paths;
7. redaction, access, export, retention, compaction, legal hold, and deletion governance are approved;
8. `ERI-EV-001` through `ERI-EV-012` and applicable cross-ADR evidence pass at required levels and receive independent review;
9. applicable evidence persistence, gap, retention, replay, time, egress, broker, and recovery bounds are approved and measured;
10. residual risks are recorded and accepted only for a scope that remains within RFC-000 and RFC-001;
11. RFC-002 architecture, security-boundary, recovery, and verification reviews confirm no evidence or replay path became preventive or trading authority.

Until those gates pass, this ADR authorizes architecture and implementation-planning work only. It does not claim verification completion, ADR acceptance, restricted-live readiness, production readiness, or live trading authority.
