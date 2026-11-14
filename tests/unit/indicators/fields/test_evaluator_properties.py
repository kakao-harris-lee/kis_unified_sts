"""Evaluator properties: no look-ahead, determinism, no silent coercion.

Roadmap §6 names these as what a catalog change must be pinned by: a reference
golden (``test_catalog_ops.py``), a look-ahead test, and same-input/same-output.
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.indicators.fields import (
    FieldBar,
    FieldEvalError,
    FieldEvaluator,
    FieldsDocument,
    FieldSpec,
    PublishSpec,
    ScaleSpec,
    evaluate_bars,
    op_spec,
    parse_fields_document,
)

from .conftest import bar, document, parsed

#: A declaration that exercises every op category at once, so one look-ahead or
#: determinism failure anywhere shows up here.
_FIELDS: list[dict[str, Any]] = [
    {"name": "open", "op": "bar.open"},
    {"name": "high", "op": "bar.high"},
    {"name": "low", "op": "bar.low"},
    {"name": "close", "op": "bar.close"},
    {"name": "volume", "op": "bar.volume"},
    {"name": "token", "op": "session.token"},
    {"name": "vwap", "op": "session.vwap_typical"},
    {"name": "atr", "op": "atr", "params": {"period": 5}},
    {
        "name": "mso",
        "op": "session.minutes_since_open",
        "params": {"open_hour": 9, "open_minute": 0},
    },
    {
        "name": "entry_window",
        "op": "between",
        "inputs": ["mso"],
        "params": {"lo": 3, "hi": 345},
    },
    {"name": "atr_pos", "op": "gt", "inputs": ["atr"], "params": {"const": 0}},
    {"name": "close_pos", "op": "gt", "inputs": ["close"], "params": {"const": 0}},
    {
        "name": "usable",
        "op": "all",
        "inputs": ["entry_window", "atr_pos", "close_pos"],
    },
    {
        "name": "vol_ref",
        "op": "gated_percentile",
        "inputs": ["atr"],
        "params": {"q": 90, "window": 20, "warmup": 4, "sample_when": "usable"},
    },
    {
        "name": "vol_ok_raw",
        "op": "ge",
        "inputs": ["atr", "vol_ref"],
        "params": {"mult": 0.9},
    },
    {"name": "vol_ok", "op": "permissive", "inputs": ["vol_ok_raw"]},
    {"name": "hi_vol", "op": "all", "inputs": ["usable", "vol_ok"]},
    {"name": "z", "op": "ratio_z", "inputs": ["close", "vwap", "atr"]},
    {"name": "abs_z", "op": "abs", "inputs": ["z"]},
    {
        "name": "recent_high",
        "op": "gated_max",
        "inputs": ["close"],
        "params": {"window": 5, "warmup": 3, "sample_when": "usable"},
    },
    {
        "name": "prev_close",
        "op": "gated_lag",
        "inputs": ["close"],
        "params": {"sample_when": "usable"},
    },
    {
        "name": "stall_raw",
        "op": "le",
        "inputs": ["close", "recent_high"],
        "params": {"mult": 1.0},
    },
    {"name": "stall_ok", "op": "permissive", "inputs": ["stall_raw"]},
    {"name": "turned_raw", "op": "gt", "inputs": ["close", "prev_close"]},
    {"name": "turned", "op": "permissive", "inputs": ["turned_raw"]},
    {"name": "eod", "op": "time_ge", "params": {"at": "15:40"}},
    {"name": "not_eod", "op": "not", "inputs": ["eod"]},
    {"name": "armed", "op": "any", "inputs": ["hi_vol", "turned"]},
]

_PUBLISH: list[dict[str, Any]] = [
    {"field": "open", "as": "open_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "high", "as": "high_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "low", "as": "low_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "close", "as": "close_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "volume", "as": "volume", "scale": {"mult": 1, "round": "half_up"}},
    {"field": "token", "as": "session_token"},
    {"field": "vwap", "as": "vwap_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "atr", "as": "atr_x100", "scale": {"mult": 100, "round": "half_up"}},
    {"field": "z", "as": "z_x1000", "scale": {"mult": 1000, "round": "toward_zero"}},
    {"field": "hi_vol"},
    {"field": "stall_ok"},
    {"field": "armed"},
    {"field": "not_eod"},
]


def _spec(
    name: str,
    op: str,
    inputs: tuple[str, ...] = (),
    params: dict[str, Any] | None = None,
) -> FieldSpec:
    """Build a :class:`FieldSpec` without going through the loader.

    Only for the runtime-guard tests below: the loader refuses the declarations
    they need, and a guard that is unreachable through the loader still has to
    be proved to work.
    """
    return FieldSpec(name=name, inputs=inputs, params=params or {}, op=op_spec(op))


#: ``raw`` is ``None`` on the first bar — the lag has no earlier sample yet.
_MISSING_CHAIN: tuple[FieldSpec, ...] = (
    _spec("close", "bar.close"),
    _spec("t", "gt", ("close",), {"const": 0.0}),
    _spec("lag", "gated_lag", ("close",), {"sample_when": "t"}),
    _spec("raw", "gt", ("close", "lag")),
)


def _bars(count: int, *, day: int = 11) -> list[FieldBar]:
    """A deterministic saw-tooth price path, two sessions when long enough."""
    bars: list[FieldBar] = []
    price = 100.0
    for index in range(count):
        price += ((index * 7) % 5 - 2) * 0.25
        width = 0.25 + ((index * 3) % 4) * 0.25
        bars.append(
            bar(
                index % 60,
                open=price,
                high=price + width,
                low=price - width,
                close=price + width / 2,
                volume=100.0 + (index % 11) * 10,
                day=day + index // 60,
                hour=9 + (index % 60) // 60,
            )
        )
    return bars


class TestNoLookAhead:
    def test_appending_future_bars_never_changes_earlier_records(self) -> None:
        """The whole point of the gated base class, measured end to end."""
        short = evaluate_bars(parsed(_FIELDS, _PUBLISH), _bars(40))
        long = evaluate_bars(parsed(_FIELDS, _PUBLISH), _bars(90))
        assert len(short) == 40
        for index, (early, late) in enumerate(zip(short, long)):
            assert early.bar == late.bar, f"bar {index} differs"
            assert dict(early.values) == dict(late.values), f"values at bar {index}"
            assert dict(early.published) == dict(late.published), f"publish {index}"

    def test_a_single_extra_bar_changes_nothing_before_it(self) -> None:
        base = _bars(30)
        extra = [
            *base,
            bar(30, open=1000.0, high=1200.0, low=900.0, close=1100.0, volume=9e6),
        ]
        before = evaluate_bars(parsed(_FIELDS, _PUBLISH), base)
        after = evaluate_bars(parsed(_FIELDS, _PUBLISH), extra)
        assert [dict(r.published) for r in before] == [
            dict(r.published) for r in after[:30]
        ]


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        bars = _bars(120)
        first = evaluate_bars(parsed(_FIELDS, _PUBLISH), bars)
        second = evaluate_bars(parsed(_FIELDS, _PUBLISH), bars)
        assert [dict(r.values) for r in first] == [dict(r.values) for r in second]
        assert [dict(r.published) for r in first] == [dict(r.published) for r in second]

    def test_streaming_and_batch_agree(self) -> None:
        bars = _bars(50)
        batch = evaluate_bars(parsed(_FIELDS, _PUBLISH), bars)
        evaluator = FieldEvaluator(parsed(_FIELDS, _PUBLISH))
        streamed = [evaluator.step(one) for one in bars]
        assert [dict(r.published) for r in batch] == [
            dict(r.published) for r in streamed
        ]

    def test_published_keys_follow_publish_order(self) -> None:
        records = evaluate_bars(parsed(_FIELDS, _PUBLISH), _bars(10))
        expected = [entry.get("as", entry["field"]) for entry in _PUBLISH]
        for record in records:
            assert list(record.published) == expected

    def test_every_published_value_is_int_bool_or_str(self) -> None:
        """A float field would be dropped at the kernel border, not reported."""
        for record in evaluate_bars(parsed(_FIELDS, _PUBLISH), _bars(30)):
            for key, value in record.published.items():
                assert isinstance(value, (bool, int, str)), f"{key} -> {value!r}"


class TestPublication:
    def test_scaling_uses_the_declared_mode(self) -> None:
        fields = [
            {"name": "close", "op": "bar.close"},
            {"name": "high", "op": "bar.high"},
            {"name": "low", "op": "bar.low"},
            {"name": "z", "op": "ratio_z", "inputs": ["low", "high", "close"]},
            {"name": "probe", "op": "gt", "inputs": ["z"], "params": {"const": -99}},
        ]
        publish = [
            {
                "field": "close",
                "as": "close_x100",
                "scale": {"mult": 100, "round": "half_up"},
            },
            {
                "field": "z",
                "as": "z_x1000",
                "scale": {"mult": 1000, "round": "toward_zero"},
            },
        ]
        # close = 559.455 -> half_up 55946; z = (8 - 12) / 559.455 is negative
        # and truncates TOWARD zero, not down.
        bars = [bar(0, high=12.0, low=8.0, close=559.455)]
        record = evaluate_bars(parsed(fields, publish), bars)[0]
        assert record.published["close_x100"] == 55946
        assert record.published["z_x1000"] == -7  # -4/559.455 = -0.007149...


class TestRefusalsAtRuntime:
    def test_ratio_z_by_zero_names_the_bar_and_the_divisor(self) -> None:
        """The legacy contract: ``vwap_extension_z`` raises at ``atr == 0``
        rather than returning a fabricated extreme. Which bars a producer then
        OMITS stays the producer's decision (``_inputs_unusable``)."""
        fields = [
            {"name": "close", "op": "bar.close"},
            {"name": "high", "op": "bar.high"},
            {"name": "atr", "op": "atr", "params": {"period": 3}},
            {"name": "z", "op": "ratio_z", "inputs": ["close", "high", "atr"]},
            {"name": "probe", "op": "gt", "inputs": ["z"], "params": {"const": -99}},
        ]
        flat = [
            bar(index, open=10.0, high=10.0, low=10.0, close=10.0, volume=100.0)
            for index in range(3)
        ]
        with pytest.raises(FieldEvalError, match=r"'atr' = 0"):
            evaluate_bars(parsed(fields), flat)

    def test_a_non_finite_bar_is_refused_at_construction(self) -> None:
        with pytest.raises(FieldEvalError, match="non-finite bar"):
            FieldBar.create(
                "2026-11-11 09:00",
                open=1.0,
                high=float("nan"),
                low=1.0,
                close=1.0,
                volume=1.0,
            )

    def test_a_missing_value_reaching_all_is_refused_on_the_bar(self) -> None:
        """The runtime BACKSTOP behind the loader's "may be missing" refusal.

        The loader now refuses this declaration, so it cannot arrive through
        ``fields.yaml``; the guard is kept and exercised on a hand-built
        document because "a missing value is not False" has to hold wherever a
        ``FieldsDocument`` comes from.
        """
        forced = FieldsDocument(
            fields=(*_MISSING_CHAIN, _spec("bad", "all", ("t", "raw"))),
            publish=(PublishSpec(field="bad", name="bad", scale=None),),
        )
        with pytest.raises(FieldEvalError, match="is not False"):
            evaluate_bars(forced, [bar(0)])

    def test_a_missing_sample_when_is_refused_on_the_bar(self) -> None:
        """Same backstop for a ``sample_when`` gate with no value."""
        forced = FieldsDocument(
            fields=(
                *_MISSING_CHAIN,
                _spec(
                    "gated",
                    "gated_max",
                    ("close",),
                    {"window": 3, "warmup": 1, "sample_when": "raw"},
                ),
                _spec("out", "permissive", ("t",)),
            ),
            publish=(PublishSpec(field="out", name="out", scale=None),),
        )
        with pytest.raises(FieldEvalError, match="sample_when has no value"):
            evaluate_bars(forced, [bar(0)])

    def test_a_missing_published_value_is_refused(self) -> None:
        """Unreachable through the loader (it refuses a non-definite publish),
        so the guard is exercised on a hand-built document — the evaluator must
        never emit a journal line with a hole in it."""
        loaded = parse_fields_document(
            document(
                [
                    {"name": "close", "op": "bar.close"},
                    {
                        "name": "pos",
                        "op": "gt",
                        "inputs": ["close"],
                        "params": {"const": 0},
                    },
                    {
                        "name": "lagged",
                        "op": "gated_lag",
                        "inputs": ["close"],
                        "params": {"sample_when": "pos"},
                    },
                    {"name": "probe", "op": "permissive", "inputs": ["pos"]},
                ]
            )
        )
        forced = FieldsDocument(
            fields=loaded.fields,
            publish=(
                PublishSpec(
                    field="lagged",
                    name="lagged_x100",
                    scale=ScaleSpec(mult=100, rounding="half_up"),
                ),
            ),
        )
        with pytest.raises(FieldEvalError, match="has no value on this bar"):
            evaluate_bars(forced, [bar(0)])
