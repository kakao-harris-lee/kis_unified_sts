"""Order Construction (design #34 §3) — the G5 quantity / price derivation + the ioc wrapping.

ADR-002-002 §11.1:583 gives step 2 to a deterministic construction of a candidate Canonical
Broker Command "from the exact proposal under a proposed Authorized Construction Envelope", and
RFC-002 §9.1:553 gives the rules to Order Construction Policy governance. The G5 problem this
module answers is that the dsl ``Proposal`` carries **no numeric field at all** — only a
``quantity_basis`` token ("evidence, never capacity", ``dsl/proposal.py:74-76``) — while ioc
``compile_command`` **verifies** rather than derives (``ioc/records.py:14`` "Every multiplier /
price scale / quantity / limit is an **injected** value"). The step that renders an abstract
basis into a concrete size was therefore unowned; design #34 §3.1 gives it to Order Construction
under three rules:

* **deterministic** — the same ``(basis, envelope, price, constraint)`` always produces the same
  canonical command and digest. No wall clock, no RNG, no ambient state (IOC-INV-002).
* **bounded** — the sizing bound is *enclosed in the proposed Authorized Construction Envelope*
  (design #34 §3.1 MINOR-3), so there is no path by which an author supplies a quantity: the
  only producer of a size is :func:`derive_order_size` reading governance-supplied bounds.
* **no repair** — RFC-005 §7:211-213 / §12:356 item 3: "SHALL NOT invent, default, normalize,
  round, or repair any broker-command field". An unknown input is a denial, not a default; a
  result outside the envelope is a denial, not a clamp; and the only admissible rounding is the
  **authored, explicit** :class:`~tos.egressgw.vocabulary.LotRoundingPolicy` — the structural
  opposite of the silent ``"01"`` fallback the existing ``shared/execution/executor.py:785-795``
  performs (Q-MIC-3; design #34 §13).

The three-way division of labour (design #34 §3.1, reconciling RFC-002 §10.2:617): the **Decision
Service identifies the abstract quantity intent** (the basis), **Order Construction renders it
deterministically**, and **step 4 Independent Approval validates that candidate exact-unchanged**
(ADR-002-002 §11.1:585). This module owns only the middle third, and its records carry the
all-false RFC-002 §9.1:553 authority block (design #34 §3.3).

⚠ **provisional** (design #34 §3.1): the *values* are not approved — the price value surface is
D-E2's, and the sizing bound (:class:`~tos.egressgw.records.SizingBound` — ``risk_budget``,
``per_unit_risk``, ``lot_size``, ``min_quantity``/``max_quantity``, ``max_notional``) is **not a
VERIFICATION-PROFILE-002 key at all**: none of those field names is in the profile's bounds/limits
census, so this is not a P0-1 (Phase-0 bounds approval) gap. Governance of these
values belongs to Order Construction Policy (RFC-002 §9.1:553), a separate, still-unratified
artifact — so a slice run wires provisional numbers and closes no EV. What is confirmed now is
the **seam**: what may flow, what is forbidden, and which artifact encloses the bound.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from tos.canonical import CanonicalizationScheme
from tos.dsl import FLAT_QUANTITY_BASIS, ContextValue, ContextValueView
from tos.egressgw._base import ArtifactIntegrityError
from tos.egressgw.records import (
    AdmittedPriceObservation,
    CandidateConstruction,
    EffectDimensionSpec,
    ProposedConstructionEnvelope,
    QuantityDerivation,
    SizingBound,
    VenueQuantityConstraint,
    positive_decimal,
)
from tos.egressgw.vocabulary import (
    DerivationOutcome,
    EffectBasis,
    LotRoundingPolicy,
)
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    CommitmentStep,
    StageAuthorityClass,
    StageOutcome,
    StageRequest,
    StageVerdict,
    conformance_proof_verdict,
    economic_effect_envelope_verdict,
    venue_admissibility_verdict,
)
from tos.ioc import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    ConformanceAxis,
    ConformanceResult,
    EconomicEffectEnvelope,
    OrderConformanceProof,
    OrderConstructionPolicy,
    command_conforms,
    compile_command,
    mutation_fence_holds,
    no_silent_widening,
    numerical_safety,
)
from tos.rcl import CapacityComponent
from tos.venue import (
    ActionClass,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
    order_shape_admissible,
    session_phase_admits,
)

__all__ = [
    "ConformanceProofStage",
    "EconomicEffectStage",
    "OrderConstructionStage",
    "VenueConstraintStage",
    "admitted_price_from_view",
    "admitted_shape_price_from_view",
    "build_order_conformance_proof",
    "candidate_command_verdict",
    "construct_candidate_command",
    "derive_economic_effect_envelope",
    "derive_order_size",
    "fold_venue_admissibility",
]


#: The authored derivation rule, recorded on every derived result so the evidence *names* the
#: computation instead of asserting it. It is a label for
#: ``floor_or_exact_multiple(risk_budget / per_unit_risk, lot_size)`` under the envelope's
#: explicitly authored :class:`~tos.egressgw.vocabulary.LotRoundingPolicy` (design #34 §3.1).
DERIVATION_RULE = "risk_budget / per_unit_risk under the authored lot policy"

#: The flat basis's derivation rule (design #35 §5.2). Recorded instead of
#: :data:`DERIVATION_RULE` on a position-closing derivation, because naming a computation the
#: rule never performed would be exactly the phantom the "name it, do not assert it" discipline
#: exists to prevent: a flat reads no risk budget at all.
_FLAT_DERIVATION_RULE = "observed held position under the authored lot policy"

#: The **pinned** arithmetic context the derivation runs under (adversarial review NIT-1).
#: ``decimal`` arithmetic reads an ambient per-thread context, so a caller that had set a
#: different precision, rounding mode, or trap set would change the derived size — an ambient
#: input the design's determinism claim (IOC-INV-002, design #34 §3.1) does not admit. A fresh
#: :class:`~decimal.Context` (not a copy of the caller's) makes the derivation a pure function of
#: its declared arguments alone; :func:`~decimal.localcontext` restores the caller's on exit.
DERIVATION_CONTEXT: Context = Context(prec=28, rounding=ROUND_HALF_EVEN)

#: The **positive closed set** of decided ioc conformance results. A gate "evaluated" a choice
#: set only when it reached a decidable answer about it; ``UNKNOWN`` means it could not. Written
#: as a positive membership rather than ``is not UNKNOWN`` so it cannot fail open on ``None`` or
#: on a future member (design #34 §7).
_DECIDED_RESULTS: frozenset[ConformanceResult] = frozenset(
    {ConformanceResult.CONFORMANT, ConformanceResult.NON_CONFORMANT}
)


def _denied(reason: str) -> QuantityDerivation:
    """A denied derivation carrying no partially-repaired value (design #34 §3.1)."""
    return QuantityDerivation(outcome=DerivationOutcome.DENIED, denial_reason=reason)


def _exact_admitted_int_value(
    view: ContextValueView, *, field_key: str
) -> tuple[int | None, ContextValue | None]:
    """The single #32 §2.5 exact-integer admission predicate both projections share.

    Returns ``(magnitude, ContextValue)`` when exactly one value carries ``field_key`` and its
    value is an exact ``int``; otherwise ``(None, None)``. This is the sole definition of "an
    exact-integer admitted value", so :func:`admitted_price_from_view` and
    :func:`admitted_shape_price_from_view` cannot drift in what they admit (design #36 §3.2) —
    a future relaxation of the rule reaches both projections or neither.

    ★ the bool≠1 contract (its home moved here from ``admitted_price_from_view``'s docstring when
    the check was shared — design #36 §3.2): ``ScalarValue`` is ``bool | int | float | str``
    (``dsl/vocabulary.py:93``), so a ``bool``-valued :class:`~tos.dsl.ContextValue` is
    **reachable**, not hypothetical, and ``bool`` is an ``int`` subclass in Python. It is refused
    by the **exact** ``type(magnitude) is not int`` check below, never by an ``isinstance`` that
    would silently admit ``True`` as ``1`` (design #32 §2.5 excludes bool from order comparison).
    A fractional magnitude stays fail-closed until the deterministic-float projection rule is
    ratified. This is the exact line the bool canary in ``test_egressgw_construction.py``
    mutates, for both projections.

    Args:
        view: The resolved :class:`~tos.dsl.ContextValueView` for this decision.
        field_key: The governed field key to project (injected, never hardcoded).

    Returns:
        The exact integer magnitude and the :class:`~tos.dsl.ContextValue` it came from, or
        ``(None, None)`` when nothing is admissible under the rule above.
    """
    if not view.values:
        return (None, None)
    matched = [value for value in view.values if value.field_key == field_key]
    if len(matched) != 1:
        # ``ContextValueView`` already rejects duplicate field keys, so the only reachable
        # non-unique case is zero matches; the positive ``== 1`` membership keeps a future
        # relaxation from falling open here.
        return (None, None)
    admitted = matched[0]
    magnitude = admitted.value
    if type(magnitude) is not int:
        return (None, None)
    return (magnitude, admitted)


def admitted_price_from_view(
    view: ContextValueView, *, field_key: str
) -> AdmittedPriceObservation:
    """Project one admitted Critical Input value onto a price observation (design #35 §4.2).

    The gap this closes, stated as slice #1 measured it: the strategy decided on one number (the
    band-crossing close, read off the admitted value surface) and the order was sized against a
    *different* one (an injected provisional scalar), and the only tie between them was a
    ``snapshot_digest`` string the caller supplied. This projection makes the tie a **digest**:
    the value and its own ``ContextValue.payload_digest`` travel together.

    ``ContextValueView`` is D-E2's published surface (``tos.dsl`` carries the type; ``tos.dsl`` is
    already inside this package's runtime closure through ``tos.engine``, and design #34 §0.3 now
    admits it as a direct naming edge — design #35 §0.3/§6-C9).

    **The value ⟺ digest binding is verified at production, not here** (design #32 §2.3 trust
    seam): the D-E2 resolver publishes a view only when the snapshot binding matched exactly, and
    ``ContextValueView`` makes a blank snapshot / view digest and a blank per-value provenance
    pointer structurally unconstructable (``context_value.py:172-200`` / ``:120-140``).
    Re-deriving that here would be an over-claim, so this function consumes the guarantee and
    re-asserts none of it.

    ∅ both ways — the two absences are **different events and are recorded differently**:

    * an **explicit-empty** view (``values == ()``, ``context_value.py:157-158``) resolved and
      admitted nothing, so there is no admitted Critical Input source to attribute at all: the
      observation carries no source and ``derive_order_size`` denies on the source rule;
    * a **populated view that lacks ``field_key``** (or carries a magnitude this projection cannot
      render exactly) does have an admitted surface, just not this value: the observation carries
      the capsule source and the snapshot lineage but **no value**, and the derivation denies with
      "no positive finite value". An unknown price is a no-send, never a last-known default
      (mirroring ``derive_order_size``'s own rule).

    Only an exact integer magnitude is projected, and that rule — including why ``bool`` is
    refused by an exact type check rather than by an ``isinstance`` — lives once in
    :func:`_exact_admitted_int_value`, shared with the venue-shape projection (design #36 §3.2).

    Args:
        view: The resolved :class:`~tos.dsl.ContextValueView` for this decision.
        field_key: The governed field key the sizing policy names as its price (injected, never
            hardcoded — design #35 §4.2 (4)).

    Returns:
        The :class:`~tos.egressgw.records.AdmittedPriceObservation` — carrying the value and its
        per-value provenance digest, or a restrictive observation that denies the send.
    """
    if not view.values:
        return AdmittedPriceObservation()
    lineage = AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE,
        snapshot_digest=view.snapshot_canonical_digest,
    )
    magnitude, admitted = _exact_admitted_int_value(view, field_key=field_key)
    if magnitude is None or admitted is None:
        return lineage
    return AdmittedPriceObservation(
        source=CAPSULE_CONTEXT_SOURCE,
        value=Decimal(magnitude),
        snapshot_digest=view.snapshot_canonical_digest,
        value_payload_digest=admitted.payload_digest,
    )


