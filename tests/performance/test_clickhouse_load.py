"""Performance benchmarks for ClickHouse warmup query latency.

This module benchmarks the query latency for fetching historical market data
from ClickHouse, which is critical for pre-market warmup and backtest operations.

**Optimization Goals:**
- Measure query latency for various data range sizes (1 day, 30 days, 100 days)
- Document concurrent query performance under backtest load
- Establish baseline metrics for regression detection
- Validate p95 latency < 1000ms for 30-day queries (SLA requirement)

**Benchmark Scenarios:**
- Warmup queries: Single symbol, varying date ranges
- Concurrent queries: 5 workers (normal), 20 workers (stress test)
- Both daily and minute candle queries

**Performance Targets (per spec):**
- Query latency p95: < 1000ms for 30-day daily candles
- Concurrent query throughput: Support 20 concurrent backtests
- No connection pool exhaustion under concurrent load

**System Architecture:**
Pre-market warmup flow:
  Orchestrator start → ClickHouse warmup query → Load recent candles → Compute indicators
This latency directly impacts trading start time and indicator accuracy.
"""

from __future__ import annotations

import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Any

import pytest

# Try to import ClickHouse dependencies, skip all tests if not available
pytest.importorskip("clickhouse_driver", reason="clickhouse-driver not installed")

from shared.db.client import ClickHouseClient
from shared.db.config import ClickHouseConfig
from shared.db.models import DailyCandle, MinuteCandle

_LIVE_INFRA_ENV = "KIS_RUN_LIVE_INFRA_TESTS"


def _live_infra_enabled() -> bool:
    """Return whether live ClickHouse tests may touch infrastructure."""
    return os.getenv(_LIVE_INFRA_ENV, "").lower() in {"1", "true", "yes"}


def _is_clickhouse_available() -> bool:
    """Check if ClickHouse is available for testing."""
    if not _live_infra_enabled():
        return False

    try:
        config = ClickHouseConfig.from_env()
        client = ClickHouseClient(config=config)
        client.get_sync_client().execute("SELECT 1")
        return True
    except Exception:
        return False


# Skip all tests if ClickHouse is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _is_clickhouse_available(),
        reason="ClickHouse not available (start with: docker-compose up -d clickhouse)",
    ),
]


def _calculate_percentiles(latencies: list[float]) -> dict[str, float]:
    """Calculate p50, p95, p99 percentiles from latency list.

    Args:
        latencies: List of latency values in microseconds

    Returns:
        dict with p50, p95, p99 keys
    """
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "p50": sorted_latencies[int(n * 0.50)] if n > 0 else 0.0,
        "p95": sorted_latencies[int(n * 0.95)] if n > 1 else sorted_latencies[0] if n == 1 else 0.0,
        "p99": sorted_latencies[int(n * 0.99)] if n > 1 else sorted_latencies[0] if n == 1 else 0.0,
    }


def _format_latency_stats(latencies: list[float], label: str) -> str:
    """Format latency statistics for display.

    Args:
        latencies: List of latency values in microseconds
        label: Description label for the stats

    Returns:
        Formatted string with mean, p50, p95, p99
    """
    if not latencies:
        return f"{label}: No data"

    percentiles = _calculate_percentiles(latencies)
    mean = statistics.mean(latencies)

    return (
        f"{label}:\n"
        f"  Mean:   {mean:10.2f} μs ({mean/1000:7.2f} ms)\n"
        f"  p50:    {percentiles['p50']:10.2f} μs ({percentiles['p50']/1000:7.2f} ms)\n"
        f"  p95:    {percentiles['p95']:10.2f} μs ({percentiles['p95']/1000:7.2f} ms)\n"
        f"  p99:    {percentiles['p99']:10.2f} μs ({percentiles['p99']/1000:7.2f} ms)"
    )


