# ADR-002-029 — Software Supply-Chain Integrity, Release-Artifact Admission, and Deployment Provenance Governance

- **Status:** Proposed
- **Date:** 2026-07-14
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Source revision integrity, isolated build provenance, dependency and toolchain closure, release-artifact identity, signing and registry custody, independent artifact admission, Release Generation, deployment promotion, runtime attestation, restriction, rollback, restore, currentness, evidence, recovery, and acceptance
- **Supersedes:** None
- **Refines:** RFC-001 §§6–8, §§11.3–11.5, §§13.4–13.6, Appendix B, and SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-014, SAFE-030, SAFE-031, SAFE-033 through SAFE-035, SAFE-041, SAFE-044 through SAFE-048, SAFE-050, SAFE-051, and SAFE-052; RFC-002 §§4.1–4.7, 7, 8, 9.1, 10.13, 10.16, 10.18–10.21, 10.24, 10.26–10.30, 17–19, and 23–25; VER-002-001 §§5, 350–361, 374, and 377–381
- **Depends On:** RFC-000; RFC-001; ADR-002-001 through ADR-002-028

---

## 1. Decision

The Trading Operating System SHALL treat software source, build inputs, dependencies, toolchains, release artifacts, signing identities, registries, deployment state, and actual runtime bytes as safety-critical inputs governed by an exact, content-addressed, generation-fenced, fail-closed, and non-authorizing protocol.

One ADR-002-014 governed **Software Release Policy** SHALL define the approved source, review, build, dependency, toolchain, provenance, reproducibility, signing, registry, admission, compatibility, deployment, runtime-attestation, restriction, evidence, recovery, and failure rules for one exact scope. Missing, stale, conflicting, ambiguous, incompletely closed, unapproved, or unverifiable supply-chain state grants zero eligibility for dependent new risk.

Every candidate SHALL bind one immutable **Source Revision Manifest**, one complete **Dependency and Toolchain Closure Manifest**, one **Build Provenance Attestation**, and one **Release Artifact Manifest**. Those artifacts SHALL identify exact scalar digests and closed-set digests. A branch, tag, package name, registry path, service label, mutable image tag, `latest`, local cache, successful build, passing scan, or historical signature is not artifact identity and is not current admission proof.

An independent **Artifact Admission Decision** may return only `ADMIT`, `DENY`, or `UNKNOWN` for one exact release artifact, policy, compatibility graph, target scope, and predecessor Release Generation. `ADMIT` means only that the exact artifact is eligible to be included in one new **Admitted Release Set**. It does not deploy software, activate configuration, issue Safety Authority or Live Authorization, mutate or release Risk Capacity Ledger capacity, classify protection, create a Transmission Capability, permit broker transmission, clear HALT, close an incident, establish recovery readiness, restore production scope, or re-arm.

One monotonic **Release Generation** SHALL identify the exact Software Release Policy, Admitted Release Set, artifact lineage, compatibility state, restriction floor, and deployment scope. A rollback, restore, rebuild, re-sign, registry recovery, signer recovery, dependency correction, hotfix, or identical byte sequence SHALL use a new generation. No historical admission, configuration activation, deployment success, trial result, or prior Live Authorization may revive a superseded, revoked, rejected, quarantined, or restored generation.

Every safety-critical runtime SHALL produce a current **Runtime Artifact Attestation** binding the actual executable, image, library, plugin, sidecar, proxy, serializer, SDK, signer component, configuration, workload identity, deployment identity, environment, and Safety Cell to the exact admitted artifact set. Desired deployment state, process health, workload name, image tag, orchestrator status, canary success, or absence of drift alerts is not proof of actual runtime identity.

Every permission-creating consumer and the Broker Adapter / Egress Gateway SHALL actively verify the exact current Release Generation, Admitted Release Set digest, applicable Release Artifact Manifest digest, Runtime Artifact Attestation, compatibility result, and restriction floor as part of ADR-002-024 active currentness. A successful check is only a negative gate. It cannot supply capacity, authority, protection, approval, admissibility, or permission that another owner has not independently granted.

Suspected source, builder, dependency, toolchain, signer, registry, admission, deployment, or runtime compromise SHALL restrict the greatest credible dependency scope and enter ADR-002-027 incident governance. Missing ACK remains possible acceptance. Cancel ACK is not Final Quantity Proof. Artifact expiry, revocation, deletion, rollback, or restore never expires economic effect or releases capacity. Documentation, SBOMs, signatures, scans, tests, audit, and replay do not substitute for prevention. Recovery never automatically re-arms.

---

## 2. Context

RFC-002 assigns deployment provenance and independent safety-component release controls to Deployment and Identity Architecture. ADR-002-009 requires immutable artifact identity, source revision, build provenance, artifact digest, compatibility, and deployment fencing. ADR-002-014 binds software compatibility into safety configuration. ADR-002-016 preserves software and build evidence. ADR-002-020 binds compiler, serializer, SDK, dependency, and build identity into command conformance.

Those obligations do not define one closed protocol from reviewed source to actual runtime bytes. Without this ADR, an implementation could:

- sign an artifact built from unreviewed generated source or a substituted submodule;
- fetch a mutable dependency, plugin, compiler, SDK, base image, or build script after review;
- treat a provenance signature as proof that source or output is safe;
- scan one artifact and deploy another platform variant or registry layer;
- count build, signer, registry, and admission accounts controlled by one person as independent;
- accept a valid signature after signer compromise or key rollback;
- use mutable tags or `latest` as an identity at configuration or egress;
- combine individually admitted old and new components into an unproved mixed release;
- treat deployment, canary, readiness, or health success as live permission;
- roll back to a historically accepted artifact and reuse prior authority;
- restore an older admission registry that omits a later restriction;
- leave a stale pod, sidecar, proxy, signer, or broker-capable session active after replacement; or
- let supply-chain recovery, evidence repair, or incident closure revive release eligibility automatically.

