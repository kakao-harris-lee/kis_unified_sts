"""Telegram 도메인 라우팅 regression 테스트.

선물/주식/브리핑 채널이 엄격히 분리되는지, legacy TELEGRAM_BOT_TOKEN으로
silent fallback 하지 않는지 검증한다.
"""
from __future__ import annotations

import pytest

from shared.notification.telegram import (
    notifier_for_domain,
    resolve_domain_credentials,
)

DOMAIN_ENV_KEYS = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_STOCK_BOT_TOKEN",
    "TELEGRAM_STOCK_CHAT_ID",
    "TELEGRAM_FUTURES_BOT_TOKEN",
    "TELEGRAM_FUTURES_CHAT_ID",
    "TELEGRAM_BRIEFING_BOT_TOKEN",
    "TELEGRAM_BRIEFING_CHAT_ID",
]


@pytest.fixture(autouse=True)
def _clean_telegram_env(monkeypatch):
    """각 테스트마다 TELEGRAM_* 환경변수를 초기화."""
    for key in DOMAIN_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


class TestResolveDomainCredentials:
    def test_stock_domain_reads_stock_keys(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_STOCK_BOT_TOKEN", "STK_TOK")
        monkeypatch.setenv("TELEGRAM_STOCK_CHAT_ID", "STK_CHAT")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        assert resolve_domain_credentials("stock") == ("STK_TOK", "STK_CHAT")

    def test_futures_domain_reads_futures_keys(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "FUT_TOK")
        monkeypatch.setenv("TELEGRAM_FUTURES_CHAT_ID", "FUT_CHAT")
        assert resolve_domain_credentials("futures") == ("FUT_TOK", "FUT_CHAT")

    def test_briefing_domain_reads_briefing_keys(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BRIEFING_BOT_TOKEN", "BRF_TOK")
        monkeypatch.setenv("TELEGRAM_BRIEFING_CHAT_ID", "BRF_CHAT")
        assert resolve_domain_credentials("briefing") == ("BRF_TOK", "BRF_CHAT")

    def test_futures_missing_does_not_fallback_to_legacy(self, monkeypatch):
        """선물 전용 env가 없을 때 legacy TELEGRAM_BOT_TOKEN으로 떨어지면 안 된다.
        이것이 'futures → stock 채널' 누수의 원인이었다.
        """
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        # TELEGRAM_FUTURES_* 의도적으로 unset
        assert resolve_domain_credentials("futures") == ("", "")

    def test_briefing_missing_does_not_fallback_to_legacy(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        assert resolve_domain_credentials("briefing") == ("", "")

    def test_none_domain_uses_generic(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        assert resolve_domain_credentials(None) == ("LEGACY_TOK", "LEGACY_CHAT")

    def test_unknown_domain_uses_generic(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        assert resolve_domain_credentials("unknown") == ("LEGACY_TOK", "LEGACY_CHAT")


class TestNotifierForDomain:
    def test_returns_notifier_when_futures_configured(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "FUT_TOK")
        monkeypatch.setenv("TELEGRAM_FUTURES_CHAT_ID", "FUT_CHAT")
        notifier = notifier_for_domain("futures")
        assert notifier is not None
        assert notifier.token == "FUT_TOK"
        assert notifier.chat_id == "FUT_CHAT"

    def test_returns_none_when_futures_missing_even_if_legacy_set(self, monkeypatch):
        """legacy env가 있어도 futures 전용 env가 없으면 None 반환."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        assert notifier_for_domain("futures") is None

    def test_returns_none_when_briefing_missing_even_if_legacy_set(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        assert notifier_for_domain("briefing") is None

    def test_domains_are_isolated(self, monkeypatch):
        """각 도메인은 서로 다른 채널을 사용해야 한다."""
        monkeypatch.setenv("TELEGRAM_STOCK_BOT_TOKEN", "STK_TOK")
        monkeypatch.setenv("TELEGRAM_STOCK_CHAT_ID", "STK_CHAT")
        monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "FUT_TOK")
        monkeypatch.setenv("TELEGRAM_FUTURES_CHAT_ID", "FUT_CHAT")
        monkeypatch.setenv("TELEGRAM_BRIEFING_BOT_TOKEN", "BRF_TOK")
        monkeypatch.setenv("TELEGRAM_BRIEFING_CHAT_ID", "BRF_CHAT")

        stock = notifier_for_domain("stock")
        futures = notifier_for_domain("futures")
        briefing = notifier_for_domain("briefing")

        tokens = {stock.token, futures.token, briefing.token}  # type: ignore[union-attr]
        assert tokens == {"STK_TOK", "FUT_TOK", "BRF_TOK"}


class TestNoSilentLegacyFallback:
    """The .env in this repo aliases TELEGRAM_BOT_TOKEN=${TELEGRAM_STOCK_BOT_TOKEN}.

    A futures/briefing domain that resolves to legacy as a fallback would
    silently leak messages to the stock channel.  These regression tests
    pin the no-fallback behaviour of resolve_domain_credentials and
    notifier_for_domain.
    """

    def test_futures_with_only_legacy_set_returns_empty(self, monkeypatch):
        """If TELEGRAM_FUTURES_* is unset and only TELEGRAM_BOT_TOKEN is
        present, futures must NOT fall back to it.  Returning ('', '')
        is the right outcome — caller will refuse to create the notifier
        and log a clear "credentials missing" warning instead of leaking.
        """
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_STOCK_ALIASED_TOKEN")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_STOCK_ALIASED_CHAT")
        # TELEGRAM_FUTURES_* intentionally NOT set
        token, chat_id = resolve_domain_credentials("futures")
        assert token == ""
        assert chat_id == ""
        assert notifier_for_domain("futures") is None

    def test_briefing_with_only_legacy_set_returns_empty(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOKEN")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        token, chat_id = resolve_domain_credentials("briefing")
        assert token == ""
        assert chat_id == ""
        assert notifier_for_domain("briefing") is None

    def test_partial_futures_creds_still_no_fallback(self, monkeypatch):
        """Only TELEGRAM_FUTURES_BOT_TOKEN set (no chat_id) — partial
        config must NOT trigger legacy fallback for the missing chat_id.
        """
        monkeypatch.setenv("TELEGRAM_FUTURES_BOT_TOKEN", "FUT_TOK")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "LEGACY_TOK")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "LEGACY_CHAT")
        # TELEGRAM_FUTURES_CHAT_ID NOT set
        token, chat_id = resolve_domain_credentials("futures")
        assert token == "FUT_TOK"
        assert chat_id == ""  # NOT "LEGACY_CHAT"
        assert notifier_for_domain("futures") is None  # incomplete creds → None
