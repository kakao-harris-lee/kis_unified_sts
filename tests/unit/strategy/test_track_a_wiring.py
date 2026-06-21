"""Wiring tests: track_a_exit registry + YAML config integration.

TDD: write failing tests → implement → pass.
"""
import yaml
import pytest
from pathlib import Path

CONFIG_DIR = Path(__file__).parents[3] / "config"


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Registry round-trip
# ---------------------------------------------------------------------------

def test_track_a_exit_registered_after_builtin():
    """track_a_exit is registered after register_builtin_components()."""
    from shared.strategy.registry import ExitRegistry, register_builtin_components

    ExitRegistry.clear()
    register_builtin_components()

    assert ExitRegistry.is_registered("track_a_exit"), (
        "track_a_exit not found; available: " + str(ExitRegistry.list_all())
    )


def test_track_a_exit_creatable():
    """ExitRegistry.create('track_a_exit', {}) returns a TrackAExit with correct name."""
    from shared.strategy.registry import ExitRegistry, register_builtin_components
    from shared.strategy.exit.track_a_exit import TrackAExit

    ExitRegistry.clear()
    register_builtin_components()

    instance = ExitRegistry.create("track_a_exit", {})
    assert isinstance(instance, TrackAExit)
    assert instance.name == "track_a_exit"


def test_setup_target_exit_still_registered():
    """setup_target_exit must remain registered (rollback path)."""
    from shared.strategy.registry import ExitRegistry, register_builtin_components

    ExitRegistry.clear()
    register_builtin_components()

    assert ExitRegistry.is_registered("setup_target_exit"), (
        "setup_target_exit missing — rollback path broken"
    )


# ---------------------------------------------------------------------------
# track_a_exit.yaml default params
# ---------------------------------------------------------------------------

def test_track_a_exit_yaml_defaults():
    """track_a_exit.yaml exposes the expected default param values."""
    path = CONFIG_DIR / "strategies" / "futures" / "track_a_exit.yaml"
    assert path.exists(), f"Missing {path}"
    data = _load_yaml(path)
    params = data["track_a_exit"]["params"]

    assert params["trail_atr_mult"] == 3.0
    assert params["crash_atr_mult"] == 3.5
    assert params["catastrophic_atr_mult"] == 6.0
    assert params["eod_close_hour"] == 15
    assert params["eod_close_minute"] == 15
    assert params["trail_activate_atr_mult"] == 1.0
    assert params["eod_close_enabled"] is True
    assert params["enabled"] is True


# ---------------------------------------------------------------------------
# Setup A/C YAML: exit.type == track_a_exit
# ---------------------------------------------------------------------------

def test_setup_a_yaml_uses_track_a_exit():
    """setup_a_gap_reversion.yaml specifies exit.type: track_a_exit."""
    path = CONFIG_DIR / "strategies" / "futures" / "setup_a_gap_reversion.yaml"
    data = _load_yaml(path)
    exit_type = data["strategy"]["exit"]["type"]
    assert exit_type == "track_a_exit", f"Expected track_a_exit, got {exit_type!r}"


def test_setup_c_yaml_uses_track_a_exit():
    """setup_c_event_reaction.yaml specifies exit.type: track_a_exit."""
    path = CONFIG_DIR / "strategies" / "futures" / "setup_c_event_reaction.yaml"
    data = _load_yaml(path)
    exit_type = data["strategy"]["exit"]["type"]
    assert exit_type == "track_a_exit", f"Expected track_a_exit, got {exit_type!r}"


# ---------------------------------------------------------------------------
# Setup A/C YAML: daily_bias_filter params present
# ---------------------------------------------------------------------------

def test_setup_a_yaml_has_daily_bias_filter():
    """setup_a_gap_reversion.yaml entry.params includes daily_bias_filter fields."""
    path = CONFIG_DIR / "strategies" / "futures" / "setup_a_gap_reversion.yaml"
    data = _load_yaml(path)
    params = data["strategy"]["entry"]["params"]
    assert "daily_bias_filter_enabled" in params
    assert "daily_bias_min_confidence" in params
    assert params["daily_bias_min_confidence"] == 0.5


def test_setup_c_yaml_has_daily_bias_filter():
    """setup_c_event_reaction.yaml entry.params includes daily_bias_filter fields."""
    path = CONFIG_DIR / "strategies" / "futures" / "setup_c_event_reaction.yaml"
    data = _load_yaml(path)
    params = data["strategy"]["entry"]["params"]
    assert "daily_bias_filter_enabled" in params
    assert "daily_bias_min_confidence" in params
    assert params["daily_bias_min_confidence"] == 0.5


# ---------------------------------------------------------------------------
# load_strategy_config integration (loader path)
# ---------------------------------------------------------------------------

def test_setup_a_via_loader_exit_type():
    """load_strategy_config returns setup_a config with exit.type=track_a_exit."""
    from shared.config.loader import load_strategy_config

    cfg = load_strategy_config("futures", "setup_a_gap_reversion")
    exit_type = cfg["strategy"]["exit"]["type"]
    assert exit_type == "track_a_exit", f"Loader returned exit.type={exit_type!r}"


def test_setup_c_via_loader_exit_type():
    """load_strategy_config returns setup_c config with exit.type=track_a_exit."""
    from shared.config.loader import load_strategy_config

    cfg = load_strategy_config("futures", "setup_c_event_reaction")
    exit_type = cfg["strategy"]["exit"]["type"]
    assert exit_type == "track_a_exit", f"Loader returned exit.type={exit_type!r}"
