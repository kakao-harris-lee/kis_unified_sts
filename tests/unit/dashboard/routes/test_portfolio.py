"""Tests for the read-only unified portfolio equity dashboard API (Phase 3D)."""

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

EQUITY_KEY = "portfolio:equity:latest"


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _publish_equity_hash(
    redis,
    *,
    degraded: str = "false",
    asof: datetime | None = None,
    track_a: str = "",
    stage: str = "NORMAL",
    mode: str = "shadow",
):
    asof = asof or _now_kst_naive()
    redis.hset(
        EQUITY_KEY,
        mapping={
            "total_equity": "125000000",
            "track_b_equity": "21875000",
            "track_c_equity": "9375000",
            "track_a_equity": track_a,
            "month_start_equity": "130000000",
            "month_peak_equity": "131500000",
            "monthly_mdd_pct": "-4.94",
            "stage": stage,
            "mode": mode,
            "degraded": degraded,
            "missing_components": json.dumps(["track_a_ledger"]),
            "asof_ts": asof.isoformat(),
        },
    )


def _create_history_db(tmp_path, rows: list[dict] | None = None):
    """Simulate the batch lane's ``portfolio_equity_daily`` table."""
    db_path = tmp_path / "runtime_ledger.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE portfolio_equity_daily (
            trade_date TEXT PRIMARY KEY,
            track_a_equity REAL,
            track_b_equity REAL,
            track_c_equity REAL,
            total_equity REAL,
            month_start_equity REAL,
            month_peak_equity REAL,
            monthly_mdd_pct REAL,
            stage TEXT,
            mode TEXT
        )
        """)
    for row in rows or []:
        conn.execute(
            """
            INSERT OR REPLACE INTO portfolio_equity_daily (
                trade_date, track_a_equity, track_b_equity, track_c_equity,
                total_equity, month_start_equity, month_peak_equity,
                monthly_mdd_pct, stage, mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["trade_date"],
                row.get("track_a_equity"),
                row.get("track_b_equity"),
                row.get("track_c_equity"),
                row.get("total_equity"),
                row.get("month_start_equity"),
                row.get("month_peak_equity"),
                row.get("monthly_mdd_pct"),
                row.get("stage"),
                row.get("mode"),
            ),
        )
    conn.commit()
    conn.close()
    return db_path


def _daily_row(day, **overrides):
    row = {
        "trade_date": day.isoformat(),
        "track_a_equity": None,
        "track_b_equity": 21_875_000.0,
        "track_c_equity": 9_375_000.0,
        "total_equity": 125_000_000.0,
        "month_start_equity": 130_000_000.0,
        "month_peak_equity": 131_500_000.0,
        "monthly_mdd_pct": -4.94,
        "stage": "NORMAL",
        "mode": "shadow",
    }
    row.update(overrides)
    return row


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


def _assert_default_stages(stages: dict) -> None:
    """Assertions valid for both the shipped YAML and the code defaults."""
    assert stages["mode"] in {"off", "shadow", "enforce"}
    assert stages["reduce"]["threshold"] == pytest.approx(-0.05)
    assert stages["reduce"]["new_entry_size_factor"] == pytest.approx(0.5)
    assert stages["halt_new"]["threshold"] == pytest.approx(-0.08)
    assert stages["full_stop"]["threshold"] == pytest.approx(-0.12)


# ---------------------------------------------------------------------------
# GET /api/portfolio/equity
# ---------------------------------------------------------------------------


def test_latest_ok_parses_contract_hash(monkeypatch, redis_client):
    _publish_equity_hash(redis_client)
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["status"] == "ok"
    assert body["source"] == EQUITY_KEY
    equity = body["equity"]
    assert equity["total_equity"] == pytest.approx(125_000_000)
    assert equity["track_b_equity"] == pytest.approx(21_875_000)
    assert equity["track_c_equity"] == pytest.approx(9_375_000)
    # Contract: track_a_equity publishes "" while unrecorded → null.
    assert equity["track_a_equity"] is None
    assert equity["month_start_equity"] == pytest.approx(130_000_000)
    assert equity["month_peak_equity"] == pytest.approx(131_500_000)
    assert equity["monthly_mdd_pct"] == pytest.approx(-4.94)
    assert equity["stage"] == "NORMAL"
    assert equity["mode"] == "shadow"
    assert equity["degraded"] is False
    assert equity["missing_components"] == ["track_a_ledger"]
    assert equity["stale"] is False
    assert equity["age_s"] is not None
    _assert_default_stages(body["stages"])


def test_latest_unavailable_when_batch_not_published(monkeypatch, redis_client):
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["status"] == "unavailable"
    assert body["equity"] is None
    # Stage thresholds are config-sourced and do not depend on the batch.
    _assert_default_stages(body["stages"])


def test_latest_degraded_flag_maps_to_status(monkeypatch, redis_client):
    _publish_equity_hash(redis_client, degraded="true", stage="REDUCE")
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["status"] == "degraded"
    assert body["equity"]["degraded"] is True
    assert body["equity"]["stage"] == "REDUCE"


