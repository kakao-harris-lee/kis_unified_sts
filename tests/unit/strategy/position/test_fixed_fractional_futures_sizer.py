"""Unit tests for FixedFractionalFuturesSizer.

Test cases:
    (a) Basic risk-budget sizing — clamped to max_position_size.
    (b) Zero stop distance — returns 1 (division-by-zero safeguard).
    (c) Consecutive losses below threshold — size unchanged.
    (d) Consecutive losses equal to threshold — soft-reduce fires.
    (e) Consecutive losses well above threshold — soft-reduce fires.
    (f) Registry lookup — SizerRegistry.get("fixed_fractional_futures") returns class.
    (g) No state_snapshot — no soft-reduce logic applied.
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.execution.contract_spec import ContractSpec
from shared.risk.state import RiskStateSnapshot
from shared.strategy.position.sizers import (
    FixedFractionalFuturesConfig,
    FixedFractionalFuturesSizer,
)
from shared.strategy.registry import SizerRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MINI_SPEC = ContractSpec(
    name="kospi200_mini",
    multiplier_krw_per_point=50_000,
    tick_size_points=0.05,
    tick_value_krw=2_500,
    commission_rate=0.000_03,
    symbol_prefix="A05",
)

DEFAULT_CONFIG = FixedFractionalFuturesConfig(
    max_position_risk_pct=0.015,
    max_position_size=2,
    soft_reduce_threshold=4,
)


def _make_signal(entry: float = 300.0, stop: float = 299.5) -> Signal:
    """Return a minimal Signal with the given entry/stop pair."""
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=entry,
        stop_loss=stop,
        take_profit=entry + 1.0,
        confidence=0.8,
    )


def _make_sizer(
    config: FixedFractionalFuturesConfig | None = None,
    spec: ContractSpec | None = MINI_SPEC,
    state: RiskStateSnapshot | None = None,
) -> FixedFractionalFuturesSizer:
    return FixedFractionalFuturesSizer(
        config=config or DEFAULT_CONFIG,
        contract_spec=spec,
        state_snapshot=state,
    )


# ---------------------------------------------------------------------------
# (a) Basic risk-budget sizing — raw size exceeds cap, clamped to max
# ---------------------------------------------------------------------------


def test_basic_risk_budget_sizing_clamped_to_max():
    """equity=5_000_000, risk_pct=0.015 → 75,000 KRW budget.
    stop_dist=0.5 pts, multiplier=50,000 → 25,000 KRW/contract.
    raw = 75,000 / 25,000 = 3. max_position_size=2 → returns 2.
    """
    signal = _make_signal(entry=300.0, stop=299.5)  # distance = 0.5 pts
    sizer = _make_sizer()
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    assert result == 2


# ---------------------------------------------------------------------------
# (b) Zero stop distance — krw_per_contract = 0, must not divide by zero
# ---------------------------------------------------------------------------


def test_zero_stop_distance_returns_minimum_one():
    """When entry_price == stop_loss the distance is 0.

    We cannot construct a valid Signal with entry == stop (validator rejects
    stop_loss == entry because it becomes 0 after abs difference *but* the
    Signal itself only validates stop_loss > 0).  Simulate the edge case by
    using a very small but non-zero distance and confirm the floor applies,
    then test the krw_per_contract=0 path by passing a spec with multiplier=0.
    """
    # Spec with multiplier=0 drives krw_per_contract to 0.
    zero_mult_spec = ContractSpec(
        name="zero_mult",
        multiplier_krw_per_point=0,
        tick_size_points=0.05,
        tick_value_krw=0,
        commission_rate=0.0,
        symbol_prefix="A99",
    )
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(spec=zero_mult_spec)
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    # krw_per_contract = 0 → denominator clamped to 1.0 → raw=75,000 → clamp to 2
    # But max_position_size=2 so result is 2, still >= 1.
    assert result >= 1


def test_zero_stop_distance_denominator_protection():
    """Force krw_per_contract=0 via multiplier=0 and tiny equity so raw<1."""
    zero_mult_spec = ContractSpec(
        name="zero_mult",
        multiplier_krw_per_point=0,
        tick_size_points=0.05,
        tick_value_krw=0,
        commission_rate=0.0,
        symbol_prefix="A99",
    )
    tiny_config = FixedFractionalFuturesConfig(
        max_position_risk_pct=0.0,  # target_risk_krw = 0 → raw = 0
        max_position_size=2,
        soft_reduce_threshold=4,
    )
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(config=tiny_config, spec=zero_mult_spec)
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    # max(1, int(0)) = 1
    assert result == 1


# ---------------------------------------------------------------------------
# (c) Consecutive losses below threshold — no soft-reduce
# ---------------------------------------------------------------------------


def test_soft_reduce_not_triggered_below_threshold():
    """consecutive_losses = threshold - 1 → size unchanged."""
    state = RiskStateSnapshot(consecutive_losses=3)  # threshold=4
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(state=state)
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    assert result == 2  # same as unconstrained baseline


# ---------------------------------------------------------------------------
# (d) Consecutive losses equal to threshold — soft-reduce fires
# ---------------------------------------------------------------------------


def test_soft_reduce_triggered_at_threshold():
    """consecutive_losses == soft_reduce_threshold → size // 2 (min 1)."""
    state = RiskStateSnapshot(consecutive_losses=4)  # threshold=4
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(state=state)
    # Without reduce: size=2. With reduce: max(1, 2//2)=1.
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    assert result == 1


