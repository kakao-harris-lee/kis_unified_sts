# DR-0001 — Single-Operator Live Governance

- **Decision ID:** DR-0001
- **Date:** 2026-07-17
- **Status:** Accepted
- **Decision Owner:** System Owner (final risk-acceptance authority, vision §12.1)
- **Category:** Governance Decision
- **Originating Finding:** CORPUS-REVIEW-0001 CR-02 — mandatory
  natural-person dual control versus the single-operator reality
- **Normative Carriers:** RFC-001 SAFE-053; ADR-002-015 §17.1 (Governed
  Single-Operator Re-Arm Variant); ADR-002-025, ADR-002-026, ADR-002-027
  recognition clauses

---

## 1. Context

CORPUS-REVIEW-0001 (finding CR-02, converged on by four independent review
lenses) established that ADR-002-015 originates a constitutional-grade
obligation — "at least two distinct authenticated natural persons" for every
risk-increasing re-arm [ADR-002-015 §1, §17, HAG-AC-010] — and propagates it
as a live-gate precondition through ADR-002-025 (RLP-INV-014), ADR-002-026
(WDR-INV-007), and ADR-002-027 (SIR-INV-016).

Three problems compound:

1. **No normative parent.** RFC-000 CONST-005 requires only *logical*
   independence between decision and approval ("Decision components SHALL NOT
   approve their own trading actions"). RFC-001 contains no
   natural-person-separation requirement. An ADR was therefore originating a
   Safety-Case-grade obligation with no higher-level parent — a hierarchy
   inversion under philosophy §35 ("a lower-level document should not
   reinterpret higher-level intent").
2. **Direct tension with the baseline.** vision's §12 closing note (following
   §12.7) states that "a single person may perform multiple roles in a small
   project, but the logical responsibilities remain distinct." No sentence in the corpus reconciled the
   mandatory two-natural-person rule with that baseline.
3. **Unstated consequence.** As written, a genuine single-operator deployment
   could never reach live, re-arm after any material failure, approve a
   deviation, promote scope, or close an incident. This is fail-closed and
   creates no capital-loss path, but it silently nullifies the project's
   stated purpose, and that decision was surfaced nowhere.

CR-02 required the System Owner to choose one resolution explicitly and
prohibited resolution by silence.

## 2. Decision

The System Owner adopts **option (c): a governed single-operator re-arm
variant**.

Risk-increasing live re-arm, live authorization issuance, and production-scope
promotion SHALL require the independent approval of at least two distinct
effective principals. That requirement MAY be satisfied by either a quorum of
two distinct authenticated natural persons **or** an approved **Governed
Single-Operator Re-Arm Variant** defined by ADR-002-015. The two-natural-person
construction remains the default and the broadest-scope path; the variant is an
approved, scope-limited alternative satisfaction path, not a relaxation of the
obligation.

The requirement is given a normative parent at the Safety-Case level
(RFC-001 SAFE-053) so that the ADR-002-015 obligation is no longer originating.
The ADR-002-026 Non-Waivable Boundary remains intact and is not eroded by this
decision.

## 3. Options Considered

### 3.1 Option (a) — Promote natural-person dual control into the constitution and carve out vision §12.7

Promote mandatory two-natural-person dual control into RFC-000/RFC-001 and add
an explicit carve-out to vision §12.7 accepting "live requires at least two
persons."

**Rejected.** It hard-codes a staffing precondition the project cannot meet in
its stated single-operator setting, and it requires amending a non-normative
baseline document (vision) to accept a permanent operational impossibility. It
resolves the hierarchy inversion but forecloses the project's purpose.

### 3.2 Option (b) — Confine single-operator deployments to non-live scope

Normatively state that genuine single-person deployments are confined to
non-live scope, and record that as an accepted consequence.

**Rejected.** Fail-closed and honest, but it permanently prevents the intended
system from operating live under its actual staffing. It converts a governance
gap into a declared non-goal that contradicts the project's purpose.

### 3.3 Option (c) — Governed single-operator re-arm variant (ADOPTED)

Define a governed single-operator re-arm variant: a pre-approved,
time-separated, re-authenticated single-operator path combined with an
independent non-authorizing automated attestation and, where available, an
external independent reviewer recognized as a second effective principal, while
keeping the ADR-002-026 Non-Waivable Boundary intact.

**Adopted.** It reconciles the single-operator reality with the project's
purpose without introducing any fail-open path. It preserves the fail-closed
posture (an unavailable or indeterminate attestation denies re-arm), keeps
break-glass restrictive-only, keeps the Hard Safety Envelope fixed, and
constrains the scope a single operator may arm to a reduced scope delta (an ADR-002-025 §5.11 Progressive Promotion step) relative to a
two-natural-person quorum.

## 4. Rationale

1. **Single-operator reality and project purpose.** The system is intended to
   operate under single-operator staffing (vision §12 closing note, following
   §12.7). Options (a) and (b)
   each foreclose that purpose; option (c) preserves it.
2. **Fail-closed is preserved.** The variant adds a *path to satisfy* the
   two-independent-effective-principal requirement; it removes no gate. Every
   ambiguity continues to resolve restrictively: an unavailable or
   indeterminate attestation, an unresolved reconciled-state check, or an
   unverifiable independence relation denies re-arm.
3. **Hierarchy inversion resolved at the Safety-Case level.** By creating
   RFC-001 SAFE-053 as the normative parent, the ADR-002-015 natural-person
   requirement gains a higher-level parent (Safety Case sits above ADR in
   philosophy §35). The ADR now refines a Safety-Case requirement rather than
   originating one.
4. **Bounded human authority.** The decision is consistent with philosophy §22
   (human authority is necessary but bounded) and vision §6.9: human authority
   remains authenticated, scoped, attributable, reviewable, and incapable of
   extending exposure beyond the Hard Safety Envelope.
5. **Non-waivable boundary intact.** The variant cannot waive any requirement
   inside the ADR-002-026 Non-Waivable Boundary, cannot widen break-glass
   authority, and cannot expand the Hard Safety Envelope.

## 5. Consequences

1. **vision.md is not modified.** vision's §12 closing note (following §12.7)
   already states that a single person may hold multiple roles while the logical
   responsibilities remain distinct. Option (c) realizes exactly that principle: the logical
   responsibilities of proposer, approver, attestor, and armer remain distinct
   and are satisfied through time-separation, an independent non-authorizing
   attestation, and (where available) an external reviewer — rather than
   collapsed into one unattested act. The CR-02 conflict with vision §12.7 is
   therefore resolved by adopting option (c), so vision.md requires no
   amendment. philosophy.md is likewise not modified (both are non-normative
   baseline documents).
2. **RFC-001 SAFE-053 is created** as the Safety-Case-level parent requiring
   two independent effective principals with two satisfaction paths.
3. **ADR-002-015 §17.1 defines the variant** and adds invariants
   HAG-INV-015 through HAG-INV-019.
4. **ADR-002-025/026/027 gain recognition clauses** (RLP-INV-014,
   WDR-INV-007, SIR-INV-016 and related sections) admitting the variant as an
   additional satisfaction path for the second effective principal, without
   relaxing the underlying independence obligation.
5. **Reduced armable scope.** The scope a single operator may arm through the
   variant may be narrower than a two-natural-person quorum and is bound to the
   ADR-002-025 §5.11 Progressive Promotion steps (explicitly approved scope deltas).
6. **Evidence debt is recorded, not discharged here.** SAFE-053 and
   HAG-INV-015..019 require verification-evidence coverage that is deliberately
   *not* added to EVIDENCE-REGISTER-002 in this wave; it is recorded as an
   explicit evidence-debt item in ARCHITECTURE-GATE-STATUS to avoid register
   count drift, and is scheduled for the Part-2/3 register consolidation
   (a later wave).

## 6. Normative Status and Future Constitutional Work

This decision record is a governance artifact. Its normative force is carried
entirely by the documents named under **Normative Carriers**; DR-0001 itself
grants no authority and creates no live readiness.

The dedicated constitutional principle bounding human authority that this
section originally recorded as owed to a later wave has since been delivered:
**RFC-000 CONST-015 (Bounded Human Authority)**, authored in CORPUS-REVIEW-0001
Wave 2 (RFC-000 v0.12). SAFE-053 is its Safety-Case discharge and now lists
CONST-015 in its `Derived from` set (RFC-001 §10, §12); as anticipated,
SAFE-053's requirement text required no change to accept that parent.

## 7. Related Documents

- CORPUS-REVIEW-0001 — CR-02 (originating finding); M-03 (bounded-human-
  authority constitutional principle — discharged by RFC-000 CONST-015, Wave 2)
- vision §5, §6.9, §12.1, §12.7 (baseline, unmodified)
- philosophy §22, §34, §35 (baseline, unmodified)
- RFC-000 CONST-005, CONST-011, CONST-013 (existing constitutional anchors)
- RFC-001 SAFE-053 (new normative parent); RFC-001-Patch-0008
- ADR-002-015 §17.1 and HAG-INV-015..019; PATCH-ADR-002-015-v0.2
- ADR-002-025 / ADR-002-026 / ADR-002-027 recognition patches
- ADR-002-007 §12–§13 (re-arm workflow); ADR-002-017 (Recovery Barrier,
  Recovery Readiness Decision); ADR-DEV-012 (Reconciled-State Checklist)
- ARCHITECTURE-GATE-STATUS §3.4 (merge map), §4.2 (evidence debt)
