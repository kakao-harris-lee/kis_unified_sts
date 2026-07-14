# ADR-002-018 — Critical Input Integrity, Provenance, and Decision-Context Fencing

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Critical Input classification, approved-source identity, source continuity, provenance, units and mappings, transformation lineage, freshness, consistency, corroboration, immutable snapshots, decision-context binding, correction and invalidation, final-egress currentness, degraded behavior, recovery, evidence, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 SAFE-030 through SAFE-035; RFC-002 §§7.1, 10.1–10.3, 10.8, 15, 22, 23, and 29
- **Depends On:** RFC-000 constitutional safe state; RFC-001 SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020 through SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052; ADR-002-002 through ADR-002-017

---

## 1. Decision

Every value that can change direction, instrument, account, quantity, price constraint, exposure, risk, margin, venue or session eligibility, authorization, protective classification, or execution behavior SHALL be governed as a **Critical Input** for the affected action and scope. A component may not avoid this contract by calling the value a feature, signal, cache, reference, override, derived field, broker fact, or operator input.

Critical Inputs SHALL be admitted only under an approved immutable **Critical Input Policy**. Every admitted observation SHALL retain authenticated source identity, source-continuity generation, source-native sequence or revision where available, schema and semantic version, instrument and account mapping, unit and scale, trustworthy-time evidence, local receipt ordering, raw payload digest, and complete transformation lineage.

The Context Integrity Service SHALL construct an immutable **Critical Input Snapshot** and a purpose-bound **Decision Context Capsule**. The capsule SHALL bind the exact observations, transformations, validation results, uncertainty, corroboration, policy and configuration generations, scope, intended use, maximum age, and invalidation conditions used by proposal and independent approval. It grants no approval, capacity, Live Authorization, protective classification, or broker permission.

Proposal, approval, Intent, capacity request, Live Authorization, Transmission Capability, Commit Proof, and broker request SHALL bind the exact Decision Context Capsule identity and digest where that context can affect the authorized economic effect. Substitution, union, partial refresh, hidden recomputation, or mutation creates a new capsule and requires every affected downstream decision to be repeated.

Whether context can affect authorized economic effect SHALL be determined only by the active Critical Input Policy under §8 and the conservative Material Context Change definition in §5.8. A proposer, consumer, or implementation component SHALL NOT self-exempt a context dependency. Missing, stale, contradictory, or unresolved materiality defaults to Critical and requires exact binding.

The Independent Approval Service SHALL validate safety-critical facts independently from the proposing component. A shared upstream source, parser, mapping table, feature store, cache, transformation library, administrator, or data plane SHALL be treated as a common-mode dependency rather than independent corroboration. Where independent corroboration is unavailable, the limitation SHALL be approved as explicit residual risk under SAFE-034, with additional validation and corresponding live-scope reduction; the proposer cannot approve the exception.

Missing, stale, future-dated, crossed, out-of-range, incorrectly scaled, ambiguously mapped, discontinuous, contradictory, unsupported, or unverifiable Critical Input is `UNKNOWN`, `STALE`, `CONFLICTED`, or `INVALID` as applicable. It SHALL block new risk in the affected dependency closure. Last-known-good data, a majority vote, cache agreement, service health, a heartbeat, a TTL, eventual consistency, or absence of a correction SHALL NOT convert uncertainty into permission.

Material correction, retraction, source-continuity change, policy change, mapping change, newer authoritative revision, or trust degradation SHALL invalidate every affected Snapshot, Capsule, proposal, approval, Intent, authorization, and unconsumed capability before future new-risk transmission. Materiality SHALL be classified only by the active §8 policy under §5.8; unknown or unresolved materiality is treated as material. Invalidating an artifact never expires an order, fill, exposure, UNKNOWN state, or Risk-Capacity commitment already capable of economic effect.

Final egress remains the last enforcement point. For every new-risk send it SHALL verify the exact Capsule binding and actively establish current policy, source-continuity, context-generation, validity, and invalidation status within approved bounds. A permissive cache or absence-of-invalidation event is not proof. If currentness cannot be positively established at the irreversible send boundary, transmission is denied. Final egress does not recompute strategy logic; it verifies that the exact already-approved context and its safety-critical currentness predicates remain valid.

Recovery of a source, cache, Context Integrity Service, clock, mapping registry, approval service, or evidence store cannot revive an older Capsule or authority. Recovery SHALL establish new continuity where required, satisfy ADR-002-017 obligations, and use a fresh governed re-arm chain. No automatic re-arm is permitted.

---

## 2. Context

RFC-001 makes Trustworthy Context a precondition for decision, approval, sizing, and execution. It requires Critical Input provenance and independent approval inputs. RFC-002 assigns validation to the Context Integrity Service and makes strategy an untrusted proposer.

Those allocations do not yet define one complete protocol. Without it, an implementation can:

- validate a market event at proposal time but silently read a different price, multiplier, account, or venue state during approval or execution;
- treat two services reading the same corrupted feed or mapping table as independent corroboration;
- accept a plausible but wrong unit, contract multiplier, currency, sign, split factor, or account mapping;
- reuse a stale feature-store row after the source stream restarted or rolled back its sequence;
- combine individually fresh fields from incompatible market, account, reference, or session cuts;
- let a correction arrive after approval without invalidating the approved decision;
- use a cached “context healthy” flag after source continuity or venue state changed;
- replace a missing field with zero, prior value, midpoint, default account, or parser fallback;
- let an operator type a value that bypasses provenance and independent validation;
- allow the proposer to certify that independent corroboration is infeasible;
- record provenance only in audit logs without binding it to authorization and egress;
- treat a restart, source recovery, replay match, or cache warm-up as restoration of prior permission.

