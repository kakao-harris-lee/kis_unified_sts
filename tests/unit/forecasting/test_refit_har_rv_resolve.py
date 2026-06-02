"""Unit tests for refit_har_rv._resolve_proxy_code contract resolution.

Regression: the resolver picked an illiquid far-month (A01612, 1 bar / vol=18)
when the active near-month had a brief ingestion gap, whose degenerate recent
RV then produced a NaN OOS R² that blocked the daily HAR-RV refit. The guard
query now requires a minimum bar count and a wider window so a stray single
bar cannot win.
"""

from __future__ import annotations

from scripts.forecasting.refit_har_rv import (
    _FALLBACK_PROXY_CODE,
    _MIN_RESOLVE_BARS,
    _resolve_proxy_code,
)


class _StubCH:
    def __init__(self, rows=None, raise_exc=None):
        self._rows = rows or []
        self._raise = raise_exc
        self.last_query: str | None = None
        self.last_params: dict | None = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        if self._raise is not None:
            raise self._raise
        return self._rows


def test_env_override_takes_precedence(monkeypatch):
    monkeypatch.setenv("FORECAST_REFIT_CODE", "A09999")
    ch = _StubCH(rows=[("A01606", 100, 200)])
    assert _resolve_proxy_code(ch) == "A09999"
    # Override short-circuits before any DB query.
    assert ch.last_query is None


def test_auto_resolve_picks_liquid_contract(monkeypatch):
    monkeypatch.delenv("FORECAST_REFIT_CODE", raising=False)
    ch = _StubCH(rows=[("A01606", 78_679, 204)])
    assert _resolve_proxy_code(ch) == "A01606"
    # Guard query must filter by bar count and widen the window so a stray
    # single-bar far-month cannot win.
    assert "HAVING" in ch.last_query
    assert "5 DAY" in ch.last_query
    assert ch.last_params == {"min_bars": _MIN_RESOLVE_BARS}


def test_empty_result_falls_back(monkeypatch):
    monkeypatch.delenv("FORECAST_REFIT_CODE", raising=False)
    # HAVING filtered out every stray-bar contract → no eligible rows.
    ch = _StubCH(rows=[])
    assert _resolve_proxy_code(ch) == _FALLBACK_PROXY_CODE


def test_query_error_falls_back(monkeypatch):
    monkeypatch.delenv("FORECAST_REFIT_CODE", raising=False)
    ch = _StubCH(raise_exc=RuntimeError("ch down"))
    assert _resolve_proxy_code(ch) == _FALLBACK_PROXY_CODE
