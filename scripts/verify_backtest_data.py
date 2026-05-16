#!/usr/bin/env python3
"""
Verify ClickHouse has 6+ months of minute-bar data for backtest validation.

Usage:
    python scripts/verify_backtest_data.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import clickhouse_connect
from dotenv import load_dotenv

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load environment
load_dotenv(REPO_ROOT / ".env")

from shared.collector.historical.stock_universe import STOCK_UNIVERSE

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]

MIN_MONTHS = 6
MIN_SYMBOLS = 10


def get_clickhouse_client():
    """Create ClickHouse client."""
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )


def check_data_availability(client, symbols: list[str], min_months: int = 6) -> dict:
    """Check data availability for symbols in ClickHouse."""
    database = os.getenv("CLICKHOUSE_STOCK_DATABASE", "market")
    table = os.getenv("CLICKHOUSE_STOCK_MINUTE_TABLE", "minute_candles")

    # Calculate minimum date (6 months ago)
    min_date = datetime.now() - timedelta(days=min_months * 30)

    results = {
        "total_symbols": len(symbols),
        "symbols_with_data": [],
        "symbols_missing": [],
        "symbols_insufficient": [],
        "details": {},
    }

    for code in symbols:
        query = f"""
            SELECT
                code,
                min(datetime) as first_date,
                max(datetime) as last_date,
                count() as row_count,
                dateDiff('day', min(datetime), max(datetime)) as days_span
            FROM {database}.{table}
            WHERE code = {{code:String}}
            GROUP BY code
        """

        try:
            result = client.query(query, parameters={"code": code})

            if not result.result_rows:
                results["symbols_missing"].append(code)
                results["details"][code] = {
                    "status": "missing",
                    "message": "No data found",
                }
            else:
                row = result.result_rows[0]
                first_date = row[1]
                last_date = row[2]
                row_count = row[3]
                days_span = row[4]

                # Check if data is sufficient (6+ months). ClickHouse may
                # return timezone-aware datetimes depending on client settings.
                threshold = min_date
                if (
                    getattr(first_date, "tzinfo", None) is not None
                    and threshold.tzinfo is None
                ):
                    threshold = threshold.replace(tzinfo=first_date.tzinfo)
                elif (
                    getattr(first_date, "tzinfo", None) is None
                    and threshold.tzinfo is not None
                ):
                    threshold = threshold.replace(tzinfo=None)
                if first_date <= threshold:
                    results["symbols_with_data"].append(code)
                    results["details"][code] = {
                        "status": "ok",
                        "first_date": str(first_date),
                        "last_date": str(last_date),
                        "row_count": row_count,
                        "days_span": days_span,
                        "months": days_span / 30.0,
                    }
                else:
                    results["symbols_insufficient"].append(code)
                    results["details"][code] = {
                        "status": "insufficient",
                        "first_date": str(first_date),
                        "last_date": str(last_date),
                        "row_count": row_count,
                        "days_span": days_span,
                        "months": days_span / 30.0,
                        "message": f"Only {days_span / 30.0:.1f} months of data",
                    }
        except Exception as e:
            results["symbols_missing"].append(code)
            results["details"][code] = {"status": "error", "message": str(e)}

    return results


def print_report(results: dict, min_symbols: int = 10, min_months: int = 6):
    """Print verification report."""
    print("=" * 80)
    print("BACKTEST DATA VERIFICATION REPORT")
    print("=" * 80)
    print()

    print(f"Total symbols checked: {results['total_symbols']}")
    print(f"Symbols with 6+ months data: {len(results['symbols_with_data'])}")
    print(f"Symbols with insufficient data: {len(results['symbols_insufficient'])}")
    print(f"Symbols with no data: {len(results['symbols_missing'])}")
    print()

    # Print detailed status for symbols with sufficient data
    if results["symbols_with_data"]:
        print("✅ SYMBOLS WITH SUFFICIENT DATA (6+ months):")
        print("-" * 80)
        for code in results["symbols_with_data"][:20]:  # Show first 20
            details = results["details"][code]
            print(
                f"  {code}: {details['months']:.1f} months "
                f"({details['first_date']} to {details['last_date']}, "
                f"{details['row_count']:,} rows)"
            )
        if len(results["symbols_with_data"]) > 20:
            print(f"  ... and {len(results['symbols_with_data']) - 20} more")
        print()

    # Print symbols with insufficient data
    if results["symbols_insufficient"]:
        print("⚠️  SYMBOLS WITH INSUFFICIENT DATA (<6 months):")
        print("-" * 80)
        for code in results["symbols_insufficient"]:
            details = results["details"][code]
            print(
                f"  {code}: {details.get('months', 0):.1f} months "
                f"({details.get('message', 'Unknown')})"
            )
        print()

    # Print missing symbols
    if results["symbols_missing"]:
        print("❌ SYMBOLS WITH NO DATA:")
        print("-" * 80)
        for code in results["symbols_missing"][:20]:
            details = results["details"][code]
            print(f"  {code}: {details.get('message', 'No data')}")
        if len(results["symbols_missing"]) > 20:
            print(f"  ... and {len(results['symbols_missing']) - 20} more")
        print()

    # Final verdict
    print("=" * 80)
    print("VERIFICATION RESULT:")
    print("=" * 80)

    if len(results["symbols_with_data"]) >= min_symbols:
        print(
            f"✅ PASS: {len(results['symbols_with_data'])} symbols have 6+ months of data"
        )
        print(f"         (minimum required: {min_symbols} symbols)")
        print()
        print("You can proceed with backtest validation!")
        return True
    else:
        print(
            f"❌ FAIL: Only {len(results['symbols_with_data'])} symbols have 6+ months of data"
        )
        print(f"         (minimum required: {min_symbols} symbols)")
        print()
        print("ACTION REQUIRED:")
        print("  Run data collection to populate ClickHouse:")
        print("    python -m cli.main stock-backfill run --days 180")
        print()
        return False


def main():
    """Main entry point."""
    print("Connecting to ClickHouse...")
    client = get_clickhouse_client()

    print(f"Checking data for {len(DEFAULT_SYMBOLS)} symbols...")
    print(
        f"Minimum requirement: {MIN_MONTHS} months of data for at least {MIN_SYMBOLS} symbols"
    )
    print()

    results = check_data_availability(client, DEFAULT_SYMBOLS, MIN_MONTHS)
    success = print_report(results, MIN_SYMBOLS, MIN_MONTHS)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