This ADR closes those paths without making the Context Integrity Service an authorization or transmission authority.

---

## 3. Decision Drivers

1. Every safety-relevant value must have attributable semantics, not merely a payload.
2. Source restart, rollback, substitution, correction, and mapping drift must be explicit and fenced.
3. Independently approved facts must not share hidden common-mode corruption.
4. Proposal, approval, authorization, and egress must refer to one exact immutable context.
5. Freshness must be measurable through trustworthy time and consumer-local age evidence.
6. Multi-source and multi-field consistency must be conservative under non-atomic observation.
7. Corrections and retractions must invalidate permission without erasing economic effects.
8. UNKNOWN or unbounded input state must consume conservative capacity where exposure may exist and must block new risk.
9. Final egress must prevent context substitution and stale-context transmission.
10. Recovery and data-health restoration must never automatically re-arm.

---

## 4. Scope and Non-Scope

This ADR decides:

- Critical Input classification and dependency closure;
- Critical Input Policy and approved-source registry requirements;
- source identity, continuity, revision, provenance, units, mappings, and transformation lineage;
- raw observation, snapshot, and Decision Context Capsule contracts;
- freshness, uncertainty, range, cross-field, consistency, and corroboration rules;
- independent approval input separation and common-mode disclosure;
- correction, retraction, supersession, and invalidation propagation;
- exact context binding through final egress;
- degraded, partition, restart, restore, and recovery behavior;
- evidence, metrics, alerts, acceptance cases, and approval gates.

This ADR does not decide:

- strategy alpha, model selection, feature usefulness, or commercial data products;
- generic per-field broker/account reconciliation confidence, which remains ADR-002-006;
- broker-specific semantics and Final Quantity Proof, which remain ADR-002-004;
- trustworthy-time implementation, which remains ADR-002-008;
- corporate-action economic transitions, which remain ADR-002-010;
- capacity mutation or release, which remain solely with the RCL under ADR-002-002 and ADR-002-012;
- configuration activation, which remains ADR-002-014;
- evidence custody and replay, which remain ADR-002-016;
- recovery readiness and re-arm, which remain ADR-002-017 and ADR-002-007;
- concrete feed, schema-registry, stream-processing, storage, or transport products;
- numeric freshness, propagation, invalidation, or source-loss bounds, which belong in approved policies and the Verification Profile.

---

## 5. Definitions

### 5.1 Critical Input Policy

An immutable, authenticated, separately governed artifact that declares Critical Input classes, approved sources, source and transformation semantics, validation and corroboration rules, maximum ages, dependency and invalidation rules, conservative failure responses, and permitted scopes.

### 5.2 Critical Input Observation

An immutable source-attributed record containing raw or losslessly referenced payload, source identity and continuity, native revision or sequence, semantic metadata, trustworthy-time evidence, receipt ordering, and integrity data. An observation is evidence, not permission.

### 5.3 Source Continuity Identity

The generation identity within which source-native sequences, revisions, schemas, and completeness claims are meaningful. Restart, restore, failover, rollback, credential or endpoint substitution, sequence reset, or unverifiable continuity creates a new identity or an explicit continuity gap.

### 5.4 Transformation Lineage

The ordered graph of raw observations, code/build identity, schema, configuration, mapping, unit conversion, normalization, aggregation, model or formula, parameters, and intermediate digests that produced a derived Critical Input.

### 5.5 Critical Input Snapshot

An immutable purpose- and scope-bound evaluation of a closed Critical Input dependency set, including exact observation versions, validation outcomes, confidence states, uncertainty, consistency cut, freshness, and invalidation predicates.

### 5.6 Decision Context Capsule

An immutable canonical artifact binding one proposed action purpose and scope to the exact Critical Input Snapshot, safety configuration, trustworthy-time evidence, independent-validation requirements, maximum age, and invalidation generation. It is the context identity carried through later decisions.

### 5.7 Context Generation

A monotonic generation for one context domain that orders restrictive invalidation and source/policy continuity changes. An older generation cannot authorize a future new-risk action after a newer restrictive generation is committed or locally hard-fenced.

### 5.8 Material Context Change

Any change that may alter the action’s identity, allowedness, economic effect, risk, approval result, capacity need, route, or broker conformance, or that weakens the evidence supporting those facts.

### 5.9 Consistency Cut

The explicit set of source revisions, continuity identities, receipt intervals, and uncertainty bounds used together. It does not assert atomicity unless the source protocol proves atomicity.

---

## 6. Safety Invariants

### CII-INV-001 — No Unclassified Safety Input

Any value capable of altering a safety-relevant action property is a Critical Input for that action and cannot bypass policy by naming or storage location.

### CII-INV-002 — Exact Provenance and Semantics

Every admitted Critical Input is attributable to approved source, continuity, revision, time, instrument, account, unit, scale, schema, processing version, and complete transformation lineage.

### CII-INV-003 — Immutable Exact Context

