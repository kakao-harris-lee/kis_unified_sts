"""Tests for signal decision trace endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _reader_with_signals(signals: list[dict]) -> MagicMock:
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
