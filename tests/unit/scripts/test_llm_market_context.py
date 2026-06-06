"""M5b cron: mode routing, fail-safe shadow isolation, single-shot run+publish."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

import scripts.analysis.llm_market_context as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_LLM_CONTEXT", raising=False)
    assert m._resolve_mode() == "off"


def test_ensure_shadow_isolation_forces_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv (tracked) so teardown removes it even though _ensure writes os.environ
    # directly — mirrors the M5a env-leak fix.
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("shadow")
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"


def test_ensure_shadow_isolation_live_leaves_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_run_once_off_is_inert() -> None:
    rc = asyncio.run(m.run_once("off"))
    assert rc == 0  # off: no import, no OpenAI/Redis touch


def test_run_once_shadow_runs_and_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = MagicMock()
    inst.run_analysis = AsyncMock(
        return_value=MagicMock(regime="BULL_STRONG", confidence=0.8)
    )
    cls = MagicMock(return_value=inst)
    monkeypatch.setattr(
        "services.trading.llm_context_publisher.LLMContextPublisher", cls
    )
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")

    rc = asyncio.run(m.run_once("shadow"))

    assert rc == 0
    cls.assert_called_once_with("stock")
    inst.run_analysis.assert_awaited_once()
    inst.publish_to_redis.assert_called_once()
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"  # fail-safe isolation


def test_run_once_none_analysis_skips_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = MagicMock()
    inst.run_analysis = AsyncMock(return_value=None)  # OpenAI failure -> None
    cls = MagicMock(return_value=inst)
    monkeypatch.setattr(
        "services.trading.llm_context_publisher.LLMContextPublisher", cls
    )
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")

    rc = asyncio.run(m.run_once("shadow"))

    assert rc == 0  # graceful — prior context persists via Redis TTL
    inst.publish_to_redis.assert_not_called()