Proposal, approval, Intent, authorization, capability, proof, and egress refer to the same exact Capsule digest; mutation or substitution requires a new chain.

### CII-INV-004 — Independent Approval Is Actually Independent

Common source, code, mapping, cache, operator, administrator, credential, transport, or failure domain cannot be counted as independent corroboration.

### CII-INV-005 — Ambiguity Is Restrictive

Missing, stale, future, conflicting, discontinuous, wrongly scaled, ambiguously mapped, unsupported, or unverifiable Critical Input blocks new risk and never defaults to a permissive value.

### CII-INV-006 — Freshness Uses Trustworthy Time

Every time-dependent validity claim uses an approved measurable bound and ADR-002-008 evidence. Cross-host monotonic values are never directly subtracted.

### CII-INV-007 — Non-Atomic Inputs Stay Conservative

Fields from incompatible cuts cannot be combined as one coherent state. Unknown interleaving is bounded adversely or blocks new risk.

### CII-INV-008 — Correction Invalidates Permission

Correction, retraction, supersession, continuity change, or material policy/mapping change invalidates all affected unconsumed downstream permission before future new-risk send.

### CII-INV-009 — Economic Effect Outlives Context

Snapshot, Capsule, policy, source, or evidence expiry/invalidation never expires orders, attempts, fills, exposure, UNKNOWN, or capacity commitments.

### CII-INV-010 — Final Egress Fences Context

No new-risk broker byte is sent unless exact context binding and current policy, continuity, generation, validity, and invalidation status are actively proven at the irreversible boundary.

### CII-INV-011 — Context Service Has No Economic Authority

Context validation cannot approve, mutate capacity, issue Live Authorization, classify protection, clear HALT, transmit, or re-arm.

### CII-INV-012 — UNKNOWN Consumes Conservatively

Where uncertain input state can hide an existing or potentially-live economic effect, its worst credible effect remains capacity-consuming; uncertainty never creates headroom or new-risk permission.

### CII-INV-013 — Restriction Dominates Data Recovery

Source, cache, parser, mapping, clock, or service recovery cannot revive a prior Capsule, approval, authorization, capability, or live state.

### CII-INV-014 — Evidence Does Not Replace Prevention

Logs, lineage, dashboards, audit, replay, or later correction cannot substitute for admission, invalidation, authority, capacity, and egress enforcement.

---

## 7. Authority Ownership and Separation

| Function | Owning authority | Prohibited collapse |
|---|---|---|
| Classify input and approve source/policy | Critical Input Policy governance under ADR-002-014 controls | proposer cannot self-exempt an input or activate policy |
| Capture source observation | authenticated source ingress | ingress cannot declare an action safe |
| Validate and assemble Snapshot/Capsule | Context Integrity Service | cannot approve, mutate capacity, arm, classify protection, or transmit |
| Propose action | Decision Service | cannot validate its own independent approval inputs |
| Independently approve safety facts | Independent Approval Service | cannot rely solely on proposer-derived values or create transmission authority |
| Evaluate/commit capacity | Aggregate Risk Authority / RCL respectively | context service and approval service cannot mutate capacity |
| Issue Live Authorization/capability | ADR-002-007 authorities | context health alone cannot issue or revive authority |
| Enforce broker send | ADR-002-013 final egress | no upstream “validated” status permits bypass |
| Preserve evidence/replay | ADR-002-016 services | evidence and replay cannot alter current input or live state |
| Recover and re-arm | ADR-002-017/007/015 workflow | recovered context cannot reopen live scope |

No Critical Input component SHALL hold a usable live broker credential or route merely because it evaluates venue or account data.

---

## 8. Critical Input Policy and Classification

The policy SHALL define, at minimum:

- input class, purpose, hazard, affected scope, and materiality;
- approved source identities, endpoints, credentials, and continuity semantics;
- schema, field presence, nullability, enum, range, precision, unit, currency, multiplier, sign, and mapping rules;
- freshness, future-time, ordering, rate-of-change, crossed-state, cross-field, and session checks;
- allowed transformations and exact code/configuration identities;
- source-independence and corroboration requirements;
- consistency-cut and non-atomic observation rules;
- correction, retraction, supersession, and invalidation rules;
- last-known-good restrictions and maximum adverse bounds;
- conservative failure response and dependency-closure expansion;
- evidence class, retention, review, and approved live scope.

Unknown input classification is Critical by default when the input can affect a safety-relevant field. A policy may classify an input as non-Critical only with a traceable proof that corruption or omission cannot affect safety or economic effect in the declared scope. A strategy or data owner cannot make that determination unilaterally.

Policy activation follows ADR-002-014. Repository merge, signature, deployment, source health, or distribution is not activation and does not re-arm live scope.

---

## 9. Source Identity, Continuity, and Admission

Each source observation SHALL bind:

- source principal, provider, product/feed, endpoint, environment, account and venue scope;
- credential or trust identity without exposing secrets;
- Source Continuity Identity, connection/session identity, native sequence/revision, page/cursor/completeness where applicable;
- raw event identity and payload digest;
- source event time and semantics, local receipt trustworthy-time anchor, and uncertainty;
- schema and semantic-contract versions;
- instrument, contract, venue, account, currency, unit, scale, multiplier, and sign metadata;
- correction, retraction, supersession, and predecessor links;
- ingestion software, parser, policy, deployment, and evidence continuity generations.

