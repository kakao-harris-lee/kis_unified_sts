#!/usr/bin/env python3
"""
LLM Pre-Market Briefing

Sends morning briefing with stock and futures recommendations.
Cron: 30 6 * * 1-5 (06:30 KST — analysis historically takes ~1h27m–1h47m,
so a 06:30 start finishes around 08:00–08:30 KST, comfortably pre-market.
"""

import asyncio
import logging
import os
import sys

# Add project root to path, then load env BEFORE importing shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from shared.llm.llm_analyzer import run_unified_analysis  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

ANALYSIS_TIMEOUT_SECONDS = 7200  # 2h — historical runs complete in 1h15m–1h47m


def is_market_open_today() -> bool:
    """Check if market is open today (simple weekday check)."""
    from datetime import datetime

    today = datetime.now()
    # Monday=0, Sunday=6
    return today.weekday() < 5


async def main():
    logger.info("Pre-Market Briefing Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    notifier = None
    try:
        from shared.notification import notifier_for_domain

        # Briefing is an explicitly-triggered report and must deliver in full
        # regardless of hour (it runs at 06:30 KST, before the 08:30 intraday
        # alert window).  Use a 24h window so body messages are not gated.
        # This does NOT affect intraday-alert notifiers.
        notifier = notifier_for_domain(
            "briefing",
            notification_start="00:00",
            notification_end="23:59",
        )
        if notifier is None:
            logger.warning(
                "Briefing Telegram channel not configured; running without notifications"
            )
    except ImportError:
        logger.warning("TelegramNotifier not available, running without notifications")

    try:
        stock_plans, futures_plan, _ = await asyncio.wait_for(
            run_unified_analysis(
                notifier=notifier, mode="all", send_telegram=notifier is not None
            ),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
        logger.info(f"Complete: {len(stock_plans)} stock recommendations")

        if futures_plan:
            logger.info(f"Futures: {futures_plan.direction}")

        # Best-effort scorecard prediction capture — never breaks the briefing
        try:
            from datetime import datetime
            from shared.llm_scorecard.config import ScorecardConfig
            import shared.llm_scorecard.facets.direction  # noqa: F401 — registers facet
            from shared.llm_scorecard.recorder import PredictionRecorder
            from shared.llm_scorecard.facets.base import CaptureContext
            from shared.storage.config import StorageConfig
            from shared.storage.runtime_ledger import SQLiteRuntimeLedger
            from shared.streaming.trading_state import TradingStatePublisher

            _cfg = ScorecardConfig.from_yaml()
            _storage = StorageConfig.load_or_default()
            _ledger = SQLiteRuntimeLedger(_storage.runtime_storage.sqlite)
            _now = datetime.now()
            _date_kst = _now.strftime("%Y-%m-%d")
            # Attempt to get market_context from Redis
            _mc = None
            try:
                _pub = TradingStatePublisher("futures")
                _mc_obj = _pub.get_market_context()
                if _mc_obj is not None:
                    _mc = _mc_obj.to_dict() if hasattr(_mc_obj, "to_dict") else _mc_obj
            except Exception:
                pass
            _ctx = CaptureContext(date_kst=_date_kst, now_kst=_now, market_context=_mc)
            _recorder = PredictionRecorder(_cfg, _ledger, _ctx)
            _preds = _recorder.capture_predictions()
            logger.info("Scorecard: captured %d predictions for %s", len(_preds), _date_kst)
        except Exception as _sc_exc:
            logger.warning("Scorecard prediction capture failed (non-fatal): %s", _sc_exc)

    except TimeoutError:
        logger.error(
            f"Pre-market analysis exceeded {ANALYSIS_TIMEOUT_SECONDS}s timeout — aborting"
        )
        if notifier is not None:
            try:
                await notifier.send_message(
                    f"⚠️ <b>장전 브리핑 타임아웃</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"분석이 {ANALYSIS_TIMEOUT_SECONDS // 60}분을 초과하여 중단되었습니다.\n"
                    f"외부 API (KIS / DART / KRX) 응답 지연 가능성. 로그 확인 필요.",
                    is_critical=True,
                )
            except Exception as send_err:  # noqa: BLE001
                logger.error(f"Failed to send timeout alert: {send_err}")
        raise
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
