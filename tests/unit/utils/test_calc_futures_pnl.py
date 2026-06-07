"""F-5: futures realized PnL — parity with PseudoOCO._record_pnl (no fee)."""

from __future__ import annotations

import pytest

from shared.utils.calc import calc_futures_realized_pnl

MULT = 50_000.0


def test_long_win() -> None:
    # (333.00-331.20)*1*1*50000 = 90000
    assert calc_futures_realized_pnl(
        331.20, 333.00, 1, "long", multiplier_krw_per_point=MULT
    ) == pytest.approx(90_000.0)


def test_long_loss() -> None:
    assert calc_futures_realized_pnl(
        331.20, 330.00, 1, "long", multiplier_krw_per_point=MULT
    ) == pytest.approx(-60_000.0)


def test_short_win() -> None:
    # short: (329.40-331.20)*(-1)*1*50000 = 90000
    assert calc_futures_realized_pnl(
        331.20, 329.40, 1, "short", multiplier_krw_per_point=MULT
    ) == pytest.approx(90_000.0)


def test_short_loss() -> None:
    assert calc_futures_realized_pnl(
        331.20, 332.40, 1, "short", multiplier_krw_per_point=MULT
    ) == pytest.approx(-60_000.0)


def test_quantity_scales() -> None:
    assert calc_futures_realized_pnl(
        331.20, 333.20, 3, "long", multiplier_krw_per_point=MULT
    ) == pytest.approx(300_000.0)
