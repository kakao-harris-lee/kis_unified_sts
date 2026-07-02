"""Unit tests for services.market_structure_collector (Wave 2b).

Hermetic: no real network / Redis / KIS. Redis is fakeredis (sync,
decode_responses), the store is ParquetMarketStructureStore on tmp_path,
KIS/KRX are canned fakes, and the macro overnight read is a stub snapshot.
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import date, datetime
from types import SimpleNamespace

import fakeredis
import pytest

from services.market_structure_collector import derived
from services.market_structure_collector.config import (
    DEFAULT_COMPONENTS,
    MarketStructureCollectorConfig,
)
from services.market_structure_collector.main import (
    _coverage,
    _read_night_close,
    collect_close,
    collect_premarket,
    compute_basis_columns,
    publish_row,
)
from shared.storage.market_structure_store import ParquetMarketStructureStore

TRADE_DAY = date(2026, 7, 2)  # Thursday, KRX market day
PREV_DAY = date(2026, 7, 1)


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


class _ClosedCalendar:
    def is_market_day(self, _day: date) -> bool:
        return False


class FakeKISClient:
    """Canned KIS quotation TR responses (see shared/kis/client.py wrappers)."""

    def __init__(self, *, fail: set[str] | None = None) -> None:
        self.fail = fail or set()
        self.calls: list[tuple] = []

    async def fetch_market_investor_trend(self, market_code, product_code):
        self.calls.append(("investor_trend", market_code, product_code))
        if "foreign_futures" in self.fail:
            raise RuntimeError("boom")
        return [{"frgn_ntby_qty": "-1,250", "frgn_ntby_tr_pbmn": "-31500"}]

    async def fetch_program_trade_daily(self, start, end, *, market_div="J"):
        self.calls.append(("program", start, end, market_div))
        if "program" in self.fail:
            raise RuntimeError("boom")
        return [
            {
                "stck_bsop_date": start.strftime("%Y%m%d"),
                "arbt_ntby_tr_pbmn": "120",
                "nabt_ntby_tr_pbmn": "-320",
            }
        ]

    async def get_current_price(self, symbol):
        self.calls.append(("quote", symbol))
        if "futures_quote" in self.fail:
            raise RuntimeError("boom")
        return {
            "code": symbol,
            "close": 381.4,
            "change": -0.0075,  # fraction (futs_prdy_ctrt / 100)
            "open_interest": 248_100.0,
            "open_interest_change": 1_530.0,
        }

    async def fetch_index_price(self, index_code, *, market_div="U"):
        self.calls.append(("index", index_code, market_div))
        if "k200" in self.fail:
            raise RuntimeError("boom")
        return {"bstp_nmix_prpr": "380.11", "bstp_nmix_prdy_ctrt": "-0.62"}


class FakeKRXCollector:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def get_investor_trading(self):
        if self.fail:
            raise RuntimeError("krx down")
        return {
            "foreign_net": -2_310.0,
            "institution_net": 1_050.0,
            "retail_net": 1_260.0,
        }


def _macro_stub():
    return SimpleNamespace(
        usdkrw=1_391.5,
        usdkrw_realtime=1_392.1,
        es_futures=5_610.25,
        es_futures_change_pct=-0.42,
        nq_futures=20_310.5,
        nq_futures_change_pct=-0.77,
        sox=5_120.4,
        sox_change_pct=-1.31,
    )


@pytest.fixture
def redis():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(tmp_path):
    return ParquetMarketStructureStore(tmp_path / "market")


@pytest.fixture
def config():
    return MarketStructureCollectorConfig()


@pytest.fixture
def macro(monkeypatch):
    snap = _macro_stub()
    monkeypatch.setattr(
        "services.market_structure_collector.main.read_latest_macro_snapshot",
        lambda _redis, _stream: snap,
    )
    return snap


def _run_close(
    redis, store, config, *, kis=None, krx=None, day=TRADE_DAY, calendar=None
):
    return asyncio.run(
        collect_close(
            kis_client=kis or FakeKISClient(),
            krx_collector=krx or FakeKRXCollector(),
            store=store,
            redis=redis,
            config=config,
            trade_date=day,
            calendar=calendar or _AlwaysOpenCalendar(),
        )
    )


def _stored_row(store, day, snapshot):
    frame = store.read_range(day, day, snapshot=snapshot)
    assert len(frame) == 1
    return frame.iloc[0].to_dict()


# ---------------------------------------------------------------------------
# close mode
# ---------------------------------------------------------------------------


class TestCollectClose:
    def test_full_row_assembled_and_persisted(self, redis, store, config, macro):
        assert _run_close(redis, store, config) == 0

        row = _stored_row(store, TRADE_DAY, "close")
        assert row["fut_foreign_net_qty"] == -1250.0
        assert row["fut_foreign_net_val"] == -31500.0
        # whole = arb + nonarb fallback when whole key is absent
        assert row["prog_net_val"] == pytest.approx(120 - 320)
        assert row["fut_close"] == 381.4
        assert row["fut_change_pct"] == pytest.approx(-0.75)
        assert row["fut_oi_qty"] == 248_100.0
        assert row["k200_close"] == 380.11
        assert row["stock_foreign_net_val"] == -2310.0
        assert row["usdkrw"] == 1391.5
        assert row["es_futures_change_pct"] == -0.42
        # basis columns come from the shared fair-value formula
        assert row["basis"] == pytest.approx(381.4 - 380.11)
        assert row["days_to_expiry"] >= 0
        # price down + OI up = new shorts (roadmap §4.1 quadrant)
        assert row["oi_price_signal"] == "new_shorts"
        assert row["coverage_ratio"] == 1.0
        assert json.loads(row["missing_components"]) == []
        assert bool(row["finalized"]) is True

    def test_redis_publication_keys_and_ttls(self, redis, store, config, macro):
        _run_close(redis, store, config)

        latest = redis.hgetall(config.redis.latest_key)
        assert latest["snapshot"] == "close"
        assert latest["trade_date"] == TRADE_DAY.isoformat()
        assert latest["fut_foreign_net_qty"] == "-1250.0"
        assert latest["missing_components"] == "[]"
        ttl = redis.ttl(config.redis.latest_key)
        assert 0 < ttl <= config.redis.latest_ttl_seconds

        entries = redis.xrange(config.redis.stream_key)
        assert len(entries) == 1
        assert entries[0][1]["snapshot"] == "close"
        stream_ttl = redis.ttl(config.redis.stream_key)
        assert 0 < stream_ttl <= config.redis.stream_ttl_seconds

    def test_cum20_window_published_and_idempotent(self, redis, store, config, macro):
        _run_close(redis, store, config)
        _run_close(redis, store, config)  # re-run same day replaces, not appends

        raw = redis.get(config.redis.cum20_key)
        payload = json.loads(raw)
        assert payload["window"] == [[TRADE_DAY.isoformat(), -1250.0]]
        assert payload["cum"] == -1250.0
        ttl = redis.ttl(config.redis.cum20_key)
        assert 0 < ttl <= config.redis.cum20_ttl_seconds

        row = _stored_row(store, TRADE_DAY, "close")
        assert row["fut_foreign_net_qty_cum20"] == -1250.0

    def test_missing_components_recorded_not_synthesized(
        self, redis, store, config, monkeypatch
    ):
        # macro stream empty + KIS foreign futures/program failing
        monkeypatch.setattr(
            "services.market_structure_collector.main.read_latest_macro_snapshot",
            lambda _redis, _stream: None,
        )
        kis = FakeKISClient(fail={"foreign_futures", "program"})
        krx = FakeKRXCollector(fail=True)
        assert _run_close(redis, store, config, kis=kis, krx=krx) == 0

        row = _stored_row(store, TRADE_DAY, "close")
        missing = json.loads(row["missing_components"])
        assert set(missing) == {
            "foreign_futures",
            "program",
            "stock_investor",
            "fx",
            "overseas",
        }
        assert row["coverage_ratio"] == pytest.approx(3 / 8)
        # never synthesized
        assert "fut_foreign_net_qty" not in row or (
            isinstance(row.get("fut_foreign_net_qty"), float)
            and math.isnan(row["fut_foreign_net_qty"])
        )
        # cum20 window is not published without the day's confirmed value
        assert redis.get(config.redis.cum20_key) is None

    def test_derived_use_prior_close_history(self, redis, store, config, macro):
        # Seed 5 prior close rows so basis_dev_ma5 / usdkrw_ret_5d activate.
        prior_days = [date(2026, 6, d) for d in (24, 25, 26, 29, 30)]
        for i, day in enumerate(prior_days):
            store.replace_day(
                day,
                "close",
                {
                    "basis_dev": 0.10 * i,
                    "usdkrw": 1_380.0 + i,
                    "fut_foreign_net_qty": 100.0 * i,
                },
            )
        _run_close(redis, store, config)

        row = _stored_row(store, TRADE_DAY, "close")
        # basis_dev_ma5 = mean of last 5 observations incl. today's
        expected_tail = [0.10, 0.20, 0.30, 0.40, row["basis_dev"]]
        assert row["basis_dev_ma5"] == pytest.approx(sum(expected_tail) / 5)
        # usdkrw 5d return: base is the observation 5 steps back (1380.0)
        assert row["usdkrw_ret_5d"] == pytest.approx((1391.5 / 1380.0 - 1.0) * 100.0)
        # cum window rebuilt from parquet history + today's value
        payload = json.loads(redis.get(config.redis.cum20_key))
        assert len(payload["window"]) == 6
        assert payload["cum"] == pytest.approx(0 + 100 + 200 + 300 + 400 - 1250)

    def test_non_market_day_skips(self, redis, store, config, macro):
        rc = _run_close(redis, store, config, calendar=_ClosedCalendar())
        assert rc == 0
        assert store.read_range(TRADE_DAY, TRADE_DAY).empty
        assert not redis.exists(config.redis.latest_key)


# ---------------------------------------------------------------------------
# premarket mode
# ---------------------------------------------------------------------------


def _run_premarket(redis, store, config, *, day=TRADE_DAY, calendar=None):
    return asyncio.run(
        collect_premarket(
            store=store,
            redis=redis,
            config=config,
            trade_date=day,
            calendar=calendar or _AlwaysOpenCalendar(),
        )
    )


class TestCollectPremarket:
    def _seed_prev_close(self, store):
        store.replace_day(
            PREV_DAY,
            "close",
            {
                "fut_foreign_net_qty": -900.0,
                "fut_close": 380.0,
                "k200_close": 379.2,
                "basis_dev": -0.2,
                "prog_net_val": 55.0,
                "usdkrw": 1_388.0,
                "es_futures_change_pct": 0.15,
                "nq_futures_change_pct": 0.30,
                "sox_change_pct": 0.10,
                "fut_oi_qty": 240_000.0,
                "stock_foreign_net_val": -100.0,
            },
        )

    def test_carries_prev_close_and_merges_overnight(self, redis, store, config, macro):
        self._seed_prev_close(store)
        redis.hset(
            config.redis.night_close_key,
            mapping={
                "close": "412.35",
                "mrkt_basis": "0.85",
                "open_interest": "24810",
                "asof_ts": "2026-07-02T05:59:30+09:00",
                "product_code": "101W9000",
            },
        )

        assert _run_premarket(redis, store, config) == 0

        row = _stored_row(store, TRADE_DAY, "premarket")
        # carried from the previous close row
        assert row["fut_foreign_net_qty"] == -900.0
        assert row["prog_net_val"] == 55.0
        assert row["source_trade_date"] == PREV_DAY.isoformat()
        # overnight macro overwrites the carried FX/overseas values
        assert row["usdkrw"] == 1391.5
        assert row["es_futures_change_pct"] == -0.42
        # night capture merged with night_ prefix; text fields kept as strings
        assert row["night_close"] == 412.35
        assert row["night_mrkt_basis"] == 0.85
        assert row["night_asof_ts"] == "2026-07-02T05:59:30+09:00"
        assert row["night_product_code"] == "101W9000"
        assert bool(row["finalized"]) is False
        assert row["coverage_ratio"] == 1.0

        latest = redis.hgetall(config.redis.latest_key)
        assert latest["snapshot"] == "premarket"
        assert latest["night_close"] == "412.35"

    def test_overnight_only_when_no_prior_close(self, redis, store, config, macro):
        assert _run_premarket(redis, store, config) == 0

        row = _stored_row(store, TRADE_DAY, "premarket")
        missing = json.loads(row["missing_components"])
        assert set(missing) == {
            "foreign_futures",
            "program",
            "oi",
            "k200",
            "basis",
            "stock_investor",
        }
        assert row["coverage_ratio"] == pytest.approx(2 / 8)
        assert row["usdkrw"] == 1391.5

    def test_does_not_carry_same_day_close(self, redis, store, config, macro):
        # A same-day (or future) close row must never leak into premarket.
        store.replace_day(TRADE_DAY, "close", {"fut_foreign_net_qty": -1.0})
        assert _run_premarket(redis, store, config) == 0

        row = _stored_row(store, TRADE_DAY, "premarket")
        assert "fut_foreign_net_qty" not in row or (
            isinstance(row.get("fut_foreign_net_qty"), float)
            and math.isnan(row["fut_foreign_net_qty"])
        )
        assert "source_trade_date" not in row or not isinstance(
            row.get("source_trade_date"), str
        )

    def test_non_market_day_skips(self, redis, store, config, macro):
        rc = _run_premarket(redis, store, config, calendar=_ClosedCalendar())
        assert rc == 0
        assert store.read_range(TRADE_DAY, TRADE_DAY).empty


# ---------------------------------------------------------------------------
# night_close parsing
# ---------------------------------------------------------------------------


class TestReadNightClose:
    def test_reads_hash_with_prefix(self, redis, config):
        redis.hset(
            config.redis.night_close_key,
            mapping={"close": "411.0", "dprt": "-0.15", "product_code": "101W9000"},
        )
        columns = _read_night_close(redis, config)
        assert columns == {
            "night_close": 411.0,
            "night_dprt": -0.15,
            "night_product_code": "101W9000",
        }

    def test_json_string_fallback(self, redis, config):
        redis.set(
            config.redis.night_close_key,
            json.dumps({"close": 410.5, "asof_ts": "2026-07-02T05:59:00"}),
        )
        columns = _read_night_close(redis, config)
        assert columns["night_close"] == 410.5
        assert columns["night_asof_ts"] == "2026-07-02T05:59:00"

    def test_absent_key_is_soft_miss(self, redis, config):
        assert _read_night_close(redis, config) == {}


# ---------------------------------------------------------------------------
# publish_row contract
# ---------------------------------------------------------------------------


class TestPublishRow:
    def test_previous_snapshot_fields_do_not_linger(self, redis, config):
        publish_row(redis, config, {"snapshot": "close", "only_in_close": 1.0})
        publish_row(redis, config, {"snapshot": "premarket"})
        latest = redis.hgetall(config.redis.latest_key)
        assert latest["snapshot"] == "premarket"
        assert "only_in_close" not in latest

    def test_none_and_structures_flattened(self, redis, config):
        publish_row(
            redis,
            config,
            {
                "snapshot": "close",
                "trade_date": TRADE_DAY,
                "asof": datetime(2026, 7, 2, 18, 40),
                "empty": None,
                "missing_components": ["fx"],
            },
        )
        latest = redis.hgetall(config.redis.latest_key)
        assert latest["empty"] == ""
        assert latest["trade_date"] == "2026-07-02"
        assert latest["asof"] == "2026-07-02T18:40:00"
        assert json.loads(latest["missing_components"]) == ["fx"]


# ---------------------------------------------------------------------------
# derived computations (pure)
# ---------------------------------------------------------------------------


class TestOiPriceSignal:
    @pytest.mark.parametrize(
        ("price", "oi", "expected"),
        [
            (0.5, 100.0, derived.SIGNAL_NEW_LONGS),
            (-0.5, 100.0, derived.SIGNAL_NEW_SHORTS),
            (0.5, -100.0, derived.SIGNAL_SHORT_COVERING),
            (-0.5, -100.0, derived.SIGNAL_LONG_LIQUIDATION),
            (0.0, 100.0, derived.SIGNAL_NEUTRAL),
            (0.5, 0.0, derived.SIGNAL_NEUTRAL),
        ],
    )
    def test_quadrants_and_boundaries(self, price, oi, expected):
        assert derived.oi_price_signal(price, oi) == expected

    @pytest.mark.parametrize(
        ("price", "oi"),
        [(None, 100.0), (0.5, None), (float("nan"), 1.0), (1.0, float("nan"))],
    )
    def test_missing_inputs_return_none(self, price, oi):
        assert derived.oi_price_signal(price, oi) is None


class TestCumWindow:
    def test_update_inserts_sorts_and_trims(self):
        window = [["2026-06-30", 10.0], ["2026-06-29", 5.0]]
        updated = derived.update_cum_window(window, date(2026, 7, 1), -3.0, size=2)
        assert updated == [["2026-06-30", 10.0], ["2026-07-01", -3.0]]

    def test_update_replaces_same_date(self):
        window = [["2026-07-01", 10.0]]
        updated = derived.update_cum_window(window, date(2026, 7, 1), -3.0, size=20)
        assert updated == [["2026-07-01", -3.0]]

    def test_update_drops_malformed_entries(self):
        window = [["2026-06-30"], ["2026-06-29", None], ["2026-06-28", 4.0]]
        updated = derived.update_cum_window(window, date(2026, 7, 1), 1.0, size=20)
        assert updated == [["2026-06-28", 4.0], ["2026-07-01", 1.0]]

    def test_sum(self):
        assert derived.cum_window_sum([]) is None
        assert derived.cum_window_sum([["a", 1.0], ["b", -4.0]]) == -3.0


class TestMovingAverageAndReturns:
    def test_moving_average_underfilled_returns_none(self):
        assert derived.moving_average([1.0, 2.0], 3) is None
        assert derived.moving_average([1.0, 2.0, 3.0], 0) is None

    def test_moving_average_exact_and_trailing(self):
        assert derived.moving_average([1.0, 2.0, 3.0], 3) == 2.0
        assert derived.moving_average([9.0, 1.0, 2.0, 3.0], 3) == 2.0

    def test_moving_average_skips_none_and_nan(self):
        assert derived.moving_average([None, 1.0, float("nan"), 3.0], 2) == 2.0

    def test_pct_return_boundaries(self):
        assert derived.pct_return([100.0], 1) is None  # needs periods+1
        assert derived.pct_return([100.0, 110.0], 1) == pytest.approx(10.0)
        assert derived.pct_return([0.0, 110.0], 1) is None  # zero base
        series = [100.0, 1.0, 2.0, 3.0, 4.0, 105.0]
        assert derived.pct_return(series, 5) == pytest.approx(5.0)


class TestMaAlignment:
    def test_bullish_when_short_above_long(self):
        assert derived.ma_alignment([110.0, 105.0, 100.0]) == "bullish"

    def test_bearish_when_short_below_long(self):
        assert derived.ma_alignment([100.0, 105.0, 110.0]) == "bearish"

    def test_mixed_and_equal_are_not_directional(self):
        assert derived.ma_alignment([105.0, 100.0, 110.0]) == "mixed"
        assert derived.ma_alignment([100.0, 100.0, 100.0]) == "mixed"

    def test_missing_ma_returns_none(self):
        assert derived.ma_alignment([110.0, None, 100.0]) is None
        assert derived.ma_alignment([110.0]) is None


class TestBasisColumns:
    def test_deviation_against_theoretical_fair_value(self):
        columns = compute_basis_columns(
            fut_close=381.4,
            k200_close=380.11,
            trade_date=TRADE_DAY,
            risk_free_rate=0.035,
        )
        days = columns["days_to_expiry"]
        fair = 380.11 * (1 + 0.035 * days / 365.0)
        assert columns["basis"] == pytest.approx(381.4 - 380.11)
        assert columns["basis_dev"] == pytest.approx(381.4 - fair)
        assert days >= 0

    def test_missing_inputs_yield_no_columns(self):
        assert (
            compute_basis_columns(
                fut_close=None,
                k200_close=380.0,
                trade_date=TRADE_DAY,
                risk_free_rate=0.035,
            )
            == {}
        )
        assert (
            compute_basis_columns(
                fut_close=381.0,
                k200_close=0.0,
                trade_date=TRADE_DAY,
                risk_free_rate=0.035,
            )
            == {}
        )


class TestCoverage:
    def test_any_of_semantics_for_overseas(self):
        row = {"sox_change_pct": -1.0}
        ratio, missing = _coverage(row, list(DEFAULT_COMPONENTS))
        assert "overseas" not in missing
        assert ratio == pytest.approx(1 / 8)

    def test_nan_counts_as_missing(self):
        row = {"usdkrw": float("nan")}
        _, missing = _coverage(row, ["fx"])
        assert missing == ["fx"]