Admission SHALL reject or explicitly mark uncertain:

- unknown or substituted source identity;
- sequence reset, rollback, duplicate conflict, gap, or out-of-order event outside approved semantics;
- schema or semantic drift, missing mandatory metadata, or unsupported enum;
- wrong environment, account, venue, session, instrument, currency, unit, scale, sign, or multiplier;
- unverifiable timestamp or receipt age;
- an endpoint, credential, proxy, cache, or normalization path outside the declared trust and failure-domain allocation.

Source continuity is not inferred from TCP health, process uptime, credential validity, identical payload, or last sequence cached by a restarted consumer. Unknown continuity produces a gap and blocks dependent new risk.

---

## 10. Transformation Lineage and Derived Inputs

Every derived Critical Input SHALL retain the complete deterministic or explicitly stochastic lineage from admitted observations. The lineage SHALL bind:

- exact parents and their digests;
- ordered transformation graph;
- code/build, model, formula, library, schema, and configuration versions;
- units before and after every conversion;
- rounding, clipping, interpolation, imputation, aggregation, and missing-data behavior;
- model parameters, random seed or non-determinism declaration where applicable;
- output type, range, precision, uncertainty, and intended scope.

No hidden default, silent coercion, forward fill, zero fill, stale feature reuse, symbol alias, unit conversion, or fallback source may occur outside policy. A transformation that cannot be reproduced or whose dependency is missing produces an invalid output for new-risk use.

The same library used by proposer and approver is a common-mode dependency unless independently verified isolation or diverse implementation is demonstrated. Recalculation by the same corrupted code is not independent corroboration.

---

## 11. Snapshot and Consistency-Cut Construction

The Context Integrity Service SHALL assemble a closed dependency graph for the requested decision. The resulting Snapshot SHALL include:

- policy and Context Generation;
- exact observation and transformation identities/digests;
- source continuity and sequence/revision vector;
- Consistency Cut and non-atomicity assumptions;
- field-level states: `VALID`, `UNKNOWN`, `STALE`, `CONFLICTED`, or `INVALID`;
- freshness and time-health evidence;
- range, rate, crossed-state, cross-field, mapping, unit, and venue/session results;
- corroboration paths, independence analysis, common-mode scope, and residual risks;
- uncertainty and worst-credible bound;
- issue scope, intended use, maximum age, and invalidation predicates.

Individually fresh fields do not form a valid Snapshot if their revisions or effective states are incompatible. Where a source cannot supply an atomic view, the policy SHALL define a bounded conservative cut, capture intervening events, and repeat or reconcile observations. Equality between reads and absence from one query are not completeness proof.

A Snapshot with any blocking dependency outside its proof rules cannot be labelled valid by averaging confidence, majority vote, or ignoring the field.

---

## 12. Decision Context Capsule

The Capsule SHALL bind:

- unique identity, canonical bytes, digest, schema, issuer, and signature;
- policy, Context Generation, Snapshot identity/digest, and consistency cut;
- environment, Safety Cell, account, instrument, venue, strategy/decision class, and requested action scope;
- safety configuration, broker profile, trustworthy-time, recovery, authority, deployment, identity, and evidence generations;
- every safety-critical proposed fact: account, instrument, direction, quantity basis, unit, price/order constraints, exposure effect, venue/session/tradability, and expiration;
- independent-validation requirements and declared common-mode limitations;
- issue receipt anchor, maximum age, expiry, and invalidation set;
- explicit statements that it creates no approval, capacity, Live Authorization, capability, protection, transmission, or re-arm.

A Capsule is immutable. Updating one field, refreshing one parent, changing a mapping, using a newer price, or extending age creates a new identity and digest. Capsules SHALL NOT be merged, intersected, unioned, partially refreshed, or “patched” to preserve an approval.

---

## 13. Independent Approval Inputs

The Independent Approval Service SHALL:

1. verify the Capsule signature, digest, policy, scope, generations, age, and invalidation state;
2. obtain or validate safety-critical facts through approved independent or independently controlled paths;
3. recompute account, instrument, direction, quantity, unit, price constraints, exposure effect, venue/session/tradability, and applicable risk predicates;
4. compare recomputed facts to the proposal and Capsule;
5. record source/common-mode analysis and any approved residual limitation;
6. deny on mismatch, missing proof, stale input, conflict, or unapproved dependency;
7. bind its attestation and Approval Set to the exact Capsule digest.

Independence is assessed by effective control and failure path, not process count, vendor brand, API endpoint count, region label, or organizational ownership. Two feeds derived from one exchange sequence, two caches populated by one parser, or two services sharing one mapping registry do not automatically corroborate each other.

Where true independent corroboration is not feasible, SAFE-034 requires independent review of the limitation and documented additional validation. The permitted scope SHALL remain no broader than the demonstrated conservative residual risk. Availability pressure cannot waive this requirement.

---

## 14. Freshness, Uncertainty, and Source Disagreement

Freshness SHALL be evaluated from source-time semantics plus consumer-local receipt monotonic age and conservative transport uncertainty under ADR-002-008. Issuer and consumer monotonic clocks are never directly subtracted across continuity identities.

The policy SHALL define separately:

- source production delay;
- transport and queue delay;
- consumer receipt age;
- transformation and Snapshot age;
- Capsule age;
- session and venue-state age;
- correction and late-revision horizon;
- source-loss detection and invalidation propagation bounds.

