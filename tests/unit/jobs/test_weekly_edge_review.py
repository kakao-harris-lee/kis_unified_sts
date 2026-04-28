"""Tests for jobs/weekly_edge_review.py — Phase 4 Task 15."""

from unittest.mock import AsyncMock

import pytest

from jobs.weekly_edge_review import (
    EdgeRow,
    WeeklyEdgeReviewJob,
    classify_alerts,
    format_telegram_message,
)


def _row(
    setup="A_gap_reversion",
    n=10,
    avg_slip=0.2,
    p95_slip=0.4,
    pnl_krw=500_000,
    win_rate=0.55,
):
    return EdgeRow(
        setup_type=setup,
        n=n,
        avg_slip=avg_slip,
        p95_slip=p95_slip,
        pnl_krw=pnl_krw,
        win_rate=win_rate,
    )


class TestClassifyAlerts:
    def test_no_alerts_when_healthy(self):
        rows = [_row()]
        alerts = classify_alerts(rows, prev_week_rows=rows)
        assert alerts == []

    def test_negative_pnl_alert(self):
        rows = [_row(pnl_krw=-100_000)]
        alerts = classify_alerts(rows, prev_week_rows=rows)
        assert any(a.kind == "negative_ev" for a in alerts)
        assert any("A_gap_reversion" in a.message for a in alerts)

    def test_high_slippage_alert(self):
        rows = [_row(avg_slip=0.6)]
        alerts = classify_alerts(rows, prev_week_rows=rows)
        assert any(a.kind == "slippage" for a in alerts)

    def test_zero_trades_two_weeks_alert(self):
        rows_now = [_row(setup="C_event_reaction", n=0)]
        rows_prev = [_row(setup="C_event_reaction", n=0)]
        alerts = classify_alerts(rows_now, prev_week_rows=rows_prev)
        assert any(a.kind == "no_trades_2w" for a in alerts)

    def test_no_trades_2w_alert_skipped_when_only_one_week_zero(self):
        rows_now = [_row(setup="C_event_reaction", n=0)]
        rows_prev = [_row(setup="C_event_reaction", n=5)]
        alerts = classify_alerts(rows_now, prev_week_rows=rows_prev)
        assert all(a.kind != "no_trades_2w" for a in alerts)

    def test_multiple_alerts_per_setup(self):
        rows = [_row(pnl_krw=-50_000, avg_slip=0.7)]
        alerts = classify_alerts(rows, prev_week_rows=rows)
        kinds = {a.kind for a in alerts}
        assert "negative_ev" in kinds
        assert "slippage" in kinds


class TestFormatTelegramMessage:
    def test_message_includes_setup_stats(self):
        rows = [_row()]
        msg = format_telegram_message(rows, alerts=[])
        assert "A_gap_reversion" in msg
        assert "n=10" in msg or "10" in msg

    def test_message_includes_alerts_section_when_present(self):
        rows = [_row(pnl_krw=-100_000)]
        alerts = classify_alerts(rows, prev_week_rows=rows)
        msg = format_telegram_message(rows, alerts=alerts)
        assert "ALERT" in msg or "alert" in msg.lower()

    def test_message_no_alerts_section_when_clean(self):
        rows = [_row()]
        msg = format_telegram_message(rows, alerts=[])
        assert "ALERT" not in msg


class TestWeeklyEdgeReviewJob:
    @pytest.mark.asyncio
    async def test_run_queries_ch_and_sends_telegram(self):
        ch_client = AsyncMock()
        # Fetch returns rows: (setup_type, n, avg_slip, p95_slip, pnl_krw, win_rate)
        ch_client.fetch.side_effect = [
            [("A_gap_reversion", 10, 0.2, 0.4, 500_000, 0.55)],  # current week
            [("A_gap_reversion", 8, 0.25, 0.45, 300_000, 0.50)],  # prev week
        ]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)

        await job.run()

        assert ch_client.fetch.await_count == 2
        telegram.send_message.assert_awaited_once()
        msg = telegram.send_message.call_args.args[0]
        assert "A_gap_reversion" in msg

    @pytest.mark.asyncio
    async def test_run_does_not_send_when_no_data(self):
        ch_client = AsyncMock()
        ch_client.fetch.side_effect = [[], []]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)

        await job.run()

        # No data → no telegram (avoid empty noise spam)
        telegram.send_message.assert_not_awaited()
