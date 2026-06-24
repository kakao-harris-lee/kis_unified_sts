#!/usr/bin/env python3
"""Post-close LLM scorecard scorer + daily Telegram (cron).

Wires the module-level scorecard API: score the day, query the ledger for the
day's rows + the rolling window, format the daily message, and (if configured)
send it to Telegram. Run after the 15:30 KST close + settlement.
"""
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
    date_str = target_date.isoformat()
    logger.info("Scoring date: %s", date_str)

    from shared.llm_scorecard.aggregator import rolling_metrics
    from shared.llm_scorecard.config import ScorecardConfig
    from shared.llm_scorecard.outcome_data import OutcomeData
    from shared.llm_scorecard.reporter import format_daily
    from shared.llm_scorecard.scorer import score_day
    from shared.storage.config import StorageConfig
    from shared.storage.market_data_store import create_market_data_store
    from shared.storage.runtime_ledger import SQLiteRuntimeLedger

    cfg = ScorecardConfig.from_yaml()

    storage_cfg = StorageConfig.load_or_default()
    ledger = SQLiteRuntimeLedger(storage_cfg.runtime_storage.sqlite)

    store = create_market_data_store(asset_class="futures")
    outcome = OutcomeData(store, datetime.now())

    n = score_day(date_str, cfg, ledger, outcome)
    logger.info("Scored %d facets for %s", n, date_str)

    # Build the daily message from the persisted rows (pure formatting seam).
    day_scores = ledger.query_scores(start=date_str, end=date_str)
    window = cfg.rolling_windows[-1] if cfg.rolling_windows else 60
    rolling = rolling_metrics(ledger.query_scores(facet="direction"), window)
    msg = format_daily(date_str, day_scores, rolling)
    print(msg)

    if cfg.report_daily and day_scores:
        try:
            from shared.notification import notifier_for_domain

            notifier = notifier_for_domain(
                cfg.telegram_domain,
                notification_start="00:00",
                notification_end="23:59",
            )
            if notifier is not None:
                await notifier.send_message(msg, is_critical=False)
                logger.info("Sent scorecard to Telegram (%s)", cfg.telegram_domain)
        except Exception as exc:
            logger.warning("Telegram send failed (non-fatal): %s", exc)


if __name__ == "__main__":
    asyncio.run(main())