This ADR closes those paths while preserving the authority ownership already assigned to configuration governance, Safety Authority, RCL, protective classification, final egress, incident response, recovery, and re-arm.

---

## 3. Decision Drivers

1. The exact bytes executing a safety decision must be attributable to reviewed source and a complete build closure.
2. A signature proves an authenticated statement, not correctness, completeness, compatibility, currentness, or permission.
3. Transitive dependencies, toolchains, generated code, plugins, and runtime-loaded modules must not remain hidden inputs.
4. Build, signing, registry, admission, deployment, activation, arming, and transmission authorities must remain separate under effective control.
5. Mutable names, tags, registries, caches, and deployment labels must not become artifact identity.
6. Mixed-version and partial deployment must fail closed unless exact compatibility and safety dominance are proven.
7. Compromise and revocation must reach authority consumers and final egress through a monotonic restrictive path.
8. Rollback, restore, hotfix, rebuild, or recovery must not revive prior admission or live authority.
9. Artifact lifecycle must not alter broker finality, economic effect, UNKNOWN, or RCL ownership.
10. Written cases, signatures, scans, and retained evidence must not be confused with executed verification or live readiness.

---

## 4. Scope and Non-Scope

This ADR governs:

- source revision identity, protected review, generated source, submodule, and external-source closure;
- deterministic build recipes, builder identity, isolation, and provenance;
- complete transitive dependency and toolchain closure;
- artifact identity, signing, registry custody, retrieval, and substitution resistance;
- independent admission, compatibility evaluation, Release Generation, and Admitted Release Set;
- deployment staging, promotion, mixed-version behavior, and actual runtime attestation;
- compromise, restriction, revocation, stale-writer fencing, partition, and send races;
- rollback, restore, emergency hotfix, evidence, recovery, and non-revival;
- final-egress release currentness and acceptance evidence.

It does not select:

- a source-control, build, package, signing, registry, scanner, deployment, or attestation product;
- a programming language, compiler, operating system, container runtime, or orchestration platform;
- the semantic correctness of trading logic, which remains governed by the applicable safety and conformance ADRs;
- safety configuration activation, which remains ADR-002-014;
- production-scope promotion, which remains ADR-002-025;
- incident declaration or closure, which remains ADR-002-027;
- a broker-specific Final Quantity Proof; or
- production authorization.

---

## 5. Definitions

### 5.1 Software Release Policy

The immutable ADR-002-014 governed policy defining source, build, dependency, toolchain, provenance, signing, registry, admission, compatibility, deployment, attestation, restriction, evidence, and recovery rules for one exact scope.

### 5.2 Source Revision Manifest

An immutable manifest binding one exact repository identity, source-tree digest, revision digest, review-policy digest, generated-source digest, submodule-closure digest, external-source digest, and source-history continuity identity.

### 5.3 Build Recipe

The immutable exact build definition covering commands, ordered steps, environment, platform, declared inputs, network policy, deterministic settings, allowed nondeterminism, and output rules.

### 5.4 Dependency and Toolchain Closure Manifest

An immutable manifest binding the complete transitive dependency, build script, plugin, compiler, linker, interpreter, SDK, code generator, base image, operating-system package, runtime-loaded module, registry source, and resolution-policy closure by canonical digest.

### 5.5 Build Provenance Attestation

An authenticated non-authorizing statement binding one builder identity and epoch, source manifest, build recipe, dependency and toolchain closure, build environment, output artifact digest, and trustworthy-time evidence.

### 5.6 Release Artifact Manifest

An immutable manifest binding the exact release bytes, platform and architecture, source and build lineage, dependency closure, software bill of materials digest, schemas, protocols, migrations, compatibility graph, required policy/configuration identities, and intended deployment scope.

### 5.7 Artifact Admission Decision

An immutable single-use non-authorizing result of `ADMIT`, `DENY`, or `UNKNOWN` for one exact Release Artifact Manifest, Software Release Policy, compatibility graph, target scope, and predecessor Release Generation.

### 5.8 Release Generation

A monotonic restrictive generation identifying one exact committed Admitted Release Set, policy, scope, compatibility state, restriction floor, and predecessor. It cannot be reused after rejection, revocation, rollback, restore, compromise, or supersession.

### 5.9 Admitted Release Set

The complete canonical set digest of exact Release Artifact Manifests eligible for deployment in one scope and Release Generation. It is a non-authorizing negative gate and cannot be patched, unioned, widened, or resolved through mutable names.

### 5.10 Runtime Artifact Attestation

An authenticated current statement binding the actual loaded and executable artifact-set digest, runtime dependency digest, workload and deployment identities, environment, Safety Cell, configuration digest, attestor identity, owner epoch, receipt anchor, and Release Generation.

### 5.11 Release Restriction

A monotonic scope-complete fact that one source, build, dependency, signer, registry, admission, artifact, deployment, runtime, or Release Generation cannot support future new-risk permission.

### 5.12 Artifact Lineage and Compatibility Graph

The closed graph from reviewed source through build inputs and artifact outputs to every deployed consumer, protocol, schema, migration, configuration, identity, route, and final-egress compatibility edge.

---

## 6. Safety Invariants

### SCI-INV-001 — Supply-Chain Artifacts Are Not Authority

No policy, manifest, provenance attestation, signature, admission decision, release set, deployment record, runtime attestation, scan, test, or evidence artifact creates capacity, approval, protection, live authority, broker permission, incident closure, readiness, scope restoration, or re-arm.

