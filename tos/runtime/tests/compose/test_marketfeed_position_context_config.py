"""``marketfeed.yaml::position_context`` — opt-in per tree, fail-closed (plan P4 §2 D5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MARKETFEED_CONFIG_NAME,
    MarketFeedConfigError,
    load_marketfeed_config,
    load_position_context_config,
)

_BASE: dict[str, Any] = {
    "instruments": ["000660"],
    "instrument_class": "krx-stock",
    "account": "88888888-01",
    "direction": "LONG",
    "quantity_basis": "RISK",
    "unit": "SHARES",
    "intake_kind": "journal",
    "journal_path": "observations.jsonl",
    "journal_pass_allowance_ms": 100,
    "poll_interval_ms": 400,
    "snapshot_age_bound": 20,
    "interval_width": 10,
    "time_evaluate_closed_interval_ms": 60_000,
}


def _write(tmp_path: Path, block: Any = "ABSENT") -> Path:
    document = dict(_BASE)
    if block != "ABSENT":
        document["position_context"] = block
    path = tmp_path / MARKETFEED_CONFIG_NAME
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def test_an_absent_block_is_off_and_never_a_default(tmp_path: Path) -> None:
    """A tree that says nothing gets nothing — that is what keeps the off path byte-identical."""
    path = _write(tmp_path)
    assert load_marketfeed_config(path).position_context is None
    assert load_position_context_config(tmp_path) is None


def test_an_absent_marketfeed_file_declares_no_block(tmp_path: Path) -> None:
    assert load_position_context_config(tmp_path) is None


def test_a_declared_block_is_loaded_whole(tmp_path: Path) -> None:
    _write(tmp_path, {"enabled": True, "bar_interval_ms": 60_000})
    declared = load_position_context_config(tmp_path)
    assert declared is not None
    assert declared.enabled is True
    assert declared.bar_interval_ms == 60_000


def test_an_explicitly_disabled_block_needs_no_bar_interval(tmp_path: Path) -> None:
    _write(tmp_path, {"enabled": False})
    declared = load_position_context_config(tmp_path)
    assert declared is not None
    assert declared.enabled is False
    assert declared.bar_interval_ms is None


def test_enabled_without_a_bar_interval_refuses_the_boot(tmp_path: Path) -> None:
    """``bars_held`` divides by it — a declared time exit cannot count bars without it."""
    _write(tmp_path, {"enabled": True})
    with pytest.raises(MarketFeedConfigError, match="bar_interval_ms"):
        load_position_context_config(tmp_path)


@pytest.mark.parametrize("enabled", ["true", 1, None, "yes"])
def test_a_non_bool_enabled_refuses_the_boot(tmp_path: Path, enabled: Any) -> None:
    _write(tmp_path, {"enabled": enabled, "bar_interval_ms": 60_000})
    with pytest.raises(MarketFeedConfigError, match="enabled"):
        load_position_context_config(tmp_path)


@pytest.mark.parametrize("bar_interval_ms", [0, -1, "60000", True, 1.5])
def test_a_non_positive_or_non_int_bar_interval_refuses_the_boot(
    tmp_path: Path, bar_interval_ms: Any
) -> None:
    _write(tmp_path, {"enabled": True, "bar_interval_ms": bar_interval_ms})
    with pytest.raises(MarketFeedConfigError, match="bar_interval_ms"):
        load_position_context_config(tmp_path)


def test_an_unrecognized_sub_key_refuses_the_boot(tmp_path: Path) -> None:
    """A stray key would look load-bearing while being ignored (the module's own rule)."""
    _write(
        tmp_path,
        {"enabled": True, "bar_interval_ms": 60_000, "price_field_key": "close"},
    )
    with pytest.raises(MarketFeedConfigError, match="unrecognized key"):
        load_position_context_config(tmp_path)


@pytest.mark.parametrize("block", [[], "on", 1])
def test_a_block_that_is_not_a_mapping_refuses_the_boot(
    tmp_path: Path, block: Any
) -> None:
    _write(tmp_path, block)
    with pytest.raises(MarketFeedConfigError, match="must be a mapping"):
        load_position_context_config(tmp_path)


def test_every_shipped_tree_declares_no_position_context_yet(tmp_path: Path) -> None:
    """Completion 3: this PR ships the feature OFF for every tree under ``config/``."""
    del tmp_path
    repo_root = Path(__file__).resolve().parents[4]
    trees = sorted(
        (repo_root / "config" / "tos_runtime").glob(f"*/{MARKETFEED_CONFIG_NAME}")
    )
    assert trees, "no shipped tenant tree marketfeed.yaml found"
    for path in trees:
        assert load_position_context_config(path.parent) is None, path