def admitted_shape_price_from_view(view: ContextValueView, *, field_key: str) -> int | None:
    """Project one admitted Critical Input value onto an integer venue-shape price (design #36 §4).

    :attr:`~tos.venue.OrderShapeFields.price` is ``int`` and D-E2 exposes numeric
    order-comparison values as integer minor / tick units (design #32 §2.5), so this is an exact
    int→int projection — no Decimal round-trip, no rounding, no normalization. Venue's own
    ``order_shape_admissible`` contract forbids permissive rounding, so a projection that
    adjusted a magnitude to fit the grid would manufacture a *new* broker-request shape.

    An absent / non-unique / non-integer value yields ``None``: an unknown shape price is a
    structural ``UNKNOWN`` at ``order_shape_admissible``, never a last-known injected default.
    The exact-int / bool≠1 admission rule lives once in :func:`_exact_admitted_int_value`
    (design #36 §3.2), so this projection cannot drift from the price projection's.

    Unlike :func:`admitted_price_from_view`, the two absences are **not** distinguished here: a
    shape price is a raw ``int`` with no lineage fields to record an explicit-empty view in, and
    venue folds both absences to the same ``UNKNOWN``. Inventing a distinction the consumer
    cannot act on would be the over-claim, not the honesty.

    Args:
        view: The resolved :class:`~tos.dsl.ContextValueView` for this decision.
        field_key: The governed field key the venue shape is priced on (injected, never
            hardcoded — the same key the sizing policy names).

    Returns:
        The exact integer shape price, or ``None`` when the value surface carries none.
    """
    magnitude, _admitted = _exact_admitted_int_value(view, field_key=field_key)
    return magnitude


