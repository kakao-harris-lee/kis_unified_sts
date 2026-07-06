"""Tests for neutral futures instrument contract-code helpers."""

from datetime import date, datetime

import pytest

from shared.instruments.futures import (
    CONTRACT_STATE_SCHEMA_VERSION,
    compute_contract_state,
    contract_state_to_fields,
    get_expiry_date,
    get_front_month_code,
    get_next_month_code,
)


def test_mini_front_month_uses_legacy_a05_prefix():
    code = get_front_month_code(product="mini", target_date=date(2026, 3, 1))
    assert code == "A05603"


def test_kospi200_rolls_after_expiry():
    expiry = get_expiry_date(2026, 3)
    day_after = date(expiry.year, expiry.month, expiry.day + 1)
    assert get_front_month_code(product="kospi200", target_date=day_after) == "A01606"


def test_next_month_code_mini_is_month_after_front():
    # 2026-07 front (expiry 07-09) → next is 2026-08.
    assert get_next_month_code(product="mini", target_date=date(2026, 7, 1)) == "A05608"


def test_next_month_code_kospi200_is_next_quarterly():
    # 2026-07 → front quarterly is 09, next is 12.
    assert (
        get_next_month_code(product="kospi200", target_date=date(2026, 7, 1)) == "A01612"
    )


# ---------------------------------------------------------------------------
# Contract / roll-state classification (docs §4.1)
# ---------------------------------------------------------------------------

_ASOF = datetime(2026, 7, 1, 8, 0)


def _state(target_date, *, product="mini", night="1A01609", night_required=True):
    return compute_contract_state(
        product=product,
        target_date=target_date,
        asof_ts=_ASOF,
        pre_roll_days=5,
        block_front_new_entries_days=2,
        require_roll_on_expiry_day=True,
        night_front_symbol=night,
        night_required=night_required,
    )


@pytest.mark.parametrize(
    ("target_date", "expected_dte", "expected_state", "new_entry"),
    [
        (date(2026, 7, 1), 8, "normal", True),  # dte 8 > pre_roll 5
        (date(2026, 7, 4), 5, "pre_roll", True),  # dte 5 <= pre_roll
        (date(2026, 7, 7), 2, "roll_required", False),  # dte 2 <= block
        (date(2026, 7, 9), 0, "expired", False),  # expiry day
    ],
)
def test_roll_state_boundaries(target_date, expected_dte, expected_state, new_entry):
    state = _state(target_date)
    assert state.days_to_expiry == expected_dte
    assert state.roll_state == expected_state
    assert state.new_entry_front_allowed is new_entry


def test_front_rolls_after_expiry_day():
    # Day after the 07-09 expiry → front is the August contract, dte far out.
    state = _state(date(2026, 7, 10))
    assert state.front_symbol == "A05608"
    assert state.roll_state == "normal"


def test_missing_night_master_yields_unknown_fail_closed():
    state = _state(date(2026, 7, 1), night=None, night_required=True)
    assert state.roll_state == "unknown"
    assert state.roll_reason == "missing_master"
    assert state.new_entry_front_allowed is False
    assert state.hedge_front_allowed is False


def test_night_not_required_ignores_missing_symbol():
    state = _state(date(2026, 7, 1), night=None, night_required=False)
    assert state.roll_state == "normal"


def test_full_product_uses_quarterly_codes():
    state = _state(date(2026, 7, 1), product="kospi200", night_required=False)
    assert state.front_symbol == "A01609"
    assert state.next_symbol == "A01612"


def test_contract_state_to_fields_contract():
    state = _state(date(2026, 7, 1))
    fields = contract_state_to_fields(state)
    assert fields["schema_version"] == str(CONTRACT_STATE_SCHEMA_VERSION)
    assert fields["product"] == "mini"
    assert fields["front_symbol"] == "A05607"
    assert fields["next_symbol"] == "A05608"
    assert fields["night_front_symbol"] == "1A01609"
    assert fields["roll_state"] == "normal"
    assert fields["new_entry_front_allowed"] == "true"
    assert fields["hedge_front_allowed"] == "true"
    assert fields["expiry_date"] == "2026-07-09"
    # Every published value is a string (Redis hash contract).
    assert all(isinstance(v, str) for v in fields.values())


def test_contract_state_to_fields_null_marker_for_missing_night():
    state = _state(date(2026, 7, 1), night=None, night_required=False)
    fields = contract_state_to_fields(state)
    assert fields["night_front_symbol"] == ""
    assert fields["night_next_symbol"] == ""
