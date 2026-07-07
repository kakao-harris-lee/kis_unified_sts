"""Inbound telegram_bot service entrypoint (long-polling, Telegram interactive alerts).

Design: docs/plans/2026-07-07-telegram-interactive-alerts-design.md.

Runs a single ``python-telegram-bot`` :class:`telegram.ext.Application` in
long-polling mode (no public URL / webhook / Caddy route needed — the design
doc explicitly rejected webhooks for this feature). This is the ONLY inbound
Telegram surface in the repo; existing outbound notifications
(``shared/notification/telegram.py``) are unrelated and unaffected.

Token/channel choice: the bot listens on the **stock** domain token
(``TELEGRAM_STOCK_BOT_TOKEN`` via
:func:`shared.notification.telegram.resolve_domain_credentials`). Rationale —
the design doc's ``allowed_chat_ids`` default
(``["${TELEGRAM_STOCK_CHAT_ID}", "${TELEGRAM_FUTURES_CHAT_ID}"]``,
``config/telegram_bot.yaml``) already whitelists both the stock and futures
operator chat_ids, and this bot's ``/positions``+close flow is explicitly
asset-symmetric (it iterates both ``"stock"`` and ``"futures"`` — see
``handlers.py::positions_command``). Telegram bots are single-token processes,
so ONE of the domain tokens must own the bot identity that receives
`/positions`, approve/reject, and close button taps; the stock token was
already the de-facto "operator" channel before this feature (legacy
``get_telegram_notifier()``/``TELEGRAM_BOT_TOKEN`` aliases to
``TELEGRAM_STOCK_*`` in ``.env``), so reusing it here needs no new bot to be
registered with Telegram — the operator only has to invite/whitelist the
existing stock bot in the futures chat too (or vice versa) for full coverage.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.config.runtime_defaults import redis_url_from_env
from shared.notification.telegram import resolve_domain_credentials

logger = logging.getLogger(__name__)

# Domain whose bot token this service listens on (see module docstring).
_TOKEN_DOMAIN = "stock"


def build_application(*, token: str, redis: Any, config: Any) -> Any:
    """Build a fully-wired :class:`telegram.ext.Application` (no polling started).

    Registers every handler from ``services.telegram_bot.handlers`` and injects
    *redis* + *config* via ``application.bot_data`` (the standard
    python-telegram-bot dependency-injection idiom), so handlers stay plain
    functions that read ``context.bot_data["redis"]`` /
    ``context.bot_data["config"]`` instead of closing over module globals —
    this is what lets tests call handlers directly with a fake ``bot_data``
    dict and no real ``Application``.

    Args:
        token: Telegram bot token.
        redis: Async Redis client (``redis.asyncio.Redis`` in production,
            ``fakeredis.aioredis.FakeRedis`` in tests).
        config: Loaded :class:`services.telegram_bot.config.TelegramBotConfig`.

    Returns:
        A built (but not yet initialized/started) ``Application``.
    """
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler

    from services.telegram_bot import handlers

    application = Application.builder().token(token).build()
    application.bot_data["redis"] = redis
    application.bot_data["config"] = config

    application.add_handler(
        CallbackQueryHandler(handlers.approve_callback, pattern=r"^approve:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.reject_callback, pattern=r"^reject:")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.close_callback, pattern=r"^close:")
    )
    application.add_handler(CommandHandler("positions", handlers.positions_command))
    application.add_handler(CommandHandler("pending", handlers.pending_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("start", handlers.start_command))
    return application


async def _run_polling(application: Any, *, poll_interval: float) -> None:
    """Run *application* in long-polling mode until a stop signal.

    Uses the manual (non-``run_polling``) lifecycle
    (initialize/start/updater.start_polling/.../updater.stop/stop/shutdown) so
    this coroutine composes with this repo's existing
    ``asyncio.run(_build_and_run())`` + explicit SIGTERM/SIGINT handler
    pattern (see e.g. ``services/risk_filter/main.py::_build_and_run``)
    instead of ``Application.run_polling()``'s own internal signal handling,
    which would conflict with it.
    """
    import signal as signal_mod

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    async with application:
        await application.start()
        await application.updater.start_polling(poll_interval=poll_interval)
        try:
            await stop_event.wait()
        finally:
            await application.updater.stop()
            await application.stop()


async def _build_and_run() -> int:
    """Production entrypoint.

    Inert (returns 0 immediately, no Redis/Application constructed) when
    ``telegram_bot.enabled`` is false (default) or the domain token/whitelist
    is unset — mirrors the off-by-default contract every other daemon in this
    repo follows (``_resolve_mode() == "off"`` inertness pattern).
    """
    from services.telegram_bot.config import TelegramBotConfig

    config = TelegramBotConfig.from_yaml()
    if not config.enabled:
        logger.info("telegram_bot.enabled=false — bot inert, exiting")
        return 0
    if not config.allowed_chat_ids:
        logger.warning("telegram_bot.allowed_chat_ids is empty — bot inert, exiting")
        return 0

    token, _chat_id = resolve_domain_credentials(_TOKEN_DOMAIN)
    if not token:
        logger.warning(
            "Telegram token missing for domain=%s — bot inert, exiting", _TOKEN_DOMAIN
        )
        return 0

    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(redis_url_from_env())
    application = build_application(token=token, redis=redis_client, config=config)

    try:
        await _run_polling(application, poll_interval=config.poll_interval_seconds)
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