def _setup_test_data(client: ClickHouseClient, code: str = "005930", num_days: int = 100) -> None:
    """Insert test data into ClickHouse for benchmarking.

    Args:
        client: ClickHouse client instance
        code: Stock code to insert
        num_days: Number of days of historical data
    """
    # Insert daily candles
    end_date = date.today()
    start_date = end_date - timedelta(days=num_days)

    daily_candles = []
    current_date = start_date
    base_price = 50000.0

    while current_date <= end_date:
        # Skip weekends (simple approximation)
        if current_date.weekday() < 5:
            daily_candles.append(
                DailyCandle(
                    code=code,
                    date=current_date,
                    open=base_price,
                    high=base_price * 1.02,
                    low=base_price * 0.98,
                    close=base_price * 1.01,
                    volume=1_000_000,
                    value=50_000_000_000,
                    change_rate=1.0,
                )
            )
        current_date += timedelta(days=1)

    if daily_candles:
        client.insert_daily_candles(daily_candles)

    # Insert minute candles for the last 7 days (for minute query tests)
    minute_start = datetime.now() - timedelta(days=7)
    minute_end = datetime.now()
    minute_candles = []

    current_time = minute_start
    while current_time <= minute_end:
        # Trading hours: 09:00 - 15:30 (approx)
        if 9 <= current_time.hour < 16:
            minute_candles.append(
                MinuteCandle(
                    code=code,
                    datetime=current_time,
                    open=base_price,
                    high=base_price * 1.001,
                    low=base_price * 0.999,
                    close=base_price * 1.0005,
                    volume=10_000,
                    value=500_000_000,
                )
            )
        current_time += timedelta(minutes=1)

    if minute_candles:
        client.insert_minute_candles(minute_candles)


def _benchmark_query(
    client: ClickHouseClient,
    query_func,
    iterations: int = 10,
    **query_kwargs,
) -> dict[str, Any]:
    """Benchmark a query function multiple times and return statistics.

    Args:
        client: ClickHouse client instance
        query_func: Function to benchmark (bound method of client)
        iterations: Number of iterations to run
        **query_kwargs: Keyword arguments to pass to query_func

    Returns:
        dict with latencies (list), mean, and percentiles
    """
    latencies = []

    for _ in range(iterations):
        start = time.perf_counter()
        result = query_func(**query_kwargs)
        end = time.perf_counter()

        latency_us = (end - start) * 1_000_000  # Convert to microseconds
        latencies.append(latency_us)

    return {
        "latencies": latencies,
        "mean": statistics.mean(latencies),
        "percentiles": _calculate_percentiles(latencies),
        "result_count": len(result) if result else 0,
    }