def derive_order_size(
    *,
    quantity_basis: str | None,
    envelope: ProposedConstructionEnvelope | None,
    price: AdmittedPriceObservation | None,
    venue_constraint: VenueQuantityConstraint | None,
    held_position: Decimal | None = None,
) -> QuantityDerivation:
    """Derive the order size deterministically, bounded, with no repair (design #34 §3.1).

    A **pure ``(proposal-basis, envelope, price, constraint, held position)`` function**. Every
    denial below is a denial *of the send*, never a fallback: RFC-005 §7:211-213 forbids
    inventing, defaulting, normalizing, rounding, or repairing a broker-command field, and
    ADR-002-020 §9:270 makes the compiler's denial total ("must not 'best effort' an unsupported
    field or fall back to a prior mapping").

    **Two raw-size rules, chosen by the basis** (design #35 §5.2). A dsl Explicit Flat carries
    ``quantity_basis == FLAT_QUANTITY_BASIS`` by construction (``dsl/proposal.py:49``; an ACTION
    proposal may not use it and a FLAT proposal must), and its magnitude is *the position being
    closed* — not a risk budget. So:

    * a **flat** basis derives ``raw = held_position``, and reads neither ``risk_budget`` nor
      ``per_unit_risk``. It does not require them either: a pure-close policy that holds no risk
      budget at all sizes an exit correctly, because requiring an input the rule never consumes
      would be a latent denial, not a safety property (design #35 §5.2 MINOR-2);
    * every **other** basis derives ``raw = risk_budget / per_unit_risk`` as before, unchanged.

    Both then pass through the *same* lot / envelope / venue / notional bounds — the seal is
    shared, only the raw magnitude's source differs.

    ⚠ Sizing a flat is **not** capacity admission. The at-most-one exposure retention still denies
    an overlapping effect at the ledger stage (step 8), which runs after this one (step 2); what
    changes is only that the recorded reason for a stop is then the capacity seal rather than the
    sizing rule, and the two are not the same fact (design #35 §5.3). Reduce-only capacity
    semantics — letting a position-reducing order through the seal — wait for the real RCL.

    Denies when — in this order, so the recorded reason names the first missing fact:

    1. the envelope or its enclosed :class:`~tos.egressgw.records.SizingBound` is absent (an
       absent envelope permits no construction, ADR-002-020 §5.3:125);
    2. the ``quantity_basis`` is absent or is **not in** the envelope's closed
       ``admitted_quantity_bases`` set — an ∅ set authorizes nothing (both-ways ∅ discipline);
    3. the price observation is absent, is not sourced from the **capsule** context source, or
       carries no value / snapshot lineage — a market value carried as an authored constant is
       the RFC-008 §10:327-331 relabelling prohibition, and an unknown price is a no-send rather
       than a last-known default (design #34 §3.1 (a));
    4. the basis-specific raw input is missing: for a flat, the ``held_position`` is absent
       (nothing is known to close) or is non-positive (∅ both ways — an explicit zero is
       "nothing to close", a different recorded fact from "no observation at all"); for every
       other basis, the risk budget or per-unit risk is absent or non-positive;
    5. any shared governance bound (lot size, min / max quantity, unit) or the **authored lot
       policy** is absent or non-positive — an unstated lot policy is a denial, never a silent
       round;
    6. the venue / brokercap constraint is absent, or its unit disagrees with the envelope's;
    7. the derived size is not an exact lot multiple under
       :attr:`~tos.egressgw.vocabulary.LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED`;
    8. the derived size is zero, outside the envelope's ``[min_quantity, max_quantity]``, outside
       the venue constraint, or breaches a declared notional ceiling — **denial, not a clamp**
       (ioc ``compile_command``: "outside the authorized envelope — denial").

    Args:
        quantity_basis: The dsl ``Proposal.quantity_basis`` token (a *basis*, not a quantity).
        envelope: The proposed Authorized Construction Envelope enclosing the sizing bound.
        price: The admitted Critical Input price observation.
        venue_constraint: The injected venue / brokercap quantity constraint.
        held_position: The **observed** magnitude of the position a flat closes, read off the
            engine's own reservation projection (design #35 §5.2). It is an observation, never a
            claim: this function neither obtains it nor mutates anything to get it, and no other
            basis consumes it.

    Returns:
        The :class:`~tos.egressgw.records.QuantityDerivation` — ``DERIVED`` with values, or
        ``DENIED`` with a recorded reason and no values at all.
    """
    if envelope is None:
        return _denied(
            "no proposed Authorized Construction Envelope — an absent envelope permits no "
            "construction (ADR-002-020 §5.3:125)"
        )
    bound: SizingBound | None = envelope.sizing_bound
    if bound is None:
        return _denied(
            "the proposed envelope encloses no sizing bound — the derivation's boundedness is "
            "governance-supplied and cannot be sourced elsewhere (design #34 §3.1)"
        )
    if quantity_basis is None or not quantity_basis.strip():
        return _denied("the proposal declares no quantity_basis — nothing to render")
    if not bound.admitted_quantity_bases:
        return _denied(
            "the sizing bound admits no quantity basis — an empty admitted set authorizes "
            "nothing (∅ fail-closed, design #34 §7)"
        )
    if quantity_basis not in bound.admitted_quantity_bases:
        return _denied(
            f"quantity_basis {quantity_basis!r} is not in the envelope's admitted set — a "
            "basis outside the authorized closed set is a silent widening (ADR-002-020 §5.3)"
        )
    if price is None:
        return _denied(
            "no admitted Critical Input price observation — an unknown price is a no-send, "
            "never a last-known default (RFC-005 §7:211; design #34 §3.1 (a))"
        )
    if price.source != CAPSULE_CONTEXT_SOURCE:
        return _denied(
            f"price source {price.source!r} is not the admitted Critical Input source "
            f"{CAPSULE_CONTEXT_SOURCE!r} — a market-derived value carried as an authored "
            "constant is the RFC-008 §10:327-331 relabelling prohibition"
        )
    if not (price.snapshot_digest or "").strip():
        return _denied("the price observation carries no snapshot lineage")
    if not positive_decimal(price.value):
        return _denied("the price observation carries no positive finite value")
    # ★ the basis-specific raw inputs (design #35 §5.2). The risk-budget presence guard sits
    # *inside* the non-flat branch: it is the input of a rule a flat never runs, so demanding it
    # unconditionally would deny a pure-close policy for lacking a number it does not use.
    is_flat = quantity_basis == FLAT_QUANTITY_BASIS
    if is_flat:
        if held_position is None:
            return _denied(
                f"quantity_basis {FLAT_QUANTITY_BASIS!r} closes a position but no held position "
                "was observed — an unknown held position is a no-send, never an assumed size "
                "(design #35 §5.2)"
            )
        if not positive_decimal(held_position):
            return _denied(
                f"the observed held position is {held_position} — there is nothing to close, and "
                f"a zero-size {FLAT_QUANTITY_BASIS!r} order is not a smaller exit, it is no order "
                "(∅ both ways: an explicit zero is not an absent observation)"
            )
    else:
        if not positive_decimal(bound.risk_budget):
            return _denied("the sizing bound declares no positive risk budget")
        if not positive_decimal(bound.per_unit_risk):
            return _denied(
                "the sizing bound declares no positive per-unit risk — a missing per-unit risk "
                "is never assumed to be one"
            )
    if not positive_decimal(bound.lot_size):
        return _denied("the sizing bound declares no positive lot size")
    if bound.lot_rounding is None:
        return _denied(
            "the sizing bound states no lot policy — an unstated rounding policy is a denial, "
            "never a silent round (RFC-005 §7:211; design #34 §3.1)"
        )
    if bound.quantity_unit is None:
        return _denied("the sizing bound declares no quantity unit")
    if bound.min_quantity is None or bound.max_quantity is None:
        return _denied("the sizing bound declares no quantity floor / ceiling")
    if venue_constraint is None:
        return _denied(
            "no venue / broker quantity constraint — a missing constraint is not 'no "
            "constraint' (venue order_shape_admissible UNKNOWN discipline)"
        )
    if (
        not positive_decimal(venue_constraint.lot_size)
        or venue_constraint.min_quantity is None
        or venue_constraint.max_quantity is None
        or venue_constraint.quantity_unit is None
    ):
        return _denied("the venue / broker quantity constraint is incomplete")
    if venue_constraint.quantity_unit is not bound.quantity_unit:
        return _denied(
            f"quantity unit disagreement: envelope {bound.quantity_unit.value} vs venue "
            f"{venue_constraint.quantity_unit.value} — a unit mismatch is prohibited "
            "(ADR-002-020 §11:301)"
        )

    # -- the authored bounded rule -------------------------------------------------------
    assert bound.lot_size is not None  # narrowed by positive_decimal
    lot: Decimal = bound.lot_size
    assert price.value is not None
    # ★ pinned context (NIT-1). Every Decimal operation from here on — the division, the lot
    # floor / remainder, the venue lot remainder, and the notional product — is context-sensitive
    # (a caller's ``prec`` can change the result, or make ``%`` raise ``DivisionImpossible``), so
    # the whole bounded rule *and its bound checks* run under one pinned context rather than the
    # ambient one. Returning from inside the block is safe: ``localcontext`` restores on exit.
    with localcontext(DERIVATION_CONTEXT):
        # ★ structural derivation, not self-report: a flat's magnitude *is* the observed held
        # position, so no risk budget can move it (design #35 §5.2 / §9-5).
        if is_flat:
            assert held_position is not None  # narrowed above
            raw: Decimal = held_position
        else:
            assert bound.risk_budget is not None  # narrowed by positive_decimal
            assert bound.per_unit_risk is not None
            raw = bound.risk_budget / bound.per_unit_risk
        if not raw.is_finite():
            return _denied("the derived raw size is not finite")
        if bound.lot_rounding is LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED:
            if raw % lot != 0:
                return _denied(
                    f"derived size {raw} is not an exact multiple of lot {lot} and the authored "
                    "policy is EXACT_MULTIPLE_REQUIRED — adjusting it would be a repair "
                    "(RFC-005 §7:211)"
                )
            quantity = raw
        else:  # LotRoundingPolicy.FLOOR_TO_LOT — the authored, risk-reducing floor.
            quantity = (raw // lot) * lot

        if not positive_decimal(quantity):
            return _denied(
                f"the authored lot policy yields a non-positive size ({quantity}) — a zero-size "
                "order is not a smaller order, it is no order"
            )
        if quantity < bound.min_quantity or quantity > bound.max_quantity:
            return _denied(
                f"derived size {quantity} is outside the authorized envelope "
                f"[{bound.min_quantity}, {bound.max_quantity}] — denial, never a clamp "
                "(ADR-002-020 §9 'outside the authorized envelope — denial')"
            )
        if (
            quantity < venue_constraint.min_quantity
            or quantity > venue_constraint.max_quantity
            or quantity % venue_constraint.lot_size != 0
        ):
            return _denied(
                f"derived size {quantity} violates the venue / broker quantity constraint — "
                "denial, never a permissive adjustment (ADR-002-019 §12:309)"
            )
        notional = quantity * price.value
        if bound.max_notional is not None and notional > bound.max_notional:
            return _denied(
                f"derived notional {notional} exceeds the authorized ceiling "
                f"{bound.max_notional} — denial, never a reduction"
            )
        # The record is built inside the pinned context too: ``CanonicalDecimal`` normalizes at
        # validation time (``canonical/canonicalization.py`` ``_normalize_decimal``), and
        # ``Decimal.normalize()`` is itself context-sensitive — under an ambient one-digit
        # precision the very same magnitude would be stored as a different value, and therefore
        # digest differently downstream.
        return QuantityDerivation(
            outcome=DerivationOutcome.DERIVED,
            quantity=quantity,
            price=price.value,
            quantity_unit=bound.quantity_unit,
            rule=_FLAT_DERIVATION_RULE if is_flat else DERIVATION_RULE,
        )


def _derived_axis_bindings(derivation: QuantityDerivation) -> tuple[AxisBinding, ...]:
    """The three derivation-owned axis bindings, rendered from the single derivation."""
    assert derivation.quantity is not None
    assert derivation.price is not None
    assert derivation.quantity_unit is not None
    return (
        AxisBinding(axis=ConformanceAxis.QUANTITY, value=str(derivation.quantity)),
        AxisBinding(axis=ConformanceAxis.PRICE, value=str(derivation.price)),
        AxisBinding(axis=ConformanceAxis.UNIT, value=derivation.quantity_unit.value),
    )


def construct_candidate_command(
    *,
    proposal_id: str | None,
    proposal_digest: str | None,
    derivation: QuantityDerivation,
    envelope: ProposedConstructionEnvelope,
    scheme: CanonicalizationScheme,
    intent_id: str,
    intent_version: str,
    envelope_id: str,
    policy_id: str,
    policy_version: str,
    policy_generation: int,
    command_id: str,
    generation: int,
) -> CandidateConstruction:
    """Compile the candidate command from a derived size and seal it with ioc (design #34 §3.2).

    The declare-and-verify seal: the derivation's three axes are rendered **once** and declared
    onto both the :class:`~tos.ioc.ApprovedIntentContract` and the
    :class:`~tos.ioc.AuthorizedConstructionEnvelope`, and ioc ``compile_command`` then enforces
    ``intent == authorized`` for every axis (``ioc/predicates.py:246-256``). ioc derives nothing —
    it verifies — which is exactly why the derivation had to be owned here (design #34 E3).

    A denied derivation short-circuits: no command is compiled at all, so there is no
    partially-constructed artifact for a later stage to consume. An
    :class:`~tos.canonical.ArtifactIntegrityError` from ``compile_command`` (an undetermined or
    out-of-envelope axis) is likewise recorded as a **denial**, never retried with a relaxed
    input.

    Args:
        proposal_id: The exact proposal lineage identity.
        proposal_digest: The exact proposal lineage digest.
        derivation: The :func:`derive_order_size` result.
        envelope: The proposed Authorized Construction Envelope.
        scheme: The injected canonicalization scheme.
        intent_id: The independent Approved Intent Contract identity to assign.
        intent_version: The immutable intent version.
        envelope_id: The independent envelope identity to assign.
        policy_id: The independent Order Construction Policy identity.
        policy_version: The Order Construction Policy version.
        policy_generation: The Order Construction Policy generation.
        command_id: The independent command identity to assign.
        generation: The Construction Generation (monotonic, ADR-002-020 §5.7).

    Returns:
        The :class:`~tos.egressgw.records.CandidateConstruction` bundle.
    """
    if derivation.outcome is not DerivationOutcome.DERIVED:
        return CandidateConstruction(
            derivation=derivation,
            denial_reason=derivation.denial_reason
            or "the quantity derivation was denied",
        )
    bindings = tuple(envelope.authorized_axis_bindings) + _derived_axis_bindings(derivation)
    intent: ApprovedIntentContract | None = None
    ioc_envelope: AuthorizedConstructionEnvelope | None = None
    policy: OrderConstructionPolicy | None = None
    try:
        issued_intent = ApprovedIntentContract.issue(
            scheme=scheme,
            intent_id=intent_id,
            intent_generation=generation,
            intent_version=intent_version,
            proposal_id=proposal_id,
            proposal_digest=proposal_digest,
            authorized_axis_bindings=bindings,
        )
        assert isinstance(issued_intent, ApprovedIntentContract)
        intent = issued_intent
        issued_envelope = AuthorizedConstructionEnvelope.issue(
            scheme=scheme,
            envelope_id=envelope_id,
            envelope_generation=envelope.envelope_generation,
            authorized_axis_bindings=bindings,
            policy_binding_id=envelope.policy_binding_id,
        )
        assert isinstance(issued_envelope, AuthorizedConstructionEnvelope)
        ioc_envelope = issued_envelope
        issued_policy = OrderConstructionPolicy.issue(
            scheme=scheme,
            policy_id=policy_id,
            policy_generation=policy_generation,
            policy_version=policy_version,
        )
        assert isinstance(issued_policy, OrderConstructionPolicy)
        policy = issued_policy
        command = compile_command(
            intent=intent,
            policy=policy,
            envelope=ioc_envelope,
            generation=generation,
            scheme=scheme,
            command_id=command_id,
        )
    except ArtifactIntegrityError as exc:
        return CandidateConstruction(
            derivation=derivation,
            intent=intent,
            envelope=ioc_envelope,
            policy=policy,
            denial_reason=(
                f"ioc construction denied the candidate: {exc} — denial is total, there is "
                "no best-effort recompile (ADR-002-020 §9:270)"
            ),
        )
    conformance = command_conforms(intent, command, policy, ioc_envelope)
    # ★ structural derivation, not self-report: unit consistency is read off the artifacts the
    # derivation already reconciled (envelope unit == venue unit, enforced in derive_order_size),
    # never taken from a caller's claim.
    numerical = numerical_safety(
        [derivation.quantity, derivation.price],
        units_consistent=derivation.quantity_unit is not None,
    )
    # ★ both witnesses are derived from what actually happened: the size passed every envelope
    # and venue bound inside derive_order_size (otherwise it would be DENIED), and both dependent
    # gates reached a *decidable* answer about this exact choice set (an UNKNOWN gate did not
    # evaluate it — IOC-INV-006 "every dependent gate evaluated it").
    widening_ok = no_silent_widening(
        exact_bounded_within_envelope=derivation.outcome is DerivationOutcome.DERIVED,
        every_dependent_gate_evaluated=(
            conformance in _DECIDED_RESULTS and numerical in _DECIDED_RESULTS
        ),
    )
    return CandidateConstruction(
        derivation=derivation,
        intent=intent,
        envelope=ioc_envelope,
        policy=policy,
        command=command,
        conformance_result=conformance,
        numerical_result=numerical,
        no_silent_widening_ok=widening_ok,
    )


def candidate_command_verdict(
    construction: CandidateConstruction | None,
    *,
    step: CommitmentStep = CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
) -> StageVerdict:
    """Wrap a candidate construction as a positive-admit step-2 verdict (design #34 §3.2).

    The thin new adapter D-E1 does not carry (its ``conformance_proof_verdict`` answers step 11,
    not step 2), isomorphic to it: **only** a positively ``CONFORMANT`` command with a
    ``CONFORMANT`` numerical-safety result and a positively ``True`` no-silent-widening witness
    admits. ``None`` and ``UNKNOWN`` are ``UNKNOWN`` — never a pass — and everything else denies.

    Args:
        construction: The step-2 bundle (``None`` ⇒ ``UNKNOWN``).
        step: The commitment step this verdict answers.

    Returns:
        The positive-admit :class:`~tos.engine.StageVerdict`.
    """
    if construction is None:
        return StageVerdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            reason="no candidate construction was produced",
        )
    if construction.command is None or construction.conformance_result is None:
        return StageVerdict(
            step=step,
            outcome=StageOutcome.DENY,
            authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
            native_verdict_type=type(construction).__name__,
            reason=construction.denial_reason
            or "the candidate command was not constructed",
        )
    if (
        construction.conformance_result is ConformanceResult.CONFORMANT
        and construction.numerical_result is ConformanceResult.CONFORMANT
        and construction.no_silent_widening_ok is True
    ):
        outcome = StageOutcome.ADMIT
        reason = None
    elif (
        construction.conformance_result is ConformanceResult.UNKNOWN
        or construction.numerical_result is ConformanceResult.UNKNOWN
    ):
        outcome = StageOutcome.UNKNOWN
        reason = "candidate conformance or numerical safety is UNKNOWN — denial"
    else:
        outcome = StageOutcome.DENY
        reason = "the candidate command is NON_CONFORMANT or silently widened"
    return StageVerdict(
        step=step,
        outcome=outcome,
        authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
        native_verdict_type=type(construction.conformance_result).__name__,
        native_verdict_value=str(construction.conformance_result.value),
        bound_digest=construction.command.canonical_digest,
        bound_identity=construction.command.command_id,
        reason=reason,
    )


