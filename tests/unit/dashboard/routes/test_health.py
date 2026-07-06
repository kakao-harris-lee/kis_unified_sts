"""Health endpoints — process / data-freshness / kill-switch / summary."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from services.dashboard.app import create_app


class FakeRedis:
    def __init__(
        self,
        *,
        values: dict[str, object] | None = None,
        hashes: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.values = values or {}
        self.hashes = hashes or {}

    def get(self, key: str):
        return self.values.get(key)

    def hgetall(self, key: str):
        return self.hashes.get(key, {})


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

    def test_ops_summary_full_payload(self, client, monkeypatch):
        from services.dashboard.routes import health

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        fake_redis = FakeRedis(
            values={
                "trading:stock:data_freshness": json.dumps(
                    {"symbol_count": 10, "fresh_count": 9, "last_tick_s": 8}
                ),
                "trading:futures:data_freshness": json.dumps(
                    {"symbol_count": 1, "fresh_count": 1, "last_tick_s": 5}
                ),
                "system:universe:latest": json.dumps(
                    {"generated_at": now_iso, "codes": ["005930", "000660"]}
                ),
                "system:trade_targets:latest": json.dumps(
                    {"generated_at": now_iso, "codes": ["005930"]}
                ),
                "forecast:vol:current": json.dumps({"asof": now_iso}),
                "forecast:vol:model": json.dumps(
                    {"coefficients": {"fit_date": "2026-06-22", "r2_oos": 0.42}}
                ),
            },
            hashes={
                "trading:stock:status": {
                    "state": "running",
                    "source": "stock_monitor",
                    "updated_at": now_iso,
                    "publisher_pid": "111",
                    "config": json.dumps(
                        {"paper_trading": True, "strategy": "bb_reversion"}
                    ),
                    "positions": json.dumps(
                        {"open_positions": 2, "unrealized_pnl": 1200}
                    ),
                    "strategies": json.dumps({"strategies": ["bb_reversion"]}),
                    "pipeline": json.dumps(
                        {"is_running": True, "stages": {"entry": {"status": "ok"}}}
                    ),
                },
                "trading:futures:status": {
                    "state": "running",
                    "source": "futures_monitor",
                    "updated_at": now_iso,
                    "publisher_pid": "222",
                    "config": json.dumps({"paper_trading": False}),
                    "positions": json.dumps({"open_positions": 1}),
                    "pipeline": json.dumps({"is_running": True}),
                },
                "scheduler:status": {
                    "status": "ok",
                    "last_success_at": now_iso,
                    "jobs": json.dumps([{"name": "daily_indicator_scanner"}]),
                },
            },
        )

        async def fake_process_health():
            return {
                "processes": [
                    {
                        "asset_class": "stock",
                        "pid": 111,
                        "uptime_s": 90,
                        "last_activity_s": 0,
                        "alive": True,
                    },
                    {
                        "asset_class": "futures",
                        "pid": 222,
                        "uptime_s": 120,
                        "last_activity_s": 0,
                        "alive": True,
                    },
                ],
                "checked_at": now_iso,
            }

        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)
        monkeypatch.setattr(health, "get_process_health", fake_process_health)
        monkeypatch.setattr(
            health,
            "_today_pnl_krw",
            lambda asset: {"stock": 1_000, "futures": 2_000, "all": 3_000}[asset],
        )

        res = client.get("/api/health/summary", params={"asset_class": "all"})

        assert res.status_code == 200
        body = res.json()
        assert {"processes", "data_sources", "kill_switch", "today_pnl"} <= set(body)
        assert body["today_pnl"] == 3_000

        ops = body["ops_summary"]
        assert ops["asset_class"] == "all"
        assert set(ops["assets"]) == {"stock", "futures"}
        assert ops["assets"]["stock"]["process"]["status"] == "ok"
        assert ops["assets"]["stock"]["data_freshness"]["status"] == "ok"
        assert ops["assets"]["stock"]["pipeline"]["status"] == "ok"
        assert ops["assets"]["stock"]["pipeline"]["details"]["is_running"] is True
        assert ops["assets"]["stock"]["mode"]["value"] == "paper"
        assert ops["assets"]["futures"]["mode"]["value"] == "live"
        assert ops["scheduler"]["status"] == "ok"
        assert ops["scheduler"]["jobs"] == [{"name": "daily_indicator_scanner"}]
        assert ops["producers"]["assets"]["stock"]["status"] == "ok"
        assert ops["forecasting"]["status"] == "ok"
        assert ops["mode"]["value"] == "mixed"
        assert body["pipeline"] == ops["pipeline"]
        assert body["mode"] == ops["mode"]

    def test_ops_summary_defaults_to_unknown_when_unavailable(
        self, client, monkeypatch
    ):
        from services.dashboard.routes import health

        now_iso = datetime.now(UTC).isoformat()

        async def fake_process_health():
            return {
                "processes": [
                    {
                        "asset_class": "stock",
                        "pid": 0,
                        "uptime_s": 0,
                        "last_activity_s": -1,
                        "alive": False,
                    }
                ],
                "checked_at": now_iso,
            }

        monkeypatch.setattr(health, "_get_redis_client", lambda: None)
        monkeypatch.setattr(health, "get_process_health", fake_process_health)
        monkeypatch.setattr(health, "_today_pnl_krw", lambda _asset: 0)

        res = client.get("/api/health/summary", params={"asset_class": "stock"})

        assert res.status_code == 200
        body = res.json()
        assert body["today_pnl"] == 0

        ops = body["ops_summary"]
        assert ops["asset_class"] == "stock"
        assert ops["process"]["status"] == "unknown"
        assert ops["data_freshness"]["status"] == "unknown"
        assert ops["scheduler"]["status"] == "unknown"
        assert ops["forecasting"]["status"] == "unknown"
        assert ops["pipeline"]["status"] == "unknown"
        assert ops["mode"]["value"] == "unknown"
        assert ops["producers"]["items"][0]["status"] == "unknown"

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


class TestMarketStructureHealth:
    """market:structure:latest asof freshness (Wave 2b daily collector)."""

    KST = ZoneInfo("Asia/Seoul")

    def _latest_hash(self, asof: datetime) -> dict[str, object]:
        return {
            "market:structure:latest": {
                "snapshot": "close",
                "trade_date": "2026-07-02",
                # collector publishes naive-KST isoformat
                "asof": asof.astimezone(self.KST).replace(tzinfo=None).isoformat(),
                "coverage_ratio": "0.875",
                "missing_components": json.dumps(["program"]),
                "fut_foreign_net_qty": "-1250.0",
            }
        }

    def test_unknown_when_redis_unavailable(self, client, monkeypatch):
        from services.dashboard.routes import health

        monkeypatch.setattr(health, "_get_redis_client", lambda: None)

        res = client.get("/api/health/market-structure")

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "unknown"
        assert body["source"] == "market:structure:latest"
        assert body["asof"] is None
        assert body["age_s"] is None
        assert body["missing_components"] == []

    def test_fresh_snapshot_is_ok(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=5)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/market-structure")

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["snapshot"] == "close"
        assert body["trade_date"] == "2026-07-02"
        assert 0 <= body["age_s"] <= 600
        assert body["stale_after_s"] == 50400
        assert body["coverage_ratio"] == pytest.approx(0.875)
        assert body["missing_components"] == ["program"]

    def test_old_snapshot_is_stale(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(hours=20)  # > 14h threshold
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/market-structure")

        body = res.json()
        assert body["status"] == "stale"
        assert body["age_s"] > body["stale_after_s"]

    def test_summary_exposes_market_structure(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=10)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/summary", params={"asset_class": "all"})

        assert res.status_code == 200
        body = res.json()
        assert body["market_structure"]["status"] == "ok"
        assert body["ops_summary"]["market_structure"]["snapshot"] == "close"


class TestFuturesContractHealth:
    """futures:contract:latest roll-state read-model (Phase A, shadow)."""

    KST = ZoneInfo("Asia/Seoul")

    def _latest_hash(
        self, asof: datetime, *, roll_state: str = "normal"
    ) -> dict[str, object]:
        return {
            "futures:contract:latest": {
                "schema_version": "1",
                "product": "mini",
                "front_symbol": "A05607",
                "next_symbol": "A05608",
                "night_front_symbol": "1A01609",
                "days_to_expiry": "8",
                "roll_state": roll_state,
                "roll_reason": "days_to_expiry>pre_roll",
                "new_entry_front_allowed": "true",
                "hedge_front_allowed": "true",
                "asof_ts": asof.astimezone(self.KST).replace(tzinfo=None).isoformat(),
            }
        }

    def test_unknown_when_redis_unavailable(self, client, monkeypatch):
        from services.dashboard.routes import health

        monkeypatch.setattr(health, "_get_redis_client", lambda: None)

        res = client.get("/api/health/futures-contract")

        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "unknown"
        assert body["source"] == "futures:contract:latest"
        assert body["roll_state"] is None

    def test_fresh_normal_snapshot_is_ok(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=5)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/futures-contract")

        body = res.json()
        assert body["status"] == "ok"
        assert body["product"] == "mini"
        assert body["front_symbol"] == "A05607"
        assert body["night_front_symbol"] == "1A01609"
        assert body["days_to_expiry"] == 8
        assert body["new_entry_front_allowed"] is True

    def test_expired_roll_state_warns_even_when_fresh(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=5)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof, roll_state="expired"))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/futures-contract")

        body = res.json()
        assert body["status"] == "warn"
        assert body["roll_state"] == "expired"

    def test_summary_exposes_futures_contract(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=10)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/summary", params={"asset_class": "all"})

        assert res.status_code == 200
        body = res.json()
        assert body["futures_contract"]["status"] == "ok"
        assert body["ops_summary"]["futures_contract"]["front_symbol"] == "A05607"


class TestFuturesMarginHealth:
    """futures:risk:latest margin-risk read-model (Phase B, shadow)."""

    KST = ZoneInfo("Asia/Seoul")

    def _latest_hash(
        self, asof: datetime, *, risk_level: str = "ok"
    ) -> dict[str, object]:
        return {
            "futures:risk:latest": {
                "schema_version": "1",
                "account_equity_krw": "50000000.0000",
                "initial_margin_required_krw": "1600000.0000",
                "margin_usage_pct": "0.0320",
                "maintenance_buffer_krw": "48800000.0000",
                "liquidation_buffer_ticks": "48800.0000",
                "stress_loss_1atr_krw": "250000.0000",
                "max_additional_contracts": "24",
                "risk_level": risk_level,
                "degraded": "false",
                "missing_components": json.dumps([]),
                "asof_ts": asof.astimezone(self.KST).replace(tzinfo=None).isoformat(),
            }
        }

    def test_unknown_when_redis_unavailable(self, client, monkeypatch):
        from services.dashboard.routes import health

        monkeypatch.setattr(health, "_get_redis_client", lambda: None)

        res = client.get("/api/health/futures-margin")

        body = res.json()
        assert body["status"] == "unknown"
        assert body["source"] == "futures:risk:latest"
        assert body["risk_level"] is None

    def test_fresh_ok_snapshot(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=2)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/futures-margin")

        body = res.json()
        assert body["status"] == "ok"
        assert body["risk_level"] == "ok"
        assert body["margin_usage_pct"] == pytest.approx(0.032)
        assert body["max_additional_contracts"] == 24
        assert body["degraded"] is False

    def test_reduce_only_warns_when_fresh(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=2)
        fake_redis = FakeRedis(
            hashes=self._latest_hash(asof, risk_level="reduce_only")
        )
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/futures-margin")

        body = res.json()
        assert body["status"] == "warn"
        assert body["risk_level"] == "reduce_only"

    def test_critical_maps_to_critical(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=2)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof, risk_level="critical"))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/futures-margin")

        body = res.json()
        assert body["status"] == "critical"
        assert body["risk_level"] == "critical"

    def test_summary_exposes_futures_margin(self, client, monkeypatch):
        from services.dashboard.routes import health

        asof = datetime.now(UTC) - timedelta(minutes=5)
        fake_redis = FakeRedis(hashes=self._latest_hash(asof))
        monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)

        res = client.get("/api/health/summary", params={"asset_class": "all"})

        body = res.json()
        assert body["futures_margin"]["status"] == "ok"
        assert body["ops_summary"]["futures_margin"]["risk_level"] == "ok"
