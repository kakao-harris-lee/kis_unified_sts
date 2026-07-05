from __future__ import annotations

from services.monitoring import stream_exporter as mod


class _FakeMetric:
    def __init__(self, *_args, **_kwargs) -> None:
        self.values: list[float] = []

    def labels(self, **_labels):
        return self

    def inc(self) -> None:
        self.values.append(1.0)

    def set(self, value: float) -> None:
        self.values.append(value)


def _exporter(monkeypatch):
    monkeypatch.setattr(mod, "Counter", _FakeMetric)
    monkeypatch.setattr(mod, "Gauge", _FakeMetric)
    monkeypatch.setattr(mod.RedisClient, "get_client", lambda: object())
    return mod.StreamExporter(
        mod.ExporterConfig(streams=("market:ticks",), max_symbols_per_asset=10)
    )


def test_process_one_accepts_canonical_market_tick_schema(monkeypatch):
    exporter = _exporter(monkeypatch)

    exporter._process_one(
        "market:ticks",
        "1700000000000-0",
        {
            "schema_version": "1",
            "asset": "stock",
            "symbol": "005930",
            "price": "71500.0",
            "timestamp": "1700000000.0",
            "name": "SamsungElec",
            "volume": "7",
            "volume_is_cumulative": "false",
        },
        now=1700000001.0,
        msg_ts=1700000000.0,
    )

    key = ("stock", "005930")
    assert exporter._last_seen[key] == 1700000001.0
    assert exporter._symbol_names[key] == "SamsungElec"
    assert exporter._bars[key].close == 71500.0
    assert exporter._bars[key].volume == 7.0


def test_process_one_accepts_legacy_market_tick_aliases(monkeypatch):
    exporter = _exporter(monkeypatch)

    exporter._process_one(
        "market:ticks",
        "1700000000000-0",
        {
            "code": "005930",
            "current_price": "71500.0",
            "timestamp": "1700000000.0",
        },
        now=1700000001.0,
        msg_ts=1700000000.0,
    )

    key = ("stock", "005930")
    assert exporter._last_seen[key] == 1700000001.0
    assert exporter._bars[key].close == 71500.0


def test_process_one_preserves_exporter_legacy_price_priority(monkeypatch):
    exporter = _exporter(monkeypatch)

    exporter._process_one(
        "market:ticks",
        "1700000000000-0",
        {
            "symbol": "005930",
            "current_price": "71500.0",
            "close": "70000.0",
            "price": "69000.0",
            "timestamp": "1700000000.0",
        },
        now=1700000001.0,
        msg_ts=1700000000.0,
    )

    assert exporter._bars[("stock", "005930")].close == 71500.0
