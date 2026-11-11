"""P2-b — the three trees' ``fields.yaml`` and the equivalence harness.

Two things are pinned here:

1. **The duplicated parameters agree.** While P2-b runs, every threshold and
   window lives in TWO places: the legacy strategy YAML (which the legacy-driven
   producer reads) and each tree's ``fields.yaml`` (which the declarative
   evaluator reads). Plan §6 risk 4 names the drift that costs; this module is
   the test that forbids it. The source of truth moves to ``fields.yaml`` in
   P2-c, and then these assertions become the migration's checklist.
2. **The harness actually finds a difference when there is one.** A comparison
   that cannot fail proves nothing, so the end-to-end case is run once clean and
   once against a deliberately perturbed declaration.

The end-to-end case is hermetic: a synthetic frame, no Parquet, no network. The
real 20-day and recorded-session runs are measurements in the PR body, not tests
(CLAUDE.md R7).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from shared.indicators.fields import load_fields_file, parse_fields_document
from shared.instruments.contract_spec import ContractSpec
from tools.tos_cp3 import fields_equivalence as fe
from tools.tos_cp3.produce_fields import (
    FIELD_ORDER,
    OpenAnchor,
    load_strategy_inputs,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_YAML = (
    REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)
TREES = ("cp3-setup-d-long", "cp3-setup-d-short", "cp3-setup-d-stock-005930")

#: Each tree's open anchor, and the producer config that is its source.
TREE_ANCHORS = {
    "cp3-setup-d-long": (8, 45),
    "cp3-setup-d-short": (8, 45),
    "cp3-setup-d-stock-005930": (9, 0),
}

#: The one field of ``FIELD_ORDER`` this catalog version cannot express — see
#: the ⚠ block at the top of each ``fields.yaml``.
NOT_YET_REPRODUCED = frozenset({"reversal_ok"})


def _fields_yaml(tree: str) -> Path:
    return REPO_ROOT / "config" / "tos_runtime" / tree / "fields.yaml"


def _by_name(document: Any) -> dict[str, Any]:
    return {spec.name: spec for spec in document.fields}


@pytest.fixture(scope="module")
def strategy() -> Any:
    return load_strategy_inputs(STRATEGY_YAML)


# ---------------------------------------------------------------------------
# 1. The duplicated parameters agree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree", TREES)
class TestDeclarationMatchesTheStrategyYaml:
    def test_it_loads(self, tree: str) -> None:
        document = load_fields_file(_fields_yaml(tree))
        assert document.fields
        assert document.publish

    def test_entry_window_bounds(self, tree: str, strategy: Any) -> None:
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["entry_window"]
        config = strategy.entry_config
        assert spec.params["lo"] == float(config.valid_minutes_min)
        assert spec.params["hi"] == float(config.no_entry_after_minutes_since_open)

    def test_vol_window(self, tree: str, strategy: Any) -> None:
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["vol_ref"]
        config = strategy.entry_config
        assert spec.params["window"] == config.vol_window_bars
        assert spec.params["warmup"] == config.vol_warmup_bars
        assert spec.params["q"] == float(config.vol_percentile)
        assert spec.op_name == "gated_percentile"

    def test_min_atr_ratio(self, tree: str, strategy: Any) -> None:
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["vol_ok_raw"]
        assert spec.params["mult"] == float(strategy.entry_config.min_atr_ratio)

    def test_range_window(self, tree: str, strategy: Any) -> None:
        document = load_fields_file(_fields_yaml(tree))
        config = strategy.entry_config
        for name in ("recent_high", "recent_low"):
            spec = _by_name(document)[name]
            assert spec.params["window"] == config.range_window_bars
            assert spec.params["warmup"] == config.range_warmup_bars

    def test_extreme_threshold_both_signs(self, tree: str, strategy: Any) -> None:
        document = _by_name(load_fields_file(_fields_yaml(tree)))
        extreme = float(strategy.entry_config.extreme_atr_mult)
        assert document["z_short_side"].params["const"] == extreme
        assert document["z_long_side"].params["const"] == -extreme

    def test_stall_buffer(self, tree: str, strategy: Any) -> None:
        document = _by_name(load_fields_file(_fields_yaml(tree)))
        buffer = float(strategy.entry_config.stall_buffer_atr_mult)
        assert document["stall_short_raw"].params["const"] == buffer
        assert document["stall_long_raw"].params["const"] == buffer

    def test_vwap_revert_band(self, tree: str, strategy: Any) -> None:
        """The band's source is the producer's documented fallback."""
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["vwap_reverted"]
        assert spec.params["const"] == strategy.vwap_revert_band
        assert "reversal_confirm_atr_mult" in strategy.vwap_revert_band_source

    def test_eod_cutoff(self, tree: str, strategy: Any) -> None:
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["eod"]
        assert spec.params["at"] == strategy.exit_config.eod_close_time
        assert strategy.exit_config.eod_close_enabled is True

    def test_atr_period(self, tree: str) -> None:
        """14 — the replay's ``_ATR_PERIOD``, which the witness pins."""
        from shared.backtest.market_context_replay import _ATR_PERIOD

        spec = _by_name(load_fields_file(_fields_yaml(tree)))["atr"]
        assert spec.params["period"] == _ATR_PERIOD

    def test_open_anchor_is_this_tree_s(self, tree: str) -> None:
        spec = _by_name(load_fields_file(_fields_yaml(tree)))["mso"]
        hour, minute = TREE_ANCHORS[tree]
        assert (spec.params["open_hour"], spec.params["open_minute"]) == (hour, minute)

    def test_publishes_field_order_minus_the_one_gap(self, tree: str) -> None:
        document = load_fields_file(_fields_yaml(tree))
        published = tuple(entry.name for entry in document.publish)
        expected = tuple(name for name in FIELD_ORDER if name not in NOT_YET_REPRODUCED)
        assert published == expected

    def test_no_trend_field_because_the_gate_ships_off(
        self, tree: str, strategy: Any
    ) -> None:
        """The producer refuses a trend-filter run, so no trend field exists."""
        assert strategy.entry_config.trend_filter_enabled is False
        document = load_fields_file(_fields_yaml(tree))
        assert not [spec for spec in document.fields if "trend" in spec.name]


