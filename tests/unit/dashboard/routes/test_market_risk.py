"""Tests for the read-only Market Risk dashboard API (Phase 1c)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

KST = ZoneInfo("Asia/Seoul")

RISK_KEY = "market:risk:latest"
STRUCTURE_KEY = "market:structure:latest"
NIGHT_KEY = "market:structure:night_close"

COMPONENTS = {
    "foreign_fut": {
        "sub": 82.0,
        "weight": 25.0,
        "contribution": 22.4,
        "raw": -18250.0,
        "asof": "2026-07-02T18:40:00",
    },
    "basis": {
        "sub": 61.0,
        "weight": 15.0,
        "contribution": 10.0,
        "raw": -0.42,
        "asof": "2026-07-02T18:40:00",
    },
}


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _publish_risk_hash(redis, *, degraded: str = "false", asof: datetime | None = None):
    asof = asof or _now_kst_naive()
    redis.hset(
        RISK_KEY,
        mapping={
            "score": "74.2",
            "score_ema3": "71.8",
            "band": "HIGH",
            "regime": "RISK_OFF",
            "degraded": degraded,
            "coverage_ratio": "0.875",
            "missing_components": json.dumps(["vol"]),
            "asof_ts": asof.isoformat(),
            "kind": "close",
            "components": json.dumps(COMPONENTS),
        },
    )


def _store(tmp_path):
    from shared.storage.market_structure_store import ParquetMarketStructureStore

    return ParquetMarketStructureStore(tmp_path / "market")


def _close_row(day: date, **overrides):
    row = {
        "asof_ts": datetime.combine(day, datetime.min.time()).replace(
            hour=18, minute=40
        ),
        "risk_score": 55.0,
        "risk_score_ema3": 54.0,
        "risk_band": "ELEVATED",
        "unified_regime": "NEUTRAL",
        "degraded": "false",
        # Engine score coverage vs collector data coverage: the history API
        # must prefer risk_coverage_ratio (Phase 1a engine column).
        "risk_coverage_ratio": 0.875,
        "coverage_ratio": 1.0,
        "sub_foreign_fut": 60.0,
        "sub_basis": 50.0,
        "sub_usdkrw": 40.0,
        "sub_program": 45.0,
        "sub_oi": 55.0,
        "sub_overseas": 35.0,
        "sub_vol": 65.0,
        "sub_trend": 30.0,
        "k200_close": 372.5,
        "fut_close": 371.9,
        "fut_foreign_net_qty": -1250.0,
        "fut_foreign_net_qty_cum20": -18250.0,
        "basis": -0.6,
        "basis_dev": -0.42,
        "fut_oi_qty": 285000.0,
        "prog_net_val": -215000000000.0,
        "usdkrw": 1391.5,
        "es_futures_change_pct": -1.2,
        "nq_futures_change_pct": -1.8,
        "sox_change_pct": -2.4,
        "oi_price_signal": "new_shorts",
        "k200_ma_alignment": "bearish",
    }
    row.update(overrides)
    return row


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def _client(monkeypatch, redis_client, store):
    from services.dashboard.routes import market_risk

    monkeypatch.setattr(market_risk, "_get_redis_client", lambda: redis_client)
    monkeypatch.setattr(market_risk, "_get_store", lambda: store)
    # Health helper shares the same Redis for the structure freshness block.
    from services.dashboard.routes import health

    monkeypatch.setattr(health, "_get_redis_client", lambda: redis_client)
    app = FastAPI()
    app.include_router(market_risk.router)
    return TestClient(app)


def test_latest_ok_with_components_and_delta(monkeypatch, tmp_path, redis_client):
    store = _store(tmp_path)
    today = datetime.now(KST).date()
    prev_day = today - timedelta(days=1)
    store.replace_day(prev_day, "close", _close_row(prev_day, risk_score=70.0))

    _publish_risk_hash(redis_client)
    redis_client.hset(
        STRUCTURE_KEY,
        mapping={
            "snapshot": "close",
            "trade_date": today.isoformat(),
            "asof": _now_kst_naive().isoformat(),
            "coverage_ratio": "0.875",
        },
    )
    redis_client.hset(
        NIGHT_KEY,
        mapping={
            "close": "370.15",
            "mrkt_basis": "-0.85",
            "dprt": "-0.23",
            "open_interest": "284500",
            "acml_vol": "10250",
            "asof_ts": _now_kst_naive().isoformat(),
            "product_code": "101W09",
        },
    )

    client = _client(monkeypatch, redis_client, store)
    body = client.get("/api/market-risk").json()

    assert body["status"] == "ok"
    risk = body["risk"]
    assert risk["score"] == pytest.approx(74.2)
    assert risk["band"] == "HIGH"
    assert risk["regime"] == "RISK_OFF"
    assert risk["degraded"] is False
    assert risk["kind"] == "close"
    assert risk["missing_components"] == ["vol"]
    assert risk["coverage_ratio"] == pytest.approx(0.875)
    # 전일 대비 Δ from the previous close row in the store.
    assert risk["prev_close_score"] == pytest.approx(70.0)
    assert risk["score_delta_1d"] == pytest.approx(4.2)
    # Contract components decode + fixed 8-row layout (missing ones null).
    components = risk["components"]
    assert set(components) >= {
        "foreign_fut",
        "basis",
        "usdkrw",
        "program",
        "oi",
        "overseas",
        "vol",
        "trend",
    }
    assert components["foreign_fut"]["sub"] == pytest.approx(82.0)
    assert components["foreign_fut"]["contribution"] == pytest.approx(22.4)
    assert components["vol"]["sub"] is None

    assert body["structure"]["status"] == "ok"
    assert body["structure"]["snapshot"] == "close"
    night = body["night_close"]
    assert night["available"] is True
    assert night["close"] == pytest.approx(370.15)
    assert night["dprt"] == pytest.approx(-0.23)


def test_latest_unavailable_when_engine_not_published(monkeypatch, redis_client):
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["status"] == "unavailable"
    assert body["risk"] is None
    assert body["structure"]["status"] == "unknown"
    assert body["night_close"]["available"] is False
    assert body["night_close"]["status"] == "missing"


# ---------------------------------------------------------------------------
# night_close staleness bound (O11-③ review): the dashboard's freshness
# check must reuse the SAME bound as the night-futures collector's Redis
# TTL (config/night_futures.yaml::redis_ttl_seconds, 183600s = 51h), not an
# independently hardcoded value that can drift from it.
# ---------------------------------------------------------------------------


def test_night_close_survives_the_friday_to_monday_weekend_gap(
    monkeypatch, redis_client
):
    """~47h48m old (Friday 06:00 close -> Monday 05:48 premarket read)."""
    from services.dashboard.routes import market_risk

    monkeypatch.setattr(market_risk, "_NIGHT_CLOSE_STALE_SECONDS", 183600)
    asof = _now_kst_naive() - timedelta(hours=47, minutes=48)
    redis_client.hset(
        NIGHT_KEY, mapping={"close": "370.15", "asof_ts": asof.isoformat()}
    )
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["night_close"]["available"] is True
    assert body["night_close"]["status"] == "ok"


def test_night_close_flags_a_missed_capture_a_day_later(monkeypatch, redis_client):
    """~71h48m old — a genuinely missed capture, must still read stale."""
    from services.dashboard.routes import market_risk

    monkeypatch.setattr(market_risk, "_NIGHT_CLOSE_STALE_SECONDS", 183600)
    asof = _now_kst_naive() - timedelta(hours=71, minutes=48)
    redis_client.hset(
        NIGHT_KEY, mapping={"close": "370.15", "asof_ts": asof.isoformat()}
    )
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["night_close"]["available"] is True
    assert body["night_close"]["status"] == "stale"


def test_default_night_close_stale_seconds_reads_the_shipped_config():
    """Config round-trip: the module-load-time default matches the shipped
    config/night_futures.yaml::redis_ttl_seconds (single source, O11-③)."""
    from services.dashboard.routes.market_risk import (
        _default_night_close_stale_seconds,
    )

    assert _default_night_close_stale_seconds() == 183600


def test_default_night_close_stale_seconds_threads_through_the_loaded_config(
    monkeypatch,
):
    """Proves the success path reads the config value, not just the fallback
    constant (both currently equal 183600, which alone can't tell them apart)."""
    from services.night_futures_collector.config import NightCloseCaptureConfig

    monkeypatch.setattr(
        NightCloseCaptureConfig,
        "load_or_default",
        classmethod(lambda cls, *a, **kw: cls(redis_ttl_seconds=999)),
    )
    from services.dashboard.routes.market_risk import (
        _default_night_close_stale_seconds,
    )

    assert _default_night_close_stale_seconds() == 999


def test_default_night_close_stale_seconds_falls_back_when_config_load_fails(
    monkeypatch,
):
    from services.night_futures_collector.config import NightCloseCaptureConfig

    def _broken(cls, *args, **kwargs):
        raise ValueError("malformed night_futures.yaml")

    monkeypatch.setattr(
        NightCloseCaptureConfig, "load_or_default", classmethod(_broken)
    )
    from services.dashboard.routes.market_risk import (
        _default_night_close_stale_seconds,
    )

    assert _default_night_close_stale_seconds() == 183600


def test_night_close_stale_seconds_module_constant_matches_the_config_default():
    """The unpatched module constant itself — not just the helper function —
    must equal the config's redis_ttl_seconds when no env override is set.

    Every other test in this file monkeypatches
    ``market_risk._NIGHT_CLOSE_STALE_SECONDS`` to a literal, so nothing else
    exercises the module-load-time assignment
    (``_NIGHT_CLOSE_STALE_SECONDS = int(os.environ.get(..., str(
    _default_night_close_stale_seconds())))``) against the real config load.
    """
    import os

    from services.dashboard.routes import market_risk
    from services.night_futures_collector.config import NightCloseCaptureConfig

    if os.environ.get("MARKET_RISK_NIGHT_STALE_SECONDS") is not None:
        pytest.skip("MARKET_RISK_NIGHT_STALE_SECONDS overridden in this environment")

    assert (
        NightCloseCaptureConfig.load_or_default().redis_ttl_seconds
        == market_risk._NIGHT_CLOSE_STALE_SECONDS
    )
    assert market_risk._NIGHT_CLOSE_STALE_SECONDS == 183600


def test_latest_degraded_flag_maps_to_status(monkeypatch, redis_client):
    _publish_risk_hash(redis_client, degraded="true")
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["status"] == "degraded"
    assert body["risk"]["degraded"] is True
    # Store unavailable → delta degrades to null instead of failing.
    assert body["risk"]["score_delta_1d"] is None


def test_latest_stale_when_publication_is_old(monkeypatch, redis_client):
    _publish_risk_hash(redis_client, asof=_now_kst_naive() - timedelta(days=2))
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["status"] == "stale"
    assert body["risk"]["stale"] is True


def test_history_returns_close_series(monkeypatch, tmp_path, redis_client):
    store = _store(tmp_path)
    today = datetime.now(KST).date()
    for offset, score in ((3, 48.0), (2, 55.0), (1, 70.0)):
        day = today - timedelta(days=offset)
        store.replace_day(day, "close", _close_row(day, risk_score=score))
    # premarket row must be excluded from the daily series
    store.replace_day(today, "premarket", _close_row(today, risk_score=99.0))

    client = _client(monkeypatch, redis_client, store)
    body = client.get("/api/market-risk/history", params={"days": 90}).json()

    assert body["status"] == "ok"
    assert body["count"] == 3
    scores = [point["risk_score"] for point in body["points"]]
    assert scores == [48.0, 55.0, 70.0]
    latest = body["points"][-1]
    assert latest["risk_band"] == "ELEVATED"
    assert latest["unified_regime"] == "NEUTRAL"
    assert latest["degraded"] is False
    # risk_coverage_ratio (engine) wins over coverage_ratio (collector).
    assert latest["coverage_ratio"] == pytest.approx(0.875)
    # column fallbacks: k200_close → kospi_close, fut_oi_qty → fut_oi
    assert latest["kospi_close"] == pytest.approx(372.5)
    assert latest["fut_oi"] == pytest.approx(285000.0)
    assert latest["fut_foreign_net_qty_cum20"] == pytest.approx(-18250.0)
    assert latest["basis_dev"] == pytest.approx(-0.42)
    assert latest["es_ovn_ret"] == pytest.approx(-1.2)
    assert latest["sub_foreign_fut"] == pytest.approx(60.0)
    assert latest["oi_price_signal"] == "new_shorts"


def test_history_days_window_filters_old_rows(monkeypatch, tmp_path, redis_client):
    store = _store(tmp_path)
    today = datetime.now(KST).date()
    old_day = today - timedelta(days=40)
    recent_day = today - timedelta(days=2)
    store.replace_day(old_day, "close", _close_row(old_day, risk_score=10.0))
    store.replace_day(recent_day, "close", _close_row(recent_day, risk_score=60.0))

    client = _client(monkeypatch, redis_client, store)
    body = client.get("/api/market-risk/history", params={"days": 7}).json()

    assert body["count"] == 1
    assert body["points"][0]["risk_score"] == pytest.approx(60.0)


def test_history_empty_when_dataset_missing(monkeypatch, tmp_path, redis_client):
    client = _client(monkeypatch, redis_client, _store(tmp_path))

    body = client.get("/api/market-risk/history").json()

    assert body["status"] == "empty"
    assert body["points"] == []
    assert body["days"] == 90


def test_history_handles_rows_without_engine_columns(
    monkeypatch, tmp_path, redis_client
):
    """Phase 0 rows (collector only, no risk_score yet) must not break."""
    store = _store(tmp_path)
    day = datetime.now(KST).date() - timedelta(days=1)
    store.replace_day(
        day,
        "close",
        {
            "asof_ts": datetime.combine(day, datetime.min.time()),
            "coverage_ratio": 0.75,
            "k200_close": 371.0,
            "basis_dev": -0.2,
        },
    )

    client = _client(monkeypatch, redis_client, store)
    body = client.get("/api/market-risk/history").json()

    assert body["status"] == "ok"
    point = body["points"][0]
    assert point["risk_score"] is None
    assert point["risk_band"] is None
    assert point["degraded"] is None
    assert point["kospi_close"] == pytest.approx(371.0)


def test_endpoint_is_read_only(monkeypatch, redis_client):
    """No mutating verbs are exposed on the market-risk surface."""
    client = _client(monkeypatch, redis_client, None)

    assert client.post("/api/market-risk").status_code == 405
    assert client.put("/api/market-risk").status_code == 405
    assert client.delete("/api/market-risk").status_code == 405
    assert client.post("/api/market-risk/history").status_code == 405


# ---------------------------------------------------------------------------
# Gate section (Phase 2E — config/market_risk_gate.yaml, display-only)
# ---------------------------------------------------------------------------


def _assert_default_gate_matrix(gate: dict) -> None:
    """Assertions valid for both the shipped YAML and the code defaults."""
    assert gate["mode"] in {"off", "shadow", "enforce"}
    assert gate["staleness_max_age_seconds"] > 0
    matrix = gate["matrix"]
    for asset in ("stock", "futures"):
        assert set(matrix[asset]) == {
            "LOW",
            "NEUTRAL",
            "ELEVATED",
            "HIGH",
            "CRITICAL",
        }
    assert matrix["stock"]["HIGH"]["allow_long"] is False
    assert matrix["stock"]["ELEVATED"]["min_confidence"] == "HIGH"
    assert matrix["stock"]["CRITICAL"]["allow_short"] is False
    assert matrix["futures"]["ELEVATED"]["size_factor"] == pytest.approx(0.7)
    assert matrix["futures"]["HIGH"]["allow_long"] is False
    assert matrix["futures"]["HIGH"]["allow_short"] is True
    assert matrix["futures"]["HIGH"]["size_factor"] == pytest.approx(0.5)
    assert matrix["futures"]["CRITICAL"]["allow_long"] is False
    assert matrix["futures"]["CRITICAL"]["allow_short"] is False


def test_latest_includes_gate_matrix_section(monkeypatch, redis_client):
    _publish_risk_hash(redis_client)
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    _assert_default_gate_matrix(body["gate"])


def test_gate_present_even_when_engine_unavailable(monkeypatch, redis_client):
    """The config-sourced gate block does not depend on the Redis hash."""
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["status"] == "unavailable"
    _assert_default_gate_matrix(body["gate"])


def test_gate_falls_back_to_defaults_when_yaml_is_malformed(monkeypatch, redis_client):
    """A broken YAML degrades to the code-default mirror, never a 500."""
    from shared.risk.market_risk_gate import MarketRiskGateConfig

    def _broken_yaml(cls, *args, **kwargs):
        raise ValueError("malformed market_risk_gate.yaml")

    monkeypatch.setattr(MarketRiskGateConfig, "from_yaml", classmethod(_broken_yaml))
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    _assert_default_gate_matrix(body["gate"])
    assert body["gate"]["mode"] == "shadow"
    assert body["gate"]["staleness_max_age_seconds"] == 21600


def test_gate_is_null_when_gate_module_unavailable(monkeypatch, redis_client):
    """Total gate failure yields gate=null so the UI keeps the static panel."""
    from services.dashboard.routes import market_risk

    monkeypatch.setattr(market_risk, "_load_gate_config", lambda: None)
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/market-risk").json()

    assert body["gate"] is None
