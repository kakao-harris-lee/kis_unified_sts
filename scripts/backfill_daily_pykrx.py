"""pykrx 일봉 백필 스크립트.

pykrx를 사용하여 최근 N 거래일의 일봉 데이터를 ClickHouse market.daily_candles에 적재.
SMA(200) 계산을 위해 최소 500 거래일(~2년) 필요.

Usage:
    python scripts/backfill_daily_pykrx.py --days 500
    python scripts/backfill_daily_pykrx.py --days 500 --symbols 005930,000660
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta

import clickhouse_connect
from pykrx import stock as pykrx_stock

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Tier all 30종목 (MEMORY.md 기반)
DEFAULT_SYMBOLS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "005380",  # 현대차
    "000270",  # 기아
    "068270",  # 셀트리온
    "035420",  # NAVER
    "105560",  # KB금융
    "055550",  # 신한지주
    "006400",  # 삼성SDI
    "003670",  # 포스코퓨처엠
    "012330",  # 현대모비스
    "034730",  # SK
    "051910",  # LG화학
    "028260",  # 삼성물산
    "066570",  # LG전자
    "032830",  # 삼성생명
    "096770",  # SK이노베이션
    "003550",  # LG
    "015760",  # 한국전력
    "034020",  # 두산에너빌리티
    "009150",  # 삼성전기
    "000810",  # 삼성화재
    "086790",  # 하나금융지주
    "010130",  # 고려아연
    "033780",  # KT&G
    "003490",  # 대한항공
    "011200",  # HMM
    "010950",  # S-Oil
]


def get_clickhouse_client():
    """ClickHouse 클라이언트 생성."""
    import os

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def backfill_symbol(
    client,
    symbol: str,
    from_date: str,
    to_date: str,
) -> int:
    """단일 종목의 일봉 데이터를 pykrx에서 가져와 ClickHouse에 적재.

    Returns:
        적재된 행 수
    """
    try:
        df = pykrx_stock.get_market_ohlcv_by_date(
            fromdate=from_date,
            todate=to_date,
            ticker=symbol,
        )
    except Exception as e:
        logger.warning(f"  {symbol}: pykrx error — {e}")
        return 0

    if df.empty:
        logger.info(f"  {symbol}: no data from pykrx")
        return 0

    # pykrx returns: index=날짜, columns=시가,고가,저가,종가,거래량,등락률
    df = df.reset_index()
    df.columns = ["date", "open", "high", "low", "close", "volume", "change_rate"]

    # Add value column (거래대금 not provided by pykrx, estimate from close*volume)
    df["value"] = (df["close"] * df["volume"]).astype(int)

    # Filter zero-volume rows (holidays/errors)
    df = df[df["volume"] > 0].copy()

    if df.empty:
        logger.info(f"  {symbol}: all rows zero volume")
        return 0

    # Prepare batch insert
    rows = []
    for _, row in df.iterrows():
        rows.append([
            symbol,
            row["date"].date() if hasattr(row["date"], "date") else row["date"],
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            int(row["volume"]),
            int(row["value"]),
            float(row["change_rate"]),
        ])

    client.insert(
        "market.daily_candles",
        rows,
        column_names=["code", "date", "open", "high", "low", "close", "volume", "value", "change_rate"],
    )

    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="pykrx 일봉 백필 to ClickHouse")
    parser.add_argument("--days", type=int, default=500, help="백필 거래일 수 (default: 500)")
    parser.add_argument("--symbols", type=str, default=None, help="종목 코드 (콤마 구분, default: tier all 30)")
    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    days = args.days

    # 캘린더 일 기준으로 넉넉히 잡기 (거래일 500일 ≈ 캘린더 700일)
    to_date = datetime.now().strftime("%Y%m%d")
    from_date = (datetime.now() - timedelta(days=int(days * 1.5))).strftime("%Y%m%d")

    logger.info(f"Backfilling {len(symbols)} symbols, {from_date} ~ {to_date} (~{days} trading days)")

    client = get_clickhouse_client()

    total_rows = 0
    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] {symbol}")
        count = backfill_symbol(client, symbol, from_date, to_date)
        total_rows += count
        logger.info(f"  {symbol}: {count} rows inserted")

        # Rate limit for pykrx
        if i < len(symbols):
            time.sleep(1.0)

    logger.info(f"Done! Total: {total_rows} rows across {len(symbols)} symbols")


if __name__ == "__main__":
    main()
