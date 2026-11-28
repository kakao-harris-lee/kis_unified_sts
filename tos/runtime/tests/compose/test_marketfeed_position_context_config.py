"""``marketfeed.yaml::position_context`` — opt-in per tree, fail-closed (plan P4 §2 D5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos_runtime.compose._marketfeed_wiring import (
    MARKETFEED_CONFIG_NAME,
    MarketFeedConfig,
    MarketFeedConfigError,
    _position_context_source,
    load_marketfeed_config,
    load_position_context_config,
)
from tos_runtime.riskstate.close_bound import EntryCloseBound

from . import _fixtures as fx

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


_NEVER_READ = EntryCloseBound(
    account="never-read",
    instrument="never-read",
    entry_reservation_id=None,
    entry_attempt_id=None,
    entry_quantity=None,
    prior_closed=None,
    rcl_writer_epoch=None,
    rcl_last_seq=None,
    refusal="NEVER_READ",
)


def _source(tmp_path: Path, block: Any = "ABSENT", **overrides: Any) -> Any:
    """``_position_context_source`` over a loaded config, every seam absent unless overridden."""
    config: MarketFeedConfig = load_marketfeed_config(_write(tmp_path, block))
    kwargs: dict[str, Any] = {
        "config_dir": tmp_path,
        "inbox": None,
        "evidence_store": None,
        "scheme": fx.SCHEME,
        "construction": None,
        "reservation_projection": None,
        "entry_close_bound_reader": None,
    }
    kwargs.update(overrides)
    return _position_context_source(config, **kwargs)


@pytest.mark.parametrize("block", ["ABSENT", {"enabled": False}])
def test_a_disabled_tree_builds_no_source_and_needs_no_evidence(
    tmp_path: Path, block: Any
) -> None:
    """Off is off — no reader is built, so nothing of the position path runs for that tree."""
    assert _source(tmp_path, block) is None


def test_an_enabled_tree_whose_compose_passed_no_evidence_refuses_the_boot(
    tmp_path: Path,
) -> None:
    """A silently absent namespace makes every rule that reads it permanently false."""
    with pytest.raises(MarketFeedConfigError, match="position evidence"):
        _source(tmp_path, {"enabled": True, "bar_interval_ms": 60_000})


def test_an_enabled_tree_with_no_construction_price_field_key_refuses_the_boot(
    tmp_path: Path,
) -> None:
    """The bar price must be the ORDER's own admitted value — there is no second key to fall to."""
    with pytest.raises(MarketFeedConfigError, match="price_field_key"):
        _source(
            tmp_path,
            {"enabled": True, "bar_interval_ms": 60_000},
            construction=fx.construction_config(price_field_key=None),
            reservation_projection=object(),
            entry_close_bound_reader=lambda: _NEVER_READ,
        )


#: The ONE shipped tree that turns the namespace on (P4 S4 — the plan's §3 first
#: application). Every other tree stays off, which is what keeps its payload, environment
#: and signature byte-identical to the pre-P4 path (plan completion 3).
_TREES_WITH_POSITION_CONTEXT: frozenset[str] = frozenset({"cp3-setup-d-stock-000660"})


def test_exactly_the_declared_shipped_trees_turn_the_namespace_on(
    tmp_path: Path,
) -> None:
    """Completion 3: opt-in per tree, and the opt-in set is written down right here."""
    del tmp_path
    repo_root = Path(__file__).resolve().parents[4]
    trees = sorted(
        (repo_root / "config" / "tos_runtime").glob(f"*/{MARKETFEED_CONFIG_NAME}")
    )
    assert trees, "no shipped tenant tree marketfeed.yaml found"
    carrying: set[str] = set()
    for path in trees:
        declared = load_position_context_config(path.parent)
        if declared is None:
            continue
        # SAFETY: a tree that merely CARRIES the block is counted here, enabled or not — a
        # `position_context: {enabled: false}` landing unlisted is the next switch-on
        # arriving without anyone saying out loud that the leaf must be re-genesis'd.
        carrying.add(path.parent.name)
        assert declared.enabled is True, path
        assert declared.bar_interval_ms == 60_000, path
    assert carrying == set(_TREES_WITH_POSITION_CONTEXT), carrying
