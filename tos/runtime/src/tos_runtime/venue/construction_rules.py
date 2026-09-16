"""The typed Order Construction rules an OCP document declares — the (a′) wave's contract.

**Types only. No loader, no issuer, no logic** — this module lands first so the wave's lanes can
be authored in parallel against one committed shape: lane A fills these from the OCP document,
lane B builds the :class:`~tos.egressgw.ProposedConstructionEnvelope` out of them, lane C sources
the order shape's non-derived fields from them, and lane D wires the result.

**What the wave is.** ``SizingBound``'s own docstring names the owner outright — "RFC-002
§9.1:553 makes Order Construction Policy governance the supplier of construction rules" — and
seals the bypass structurally: "an author cannot hand the constructor a quantity, because no
quantity field exists". The supplier is named, but there is no supply path: the OCP instance
(``config/tos_runtime/paper/order_construction_policy.yaml``) states its rules as **prose
strings** (``direction_side_and_position_effect_rules``, ``price_tick_lot_quantity_and_rounding
_rules``) and its ``_runtime`` block carries only ``canonicalization_version``/``wire_codec``.
So the runtime declares, per attempt, what the governance document already declares in prose.

This module is the shape that closes that gap. Nothing here is a new authority: every field is
something the OCP document already asserts, made machine-readable.

**The asymmetry this wave also closes.** The kernel designates ``DERIVED_AXES = {QUANTITY,
PRICE, UNIT}`` (``egressgw/records.py:267-269``) as derivation-owned and **refuses** an envelope
that re-declares one — ``_no_derived_axis_is_pre_declared``, citing ADR-002-020 §10:284's
"ambiguity is denial". Yet ``construct_candidate_command`` (``construction.py:609-611``) puts the
derived quantity onto the intent and the command via ``_derived_axis_bindings``, while
``OrderShapeFields.quantity`` — the quantity the venue gate actually checks — stays a
caller-declared literal that nothing reconciles against it (``tos/src/tos/venue/predicates.py``
references ``candidate_command`` zero times; ``order_shape_admissible`` does not even take that
parameter). One attempt therefore carries **two quantities**. :attr:`ConstructionRules
.action_class_shape` and the wave's shape sourcing exist so the declared one stops existing.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` only. No
``shared.*`` (rule (h)), no I/O — the loader that reads the document is lane A's, not this file's.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.egressgw import EffectDimensionSpec, SizingBound
from tos.ioc import AxisBinding
from tos.venue import ActionClass

__all__ = [
    "ActionClassShape",
    "ConstructionRules",
]


@dataclass(frozen=True)
class ActionClassShape:
    """The side / position-effect / direction one ``ActionClass`` maps to.

    The OCP instance already states this mapping, in prose:

        ``direction_side_and_position_effect_rules:``
        ``  - "long/short symmetric: NEW_LONG↔BUY/OPEN, NEW_SHORT↔SELL/OPEN, CLOSE↔opposite
        side/CLOSE"``

    Making it machine-readable is the whole of this type. It adds no rule the document does not
    already carry, which is why the wave treats a mismatch between this mapping and that prose as
    a document defect rather than a code choice.

    ⚠ **Long/short symmetry is a repo non-negotiable** (``CLAUDE.md``: "Futures must preserve
    long/short symmetry. Entry/exit direction follows ``signal_direction``"). A mapping that
    admits ``NEW_LONG`` but not its ``NEW_SHORT`` mirror is a policy error, not a narrower scope,
    and the lane that loads this is expected to refuse rather than silently support one side.

    Attributes:
        side: The outbound side token (e.g. ``"BUY"``/``"SELL"``) — the value that reaches
            ``OrderShapeFields.side`` and the ``SIDE`` axis binding.
        position_effect: ``"OPEN"``/``"CLOSE"`` — reaches ``OrderShapeFields.position_effect``.
        direction: The ``DIRECTION`` axis value (e.g. ``"LONG"``/``"SHORT"``). Distinct from
            ``side``: a CLOSE of a long is ``SELL`` on a ``LONG`` direction, and collapsing the
            two would lose exactly the symmetry the non-negotiable protects.
    """

    side: str
    position_effect: str
    direction: str


@dataclass(frozen=True)
class ConstructionRules:
    """The machine-readable construction rules one OCP generation declares.

    Produced by lane A's loader from the document's ``_runtime.construction`` block; consumed by
    lane B (envelope issuance) and lane C (order-shape sourcing). Every field is fail-closed at
    its consumer: this type carries no defaults and no "absent means permissive" member, because
    an unstated construction rule is a denial at ``derive_order_size``, never a fallback
    (``construction.py``'s denial list, rules 1/2/5).

    Attributes:
        sizing_bound: The governance-supplied bound the derivation consumes. The operator-adopted
            paper values (proposal table, 2026-09-16) are ``max_quantity=1`` — derived from the
            already-approved ``aggregate_risk_policy`` effective limit, so it introduces no new
            judgement — ``lot_rounding=EXACT_MULTIPLE_REQUIRED``, the only kernel member matching
            the OCP's own "no silent rounding" prose, and ``risk_budget``/``per_unit_risk`` as a
            **structural encoding** of "exactly one contract" (ratio 1), explicitly **not** an
            economic calibration. ``max_notional`` stays ``None``: it is an optional ceiling
            (``construction.py:525`` guards it with ``is not None``) and no approved notional
            source exists, so the binding constraint is the contract count.
        admitted_quantity_bases: The closed set of ``Proposal.quantity_basis`` tokens this
            generation authorizes. **An empty set authorizes nothing** — ∅ is fail-closed both
            ways, and a vacuous "every basis is fine" is not authorization (``SizingBound``'s own
            docstring). Operator decision 2026-09-16: the paper instance leaves this
            operator-fill until the deployed strategy file's own ``quantity_basis`` is settled,
            so the paper policy does not boot until then — the same state
            ``scope.accounts``/``scope.instruments`` are already in, not a new block.
        authorized_axes: The non-derived axis bindings the envelope authorizes — account,
            instrument, direction, side, order type, TIF, environment. **Never** a member of
            ``DERIVED_AXES``: declaring one here is refused by the kernel envelope validator, and
            the lane that assembles these is expected to fail loudly rather than filter silently.
        action_class_shape: ``ActionClass`` → :class:`ActionClassShape`. A class absent from this
            mapping is unauthorized for this generation, not defaulted.
        effect_dimensions: The per-dimension Economic Effect Envelope specs. An empty tuple means
            nothing is derived, which reaches the step-5 adapter as ``UNKNOWN`` — "an empty
            vector is not no effect".
    """

    sizing_bound: SizingBound
    admitted_quantity_bases: frozenset[str]
    authorized_axes: tuple[AxisBinding, ...]
    action_class_shape: dict[ActionClass, ActionClassShape]
    effect_dimensions: tuple[EffectDimensionSpec, ...]
