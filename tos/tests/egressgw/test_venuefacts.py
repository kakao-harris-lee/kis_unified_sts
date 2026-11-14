"""``tos.egressgw.venuefacts`` — item 12's venue-half composite predicate + full item-12 verdict"""

from __future__ import annotations

import itertools

import pytest
from tos.egressgw.records import SendBoundaryContext
from tos.egressgw.venuefacts import (
    venue_generation_item_verdict,
    venue_session_account_facts_current,
)
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome

_TRI_STATE = (True, False, None)


def _expected_composite(
    session: bool | None, tradability: bool | None, account: bool | None
) -> bool | None:
    values = (session, tradability, account)
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


@pytest.mark.parametrize(
    ("session", "tradability", "account"),
    list(itertools.product(_TRI_STATE, repeat=3)),
)
def test_composite_all_27_combinations(
    session: bool | None, tradability: bool | None, account: bool | None
) -> None:
    """(mutation M3) Every one of the 3³ = 27 sub-fact combinations matches the None-propagating"""
    assert venue_session_account_facts_current(
        session, tradability, account
    ) == _expected_composite(session, tradability, account)


def test_false_dominates_over_none_regardless_of_position() -> None:
    """An explicit ``False`` anywhere wins over a ``None`` anywhere else — order-independent."""
    assert venue_session_account_facts_current(False, None, None) is False
    assert venue_session_account_facts_current(None, False, None) is False
    assert venue_session_account_facts_current(None, None, False) is False
    assert venue_session_account_facts_current(False, True, None) is False
    assert venue_session_account_facts_current(True, False, None) is False


def test_all_true_is_true() -> None:
    assert venue_session_account_facts_current(True, True, True) is True


_ITEM = SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION


def _context(
    *,
    session: bool | None = True,
    tradability: bool | None = True,
    account: bool | None = True,
    broker: bool | None = True,
) -> SendBoundaryContext:
    """A context carrying only item 12's own four inputs (mutation M4: constructing with just"""
    return SendBoundaryContext(
        session_facts_current=session,
        tradability_facts_current=tradability,
        account_facts_current=account,
        broker_constraint_generation_current=broker,
    )


def test_venue_false_denies_before_the_broker_half_is_ever_read() -> None:
    """(kernel round #3 §11 결정 5) An explicit venue-half ``False`` is ``DENIED`` — never folded"""
    verdict = venue_generation_item_verdict(_context(session=False, broker=True))
    assert verdict.item is _ITEM
    assert verdict.outcome is VerifyOutcome.DENIED
    assert "venue / session" in (verdict.reason or "")
    assert "broker-constraint generation" not in (verdict.reason or "")
    assert "session_facts_current" in (verdict.reason or "")


def test_venue_none_is_unknown() -> None:
    verdict = venue_generation_item_verdict(_context(tradability=None, broker=True))
    assert verdict.outcome is VerifyOutcome.UNKNOWN
    assert "venue / session" in (verdict.reason or "")
    assert "broker-constraint generation" not in (verdict.reason or "")
    assert "tradability_facts_current" in (verdict.reason or "")


def test_reason_names_the_first_non_positive_subfact_in_order() -> None:
    """session, then tradability, then account — the order :func:`_first_non_positive_sub_fact`"""
    v1 = venue_generation_item_verdict(_context(session=False, tradability=None))
    assert "session_facts_current" in (v1.reason or "")
    assert "tradability_facts_current" not in (v1.reason or "")

    v2 = venue_generation_item_verdict(
        _context(session=True, tradability=None, account=False)
    )
    assert "tradability_facts_current" in (v2.reason or "")
    assert "account_facts_current" not in (v2.reason or "")

    v3 = venue_generation_item_verdict(
        _context(session=True, tradability=True, account=None)
    )
    assert "account_facts_current" in (v3.reason or "")


def test_venue_true_and_broker_true_is_satisfied() -> None:
    verdict = venue_generation_item_verdict(_context(broker=True))
    assert verdict.outcome is VerifyOutcome.SATISFIED
    assert "venue / session" in (verdict.reason or "")
    assert "broker-constraint" in (verdict.reason or "")


def test_venue_true_and_broker_false_is_denied() -> None:
    verdict = venue_generation_item_verdict(_context(broker=False))
    assert verdict.outcome is VerifyOutcome.DENIED
    assert "broker-constraint generation" in (verdict.reason or "")
    assert "venue / session" not in (verdict.reason or "")


def test_venue_true_and_broker_none_is_unknown() -> None:
    verdict = venue_generation_item_verdict(_context(broker=None))
    assert verdict.outcome is VerifyOutcome.UNKNOWN
    assert "broker-constraint generation" in (verdict.reason or "")
    assert "venue / session" not in (verdict.reason or "")


@pytest.mark.parametrize(
    ("session", "tradability", "account", "broker", "expected"),
    [
        (True, True, True, True, VerifyOutcome.SATISFIED),
        (True, True, True, False, VerifyOutcome.DENIED),
        (True, True, True, None, VerifyOutcome.UNKNOWN),
        (False, True, True, True, VerifyOutcome.DENIED),
        (None, True, True, True, VerifyOutcome.UNKNOWN),
        (True, False, True, True, VerifyOutcome.DENIED),
        (True, None, True, True, VerifyOutcome.UNKNOWN),
        (True, True, False, True, VerifyOutcome.DENIED),
        (True, True, None, True, VerifyOutcome.UNKNOWN),
        (False, True, True, False, VerifyOutcome.DENIED),
        (False, True, True, None, VerifyOutcome.DENIED),
        (None, True, True, False, VerifyOutcome.UNKNOWN),
        (None, True, True, None, VerifyOutcome.UNKNOWN),
    ],
)
def test_item12_polarity_table(
    session: bool | None,
    tradability: bool | None,
    account: bool | None,
    broker: bool | None,
    expected: VerifyOutcome,
) -> None:
    """The closed outcome table (kernel round #3 §2 decision 4 / §5 실증 3): venue-half ``False``"""
    verdict = venue_generation_item_verdict(
        _context(
            session=session, tradability=tradability, account=account, broker=broker
        )
    )
    assert verdict.outcome is expected


def test_the_legacy_field_no_longer_exists_on_send_boundary_context() -> None:
    """(mutation M4) Reintroducing ``venue_session_account_facts_current`` as a"""
    assert "venue_session_account_facts_current" not in SendBoundaryContext.model_fields
    assert "session_facts_current" in SendBoundaryContext.model_fields
    assert "tradability_facts_current" in SendBoundaryContext.model_fields
    assert "account_facts_current" in SendBoundaryContext.model_fields
