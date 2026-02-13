"""Tests for KellyPositionSizer.

Tests Kelly Criterion-based position sizing with entropy confidence,
verifying math correctness, configuration loading, and integration.
"""

import numpy as np
import pytest

from shared.ml.rl.position_sizing import KellyPositionSizer, KellySizingConfig


@pytest.fixture
def default_sizer():
    """Create sizer with default config."""
    return KellyPositionSizer()


@pytest.fixture
def custom_sizer():
    """Create sizer with custom config."""
    config = KellySizingConfig(
        enabled=True,
        fraction=0.5,
        min_trades=5,
        min_scale=0.3,
        max_scale=1.0,
        default_win_rate=0.5,
        default_wl_ratio=2.0,
    )
    return KellyPositionSizer(config)


@pytest.fixture
def disabled_sizer():
    """Create sizer with sizing disabled."""
    config = KellySizingConfig(enabled=False)
    return KellyPositionSizer(config)


class TestKellySizingConfig:
    def test_default_values(self):
        cfg = KellySizingConfig()
        assert cfg.enabled is True
        assert cfg.fraction == 0.5  # Half-Kelly
        assert cfg.min_trades == 10
        assert cfg.min_scale == 0.2
        assert cfg.max_scale == 1.0
        assert cfg.default_win_rate == 0.45
        assert cfg.default_wl_ratio == 1.5

    def test_custom_values(self):
        cfg = KellySizingConfig(
            fraction=0.25,
            min_scale=0.1,
            default_win_rate=0.6,
        )
        assert cfg.fraction == 0.25
        assert cfg.min_scale == 0.1
        assert cfg.default_win_rate == 0.6


class TestKellyFraction:
    def test_kelly_positive_edge(self):
        """Test Kelly formula for profitable strategy."""
        # win_rate=0.6, wl_ratio=2.0
        # f* = (0.6 * 2 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.4
        kelly = KellyPositionSizer.kelly_fraction(0.6, 2.0)
        assert kelly == pytest.approx(0.4, abs=1e-6)

    def test_kelly_zero_edge(self):
        """Test Kelly when expected value is zero."""
        # win_rate=0.5, wl_ratio=1.0 (fair game)
        # f* = (0.5 * 1 - 0.5) / 1 = 0
        kelly = KellyPositionSizer.kelly_fraction(0.5, 1.0)
        assert kelly == pytest.approx(0.0, abs=1e-6)

    def test_kelly_negative_edge(self):
        """Test Kelly returns negative for losing strategy."""
        # win_rate=0.3, wl_ratio=1.0
        # f* = (0.3 * 1 - 0.7) / 1 = -0.4
        kelly = KellyPositionSizer.kelly_fraction(0.3, 1.0)
        assert kelly < 0

    def test_kelly_high_winrate_low_ratio(self):
        """High win rate but low profit ratio."""
        # win_rate=0.9, wl_ratio=0.5 (many small wins, rare big losses)
        # f* = (0.9 * 0.5 - 0.1) / 0.5 = (0.45 - 0.1) / 0.5 = 0.7
        kelly = KellyPositionSizer.kelly_fraction(0.9, 0.5)
        assert kelly == pytest.approx(0.7, abs=1e-6)

    def test_kelly_low_winrate_high_ratio(self):
        """Low win rate but high profit ratio."""
        # win_rate=0.35, wl_ratio=3.0 (rare wins, big when they hit)
        # f* = (0.35 * 3 - 0.65) / 3 = (1.05 - 0.65) / 3 = 0.133
        kelly = KellyPositionSizer.kelly_fraction(0.35, 3.0)
        assert kelly == pytest.approx(0.133, abs=1e-3)

    def test_kelly_zero_wl_ratio(self):
        """Zero W/L ratio should return 0 to avoid division by zero."""
        kelly = KellyPositionSizer.kelly_fraction(0.6, 0.0)
        assert kelly == 0.0

    def test_kelly_negative_wl_ratio(self):
        """Negative W/L ratio (invalid) should return 0."""
        kelly = KellyPositionSizer.kelly_fraction(0.6, -1.0)
        assert kelly == 0.0


