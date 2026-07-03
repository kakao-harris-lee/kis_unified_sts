"""Tests for the read-only feedback report API (Phase 6B).

Covers listing, single-report, latest (Redis + file-scan fallback), empty /
degraded states, method-not-allowed, and path-traversal rejection. The engine
(Phase 6A) is never exercised — the route only reads files + a Redis pointer.
"""

from __future__ import annotations

import json

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

LATEST_KEY = "portfolio:feedback:latest"


@pytest.fixture()
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture()
def reports_root(tmp_path):
    root = tmp_path / "feedback"
    for kind in ("weekly", "monthly", "quarterly"):
        (root / kind).mkdir(parents=True)
    return root


def _write_report(root, kind: str, period_label: str, body: dict, *, md: bool = True):
    (root / kind / f"{period_label}.json").write_text(
        json.dumps(body), encoding="utf-8"
    )
    if md:
        (root / kind / f"{period_label}.md").write_text(
            f"# {period_label}\n", encoding="utf-8"
        )


def _weekly_body(period_label: str, **over) -> dict:
    body = {
        "kind": "weekly",
        "period_label": period_label,
        "generated_at": "2026-07-03T18:10:00+09:00",
        "tracks": {
            "B": {
                "trades": 12,
                "win_rate": 0.58,
                "avg_win_loss": 1.4,
                "expectancy": 0.21,
                "realized_pnl": 350000,
                "slippage": None,
            },
            "C": {
                "trade_count": 5,
                "win_rate_pct": 40.0,
                "payoff": 2.1,
                "ev": -0.05,
                "pnl": -80000,
                "slippage_bps": 3.2,
            },
            "A": {},
        },
        "missing": ["track_a_ledger"],
        "headline": "주간: 트랙 B 우세, 트랙 C 관망",
    }
    body.update(over)
    return body


def _client(monkeypatch, redis_client, reports_root):
    from services.dashboard.routes import feedback

    monkeypatch.setattr(feedback, "_get_redis_client", lambda: redis_client)
    monkeypatch.setattr(feedback, "_reports_root", lambda: reports_root)
    app = FastAPI()
    app.include_router(feedback.router)
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #


def test_list_returns_newest_first_with_track_summary(
    monkeypatch, redis_client, reports_root
):
    _write_report(reports_root, "weekly", "2026-06-22", _weekly_body("2026-06-22"))
    _write_report(reports_root, "weekly", "2026-06-29", _weekly_body("2026-06-29"))
    _write_report(reports_root, "weekly", "2026-07-06", _weekly_body("2026-07-06"))
    client = _client(monkeypatch, redis_client, reports_root)

    resp = client.get("/api/reports/feedback", params={"kind": "weekly", "limit": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "weekly"
    assert body["count"] == 2
    labels = [r["period_label"] for r in body["reports"]]
    assert labels == ["2026-07-06", "2026-06-29"]  # newest first, limit honored

    top = body["reports"][0]
    assert top["tracks"]["B"]["trades"] == 12
    assert top["tracks"]["B"]["win_rate"] == pytest.approx(0.58)
    # C uses candidate keys (trade_count / win_rate_pct / pnl)
    assert top["tracks"]["C"]["trades"] == 5
    assert top["tracks"]["C"]["realized_pnl"] == pytest.approx(-80000)
    assert top["missing"] == ["track_a_ledger"]
    assert top["md_exists"] is True


def test_list_empty_when_directory_missing(monkeypatch, redis_client, reports_root):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback", params={"kind": "monthly"})
    assert resp.status_code == 200
    assert resp.json() == {"kind": "monthly", "count": 0, "reports": []}


def test_list_rejects_unknown_kind(monkeypatch, redis_client, reports_root):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback", params={"kind": "daily"})
    assert resp.status_code == 400


def test_list_quarterly_exposes_verdicts(monkeypatch, redis_client, reports_root):
    body = {
        "kind": "quarterly",
        "period_label": "2026-Q2",
        "generated_at": "2026-07-01T09:00:00+09:00",
        "tracks": {
            "B": {"trades": 40, "verdict": "met"},
            "C": {"trades": 12, "status": "below_expectation"},
            "A": {"judgment": "deferred (3-year)"},
        },
        "missing": [],
    }
    _write_report(reports_root, "quarterly", "2026-Q2", body)
    client = _client(monkeypatch, redis_client, reports_root)

    resp = client.get("/api/reports/feedback", params={"kind": "quarterly"})
    assert resp.status_code == 200
    verdicts = resp.json()["reports"][0]["verdicts"]
    assert verdicts == {"B": "met", "C": "below", "A": "deferred"}


def test_list_quarterly_maps_real_engine_verdict_tokens(
    monkeypatch, redis_client, reports_root
):
    """Cross-lane contract: the exact verdict strings the 6A engine emits
    (shared/reports/feedback.py) must map onto the 4 UI badge buckets, not
    fall through to "unknown". Guards the meets/on_track/outperform gap.
    """
    body = {
        "kind": "quarterly",
        "period_label": "2026-Q2",
        "generated_at": "2026-07-01T09:00:00+09:00",
        # nested-in-track verdict field, exactly as compute_quarter_* returns.
        "tracks": {
            "B": {"trades": 40, "verdict": "meets"},
            "C": {"trades": 12, "verdict": "on_track"},
            "A": {"trades": 0, "verdict": "outperform"},
        },
        "missing": [],
    }
    _write_report(reports_root, "quarterly", "2026-Q2", body)
    client = _client(monkeypatch, redis_client, reports_root)

    resp = client.get("/api/reports/feedback", params={"kind": "quarterly"})
    assert resp.status_code == 200
    verdicts = resp.json()["reports"][0]["verdicts"]
    # meets / on_track / outperform are all "met" (success) — never "unknown".
    assert verdicts == {"B": "met", "C": "met", "A": "met"}


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("meets", "met"),
        ("on_track", "met"),
        ("outperform", "met"),
        ("below", "below"),
        ("below_breakeven", "below"),
        ("reduce_capital_50", "below"),
        ("review_termination", "below"),
        ("underperform", "below"),
        ("insufficient_evidence", "insufficient"),
        ("deferred", "deferred"),
    ],
)
def test_normalize_verdict_covers_all_engine_tokens(token, expected):
    from services.dashboard.routes import feedback

    assert feedback._normalize_verdict(token) == expected


