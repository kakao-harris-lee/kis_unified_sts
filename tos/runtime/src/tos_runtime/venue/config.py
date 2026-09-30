"""tos_runtime.venue.config — Venue Constraint Policy / Order Construction Policy loaders.

TOS venue constraint service wave, plan §2 decisions 1/2/6, §4.1
(``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``), CORRECTED
per team-lead 2026-09-15: the runtime instance YAML documents this package
loads are INSTANCES of the two tos-spec verification templates —
``tos-spec/src/part-1-foundation/verification/VENUE-CONSTRAINT-POLICY-template.yaml``
and ``.../ORDER-CONSTRUCTION-POLICY-template.yaml`` — not a bespoke,
runtime-invented key set.

**A thin re-export shim.** The actual loader implementations live in three
sibling modules, split out purely for this module's own size budget
(``config/tos_size_budget.yaml`` — module ceiling 1000 lines; no behavioural
difference from having them all inline here):
:mod:`tos_runtime.venue._policy_primitives` (shared YAML primitives +
:class:`VenuePolicyConfigError`), :mod:`tos_runtime.venue._venue_policy_loader`
(:func:`load_venue_constraint_policy` + :class:`VenuePolicyScope` /
:class:`LoadedVenuePolicy`), and
:mod:`tos_runtime.venue._order_construction_policy_loader`
(:func:`load_order_construction_policy` + :class:`LoadedOrderConstructionPolicy`).
This module re-exports every public name those three modules define — every
existing ``from tos_runtime.venue.config import ...`` call site is unchanged.

**``_model_view`` / ``_runtime`` discipline — the one rule these loaders
never break** (mirrors :mod:`tos_runtime.brokercap.instance`'s own stated
discipline, its module docstring's "the one rule this module never breaks").
The template's own top-level keys (``artifact_type``, ``schema_version``,
``policy_id``, ``policy_generation``, ``canonical_digest``, ``status``,
``scope``, and the long run of rule-list / ``authority`` / ``evidence``
governance keys) are read EITHER directly as plain scalars/lists — when the
template's own vocabulary already matches what the kernel needs (identity
scalars, the ``scope`` list block) — OR only for PRESENCE/shape fidelity
(every rule-list key, ``approved_by``, ``authority``, ``evidence`` — nothing
is stored from them and nothing is interpreted; a governance document with
an author-editable rule-list is not consulted for kernel construction). Two
SIBLING top-level blocks the templates do not themselves define carry the
kernel-typed content the loaders actually build records from: ``_model_view``
(kernel-field-named values, already in the kernel's own enum vocabulary —
never "fixed" from a template spelling) and ``_runtime`` (runtime-only facts
with no template counterpart at all, e.g.
``instrument_class``/``quantity_unit``/``canonicalization_version``). A
missing ``_model_view``/``_runtime`` block, or a value that is not already
exact kernel vocabulary, is a refusal — never invented
(:class:`VenuePolicyConfigError`).

**``schema_version`` is a hardcoded constant, never a tos-spec read.** The
runtime does not import or read ``tos-spec`` at all (§0.3 sibling-edge
discipline — spec and runtime are separate distributions). The accepted
value is copied by hand from the two templates' own
``schema_version: "1.0-DRAFT"`` line and must be bumped by hand if a future
spec PR changes it.

**``status`` must be ``ISSUED`` (the kernel's own ``ArtifactStatus.ISSUED``
value).** A document still carrying the template's own ``status: DRAFT``
default is refused outright — "a DRAFT policy cannot be activated" — never
silently promoted.

**``canonical_digest``: ``"TBD"`` is accepted, anything else must match.**
Both loaders ALWAYS recompute the digest themselves via the kernel's own
``.issue()`` (never trust a document-supplied digest as input); the
document's own ``canonical_digest`` field is then checked only as an
independent cross-check — the template placeholder ``"TBD"`` passes (the
document has not yet recorded a digest), and any other string must equal the
freshly computed one exactly, or the load refuses (tamper/stale detection —
an operator who edited the policy's content without re-running the issuing
tool would otherwise silently drift).

**The single-live-scope rule (v1).** The template's ``scope`` list fields
allow an arbitrary set (a governed policy MAY one day scope multiple
environments/venues at once); v1 of these loaders only support EXACTLY one
live scope, so ``environments``/``brokers``/``accounts``/``venues``/
``market_segments``/``instruments`` (venue policy) and ``environments``/
``brokers``/``accounts``/``instruments`` (Order Construction Policy) must
each carry exactly one string — zero or two-or-more is refused. The other
``scope`` list keys (``safety_cells``, ``contracts``, and — OCP only —
``venues``/``market_segments``) are accepted as explicit lists of any length
(may be empty) for schema fidelity only; nothing is read from them.
``action_classes`` is validated as a list of kernel ``ActionClass`` tokens on
BOTH loaders (venue policy: cross-checked below; OCP: validated the same way
but with no cross-check — the plan names no OCP-side use of it, so an OCP
``action_classes`` entry is checked for a real ``ActionClass`` spelling and
then discarded). ``order_types`` (OCP only) joined the OCP single-live-scope
SINGLETON set in the (a′) wave (``docs/plans/
2026-09-16-tos-aprime-envelope-order-shape-plan.md`` §4 lane A) — previously
an explicit list of strings, not further typed and discarded; the OCP
loader's ``_runtime.construction`` block now DERIVES the ``ORDER_TYPE``
authorized-axis binding from it, so it must carry exactly one value, same as
``environments``/``brokers``/``accounts``/``instruments`` already did.

**Top-level scalar presence — ``effective_from``/``review_due``.** Both
templates declare these two keys (DR-0002 §2.1: "every template key is
present"); both loaders check only that the KEY is present (the template
itself lets either be ``null`` — not yet effective / no review scheduled —
so a present ``null`` is valid, never a refusal); a present non-``null``
value must be a string. A MISSING key (the template omitted, not merely left
``null``) refuses — team-lead review MEDIUM, 2026-09-15.

**Scope/admission cross-check (venue policy only).** Every
``_model_view.admitting_phase_rules[*].action`` must be a member of
``scope.action_classes`` — a policy that admits an action outside its own
declared scope is refused at load (a scope-declaration bug, not a runtime
admissibility judgement; these loaders author no ``OrderAdmissibilityResult``).

Fail-closed discipline throughout (mirrors :mod:`tos_runtime.calendar.config`'s
own module docstring): a missing file, a non-mapping top level, a missing
required key, or a required scalar left ``null`` (named-TBD) all refuse to
load — never a silent default. Explicit-list keys accept ``[]`` as a
deliberate "none declared"; a missing key or ``null`` is refused as
still-TBD.

**Deliberate exception — six numeric ``shape_constraints`` bounds** (inside
``_model_view``). ``price_min``/``price_max``/``tick_size``/``lot_size``/
``min_quantity``/``max_quantity`` MAY be ``null`` = "no source" (plan §2
decision 2; ADR-002-019 §9: "None alone proves current admissibility unless
the active policy explicitly defines the fact"). A ``null`` bound is passed
straight through to the kernel's ``VenueShapeConstraints`` —
``order_shape_admissible`` already returns ``UNKNOWN`` on a ``None`` bound —
the honest semantics for a constraint the operator has not yet sourced. Each
null bound's field name is recorded on
:attr:`~tos_runtime.venue._venue_policy_loader.LoadedVenuePolicy.null_shape_bounds`.

``OrderConstructionPolicy`` is issued with ``signer_identity``/
``approval_identity``/``evidence_package_ref`` all ``None`` — DELIBERATE, not
a gap: the kernel's own ``construct_candidate_command`` issues its own
``OrderConstructionPolicy`` from the SAME three coordinates
(``policy_id``/``policy_generation``/``policy_version``) with those same
three fields ``None`` too, so a loader that filled them would manufacture a
``classify_record_pair`` ``CRITICAL_CONFLICT`` — "same id, different bytes"
(plan §2 decision 6). Filling those three fields for real is deferred to a
kernel signature change (plan §6 decision 4, "커널 라운드 #4 후보").

Firewall (R1, runtime scope): stdlib + ``pyyaml`` + ``tos.*`` only — no
``shared.*``, no ``os.environ``, no ``subprocess``, no
``importlib.import_module`` (``tools/tos_firewall_check.py`` scans tests
too). Nothing here reads ``tos-spec`` (a separate, non-runtime
distribution) — the templates are cited above for a human reader only.
"""

from __future__ import annotations

from tos_runtime.venue._order_construction_policy_loader import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    LoadedOrderConstructionPolicy,
    load_order_construction_policy,
)
from tos_runtime.venue._policy_primitives import VenuePolicyConfigError
from tos_runtime.venue._venue_policy_loader import (
    VENUE_POLICY_CONFIG_NAME,
    LoadedVenuePolicy,
    VenuePolicyScope,
    load_venue_constraint_policy,
)

__all__ = [
    "VENUE_POLICY_CONFIG_NAME",
    "ORDER_CONSTRUCTION_POLICY_CONFIG_NAME",
    "VenuePolicyConfigError",
    "VenuePolicyScope",
    "LoadedVenuePolicy",
    "load_venue_constraint_policy",
    "LoadedOrderConstructionPolicy",
    "load_order_construction_policy",
]