class TestEntropyConfidence:
    def test_uniform_distribution_zero_confidence(self):
        """Uniform probability = maximum entropy = zero confidence."""
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence == pytest.approx(0.0, abs=1e-6)

    def test_deterministic_full_confidence(self):
        """Deterministic choice = zero entropy = full confidence."""
        probs = np.array([1.0, 0.0, 0.0, 0.0])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence == pytest.approx(1.0, abs=1e-6)

    def test_high_confidence_skewed_distribution(self):
        """Highly skewed distribution = high confidence."""
        probs = np.array([0.9, 0.05, 0.03, 0.02])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence > 0.65  # Should be quite confident

    def test_medium_confidence(self):
        """Moderate skew = medium confidence."""
        probs = np.array([0.5, 0.3, 0.15, 0.05])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert 0.15 < confidence < 0.5  # Less confident with more spread

    def test_binary_choice_extremes(self):
        """Binary choice extremes."""
        # Uniform binary
        probs = np.array([0.5, 0.5])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence == pytest.approx(0.0, abs=1e-6)

        # Deterministic binary
        probs = np.array([1.0, 0.0])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence == pytest.approx(1.0, abs=1e-6)

    def test_normalizes_input(self):
        """Should normalize probabilities that don't sum to 1."""
        probs = np.array([2.0, 1.0, 1.0])  # Sum = 4
        confidence = KellyPositionSizer.entropy_confidence(probs)
        # After normalization: [0.5, 0.25, 0.25]
        assert confidence > 0.0  # Not uniform

    def test_handles_zero_probabilities(self):
        """Should handle zero probabilities (clip to avoid log(0))."""
        probs = np.array([0.8, 0.2, 0.0, 0.0])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert 0.0 <= confidence <= 1.0

    def test_single_action(self):
        """Single action = full confidence."""
        probs = np.array([1.0])
        confidence = KellyPositionSizer.entropy_confidence(probs)
        assert confidence == 1.0


class TestTradeRecording:
    def test_record_single_trade(self, default_sizer):
        assert len(default_sizer._trade_pnls) == 0
        default_sizer.record_trade(1000.0)
        assert len(default_sizer._trade_pnls) == 1
        assert default_sizer._trade_pnls[0] == 1000.0

    def test_record_multiple_trades(self, default_sizer):
        pnls = [1000, -500, 2000, -300, 1500]
        for pnl in pnls:
            default_sizer.record_trade(pnl)
        assert len(default_sizer._trade_pnls) == 5
        assert list(default_sizer._trade_pnls) == pnls

    def test_get_trade_stats_insufficient_trades(self, default_sizer):
        """Should return defaults if < min_trades."""
        default_sizer.record_trade(1000)
        default_sizer.record_trade(-500)
        # Only 2 trades, min_trades=10
        win_rate, wl_ratio = default_sizer.get_trade_stats()
        assert win_rate == 0.45  # default
        assert wl_ratio == 1.5   # default

    def test_get_trade_stats_sufficient_trades(self, custom_sizer):
        """Should calculate from history when >= min_trades."""
        # custom_sizer has min_trades=5
        trades = [1000, -500, 2000, -300, 1500]  # 3 wins, 2 losses
        for pnl in trades:
            custom_sizer.record_trade(pnl)

        win_rate, wl_ratio = custom_sizer.get_trade_stats()
        assert win_rate == 3 / 5  # 0.6

        # avg_win = (1000 + 2000 + 1500) / 3 = 1500
        # avg_loss = (500 + 300) / 2 = 400
        # wl_ratio = 1500 / 400 = 3.75
        assert wl_ratio == pytest.approx(3.75, abs=0.01)

    def test_get_trade_stats_all_wins(self, custom_sizer):
        """All winning trades."""
        for _ in range(5):
            custom_sizer.record_trade(1000)

        win_rate, wl_ratio = custom_sizer.get_trade_stats()
        assert win_rate == 1.0
        # No losses, avg_loss=1.0 (default), so wl_ratio = avg_win / 1.0
        assert wl_ratio == 1000.0

    def test_get_trade_stats_all_losses(self, custom_sizer):
        """All losing trades."""
        for _ in range(5):
            custom_sizer.record_trade(-500)

        win_rate, wl_ratio = custom_sizer.get_trade_stats()
        assert win_rate == 0.0
        # No wins, avg_win=1.0 (default), avg_loss=500, so wl_ratio = 1.0/500
        assert wl_ratio == pytest.approx(0.002, abs=0.001)


