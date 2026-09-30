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
    """The side / position-effect one ``(ActionClass, direction)`` pair maps to.

    The OCP instance already states this mapping, in prose:

        ``direction_side_and_position_effect_rules:``
        ``  - "long/short symmetric: NEW_LONG↔BUY/OPEN, NEW_SHORT↔SELL/OPEN, CLOSE↔opposite
        side/CLOSE"``

    Making it machine-readable is the whole of this type. It adds no rule the document does not
    already carry, which is why the wave treats a mismatch between this mapping and that prose as
    a document defect rather than a code choice.

    ⚠ **Direction is the key, not a field** (amended 2026-09-16, lane A finding). The first cut
    of this type carried ``direction`` as a third *attribute*, which made the mapping
    ``ActionClass → shape`` — one triple per class. That could not express the document's own
    ``CLOSE↔opposite side/CLOSE`` rule: ``ActionClass`` has a single ``CLOSE`` member (no
    ``CLOSE_LONG``/``CLOSE_SHORT`` split, ``tos/src/tos/venue/vocabulary.py:141``), so closing a
    long (sell) and closing a short (buy) collapse onto one key and **one arm has to be invented**.
    Lane A hit exactly that and refused to invent it. Keying by ``(ActionClass, direction)``
    instead makes both arms declarable, and makes the long/short symmetry check something the
    loader can actually enforce — an action class present for one direction and absent for its
    mirror is a refusal, not a narrower scope.

    That is also the direction of travel. ``Proposal.direction`` already exists in the kernel
    (``tos/src/tos/dsl/proposal.py:126``) and ``build_flat_proposal`` takes the direction of a
    closing action as an explicit argument (``proposal.py:251``) — direction is **per-attempt
    strategy content**, not a policy output. The runtime has no proposal path yet (zero
    ``DIRECTION`` sources under ``tos_runtime/src`` as of this wave), so for now the direction
    comes from the policy's own ``DIRECTION`` axis binding in :attr:`ConstructionRules
    .authorized_axes` — a per-composition fact. When the proposal path lands, direction becomes a
    per-attempt lookup key and **this mapping is unchanged**; had it stayed an output attribute it
    would have had to be deleted.

    ⚠ **Long/short symmetry is a repo non-negotiable** (``CLAUDE.md``: "Futures must preserve
    long/short symmetry. Entry/exit direction follows ``signal_direction``"). A mapping that
    admits one direction of an action class but not its mirror is a policy error, and the loader
    is expected to refuse rather than silently support one side.

    Attributes:
        side: The outbound side token — the value that reaches ``OrderShapeFields.side`` and the
            ``SIDE`` axis binding. Carried by the policy document, never authored here: note that
            ``tos/runtime/tests/test_no_side_literals.py`` pins **zero quoted side literals**
            anywhere under ``tos_runtime/src`` outside the KIS mock wire codec, and that pin has a
            deliberately empty carve-out list. It scans docstrings too — spelling the two tokens
            in quotes *in this very docstring* is what broke it at the contract commit. Do not
            re-add them; the point of the type is that the spelling lives in the document.
        position_effect: The position effect this pair opens or closes — reaches
            ``OrderShapeFields.position_effect``.
    """

    side: str
    position_effect: str


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
        action_class_shape: ``(ActionClass, direction)`` → :class:`ActionClassShape`. A pair
            absent from this mapping is unauthorized for this generation, not defaulted — and a
            class present for one direction but missing its mirror is a symmetry refusal, not a
            narrower scope. See :class:`ActionClassShape` for why direction is the key.
        effect_dimensions: The per-dimension Economic Effect Envelope specs. An empty tuple means
            nothing is derived, which reaches the step-5 adapter as ``UNKNOWN`` — "an empty
            vector is not no effect".
    """

    sizing_bound: SizingBound
    admitted_quantity_bases: frozenset[str]
    authorized_axes: tuple[AxisBinding, ...]
    action_class_shape: dict[tuple[ActionClass, str], ActionClassShape]
    effect_dimensions: tuple[EffectDimensionSpec, ...]