### SCI-INV-002 — Artifact Identity Is Exact and Immutable

Safety-relevant identity uses exact canonical content digests. Tags, branches, package names, registry paths, service names, deployment labels, timestamps, `latest`, and local cache state are not identity or currentness proof.

### SCI-INV-003 — Source-to-Artifact Lineage Is Closed

Every generated source, submodule, external object, build recipe, dependency, toolchain, plugin, base image, and runtime-loaded input is inside the exact lineage closure. Unknown or omitted input is restrictive.

### SCI-INV-004 — Provenance Is Not Correctness

Valid build provenance or a reproducible output does not prove semantic safety, absence of malicious source, current admission, compatibility, or live permission.

### SCI-INV-005 — Dependency and Toolchain Closure Is Complete

Mutable, dynamic, undeclared, floating, unbounded, or ambiguously resolved dependencies and toolchains cannot support admission or dependent new risk.

### SCI-INV-006 — Admission Is Deterministic and Exact-Scope

Admission binds one exact policy, artifact, lineage, compatibility graph, scope, and predecessor generation. Missing, wildcarded, patched, unioned, mixed, or conflicting scope is `UNKNOWN` or `DENY`.

### SCI-INV-007 — Effective Independence Is Required

Source author, reviewer, builder, signer, registry administrator, admission reviewer, deployer, configuration activator, and live armer are evaluated by effective control and common mode before independence or quorum is credited.

### SCI-INV-008 — Signature Is Not Current Admission

A signature from a compromised, revoked, stale, wrong-scope, wrong-environment, rolled-back, or unverifiable key grants nothing. Historical signature validity cannot defeat a newer restriction.

### SCI-INV-009 — One Complete Release Generation Governs Scope

Every overlapping scope binds one complete current Release Generation and Admitted Release Set. Partial deployment and favorable subsets cannot form a permissive union.

### SCI-INV-010 — Actual Runtime Bytes Must Match

Every executable, library, plugin, sidecar, proxy, SDK, signer component, and runtime-loaded module affecting safety matches the exact current attested artifact set. Desired state and process health are insufficient.

### SCI-INV-011 — Unknown Compatibility Is Incompatibility

Mixed versions may operate only where every affected protocol, schema, migration, state, configuration, library, and egress edge has an exact approved compatibility and safety-dominance proof.

### SCI-INV-012 — Rollback and Restore Are New Generations

Rollback, restore, rebuild, re-sign, hotfix, registry recovery, or identical bytes require a new Release Generation and fresh governed admission. No predecessor admission or authority revives.

### SCI-INV-013 — Active Release Currentness Is a Negative Gate

Every permission-creating consumer and final egress actively verifies the exact current release facts and restriction floors. Cache, TTL, heartbeat, health, deployment status, and absence of revocation are not currentness proof.

### SCI-INV-014 — Restriction Dominates Send Races

A release restriction ordered before capability claim denies send. Unprovable ordering against first broker-directed byte leaves the attempt potentially live, capacity-covered, and ineligible for blind retry.

### SCI-INV-015 — Economic Effect Outlives Artifact State

Artifact, signature, admission, release-set, deployment, or attestation expiry, deletion, invalidation, revocation, rollback, or supersession never proves non-acceptance, Final Quantity, zero exposure, or capacity release.

### SCI-INV-016 — Evidence and Recovery Do Not Revive

SBOMs, signatures, scans, tests, CI results, deployment reports, evidence, replay, incident closure, registry recovery, signer recovery, or runtime health cannot substitute for prevention, mark verification complete, restore prior authority, or automatically re-arm.

---

## 7. Authority Ownership and Separation

| Action | Owner | Prohibited implication |
|---|---|---|
| Propose source change | source author | cannot approve, build, admit, deploy, or arm its own change |
| Approve exact source revision | independent source-review authority | review does not build, sign, admit, or authorize live use |
| Build artifact and provenance | fenced build service | build success and provenance do not create admission |
| Resolve dependency/toolchain closure | governed resolver and verifier | resolver cannot omit a dependency or self-admit output |
| Sign artifact or attestation | independently controlled artifact signer | signature cannot create current admission or permission |
| Store and retrieve artifact | immutable artifact registry | registry presence or tag resolution cannot admit |
| Decide artifact admission | independent Release Admission Authority | decision cannot deploy, activate, arm, mutate capacity, or transmit |
| Commit Release Generation | fenced Release Registry / ordering domain | release-set commit creates no configuration activation or live authority |
| Deploy exact admitted artifact | deployment controller | deployment starts non-live and cannot self-admit or arm |
| Attest actual runtime bytes | independent runtime-attestation path | attestation is a fact, not permission |
| Activate configuration | ADR-002-014 governance | activation does not admit software or prove actual runtime bytes |
| Restrict current use | ADR-002-024 restrictive path and existing owners | supply-chain service cannot clear the resulting latch |
| Mutate or release capacity | Risk Capacity Ledger only | artifact lifecycle never writes capacity |
| Classify protection | Protective Action Controller | release labels cannot create protective classification or reserve |
| Declare or close incident | ADR-002-027 governance | supply-chain signal does not own incident lifecycle |
| Transmit | Broker Adapter / Egress Gateway | exact current release state is mandatory but not sufficient |
| Establish readiness and re-arm | ADR-002-017 then ADR-002-007/015 | recovery, deployment, or admission cannot auto-rearm |

No source, build, dependency, signing, registry, admission, deployment, attestation, scan, CI/CD, evidence, or replay identity may hold a usable live-order credential and broker route. If combined inside final egress, the complete identity and code path is inside the ADR-002-013 trust boundary and must enforce every gate.

