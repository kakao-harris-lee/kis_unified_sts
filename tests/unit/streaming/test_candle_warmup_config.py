from shared.streaming.candle_warmup import StockPrewarmConfig


def test_defaults_are_conservative():
    c = StockPrewarmConfig()
    assert c.rest_enabled is False
    assert c.parquet_minute_limit == 120
    assert c.daily_limit == 252
    assert c.rest_count == 30
    assert c.min_candles == 20
    assert c.max_prewarm_per_cycle == 5
    assert c.minute_lookback_days == 5
    assert c.daily_lookback_days == 400


def test_load_returns_defaults_when_section_missing(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(lambda _f: {}))
    c = StockPrewarmConfig.load()
    assert c.rest_enabled is False


def test_load_reads_overrides(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(
        loader_mod.ConfigLoader,
        "load",
        staticmethod(
            lambda _f: {"stock_prewarm": {"rest_enabled": True, "max_prewarm_per_cycle": 3}}
        ),
    )
    c = StockPrewarmConfig.load()
    assert c.rest_enabled is True
    assert c.max_prewarm_per_cycle == 3
    assert c.daily_limit == 252  # untouched default
