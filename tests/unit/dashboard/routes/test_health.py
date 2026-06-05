"""Health endpoints — process / data-freshness / kill-switch / summary."""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from services.dashboard.app import create_app


@pytest.fixture
def client():
    app = create_app(require_auth=False)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_summary_cache():
    """Reset the health summary cache between tests to avoid bleed-over."""
    from services.dashboard.routes import health

    health._summary_cache["data"] = None
    health._summary_cache["expires_at"] = 0.0
    health._summary_cache["asset"] = None
    yield
    health._summary_cache["data"] = None
    health._summary_cache["expires_at"] = 0.0
    health._summary_cache["asset"] = None


class TestProcessHealth:
    def test_returns_per_process_status(self, client):
        res = client.get("/api/health/process")
        assert res.status_code == 200
        body = res.json()
        assert "processes" in body
        for p in body["processes"]:
            assert {
                "asset_class",
                "pid",
                "uptime_s",
                "last_activity_s",
                "alive",
            } <= set(p.keys())

    def test_alive_when_pid_running(self, client):
        res = client.get("/api/health/process")
        assert res.status_code == 200

    def test_dead_process_has_zero_pid(self, client):
        with patch(
            "services.dashboard.routes.health._read_pid_file", return_value=None
        ):
            res = client.get("/api/health/process")
            assert res.status_code == 200
            for p in res.json()["processes"]:
                assert p["alive"] is False
                assert p["pid"] == 0


class TestDataFreshness:
    def test_returns_per_source_freshness(self, client):
        res = client.get("/api/health/data-freshness")
        assert res.status_code == 200
        body = res.json()
        assert "sources" in body
        for src in body["sources"]:
            assert {
                "source",
                "asset_class",
                "symbol_count",
                "fresh_count",
                "fresh_ratio",
                "last_tick_s",
            } <= set(src.keys())

    def test_fresh_ratio_is_float_between_zero_and_one(self, client):
        res = client.get("/api/health/data-freshness")
        for src in res.json()["sources"]:
            assert 0.0 <= src["fresh_ratio"] <= 1.0

    def test_filters_by_asset_class(self, client):
        res = client.get("/api/health/data-freshness", params={"asset_class": "stock"})
        assert res.status_code == 200
        for src in res.json()["sources"]:
            assert src["asset_class"] in {"stock", "all"}


class TestKillSwitch:
    def test_returns_disabled_when_no_keys(self, client):
        res = client.get("/api/health/kill-switch")
        assert res.status_code == 200
        body = res.json()
        assert "enabled" in body
        assert "active_conditions" in body
        assert isinstance(body["active_conditions"], list)

    def test_conditions_namespace(self, client):
        res = client.get("/api/health/kill-switch")
        EXPECTED = {
            "daily_mdd_exceeded",
            "weekly_mdd_exceeded",
            "consecutive_losses",
            "kis_error_rate_high",
            "news_pipeline_lag",
        }
        for cond in res.json()["active_conditions"]:
            assert cond["name"] in EXPECTED


class TestHealthSummary:
    def test_returns_combined_payload(self, client):
        res = client.get("/api/health/summary")
        assert res.status_code == 200
        body = res.json()
        assert {"processes", "data_sources", "kill_switch", "today_pnl"} <= set(
            body.keys()
        )

    def test_supports_asset_class_filter(self, client):
        res = client.get("/api/health/summary", params={"asset_class": "futures"})
        assert res.status_code == 200

    def test_today_pnl_reads_runtime_ledger(self, client, monkeypatch, tmp_path):
        from services.dashboard.routes import health
        from shared.storage.runtime_ledger import SQLiteRuntimeLedger

        db_path = tmp_path / "runtime.db"
        monkeypatch.setenv("RUNTIME_STORAGE_BACKEND", "sqlite")
        monkeypatch.setenv("RUNTIME_STORAGE_SQLITE_PATH", str(db_path))
        monkeypatch.setattr(health, "_futures_multiplier_krw_per_point", lambda: 50_000)

        kst = ZoneInfo("Asia/Seoul")
        today = datetime.now(kst).replace(hour=10, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        ledger = SQLiteRuntimeLedger(db_path)
        ledger.record_trade(
            {
                "id": "stock-today",
                "asset_class": "stock",
                "code": "005930",
                "side": "long",
                "entry_time": today.isoformat(),
                "entry_price": 1000.0,
                "exit_time": today.isoformat(),
                "exit_price": 1100.0,
                "quantity": 10,
            }
        )
        ledger.record_trade(
            {
                "id": "futures-today",
                "asset_class": "futures",
                "code": "101S6000",
                "side": "long",
                "entry_time": today.isoformat(),
                "entry_price": 350.0,
                "exit_time": today.isoformat(),
                "exit_price": 351.0,
                "quantity": 1,
            }
        )
        ledger.record_trade(
            {
                "id": "stock-yesterday",
                "asset_class": "stock",
                "code": "000000",
                "side": "long",
                "entry_time": yesterday.isoformat(),
                "entry_price": 1000.0,
                "exit_time": yesterday.isoformat(),
                "exit_price": 2000.0,
                "quantity": 1,
            }
        )
        ledger.close()

        res = client.get("/api/health/summary", params={"asset_class": "all"})
        assert res.status_code == 200
        assert res.json()["today_pnl"] == 51_000

    # serial: the two requests must land within the real 1s cache window;
    # parallel CPU starvation can space them further apart and break the cache.
    @pytest.mark.serial
    def test_caches_response_1s(self, client):
        a = client.get("/api/health/summary").json()
        b = client.get("/api/health/summary").json()
        assert a["checked_at"] == b["checked_at"]


class TestForecastingHealth:
    def test_returns_service_status(self, client):
        res = client.get("/api/health/forecasting")
        assert res.status_code == 200
        body = res.json()
        assert {
            "service_alive",
            "forecast_fresh",
            "forecast_age_s",
            "model_loaded",
            "model_last_refit",
            "model_r2_oos",
        } <= set(body.keys())