class TestTreesDifferOnlyByTheirAnchor:
    def test_long_and_short_declarations_are_identical_apart_from_the_header(
        self,
    ) -> None:
        """Direction lives in the DSL's threshold sign, never in the fields."""
        long_doc = parse_fields_document(
            yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        )
        short_doc = parse_fields_document(
            yaml.safe_load(_fields_yaml("cp3-setup-d-short").read_text("utf-8"))
        )
        assert [
            (s.name, s.op_name, s.inputs, dict(s.params)) for s in long_doc.fields
        ] == [(s.name, s.op_name, s.inputs, dict(s.params)) for s in short_doc.fields]

    def test_stock_differs_from_futures_in_exactly_one_parameter(self) -> None:
        futures = _by_name(load_fields_file(_fields_yaml("cp3-setup-d-long")))
        stock = _by_name(load_fields_file(_fields_yaml("cp3-setup-d-stock-005930")))
        assert set(futures) == set(stock)
        differing = {
            name
            for name in futures
            if dict(futures[name].params) != dict(stock[name].params)
        }
        assert differing == {"mso"}


# ---------------------------------------------------------------------------
# 2. The harness: hermetic end-to-end, and it can fail
# ---------------------------------------------------------------------------


def _frame(sessions: int = 7, bars_per_session: int = 360) -> pd.DataFrame:
    """Synthetic 1-minute futures bars from the 08:45 open, volatile enough
    that the Setup D gates actually change state across the frame."""
    rng = np.random.RandomState(7)
    rows = []
    price = 350.0
    day = datetime(2026, 7, 1, 8, 45, 0)
    for session in range(sessions):
        start = day + timedelta(days=session)
        for index in range(bars_per_session):
            price += float(rng.normal(0.0, 0.25))
            spread = float(abs(rng.normal(0.15, 0.12))) + 0.01
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=index),
                    "open": price - 0.05,
                    "high": price + spread,
                    "low": price - spread,
                    "close": price,
                    "volume": float(rng.randint(40, 600)),
                }
            )
    return pd.DataFrame(rows)


