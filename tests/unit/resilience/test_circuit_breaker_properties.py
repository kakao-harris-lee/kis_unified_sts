"""Property-based tests for CircuitBreaker using Hypothesis."""

import time
from hypothesis import given, settings, strategies as st, assume


from shared.resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState


class TestCircuitBreakerProperties:
    """Property-based tests for CircuitBreaker."""

    @given(
        failure_threshold=st.integers(min_value=1, max_value=100),
        reset_timeout=st.floats(min_value=0.01, max_value=60.0),
        half_open_max_calls=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_config_round_trip(
        self, failure_threshold: int, reset_timeout: float, half_open_max_calls: int
    ):
        """Property: Config values should be preserved after initialization."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            half_open_max_calls=half_open_max_calls,
        )

        assert breaker.failure_threshold == failure_threshold
        assert breaker.reset_timeout == reset_timeout
        assert breaker.half_open_max_calls == half_open_max_calls

    @given(failure_count=st.integers(min_value=0, max_value=50))
    @settings(max_examples=50)
    def test_opens_at_threshold(self, failure_count: int):
        """Property: Circuit opens exactly when failure count reaches threshold."""
        threshold = 5
        breaker = CircuitBreaker(name="test", failure_threshold=threshold)

        for _ in range(failure_count):
            breaker.record_failure()

        if failure_count >= threshold:
            assert breaker.state == CircuitState.OPEN
        else:
            assert breaker.state == CircuitState.CLOSED

    @given(
        failures_before=st.integers(min_value=0, max_value=4),
        successes=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50)
    def test_success_resets_failure_count(
        self, failures_before: int, _successes: int
    ):
        """Property: Success in CLOSED state resets failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Record some failures (not enough to open)
        for _ in range(failures_before):
            breaker.record_failure()

        # Record success
        breaker.record_success()

        # Now we need threshold failures to open (failure count was reset)
        for _ in range(4):  # Not enough to reach threshold=5
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED

    @given(success_count=st.integers(min_value=0, max_value=10))
    @settings(max_examples=30)
    def test_success_count_tracked(self, success_count: int):
        """Property: Success count is accurately tracked."""
        breaker = CircuitBreaker(name="test")

        for _ in range(success_count):
            breaker.record_success()

        status = breaker.get_status()
        assert status["success_count"] == success_count

    @given(
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="-_"
        ))
    )
    @settings(max_examples=30)
    def test_name_preserved(self, name: str):
        """Property: Name is preserved in status."""
        assume(name.strip())  # Skip empty/whitespace names
        breaker = CircuitBreaker(name=name)
        status = breaker.get_status()
        assert status["name"] == name

    @given(
        failures=st.lists(st.just("F"), min_size=0, max_size=20),
        successes=st.lists(st.just("S"), min_size=0, max_size=20),
    )
    @settings(max_examples=50)
    def test_state_invariants(self, failures: list, successes: list):
        """Property: State is always valid after any sequence of operations."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        # Interleave failures and successes randomly
        operations = failures + successes
        import random
        random.shuffle(operations)

        for op in operations:
            if op == "F":
                breaker.record_failure()
            else:
                breaker.record_success()

        # State should always be valid
        assert breaker.state in (
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        )

        # Status should be consistent
        status = breaker.get_status()
        assert status["state"] == breaker.state.value
        assert status["failure_count"] >= 0
        assert status["success_count"] >= 0


class TestCircuitBreakerConfigProperties:
    """Property-based tests for CircuitBreakerConfig."""

    @given(
        failure_threshold=st.integers(min_value=1, max_value=100),
        reset_timeout=st.floats(min_value=0.1, max_value=3600.0),
        half_open_max_calls=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=50)
    def test_config_values_preserved(
        self,
        failure_threshold: int,
        reset_timeout: float,
        half_open_max_calls: int,
    ):
        """Property: Config dataclass preserves all values."""
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            half_open_max_calls=half_open_max_calls,
        )

        assert config.failure_threshold == failure_threshold
        assert config.reset_timeout == reset_timeout
        assert config.half_open_max_calls == half_open_max_calls

    @given(reset_timeout=st.floats(min_value=0.1, max_value=3600.0))
    @settings(max_examples=30)
    def test_recovery_timeout_alias(self, reset_timeout: float):
        """Property: recovery_timeout_seconds is alias for reset_timeout."""
        config = CircuitBreakerConfig(reset_timeout=reset_timeout)
        assert config.recovery_timeout_seconds == config.reset_timeout

    @given(
        failure_threshold=st.integers(min_value=1, max_value=100),
        reset_timeout=st.floats(min_value=0.1, max_value=3600.0),
        half_open_max_calls=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=30)
    def test_config_initializes_breaker(
        self,
        failure_threshold: int,
        reset_timeout: float,
        half_open_max_calls: int,
    ):
        """Property: Config can be used to initialize a breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
            half_open_max_calls=half_open_max_calls,
        )

        breaker = CircuitBreaker(name="test", config=config)

        assert breaker.failure_threshold == failure_threshold
        assert breaker.reset_timeout == reset_timeout
        assert breaker.half_open_max_calls == half_open_max_calls


class TestCircuitBreakerResetTimeProperties:
    """Property-based tests for reset time calculations."""

    @given(
        reset_timeout=st.floats(min_value=1.0, max_value=100.0),
    )
    @settings(max_examples=20)
    def test_reset_time_bounded(self, reset_timeout: float):
        """Property: Reset time is always between 0 and reset_timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=reset_timeout,
        )

        breaker.record_failure()  # Open the circuit

        reset_time = breaker.get_reset_time()
        assert 0 <= reset_time <= reset_timeout

    def test_reset_time_decreases(self):
        """Property: Reset time decreases over time."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=1,
            reset_timeout=5.0,
        )

        breaker.record_failure()
        t1 = breaker.get_reset_time()

        time.sleep(0.1)
        t2 = breaker.get_reset_time()

        assert t2 < t1

    def test_reset_time_zero_when_closed(self):
        """Property: Reset time is 0 when circuit is closed."""
        breaker = CircuitBreaker(name="test")
        assert breaker.get_reset_time() == 0.0


class TestCircuitBreakerThreadSafety:
    """Property-based tests for thread safety settings."""

    @given(thread_safe=st.booleans())
    @settings(max_examples=10)
    def test_thread_safe_option(self, thread_safe: bool):
        """Property: thread_safe option controls lock creation."""
        breaker = CircuitBreaker(name="test", thread_safe=thread_safe)

        if thread_safe:
            assert breaker._lock is not None
        else:
            assert breaker._lock is None

        # Should work regardless of thread_safe setting
        breaker.record_failure()
        breaker.record_success()
        _ = breaker.state
