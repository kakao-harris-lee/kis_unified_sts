#!/usr/bin/env python3
"""Post-close LLM scorecard scorer. Run after 15:30 KST close."""
import argparse
import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _yesterday_kst() -> date:
    return datetime.now().date() - timedelta(days=1)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: yesterday KST)")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else _yesterday_kst()
    logger.info("Scoring date: %s", target_date)

    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig.from_yaml()

    # Import direction facet to register it
    import shared.llm_scorecard.facets.direction  # noqa: F401

    # Build ledger
    from shared.storage.config import StorageConfig
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    storage_cfg = StorageConfig.load_or_default()
    ledger = SQLiteRuntimeLedger(storage_cfg.runtime_storage.sqlite)

    # Build outcome data
    from shared.llm_scorecard.outcome_data import OutcomeData
    from shared.storage.market_data_store import create_market_data_store

    store = create_market_data_store(asset_class="futures")
    outcome = OutcomeData(store, datetime.now())

    # Score
    from shared.llm_scorecard.scorer import DayScorer

    scorer = DayScorer(cfg, ledger, outcome)
    scores = scorer.score_day(target_date)
    logger.info("Scored %d facets for %s", len(scores), target_date)

    # Report
    from shared.llm_scorecard.aggregator import RollingAggregator
    from shared.llm_scorecard.reporter import DailyScorecardReporter

    agg = RollingAggregator(cfg, ledger)
    reporter = DailyScorecardReporter(cfg, agg, ledger)
    msg = reporter.format_daily(target_date)
    print(msg)

    # Send to Telegram if configured
    if cfg.report_daily:
        try:
            from shared.notification import notifier_for_domain

            notifier = notifier_for_domain(
                cfg.telegram_domain,
                notification_start="00:00",
                notification_end="23:59",
            )
            if notifier is not None:
                await notifier.send_message(msg)
                logger.info("Sent scorecard to Telegram (%s)", cfg.telegram_domain)
        except Exception as exc:
            logger.warning("Telegram send failed (non-fatal): %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
