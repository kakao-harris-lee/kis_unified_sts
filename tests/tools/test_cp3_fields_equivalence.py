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

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

from shared.indicators.fields import load_fields_file, parse_fields_document
from shared.instruments.contract_spec import ContractSpec
from tools.tos_cp3 import fields_equivalence as fe
from tools.tos_cp3 import legacy_setup_d_driver as legacy_driver  # noqa: E402
from tools.tos_cp3 import produce_fields as pf
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

    def test_publishes_every_field_order_field_in_order(self, tree: str) -> None:
        """All 15, in ``FIELD_ORDER``'s order — nothing left behind.

        The journal's key order is what makes the CP-3 file byte-stable, and a
        kernel poll is refused whole on a missing key
        (``tos_runtime/marketfeed/journal.py``), so "the same set" is not
        enough: it has to be the same sequence.
        """
        document = load_fields_file(_fields_yaml(tree))
        published = tuple(entry.name for entry in document.publish)
        assert published == FIELD_ORDER
        assert len(published) == 15

    def test_reversal_confirmation_matches_the_strategy_yaml(
        self, tree: str, strategy: Any
    ) -> None:
        """The gate that needed the ``const`` op, and its two companions."""
        document = _by_name(load_fields_file(_fields_yaml(tree)))
        config = strategy.entry_config
        assert config.reversal_confirm_enabled is True
        assert document["improve_raw"].params["const"] == float(
            config.reversal_confirm_atr_mult
        )
        # The difference is taken through a 1.0 divisor, which is exact.
        assert document["one"].params["value"] == 1.0
        assert document["z_improvement"].inputs == ("abs_prev_z", "abs_z", "one")
        # requires_price_turn is true, so the turn gates are part of the chain.
        assert config.reversal_confirm_requires_price_turn is True
        assert set(document["reversal_ok"].inputs) == {
            "stall_ok",
            "prev_close_known",
            "turn_long_gate",
            "turn_short_gate",
            "improve_ok",
        }

    def test_a_missing_prior_close_rejects_rather_than_permits(self, tree: str) -> None:
        """Legacy step 6: ``prev_close is None`` -> ``reversal_ok = False``.

        Both resolutions must be ``when_missing: false``; ``true`` would turn
        the legacy's reject into a pass on every warmup bar.
        """
        document = _by_name(load_fields_file(_fields_yaml(tree)))
        for name in ("prev_close_known", "improve_ok", "turn_long", "turn_short"):
            assert document[name].params["when_missing"] is False, name

    def test_no_trend_field_because_the_gate_ships_off(
        self, tree: str, strategy: Any
    ) -> None:
        """The producer refuses a trend-filter run, so no trend field exists."""
        assert strategy.entry_config.trend_filter_enabled is False
        document = load_fields_file(_fields_yaml(tree))
        assert not [spec for spec in document.fields if "trend" in spec.name]


class TestTreesDifferOnlyByTheirAnchor:
    def test_long_and_short_declarations_are_byte_identical(self) -> None:
        """Direction lives in the DSL's threshold sign, never in the fields.

        BYTE identity, not just parsed equality: the two files have no reason
        to differ at all, and ``tos/runtime/tests/compose/test_tenant_tree_copies.py``
        counts them as one of the LONG-identical tenant files. Parsed equality
        is asserted below as well, so a divergence says which kind it is.
        """
        assert (
            _fields_yaml("cp3-setup-d-long").read_bytes()
            == _fields_yaml("cp3-setup-d-short").read_bytes()
        )

    def test_long_and_short_declarations_parse_identically(self) -> None:
        """The same claim at the parsed level, so a header-only drift is named
        as a header-only drift rather than as a semantic one."""
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
        assert len(result.published_fields) == 15
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

        The assertion is on the DIVERGENCES, not only on ``passed`` (review
        2026-11-11 LOW): ``passed`` has several other clauses now — capacity,
        journal matching, missing fields — so ``not bad.passed`` alone would
        also be satisfied by a run that diverged nowhere and merely failed one
        of those, and this test would then no longer be about sampling.
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
        # The run really diverged, and in the vol chain the gate feeds.
        assert bad.divergences, bad.render()
        assert {d.published_field for d in bad.divergences} & {
            "hi_vol",
            "stall_ok",
            "reversal_ok",
        }, sorted({d.published_field for d in bad.divergences})


# ---------------------------------------------------------------------------
# 3. The journal comparison, and what the verdict refuses to call PASS
# ---------------------------------------------------------------------------