---

## 8. Software Release Policy

The Software Release Policy SHALL bind:

- exact policy identity, generation, canonical digest, predecessor, and scope;
- approved source repositories, review policies, effective-principal rules, and history protections;
- approved build recipes, builders, network policy, deterministic settings, and allowed nondeterminism;
- dependency, toolchain, package-source, base-image, plugin, code-generation, and runtime-loading rules;
- provenance, independent-build, reproducibility, differential, scan, test, and evidence requirements;
- signer, key, threshold, rotation, revocation, registry, and custody rules;
- artifact-manifest, admission, compatibility, deployment, runtime-attestation, and Release Generation contracts;
- restriction, incident, rollback, restore, hotfix, recovery, and final-egress currentness behavior;
- approved numeric bounds and age limits.

Unknown fields, mutable references, hidden defaults, local overrides, consumer-selected substitutions, implicit inheritance, or `latest` resolution are prohibited. Policy activation follows ADR-002-014 and creates neither artifact admission nor live permission.

---

## 9. Source Revision Integrity

The Source Revision Manifest SHALL bind one exact source-tree digest and closed external-source digest. The closure includes generated source, submodules, vendored objects, large-file objects, schemas, migration source, build scripts, code generators, lock files, and safety-relevant documentation consumed by generation or build.

Source review SHALL verify the exact manifest digest and effective-principal independence. Repository administration, branch protection, signed commits, review count, or merge status alone does not prove independence when one person controls the underlying accounts, recovery paths, automation, or signing identities.

Force push, history rewrite, deleted branch, moved tag, mirror divergence, submodule retarget, regenerated source, or repository restore advances source continuity and invalidates affected unconsumed admission decisions. Identical tree bytes may be proposed again only through a fresh current policy and generation.

---

## 10. Build Isolation and Determinism

Every release build SHALL use one exact Build Recipe and an isolated, fenced builder identity and epoch. Inputs not present in the Source Revision Manifest or Dependency and Toolchain Closure Manifest are denied.

The build SHALL prevent undeclared network fetch, mutable environment inheritance, unbound secrets, locale or timezone drift, hidden wall-clock reads, randomness, nondeterministic ordering, host-library leakage, mutable cache substitution, and platform ambiguity unless the exact value is policy-approved and bound into provenance.

Builder restart, replacement, rollback, image change, cache restore, credential rotation, or runner recovery creates a new builder continuity identity. A healthy runner, CI success, cached output, or prior reproducible build cannot preserve current admission by itself.

---

## 11. Dependency and Toolchain Closure

The closure manifest SHALL cover all transitive build-time and runtime dependencies, package sources, plugins, compilers, linkers, interpreters, SDKs, code generators, base images, operating-system packages, native libraries, dynamically loaded modules, sidecars, proxies, migration tools, and signer components that can change safety-relevant behavior or broker-directed bytes.

Each item SHALL bind exact content identity, source, semantic role, version, platform, license or policy classification where applicable, known correction and revocation state, and compatibility relationships. A lock file is evidence only when it closes all resolution paths and exact fetched bytes match it.

Missing dependency, floating version, mutable package source, ambiguous platform selection, unknown transitive script, unavailable status source, or unresolved correction is restrictive. Majority registry results, previous successful install, local package cache, or expected compatibility cannot supply a favorable answer.

---

## 12. Build Provenance and Independent Reproduction

The Build Provenance Attestation SHALL bind exact source, recipe, closure, builder, environment, output, time, and continuity identities. The signer authenticates that statement; it does not certify safety.

Where policy requires independent reproduction, independence is evaluated across effective control, source mirror, builder, dependency source, toolchain, parser, signer, registry, network, identity provider, and administrator. Two builds sharing a corrupted compiler or package source are one common-mode path.

Output disagreement is `UNKNOWN` or `DENY`; the release process cannot select the favorable artifact. Approved nondeterminism SHALL be explicitly bounded and compared semantically without excluding any byte or behavior that can affect safety, identity, compatibility, or broker transmission.

---

## 13. Artifact Signing and Key Governance

Artifact signatures and provenance attestations SHALL bind exact canonical artifact and statement digests, artifact type, policy, environment, scope, signer identity, key generation, validity, and revocation state.

Signing keys SHALL be environment-scoped, least privilege, independently controlled, rollback-protected, and unable to sign arbitrary broker requests. Rotation is deny-first unless a bounded overlap is explicitly approved and both generations remain attributable and non-bypassable.

Suspected signer compromise, recovery-path compromise, unauthorized signing, key rollback, missing revocation status, stale trust bundle, or signature/parser differential creates a Release Restriction for the greatest credible scope. A compromised signer cannot attest its own recovery, and a historical signature cannot defeat a newer restriction.

---

## 14. Artifact Registry and Custody

Release artifacts SHALL be stored and retrieved by immutable content digest. Registry tags and paths may be discovery metadata only; every consumer verifies the complete manifest, platform variant, layer/blob closure, signature, and canonical digest after retrieval and before use.

The registry SHALL preserve provenance, admission, restriction, revocation, tombstone, and restore history. Garbage collection, replication, mirror failover, tag mutation, manifest-list resolution, partial upload, stale replica, or backup restore cannot make unavailable or historical bytes current.

If registry history, digest closure, current restriction state, or retrieved bytes cannot be proven, the artifact is quarantined and dependent new risk is denied. Registry availability and artifact presence are not admission.

---

## 15. Artifact Admission Protocol

Admission SHALL follow this order:

