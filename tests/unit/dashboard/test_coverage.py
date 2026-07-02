"""Tests for dashboard universe/data coverage endpoint."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeRedis:
    def __init__(self, payloads: dict[str, object]) -> None:
        self.payloads = payloads

    def get(self, key: str) -> str | None:
        payload = self.payloads.get(key)
        return json.dumps(payload) if payload is not None else None


def _client(monkeypatch, tmp_path: Path, payloads: dict[str, object]):
    monkeypatch.setenv("STOCK_EXPERIMENT_OUTPUT_DIR", str(tmp_path / "reports"))
    from services.dashboard.routes import coverage

    importlib.reload(coverage)
    monkeypatch.setattr(coverage, "_get_redis_client", lambda: _FakeRedis(payloads))
    app = FastAPI()
    app.include_router(coverage.router)
    return TestClient(app), coverage


def test_coverage_reports_daily_indicator_gaps(monkeypatch, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "stock_experiment_20260601_000000.json").write_text(
        json.dumps(
            {
                "data_coverage": {
                    "005930": {"loaded": True, "rows": 100},
                    "123456": {"loaded": False, "error": "no_minute_data"},
                }
            }
        ),
        encoding="utf-8",
    )
    client, _ = _client(
        monkeypatch,
        tmp_path,
        {
            "system:universe:latest": {
                "codes": ["005930", "123456"],
                "names": {"005930": "삼성전자", "123456": "테스트종목"},
                "generated_at": "2026-06-22T00:00:00+00:00",
            },
            "system:trade_targets:latest": {
                "codes": ["123456"],
                "names": {"123456": "테스트종목"},
            },
            "system:theme_targets:latest": {
                "codes": ["005930", "222222"],
                "metadata": {
                    "005930": {
                        "theme_id": "ai_hbm",
                        "state": "active",
                        "name": "삼성전자",
                    },
                    "222222": {
                        "theme_id": "physical_ai",
                        "state": "watch",
                        "name": "테마종목",
                    },
                },
                "themes": {"ai_hbm": {"label": "AI/HBM"}},
                "state_counts": {"active": 1, "watch": 1},
                "generated_at": "2026-06-22T00:01:00+00:00",
            },
            "system:daily_indicators:latest": {"indicators": {"005930": {}}},
        },
    )

    response = client.get("/api/coverage?asset_class=stock")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_class"] == "stock"
    sources = {row["name"]: row for row in body["sources"]}
    assert sources["screener_universe"]["count"] == 2
    assert sources["screener_universe"]["names"]["005930"] == "삼성전자"
    assert sources["screener_universe"]["missing_symbols"] == ["123456"]
    assert sources["trade_targets"]["names"]["123456"] == "테스트종목"
    assert sources["trade_targets"]["missing_symbols"] == ["123456"]
    assert sources["theme_targets"]["count"] == 2
    assert sources["theme_targets"]["names"]["222222"] == "테마종목"
    assert sources["theme_targets"]["missing_symbols"] == ["222222"]
    assert sources["theme_targets"]["metadata"]["themes"] == {
        "ai_hbm": {"label": "AI/HBM"}
    }
    assert sources["theme_targets"]["metadata"]["state_counts"] == {
        "active": 1,
        "watch": 1,
    }
    assert sources["daily_indicators"]["count"] == 1
    assert body["experiment_coverage"][0]["symbol"] == "005930"
    assert body["experiment_coverage"][0]["name"] == "삼성전자"
    assert body["experiment_coverage"][1]["error"] == "no_minute_data"
    assert body["experiment_coverage"][1]["name"] == "테스트종목"
    assert body["missing_evidence"] == []


def test_coverage_is_explicit_when_sources_missing(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path, {})

    response = client.get("/api/coverage?asset_class=all")

    assert response.status_code == 200
    body = response.json()
    assert "screener_universe" in body["missing_evidence"]
    assert "theme_targets" in body["missing_evidence"]
    assert "daily_indicators" in body["missing_evidence"]
    assert "futures_data_coverage" in body["missing_evidence"]
    assert "latest_experiment_coverage" in body["missing_evidence"]
