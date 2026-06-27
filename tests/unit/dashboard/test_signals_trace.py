"""Tests for signal decision trace endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _reader_with_signals(signals: list[object]) -> MagicMock:
    return MagicMock(get_signals=MagicMock(return_value=signals))


async def _get(path: str):
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_signal_trace_returns_basic_signal_and_explicit_missing_gaps():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            {
                "id": "sig-basic-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
                "reason": "gap_reversion_candidate",
                "trace": {
                    "orderability": {"state": "paper_orderable"},
                    "reject_stage": "",
                    "reject_reason": "",
                },
            }
        ]
    )

    with patch.object(signals_route, "_get_reader", return_value=reader):
        response = await _get("/api/signals/sig-basic-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["id"] == "sig-basic-1"
    assert body["signal"]["symbol"] == "101S6000"
    assert body["summary"]["state"] == "orderable"
    assert "setup_a_gap_reversion generated BUY 101S6000" in body["summary"]["text"]
    assert body["llm_context"]["status"] == "not_available"
    assert body["scorecard"]["status"] == "missing"
    assert body["lifecycle"]["status"] == "missing"
    assert {gap["code"] for gap in body["evidence_gaps"]} >= {
        "llm_context_not_available",
        "scorecard_missing",
        "no_lifecycle_evidence",
    }


@pytest.mark.asyncio
async def test_signal_trace_skips_malformed_rows_and_finds_valid_signal():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            "stale-scalar-row",
            ["stale", "list", "row"],
            {
                "id": "sig-after-malformed",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
            },
        ]
    )

    with patch.object(signals_route, "_get_reader", return_value=reader):
        response = await _get(
            "/api/signals/sig-after-malformed/trace?asset_class=futures"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["id"] == "sig-after-malformed"
    assert body["summary"]["state"] == "generated"


@pytest.mark.asyncio
async def test_signal_trace_lineage_summary_does_not_claim_lifecycle_loaded():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            {
                "id": "sig-filled-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": True,
                "trace": {"fill_id": "fill-1"},
            }
        ]
    )

    with patch.object(signals_route, "_get_reader", return_value=reader):
        response = await _get("/api/signals/sig-filled-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["state"] == "filled"
    assert body["lifecycle"]["status"] == "missing"
    assert "fill evidence is available" not in body["summary"]["text"]
    assert (
        "lineage id is present; lifecycle evidence is not loaded yet"
        in body["summary"]["text"]
    )


@pytest.mark.asyncio
async def test_signal_trace_enriches_llm_context_and_scorecard_from_ledger(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_signal_decision(
        {
            "signal_id": "sig-ledger-1",
            "asset_class": "futures",
            "symbol": "101S6000",
            "strategy": "setup_a_gap_reversion",
            "decision": "generated",
            "created_at": "2026-06-27T00:19:00+00:00",
            "indicators": {"gap_pct": -0.42, "atr": 1.8},
            "thresholds": {"min_gap_pct": 0.3},
        }
    )
    ledger.record_market_context(
        {
            "asset_class": "futures",
            "context_type": "premarket",
            "created_at": "2026-06-27T00:10:00+00:00",
            "overall_signal": "BULLISH",
            "confidence": 0.71,
            "risk_mode": "risk_on",
            "regime": "trend",
            "risk_score": 0.22,
            "source": "llm_premarket_briefing",
        }
    )
    ledger.save_prediction(
        "2026-06-27",
        "direction",
        "2026-06-27T00:05:00+00:00",
        {"overall_signal": "BULLISH"},
        0.71,
    )
    ledger.save_score(
        {
            "date_kst": "2026-06-27",
            "facet": "direction",
            "correct": True,
            "value": 0.28,
            "economic_proxy": 0.18,
            "baseline_value": 0.10,
            "edge": 0.18,
            "detail": {"outcome": "up"},
            "scored_at": "2026-06-27T07:00:00+00:00",
        }
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "sig-ledger-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
            }
        ]
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(
            signals_route,
            "_get_trace_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
    ):
        response = await _get("/api/signals/sig-ledger-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_context"]["status"] == "ok"
    assert body["llm_context"]["overall_signal"] == "BULLISH"
    assert body["strategy_inputs"]["indicators"]["gap_pct"] == -0.42
    assert body["strategy_inputs"]["thresholds"]["min_gap_pct"] == 0.3
    assert body["scorecard"]["status"] == "ok"
    assert body["scorecard"]["facet"] == "direction"
    assert body["scorecard"]["edge"] == 0.18
    assert "llm_context_not_available" not in {
        gap["code"] for gap in body["evidence_gaps"]
    }
    assert "scorecard_missing" not in {gap["code"] for gap in body["evidence_gaps"]}


@pytest.mark.asyncio
async def test_signal_trace_scorecard_uses_no_future_trading_date(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.save_prediction(
        "2026-06-28",
        "direction",
        "2026-06-28T00:05:00+00:00",
        {"overall_signal": "BULLISH"},
        0.90,
    )
    ledger.save_score(
        {
            "date_kst": "2026-06-28",
            "facet": "direction",
            "correct": True,
            "value": 1.0,
            "economic_proxy": 1.0,
            "baseline_value": 0.0,
            "edge": 1.0,
            "detail": {"outcome": "future"},
            "scored_at": "2026-06-28T07:00:00+00:00",
        }
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "sig-no-lookahead",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": False,
            }
        ]
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(
            signals_route,
            "_get_trace_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
    ):
        response = await _get("/api/signals/sig-no-lookahead/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["scorecard"]["status"] == "missing"
    assert body["scorecard"]["date_kst"] is None
    assert "scorecard_missing" in {gap["code"] for gap in body["evidence_gaps"]}