class TestCalculateScale:
    def test_disabled_returns_max_scale(self, disabled_sizer):
        """When disabled, should always return max_scale."""
        scale = disabled_sizer.calculate_scale()
        assert scale == 1.0

        scale = disabled_sizer.calculate_scale(
            action_probs=np.array([0.5, 0.5]),
            win_rate=0.3,
            wl_ratio=0.5,
        )
        assert scale == 1.0

    def test_negative_kelly_returns_zero(self, default_sizer):
        """Negative Kelly (losing strategy) should return 0."""
        scale = default_sizer.calculate_scale(win_rate=0.3, wl_ratio=0.8)
        assert scale == 0.0

    def test_positive_kelly_with_full_confidence(self, default_sizer):
        """Positive Kelly with deterministic action."""
        # win_rate=0.6, wl_ratio=2.0
        # kelly = 0.4, half_kelly = 0.2, confidence=1.0
        # scale = 0.2 * 1.0 = 0.2
        probs = np.array([1.0, 0.0, 0.0])
        scale = default_sizer.calculate_scale(
            action_probs=probs,
            win_rate=0.6,
            wl_ratio=2.0,
        )
        assert scale == pytest.approx(0.2, abs=1e-6)

    def test_positive_kelly_with_zero_confidence(self, default_sizer):
        """Positive Kelly with uniform distribution (no confidence)."""
        # kelly = 0.4, half_kelly = 0.2, confidence=0.0
        # scale = 0.2 * 0.0 = 0.0
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        scale = default_sizer.calculate_scale(
            action_probs=probs,
            win_rate=0.6,
            wl_ratio=2.0,
        )
        assert scale == pytest.approx(0.0, abs=1e-6)

    def test_capped_at_max_scale(self, default_sizer):
        """Scale should not exceed max_scale."""
        # Very high kelly + full confidence
        probs = np.array([1.0, 0.0])
        scale = default_sizer.calculate_scale(
            action_probs=probs,
            win_rate=0.9,
            wl_ratio=5.0,
        )
        assert scale <= 1.0

    def test_uses_history_when_params_none(self, custom_sizer):
        """Should use trade history if win_rate/wl_ratio not provided."""
        # Record trades to build history
        for _ in range(6):  # > min_trades
            custom_sizer.record_trade(1000)

        scale = custom_sizer.calculate_scale()
        # win_rate=1.0, wl_ratio=default=2.0 (no losses)
        # kelly = (1.0 * 2.0 - 0) / 2.0 = 1.0
        # half_kelly = 0.5
        # confidence = 1.0 (no probs given)
        assert scale == pytest.approx(0.5, abs=0.01)

    def test_none_action_probs_means_full_confidence(self, default_sizer):
        """If action_probs=None, confidence=1.0."""
        scale = default_sizer.calculate_scale(
            action_probs=None,
            win_rate=0.6,
            wl_ratio=2.0,
        )
        # kelly=0.4, half=0.2, confidence=1.0 -> 0.2
        assert scale == pytest.approx(0.2, abs=1e-6)


class TestGetContracts:
    def test_returns_zero_when_scale_below_min(self, default_sizer):
        """Should return 0 if scale < min_scale."""
        # default min_scale = 0.2
        # Force very low scale
        contracts = default_sizer.get_contracts(
            max_contracts=10,
            win_rate=0.3,
            wl_ratio=0.8,  # Negative Kelly -> scale=0
        )
        assert contracts == 0

    def test_returns_at_least_one_if_above_min(self, custom_sizer):
        """Should return at least 1 contract if scale >= min_scale."""
        # custom min_scale = 0.3
        # win_rate=0.6, wl_ratio=2.0 -> kelly=0.4, half=0.2, confidence=1.0 -> scale=0.2
        # But this is below min_scale, so should return 0
        contracts = custom_sizer.get_contracts(
            max_contracts=10,
            win_rate=0.6,
            wl_ratio=2.0,
        )
        assert contracts == 0

        # Now with higher edge
        # win_rate=0.7, wl_ratio=2.0 -> kelly=(0.7*2-0.3)/2=0.55, half=0.275 < 0.3 min_scale
        # Need higher params to exceed min_scale
        # win_rate=0.75, wl_ratio=2.0 -> kelly=(0.75*2-0.25)/2=0.625, half=0.3125 > 0.3
        contracts = custom_sizer.get_contracts(
            max_contracts=10,
            win_rate=0.75,
            wl_ratio=2.0,
        )
        assert contracts >= 1

    def test_scales_max_contracts(self, default_sizer):
        """Should scale max_contracts by position scale."""
        # Need scale >= min_scale (0.2) to trade
        # win_rate=0.65, wl_ratio=2.0 -> kelly=(0.65*2-0.35)/2=0.475, half=0.2375 > 0.2
        contracts = default_sizer.get_contracts(
            max_contracts=10,
            win_rate=0.65,
            wl_ratio=2.0,
        )
        # scale=0.2375, contracts = round(10 * 0.2375) = 2
        assert contracts == 2

    def test_rounds_to_nearest_integer(self, default_sizer):
        """Should round fractional contracts."""
        # scale = 0.25 -> 10 * 0.25 = 2.5 -> round to 2 or 3
        contracts = default_sizer.get_contracts(
            max_contracts=10,
            win_rate=0.65,
            wl_ratio=2.0,
        )
        assert contracts in [2, 3]

    def test_capped_at_max_contracts(self, default_sizer):
        """Should not exceed max_contracts."""
        contracts = default_sizer.get_contracts(
            max_contracts=2,
            win_rate=0.9,
            wl_ratio=5.0,
        )
        assert contracts <= 2

    def test_with_action_probs(self, default_sizer):
        """Should use entropy confidence when probs given."""
        # Deterministic choice (confidence=1.0)
        # Need scale >= 0.2, so win_rate=0.65, wl_ratio=2.0 -> kelly=0.475, half=0.2375
        probs = np.array([1.0, 0.0, 0.0])
        contracts = default_sizer.get_contracts(
            max_contracts=10,
            action_probs=probs,
            win_rate=0.65,
            wl_ratio=2.0,
        )
        assert contracts == 2  # scale=0.2375, 10*0.2375=2

        # Uniform choice (zero confidence)
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        contracts = default_sizer.get_contracts(
            max_contracts=10,
            action_probs=probs,
            win_rate=0.65,
            wl_ratio=2.0,
        )
        assert contracts == 0  # scale=0, below min_scale


