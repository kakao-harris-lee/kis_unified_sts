"""Performance benchmarks for Redis position state CRUD operations.

This module benchmarks Redis throughput and latency for position state operations
that are critical to the trading orchestrator:

- Position writes (HSET): Adding/updating open positions
- Position reads (HGET/HGETALL): Retrieving position state
- Concurrent access: Multiple workers accessing Redis simultaneously

**Performance Goals:**
- Read ops/s: >= 1000 ops/second (single-threaded)
- Write ops/s: >= 1000 ops/second (single-threaded)
- Concurrent throughput: Graceful degradation under 10-50 workers
- Latency p99: < 10ms for individual CRUD operations

**Redis Position State Schema:**
- Key: trading:{asset}:positions (HASH)
- Field: position_id
- Value: JSON serialized Position data

**Benchmark Scenarios:**
1. Single-threaded write throughput (baseline)
2. Single-threaded read throughput (baseline)
3. Concurrent access with 10 workers (normal load)
4. Concurrent access with 50 workers (stress test)
5. Latency percentiles (p50, p95, p99)
"""

from __future__ import annotations

import concurrent.futures
import json
import statistics
import time
from dataclasses import asdict
from datetime import datetime
from typing import Any

import pytest
import redis

from shared.models.position import Position, PositionSide, PositionState
from shared.streaming.client import RedisClient


def _is_redis_available() -> bool:
    """Check if Redis is available for testing."""
    try:
        client = RedisClient.get_client()
        client.ping()
        return True
    except (redis.ConnectionError, redis.TimeoutError, OSError):
        return False


# Skip all tests if Redis is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not _is_redis_available(),
        reason="Redis not available (start with: docker-compose up -d redis)"
    ),
]


def _create_test_position(position_id: str, code: str = "005930") -> Position:
    """Create a test position for benchmarking."""
    return Position(
        id=position_id,
        code=code,
        name=f"Stock {code}",
        side=PositionSide.LONG,
        quantity=100,
        entry_price=50000.0,
        entry_time=datetime.now(),
        current_price=51000.0,
        highest_price=52000.0,
        lowest_price=49500.0,
        stop_price=48000.0,
        state=PositionState.BREAKEVEN,
        strategy="mean_reversion",
        fee_rate=0.003,
    )


def _serialize_position(position: Position) -> dict[str, Any]:
    """Serialize a position to JSON-compatible dict (matches trading_state.py)."""
    data = {
        "id": position.id,
        "code": position.code,
        "name": position.name,
        "side": position.side.value,
        "quantity": position.quantity,
        "entry_price": position.entry_price,
        "entry_time": position.entry_time.isoformat(),
        "current_price": position.current_price,
        "highest_price": position.highest_price,
        "lowest_price": position.lowest_price,
        "stop_price": position.stop_price,
        "state": position.state.value,
        "strategy": position.strategy,
        "fee_rate": position.fee_rate,
        "profit_rate": position.profit_rate,
        "profit_pct": position.profit_pct,
        "unrealized_pnl": position.unrealized_pnl,
    }
    return data


def _benchmark_write_throughput(redis_client, num_positions: int) -> float:
    """Benchmark single-threaded write throughput.

    Returns:
        Operations per second
    """
    key = "test:positions:write_throughput"
    positions = [_create_test_position(f"pos_{i}") for i in range(num_positions)]

    # Clear existing data
    redis_client.delete(key)

    # Benchmark writes
    start = time.perf_counter()
    for pos in positions:
        data = _serialize_position(pos)
        redis_client.hset(key, pos.id, json.dumps(data))
    end = time.perf_counter()

    # Cleanup
    redis_client.delete(key)

    elapsed = end - start
    ops_per_second = num_positions / elapsed
    return ops_per_second


def _benchmark_read_throughput(redis_client, num_positions: int) -> float:
    """Benchmark single-threaded read throughput.

    Returns:
        Operations per second
    """
    key = "test:positions:read_throughput"

    # Setup: Write positions first
    positions = [_create_test_position(f"pos_{i}") for i in range(num_positions)]
    mapping = {}
    for pos in positions:
        data = _serialize_position(pos)
        mapping[pos.id] = json.dumps(data)
    redis_client.hset(key, mapping=mapping)

    # Benchmark reads (individual HGET)
    start = time.perf_counter()
    for pos in positions:
        redis_client.hget(key, pos.id)
    end = time.perf_counter()

    # Cleanup
    redis_client.delete(key)

    elapsed = end - start
    ops_per_second = num_positions / elapsed
    return ops_per_second


