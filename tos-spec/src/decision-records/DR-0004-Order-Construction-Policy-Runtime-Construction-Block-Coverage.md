# DR-0004 — Order Construction Policy: the `_runtime.construction` Block and What the Kernel Now Realizes

- **Decision ID:** DR-0004
- **Date:** 2026-09-16
- **Status:** Proposed (becomes `Accepted` when the System Owner merges the
  change that introduces it, per DR-0002 §6's own convention)
- **Decision Owner:** System Owner (final risk-acceptance authority, vision §12.1)
- **Category:** Governance Decision
- **Originating Finding:** DR-0002 §2.3's coverage table records, for the Order
  Construction Policy, that everything beyond identity/generation/version and
  the two `_runtime` codec facts is "not realized — preserved as data; `TBD`
  where owed". The (a′) wave makes a defined subset of the OCP's RFC-002 §9
  construction declarations **machine-readable and kernel-consumed**, which
  makes that row false. DR-0002 §6 states that such a change "supersedes the
  corresponding rows of §2.3 **by a new decision record, never by editing this
  one**". This is that record.
- **Normative Carriers:** DR-0002 §§2.3, 6; RFC-002 §9.1; ADR-002-020 §§10, 11;
  ADR-002-014 §13; DR-0003 (the sibling extension for ARE/AFG instances)

---

## 1. Context

DR-0002 fixed placement, activation and coverage for the Venue Constraint
Policy and the Order Construction Policy. Its coverage table was honest about a
gap it did not close: RFC-002 §9.1:553 names Order Construction Policy
governance as **the supplier of construction rules**, and `SizingBound`'s own
docstring seals the bypass structurally — "an author cannot hand the
constructor a quantity, because no quantity field exists" — yet the OCP
instance stated those rules as **prose strings**, and its `_runtime` block
carried only `canonicalization_version` and `wire_codec`. The supplier was
named; there was no supply path. The runtime therefore re-declared, per
attempt, what the governed document already declared in prose.

The (a′) wave closes that gap with **no kernel change** (kernel diff 0). It adds
one `_runtime` sibling block, `construction`, parsed into a runtime type
(`tos_runtime.venue.construction_rules.ConstructionRules`) that the composition
root folds into the envelope the kernel's own construction path consumes.

## 2. Decision

### 2.1 The block, and the rows it supersedes

A new `_runtime.construction` block is kernel-realized content. It carries
`sizing` (the `SizingBound` the derivation consumes, plus the closed set of
admitted quantity bases), `authorized_axes`, `action_class_shape`
(`(ActionClass, direction)` → side / position effect), and `effect_dimensions`.

This **supersedes** the DR-0002 §2.3 row reading "Order Construction Policy:
every other §9 declaration | not realized | preserved as data; `TBD` where
owed", for the named subset only. The replacement row:

| Template content | Kernel realization | v1 instance treatment |
|---|---|---|
| Order Construction Policy: direction/side/position-effect rules, price-tick-lot-quantity-and-rounding rules, economic effect declarations | `_runtime.construction` → `ConstructionRules` → `ProposedConstructionEnvelope` (`sizing_bound`, `authorized_axis_bindings`, `effect_dimensions`) consumed by `construct_candidate_command` / `derive_order_size` / `derive_economic_effect_envelope` | filled where the document's own prose determines the value; **nothing is invented** — a rule the prose does not determine is left operator-fill and refuses the load |

Every other §9 declaration remains as DR-0002 recorded it: preserved as data,
not interpreted.

### 2.2 The document remains the only authority

This record grants the runtime no new authority. Every field in the block is
something the OCP document already asserts; the block is its machine-readable
form. A mismatch between the block and the document's prose is a **document
defect**, not a code choice.

### 2.3 What the OCP does not own

`quantity_unit` is **deliberately absent** from the block. The Venue Constraint
Policy owns it (`_runtime.quantity_unit`), and the kernel denies twice on it —
once when the sizing bound states none, and again on any envelope/venue
disagreement (ADR-002-020 §11:301). Declaring it in both documents would place
one fact in two files with nothing pinning them. The composition root takes the
venue's value, so the two agree **by construction, never by hand-synchronisation**.

The same discipline governs side: the block declares side once, inside
`action_class_shape`, and the composition root **derives** the `SIDE` axis
binding from it rather than letting the document state it twice.

### 2.4 Boot-time cross-checks this adds

Because the block restates facts other governed documents own, the composition
root refuses to boot on disagreement, extending the existing
`_cross_check_side_tokens` family:

- every side the OCP yields must be a member of the venue policy's allowed sides;
- the OCP sizing bound must not be **wider** than the venue's (subset, never
  equality — a policy is permitted to be narrower than its venue).

