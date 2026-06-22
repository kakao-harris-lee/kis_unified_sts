"""Tests for dashboard event-context diagnostics."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeRedis:
    def __init__(
        self,
        *,
        values: dict[str, object] | None = None,
        hashes: dict[str, dict[str, object]] | None = None,
        streams: dict[str, list[tuple[str, dict[str, object]]]] | None = None,
    ) -> None:
        self.values = values or {}
        self.hashes = hashes or {}
        self.streams = streams or {}

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def hget(self, key: str, field: str) -> object | None:
        return self.hashes.get(key, {}).get(field)

    def xrevrange(self, key: str, count: int = 3):
        return list(reversed(self.streams.get(key, [])))[:count]

    def xlen(self, key: str) -> int:
        return len(self.streams.get(key, []))


def _write_events(path: Path, scheduled_at: datetime) -> None:
    path.write_text(
        "\n".join(
            [
                "events:",
                "  - event_id: bok_test",
                "    event_type: BOK_rate_decision",
                f'    scheduled_at: "{scheduled_at.astimezone(UTC).isoformat()}"',
                "    impact_tier: 1",
            ]
        ),
        encoding="utf-8",
    )


def _client(monkeypatch, tmp_path: Path, redis: _FakeRedis):
    from services.dashboard.routes import event_context

    importlib.reload(event_context)
    scheduled_path = tmp_path / "scheduled_events.yaml"
    monkeypatch.setattr(event_context, "_SCHEDULED_EVENTS_PATH", str(scheduled_path))
    monkeypatch.setattr(event_context, "_get_redis_client", lambda: redis)
    app = FastAPI()
    app.include_router(event_context.router)
    return TestClient(app), scheduled_path


def _stream_entry(ts: datetime, fields: dict[str, object] | None = None):
    ts_ms = int(ts.timestamp() * 1000)
    return f"{ts_ms}-0", {"ts_ms": str(ts_ms), **(fields or {})}


def test_event_context_reports_fresh_sources_and_setup_c_candidates(
    monkeypatch,
    tmp_path,
):
    now = datetime.now(UTC)
    event_score = json.dumps(
        {
            "asof": (now - timedelta(minutes=1)).isoformat(),
            "impact_score": 88.0,
            "event_type": "BOK_rate_decision",
            "source": "rule",
            "raw_text": None,
            "ttl_minutes": 30,
        }
    )
    redis = _FakeRedis(
        values={"forecast:event:latest": event_score},
        hashes={
            "trading:futures:setup_eval": {
                "setup_c_event_reaction": json.dumps(
                    {
                        "outcome": "reject",
                        "reason": "no_breakout_within_buffer(px=100,hi=101,lo=99,buf=1)",
                        "ts_kst": now.isoformat(),
                    }
                )
            }
        },
        streams={
            "stream:news.raw": [
                _stream_entry(now - timedelta(minutes=3), {"title": "BOK decision"})
            ],
            "stream:news.scored": [
                _stream_entry(
                    now - timedelta(minutes=2),
                    {"event_type": "BOK_rate_decision", "impact_score": "88"},
                )
            ],
            "stream:macro.overnight": [
                _stream_entry(
                    now - timedelta(minutes=5),
                    {"session": "overnight_us_close", "sp500_change_pct": "0.8"},
                )
            ],
        },
    )
    client, scheduled_path = _client(monkeypatch, tmp_path, redis)
    _write_events(scheduled_path, now - timedelta(minutes=5))

    response = client.get("/api/event-context/diagnostics?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_class"] == "futures"
    assert body["event_score"]["status"] == "fresh"
    sources = {row["name"]: row for row in body["source_timeline"]}
    assert sources["news_raw"]["status"] == "ok"
    assert sources["news_scored"]["count"] == 1
    assert body["setup_c"]["candidate_count"] == 1
    assert body["setup_c"]["root_cause"] == "setup_c_selective_breakout_or_risk"
    assert body["missing_evidence"] == []


def test_event_context_exposes_empty_event_sourcing(monkeypatch, tmp_path):
    redis = _FakeRedis()
    client, scheduled_path = _client(monkeypatch, tmp_path, redis)
    scheduled_path.write_text("events: []\n", encoding="utf-8")

    response = client.get("/api/event-context/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["event_score"]["status"] == "missing"
    assert body["setup_c"]["root_cause"] == "event_sourcing_empty"
    assert "forecast_event_latest" in body["missing_evidence"]
    assert "news_raw" in body["missing_evidence"]
    assert "news_scored" in body["missing_evidence"]
    assert body["setup_c"]["blocked_reasons"]["event_score_missing"] == 1


def test_event_context_marks_setup_c_not_applicable_for_stock(monkeypatch, tmp_path):
    redis = _FakeRedis()
    client, scheduled_path = _client(monkeypatch, tmp_path, redis)
    scheduled_path.write_text("events: []\n", encoding="utf-8")

    response = client.get("/api/event-context/diagnostics?asset_class=stock")

    assert response.status_code == 200
    body = response.json()
    assert body["asset_class"] == "stock"
    assert body["setup_c"]["enabled"] is False
    assert body["setup_c"]["root_cause"] == "not_applicable"
    assert body["setup_c"]["blocked_reasons"] == {
        "setup_c_not_applicable_to_stock": 1
    }


def test_event_context_marks_malformed_runtime_payloads(monkeypatch, tmp_path):
    redis = _FakeRedis(
        values={"forecast:event:latest": json.dumps({"impact_score": 88})},
        hashes={
            "trading:futures:setup_eval": {
                "setup_c_event_reaction": json.dumps(
                    {"outcome": "reject", "reason": "no_event_in_window"}
                )
            }
        },
    )
    client, scheduled_path = _client(monkeypatch, tmp_path, redis)
    scheduled_path.write_text("events: []\n", encoding="utf-8")

    response = client.get("/api/event-context/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["event_score"]["status"] == "invalid"
    assert body["setup_eval"]["status"] == "malformed"
    assert "forecast_event_latest_invalid" in body["missing_evidence"]
    assert "setup_c_latest_eval_malformed" in body["missing_evidence"]
