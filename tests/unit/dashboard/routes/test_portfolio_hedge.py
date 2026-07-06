"""Tests for the read-only hedge advisor dashboard API (Phase 4B).

The advisor engine (4A lane) publishes ``portfolio:hedge:latest`` and appends
to the RuntimeLedger ``hedge_advice`` table; this API only reads both. These
tests simulate the fixed publication contract with fakeredis and a tmp SQLite
ledger so the surface is verified before the engine lands.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

KST = ZoneInfo("Asia/Seoul")

HEDGE_KEY = "portfolio:hedge:latest"


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _publish_hedge_hash(
    redis,
    *,
    advisory_active: str = "true",
    degraded: str = "false",
    asof: datetime | None = None,
    recommended: str = "3",
    band: str = "HIGH",
    v2: bool = False,
):
    """Fixed Phase 4 contract hash (mini KOSPI200 — O4)."""
    asof = asof or _now_kst_naive()
    mapping = {
        "product": "mini_kospi200",
        "multiplier": "50000",
        "futures_price": "368.5",
        "stock_long_notional": "52000000",
        "portfolio_beta": "1.08",
        "beta_notional": "56160000",
        "futures_net_contracts": "-1",
        "futures_net_notional": "-18425000",
        "net_beta_exposure": "37735000",
        "recommended_short_contracts": recommended,
        "residual_exposure_after": "-13520000",
        "band": band,
        "score": "74.2",
        "advisory_active": advisory_active,
        "reason": "HIGH 밴드 + 순 β-노출 ₩37.7M > 헤지 임계",
        "degraded": degraded,
        "missing_components": json.dumps(["portfolio_beta"]),
        "asof_ts": asof.isoformat(),
    }
    if v2:
        # HedgeAdvisorV2 append-only feasibility fields.
        mapping.update(
            {
                "target_hedge_ratio": "0.5000",
                "current_hedge_ratio": "0.3300",
                "delta_short_contracts": "1",
                "max_contracts_by_margin": "10",
                "margin_after_hedge_pct": "0.1640",
                "estimated_slippage_ticks": "",
                "roll_adjustment": "none",
                "execution_feasibility": "feasible",
                "operator_action": "place_manual_hedge",
            }
        )
    redis.hset(HEDGE_KEY, mapping=mapping)


def _create_hedge_db(tmp_path, rows: list[dict] | None = None, *, alt_schema=False):
    """Simulate the advisor lane's ``hedge_advice`` table (ledger v4).

    ``alt_schema`` uses plausible alternate column names to exercise the
    defensive candidate-column mapping.
    """
    db_path = tmp_path / "runtime_ledger.db"
    conn = sqlite3.connect(db_path)
    if alt_schema:
        conn.execute("""
            CREATE TABLE hedge_advice (
                created_at TEXT,
                risk_band TEXT,
                risk_score REAL,
                recommended_contracts INTEGER,
                net_beta_exposure REAL,
                active INTEGER
            )
            """)
        for row in rows or []:
            conn.execute(
                "INSERT INTO hedge_advice VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["asof_ts"],
                    row.get("band"),
                    row.get("score"),
                    row.get("recommended_short_contracts"),
                    row.get("net_beta_exposure"),
                    row.get("advisory_active"),
                ),
            )
    else:
        conn.execute("""
            CREATE TABLE hedge_advice (
                asof_ts TEXT,
                product TEXT,
                band TEXT,
                score REAL,
                recommended_short_contracts INTEGER,
                net_beta_exposure REAL,
                beta_notional REAL,
                futures_net_notional REAL,
                residual_exposure_after REAL,
                futures_price REAL,
                advisory_active TEXT,
                reason TEXT
            )
            """)
        for row in rows or []:
            conn.execute(
                "INSERT INTO hedge_advice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["asof_ts"],
                    row.get("product", "mini_kospi200"),
                    row.get("band", "HIGH"),
                    row.get("score", 74.2),
                    row.get("recommended_short_contracts", 3),
                    row.get("net_beta_exposure", 37_735_000.0),
                    row.get("beta_notional", 56_160_000.0),
                    row.get("futures_net_notional", -18_425_000.0),
                    row.get("residual_exposure_after", -13_520_000.0),
                    row.get("futures_price", 368.5),
                    row.get("advisory_active", "true"),
                    row.get("reason", "HIGH 밴드"),
                ),
            )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def _client(monkeypatch, redis_client, db_path=None):
    from services.dashboard.routes import portfolio

    monkeypatch.setattr(portfolio, "_get_redis_client", lambda: redis_client)
    monkeypatch.setattr(portfolio, "_ledger_db_path", lambda: db_path)
    app = FastAPI()
    app.include_router(portfolio.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/portfolio/hedge
# ---------------------------------------------------------------------------


def test_hedge_ok_parses_contract_hash(monkeypatch, redis_client):
    _publish_hedge_hash(redis_client)
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/hedge").json()

    assert body["status"] == "ok"
    assert body["source"] == HEDGE_KEY
    # 권고 전용 마커는 응답에 항상 고정된다 (자동 주문 없음).
    assert body["advisory_only"] is True
    hedge = body["hedge"]
    assert hedge["product"] == "mini_kospi200"
    assert hedge["multiplier"] == pytest.approx(50_000)
    assert hedge["futures_price"] == pytest.approx(368.5)
    assert hedge["stock_long_notional"] == pytest.approx(52_000_000)
    assert hedge["portfolio_beta"] == pytest.approx(1.08)
    assert hedge["beta_notional"] == pytest.approx(56_160_000)
    assert hedge["futures_net_contracts"] == pytest.approx(-1)
    # 서명 노출: 숏은 음수.
    assert hedge["futures_net_notional"] == pytest.approx(-18_425_000)
    assert hedge["net_beta_exposure"] == pytest.approx(37_735_000)
    assert hedge["recommended_short_contracts"] == 3
    assert isinstance(hedge["recommended_short_contracts"], int)
    assert hedge["residual_exposure_after"] == pytest.approx(-13_520_000)
    assert hedge["band"] == "HIGH"
    assert hedge["score"] == pytest.approx(74.2)
    assert hedge["advisory_active"] is True
    assert "헤지 임계" in hedge["reason"]
    assert hedge["degraded"] is False
    assert hedge["missing_components"] == ["portfolio_beta"]
    assert hedge["stale"] is False
    assert hedge["age_s"] is not None


def test_hedge_surfaces_v2_feasibility_fields(monkeypatch, redis_client):
    _publish_hedge_hash(redis_client, v2=True)
    client = _client(monkeypatch, redis_client)

    hedge = client.get("/api/portfolio/hedge").json()["hedge"]

    assert hedge["target_hedge_ratio"] == pytest.approx(0.50)
    assert hedge["current_hedge_ratio"] == pytest.approx(0.33)
    assert hedge["delta_short_contracts"] == 1
    assert hedge["max_contracts_by_margin"] == 10
    assert hedge["margin_after_hedge_pct"] == pytest.approx(0.164)
    assert hedge["estimated_slippage_ticks"] is None  # "" → None
    assert hedge["roll_adjustment"] == "none"
    assert hedge["execution_feasibility"] == "feasible"
    assert hedge["operator_action"] == "place_manual_hedge"


def test_hedge_v2_fields_none_on_pre_v2_hash(monkeypatch, redis_client):
    # A base (pre-v2) publication has no v2 keys → all v2 fields read None.
    _publish_hedge_hash(redis_client, v2=False)
    client = _client(monkeypatch, redis_client)

    hedge = client.get("/api/portfolio/hedge").json()["hedge"]

    assert hedge["execution_feasibility"] is None
    assert hedge["operator_action"] is None
    assert hedge["target_hedge_ratio"] is None
    # Base fields still parse unchanged.
    assert hedge["recommended_short_contracts"] == 3


def test_hedge_unavailable_when_advisor_not_published(monkeypatch, redis_client):
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/hedge").json()

    assert body["status"] == "unavailable"
    assert body["hedge"] is None
    assert body["advisory_only"] is True


def test_hedge_inactive_advisory_coerces_false(monkeypatch, redis_client):
    _publish_hedge_hash(
        redis_client, advisory_active="false", recommended="0", band="NEUTRAL"
    )
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/hedge").json()

    assert body["status"] == "ok"
    assert body["hedge"]["advisory_active"] is False
    assert body["hedge"]["recommended_short_contracts"] == 0


def test_hedge_degraded_flag_maps_to_status(monkeypatch, redis_client):
    _publish_hedge_hash(redis_client, degraded="true")
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/hedge").json()

    assert body["status"] == "degraded"
    assert body["hedge"]["degraded"] is True


def test_hedge_stale_when_publication_is_old(monkeypatch, redis_client):
    _publish_hedge_hash(redis_client, asof=_now_kst_naive() - timedelta(days=2))
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/hedge").json()

    assert body["status"] == "stale"
    assert body["hedge"]["stale"] is True


# ---------------------------------------------------------------------------
# GET /api/portfolio/hedge/history
# ---------------------------------------------------------------------------


def _advice_row(asof: datetime, **overrides):
    row = {"asof_ts": asof.isoformat()}
    row.update(overrides)
    return row


def test_hedge_history_returns_recent_series(monkeypatch, tmp_path, redis_client):
    now = _now_kst_naive()
    rows = [
        _advice_row(now - timedelta(days=2), recommended_short_contracts=2),
        _advice_row(
            now - timedelta(days=1),
            recommended_short_contracts=3,
            band="CRITICAL",
            advisory_active="true",
        ),
    ]
    db_path = _create_hedge_db(tmp_path, rows)
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/hedge/history", params={"days": 30}).json()

    assert body["status"] == "ok"
    assert body["days"] == 30
    assert body["count"] == 2
    contracts = [p["recommended_short_contracts"] for p in body["points"]]
    assert contracts == [2, 3]
    latest = body["points"][-1]
    assert latest["band"] == "CRITICAL"
    assert latest["product"] == "mini_kospi200"
    assert latest["net_beta_exposure"] == pytest.approx(37_735_000)
    assert latest["beta_notional"] == pytest.approx(56_160_000)
    assert latest["futures_net_notional"] == pytest.approx(-18_425_000)
    assert latest["residual_exposure_after"] == pytest.approx(-13_520_000)
    assert latest["score"] == pytest.approx(74.2)
    assert latest["advisory_active"] is True
    assert latest["trade_date"] == (now - timedelta(days=1)).date().isoformat()


def test_hedge_history_days_window_filters_old_rows(
    monkeypatch, tmp_path, redis_client
):
    now = _now_kst_naive()
    rows = [
        _advice_row(now - timedelta(days=40), recommended_short_contracts=9),
        _advice_row(now - timedelta(days=2), recommended_short_contracts=1),
    ]
    db_path = _create_hedge_db(tmp_path, rows)
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/hedge/history", params={"days": 7}).json()

    assert body["count"] == 1
    assert body["points"][0]["recommended_short_contracts"] == 1


def test_hedge_history_maps_alternate_column_names(monkeypatch, tmp_path, redis_client):
    """The v4 schema is not finalized — candidate columns must still map."""
    now = _now_kst_naive()
    rows = [
        _advice_row(
            now - timedelta(days=1),
            band="HIGH",
            score=71.0,
            recommended_short_contracts=2,
            net_beta_exposure=30_000_000.0,
            advisory_active=1,
        ),
    ]
    db_path = _create_hedge_db(tmp_path, rows, alt_schema=True)
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/hedge/history").json()

    assert body["status"] == "ok"
    point = body["points"][0]
    assert point["band"] == "HIGH"
    assert point["score"] == pytest.approx(71.0)
    assert point["recommended_short_contracts"] == 2
    assert point["net_beta_exposure"] == pytest.approx(30_000_000)
    assert point["advisory_active"] is True
    # Columns absent from the alternate schema degrade to null.
    assert point["beta_notional"] is None
    assert point["reason"] is None


def test_hedge_history_empty_when_table_missing(monkeypatch, tmp_path, redis_client):
    """DB exists but the advisor lane's table has not landed yet."""
    db_path = tmp_path / "runtime_ledger.db"
    sqlite3.connect(db_path).close()
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/hedge/history").json()

    assert body["status"] == "empty"
    assert body["points"] == []
    assert body["days"] == 30


def test_hedge_history_empty_when_db_unavailable(monkeypatch, redis_client):
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/portfolio/hedge/history").json()

    assert body["status"] == "empty"
    assert body["points"] == []


def test_hedge_history_is_read_only_on_the_ledger(monkeypatch, tmp_path, redis_client):
    """The history endpoint must never create schema in the ledger DB."""
    db_path = tmp_path / "runtime_ledger.db"
    sqlite3.connect(db_path).close()
    client = _client(monkeypatch, redis_client, db_path)

    client.get("/api/portfolio/hedge/history")

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert tables == set()


def test_hedge_endpoints_are_read_only(monkeypatch, redis_client):
    """권고 전용 원칙: no mutating verbs, no order/execution controls."""
    client = _client(monkeypatch, redis_client)

    assert client.post("/api/portfolio/hedge").status_code == 405
    assert client.put("/api/portfolio/hedge").status_code == 405
    assert client.delete("/api/portfolio/hedge").status_code == 405
    assert client.post("/api/portfolio/hedge/history").status_code == 405
