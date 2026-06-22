import pytest

from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine


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
        for i, r in enumerate(self._rows):
            yield i, r


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
