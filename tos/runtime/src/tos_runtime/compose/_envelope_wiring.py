"""``tos_runtime.compose._envelope_wiring`` — builds step 2's
:class:`~tos.egressgw.ProposedConstructionEnvelope` from the governed Order Construction
Policy's own :class:`~tos_runtime.venue.construction_rules.ConstructionRules`, and derives the
identity values :func:`~tos_runtime.compose._wiring._build_construction_stages` hands to
:class:`~tos.egressgw.OrderConstructionStage` / :class:`~tos.egressgw.ConformanceProofStage`
((a′) wave, lane B; ``docs/plans/2026-09-16-tos-aprime-envelope-order-shape-plan.md``).

**The gap this module closes.** Before this wave, ``_build_construction_stages`` built the
envelope from an **injected** ``construction.envelope`` — a ``ConstructionConfig`` field a test
fixture hands the runtime, which is the very authorization the runtime is supposed to derive
from the governed OCP document — and stamped five identity values plus ``proof_id`` as literals
or f-strings of ``account``/``instrument`` alone. ``generation=1`` in particular was a bare
constant: any generation-fencing predicate downstream (ADR-002-020 §5.7's own "Construction
Generation, monotonic") was vacuous against it, because it never varied across OCP generations.

**Envelope construction (:func:`build_construction_envelope`).** Lane A's loader parses the OCP
document's ``_runtime.construction`` block into a :class:`~tos_runtime.venue.construction_rules
.ConstructionRules` — ``sizing_bound``/``authorized_axes``/``effect_dimensions`` map onto
:class:`~tos.egressgw.ProposedConstructionEnvelope`'s own three non-identity fields almost 1:1.
``envelope_generation``/``policy_binding_id`` come from the OCP's own identity, never a second
injected field.

⚠ **``sizing_bound.quantity_unit`` comes from the Venue Constraint Policy, never from the
OCP — the single most load-bearing decision in this module.** ``derive_order_size``
(``egressgw/construction.py:440``) denies when ``bound.quantity_unit is None``, and denies
again (``:456``) when ``venue_constraint.quantity_unit is not bound.quantity_unit``. Lane A's
``_parse_sizing`` deliberately leaves ``quantity_unit=None`` on the ``SizingBound`` it
produces — a consumer assembling the final envelope is expected to fill it from the venue, not
invent one here. Declaring the same unit in two governed YAML documents with nothing pinning
them would let the two drift apart silently (the "registry + unpinned satellite" defect class
this repo has hit four times already); sourcing it from
:attr:`~tos_runtime.venue.VenueConstraintService.quantity_constraint` — the SAME object
``derive_order_size`` compares against — satisfies the ``:456`` check **by construction**.

**Two boot-time cross-checks, both siblings of ``_riskstate_wiring._cross_check_side_tokens``
(same subset-and-refuse shape, same ``RiskPolicyScopeMismatch``), not a new mechanism:**

1. **Sides** (:func:`~tos_runtime.compose._riskstate_wiring._cross_check_ocp_side_tokens`).
   ``(b′)`` already cross-checks the Action Flow Policy's own ``side_tokens`` against the venue
   policy's ``allowed_sides``. The OCP's own ``action_class_shape`` makes a THIRD declarant of
   the same side-token fact; every side it yields must be a member of the venue's
   ``allowed_sides``, or boot refuses naming the offenders.
2. **Sizing** (:func:`~tos_runtime.compose._riskstate_wiring._cross_check_ocp_sizing_bound`).
   The OCP document's own comment says its ``max_quantity``/``min_quantity``/``lot_size`` are
   DERIVED from the venue policy's — another unpinned fact. The check is a SUBSET direction
   only (OCP not wider than the venue), never equality; see that function's own docstring.

**The SIDE axis binding is DERIVED here, never authored in the OCP document.** Lane A's own
``_build_authorized_axes`` docstring flags this gap by name: ``SIDE`` is one of the seven axes
:class:`~tos_runtime.venue.construction_rules.ConstructionRules`'s own docstring names, but
declaring it under ``_runtime.construction.axes`` would put the same fact ``action_class_shape``
already carries in two places with nothing reconciling them — the exact "two quantities"
duplication this wave exists to remove, applied to side instead of quantity. So
:func:`build_construction_envelope` derives it instead: looks up the composition's fixed
``DIRECTION`` axis binding (already in ``rules.authorized_axes`` — an authored, not derived,
axis; ``TBD`` on the shipped paper instance refuses at LOAD time, before this function ever
runs) and this composition's ``action_class``, and reads
``action_class_shape[(action_class, direction)].side`` — the one source
:class:`ActionClassShape` already is. A missing DIRECTION binding or an ``action_class_shape``
entry with no arm for that ``(action_class, direction)`` pair refuses here rather than building
an envelope with no SIDE axis, exactly the ``construction_generation`` discipline
:func:`build_construction_identities` already follows.

This closes a real gate, not a paper one: ``tos/src/tos/egressgw/gateway.py:1215`` reads
``construction.command.axis_value(ConformanceAxis.SIDE)`` and refuses the send outright when it
is ``None`` — and SIDE is not a :data:`~tos.egressgw.DERIVED_AXES` member, so nothing else ever
puts it on the command. Without this, every attempt was refused at the egress gate. It also
gives an existing kernel check something true to check against for the first time:
``gateway.py:1220`` already requires the injected ``ConstructionConfig.outbound_side`` to equal
the command's own SIDE axis — today that is a bare literal nothing constrains; once SIDE is
policy-derived, that comparison is a real pin, not a tautology against an unconstrained value.

**Identity derivation (:func:`build_construction_identities`).** Every identity is a
deterministic function of real composition facts — the OCP's own ``policy_id``/
``policy_version``/``policy_generation``, its ``construction_generation``, and this
composition's ``account``/``instrument`` — never a bare literal or an f-string that merely
LOOKS derived (a template of ``account``/``instrument`` alone, unchanged across OCP
generations, is exactly what made the prior ``generation=1`` constant vacuous). The digest
reuses :meth:`~tos.canonical.CanonicalizationScheme.compute_digest` — the SAME mechanism
``tos_runtime.compose._request_digest.CapsuleStandInDigest`` already uses — rather than
inventing a second hashing convention.

``generation``/``envelope_generation`` are sourced directly from the OCP's own
``construction_generation`` (ADR-002-020 §5.7's "Construction Generation, monotonic") — not a
digest — so the intent, envelope, and command a single attempt produces all carry one
construction generation. ``intent_version`` is the OCP's own ``policy_version`` string
directly: the real governing version an intent was constructed under, not a second name for it.

**:func:`build_construction_inputs`** bundles both builders into one call, plus the OCP identity
fields the call site needs directly (``policy_id``/``policy_version``/``policy_generation``,
already narrowed to non-``None``) — the one real call site (``_build_construction_stages``)
needs all of it, and ``_wiring.py`` carries a net-zero size-budget ratchet
(``config/tos_size_budget.yaml``), so a single statement there is required, not a style
preference.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.egressgw import ProposedConstructionEnvelope, VenueQuantityConstraint
from tos.ioc import AxisBinding, ConformanceAxis
from tos.venue import ActionClass

from tos_runtime.compose._riskstate_wiring import (
    _cross_check_ocp_side_tokens,
    _cross_check_ocp_sizing_bound,
)
from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.venue import LoadedOrderConstructionPolicy, VenueConstraintService
from tos_runtime.venue.construction_rules import ConstructionRules

__all__ = [
    "ConstructionIdentities",
    "ConstructionInputs",
    "SideDerivationRefused",
    "build_construction_envelope",
    "build_construction_identities",
    "build_construction_inputs",
]


class SideDerivationRefused(RuntimeError):
    """The SIDE axis binding could not be derived from ``rules`` for this composition's
    ``action_class`` (module docstring) — either no ``DIRECTION`` axis binding is present (the
    shipped paper instance ships ``DIRECTION: "TBD"``, which the OCP loader itself already
    refuses at LOAD time; this only fires for some OTHER absence) or ``action_class_shape`` has
    no arm for the resulting ``(action_class, direction)`` pair. Refused, never defaulted — an
    envelope with no SIDE axis would make every attempt refuse later, at the egress gate,
    instead of here at boot with a clear reason."""


def _derive_side_axis_binding(
    rules: ConstructionRules, *, action_class: ActionClass
) -> AxisBinding:
    """The one place SIDE is derived (module docstring) — never authored in the OCP document."""
    direction = next(
        (b.value for b in rules.authorized_axes if b.axis is ConformanceAxis.DIRECTION),
        None,
    )
    if direction is None:
        raise SideDerivationRefused(
            "no DIRECTION axis binding in rules.authorized_axes — cannot derive SIDE for "
            f"action_class {action_class!r} without a direction to key action_class_shape by"
        )
    shape = rules.action_class_shape.get((action_class, direction))
    if shape is None:
        raise SideDerivationRefused(
            f"action_class_shape has no entry for (action_class={action_class!r}, "
            f"direction={direction!r}) — cannot derive a SIDE axis binding for this composition"
        )
    return AxisBinding(axis=ConformanceAxis.SIDE, value=shape.side)


def build_construction_envelope(
    rules: ConstructionRules,
    *,
    loaded_ocp: LoadedOrderConstructionPolicy,
    action_class: ActionClass,
    venue_quantity_constraint: VenueQuantityConstraint,
    venue_allowed_sides: frozenset[str],
) -> ProposedConstructionEnvelope:
    """Build the proposed Authorized Construction Envelope from the OCP's own
    :class:`~tos_runtime.venue.construction_rules.ConstructionRules` (module docstring).

    Args:
        rules: The OCP's machine-readable construction rules
            (:attr:`~tos_runtime.venue.LoadedOrderConstructionPolicy.construction_rules`).
        loaded_ocp: The same loaded OCP ``rules`` came from — supplies the envelope's own
            identity (``envelope_generation``/``policy_binding_id``).
        action_class: This composition's fixed action class
            (:attr:`~tos_runtime.compose._types.ConstructionConfig.action_class`) — keys the
            SIDE derivation below together with ``rules``' own DIRECTION axis binding.
        venue_quantity_constraint: ``VenueConstraintService.quantity_constraint`` — its
            ``quantity_unit`` is stamped onto the envelope's ``sizing_bound`` (module
            docstring's "the single most load-bearing decision"; NEVER read off the OCP, and
            passed through as-is including ``None`` — an absent venue unit is left for
            :func:`~tos.egressgw.construction.derive_order_size` to deny per attempt, the same
            fail-closed-at-consumption discipline the rest of ``SizingBound`` follows), and its
            full bound feeds the sizing cross-check below.
        venue_allowed_sides: The venue policy's own ``VenueShapeConstraints.allowed_sides`` —
            every side ``rules.action_class_shape`` names must be a member.

    Returns:
        The envelope ``OrderConstructionStage`` should be constructed with — its
        ``authorized_axis_bindings`` carries the derived SIDE binding (module docstring)
        alongside ``rules.authorized_axes``.

    Raises:
        tos_runtime.compose._riskstate_wiring.RiskPolicyScopeMismatch: an
            ``action_class_shape`` side is not a member of ``venue_allowed_sides``, or the
            OCP's sizing bound is wider than ``venue_quantity_constraint``.
        SideDerivationRefused: no ``DIRECTION`` axis binding is present in
            ``rules.authorized_axes``, or ``action_class_shape`` has no arm for
            ``(action_class, direction)``.
    """
    ocp_sides = frozenset(shape.side for shape in rules.action_class_shape.values())
    _cross_check_ocp_side_tokens(ocp_sides, venue_allowed_sides=venue_allowed_sides)
    _cross_check_ocp_sizing_bound(
        rules.sizing_bound, venue_quantity_constraint=venue_quantity_constraint
    )
    side_binding = _derive_side_axis_binding(rules, action_class=action_class)
    sizing_bound = rules.sizing_bound.model_copy(
        update={"quantity_unit": venue_quantity_constraint.quantity_unit}
    )
    return ProposedConstructionEnvelope(
        envelope_generation=loaded_ocp.construction_generation,
        policy_binding_id=loaded_ocp.policy.policy_id,
        authorized_axis_bindings=rules.authorized_axes + (side_binding,),
        sizing_bound=sizing_bound,
        effect_dimensions=rules.effect_dimensions,
    )


@dataclass(frozen=True)
class ConstructionIdentities:
    """The six step-2 identity values :func:`build_construction_identities` derives (module
    docstring) — replaces the five ``OrderConstructionStage`` literals plus the
    ``ConformanceProofStage`` ``proof_id`` literal ``_build_construction_stages`` used to author
    itself."""

    intent_id: str
    intent_version: str
    envelope_id: str
    command_id: str
    generation: int
    proof_id: str


def _identity_digest(
    scheme: CanonicalizationScheme,
    *,
    kind: str,
    account: str,
    instrument: str,
    loaded_ocp: LoadedOrderConstructionPolicy,
    construction_generation: int,
) -> str:
    """One identity's digest over the real composition facts that distinguish it: which kind of
    identity (``intent``/``envelope``/``command``/``proof``), the account/instrument this
    composition is fixed to, and the OCP's own identity + generation — so the digest changes
    across OCP generations, unlike the prior bare ``account``/``instrument`` templates (module
    docstring)."""
    ocp = loaded_ocp.policy
    return scheme.compute_digest(
        {
            "kind": kind,
            "account": account,
            "instrument": instrument,
            "policy_id": ocp.policy_id,
            "policy_version": ocp.policy_version,
            "policy_generation": ocp.policy_generation,
            "construction_generation": construction_generation,
        }
    )


def build_construction_identities(
    *,
    account: str,
    instrument: str,
    loaded_ocp: LoadedOrderConstructionPolicy,
    scheme: CanonicalizationScheme,
) -> ConstructionIdentities:
    """Derive the six step-2 identity values from real composition facts (module docstring).

    Args:
        account: This composition's fixed account coordinate.
        instrument: This composition's fixed instrument coordinate.
        loaded_ocp: The loaded OCP — supplies ``policy_id``/``policy_version``/
            ``policy_generation`` (asserted non-``None``, same as the prior call site) and
            ``construction_generation`` (asserted non-``None`` here — an absent construction
            generation is a denial, never a silent fallback to a literal).
        scheme: The injected canonicalization scheme the digest is computed under.

    Returns:
        The six derived identity values.
    """
    ocp = loaded_ocp.policy
    assert ocp.policy_id is not None and ocp.policy_version is not None
    assert ocp.policy_generation is not None
    construction_generation = loaded_ocp.construction_generation
    assert construction_generation is not None, (
        "build_construction_identities: loaded_ocp.construction_generation is None — an "
        "absent Construction Generation is a denial, never a silent generation=1 fallback "
        "(ADR-002-020 §5.7)"
    )

    def _digest(kind: str) -> str:
        return _identity_digest(
            scheme,
            kind=kind,
            account=account,
            instrument=instrument,
            loaded_ocp=loaded_ocp,
            construction_generation=construction_generation,
        )

    return ConstructionIdentities(
        intent_id=f"intent-{_digest('intent')}",
        intent_version=ocp.policy_version,
        envelope_id=f"envelope-{_digest('envelope')}",
        command_id=f"cmd-{_digest('command')}",
        generation=construction_generation,
        proof_id=f"ocp-proof-{_digest('proof')}",
    )


@dataclass(frozen=True)
class ConstructionInputs:
    """Every step-2 input ``_build_construction_stages`` needs from the governed OCP + venue
    (module docstring) — :func:`build_construction_envelope` + :func:`build_construction_identities`'s
    results, plus the OCP's own ``policy_id``/``policy_version``/``policy_generation`` ALREADY
    narrowed to non-``None`` (the ``assert`` that does that lives in
    :func:`build_construction_inputs`, not at the call site — it exists only to satisfy mypy for
    values this is the one place that consumes, so it belongs next to the consumer)."""

    envelope: ProposedConstructionEnvelope
    identities: ConstructionIdentities
    policy_id: str
    policy_version: str
    policy_generation: int


def build_construction_inputs(
    construction: ConstructionConfig,
    *,
    venue_service: VenueConstraintService,
    loaded_ocp: LoadedOrderConstructionPolicy,
    scheme: CanonicalizationScheme,
) -> ConstructionInputs:
    """The one call for the one call site (module docstring): takes the SAME three objects
    ``_build_construction_stages`` already holds rather than their individual fields — the
    call-site compression ``_wiring.py``'s size-budget ratchet requires, not a style
    preference. Unpacks them into :func:`build_construction_envelope`'s and
    :func:`build_construction_identities`'s own narrower, independently-testable signatures
    internally."""
    ocp = loaded_ocp.policy
    # build_venue_service's own loader always fills these (never a real absence here).
    assert ocp.policy_id is not None and ocp.policy_version is not None
    assert ocp.policy_generation is not None
    envelope = build_construction_envelope(
        loaded_ocp.construction_rules,
        loaded_ocp=loaded_ocp,
        action_class=construction.action_class,
        venue_quantity_constraint=venue_service.quantity_constraint,
        venue_allowed_sides=venue_service.shape_constraints.allowed_sides,
    )
    identities = build_construction_identities(
        account=construction.account,
        instrument=construction.instrument,
        loaded_ocp=loaded_ocp,
        scheme=scheme,
    )
    return ConstructionInputs(
        envelope=envelope,
        identities=identities,
        policy_id=ocp.policy_id,
        policy_version=ocp.policy_version,
        policy_generation=ocp.policy_generation,
    )