Negative age, future timestamp outside tolerance, missing time, unknown transport, clock discontinuity, or source disagreement cannot be clamped or ignored. Source disagreement SHALL preserve each observation and apply an approved source-authority and consistency rule. Majority vote is insufficient where sources share origin or one source is authoritative for a different semantic field.

Last-known-good input may support evidence, reconciliation, HALT, scope narrowing, or separately authorized protective reasoning only where policy proves that use cannot increase exposure. It SHALL NOT authorize ordinary new risk merely because the value remains within a TTL.

---

## 15. Binding Through Intent, Capacity, Authority, and Egress

The exact Capsule identity/digest SHALL be included or cryptographically bound in:

1. proposal and rationale;
2. independent approval request, attestation, and Approval Set;
3. immutable Intent;
4. aggregate-risk evaluation and RCL commitment request where the active §8 policy determines that context affects capacity;
5. Live Authorization and per-action Transmission Capability;
6. Quorum Commit Certificate / Commit Proof;
7. evidence pre-effect receipt and `SEND_STARTED` record;
8. final broker request construction and egress decision.

ADR-002-020 consumes the exact Capsule as a fixed construction input. The compiler cannot refresh, substitute, or recompute context; any material Capsule change requires a new candidate command, venue decision, approval, capacity evaluation, proof, and authority chain.

Every consumer SHALL reject a missing, mismatched, stale, invalidated, wrong-scope, wrong-environment, or unsupported Capsule. A consumer may derive a narrower restriction, but it cannot silently substitute a more permissive value or newer input into an existing chain.

The applicability of a binding cannot be decided ad hoc by a consumer. It SHALL follow the Critical Input Policy and §5.8 materiality rules; unknown dependency or materiality requires the binding and the more restrictive result.

RCL remains the sole capacity mutation/serialization authority. Context invalidation may request quarantine or re-evaluation, but only RCL transitions can preserve, enlarge conservatively, transfer, or release capacity. No context expiry or “decision cancelled” status releases capacity after potential economic effect.

---

## 16. Final-Egress Currentness and Send Race

For each new-risk send, final egress SHALL validate:

- exact Capsule, Intent, approval, commitment, capability, proof, and broker-request binding;
- current Critical Input Policy and Context Generation;
- current Source Continuity Identities for permission-critical sources;
- Capsule validity, age, scope, and invalidation status;
- current venue/session/tradability and broker constraints required by SAFE-032;
- current trustworthy time, recovery generation, safety authority, configuration, identity, route, and evidence predicates required by other ADRs.

Currentness SHALL be obtained through an authenticated fenced mechanism with approved maximum proof age and propagation bounds. Cached health, TTL, heartbeat, last-known generation, eventual-consistency window, or absence of a correction/invalidation record is not proof. Failure to establish current state is denial.

A material input invalidation SHALL reach affected authorization issuers and every final egress within `B_critical_input_invalid_to_authority` and `B_critical_input_invalid_to_egress`. The capability claim and first broker byte remain bounded by ADR-002-007 and ADR-002-013. If invalidation races the send and ordering cannot prove that the send preceded the restrictive generation, the attempt is potentially live, its worst credible effect remains capacity-covered, and no blind retry is allowed.

Final egress verifies safety-context validity; it does not choose signals, recompute alpha, or create a replacement proposal.

---

## 17. Correction, Retraction, and Continuous Invalidation

Corrections and retractions SHALL be new immutable observations linked to the superseded record. Destructive overwrite is prohibited.

Materiality and affected-scope classification SHALL follow §5.8 and the active §8 policy. No source, proposer, approver, consumer, or operator may classify its own correction as immaterial outside that policy. Unknown or unresolved materiality is material and expands the restrictive dependency closure.

At minimum, the following trigger impact analysis and restrictive invalidation where material:

- source sequence correction, retraction, bust, or revised reference data;
- instrument identity, symbol, contract, multiplier, currency, account, venue, or session remap;
- source continuity, endpoint, credential, parser, schema, mapping, transformation, model, or configuration change;
- freshness expiry, time-health degradation, source loss, gap, fork, or disagreement;
- venue halt, suspension, tradability, order-type, price-limit, settlement, or margin change;
- broker/account state correction, external activity, or non-trade event;
- evidence gap, integrity failure, policy invalidation, or common-mode discovery.

The system SHALL compute the dependency closure of affected Snapshots, Capsules, proposals, approvals, Intents, authorizations, capabilities, open attempts, orders, capacity, and protection. New-risk permission is revoked or denied before future send. Existing or uncertain economic effects remain explicit and conservatively capacity-covered.

After a broker send, corrected context may prove the decision was based on bad input, but it cannot retroactively make non-acceptance, cancellation, or zero exposure true. Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof.

---

## 18. Degraded Operation and Protective Use

Input degradation SHALL NOT become ordinary new-risk permission. Permitted responses are:

- deny, HALT, narrow scope, or suspend affected authority;
- continue evidence capture, reconciliation, source diagnosis, and recovery;
- preserve existing required protection;
- request separately authorized containment or protective action under ADR-002-001, ADR-002-003, ADR-002-011, RCL capacity, current trustworthy time, broker capability, and final-egress rules.

