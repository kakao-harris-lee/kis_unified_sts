"""``session.vwap_typical`` / ``atr`` / ``session.minutes_since_open`` must equal
``MarketContextReplay`` — bit for bit, on a fixture frame.

Why a test rather than an import
--------------------------------
These three values are defined by the B3 witness path
(``shared/backtest/market_context_replay.py``, byte-frozen until
``TOS_PAPER_READY``) and by ``shared/decision/context.py``. Neither package is in
the six pure-commons packages ``tos`` may import, and
``shared/indicators/fields/`` has to stay importable by the kernel, so it cannot
call either. Extracting a shared helper would mean EDITING the frozen witness,
which the plan forbids (§4).

So the fields package repeats the definitions and THIS test is what pins them:
exact float equality (``==``, no tolerance — a tolerance would hide exactly the
drift P2-b's byte-identical comparison exists to catch), against the witness
itself for all three, plus against the indicator engine's ``atr_partial`` — the
op the witness delegates its ATR to — for the ATR.

The test is in ``tests/``, which may import anything.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.market_context_replay import MarketContextReplay
from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    backtest_indicator_engine,
)
from shared.indicators.fields import FieldBar, FieldEvaluator
from shared.instruments.contract_spec import ContractSpec

from .conftest import parsed

_OPEN_HOUR = 8
_OPEN_MINUTE = 45
_ATR_PERIOD = 14

_FIELDS = [
    {"name": "close", "op": "bar.close"},
    {"name": "vwap", "op": "session.vwap_typical"},
    {"name": "atr", "op": "atr", "params": {"period": _ATR_PERIOD}},
    {
        "name": "mso",
        "op": "session.minutes_since_open",
        "params": {"open_hour": _OPEN_HOUR, "open_minute": _OPEN_MINUTE},
    },
]
_PUBLISH = [
    {"field": "close", "as": "close_x100", "scale": {"mult": 100, "round": "half_up"}},
]


def _frame(sessions: int = 3, bars_per_session: int = 120) -> pd.DataFrame:
    """Seeded synthetic 1-minute OHLCV, same shape the replay goldens use."""
    rng = np.random.RandomState(11)
    rows = []
    price = 350.0
    for day in range(sessions):
        day_ts = datetime(2026, 4, 6 + day, 9, 0, 0)
        for index in range(bars_per_session):
            price += float(rng.normal(0.0, 0.15))
            high = price + float(abs(rng.normal(0.1, 0.05)))
            low = price - float(abs(rng.normal(0.1, 0.05)))
            rows.append(
                {
                    "timestamp": day_ts + timedelta(minutes=index),
                    "open": price - 0.05,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": int(rng.randint(50, 500)),
                }
            )
    return pd.DataFrame(rows)


def _contract_spec() -> ContractSpec:
    return ContractSpec(
        name="parity",
        multiplier_krw_per_point=250_000,
        tick_size_points=0.05,
        tick_value_krw=12_500,
        commission_rate=0.00003,
        symbol_prefix="101",
    )


def _field_bars(df: pd.DataFrame) -> list[FieldBar]:
    """Every frame row as a :class:`FieldBar`, in order.

    EVERY row, not just the ones the replay yields: the replay precomputes ATR
    over the whole frame and accumulates VWAP from each session's first bar, so
    the evaluator has to see the same history to agree with it.
    """
    return [
        FieldBar.create(
            row.timestamp,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in df.itertuples(index=False)
    ]


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return _frame()


class TestWitnessParity:
    def test_vwap_atr_and_minutes_since_open_are_bit_identical(
        self, frame: pd.DataFrame
    ) -> None:
        replay = MarketContextReplay(
            df=frame,
            symbol="101S6000",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=_contract_spec(),
            market_open_hour=_OPEN_HOUR,
            market_open_minute=_OPEN_MINUTE,
        )
        declared = {
            record.bar.ts_kst: record.values
            for record in FieldEvaluator(parsed(_FIELDS, _PUBLISH)).run(
                _field_bars(frame)
            )
        }

        compared = 0
        for ctx in replay.iter_contexts():
            values = declared[ctx.now]
            assert values["vwap"] == ctx.vwap, f"vwap at {ctx.now}"
            assert values["atr"] == ctx.atr_14, f"atr at {ctx.now}"
            assert values["mso"] == ctx.minutes_since_open(), f"mso at {ctx.now}"
            assert values["close"] == ctx.current_price, f"close at {ctx.now}"
            compared += 1
        # The replay skips the warmup bars and the first session (no prior
        # close), so this must still be a substantial sample.
        assert compared >= 200, f"only {compared} bars compared"

    def test_atr_matches_the_engine_op_the_witness_delegates_to(
        self, frame: pd.DataFrame
    ) -> None:
        """``atr_partial`` over the whole frame, which is what the witness calls."""
        window = OHLCVWindow.from_sequences(
            open=frame["open"].to_numpy(dtype=float),
            high=frame["high"].to_numpy(dtype=float),
            low=frame["low"].to_numpy(dtype=float),
            close=frame["close"].to_numpy(dtype=float),
            volume=frame["volume"].to_numpy(dtype=float),
        )
        expected = (
            backtest_indicator_engine()
            .compute(
                IndicatorSpec.create("atr_partial", {"period": _ATR_PERIOD}), window
            )
            .series["value"]
        )
        observed = np.array(
            [
                record.values["atr"]
                for record in FieldEvaluator(parsed(_FIELDS, _PUBLISH)).run(
                    _field_bars(frame)
                )
            ],
            dtype=float,
        )
        np.testing.assert_array_equal(
            observed,
            expected,
            err_msg="declarative atr drifted from the engine's atr_partial",
        )

    def test_vwap_matches_a_restatement_of_the_witness_expression(
        self, frame: pd.DataFrame
    ) -> None:
        """The witness computes VWAP inline, so there is no helper to call —
        this restates its expression and compares bit for bit."""
        highs = frame["high"].to_numpy(dtype=float)
        lows = frame["low"].to_numpy(dtype=float)
        closes = frame["close"].to_numpy(dtype=float)
        volumes = frame["volume"].to_numpy(dtype=float)
        dates = [pd.Timestamp(ts).date() for ts in frame["timestamp"]]

        expected: list[float] = []
        session_start = 0
        for index in range(len(frame)):
            if index > 0 and dates[index] != dates[index - 1]:
                session_start = index
            slice_h = highs[session_start : index + 1]
            slice_l = lows[session_start : index + 1]
            slice_c = closes[session_start : index + 1]
            slice_v = volumes[session_start : index + 1]
            typical_price = (slice_h + slice_l + slice_c) / 3.0
            total_vol = slice_v.sum()
            if total_vol > 0:
                expected.append(float((typical_price * slice_v).sum() / total_vol))
            else:
                expected.append(float(closes[index]))

        observed = [
            record.values["vwap"]
            for record in FieldEvaluator(parsed(_FIELDS, _PUBLISH)).run(
                _field_bars(frame)
            )
        ]
        assert observed == expected
