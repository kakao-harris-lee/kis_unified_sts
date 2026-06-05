#!/usr/bin/env python3
"""
Verify Parquet has 6+ months of minute-bar data for backtest validation.

Usage:
    python scripts/verify_backtest_data.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load environment
load_dotenv(REPO_ROOT / ".env")

from shared.collector.historical.stock_universe import STOCK_UNIVERSE
from shared.storage.config import StorageConfig
from shared.storage.market_data_store import ParquetMarketDataStore

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]

MIN_MONTHS = 6
MIN_SYMBOLS = 10


def get_market_data_store() -> ParquetMarketDataStore:
    """Create Parquet market-data store."""
    storage_config = StorageConfig.load_or_default()
    return ParquetMarketDataStore(
        storage_config.market_data.parquet.root,
        asset_class="stock",
    )


def check_data_availability(
    store: ParquetMarketDataStore,
    symbols: list[str],
    min_months: int = 6,
) -> dict:
    """Check data availability for symbols in Parquet."""
    min_date = datetime.now() - timedelta(days=min_months * 30)

    results = {
        "total_symbols": len(symbols),
        "symbols_with_data": [],
        "symbols_missing": [],
        "symbols_insufficient": [],
        "details": {},
    }

    for code in symbols:
        try:
            df = store.get_minute_bars(code)
            if df.empty:
                results["symbols_missing"].append(code)
                results["details"][code] = {
                    "status": "missing",
                    "message": "No data found",
                }
            else:
                first_date = df["datetime"].min().to_pydatetime()
                last_date = df["datetime"].max().to_pydatetime()
                row_count = len(df)
                days_span = (last_date - first_date).days

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
        print("  Run data collection to populate Parquet:")
        print("    python -m cli.main stock-backfill run --days 180")
        print()
        return False


def main():
    """Main entry point."""
    print("Opening Parquet market-data store...")
    store = get_market_data_store()

    print(f"Checking data for {len(DEFAULT_SYMBOLS)} symbols...")
    print(
        f"Minimum requirement: {MIN_MONTHS} months of data for at least {MIN_SYMBOLS} symbols"
    )
    print()

    results = check_data_availability(store, DEFAULT_SYMBOLS, MIN_MONTHS)
    success = print_report(results, MIN_SYMBOLS, MIN_MONTHS)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
