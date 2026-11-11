"""The gated ops: read-before-append, ``sample_when`` gating, warmup ``None``.

These three are the whole risk of the P2 port (plan §6, risk 1: "a difference in
``sample_when`` meaning makes ``hi_vol`` diverge from the warmup onward"), so
they are tested on the base class AND through a declaration, and the percentile
is pinned against the exact ``np.percentile`` call the legacy
``_vol_reference`` makes.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from shared.indicators.fields import (
    FieldBar,
    FieldEvalError,
    FieldEvaluator,
    FieldSpecError,
    GatedLag,
    GatedMax,
    GatedMin,
    GatedPercentile,
    parse_fields_document,
)

from .conftest import bar, document, parsed

# ---------------------------------------------------------------------------
# The base class invariants, directly
# ---------------------------------------------------------------------------


class TestReadBeforeAppend:
    def test_first_read_is_none_and_the_bar_is_not_in_its_own_window(self) -> None:
        gate = GatedMax(window=3, warmup=1, field="probe")
        # Bar 0: nothing sampled yet -> None, and 5.0 enters AFTER the read.
        assert gate.step(5.0, sample=True) is None
        assert gate.sample_count == 1
        # Bar 1 sees only bar 0.
        assert gate.step(1.0, sample=True) == 5.0
        # Bar 2 sees bars 0..1.
        assert gate.step(2.0, sample=True) == 5.0

    def test_min_mirrors_max(self) -> None:
        gate = GatedMin(window=3, warmup=1, field="probe")
        assert gate.step(5.0, sample=True) is None
        assert gate.step(1.0, sample=True) == 5.0
        assert gate.step(9.0, sample=True) == 1.0

    def test_window_cap_drops_the_oldest_sample(self) -> None:
        gate = GatedMax(window=2, warmup=1, field="probe")
        gate.step(9.0, sample=True)
        gate.step(1.0, sample=True)
        gate.step(2.0, sample=True)  # window is now [1.0, 2.0]; 9.0 dropped
        assert gate.step(0.0, sample=True) == 2.0

    def test_lag_is_the_last_sample_before_this_bar(self) -> None:
        """``prev_close`` in ``vwap_reversion.check``, read before the append."""
        gate = GatedLag(field="probe")
        assert gate.step(10.0, sample=True) is None
        assert gate.step(20.0, sample=True) == 10.0
        assert gate.step(30.0, sample=True) == 20.0


class TestWarmup:
    def test_none_until_warmup_samples_exist(self) -> None:
        gate = GatedPercentile(q=50.0, window=10, warmup=3, field="probe")
        assert gate.step(1.0, sample=True) is None  # 0 samples
        assert gate.step(2.0, sample=True) is None  # 1 sample
        assert gate.step(3.0, sample=True) is None  # 2 samples
        assert gate.step(4.0, sample=True) == 2.0  # 3 samples: median of 1,2,3

    def test_warmup_counts_samples_not_bars(self) -> None:
        gate = GatedMax(window=10, warmup=2, field="probe")
        for _ in range(5):
            assert gate.step(1.0, sample=False) is None
        assert gate.step(7.0, sample=True) is None  # still 0 samples
        assert gate.step(3.0, sample=True) is None  # 1 sample
        assert gate.step(0.0, sample=True) == 7.0  # 2 samples


class TestSampleGating:
    def test_an_ungated_bar_is_read_but_contributes_nothing(self) -> None:
        gate = GatedMax(window=5, warmup=1, field="probe")
        gate.step(5.0, sample=True)
        assert gate.step(100.0, sample=False) == 5.0
        assert gate.sample_count == 1
        assert gate.step(1.0, sample=True) == 5.0  # 100.0 never entered
        assert gate.step(0.0, sample=True) == 5.0

    def test_a_sampled_missing_value_is_refused(self) -> None:
        gate = GatedMax(window=5, warmup=1, field="probe")
        with pytest.raises(FieldEvalError, match="causal window"):
            gate.step(None, sample=True)

    def test_an_ungated_missing_value_is_fine(self) -> None:
        gate = GatedMax(window=5, warmup=1, field="probe")
        assert gate.step(None, sample=False) is None
        assert gate.sample_count == 0


class TestPercentileMatchesTheLegacyCall:
    @pytest.mark.parametrize("q", [0.0, 25.0, 50.0, 90.0, 100.0])
    def test_same_function_same_input_order(self, q: float) -> None:
        """``np.percentile(window, q)`` with its default interpolation.

        The legacy reference is ``np.percentile(self._atr_window,
        self.config.vol_percentile)``; the plan forbids a tolerance here (§6,
        risk 2), so this asserts bit equality against that same call.
        """
        samples = [0.31, 0.12, 0.44, 0.07, 0.29, 0.55, 0.18]
        gate = GatedPercentile(q=q, window=len(samples), warmup=1, field="probe")
        for value in samples:
            gate.step(value, sample=True)
        # One more bar reads the full window without changing it.
        observed = gate.step(0.99, sample=False)
        assert observed == float(np.percentile(samples, q))

    def test_interpolated_golden(self) -> None:
        """q=90 over [1, 2, 3]: index 0.9*(3-1) = 1.8 -> 2 + 0.8*(3-2) = 2.8."""
        gate = GatedPercentile(q=90.0, window=3, warmup=3, field="probe")
        gate.step(1.0, sample=True)
        gate.step(2.0, sample=True)
        gate.step(3.0, sample=True)
        assert gate.step(0.0, sample=False) == pytest.approx(2.8)


class TestConstructionRefusals:
    def test_window_below_one(self) -> None:
        with pytest.raises(FieldEvalError, match="window must be >= 1"):
            GatedMax(window=0, warmup=1, field="probe")

    def test_warmup_below_one(self) -> None:
        with pytest.raises(FieldEvalError, match="warmup must be >= 1"):
            GatedMax(window=5, warmup=0, field="probe")

    def test_warmup_above_window_is_a_silently_dead_gate(self) -> None:
        with pytest.raises(FieldEvalError, match="permanently None"):
            GatedMax(window=5, warmup=6, field="probe")

    def test_percentile_out_of_range(self) -> None:
        with pytest.raises(FieldEvalError, match=r"q must be in \[0, 100\]"):
            GatedPercentile(q=101.0, window=5, warmup=1, field="probe")


# ---------------------------------------------------------------------------
# The same invariants through a declaration
# ---------------------------------------------------------------------------

#: A declaration shaped like the legacy high-vol gate: the window only advances
#: on bars the chain would have reached (``usable``), the reference is ``None``
#: during warmup, and ``permissive`` is what makes the gate non-blocking then.
_HI_VOL_FIELDS: list[dict[str, Any]] = [
    {"name": "close", "op": "bar.close"},
    {"name": "atr", "op": "atr", "params": {"period": 2}},
    {
        "name": "mso",
        "op": "session.minutes_since_open",
        "params": {"open_hour": 9, "open_minute": 0},
    },
    {
        "name": "entry_window",
        "op": "between",
        "inputs": ["mso"],
        "params": {"lo": 2, "hi": 345},
    },
    {"name": "atr_pos", "op": "gt", "inputs": ["atr"], "params": {"const": 0}},
    {"name": "close_pos", "op": "gt", "inputs": ["close"], "params": {"const": 0}},
    {"name": "usable", "op": "all", "inputs": ["entry_window", "atr_pos", "close_pos"]},
    {
        "name": "vol_ref",
        "op": "gated_percentile",
        "inputs": ["atr"],
        "params": {"q": 90, "window": 4, "warmup": 2, "sample_when": "usable"},
    },
    {
        "name": "vol_ok_raw",
        "op": "ge",
        "inputs": ["atr", "vol_ref"],
        "params": {"mult": 1.0},
    },
    {
        "name": "vol_ok",
        "op": "permissive",
        "inputs": ["vol_ok_raw"],
        "params": {"when_missing": True},
    },
    {"name": "hi_vol", "op": "all", "inputs": ["usable", "vol_ok"]},
]


def _ladder() -> list[FieldBar]:
    """Bars 09:00..09:07 with a rising then collapsing range."""
    ranges = [1.0, 1.0, 1.0, 1.0, 4.0, 0.25, 0.25, 0.25]
    bars = []
    for minute, width in enumerate(ranges):
        bars.append(
            bar(
                minute,
                open=100.0,
                high=100.0 + width,
                low=100.0,
                close=100.0,
                volume=100.0,
            )
        )
    return bars


class TestDeclaredGate:
    def test_warmup_bars_are_permissive_not_blocked(self) -> None:
        """The legacy promise: the gate is never silently dead during warmup."""
        records = FieldEvaluator(parsed(_HI_VOL_FIELDS)).run(_ladder())
        # 09:00 and 09:01 are outside the entry window (lo=2) or pre-warmup.
        assert records[0].values["vol_ref"] is None
        assert records[0].values["vol_ok_raw"] is None
        assert records[0].values["vol_ok"] is True

    def test_the_window_only_advances_on_gated_bars(self) -> None:
        """Bars 09:00 and 09:01 fail ``entry_window`` (lo=2), so they are
        read but never sampled — the reference therefore stays ``None`` two
        bars longer than a bar count would suggest."""
        records = FieldEvaluator(parsed(_HI_VOL_FIELDS)).run(_ladder())
        gated = [bool(record.values["usable"]) for record in records]
        assert gated == [False, False, True, True, True, True, True, True]
        refs = [record.values["vol_ref"] for record in records]
        # Samples enter at 09:02 and 09:03; warmup=2 is first met at 09:04.
        assert refs[:4] == [None, None, None, None]
        assert refs[4] is not None

    def test_permissive_when_missing_false_blocks_during_warmup(self) -> None:
        fields = [
            dict(spec) for spec in _HI_VOL_FIELDS[:-1] if spec["name"] != "vol_ok"
        ]
        fields.append(
            {
                "name": "vol_ok",
                "op": "permissive",
                "inputs": ["vol_ok_raw"],
                "params": {"when_missing": False},
            }
        )
        fields.append({"name": "hi_vol", "op": "all", "inputs": ["usable", "vol_ok"]})
        records = FieldEvaluator(parsed(fields)).run(_ladder())
        assert records[0].values["vol_ok"] is False

    def test_permissive_defaults_to_true(self) -> None:
        fields = [
            dict(spec) for spec in _HI_VOL_FIELDS[:-1] if spec["name"] != "vol_ok"
        ]
        fields.append({"name": "vol_ok", "op": "permissive", "inputs": ["vol_ok_raw"]})
        fields.append({"name": "hi_vol", "op": "all", "inputs": ["usable", "vol_ok"]})
        records = FieldEvaluator(parsed(fields)).run(_ladder())
        assert records[0].values["vol_ok"] is True

    def test_a_missing_value_reaching_all_is_refused_not_read_as_false(self) -> None:
        """Drop the ``permissive`` and the declaration refuses the warmup bar."""
        fields = [
            spec for spec in _HI_VOL_FIELDS if spec["name"] not in {"vol_ok", "hi_vol"}
        ]
        fields.append(
            {"name": "hi_vol", "op": "all", "inputs": ["usable", "vol_ok_raw"]}
        )
        evaluator = FieldEvaluator(parsed(fields))
        with pytest.raises(FieldEvalError, match="is not False"):
            evaluator.run(_ladder())

    def test_a_missing_sample_when_is_refused(self) -> None:
        """``sample_when`` must be definite: a propagated ``None`` is a bug."""
        fields: list[dict[str, Any]] = [
            {"name": "close", "op": "bar.close"},
            {"name": "atr", "op": "atr", "params": {"period": 2}},
            {"name": "always", "op": "gt", "inputs": ["close"], "params": {"const": 0}},
            {
                "name": "lagged",
                "op": "gated_lag",
                "inputs": ["atr"],
                "params": {"sample_when": "always"},
            },
            {"name": "maybe", "op": "gt", "inputs": ["atr", "lagged"]},
            {
                "name": "probe",
                "op": "gated_max",
                "inputs": ["atr"],
                "params": {"window": 3, "warmup": 1, "sample_when": "maybe"},
            },
            {"name": "out", "op": "permissive", "inputs": ["maybe"]},
        ]
        evaluator = FieldEvaluator(parsed(fields))
        with pytest.raises(FieldEvalError, match="sample_when has no value"):
            evaluator.run(_ladder())

    def test_gated_fields_cannot_be_published_directly(self) -> None:
        with pytest.raises(FieldSpecError, match="no value during warmup"):
            parse_fields_document(
                document(
                    _HI_VOL_FIELDS,
                    [
                        {
                            "field": "vol_ref",
                            "as": "vol_ref_x100",
                            "scale": {"mult": 100, "round": "half_up"},
                        }
                    ],
                )
            )
