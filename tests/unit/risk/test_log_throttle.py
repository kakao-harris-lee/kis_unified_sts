"""Unit tests for shared.risk.log_throttle (per-reason log throttling).

Both the stock M4-P market-risk-gate shadow log
(``services/stock_strategy/daemon_market_risk.py``) and the futures
decision-engine shadow-gate log (``services/decision_engine/main.py``)
consume this helper so they converge on the same per-reason (not
single-global-timestamp) throttling behavior.
"""

from __future__ import annotations

import pytest

from shared.risk.log_throttle import (
    ReasonLogThrottle,
    gate_log_throttle_key,
    setup_eval_reason_kind,
    setup_eval_throttle_key,
)


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


def test_key_namespaces_band_and_reason_so_they_never_collide():
    """A fail-open ``reason`` that happens to read the same as a band label
    must not share a throttle slot with that band (namespacing fix)."""
    band_key = gate_log_throttle_key(band="HIGH", reason="market_risk band=HIGH")
    reason_key = gate_log_throttle_key(band=None, reason="HIGH")

    assert band_key != reason_key
    assert band_key == "band:HIGH"
    assert reason_key == "reason:HIGH"


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


# ---------------------------------------------------------------------------
# setup_eval keys — structural, measurements stripped
# ---------------------------------------------------------------------------


class TestSetupEvalThrottleKey:
    """Setup reject reasons embed live measurements; the key must not."""

    @pytest.mark.parametrize(
        "reason, expected_kind",
        [
            ("not_extreme(z=+0.42,need±1.8)", "not_extreme"),
            ("vol_below_gate(0.85<0.9)", "vol_below_gate"),
            ("outside_time_window(297m∉[10,60])", "outside_time_window"),
            ("low_confidence(0.55<0.6)", "low_confidence"),
            # No measurement at all — the whole reason is the kind.
            ("no_atr", "no_atr"),
            ("no_vwap", "no_vwap"),
            ("no_market_context", "no_market_context"),
        ],
    )
    def test_reason_kind_strips_measurements(
        self, reason: str, expected_kind: str
    ) -> None:
        assert setup_eval_reason_kind(reason) == expected_kind

    def test_changing_measurements_share_one_key(self) -> None:
        """The whole point: a moving z value is the SAME cause."""
        keys = {
            setup_eval_throttle_key("setup_d_vwap_reversion", "reject", reason)
            for reason in (
                "not_extreme(z=+0.42,need±1.8)",
                "not_extreme(z=+0.91,need±1.8)",
                "not_extreme(z=-1.55,need±1.8)",
            )
        }
        assert len(keys) == 1

    def test_different_causes_do_not_collide(self) -> None:
        assert setup_eval_throttle_key(
            "setup_d_vwap_reversion", "reject", "not_extreme(z=+0.4,need±1.8)"
        ) != setup_eval_throttle_key(
            "setup_d_vwap_reversion", "reject", "vol_below_gate(0.85<0.9)"
        )

    def test_setup_name_and_outcome_are_part_of_the_key(self) -> None:
        assert setup_eval_throttle_key(
            "setup_a_gap_reversion", "reject", "no_atr"
        ) != setup_eval_throttle_key("setup_d_vwap_reversion", "reject", "no_atr")
        assert setup_eval_throttle_key(
            "setup_d_vwap_reversion", "reject", "short"
        ) != setup_eval_throttle_key("setup_d_vwap_reversion", "fired", "short")

    def test_namespaced_away_from_gate_keys(self) -> None:
        """A shared ReasonLogThrottle cache must not mix the two key families."""
        assert setup_eval_throttle_key("s", "reject", "HIGH").startswith("setup_eval:")
        assert not gate_log_throttle_key(band="HIGH", reason="x").startswith(
            "setup_eval:"
        )

    def test_throttle_actually_throttles_across_changing_numbers(self) -> None:
        """End-to-end with ReasonLogThrottle: one log, not one per tick."""
        throttle = ReasonLogThrottle(interval_seconds=300.0)
        allowed = [
            throttle.should_log(
                setup_eval_throttle_key(
                    "setup_d_vwap_reversion", "reject", f"not_extreme(z={z},need±1.8)"
                ),
                now,
            )
            for now, z in enumerate(("+0.10", "+0.42", "+0.91", "+1.55"))
        ]
        assert allowed == [True, False, False, False]

    def test_non_string_reason_is_coerced_not_raised(self) -> None:
        """Observability must not raise on the trading path.

        An adapter can pass a not-yet-stringified signal attribute; the old
        f-string key accepted anything, so this one must too.
        """

        class _NotAString:
            def __str__(self) -> str:
                return "direction_blocked(long:BULL_STRONG)"

        assert setup_eval_reason_kind(_NotAString()) == "direction_blocked"
        assert setup_eval_throttle_key("s", "reject", _NotAString()).endswith(
            "direction_blocked"
        )
