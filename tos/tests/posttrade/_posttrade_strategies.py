"""Shared valid-artifact builders + strategies for the posttrade property tests (§7).

Firewall-clean: imports only ``hypothesis`` and ``tos.*`` (design #24 §0.3). The builders
enforce the §7 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture must be
*genuinely* admissible, never a permissive shortcut):

* a **clean** :class:`~tos.posttrade.EconomicObligationRecord` fills every
  ``_REQUIRED_COVERED`` path with a concrete value (never the reserved ``"TBD"``
  placeholder) and carries an all-false consequence block;
* a **clean** :class:`~tos.posttrade.PostTradeFinalityProof` carries a **fully specified**
  six-component scope whose finality class equals the proof's, a present amount, a bound
  generation, and a non-empty ``does_not_prove``;
* the **∅ strategies** deliberately generate empty required-leg sets, empty coverage sets,
  empty dependency sets, empty allocation sequences, and empty proof maps so the ∅-void
  guards are actually exercised (the #10 lesson — a strategy that never emits an empty set
  leaves the ∅ branch untested);
* the **forgery strategies** deliberately generate **both** truthy and **falsy** non-``bool``
  values (``1`` / ``0`` / ``""`` / ``"yes"`` / ``[]`` / ``[1]``), raw member strings, ``None``,
  and nonsense tokens (the #16 lesson — a strategy that only samples safe enum members cannot
  catch a fall-through gate; the falsy axis additionally catches a guard that leans on
  truthiness instead of ``is True``).

Every magnitude is an explicit fixture value: nothing here is a *policy* number — the real
post-trade timing, age, and currentness bounds are Verification-Profile injected and are
**all null (and ``owner: TBD``) in Phase 1** (design #24 §8.1, all 19 keys). No concrete
broker, clearing house, custodian, or bank is named anywhere.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import hypothesis.strategies as st
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.posttrade import (
    EconomicObligationRecord,
    FinalityDimensionKind,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeFinalityProof,
    PostTradeObligationLifecycleState,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

# ---------------------------------------------------------------------------
# Scalar strategies
# ---------------------------------------------------------------------------

#: A finite non-negative magnitude (NaN / infinity are unconstructable, §3.1).
FINITE_NON_NEGATIVE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A finite **positive** magnitude (strictly above the structural zero).
FINITE_POSITIVE = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A finite **negative** magnitude — a sign error on the gross obligation / collateral axes.
FINITE_NEGATIVE = st.decimals(
    min_value=Decimal("-1000"),
    max_value=Decimal("-0.01"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

#: A magnitude slot that may be absent (``None`` = UNKNOWN), negative, or non-negative —
#: the three cases every structural derivation must discriminate.
MAGNITUDE_SLOT = st.one_of(st.none(), FINITE_NEGATIVE, FINITE_NON_NEGATIVE)

#: The ten orthogonal finality dimensions.
FINALITY_DIMENSIONS = st.sampled_from(list(FinalityDimensionKind))

#: The eight obligation leg directions.
LEG_DIRECTIONS = st.sampled_from(list(ObligationLegDirection))

#: Leg-direction subsets **including the empty set** (∅ must be reachable — it is the
#: structural guard of ``obligation_leg_set_complete``).
LEG_DIRECTION_SETS = st.frozensets(LEG_DIRECTIONS, min_size=0, max_size=8)

# ---------------------------------------------------------------------------
# Per-dimension finality proof maps
# ---------------------------------------------------------------------------


def proof_map_only(
    dimension: FinalityDimensionKind,
) -> dict[FinalityDimensionKind, bool]:
    """A proof map in which exactly one dimension is proven and the other nine are not.

    The FQP non-implication fixture: ``proof_map_only(ORDER_FQP)`` is the state ADR §12 line
    340-345 describes — a final quantity proof and nothing else.

    Args:
        dimension: The single proven dimension.

    Returns:
        A ten-entry map with ``True`` on ``dimension`` and ``False`` elsewhere.
    """
    return {member: member is dimension for member in FinalityDimensionKind}


#: Proof maps over the ten dimensions with ``True`` / ``False`` / ``None`` entries, **plus**
#: the empty map (the ∅ guard of both ``finality_dimensions_orthogonal`` and
#: ``event_state_not_obligation_finality``).
PROOF_MAPS = st.dictionaries(
    FINALITY_DIMENSIONS,
    st.sampled_from([True, False, None]),
    min_size=0,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Clean artifact builders
# ---------------------------------------------------------------------------

#: The **single source of truth** for a genuinely complete issue-content dict per digest-bound
#: citizen. Every ``clean_*`` builder copies its entry, and the review MINOR-2 canary in
#: ``test_posttrade_records`` knocks one required field out of the *same* dict at a time — so
#: a builder and the canary can never disagree about what "complete" means.
CLEAN_ISSUE_CONTENT: dict[type, dict[str, Any]] = {
    EconomicObligationRecord: {
        "obligation_id": "OBL-1",
        "obligation_type": "SETTLEMENT_LEG",
        "obligation_version": "V1",
        "obligation_generation": 1,
        "idempotency_key": "IDEM-1",
        "lifecycle_state": PostTradeObligationLifecycleState.DUE,
        "account_scope": "ACCOUNT-A",
        "currency": "CUR-A",
    },
    PostTradeFinalityProof: {
        "proof_id": "PRF-1",
        "obligation_ref": "OBL-1",
        "obligation_version": "V1",
        "leg_scope": ObligationLegScope(
            leg=ObligationLegDirection.DEBIT,
            account="ACCOUNT-A",
            currency="CUR-A",
            value_date="VD-1",
            source_revision="REV-1",
            finality_class=FinalityDimensionKind.SETTLEMENT,
        ),
        "amount": Decimal("10.00"),
        "finality_class": FinalityDimensionKind.SETTLEMENT,
        "bound_generation": 1,
        "does_not_prove": ("CASH_AVAILABILITY", "CUSTODY_TITLE"),
        "proof_recipe_id": "RECIPE-1",
        "source_revision": "REV-1",
        "idempotency_key": "IDEM-P1",
    },
}


def clean_scope(**overrides: Any) -> ObligationLegScope:
    """A fully specified six-component :class:`ObligationLegScope`.

    Args:
        **overrides: Field overrides (used to build the *illegal* under-specified and
            cross-leg variants).

    Returns:
        The scope value model.
    """
    fields: dict[str, Any] = {
        "leg": ObligationLegDirection.DEBIT,
        "account": "ACCOUNT-A",
        "currency": "CUR-A",
        "value_date": "VD-1",
        "source_revision": "REV-1",
        "finality_class": FinalityDimensionKind.SETTLEMENT,
    }
    fields.update(overrides)
    return ObligationLegScope(**fields)


def clean_obligation_record(**overrides: Any) -> EconomicObligationRecord:
    """An ISSUED :class:`EconomicObligationRecord` with every required covered field concrete.

    Args:
        **overrides: Covered-content overrides (an override that changes covered content
            changes the digest, which is exactly how the forgery fixtures are built).

    Returns:
        The issued, digest-verified obligation record.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[EconomicObligationRecord])
    content.update(overrides)
    record = EconomicObligationRecord.issue(scheme=SCHEME, **content)
    assert isinstance(record, EconomicObligationRecord)
    return record


def clean_finality_proof(**overrides: Any) -> PostTradeFinalityProof:
    """An ISSUED :class:`PostTradeFinalityProof` that satisfies the §5.7 conjunction.

    Args:
        **overrides: Covered-content overrides.

    Returns:
        The issued, digest-verified finality proof.
    """
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[PostTradeFinalityProof])
    content.update(overrides)
    proof = PostTradeFinalityProof.issue(scheme=SCHEME, **content)
    assert isinstance(proof, PostTradeFinalityProof)
    return proof
