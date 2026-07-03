"""PortfolioConfig loader and track-mapping tests (unified roadmap Phase 3A)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from shared.portfolio.config import (
    ASSET_CLASS_TRACKS,
    TRACK_CORE,
    TRACK_FUTURES,
    TRACK_STOCK,
    VALID_TRACK_IDS,
    PortfolioConfig,
    track_for_asset_class,
)

_REPO_YAML = Path(__file__).resolve().parents[3] / "config" / "portfolio.yaml"


class TestTrackMapping:
    def test_pipeline_asset_classes_map_to_tracks(self):
        assert track_for_asset_class("stock") == TRACK_STOCK == "B"
        assert track_for_asset_class("futures") == TRACK_FUTURES == "C"

    def test_mapping_is_case_and_whitespace_insensitive(self):
        assert track_for_asset_class("STOCK") == "B"
        assert track_for_asset_class("  Futures ") == "C"

    def test_unknown_or_missing_asset_class_stays_untagged(self):
        assert track_for_asset_class(None) is None
        assert track_for_asset_class("") is None
        assert track_for_asset_class("crypto") is None

    def test_track_a_reserved_but_never_derived_from_asset_class(self):
        # Track A (manual core ledger, Phase 5) is a valid id, but no runtime
        # asset class may auto-derive it.
        assert TRACK_CORE == "A"
        assert TRACK_CORE in VALID_TRACK_IDS
        assert TRACK_CORE not in ASSET_CLASS_TRACKS.values()


class TestPortfolioConfig:
    def test_defaults_match_design_doc(self):
        config = PortfolioConfig()

        assert config.tiers.tier1_core == pytest.approx(0.65)
        assert config.tiers.tier2_trading == pytest.approx(0.25)
        assert config.tiers.tier3_opportunity == pytest.approx(0.10)
        assert config.tier2_split.track_b_stock == pytest.approx(0.70)
        assert config.tier2_split.track_c_futures == pytest.approx(0.30)

        movement = config.fund_movement
        assert movement.tier2_to_tier1.profit_threshold_pct == pytest.approx(0.30)
        assert movement.tier2_to_tier1.transfer_ratio == pytest.approx(0.50)
        assert movement.tier3_activation.kospi_drawdown_from_peak == pytest.approx(
            -0.15
        )
        assert movement.tier3_activation.tranches == 3

        breaker = config.circuit_breaker
        assert breaker.mode == "shadow"
        assert breaker.monthly_mdd_stages.reduce.threshold == pytest.approx(-0.05)
        assert breaker.monthly_mdd_stages.reduce.new_entry_size_factor == (
            pytest.approx(0.5)
        )
        assert breaker.monthly_mdd_stages.halt_new.threshold == pytest.approx(-0.08)
        assert breaker.monthly_mdd_stages.full_stop.threshold == pytest.approx(-0.12)

        assert config.track_c_monthly_loss_halt == pytest.approx(0.15)

    def test_repo_yaml_loads_and_matches_defaults(self):
        config = PortfolioConfig.from_yaml(str(_REPO_YAML))
        assert config == PortfolioConfig()

    def test_tiers_must_sum_to_one(self):
        with pytest.raises(ValidationError, match="tiers must sum to 1.0"):
            PortfolioConfig(
                tiers={
                    "tier1_core": 0.65,
                    "tier2_trading": 0.25,
                    "tier3_opportunity": 0.20,
                }
            )

    def test_tier2_split_must_sum_to_one(self):
        with pytest.raises(ValidationError, match="tier2_split must sum to 1.0"):
            PortfolioConfig(
                tier2_split={"track_b_stock": 0.70, "track_c_futures": 0.40}
            )

    def test_mdd_stage_thresholds_must_deepen_monotonically(self):
        with pytest.raises(ValidationError, match="deepen monotonically"):
            PortfolioConfig(
                circuit_breaker={
                    "monthly_mdd_stages": {
                        "reduce": {"threshold": -0.10},
                        "halt_new": {"threshold": -0.08},
                        "full_stop": {"threshold": -0.12},
                    }
                }
            )

    def test_circuit_breaker_mode_is_constrained(self):
        with pytest.raises(ValidationError):
            PortfolioConfig(circuit_breaker={"mode": "dry_run"})

    def test_load_or_default_falls_back_when_yaml_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
        from shared.config.loader import ConfigLoader

        ConfigLoader.set_config_dir(str(tmp_path))

        config = PortfolioConfig.load_or_default()

        assert config == PortfolioConfig()

    def test_load_or_default_reads_yaml_overrides(self, monkeypatch, tmp_path):
        (tmp_path / "portfolio.yaml").write_text(
            """
tiers:
  tier1_core: 0.60
  tier2_trading: 0.30
  tier3_opportunity: 0.10
circuit_breaker:
  mode: enforce
track_c_monthly_loss_halt: 0.10
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
        from shared.config.loader import ConfigLoader

        ConfigLoader.set_config_dir(str(tmp_path))

        config = PortfolioConfig.load_or_default()

        assert config.tiers.tier1_core == pytest.approx(0.60)
        assert config.tiers.tier2_trading == pytest.approx(0.30)
        assert config.circuit_breaker.mode == "enforce"
        assert config.track_c_monthly_loss_halt == pytest.approx(0.10)
        # Unspecified sections keep validated defaults.
        assert config.tier2_split.track_b_stock == pytest.approx(0.70)


class TestPhase3BSections:
    """capital_base / monitor / stage_latch additions (Phase 3B monitor)."""

    def test_capital_base_defaults_and_track_lookup(self):
        config = PortfolioConfig()
        assert config.capital_base.track_a_core_krw is None
        assert config.capital_base.track_b_stock_krw == pytest.approx(10_000_000)
        assert config.capital_base.track_c_futures_krw == pytest.approx(5_000_000)
        assert config.capital_base.for_track(TRACK_CORE) is None
        assert config.capital_base.for_track(TRACK_STOCK) == pytest.approx(10_000_000)
        assert config.capital_base.for_track(TRACK_FUTURES) == pytest.approx(5_000_000)

    def test_stage_latch_defaults_on(self):
        assert PortfolioConfig().circuit_breaker.stage_latch is True

    def test_monitor_redis_contract_defaults(self):
        monitor = PortfolioConfig().monitor
        assert monitor.redis.latest_key == "portfolio:equity:latest"
        assert monitor.redis.latest_ttl_seconds == 86400
        assert monitor.redis.stream_key == "stream:portfolio.equity"
        assert monitor.redis.stream_ttl_seconds == 86400
        assert monitor.alerts.notify_stages == ["REDUCE", "HALT_NEW", "FULL_STOP"]

    def test_capital_base_yaml_overrides(self, monkeypatch, tmp_path):
        (tmp_path / "portfolio.yaml").write_text(
            """
capital_base:
  track_a_core_krw: 50000000
  track_b_stock_krw: 20000000
  track_c_futures_krw: 8000000
circuit_breaker:
  stage_latch: false
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("KIS_CONFIG_DIR", str(tmp_path))
        from shared.config.loader import ConfigLoader

        ConfigLoader.set_config_dir(str(tmp_path))

        config = PortfolioConfig.load_or_default()
        assert config.capital_base.for_track(TRACK_CORE) == pytest.approx(50_000_000)
        assert config.capital_base.for_track(TRACK_STOCK) == pytest.approx(20_000_000)
        assert config.capital_base.for_track(TRACK_FUTURES) == pytest.approx(8_000_000)
        assert config.circuit_breaker.stage_latch is False
