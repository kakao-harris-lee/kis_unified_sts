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

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

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


def _edge_frame() -> pd.DataFrame:
    """A frame built out of the shapes that break a careless VWAP or ATR.

    LOW-2 of the P2-a review. Four sessions, each carrying one hazard:

    ===  ================================================================
    day  hazard
    ===  ================================================================
    1    130 bars from the 08:45 open — the only purpose is to seed ATR
         and give day 2 a ``prev_close`` (the replay yields nothing from a
         first session). ``minutes_since_open`` starts at exactly 0.
    2    an ALL-ZERO-VOLUME START: the first 25 bars have volume 0, so the
         session's cumulative volume is 0 and VWAP must fall back to the
         close on every one of them. Then scattered zero-volume bars.
    3    a MISSING-MINUTE GAP: day 2 stops early (10:20) and day 3 starts
         at 08:45, so the gap straddles the session boundary; day 3 also
         skips minutes 30..40 inside the session. ATR's true range must
         still reach across both (it is not reset per session).
    4    an ENTIRELY zero-volume session — the fallback on every bar, in
         the range the replay actually yields.
    ===  ================================================================
    """
    rng = np.random.RandomState(29)
    rows: list[dict[str, Any]] = []

    def add(day: int, minute_offsets: Iterable[int], volumes: Iterable[float]) -> None:
        nonlocal price
        day_ts = datetime(2026, 4, 6 + day, 8, 45, 0)
        for offset, volume in zip(minute_offsets, volumes):
            price += float(rng.normal(0.0, 0.12))
            high = price + float(abs(rng.normal(0.08, 0.04)))
            low = price - float(abs(rng.normal(0.08, 0.04)))
            rows.append(
                {
                    "timestamp": day_ts + timedelta(minutes=offset),
                    "open": price - 0.05,
                    "high": high,
                    "low": low,
                    "close": price,
                    "volume": volume,
                }
            )

    price = 350.0
    # Day 1 — seed, from the open.
    add(0, range(130), [float(rng.randint(50, 400)) for _ in range(130)])
    # Day 2 — 25 zero-volume bars, then scattered ones; stops early at 10:20.
    day2_minutes = list(range(95))  # 08:45 .. 10:19
    day2_volumes = [
        0.0 if index < 25 or index % 17 == 0 else float(rng.randint(50, 400))
        for index in range(len(day2_minutes))
    ]
    add(1, day2_minutes, day2_volumes)
    # Day 3 — starts at the open, skips minutes 30..40.
    day3_minutes = [m for m in range(110) if not 30 <= m < 40]
    add(
        2,
        day3_minutes,
        [
            0.0 if index % 23 == 0 else float(rng.randint(50, 400))
            for index in range(len(day3_minutes))
        ],
    )
    # Day 4 — every bar zero volume.
    add(3, range(60), [0.0] * 60)
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


@pytest.fixture(scope="module")
def edge_frame() -> pd.DataFrame:
    return _edge_frame()


#: The two frames every parity assertion runs on: a plain seeded path, and the
#: edge-shape frame from LOW-2 of the P2-a review.
_FRAMES = ("frame", "edge_frame")


def _declared_values(frame: pd.DataFrame) -> dict[Any, Any]:
    return {
        record.bar.ts_kst: record.values
        for record in FieldEvaluator(parsed(_FIELDS, _PUBLISH)).run(_field_bars(frame))
    }


def _declared_series(frame: pd.DataFrame, field: str) -> list[float]:
    return [
        record.values[field]
        for record in FieldEvaluator(parsed(_FIELDS, _PUBLISH)).run(_field_bars(frame))
    ]


@pytest.mark.parametrize("frame_name", _FRAMES)
class TestWitnessParity:
    def test_vwap_atr_and_minutes_since_open_are_bit_identical(
        self, frame_name: str, request: pytest.FixtureRequest
    ) -> None:
        frame = request.getfixturevalue(frame_name)
        replay = MarketContextReplay(
            df=frame,
            symbol="101S6000",
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=_contract_spec(),
            market_open_hour=_OPEN_HOUR,
            market_open_minute=_OPEN_MINUTE,
        )
        declared = _declared_values(frame)

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
        self, frame_name: str, request: pytest.FixtureRequest
    ) -> None:
        """``atr_partial`` over the whole frame, which is what the witness calls."""
        frame = request.getfixturevalue(frame_name)
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
        observed = np.array(_declared_series(frame, "atr"), dtype=float)
        np.testing.assert_array_equal(
            observed,
            expected,
            err_msg="declarative atr drifted from the engine's atr_partial",
        )

    def test_vwap_matches_a_restatement_of_the_witness_expression(
        self, frame_name: str, request: pytest.FixtureRequest
    ) -> None:
        """The witness computes VWAP inline, so there is no helper to call —
        this restates its expression and compares bit for bit."""
        frame = request.getfixturevalue(frame_name)
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

        assert _declared_series(frame, "vwap") == expected


class TestEdgeFrameActuallyCarriesTheHazards:
    """A frame that quietly lost its hazards would make the parity run vacuous."""

    def test_zero_volume_bars_and_an_all_zero_session_exist(
        self, edge_frame: pd.DataFrame
    ) -> None:
        by_date = edge_frame.groupby(edge_frame["timestamp"].dt.date)["volume"]
        totals = by_date.sum()
        assert (edge_frame["volume"] == 0).sum() >= 30, "no zero-volume bars"
        assert (totals == 0).sum() == 1, "no entirely zero-volume session"

    def test_a_session_starts_with_zero_cumulative_volume(
        self, edge_frame: pd.DataFrame
    ) -> None:
        """The VWAP branch the witness documents: cumulative volume still 0."""
        day2 = edge_frame[edge_frame["timestamp"].dt.date == date(2026, 4, 7)]
        assert day2["volume"].to_numpy()[:25].sum() == 0

    def test_bars_start_exactly_at_the_configured_open(
        self, edge_frame: pd.DataFrame
    ) -> None:
        firsts = edge_frame.groupby(edge_frame["timestamp"].dt.date)["timestamp"].min()
        for stamp in firsts:
            assert (stamp.hour, stamp.minute) == (_OPEN_HOUR, _OPEN_MINUTE)

    def test_a_minute_gap_straddles_a_session_boundary(
        self, edge_frame: pd.DataFrame
    ) -> None:
        stamps = edge_frame["timestamp"].tolist()
        gaps = [
            (before, after)
            for before, after in zip(stamps, stamps[1:])
            if (after - before) != timedelta(minutes=1)
        ]
        crossing = [pair for pair in gaps if pair[0].date() != pair[1].date()]
        within = [pair for pair in gaps if pair[0].date() == pair[1].date()]
        assert crossing, "no gap across a session boundary"
        assert within, "no missing minute inside a session"