1. bind one exact current Software Release Policy and target scope;
2. verify Source Revision Manifest identity, review, continuity, and effective-principal independence;
3. verify the complete dependency and toolchain closure and correction state;
4. verify Build Provenance Attestation, builder epoch, output digest, and required independent reproduction;
5. verify Release Artifact Manifest, signature, registry custody, schemas, protocols, migrations, and compatibility graph;
6. verify required scans, tests, evidence receipts, and unresolved findings without treating them as authority;
7. verify predecessor Release Generation and every current restriction floor;
8. issue one immutable `ADMIT`, `DENY`, or `UNKNOWN` decision for the exact candidate;
9. independently commit any eligible `ADMIT` decision into one new complete Admitted Release Set and Release Generation;
10. invalidate the single-use decision and every stale competing candidate.

Admission failure is denial. Decisions cannot be patched, unioned, replayed, widened, or silently re-evaluated with newer favorable inputs. Material change creates a new candidate and decision.

---

## 16. Release Generation and Admitted Release Set

The Release Registry SHALL serialize one current Release Generation per overlapping scope. The committed record binds exact policy, artifact-set, lineage-graph, compatibility, approval, predecessor, restriction-floor, target, and evidence digests.

The Admitted Release Set is complete. Missing artifact, extra artifact, mixed platform, undeclared sidecar, local patch, runtime plugin, consumer override, or union of narrower sets invalidates the set for the affected scope.

New restrictive facts advance the release restriction floor without waiting for a replacement permissive set. Old admission publishers, registries, deployment controllers, restored databases, and runtime attestors are potentially active until hard fencing proves they cannot publish or consume a current release fact.

---

## 17. Deployment Promotion and Compatibility

Software deployment promotion across development, test, simulation, paper, restricted-live, and production environments SHALL bind exact artifact and Release Generation identities. Evidence from one environment, platform, Safety Cell, broker, route, credential, or failure domain cannot be extrapolated without explicit equivalence proof.

Deployment starts non-live. Staging, rollout, canary, readiness, health, low error rate, incident-free time, or successful trial does not admit software, activate configuration, issue Live Authorization, or promote production scope.

Mixed-version operation requires a closed compatibility proof covering protocols, schemas, migrations, state transitions, configuration, safety libraries, serializers, SDKs, signers, evidence, currentness, and final egress. Unknown compatibility denies the affected scope. Break-before-make and hard fencing apply where overlap can create conflicting authority or broker effect.

ADR-002-025 production-scope promotion remains separate. Its evidence binds the exact Release Generation, but promotion eligibility cannot admit a new artifact or reuse evidence across a changed release.

---

## 18. Runtime Artifact Attestation

The runtime-attestation path SHALL establish the actual loaded artifact-set digest, executable and image digests, runtime dependencies, plugins, sidecars, proxies, SDKs, signer components, configuration digest, deployment and workload identity, environment, Safety Cell, owner epoch, Release Generation, trustworthy-time receipt anchor, and invalidation state.

Attestation SHALL be independently verifiable and resistant to self-report substitution. Orchestrator desired state, deployment manifest, image tag, process command line, filesystem name, health endpoint, inventory cache, or a statement produced solely by the workload being evaluated is insufficient.

Runtime drift, unmeasured code, mutable volume injection, debugging modification, dynamic module load, sidecar replacement, host-library change, attestor loss, stale attestation, or digest mismatch creates a Release Restriction and denies dependent new risk.

---

## 19. Active Currentness and Final Egress

The ADR-002-024 Safety Currentness Vector for every risk-increasing send SHALL include:

1. exact Software Release Policy identity, generation, and digest;
2. exact Release Generation and Admitted Release Set digest;
3. exact applicable Release Artifact Manifest and lineage-graph digests;
4. current artifact-signing trust-bundle and key-status generation;
5. exact deployment, workload, environment, Safety Cell, and runtime-attestation identities;
6. current compatibility result for every consumer and broker-egress edge;
7. current restriction floors, incident scope, and stale-owner fences;
8. approved ages, trustworthy-time evidence, and invalidation state.

Those facts SHALL be established actively inside the per-send ordered currentness transaction. Cache, TTL, heartbeat, registry reachability, signer health, deployment readiness, canary status, last-known Release Generation, absence of revocation, or a valid historical signature is not currentness proof.

Final egress verifies exact facts and conformance; it does not choose source, build, dependency, artifact, or compatibility alternatives. Failure or ambiguity denies new risk. No valid release state can override a HALT, UNKNOWN, capacity denial, venue denial, approval denial, or any other restrictive fact.

---

## 20. Restriction, Revocation, and Incident Handoff

Restriction triggers include:

- unauthorized source or history change;
- source, build, provenance, dependency, toolchain, artifact, signature, registry, or attestation conflict;
- newly discovered malicious behavior, correction, vulnerability, revoked dependency, or incompatible consumer;
- builder, signer, registry, admission, deployment, attestor, identity, or administrator compromise;
- partial, mixed, stale, unknown, restored, or unmeasured deployment;
- inability to establish current Release Generation or restriction floor.

A credible authenticated restriction first reduces future authority through ADR-002-024. It does not wait for normal release admission, deployment, alert, evidence, or incident services. Scope expands to the greatest credible dependency closure when exact impact is unknown.

The same signal enters ADR-002-027 when policy-classified as an incident. Incident declaration, stabilization, remediation, administrative closure, postmortem, signer recovery, registry recovery, or quiet time does not readmit an artifact, clear a release restriction, restore production scope, or re-arm.

---

## 21. Partition, Backpressure, and Failure Behavior

