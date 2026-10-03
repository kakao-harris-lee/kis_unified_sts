"""Performance benchmarks for orchestrator scalability with varying position counts.

This module benchmarks orchestrator CYCLE TIME as the number of concurrent
positions increases from 1 to 20. The goal is to verify linear (or better)
scaling and identify the maximum sustainable concurrent positions.

Nothing here measures memory. It once appeared to: `_benchmark_orchestrator_cycle`
returned a memory delta taken from a helper that returned a hardcoded `0.0`, so
every reading was 0.00 MB and no test asserted on it. The helper, the delta and
the two `gc.collect()` calls that bracketed it were removed in PR #857 (#768),
where they turned out to be 92% of the measured duration of the two longest
benchmarks here. `test_memory_usage_scaling` keeps its name for continuity with
the baseline file; what it checks is cycle-time scaling, as its body always did.

**Performance Goals:**
- Cycle time for 10 positions: < 5 seconds (SLA requirement)
- Scalability: Linear or sub-linear (cycle time shouldn't grow exponentially)
- Maximum sustainable positions: >= 20 concurrent positions

**Orchestrator Cycle Simulation:**
A trading cycle consists of:
1. Entry signal checking (_handle_entry) - scans candidates for entry signals
2. Exit signal checking (_handle_exit) - scans open positions for exit signals
3. Position state updates - updates position metrics (PnL, stop prices, etc.)
4. Risk management checks - validates drawdown limits, regime filters

**Benchmark Scenarios:**
1. 1 position (baseline) - single position cycle time
2. 5 positions (typical small portfolio) - normal small load
3. 10 positions (normal load) - SLA target of < 5s cycle time
4. 20 positions (stress test) - maximum sustainable load
5. Scalability sweep - cycle time across all four counts in one test

**Why Micro-benchmarks Matter:**
Unlike integration tests, these micro-benchmarks isolate core orchestrator logic
to measure pure scalability without external dependencies (WebSocket, Redis, etc.).
This allows us to identify orchestrator-specific bottlenecks.
"""

from __future__ import annotations

import time

# Cycles timed per measurement. 100 left the two sweep benchmarks at 6.2-6.3 ms
# once PR #857 took the garbage collection out of the measured window -- below
# the regression checker's 50 ms noise floor, which would have exempted them
# from the baseline-ratio check entirely and left only the assertions below.
# 2000 puts the real work at ~120 ms on a CI runner: comfortably over the floor,
# and still a tenth of a second per benchmark.
BENCHMARK_ITERATIONS = 2000

# Wall-clock ceiling per cycle, by concurrent position count. One source: the
# four single-count tests and the sweep in `test_scalability_summary` assert
# the same numbers, and the summary's printed "SLA PASS"/"OK" is derived from
# this map rather than restating it.
CYCLE_TIME_CEILINGS_MS = {1: 100.0, 5: 500.0, 10: 5000.0, 20: 10000.0}

# Cycle time at 20 positions over cycle time at 1 position. 20x is exactly
# linear; above that, scaling is super-linear.
MAX_SCALING_FACTOR = 20.0
from datetime import datetime
from typing import Any

from shared.models.position import Position, PositionSide, PositionState


def _create_test_positions(count: int) -> list[Position]:
    """Create test positions for benchmarking.

    Args:
        count: Number of positions to create

    Returns:
        List of Position objects
    """
    positions = []
    for i in range(count):
        code = f"{i:06d}"
        position = Position(
            id=f"pos_{code}",
            code=code,
            name=f"Stock {code}",
            side=PositionSide.LONG,
            quantity=100,
            entry_price=50000.0 + (i * 100),  # Vary entry price slightly
            entry_time=datetime.now(),
            current_price=51000.0 + (i * 100),
            highest_price=52000.0 + (i * 100),
            lowest_price=49500.0 + (i * 100),
            stop_price=48000.0 + (i * 100),
            state=PositionState.BREAKEVEN,
            strategy="mean_reversion",
            fee_rate=0.003,
        )
        positions.append(position)
    return positions


