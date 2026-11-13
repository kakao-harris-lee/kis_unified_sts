"""Shared valid-artifact builders + strategies for the posttrade property tests (§7)."""

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


FINITE_NON_NEGATIVE = st.decimals(
    min_value=Decimal("0"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

FINITE_POSITIVE = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

FINITE_NEGATIVE = st.decimals(
    min_value=Decimal("-1000"),
    max_value=Decimal("-0.01"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)

MAGNITUDE_SLOT = st.one_of(st.none(), FINITE_NEGATIVE, FINITE_NON_NEGATIVE)

FINALITY_DIMENSIONS = st.sampled_from(list(FinalityDimensionKind))

LEG_DIRECTIONS = st.sampled_from(list(ObligationLegDirection))

LEG_DIRECTION_SETS = st.frozensets(LEG_DIRECTIONS, min_size=0, max_size=8)


def proof_map_only(
    dimension: FinalityDimensionKind,
) -> dict[FinalityDimensionKind, bool]:
    """A proof map in which exactly one dimension is proven and the other nine are not."""
    return {member: member is dimension for member in FinalityDimensionKind}


PROOF_MAPS = st.dictionaries(
    FINALITY_DIMENSIONS,
    st.sampled_from([True, False, None]),
    min_size=0,
    max_size=10,
)


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
    """A fully specified six-component :class:`ObligationLegScope`."""
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
    """An ISSUED :class:`EconomicObligationRecord` with every required covered field concrete."""
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[EconomicObligationRecord])
    content.update(overrides)
    record = EconomicObligationRecord.issue(scheme=SCHEME, **content)
    assert isinstance(record, EconomicObligationRecord)
    return record


def clean_finality_proof(**overrides: Any) -> PostTradeFinalityProof:
    """An ISSUED :class:`PostTradeFinalityProof` that satisfies the §5.7 conjunction."""
    content: dict[str, Any] = dict(CLEAN_ISSUE_CONTENT[PostTradeFinalityProof])
    content.update(overrides)
    proof = PostTradeFinalityProof.issue(scheme=SCHEME, **content)
    assert isinstance(proof, PostTradeFinalityProof)
    return proof
