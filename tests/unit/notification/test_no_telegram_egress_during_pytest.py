"""Guard: no real Telegram credentials are live during a pytest session.

Regression: ``tests/conftest.py`` loads the repo ``.env`` (so integration
tests can reach Redis etc.). That ``.env`` also carries real
``TELEGRAM_*_BOT_TOKEN``/``CHAT_ID`` values, and any test that starts a real
``TradingOrchestrator`` without mocking ``_notify`` (e.g.
``test_orchestrator_lifecycle``) would then send real
"🚀 Trading Started" / "🛑 Trading Stopped" messages to the operator's
Telegram during ``pytest``.

conftest scrubs those credentials for the whole session so notifications
short-circuit ("Telegram not configured") instead of hitting the network.
These tests pin that behavior. They intentionally do NOT use monkeypatch,
so they observe the session-level environment as the orchestrator would.
"""

from __future__ import annotations

import os

from shared.notification.telegram import resolve_domain_credentials

# Keys mirror shared.notification.telegram._DOMAIN_KEYS plus the generic pair.
_TELEGRAM_CREDENTIAL_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_STOCK_BOT_TOKEN",
    "TELEGRAM_STOCK_CHAT_ID",
    "TELEGRAM_FUTURES_BOT_TOKEN",
    "TELEGRAM_FUTURES_CHAT_ID",
    "TELEGRAM_BRIEFING_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHAT_ID",
)


def test_telegram_credential_env_is_blank_during_pytest():
    """No TELEGRAM_* credential env var carries a real value under pytest."""
    for key in _TELEGRAM_CREDENTIAL_KEYS:
        assert not os.environ.get(key), (
            f"{key} is set during pytest; real Telegram messages can leak. "
            "conftest must scrub Telegram credentials for the session."
        )


def test_resolve_domain_credentials_returns_empty_for_all_domains():
    """The credential resolver used by orchestrator._notify yields nothing."""
    for domain in ("stock", "futures", "briefing", None, "unknown"):
        assert resolve_domain_credentials(domain) == ("", ""), (
            f"domain={domain!r} resolved to non-empty Telegram credentials; "
            "orchestrator._notify would send during pytest."
        )