def test_latest_stale_when_publication_is_old(monkeypatch, redis_client):
    _publish_equity_hash(redis_client, asof=_now_kst_naive() - timedelta(days=5))
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["status"] == "stale"
    assert body["equity"]["stale"] is True


def test_latest_track_a_value_passes_through(monkeypatch, redis_client):
    _publish_equity_hash(redis_client, track_a="93750000")
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["equity"]["track_a_equity"] == pytest.approx(93_750_000)


def test_stages_fall_back_to_defaults_when_yaml_is_malformed(monkeypatch, redis_client):
    """A broken YAML degrades to the code-default mirror, never a 500."""
    from shared.portfolio.config import PortfolioConfig

    def _broken_yaml(cls, *args, **kwargs):
        raise ValueError("malformed portfolio.yaml")

    monkeypatch.setattr(PortfolioConfig, "from_yaml", classmethod(_broken_yaml))
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    _assert_default_stages(body["stages"])
    assert body["stages"]["mode"] == "shadow"


def test_stages_null_when_portfolio_module_unavailable(monkeypatch, redis_client):
    """Total config failure yields stages=null so the UI uses static labels."""
    from services.dashboard.routes import portfolio

    monkeypatch.setattr(portfolio, "_load_portfolio_config", lambda: None)
    client = _client(monkeypatch, redis_client)

    body = client.get("/api/portfolio/equity").json()

    assert body["stages"] is None


# ---------------------------------------------------------------------------
# GET /api/portfolio/equity/history
# ---------------------------------------------------------------------------


def test_history_returns_daily_series(monkeypatch, tmp_path, redis_client):
    today = datetime.now(KST).date()
    rows = [
        _daily_row(today - timedelta(days=3), total_equity=131_000_000.0),
        _daily_row(
            today - timedelta(days=2),
            total_equity=127_000_000.0,
            monthly_mdd_pct=-3.42,
            stage="NORMAL",
        ),
        _daily_row(
            today - timedelta(days=1),
            total_equity=123_500_000.0,
            monthly_mdd_pct=-6.08,
            stage="REDUCE",
        ),
    ]
    db_path = _create_history_db(tmp_path, rows)
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/equity/history", params={"days": 90}).json()

    assert body["status"] == "ok"
    assert body["count"] == 3
    totals = [point["total_equity"] for point in body["points"]]
    assert totals == [131_000_000.0, 127_000_000.0, 123_500_000.0]
    latest = body["points"][-1]
    assert latest["trade_date"] == (today - timedelta(days=1)).isoformat()
    assert latest["track_b_equity"] == pytest.approx(21_875_000)
    assert latest["track_a_equity"] is None
    assert latest["monthly_mdd_pct"] == pytest.approx(-6.08)
    assert latest["stage"] == "REDUCE"
    assert latest["mode"] == "shadow"


def test_history_days_window_filters_old_rows(monkeypatch, tmp_path, redis_client):
    today = datetime.now(KST).date()
    rows = [
        _daily_row(today - timedelta(days=40), total_equity=100.0),
        _daily_row(today - timedelta(days=2), total_equity=200.0),
    ]
    db_path = _create_history_db(tmp_path, rows)
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/equity/history", params={"days": 7}).json()

    assert body["count"] == 1
    assert body["points"][0]["total_equity"] == pytest.approx(200.0)


def test_history_empty_when_table_missing(monkeypatch, tmp_path, redis_client):
    """DB exists but the batch lane's table has not landed yet."""
    db_path = tmp_path / "runtime_ledger.db"
    sqlite3.connect(db_path).close()
    client = _client(monkeypatch, redis_client, db_path)

    body = client.get("/api/portfolio/equity/history").json()

    assert body["status"] == "empty"
    assert body["points"] == []
    assert body["days"] == 90


def test_history_empty_when_db_unavailable(monkeypatch, redis_client):
    client = _client(monkeypatch, redis_client, None)

    body = client.get("/api/portfolio/equity/history").json()

    assert body["status"] == "empty"
    assert body["points"] == []


def test_history_is_read_only_on_the_ledger(monkeypatch, tmp_path, redis_client):
    """The history endpoint must never create schema in the ledger DB."""
    db_path = tmp_path / "runtime_ledger.db"
    sqlite3.connect(db_path).close()
    client = _client(monkeypatch, redis_client, db_path)

    client.get("/api/portfolio/equity/history")

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    assert tables == set()


def test_endpoints_are_read_only(monkeypatch, redis_client):
    """No mutating verbs are exposed on the portfolio surface."""
    client = _client(monkeypatch, redis_client)

    assert client.post("/api/portfolio/equity").status_code == 405
    assert client.put("/api/portfolio/equity").status_code == 405
    assert client.delete("/api/portfolio/equity").status_code == 405
    assert client.post("/api/portfolio/equity/history").status_code == 405
