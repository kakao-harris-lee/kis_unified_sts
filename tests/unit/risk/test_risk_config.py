"""TDD tests for FuturesRiskConfig and load_trading_windows.

Written before implementation (red → green).  Covers:

1. FuturesRiskConfig.from_yaml() reads the project config/risk.yaml.
2. FuturesRiskConfig() with no YAML uses sensible defaults.
3. load_trading_windows() reads the project YAML and returns expected windows.
4. A YAML override for daily_mdd_limit_pct propagates correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.risk.config import FuturesRiskConfig, load_trading_windows

# ---------------------------------------------------------------------------
# Constants — must match config/risk.yaml verbatim
# ---------------------------------------------------------------------------

EXPECTED_WINDOWS = ["09:00-10:30", "14:30-15:20"]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_RISK_YAML = _PROJECT_ROOT / "config" / "risk.yaml"


# ---------------------------------------------------------------------------
# Test 1: from_yaml() populates all fields from project config/risk.yaml
# ---------------------------------------------------------------------------


class TestFuturesRiskConfigFromYaml:
    """FuturesRiskConfig.from_yaml() with the real project config."""

    @pytest.fixture(autouse=True)
    def set_config_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Point ConfigLoader at the project config directory."""
        monkeypatch.setenv("KIS_CONFIG_DIR", str(_PROJECT_ROOT / "config"))

    def test_from_yaml_returns_instance(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert isinstance(config, FuturesRiskConfig)

    def test_account_equity_krw(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.account_equity_krw == 5_000_000

    def test_daily_mdd_limit_pct(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.daily_mdd_limit_pct == pytest.approx(0.03)

    def test_weekly_mdd_limit_pct(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.weekly_mdd_limit_pct == pytest.approx(0.07)

    def test_max_position_risk_pct(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.max_position_risk_pct == pytest.approx(0.015)

    def test_max_daily_trades(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.max_daily_trades == 3

    def test_max_position_size_contracts(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.max_position_size_contracts == 2

    def test_consecutive_loss_soft_threshold(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.consecutive_loss_soft_threshold == 4

    def test_consecutive_loss_hard_threshold(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.consecutive_loss_hard_threshold == 6

    def test_max_spread_ticks(self) -> None:
        config = FuturesRiskConfig.from_yaml()
        assert config.max_spread_ticks == 2

    def test_leverage_block_ships_enforced(self) -> None:
        """Phase 4-g futures leverage cap ships ENABLED + enforce + cap 3.0 after
        the operator flip (2026-07-12): P4-g gate + P5-3 provider wiring complete.
        Pinning the shipped values here fails the build if the block is ever
        accidentally reverted to shadow/disabled, the cap is typo'd, or the
        sub-block is mis-nested. The filter remains fail-open on missing/stale/
        no-provider data — only gross_leverage > cap rejects a new entry."""
        lev = FuturesRiskConfig.from_yaml().leverage
        assert lev.enabled is True
        assert lev.mode == "enforce"
        assert lev.max_gross_leverage == 3.0
        assert lev.stale_max_age_seconds is None

    def test_margin_gate_block_ships_enforced(self) -> None:
        """Phase 4-f futures margin gate ships ENABLED + enforce after the
        operator flip (2026-07-12): P4-f gate + services/futures_margin_risk
        publisher wiring complete. Pinning the shipped values fails the build on
        an accidental revert to shadow/disabled or a mis-nested sub-block. The
        gate stays fail-open on missing/stale/corrupt snapshots — only
        risk_level in {block_new_entries, critical} rejects a new entry."""
        mg = FuturesRiskConfig.from_yaml().margin_gate
        assert mg.enabled is True
        assert mg.mode == "enforce"
        assert mg.latest_key == "futures:risk:latest"
        assert mg.stale_max_age_seconds == 600


# ---------------------------------------------------------------------------
# Test 2: Default values (no YAML)
# ---------------------------------------------------------------------------


class TestFuturesRiskConfigDefaults:
    """FuturesRiskConfig() instantiated with no arguments uses spec defaults."""

    def test_defaults_are_valid(self) -> None:
        config = FuturesRiskConfig()
        assert isinstance(config, FuturesRiskConfig)

    def test_default_account_equity_krw(self) -> None:
        assert FuturesRiskConfig().account_equity_krw == 5_000_000

    def test_default_daily_mdd_limit_pct(self) -> None:
        assert FuturesRiskConfig().daily_mdd_limit_pct == pytest.approx(0.03)

    def test_default_weekly_mdd_limit_pct(self) -> None:
        assert FuturesRiskConfig().weekly_mdd_limit_pct == pytest.approx(0.07)

    def test_default_max_position_risk_pct(self) -> None:
        assert FuturesRiskConfig().max_position_risk_pct == pytest.approx(0.015)

    def test_default_max_daily_trades(self) -> None:
        assert FuturesRiskConfig().max_daily_trades == 3

    def test_default_max_position_size_contracts(self) -> None:
        assert FuturesRiskConfig().max_position_size_contracts == 2

    def test_default_consecutive_loss_soft_threshold(self) -> None:
        assert FuturesRiskConfig().consecutive_loss_soft_threshold == 4

    def test_default_consecutive_loss_hard_threshold(self) -> None:
        assert FuturesRiskConfig().consecutive_loss_hard_threshold == 6

    def test_default_max_spread_ticks(self) -> None:
        assert FuturesRiskConfig().max_spread_ticks == 2


# ---------------------------------------------------------------------------
# Test 3: load_trading_windows() from project YAML
# ---------------------------------------------------------------------------


class TestLoadTradingWindows:
    """load_trading_windows() reads the top-level trading_windows key."""

    @pytest.fixture(autouse=True)
    def set_config_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KIS_CONFIG_DIR", str(_PROJECT_ROOT / "config"))

    def test_returns_list(self) -> None:
        windows = load_trading_windows()
        assert isinstance(windows, list)

    def test_returns_two_windows(self) -> None:
        windows = load_trading_windows()
        assert len(windows) == 2

    def test_first_window(self) -> None:
        windows = load_trading_windows()
        assert windows[0] == "09:00-10:30"

    def test_second_window(self) -> None:
        windows = load_trading_windows()
        assert windows[1] == "14:30-15:20"

    def test_absolute_path_override(self) -> None:
        """Passing an absolute path bypasses ConfigLoader."""
        windows = load_trading_windows(path=str(_CONFIG_RISK_YAML))
        assert windows == EXPECTED_WINDOWS

    def test_missing_file_returns_empty(self) -> None:
        """Non-existent absolute path returns []."""
        windows = load_trading_windows(path="/tmp/nonexistent_risk_9999.yaml")
        assert windows == []


# ---------------------------------------------------------------------------
# Test 4: YAML override propagates (write a temp YAML and load from it)
# ---------------------------------------------------------------------------


class TestFuturesRiskConfigYamlOverride:
    """A modified YAML value propagates into the loaded config."""

    def test_daily_mdd_limit_pct_override(self, tmp_path: Path) -> None:
        """Override daily_mdd_limit_pct to 0.05; from_yaml() should reflect it."""
        custom_yaml = tmp_path / "risk.yaml"
        custom_yaml.write_text(
            "risk:\n"
            "  account_equity_krw: 5000000\n"
            "  daily_mdd_limit_pct: 0.05\n"
            "  weekly_mdd_limit_pct: 0.07\n"
            "  max_position_risk_pct: 0.015\n"
            "  max_daily_trades: 3\n"
            "  max_position_size_contracts: 2\n"
            "  consecutive_loss_soft_threshold: 4\n"
            "  consecutive_loss_hard_threshold: 6\n"
            "  max_spread_ticks: 2\n"
            "\n"
            "trading_windows:\n"
            '  - "09:00-10:30"\n'
            '  - "14:30-15:20"\n',
            encoding="utf-8",
        )
        config = FuturesRiskConfig.from_yaml(path=str(custom_yaml))
        assert config.daily_mdd_limit_pct == pytest.approx(0.05)
        # Other fields keep their specified values
        assert config.max_daily_trades == 3

    def test_trading_windows_override(self, tmp_path: Path) -> None:
        """Custom trading windows are read correctly via load_trading_windows()."""
        custom_yaml = tmp_path / "risk.yaml"
        custom_yaml.write_text(
            "risk:\n"
            "  account_equity_krw: 5000000\n"
            "  daily_mdd_limit_pct: 0.03\n"
            "  weekly_mdd_limit_pct: 0.07\n"
            "  max_position_risk_pct: 0.015\n"
            "  max_daily_trades: 3\n"
            "  max_position_size_contracts: 2\n"
            "  consecutive_loss_soft_threshold: 4\n"
            "  consecutive_loss_hard_threshold: 6\n"
            "  max_spread_ticks: 2\n"
            "\n"
            "trading_windows:\n"
            '  - "09:00-11:00"\n'
            '  - "13:00-15:20"\n',
            encoding="utf-8",
        )
        windows = load_trading_windows(path=str(custom_yaml))
        assert windows == ["09:00-11:00", "13:00-15:20"]