A protective label does not make stale data safe. The Protective Action Controller SHALL use an approved conservative input set and prove the action’s intermediate and final economic bounds. Priority is not reserved protective capacity. If the necessary protective inputs are unavailable or contradictory, the response is broader containment and escalation, not invented certainty.

An operator-provided price, symbol, quantity, mapping, venue state, or account fact is a Critical Input and follows the same provenance, policy, approval, evidence, and egress rules. Break-glass may HALT or narrow; it cannot inject a permissive value or direct broker order.

---

## 19. Failure, Partition, Restart, and Restore

| Condition | Required response |
|---|---|
| Source unavailable or late | mark affected fields stale/unknown; block new risk; preserve conservative capacity |
| Sources disagree | retain all observations and common-mode analysis; apply approved semantic authority or deny |
| Sequence gap/reset/rollback | create continuity gap/new generation; invalidate dependants; no cached continuity assumption |
| Parser/schema/mapping drift | stop admission; invalidate affected context; quarantine derived outputs |
| Context service partitioned from authority/egress | no new-risk context proof; final egress denies |
| Correction arrives after approval | invalidate chain before future send; if already sent, preserve potentially-live effect and reconcile |
| Snapshot/Capsule store unavailable | cannot create or validate new-risk context; existing economic state persists |
| Restart with warm cache | cache is recovery input only; re-establish source continuity and fresh Snapshot |
| Restore older policy/data history | preserve branches; create new generations; do not select by timestamp or convenience |
| Invalidation propagation exceeds bound | HALT or contain affected scope; evidence item fails |
| Human requests stale-data override | deny; allow only restrictive direction or separately governed containment |

Former source, parser, mapping, or context instances remain potentially current until fenced or their inability to publish accepted observations is positively proven.

---

## 20. Recovery and Non-Revival

ADR-002-017 Recovery Obligations SHALL inventory:

- policy, Context Generation, source registry, continuity identities, gaps, corrections, and source-health semantics;
- raw observations, transformation lineage, Snapshots, Capsules, dependent approvals/Intents/capabilities, and invalidations;
- schema, mapping, unit, account, instrument, venue, session, parser, model, deployment, credential, and endpoint generations;
- common-mode and source-independence claims;
- outstanding UNKNOWN, external, non-trade, protective, capacity, and evidence effects.

Recovery SHALL not mark a cached value current merely because the source reconnects or the value matches replay. A restarted or restored source establishes new continuity unless continuity across the event is positively proven by its approved protocol. A new Snapshot and Capsule are required after material recovery.

Recovery readiness grants no input exception and no live permission. Fresh human approval, Live Authorization, capability, and final-egress validation remain mandatory. There is no automatic re-arm.

---

## 21. Evidence, Metrics, and Alerts

ADR-002-016 governs evidence custody. Required records include:

- Critical Input Policy proposal, review, activation, supersession, and generation;
- source registry, principal, endpoint, credential reference, continuity, sequence/revision, schema, and admission result;
- raw observations and correction/retraction lineage;
- transformations, code/config/model identity, units, mappings, parameters, intermediate and output digests;
- Snapshot dependency graph, consistency cut, field states, freshness, uncertainty, corroboration, and common-mode analysis;
- Capsule canonical bytes, digest, scope, generations, age, validity, and invalidation;
- proposal, approval, Intent, capacity, authorization, capability, proof, evidence receipt, egress, and broker binding;
- every denial, conflict, gap, timeout, fallback, operator action, protective request, and residual-risk decision;
- post-send correction impact, UNKNOWN state, reconciliation, capacity preservation, and recovery/re-arm lineage.

Metrics SHALL include source and receipt age, continuity changes, sequence gaps, duplicate conflicts, schema/mapping/unit failures, cross-field failures, source disagreement, Snapshot/Capsule age, common-mode dependency count, invalidation fan-out and latency, stale-context egress denial, UNKNOWN capacity, and recovery duration.

Critical alerts include unclassified safety input, unknown source, continuity rollback, silent coercion/default, unit or mapping mismatch, stale/future data accepted, proposer-only approval input, false independence, Capsule substitution, invalidation missed at egress, context-service authority escalation, context expiry releasing capacity, or data recovery re-arming live scope.

Documentation, audit, lineage, replay, and alerts are evidence. They do not replace preventive admission, invalidation, authority, RCL, or final-egress gates.

---

## 22. Security and Common-Mode Analysis

The threat model SHALL cover:

- source credential or endpoint compromise and source substitution;
- replayed or fabricated observations, sequence rollback, and continuity reset;
- parser, schema, mapping, unit, multiplier, sign, and instrument-identity manipulation;
- shared library, cache, feature store, message bus, time source, administrator, CI/CD, or deployment corruption;
- proposer influencing approval source selection or residual-risk declaration;
- Capsule digest substitution, downgrade, union, partial refresh, or invalidation suppression;
- stale context principal, restored database, or isolated service publishing accepted state;
- direct route from data, decision, operator, or replay systems to broker egress;
- denial of input service used to pressure a permissive fallback.

Source diversity is not independence until effective control, origin, transformation, identity, deployment, and failure-domain paths are evidenced. Unknown common-mode scope is treated as shared.

Compromise containment SHALL advance appropriate policy/context/source generations, deny affected new risk, fence publishers and consumers, preserve raw evidence and economic effects, and require ADR-002-017 recovery plus fresh re-arm.

