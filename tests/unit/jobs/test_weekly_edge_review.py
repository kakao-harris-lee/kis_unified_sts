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
        # current week returns 6-tuple per the materialise_rows contract
        # prev week returns 2-tuple (setup_type, n) — entry-only count
        ch_client.fetch.side_effect = [
            [("A_gap_reversion", 10, 0.2, 0.4, 500_000, 0.55)],
            [("A_gap_reversion", 8)],
        ]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)

        await job.run()

        assert ch_client.fetch.await_count == 2
        telegram.send_message.assert_awaited_once()
        msg = telegram.send_message.call_args.args[0]
        assert "A_gap_reversion" in msg

    @pytest.mark.asyncio
    async def test_telegram_uses_is_critical_to_bypass_05_kst_gate(self):
        """05:00 KST cron is outside TelegramNotifier's 08:30-15:40 window;
        is_critical=True must be set so the gate doesn't drop the message."""
        ch_client = AsyncMock()
        ch_client.fetch.side_effect = [
            [("A_gap_reversion", 10, 0.2, 0.4, 500_000, 0.55)],
            [("A_gap_reversion", 8)],
        ]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)

        await job.run()

        kwargs = telegram.send_message.call_args.kwargs
        assert kwargs.get("is_critical") is True

    @pytest.mark.asyncio
    async def test_run_does_not_send_when_no_data(self):
        ch_client = AsyncMock()
        ch_client.fetch.side_effect = [[], []]
        telegram = AsyncMock()
        job = WeeklyEdgeReviewJob(ch_client=ch_client, telegram_client=telegram)

        await job.run()

        # No data → no telegram (avoid empty noise spam)
        telegram.send_message.assert_not_awaited()


class TestMaterialiseRows:
    """Phase 4 spec §5.3 'no_trades_2w' alert requires n=0 rows even when
    the INNER-JOIN aggregate skips zero-fill setups."""

    def test_zero_fill_setups_get_n_zero_rows(self):
        from jobs.weekly_edge_review import _materialise_rows

        # SQL produced only one of the two known setups
        result = _materialise_rows([("A_gap_reversion", 10, 0.2, 0.4, 500_000, 0.55)])
        setups = {r.setup_type: r for r in result}
        assert "A_gap_reversion" in setups
        assert setups["A_gap_reversion"].n == 10
        # The OTHER known setup must appear with n=0
        c = setups["C_event_reaction"]
        assert c.n == 0
        assert c.pnl_krw == 0.0

    def test_no_duplicate_when_all_setups_present(self):
        from jobs.weekly_edge_review import _materialise_rows

        result = _materialise_rows(
            [
                ("A_gap_reversion", 10, 0.2, 0.4, 500_000, 0.55),
                ("C_event_reaction", 5, 0.3, 0.5, 200_000, 0.40),
            ]
        )
        names = sorted(r.setup_type for r in result)
        assert names == ["A_gap_reversion", "C_event_reaction"]
        assert len(result) == 2

    def test_known_setups_param_overrides_default(self):
        from jobs.weekly_edge_review import _materialise_rows

        result = _materialise_rows([], known_setups=["X", "Y", "Z"])
        names = sorted(r.setup_type for r in result)
        assert names == ["X", "Y", "Z"]
        assert all(r.n == 0 for r in result)
