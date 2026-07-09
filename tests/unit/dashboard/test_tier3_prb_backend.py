"""Tests for Tier-3 PR-B backend additions:
- slippage/TCA fields on fills (trades_data._ledger_fill_to_dict + _slippage_bps)
- backtest-vs-paper divergence series (experiments._divergence_series)
- market-data bars route (empty-degrade path).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_slippage_bps_buy_adverse_positive():
    from services.dashboard.routes.trades_data import _slippage_bps

    # buy filled above requested → adverse → positive bps
    assert _slippage_bps(100.0, 100.5, "BUY") == 50.0
    # buy filled below requested → favorable → negative
    assert _slippage_bps(100.0, 99.5, "BUY") == -50.0


def test_slippage_bps_sell_sign_flips():
    from services.dashboard.routes.trades_data import _slippage_bps

    # sell filled below requested → adverse → positive (sign flipped vs buy)
    assert _slippage_bps(100.0, 99.5, "SELL") == 50.0
    assert _slippage_bps(100.0, 100.5, "SELL") == -50.0


def test_slippage_bps_none_when_no_requested():
    from services.dashboard.routes.trades_data import _slippage_bps

    assert _slippage_bps(None, 100.0, "BUY") is None
    assert _slippage_bps(0.0, 100.0, "BUY") is None


def test_fill_mapper_projects_execution_fields():
    from services.dashboard.routes.trades_data import _ledger_fill_to_dict

    fill = {
        "symbol": "005930",
        "side": "BUY",
        "price": 70_500.0,
        "quantity": 10,
        "filled_at": "2026-07-09T00:00:00+00:00",
        "payload": {
            "requested_price": 70_000.0,
            "filled_price": 70_500.0,
            "tick_size_points": 100.0,
            "slippage_ticks": 5.0,
            "trade_role": "entry",
        },
    }
    out = _ledger_fill_to_dict(fill)
    assert out["requested_price"] == 70_000.0
    assert out["tick_size_points"] == 100.0
    assert out["slippage_ticks"] == 5.0
    # (70500-70000)/70000 * 10000 ≈ 71.43 bps, buy adverse → positive
    assert out["slippage_bps"] is not None
    assert out["slippage_bps"] > 0


def test_fill_mapper_legacy_row_without_requested_price():
    from services.dashboard.routes.trades_data import _ledger_fill_to_dict

    fill = {"symbol": "X", "side": "SELL", "price": 1.0, "payload": {}}
    out = _ledger_fill_to_dict(fill)
    assert out["requested_price"] is None
    assert out["slippage_bps"] is None  # cannot compute without requested


def test_divergence_series_joins_on_date():
    from services.dashboard.routes.experiments import _divergence_series

    report = {
        "equity_curves": {
            "s1": [
                {"date": "2026-07-01", "equity": 100.0},
                {"date": "2026-07-02", "equity": 110.0},
                {"date": "2026-07-03", "equity": 121.0},
            ]
        }
    }
    paper = [
        {"trade_date": "2026-07-01", "total_equity": 100.0},
        {"trade_date": "2026-07-02", "total_equity": 105.0},
        {"trade_date": "2026-07-03", "total_equity": 108.0},
    ]
    out = _divergence_series(report, paper)
    assert out["status"] == "ok"
    assert len(out["points"]) == 3
    first = out["points"][0]
    # both indexed to 0% at the first shared date
    assert first["backtest_cum_pct"] == 0.0
    assert first["paper_cum_pct"] == 0.0
    # by day 3 backtest is +21%, paper +8% → divergence = paper - backtest < 0
    assert out["points"][2]["divergence_pct"] < 0


def test_divergence_series_no_report():
    from services.dashboard.routes.experiments import _divergence_series

    out = _divergence_series(None, [])
    assert out["status"] == "no_report"
    assert out["points"] == []


def test_divergence_series_no_overlap():
    from services.dashboard.routes.experiments import _divergence_series

    report = {"equity_curves": {"s1": [{"date": "2026-01-01", "equity": 100.0}]}}
    paper = [{"trade_date": "2026-07-01", "total_equity": 100.0}]
    out = _divergence_series(report, paper)
    assert out["status"] == "insufficient_data"


def test_market_data_bars_empty_degrade(monkeypatch):
    import importlib

    from services.dashboard.routes import market_data

    importlib.reload(market_data)

    # Force the store factory to raise → route must degrade to empty, not 500.
    def _boom(*args, **kwargs):
        raise RuntimeError("no parquet")

    import shared.storage.market_data_store as mds

    monkeypatch.setattr(mds, "create_market_data_store", _boom)

    app = FastAPI()
    app.include_router(market_data.router)
    client = TestClient(app)
    resp = client.get("/api/market-data/bars?symbol=005930&timeframe=daily&days=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "empty"
    assert body["bars"] == []
    assert body["symbol"] == "005930"
