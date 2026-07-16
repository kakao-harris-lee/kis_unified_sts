# ADR-DEV-008 — Authoring Under a Degraded or Unavailable Companion Model

**ADR ID:** ADR-DEV-008
**Title:** Authoring Under a Degraded or Unavailable Companion Model
**Status:** Proposed
**Decision Type:** Implementation-Layer Decision (Safety-Relevant)
**Parent Document:** RFC-008 — Strategy DSL (with RFC-003 and RFC-004/006/007)
**Governed By:** RFC-000 — Trading Constitution and RFC-001 — Safety Case
**Constrained By:** RFC-002 — Architecture and RFC-003 — Decision Framework
**Resolves:** RFC-008 §14 Q6
**Date:** 2026-07-16
**Version:** 0.1 Review Draft
**Last Updated:** 2026-07-16
**Owners:** Trading Operating System Architecture Board

---

## 1. Decision

When a companion model (RFC-004 market, RFC-006 risk, RFC-007 hedge) is degraded or
unavailable, the DSL SHALL make the conforming expression **narrow the action set — a
more conservative action or no-action — never widen it**:

* a degraded, `UNKNOWN`, or `STALE` model output is expressible only restrictively; the
  DSL provides no construct that treats absence-of-a-model or a degraded output as a
  neutral prior or a permissive default (RFC-008 §10; ADR-002-018 CII-INV-005; RFC-006
  §6 principle 4; RFC-003 §6);
* the degraded-context decision is a first-class, reproducible, recorded outcome — with
  its rationale — not an error, a null, or a silent fallback (RFC-008 §6 principle 5;
  ADR-DEV-002);
* a strategy SHALL NOT substitute its own computation for a degraded model to acquire the
  authority that model's output would have carried — self-computed risk is not capacity
  and a self-computed hedge is not protective (RFC-008 §10, §11 items 6/9; ADR-002-002;
  ADR-002-001 §6);
* one model's degradation narrows only the affected strategy's own scope and never widens
  another strategy's outcome or a safety control (RFC-008 §9 isolation).

This resolves RFC-008 §14 Q6. It grants no authority, defines no model, and authorizes no
live operation.

---

## 2. Context

RFC-008 §10 requires a strategy to consume the RFC-004–007 models as evidence and makes
`UNKNOWN` restrictive: "Missing, stale, conflicting, ambiguous, or unverifiable context
or model output SHALL be expressible only restrictively; the DSL SHALL NOT provide a
permissive default that treats absence as permission (ADR-002-018 CII-INV-005; RFC-006
§6)." RFC-008 §6 principle 6 forbids any construct that widens the action set as
confidence rises, and principle 5 makes no-action first-class. RFC-006 §6 principle 4
holds that a missing/stale/unverifiable risk input is worst-credible.

RFC-008 §14 Q6 leaves open *how* an Authored Strategy expresses a decision when a
companion model is itself degraded or unavailable, "such that degradation narrows rather
than widens the action set." This ADR fixes that authoring discipline. It defines none of
the models (RFC-004–007), the Critical Input degraded-state mechanism (ADR-002-018), or
the risk-capacity authority (ADR-002-002) — it fixes how a strategy may *express* a
decision under model degradation.

---

## 3. Decision Drivers

1. **Uncertainty reduces authority** (philosophy §8; RFC-003 §6). A degraded model is
   uncertainty; the only conforming responses are more conservative or no action.
2. **Absence is not a neutral prior.** Treating a missing model as a zero, a mean, or a
   permissive default silently widens authority (RFC-008 §10; ADR-002-018 CII-INV-005).
3. **No-action is a valid, first-class decision** (philosophy §6; RFC-008 §6 principle 5).
   Declining under degradation must be as ordinary and reproducible as acting.
4. **A strategy cannot mint the authority a model carried.** Self-computing a substitute
   for a degraded risk/hedge model does not confer capacity or protective status
   (RFC-008 §11 items 6/9; ADR-002-002; ADR-002-001 §6).
