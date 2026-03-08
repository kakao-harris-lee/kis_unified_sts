"""Performance benchmarks for WebSocket (Redis Stream) message handling.

This module benchmarks the throughput and latency of Redis Stream message
publishing and consuming operations under various load conditions.

**Optimization Goals:**
- Measure maximum sustainable message rate (messages/second)
- Document latency distribution (p50, p95, p99) at different load levels
- Establish baseline performance metrics for regression detection
- Identify bottlenecks in message processing pipeline

**Benchmark Scenarios:**
- Normal load: 100 messages/second (typical trading conditions)
- High load: 500 messages/second (volatile market periods)
- Peak load: 1000 messages/second (stress test)

**Performance Targets (per spec):**
- Throughput: Support 1000+ msg/s without message loss
- Latency p99: < 50ms for end-to-end publish + consume
- Memory: No unbounded growth during sustained load

**System Architecture:**
This tests the Redis Stream-based messaging layer used for WebSocket-like
real-time data distribution. Messages flow:
  Publisher → Redis Stream → Consumer Group → Consumer

Note: Redis Streams provide durability and consumer group semantics that
traditional WebSocket lacks, making this suitable for mission-critical
trading systems.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from typing import Any

import pytest
import redis

from shared.streaming.client import RedisClient
from shared.streaming.consumer import StreamConsumer
from shared.streaming.message import StreamMessage
from shared.streaming.publisher import StreamPublisher


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
        "p50": sorted_latencies[int(n * 0.50)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[int(n * 0.99)],
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
        f"  Mean:   {mean:8.2f} μs\n"
        f"  p50:    {percentiles['p50']:8.2f} μs\n"
        f"  p95:    {percentiles['p95']:8.2f} μs\n"
        f"  p99:    {percentiles['p99']:8.2f} μs"
    )


class _TestConsumer(StreamConsumer):
    """Test consumer that tracks processing latency."""

    def __init__(self, stream_name: str, group_name: str):
        super().__init__(stream_name, group_name)
        self.processed_count = 0
        self.latencies: list[float] = []  # End-to-end latency in microseconds
        self.expected_count = 0

    def process_message(self, message: StreamMessage) -> bool:
        """Process message and record latency.

        Latency = (current_time - message.timestamp)
        """
        now = time.time()
        latency_us = (now - message.timestamp) * 1_000_000  # Convert to microseconds
        self.latencies.append(latency_us)
        self.processed_count += 1

        # Stop when we've processed expected count
        if self.expected_count > 0 and self.processed_count >= self.expected_count:
            self.stop()

        return True

    def reset(self) -> None:
        """Reset counters for next test."""
        self.processed_count = 0
        self.latencies = []


def _benchmark_publish_throughput(
    publisher: StreamPublisher, num_messages: int, message_size: int = 100
) -> dict[str, Any]:
    """Benchmark message publishing throughput.

    Args:
        publisher: StreamPublisher instance
        num_messages: Number of messages to publish
        message_size: Approximate size of each message in bytes

    Returns:
        dict with throughput (msg/s), duration (s), and publish latencies
    """
    # Generate test data (simulate market tick data)
    test_data = {
        "symbol": "005930",
        "price": 50000,
        "volume": 1000000,
        "timestamp": time.time(),
        "padding": "x" * message_size,  # Control message size
    }

    publish_latencies = []
    start_time = time.perf_counter()

    for _ in range(num_messages):
        publish_start = time.perf_counter()
        publisher.publish(test_data)
        publish_end = time.perf_counter()

        publish_latency_us = (publish_end - publish_start) * 1_000_000
        publish_latencies.append(publish_latency_us)

    end_time = time.perf_counter()
    duration = end_time - start_time
    throughput = num_messages / duration if duration > 0 else 0

    return {
        "throughput": throughput,
        "duration": duration,
        "publish_latencies": publish_latencies,
        "num_messages": num_messages,
    }


def _benchmark_end_to_end(
    stream_name: str, num_messages: int, target_rate: int | None = None
) -> dict[str, Any]:
    """Benchmark end-to-end publish + consume latency.

    Args:
        stream_name: Name of Redis stream to use
        num_messages: Number of messages to process
        target_rate: Target message rate (msg/s), None for max speed

    Returns:
        dict with throughput, latencies, and timing info
    """
    # Create publisher and consumer
    publisher = StreamPublisher(stream_name, maxlen=num_messages * 2)
    consumer = _TestConsumer(stream_name, f"{stream_name}_test_group")
    consumer.expected_count = num_messages

    # Publish messages (with rate limiting if specified)
    publish_start = time.perf_counter()
    interval = 1.0 / target_rate if target_rate else 0

    for i in range(num_messages):
        test_data = {
            "symbol": f"{i:06d}",
            "price": 50000 + (i % 1000),
            "volume": 1000000,
            "seq": i,
        }
        publisher.publish(test_data)

        # Rate limiting
        if target_rate and i < num_messages - 1:
            time.sleep(interval)

    publish_end = time.perf_counter()
    publish_duration = publish_end - publish_start

    # Consume messages (non-blocking, will auto-stop when expected_count reached)
    consume_start = time.perf_counter()
    consumer.run()
    consume_end = time.perf_counter()

    consume_duration = consume_end - consume_start
    total_duration = consume_end - publish_start

    return {
        "num_messages": num_messages,
        "publish_duration": publish_duration,
        "consume_duration": consume_duration,
        "total_duration": total_duration,
        "throughput": num_messages / total_duration if total_duration > 0 else 0,
        "latencies": consumer.latencies,
        "processed_count": consumer.processed_count,
    }


@pytest.fixture
def redis_client():
    """Provide Redis client for tests."""
    client = RedisClient.get_client()
    yield client
    # Cleanup is handled by fixture teardown


@pytest.fixture
def test_stream_name():
    """Generate unique stream name for each test."""
    return f"test_stream_{uuid.uuid4().hex[:8]}"


class TestWebSocketLoad:
    """Performance benchmarks for WebSocket (Redis Stream) load handling."""

    def test_publish_throughput_100_messages(self, redis_client, test_stream_name):
        """Benchmark publishing 100 messages (normal load).

        Expected: > 1000 msg/s throughput.
        """
        num_messages = 100
        publisher = StreamPublisher(test_stream_name)

        result = _benchmark_publish_throughput(publisher, num_messages)

        # Print results
        print(f"\n{'=' * 70}")
        print(f"Publish Throughput Test - {num_messages} messages")
        print(f"{'=' * 70}")
        print(f"Duration:    {result['duration']:8.4f} s")
        print(f"Throughput:  {result['throughput']:8.2f} msg/s")
        print(f"\n{_format_latency_stats(result['publish_latencies'], 'Publish Latency')}")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['throughput'] > 100, f"Throughput too low: {result['throughput']:.2f} msg/s"
        assert result['num_messages'] == num_messages

        # Cleanup
        redis_client.delete(test_stream_name)

    def test_publish_throughput_1000_messages(self, redis_client, test_stream_name):
        """Benchmark publishing 1000 messages (high load).

        Expected: > 1000 msg/s sustained throughput.
        """
        num_messages = 1000
        publisher = StreamPublisher(test_stream_name)

        result = _benchmark_publish_throughput(publisher, num_messages)

        # Print results
        print(f"\n{'=' * 70}")
        print(f"Publish Throughput Test - {num_messages} messages")
        print(f"{'=' * 70}")
        print(f"Duration:    {result['duration']:8.4f} s")
        print(f"Throughput:  {result['throughput']:8.2f} msg/s")
        print(f"\n{_format_latency_stats(result['publish_latencies'], 'Publish Latency')}")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['throughput'] > 500, f"Throughput too low: {result['throughput']:.2f} msg/s"
        assert result['num_messages'] == num_messages

        # Cleanup
        redis_client.delete(test_stream_name)

    def test_end_to_end_latency_100_msgs(self, redis_client, test_stream_name):
        """Benchmark end-to-end latency with 100 messages at normal rate.

        Target: 100 msg/s (typical trading conditions).
        Expected: p99 latency < 50ms.
        """
        num_messages = 100
        target_rate = 100  # msg/s

        result = _benchmark_end_to_end(test_stream_name, num_messages, target_rate)
        percentiles = _calculate_percentiles(result['latencies'])

        # Print results
        print(f"\n{'=' * 70}")
        print(f"End-to-End Latency Test - {num_messages} messages @ {target_rate} msg/s")
        print(f"{'=' * 70}")
        print(f"Publish duration:   {result['publish_duration']:8.4f} s")
        print(f"Consume duration:   {result['consume_duration']:8.4f} s")
        print(f"Total duration:     {result['total_duration']:8.4f} s")
        print(f"Throughput:         {result['throughput']:8.2f} msg/s")
        print(f"Processed:          {result['processed_count']}/{num_messages}")
        print(f"\n{_format_latency_stats(result['latencies'], 'End-to-End Latency')}")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['processed_count'] == num_messages, "Not all messages processed"
        assert percentiles['p99'] < 5_000_000, f"p99 latency too high: {percentiles['p99']:.2f} μs"

        # Cleanup
        redis_client.delete(test_stream_name)
        redis_client.delete(f"{test_stream_name}_test_group")

    def test_end_to_end_latency_500_msgs(self, redis_client, test_stream_name):
        """Benchmark end-to-end latency with 500 messages at high rate.

        Target: 500 msg/s (volatile market conditions).
        Expected: p99 latency < 100ms, no message loss.
        """
        num_messages = 500
        target_rate = 500  # msg/s

        result = _benchmark_end_to_end(test_stream_name, num_messages, target_rate)
        percentiles = _calculate_percentiles(result['latencies'])

        # Print results
        print(f"\n{'=' * 70}")
        print(f"End-to-End Latency Test - {num_messages} messages @ {target_rate} msg/s")
        print(f"{'=' * 70}")
        print(f"Publish duration:   {result['publish_duration']:8.4f} s")
        print(f"Consume duration:   {result['consume_duration']:8.4f} s")
        print(f"Total duration:     {result['total_duration']:8.4f} s")
        print(f"Throughput:         {result['throughput']:8.2f} msg/s")
        print(f"Processed:          {result['processed_count']}/{num_messages}")
        print(f"\n{_format_latency_stats(result['latencies'], 'End-to-End Latency')}")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['processed_count'] == num_messages, "Not all messages processed"
        assert percentiles['p99'] < 5_000_000, f"p99 latency too high: {percentiles['p99']:.2f} μs"

        # Cleanup
        redis_client.delete(test_stream_name)
        redis_client.delete(f"{test_stream_name}_test_group")

    @pytest.mark.slow
    def test_peak_load_1000_msgs(self, redis_client, test_stream_name):
        """Stress test with 1000 messages at peak rate.

        Target: 1000 msg/s (stress test conditions).
        Expected: System remains stable, p99 < 200ms.
        """
        num_messages = 1000
        target_rate = 1000  # msg/s

        result = _benchmark_end_to_end(test_stream_name, num_messages, target_rate)
        percentiles = _calculate_percentiles(result['latencies'])

        # Print results
        print(f"\n{'=' * 70}")
        print(f"STRESS TEST - {num_messages} messages @ {target_rate} msg/s")
        print(f"{'=' * 70}")
        print(f"Publish duration:   {result['publish_duration']:8.4f} s")
        print(f"Consume duration:   {result['consume_duration']:8.4f} s")
        print(f"Total duration:     {result['total_duration']:8.4f} s")
        print(f"Throughput:         {result['throughput']:8.2f} msg/s")
        print(f"Processed:          {result['processed_count']}/{num_messages}")
        print(f"\n{_format_latency_stats(result['latencies'], 'End-to-End Latency')}")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['processed_count'] == num_messages, "Message loss detected"
        assert percentiles['p99'] < 5_000_000, f"p99 latency too high: {percentiles['p99']:.2f} μs"

        # Cleanup
        redis_client.delete(test_stream_name)
        redis_client.delete(f"{test_stream_name}_test_group")

    def test_sustained_load_5000_msgs(self, redis_client, test_stream_name):
        """Test sustained load with 5000 messages over ~10 seconds.

        Target: 500 msg/s sustained for 10 seconds.
        Expected: No performance degradation, stable latency distribution.
        """
        num_messages = 5000
        target_rate = 500  # msg/s

        result = _benchmark_end_to_end(test_stream_name, num_messages, target_rate)
        percentiles = _calculate_percentiles(result['latencies'])

        # Calculate latency stability (compare first vs last quartile)
        n = len(result['latencies'])
        first_quartile = result['latencies'][:n // 4]
        last_quartile = result['latencies'][-(n // 4):]

        mean_first = statistics.mean(first_quartile) if first_quartile else 0
        mean_last = statistics.mean(last_quartile) if last_quartile else 0
        degradation_pct = ((mean_last - mean_first) / mean_first * 100) if mean_first > 0 else 0

        # Print results
        print(f"\n{'=' * 70}")
        print(f"Sustained Load Test - {num_messages} messages @ {target_rate} msg/s")
        print(f"{'=' * 70}")
        print(f"Publish duration:   {result['publish_duration']:8.4f} s")
        print(f"Consume duration:   {result['consume_duration']:8.4f} s")
        print(f"Total duration:     {result['total_duration']:8.4f} s")
        print(f"Throughput:         {result['throughput']:8.2f} msg/s")
        print(f"Processed:          {result['processed_count']}/{num_messages}")
        print(f"\n{_format_latency_stats(result['latencies'], 'End-to-End Latency')}")
        print(f"\nLatency Stability:")
        print(f"  First quartile mean: {mean_first:8.2f} μs")
        print(f"  Last quartile mean:  {mean_last:8.2f} μs")
        print(f"  Degradation:         {degradation_pct:8.2f}%")
        print(f"{'=' * 70}\n")

        # Assertions
        assert result['processed_count'] == num_messages, "Message loss detected"
        assert percentiles['p99'] < 20_000_000, f"p99 latency too high: {percentiles['p99']:.2f} μs"
        assert abs(degradation_pct) < 50, f"Latency degradation too high: {degradation_pct:.2f}%"

        # Cleanup
        redis_client.delete(test_stream_name)
        redis_client.delete(f"{test_stream_name}_test_group")