def _benchmark_concurrent_queries(
    client: ClickHouseClient,
    num_workers: int,
    queries_per_worker: int,
    code: str,
    days: int,
) -> dict[str, Any]:
    """Benchmark concurrent query execution.

    Args:
        client: ClickHouse client instance
        num_workers: Number of concurrent workers
        queries_per_worker: Number of queries each worker executes
        code: Stock code to query
        days: Number of days to query

    Returns:
        dict with total_queries, total_time, throughput, and latencies
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    def _worker_task(worker_id: int) -> list[float]:
        """Worker task: execute multiple queries and record latencies."""
        worker_latencies = []
        for _ in range(queries_per_worker):
            start = time.perf_counter()
            client.get_daily_candles(code=code, start_date=start_date, end_date=end_date)
            end = time.perf_counter()
            worker_latencies.append((end - start) * 1_000_000)
        return worker_latencies

    # Execute concurrent queries
    overall_start = time.perf_counter()
    all_latencies = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(_worker_task, i) for i in range(num_workers)]

        for future in as_completed(futures):
            worker_latencies = future.result()
            all_latencies.extend(worker_latencies)

    overall_end = time.perf_counter()
    total_time = overall_end - overall_start
    total_queries = num_workers * queries_per_worker
    throughput = total_queries / total_time

    return {
        "total_queries": total_queries,
        "total_time_seconds": total_time,
        "throughput_qps": throughput,
        "latencies": all_latencies,
        "percentiles": _calculate_percentiles(all_latencies),
    }


class TestClickHouseLoadBenchmarks:
    """Performance benchmarks for ClickHouse query operations."""

    @pytest.fixture(scope="class", autouse=True)
    def setup_client(self):
        """Setup ClickHouse client and test data once for all tests."""
        config = ClickHouseConfig.from_env()
        client = ClickHouseClient(config=config)

        # Initialize schema
        client.init_schema()

        # Setup test data
        _setup_test_data(client, code="005930", num_days=100)

        yield client

        # Cleanup singleton after all tests
        ClickHouseClient.reset_singleton()

    def test_warmup_query_1_day(self, setup_client):
        """Benchmark warmup query for 1 day of data (minimal range).

        Expected: Very fast (< 100ms p95) due to small data range.
        """
        client = setup_client
        end_date = date.today()
        start_date = end_date - timedelta(days=1)

        stats = _benchmark_query(
            client,
            client.get_daily_candles,
            iterations=20,
            code="005930",
            start_date=start_date,
            end_date=end_date,
        )

        print("\n" + "=" * 70)
        print("Warmup Query: 1 Day (Minimal Range)")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print("=" * 70)

        # Assertion: p95 should be reasonable for 1 day
        assert stats["percentiles"]["p95"] < 500_000, "1-day query p95 should be < 500ms"

    def test_warmup_query_7_days(self, setup_client):
        """Benchmark warmup query for 7 days of data (typical week).

        Expected: Fast (< 200ms p95) - common for weekly indicator calculation.
        """
        client = setup_client
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        stats = _benchmark_query(
            client,
            client.get_daily_candles,
            iterations=20,
            code="005930",
            start_date=start_date,
            end_date=end_date,
        )

        print("\n" + "=" * 70)
        print("Warmup Query: 7 Days (Weekly Range)")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print("=" * 70)

        # Assertion: p95 should be reasonable for 7 days
        assert stats["percentiles"]["p95"] < 1_000_000, "7-day query p95 should be < 1000ms"

    def test_warmup_query_30_days(self, setup_client):
        """Benchmark warmup query for 30 days of data (typical monthly range).

        **SLA Requirement:** p95 < 1000ms for 30-day queries.
        This is critical for pre-market warmup and monthly indicator calculations.
        """
        client = setup_client
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        stats = _benchmark_query(
            client,
            client.get_daily_candles,
            iterations=20,
            code="005930",
            start_date=start_date,
            end_date=end_date,
        )

        print("\n" + "=" * 70)
        print("Warmup Query: 30 Days (Monthly Range) - SLA TARGET")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print(f"\n  SLA Target: p95 < 1000ms")
        print(f"  SLA Status: {'✓ PASS' if stats['percentiles']['p95'] < 1_000_000 else '✗ FAIL'}")
        print("=" * 70)

        # SLA assertion: p95 < 1000ms for 30-day queries
        assert stats["percentiles"]["p95"] < 1_000_000, "30-day query p95 must be < 1000ms (SLA)"

    def test_warmup_query_100_days(self, setup_client):
        """Benchmark warmup query for 100 days of data (extended backtest range).

        Expected: Moderate latency (< 2000ms p95) - used for comprehensive backtests.
        """
        client = setup_client
        end_date = date.today()
        start_date = end_date - timedelta(days=100)

        stats = _benchmark_query(
            client,
            client.get_daily_candles,
            iterations=20,
            code="005930",
            start_date=start_date,
            end_date=end_date,
        )

        print("\n" + "=" * 70)
        print("Warmup Query: 100 Days (Extended Backtest Range)")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print("=" * 70)

        # Assertion: p95 should be reasonable for 100 days
        assert stats["percentiles"]["p95"] < 2_000_000, "100-day query p95 should be < 2000ms"

    def test_minute_candle_query_1_day(self, setup_client):
        """Benchmark minute candle query for 1 day (intraday warmup).

        Expected: Fast (< 500ms p95) despite higher row count than daily candles.
        """
        client = setup_client
        end_datetime = datetime.now()
        start_datetime = end_datetime - timedelta(days=1)

        stats = _benchmark_query(
            client,
            client.get_minute_candles,
            iterations=20,
            code="005930",
            start=start_datetime,
            end=end_datetime,
        )

        print("\n" + "=" * 70)
        print("Minute Candle Query: 1 Day (Intraday Warmup)")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print("=" * 70)

        # Assertion: p95 should be reasonable for 1 day of minute data
        assert stats["percentiles"]["p95"] < 1_000_000, "1-day minute query p95 should be < 1000ms"

    def test_minute_candle_query_7_days(self, setup_client):
        """Benchmark minute candle query for 7 days (weekly intraday analysis).

        Expected: Moderate latency (< 2000ms p95) due to higher data volume.
        """
        client = setup_client
        end_datetime = datetime.now()
        start_datetime = end_datetime - timedelta(days=7)

        stats = _benchmark_query(
            client,
            client.get_minute_candles,
            iterations=20,
            code="005930",
            start=start_datetime,
            end=end_datetime,
        )

        print("\n" + "=" * 70)
        print("Minute Candle Query: 7 Days (Weekly Intraday Analysis)")
        print("=" * 70)
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print(f"  Result rows: {stats['result_count']}")
        print("=" * 70)

        # Assertion: p95 should be reasonable for 7 days of minute data
        assert stats["percentiles"]["p95"] < 2_000_000, "7-day minute query p95 should be < 2000ms"

    def test_concurrent_queries_5_workers(self, setup_client):
        """Benchmark concurrent queries with 5 workers (normal load).

        Simulates 5 concurrent backtests querying 30-day data.
        Expected: No significant latency degradation vs single query.
        """
        client = setup_client

        stats = _benchmark_concurrent_queries(
            client,
            num_workers=5,
            queries_per_worker=4,
            code="005930",
            days=30,
        )

        print("\n" + "=" * 70)
        print("Concurrent Queries: 5 Workers (Normal Load)")
        print("=" * 70)
        print(f"  Total queries:     {stats['total_queries']}")
        print(f"  Total time:        {stats['total_time_seconds']:.2f} seconds")
        print(f"  Throughput:        {stats['throughput_qps']:.2f} queries/second")
        print()
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print("=" * 70)

        # Assertion: p95 should not degrade significantly under concurrent load
        assert stats["percentiles"]["p95"] < 2_000_000, "5-worker concurrent p95 should be < 2000ms"

    def test_concurrent_queries_20_workers(self, setup_client):
        """Benchmark concurrent queries with 20 workers (stress test).

        Simulates 20 concurrent backtests querying 30-day data.
        This is the maximum expected concurrent backtest load per spec.
        Expected: Acceptable latency degradation, no connection pool exhaustion.
        """
        client = setup_client

        stats = _benchmark_concurrent_queries(
            client,
            num_workers=20,
            queries_per_worker=3,
            code="005930",
            days=30,
        )

        print("\n" + "=" * 70)
        print("Concurrent Queries: 20 Workers (Stress Test)")
        print("=" * 70)
        print(f"  Total queries:     {stats['total_queries']}")
        print(f"  Total time:        {stats['total_time_seconds']:.2f} seconds")
        print(f"  Throughput:        {stats['throughput_qps']:.2f} queries/second")
        print()
        print(_format_latency_stats(stats["latencies"], "Query Latency"))
        print("=" * 70)

        # Assertion: System should handle 20 concurrent workers without failure
        assert stats["total_queries"] == 60, "All queries should complete successfully"
        assert stats["percentiles"]["p95"] < 5_000_000, "20-worker concurrent p95 should be < 5000ms"

    def test_query_latency_percentiles(self, setup_client):
        """Comprehensive latency percentile analysis across multiple data ranges.

        Runs 100 queries for each range size to build robust percentile distribution.
        This provides baseline metrics for performance regression detection.
        """
        client = setup_client
        end_date = date.today()

        test_ranges = [
            ("1-day", 1),
            ("7-day", 7),
            ("30-day", 30),
            ("100-day", 100),
        ]

        print("\n" + "=" * 70)
        print("Query Latency Percentile Analysis (100 iterations per range)")
        print("=" * 70)

        all_results = {}
        for label, days in test_ranges:
            start_date = end_date - timedelta(days=days)

            stats = _benchmark_query(
                client,
                client.get_daily_candles,
                iterations=100,
                code="005930",
                start_date=start_date,
                end_date=end_date,
            )

            all_results[label] = stats

            print(f"\n{label} range ({days} days):")
            print(f"  Mean:   {stats['mean']/1000:8.2f} ms")
            print(f"  p50:    {stats['percentiles']['p50']/1000:8.2f} ms")
            print(f"  p95:    {stats['percentiles']['p95']/1000:8.2f} ms")
            print(f"  p99:    {stats['percentiles']['p99']/1000:8.2f} ms")
            print(f"  Rows:   {stats['result_count']}")

        print("=" * 70)

        # SLA assertion for 30-day range
        assert (
            all_results["30-day"]["percentiles"]["p95"] < 1_000_000
        ), "30-day p95 must be < 1000ms (SLA)"