5. **Degradation is contained, not contagious.** One model's failure must not widen
   another strategy's or a control's authority (RFC-008 §9).

---

## 4. Scope and Non-Scope

**In scope:**

* how the DSL expresses a decision when a companion model is degraded or unavailable;
* the restrictive, narrowing treatment of a degraded/`UNKNOWN`/`STALE` model output;
* the first-class, reproducible status of the degraded-context decision;
* the prohibition on substituting self-computation to acquire a degraded model's
  authority.

**Not in scope (owned elsewhere):**

* the market/risk/hedge models themselves — RFC-004/006/007;
* the Critical Input degraded-state classification and `UNKNOWN`/`STALE`/`INVALID`
  mechanism — ADR-002-018;
* risk-capacity authority and the RCL — ADR-002-002; protective classification —
  ADR-002-001 §6;
* staleness/re-authoring of a captured model output as an external value — ADR-DEV-003;
* reproducibility/identity of the degraded outcome — ADR-DEV-002;
* numeric degradation thresholds and conservative defaults, which are approved
  configuration.

---

## 5. Definitions

This ADR reuses canonical terms from RFC-008 §5, RFC-003 §5, and ADR-002-018
(`UNKNOWN`/`STALE`/`CONFLICTED`/`INVALID`; **Critical Input**), and SHALL NOT introduce
synonyms. The
following terms are scoped to this decision and are non-authorizing.

* **Companion Model** — an RFC-004 market, RFC-006 risk, or RFC-007 hedge model whose
  output an Authored Strategy consumes as evidence (RFC-008 §10).
* **Model Degradation** — a state in which a Companion Model's output is unavailable,
  `UNKNOWN`, `STALE`, `CONFLICTED`, `INVALID`, or otherwise unverifiable (ADR-002-018).
* **Narrowed Action Set** — the conforming set of outcomes under Model Degradation,
  containing only more-conservative actions and no-action; it is a subset of, never a
  superset of, the nominal action set.

These terms describe an authoring discipline under degradation. None grants authority or
defines a model.

---

## 6. Safety Invariants

* **DCM-INV-001 — Degradation Narrows, Never Widens.** Under Model Degradation the
  conforming expressible outcomes are a more conservative action or no-action; the DSL
  provides no construct that widens the action set as a model degrades (RFC-008 §6, §10;
  RFC-003 §6).
* **DCM-INV-002 — Degraded Output Is Restrictive, Not Neutral.** A degraded, `UNKNOWN`,
  or `STALE` Companion Model output is expressible only restrictively and is never a
  neutral prior or a permissive default (RFC-008 §10; ADR-002-018 CII-INV-005; RFC-006 §6
  principle 4).
* **DCM-INV-003 — The Degraded Decision Is First-Class and Reproducible.** A decision made
  under Model Degradation is a recorded, reproducible outcome with its rationale, as
  rigorous as an action — not an error, null, or silent fallback (RFC-008 §6 principle 5;
  ADR-DEV-002 ARI-INV-002).
* **DCM-INV-004 — No Authority Substitution.** A strategy SHALL NOT substitute its own
  computation for a degraded Companion Model to acquire the authority that model's output
  would have carried; self-computed risk is not capacity and a self-computed hedge is not
  protective (RFC-008 §10, §11 items 6/9; ADR-002-002; ADR-002-001 §6).
* **DCM-INV-005 — Degradation Is Scope-Isolated.** One Companion Model's degradation
  narrows only the affected strategy's own scope and never widens another strategy's
  outcome or a safety control (RFC-008 §9; RFC-003 §13).

---

## 7. Narrowing Under Degradation (RFC-008 §14 Q6)

The DSL SHALL make the natural, and only conforming, expression under Model Degradation a
Narrowed Action Set (DCM-INV-001, -002):

