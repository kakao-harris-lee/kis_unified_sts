# tos-spec Part 3 — ADR Decision Map (분해 제안서)

**Date:** 2026-07-15
**Status:** Decision Record — proposal awaiting go/no-go (no ADRs authored yet)
**Scope:** `tos-spec/src/part-3-development/` (RFC-008 Strategy DSL, RFC-009 Agent
Guide, RFC-010 Testing Strategy, RFC-011 Operational Guidelines)
**Question:** Does Part 3 need its own ADR series, and if so, how should the 25
open questions decompose into ADRs?

---

## 1. Background — verified current state

- The **only ADR series that exists is `ADR-002-001 … ADR-002-030`** (30 records),
  all under Part 1 (`part-1-foundation/`). They decompose **RFC-002 Architecture**:
  RFC-002 states each mechanism at a high level and delegates the exact, verifiable
  decision with the phrasing *"ADR-002-NNN defines the exact …"*. ADRs are named by
  their parent RFC number (RFC-002 → ADR-002-NNN).
- **Part 2 (RFC-003–007) has 0 open questions and 0 ADRs.** It is self-contained at
  its layer and references only ADR-002-xxx.
- **Part 3 (RFC-008–011) has 25 enumerated `§14 Open Questions` and 0 ADRs.** Each
  RFC explicitly forbids resolving them by *informal convention* and marks them open
  "while a Review Draft." No Part-3 RFC references any future ADR series.
- No roadmap/plans document mentions ADRs for the Decision or Development layers.

**Conclusion.** The premise "Part 2처럼" is inverted — Part 2 has no ADRs; the
ADR-002 series belongs to Part 1's RFC-002. Part 2 and Part 3 are currently in the
*same* state (RFC-only). So the real question is **whether Part 3 should adopt the
Part-1 rigor (ADR-002 pattern)**, and the strongest signal that it should is the
**asymmetry: 25 deferred design decisions vs Part 2's zero.** Those 25 must be
resolved *somewhere* before Part 3 can leave Review Draft, and the established tool
for "record an exact decision, number it, review it independently" is the ADR.

---

## 2. Consolidation principle (why 25 → ~15)

Several open questions are the **same underlying decision across different RFCs** and
must collapse into one ADR rather than duplicate per-RFC:

| Cross-cutting decision | Raw questions merged |
|---|---|
| Artifact reproducibility granularity (bit-for-bit vs reproducible-from-recorded-inputs) | RFC-008 Q3⁻, RFC-009 Q3, RFC-010 Q2 |
| Independent review/verification of an AI-authored strategy (human/tool/either) | RFC-009 Q2, RFC-010 Q4 |
| Externally-sourced / LLM-derived value staleness & capture | RFC-008 Q3, RFC-009 Q6 |
| Authoring provenance ↔ software-artifact admission (ADR-002-029) | RFC-008 Q7, RFC-009 Q1 |

Because roughly **half the decisions are cross-cutting**, a naive per-RFC numbering
(`ADR-008-xxx`, `ADR-009-xxx`, …) is a poor fit — a cross-cutting ADR has no single
owning RFC. This drives the numbering recommendation in §5.

---

## 3. Candidate ADR map (25 open questions → 15 candidate ADRs)

Grade legend: **ADR** = standalone decision record; **ADR/clar** = contested — the
pure-representation portion could instead be resolved by an in-place RFC
clarification. Priority: **T1** foundational (gates others) · **T2** core · **T3**
operational/scale.

| ID | Candidate ADR (decision at stake) | Covers | Grade | Tier | Upstream anchor |
|---|---|---|---|---|---|
| D1 | DSL realization form & purity/escape-closure enforcement (standalone lang vs sandboxed embedding vs restricted API; how enforcement is itself verified) | 008 Q1, Q2 | ADR | **T1** | RFC-008 §9/§11 item 17 |
| D2 | Artifact reproducibility & identity granularity (bit-for-bit vs recorded-inputs) so "tested = admitted" | 008 Q3⁻, 009 Q3, 010 Q2 | ADR | **T1** | ADR-002-016 |
| D3 | Externally-sourced / LLM-derived value: pre-eval capture, staleness, re-authoring; no live side channel | 008 Q3, 009 Q6 | ADR | T2 | ADR-002-018 |
| D4 | Authoring provenance record + versioning/substitution + admission binding | 008 Q7, 009 Q1 | ADR | **T1** | ADR-002-029 |
| D5 | Independent review of AI-authored strategy + rationale representation (aids review, not mistaken for verified conformance) | 009 Q2, Q4, 010 Q4 | ADR | **T1** | philosophy §34; RFC-009 §10 |
| D6 | Bulk/family authoring: per-artifact review & admission not diluted by scale | 009 Q5 | ADR | T3 | RFC-009 §10 |
| D7 | Strategy output semantics: no-action/hold vs explicit-flat (target=0); atomic unit (per-instrument vs portfolio vector); no combined-authority aggregation | 008 Q4, Q5 | ADR/clar | T2 | RFC-003 §§13, 16 |
| D8 | Degraded-companion-model authoring (degradation narrows, never widens, the action set) | 008 Q6 | ADR | T2 | RFC-003 §16 Q6 |
| D9 | Containment adversarial escape-vector minimum set & how it stays current as the DSL evolves | 010 Q1 | ADR | T2 (needs D1) | RFC-008 §11 |
| D10 | Backtest methodology, cost/slippage realism, and look-ahead/overfit disqualifiers | 010 Q3 | ADR | T2 | RFC-005 §9; RFC-006 §11 |
| D11 | Test-assumptions recording discipline **and** the pre-deployment-testing ↔ runtime-monitoring boundary | 010 Q5, Q6 | ADR/clar | T2/T3 | ADR-002-028 |
| D12 | Re-arm reconciled-state checklist & where it binds vs the ADR-002-017 recovery barrier | 011 Q1 | ADR | T2 | ADR-002-017 |
| D13 | Operator boundaries: approved degraded-response vs break-glass; operator-containment vs incident governance | 011 Q2, Q5 | ADR | T3 | ADR-002-015/027 |
| D14 | Operator observability contract & "withhold re-arm" as a first-class recorded outcome (without the dashboard becoming a trusted authority) | 011 Q3, Q4 | ADR/clar | T3 | ADR-002-028 |
| D15 | Operator authority scope expression & revocation | 011 Q6 | ADR | T3 | ADR-002-015; Vision §6.6 |

