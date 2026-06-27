from datetime import datetime, timedelta

import pytest

from shared.streaming.candle_warmup import (
    StockPrewarmConfig,
    _df_tail_to_candles,
    warmup_engine,
)


class _Engine:
    def __init__(self, warm=()):
        self._warm = set(warm)
        self.seeded = {}
        self.daily = {}

    def is_warm(self, s):
        return s in self._warm

    def seed_candles(self, s, candles, minute=None):
        self.seeded[s] = candles

    def seed_daily_candles(self, s, candles):
        self.daily[s] = candles


class _DF:
    """Minimal DataFrame stand-in: list of dict rows."""

    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    @property
    def iloc(self):
        outer = self

        class _ILoc:
            def __getitem__(self, sl):
                return _DF(outer._rows[sl])

        return _ILoc()

    def iterrows(self):
        yield from enumerate(self._rows)


def _bars(n, base=100.0):
    return [
        {"open": base, "high": base + 1, "low": base - 1, "close": base, "volume": 10}
        for _ in range(n)
    ]


class _Store:
    def __init__(self, minute=None, daily=None):
        self._minute = minute
        self._daily = daily

    def get_minute_bars(self, s, start=None, limit=None):
        return _DF(self._minute) if self._minute is not None else _DF([])

    def get_daily_bars(self, s, start=None, limit=None):
        return _DF(self._daily) if self._daily is not None else _DF([])


class _Kis:
    def __init__(self, rate_limited=False, rest_bars=None):
        self.is_rate_limited = rate_limited
        self._rest = rest_bars
        self.calls = 0

    async def get_minute_bars(self, s, count=30):
        self.calls += 1
        return list(self._rest or [])


@pytest.mark.asyncio
async def test_parquet_hit_seeds_minute_and_daily_no_rest():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=_bars(120), daily=_bars(252))
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "005930", store=store, kis_client=kis, config=cfg)
    assert res.source == "parquet"
    assert res.minute_seeded == 120
    assert res.daily_seeded == 252
    assert kis.calls == 0  # parquet hit → no REST
    assert "005930" in eng.seeded and "005930" in eng.daily


@pytest.mark.asyncio
async def test_parquet_miss_falls_back_to_rest():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=[], daily=_bars(252))
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "rest"
    assert res.minute_seeded == 30
    assert kis.calls == 1
    assert eng.daily["123456"]  # daily still seeded from parquet


@pytest.mark.asyncio
async def test_rest_skipped_when_rate_limited():
    eng = _Engine()
    kis = _Kis(rate_limited=True, rest_bars=_bars(30))
    store = _Store(minute=[], daily=[])
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "none"
    assert res.minute_seeded == 0
    assert kis.calls == 0  # rate limited → no REST call (IP-ban guard)


@pytest.mark.asyncio
async def test_rest_skipped_when_disabled():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=[], daily=[])
    cfg = StockPrewarmConfig(rest_enabled=False)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "none"
    assert kis.calls == 0


@pytest.mark.asyncio
async def test_already_warm_is_noop():
    eng = _Engine(warm=("005930",))
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=_bars(120))
    res = await warmup_engine(
        eng, "005930", store=store, kis_client=kis, config=StockPrewarmConfig()
    )
    assert res.source == "none"
    assert res.minute_seeded == 0
    assert "005930" not in eng.seeded


@pytest.mark.asyncio
async def test_exception_is_best_effort():
    class _Boom:
        def get_minute_bars(self, *a, **k):
            raise RuntimeError("parquet down")

        def get_daily_bars(self, *a, **k):
            raise RuntimeError("parquet down")

    eng = _Engine()
    res = await warmup_engine(
        eng, "x", store=_Boom(), kis_client=None, config=StockPrewarmConfig()
    )
    assert res.source == "none"
    assert res.minute_seeded == 0


@pytest.mark.asyncio
async def test_seed_daily_false_skips_daily_seeding():
    """seed_daily=False must not call seed_daily_candles; minute seeding still happens."""
    eng = _Engine()
    store = _Store(minute=_bars(60), daily=_bars(252))
    cfg = StockPrewarmConfig()
    res = await warmup_engine(
        eng, "005930", store=store, kis_client=None, config=cfg, seed_daily=False
    )
    assert res.daily_seeded == 0
    assert "005930" not in eng.daily  # seed_daily_candles NOT called
    assert res.minute_seeded == 60  # minute seeding unaffected
    assert res.source == "parquet"


