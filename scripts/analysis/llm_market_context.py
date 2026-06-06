"""Standalone LLM market-context publisher (M5b cron, shadow-first, default-off).

Extracts the orchestrator's 60-min LLMContextPublisher loop into a single-shot
cron. Each invocation runs ONE market analysis and publishes
``trading:stock:market_context`` (to the ``:shadow`` namespace in shadow mode).
Market-hours gating is the crontab schedule's job, not this script.

Modes (env ``STOCK_LLM_CONTEXT``):
  off (default) — inert: no OpenAI/Redis, exit 0.
  shadow        — publish to trading:stock:market_context:shadow (fail-safe
                  TRADING_STATE_KEY_SUFFIX). Never clobbers the orchestrator's
                  live key — for side-by-side validation before the M5d cutover.
  live (M5d)    — publish to the live key (orchestrator publisher gated off).

Recommended crontab (KST, CRON_TZ=Asia/Seoul; operator-managed):
  30 8  * * 1-5  STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
  0 9-15 * * 1-5 STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    """Return the cron mode from STOCK_LLM_CONTEXT (default 'off')."""
    return os.getenv("STOCK_LLM_CONTEXT", "off").strip().lower()


def _ensure_shadow_isolation(mode: str) -> None:
    """Fail-safe: in shadow, force TRADING_STATE_KEY_SUFFIX if the operator
    forgot it, so the publish can never clobber the orchestrator's live key."""
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"


async def run_once(mode: str) -> int:
    """Run a single market analysis and publish the context (or inert when off)."""
    if mode not in ("shadow", "live"):
        logger.info("STOCK_LLM_CONTEXT=%s (off) — inert, exiting", mode)
        return 0

    _ensure_shadow_isolation(mode)

    from services.trading.llm_context_publisher import LLMContextPublisher

    publisher = LLMContextPublisher("stock")
    context = await publisher.run_analysis()
    if context is not None:
        publisher.publish_to_redis(context)
        logger.info(
            "llm market context published mode=%s regime=%s confidence=%.2f",
            mode,
            context.regime,
            context.confidence,
        )
    else:
        logger.warning("llm analysis returned None; skipping publish (mode=%s)", mode)
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(run_once(_resolve_mode()))


if __name__ == "__main__":
    import sys

    sys.exit(main())
