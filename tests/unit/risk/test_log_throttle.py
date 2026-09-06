"""Unit tests for shared.risk.log_throttle (per-reason log throttling).

Both the stock M4-P market-risk-gate shadow log
(``services/stock_strategy/daemon_market_risk.py``) and the futures
decision-engine shadow-gate log (``services/decision_engine/main.py``)
consume this helper so they converge on the same per-reason (not
single-global-timestamp) throttling behavior.
"""

from __future__ import annotations

from shared.risk.log_throttle import ReasonLogThrottle, gate_log_throttle_key


def test_first_observation_for_a_reason_always_logs():
    throttle = ReasonLogThrottle(interval_seconds=300.0)

    assert throttle.should_log("HIGH", now=1000.0) is True


def test_repeated_observation_within_interval_is_suppressed():
    throttle = ReasonLogThrottle(interval_seconds=300.0)

    assert throttle.should_log("HIGH", now=1000.0) is True
    assert throttle.should_log("HIGH", now=1000.0 + 299.0) is False


def test_observation_after_interval_elapses_logs_again():
    throttle = ReasonLogThrottle(interval_seconds=300.0)

    assert throttle.should_log("HIGH", now=1000.0) is True
    assert throttle.should_log("HIGH", now=1000.0 + 300.0) is True


def test_throttling_is_independent_per_reason():
    """Different reasons must not suppress each other (per-reason cache)."""
    throttle = ReasonLogThrottle(interval_seconds=300.0)

    assert throttle.should_log("HIGH", now=1000.0) is True
    # A distinct reason logs immediately even though HIGH just logged.
    assert throttle.should_log("CRITICAL", now=1000.0) is True
    # HIGH itself is still throttled.
    assert throttle.should_log("HIGH", now=1000.1) is False


# ---------------------------------------------------------------------------
# gate_log_throttle_key (O14-③ review finding 5): the throttle key must be
# derived from structural fields (band, side) — never from the free-text
# ``reason`` string, which embeds ``score`` and would reset the throttle on
# every gate refresh (a 30-min cron today, but that cadence is config).
# ---------------------------------------------------------------------------


def test_key_uses_band_not_the_score_carrying_reason_string():
    key_low_score = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=74.2 rule=block_new_long"
    )
    key_high_score = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=91.0 rule=block_new_long"
    )

    assert key_low_score == key_high_score


def test_key_falls_back_to_reason_when_band_is_none():
    """Fail-open paths (missing hash, gate off) carry no band."""
    key = gate_log_throttle_key(band=None, reason="fail_open:missing_hash")

    assert "fail_open:missing_hash" in key


def test_key_distinguishes_same_band_different_side():
    """HIGH blocking new longs vs. HIGH allowing shorts at reduced size are
    structurally different verdicts and must not share a throttle slot."""
    long_key = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=74.2 rule=x", side="long"
    )
    short_key = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=74.2 rule=x", side="short"
    )

    assert long_key != short_key


def test_key_is_stable_without_a_side_argument():
    """Stock is long-only and calls this with no side — must not crash and
    must stay stable across repeated calls with the same inputs."""
    key1 = gate_log_throttle_key(
        band="ELEVATED",
        reason="market_risk band=ELEVATED score=60.0 rule=min_confidence:HIGH",
    )
    key2 = gate_log_throttle_key(
        band="ELEVATED",
        reason="market_risk band=ELEVATED score=61.5 rule=min_confidence:HIGH",
    )

    assert key1 == key2


def test_key_end_to_end_with_the_throttle():
    """Same band, two different scores, within the interval: logs once."""
    throttle = ReasonLogThrottle(interval_seconds=300.0)
    key1 = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=74.2 rule=x", side="long"
    )
    key2 = gate_log_throttle_key(
        band="HIGH", reason="market_risk band=HIGH score=91.0 rule=x", side="long"
    )

    assert throttle.should_log(key1, now=1000.0) is True
    assert throttle.should_log(key2, now=1000.1) is False

    # Two bands log independently.
    key_critical = gate_log_throttle_key(
        band="CRITICAL",
        reason="market_risk band=CRITICAL score=95.0 rule=y",
        side="long",
    )
    assert throttle.should_log(key_critical, now=1000.1) is True

    # A fail-open decision (band None) still throttles by reason.
    key_fail_open = gate_log_throttle_key(band=None, reason="fail_open:missing_hash")
    assert throttle.should_log(key_fail_open, now=1000.2) is True
    assert throttle.should_log(key_fail_open, now=1000.3) is False