@pytest.mark.asyncio
async def test_seed_daily_true_default_still_seeds_daily():
    """Default (seed_daily=True) must still seed daily — regression guard."""
    eng = _Engine()
    store = _Store(minute=_bars(60), daily=_bars(252))
    cfg = StockPrewarmConfig()
    res = await warmup_engine(eng, "005930", store=store, kis_client=None, config=cfg)
    assert res.daily_seeded == 252
    assert "005930" in eng.daily  # seed_daily_candles was called


# ---------------------------------------------------------------------------
# _df_tail_to_candles must carry datetime/minute so seed_candles can bucket
# seeded 1m bars into the correct MTF timeframes (Fix #2).
#
# Without datetime/minute every seeded bar collapsed into MTF bucket 0
# (minute=0), so no 5m bar ever closed → is_warm() stayed False all morning
# (~100-min cold dead-zone) and no eval happened. The 1m datetime is what the
# engine derives the HHMM minute from (mirroring the live tick path).
# ---------------------------------------------------------------------------


def _minute_bars(n, start=None, base=100.0):
    """Minute bars shaped like the parquet store output (datetime column)."""
    start = start or datetime(2026, 6, 24, 9, 0)
    return [
        {
            "datetime": start + timedelta(minutes=i),
            "open": base,
            "high": base + 1,
            "low": base - 1,
            "close": base,
            "volume": 10,
        }
        for i in range(n)
    ]


def test_df_tail_to_candles_carries_datetime():
    """Seed dicts must include datetime (so seed_candles can derive HHMM minute)."""
    df = _DF(_minute_bars(5))
    out = _df_tail_to_candles(df, 5)

    assert len(out) == 5
    assert all("datetime" in c for c in out), "seed dicts must carry datetime"
    # OHLCV still present and coerced to float (existing contract).
    first = out[0]
    assert first["open"] == 100.0 and first["close"] == 100.0
    assert first["datetime"] == datetime(2026, 6, 24, 9, 0)


def test_df_tail_to_candles_without_datetime_column_is_safe():
    """Defensive: rows lacking a datetime column still produce OHLCV seeds."""
    df = _DF(_bars(3))  # no datetime key
    out = _df_tail_to_candles(df, 3)

    assert len(out) == 3
    assert all("datetime" not in c for c in out)
    assert out[0]["open"] == 100.0


def test_seeded_minute_bars_warm_the_engine_via_mtf_5m():
    """The diagnosis repro: 120 seeded 1m bars must close 5m bars and warm.

    Feeding _df_tail_to_candles output through seed_candles must advance the 5m
    MTF accumulator (5m_closed > 0) and report is_warm()==True. Before the fix
    the seeds had no datetime → minute=0 → 5m_closed=0 → is_warm()==False.
    """
    from services.trading.indicator_engine import StreamingIndicatorEngine

    engine = StreamingIndicatorEngine(
        bb_period=20,
        mtf_timeframes=[5],
        mtf_warmth_timeframe=5,
        staleness_seconds=0,
    )

    df = _DF(_minute_bars(120))
    candles = _df_tail_to_candles(df, 120)
    engine.seed_candles("005930", candles)

    closed_5m = engine.mtf_total_appended("005930", 5)
    assert closed_5m > 0, "seeded 1m bars must roll up into closed 5m bars"
    assert engine.is_warm("005930") is True, "120 seeded 1m bars must warm the engine"


def test_seeded_minute_bars_collapse_to_bucket_zero_without_datetime():
    """Regression contract: dropping datetime collapses every bar to bucket 0.

    Documents the failure mode the fix prevents — same 120 bars with no
    datetime/minute never close a 5m bar, so the engine stays cold.
    """
    from services.trading.indicator_engine import StreamingIndicatorEngine

    engine = StreamingIndicatorEngine(
        bb_period=20,
        mtf_timeframes=[5],
        mtf_warmth_timeframe=5,
        staleness_seconds=0,
    )
    # Bars without datetime/minute (the pre-fix _df_tail_to_candles shape).
    engine.seed_candles("005930", _bars(120))

    assert engine.mtf_total_appended("005930", 5) == 0
    assert engine.is_warm("005930") is False
