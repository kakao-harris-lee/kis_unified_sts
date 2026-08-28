"""§7 envelope subordination + §12.5/12.6 sufficiency / allocation + §6.7 reconciliation.

The protective envelope must be axis-for-axis subordinate to the Hard Safety Envelope;
dynamic reserve is sufficient only when every required domain's forecast meets its injected
minimum; multi-account minimum allocation must not encroach; protective-lease reconciliation
is the three-verdict conjunction (MAJOR-1). Each is a produced bool / verdict feeding liveauth
or authority — none closes an EV item.
"""

from __future__ import annotations

from decimal import Decimal

from tos.protective import (
    ProtectiveResourceDomain,
    account_minimum_preserved,
    envelope_subordinate,
    protective_coverage_added,
    protective_leases_reconciled,
    reserve_sufficiency,
)

from ._protective_strategies import (
    action_envelope,
    approved_minimum,
    hard_envelope,
    issue_profile,
    sufficient_forecast,
)

# ---------------------------------------------------------------------------
# §6.6 envelope subordination
# ---------------------------------------------------------------------------


def test_envelope_all_axes_subordinate_is_true() -> None:
    """(§7 canary b) Every protective axis <= the Hard Safety Envelope axis => True."""
    assert (
        envelope_subordinate(action_envelope(), hard_envelope_bounds=hard_envelope())
        is True
    )


def test_envelope_one_axis_exceeds_is_false() -> None:
    """(§7 line 315 canary a) A protective axis above the hard bound => False."""
    over = action_envelope(max_quantity=Decimal("100.0"))
    assert envelope_subordinate(over, hard_envelope_bounds=hard_envelope()) is False


def test_envelope_missing_axis_fails_closed() -> None:
    """(§6.6 fail-closed) A None axis on either side => subordination cannot be proven => False."""
    missing_protective = action_envelope(max_notional=None)
    assert (
        envelope_subordinate(missing_protective, hard_envelope_bounds=hard_envelope())
        is False
    )
    assert (
        envelope_subordinate(
            action_envelope(), hard_envelope_bounds=hard_envelope(max_margin=None)
        )
        is False
    )


def test_envelope_none_inputs_fail_closed() -> None:
    """(§6.6 ∅ fail-closed) A None envelope / None hard bound => False."""
    assert envelope_subordinate(None, hard_envelope_bounds=hard_envelope()) is False
    assert envelope_subordinate(action_envelope(), hard_envelope_bounds=None) is False


# ---------------------------------------------------------------------------
# §12.5 reserve_sufficiency (produces protective_coverage_valid)
# ---------------------------------------------------------------------------


def test_reserve_sufficient_when_every_forecast_meets_minimum() -> None:
    """(§12.5 canary b) Every required-domain forecast >= minimum => sufficient (positive side)."""
    assert (
        reserve_sufficiency(
            issue_profile(),
            forecast_capacity=sufficient_forecast(),
            approved_minimum=approved_minimum(),
        )
        is True
    )


def test_reserve_insufficient_when_a_forecast_below_minimum() -> None:
    """(§12.5 canary a) A forecast below the minimum => insufficient."""
    forecast = sufficient_forecast()
    forecast[ProtectiveResourceDomain.NETWORK_AND_CONTROL_PATH] = Decimal("0.5")
    minimum = approved_minimum()
    minimum[ProtectiveResourceDomain.NETWORK_AND_CONTROL_PATH] = Decimal("1.0")
    assert (
        reserve_sufficiency(
            issue_profile(), forecast_capacity=forecast, approved_minimum=minimum
        )
        is False
    )


def test_reserve_none_forecast_fails_closed() -> None:
    """(§8 fail-closed) A None forecast for a required domain => insufficient."""
    forecast: dict = dict(sufficient_forecast())
    forecast[ProtectiveResourceDomain.OPERATOR_EMERGENCY_PATH] = None
    assert (
        reserve_sufficiency(
            issue_profile(),
            forecast_capacity=forecast,
            approved_minimum=approved_minimum(),
        )
        is False
    )


def test_reserve_empty_maps_fail_closed() -> None:
    """(∅ fail-closed) Empty forecast / minimum maps => every required domain missing => False."""
    assert (
        reserve_sufficiency(issue_profile(), forecast_capacity={}, approved_minimum={})
        is False
    )


