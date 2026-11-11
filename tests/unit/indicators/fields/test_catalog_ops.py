"""Per-op goldens: every ``tos-field-catalog/1`` op against a hand computation.

Each value below is worked out from the op's definition on bars small enough to
do in the head, and chosen so the arithmetic is exact in binary (no tolerance:
P2-b compares byte for byte, so a tolerance here would hide the drift it is
supposed to catch).
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.indicators.fields import (
    CATALOG,
    CATALOG_VERSION,
    FieldBar,
    FieldEvaluator,
    ValueKind,
    known_op_names,
)

from .conftest import bar, parsed


def _values(fields: list[dict[str, Any]], bars: list[FieldBar]) -> list[dict[str, Any]]:
    """Run *fields* over *bars* and return each bar's field values."""
    evaluator = FieldEvaluator(parsed(fields))
    return [dict(record.values) for record in evaluator.run(bars)]


def _last(fields: list[dict[str, Any]], bars: list[FieldBar]) -> dict[str, Any]:
    return _values(fields, bars)[-1]


# ---------------------------------------------------------------------------
# Catalog shape
# ---------------------------------------------------------------------------


class TestCatalogShape:
    def test_version(self) -> None:
        assert CATALOG_VERSION == "tos-field-catalog/1"

    def test_is_exactly_the_plan_table(self) -> None:
        """§2.3's table, op for op. A new op is a reviewed catalog change."""
        assert set(known_op_names()) == {
            "abs",
            "all",
            "any",
            "atr",
            "bar.close",
            "bar.high",
            "bar.low",
            "bar.open",
            "bar.volume",
            "between",
            "gated_lag",
            "gated_max",
            "gated_min",
            "gated_percentile",
            "ge",
            "gt",
            "le",
            "lt",
            "not",
            "permissive",
            "ratio_z",
            "session.minutes_since_open",
            "session.token",
            "session.vwap_typical",
            "time_ge",
        }

    def test_no_op_carries_a_strategy_name(self) -> None:
        """Roadmap §5 risk 2: ops differ by parameters, never by strategy.

        The three Setup D gates are ``gated_percentile``/``gated_max``/
        ``gated_min`` plus comparisons — nothing in the catalog is named after
        the setup, the registry name, or any of its field names.
        """
        banned = (
            "setup",
            "vwap_reversion",
            "hi_vol",
            "stall",
            "reversal",
            "williams",
            "rsi_reversion",
            "_d_",
        )
        for name in known_op_names():
            lowered = name.lower()
            for token in banned:
                assert token not in lowered, f"op {name!r} carries a strategy name"

    def test_every_op_declares_what_it_returns(self) -> None:
        for spec in CATALOG.values():
            assert isinstance(spec.returns, ValueKind)
            assert spec.summary, f"op {spec.name!r} has no summary"


# ---------------------------------------------------------------------------
# Bar raw values
# ---------------------------------------------------------------------------


class TestBarOps:
    def test_raw_values_are_the_bar(self) -> None:
        fields = [
            {"name": "o", "op": "bar.open"},
            {"name": "h", "op": "bar.high"},
            {"name": "lo", "op": "bar.low"},
            {"name": "c", "op": "bar.close"},
            {"name": "v", "op": "bar.volume"},
            {"name": "probe", "op": "gt", "inputs": ["c"], "params": {"const": 0}},
        ]
        values = _last(
            fields,
            [bar(0, open=102.5, high=105.25, low=99.75, close=101.0, volume=1234.0)],
        )
        assert values["o"] == 102.5
        assert values["h"] == 105.25
        assert values["lo"] == 99.75
        assert values["c"] == 101.0
        assert values["v"] == 1234.0

    def test_session_token_is_the_kst_date(self) -> None:
        fields = [{"name": "probe", "op": "session.token"}]
        assert _last(fields, [bar(0, day=11)])["probe"] == "2026-11-11"
        assert _last(fields, [bar(0, day=12)])["probe"] == "2026-11-12"


class TestMinutesSinceOpen:
    FIELDS = [
        {
            "name": "mso",
            "op": "session.minutes_since_open",
            "params": {"open_hour": 8, "open_minute": 45},
        },
        {
            "name": "probe",
            "op": "gt",
            "inputs": ["mso"],
            "params": {"const": -1e9},
        },
    ]

    @pytest.mark.parametrize(
        ("hour", "minute", "expected"),
        [
            (8, 45, 0.0),  # at the open
            (9, 0, 15.0),  # 15 minutes in — the legacy's valid_minutes_min
            (9, 3, 18.0),
            (14, 30, 345.0),  # the legacy's no_entry_after cutoff
            (8, 30, -15.0),  # before the open: negative, never wrapped
        ],
    )
    def test_golden(self, hour: int, minute: int, expected: float) -> None:
        bars = [bar(minute, hour=hour)]
        assert _last(self.FIELDS, bars)["mso"] == expected

    def test_anchor_comes_from_params_not_from_a_default(self) -> None:
        """A 09:00 stock open and an 08:45 futures open differ by 15 minutes."""
        futures = [
            {
                "name": "mso",
                "op": "session.minutes_since_open",
                "params": {"open_hour": 8, "open_minute": 45},
            },
            {"name": "probe", "op": "gt", "inputs": ["mso"], "params": {"const": 0}},
        ]
        stock = [
            {
                "name": "mso",
                "op": "session.minutes_since_open",
                "params": {"open_hour": 9, "open_minute": 0},
            },
            {"name": "probe", "op": "gt", "inputs": ["mso"], "params": {"const": 0}},
        ]
        bars = [bar(20, hour=9)]  # 09:20
        assert _last(futures, bars)["mso"] == 35.0
        assert _last(stock, bars)["mso"] == 20.0