def _inputs(document: Any, df: pd.DataFrame, strategy: Any) -> fe.Inputs:
    days = sorted({stamp.date() for stamp in df["timestamp"]})
    return fe.Inputs(
        df=df,
        symbol="101S6000",
        asset_class="futures",
        strategy=strategy,
        contract_spec=ContractSpec(
            name="equivalence",
            multiplier_krw_per_point=250_000,
            tick_size_points=0.05,
            tick_value_krw=12_500,
            commission_rate=0.00003,
            symbol_prefix="101",
        ),
        anchor=OpenAnchor(8, 45, "test"),
        document=document,
        emit_days=frozenset(days[4:]),
    )


class TestHarnessEndToEnd:
    def test_the_shipped_declaration_reproduces_the_legacy_fields(
        self, strategy: Any
    ) -> None:
        """The P2-b claim, on a frame small enough for CI."""
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        result = fe.compare(_inputs(document, _frame(), strategy), mode="window")
        assert result.bars_compared > 500
        assert result.cells_compared > 7000
        assert result.divergences == (), result.render()
        assert result.omitted_lists_agree
        assert result.bar_sets_agree
        assert result.passed, result.render()

    def test_the_causal_window_is_filled_before_the_compared_days(
        self, strategy: Any
    ) -> None:
        """Measured, never assumed — the live producer's own seed condition."""
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        result = fe.compare(_inputs(document, _frame(), strategy), mode="window")
        assert result.capacity_required == strategy.entry_config.vol_window_bars
        assert result.capacity_before_first_compared_day >= result.capacity_required

    def test_a_perturbed_threshold_is_caught(self, strategy: Any) -> None:
        """A comparison that cannot fail proves nothing.

        One threshold is moved by a hair — ``min_atr_ratio`` 0.9 -> 0.91 — and
        the harness must name ``hi_vol`` (and the chain field below it).
        """
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        for entry in raw["fields"]:
            if entry["name"] == "vol_ok_raw":
                entry["params"]["mult"] = 0.91
        document = parse_fields_document(raw)
        result = fe.compare(_inputs(document, _frame(), strategy), mode="window")
        assert not result.passed
        assert {d.published_field for d in result.divergences} & {"hi_vol", "stall_ok"}

    def test_a_perturbed_sample_gate_is_caught(self, strategy: Any) -> None:
        """Risk 1 of the plan: sampling the wrong bars into the causal window.

        ``sample_when`` is moved from ``usable`` to ``entry_window``, which lets
        bars with a non-positive ATR into the percentile window.
        """
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        flat = _frame()
        # Make a handful of bars perfectly flat so atr can reach 0 and the two
        # sampling rules actually differ.
        for index in range(1200, 1240):
            flat.loc[index, ["open", "high", "low", "close"]] = 350.0
        for entry in raw["fields"]:
            if entry["name"] in {"vol_ref", "recent_high", "recent_low"}:
                entry["params"]["sample_when"] = "entry_window"
        document = parse_fields_document(raw)
        baseline = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        good = fe.compare(_inputs(baseline, flat, strategy), mode="window")
        bad = fe.compare(_inputs(document, flat, strategy), mode="window")
        assert good.passed, good.render()
        assert not bad.passed


class TestAnchorGuard:
    def test_a_declaration_whose_anchor_is_not_the_window_s_is_refused(self) -> None:
        """The concrete input: the 08:45 futures declaration over a
        pre-2026-06-28 window, where the era rule gives the legacy 09:00."""
        with pytest.raises(fe.EquivalenceError, match="pins the open anchor"):
            fe._assert_anchor_agrees(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                anchor=OpenAnchor(9, 0, "era-rule"),
                fields_yaml=_fields_yaml("cp3-setup-d-long"),
            )

    def test_the_matching_anchor_passes(self) -> None:
        fe._assert_anchor_agrees(
            load_fields_file(_fields_yaml("cp3-setup-d-long")),
            anchor=OpenAnchor(8, 45, "config"),
            fields_yaml=_fields_yaml("cp3-setup-d-long"),
        )