#: One published row's worth of fields, in ``FIELD_ORDER``. Values are
#: arbitrary but TYPED the way the journal carries them (scaled ints, bools),
#: because the comparison is type-sensitive by design.
_ROW_FIELDS: dict[str, Any] = {
    "open_x100": 35_000,
    "high_x100": 35_020,
    "low_x100": 34_980,
    "close_x100": 35_010,
    "volume": 120,
    "session_token": "20261110",
    "vwap_x100": 35_005,
    "atr14_x100": 150,
    "z_x1000": -1_900,
    "hi_vol": True,
    "stall_ok": False,
    "reversal_ok": False,
    "entry_window": True,
    "vwap_reverted": False,
    "eod": False,
}


def _bar_id(minute: int) -> str:
    return f"005930:1m:20261110T09{minute:02d}00+0900"


def _write_journal(path: Path, rows: list[tuple[str, dict[str, Any]]]) -> Path:
    """A journal in the live sink's shape: one JSON object per line."""
    import json

    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "raw_event_id": raw_event_id,
                    "source_id": "tos-cp3-live/0.1.0",
                    "instrument": "005930",
                    "as_of_ms": 1,
                    "received_ms": 2,
                    "fields": fields,
                },
                ensure_ascii=False,
            )
            for raw_event_id, fields in rows
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class TestJournalComparison:
    """``_compare_journal`` must REPORT what it could not compare.

    Both skips this class pins were silent ``continue``s until 2026-11-11, so a
    session whose declaration reproduced fewer bars than the journal published
    reported ``journal divergences 0`` and PASS.
    """

    def test_a_changed_value_and_an_unmatched_row_are_both_caught(
        self, tmp_path: Path
    ) -> None:
        """The review's concrete input, in one journal.

        Three rows: one that matches, one whose ``z_x1000`` the declaration
        does not reproduce, and one whose bar the declaration never emitted.
        Plus a declared bar the journal has no row for, which is the opposite
        direction and must be reported WITHOUT failing the comparison.
        """
        changed = dict(_ROW_FIELDS, z_x1000=-1_901)
        journal = _write_journal(
            tmp_path / "journal.jsonl",
            [
                (_bar_id(0), dict(_ROW_FIELDS)),
                (_bar_id(1), changed),
                (_bar_id(2), dict(_ROW_FIELDS)),  # declaration never emitted it
            ],
        )
        declared = {
            _bar_id(0): dict(_ROW_FIELDS),
            _bar_id(1): dict(_ROW_FIELDS),  # still -1900, so row 1 diverges
            _bar_id(3): dict(_ROW_FIELDS),  # declared-only
        }
        outcome = fe._compare_journal(
            journal, declared=declared, published_fields=tuple(_ROW_FIELDS)
        )

        assert outcome.rows == 3
        assert outcome.compared == 2
        assert [
            (d.published_field, d.legacy, d.declared) for d in outcome.divergences
        ] == [("z_x1000", -1_901, -1_900)]
        assert outcome.unmatched_ids == (_bar_id(2),)
        assert outcome.missing_fields == ()
        assert outcome.declared_only_ids == (_bar_id(3),)

    def test_a_journal_row_missing_a_published_field_is_reported(
        self, tmp_path: Path
    ) -> None:
        """A field absent from the row is an uncompared cell, not a pass."""
        short_row = {k: v for k, v in _ROW_FIELDS.items() if k != "eod"}
        journal = _write_journal(tmp_path / "journal.jsonl", [(_bar_id(0), short_row)])
        outcome = fe._compare_journal(
            journal,
            declared={_bar_id(0): dict(_ROW_FIELDS)},
            published_fields=tuple(_ROW_FIELDS),
        )
        assert outcome.rows == 1
        assert outcome.compared == 1
        assert outcome.divergences == ()
        assert outcome.missing_fields == ((_bar_id(0), "eod"),)

    def test_a_blank_line_is_not_a_row(self, tmp_path: Path) -> None:
        """The trailing newline the sink writes must not count as a skip."""
        path = tmp_path / "journal.jsonl"
        _write_journal(path, [(_bar_id(0), dict(_ROW_FIELDS))])
        path.write_text(path.read_text("utf-8") + "\n\n", encoding="utf-8")
        outcome = fe._compare_journal(
            path,
            declared={_bar_id(0): dict(_ROW_FIELDS)},
            published_fields=tuple(_ROW_FIELDS),
        )
        assert (outcome.rows, outcome.compared) == (1, 1)
        assert outcome.unmatched_ids == ()


