from __future__ import annotations

from datetime import date

import pytest

import scripts.analysis.futures_minute_coverage_gate as gate
from shared.collector.historical.parquet_backfill import (
    MINUTE_COMPLETENESS_MIN_ROWS,
    MINUTE_SESSION_BARS,
)


class _FakeStore:
    """Read-only market-data store double returning canned bar counts."""

    def __init__(self, counts_by_day: dict[date, int]) -> None:
        self.counts_by_day = counts_by_day
        self.queries: list[date] = []

    def count_minute_bars_for_day(self, _code: str, day: date) -> int:
        self.queries.append(day)
        return self.counts_by_day.get(day, 0)


def _config(**overrides) -> gate.CoverageConfig:
    """Build a CoverageConfig using the same defaults as the module (_DEFAULT_HALF_DAY_MIN_ROWS)."""
    base = {
        "lookback_days": 5,
        "min_rows": MINUTE_COMPLETENESS_MIN_ROWS,
        "half_day_min_rows": gate._DEFAULT_HALF_DAY_MIN_ROWS,
        "notify_on_shortfall": True,
    }
    base.update(overrides)
    return gate.CoverageConfig(**base)


def test_full_day_is_ok_no_shortfall():
    day = date(2026, 6, 18)  # Thursday, trading day
    store = _FakeStore({day: MINUTE_SESSION_BARS})
    report = gate.evaluate_coverage(
        store=store,
        code="A05607",
        trading_days=[day],
        config=_config(),
    )
    assert report.shortfalls == []
    assert report.has_shortfall is False
    assert report.checked_days == 1


def test_shortfall_day_is_flagged():
    # 102/360-style single-page-only shortfall.
    day = date(2026, 6, 18)
    store = _FakeStore({day: 102})
    report = gate.evaluate_coverage(
        store=store,
        code="A05607",
        trading_days=[day],
        config=_config(),
    )
    assert report.has_shortfall is True
    assert len(report.shortfalls) == 1
    shortfall = report.shortfalls[0]
    assert shortfall.code == "A05607"
    assert shortfall.day == day
    assert shortfall.bars == 102
    assert shortfall.expected == MINUTE_COMPLETENESS_MIN_ROWS


def test_half_day_tolerance_not_flagged():
    # A realistic KRX early-close / half-day (~200 bars) must NOT be flagged with
    # the DEFAULT half_day_min_rows (150).  Bars=200 sits in the tolerated band:
    #   half_day_min_rows (150) <= 200 < min_rows (303)  → tolerated, not flagged.
    day = date(2026, 6, 18)
    store = _FakeStore({day: 200})
    report = gate.evaluate_coverage(
        store=store,
        code="A05607",
        trading_days=[day],
        config=_config(),  # default floor = 150
    )
    assert report.has_shortfall is False
    assert report.shortfalls == []


def test_single_page_fetch_is_flagged():
    # A single-KIS-page-only fetch (~102 bars) must be flagged; 102 < 150 floor.
    day = date(2026, 6, 18)
    store = _FakeStore({day: 102})
    report = gate.evaluate_coverage(
        store=store,
        code="A05607",
        trading_days=[day],
        config=_config(),  # default floor = 150
    )
    assert report.has_shortfall is True
    assert len(report.shortfalls) == 1
    assert report.shortfalls[0].bars == 102


def test_in_progress_day_is_skipped(monkeypatch):
    # An open (not-yet-closed) trading day must be skipped, never flagged.
    open_day = date(2026, 6, 19)
    monkeypatch.setattr(gate, "_is_day_closed", lambda d: d != open_day)
    store = _FakeStore({open_day: 12})
    report = gate.evaluate_coverage(
        store=store,
        code="A05607",
        trading_days=[open_day],
        config=_config(),
    )
    assert report.checked_days == 0
    assert report.skipped_days == 1
    assert report.has_shortfall is False
    assert open_day not in store.queries


def test_run_gate_alerts_on_shortfall(monkeypatch):
    day = date(2026, 6, 18)
    store = _FakeStore({day: 102})

    sent: list[dict] = []

    class _FakeNotifier:
        async def send_message(self, text, **kwargs):
            sent.append({"text": text, "kwargs": kwargs})

    monkeypatch.setattr(gate, "_build_store", lambda: store)
    monkeypatch.setattr(gate, "_front_month_code", lambda _d, **_kw: "A05607")
    monkeypatch.setattr(gate, "_resolve_trading_days", lambda _cfg, _d: [day])
    monkeypatch.setattr(gate, "_is_day_closed", lambda _d: True)
    monkeypatch.setattr(gate, "notifier_for_domain", lambda _domain: _FakeNotifier())

    rc = gate.run_gate(report_date=date(2026, 6, 19), config=_config())

    assert rc == 1  # shortfall exit code
    assert len(sent) == 1
    assert "A05607" in sent[0]["text"]
    assert "2026-06-18" in sent[0]["text"]
    assert "102" in sent[0]["text"]


def test_run_gate_no_alert_when_full(monkeypatch):
    day = date(2026, 6, 18)
    store = _FakeStore({day: MINUTE_SESSION_BARS})

    sent: list[dict] = []

    class _FakeNotifier:
        async def send_message(self, text, **_kwargs):
            sent.append({"text": text})

    monkeypatch.setattr(gate, "_build_store", lambda: store)
    monkeypatch.setattr(gate, "_front_month_code", lambda _d, **_kw: "A05607")
    monkeypatch.setattr(gate, "_resolve_trading_days", lambda _cfg, _d: [day])
    monkeypatch.setattr(gate, "_is_day_closed", lambda _d: True)
    monkeypatch.setattr(
        gate,
        "notifier_for_domain",
        lambda _domain: pytest.fail("notifier must not be created when coverage is OK"),
    )

    rc = gate.run_gate(report_date=date(2026, 6, 19), config=_config())

    assert rc == 0
    assert sent == []


def test_run_gate_returns_rc2_on_store_error(monkeypatch):
    # When _build_store raises, run_gate must return rc=2 and send no alert.
    sent: list[dict] = []

    class _FakeNotifier:
        async def send_message(self, text, **_kwargs):
            sent.append({"text": text})

    def _raise():
        raise RuntimeError("parquet unavailable")

    monkeypatch.setattr(gate, "_build_store", _raise)
    monkeypatch.setattr(gate, "notifier_for_domain", lambda _domain: _FakeNotifier())

    rc = gate.run_gate(report_date=date(2026, 6, 19), config=_config())

    assert rc == 2
    assert sent == [], "No alert must be sent on store/script error"
