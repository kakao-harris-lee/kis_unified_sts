# IMPLEMENTATION-PLAN-002 — Safety Architecture Implementation & Verification Plan

- **Status:** PROPOSED PLAN — not approved; no implementation code has been written.
- **Date:** 2026-07-13
- **Covers:** ARCHITECTURE-GATE-STATUS §7 implementation, fault injection, evidence execution, and independent review for all currently registered ADR-002-001..016 evidence cases.
- **Governed by:** RFC-000, RFC-001, RFC-002 v0.2, ADR-002-001..016, VER-002-001. Current VER and Evidence Register coverage includes 195 items and one-to-one dedicated acceptance cases for ADR-002-005..016; registration is not executed evidence.
- **Authorization:** This plan authorizes nothing. Production, live, and ADR-Accepted status remain NO.

---

## 0. Why this is a plan and not code

The remaining gate steps cannot be executed unilaterally without defeating the
safety model they implement:

- numeric bounds require **human approval** (VER-002-001 §6; separation of duties);
- owners and the **independent reviewer** must be assigned — the reviewer SHALL NOT
  be the author/integrator of this architecture (RFC-001 §11.4);
- implementation must follow **plan-first** approval, including ratification of the
  proposed greenfield TOS boundary and mechanism substrate (project workflow);
- EV-L1..L3 evidence cannot be "declared" — it must be produced by real tests,
  fault injection, and captured artifacts (VER-002-001 §5, ARCHITECTURE-GATE-STATUS §6);
- EV-L4 needs a broker sandbox or certified test environment; EV-L5/L6 need production authority that does not exist.

This document exists so those gates are explicit and ratifiable, not bypassed.

---

## 1. Phase 0 — Blocking human inputs (required before Phase 1 code)

| Input | Owner | Why it blocks |
|---|---|---|
| Approve/replace bounds in `VERIFICATION-PROFILE-002.yaml` | Safety/Risk authority | Tests need pass/fail thresholds, including Human HALT ingress-to-commit; unapproved bounds are not bounds |
| Measure broker-specific bounds from an approved Broker Capability Profile | Broker/Exec eng | Final Quantity Proof, late fill, rate/session, query, replacement gap/overlap, and non-trade detection/reconciliation |
| Assign implementation owner + evidence owner + **independent reviewer** per evidence item | System owner | `EVIDENCE-REGISTER-002.csv` (195 items); independence is mandatory |
| Ratify this plan, the §2 greenfield boundary, and the mechanism substrate | Architecture board | Determines what is implemented and where |

I will not fabricate any of these. I can *draft candidates* (done for bounds; role scheme in §3) for you to ratify.

---

## 2. Proposed greenfield TOS boundary

RFC-002's Risk Capacity Ledger, Safety Authority, Trustworthy Time Service, Live
Authorization Service, Egress Gateway, Reconciliation Service, Recovery Coordinator,
Protective Action Controller, and Safety Profile Validator form a new safety core with
explicit authority and failure-domain boundaries. This architecture is not constrained
by an existing trading implementation.

The greenfield boundary requires:

1. strategy and orchestration submit non-transmitting intents and cannot mutate
   capacity, issue authority, or reach the broker directly;
2. the Risk Capacity Ledger is the sole capacity mutation and serialization authority;
3. the Safety Authority issues scoped capabilities through the Currentness Sequencer
   without holding broker credentials;
4. one ADR-002-013 logical Broker Egress Authority per Safety Cell and scope confines
   every usable live-order credential, route, active principal, session, signer, and downstream
   intermediary inside the effective Final Egress Trust Boundary;
5. recovery, reconciliation, operator, evidence, and market-data components cannot
   bypass the Egress Gateway or convert missing/unknown state into permission;
6. ADR-002-012's quorum-replicated deterministic Safety Commit Log and ADR-002-013's
   quorum-sufficient proof, credential/route confinement, exact-principal binding, and deny-first
   hard-fence semantics are required; conforming products, cryptography, voter/principal/failure-domain
   allocation, broker fence, and physical topology remain architecture-board decisions and verification targets.