def derive_economic_effect_envelope(
    derivation: QuantityDerivation,
    specs: tuple[EffectDimensionSpec, ...] = (),
) -> EconomicEffectEnvelope:
    """Derive the conservative Economic Effect Envelope from the order size (step 5).

    ``EconomicEffectEnvelope`` **is** the rcl :class:`~tos.rcl.CapacityVector` type (the single
    ``ioc -> rcl`` edge), so dominance is sealed at the type level and no reduction reducer is
    authored here. Each declared dimension's magnitude is **computed** from the derived size
    under its injected :class:`~tos.egressgw.vocabulary.EffectBasis` — never self-reported.

    A denied derivation, an empty spec tuple, or a spec with a missing id / basis yields an
    envelope whose affected component carries a ``None`` magnitude (or no component at all), and
    D-E1's ``economic_effect_envelope_verdict`` turns both into ``UNKNOWN``: "an empty vector is
    not no effect" (∅ both-ways, design #34 §7).

    Args:
        derivation: The :func:`derive_order_size` result.
        specs: The injected :class:`~tos.egressgw.records.EffectDimensionSpec` tuple.

    Returns:
        The :class:`~tos.ioc.EconomicEffectEnvelope` (an rcl ``CapacityVector``).
    """
    components: list[CapacityComponent] = []
    quantity = derivation.quantity
    price = derivation.price
    derived = derivation.outcome is DerivationOutcome.DERIVED
    # ★ pinned context (NIT-1): a capacity magnitude may not vary with an ambient decimal
    # context — the envelope rcl commits must be reproducible, and ``CanonicalDecimal``
    # normalizes at validation time, so the component construction is inside the block too.
    with localcontext(DERIVATION_CONTEXT):
        for spec in specs:
            if spec.dimension_id is None:
                continue
            magnitude: Decimal | None = None
            if derived and quantity is not None:
                if spec.basis is EffectBasis.QUANTITY:
                    magnitude = quantity
                elif spec.basis is EffectBasis.NOTIONAL and price is not None:
                    magnitude = quantity * price
            components.append(
                CapacityComponent(
                    dimension_id=spec.dimension_id,
                    magnitude=magnitude,
                    unit=spec.unit,
                    scale=spec.scale,
                )
            )
        return EconomicEffectEnvelope(components=tuple(components))