---

## 23. Rejected Alternatives

### 23.1 Validate Only at Ingestion

Rejected because mapping, transformation, freshness, correction, and decision-to-send substitution can occur after ingestion.

### 23.2 “Healthy Feed” Boolean

Rejected because one blended flag hides per-field provenance, uncertainty, continuity, and common-mode failure.

### 23.3 TTL or Last-Known-Good Permits New Risk

Rejected because age alone does not prove semantic validity, continuity, venue state, or absence of correction.

### 23.4 Two Consumers Equal Independent Approval

Rejected because they may share the same corrupted source, parser, mapping, cache, identity, or administrator.

### 23.5 Patch an Approved Context

Rejected because partial refresh breaks exact review and authority binding.

### 23.6 Majority Vote Resolves Source Conflict

Rejected because majority paths may share one origin or have different semantic authority.

### 23.7 Human Override of Missing Input

Rejected because a human-entered permissive fact is still a Critical Input and cannot waive constitutional controls.

### 23.8 Egress Trusts Upstream “Validated” Status

Rejected because the final irreversible boundary must reject stale, substituted, invalidated, or unverifiable context.

### 23.9 Correction or Expiry Releases Capacity

Rejected because economic effect survives artifact lifecycle and correction can increase uncertainty.

### 23.10 Replay Match Restores Permission

Rejected because replay is evidence, not prevention or authority, and recovery cannot automatically re-arm.

---

## 24. Consequences

### 24.1 Positive

- Safety decisions become attributable to exact immutable input semantics and versions.
- Source restart, correction, mapping drift, and common-mode corruption cannot silently preserve permission.
- Independent approval has an enforceable meaning beyond process separation.
- Context cannot change between proposal, approval, capacity, and broker send without a new chain.
- Final egress blocks stale or substituted context while remaining separate from strategy logic.
- UNKNOWN and corrections preserve conservative capacity and economic continuity.
- Recovery cannot revive data-derived authority.

### 24.2 Negative

- Source contracts, lineage, dependency graphs, and canonical Capsules add latency and storage.
- Some feeds, derived features, or broker scopes may be unusable live because provenance or continuity is insufficient.
- Independent corroboration can require diverse sources or implementations and explicit residual scope reduction.
- Corrections may invalidate many downstream artifacts and reduce availability.
- Active currentness and egress invalidation propagation add control-plane complexity.

These costs are accepted. Availability SHALL be improved by better evidence and bounded mechanisms, not weaker trust rules.

---

## 25. Acceptance Cases

The following cases are mandatory and map one-to-one to `CII-EV-001` through `CII-EV-012`. Written cases are not completed evidence.

| Acceptance case | Required result |
|---|---|
| `CII-AC-001` | Every value capable of changing safety or economic effect is classified Critical and no feature/cache/override/derived-value naming bypasses policy |
| `CII-AC-002` | Unknown source, continuity reset, sequence gap, rollback, endpoint or credential substitution, schema drift, and replayed observation are rejected or made explicitly non-permissive |
| `CII-AC-003` | Wrong instrument/account/venue/currency/unit/scale/sign/multiplier and ambiguous mapping cannot produce approved or transmitted new risk |
| `CII-AC-004` | Hidden defaults, fill-forward, imputation, parser/library/model/config drift, and unreproducible transformation invalidate derived Critical Inputs |
| `CII-AC-005` | Non-atomic, stale, future, crossed, outlier, conflicting, and source-disagreed inputs remain field-explicit and conservative; no majority, cache, or health shortcut creates trust |
| `CII-AC-006` | Proposer and approver sharing source, parser, mapping, cache, administrator, or failure domain are identified as common mode and cannot satisfy independent corroboration |
| `CII-AC-007` | Capsule mutation, union, partial refresh, digest substitution, wrong scope/generation, and downstream hidden recomputation invalidate the full proposal-to-egress chain |
| `CII-AC-008` | Correction, retraction, continuity/policy/mapping change, and freshness expiry invalidate affected permission before future authority issuance and final egress |
| `CII-AC-009` | Final egress actively proves exact current context without permissive cache; stale or unverifiable state is denied and the send race remains potentially live/capacity-covered when ambiguous |
| `CII-AC-010` | Input outage and degraded operation block new risk while HALT and only separately authorized capacity-backed protective/containment actions remain possible |
| `CII-AC-011` | Context service, data operator, human override, evidence, and replay cannot approve, mutate/release RCL capacity, classify protection, issue authority, transmit, clear HALT, or force readiness |
| `CII-AC-012` | Restart, restore, source recovery, cache warm-up, evidence repair, and replay match create no authority revival or automatic re-arm; economic and UNKNOWN effects persist |

---

## 26. Requirements Traceability