7. ADR-002-014's immutable Hard Safety Envelope and Runtime Safety Profile artifacts,
   canonical semantic validation, separated approval, Consumer Compatibility Manifest, committed
   Profile Generation, break-before-make activation, Restrictive Override, and rollback non-revival
   semantics are required; conforming formats, registries, signing, approval, and validation products remain open.
8. ADR-002-015's Effective Principal Graph, Human Authority Policy, exact Approval Request,
   Approval Attestation, single-use Approval Set, one-human restrictive HALT, break-glass confinement,
   delegation, compromise, and non-revival semantics are required; human approval cannot activate
   configuration, mutate capacity, classify protection, issue Live Authorization, or reach the broker.
9. ADR-002-016's Safety Evidence Envelope, Evidence Integrity Policy, exact pre-effect durability,
   commit receipt, source continuity, integrity anchor, gap containment, protected retention/redaction,
   and isolated Replay Capsule semantics are required; evidence and replay cannot create permission,
   mutate live state, release capacity, clear UNKNOWN, or automatically re-arm.

---

## 3. Proposed roles & separation of duties (draft — assign real people)

Role placeholders for `EVIDENCE-REGISTER-002`; a single person may hold several,
subject to the exclusions:

- **RC-Impl / RCLP-Impl / EgressSec-Impl / SPG-Impl / HAG-Impl / ERI-Impl / SA-Impl / TT-Impl / LA-Impl / BC-Impl** — implement Risk Capacity, quorum persistence/fencing, final-egress security, safety-profile governance, human-authority governance, evidence/replay integrity, Safety Authority, Trustworthy Time, Live Authorization, and Broker layers.
- **State-Impl / Recon-Impl / FD-Impl / PR-Impl / NT-Impl** — implement orthogonal state, evidence confidence, failure-domain fencing, protective replacement, and non-trade transition layers.
- **Harness-Eng** — deterministic fault injection + evidence capture.
- **Evidence-Owner** — runs a case, produces the manifest + artifacts.
- **Independent-Safety-Reviewer** — signs evidence; MUST NOT be any Impl role or the architecture author.
- **Bounds-Approver** — ratifies `VERIFICATION-PROFILE-002`; MUST NOT arm live trading.
- **Live-Armer** — separate identity; MUST NOT enlarge limits (ADR-002-002 §29.3).

Exclusions (hard): Impl ≠ Independent-Reviewer; Bounds-Approver ≠ Live-Armer; author/integrator of RFC-002/ADRs ≠ Independent-Reviewer.

---

## 4. Phased implementation → evidence

Each phase gates the next. No phase claims completion without the VER-002-001 evidence.

### Phase 1 — Model & property verification (EV-L1)
- Implement the **capacity state machine** (ADR-002-002 §10: COMMITTED_UNBOUND … RELEASED)
  and **authority epoch/lease**, **Time Health/continuity**, and **Live Authorization/revocation**
  models (ADR-002-003/007/008) as pure, non-transmitting models.
- Implement the ADR-002-012 deterministic command, committed-prefix, Writer Epoch,
  membership-change, snapshot/restore, and idempotency models without selecting a live product.
- Implement ADR-002-013 Egress Generation, Active Egress Principal, credential/session,
  route/endpoint, Quorum Commit Certificate, downstream intermediary, hard-fence, and recovery models.
- Implement ADR-002-014 envelope/profile artifact, canonical semantic digest, authority-separation,
  compatibility, Profile Generation, activation, restriction, expiry, rollback, and restore models.
- Implement ADR-002-015 effective-principal collapse, exact approval context, quorum and conflict,
  Approval Set consumption, delegation, Human HALT, break-glass, compromise, and recovery models.
- Implement ADR-002-016 record/receipt identity, causal graph, durability class, continuity, gap,
  integrity-anchor, retention, redaction, Replay Capsule, divergence, and non-revival models.
- Implement pure models for the five orthogonal state dimensions and CPL invariants, per-field
  evidence confidence, Failure-Domain Allocation Matrix, protection gap/overlap, and conservative
  non-trade transition envelope (ADR-002-005/006/009/011/010).
