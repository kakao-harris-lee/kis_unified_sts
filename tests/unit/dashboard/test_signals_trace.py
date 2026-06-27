"""Tests for signal decision trace endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _reader_with_signals(signals: list[object]) -> MagicMock:
    return MagicMock(get_signals=MagicMock(return_value=signals))


def _missing_lifecycle(signals_route):
    return signals_route.DecisionTraceLifecycle(
        status="missing",
        steps=[],
        warnings=["no_lifecycle_evidence"],
    )


async def _get(path: str):
    from services.dashboard.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _record_complete_lifecycle(
    ledger,
    *,
    signal_id: str,
    symbol: str,
    order_id: str,
    fill_id: str,
    position_id: str,
    trade_id: str,
) -> None:
    ledger.record_signal_decision(
        {
            "decision_id": f"{signal_id}-decision",
            "signal_id": signal_id,
            "asset_class": "futures",
            "code": symbol,
            "strategy": "setup_a_gap_reversion",
            "decision": "accepted",
            "created_at": "2026-06-27T00:19:00+00:00",
            "side": "BUY",
        }
    )
    ledger.record_order(
        {
            "id": order_id,
            "idempotency_key": order_id,
            "signal_id": signal_id,
            "asset_class": "futures",
            "code": symbol,
            "side": "BUY",
            "order_type": "limit",
            "quantity": 1,
            "price": 390.25,
            "status": "submitted",
            "strategy": "setup_a_gap_reversion",
        }
    )
    ledger.record_fill(
        {
            "id": fill_id,
            "idempotency_key": fill_id,
            "signal_id": signal_id,
            "order_id": order_id,
            "asset_class": "futures",
            "code": symbol,
            "side": "BUY",
            "filled_qty": 1,
            "filled_price": 390.25,
            "filled_at": "2026-06-27T00:21:00+00:00",
            "trade_role": "entry",
        }
    )
    ledger.record_position_snapshot(
        {
            "id": position_id,
            "idempotency_key": f"{position_id}-snapshot",
            "asset_class": "futures",
            "code": symbol,
            "side": "long",
            "strategy": "setup_a_gap_reversion",
            "quantity": 1,
            "entry_time": "2026-06-27T00:21:00+00:00",
            "entry_price": 390.25,
            "snapshot_time": "2026-06-27T00:22:00+00:00",
        }
    )
    ledger.record_trade(
        {
            "id": trade_id,
            "idempotency_key": trade_id,
            "signal_id": signal_id,
            "order_id": order_id,
            "fill_id": fill_id,
            "position_id": position_id,
            "asset_class": "futures",
            "code": symbol,
            "side": "long",
            "strategy": "setup_a_gap_reversion",
            "entry_time": "2026-06-27T00:21:00+00:00",
            "entry_price": 390.25,
            "exit_time": "2026-06-27T00:45:00+00:00",
            "exit_price": 392.0,
            "quantity": 1,
            "exit_reason": "target",
        }
    )


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

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
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

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
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

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
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
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
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
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
        response = await _get("/api/signals/sig-no-lookahead/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["scorecard"]["status"] == "missing"
    assert body["scorecard"]["date_kst"] is None
    assert "scorecard_missing" in {gap["code"] for gap in body["evidence_gaps"]}


@pytest.mark.asyncio
async def test_signal_trace_market_context_finds_prior_row_past_future_rows(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    ledger.record_market_context(
        {
            "asset_class": "futures",
            "context_type": "premarket",
            "created_at": "2026-06-27T00:10:00+00:00",
            "overall_signal": "BULLISH_PRIOR",
            "confidence": 0.67,
            "risk_mode": "risk_on",
            "regime": "trend",
            "risk_score": 0.25,
            "source": "prior_context",
        }
    )
    for offset in range(60):
        total_minutes = 21 + offset
        hour = total_minutes // 60
        minute = total_minutes % 60
        ledger.record_market_context(
            {
                "asset_class": "futures",
                "context_type": "intraday",
                "created_at": f"2026-06-27T{hour:02d}:{minute:02d}:00+00:00",
                "overall_signal": "FUTURE",
                "confidence": 0.99,
                "risk_mode": "risk_off",
                "regime": "future",
                "risk_score": 0.99,
                "source": f"future_context_{offset}",
            }
        )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "sig-context-prior",
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
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
        response = await _get(
            "/api/signals/sig-context-prior/trace?asset_class=futures"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["llm_context"]["status"] == "ok"
    assert body["llm_context"]["overall_signal"] == "BULLISH_PRIOR"
    assert "llm_context_not_available" not in {
        gap["code"] for gap in body["evidence_gaps"]
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy", "setup_type"),
    [
        ("A_gap_reversion", None),
        ("futures_monitor", "A"),
    ],
)
async def test_signal_trace_scorecard_maps_setup_ac_shorthand_to_direction(
    tmp_path,
    strategy,
    setup_type,
):
    from services.dashboard.routes import signals as signals_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
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

    raw_signal = {
        "id": f"sig-scorecard-{strategy}-{setup_type or 'none'}",
        "symbol": "101S6000",
        "side": "BUY",
        "signal_type": "entry",
        "strategy": strategy,
        "price": 390.25,
        "confidence": 0.72,
        "timestamp": "2026-06-27T00:20:00+00:00",
        "executed": False,
    }
    if setup_type is not None:
        raw_signal["setup_type"] = setup_type

    reader = _reader_with_signals([raw_signal])

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(
            signals_route,
            "_get_trace_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
        patch.object(
            signals_route,
            "_build_trace_lifecycle",
            return_value=_missing_lifecycle(signals_route),
        ),
    ):
        response = await _get(
            f"/api/signals/{raw_signal['id']}/trace?asset_class=futures"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["scorecard"]["status"] == "ok"
    assert body["scorecard"]["facet"] == "direction"
    assert body["scorecard"]["edge"] == 0.18
    assert "scorecard_missing" not in {gap["code"] for gap in body["evidence_gaps"]}


@pytest.mark.asyncio
async def test_signal_trace_embeds_lifecycle_and_removes_lifecycle_gap():
    from services.dashboard.routes import signals as signals_route

    reader = _reader_with_signals(
        [
            {
                "id": "sig-life-1",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": True,
                "trace": {"order_id": "ord-1", "fill_id": "fill-1"},
            }
        ]
    )
    lifecycle = signals_route.DecisionTraceLifecycle(
        status="partial",
        steps=[
            {
                "stage": "signal",
                "label": "Signal",
                "status": "generated",
                "id": "sig-life-1",
                "timestamp": "2026-06-27T00:20:00+00:00",
                "source": "runtime_ledger",
                "summary": "BUY 101S6000",
                "details": {"strategy": "setup_a_gap_reversion"},
            }
        ],
        warnings=["partial_legacy_lineage"],
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(signals_route, "_build_trace_lifecycle", return_value=lifecycle),
    ):
        response = await _get("/api/signals/sig-life-1/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle"]["status"] == "partial"
    assert body["lifecycle"]["steps"][0]["stage"] == "signal"
    assert "partial_legacy_lineage" in body["summary"]["warnings"]
    assert "no_lifecycle_evidence" not in {gap["code"] for gap in body["evidence_gaps"]}


@pytest.mark.asyncio
async def test_signal_trace_lifecycle_does_not_attach_stale_same_symbol_rows(tmp_path):
    from services.dashboard.routes import signals as signals_route
    from services.dashboard.routes import trades as trades_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    _record_complete_lifecycle(
        ledger,
        signal_id="old-sig",
        symbol="101S6000",
        order_id="old-order",
        fill_id="old-fill",
        position_id="old-position",
        trade_id="old-trade",
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "current-sig",
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
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(
            trades_route,
            "_get_runtime_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
        patch.object(
            trades_route,
            "_load_lifecycle_redis_rows",
            return_value=trades_route._empty_lifecycle_rows(),
        ),
    ):
        response = await _get("/api/signals/current-sig/trace?asset_class=futures")

    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle"]["status"] == "missing"
    stale_ids = {"old-order", "old-fill", "old-position", "old-trade"}
    assert stale_ids.isdisjoint({step["id"] for step in body["lifecycle"]["steps"]})
    assert stale_ids.isdisjoint(set(body["lineage"].values()))


@pytest.mark.asyncio
async def test_signal_trace_lifecycle_uses_exact_position_id_without_symbol_fallback(
    tmp_path,
):
    from services.dashboard.routes import signals as signals_route
    from services.dashboard.routes import trades as trades_route
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    db_path = tmp_path / "runtime.db"
    ledger = SQLiteRuntimeLedger(db_path)
    _record_complete_lifecycle(
        ledger,
        signal_id="old-sig",
        symbol="101S6000",
        order_id="old-order",
        fill_id="old-fill",
        position_id="old-position",
        trade_id="old-trade",
    )
    ledger.record_position_snapshot(
        {
            "id": "pos-current",
            "idempotency_key": "pos-current-snapshot",
            "asset_class": "futures",
            "code": "DIFFERENT",
            "side": "long",
            "strategy": "setup_a_gap_reversion",
            "quantity": 1,
            "entry_time": "2026-06-27T00:21:00+00:00",
            "entry_price": 390.25,
            "snapshot_time": "2026-06-27T00:22:00+00:00",
        }
    )
    ledger.close()

    reader = _reader_with_signals(
        [
            {
                "id": "current-position-sig",
                "symbol": "101S6000",
                "side": "BUY",
                "signal_type": "entry",
                "strategy": "setup_a_gap_reversion",
                "price": 390.25,
                "confidence": 0.72,
                "timestamp": "2026-06-27T00:20:00+00:00",
                "executed": True,
                "trace": {"position_id": "pos-current"},
            }
        ]
    )

    with (
        patch.object(signals_route, "_get_reader", return_value=reader),
        patch.object(signals_route, "_get_trace_ledger", return_value=None),
        patch.object(
            trades_route,
            "_get_runtime_ledger",
            side_effect=lambda: SQLiteRuntimeLedger(db_path),
        ),
        patch.object(
            trades_route,
            "_load_lifecycle_redis_rows",
            return_value=trades_route._empty_lifecycle_rows(),
        ),
    ):
        response = await _get(
            "/api/signals/current-position-sig/trace?asset_class=futures"
        )

    assert response.status_code == 200
    body = response.json()
    by_stage = {step["stage"]: step for step in body["lifecycle"]["steps"]}
    assert by_stage["position"]["id"] == "pos-current"
    assert by_stage["position"]["source"] == "runtime_ledger"
    stale_ids = {"old-order", "old-fill", "old-position", "old-trade"}
    assert stale_ids.isdisjoint({step["id"] for step in body["lifecycle"]["steps"]})