# ---------------------------------------------------------------------------
# Window values
# ---------------------------------------------------------------------------


class TestAtr:
    FIELDS = [
        {"name": "atr", "op": "atr", "params": {"period": 2}},
        {"name": "probe", "op": "gt", "inputs": ["atr"], "params": {"const": 0}},
    ]

    def test_partial_window_golden(self, hand_bars: list[FieldBar]) -> None:
        """TR = [2, 2, 4]; ATR(2) = [2/1, (2+2)/2, (2+4)/2]."""
        series = [values["atr"] for values in _values(self.FIELDS, hand_bars)]
        assert series == [2.0, 2.0, 3.0]

    def test_first_bar_true_range_is_high_minus_low(self) -> None:
        """No previous close exists at bar 0 — the replay's TR seed."""
        bars = [bar(0, high=12.0, low=8.0, close=10.0)]
        assert _last(self.FIELDS, bars)["atr"] == 4.0

    def test_true_range_uses_the_previous_close_across_sessions(self) -> None:
        """ATR is NOT reset per session — a stitched seed must advance it."""
        bars = [
            bar(0, high=10.0, low=8.0, close=9.0, day=11),
            bar(0, high=11.0, low=10.0, close=9.0, day=12),
        ]
        # bar 1 TR = max(11-10=1, |11-9|=2, |10-9|=1) = 2 -> ATR(2) = (2+2)/2
        assert [v["atr"] for v in _values(self.FIELDS, bars)] == [2.0, 2.0]

    def test_period_is_required(self) -> None:
        assert CATALOG["atr"].required_params == frozenset({"period"})


class TestSessionVwapTypical:
    FIELDS = [
        {"name": "vwap", "op": "session.vwap_typical"},
        {"name": "probe", "op": "gt", "inputs": ["vwap"], "params": {"const": 0}},
    ]

    def test_golden(self, hand_bars: list[FieldBar]) -> None:
        """tp = [9, 10, 10]; cumulative pv/v = [9, 3900/400, 9900/1000]."""
        series = [values["vwap"] for values in _values(self.FIELDS, hand_bars)]
        assert series == [9.0, 9.75, 9.9]

    def test_resets_on_the_session_boundary(self, hand_bars: list[FieldBar]) -> None:
        next_day = bar(0, high=20.0, low=10.0, close=15.0, volume=50.0, day=12)
        series = [
            values["vwap"] for values in _values(self.FIELDS, [*hand_bars, next_day])
        ]
        assert series[:3] == [9.0, 9.75, 9.9]
        assert series[3] == 15.0  # (20+10+15)/3, the new session's only bar

    def test_zero_volume_session_falls_back_to_the_close(self) -> None:
        bars = [bar(0, high=10.0, low=8.0, close=9.25, volume=0.0)]
        assert _last(self.FIELDS, bars)["vwap"] == 9.25


# ---------------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------------


class TestArithmeticOps:
    def test_ratio_z_golden(self) -> None:
        fields = [
            {"name": "h", "op": "bar.high"},
            {"name": "c", "op": "bar.close"},
            {"name": "lo", "op": "bar.low"},
            {"name": "z", "op": "ratio_z", "inputs": ["h", "c", "lo"]},
            {"name": "probe", "op": "gt", "inputs": ["z"], "params": {"const": 0}},
        ]
        # (12 - 10) / 8 = 0.25
        bars = [bar(0, high=12.0, low=8.0, close=10.0)]
        assert _last(fields, bars)["z"] == 0.25

    def test_ratio_z_is_signed(self) -> None:
        fields = [
            {"name": "h", "op": "bar.high"},
            {"name": "c", "op": "bar.close"},
            {"name": "lo", "op": "bar.low"},
            {"name": "z", "op": "ratio_z", "inputs": ["c", "h", "lo"]},
            {"name": "probe", "op": "gt", "inputs": ["z"], "params": {"const": -1}},
        ]
        # (10 - 12) / 8 = -0.25
        bars = [bar(0, high=12.0, low=8.0, close=10.0)]
        assert _last(fields, bars)["z"] == -0.25

    def test_abs_golden(self) -> None:
        fields = [
            {"name": "h", "op": "bar.high"},
            {"name": "c", "op": "bar.close"},
            {"name": "lo", "op": "bar.low"},
            {"name": "z", "op": "ratio_z", "inputs": ["c", "h", "lo"]},
            {"name": "az", "op": "abs", "inputs": ["z"]},
            {"name": "probe", "op": "gt", "inputs": ["az"], "params": {"const": 0}},
        ]
        bars = [bar(0, high=12.0, low=8.0, close=10.0)]
        values = _last(fields, bars)
        assert values["z"] == -0.25
        assert values["az"] == 0.25


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def _compare(op: str, params: dict[str, Any], inputs: list[str]) -> bool:
    fields = [
        {"name": "h", "op": "bar.high"},
        {"name": "c", "op": "bar.close"},
        {"name": "lo", "op": "bar.low"},
        {"name": "probe", "op": op, "inputs": inputs, "params": params},
    ]
    bars = [bar(0, high=12.0, low=8.0, close=10.0)]
    value = _last(fields, bars)["probe"]
    assert isinstance(value, bool)
    return value