* a degraded/`UNKNOWN`/`STALE` output is readable only as restrictive evidence; there is
  no construct that reads it as a neutral prior, a zero, a mean, or a "proceed anyway"
  default (RFC-008 §10; ADR-002-018 CII-INV-005);
* as a model degrades, the expressible outcomes contract toward no-action; the DSL
  provides no construct whose effect is to widen the action set under degraded context
  (RFC-008 §6 principle 6 first clause; RFC-003 §6 principle 3 — "the action set SHALL
  NOT expand");
* an unavailable model is treated restrictively — blocking new risk in the dependency it
  feeds (ADR-002-018 CII-INV-005) and, for a risk or hedge dependency, worst-credible
  (RFC-006 §6 principle 4) — never as an absence to be optimistically filled.

Two things here are distinct. That a degraded output cannot be read as a neutral prior
and cannot carry the model's authority is **structural** — the DSL provides no such
construct (DCM-INV-002, -004). That a strategy *actively* narrows on a dependency it
consults is an **authoring obligation** — the author writes the conservative/no-action
path, and RFC-010 and ADR-DEV-005 review verify it. (A strategy that never consults a
degraded model is simply unaffected by its degradation; its authority remains capped by
capacity and approval regardless.)

---

## 8. The Degraded Decision Is First-Class

A decision under Model Degradation is a real, recorded outcome (DCM-INV-003):

* declining to act, and an explicit conservative action, are directly expressible,
  reproducible, and carry a rationale, exactly as a nominal action does (RFC-008 §6
  principle 5; ADR-DEV-002);
* a degraded decision SHALL NOT be represented as an error, an exception, a null, or a
  silent fallback that hides the fact that the system chose to narrow; an evaluation that
  exhausts a time or resource bound degrades to a recorded no-action, not a thrown error
  (RFC-008 §9);
* the degraded outcome and its rationale are reproducible from the Recorded Input Set and
  recorded as decision evidence, so review and replay see that degradation was handled,
  not swallowed (ADR-DEV-002 ARI-INV-002).

---

## 9. No Authority Substitution

Model Degradation does not license a strategy to manufacture the authority the model
carried (DCM-INV-004):

* a strategy MAY still express a risk estimate as evidence, but a self-computed estimate
  substituted for a degraded RFC-006 output is not authoritative capacity and SHALL NOT
  size beyond the Aggregate Risk Decision or RCL commitment (RFC-008 §11 item 9;
  ADR-002-002);
* a strategy MAY propose a hedge, but a self-computed hedge substituted for a degraded
  RFC-007 output is not protective; protective classification is owned by the Protective
  Action Controller (RFC-008 §11 item 6; ADR-002-001 §6);
* substitution that would widen authority is a §11 boundary violation, unexpressible by
  construction (ADR-DEV-001), and caught by the ADR-DEV-009 containment suite.

Degradation narrows what a strategy may claim; it never lets the strategy step into the
degraded model's authority.

---

## 10. Alternatives Considered

* **10.1 Treat a missing model as a neutral prior (zero/mean) and proceed.** Rejected:
  absence is not permission; a neutral prior silently widens the action set (DCM-INV-002;
  RFC-008 §10).
* **10.2 Let the strategy self-compute a substitute carrying the model's authority.**
  Rejected: self-computed risk/hedge is evidence, not capacity or protection (DCM-INV-004;
  RFC-008 §11 items 6/9).
* **10.3 Represent a degraded decision as an error/exception.** Rejected: that hides the
  narrowing and is not reproducible as a first-class outcome (DCM-INV-003).
* **10.4 Widen the action set to preserve availability under degradation.** Rejected:
  uncertainty reduces authority; availability is never bought by widening under
  degradation (DCM-INV-001; philosophy §8; RFC-003 §6).
* **10.5 Let one model's degradation relax another strategy's constraints.** Rejected:
  degradation is scope-isolated (DCM-INV-005; RFC-008 §9).

---

## 11. Consequences

**Positive.**

* Makes degradation-narrows-not-widens a structural authoring property, closing
  RFC-008 §14 Q6.
* First-class degraded decisions are reviewable and replayable, not hidden in error paths.
* No-authority-substitution keeps a degraded model from becoming a hole through which a
  strategy mints capacity or protection.

**Negative / costs.**

* Strategies must express an explicit conservative/no-action path for each companion-model
  dependency — more authoring surface to design and test.
* A degraded model can force no-action and a missed opportunity; that is the intended,
  conservative consequence (philosophy §8; Vision §9.6).
* Distinguishing "restrictive evidence" from "authoritative output" requires the DSL to
  represent model-output confidence/degradation explicitly.

---

## 12. Failure Modes Introduced by This Decision

* **12.1 Optimistic fill.** A degraded output read as a neutral prior; blocked by the
  no-coercion rule of ADR-002-018 §10 and CII-INV-005 (an `UNKNOWN` input is never
  coerced to a value) together with DCM-INV-002, and exercised by this ADR's §13.2
  model-degradation test under RFC-010 — not by the ADR-DEV-009 containment suite, whose
  minimum set is the RFC-008 §11 prohibited-effect boundary and includes no neutral-prior
  vector.
* **12.2 Authority laundering.** A self-computed substitute treated as capacity/protection;
  blocked by DCM-INV-004 and RFC-008 §11 items 6/9.
* **12.3 Swallowed degradation.** A degraded decision hidden as an error; prevented by
  DCM-INV-003 (first-class, recorded).
* **12.4 Contagion.** One model's degradation widening another scope; blocked by
  DCM-INV-005 and RFC-008 §9 isolation.

---

## 13. Verification Requirements

The following SHALL be demonstrated (executed by RFC-010):

* **13.1** A degraded/`UNKNOWN`/`STALE` companion-model output yields only a Narrowed
  Action Set — conservative or no-action — never a widened one (DCM-INV-001, -002).
* **13.2** No construct reads an absent model as a neutral prior or permissive default
  (DCM-INV-002).
* **13.3** A degraded decision is produced, recorded, and reproduced with rationale, as an
  action is — not as an error/null/fallback (DCM-INV-003).
* **13.4** A self-computed substitute for a degraded model does not size beyond capacity
  or obtain protective status (DCM-INV-004).
* **13.5** One model's degradation does not widen another strategy's outcome or a safety
  control (DCM-INV-005).

---

## 14. Acceptance Criteria

ADR-DEV-008 is acceptable when:

* degradation narrows and never widens the action set (DCM-INV-001), with degraded output
  restrictive and never neutral (DCM-INV-002);
* the degraded decision is first-class, recorded, and reproducible (DCM-INV-003);
* no self-computed substitute acquires the degraded model's authority (DCM-INV-004);
* degradation is scope-isolated (DCM-INV-005);
* independent adversarial review (EV-L0) confirms every §13 obligation is discharged and
  every citation resolves against source.

Acceptance records a decision; it grants no authority and does not authorize live
operation, which remain governed by RFC-001 and VER-002-001.

---

## 15. Traceability

| Requirement | Discharge in ADR-DEV-008 |
|---|---|
| RFC-008 §14 Q6 (degradation narrows, not widens) | Narrowed Action Set is the only conforming expression (§7; DCM-INV-001) |
| RFC-008 §10 (UNKNOWN restrictive; no permissive default) | degraded output restrictive, not neutral (§7; DCM-INV-002) |
| RFC-008 §6 principles 5/6 (no-action first-class; no widening) | first-class degraded decision; no widening construct (§§7, 8; DCM-INV-001/003) |
| RFC-008 §9 (isolation) | degradation scope-isolated (DCM-INV-005) |
| RFC-008 §11 items 6/9 (no protective self-label; no size-beyond-capacity) | no authority substitution (§9; DCM-INV-004) |
| RFC-003 §6 (uncertainty restrictive) | narrowing under degradation (§7; DCM-INV-001) |
| RFC-006 §6 principle 4 (UNKNOWN worst-credible) | unavailable model treated worst-credible (§7; DCM-INV-002) |
| ADR-002-018 CII-INV-005 (ambiguity restrictive) | degraded output blocks new risk, no permissive default (DCM-INV-002) |
| ADR-002-002 (RCL/capacity) | self-computed risk is not capacity (§9; DCM-INV-004) |
| ADR-002-001 §6 (protective classification) | self-computed hedge is not protective (§9; DCM-INV-004) |
| ADR-DEV-001 (unexpressibility) | authority *substitution* (§11 items 6/9) unexpressible by construction (§9); optimistic-fill / neutral-prior is blocked instead by ADR-002-018 §10 / CII-INV-005 (§7, §12.1) |
| ADR-DEV-002 (reproducibility) | degraded decision reproducible and recorded (§8; DCM-INV-003) |
| ADR-DEV-003 (external-value staleness) | a stale captured model output degrades → narrows (§7; cross-ref) |
| philosophy §6, §8; Vision §9.6 | no-trade is valid; uncertainty restrictive; missed opportunity acceptable (§§3, 11) |

This ADR introduces no SAFE-xxx requirement and no numeric bound. It fixes the
authoring discipline under model degradation and relies on RFC-004/006/007, ADR-002-018,
ADR-002-002, and ADR-002-001 for the models and their governance.

---

## 16. Review History

### v0.1 — Initial Draft

* Established ADR-DEV-008, resolving RFC-008 §14 Q6 (expressing a decision when a
  companion model is degraded or unavailable so degradation narrows, not widens, the
  action set).
* Set the decision: a degraded/`UNKNOWN`/`STALE` model output is expressible only
  restrictively (never a neutral prior); the degraded decision is a first-class,
  reproducible, recorded outcome; a strategy may not substitute self-computation to
  acquire the degraded model's authority; and degradation is scope-isolated.
* Defined five invariants DCM-INV-001…005 and traced them to RFC-008 §6/§9/§10/§11,
  RFC-003 §6, RFC-006 §6 principle 4, ADR-002-018 (CII-INV-005), ADR-002-002,
  ADR-002-001 §6, and ADR-DEV-001/002/003.
* Introduced no SAFE-xxx requirement, numeric bound, or authority; confers no acceptance
  or live-readiness.
* Independent adversarial EV-L0 document review returned **PASS-WITH-FIXES** with no
  Critical finding; the never-widens safety core was found airtight (no expressible
  widening path survives the capacity/protective/isolation bounds) and all twelve attack
  sequences blocked. Three Major findings were resolved: (M1) §7 overclaimed narrowing as
  "structural" while §11 admits an authoring obligation — now split into the structural
  never-widens guarantee and the authoring obligation to write the conservative/no-action
  path (verified by RFC-010/ADR-DEV-005); (M2) §12.1 and §15 attributed optimistic-fill
  blocking to a non-existent ADR-DEV-009 "permissive-default vector" — re-anchored on the
  ADR-002-018 §10 / CII-INV-005 no-coercion rule and this ADR's §13.2 RFC-010 test, with
  the §15 row split (substitution → ADR-DEV-001; neutral-prior → ADR-002-018); (M3) §7's
  RFC-006 §6 principle 4 (risk-scoped) was over-generalized to all models — now cites
  CII-INV-005 for the general case, worst-credible only for risk/hedge. Six Minor fixes:
  §1/§3 restored the hedge-is-not-protective half of DCM-INV-004; §5 state enumerations
  reconciled (INVALID explicit); §8 corrected the outcome anchor to ARI-INV-002 and cited
  RFC-008 §9 bounded-evaluation for error→no-action; the principle-6 axis was corrected to
  RFC-003 §6 principle 3; and the RFC-008 §14 Q6 back-annotation was already added. The
  review is EV-L0 only and confers no acceptance or live-readiness.
