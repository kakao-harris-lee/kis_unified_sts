"""RL Inference Latency Benchmarks

Measures RL model inference performance to ensure compliance with the 1-minute
candle interval constraint. The critical SLA is p99 latency < 60 seconds.

**Performance Requirements:**
- Single inference: Fast enough for real-time trading decisions
- Batch inference: Efficient processing of multiple predictions
- p99 latency: Must be < 60,000ms (1-minute candle interval)
- Cold start: Model loading time acceptable (one-time cost)
- Warm inference: Subsequent predictions should be fast (<100ms target)

**Benchmark Scenarios:**
1. Single inference latency (baseline)
2. Batch inference (10 predictions)
3. Latency percentiles (p50, p95, p99) over 100 iterations
4. Cold start vs warm inference comparison

**Critical Constraint:**
RL inference p99 must be < 60 seconds to fit within 1-minute candle intervals.
Failing this constraint means the model cannot be used for real-time trading.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

# Configure logging for benchmarks
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _create_sample_observation(n_features: int = 31) -> np.ndarray:
    """Create a sample observation for inference testing.

    Args:
        n_features: Total feature count (default 31: 25 market + 3 position + 3 time)

    Returns:
        Random observation array of shape (n_features,)
    """
    np.random.seed(42)
    return np.random.randn(n_features).astype(np.float32)


def _create_batch_observations(batch_size: int, n_features: int = 31) -> np.ndarray:
    """Create a batch of observations for batch inference testing.

    Args:
        batch_size: Number of observations in batch
        n_features: Total feature count

    Returns:
        Random observation array of shape (batch_size, n_features)
    """
    np.random.seed(42)
    return np.random.randn(batch_size, n_features).astype(np.float32)


def _create_action_masks() -> list[bool]:
    """Create action masks for MaskablePPO inference.

    Returns:
        List of 5 boolean values (one per action: LONG_ENTRY, LONG_EXIT, SHORT_ENTRY, SHORT_EXIT, HOLD)
    """
    # All actions enabled by default
    return [True, True, True, True, True]


def _benchmark_single(func, *args, iterations: int = 1) -> float:
    """Run a benchmark function and return time in milliseconds.

    Args:
        func: Function to benchmark
        args: Arguments to pass to func
        iterations: Number of iterations to run

    Returns:
        Average time per iteration in milliseconds
    """
    start = time.perf_counter()
    for _ in range(iterations):
        func(*args)
    end = time.perf_counter()

    total_time_ms = (end - start) * 1000.0  # Convert to milliseconds
    return total_time_ms / iterations


def _compute_percentiles(latencies: list[float]) -> dict[str, float]:
    """Compute latency percentiles (p50, p95, p99).

    Args:
        latencies: List of latency measurements in milliseconds

    Returns:
        Dictionary with p50, p95, p99 keys
    """
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "p50": sorted_latencies[int(n * 0.50)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[min(int(n * 0.99), n - 1)],
    }


def _load_model_for_benchmark(model_path: str, device: str = "cpu") -> Any | None:
    """Load RL model for benchmarking.

    Args:
        model_path: Path to model file
        device: Device to load model on (cpu/cuda)

    Returns:
        Loaded model or None if loading fails
    """
    try:
        from sb3_contrib import MaskablePPO

        if not Path(model_path).exists():
            logger.warning(f"Model not found: {model_path}")
            return None

        model = MaskablePPO.load(model_path, device=device)
        return model
    except ImportError:
        logger.warning("sb3-contrib not installed, skipping RL inference benchmarks")
        return None
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return None


class TestBenchmarkInfrastructure:
    """Test benchmark infrastructure without requiring RL model."""

    def test_benchmark_helper_functions(self):
        """Verify benchmark helper functions work correctly."""
        # Test observation creation
        obs = _create_sample_observation(31)
        assert obs.shape == (31,)
        assert obs.dtype == np.float32

        # Test batch observation creation
        batch_obs = _create_batch_observations(10, 31)
        assert batch_obs.shape == (10, 31)
        assert batch_obs.dtype == np.float32

        # Test action masks
        masks = _create_action_masks()
        assert len(masks) == 5
        assert all(isinstance(m, bool) for m in masks)

        # Test percentile computation
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        percentiles = _compute_percentiles(latencies)
        assert "p50" in percentiles
        assert "p95" in percentiles
        assert "p99" in percentiles
        # p50 of [10..100] is at index int(10 * 0.50) = 5 → 60.0
        assert percentiles["p50"] == 60.0
        # p95 is at index int(10 * 0.95) = 9 → 100.0
        assert percentiles["p95"] == 100.0

        print(
            f"\n{'=' * 80}\n"
            f"Benchmark Infrastructure Test\n"
            f"{'=' * 80}\n"
            f"✓ Observation creation works\n"
            f"✓ Batch observation creation works\n"
            f"✓ Action mask creation works\n"
            f"✓ Percentile computation works\n"
            f"{'=' * 80}\n"
        )


class TestRLInferenceLatency:
    """RL model inference latency benchmarks.

    These tests measure the performance of RL model inference to ensure
    compliance with the 1-minute candle interval constraint (p99 < 60s).
    """

    @pytest.fixture
    def model_path(self) -> str:
        """Get model path from config or use default."""
        default_path = "models/futures/rl/mppo_best/best_model.zip"
        # Check environment variable override
        import os

        return os.getenv("RL_MPPO_MODEL_PATH", default_path)

    @pytest.fixture
    def device(self) -> str:
        """Get device for model inference (cpu/cuda)."""
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @pytest.fixture
    def model(self, model_path: str, device: str) -> Any | None:
        """Load RL model for testing."""
        return _load_model_for_benchmark(model_path, device)

    def test_single_inference_latency(self, model, device):
        """Benchmark single inference latency (baseline).

        Expected: < 100ms for CPU, < 50ms for GPU
        This is the typical latency for a single prediction in production.
        """
        if model is None:
            pytest.skip("RL model not available for benchmarking")

        obs = _create_sample_observation()
        action_masks = _create_action_masks()
        iterations = 100

        def _run_inference():
            model.predict(obs, action_masks=action_masks, deterministic=True)

        # Warmup
        for _ in range(10):
            _run_inference()

        # Benchmark
        avg_latency_ms = _benchmark_single(_run_inference, iterations=iterations)

        print(
            f"\n{'=' * 80}\n"
            f"Single Inference Latency Benchmark\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"Iterations: {iterations}\n"
            f"Average latency: {avg_latency_ms:.2f}ms\n"
            f"{'=' * 80}\n"
        )

        # Assertions
        if device == "cuda":
            assert (
                avg_latency_ms < 50.0
            ), f"GPU inference too slow: {avg_latency_ms:.2f}ms (expected < 50ms)"
        else:
            assert (
                avg_latency_ms < 100.0
            ), f"CPU inference too slow: {avg_latency_ms:.2f}ms (expected < 100ms)"

    def test_batch_inference_latency(self, model, device):
        """Benchmark batch inference latency (10 predictions).

        Expected: Batch processing should be more efficient than 10x single inference
        due to vectorization and reduced overhead.
        """
        if model is None:
            pytest.skip("RL model not available for benchmarking")

        batch_size = 10
        obs_batch = _create_batch_observations(batch_size)
        action_masks_batch = [_create_action_masks() for _ in range(batch_size)]
        iterations = 50

        def _run_batch_inference():
            for i in range(batch_size):
                model.predict(
                    obs_batch[i], action_masks=action_masks_batch[i], deterministic=True
                )

        # Warmup
        for _ in range(5):
            _run_batch_inference()

        # Benchmark
        avg_latency_ms = _benchmark_single(_run_batch_inference, iterations=iterations)
        per_prediction_ms = avg_latency_ms / batch_size

        print(
            f"\n{'=' * 80}\n"
            f"Batch Inference Latency Benchmark (batch_size={batch_size})\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"Iterations: {iterations}\n"
            f"Total batch latency: {avg_latency_ms:.2f}ms\n"
            f"Per-prediction latency: {per_prediction_ms:.2f}ms\n"
            f"{'=' * 80}\n"
        )

        # Assertions
        if device == "cuda":
            assert (
                per_prediction_ms < 50.0
            ), f"GPU batch inference too slow: {per_prediction_ms:.2f}ms/prediction"
        else:
            assert (
                per_prediction_ms < 100.0
            ), f"CPU batch inference too slow: {per_prediction_ms:.2f}ms/prediction"

    def test_latency_percentiles(self, model, device):
        """Measure p50, p95, p99 latency over 100 iterations.

        **Critical SLA: p99 latency must be < 60,000ms (1-minute candle interval)**

        This is the most important benchmark as it validates the hard constraint
        that RL inference must complete within the 1-minute candle interval.
        """
        if model is None:
            pytest.skip("RL model not available for benchmarking")

        obs = _create_sample_observation()
        action_masks = _create_action_masks()
        iterations = 100

        # Warmup
        for _ in range(10):
            model.predict(obs, action_masks=action_masks, deterministic=True)

        # Collect individual latencies
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            model.predict(obs, action_masks=action_masks, deterministic=True)
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)  # Convert to milliseconds

        # Compute percentiles
        percentiles = _compute_percentiles(latencies)

        print(
            f"\n{'=' * 80}\n"
            f"Latency Percentiles (n={iterations})\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"p50 (median): {percentiles['p50']:.2f}ms\n"
            f"p95: {percentiles['p95']:.2f}ms\n"
            f"p99: {percentiles['p99']:.2f}ms\n"
            f"{'=' * 80}\n"
            f"SLA Compliance:\n"
            f"  ✓ p99 < 60,000ms (1-min candle): {percentiles['p99']:.2f}ms\n"
            f"{'=' * 80}\n"
        )

        # Critical SLA assertion
        assert (
            percentiles["p99"] < 60_000.0
        ), f"CRITICAL: p99 latency {percentiles['p99']:.2f}ms exceeds 60-second candle interval!"

        # Performance targets (non-critical)
        if device == "cuda":
            assert (
                percentiles["p95"] < 50.0
            ), f"GPU p95 latency too high: {percentiles['p95']:.2f}ms"
        else:
            assert (
                percentiles["p95"] < 100.0
            ), f"CPU p95 latency too high: {percentiles['p95']:.2f}ms"

    def test_cold_start_latency(self, model_path: str, device: str):
        """Measure cold start latency (model loading + first inference).

        Cold start includes:
        1. Model loading from disk
        2. Model initialization
        3. First inference (may include JIT compilation, cache warmup, etc.)

        This is a one-time cost at system startup, so higher latency is acceptable.
        """
        if not Path(model_path).exists():
            pytest.skip(f"Model not found: {model_path}")

        obs = _create_sample_observation()
        action_masks = _create_action_masks()

        # Measure cold start (model loading + first inference)
        start = time.perf_counter()
        model = _load_model_for_benchmark(model_path, device)
        if model is None:
            pytest.skip("Failed to load model for cold start benchmark")

        model.predict(obs, action_masks=action_masks, deterministic=True)
        end = time.perf_counter()

        cold_start_latency_ms = (end - start) * 1000.0

        print(
            f"\n{'=' * 80}\n"
            f"Cold Start Latency Benchmark\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"Model path: {model_path}\n"
            f"Cold start latency: {cold_start_latency_ms:.2f}ms\n"
            f"  (includes model loading + first inference)\n"
            f"{'=' * 80}\n"
        )

        # Cold start should complete within reasonable time (< 30 seconds)
        assert (
            cold_start_latency_ms < 30_000.0
        ), f"Cold start too slow: {cold_start_latency_ms:.2f}ms (expected < 30s)"

    def test_warm_inference_latency(self, model, device):
        """Measure warm inference latency (cached model, subsequent inferences).

        Warm inference represents the typical production scenario where the model
        is already loaded and we're making subsequent predictions.

        Target: < 50ms for optimal trading performance
        """
        if model is None:
            pytest.skip("RL model not available for benchmarking")

        obs = _create_sample_observation()
        action_masks = _create_action_masks()

        # Warmup (10 inferences to ensure caches are populated)
        for _ in range(10):
            model.predict(obs, action_masks=action_masks, deterministic=True)

        # Measure warm inference (100 iterations)
        iterations = 100
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            model.predict(obs, action_masks=action_masks, deterministic=True)
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)

        avg_latency_ms = sum(latencies) / len(latencies)
        min_latency_ms = min(latencies)
        max_latency_ms = max(latencies)

        print(
            f"\n{'=' * 80}\n"
            f"Warm Inference Latency Benchmark (n={iterations})\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"Average: {avg_latency_ms:.2f}ms\n"
            f"Min: {min_latency_ms:.2f}ms\n"
            f"Max: {max_latency_ms:.2f}ms\n"
            f"{'=' * 80}\n"
        )

        # Performance targets
        if device == "cuda":
            assert (
                avg_latency_ms < 50.0
            ), f"GPU warm inference too slow: {avg_latency_ms:.2f}ms (target < 50ms)"
        else:
            assert (
                avg_latency_ms < 100.0
            ), f"CPU warm inference too slow: {avg_latency_ms:.2f}ms (target < 100ms)"

    def test_inference_consistency(self, model, device):
        """Verify inference latency consistency (low variance).

        High variance in inference latency can cause unpredictable trading behavior.
        This test ensures that inference times are consistent.
        """
        if model is None:
            pytest.skip("RL model not available for benchmarking")

        obs = _create_sample_observation()
        action_masks = _create_action_masks()

        # Warmup
        for _ in range(10):
            model.predict(obs, action_masks=action_masks, deterministic=True)

        # Collect latencies
        iterations = 100
        latencies = []
        for _ in range(iterations):
            start = time.perf_counter()
            model.predict(obs, action_masks=action_masks, deterministic=True)
            end = time.perf_counter()
            latencies.append((end - start) * 1000.0)

        # Compute statistics
        mean = np.mean(latencies)
        std = np.std(latencies)
        cv = (std / mean) * 100.0  # Coefficient of variation (%)

        print(
            f"\n{'=' * 80}\n"
            f"Inference Consistency Benchmark (n={iterations})\n"
            f"{'=' * 80}\n"
            f"Device: {device.upper()}\n"
            f"Mean: {mean:.2f}ms\n"
            f"Std Dev: {std:.2f}ms\n"
            f"Coefficient of Variation: {cv:.1f}%\n"
            f"{'=' * 80}\n"
        )

        # Consistency check: CV should be < 20%
        assert cv < 20.0, f"Inference latency too variable: CV={cv:.1f}% (expected < 20%)"
