"""``tos.egressgw.venuefacts`` — item 12's venue-half composite predicate + full item-12 verdict
polarity (kernel round #3 §2 decision 4, `docs/plans/2026-09-12-tos-kernel-round-3-plan.md`).

Two things this file locks that nothing else does:

* **The None-propagating AND is exhaustively tested**, all 3³ = 27 combinations of the three
  sub-facts (``session_facts_current`` / ``tradability_facts_current`` / ``account_facts_current``
  each in ``{True, False, None}``) — mutation M3 (folding an explicit ``False`` into ``None``)
  cannot survive an exhaustive table the way it could survive a handful of hand-picked cases.
* **The full item-12 verdict's polarity**, venue half then broker half, over every outcome this
  gate can reach: ``DENIED`` from an explicit venue ``False``, ``UNKNOWN`` from an unresolved venue
  ``None``, and — only once the venue half is positively ``True`` — ``SATISFIED`` / ``DENIED`` /
  ``UNKNOWN`` from the broker-constraint-generation half. Mutation M4 (reintroducing the legacy
  ``venue_session_account_facts_current`` field) has nowhere to hide: :class:`SendBoundaryContext`
  is constructed here with only the three sub-fact fields, so a stray legacy field would be a
  ``pydantic`` validation error, not a silently-ignored extra kwarg.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

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


# ===========================================================================
# venue_session_account_facts_current — exhaustive 27-combination AND-with-None
# ===========================================================================


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
    """(mutation M3) Every one of the 3³ = 27 sub-fact combinations matches the None-propagating
    AND: any ``False`` dominates to ``False``; else any ``None`` propagates to ``None``; else
    ``True``. A composite that folded ``False`` into ``None`` (mutation M3) would only be caught
    by the combinations where ``False`` and ``None`` are both present — this table includes all of
    them (e.g. ``(False, None, True)``), not just the all-``False`` or all-``None`` corners.
    """
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


# ===========================================================================
# venue_generation_item_verdict — full item-12 polarity (venue half, then broker half)
# ===========================================================================

_ITEM = SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION


def _context(
    *,
    session: bool | None = True,
    tradability: bool | None = True,
    account: bool | None = True,
    broker: bool | None = True,
) -> SendBoundaryContext:
    """A context carrying only item 12's own four inputs (mutation M4: constructing with just
    these — no legacy ``venue_session_account_facts_current`` field — proves that field is really
    gone; reintroducing it would make every other :class:`SendBoundaryContext` construction site
    in the suite pass an unrecognized kwarg were it required again, but here the absence itself is
    the pin: this call would still succeed after M4 since pydantic tolerates a missing deleted
    field's *absence* — the mutation is caught instead by ``test_egressgw_gateway.py``'s field-
    table cases and by :mod:`tos.tests.egressgw.test_egressgw_import_closure`'s allowlist, which
    would need no change for M4, but ``records.py``'s own field enumeration test would gain a
    stray attribute — see ``test_egressgw_package.py``)."""
    return SendBoundaryContext(
        session_facts_current=session,
        tradability_facts_current=tradability,
        account_facts_current=account,
        broker_constraint_generation_current=broker,
    )


def test_venue_false_denies_before_the_broker_half_is_ever_read() -> None:
    """(kernel round #3 §11 결정 5) An explicit venue-half ``False`` is ``DENIED`` — never folded
    into ``UNKNOWN`` the way the pre-round-#3 gate treated every non-``True`` case."""
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
    """session, then tradability, then account — the order :func:`_first_non_positive_sub_fact`
    walks (kernel round #3 §2 decision 4: "첫 비양성 우선")."""
    # session is the first non-positive even though tradability is also non-positive.
    v1 = venue_generation_item_verdict(_context(session=False, tradability=None))
    assert "session_facts_current" in (v1.reason or "")
    assert "tradability_facts_current" not in (v1.reason or "")

    # session True, so tradability is the first non-positive.
    v2 = venue_generation_item_verdict(
        _context(session=True, tradability=None, account=False)
    )
    assert "tradability_facts_current" in (v2.reason or "")
    assert "account_facts_current" not in (v2.reason or "")

    # session and tradability both True, so account is the first (and only) non-positive.
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
        # A venue-half DENIED/UNKNOWN outcome does not depend on the broker half's own value —
        # the venue half is checked first and short-circuits (kernel round #3 §2 decision 4).
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
    """The closed outcome table (kernel round #3 §2 decision 4 / §5 실증 3): venue-half ``False``
    ⇒ ``DENIED``, venue-half ``None`` ⇒ ``UNKNOWN`` regardless of the broker half; venue-half
    ``True`` defers to the broker half's own ``True``/``False``/``None`` ⇒
    ``SATISFIED``/``DENIED``/``UNKNOWN``."""
    verdict = venue_generation_item_verdict(
        _context(
            session=session, tradability=tradability, account=account, broker=broker
        )
    )
    assert verdict.outcome is expected


def test_the_legacy_field_no_longer_exists_on_send_boundary_context() -> None:
    """(mutation M4) Reintroducing ``venue_session_account_facts_current`` as a
    :class:`SendBoundaryContext` field would make this assertion fail — the composed value lives
    only in the kernel function, never in a stand-in field on the context."""
    assert "venue_session_account_facts_current" not in SendBoundaryContext.model_fields
    assert "session_facts_current" in SendBoundaryContext.model_fields
    assert "tradability_facts_current" in SendBoundaryContext.model_fields
    assert "account_facts_current" in SendBoundaryContext.model_fields