def build_order_conformance_proof(
    *,
    construction: CandidateConstruction,
    scheme: CanonicalizationScheme,
    proof_id: str,
    proof_generation: int,
    effect_digest: str | None = None,
    venue_admissibility_decision_digest: str | None = None,
    broker_capability_profile_digest: str | None = None,
    required_authority_scope: tuple[str, ...] = (),
) -> OrderConformanceProof | None:
    """Issue the step-11 Order Conformance Proof binding the exact command (design #34 §3.2).

    The proof binds the policy / envelope / command digests by **scalar** (ioc's sibling-edge-0
    discipline) and carries the ioc ``ConformanceResult``. It is issued **only** for a
    constructed candidate: there is no proof of an unconstructed command.

    ``required_authority_scope`` is mandatory and restrictive (ADR-002-020 §14:374): an empty
    scope means ``UNKNOWN`` / ``NON_CONFORMANT`` at the consuming gate, never zero / wildcard /
    unconstrained authority — so it is injected, never defaulted here.

    Args:
        construction: The step-2 bundle.
        scheme: The injected canonicalization scheme.
        proof_id: The independent proof identity to assign.
        proof_generation: The proof generation.
        effect_digest: The Economic Effect Envelope digest (scalar seam).
        venue_admissibility_decision_digest: The venue decision digest (scalar seam).
        broker_capability_profile_digest: The Broker Capability Profile digest (scalar seam).
        required_authority_scope: The mandatory restrictive authority scope.

    Returns:
        The issued proof, or ``None`` when no command was constructed.
    """
    if construction.command is None or construction.envelope is None:
        return None
    proof = OrderConformanceProof.issue(
        scheme=scheme,
        proof_id=proof_id,
        proof_generation=proof_generation,
        policy_digest=None if construction.policy is None else construction.policy.canonical_digest,
        envelope_digest=construction.envelope.canonical_digest,
        command_digest=construction.command.canonical_digest,
        effect_digest=effect_digest,
        venue_admissibility_decision_digest=venue_admissibility_decision_digest,
        broker_capability_profile_digest=broker_capability_profile_digest,
        required_authority_scope=required_authority_scope,
        conformance_result=construction.conformance_result,
    )
    assert isinstance(proof, OrderConformanceProof)
    return proof


