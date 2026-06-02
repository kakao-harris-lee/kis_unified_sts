from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_stock_builder_preset_experiment_report_endpoint(tmp_path, monkeypatch):
    report_dir = tmp_path / "reports"
    log_dir = tmp_path / "logs"
    report_dir.mkdir()
    log_dir.mkdir()
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "experiment": {
                    "id": "unit_experiment",
                    "description": "unit",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-05",
                    "output_dir": str(report_dir),
                    "fallback_symbols": ["000660"],
                    "basket_source": {"type": "disabled"},
                    "presets": [{"id": "trend_filter"}],
                }
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "experiment": {
            "id": "unit_experiment",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "generated_at": datetime(2026, 6, 1, 7, 35, tzinfo=UTC).isoformat(),
            "symbols": ["000660"],
            "presets": ["trend_filter"],
        },
        "summaries": [{"strategy_id": "trend_filter", "total_return_pct": 1.2}],
        "trades": [],
        "equity_curves": {"trend_filter": [{"date": "2026-06-01", "equity": 101}]},
    }
    (report_dir / "unit.json").write_text(json.dumps(payload), encoding="utf-8")
    (log_dir / "stock_builder_preset_experiment_20260601.log").write_text(
        "ok\njson=unit.json\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("STOCK_BUILDER_PRESET_EXPERIMENT_CONFIG", str(config_path))
    monkeypatch.setenv("KIS_LOG_DIR", str(log_dir))

    from services.dashboard.routes import kis_builder

    importlib.reload(kis_builder)
    app = FastAPI()
    app.include_router(kis_builder.router)
    client = TestClient(app)

    response = client.get("/api/kis-builder/experiments/stock-builder-preset")

    assert response.status_code == 200
    body = response.json()
    assert body["experiment"]["id"] == "unit_experiment"
    assert body["progress"]["completed_report_days"] == 1
    assert body["reports"][0]["filename"] == "unit.json"
    assert body["latest_report"]["summaries"][0]["strategy_id"] == "trend_filter"
    assert body["latest_log"]["lines"][-1] == "json=unit.json"


def test_dashboard_compose_mounts_experiment_reports():
    compose = yaml.safe_load(
        (_REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    dashboard_volumes = compose["services"]["dashboard"]["volumes"]

    assert "./reports:/app/reports:ro" in dashboard_volumes