| Failure | Mandatory result |
|---|---|
| source or review history unavailable or conflicting | quarantine candidate; deny admission and dependent new risk |
| builder, dependency source, toolchain, signer, or registry unavailable | no favorable fallback; existing effects persist; new admission denied |
| admission registry or Release Generation conflict | fence writers; deny affected scope until one current history is proven |
| supply-chain control plane partitioned while broker egress is reachable | final egress denies unless exact current release state is independently proven |
| artifact retrieval digest, platform, layer, or signature mismatch | quarantine bytes; create restriction and incident signal |
| runtime attestation missing, stale, mixed, or conflicting | deny dependent new risk; treat deployed scope as unknown |
| deployment queue or rollout backpressure | do not extend admission validity or drain by enabling send |
| revocation delivery delayed or lost | independent restrictive ingress and local latch preserve denial |
| signer or registry compromise suspected | restrict greatest credible shared scope; rotate/fence; preserve history |
| evidence or scanner unavailable | evidence gap; no admission or PASS; restrictive enforcement remains independent |
| unknown instance remains after rollout | potentially active until hard-fenced; normal live authority denied |
| recovery completes | no release or authority revival; fresh admission, recovery, and re-arm remain mandatory |

No retry, mirror, cache, alternate registry, previous artifact, emergency signer, manual copy, or operator assertion may select a more permissive state when provenance, ordering, currentness, or scope is unknown.

---

## 22. Rollback, Restore, and Emergency Hotfix

Rollback is a new release proposal, admission decision, Admitted Release Set, and Release Generation. Historical acceptance does not prove present compatibility, key status, dependency status, current Hard Safety Envelope compliance, or runtime suitability.

Backup, registry, source, key, admission, or deployment restore SHALL preserve all later restrictions, revocations, tombstones, generations, decisions, artifact digests, and incident links. Restore advances the applicable restore and release continuity generations. If the highest committed history cannot be proven, the affected scope remains non-live.

An emergency hotfix follows the same source, build, closure, signing, admission, deployment, attestation, currentness, and evidence rules. Break-glass may request restriction or accelerate independently approved workflow; it cannot bypass the Non-Waivable Boundary, create admission, hold a broker route, or re-arm.

No rollback, restore, or hotfix blindly cancels orders or required protection. Necessary protective actions remain separately classified, capacity-covered, and enforced under their existing owners.

---

## 23. UNKNOWN, Capacity, Broker Finality, and Economic Continuity

Software supply-chain components do not own broker, order, fill, position, exposure, capacity, or settlement truth. A release restriction may deny future action but cannot declare an order absent, a fill reversed, a position zero, or an obligation settled.

Unknown artifact or runtime state cannot become permission because capacity is available. Where software uncertainty may have affected a broker-directed attempt or authoritative state, the greatest credible economic effect remains UNKNOWN and capacity-consuming until resolved through the normal evidence, reconciliation, and RCL transition rules.

Missing ACK is not proof of non-acceptance. Cancel ACK is not Final Quantity Proof. Artifact deletion, admission expiry, signature revocation, workload termination, process death, deployment rollback, registry restore, or incident closure is never capacity-release proof.

RCL remains the sole capacity mutation and serialization authority. Priority, emergency release label, deployment urgency, or hotfix status is not reserved protective capacity.

---

## 24. Evidence, Recovery, and Non-Revival

Evidence SHALL preserve:

- source manifests, review identities, history continuity, generated source, and external-source closure;
- build recipes, builder identities and epochs, complete inputs, environments, logs, outputs, and provenance;
- dependency/toolchain manifests, resolution evidence, corrections, revocations, and common modes;
- artifact manifests, exact bytes, platform variants, signatures, trust bundles, registry custody, and retrieval proofs;
- admission requests, decisions, predecessor conflicts, Release Generations, restrictions, and Admitted Release Sets;
- deployment, mixed-version, compatibility, runtime-attestation, drift, stale-owner, hard-fence, and final-egress evidence;
- negative, failed, conflicting, missing, late, restored, compromised, and inconclusive results.

ADR-002-016 owns custody and replay. Evidence records the protocol; it does not admit software, deploy it, activate configuration, issue authority, transmit, or repair an unsafe historical action.

ADR-002-017 recovery obligations include exact source/build/dependency/artifact/admission/release/runtime state, all restrictions and incidents, unknown instances, key and registry continuity, compatibility, runtime drift, final-egress fencing, and evidence gaps. Recovery readiness remains non-authorizing. Fresh ADR-002-007/015 re-arm is mandatory, and no automatic re-arm is permitted.

---

## 25. Rejected Alternatives

### 25.1 “A signed artifact is trusted software”

Rejected because a signature proves an authenticated statement, not safe source, complete inputs, compatibility, current admission, or uncompromised key status.

### 25.2 “The repository commit is the complete source”

Rejected when generated source, submodules, external objects, build scripts, schemas, or code generators remain outside the manifest.

### 25.3 “A lock file closes the dependency graph”

Rejected unless every transitive build and runtime resolution path and the exact fetched bytes are included.

### 25.4 “Two builds prove independence”

Rejected when they share source compromise, compiler, package source, base image, administrator, signer, or verifier common mode.

### 25.5 “A passing scan or test admits the artifact”

Rejected because scanners and tests are evidence inputs, not admission or prevention authority.

### 25.6 “Registry tag or latest is stable enough”

Rejected because mutable resolution can substitute artifact, platform, layer, or manifest after review.

### 25.7 “Canary and deployment health create live eligibility”

Rejected because deployment, admission, configuration activation, production-scope promotion, and Live Authorization are separate transitions.

### 25.8 “Previously accepted rollback is automatically safer”