- Property/model tests for INV-001..012 and AC-001..018 (concurrency, crash points,
  cancel-crossing-fill, replace overlap, TTL, UNKNOWN, protective lease partition), plus
  time continuity, snapshot age, non-revivable authorization, partial scope, restrictive-generation
  precedence, state ownership, evidence conflict, replacement interleavings, and non-trade idempotency.
- Deliverable: EV-L1 evidence for every RC/SA/TIME/REARM/STATE/RECON/FD/PR/NT/RCLP/EGRESS/SPG/HAG/ERI item marked EV-L1-reachable.

### Phase 2 — Component fault tests (EV-L2)
- Durable quorum-replicated **single-logical-writer Risk Capacity Ledger** with the
  ADR-002-012 deterministic Safety Commit Log, committed-prefix checks, Writer Epoch,
  joint membership change, snapshot/restore generation, and hard fencing;
  **Safety Authority epoch registry**; durable evidence identities +
  write-ahead `SEND_STARTED`; Time Health generation and consumer receipt-anchor model;
  Live Authorization revocation/HALT generation model.
- Implement the ADR-002-007 §§9.1–9.5 protocol components: linearizably ordered
  single-use capability issuance, authenticated currentness session, consumer-local
  monotonic deny latch, quorum-committed claim, and ADR-002-013 quorum-sufficient proof
  validation, exact request construction, credential custody, route policy, and hard fencing.
  The selected products and topology remain subject to Phase 0 approval.
- Implement ADR-002-014 canonical artifact parsing and semantic comparison, immutable registry,
  separated approval checks, Consumer Compatibility Manifest validation, staged distribution,
  committed Activation Record, and fail-closed restrictive/rollback behavior without live arming.
- Implement ADR-002-015 policy and graph validation, phishing-resistant principal/session checks,
  exact attestation and quorum verification, transactionally ordered single-use Approval Set consumption,
  independent restrictive Human HALT ingress/local latch, and non-permissive break-glass controls.
- Implement ADR-002-016 canonical envelopes and receipts, source-authenticated append-only storage,
  source/causal completeness indexes, independent emergency journal, integrity anchoring, Evidence Gap
  containment, protected raw/redacted views, retention controls, and isolated replay without live authority.
- Durable orthogonal-state ownership, reconciliation-confidence bounds, deployment and credential
  identities, replacement workflow lineage, and non-trade event/version lineage.
- Component-level fault injection (missing input, stale epoch, crash-at-boundary).
- Deliverable: EV-L2 evidence (e.g., RC-EV-009, RC-EV-018, SA-EV-005/015).

### Phase 3 — Integrated system fault tests (EV-L3)
- Wire the **final broker-egress gate** (Transmission Capability validation) in front
  of a *simulated* broker; real persistence + network boundaries; duplicate-instance /
  split-brain / partition / restart harness.
- Fence the validation decision and irreversible simulated send boundary against current
  authority, revocation, HALT, and Time Health generations. Enforce
  `B_capability_claim_to_send` between durable claim/`SEND_STARTED` and the first
  simulated broker byte.
- Inject quorum loss, minority-with-broker-reachability, stale/removed writer resume,
  membership transition, snapshot/compaction, conflicting restore, and protective
  sub-ledger rejoin failures.
- Inject credential/session compromise, stale egress resume, trust-bundle rollback,
  proof and request substitution, route/endpoint crossover, proxy/queue replay,
  credential-rotation overlap, and hard-fence delay.
- Inject unit/schema/canonicalization mutation, omitted and unknown profile fields, partial and
  mixed-generation distribution, stale-base activation, incompatible consumer, approval compromise,
  Restrictive Override races, expiry recovery, and configuration rollback/restore.
- Inject common-control identity aliases, self-approval chains, stale graphs, quorum and roster drift,
  delegation/recovery, workflow and identity outages, attestation replay, duplicate consumption,
  approver compromise, break-glass expansion, and Human HALT propagation/races.