class TestComparisonOps:
    @pytest.mark.parametrize(
        ("op", "const", "expected"),
        [
            ("gt", 9.0, True),
            ("gt", 10.0, False),
            ("gt", 11.0, False),
            ("ge", 10.0, True),
            ("ge", 10.5, False),
            ("lt", 10.0, False),
            ("lt", 10.5, True),
            ("le", 10.0, True),
            ("le", 9.5, False),
        ],
    )
    def test_against_a_const(self, op: str, const: float, expected: bool) -> None:
        """close = 10.0 against each boundary, including equality."""
        assert _compare(op, {"const": const}, ["c"]) is expected

    @pytest.mark.parametrize(
        ("op", "mult", "expected"),
        [
            # rhs = low * mult = 8 * 1.5 = 12; high = 12 -> equality
            ("ge", 1.5, True),
            ("gt", 1.5, False),
            ("le", 1.5, True),
            ("lt", 1.5, False),
            # rhs = 8 * 2.0 = 16
            ("lt", 2.0, True),
            ("gt", 2.0, False),
        ],
    )
    def test_against_a_field_times_mult(
        self, op: str, mult: float, expected: bool
    ) -> None:
        """This is the shape of the legacy high-vol gate: ``atr >= k * vol_ref``."""
        assert _compare(op, {"mult": mult}, ["h", "lo"]) is expected

    def test_const_times_mult(self) -> None:
        # rhs = 4.0 * 2.0 = 8.0; high = 12
        assert _compare("gt", {"const": 4.0, "mult": 2.0}, ["h"]) is True
        assert _compare("gt", {"const": 7.0, "mult": 2.0}, ["h"]) is False

    @pytest.mark.parametrize(
        ("lo", "hi", "expected"),
        [
            (10.0, 20.0, True),  # lower edge is inclusive
            (0.0, 10.0, True),  # upper edge is inclusive
            (10.0, 10.0, True),  # degenerate but valid
            (10.5, 20.0, False),
            (0.0, 9.5, False),
        ],
    )
    def test_between_is_inclusive_on_both_edges(
        self, lo: float, hi: float, expected: bool
    ) -> None:
        """``valid_minutes_min <= mso <= no_entry_after`` — both ends inclusive."""
        assert _compare("between", {"lo": lo, "hi": hi}, ["c"]) is expected

    @pytest.mark.parametrize(
        ("at", "hour", "minute", "expected"),
        [
            ("15:40", 15, 40, True),  # the EOD cutoff bar itself qualifies
            ("15:40", 15, 39, False),
            ("15:40", 15, 41, True),
            ("15:40:30", 15, 40, False),
            ("09:00", 15, 40, True),
        ],
    )
    def test_time_ge_golden(
        self, at: str, hour: int, minute: int, expected: bool
    ) -> None:
        fields = [{"name": "probe", "op": "time_ge", "params": {"at": at}}]
        assert _last(fields, [bar(minute, hour=hour)])["probe"] is expected


class TestBooleanOps:
    @pytest.mark.parametrize(
        ("op", "flags", "expected"),
        [
            ("all", (True, True, True), True),
            ("all", (True, False, True), False),
            ("all", (True,), True),
            ("any", (False, False, True), True),
            ("any", (False, False, False), False),
            ("not", (True,), False),
            ("not", (False,), True),
        ],
    )
    def test_golden(self, op: str, flags: tuple[bool, ...], expected: bool) -> None:
        # Each flag is a comparison of close (10.0) against a const that makes
        # it true or false, so the declaration stays inside the catalog.
        fields: list[dict[str, Any]] = [{"name": "c", "op": "bar.close"}]
        names = []
        for index, flag in enumerate(flags):
            name = f"f{index}"
            names.append(name)
            fields.append(
                {
                    "name": name,
                    "op": "gt",
                    "inputs": ["c"],
                    "params": {"const": 9.0 if flag else 11.0},
                }
            )
        fields.append({"name": "probe", "op": op, "inputs": names})
        bars = [bar(0, high=12.0, low=8.0, close=10.0)]
        assert _last(fields, bars)["probe"] is expected
