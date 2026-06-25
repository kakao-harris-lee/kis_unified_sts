"""Hermetic tests for the conviction-hold conjunction gate (THESIS C).

The gate is a pure filter over a plain value object — no Redis, no clock, no
data. Each test pins one arm of the conjunction. Long/short symmetry is asserted
explicitly. The gate ships disabled (the conjunction is falsified on the clean
window) so these tests guard the *mechanics*, not a profitability claim.
"""

import datetime as dt

import pytest

from shared.strategy.gates.conviction_hold_gate import (
    ConvictionHoldConfig,
    ConvictionHoldGate,
    ConvictionHoldInputs,
    conviction_hold_cfg_from_yaml,
)

TS = dt.datetime(2026, 3, 2, 10, 0)


def _cfg(**kw) -> ConvictionHoldConfig:
    return ConvictionHoldConfig(**kw)


def _aligned_long(**over) -> ConvictionHoldInputs:
    """A fully-aligned LONG conjunction (all arms pass)."""
    base = {
        "morning_disp_pct": 0.6,
        "morning_efficiency": 0.20,
        "mfi_state": "BULL_STRONG",
        "semi_leadership_pct": 1.5,
        "llm_bias": None,
    }
    base.update(over)
    return ConvictionHoldInputs(**base)


def _aligned_short(**over) -> ConvictionHoldInputs:
    base = {
        "morning_disp_pct": -0.6,
        "morning_efficiency": 0.20,
        "mfi_state": "BEAR_STRONG",
        "semi_leadership_pct": -1.5,
        "llm_bias": None,
    }
    base.update(over)
    return ConvictionHoldInputs(**base)


# --------------------------------------------------------------------------- #
# Full conjunction arms
# --------------------------------------------------------------------------- #
def test_arms_long_when_all_aligned():
    g = ConvictionHoldGate(_cfg())
    arm, direction, reason, score = g.evaluate(TS, _aligned_long())
    assert arm is True
    assert direction == "long"
    assert reason == "armed"
    assert 0.0 < score <= 1.0


def test_arms_short_when_all_aligned_symmetric():
    g = ConvictionHoldGate(_cfg())
    arm, direction, reason, score = g.evaluate(TS, _aligned_short())
    assert arm is True
    assert direction == "short"
    assert reason == "armed"
    assert 0.0 < score <= 1.0


# --------------------------------------------------------------------------- #
# Each arm rejects independently (long + symmetric short)
# --------------------------------------------------------------------------- #
def test_morning_displacement_too_small_blocks():
    g = ConvictionHoldGate(_cfg(min_morning_disp_pct=0.30))
    arm, direction, reason, _ = g.evaluate(TS, _aligned_long(morning_disp_pct=0.10))
    assert arm is False
    assert direction == "flat"
    assert "morning_disp" in reason


def test_morning_efficiency_too_low_blocks():
    g = ConvictionHoldGate(_cfg(min_morning_efficiency=0.10))
    arm, _, reason, _ = g.evaluate(TS, _aligned_long(morning_efficiency=0.05))
    assert arm is False
    assert "morning_eff" in reason


def test_mfi_not_strong_blocks_long():
    g = ConvictionHoldGate(_cfg(require_mfi_strong=True))
    arm, _, reason, _ = g.evaluate(TS, _aligned_long(mfi_state="BULL_MODERATE"))
    assert arm is False
    assert "mfi_state" in reason


def test_mfi_not_strong_blocks_short():
    g = ConvictionHoldGate(_cfg(require_mfi_strong=True))
    arm, _, reason, _ = g.evaluate(TS, _aligned_short(mfi_state="SIDEWAYS_DOWN"))
    assert arm is False
    assert "mfi_state" in reason


def test_semi_leadership_insufficient_blocks_long():
    g = ConvictionHoldGate(_cfg(min_semi_leadership_pct=0.50))
    arm, _, reason, _ = g.evaluate(TS, _aligned_long(semi_leadership_pct=0.20))
    assert arm is False
    assert "semi_lead" in reason


def test_semi_leadership_wrong_sign_blocks_short():
    # short needs semi <= -0.50; +1.0 must block
    g = ConvictionHoldGate(_cfg(min_semi_leadership_pct=0.50))
    arm, _, reason, _ = g.evaluate(TS, _aligned_short(semi_leadership_pct=1.0))
    assert arm is False
    assert "semi_lead" in reason


# --------------------------------------------------------------------------- #
# MFI-strong relaxed
# --------------------------------------------------------------------------- #
def test_mfi_strong_not_required_allows_non_strong_state():
    g = ConvictionHoldGate(_cfg(require_mfi_strong=False))
    arm, direction, reason, _ = g.evaluate(TS, _aligned_long(mfi_state="BULL_MODERATE"))
    assert arm is True
    assert direction == "long"