def _result(**overrides: Any) -> fe.EquivalenceResult:
    """A PASSING result, with the one field under test overridden."""
    base: dict[str, Any] = {
        "mode": "window",
        "symbol": "005930",
        "asset_class": "stock",
        "emit_days": (date(2026, 11, 10),),
        "bars_replayed": 1_000,
        "bars_compared": 300,
        "published_fields": tuple(_ROW_FIELDS),
        "divergences": (),
        "legacy_omitted": (),
        "declared_omitted": (),
        "legacy_only_ids": (),
        "declared_only_ids": (),
        "capacity_before_first_compared_day": 900,
        "capacity_required": 780,
    }
    base.update(overrides)
    return fe.EquivalenceResult(**base)


class TestVerdictGating:
    """Every clause the 2026-11-11 review added to :attr:`passed`.

    Each case is a run that the previous verdict called PASS.
    """

    def test_the_baseline_passes(self) -> None:
        assert _result().passed

    def test_a_short_seed_fails_instead_of_printing_SHORT_next_to_PASS(self) -> None:
        result = _result(capacity_before_first_compared_day=779)
        assert not result.capacity_satisfied
        assert not result.passed
        assert "SHORT" in result.render()

    def test_an_unmatched_journal_row_fails(self) -> None:
        assert not _result(
            mode="session",
            journal_rows=2,
            journal_compared=1,
            journal_unmatched_ids=(_bar_id(2),),
        ).passed

    def test_a_missing_journal_field_fails(self) -> None:
        assert not _result(
            mode="session",
            journal_rows=1,
            journal_compared=1,
            journal_missing_fields=((_bar_id(0), "eod"),),
        ).passed

    def test_a_session_that_compared_no_journal_row_fails(self) -> None:
        """ "Nothing was compared" is not a pass — and only session mode has a
        journal, so the clause is scoped to it."""
        assert not _result(mode="session", journal_rows=0, journal_compared=0).passed
        assert _result(mode="stitched").passed

    def test_a_legacy_record_missing_a_published_field_fails(self) -> None:
        assert not _result(legacy_missing_fields=((_bar_id(0), "eod"),)).passed

    def test_a_declared_only_journal_bar_is_reported_but_not_fatal(self) -> None:
        """A frame bar the journal never carried is not a field disagreement.

        Measured 2026-11-11 on the recorded corpus: 411 declared bars against
        410 published rows on ``long-20261111``, where the journal carries
        15:33 and 15:45 but not the 15:34 the frame has — a live publication
        gap. Failing on it would have made three of the four sessions red.
        """
        result = _result(
            mode="session",
            journal_rows=410,
            journal_compared=410,
            journal_declared_only_ids=(_bar_id(59),),
        )
        assert result.passed
        assert "declared-only bars   1" in result.render()
        assert result.to_payload()["journal_declared_only_ids"] == 1


class TestSessionAnchorIsDerivedFromTheProducerConfig:
    """The LOW: a recorded stock session needs no ``--market-open``."""

    def test_each_market_s_anchor_comes_from_its_live_producer_config(self) -> None:
        assert fe.producer_open_anchor("stock") == "09:00"
        # Futures keeps the era rule rather than a literal, which is what the
        # live producer passes too.
        assert fe.producer_open_anchor("futures") == "auto"

    def test_an_unknown_market_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(fe.EquivalenceError, match="exactly one"):
            fe.producer_open_anchor("bonds")  # type: ignore[arg-type]

    def test_the_stock_anchor_agrees_with_the_stock_tree_s_declaration(self) -> None:
        """The derivation and the declaration must name the same minute.

        Otherwise session mode would resolve an anchor that
        ``_assert_anchor_agrees`` then refuses — the flagless stock run this
        finding exists to make work.
        """
        hour, minute = (
            int(part) for part in fe.producer_open_anchor("stock").split(":")
        )
        spec = _by_name(load_fields_file(_fields_yaml("cp3-setup-d-stock-005930")))[
            "mso"
        ]
        assert (spec.params["open_hour"], spec.params["open_minute"]) == (hour, minute)


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


# ---------------------------------------------------------------------------
# 4. P2-c — the declarative producer and the publish-coverage refusal
# ---------------------------------------------------------------------------