def fold_venue_admissibility(
    *,
    observed_session_phase: str | None,
    action_class: ActionClass | None,
    snapshot: VenueConstraintSnapshot | None,
    policy: VenueConstraintPolicy | None,
    shape: OrderShapeFields | None,
    constraints: VenueShapeConstraints | None,
) -> OrderAdmissibilityResult:
    """Fold venue's two shipped predicates into one non-authorizing result (design #34 §3.2).

    The step-3 Venue Constraint Gate "produces a **non-authorizing** decision" (RFC-002
    §9.1:554), so this fold neither authorizes nor overrides: it combines
    ``session_phase_admits`` (§10) and ``order_shape_admissible`` (§12) restrictively —
    **any-restriction-wins**, order-independent:

    * a definite ``INADMISSIBLE`` on either side dominates (a hard reject over an undecidable one);
    * ``RESTRICTED_PROTECTIVE_ONLY`` on either side is carried through unchanged, so D-E1's
      adapter can deny it with its own reason (a protective path proceeds only through venue's
      ``protective_label_no_bypass``, and this gate self-classifies nothing — RFC-005 §12:371);
    * any ``UNKNOWN`` denies;
    * ``ADMISSIBLE`` **only** when both sides are positively ``ADMISSIBLE``.

    Note the division of roles the design draws (§3.2 MINOR-4): this is step 3 *producing* the
    non-authorizing decision, whereas the gateway's verify item 11 *enforces* the exact current
    result at step 15 (RFC-002 §9.1:554). They are the same predicate family, a different act.

    Args:
        observed_session_phase: The authoritatively observed session-phase token.
        action_class: The exact order action class.
        snapshot: The venue constraint snapshot.
        policy: The venue constraint policy.
        shape: The exact order shape.
        constraints: The injected venue shape constraints.

    Returns:
        The folded :class:`~tos.venue.OrderAdmissibilityResult`.
    """
    if action_class is None:
        return OrderAdmissibilityResult.UNKNOWN
    phase = session_phase_admits(observed_session_phase, action_class, snapshot, policy)
    shape_result = order_shape_admissible(shape, constraints)
    results = (phase, shape_result)
    for result in results:
        if result is OrderAdmissibilityResult.INADMISSIBLE:
            return OrderAdmissibilityResult.INADMISSIBLE
    for result in results:
        if result is OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:
            return OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY
    for result in results:
        if result is not OrderAdmissibilityResult.ADMISSIBLE:
            return OrderAdmissibilityResult.UNKNOWN
    return OrderAdmissibilityResult.ADMISSIBLE


