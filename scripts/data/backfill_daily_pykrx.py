"""
Backfill daily candles from pykrx into ClickHouse market.daily_candles.

Usage:
    python scripts/data/backfill_daily_pykrx.py
    python scripts/data/backfill_daily_pykrx.py --days 730
    python scripts/data/backfill_daily_pykrx.py --symbols 005930,000660
"""
import argparse
import logging
import sys
import time
from datetime import date, timedelta
from typing import List, Optional, Tuple

# Ensure project root is on the path when run directly
import os

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_daily_pykrx")


# =============================================================================
# Universe
# =============================================================================

UNIVERSE_50 = [
    # Top 10 by market cap
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "207940", "name": "삼성바이오로직스"},
    {"code": "005380", "name": "현대차"},
    {"code": "000270", "name": "기아"},
    {"code": "068270", "name": "셀트리온"},
    {"code": "035420", "name": "NAVER"},
    {"code": "005490", "name": "POSCO홀딩스"},
    {"code": "035720", "name": "카카오"},
    {"code": "051910", "name": "LG화학"},
    # Mid tier
    {"code": "006400", "name": "삼성SDI"},
    {"code": "028260", "name": "삼성물산"},
    {"code": "012330", "name": "현대모비스"},
    {"code": "055550", "name": "신한지주"},
    {"code": "105560", "name": "KB금융"},
    {"code": "034730", "name": "SK"},
    {"code": "003550", "name": "LG"},
    {"code": "066570", "name": "LG전자"},
    {"code": "032830", "name": "삼성생명"},
    {"code": "086790", "name": "하나금융지주"},
    # Theme / bottom tier
    {"code": "247540", "name": "에코프로비엠"},
    {"code": "086520", "name": "에코프로"},
    {"code": "373220", "name": "LG에너지솔루션"},
    {"code": "196170", "name": "알테오젠"},
    {"code": "003670", "name": "포스코퓨처엠"},
    {"code": "009150", "name": "삼성전기"},
    {"code": "000810", "name": "삼성화재"},
    {"code": "018260", "name": "삼성에스디에스"},
    {"code": "033780", "name": "KT&G"},
    {"code": "036570", "name": "엔씨소프트"},
    # Additional 20
    {"code": "003490", "name": "대한항공"},
    {"code": "034020", "name": "두산에너빌리티"},
    {"code": "010130", "name": "고려아연"},
    {"code": "015760", "name": "한국전력"},
    {"code": "017670", "name": "SK텔레콤"},
    {"code": "030200", "name": "KT"},
    {"code": "011200", "name": "HMM"},
    {"code": "024110", "name": "기업은행"},
    {"code": "316140", "name": "우리금융지주"},
    {"code": "259960", "name": "크래프톤"},
    {"code": "010950", "name": "S-Oil"},
    {"code": "009540", "name": "한국조선해양"},
    {"code": "036460", "name": "한국가스공사"},
    {"code": "011170", "name": "롯데케미칼"},
    {"code": "002790", "name": "아모레퍼시픽그룹"},
    {"code": "138040", "name": "메리츠금융지주"},
    {"code": "128940", "name": "한미약품"},
    {"code": "005830", "name": "DB손해보험"},
    {"code": "326030", "name": "SK바이오팜"},
    {"code": "352820", "name": "하이브"},
]


# =============================================================================
# Core backfill function
# =============================================================================

def backfill_daily(days: int = 365, symbols: Optional[List[str]] = None) -> int:
    """
    Backfill daily OHLCV candles from pykrx into ClickHouse market.daily_candles.

    Args:
        days: Number of calendar days to look back (default 365).
        symbols: Optional list of stock codes to restrict backfill to.
                 If None, all UNIVERSE_50 codes are used.

    Returns:
        Total number of rows inserted.
    """
    from pykrx import stock as pykrx_stock  # lazy import — optional dep
    from shared.collector.historical.daily_stock import (
        ensure_daily_candles_table,
        insert_daily_candles_batch,
    )
    from shared.collector.historical.stock import get_stock_db_client

    # Resolve symbol list
    if symbols:
        target = [s for s in UNIVERSE_50 if s["code"] in symbols]
        # Also include any raw codes not in UNIVERSE_50
        known_codes = {s["code"] for s in UNIVERSE_50}
        extra = [{"code": c, "name": c} for c in symbols if c not in known_codes]
        target = target + extra
    else:
        target = UNIVERSE_50

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    logger.info(
        "Backfilling daily candles | range=%s ~ %s | symbols=%d",
        start_str,
        end_str,
        len(target),
    )

    # Ensure table exists before any inserts
    ensure_daily_candles_table()
    db_client = get_stock_db_client()

    total_inserted = 0

    try:
        for i, sym in enumerate(target, start=1):
            code = sym["code"]
            name = sym["name"]

            try:
                df = pykrx_stock.get_market_ohlcv(start_str, end_str, code)
            except Exception as exc:
                logger.warning("[%d/%d] %s (%s): fetch error — %s", i, len(target), name, code, exc)
                time.sleep(0.5)
                continue

            if df is None or df.empty:
                logger.warning("[%d/%d] %s (%s): no data returned", i, len(target), name, code)
                time.sleep(0.5)
                continue

            rows: List[Tuple] = []
            for date_val, row in df.iterrows():
                try:
                    # pykrx columns: 시가, 고가, 저가, 종가, 거래량, 거래대금, 등락률
                    open_p = float(row.get("시가", 0) or 0)
                    high_p = float(row.get("고가", 0) or 0)
                    low_p = float(row.get("저가", 0) or 0)
                    close_p = float(row.get("종가", 0) or 0)
                    volume = int(row.get("거래량", 0) or 0)
                    value = int(row.get("거래대금", 0) or 0)
                    change_rate = float(row.get("등락률", 0) or 0)

                    # Skip rows with no meaningful data
                    if high_p <= 0:
                        continue

                    # date_val is a pandas Timestamp; convert to Python date
                    if hasattr(date_val, "date"):
                        d = date_val.date()
                    else:
                        d = date_val

                    rows.append((code, d, open_p, high_p, low_p, close_p, volume, value, change_rate))

                except Exception as row_exc:
                    logger.debug("Row parse error for %s on %s: %s", code, date_val, row_exc)
                    continue

            if not rows:
                logger.warning("[%d/%d] %s (%s): parsed 0 valid rows", i, len(target), name, code)
                time.sleep(0.5)
                continue

            try:
                inserted = insert_daily_candles_batch(db_client, rows)
                total_inserted += inserted
                logger.info(
                    "[%d/%d] %s (%s): inserted %d rows",
                    i,
                    len(target),
                    name,
                    code,
                    inserted,
                )
            except Exception as db_exc:
                logger.error("[%d/%d] %s (%s): DB insert failed — %s", i, len(target), name, code, db_exc)

            # Rate-limit pykrx requests
            time.sleep(0.5)

    finally:
        db_client.close()

    logger.info("Backfill complete. Total rows inserted: %d", total_inserted)
    return total_inserted


# =============================================================================
# CLI
# =============================================================================

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill daily OHLCV candles from pykrx into ClickHouse market.daily_candles.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of calendar days to look back (default: 365).",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated stock codes to backfill (e.g. 005930,000660). "
             "If omitted, all UNIVERSE_50 stocks are used.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    symbol_list: Optional[List[str]] = None
    if args.symbols:
        symbol_list = [s.strip() for s in args.symbols.split(",") if s.strip()]

    total = backfill_daily(days=args.days, symbols=symbol_list)
    sys.exit(0 if total >= 0 else 1)
