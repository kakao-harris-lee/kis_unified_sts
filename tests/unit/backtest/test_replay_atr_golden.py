"""Golden regression pins for ``MarketContextReplay`` indicator math (P1-b1).

This test freezes the exact hand-rolled ATR-14 math that
``shared/backtest/market_context_replay.py`` carried BEFORE delegation to the
indicator package, and asserts the production path reproduces those numbers
BIT-IDENTICALLY — exact float equality with NaN positions preserved
(``np.testing.assert_array_equal``). ``MarketContextReplay`` is the B3 witness's
market-context loader (``tools/tos_cp3/produce_fields.py``), so this is a pin on
the witness path.

The sibling pins for ``shared/backtest/daily_adapter.py`` and
``shared/backtest/adapter.py`` went with those two modules in the legacy removal
L7 — both fell outside the import closure
(docs/plans/2026-11-07-legacy-removal-plan.md §3).

A hard-coded literal spot pin additionally protects against BOTH sides drifting
together (e.g. a frozen copy being "fixed" alongside production).

Do NOT edit the ``_frozen_*`` reference implementation: it is a verbatim
pre-refactor copy (the golden).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from shared.backtest.market_context_replay import MarketContextReplay
from shared.execution.contract_spec import ContractSpec

# ---------------------------------------------------------------------------
# Deterministic synthetic OHLCV builder
# ---------------------------------------------------------------------------


def _replay_frame(sessions: int = 2, bars_per_session: int = 100) -> pd.DataFrame:
    """Seeded synthetic futures 1-minute OHLCV for MarketContextReplay."""
    rng = np.random.RandomState(11)
    rows = []
    price = 350.0
    for day in range(sessions):
        day_ts = datetime(2026, 4, 6 + day, 9, 0, 0)
        for i in range(bars_per_session):
            price += float(rng.normal(0.0, 0.15))
            high = price + float(abs(rng.normal(0.1, 0.05)))
            low = price - float(abs(rng.normal(0.1, 0.05)))
            rows.append(
                {
                    "timestamp": day_ts + timedelta(minutes=i),
                    "open": price - 0.05,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": int(rng.randint(50, 500)),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Frozen (pre-refactor) reference implementation
# ---------------------------------------------------------------------------


def _frozen_compute_atr(
    highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
) -> np.ndarray:
    """Verbatim pre-refactor ``market_context_replay._compute_atr`` (ATR-14,
    TR with bar-0 = H-L, partial-window numpy slice means from bar 0)."""
    _ATR_PERIOD = 14
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr = np.empty(n)
    for i in range(n):
        start = max(0, i - _ATR_PERIOD + 1)
        atr[i] = tr[start : i + 1].mean()


class TestReplayAtrGolden:
    def _replay(self, df: pd.DataFrame) -> MarketContextReplay:
        spec = ContractSpec(
            name="golden",
            multiplier_krw_per_point=250_000,
            tick_size_points=0.05,
            tick_value_krw=12_500,
            commission_rate=0.00003,
            symbol_prefix="101",
        )
        return MarketContextReplay(
            df=df,
            symbol="101S6000",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=spec,
        )

    def test_atr_series_bit_identical_to_frozen(self):
        df = _replay_frame()
        replay = self._replay(df)
        expected = _frozen_compute_atr(
            df["high"].to_numpy(dtype=float),
            df["low"].to_numpy(dtype=float),
            df["close"].to_numpy(dtype=float),
        )
        np.testing.assert_array_equal(
            replay._atr_series,
            expected,
            err_msg="numeric drift in replay ATR-14 series",
        )
        assert replay._atr_90th == float(np.nanpercentile(expected, 90))


# Literal spot pins (full repr, generated from the pre-refactor code path).
SPOT_REPLAY_ATR_LAST = 0.2438318145813493
SPOT_REPLAY_ATR_90TH = 0.2763946369876343
SPOT_REPLAY_CTX_ATR = 0.2317447600618274
