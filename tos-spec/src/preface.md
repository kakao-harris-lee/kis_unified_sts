# Preface

This is the front door to the Trading Operating System (TOS) specification corpus.
It is **non-normative**: it orients a reader and confers no requirement, authority,
or live-readiness. Where it appears to conflict with any normative document, the
normative document governs (RFC-000 §12).

## What this corpus is

The corpus specifies a mission-critical trading operating system as a layered set
of documents. It is an authoring track: every ADR is `Proposed`, every evidence
item is `NOT_IMPLEMENTED`, and no document confers live readiness. Authoring or
reviewing a document is never verification (philosophy §33).

## The four parts

| Part | Scope | Primary documents | Verification track |
|---|---|---|---|
| 0 — Introduction | Direction and stance (non-normative) | `vision.md`, `philosophy.md` | — |
| 1 — Foundation | Constitution, safety case, architecture, safety-critical ADRs | RFC-000, RFC-001, RFC-002, ADR-002-001…030 | VER-002-001 + EVIDENCE-REGISTER-002 (372 items) |
| 2 — Decision | Decision framework and companion models | RFC-003…007 | VER-DEV-001 + EVIDENCE-REGISTER-DEV |
| 3 — Development | DSL, agent guide, testing, operations, dev ADRs | RFC-008…011, ADR-DEV-001…015 | VER-DEV-001 + EVIDENCE-REGISTER-DEV (97 items, Parts 2+3) |

## Two views of the same corpus

The corpus is read along two complementary axes, which together cover every layer.

**Derivation** (how intent becomes evidence; vision §7.7):

```text
Vision -> Philosophy -> Constitution -> Safety Requirements -> Architecture
      -> Architecture Decisions -> Implementation -> Verification Evidence
```

**Governance precedence** (which document governs which; RFC-000 §12; higher governs
lower, lower never reinterprets higher):

```text
Trading Constitution (RFC-000)
  -> Safety Case (RFC-001)
    -> Architecture RFCs (RFC-002) + Architecture Decisions (ADR-002-001…030)
       + Verification Evidence (VER-002-001)
      -> Decision Framework (RFC-003…007)
        -> Development (RFC-008…011, ADR-DEV-001…015) + Verification Evidence (VER-DEV-001)
          -> Operational Procedures (runtime; RFC-011 governs, ADR owners enforce)
```

The single meta-rule binding the two: **no Part-2 or Part-3 artifact may widen,
relax, or reinterpret any Part-1 authority, limit, gate, or Hard Safety Envelope
constraint — a subordinate-layer artifact may only narrow authority, never widen
it** (RFC-000 §12). This is what makes the layering safe.

## Reading the current effective state

* The **canonical documents** (the RFCs, ADRs, and VER specs listed above) are the
  source of truth.
* `patches/` and `reviews/` are **git-excluded working artifacts**, not canonical;
  a review is a report and a patch is provenance. The committed record of what a
  patch changed is the semantic merge map in `ARCHITECTURE-GATE-STATUS.md §3`.
* **Status lives in two overlays:** Part 1 in `ARCHITECTURE-GATE-STATUS.md`
  (approval state, evidence debt, merge map); Parts 2/3 in `VER-DEV-001` and
  `EVIDENCE-REGISTER-DEV`. Everything is currently `Proposed` / `NOT_IMPLEMENTED`.

## Conventions

* **`Depends On` headers are backward-only.** An ADR's `Depends On` line records
  the documents it relies upon (lower ADR numbers, foundational RFCs). Acceptance-
  blocking *forward* dependencies (e.g. a later ADR that must also pass) are not
  listed there; they live in each ADR's Approval Gate section.
* **Broker-agnostic.** The normative corpus defines the TOS independently of any
  concrete broker; broker constraints are expressed only in Broker Capability
  Profile dimension language. Facts about a specific broker belong to non-normative
  Broker Capability Profile instances produced on the implementation track, never
  in a normative document.
