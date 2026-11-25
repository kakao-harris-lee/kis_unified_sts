"""P2-b — the three trees' ``fields.yaml`` and the equivalence harness."""

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
        """All 15, in ``FIELD_ORDER``'s order — nothing left behind."""
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
        assert document["one"].params["value"] == 1.0
        assert document["z_improvement"].inputs == ("abs_prev_z", "abs_z", "one")
        assert config.reversal_confirm_requires_price_turn is True
        assert set(document["reversal_ok"].inputs) == {
            "stall_ok",
            "prev_close_known",
            "turn_long_gate",
            "turn_short_gate",
            "improve_ok",
        }

    def test_a_missing_prior_close_rejects_rather_than_permits(self, tree: str) -> None:
        """Legacy step 6: ``prev_close is None`` -> ``reversal_ok = False``."""
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
        """Direction lives in the DSL's threshold sign, never in the fields."""
        assert (
            _fields_yaml("cp3-setup-d-long").read_bytes()
            == _fields_yaml("cp3-setup-d-short").read_bytes()
        )

    def test_long_and_short_declarations_parse_identically(self) -> None:
        """The same claim at the parsed level, so a header-only drift is named"""
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


def _frame(sessions: int = 7, bars_per_session: int = 360) -> pd.DataFrame:
    """Synthetic 1-minute futures bars from the 08:45 open, volatile enough"""
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
        """A comparison that cannot fail proves nothing."""
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        for entry in raw["fields"]:
            if entry["name"] == "vol_ok_raw":
                entry["params"]["mult"] = 0.91
        document = parse_fields_document(raw)
        result = fe.compare(_inputs(document, _frame(), strategy), mode="window")
        assert not result.passed
        assert {d.published_field for d in result.divergences} & {"hi_vol", "stall_ok"}

    def test_a_perturbed_sample_gate_is_caught(self, strategy: Any) -> None:
        """Risk 1 of the plan: sampling the wrong bars into the causal window."""
        raw = yaml.safe_load(_fields_yaml("cp3-setup-d-long").read_text("utf-8"))
        flat = _frame()
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
        assert bad.divergences, bad.render()
        assert {d.published_field for d in bad.divergences} & {
            "hi_vol",
            "stall_ok",
            "reversal_ok",
        }, sorted({d.published_field for d in bad.divergences})


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
    """``_compare_journal`` must REPORT what it could not compare."""

    def test_a_changed_value_and_an_unmatched_row_are_both_caught(
        self, tmp_path: Path
    ) -> None:
        """The review's concrete input, in one journal."""
        changed = dict(_ROW_FIELDS, z_x1000=-1_901)
        journal = _write_journal(
            tmp_path / "journal.jsonl",
            [
                (_bar_id(0), dict(_ROW_FIELDS)),
                (_bar_id(1), changed),
                (_bar_id(2), dict(_ROW_FIELDS)),
            ],
        )
        declared = {
            _bar_id(0): dict(_ROW_FIELDS),
            _bar_id(1): dict(_ROW_FIELDS),
            _bar_id(3): dict(_ROW_FIELDS),
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
    """Every clause the 2026-11-11 review added to :attr:`passed`."""

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
        '"Nothing was compared" is not a pass — and only session mode has a'
        assert not _result(mode="session", journal_rows=0, journal_compared=0).passed
        assert _result(mode="stitched").passed

    def test_a_legacy_record_missing_a_published_field_fails(self) -> None:
        assert not _result(legacy_missing_fields=((_bar_id(0), "eod"),)).passed

    def test_a_declared_only_journal_bar_is_reported_but_not_fatal(self) -> None:
        """A frame bar the journal never carried is not a field disagreement."""
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
        assert fe.producer_open_anchor("futures") == "auto"

    def test_an_unknown_market_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(fe.EquivalenceError, match="no config/tos_probes"):
            fe.producer_open_anchor("bonds")  # type: ignore[arg-type]

    def test_several_configs_of_one_market_are_fine_while_they_agree(self) -> None:
        """One tenant per stock symbol (operator directive 2026-11-19)."""
        stock = [
            path
            for path in sorted(fe.REPO_ROOT.glob(fe.PRODUCER_CONFIG_GLOB))
            if (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("market")
            == "stock"
        ]
        assert len(stock) >= 3, [str(path) for path in stock]
        assert fe.producer_open_anchor("stock") == "09:00"

    def test_a_disagreement_between_two_configs_of_one_market_is_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two anchors for one market leave none to pick, so neither is picked."""
        probes = tmp_path / "config" / "tos_probes"
        probes.mkdir(parents=True)
        (probes / "cp3-live-producer-stock-aaaaaa.yaml").write_text(
            'market: stock\nopen_anchor: "09:00"\n', encoding="utf-8"
        )
        (probes / "cp3-live-producer-stock-bbbbbb.yaml").write_text(
            'market: stock\nopen_anchor: "10:00"\n', encoding="utf-8"
        )
        monkeypatch.setattr(fe, "REPO_ROOT", tmp_path)
        with pytest.raises(fe.EquivalenceError, match="do not agree on open_anchor"):
            fe.producer_open_anchor("stock")

    def test_the_stock_anchor_agrees_with_the_stock_tree_s_declaration(self) -> None:
        """The derivation and the declaration must name the same minute."""
        hour, minute = (
            int(part) for part in fe.producer_open_anchor("stock").split(":")
        )
        spec = _by_name(load_fields_file(_fields_yaml("cp3-setup-d-stock-005930")))[
            "mso"
        ]
        assert (spec.params["open_hour"], spec.params["open_minute"]) == (hour, minute)


class TestAnchorGuard:
    def test_a_declaration_whose_anchor_is_not_the_window_s_is_refused(self) -> None:
        """The concrete input: the 08:45 futures declaration over a"""
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


class TestDeclarativeProducer:
    """``produce_bars_declarative`` emits what the legacy loop emitted."""

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
        for record in declared.records:
            assert tuple(record.fields) == FIELD_ORDER
        assert declared.omitted == legacy.omitted

    def test_a_bar_outside_the_emit_days_advances_the_windows_without_a_key(
        self, strategy: Any
    ) -> None:
        """Plan §3.2a: replayed, then dropped BEFORE a join key is derived."""
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
        """A flat run makes ATR 0, and the bar is OMITTED, not published."""
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
        assert declared.omitted
        assert legacy.omitted
        assert declared.omitted == legacy.omitted
        assert declared.omitted[0][1] == "atr_14 <= 0 (z is undefined)"
        published = {r.raw_event_id for r in declared.records}
        assert not published & {bar for bar, _ in declared.omitted}

    def test_emit_days_none_also_matches_the_legacy_loop(self, strategy: Any) -> None:
        """``emit_days=None`` is the live producer's call — it must agree too."""
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
        """NaN raises ``ProduceFieldsError``, on an emit day or not."""
        document = load_fields_file(_fields_yaml("cp3-setup-d-long"))
        for row in (10, 500, 1900):
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
        """A declaration defect must surface, not be counted as a quiet bar."""
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
        """Review #1067 L2 — a SIXTEENTH published field reaches the journal."""
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
        """The other half of L2: fourteen keys, produced, not a bare ``KeyError``."""
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
    """Review #1067 L2 — the publish set is checked against the tenant's policy."""

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
        """The kernel refuses the WHOLE poll on a missing journal key, so this"""
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
        """The concrete input: a tenant reading ``rsi14`` from a Setup D"""
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
        """A tree with no ``strategies/`` must not raise ``FileNotFoundError``."""
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
        """A DSL that cannot be read is not a DSL that agrees."""
        strategies = tmp_path / name
        strategies.mkdir()
        (strategies / "x.strategy.yaml").write_text(text, encoding="utf-8")
        with pytest.raises(pf.ProduceFieldsError, match=match):
            pf.assert_dsl_refs_are_published(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategies_dir=strategies,
            )

    def test_the_three_shipped_trees_bind_to_their_own_producer_config(self) -> None:
        """Each tree's declaration agrees with the anchor its producer resolves."""
        strategy = load_strategy_inputs(STRATEGY_YAML)
        for tree in TREES:
            hour, minute = TREE_ANCHORS[tree]
            pf.assert_declaration_binds_to_the_run(
                load_fields_file(_fields_yaml(tree)),
                strategy=strategy,
                anchor=OpenAnchor(hour, minute, "test"),
            )

    def test_a_declaration_from_the_other_market_is_refused(self) -> None:
        """The concrete input: the futures tree under the stock open."""
        strategy = load_strategy_inputs(STRATEGY_YAML)
        with pytest.raises(pf.ProduceFieldsError, match="counts minutes from 08:45"):
            pf.assert_declaration_binds_to_the_run(
                load_fields_file(_fields_yaml("cp3-setup-d-long")),
                strategy=strategy,
                anchor=OpenAnchor(9, 0, "config"),
            )

    def test_a_vol_window_the_seed_is_not_built_for_is_refused(self) -> None:
        """The seed is sized from the strategy YAML; the window consumes it."""
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
    """``produce_fields.SETUP_D_REGISTRY_NAME`` must equal the class attribute."""

    def test_the_literal_equals_the_class_attribute(self) -> None:
        from shared.decision.setups.vwap_reversion import SetupDVWAPReversion

        assert pf.SETUP_D_REGISTRY_NAME == SetupDVWAPReversion.REGISTRY_NAME

    def test_the_shipped_strategy_yaml_declares_that_type(self) -> None:
        """...and the string is the one the shipped strategy actually carries,"""
        raw = yaml.safe_load(STRATEGY_YAML.read_text(encoding="utf-8"))
        assert raw["strategy"]["entry"]["type"] == pf.SETUP_D_REGISTRY_NAME

    def test_produce_fields_names_the_legacy_class_nowhere(self) -> None:
        """Plan §5.2, as a number rather than a promise: the count is ZERO."""
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
        """Exactly one name, and it is a CONFIG dataclass — not the setup."""
        import tools.tos_cp3.produce_fields as module

        bound = {
            name
            for name, value in vars(module).items()
            if getattr(value, "__module__", None)
            == "shared.decision.setups.vwap_reversion"
        }
        assert bound == {"SetupDConfig"}, bound
        assert sys.modules["shared.decision.setups.vwap_reversion"] is not None