def _benchmark_read_all_throughput(redis_client, num_positions: int) -> float:
    """Benchmark HGETALL (batch read) throughput.

    Returns:
        Operations per second (positions read / elapsed time)
    """
    key = "test:positions:read_all_throughput"

    # Setup: Write positions first
    positions = [_create_test_position(f"pos_{i}") for i in range(num_positions)]
    mapping = {}
    for pos in positions:
        data = _serialize_position(pos)
        mapping[pos.id] = json.dumps(data)
    redis_client.hset(key, mapping=mapping)

    # Benchmark HGETALL (single operation that retrieves all positions)
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        redis_client.hgetall(key)
    end = time.perf_counter()

    # Cleanup
    redis_client.delete(key)

    elapsed = end - start
    # Calculate ops/s as: (positions * iterations) / elapsed
    total_positions_read = num_positions * iterations
    ops_per_second = total_positions_read / elapsed
    return ops_per_second


def _worker_write_task(worker_id: int, num_ops: int, key_prefix: str) -> tuple[float, list[float]]:
    """Worker task for concurrent write benchmark.

    Returns:
        (ops_per_second, latencies_ms)
    """
    redis_client = RedisClient.get_client()
    key = f"{key_prefix}:worker_{worker_id}"
    latencies = []

    start = time.perf_counter()
    for i in range(num_ops):
        pos = _create_test_position(f"pos_{worker_id}_{i}")
        data = _serialize_position(pos)

        op_start = time.perf_counter()
        redis_client.hset(key, pos.id, json.dumps(data))
        op_end = time.perf_counter()

        latencies.append((op_end - op_start) * 1000)  # Convert to ms
    end = time.perf_counter()

    # Cleanup
    redis_client.delete(key)

    elapsed = end - start
    ops_per_second = num_ops / elapsed
    return ops_per_second, latencies


def _worker_read_task(worker_id: int, num_ops: int, key_prefix: str) -> tuple[float, list[float]]:
    """Worker task for concurrent read benchmark.

    Returns:
        (ops_per_second, latencies_ms)
    """
    redis_client = RedisClient.get_client()
    key = f"{key_prefix}:worker_{worker_id}"
    latencies = []

    # Setup: Write positions first
    positions = [_create_test_position(f"pos_{worker_id}_{i}") for i in range(num_ops)]
    mapping = {}
    for pos in positions:
        data = _serialize_position(pos)
        mapping[pos.id] = json.dumps(data)
    redis_client.hset(key, mapping=mapping)

    # Benchmark reads
    start = time.perf_counter()
    for pos in positions:
        op_start = time.perf_counter()
        redis_client.hget(key, pos.id)
        op_end = time.perf_counter()

        latencies.append((op_end - op_start) * 1000)  # Convert to ms
    end = time.perf_counter()

    # Cleanup
    redis_client.delete(key)

    elapsed = end - start
    ops_per_second = num_ops / elapsed
    return ops_per_second, latencies


def _calculate_percentiles(latencies: list[float]) -> dict[str, float]:
    """Calculate latency percentiles.

    Args:
        latencies: List of latency values in milliseconds

    Returns:
        dict with p50, p95, p99 in milliseconds
    """
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_latencies = sorted(latencies)
    return {
        "p50": statistics.quantiles(sorted_latencies, n=100)[49],
        "p95": statistics.quantiles(sorted_latencies, n=100)[94],
        "p99": statistics.quantiles(sorted_latencies, n=100)[98],
    }


@pytest.fixture
def redis_client():
    """Get Redis client and ensure clean state."""
    client = RedisClient.get_client()

    # Clean up any test keys from previous runs
    test_keys = client.keys("test:positions:*")
    if test_keys:
        client.delete(*test_keys)

    yield client

    # Cleanup after tests
    test_keys = client.keys("test:positions:*")
    if test_keys:
        client.delete(*test_keys)