| Requirement | ADR-002-018 allocation |
|---|---|
| SAFE-003, SAFE-004, SAFE-050 | Critical Input Policy is separately governed, immutable, semantically validated, and non-arming (§§7–8) |
| SAFE-010, SAFE-011, SAFE-013, SAFE-015 | Context cannot bypass pre-trade gates or RCL-only capacity authority (§§7, 15–16) |
| SAFE-020, SAFE-021 | Exact Capsule identity binds Intent, attempt, capability, proof, and send while ambiguity remains potentially live (§§12, 15–17) |
| SAFE-022 through SAFE-025 | Account/broker evidence, corrections, partial state, and non-atomic cuts stay field-explicit and conservative (§§11, 17, 19) |
| SAFE-030 | Only complete, fresh, valid, consistent, purpose-suitable context may support new risk (§§8–16) |
| SAFE-031 | Source, time, unit, instrument, account, schema, processing, and lineage provenance are mandatory (§§9–12) |
| SAFE-032 | Venue, session, tradability, halt, price-limit, settlement, margin, and order constraints remain current through egress (§§12, 16–17) |
| SAFE-033 | Intent and broker request remain bound to exact approved account, instrument, direction, quantity, unit, price, effect, expiry, and mode (§§12, 15–16) |
| SAFE-034 | Approval independently validates safety facts and exposes common modes or governed residual risk (§13) |
| SAFE-035 | Freshness, ordering, source time, receipt age, and discontinuity follow trustworthy time (§14) |
| SAFE-040, SAFE-041 | Degradation narrows authority and preserves separately governed protection/HALT (§18) |
| SAFE-044, SAFE-046, SAFE-048 | Recovery, partition, currentness loss, and generation changes fail closed and require fresh re-arm (§§16, 19–20) |
| SAFE-051, SAFE-052 | Complete source-to-egress lineage and isolated replay evidence are retained without becoming authority (§21) |

---

## 27. Open Implementation Questions

Open questions reduce authority or keep scope non-live. They do not weaken the rules above.

1. Which Critical Input Policy schema, canonicalization, governance, and activation mechanism are approved?
2. Which source registry, workload identity, credential-reference, endpoint, and Source Continuity protocol cover each initial source?
3. Which schema registry, unit system, instrument/account mapping registry, transformation manifest, and lineage engine are conforming?
4. Which sources and diverse validation implementations satisfy independent approval for each safety-critical fact?
5. Where independence is infeasible, which residual-risk review, added checks, and scope reductions satisfy SAFE-034?
6. Which Consistency Cut and source-authority rules apply to non-atomic market, reference, account, venue, and session inputs?
7. Which ordered Context Generation and invalidation graph fence stale publishers, approval, authorization, and final egress?
8. How do issuers and final egress actively establish current policy, continuity, generation, and invalidation state without a permissive cache or circular dependency?
9. Which correction, retraction, source-loss, mapping, time, venue, external, and non-trade events invalidate which dependency closure?
10. Which conservative last-known-good and protective input rules are approved without permitting ordinary new risk?
11. Which artifacts and indexes let ADR-002-016 reconstruct every source-to-broker dependency and correction?
12. What values for `B_critical_input_loss_detect`, `B_critical_input_invalid_to_authority`, `B_critical_input_invalid_to_egress`, `MAX_critical_input_snapshot_age`, `MAX_decision_context_age`, correction horizon, transport uncertainty, and source-specific freshness are approved?

---

## 28. Approval Gate

ADR-002-018 SHALL remain **Proposed** until all of the following are complete:

1. Critical Input Policy, Critical Input Observation, Snapshot, Decision Context Capsule, source continuity, lineage, and invalidation schemas/canonicalization are approved;
2. all safety-relevant input classes, sources, units, mappings, transformations, consumers, and dependency closures are inventoried;
3. source identity, continuity, sequence/revision, schema, gap, correction, and restore mechanisms are implemented and security-reviewed;
4. freshness, consistency-cut, source-authority, range, cross-field, mapping, unit, and uncertainty rules are approved;
5. independent-approval paths and common-mode analyses are implemented for each safety-critical fact, with residual risks and scope reductions approved where needed;
6. exact Capsule binding is enforced through proposal, approval, Intent, capacity, Live Authorization, capability, Commit Proof, evidence receipt, and broker request;
7. Context Generation, invalidation fan-out, active issuer/egress currentness, stale-principal fencing, and ambiguous-send handling are implemented and independently reviewed;
8. RCL-only capacity mutation, HALT dominance, protective confinement, correction/economic continuity, recovery, and no-automatic-re-arm behavior are demonstrated;
9. ADR-002-016 evidence, source continuity, gap detection, retention, correction lineage, and isolated replay are implemented for all Critical Input artifacts;
10. `CII-EV-001` through `CII-EV-012` and applicable cross-ADR evidence pass at required levels and receive independent review;
11. ADR-002-019 consumes venue/session/tradability/account/broker Critical Inputs through an exact policy-owned Snapshot/Decision contract without converting context validation into admissibility or authority, and applicable VTG evidence passes;
12. ADR-002-020 consumes the exact Capsule in candidate command and conformance proof without hidden refresh or recomputation, and applicable IOC evidence passes;
13. source-loss, freshness, invalidation-to-authority, invalidation-to-egress, Snapshot/Capsule, venue-decision, command/proof age, correction, time, evidence, broker, and recovery bounds are approved and measured;
14. no unresolved unclassified-input, common-mode, mapping/unit, source-continuity, correction, context/constraint/conformance-substitution, permissive-cache, egress-bypass, capacity-release, or automatic re-arm path remains;
15. ARCHITECTURE-GATE-STATUS records an explicit acceptance decision.

Until those gates pass, this ADR authorizes architecture and implementation-planning work only. It does not claim verification completion, ADR acceptance, restricted-live readiness, production readiness, or live trading authority.