class TestDeclarativeProducer:
    """``produce_bars_declarative`` emits what the legacy loop emitted.

    The byte-identity claim itself lives in the equivalence harness above; what
    is pinned here is the PRODUCER's half — the record shape, the emit-day
    filter, and the omission gate staying with the producer.
    """

    def test_it_emits_the_same_records_the_legacy_loop_does(
        self, strategy: Any
    ) -> None:
        """Same join keys, same stamps, same fifteen values, same order."""
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        inputs = _inputs(document, _frame(), strategy)
        legacy = legacy_driver.produce_bars(
            inputs.df,
            symbol=inputs.symbol,
            strategy=strategy,
            contract_spec=inputs.contract_spec,
            anchor=inputs.anchor,
            emit_days=inputs.emit_days,
        )
        declared = pf.produce_bars_declarative(
            inputs.df,
            symbol=inputs.symbol,
            document=document,
            emit_days=inputs.emit_days,
        )
        assert [r.raw_event_id for r in declared.records] == [
            r.raw_event_id for r in legacy.records
        ]
        assert [r.as_of_ms for r in declared.records] == [
            r.as_of_ms for r in legacy.records
        ]
        assert [r.fields for r in declared.records] == [
            r.fields for r in legacy.records
        ]
        # Key ORDER too: the journal's byte stability depends on it.
        for record in declared.records:
            assert tuple(record.fields) == FIELD_ORDER
        assert declared.omitted == legacy.omitted

    def test_a_bar_outside_the_emit_days_advances_the_windows_without_a_key(
        self, strategy: Any
    ) -> None:
        """Plan §3.2a: replayed, then dropped BEFORE a join key is derived.

        The emitted set must be the emit days only, and the dropped bars must
        be COUNTED rather than listed — naming a previous month's bar after
        this symbol is the label error the plan forbids.
        """
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        inputs = _inputs(document, _frame(), strategy)
        declared = pf.produce_bars_declarative(
            inputs.df,
            symbol=inputs.symbol,
            document=document,
            emit_days=inputs.emit_days,
        )
        legacy = legacy_driver.produce_bars(
            inputs.df,
            symbol=inputs.symbol,
            strategy=strategy,
            contract_spec=inputs.contract_spec,
            anchor=inputs.anchor,
            emit_days=inputs.emit_days,
        )
        assert declared.non_target_segment_bars > 0
        # The counters are the legacy's, not the frame's: the witness yields
        # from the 60th bar onward and skips the frame's first session, and a
        # `bars_replayed` of `len(df)` would make `build_lineage`'s
        # `after_gate - dropped_before_replay == replayed` cross-check raise.
        assert declared.bars_replayed == legacy.bars_replayed
        assert declared.non_target_segment_bars == legacy.non_target_segment_bars
        assert declared.bars_replayed < len(inputs.df)
        warmup, first_session = pf._bar_accounting(inputs.df)
        assert declared.bars_replayed == len(inputs.df) - warmup - first_session
        emitted_days = {
            r.bar_kst.date() for r in declared.records  # type: ignore[union-attr]
        }
        assert emitted_days <= inputs.emit_days

    def test_the_omission_gate_is_still_the_producer_s(self, strategy: Any) -> None:
        """A flat run makes ATR 0, and the bar is OMITTED, not published.

        The gate is ``_inputs_unusable`` itself — the same function the legacy
        loop called — so the two omitted lists are answers to one question
        rather than two restatements of it, **reasons included**: the lineage
        writes ``sorted({reason})``, so one differing word is a differing file.

        The flat run sits on an EMIT day (bars 1900-1959, session 6 of 7, mid
        entry window). On a non-emit day both sides omit nothing and the
        assertion would pass on two empty lists without testing the gate
        (review of PR #1067, M3).
        """
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        flat = _frame()
        for index in range(1900, 1960):
            flat.loc[index, ["open", "high", "low", "close"]] = 350.0
        inputs = _inputs(document, flat, strategy)
        assert min(inputs.emit_days) <= flat["timestamp"].iloc[1900].date()
        declared = pf.produce_bars_declarative(
            inputs.df,
            symbol=inputs.symbol,
            document=document,
            emit_days=inputs.emit_days,
        )
        legacy = legacy_driver.produce_bars(
            inputs.df,
            symbol=inputs.symbol,
            strategy=strategy,
            contract_spec=inputs.contract_spec,
            anchor=inputs.anchor,
            emit_days=inputs.emit_days,
        )
        # Not a vacuous `[] == []`: the flat run really did drive ATR to 0 on
        # bars both sides reached and both sides omitted.
        assert declared.omitted
        assert legacy.omitted
        assert declared.omitted == legacy.omitted
        assert declared.omitted[0][1] == "atr_14 <= 0 (z is undefined)"
        published = {r.raw_event_id for r in declared.records}
        assert not published & {bar for bar, _ in declared.omitted}

    def test_emit_days_none_also_matches_the_legacy_loop(self, strategy: Any) -> None:
        """``emit_days=None`` is the live producer's call — it must agree too.

        ``tools/tos_cp3/live_producer/line.py`` passes no ``emit_days``, so this
        is the production shape. Before the admission skip was made explicit
        this emitted 360 first-session records the legacy never emitted and
        differed on 88 ``hi_vol`` cells of bars both sides DID emit, because the
        declarative ``gated_*`` windows had sampled bars the witness's
        ``check()`` never saw (review of PR #1067, M2).
        """
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        inputs = _inputs(document, _frame(), strategy)
        legacy = legacy_driver.produce_bars(
            inputs.df,
            symbol=inputs.symbol,
            strategy=strategy,
            contract_spec=inputs.contract_spec,
            anchor=inputs.anchor,
        )
        declared = pf.produce_bars_declarative(
            inputs.df, symbol=inputs.symbol, document=document
        )
        assert [r.raw_event_id for r in declared.records] == [
            r.raw_event_id for r in legacy.records
        ]
        assert [r.as_of_ms for r in declared.records] == [
            r.as_of_ms for r in legacy.records
        ]
        assert [r.fields for r in declared.records] == [
            r.fields for r in legacy.records
        ]
        assert declared.omitted == legacy.omitted
        assert declared.bars_replayed == legacy.bars_replayed
        assert declared.non_target_segment_bars == legacy.non_target_segment_bars == 0

    def test_a_non_finite_bar_is_a_corrupt_frame_not_an_omission(
        self, strategy: Any
    ) -> None:
        """NaN raises ``ProduceFieldsError``, on an emit day or not.

        ``FieldBar.create`` refuses a non-finite bar with a ``FieldEvalError``,
        which is the field layer's error class and not the one this tool's
        callers catch; and the refusal must not be swallowed by the
        per-bar omission path either, because
        :func:`produce_fields._inputs_unusable` already says why — NaN is a
        defect in the Parquet tree, and omitting the bar would hide it.
        """
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        for row in (10, 500, 1900):  # warmup, non-emit day, emit day
            frame = _frame()
            frame.loc[row, "close"] = float("nan")
            inputs = _inputs(document, frame, strategy)
            with pytest.raises(pf.ProduceFieldsError, match="non-finite"):
                pf.produce_bars_declarative(
                    inputs.df,
                    symbol=inputs.symbol,
                    document=document,
                    emit_days=inputs.emit_days,
                )

    def test_a_refusal_the_gate_cannot_name_aborts_the_run(self, strategy: Any) -> None:
        """A declaration defect must surface, not be counted as a quiet bar.

        The concrete input: the ``one`` constant that makes ``z_improvement``
        express a plain difference is declared as ``0.0`` instead of ``1.0``,
        so ``ratio_z`` divides by zero on every bar that has a ``prev_close``.
        The evaluator refuses the bar; the omission gate finds
        ``close``/``vwap``/``atr`` perfectly usable — so the bar is not an
        omission at all. Counted as one it would publish a quietly shorter
        file, and on a non-emit day it would not even be listed.
        """
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        divisors = [spec for spec in raw["fields"] if spec["name"] == "one"]
        assert len(divisors) == 1
        divisors[0]["params"]["value"] = 0.0
        broken = parse_fields_document(raw)
        inputs = _inputs(document, _frame(), strategy)
        with pytest.raises(pf.ProduceFieldsError, match="omission gate does not name"):
            pf.produce_bars_declarative(
                inputs.df,
                symbol=inputs.symbol,
                document=broken,
                emit_days=inputs.emit_days,
            )

    def test_the_row_is_the_declaration_s_publish_list_not_field_order(
        self, strategy: Any
    ) -> None:
        """Review #1067 L2 — a SIXTEENTH published field reaches the journal.

        Selecting ``FIELD_ORDER`` out of the evaluated bar made the producer's
        answer to "what does this tenant publish?" a module constant: a tenant
        could add a published field and the producer would drop it from every
        row without a word. Here the declaration publishes ``mso`` as well, and
        the record carries sixteen keys with the new one in its declared place.
        """
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        raw["publish"].append(
            {"field": "mso", "as": "mso_x1", "scale": {"mult": 1, "round": "half_up"}}
        )
        wider = parse_fields_document(raw)
        inputs = _inputs(
            load_fields_file(_fields_yaml("cp3-setup-d-long")), _frame(), strategy
        )
        declared = pf.produce_bars_declarative(
            inputs.df,
            symbol=inputs.symbol,
            document=wider,
            emit_days=inputs.emit_days,
        )
        assert tuple(declared.records[0].fields) == FIELD_ORDER + ("mso_x1",)

    def test_a_declaration_short_of_a_field_is_not_a_key_error(
        self, strategy: Any
    ) -> None:
        """The other half of L2: fourteen keys, produced, not a bare ``KeyError``.

        Dropping ``eod`` from ``publish`` used to raise ``KeyError('eod')`` out
        of the row comprehension — a traceback mid-run, with no name for what
        was actually wrong. The producer now emits what the declaration says;
        whether that set is the one this tenant's consumers expect is the
        start-time question
        :func:`~tools.tos_cp3.produce_fields.assert_publish_matches_critical_inputs`
        answers, and :class:`TestPublishMatchesTheCriticalInputPolicy` is where
        this same declaration is refused.
        """
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        raw["publish"] = [entry for entry in raw["publish"] if entry["field"] != "eod"]
        narrower = parse_fields_document(raw)
        inputs = _inputs(
            load_fields_file(_fields_yaml("cp3-setup-d-long")), _frame(), strategy
        )
        declared = pf.produce_bars_declarative(
            inputs.df,
            symbol=inputs.symbol,
            document=narrower,
            emit_days=inputs.emit_days,
        )
        published = tuple(declared.records[0].fields)
        assert "eod" not in published
        assert published == tuple(name for name in FIELD_ORDER if name != "eod")