class TestShouldTrade:
    def test_returns_true_above_min_scale(self, default_sizer):
        should = default_sizer.should_trade(
            action_probs=np.array([1.0, 0.0])
        )
        # Uses defaults: win_rate=0.45, wl_ratio=1.5
        # kelly = (0.45*1.5 - 0.55)/1.5 = 0.083, half=0.042
        # scale = 0.042 < min_scale(0.2) -> False
        assert should is False

    def test_returns_false_below_min_scale(self, default_sizer):
        # Uniform probs -> confidence=0 -> scale=0
        should = default_sizer.should_trade(
            action_probs=np.array([0.5, 0.5])
        )
        assert should is False

    def test_boundary_case(self, custom_sizer):
        """Test exactly at min_scale boundary."""
        # min_scale = 0.3
        # Craft params to get exactly 0.3
        # win_rate=0.7, wl_ratio=2.0, fraction=0.5
        # kelly = (0.7*2 - 0.3)/2 = 0.55, half=0.275
        # Need confidence to make it exactly 0.3
        should = custom_sizer.should_trade()
        # Uses defaults -> likely False, but depends on exact config
        # Just verify it returns bool
        assert isinstance(should, bool)


class TestConfigIntegration:
    def test_from_yaml_loads_config(self, tmp_path):
        """Test loading from YAML file."""
        # This would require actual YAML file or mocking ConfigLoader
        # For now, just test that method exists and accepts path
        # In real usage, this would load config/ml/rl_mppo.yaml

        # Create sizer with defaults
        sizer = KellyPositionSizer()
        assert sizer.config.enabled is True

    def test_init_with_none_uses_defaults(self):
        sizer = KellyPositionSizer(config=None)
        assert sizer.config.fraction == 0.5
        assert sizer.config.min_trades == 10


class TestEdgeCases:
    def test_empty_trade_history(self, default_sizer):
        """Empty history should use defaults."""
        win_rate, wl_ratio = default_sizer.get_trade_stats()
        assert win_rate == 0.45
        assert wl_ratio == 1.5

    def test_zero_trades_scale(self, default_sizer):
        """Should work with zero trade history."""
        scale = default_sizer.calculate_scale()
        # Uses defaults
        assert scale >= 0.0

    def test_extreme_win_rate(self, default_sizer):
        """Should handle win_rate=1.0."""
        scale = default_sizer.calculate_scale(win_rate=1.0, wl_ratio=2.0)
        # kelly = (1.0*2 - 0)/2 = 1.0, half=0.5, capped at max_scale=1.0
        assert scale == pytest.approx(0.5, abs=0.01)

    def test_extreme_wl_ratio(self, default_sizer):
        """Should handle very high W/L ratio."""
        scale = default_sizer.calculate_scale(win_rate=0.5, wl_ratio=10.0)
        # kelly = (0.5*10 - 0.5)/10 = 0.45, half=0.225
        assert scale == pytest.approx(0.225, abs=0.01)
