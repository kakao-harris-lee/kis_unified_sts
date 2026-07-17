# COMPLEXITY-REGISTER-002 — Complexity Justification Register

- **Status:** Non-Normative Governance Artifact
- **Date:** 2026-07-17
- **Discharges:** RFC-000 §8 AX-005 ("Complexity requires justification"; "Simplicity is the default architectural choice")
- **Method:** philosophy §24 (Simplicity Is a Safety Property) — the six justification questions applied per mechanism
- **Production Authorization:** NO

---

## 1. Purpose and Standing

This register discharges the RFC-000 constitutional axiom **AX-005** — complexity requires
justification, and simplicity is the default — by recording, for each load-bearing complex
mechanism in the Part-1 architecture, an explicit answer to the six justification questions of
philosophy §24.

**This document is non-normative.** It creates no requirement, no verification evidence, no
acceptance, no admission, and no live readiness. It defines no invariant and no evidence ID,
and it **adds nothing to either evidence count** (Part-1 remains 372; the development track
remains 98). Where it appears to conflict with any normative document, the normative document
governs (RFC-000 §12).

**Invention is forbidden.** Every cell cites an existing hazard (HAZ), safety requirement
(SAFE), ADR, or evidence family (EV). A question the corpus does not yet answer is recorded
honestly as **OPEN**, not filled in. The `Q4` answers are uniformly "test defined, not
demonstrated": all cited EV families are `NOT_IMPLEMENTED`, so a defined test is not a passed
one (philosophy §33).

## 2. The Six Questions (adapted from philosophy §24, which offers them as "useful questions")

- **Q1** — Which hazard does this complexity control?
- **Q2** — Which failure does it contain?
- **Q3** — Which requirement cannot be met more simply? (which simpler alternative was rejected, and why)
- **Q4** — Can its behaviour be tested?
- **Q5** — Can an operator understand its degraded state?
- **Q6** — Can it be safely removed later?

## 3. Mechanism Register

| # | Mechanism (owner) | Q1 hazard / Q2 failure | Q3 simpler alternative rejected | Q4 testable? | Q5 operator understands degraded state? | Q6 safely removable? |
|---|---|---|---|---|---|---|
| 1 | Per-send fenced single-use currentness — Safety Currentness Vector (ADR-002-024; ADR-002-007 §9.1–§9.5) | Stale- or revoked-authority transmission race (SAFE-011, SAFE-015, SAFE-048) | Cache / TTL / heartbeat currentness rejected — a cached "recently valid" state is not per-send currentness (ADR-002-007 §9.3; gate-status §2) | Defined: CUR-EV-001..012 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |
| 2 | RCL quorum consensus — 2f+1 deterministic Safety Commit Log (ADR-002-012 §1, §16) | Split-brain double-use of risk headroom / stale-writer capacity creation (SAFE-010, SAFE-013) | Single-leader / local-DB / lock rejected — none survives partition without creating capacity (ADR-002-012 §1) | Defined: RCLP-EV-001..012 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |
| 3 | PTOL / post-trade finality (ADR-002-030) | Manufactured finality / headroom from unsettled obligations (SAFE-022, SAFE-023, SAFE-024, SAFE-025) | Fills / statements-as-finality rejected — an acknowledgement is not settlement (ADR-002-030 §18) | Defined: PTF-EV-001..012 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |
| 4 | Supply-chain attestation & artifact admission (ADR-002-029) | Unreviewed / compromised runtime artifact reaching live (SAFE-045) | Signatures / CI / registry-tags-as-sufficient rejected — a tag is not content-addressed admission (ADR-002-029) | Defined: SCI-EV-001..012 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |
| 5 | Single credential-confined Egress Gateway (ADR-002-013; ADR-002-009 §10.1; RFC-002 §10.8) | Broker-bypass path / uncontained egress defect (SAFE-010, SAFE-011, SAFE-033; HAZ-025) | Multiple / direct broker send paths rejected — every live order routes through one enforcement point (ADR-002-007 §16) | Defined: EGRESS-EV-001..013 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** — and the single point is itself a single-failure concern: out-of-band containment (SAFE-054) *existence* is the open **M-06** item (gate-status §4.5) |
| 6 | Dual-control + Governed Single-Operator Re-Arm Variant (ADR-002-015; DR-0001; SAFE-053) | Single-actor self-authorized risk increase (HAZ-024; CONST-005, CONST-011, CONST-013, CONST-015) | Single-approver re-arm rejected; the governed variant is itself the *simpler* fail-closed reduced-scope path for the one-person reality (DR-0001; ADR-002-015 §17.1) | Defined: HAG-EV-001..018 (`NOT_IMPLEMENTED`) | Partial — per-mechanism observability exists (ADR-DEV-014) | **OPEN** (see §4) |
| 7 | Recovery Barrier + monotonic Recovery Generation (ADR-002-017) | Optimistic resume / auto-re-arm after failure (SAFE-044; anti-pattern §39.8) | Health-equals-recovery / reconnect-equals-resume rejected — recovery is a new safety decision (ADR-002-017 §23; philosophy §23) | Defined: SBR-EV-001..012 (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |
| 8 | Generation-fencing across incident / deviation / monitoring domains (ADR-002-026, ADR-002-027, ADR-002-028) | Stale-generation reactivation of a closed restrictive state | Closure / quiet-time-as-permission rejected — administrative closure is non-permissive and recovery does not revive (SIR-INV-012, SIR-INV-015) | Defined: SIR-, WDR-, STM-EV families (`NOT_IMPLEMENTED`) | **OPEN** (see §4) | **OPEN** (see §4) |

## 4. Consolidated OPEN Findings

These are recorded honestly, per AX-005 and philosophy §24, as questions the corpus does not
yet answer. None is resolved by this register.

- **Q4 — testability (all eight rows): defined, not demonstrated.** Every cited EV family is
  `NOT_IMPLEMENTED`; a defined test is not a passed test (philosophy §33). This register makes
  no claim that any mechanism's behaviour has been tested.
- **Q5 — operator understanding of the *degraded* state: OPEN corpus-wide.** Per-mechanism
  observability exists (ADR-DEV-014 OBS-INV-001..003), but no consolidated, cross-mechanism,
  operator-facing safety-state view is owned by any ADR. Whether an operator can understand the
  *combined* degraded state across these mechanisms is a review item (review M-25).
- **Q6 — safe removability / decommission: OPEN for all eight rows.** The corpus specifies no
  removal or decommission path for any of these mechanisms; AX-005's "can it be safely removed
  later" is therefore unanswered corpus-wide.
- **Egress single point (row 5) carries the M-06 residual.** Whether an out-of-band
  final-egress containment path independent of the egress enforcement point actually exists is
  the open M-06 item; EGRESS-EV-013 registers the obligation and SAFE-054 permits closing it via
  the accepted-residual-risk / reduced-scope branch (gate-status §4.5).

## 5. Standing (restated)

This register is non-normative and creates no verification evidence, no acceptance, and no live
readiness. It adds nothing to either evidence count (Part-1 372; development track 98). It is an
EV-L0 governance record; its cell citations and the OPEN findings are review items, with reviewer
provenance recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).