class TestPublishMatchesTheCriticalInputPolicy:
    """Review #1067 L2 — the publish set is checked against the tenant's policy.

    The producer takes the publish list whole, so the set the kernel receives
    is the declaration's. The tenant tree already states which fields its
    consumers were configured for, one ``field_key`` per entry with the
    freshness bound applied to it, and that is what this check compares
    against — at producer START, where the answer is free.
    """

    @staticmethod
    def _policy(tree: str) -> Path:
        return (
            REPO_ROOT / "config" / "tos_runtime" / tree / "critical_input_policy.yaml"
        )

    def test_the_three_shipped_trees_pass(self) -> None:
        """Green at the start: a guard, not a migration step."""
        for tree in TREES:
            pf.assert_publish_matches_critical_inputs(
                load_fields_file(_fields_yaml(tree)), policy_path=self._policy(tree)
            )

    def test_a_sixteenth_published_field_is_refused_by_name(self) -> None:
        """It would reach the snapshot with no ``max_age_ms`` of its own."""
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        raw["publish"].append(
            {"field": "mso", "as": "mso_x1", "scale": {"mult": 1, "round": "half_up"}}
        )
        with pytest.raises(pf.ProduceFieldsError, match="mso_x1"):
            pf.assert_publish_matches_critical_inputs(
                parse_fields_document(raw),
                policy_path=self._policy("cp3-setup-d-long"),
            )

    def test_a_dropped_field_is_refused_by_name(self) -> None:
        """The kernel refuses the WHOLE poll on a missing journal key, so this
        would be a refused poll every minute from the open rather than a field
        reading ``None``."""
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        raw["publish"] = [entry for entry in raw["publish"] if entry["field"] != "eod"]
        with pytest.raises(pf.ProduceFieldsError, match="declared-but-unpublished"):
            pf.assert_publish_matches_critical_inputs(
                parse_fields_document(raw),
                policy_path=self._policy("cp3-setup-d-long"),
            )

    @pytest.mark.parametrize(
        ("text", "match"),
        [
            ("policy_id: x\n", "no 'fields' list"),
            ("fields: []\n", "no 'fields' list"),
            ("fields:\n  - max_age_ms: 800\n", "no 'field_key' string"),
            ("fields: [unclosed\n", "not parseable as YAML"),
        ],
    )
    def test_a_policy_that_cannot_be_compared_is_refused(
        self, tmp_path: Path, text: str, match: str
    ) -> None:
        """An unreadable policy is not agreement."""
        policy = tmp_path / "critical_input_policy.yaml"
        policy.write_text(text, encoding="utf-8")
        with pytest.raises(pf.ProduceFieldsError, match=match):
            pf.assert_publish_matches_critical_inputs(
                load_fields_file(_fields_yaml("cp3-setup-d-long")), policy_path=policy
            )

    def test_a_missing_policy_file_is_refused_rather_than_skipped(
        self, tmp_path: Path
    ) -> None:
        """A mis-rendered tree must not pass the check by not having one."""
        with pytest.raises(pf.ProduceFieldsError, match="cannot be read"):
            pf.assert_publish_matches_critical_inputs(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                policy_path=tmp_path / "critical_input_policy.yaml",
            )