Rejected because old software may be revoked, vulnerable, incompatible, broader, based on obsolete dependencies, or missing later restrictions.

### 25.9 “Emergency hotfix may bypass normal admission”

Rejected because urgency cannot create provenance, compatibility, currentness, capacity, protection, or broker permission.

### 25.10 “Process termination fences the old artifact”

Rejected because stale credentials, signers, sessions, queues, proxies, routes, or workloads may remain broker-capable.

### 25.11 “Absence of revocation proves currentness”

Rejected because lost, delayed, suppressed, stale, or restored control-plane state can appear permissive.

### 25.12 “Recovery or incident closure restores the release”

Rejected because recovery and closure create no admission, scope restoration, authority, or re-arm.

---

## 26. Consequences

### 26.1 Positive

- The actual runtime software becomes attributable to reviewed source and a complete dependency/toolchain closure.
- Mutable tags, hidden build inputs, registry substitution, and stale releases cannot create permission.
- Build, signing, admission, deployment, configuration, arming, capacity, and transmission authorities remain separate.
- Mixed-version, rollback, restore, hotfix, and compromise behavior is fail-closed and generation-fenced.
- Final egress verifies exact current release state without letting release governance become authority.
- Evidence and recovery preserve broker finality, economic continuity, and non-revival.

### 26.2 Negative

- Hermetic builds, complete dependency inventories, independent reproduction, immutable registries, and runtime attestation add substantial cost.
- Unknown provenance, correction status, compatibility, key state, or runtime drift reduces availability.
- Release velocity is constrained by independent admission, break-before-make sequencing, and fresh re-arm.
- Some toolchains or proprietary dependencies may lack sufficient independent evidence and therefore require reduced or prohibited live scope.
- Registry, signing, build, and deployment infrastructure become explicit safety-critical failure domains.

These costs are accepted because deployment convenience cannot justify unreviewed or unverifiable code in a real-capital path.

---

## 27. Acceptance Cases

Written cases define obligations only. They are not completed evidence.

### SCI-AC-001 — Source Identity and Review Integrity

History rewrite, tag movement, generated-source drift, submodule substitution, external-object omission, repository restore, or same-effective-person review cannot yield an admitted release.

### SCI-AC-002 — Build Isolation, Provenance, and Reproducibility

Undeclared network input, builder compromise, cache substitution, environment drift, provenance replay, or unexplained independent-build divergence fails closed without selecting a favorable output.

### SCI-AC-003 — Dependency and Toolchain Closure

Every transitive dependency, build script, plugin, compiler, SDK, code generator, base image, package source, and runtime-loaded module is exact and current; omission or floating resolution denies admission.

### SCI-AC-004 — Signer, Key, and Attestation Compromise

Compromised, revoked, stale, rolled-back, wrong-environment, or wrong-scope signing state cannot admit or preserve an artifact, and the compromised path cannot attest its own recovery.

### SCI-AC-005 — Registry Custody and Artifact Substitution

Mutable tags, platform variants, manifest lists, layers, mirrors, partial uploads, stale replicas, restore, and retrieval races cannot substitute bytes between review, signing, scanning, admission, deployment, attestation, and runtime use.

### SCI-AC-006 — Independent Admission and Compatibility

Admission deterministically binds one exact artifact, policy, scope, lineage, and compatibility graph; scans, tests, CI success, self-approval, common-mode review, patching, union, or favorable subset cannot create eligibility.

### SCI-AC-007 — Release Generation and Stale Fencing

Concurrent, stale, restored, minority, or superseded release publishers and consumers cannot create or use a current Admitted Release Set, and a newer restriction dominates every predecessor.

### SCI-AC-008 — Deployment Attestation and Environment Confinement

The actual executable, library, plugin, sidecar, proxy, SDK, signer component, workload, configuration, environment, and Safety Cell match the exact release; non-live and unmeasured artifacts cannot reach live egress.

### SCI-AC-009 — Mixed Version, Promotion, Rollback, and Restore

Partial rollout, unknown compatibility, software promotion, demotion, rollback, disaster restore, and emergency hotfix remain non-live until a new complete release generation, recovery, configuration, and authorization chain is established.

### SCI-AC-010 — Active Currentness, Revocation, Partition, and Send Race

Cached admission, stale runtime attestation, control-plane partition with broker reachability, or restriction-versus-first-byte ambiguity cannot authorize new risk; a possibly sent attempt remains potentially live, capacity-covered, and not blindly retried.

### SCI-AC-011 — Authority Separation, Broker Finality, and Economic Continuity

Supply-chain identities cannot mutate RCL, classify protection, issue authority, hold an alternate broker route, reinterpret missing ACK or Cancel ACK, erase UNKNOWN, expire economic effect, or release capacity.

### SCI-AC-012 — Evidence, Recovery, Hotfix, and Non-Revival

Signatures, SBOMs, scans, tests, CI, evidence, replay, incident closure, source/build/signer/registry recovery, deployment health, or hotfix urgency cannot claim verification completion, revive release eligibility or authority, restore scope, or automatically re-arm.

---

## 28. Requirements Traceability

