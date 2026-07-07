"""TelegramBotConfig — loader for ``config/telegram_bot.yaml``'s ``telegram_bot:`` section.

Design: docs/plans/2026-07-07-telegram-interactive-alerts-design.md.

Only the config class lives here in this change — the ``Application``
long-polling wiring (``services/telegram_bot/main.py`` / ``handlers.py``) is
built by a separate change.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator

from shared.config.base import ServiceConfigBase

# Telegram's inline-keyboard callback_data byte limit lives in
# shared/notification/formatting.py (CALLBACK_DATA_MAX_BYTES) — that module
# builds every callback_data value this bot's handlers will parse, so it is
# the single source of truth. Not duplicated here.


class TelegramBotConfig(ServiceConfigBase):
    """Long-polling bot settings, loaded from ``config/telegram_bot.yaml``.

    Section: ``telegram_bot:``. Defaults to fully inert (``enabled=False``)
    per the design doc's rollout plan.
    """

    _default_config_file: ClassVar[str] = "telegram_bot.yaml"
    _default_section: ClassVar[str] = "telegram_bot"
    _env_prefix: ClassVar[str] = "TELEGRAM_BOT_"

    enabled: bool = Field(
        default=False,
        description="Master switch for the long-polling Application.",
    )
    allowed_chat_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Whitelisted chat_ids. Inbound commands/callbacks from any other "
            "chat_id are ignored. YAML entries are typically "
            "'${TELEGRAM_STOCK_CHAT_ID}' / '${TELEGRAM_FUTURES_CHAT_ID}' "
            "env-var references."
        ),
    )
    poll_interval_seconds: int = Field(
        default=2,
        gt=0,
        description="Long-polling interval passed to python-telegram-bot.",
    )

    @field_validator("allowed_chat_ids", mode="after")
    @classmethod
    def _drop_unresolved_chat_ids(cls, value: list[str]) -> list[str]:
        """Drop blank entries left by an unresolved ``${VAR}`` env reference.

        ``ConfigLoader`` resolves ``${VAR:default}`` per-list-item; an unset
        env var with no explicit default resolves to ``""``. Keeping an empty
        string in the whitelist would be harmless (chat_ids are never empty)
        but is filtered here so the list only ever contains real values.
        """
        return [chat_id for chat_id in value if chat_id]
