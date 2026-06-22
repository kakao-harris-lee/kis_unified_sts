"""Regression tests for briefing delivery outside the intraday alert window.

Root cause (fixed): `llm_premarket_briefing.py` called `notifier_for_domain("briefing")`
with the default 08:30-15:40 active window.  The briefing runs at 06:30 KST so only
the header (is_critical=True) was delivered; every body message (is_critical=False)
was silently dropped at TelegramNotifier.send_message line 103.

Fix: briefing notifiers use notification_start="00:00" / notification_end="23:59" so
scheduled briefings always deliver in full, while the intraday-alert gate is unchanged.
"""

from __future__ import annotations

from datetime import time
from unittest.mock import patch

import pytest

from shared.notification.telegram import TelegramNotifier, notifier_for_domain

BRIEFING_ENV_KEYS = [
    "TELEGRAM_BRIEFING_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHAT_ID",
]


@pytest.fixture(autouse=True)
def _clean_briefing_env(monkeypatch):
    """Each test starts with a clean TELEGRAM_BRIEFING_* environment."""
    for key in BRIEFING_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


class TestBriefingNotifierDeliveryWindow:
    """Briefing notifier must deliver body messages at 06:30 KST (pre-market)."""

    def _make_briefing_notifier(self) -> TelegramNotifier:
        """Mirrors what llm_premarket_briefing.py and llm_nightly_analysis.py do."""
        return TelegramNotifier(
            bot_token="dummy_tok",
            chat_id="dummy_chat",
            notification_start="00:00",
            notification_end="23:59",
        )

    @pytest.mark.parametrize(
        "test_time",
        [
            time(6, 30),   # premarket briefing cron start
            time(21, 0),   # nightly briefing cron start
            time(0, 0),    # midnight
            time(23, 59),  # end of day
        ],
    )
    def test_briefing_notifier_active_at_off_hours(self, test_time):
        """Briefing notifier with 24h window reports active at any hour."""
        notifier = self._make_briefing_notifier()
        with patch("shared.notification.telegram.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = test_time
            assert notifier.is_notification_active() is True

    @pytest.mark.parametrize(
        "test_time",
        [
            time(6, 30),   # premarket — before intraday window
            time(21, 0),   # nightly — after intraday window
        ],
    )
    def test_intraday_alert_notifier_inactive_at_off_hours(self, test_time):
        """Default intraday-alert notifier (08:30-15:40) is inactive at off-hours.

        This confirms the gate is NOT broken by the briefing fix.
        """
        intraday_notifier = TelegramNotifier(
            bot_token="dummy_tok",
            chat_id="dummy_chat",
            notification_start="08:30",
            notification_end="15:40",
        )
        with patch("shared.notification.telegram.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = test_time
            assert intraday_notifier.is_notification_active() is False


class TestNotifierForDomainBriefingWindow:
    """notifier_for_domain("briefing") with 24h window delivers body off-hours."""

    def test_briefing_notifier_24h_window_via_factory(self, monkeypatch):
        """Factory call (premarket/nightly style) produces a 24h-window notifier."""
        monkeypatch.setenv("TELEGRAM_BRIEFING_BOT_TOKEN", "BRF_TOK")
        monkeypatch.setenv("TELEGRAM_BRIEFING_CHAT_ID", "BRF_CHAT")

        notifier = notifier_for_domain(
            "briefing",
            notification_start="00:00",
            notification_end="23:59",
        )
        assert notifier is not None

        # Must be active at 06:30 (premarket) and 21:00 (nightly)
        for test_time in (time(6, 30), time(21, 0)):
            with patch("shared.notification.telegram.datetime") as mock_dt:
                mock_dt.now.return_value.time.return_value = test_time
                assert notifier.is_notification_active() is True, (
                    f"Briefing notifier should be active at {test_time} (24h window)"
                )

    def test_default_briefing_notifier_blocks_body_at_0630(self, monkeypatch):
        """Without the fix: default 08:30-15:40 window blocks at 06:30.

        This documents the original bug — the default window is the wrong choice
        for scheduled briefings.
        """
        monkeypatch.setenv("TELEGRAM_BRIEFING_BOT_TOKEN", "BRF_TOK")
        monkeypatch.setenv("TELEGRAM_BRIEFING_CHAT_ID", "BRF_CHAT")

        buggy_notifier = notifier_for_domain("briefing")  # default window
        assert buggy_notifier is not None

        with patch("shared.notification.telegram.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(6, 30)
            # Old behaviour: inactive at 06:30 → body messages dropped
            assert buggy_notifier.is_notification_active() is False, (
                "Default window must still block at 06:30 — this is correct for "
                "intraday alerts; scheduled briefings must opt in to 24h window."
            )
