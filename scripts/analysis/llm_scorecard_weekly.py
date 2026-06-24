#!/usr/bin/env python3
"""Weekly LLM scorecard digest + Telegram (cron — Friday post-close).

Computes per-facet rolling metrics over the largest configured window and
sends a digest to the BRIEFING Telegram channel. Run after the weekly close.

Usage (cron / module form):
    python -m scripts.analysis.llm_scorecard_weekly
    python scripts/analysis/llm_scorecard_weekly.py  [--window N]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def build_by_facet(cfg, ledger) -> tuple[int, dict[str, dict]]:
    """Return (window, by_facet) for the largest configured rolling window.

    For each enabled facet, queries all score rows then computes rolling_metrics
    over ``window`` (the last N rows). Pure ledger reads — no I/O side effects.
    """
    from shared.llm_scorecard.aggregator import rolling_metrics
    from shared.llm_scorecard.facets.base import enabled_facets

    window = cfg.rolling_windows[-1] if cfg.rolling_windows else 60
    by_facet: dict[str, dict] = {}
    for facet in enabled_facets(cfg):
        rows = ledger.query_scores(facet=facet.name)
        by_facet[facet.name] = rolling_metrics(rows, window)
        logger.info(
            "Weekly metrics [%s] window=%d n=%d n_scored=%d hit_rate=%s",
            facet.name,
            window,
            by_facet[facet.name]["n"],
            by_facet[facet.name]["n_scored"],
            by_facet[facet.name].get("hit_rate"),
        )
    return window, by_facet


async def main() -> None:
    parser = argparse.ArgumentParser(description="LLM scorecard weekly digest")
    parser.add_argument(
        "--window",
        type=int,
        default=None,
        help="Rolling window override (default: largest configured window)",
    )
    args = parser.parse_args()

    import shared.llm_scorecard.facets  # noqa: F401 — populates FACET_REGISTRY
    from shared.llm_scorecard.config import ScorecardConfig
    from shared.llm_scorecard.reporter import format_weekly
    from shared.storage.config import StorageConfig
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    cfg = ScorecardConfig.from_yaml()

    if not cfg.report_weekly:
        logger.info("report_weekly=false in config; skipping weekly digest")
        return

    storage_cfg = StorageConfig.load_or_default()
    ledger = SQLiteRuntimeLedger(storage_cfg.runtime_storage.sqlite)

    window, by_facet = build_by_facet(cfg, ledger)
    if args.window is not None:
        window = args.window

    if not by_facet:
        logger.info("No enabled facets with score data; skipping weekly digest")
        return

    msg = format_weekly(window, by_facet)
    print(msg)

    try:
        from shared.notification import notifier_for_domain

        notifier = notifier_for_domain(
            cfg.telegram_domain,
            notification_start="00:00",
            notification_end="23:59",
        )
        if notifier is not None:
            await notifier.send_message(msg, is_critical=False)
            logger.info("Sent weekly scorecard to Telegram (%s)", cfg.telegram_domain)
        else:
            logger.warning("Telegram notifier not configured; printed to stdout only")
    except Exception as exc:
        logger.warning("Telegram send failed (non-fatal): %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