# ===========================================================================
# §3.2 — the four injected D-E1 ``Stage`` implementations (steps 2, 3, 5, 11)
# ===========================================================================


class OrderConstructionStage:
    """The step-2 ``Stage``: derive, compile, and seal the candidate command (design #34 §3.2).

    Holds the injected construction inputs (the proposed envelope, the admitted price
    observation, the venue quantity constraint, the identities and the scheme) and reads the
    ``quantity_basis`` from the sequencer's own ``StageRequest.proposal`` — so the *basis* comes
    from the Decision Service and the *size* from governance-supplied bounds, exactly the
    three-way division of labour §3.1 draws.

    The completed :class:`~tos.egressgw.records.CandidateConstruction` is retained on
    :attr:`construction` so the later stages (5, 11) and the gateway's verify item 13 consume the
    **same** artifact rather than recomputing it — recomputation would be a second chance for a
    different answer.
    """

    def __init__(
        self,
        *,
        envelope: ProposedConstructionEnvelope,
        price: AdmittedPriceObservation | None,
        venue_constraint: VenueQuantityConstraint | None,
        scheme: CanonicalizationScheme,
        intent_id: str,
        intent_version: str,
        envelope_id: str,
        policy_id: str,
        policy_version: str,
        policy_generation: int,
        command_id: str,
        generation: int,
        price_field_key: str | None = None,
    ) -> None:
        """Configure the stage with its injected construction inputs.

        ``price_field_key`` names the governed Critical Input field the sizing policy prices
        against (design #35 §4.2 (4)). It is injected — there is no default field name here,
        because guessing one would be a hardcoded market-data assumption. When it is supplied
        **and** the tick carried a value view, the price is projected off that surface and the
        injected ``price`` observation is not consulted; otherwise the injected provisional
        observation is used unchanged (design #35 §4.2 (3)).
        """
        self._envelope = envelope
        self._price = price
        self._price_field_key = price_field_key
        self._venue_constraint = venue_constraint
        self._scheme = scheme
        self._intent_id = intent_id
        self._intent_version = intent_version
        self._envelope_id = envelope_id
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._policy_generation = policy_generation
        self._command_id = command_id
        self._generation = generation
        self.construction: CandidateConstruction | None = None

    @property
    def effect_specs(self) -> tuple[EffectDimensionSpec, ...]:
        """The injected Economic Effect Envelope specs the proposed envelope encloses."""
        return self._envelope.effect_dimensions

    def _price_for(self, request: StageRequest) -> AdmittedPriceObservation | None:
        """The price this construction sizes against (design #35 §4.2 (3)).

        The value surface wins when both a governed ``price_field_key`` and a published view are
        present, because that is the number the decision was actually made on. A tick that carried
        no view is *value-free*, not "no price": the injected provisional observation stands in,
        and it is provisional exactly as it was before this seam existed.
        """
        view = request.value_view
        if self._price_field_key is None or view is None:
            return self._price
        return admitted_price_from_view(view, field_key=self._price_field_key)

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Run the derivation + compile and return the positive-admit step-2 verdict."""
        proposal = request.proposal
        derivation = derive_order_size(
            quantity_basis=getattr(proposal, "quantity_basis", None),
            envelope=self._envelope,
            price=self._price_for(request),
            venue_constraint=self._venue_constraint,
            held_position=request.held_position_magnitude,
        )
        self.construction = construct_candidate_command(
            proposal_id=getattr(proposal, "proposal_id", None),
            proposal_digest=getattr(proposal, "canonical_digest", None),
            derivation=derivation,
            envelope=self._envelope,
            scheme=self._scheme,
            intent_id=self._intent_id,
            intent_version=self._intent_version,
            envelope_id=self._envelope_id,
            policy_id=self._policy_id,
            policy_version=self._policy_version,
            policy_generation=self._policy_generation,
            command_id=self._command_id,
            generation=self._generation,
        )
        return candidate_command_verdict(self.construction, step=request.step)


class VenueConstraintStage:
    """The step-3 ``Stage``: a **non-authorizing thin adapter** over venue (design #34 §3.2).

    RFC-002 §9.1:554 — the Venue Constraint Gate "produces a non-authorizing decision". This
    stage folds venue's own shipped predicates (:func:`fold_venue_admissibility`) and hands the
    native result to D-E1's ``venue_admissibility_verdict``, which applies venue's mandated
    positive gate and denies ``RESTRICTED_PROTECTIVE_ONLY`` with its own reason. No venue logic
    is re-authored here and no admissibility is chosen (RFC-005 §12:368).
    """

    def __init__(
        self,
        *,
        observed_session_phase: str | None,
        action_class: ActionClass | None,
        snapshot: VenueConstraintSnapshot | None,
        policy: VenueConstraintPolicy | None,
        shape: OrderShapeFields | None,
        constraints: VenueShapeConstraints | None,
        decision: OrderAdmissibilityDecision | None = None,
        shape_price_field_key: str | None = None,
    ) -> None:
        """Configure the stage with its injected venue facts.

        ``shape_price_field_key`` names the governed Critical Input field the venue shape is
        priced on (design #36 §3.3). Left ``None``, the injected shape is folded exactly as
        before — the value-surface seam is off.
        """
        self._observed_session_phase = observed_session_phase
        self._action_class = action_class
        self._snapshot = snapshot
        self._policy = policy
        self._shape = shape
        self._constraints = constraints
        self._decision = decision
        self._shape_price_field_key = shape_price_field_key
        #: The shape this stage actually folded, retained so the send-boundary context reads the
        #: *same* object instead of rebuilding a look-alike (design #36 §3.3). ``None`` before
        #: step 3 has run — fail-closed, never a stand-in.
        self.resolved_shape: OrderShapeFields | None = None

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:
        """The injected constraints, exposed so the item-11 context reads the same object the
        step-3 fold used (design #36 §3.3 convergence)."""
        return self._constraints

    def _shape_for(self, request: StageRequest) -> OrderShapeFields | None:
        """The shape this step folds and the item-11 context reuses (design #36 §3.3).

        The value surface wins when both a governed ``shape_price_field_key`` and a published
        view are present — that is the number the decision was actually priced on. A tick that
        carried no view is *value-free*, not "no price": the injected shape stands in unchanged.
        When the field is governed but the value is unprojectable, the price becomes ``None``
        (fail-closed) — an unknown shape price is a structural ``UNKNOWN`` at
        ``order_shape_admissible``, not the stale injected stand-in.

        ⚠ Under the slice's provisional constraints (design #36 §3.4) the injected fallback
        price is itself ``INADMISSIBLE`` — it is off the provisional tick grid — so a value-free
        tick reaching step 3 fails admissibility rather than silently passing. The slice's
        crossing tick always carries a view, so this fallback path is unexercised on the happy
        path; the mutation target in design #36 §9-4 relies on exactly that.
        """
        view = request.value_view
        if self._shape_price_field_key is None or view is None:
            return self._shape
        if self._shape is None:
            return None
        projected = admitted_shape_price_from_view(
            view, field_key=self._shape_price_field_key
        )
        return self._shape.model_copy(update={"price": projected})

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Produce the non-authorizing venue verdict for step 3."""
        resolved_shape = self._shape_for(request)
        self.resolved_shape = resolved_shape
        result = fold_venue_admissibility(
            observed_session_phase=self._observed_session_phase,
            action_class=self._action_class,
            snapshot=self._snapshot,
            policy=self._policy,
            shape=resolved_shape,
            constraints=self._constraints,
        )
        return venue_admissibility_verdict(result, self._decision, step=request.step)


class EconomicEffectStage:
    """The step-5 ``Stage``: derive the conservative Economic Effect Envelope (design #34 §3.2).

    Reuses D-E1's ``economic_effect_envelope_verdict`` verbatim — the ∅-envelope and
    ``None``-magnitude ``UNKNOWN`` rules are already sealed there, so nothing is re-authored.
    """

    def __init__(self, *, construction_stage: OrderConstructionStage) -> None:
        """Configure the stage to read the step-2 stage's completed construction."""
        self._construction_stage = construction_stage
        self.envelope: EconomicEffectEnvelope | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Derive the envelope from the step-2 derivation and wrap it."""
        construction = self._construction_stage.construction
        if construction is None:
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="step 2 produced no construction — nothing to derive an effect from",
            )
        self.envelope = derive_economic_effect_envelope(
            construction.derivation,
            self._construction_stage.effect_specs,
        )
        return economic_effect_envelope_verdict(self.envelope, step=request.step)


class ConformanceProofStage:
    """The step-11 ``Stage``: issue the Order Conformance Proof and fence it (design #34 §3.2).

    Reuses D-E1's ``conformance_proof_verdict`` (``CONFORMANT`` alone admits) and additionally
    requires ioc ``mutation_fence_holds`` — the proof must bind the **exact** command's canonical
    digest, so the fenced pair is provably the same command the proof covered (ADR-002-020
    §6.2 / §15:414). A proof that does not fence its command denies, whatever its result says.
    """

    def __init__(
        self,
        *,
        construction_stage: OrderConstructionStage,
        scheme: CanonicalizationScheme,
        proof_id: str,
        proof_generation: int,
        required_authority_scope: tuple[str, ...],
        effect_digest: str | None = None,
        venue_admissibility_decision_digest: str | None = None,
        broker_capability_profile_digest: str | None = None,
    ) -> None:
        """Configure the stage with its injected proof identities and seam digests.

        ``effect_digest`` is an **injected scalar**: ``EconomicEffectEnvelope`` is the rcl
        ``CapacityVector`` *value* model, not a digest-bound artifact, so a digest for it is a
        seam scalar supplied by the caller rather than something this stage may invent.
        """
        self._construction_stage = construction_stage
        self._effect_digest = effect_digest
        self._scheme = scheme
        self._proof_id = proof_id
        self._proof_generation = proof_generation
        self._required_authority_scope = required_authority_scope
        self._venue_digest = venue_admissibility_decision_digest
        self._profile_digest = broker_capability_profile_digest
        self.proof: OrderConformanceProof | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Issue the proof, apply the mutation fence, and wrap the ioc result."""
        construction = self._construction_stage.construction
        if construction is None or construction.command is None:
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.UNKNOWN,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                reason="no candidate command exists — there is no proof of an unbuilt command",
            )
        self.proof = build_order_conformance_proof(
            construction=construction,
            scheme=self._scheme,
            proof_id=self._proof_id,
            proof_generation=self._proof_generation,
            effect_digest=self._effect_digest,
            venue_admissibility_decision_digest=self._venue_digest,
            broker_capability_profile_digest=self._profile_digest,
            required_authority_scope=self._required_authority_scope,
        )
        if not mutation_fence_holds(construction.command, self.proof):
            return StageVerdict(
                step=request.step,
                outcome=StageOutcome.DENY,
                authority_class=StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
                native_verdict_type=type(self.proof).__name__ if self.proof else None,
                reason=(
                    "the conformance proof does not fence the exact command digest — a "
                    "post-proof mutation is a new command identity and a new proof "
                    "(ADR-002-020 §6.2 / §16:429)"
                ),
            )
        return conformance_proof_verdict(
            construction.conformance_result, self.proof, step=request.step
        )