def test_mfi_state_missing_blocks_only_when_required():
    g_req = ConvictionHoldGate(_cfg(require_mfi_strong=True))
    arm, _, reason, _ = g_req.evaluate(TS, _aligned_long(mfi_state=None))
    assert arm is False
    assert reason == "missing_mfi_state"

    g_norq = ConvictionHoldGate(_cfg(require_mfi_strong=False))
    arm2, direction2, _, _ = g_norq.evaluate(TS, _aligned_long(mfi_state=None))
    assert arm2 is True
    assert direction2 == "long"


# --------------------------------------------------------------------------- #
# Optional LLM-bias arm: PERMISSIVE on missing (§9)
# --------------------------------------------------------------------------- #
def test_llm_bias_missing_is_permissive_by_default():
    g = ConvictionHoldGate(_cfg(use_llm_bias=True, permissive_on_missing=True))
    arm, direction, _, _ = g.evaluate(TS, _aligned_long(llm_bias=None))
    assert arm is True
    assert direction == "long"


def test_llm_bias_flat_is_permissive():
    g = ConvictionHoldGate(_cfg(use_llm_bias=True, permissive_on_missing=True))
    arm, _, _, _ = g.evaluate(TS, _aligned_long(llm_bias="flat"))
    assert arm is True


def test_llm_bias_missing_blocks_when_non_permissive():
    g = ConvictionHoldGate(_cfg(use_llm_bias=True, permissive_on_missing=False))
    arm, _, reason, _ = g.evaluate(TS, _aligned_long(llm_bias=None))
    assert arm is False
    assert "missing_llm_bias" in reason


def test_llm_bias_opposing_blocks():
    g = ConvictionHoldGate(_cfg(use_llm_bias=True))
    arm, _, reason, _ = g.evaluate(TS, _aligned_long(llm_bias="short"))
    assert arm is False
    assert "llm_bias" in reason


def test_llm_bias_agreeing_allows():
    g = ConvictionHoldGate(_cfg(use_llm_bias=True))
    arm, direction, _, _ = g.evaluate(TS, _aligned_long(llm_bias="long"))
    assert arm is True
    assert direction == "long"


def test_llm_bias_ignored_when_disabled():
    # opposing bias must NOT block when the arm is off
    g = ConvictionHoldGate(_cfg(use_llm_bias=False))
    arm, direction, _, _ = g.evaluate(TS, _aligned_long(llm_bias="short"))
    assert arm is True
    assert direction == "long"


# --------------------------------------------------------------------------- #
# Missing required structural inputs => flat
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "field,expected",
    [
        ("morning_disp_pct", "missing_morning_structure"),
        ("morning_efficiency", "missing_morning_structure"),
        ("semi_leadership_pct", "missing_semi_leadership"),
    ],
)
def test_missing_required_input_yields_flat(field, expected):
    g = ConvictionHoldGate(_cfg())
    arm, direction, reason, score = g.evaluate(TS, _aligned_long(**{field: None}))
    assert arm is False
    assert direction == "flat"
    assert reason == expected
    assert score == 0.0


def test_no_morning_direction_is_flat():
    g = ConvictionHoldGate(_cfg())
    arm, direction, reason, _ = g.evaluate(TS, _aligned_long(morning_disp_pct=0.0))
    assert arm is False
    assert direction == "flat"
    assert reason == "no_morning_direction"


def test_short_disabled_blocks_short_candidate():
    g = ConvictionHoldGate(_cfg(allow_short=False))
    arm, direction, reason, _ = g.evaluate(TS, _aligned_short())
    assert arm is False
    assert direction == "flat"
    assert reason == "short_disabled"


# --------------------------------------------------------------------------- #
# YAML loader
# --------------------------------------------------------------------------- #
def test_cfg_from_yaml_none_when_disabled():
    assert conviction_hold_cfg_from_yaml(None) is None
    assert conviction_hold_cfg_from_yaml({}) is None
    assert conviction_hold_cfg_from_yaml({"enabled": False}) is None


def test_cfg_from_yaml_parses_fields():
    cfg = conviction_hold_cfg_from_yaml(
        {
            "enabled": True,
            "min_morning_disp_pct": 0.45,
            "min_morning_efficiency": 0.15,
            "require_mfi_strong": False,
            "min_semi_leadership_pct": 0.80,
            "use_llm_bias": True,
            "permissive_on_missing": False,
            "decision_hour": 11,
            "decision_minute": 30,
            "allow_short": False,
        }
    )
    assert cfg is not None
    assert cfg.min_morning_disp_pct == 0.45
    assert cfg.min_morning_efficiency == 0.15
    assert cfg.require_mfi_strong is False
    assert cfg.min_semi_leadership_pct == 0.80
    assert cfg.use_llm_bias is True
    assert cfg.permissive_on_missing is False
    assert cfg.decision_hour == 11
    assert cfg.decision_minute == 30
    assert cfg.allow_short is False


def test_cfg_from_yaml_defaults():
    cfg = conviction_hold_cfg_from_yaml({"enabled": True})
    assert cfg is not None
    assert cfg.min_morning_disp_pct == 0.30
    assert cfg.require_mfi_strong is True
    assert cfg.allow_short is True