Every raw open question (008 Q1–Q7, 009 Q1–Q6, 010 Q1–Q6, 011 Q1–Q6 = 25) is
accounted for above.

---

## 4. Priority tiers (authoring order)

- **T1 — Foundational, gate the rest (4): D1 → D2 → D4 → D5.** These make the
  RFC-008/009/010 core claims *demonstrable*. In particular **D1 is a hard
  prerequisite for D9** (you cannot define the escape-vector test set until the
  enforcement mechanism is chosen). D2/D4/D5 cross-reference each other (artifact
  identity ↔ provenance ↔ independent review), so author them as one T1 block.
- **T2 — Core (6): D3, D7, D8, D9, D10, D11.**
- **T3 — Operational/scale (5): D6, D13, D14, D15 (+ D11 latter half).**

---

## 5. Numbering — recommendation

The ADR-002 convention keys ADRs to a single anchor RFC (RFC-002). Part 3 has **four
co-equal RFCs and cross-cutting decisions**, so there is no single anchor.

- **Recommended: a single consolidated, RFC-neutral Development ADR series —
  `ADR-DEV-001 … ADR-DEV-0NN`.** Each Part-3 RFC references the relevant `ADR-DEV`
  from its §14 (mirroring how RFC-002 references ADR-002-xxx). This handles the
  cross-cutting decisions cleanly and keeps one review queue.
- Alternatives considered: `ADR-008-NNN` anchored to RFC-008 as the part's first RFC
  (mimics ADR-002 but mis-attributes cross-cutting ADRs to RFC-008); strict per-RFC
  `ADR-008/009/010/011-NNN` (clean ownership, breaks for the 4 cross-cutting ADRs).

---

## 6. Scale & independent-review load

- **ADR count:** ~15 as mapped; **~12–13** if the three `ADR/clar` items (D7, D11,
  D14) resolve their pure-representation portions as in-place RFC clarifications.
- **Authoring load:** each ADR is narrower than an ADR-002-xxx (one decision each),
  so shorter documents than Part 1.
- **Review load:** each ADR should carry the **same independent adversarial EV-L0**
  the RFCs received → **~12–15 EV-L0 passes**. The four T1 ADRs are the gate; focus
  review rigor there. (RFC-008–011 themselves are already at independent EV-L0
  PASS-WITH-FIXES, so the ADR layer is the next verification frontier.)

---

## 7. Recommended path (proposal)

1. **Numbering:** adopt the consolidated **`ADR-DEV-NNN`** series (§5).
2. **Contested items (D7/D11/D14):** default them to full ADRs, with an explicit
   option during authoring to demote a pure-representation sub-part to an RFC
   clarification (targets the ~12–13 lower bound).
3. **Sequence:** author **T1 first** (D1 → {D2, D4, D5}) as one block, each with an
   independent EV-L0, before starting T2/T3. Do not begin D9 until D1 is accepted.
4. Each Part-3 RFC's `§14 Open Questions` gains a pointer to the `ADR-DEV` that will
   resolve it (so the deferral has a named home), applied when the corresponding ADR
   is drafted — not preemptively.

This keeps Part 3 on the Part-1 rigor bar while avoiding a premature 15-document
commitment: the go/no-go can be taken on the T1 block alone.

---

## 8. Open sub-decisions (user's call)

| # | Decision | Recommendation |
|---|---|---|
| 1 | Numbering scheme | **Consolidated `ADR-DEV-NNN`** |
| 2 | D7/D11/D14: ADR vs RFC-clarification | **ADR by default, demote pure-representation parts if trivial** |
| 3 | Initial scope | **T1 block (D1/D2/D4/D5) first**, then reassess |
| 4 | Whether to proceed at all | Pending — this record exists to make the go/no-go informed |

---

## 9. Next step

On go: write a Development Plan for the **T1 block** (D1, D2, D4, D5) — TDD/authoring
order, per-ADR EV-L0 review lane, and the `§14` back-pointer edits — then author and
independently review those four before opening T2. On no-go: leave this record as the
rationale and add a one-line `§14` note in each Part-3 RFC that its open questions are
tracked here.
