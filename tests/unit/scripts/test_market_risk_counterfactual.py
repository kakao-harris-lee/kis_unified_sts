"""Hermetic tests for scripts/validation/market_risk_counterfactual.py.

Synthetic Parquet score rows + a tmp_path SQLite RuntimeLedger; no network,
no Redis, no repo data.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from scripts.validation.market_risk_common import CounterfactualSettings
from scripts.validation.market_risk_counterfactual import (
    ScoreLookup,
    classify_trades,
    load_trades,
    main,
    parse_entry_kst,
    summarize,
)
from shared.storage import SQLiteRuntimeLedger
from shared.storage.market_structure_store import ParquetMarketStructureStore

KST = ZoneInfo("Asia/Seoul")
CUTOFF = time(8, 0)


@pytest.fixture
def store(tmp_path):
    store = ParquetMarketStructureStore(tmp_path / "market")
    store.replace_day(
        date(2026, 6, 29), "close", {"risk_score_ema3": 80.0, "risk_band": "HIGH"}
    )
    store.replace_day(
        date(2026, 6, 30), "close", {"risk_score_ema3": 90.0, "risk_band": "CRITICAL"}
    )
    store.replace_day(
        date(2026, 7, 1), "premarket", {"risk_score_ema3": 30.0, "risk_band": "NEUTRAL"}
    )
    return store


@pytest.fixture
def lookup(store):
    return ScoreLookup(
        store.read_range(snapshot="close"),
        store.read_range(snapshot="premarket"),
        CounterfactualSettings(),
        CUTOFF,
    )


def _trade(trade_id, side, entry_iso, pnl, asset_class="futures"):
    return {
        "trade_id": trade_id,
        "idempotency_key": trade_id,
        "asset_class": asset_class,
        "symbol": "101S6000",
        "side": side,
        "strategy": "setup_a_gap_reversion",
        "entry_time": entry_iso,
        "entry_price": 380.0,
        "exit_time": entry_iso.replace("T10:", "T14:").replace("T07:", "T14:"),
        "exit_price": 381.0,
        "quantity": 1,
        "pnl": pnl,
    }


TRADES = [
    # long on 6/30: prior close (6/29) score 80 -> blocked
    _trade("t1", "long", "2026-06-30T10:00:00+09:00", -500.0),
    # short on 6/30: shorts are never blocked
    _trade("t2", "short", "2026-06-30T10:00:00+09:00", 300.0),
    # long on 7/1 at 10:00: same-day premarket score 30 -> allowed
    _trade("t3", "long", "2026-07-01T10:00:00+09:00", 200.0),
    # long on 7/1 at 07:30 (< premarket cutoff): prior close (6/30) 90 -> blocked
    _trade("t4", "long", "2026-07-01T07:30:00+09:00", -100.0),
    # long on 6/29: no close row strictly before -> fail-open allowed
    _trade("t5", "long", "2026-06-29T10:00:00+09:00", 50.0),
]


@pytest.fixture
def ledger_path(tmp_path):
    path = tmp_path / "runtime.db"
    with SQLiteRuntimeLedger(path) as ledger:
        for trade in TRADES:
            ledger.record_trade(trade)
    return path


class TestParseEntryKst:
    def test_aware_utc_converted_to_kst(self):
        parsed = parse_entry_kst("2026-06-30T01:00:00Z", "Asia/Seoul")
        assert parsed == datetime(2026, 6, 30, 10, 0, tzinfo=KST)

    def test_naive_assumed_configured_tz(self):
        parsed = parse_entry_kst("2026-06-30 10:00:00", "Asia/Seoul")
        assert parsed.hour == 10 and parsed.tzinfo is not None

    def test_unparseable_returns_none(self):
        assert parse_entry_kst("not-a-time", "Asia/Seoul") is None
        assert parse_entry_kst(None, "Asia/Seoul") is None


class TestScoreLookup:
    def test_prior_close_strictly_before_entry_date(self, lookup):
        score, source = lookup.score_at_entry(datetime(2026, 6, 30, 10, 0, tzinfo=KST))
        assert score == pytest.approx(80.0)
        assert source == "close:2026-06-29"

    def test_same_day_close_never_used(self, lookup):
        # 6/29 has a close score but no earlier row exists -> fail-open.
        score, source = lookup.score_at_entry(datetime(2026, 6, 29, 10, 0, tzinfo=KST))
        assert score is None and source is None

    def test_premarket_used_at_or_after_cutoff(self, lookup):
        score, source = lookup.score_at_entry(datetime(2026, 7, 1, 10, 0, tzinfo=KST))
        assert score == pytest.approx(30.0)
        assert source == "premarket:2026-07-01"

    def test_premarket_skipped_before_cutoff(self, lookup):
        score, source = lookup.score_at_entry(datetime(2026, 7, 1, 7, 30, tzinfo=KST))
        assert score == pytest.approx(90.0)
        assert source == "close:2026-06-30"

    def test_degraded_scores_excluded(self, store):
        store.replace_day(
            date(2026, 6, 30),
            "close",
            {"risk_score_ema3": 90.0, "degraded": True},
        )
        lookup = ScoreLookup(
            store.read_range(snapshot="close"),
            store.read_range(snapshot="premarket"),
            CounterfactualSettings(exclude_degraded=True),
            CUTOFF,
        )
        score, source = lookup.score_at_entry(datetime(2026, 7, 1, 7, 30, tzinfo=KST))
        # degraded 6/30 row is skipped; falls back to 6/29
        assert score == pytest.approx(80.0)
        assert source == "close:2026-06-29"


class TestClassifyAndSummarize:
    def test_block_decisions_and_pnl_sums(self, ledger_path, lookup):
        settings = CounterfactualSettings()
        with SQLiteRuntimeLedger(ledger_path) as ledger:
            trades, unparseable = load_trades(ledger, settings, None, None)
        assert unparseable == 0
        assert len(trades) == 5

        rows = classify_trades(trades, lookup, settings)
        decisions = {row["trade_id"]: row["blocked"] for row in rows}
        assert decisions == {
            "t1": True,
            "t2": False,
            "t3": False,
            "t4": True,
            "t5": False,
        }

        summary = summarize(rows)
        assert summary["total_trades"] == 5
        assert summary["blocked"]["trades"] == 2
        assert summary["blocked"]["pnl_sum"] == pytest.approx(-600.0)
        assert summary["allowed"]["trades"] == 3
        assert summary["allowed"]["pnl_sum"] == pytest.approx(550.0)
        assert summary["fail_open_no_score"] == 1
        assert summary["blocked_pnl_avoided"] == pytest.approx(600.0)
        assert summary["by_side"]["short"]["blocked"]["trades"] == 0

    def test_entry_window_filter(self, ledger_path):
        settings = CounterfactualSettings()
        with SQLiteRuntimeLedger(ledger_path) as ledger:
            trades, _ = load_trades(
                ledger, settings, date(2026, 7, 1), date(2026, 7, 1)
            )
        assert {t["id"] for t in trades} == {"t3", "t4"}

    def test_asset_class_filter(self, ledger_path):
        settings = CounterfactualSettings(asset_classes=["stock"])
        with SQLiteRuntimeLedger(ledger_path) as ledger:
            trades, _ = load_trades(ledger, settings, None, None)
        assert trades == []


class TestMainCli:
    def test_end_to_end_writes_reports(self, store, ledger_path, tmp_path, capsys):
        out_dir = tmp_path / "reports"
        rc = main(
            [
                "--parquet-root",
                str(store.root),
                "--ledger",
                str(ledger_path),
                "--out-dir",
                str(out_dir),
                "--tag",
                "unit",
            ]
        )
        assert rc == 0
        report = json.loads(
            (out_dir / "market_risk_counterfactual_unit.json").read_text()
        )
        assert report["status"] == "ok"
        assert report["summary"]["blocked"]["pnl_sum"] == pytest.approx(-600.0)
        assert (out_dir / "market_risk_counterfactual_unit.md").exists()
        assert "counterfactual long-block gate" in capsys.readouterr().out

    def test_insufficient_when_no_scores(self, ledger_path, tmp_path, capsys):
        rc = main(
            [
                "--parquet-root",
                str(tmp_path / "empty"),
                "--ledger",
                str(ledger_path),
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        assert "insufficient data" in capsys.readouterr().out
        assert not (tmp_path / "reports").exists()

    def test_insufficient_when_ledger_missing(self, store, tmp_path, capsys):
        rc = main(
            [
                "--parquet-root",
                str(store.root),
                "--ledger",
                str(tmp_path / "missing.db"),
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        assert "insufficient data" in capsys.readouterr().out

    def test_insufficient_when_no_trades_match(
        self, store, ledger_path, tmp_path, capsys
    ):
        rc = main(
            [
                "--parquet-root",
                str(store.root),
                "--ledger",
                str(ledger_path),
                "--start",
                "2027-01-01",
                "--end",
                "2027-12-31",
                "--out-dir",
                str(tmp_path / "reports"),
            ]
        )
        assert rc == 0
        assert "insufficient data" in capsys.readouterr().out
        assert not (tmp_path / "reports").exists()
