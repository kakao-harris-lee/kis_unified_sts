"""Seam: ``tos.posttrade`` <-> ``tos.brokercap`` — the ``+Broker`` premise, discharged by injection.

``+Broker`` sits on **all twelve** PTF-EV rows, which makes this the seam that most needs the
broker-agnostic discipline: this package judges **no** broker, clearing, custodian, or banking
capability and names no institution. Capability is brokercap's (ADR-002-018) and arrives as an
injected verdict.

**Honest disclosure (design #24 §0.4 / §9.2-7).** brokercap has **no** dedicated
``SETTLEMENT`` / ``CUSTODIAN`` / ``STATEMENT_COVERAGE`` capability dimension — measured, not
assumed. The nearest existing dimensions are ``POSITIONS_BALANCES_MARGIN``,
``CORPORATE_ADMINISTRATIVE_EVENTS``, and ``FILL_EVENTS``. Whether to add dedicated dimensions
is a Phase-0 architecture question (ADR §29 Q2/Q5); Phase 1 consumes the existing ones and
exposes the gap rather than papering over it. This test **asserts the absence**, so the day
brokercap grows one, this seam is where the design decision has to be revisited.

Locks **2** of the 19 injected coordinates: ``CapabilityStatus.VERIFIED`` (a token) and
``fqp_adequate`` (a **producer name** — the injected value is a plain ``bool``, so the drift
lock is on the producer's existence and callability). Test-only sibling imports are not
runtime package edges.
"""

from __future__ import annotations

import pytest
import tos.posttrade.predicates as posttrade_predicates
from tos.posttrade import (
    BROKER_FQP_ADEQUACY_PRODUCER,
    CAPABILITY_STATUS_VERIFIED,
    FinalityDimensionKind,
    finality_dimensions_orthogonal,
)

from ._posttrade_strategies import proof_map_only


def test_capability_status_token_drift_lock() -> None:
    """(token 11 of 19) brokercap ``CapabilityStatus.VERIFIED``."""
    from tos.brokercap import CapabilityStatus

    assert CapabilityStatus.VERIFIED.value == CAPABILITY_STATUS_VERIFIED


def test_the_fqp_adequacy_producer_drift_lock() -> None:
    """(coordinate 12 of 19) The producer whose ``bool`` crosses this seam still exists.

    Unlike the other eighteen the injected value is a plain ``bool``, not a token, so the lock
    is on the producer's **name, existence, and callability** rather than on a string value.
    """
    import tos.brokercap as brokercap

    producer = getattr(brokercap, BROKER_FQP_ADEQUACY_PRODUCER, None)
    assert producer is not None, (
        f"brokercap.{BROKER_FQP_ADEQUACY_PRODUCER} has moved — the +Broker discharge "
        "coordinate drifted"
    )
    assert callable(producer)


def test_broker_fqp_adequacy_does_not_prove_post_trade_finality() -> None:
    """(§1 line 23) An adequate Final Quantity Proof still proves no obligation final.

    brokercap answers "is this broker's FQP adequate?"; this package answers "which post-trade
    dimension is final?". An affirmative to the first leaves all ten of the second's
    dimensions exactly where they were.
    """
    fqp_only = proof_map_only(FinalityDimensionKind.ORDER_FQP)
    for dimension in FinalityDimensionKind:
        expected = dimension is FinalityDimensionKind.ORDER_FQP
        assert finality_dimensions_orthogonal(dimension, fqp_only) is expected


def test_this_package_judges_no_broker_capability() -> None:
    """(broker-agnostic) No capability predicate exists here to disagree with brokercap's."""
    for forbidden in (
        "fqp_adequate",
        "broker_capability_sufficient",
        "capability_verified",
        "capability_status",
    ):
        assert not hasattr(posttrade_predicates, forbidden)


def test_brokercap_has_no_dedicated_settlement_custodian_or_statement_dimension() -> (
    None
):
    """(§0.4 / §9.2-7 honest disclosure) The measured gap, asserted so it stays visible.

    If a future brokercap gains a dedicated dimension this test fails, which is the intended
    signal: the Phase-0 architecture question (ADR §29 Q2/Q5) would then have been answered
    and this package's injection coordinates should be revisited.
    """
    from tos.brokercap import CapabilityDimension

    dimension_names = {member.name for member in CapabilityDimension}
    for absent in ("SETTLEMENT", "CUSTODIAN", "STATEMENT_COVERAGE"):
        assert (
            absent not in dimension_names
        ), f"brokercap gained a {absent} dimension — revisit design #24 §9.2-7"


@pytest.mark.parametrize(
    "nearest",
    ["POSITIONS_BALANCES_MARGIN", "CORPORATE_ADMINISTRATIVE_EVENTS", "FILL_EVENTS"],
)
def test_the_nearest_existing_dimensions_are_the_ones_phase_1_injects(
    nearest: str,
) -> None:
    """(§0.4) The three dimensions Phase 1 consumes in place of the absent ones."""
    from tos.brokercap import CapabilityDimension

    assert hasattr(CapabilityDimension, nearest)


def test_no_institution_is_named_in_the_seam() -> None:
    """(broker-agnostic) The package expresses broker constraints as capability classes only.

    Project memory ``tos-spec-broker-agnostic``: a concrete broker belongs in a Broker
    Capability Profile *instance*, never in the decision layer.
    """
    import tos.posttrade.vocabulary as posttrade_vocabulary

    surface = set(dir(posttrade_vocabulary)) | set(dir(posttrade_predicates))
    lowered = " ".join(name.lower() for name in surface)
    for token in ("kis", "kiwoom", "ebest", "korea"):
        assert token not in lowered