- Inject evidence receipt delay/substitution, store/ingress outage, source-sequence reset, missing causal
  parents, record mutation/deletion/fork, key/anchor rollback, conflicting restore, unsafe redaction/export,
  premature compaction/deletion, replay divergence, and replay-to-live boundary exposure.
- Prove that strategy, orchestration, recovery, reconciliation, retry, administrative,
  evidence, and market-data identities lack a direct simulated live-order route.
- Execute the EV-L3 RC-EV / SA-EV / TIME-EV / REARM-EV / STATE-EV / RECON-EV / FD-EV /
  PR-EV / NT-EV / RCLP-EV / EGRESS-EV / SPG-EV / HAG-EV / ERI-EV set; measure `B_*` bounds against
  `VERIFICATION-PROFILE-002`.
- Deliverable: EV-L3 evidence; measured detection/containment bounds.

### Phase 4 — Broker Capability Profile & sandbox (EV-L4)
- Complete the first **Broker Capability Profile** (`BROKER-CAPABILITY-PROFILE-template.yaml`):
  order identity/idempotency, cancel and atomic-replace semantics, query completeness, rate/session,
  late-fill, corporate-action/open-order adjustment, derivative lifecycle, settlement behavior,
  credential/session scope, order-route topology, Commit-Proof integration, hard fencing, and manual authority.
- Complete the first Hard Safety Envelope, Runtime Safety Profile, Consumer Compatibility Manifest,
  Safety Configuration Activation Record, Human Authority Policy, Effective Principal Graph,
  Approval Request, Approval Attestation, Approval Set, Human HALT, Evidence Integrity Policy,
  Safety Evidence Envelope, Evidence Commit Receipt, Evidence Gap Record, and Replay Capsule contracts from the non-authorizing templates; validate the exact
  Broker Capability Profile and Verification Profile digests in the closed bundle.
- Broker sandbox or certified-environment probes; derive broker-specific bounds; run BC-EV items.
- Deliverable: EV-L4 evidence + a versioned Capability Profile.

### Phase 5 — Independent review & ADR re-evaluation
- **Independent** reviewer (not me, not an Impl role) signs each evidence run.
- Only then may ADR-002-001..016 be re-evaluated toward `Accepted`, and only within the
  proven scope. Every registered case must be executed at its required evidence level; registration
  alone satisfies no acceptance criterion. Restricted live (EV-L5) is a
  separate, later, human-authorized gate.

---

## 5. What I will do vs. will not do

**Will do (on your go):** write Phase 1–3 code and harness for the ratified greenfield
boundary; keep everything non-transmitting/simulated; produce EV-L1..L3 evidence
artifacts; keep status Proposed.

**Will not do (safety model forbids):** approve bounds; assign real owners or sign as the
independent reviewer; execute against a live broker account; declare any ADR Accepted; write
implementation code before this plan, greenfield boundary, and mechanism substrate are approved.

---

## 6. Immediate decision requested

1. Approve (or amend) `VERIFICATION-PROFILE-002.yaml` proposed bounds, including the currently null egress-currentness, hard-fence, Human HALT, failure-domain, replacement, and non-trade bounds, and provide broker-measured values where required.
2. Ratify (or amend) the §2 greenfield boundary, ADR-002-007 §§9.1–9.5 protocol,
   ADR-002-012 mechanism, ADR-002-013 final-egress security boundary, ADR-002-014
   safety-configuration governance, ADR-002-015 human-authority governance, and ADR-002-016
   evidence-integrity/replay architecture; select conforming
   consensus, signer/credential, identity-aware route, Quorum Commit Certificate,
   voter/principal/failure-domain topology, hard fence, session, artifact, semantic-normalization,
   registry, signing, approval, compatibility-manifest, identity, authenticator, Effective Principal Graph,
   quorum, single-use approval-consumption, Human HALT, emergency restrictive-latch, evidence-store,
   durable-ingress, emergency-journal, source-sequence, integrity-anchor, gap-detection, protected-retention,
   redaction/export, and isolated-replay mechanisms.
3. Approve this plan so Phase 1 (EV-L1 models + property tests, non-transmitting) can begin.
4. Name the independent reviewer (or confirm it is external to this work).
