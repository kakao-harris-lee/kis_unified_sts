"""Per-op goldens: every ``tos-field-catalog/1`` op against a hand computation."""

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


class TestCatalogShape:
    def test_version(self) -> None:
        assert CATALOG_VERSION == "tos-field-catalog/1"

    def test_is_exactly_the_plan_table(self) -> None:
        """§2.3's table, op for op, plus `const`, `rsi` and `williams_r`."""
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
            "const",
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
            "rsi",
            "session.minutes_since_open",
            "session.token",
            "session.vwap_typical",
            "time_ge",
            "williams_r",
        }

    def test_no_op_carries_a_strategy_name(self) -> None:
        """Roadmap §5 risk 2: ops differ by parameters, never by strategy."""
        banned = (
            "setup",
            "reversion",
            "reversal",
            "hi_vol",
            "stall",
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
            (8, 45, 0.0),
            (9, 0, 15.0),
            (9, 3, 18.0),
            (14, 30, 345.0),
            (8, 30, -15.0),
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
        bars = [bar(20, hour=9)]
        assert _last(futures, bars)["mso"] == 35.0
        assert _last(stock, bars)["mso"] == 20.0


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
        assert [v["atr"] for v in _values(self.FIELDS, bars)] == [2.0, 2.0]

    def test_period_is_required(self) -> None:
        assert CATALOG["atr"].required_params == frozenset({"period"})


class TestRsi:
    """Hand goldens, exact in binary. TA-Lib parity is ``test_talib_reference``."""

    FIELDS = [
        {"name": "rsi", "op": "rsi", "params": {"period": 2}},
        {"name": "raw", "op": "gt", "inputs": ["rsi"], "params": {"const": 0}},
        {"name": "probe", "op": "permissive", "inputs": ["raw"]},
    ]

    CLOSES = (10.0, 13.0, 12.0, 14.0)

    def _bars(self) -> list[FieldBar]:
        return [
            bar(index, open=close, high=close + 1.0, low=close - 1.0, close=close)
            for index, close in enumerate(self.CLOSES)
        ]

    def test_golden(self) -> None:
        series = [values["rsi"] for values in _values(self.FIELDS, self._bars())]
        assert series == [None, None, 75.0, 87.5]

    def test_the_first_period_bars_have_no_value(self) -> None:
        """``period`` changes need ``period + 1`` closes — never a neutral 50."""
        fields = [
            {"name": "rsi", "op": "rsi", "params": {"period": 5}},
            {"name": "raw", "op": "gt", "inputs": ["rsi"], "params": {"const": 0}},
            {"name": "probe", "op": "permissive", "inputs": ["raw"]},
        ]
        bars = [
            bar(
                index,
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.0 + index,
            )
            for index in range(8)
        ]
        series = [values["rsi"] for values in _values(fields, bars)]
        assert series[:5] == [None] * 5
        assert series[5] == 100.0

    def test_only_the_close_moves_it(self) -> None:
        """RSI reads closes; a wild high or low on the same bar changes nothing."""
        narrow = _values(self.FIELDS, self._bars())
        wide = _values(
            self.FIELDS,
            [
                bar(index, open=close, high=close + 99.0, low=close - 99.0, close=close)
                for index, close in enumerate(self.CLOSES)
            ],
        )
        assert [v["rsi"] for v in narrow] == [v["rsi"] for v in wide]

    def test_period_is_required(self) -> None:
        assert CATALOG["rsi"].required_params == frozenset({"period"})


class TestWilliamsR:
    """Hand goldens on a window exactly 100 wide, where %R is exact in binary."""

    FIELDS = [
        {"name": "wr", "op": "williams_r", "params": {"period": 2}},
        {"name": "raw", "op": "lt", "inputs": ["wr"], "params": {"const": 0}},
        {"name": "probe", "op": "permissive", "inputs": ["raw"]},
    ]

    BARS = (
        (200.0, 150.0, 180.0),
        (190.0, 100.0, 175.0),
        (200.0, 160.0, 170.0),
        (260.0, 160.0, 200.0),
    )

    def _bars(self) -> list[FieldBar]:
        return [
            bar(index, open=close, high=high, low=low, close=close)
            for index, (high, low, close) in enumerate(self.BARS)
        ]

    def test_golden(self) -> None:
        series = [values["wr"] for values in _values(self.FIELDS, self._bars())]
        assert series == [None, -25.0, -30.0, -60.0]

    def test_the_current_bar_is_in_its_own_window(self) -> None:
        """Unlike ``gated_*``: %R is a position within a window that includes now."""
        bars = [
            bar(0, open=150.0, high=200.0, low=100.0, close=175.0),
            bar(1, open=150.0, high=200.0, low=100.0, close=175.0),
        ]
        assert _last(self.FIELDS, bars)["wr"] == -25.0

    def test_at_the_window_extremes(self) -> None:
        """Close at the window high is 0, at its low is -100."""
        at_high = [
            bar(0, open=150.0, high=200.0, low=100.0, close=200.0),
            bar(1, open=150.0, high=200.0, low=100.0, close=200.0),
        ]
        at_low = [
            bar(0, open=150.0, high=200.0, low=100.0, close=100.0),
            bar(1, open=150.0, high=200.0, low=100.0, close=100.0),
        ]
        assert _last(self.FIELDS, at_high)["wr"] == 0.0
        assert _last(self.FIELDS, at_low)["wr"] == -100.0

    def test_period_is_required(self) -> None:
        assert CATALOG["williams_r"].required_params == frozenset({"period"})


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
        assert series[3] == 15.0

    def test_zero_volume_session_falls_back_to_the_close(self) -> None:
        bars = [bar(0, high=10.0, low=8.0, close=9.25, volume=0.0)]
        assert _last(self.FIELDS, bars)["vwap"] == 9.25


class TestArithmeticOps:
    def test_ratio_z_golden(self) -> None:
        fields = [
            {"name": "h", "op": "bar.high"},
            {"name": "c", "op": "bar.close"},
            {"name": "lo", "op": "bar.low"},
            {"name": "z", "op": "ratio_z", "inputs": ["h", "c", "lo"]},
            {"name": "probe", "op": "gt", "inputs": ["z"], "params": {"const": 0}},
        ]
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
            ("ge", 1.5, True),
            ("gt", 1.5, False),
            ("le", 1.5, True),
            ("lt", 1.5, False),
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
        assert _compare("gt", {"const": 4.0, "mult": 2.0}, ["h"]) is True
        assert _compare("gt", {"const": 7.0, "mult": 2.0}, ["h"]) is False

    @pytest.mark.parametrize(
        ("lo", "hi", "expected"),
        [
            (10.0, 20.0, True),
            (0.0, 10.0, True),
            (10.0, 10.0, True),
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
            ("15:40", 15, 40, True),
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


class TestConst:
    FIELDS = [
        {"name": "one", "op": "const", "params": {"value": 1.0}},
        {"name": "probe", "op": "gt", "inputs": ["one"], "params": {"const": 0}},
    ]

    def test_is_the_declared_value(self) -> None:
        assert _last(self.FIELDS, [bar(0)])["one"] == 1.0

    @pytest.mark.parametrize("value", [0.0, 1.0, -2.5, 0.2, 1e9, -1e-9])
    def test_any_finite_value(self, value: float) -> None:
        fields = [
            {"name": "k", "op": "const", "params": {"value": value}},
            {"name": "probe", "op": "gt", "inputs": ["k"], "params": {"const": -1e18}},
        ]
        assert _last(fields, [bar(0)])["k"] == value

    def test_same_on_every_bar(self) -> None:
        values = _values(self.FIELDS, [bar(i) for i in range(5)])
        assert [row["one"] for row in values] == [1.0] * 5

    def test_divisor_of_one_makes_ratio_z_an_exact_difference(self) -> None:
        """Why the op exists: ``x / 1.0 == x`` in IEEE-754, so ``ratio_z`` with"""
        fields = [
            {"name": "one", "op": "const", "params": {"value": 1.0}},
            {"name": "h", "op": "bar.high"},
            {"name": "lo", "op": "bar.low"},
            {"name": "diff", "op": "ratio_z", "inputs": ["h", "lo", "one"]},
            {"name": "probe", "op": "gt", "inputs": ["diff"], "params": {"const": 0}},
        ]
        for high, low in ((12.25, 8.5), (0.3, 0.1), (1.7995, 1.5995), (100.1, 100.0)):
            bars = [bar(0, high=high, low=low, close=low)]
            assert _last(fields, bars)["diff"] == high - low

    def test_the_legacy_z_improvement_gate_is_reproducible(self) -> None:
        """``abs(prev_z) - abs(z) >= reversal_confirm_atr_mult`` — the shape"""
        fields = [
            {"name": "one", "op": "const", "params": {"value": 1.0}},
            {"name": "h", "op": "bar.high"},
            {"name": "lo", "op": "bar.low"},
            {"name": "improvement", "op": "ratio_z", "inputs": ["h", "lo", "one"]},
            {
                "name": "probe",
                "op": "ge",
                "inputs": ["improvement"],
                "params": {"const": 0.2},
            },
        ]
        assert _last(fields, [bar(0, high=1.25, low=1.0, close=1.0)])["probe"] is True
        assert _last(fields, [bar(0, high=1.125, low=1.0, close=1.0)])["probe"] is False
        assert (1.2 - 1.0) < 0.2
        assert _last(fields, [bar(0, high=1.2, low=1.0, close=1.0)])["probe"] is False


class TestRiskUnitField:
    """``tos-field-catalog/1`` already expresses ``max(k * ATR, floor)`` (TOS P4 S5).

    The kernel's sizing can read its per-unit risk from one admitted integer field
    (``order_construction_policy.yaml::_runtime.construction.sizing
    .per_unit_risk_field_key``), and plan §2 D6 puts the floor on that unit in the
    catalog rather than clamping the derived quantity in the kernel. No op was added
    for it: ``max(a, f) == (a + f + abs(a - f)) / 2`` is three ``ratio_z``, one
    ``abs`` and four ``const``, and the integer price scale is the ``publish`` scale.
    """

    #: k = 2, floor = 0.30 price units. ``inv_k`` is 1/k because ``ratio_z``
    #: divides: ``(atr - 0) / (1/k) == k * atr``.
    _FIELDS: list[dict[str, Any]] = [
        {"name": "atr", "op": "atr", "params": {"period": 14}},
        {"name": "zero", "op": "const", "params": {"value": 0.0}},
        {"name": "one", "op": "const", "params": {"value": 1.0}},
        {"name": "two", "op": "const", "params": {"value": 2.0}},
        {"name": "inv_k", "op": "const", "params": {"value": 0.5}},
        {"name": "neg_floor", "op": "const", "params": {"value": -0.30}},
        {"name": "floor", "op": "const", "params": {"value": 0.30}},
        {"name": "k_atr", "op": "ratio_z", "inputs": ["atr", "zero", "inv_k"]},
        {"name": "sum", "op": "ratio_z", "inputs": ["k_atr", "neg_floor", "one"]},
        {"name": "diff", "op": "ratio_z", "inputs": ["k_atr", "floor", "one"]},
        {"name": "abs_diff", "op": "abs", "inputs": ["diff"]},
        {"name": "neg_abs", "op": "ratio_z", "inputs": ["zero", "abs_diff", "one"]},
        {"name": "risk_unit", "op": "ratio_z", "inputs": ["sum", "neg_abs", "two"]},
    ]

    _PUBLISH: list[dict[str, Any]] = [
        {
            "field": "risk_unit",
            "as": "risk_unit_x100",
            "scale": {"mult": 100, "round": "half_up"},
        }
    ]

    def _published(self, *, high: float, low: float) -> int:
        """The published integer risk unit for a flat stream of ``high``/``low`` bars."""
        evaluator = FieldEvaluator(parsed(self._FIELDS, self._PUBLISH))
        bars = [bar(index, high=high, low=low, close=low) for index in range(20)]
        record = evaluator.run(bars)[-1]
        assert record.values["atr"] == pytest.approx(high - low)
        published = record.published["risk_unit_x100"]
        assert isinstance(published, int)
        return published

    def test_the_declared_multiple_of_atr_is_the_unit(self) -> None:
        """ATR 2.0 with k = 2 is 4.0 price units, published as 400 at scale 100."""
        assert self._published(high=101.0, low=99.0) == 400

    def test_the_declared_floor_binds_when_the_multiple_falls_below_it(self) -> None:
        """ATR 0.10 with k = 2 is 0.20, below the 0.30 floor — the floor is published."""
        assert self._published(high=100.10, low=100.00) == 30

    def test_the_floor_does_not_cap_a_unit_above_it(self) -> None:
        """``max`` is not ``min``: the boundary case equals the floor, not less."""
        assert self._published(high=100.15, low=100.00) == 30
        assert self._published(high=100.20, low=100.00) == 40
