"""Tests for services/telegram_bot/config.py — TelegramBotConfig loader.

Also covers shared/streaming/approval_gate.py::ApprovalGateConfig since both
sections live in the same config/telegram_bot.yaml file.
"""

from __future__ import annotations

import textwrap

from services.telegram_bot.config import TelegramBotConfig
from shared.streaming.approval_gate import ApprovalGateConfig


def test_telegram_bot_config_loads_default_yaml_inert():
    cfg = TelegramBotConfig.from_yaml()
    assert cfg.enabled is False
    assert cfg.poll_interval_seconds == 2


def test_approval_gate_config_loads_default_yaml_inert():
    cfg = ApprovalGateConfig.from_yaml()
    assert cfg.enabled is False
    assert cfg.gated_strategies == []
    assert cfg.gated_symbols == []
    assert cfg.pending_ttl_seconds == 86400


def test_telegram_bot_config_custom_yaml(tmp_path):
    custom = tmp_path / "telegram_bot.yaml"
    custom.write_text(textwrap.dedent("""
            telegram_bot:
              enabled: true
              allowed_chat_ids: ["111", "222"]
              poll_interval_seconds: 5
            """))
    cfg = TelegramBotConfig.from_yaml(str(custom))
    assert cfg.enabled is True
    assert cfg.allowed_chat_ids == ["111", "222"]
    assert cfg.poll_interval_seconds == 5


def test_telegram_bot_config_drops_unresolved_env_placeholders(tmp_path):
    custom = tmp_path / "telegram_bot.yaml"
    custom.write_text(textwrap.dedent("""
            telegram_bot:
              enabled: true
              allowed_chat_ids: ["111", ""]
            """))
    cfg = TelegramBotConfig.from_yaml(str(custom))
    assert cfg.allowed_chat_ids == ["111"]


def test_approval_gate_config_custom_yaml(tmp_path):
    custom = tmp_path / "telegram_bot.yaml"
    custom.write_text(textwrap.dedent("""
            approval_gate:
              enabled: true
              gated_strategies: ["setup_a_gap_reversion"]
              gated_symbols: ["005930"]
              pending_ttl_seconds: 3600
            """))
    cfg = ApprovalGateConfig.from_yaml(str(custom))
    assert cfg.enabled is True
    assert cfg.gated_strategies == ["setup_a_gap_reversion"]
    assert cfg.gated_symbols == ["005930"]
    assert cfg.pending_ttl_seconds == 3600