class TestRedisPositionStateCRUD:
    """Performance benchmarks for Redis position state CRUD operations."""

    def test_position_write_throughput(self, redis_client):
        """Benchmark single-threaded write throughput (baseline).

        Expected: >= 1000 ops/second
        Simulates: Orchestrator adding/updating positions during trading
        """
        num_positions = 1000
        iterations = 10

        throughputs = []
        for _ in range(iterations):
            ops_per_second = _benchmark_write_throughput(redis_client, num_positions)
            throughputs.append(ops_per_second)

        avg_throughput = statistics.mean(throughputs)
        std_throughput = statistics.stdev(throughputs)

        print(f"\n{'='*70}")
        print(f"Single-threaded Write Throughput ({num_positions} positions)")
        print(f"{'='*70}")
        print(f"Average:    {avg_throughput:,.0f} ops/second")
        print(f"Std Dev:    {std_throughput:,.0f} ops/second")
        print(f"Min:        {min(throughputs):,.0f} ops/second")
        print(f"Max:        {max(throughputs):,.0f} ops/second")
        print(f"Target:     >= 1,000 ops/second")
        print(f"Status:     {'✓ PASS' if avg_throughput >= 1000 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        assert avg_throughput >= 1000, f"Write throughput {avg_throughput:.0f} < 1000 ops/s"

    def test_position_read_throughput(self, redis_client):
        """Benchmark single-threaded read throughput (baseline).

        Expected: >= 1000 ops/second
        Simulates: Orchestrator retrieving position state for decision-making
        """
        num_positions = 1000
        iterations = 10

        throughputs = []
        for _ in range(iterations):
            ops_per_second = _benchmark_read_throughput(redis_client, num_positions)
            throughputs.append(ops_per_second)

        avg_throughput = statistics.mean(throughputs)
        std_throughput = statistics.stdev(throughputs)

        print(f"\n{'='*70}")
        print(f"Single-threaded Read Throughput ({num_positions} positions)")
        print(f"{'='*70}")
        print(f"Average:    {avg_throughput:,.0f} ops/second")
        print(f"Std Dev:    {std_throughput:,.0f} ops/second")
        print(f"Min:        {min(throughputs):,.0f} ops/second")
        print(f"Max:        {max(throughputs):,.0f} ops/second")
        print(f"Target:     >= 1,000 ops/second")
        print(f"Status:     {'✓ PASS' if avg_throughput >= 1000 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        assert avg_throughput >= 1000, f"Read throughput {avg_throughput:.0f} < 1000 ops/s"

    def test_position_read_all_throughput(self, redis_client):
        """Benchmark HGETALL (batch read) throughput.

        Expected: Much higher than individual reads (10x+)
        Simulates: Dashboard/monitoring retrieving all open positions
        """
        num_positions = 100  # Typical concurrent positions
        iterations = 10

        throughputs = []
        for _ in range(iterations):
            ops_per_second = _benchmark_read_all_throughput(redis_client, num_positions)
            throughputs.append(ops_per_second)

        avg_throughput = statistics.mean(throughputs)
        std_throughput = statistics.stdev(throughputs)

        print(f"\n{'='*70}")
        print(f"HGETALL Batch Read Throughput ({num_positions} positions)")
        print(f"{'='*70}")
        print(f"Average:    {avg_throughput:,.0f} positions/second")
        print(f"Std Dev:    {std_throughput:,.0f} positions/second")
        print(f"Min:        {min(throughputs):,.0f} positions/second")
        print(f"Max:        {max(throughputs):,.0f} positions/second")
        print(f"Note:       HGETALL is typically 10-100x faster than individual HGET")
        print(f"{'='*70}\n")

        # HGETALL should be significantly faster than individual reads
        # Expect at least 10,000 positions/s (10x baseline)
        assert avg_throughput >= 10000, f"HGETALL throughput {avg_throughput:.0f} < 10,000 positions/s"

    def test_concurrent_access_10_workers(self, redis_client):
        """Benchmark concurrent access with 10 workers (normal load).

        Expected: Graceful degradation (< 50% throughput drop per worker)
        Simulates: Multiple orchestrator instances or concurrent dashboard viewers
        """
        num_workers = 10
        ops_per_worker = 100
        key_prefix = "test:positions:concurrent_10"

        # Concurrent writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_worker_write_task, i, ops_per_worker, key_prefix)
                for i in range(num_workers)
            ]
            write_results = [f.result() for f in concurrent.futures.as_completed(futures)]

        write_throughputs = [r[0] for r in write_results]
        all_write_latencies = [lat for r in write_results for lat in r[1]]
        write_percentiles = _calculate_percentiles(all_write_latencies)

        # Concurrent reads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_worker_read_task, i, ops_per_worker, key_prefix)
                for i in range(num_workers)
            ]
            read_results = [f.result() for f in concurrent.futures.as_completed(futures)]

        read_throughputs = [r[0] for r in read_results]
        all_read_latencies = [lat for r in read_results for lat in r[1]]
        read_percentiles = _calculate_percentiles(all_read_latencies)

        # Aggregate metrics
        total_write_ops = sum(write_throughputs)
        total_read_ops = sum(read_throughputs)

        print(f"\n{'='*70}")
        print(f"Concurrent Access Benchmark ({num_workers} workers)")
        print(f"{'='*70}")
        print(f"Write Throughput:")
        print(f"  Total:      {total_write_ops:,.0f} ops/second (all workers combined)")
        print(f"  Per Worker: {statistics.mean(write_throughputs):,.0f} ops/second (average)")
        print(f"  Latency p50: {write_percentiles['p50']:.2f} ms")
        print(f"  Latency p95: {write_percentiles['p95']:.2f} ms")
        print(f"  Latency p99: {write_percentiles['p99']:.2f} ms")
        print(f"\nRead Throughput:")
        print(f"  Total:      {total_read_ops:,.0f} ops/second (all workers combined)")
        print(f"  Per Worker: {statistics.mean(read_throughputs):,.0f} ops/second (average)")
        print(f"  Latency p50: {read_percentiles['p50']:.2f} ms")
        print(f"  Latency p95: {read_percentiles['p95']:.2f} ms")
        print(f"  Latency p99: {read_percentiles['p99']:.2f} ms")
        print(f"{'='*70}\n")

        # Verify latency targets (p99 < 10ms)
        assert write_percentiles["p99"] < 10.0, f"Write p99 latency {write_percentiles['p99']:.2f}ms > 10ms"
        assert read_percentiles["p99"] < 10.0, f"Read p99 latency {read_percentiles['p99']:.2f}ms > 10ms"

    def test_concurrent_access_50_workers(self, redis_client):
        """Benchmark concurrent access with 50 workers (stress test).

        Expected: System remains stable, latency p99 < 50ms
        Simulates: Peak load with many concurrent operations
        """
        num_workers = 50
        ops_per_worker = 50
        key_prefix = "test:positions:concurrent_50"

        # Concurrent writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_worker_write_task, i, ops_per_worker, key_prefix)
                for i in range(num_workers)
            ]
            write_results = [f.result() for f in concurrent.futures.as_completed(futures)]

        write_throughputs = [r[0] for r in write_results]
        all_write_latencies = [lat for r in write_results for lat in r[1]]
        write_percentiles = _calculate_percentiles(all_write_latencies)

        # Concurrent reads
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(_worker_read_task, i, ops_per_worker, key_prefix)
                for i in range(num_workers)
            ]
            read_results = [f.result() for f in concurrent.futures.as_completed(futures)]

        read_throughputs = [r[0] for r in read_results]
        all_read_latencies = [lat for r in read_results for lat in r[1]]
        read_percentiles = _calculate_percentiles(all_read_latencies)

        # Aggregate metrics
        total_write_ops = sum(write_throughputs)
        total_read_ops = sum(read_throughputs)

        print(f"\n{'='*70}")
        print(f"Stress Test: Concurrent Access ({num_workers} workers)")
        print(f"{'='*70}")
        print(f"Write Throughput:")
        print(f"  Total:      {total_write_ops:,.0f} ops/second (all workers combined)")
        print(f"  Per Worker: {statistics.mean(write_throughputs):,.0f} ops/second (average)")
        print(f"  Latency p50: {write_percentiles['p50']:.2f} ms")
        print(f"  Latency p95: {write_percentiles['p95']:.2f} ms")
        print(f"  Latency p99: {write_percentiles['p99']:.2f} ms")
        print(f"\nRead Throughput:")
        print(f"  Total:      {total_read_ops:,.0f} ops/second (all workers combined)")
        print(f"  Per Worker: {statistics.mean(read_throughputs):,.0f} ops/second (average)")
        print(f"  Latency p50: {read_percentiles['p50']:.2f} ms")
        print(f"  Latency p95: {read_percentiles['p95']:.2f} ms")
        print(f"  Latency p99: {read_percentiles['p99']:.2f} ms")
        print(f"Target:      p99 latency < 50ms (stress test threshold)")
        print(f"Status:      {'✓ PASS' if write_percentiles['p99'] < 50 and read_percentiles['p99'] < 50 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify stress test latency targets (p99 < 50ms)
        assert write_percentiles["p99"] < 50.0, f"Write p99 latency {write_percentiles['p99']:.2f}ms > 50ms under stress"
        assert read_percentiles["p99"] < 50.0, f"Read p99 latency {read_percentiles['p99']:.2f}ms > 50ms under stress"

    def test_latency_percentiles(self, redis_client):
        """Measure p50, p95, p99 latency for read/write operations.

        Expected: p50 < 1ms, p95 < 5ms, p99 < 10ms (normal load)
        Critical for understanding tail latency behavior
        """
        num_operations = 1000
        key = "test:positions:latency"

        # Benchmark write latencies
        write_latencies = []
        for i in range(num_operations):
            pos = _create_test_position(f"pos_{i}")
            data = _serialize_position(pos)

            start = time.perf_counter()
            redis_client.hset(key, pos.id, json.dumps(data))
            end = time.perf_counter()

            write_latencies.append((end - start) * 1000)  # Convert to ms

        write_percentiles = _calculate_percentiles(write_latencies)

        # Benchmark read latencies
        read_latencies = []
        for i in range(num_operations):
            pos_id = f"pos_{i}"

            start = time.perf_counter()
            redis_client.hget(key, pos_id)
            end = time.perf_counter()

            read_latencies.append((end - start) * 1000)  # Convert to ms

        read_percentiles = _calculate_percentiles(read_latencies)

        # Cleanup
        redis_client.delete(key)

        print(f"\n{'='*70}")
        print(f"Latency Percentiles ({num_operations} operations)")
        print(f"{'='*70}")
        print(f"Write Latency:")
        print(f"  p50: {write_percentiles['p50']:.2f} ms")
        print(f"  p95: {write_percentiles['p95']:.2f} ms")
        print(f"  p99: {write_percentiles['p99']:.2f} ms")
        print(f"\nRead Latency:")
        print(f"  p50: {read_percentiles['p50']:.2f} ms")
        print(f"  p95: {read_percentiles['p95']:.2f} ms")
        print(f"  p99: {read_percentiles['p99']:.2f} ms")
        print(f"\nTargets:")
        print(f"  p50 < 1ms")
        print(f"  p95 < 5ms")
        print(f"  p99 < 10ms")
        print(f"\nStatus:")
        print(f"  Write: {'✓ PASS' if write_percentiles['p99'] < 10 else '✗ FAIL'}")
        print(f"  Read:  {'✓ PASS' if read_percentiles['p99'] < 10 else '✗ FAIL'}")
        print(f"{'='*70}\n")

        # Verify latency targets
        assert write_percentiles["p50"] < 1.0, f"Write p50 latency {write_percentiles['p50']:.2f}ms > 1ms"
        assert write_percentiles["p95"] < 5.0, f"Write p95 latency {write_percentiles['p95']:.2f}ms > 5ms"
        assert write_percentiles["p99"] < 10.0, f"Write p99 latency {write_percentiles['p99']:.2f}ms > 10ms"

        assert read_percentiles["p50"] < 1.0, f"Read p50 latency {read_percentiles['p50']:.2f}ms > 1ms"
        assert read_percentiles["p95"] < 5.0, f"Read p95 latency {read_percentiles['p95']:.2f}ms > 5ms"
        assert read_percentiles["p99"] < 10.0, f"Read p99 latency {read_percentiles['p99']:.2f}ms > 10ms"