def test_reserve_none_profile_fails_closed() -> None:
    """(fail-closed) A None profile => insufficient."""
    assert (
        reserve_sufficiency(
            None,
            forecast_capacity=sufficient_forecast(),
            approved_minimum=approved_minimum(),
        )
        is False
    )


# ---------------------------------------------------------------------------
# §14.1 protective_coverage_added (produces liveauth expansion flag)
# ---------------------------------------------------------------------------


def test_coverage_added_when_not_expanded_and_sufficient() -> None:
    """(§14.1) Delta within envelope + sufficient => coverage added True."""
    assert (
        protective_coverage_added(
            issue_profile(),
            envelope_not_expanded=True,
            forecast_capacity=sufficient_forecast(),
            approved_minimum=approved_minimum(),
        )
        is True
    )


def test_coverage_not_added_when_envelope_expanded() -> None:
    """(§14.1 canary) An expanded envelope (None / False) => coverage not added."""
    for value in (False, None):
        assert (
            protective_coverage_added(
                issue_profile(),
                envelope_not_expanded=value,
                forecast_capacity=sufficient_forecast(),
                approved_minimum=approved_minimum(),
            )
            is False
        )


def test_coverage_not_added_when_insufficient() -> None:
    """(§14.1) A not-expanded but insufficient delta => coverage not added."""
    assert (
        protective_coverage_added(
            issue_profile(),
            envelope_not_expanded=True,
            forecast_capacity={},
            approved_minimum={},
        )
        is False
    )


# ---------------------------------------------------------------------------
# §6.7 protective_leases_reconciled (MAJOR-1 conjunction)
# ---------------------------------------------------------------------------


def test_leases_reconciled_all_three_true() -> None:
    """(§6.7 canary b) All three verdicts True => reconciled (positive side)."""
    assert (
        protective_leases_reconciled(
            all_protective_leases_accounted=True,
            reconciliation_evidence_current=True,
            no_unresolved_protective_lease_conflicts=True,
        )
        is True
    )


def test_leases_reconciled_any_none_or_false_fails_closed() -> None:
    """(§6.7 canary a) Any of the three verdicts None / False => not reconciled."""
    fields = (
        "all_protective_leases_accounted",
        "reconciliation_evidence_current",
        "no_unresolved_protective_lease_conflicts",
    )
    base = dict.fromkeys(fields, True)
    for field in fields:
        for value in (None, False):
            kwargs = dict(base)
            kwargs[field] = value
            assert protective_leases_reconciled(**kwargs) is False


# ---------------------------------------------------------------------------
# §12.6 account_minimum_preserved
# ---------------------------------------------------------------------------


def test_account_minimum_preserved_positive() -> None:
    """(§12.6) Concrete pool + per-account minimums + no encroachment + separated => True."""
    assert (
        account_minimum_preserved(
            per_account_minimum={"acct-1": Decimal("1.0"), "acct-2": Decimal("1.0")},
            global_emergency_pool=Decimal("5.0"),
            no_account_encroaches_other_minimum=True,
            trapped_and_protectable_separated=True,
        )
        is True
    )


def test_account_minimum_encroachment_fails() -> None:
    """(§12.6 line 571 canary) One account encroaching on another's minimum => False."""
    assert (
        account_minimum_preserved(
            per_account_minimum={"acct-1": Decimal("1.0")},
            global_emergency_pool=Decimal("5.0"),
            no_account_encroaches_other_minimum=False,
            trapped_and_protectable_separated=True,
        )
        is False
    )


def test_account_minimum_empty_map_fails_closed() -> None:
    """(∅ fail-closed) An empty per-account-minimum map => False (no vacuous pass)."""
    assert (
        account_minimum_preserved(
            per_account_minimum={},
            global_emergency_pool=Decimal("5.0"),
            no_account_encroaches_other_minimum=True,
            trapped_and_protectable_separated=True,
        )
        is False
    )


def test_account_minimum_none_values_fail_closed() -> None:
    """(fail-closed) A None per-account minimum or None global pool => False."""
    assert (
        account_minimum_preserved(
            per_account_minimum={"acct-1": None},
            global_emergency_pool=Decimal("5.0"),
            no_account_encroaches_other_minimum=True,
            trapped_and_protectable_separated=True,
        )
        is False
    )
    assert (
        account_minimum_preserved(
            per_account_minimum={"acct-1": Decimal("1.0")},
            global_emergency_pool=None,
            no_account_encroaches_other_minimum=True,
            trapped_and_protectable_separated=True,
        )
        is False
    )