| Requirement | Discharge |
|---|---|
| RFC-001 SC-001, §§13.4–13.6, Appendix B | exact software provenance and continuous currentness become production prerequisites without claiming completed evidence (§§8–24) |
| SAFE-003, SAFE-004 | software compatibility and release policy fail closed inside the Hard Safety Envelope (§§8, 15–19) |
| SAFE-010, SAFE-011, SAFE-013, SAFE-014 | release state is a non-authorizing negative gate; RCL and final egress retain exclusive enforcement (§§7, 19, 23) |
| SAFE-030, SAFE-031 | source, processing version, build lineage, dependency identity, semantics, scope, and time provenance are exact (§§9–14) |
| SAFE-033, SAFE-034 | compiler/serializer/SDK artifacts and their independent verification/common modes are bound without self-approval (§§11–12, 15) |
| SAFE-035 | provenance, admission, key status, runtime attestation, and currentness ages use trustworthy time (§§12–13, 18–19) |
| SAFE-041, SAFE-044 | release restriction and closed recovery remain independently available before safe start or resume (§§20–24) |
| SAFE-045, SAFE-046, SAFE-047 | live/non-live artifacts are segregated and Live Authorization binds the exact software and scope (§§17–19) |
| SAFE-048 | supply-chain partition, stale admission, and lost currentness deny new risk even while broker egress is reachable (§§19–21) |
| SAFE-050 | release policy, manifests, admission, compatibility, generations, rollback, and restore are governed and fail closed (§§8–22) |
| SAFE-051, SAFE-052 | source-to-runtime and restriction evidence is complete and replayable without substituting for prevention (§24) |

---

## 29. Open Implementation Questions

1. Which Software Release Policy, Source Revision Manifest, closure, provenance, artifact, admission, release-set, and runtime-attestation schemas are approved?
2. Which source-control, review, history-protection, generated-source, submodule, mirror, and effective-principal mechanisms are conforming?
3. Which isolated builder, Build Recipe, network policy, cache policy, deterministic environment, and independent-reproduction mechanisms are approved?
4. Which dependency, package-source, compiler, SDK, code-generation, base-image, runtime-loading, correction, and SBOM mechanisms prove complete closure?
5. Which artifact signer, key custody, threshold, rotation, revocation, transparency, and trust-bundle mechanisms are conforming?
6. Which immutable registry, digest retrieval, platform/layer closure, replication, garbage collection, restore, and tombstone mechanisms preserve custody?
7. Which independent admission workflow, compatibility verifier, Release Registry, predecessor serialization, and stale-writer fence implement Release Generation?
8. Which deployment promotion, mixed-version, migration, break-before-make, workload identity, runtime measurement, and attestation mechanisms are conforming?
9. Which ADR-002-024 owner publication, restriction floor, local latch, per-send proof, and ADR-002-013 final-egress checks establish active release currentness without permissive cache?
10. Which compromise and correction sources trigger restriction and ADR-002-027 incident classification over the correct dependency closure?
11. Which rollback, disaster-restore, emergency-hotfix, Recovery Obligation, and hard-fence protocols prevent historical admission or authority revival?
12. Which `B_supply_chain_compromise_detect`, `B_release_restriction_to_authority_restrict`, `B_release_restriction_to_egress_deny`, `B_release_generation_fence`, `B_runtime_artifact_drift_detect`, `MAX_build_provenance_age_ms`, `MAX_artifact_admission_decision_age_ms`, `MAX_admitted_release_set_age_ms`, `MAX_runtime_artifact_attestation_age_ms`, and `MAX_release_key_status_age_ms` values are approved and measured?

Unresolved questions reduce or prohibit live scope. They never permit mutable identity, incomplete lineage, stale admission, historical signature, permissive rollback, or automatic re-arm.

---

## 30. Approval and Operational Gates

ADR-002-029 remains `Proposed` until all of the following are satisfied:

1. all eight canonical policy, source, dependency/toolchain, provenance, artifact, admission, release-set, and runtime-attestation schemas are approved;
2. source identity, effective review independence, history integrity, generated-source closure, and external-source closure are implemented and security-reviewed;
3. isolated build, complete dependency/toolchain closure, provenance, reproducibility/differential, and common-mode controls are implemented and independently reviewed;
4. artifact signing, key custody, revocation, immutable registry custody, retrieval, platform/layer closure, restore, and compromise response are implemented and security-reviewed;
5. deterministic independent admission, compatibility, Release Generation, complete Admitted Release Set, and stale-writer fencing are implemented without mutable names or permissive union;
6. deployment promotion, mixed-version denial, break-before-make, actual runtime attestation, non-live default, and environment confinement are implemented;
7. ADR-002-024 release restriction and active-currentness protocol and ADR-002-013 final-egress verification are implemented without cache, circular trust, alternate route, or stale-artifact bypass;
8. rollback, restore, hotfix, partition, signer/registry compromise, stale runtime, mixed release, send race, recovery, and non-revival behavior passes fault injection and security review;
9. supply-chain, build, signing, registry, admission, deployment, attestation, evidence, and replay identities cannot mutate capacity, create protection or authority, hold an external broker route, clear safety state, or re-arm;
10. numeric bounds and age limits are approved in the Verification Profile and measured under fault injection;
11. SCI-EV-001 through SCI-EV-012 and applicable upstream evidence are executed at their required levels, retained, and independently reviewed;
12. all evidence retains negative, missing, conflicting, compromised, rollback, restore, and stale-generation outcomes without treating documentation, signatures, scans, tests, or replay as prevention;
13. no Critical or Major source, build, dependency, signer, registry, admission, compatibility, runtime-attestation, currentness, economic-continuity, or authority-separation finding remains open;
14. Architecture Gate acceptance remains explicit; document review alone does not promote status.

Authorship, EV-L0 review, source merge, signed provenance, reproducible build, SBOM, scan, test, CI success, registry upload, artifact admission, deployment, canary, health status, trial evidence, configuration activation, incident closure, recovery readiness, or registered evidence item does not satisfy these gates. This ADR authorizes architecture and implementation planning only. It does not authorize acceptance, restricted-live or production operation, software deployment, production-scope promotion, broker transmission, capacity release, incident closure, or automatic re-arm.
