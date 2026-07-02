"""Smoke tests for scripts/backfill_market_structure.py (Wave 2b).

Hermetic: canned KIS/KRX/Yahoo fakes, tmp_path Parquet store, explicit
config — no network, no Redis.
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from scripts.backfill_market_structure import (
    fetch_fx_updates,
    load_foreign_futures_csv,
    recompute_derived,
    run_backfill,
)
from services.market_structure_collector.config import MarketStructureCollectorConfig
from shared.storage.market_structure_store import ParquetMarketStructureStore

START = date(2026, 6, 29)  # Mon
END = date(2026, 7, 1)  # Wed
TRADING_DAYS = [date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1)]


class _Calendar:
    def get_trading_days_in_range(self, start, end):
        return [day for day in TRADING_DAYS if start <= day <= end]

    def is_market_day(self, day):
        return day in TRADING_DAYS


class FakeKISClient:
    async def fetch_program_trade_daily(self, start, end, *, market_div="J"):
        rows = []
        for day in TRADING_DAYS:
            if start <= day <= end:
                rows.append(
                    {
                        "stck_bsop_date": day.strftime("%Y%m%d"),
                        "whol_ntby_tr_pbmn": str(100 * day.day),
                    }
                )
        return rows

    async def fetch_index_daily_candles(
        self, index_code, start, end, *, market_div="U"
    ):
        return [
            {
                "stck_bsop_date": day.strftime("%Y%m%d"),
                "bstp_nmix_prpr": f"{379.0 + i:.2f}",
            }
            for i, day in enumerate(TRADING_DAYS)
            if start <= day <= end
        ]


class FakeKRXClient:
    def get_kospi200_futures(self, base_date):
        day = int(base_date[6:8])
        return [
            SimpleNamespace(
                product_name="코스피200 F 202609",
                close_price=380.0 + day * 0.1,
                volume=250_000,
                open_interest=240_000 + day * 100,
            ),
            SimpleNamespace(
                product_name="미니코스피200 F 202609",
                close_price=380.0,
                volume=90_000,
                open_interest=50_000,
            ),
        ]


def _fake_yahoo_daily(symbol, start, end):
    closes = {}
    cursor = start
    i = 0
    while cursor <= end:
        if cursor.weekday() < 5:
            base = {"KRW=X": 1_380.0, "ES=F": 5_600.0, "NQ=F": 20_000.0}.get(
                symbol, 5_000.0
            )
            closes[cursor] = base + i
            i += 1
        cursor = cursor.__class__.fromordinal(cursor.toordinal() + 1)
    return closes


@pytest.fixture
def store(tmp_path):
    return ParquetMarketStructureStore(tmp_path / "market")


@pytest.fixture
def config():
    return MarketStructureCollectorConfig()


def _run(store, config, **kwargs):
    defaults: dict = {
        "start": START,
        "end": END,
        "components": ["program", "oi", "k200", "fx"],
        "store": store,
        "config": config,
        "kis_client": FakeKISClient(),
        "krx_client": FakeKRXClient(),
        "yahoo_daily": _fake_yahoo_daily,
        "calendar": _Calendar(),
    }
    defaults.update(kwargs)
    return asyncio.run(run_backfill(**defaults))


class TestDryRun:
    def test_dry_run_writes_nothing_and_reports_counts(self, store, config):
        report = _run(store, config, dry_run=True)

        assert report["dry_run"] is True
        assert report["trading_days"] == 3
        assert report["rows_before"] == 0
        assert report["rows_after"] == 0
        assert report["rows_written"] == 0
        assert store.dataset_manifest()["row_count"] == 0
        # every component filled all 3 days from the fakes
        assert report["component_fill_counts"] == {
            "program": 3,
            "oi": 3,
            "k200": 3,
            "fx": 3,
        }
        assert report["gap_days"] == []
        assert report["component_gap_counts"] == {
            "program": 0,
            "oi": 0,
            "k200": 0,
            "fx": 0,
        }


class TestWritePath:
    def test_writes_close_rows_with_derived_columns(self, store, config):
        report = _run(store, config, dry_run=False)

        assert report["rows_written"] == 3
        assert report["rows_after"] == 3

        frame = store.read_range(START, END, snapshot="close")
        assert len(frame) == 3
        last = frame.iloc[-1]
        assert last["prog_net_val"] == 100.0  # whol for day=1 (2026-07-01)
        assert last["fut_close"] == pytest.approx(380.1)
        assert last["fut_oi_qty"] == 240_100.0
        assert last["k200_close"] == pytest.approx(381.0)
        assert last["usdkrw"] > 0
        # consecutive-day derived values exist from the second day onward:
        # OI 7/1 (240_100) - OI 6/30 (243_000) = -2_900 (down),
        # fut_close 380.1 < 383.0 (down) → long_liquidation quadrant
        assert last["fut_oi_change"] == pytest.approx(-2_900.0)
        assert last["oi_price_signal"] == "long_liquidation"
        assert last["basis_dev"] == pytest.approx(
            380.1 - 381.0 * (1 + 0.035 * last["days_to_expiry"] / 365.0)
        )
        assert bool(last["finalized"]) is True

    def test_rerun_is_idempotent(self, store, config):
        _run(store, config, dry_run=False)
        report = _run(store, config, dry_run=False)

        assert report["rows_before"] == 3
        assert report["rows_after"] == 3  # replace-day, no duplicates


class TestForeignFuturesCsv:
    def test_manual_csv_loaded_and_windowed(self, store, config, tmp_path):
        csv_path = tmp_path / "foreign.csv"
        csv_path.write_text(
            "date,net_qty,net_val\n"
            "2026-06-29,-1200,-30000\n"
            "2026-06-30,800,20000\n"
            "2026-07-01,-100,\n"
            "2026-07-02,999,999\n",  # outside range → dropped
            encoding="utf-8",
        )

        updates = load_foreign_futures_csv(csv_path, START, END)
        assert set(updates) == set(TRADING_DAYS)
        assert updates[date(2026, 6, 30)] == {
            "fut_foreign_net_qty": 800.0,
            "fut_foreign_net_val": 20000.0,
        }

        report = _run(
            store,
            config,
            components=["foreign_futures"],
            csv_path=csv_path,
            dry_run=False,
        )
        assert report["component_fill_counts"]["foreign_futures"] == 3

        frame = store.read_range(START, END, snapshot="close")
        last = frame.iloc[-1]
        # cum20 = rolling sum over the (short) history
        assert last["fut_foreign_net_qty_cum20"] == pytest.approx(-1200 + 800 - 100)


class TestFxOvernightAlignment:
    def test_overseas_change_uses_last_us_bar_before_kst_day(self):
        symbols = {
            "usdkrw_realtime": "KRW=X",
            "es_futures": "ES=F",
            "nq_futures": "NQ=F",
            "sox": "^SOX",
        }
        updates = fetch_fx_updates(_fake_yahoo_daily, symbols, TRADING_DAYS, START, END)
        # For KST day D the change is between the two most recent bars < D.
        day = date(2026, 6, 30)
        closes = _fake_yahoo_daily("ES=F", START - date.resolution * 10, END)
        prior = sorted(d for d in closes if d < day)
        expected = (closes[prior[-1]] / closes[prior[-2]] - 1.0) * 100.0
        assert updates[day]["es_futures_change_pct"] == pytest.approx(expected)
        # O11-①: usdkrw is the last confirmed bar strictly before D — the bar
        # dated D only finalizes ~07:00 KST on D+1, past the close cutoff.
        fx_closes = _fake_yahoo_daily("KRW=X", START - date.resolution * 10, END)
        fx_prior = sorted(d for d in fx_closes if d < day)
        assert updates[day]["usdkrw"] == fx_closes[fx_prior[-1]]
        assert updates[day]["usdkrw"] != fx_closes[day]

    def test_usdkrw_never_uses_same_day_or_future_bar(self):
        symbols = {"usdkrw_realtime": "KRW=X"}
        updates = fetch_fx_updates(_fake_yahoo_daily, symbols, TRADING_DAYS, START, END)
        fx_closes = _fake_yahoo_daily("KRW=X", START - date.resolution * 10, END)
        for day in TRADING_DAYS:
            prior = sorted(d for d in fx_closes if d < day)
            assert updates[day]["usdkrw"] == fx_closes[prior[-1]]


class TestRecomputeDerived:
    def test_gap_report_lists_uncovered_trading_days(self, store, config):
        class _OnlyProgramKIS(FakeKISClient):
            async def fetch_program_trade_daily(self, start, end, *, market_div="J"):
                return [
                    {
                        "stck_bsop_date": "20260629",
                        "whol_ntby_tr_pbmn": "10",
                    }
                ]

        report = _run(
            store,
            config,
            components=["program"],
            kis_client=_OnlyProgramKIS(),
            dry_run=True,
        )
        assert report["component_gap_counts"]["program"] == 2
        assert report["gap_days"] == ["2026-06-30", "2026-07-01"]

    def test_ma_alignment_requires_all_windows(self, config):
        rows = {day: {"k200_close": 100.0 + i} for i, day in enumerate(TRADING_DAYS)}
        recompute_derived(rows, TRADING_DAYS, config)
        last = rows[TRADING_DAYS[-1]]
        # only 3 observations → ma20/ma60 are None → no alignment label
        assert last["k200_ma5"] is None
        assert last["k200_ma_alignment"] is None
        assert last["k200_ret_20d"] is None