# --------------------------------------------------------------------------- #
# Single report
# --------------------------------------------------------------------------- #


def test_get_single_report_returns_full_json(monkeypatch, redis_client, reports_root):
    _write_report(reports_root, "weekly", "2026-07-06", _weekly_body("2026-07-06"))
    client = _client(monkeypatch, redis_client, reports_root)

    resp = client.get("/api/reports/feedback/weekly/2026-07-06")
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "weekly"
    assert body["md_exists"] is True
    assert body["report"]["tracks"]["B"]["trades"] == 12  # verbatim payload


def test_get_single_report_md_absent(monkeypatch, redis_client, reports_root):
    _write_report(
        reports_root, "weekly", "2026-07-06", _weekly_body("2026-07-06"), md=False
    )
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/weekly/2026-07-06")
    assert resp.status_code == 200
    assert resp.json()["md_exists"] is False


def test_get_single_report_404_when_missing(monkeypatch, redis_client, reports_root):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/monthly/2026-05")
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "period_label",
    ["2026", "2026-13-40", "2026-Q5", "../etc/passwd", "2026-07-06.json", "not-a-date"],
)
def test_get_single_report_rejects_bad_period_label(
    monkeypatch, redis_client, reports_root, period_label
):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get(f"/api/reports/feedback/weekly/{period_label}")
    # Malformed labels are rejected (400) or never routed (404) — never served.
    assert resp.status_code in (400, 404)


def test_get_single_report_rejects_unknown_kind(
    monkeypatch, redis_client, reports_root
):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/daily/2026-07-06")
    assert resp.status_code == 404


def test_path_traversal_encoded_is_blocked(monkeypatch, redis_client, reports_root):
    # Even if a caller tries an encoded traversal, the regex whitelist rejects it.
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/weekly/%2e%2e%2f%2e%2e%2fsecret")
    assert resp.status_code in (400, 404)


# --------------------------------------------------------------------------- #
# Latest (Redis pointer + file-scan fallback)
# --------------------------------------------------------------------------- #


def test_latest_from_redis_pointer(monkeypatch, redis_client, reports_root):
    redis_client.hset(
        LATEST_KEY,
        mapping={
            "kind": "weekly",
            "period_label": "2026-07-06",
            "generated_at": "2026-07-06T18:10:00+09:00",
            "json_path": "/app/reports/feedback/weekly/2026-07-06.json",
            "md_path": "/app/reports/feedback/weekly/2026-07-06.md",
            "headline": json.dumps({"text": "주간 요약"}),
        },
    )
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["source"] == "redis"
    assert body["kind"] == "weekly"
    assert body["period_label"] == "2026-07-06"
    assert body["headline"] == {"text": "주간 요약"}  # JSON string decoded


def test_latest_falls_back_to_file_scan(monkeypatch, redis_client, reports_root):
    _write_report(reports_root, "monthly", "2026-06", _weekly_body("2026-06"))
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["source"] == "scan"
    assert body["period_label"] == "2026-06"


def test_latest_unavailable_when_nothing_published(
    monkeypatch, redis_client, reports_root
):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = client.get("/api/reports/feedback/latest")
    assert resp.status_code == 200
    assert resp.json() == {"status": "unavailable", "source": None}


# --------------------------------------------------------------------------- #
# Read-only surface
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_write_methods_not_allowed(monkeypatch, redis_client, reports_root, method):
    client = _client(monkeypatch, redis_client, reports_root)
    resp = getattr(client, method)("/api/reports/feedback/weekly/2026-07-06")
    assert resp.status_code == 405
