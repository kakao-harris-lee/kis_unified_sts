"""Tests for the Track A core dashboard API (Phase 5E — Tier 3 + holdings).

The endpoint is display-only (수동 트랙 — 자동 매매 없음) and must stay up
when either side of the contract is absent: the Tier 3 watch hash
(``portfolio:tier3:watch``) and the core holdings loader (Phase 5A lane)
degrade independently. The loader is always monkeypatched here so the tests
stay hermetic while the 5A lane lands the real module in parallel.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

KST = ZoneInfo("Asia/Seoul")

TIER3_KEY = "portfolio:tier3:watch"


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _publish_tier3_hash(
    redis,
    *,
    drawdown: str = "-0.08",
    triggered: str = "false",
    asof: datetime | None = None,
):
    asof = asof or _now_kst_naive()
    redis.hset(
        TIER3_KEY,
        mapping={
            "kospi_close": "2585.5",
            "kospi_peak": "2810.32",
            # Fixed contract: drawdown/threshold are FRACTIONS (−0.16 = −16%).
            "drawdown": drawdown,
            "trigger_threshold": "-0.15",
            "triggered": triggered,
            "asof_ts": asof.isoformat(),
        },
    )


def _sector_specs() -> dict[str, SimpleNamespace]:
    return {
        "defense": SimpleNamespace(label="방산", target_weight=0.35),
        "semis_equipment": SimpleNamespace(label="반도체 장비", target_weight=0.35),
        "robotics": SimpleNamespace(label="로보틱스", target_weight=0.15),
        "cash": SimpleNamespace(label="현금", target_weight=0.15),
    }


def _holding(**overrides) -> SimpleNamespace:
    base = {
        "symbol": "012450",
        "name": "한화에어로스페이스",
        "sector": "defense",
        "thesis": "방산 수출 구조적 성장",
        "kill_criteria": ["수주 잔고 2분기 연속 감소", "수출 규제 재도입"],
        "shares": 10.0,
        "avg_price": 250_000.0,
        "last_valuation": SimpleNamespace(date="2026-07-01", price=300_000.0),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _candidate() -> SimpleNamespace:
    return SimpleNamespace(
        symbol="277810",
        name="레인보우로보틱스",
        sector="robotics",
        thesis="협동로봇 침투율 상승",
        kill_criteria=["대기업 납품 계약 해지"],
    )


def _core_config(
    holdings: list | None = None,
    candidates: list | None = None,
    sector_weights: dict[str, float] | None = None,
    weights_raise: bool = False,
) -> SimpleNamespace:
    def _weights():
        if weights_raise:
            raise RuntimeError("valuation unavailable")
        return sector_weights if sector_weights is not None else {}

    return SimpleNamespace(
        holdings=holdings if holdings is not None else [],
        candidates=candidates if candidates is not None else [],
        sectors=_sector_specs(),
        rebalancing=SimpleNamespace(drift_threshold_pct=0.10, single_holding_max=0.25),
        sector_weights=_weights,
    )


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def _client(monkeypatch, redis_client, config=None):
    from services.dashboard.routes import portfolio

    monkeypatch.setattr(portfolio, "_get_redis_client", lambda: redis_client)
    # Hermetic: never touch the real Phase 5A loader from this suite.
    monkeypatch.setattr(portfolio, "_load_core_holdings", lambda: config)
    app = FastAPI()
    app.include_router(portfolio.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tier 3 watch (Redis contract)
# ---------------------------------------------------------------------------


def test_core_tier3_ok_parses_contract_hash(monkeypatch, redis_client):
    _publish_tier3_hash(redis_client)
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/core").json()

    assert body["status"] == "ok"
    assert body["source"] == TIER3_KEY
    # 수동 트랙 — 자동 매매 없음 fixed marker.
    assert body["manual_track"] is True
    tier3 = body["tier3"]
    assert tier3["kospi_close"] == pytest.approx(2585.5)
    assert tier3["kospi_peak"] == pytest.approx(2810.32)
    # Fractions pass through unscaled (−0.08 = −8%).
    assert tier3["drawdown"] == pytest.approx(-0.08)
    assert tier3["trigger_threshold"] == pytest.approx(-0.15)
    assert tier3["triggered"] is False
    assert tier3["stale"] is False
    assert tier3["age_s"] is not None


def test_core_tier3_triggered_flag_passes_through(monkeypatch, redis_client):
    _publish_tier3_hash(redis_client, drawdown="-0.16", triggered="true")
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/core").json()

    assert body["status"] == "ok"
    assert body["tier3"]["triggered"] is True
    assert body["tier3"]["drawdown"] == pytest.approx(-0.16)


def test_core_unavailable_when_watch_not_published(monkeypatch, redis_client):
    """Watch absent → tier3 null, but the holdings side still serves."""
    config = _core_config(holdings=[_holding()])
    client = _client(monkeypatch, redis_client, config=config)

    body = client.get("/api/portfolio/core").json()

    assert body["status"] == "unavailable"
    assert body["tier3"] is None
    assert len(body["holdings"]) == 1
    assert body["sectors"] is not None


def test_core_stale_when_watch_publication_is_old(monkeypatch, redis_client):
    _publish_tier3_hash(redis_client, asof=_now_kst_naive() - timedelta(days=3))
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/core").json()

    assert body["status"] == "stale"
    assert body["tier3"]["stale"] is True


# ---------------------------------------------------------------------------
# Core holdings (Phase 5A loader contract)
# ---------------------------------------------------------------------------


def test_core_holdings_serialization(monkeypatch, redis_client):
    _publish_tier3_hash(redis_client)
    config = _core_config(
        holdings=[
            _holding(),
            _holding(
                symbol="042700",
                name="한미반도체",
                sector="semis_equipment",
                thesis="HBM 장비 수요",
                kill_criteria=["TC 본더 경쟁 심화"],
                shares=20.0,
                avg_price=100_000.0,
                last_valuation=None,
            ),
        ],
        candidates=[_candidate()],
        sector_weights={"defense": 0.6, "semis_equipment": 0.4},
    )
    client = _client(monkeypatch, redis_client, config=config)

    body = client.get("/api/portfolio/core").json()

    first, second = body["holdings"]
    assert first["symbol"] == "012450"
    assert first["name"] == "한화에어로스페이스"
    assert first["sector"] == "defense"
    assert first["sector_label"] == "방산"
    assert first["thesis"] == "방산 수출 구조적 성장"
    assert first["kill_criteria"] == [
        "수주 잔고 2분기 연속 감소",
        "수출 규제 재도입",
    ]
    # Valuation uses the last valuation price (10 × 300,000).
    assert first["last_valuation"] == {"date": "2026-07-01", "price": 300_000.0}
    assert first["valuation"] == pytest.approx(3_000_000)
    # No last valuation → 평단 fallback (20 × 100,000).
    assert second["last_valuation"] is None
    assert second["valuation"] == pytest.approx(2_000_000)
    # Weights are fractions of the holdings total (5,000,000).
    assert first["weight"] == pytest.approx(0.6)
    assert second["weight"] == pytest.approx(0.4)

    candidate = body["candidates"][0]
    assert candidate["symbol"] == "277810"
    assert candidate["sector_label"] == "로보틱스"
    assert candidate["kill_criteria"] == ["대기업 납품 계약 해지"]

    sectors = body["sectors"]
    assert sectors["defense"] == {
        "label": "방산",
        "target_weight": pytest.approx(0.35),
        "actual_weight": pytest.approx(0.6),
    }
    # Configured sector without an actual weight → null (미산출), not 0.
    assert sectors["cash"]["target_weight"] == pytest.approx(0.15)
    assert sectors["cash"]["actual_weight"] is None

    rebalancing = body["rebalancing"]
    assert rebalancing["drift_threshold_pct"] == pytest.approx(0.10)
    assert rebalancing["single_holding_max"] == pytest.approx(0.25)


def test_core_loader_unavailable_degrades_to_null(monkeypatch, redis_client):
    """Loader import/load failure → empty holdings + null sectors (no 500)."""
    _publish_tier3_hash(redis_client)
    client = _client(monkeypatch, redis_client, config=None)

    body = client.get("/api/portfolio/core").json()

    # Tier 3 side is unaffected by the loader failure.
    assert body["status"] == "ok"
    assert body["tier3"] is not None
    assert body["holdings"] == []
    assert body["candidates"] == []
    assert body["sectors"] is None
    assert body["rebalancing"] is None


def test_core_empty_ledger_serves_sectors_and_rebalancing(monkeypatch, redis_client):
    """Loader present but no holdings recorded yet → empty lists, config kept."""
    client = _client(monkeypatch, redis_client, config=_core_config())

    body = client.get("/api/portfolio/core").json()

    assert body["holdings"] == []
    assert body["candidates"] == []
    assert set(body["sectors"]) == {"defense", "semis_equipment", "robotics", "cash"}
    assert all(spec["actual_weight"] is None for spec in body["sectors"].values())
    assert body["rebalancing"]["drift_threshold_pct"] == pytest.approx(0.10)


def test_core_sector_weights_failure_degrades_to_null_actuals(
    monkeypatch, redis_client
):
    config = _core_config(holdings=[_holding()], weights_raise=True)
    client = _client(monkeypatch, redis_client, config=config)

    body = client.get("/api/portfolio/core").json()

    assert body["sectors"]["defense"]["actual_weight"] is None
    # Holdings themselves still serialize (weight from valuations).
    assert body["holdings"][0]["weight"] == pytest.approx(1.0)


def test_core_rejects_writes(monkeypatch, redis_client):
    """수동 트랙 — no mutation surface: POST is 405, never a handler."""
    client = _client(monkeypatch, redis_client)

    assert client.post("/api/portfolio/core").status_code == 405