## 3. What this decision does not do

- It does not realize any ADR-002-014 §13 Atomic Activation Protocol step. None
  of §13's ten steps is implemented by this change, and activation continues to
  require the committed Activation Record exactly as before.
- It does not bind the Order Construction Policy's signer/approval/evidence
  fields. They remain `None`, and binding them stays a kernel-round candidate
  as DR-0002 recorded.
- It does not make the deployed paper instance bootable. See §4.
- It does not change any template. The verification templates declare no
  `_runtime` block at all; `construction` is a runtime-only sibling of the
  established `canonicalization_version`/`wire_codec` facts.

## 4. Honest limits

**The digest does not cover this content.** `canonical_digest`'s tamper/stale
check covers `policy_id`, `policy_generation` and `policy_version` — the three
coordinates DR-0002 §2.3 names — and nothing else. Editing a construction leaf
under an unchanged `policy_generation` therefore passes that check **silently**.
Bumping the generation on any content change is the correct practice and is
required by the document's own rules, but it is an operational convention that
no mechanism in the loader enforces. Recording this is the point: a reader who
believed the digest enforced it would be wrong.

**The deployed instance does not boot, by decision.** Operator-fill leaves
remain `TBD` and each independently refuses the load: `scope.accounts`,
`scope.instruments`, `admitted_quantity_bases` (awaiting the deployed strategy
file's own `quantity_basis`), the `DIRECTION` axis value (unfilled because
`scope.action_classes` authorizes both directions and committing the file to one
would narrow a symmetric authorization without operator sign-off), and
`canonical_digest`. This is the state the instance was already in before this
wave; the block adds leaves to that list, not a new class of block.

**An empty economic-effect declaration halts the attempt.** `effect_dimensions`
reaching the kernel empty yields `StageOutcome.UNKNOWN`, and the sequencer
advances only on an explicit ADMIT — so it is a halt, not a permissive default.
"An empty vector is not no effect" is load-bearing, not a slogan.

## 5. Consequences

- The runtime no longer declares construction facts the governed document
  already declares. The two-quantities asymmetry — a derived quantity on the
  intent and command, and a separately declared quantity on the order shape that
  nothing reconciled — is removed at its source.
- A governed document can now be wrong in a way the boot refuses, where before
  it could only be wrong in a way nobody read.
- Future OCP authoring is bound by the loader's fail-closed rules, including the
  long/short symmetry check: an action class declared for one direction without
  its mirror is refused.

## 6. Normative Status and Future Constitutional Work

This record is a governance decision, not a normative specification. A later
change that realizes the remaining ADR-002-014 §13 steps, that binds the Order
Construction Policy's approval fields, or that extends kernel realization beyond
the subset named in §2.1, supersedes the corresponding rows **by a new decision
record, never by editing this one** — the same rule DR-0002 §6 set and this
record follows.

## 7. Related Documents

- DR-0002 (the record this one supersedes rows of), DR-0003 (the sibling
  extension for Aggregate Risk / Action Flow instances)
- `docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md` (the wave)
- `docs/plans/2026-09-16-tos-ocp-sizing-values-proposal.md`,
  `docs/plans/2026-09-16-tos-ocp-effect-dimensions-proposal.md` (the
  operator-approved value tables)