class TestPublishCoverageRefusal:
    """Plan §2.2 — a DSL ref the declaration does not publish is refused."""

    def test_the_three_shipped_trees_pass(self) -> None:
        """The check starts green: it is a guard, not a migration step."""
        for tree in TREES:
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml(tree)),
                strategies_dir=REPO_ROOT
                / "config"
                / "tos_runtime"
                / tree
                / "strategies",
            )

    def test_a_ref_that_is_not_published_is_refused_by_name(
        self, tmp_path: Path
    ) -> None:
        """The concrete input: a tenant reading ``rsi14`` from a Setup D
        declaration that publishes only the fifteen."""
        strategies = tmp_path / "strategies"
        strategies.mkdir()
        (strategies / "x.strategy.yaml").write_text(
            yaml.safe_dump(
                {
                    "policy": {
                        "rules": [
                            {
                                "all_of": [
                                    {
                                        "left": {
                                            "ref": [
                                                "capsule",
                                                "resolved_values",
                                                "rsi14",
                                            ]
                                        },
                                        "op": "GE",
                                        "right": {"const": 1},
                                    }
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(pf.ProduceFieldsError, match="rsi14"):
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategies_dir=strategies,
            )

    def test_a_directory_with_no_strategy_is_refused(self, tmp_path: Path) -> None:
        """Agreement with nothing is not agreement."""
        empty = tmp_path / "strategies"
        empty.mkdir()
        with pytest.raises(pf.ProduceFieldsError, match="no \\*.yaml strategy"):
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategies_dir=empty,
            )

    def test_a_missing_directory_is_refused_by_name(self, tmp_path: Path) -> None:
        """A tree with no ``strategies/`` must not raise ``FileNotFoundError``.

        ``iterdir()`` on a path that is not there raises an ``OSError`` the
        producer's caller does not catch, so a mis-rendered tenant tree would
        surface as a traceback instead of as this tool's own refusal.
        """
        with pytest.raises(pf.ProduceFieldsError, match="not a directory"):
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategies_dir=tmp_path / "strategies",
            )

    @pytest.mark.parametrize(
        ("name", "text", "match"),
        [
            ("malformed", "policy: [unclosed\n", "not loadable"),
            (
                "multi_doc",
                "policy:\n  rules: []\n---\npolicy:\n  rules: []\n",
                "not loadable",
            ),
            ("empty", "\n", "not a mapping"),
            ("scalar", "just a string\n", "not a mapping"),
        ],
    )
    def test_an_unreadable_strategy_is_refused(
        self, tmp_path: Path, name: str, text: str, match: str
    ) -> None:
        """A DSL that cannot be read is not a DSL that agrees.

        ``yaml.safe_load`` raises on a malformed file and on a multi-document
        stream, and returns ``None`` for an empty one — which would have walked
        to zero refs and reported agreement it never checked.
        """
        strategies = tmp_path / name
        strategies.mkdir()
        (strategies / "x.strategy.yaml").write_text(text, encoding="utf-8")
        with pytest.raises(pf.ProduceFieldsError, match=match):
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategies_dir=strategies,
            )

    def test_the_three_shipped_trees_bind_to_their_own_producer_config(self) -> None:
        """Each tree's declaration agrees with the anchor its producer resolves.

        The binding check starts green, like the publish-coverage one: it is a
        guard, not a migration step.
        """
        strategy = load_strategy_inputs(STRATEGY_YAML)
        for tree in TREES:
            hour, minute = TREE_ANCHORS[tree]
            pf.assert_declaration_binds_to_the_run(
                load_fields_file(_fields_yaml(tree)),
                strategy=strategy,
                anchor=OpenAnchor(hour, minute, "test"),
            )

    def test_a_declaration_from_the_other_market_is_refused(self) -> None:
        """The concrete input: the futures tree under the stock open.

        08:45 against 09:00 shifts ``entry_window`` by fifteen minutes on every
        bar of the session, and the field is a bare bool — nothing downstream
        could report it.
        """
        strategy = load_strategy_inputs(STRATEGY_YAML)
        with pytest.raises(pf.ProduceFieldsError, match="counts minutes from 08:45"):
            pf.assert_declaration_binds_to_the_run(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategy=strategy,
                anchor=OpenAnchor(9, 0, "config"),
            )

    def test_a_vol_window_the_seed_is_not_built_for_is_refused(self) -> None:
        """The seed is sized from the strategy YAML; the window consumes it.

        Doubling the declaration's window leaves ``vol_ref`` inside its warmup
        all session, where the gate is PERMISSIVE — so ``hi_vol`` would read
        true on every bar, an entry gate held open because two numbers
        disagreed.
        """
        strategy = load_strategy_inputs(STRATEGY_YAML)
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        vol = next(spec for spec in raw["fields"] if spec["name"] == "vol_ref")
        vol["params"]["window"] = int(strategy.entry_config.vol_window_bars) * 2
        with pytest.raises(pf.ProduceFieldsError, match="vol_ref window="):
            pf.assert_declaration_binds_to_the_run(
                parse_fields_document(raw),
                strategy=strategy,
                anchor=OpenAnchor(8, 45, "test"),
            )

    def test_a_commented_out_ref_is_not_a_ref(self, tmp_path: Path) -> None:
        """Walked over the PARSED document, so a comment cannot trip it."""
        strategies = tmp_path / "strategies"
        strategies.mkdir()
        (strategies / "x.strategy.yaml").write_text(
            "policy:\n"
            "  rules:\n"
            "    - all_of:\n"
            "        # - left: {ref: [capsule, resolved_values, rsi14]}\n"
            "        - left: {ref: [capsule, resolved_values, hi_vol]}\n"
            "          op: EQ\n"
            "          right: {const: true}\n",
            encoding="utf-8",
        )
        pf.assert_dsl_refs_are_published(
            load_fields_file(_fields_yaml("cp3-setup-d-long")),
            strategies_dir=strategies,
        )


class TestTheRestatedRegistryName:
    """``produce_fields.SETUP_D_REGISTRY_NAME`` must equal the class attribute.

    P2-c drives the legacy imports in ``produce_fields.py`` to zero (plan §5.2),
    and two of the four uses were the registry-name string. Restating a literal
    is only honest while something compares it to its source — this is that
    something. A test MAY import the legacy class: a test is not the producer
    path, which is the thing the criterion is about.
    """

    def test_the_literal_equals_the_class_attribute(self) -> None:
        from shared.decision.setups.vwap_reversion import SetupDVWAPReversion

        assert pf.SETUP_D_REGISTRY_NAME == SetupDVWAPReversion.REGISTRY_NAME

    def test_the_shipped_strategy_yaml_declares_that_type(self) -> None:
        """...and the string is the one the shipped strategy actually carries,
        so the loader's refusal is about a real value rather than a typo both
        sides share."""
        raw = yaml.safe_load(STRATEGY_YAML.read_text(encoding="utf-8"))
        assert raw["strategy"]["entry"]["type"] == pf.SETUP_D_REGISTRY_NAME

    def test_produce_fields_names_the_legacy_class_nowhere(self) -> None:
        """Plan §5.2, as a number rather than a promise: the count is ZERO.

        The two functions that used to hold it — the legacy driver and the D7
        measurement — now live in ``tools/tos_cp3/legacy_setup_d_driver.py``,
        which is where this assertion says they are. Reading the AST rather
        than the import list is deliberate: a name reached through an alias or
        a re-export would still show up here.
        """
        import ast

        for module, expected in ((pf, False), (legacy_driver, True)):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            named = {
                node.lineno
                for node in ast.walk(tree)
                if isinstance(node, ast.Name) and node.id == "SetupDVWAPReversion"
            }
            assert bool(named) is expected, (module.__name__, sorted(named))

    def test_what_of_the_legacy_module_produce_fields_still_binds(self) -> None:
        """Exactly one name, and it is a CONFIG dataclass — not the setup.

        Said precisely because the imprecise version is tempting: importing
        ``produce_fields`` still executes
        ``shared/decision/setups/vwap_reversion.py``, because ``SetupDConfig``
        — the thresholds dataclass ``load_strategy_inputs`` fills and
        ``live_producer/frame.py::build_seed`` reads ``vol_window_bars`` out of
        — is declared in that same file. So plan §5.2's claim is about the
        DECIDING class, which the module no longer names anywhere; it is not a
        claim that the witness left the live producer's import closure. Moving
        ``SetupDConfig`` is a separate change with its own reasons.
        """
        import tools.tos_cp3.produce_fields as module

        bound = {
            name
            for name, value in vars(module).items()
            if getattr(value, "__module__", None)
            == "shared.decision.setups.vwap_reversion"
        }
        assert bound == {"SetupDConfig"}, bound
        assert sys.modules["shared.decision.setups.vwap_reversion"] is not None
