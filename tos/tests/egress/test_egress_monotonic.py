"""Not-Phase-1 thin model §6b — generation monotonicity, stale principal, monotonic denial.

These are thin L1 model properties authored defence-in-depth (design #22 §6b); they close **no**
EGRESS-EV — the real bypass resistance / reconnect runtime / race timing is +Security.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-002/006/007 seam;
EV-L1-complete claim forbidden; not-Phase-1 model property (EV NOT realized).
"""

from __future__ import annotations

from tos.egress import (
    EgressEvent,
    EgressPrincipal,
    RestrictiveLatchState,
    egress_generation_monotonic,
    monotonic_denial_no_revival,
    stale_principal_structurally_rejected,
)
from tos.ordering import OrderingEvent

from ._egress_strategies import clean_active_set


def _gen(index: int) -> OrderingEvent:
    """An ordering event carrying a quorum commit index (the monotonic generation coordinate)."""
    return OrderingEvent(event_id=f"g{index}", quorum_commit_index=index)


# ---- §6b.1 egress generation monotonicity --------------------------------


def test_generation_strictly_increases() -> None:
    """(§6b.1) A strictly increasing generation is monotonic."""
    assert egress_generation_monotonic(_gen(1), _gen(2)) is True


def test_generation_decrease_is_rejected() -> None:
    """(§6b.1) A decreasing generation is not monotonic (rollback is a NEW generation, §15)."""
    assert egress_generation_monotonic(_gen(2), _gen(1)) is False


def test_generation_equal_is_rejected() -> None:
    """(§6b.1) An equal (ambiguous) generation pair fails closed."""
    assert egress_generation_monotonic(_gen(1), _gen(1)) is False


# ---- §6b.1 stale principal structural rejection --------------------------


def test_current_active_principal_admitted() -> None:
    """(§6b.1) A represented, active, unexpired, current-generation principal is admitted."""
    assert (
        stale_principal_structurally_rejected(
            "principal-1", clean_active_set(egress_generation=9), expected_generation=9
        )
        is True
    )


def test_wrong_generation_principal_rejected() -> None:
    """(§6b.1) A principal whose set generation != expected is rejected (stale)."""
    assert (
        stale_principal_structurally_rejected(
            "principal-1", clean_active_set(egress_generation=9), expected_generation=8
        )
        is False
    )


def test_unrepresented_principal_rejected() -> None:
    """(§6b.1 / §8:233) An unrepresented principal is rejected (no membership inference)."""
    assert (
        stale_principal_structurally_rejected(
            "ghost", clean_active_set(egress_generation=9), expected_generation=9
        )
        is False
    )


def test_inactive_or_expired_principal_rejected() -> None:
    """(§6b.1) A represented but inactive / expired principal is rejected."""
    inactive = clean_active_set(
        egress_generation=9,
        principals=(
            EgressPrincipal(
                workload_identity="principal-1", active=None, expired=False
            ),
        ),
    )
    expired = clean_active_set(
        egress_generation=9,
        principals=(
            EgressPrincipal(workload_identity="principal-1", active=True, expired=True),
        ),
    )
    assert (
        stale_principal_structurally_rejected(
            "principal-1", inactive, expected_generation=9
        )
        is False
    )
    assert (
        stale_principal_structurally_rejected(
            "principal-1", expired, expected_generation=9
        )
        is False
    )


def test_unknown_expiry_principal_rejected_but_positive_non_expiry_admitted() -> None:
    """(§6b.1 MAJOR-2 polarity) expired=None (unknown) ⇒ denial; expired=False (positive) ⇒ admit.

    ``expired`` is negative-polarity (True = expired = risk), so admission requires positive proof
    of non-expiry ``is False`` — an unknown old-principal state is denial (EGRESS-INV-011 line 183).
    """
    unknown_expiry = clean_active_set(
        egress_generation=9,
        principals=(
            EgressPrincipal(workload_identity="principal-1", active=True, expired=None),
        ),
    )
    positive_non_expiry = clean_active_set(
        egress_generation=9,
        principals=(
            EgressPrincipal(
                workload_identity="principal-1", active=True, expired=False
            ),
        ),
    )
    # firing side: unknown expiry is denied (was a fail-open under `expired is not True`).
    assert (
        stale_principal_structurally_rejected(
            "principal-1", unknown_expiry, expected_generation=9
        )
        is False
    )
    # positive side: an explicitly-non-expired, active, current principal is admitted.
    assert (
        stale_principal_structurally_rejected(
            "principal-1", positive_non_expiry, expected_generation=9
        )
        is True
    )


def test_none_principal_or_set_fails_closed() -> None:
    """(§6b.1 fail-closed) A None principal / set / generation is rejected."""
    assert (
        stale_principal_structurally_rejected(
            None, clean_active_set(), expected_generation=9
        )
        is False
    )
    assert (
        stale_principal_structurally_rejected(
            "principal-1", None, expected_generation=9
        )
        is False
    )
    assert (
        stale_principal_structurally_rejected(
            "principal-1", clean_active_set(), expected_generation=None
        )
        is False
    )


# ---- §6b.3 monotonic denial non-revival ----------------------------------


def _restrictive(kind: str) -> EgressEvent:
    return EgressEvent(event_kind=kind, restrictive=True)


def _revival(kind: str) -> EgressEvent:
    return EgressEvent(event_kind=kind, restrictive=False)


def test_deny_latched_never_revives() -> None:
    """(§6b.3 / §13:393) A DENY_LATCHED state is not cleared by ANY revival event."""
    revival_events = [
        _revival("cache_recovery"),
        _revival("reconnect"),
        _revival("secret_refresh"),
        _revival("route_restoration"),
        _revival("deployment_success"),
        _revival("alert_deletion"),
    ]
    result = monotonic_denial_no_revival(
        RestrictiveLatchState.DENY_LATCHED, revival_events
    )
    assert result is RestrictiveLatchState.DENY_LATCHED


def test_clear_with_no_events_stays_clear() -> None:
    """(§6b.3 / §4.7 availability) A CLEAR latch with ∅ events stays CLEAR (no spurious deny)."""
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.CLEAR, [])
        is RestrictiveLatchState.CLEAR
    )


def test_clear_with_revival_events_stays_clear() -> None:
    """(§6b.3) A CLEAR latch with only revival (non-restrictive) events stays CLEAR."""
    assert (
        monotonic_denial_no_revival(
            RestrictiveLatchState.CLEAR, [_revival("reconnect")]
        )
        is RestrictiveLatchState.CLEAR
    )


def test_clear_with_restrictive_event_latches_deny() -> None:
    """(§6b.3) A restrictive event latches deny from CLEAR."""
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.CLEAR, [_restrictive("halt")])
        is RestrictiveLatchState.DENY_LATCHED
    )


def test_none_latch_state_fails_closed() -> None:
    """(§6b.3 fail-closed) A None (unknown) latch state resolves to DENY_LATCHED."""
    assert monotonic_denial_no_revival(None, []) is RestrictiveLatchState.DENY_LATCHED