def _create_test_market_data(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Create mock market data for entry signal checking.

    Args:
        symbols: List of symbol codes

    Returns:
        Dict mapping symbol to market data
    """
    market_data = {}
    for i, symbol in enumerate(symbols):
        market_data[symbol] = {
            "code": symbol,
            "price": 50000.0 + (i * 100),
            "volume": 1_000_000,
            "timestamp": datetime.now().isoformat(),
            # Add basic indicators
            "bb_upper": 52000.0,
            "bb_middle": 50000.0,
            "bb_lower": 48000.0,
            "rsi": 45.0,
            "macd": 100.0,
            "signal": 95.0,
        }
    return market_data


def _simulate_entry_signal_cycle(market_data: dict[str, dict[str, Any]]) -> int:
    """Simulate entry signal checking cycle.

    This simulates the hot path in _handle_entry():
    - Iterate through candidate symbols
    - Enrich with metadata
    - Check entry conditions (BB, RSI, etc.)
    - Generate entry signals

    Args:
        market_data: Market data for all candidate symbols

    Returns:
        Number of signals generated
    """
    signals_generated = 0

    for _symbol, data in market_data.items():
        # Simulate indicator access and enrichment (like orchestrator does)
        price = data.get("price", 0)
        bb_lower = data.get("bb_lower", 0)
        rsi = data.get("rsi", 50)

        # Simulate entry condition checking
        if price <= bb_lower and rsi < 30:
            signals_generated += 1

    return signals_generated


def _simulate_exit_signal_cycle(positions: list[Position]) -> int:
    """Simulate exit signal checking cycle.

    This simulates the hot path in _handle_exit():
    - Iterate through open positions
    - Update position metrics (PnL, highest/lowest)
    - Check exit conditions (stop loss, take profit, three-stage logic)
    - Generate exit signals

    Args:
        positions: List of open positions

    Returns:
        Number of exit signals generated
    """
    exit_signals = 0

    for position in positions:
        # Simulate position metric updates
        current_price = position.current_price
        entry_price = position.entry_price
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Simulate exit condition checking (three-stage example)
        if position.state == PositionState.SURVIVAL:
            # Check hard stop
            if current_price <= position.stop_price:
                exit_signals += 1
        elif position.state == PositionState.BREAKEVEN:
            # Check breakeven stop
            if pnl_pct < -0.5:
                exit_signals += 1
        elif position.state == PositionState.MAXIMIZE:
            # Check trailing stop
            if pnl_pct < 1.0:
                exit_signals += 1

    return exit_signals


def _simulate_position_update_cycle(positions: list[Position]) -> None:
    """Simulate position state updates.

    This simulates position metric updates:
    - Update current_price, highest_price, lowest_price
    - Recalculate PnL
    - Update stop prices based on state
    - Transition between states (SURVIVAL -> BREAKEVEN -> MAXIMIZE)

    Args:
        positions: List of positions to update
    """
    for position in positions:
        # Simulate price updates
        current_price = position.current_price
        position.highest_price = max(position.highest_price, current_price)
        position.lowest_price = min(position.lowest_price, current_price)

        # Simulate PnL calculation
        entry_price = position.entry_price
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Simulate state transitions (three-stage logic)
        if position.state == PositionState.SURVIVAL and pnl_pct >= 2.0:
            position.state = PositionState.BREAKEVEN
        elif position.state == PositionState.BREAKEVEN and pnl_pct >= 5.0:
            position.state = PositionState.MAXIMIZE


def _benchmark_orchestrator_cycle(position_count: int, iterations: int = 100) -> float:
    """Benchmark a full orchestrator cycle with N positions.

    No ``gc.collect()`` here. It used to bracket the loop, twice per call, to
    take a memory delta either side -- from ``_get_process_memory_mb()``, which
    returned a hardcoded ``0.0``. The delta was always 0.00 MB, no test
    asserted on it, and those two full collections were nearly the whole cost
    of this benchmark as the regression checker measures it.

    The checker sums pytest's setup+call+teardown wall time, so anything this
    function does lands in the number. A full collection walks the entire live
    object graph of the pytest process -- set by what the session imported and
    what earlier tests left allocated, not by the code under test. Measured
    2026-10-03 (#768): 8 collections cost 2.0 ms in a bare process and 1198 ms
    with 1.2M extra tracked objects. In CI that made ``test_scalability_summary``
    and ``test_memory_usage_scaling`` 101-281 ms per round whose own timed loop,
    printed by the callers, summed to 4-6 ms. They were measuring the heap: in
    run 37115379025 they read +249% and +229% in the same job where the
    pure-CPU hot-path benchmarks ran 44% faster.

    Args:
        position_count: Number of concurrent positions
        iterations: Number of cycles to run

    Returns:
        Average cycle time in milliseconds.
    """
    # Setup: Create positions and market data
    positions = _create_test_positions(position_count)
    symbols = [f"{i:06d}" for i in range(position_count * 5)]  # 5x symbols for entry scanning
    market_data = _create_test_market_data(symbols)

    # Benchmark cycle time
    cycle_times = []

    for _ in range(iterations):
        start_time = time.perf_counter()

        # Simulate full orchestrator cycle
        _simulate_entry_signal_cycle(market_data)
        _simulate_exit_signal_cycle(positions)
        _simulate_position_update_cycle(positions)

        end_time = time.perf_counter()
        cycle_time_ms = (end_time - start_time) * 1000
        cycle_times.append(cycle_time_ms)

    # Calculate average cycle time
    return sum(cycle_times) / len(cycle_times)


class TestOrchestratorScalability:
    """Performance benchmarks for orchestrator scalability."""

    def test_cycle_time_1_position(self):
        """Benchmark cycle time with 1 position (baseline).

        This establishes the baseline cycle time for a single position.
        Expected: < 100ms per cycle (micro-benchmark, no I/O overhead).
        """
        position_count = 1
        iterations = BENCHMARK_ITERATIONS

        avg_cycle_time_ms = _benchmark_orchestrator_cycle(position_count, iterations)

        print(f"\n{'='*60}")
        print("Orchestrator Cycle Time - 1 Position (Baseline)")
        print(f"{'='*60}")
        print(f"Average cycle time: {avg_cycle_time_ms:.2f} ms")
        print(f"Iterations: {iterations}")
        print(f"{'='*60}\n")

        ceiling = CYCLE_TIME_CEILINGS_MS[1]
        assert avg_cycle_time_ms < ceiling, (
            f"{position_count}-position cycle time too slow: "
            f"{avg_cycle_time_ms:.2f}ms > {ceiling:.0f}ms"
        )

    def test_cycle_time_5_positions(self):
        """Benchmark cycle time with 5 positions (typical small portfolio).

        This simulates a small portfolio with 5 concurrent positions.
        Expected: < 500ms per cycle (5x baseline with some overhead).
        """
        position_count = 5
        iterations = BENCHMARK_ITERATIONS

        avg_cycle_time_ms = _benchmark_orchestrator_cycle(position_count, iterations)

        print(f"\n{'='*60}")
        print("Orchestrator Cycle Time - 5 Positions")
        print(f"{'='*60}")
        print(f"Average cycle time: {avg_cycle_time_ms:.2f} ms")
        print(f"Iterations: {iterations}")
        print(f"{'='*60}\n")

        ceiling = CYCLE_TIME_CEILINGS_MS[5]
        assert avg_cycle_time_ms < ceiling, (
            f"{position_count}-position cycle time too slow: "
            f"{avg_cycle_time_ms:.2f}ms > {ceiling:.0f}ms"
        )

    def test_cycle_time_10_positions(self):
        """Benchmark cycle time with 10 positions (normal load).

        This simulates normal production load with 10 concurrent positions.
        Expected: < 5000ms (5 seconds) per cycle - this is the SLA requirement.

        **SLA Requirement:** Orchestrator cycle time < 5s for 10 positions.
        """
        position_count = 10
        iterations = BENCHMARK_ITERATIONS

        avg_cycle_time_ms = _benchmark_orchestrator_cycle(position_count, iterations)

        print(f"\n{'='*60}")
        print("Orchestrator Cycle Time - 10 Positions (SLA Target)")
        print(f"{'='*60}")
        print(f"Average cycle time: {avg_cycle_time_ms:.2f} ms")
        print(f"Iterations: {iterations}")
        ceiling = CYCLE_TIME_CEILINGS_MS[10]
        print(f"SLA Requirement: < {ceiling:.0f} ms")
        print(f"SLA Status: {'✓ PASS' if avg_cycle_time_ms < ceiling else '✗ FAIL'}")
        print(f"{'='*60}\n")

        # SLA requirement: < 5 seconds for 10 positions
        assert avg_cycle_time_ms < ceiling, (
            f"SLA violation: {position_count}-position cycle time "
            f"{avg_cycle_time_ms:.2f}ms > {ceiling:.0f}ms"
        )

    def test_cycle_time_20_positions(self):
        """Benchmark cycle time with 20 positions (stress test maximum load).

        This stress tests the orchestrator with the maximum expected concurrent positions.
        Expected: < 10000ms (10 seconds) - should maintain sub-linear scaling.
        """
        position_count = 20
        iterations = BENCHMARK_ITERATIONS

        avg_cycle_time_ms = _benchmark_orchestrator_cycle(position_count, iterations)

        print(f"\n{'='*60}")
        print("Orchestrator Cycle Time - 20 Positions (Stress Test)")
        print(f"{'='*60}")
        print(f"Average cycle time: {avg_cycle_time_ms:.2f} ms")
        print(f"Iterations: {iterations}")
        print(f"{'='*60}\n")

        ceiling = CYCLE_TIME_CEILINGS_MS[20]
        assert avg_cycle_time_ms < ceiling, (
            f"{position_count}-position cycle time too slow: "
            f"{avg_cycle_time_ms:.2f}ms > {ceiling:.0f}ms"
        )

    def test_memory_usage_scaling(self):
        """Verify cycle time scaling as position count increases.

        This benchmarks cycle time across all position counts to verify
        scalability. Expected: cycle time should grow linearly with position
        count, not exponentially.

        The name is historical. Nothing here measures memory, and nothing did:
        the memory delta this test once collected came from a helper that
        returned a hardcoded 0.0 (removed in PR #857, see the module
        docstring). The name is kept so the baseline entry stays matched.
        """
        position_counts = [1, 5, 10, 20]
        iterations = BENCHMARK_ITERATIONS

        results = []

        print(f"\n{'='*60}")
        print("Orchestrator Scalability Analysis")
        print(f"{'='*60}")

        for count in position_counts:
            avg_cycle_time_ms = _benchmark_orchestrator_cycle(count, iterations)
            results.append({
                "positions": count,
                "cycle_time_ms": avg_cycle_time_ms,
            })

            print(f"{count} positions: {avg_cycle_time_ms:.2f} ms cycle time")

        print(f"{'='*60}")

        # Verify linear scaling (not exponential)
        # Calculate scaling factor: cycle_time(20) / cycle_time(1) should be <= 20x
        baseline_time = results[0]["cycle_time_ms"]
        max_time = results[-1]["cycle_time_ms"]
        scaling_factor = max_time / baseline_time if baseline_time > 0 else 0

        print("\nScalability Analysis:")
        print(f"  Baseline (1 pos): {baseline_time:.2f} ms")
        print(f"  Maximum (20 pos): {max_time:.2f} ms")
        print(f"  Scaling factor: {scaling_factor:.2f}x")
        print("  Target: <= 20x (linear)")
        print(f"  Status: {'✓ Linear/Sub-linear' if scaling_factor <= 20 else '✗ Super-linear'}")
        print(f"{'='*60}\n")

        # Verify linear or sub-linear scaling (not exponential)
        assert scaling_factor <= MAX_SCALING_FACTOR, (
            f"Scaling is super-linear: {scaling_factor:.2f}x > "
            f"{MAX_SCALING_FACTOR:.0f}x (exponential growth detected)"
        )

    def test_scalability_summary(self):
        """Check every per-count ceiling and the scaling factor in one sweep.

        This used to end in ``assert True`` -- it printed "SLA PASS"/"SLA FAIL"
        and passed either way, so the only thing watching it was the regression
        checker's baseline ratio, and that ratio was 92% garbage collection
        until PR #857 (#768). It now asserts what it prints: every count
        against ``CYCLE_TIME_CEILINGS_MS`` and the 1->20 scaling factor against
        ``MAX_SCALING_FACTOR``.
        """
        position_counts = [1, 5, 10, 20]
        iterations = BENCHMARK_ITERATIONS

        print(f"\n{'='*70}")
        print("Orchestrator Scalability Summary Report")
        print(f"{'='*70}")
        print(f"{'Positions':<12} {'Cycle Time (ms)':<20} {'Status':<15}")
        print(f"{'-'*70}")

        results = []

        for count in position_counts:
            avg_cycle_time_ms = _benchmark_orchestrator_cycle(count, iterations)

            # Status comes from the same map the assertions below use, so the
            # printed verdict cannot disagree with the one that fails the test.
            ceiling = CYCLE_TIME_CEILINGS_MS[count]
            status = "✓ OK" if avg_cycle_time_ms < ceiling else "✗ OVER"

            print(f"{count:<12} {avg_cycle_time_ms:<20.2f} {status:<15}")

            results.append({
                "positions": count,
                "cycle_time_ms": avg_cycle_time_ms,
            })

        print(f"{'-'*70}")

        # Calculate scalability metrics. Initialised before the branch: it is
        # read unconditionally below, and `position_counts` having fewer than
        # two entries would otherwise be a NameError instead of a clear skip.
        scaling_factor = 0.0
        if len(results) >= 2:
            baseline_time = results[0]["cycle_time_ms"]
            max_time = results[-1]["cycle_time_ms"]
            scaling_factor = max_time / baseline_time if baseline_time > 0 else 0.0

            print("\nScalability Metrics:")
            print(f"  Actual scaling factor: {scaling_factor:.2f}x")
            print("  Linear baseline: 20x (for 20 positions)")
            print(f"  Efficiency: {(20.0 / scaling_factor * 100) if scaling_factor > 0 else 0:.1f}% of linear scaling")

        print("\nPerformance Summary:")
        print(f"  Maximum sustainable positions: >= {max(position_counts)}")
        print(
            "  Scaling behavior: "
            f"{'✓ Linear/Sub-linear' if scaling_factor <= MAX_SCALING_FACTOR else '✗ Super-linear'}"
        )
        print(f"{'='*70}\n")

        over = [
            (r["positions"], r["cycle_time_ms"])
            for r in results
            if r["cycle_time_ms"] >= CYCLE_TIME_CEILINGS_MS[r["positions"]]
        ]
        assert not over, "cycle time over its ceiling at " + ", ".join(
            f"{n} positions ({ms:.2f}ms >= {CYCLE_TIME_CEILINGS_MS[n]:.0f}ms)"
            for n, ms in over
        )
        measured_counts = {r["positions"] for r in results}
        missing = [c for c in position_counts if c not in measured_counts]
        assert not missing, f"counts not measured: {missing}"
        assert scaling_factor <= MAX_SCALING_FACTOR, (
            f"Scaling is super-linear: {scaling_factor:.2f}x > "
            f"{MAX_SCALING_FACTOR:.0f}x (exponential growth detected)"
        )
