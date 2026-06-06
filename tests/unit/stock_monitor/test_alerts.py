"""Selective Telegram policy: no per-fill spam; notable exits / health / digest only."""

from __future__ import annotations

import pytest

from services.stock_monitor.alerts import AlertSink, SessionDigest


class _FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, message: str, **_kwargs: object) -> None:
        self.sent.append(message)


@pytest.mark.asyncio
async def test_entry_never_alerts() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    await sink.on_entry(code="005930", strategy="vr", quantity=10, price=71000.0)
    assert n.sent == []  # entries are routine -> never alert


@pytest.mark.asyncio
async def test_small_exit_not_alerted_big_exit_alerted() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    await sink.on_exit(code="005930", pnl=1000.0, pnl_pct=1.0)  # below threshold
    assert n.sent == []
    await sink.on_exit(code="005930", pnl=-50000.0, pnl_pct=-5.0)  # above threshold
    assert len(n.sent) == 1 and "005930" in n.sent[0]


@pytest.mark.asyncio
async def test_exit_at_threshold_is_alerted() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    # gate is strict `<`, so pnl_pct == threshold IS notable
    await sink.on_exit(code="005930", pnl=30000.0, pnl_pct=3.0)
    assert len(n.sent) == 1 and "005930" in n.sent[0]


@pytest.mark.asyncio
async def test_on_exit_accumulates_digest() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    # mix of below/above threshold — every exit must count toward the digest
    await sink.on_exit(code="005930", pnl=1000.0, pnl_pct=1.0)  # below
    await sink.on_exit(code="000660", pnl=-50000.0, pnl_pct=-5.0)  # above
    await sink.on_exit(code="035720", pnl=2000.0, pnl_pct=0.5)  # below
    assert sink.digest.trades == 3
    assert sink.digest.realized_pnl == 1000.0 - 50000.0 + 2000.0
    assert sink.digest.wins == 2


@pytest.mark.asyncio
async def test_live_no_notifier_falls_through_to_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    sink = AlertSink(notifier=None, mode="live", pnl_alert_pct=3.0)
    with caplog.at_level(logging.INFO):
        # must not raise even though there is no notifier in live mode
        await sink.on_exit(code="005930", pnl=-50000.0, pnl_pct=-5.0)
    assert any("would-alert" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_send_health_live() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    await sink.send_health("redis stream lag 42s")
    assert len(n.sent) == 1 and "redis stream lag 42s" in n.sent[0]


def test_invalid_mode_rejected() -> None:
    n = _FakeNotifier()
    with pytest.raises(ValueError, match="unknown mode"):
        AlertSink(notifier=n, mode="dry-run", pnl_alert_pct=3.0)


@pytest.mark.asyncio
async def test_shadow_mode_suppresses_to_log(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="shadow", pnl_alert_pct=3.0)
    with caplog.at_level(logging.INFO):
        await sink.on_exit(code="005930", pnl=-50000.0, pnl_pct=-5.0)
    assert n.sent == []  # shadow never sends
    assert any("would-alert" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_digest_aggregates_and_emits() -> None:
    n = _FakeNotifier()
    sink = AlertSink(notifier=n, mode="live", pnl_alert_pct=3.0)
    sink.digest.add(pnl=1000.0)
    sink.digest.add(pnl=-500.0)
    sink.digest.add(pnl=2000.0)
    await sink.emit_digest(open_count=2)
    assert len(n.sent) == 1
    msg = n.sent[0]
    assert "거래 3건" in msg  # trade count
    assert "2500" in msg or "2,500" in msg  # net pnl


def test_digest_reset() -> None:
    d = SessionDigest()
    d.add(pnl=100.0)
    d.add(pnl=-50.0)
    assert d.trades == 2 and d.realized_pnl == 50.0 and d.wins == 1
    d.reset()
    assert d.trades == 0 and d.realized_pnl == 0.0 and d.wins == 0