# ---------------------------------------------------------------------------
# (e) Consecutive losses well above threshold — soft-reduce fires
# ---------------------------------------------------------------------------


def test_soft_reduce_triggered_above_threshold():
    """consecutive_losses >> soft_reduce_threshold → size // 2 applied."""
    state = RiskStateSnapshot(consecutive_losses=10)
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(state=state)
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    assert result == 1  # 2 // 2 = 1


# ---------------------------------------------------------------------------
# (f) Registry lookup
# ---------------------------------------------------------------------------


def test_registry_lookup_returns_class():
    """SizerRegistry.get('fixed_fractional_futures') must return the class."""
    cls = SizerRegistry.get("fixed_fractional_futures")
    assert cls is FixedFractionalFuturesSizer


def test_registry_is_registered():
    assert SizerRegistry.is_registered("fixed_fractional_futures")


# ---------------------------------------------------------------------------
# (g) Without state_snapshot — no soft-reduce logic
# ---------------------------------------------------------------------------


def test_no_state_snapshot_no_soft_reduce():
    """When state_snapshot=None, soft-reduce branch is skipped entirely."""
    signal = _make_signal(entry=300.0, stop=299.5)
    sizer = _make_sizer(state=None)  # no state
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    assert result == 2  # unconstrained baseline, no reduce


def test_no_state_snapshot_works_normally():
    """Sizer works correctly (returns valid int >= 1) with no state."""
    signal = _make_signal(entry=360.0, stop=359.0)  # 1 pt distance
    config = FixedFractionalFuturesConfig(
        max_position_risk_pct=0.02,
        max_position_size=5,
        soft_reduce_threshold=3,
    )
    sizer = _make_sizer(config=config, state=None)
    # krw/contract = 1.0 * 50000 = 50,000
    # target = 10_000_000 * 0.02 = 200,000
    # raw = 200,000 / 50,000 = 4 → clamp to min(4, 5) = 4
    result = sizer.calculate(signal, account_balance=10_000_000, current_positions=[])
    assert result == 4


# ---------------------------------------------------------------------------
# Additional: soft-reduce floor enforced (size=1 // 2 = 0 → clamp to 1)
# ---------------------------------------------------------------------------


def test_soft_reduce_floor_at_one():
    """When pre-reduce size is 1, soft-reduce must still return 1 (not 0)."""
    # tiny equity → raw_size < 2 so size=1 before reduce
    state = RiskStateSnapshot(consecutive_losses=5)
    signal = _make_signal(entry=300.0, stop=299.5)
    config = FixedFractionalFuturesConfig(
        max_position_risk_pct=0.001,  # very small budget → size=1
        max_position_size=2,
        soft_reduce_threshold=4,
    )
    sizer = _make_sizer(config=config, state=state)
    result = sizer.calculate(signal, account_balance=5_000_000, current_positions=[])
    # pre-reduce: target=5000, krw/contract=25000 → raw=0.2 → int=0 → max(1,0)=1
    # post-reduce: max(1, 1//2)=max(1,0)=1
    assert result == 1
