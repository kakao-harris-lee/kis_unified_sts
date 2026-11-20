"""The tenant trees' entry threshold: ``fields.yaml`` const <-> ``z_entry_*`` binding."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml

from shared.indicators.fields import load_fields_file

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = REPO_ROOT / "config" / "tos_runtime"
LEGACY_STRATEGY_YAML = (
    REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

TREES: tuple[tuple[str, str, str, int], ...] = (
    ("cp3-setup-d-long", "setup_d_long.strategy", "z_entry_max_x1000", -1),
    ("cp3-setup-d-short", "setup_d_short.strategy", "z_entry_min_x1000", +1),
    ("cp3-setup-d-stock-005930", "setup_d_long.strategy", "z_entry_max_x1000", -1),
    ("cp3-setup-d-stock-000660", "setup_d_long.strategy", "z_entry_max_x1000", -1),
    ("cp3-setup-d-stock-005380", "setup_d_long.strategy", "z_entry_max_x1000", -1),
)

EXPECTED_EXTREME_ATR_MULT = 1.8
EXPECTED_ABS_BINDING = 1800


def _tree_ids() -> list[str]:
    return [tree for tree, _, _, _ in TREES]


def _bindings(tree: str, stem: str) -> dict[str, Any]:
    document = yaml.safe_load(
        (CONFIG_ROOT / tree / "strategy_bindings.yaml").read_text(encoding="utf-8")
    )
    return dict(document["strategies"][stem]["bindings"])


def _field_consts(tree: str) -> dict[str, float]:
    document = load_fields_file(CONFIG_ROOT / tree / "fields.yaml")
    by_name = {spec.name: spec for spec in document.fields}
    return {
        "z_short_side": by_name["z_short_side"].params["const"],
        "z_long_side": by_name["z_long_side"].params["const"],
    }


@pytest.mark.parametrize("tree", _tree_ids())
def test_fields_yaml_declares_the_extreme_threshold_on_both_sides(tree: str) -> None:
    """+-1.8 in the declaration the producer reads, written out (#1080)."""
    consts = _field_consts(tree)

    assert consts["z_short_side"] == EXPECTED_EXTREME_ATR_MULT
    assert consts["z_long_side"] == -EXPECTED_EXTREME_ATR_MULT


@pytest.mark.parametrize(("tree", "stem", "key", "sign"), TREES, ids=_tree_ids())
def test_tenant_binds_z_entry_to_the_signed_threshold(
    tree: str, stem: str, key: str, sign: int
) -> None:
    """+-1800 in each shipped tree, including the stock tree nothing else covered."""
    bindings = _bindings(tree, stem)

    assert key in bindings, f"{tree}: {key} missing from strategy_bindings.yaml"
    assert bindings[key] == sign * EXPECTED_ABS_BINDING


@pytest.mark.parametrize(("tree", "stem", "key", "sign"), TREES, ids=_tree_ids())
def test_binding_is_trunc_of_its_own_tree_fields_const_times_1000(
    tree: str, stem: str, key: str, sign: int
) -> None:
    """The derivation, read from THIS tree's fields.yaml -- not a test-local literal."""
    consts = _field_consts(tree)
    side_const = consts["z_short_side"] if sign > 0 else consts["z_long_side"]

    assert _bindings(tree, stem)[key] == math.trunc(side_const * 1000)


def test_the_two_directions_are_exact_mirrors() -> None:
    """LONG's max and SHORT's min sum to zero -- the long/short symmetry rule."""
    long_bindings = _bindings("cp3-setup-d-long", "setup_d_long.strategy")
    short_bindings = _bindings("cp3-setup-d-short", "setup_d_short.strategy")

    assert long_bindings["z_entry_max_x1000"] + short_bindings["z_entry_min_x1000"] == 0


def test_the_cited_extreme_atr_mult_still_matches_the_legacy_setup_d_yaml() -> None:
    """The citation every tree's ``strategy_bindings.yaml`` derivation rests on."""
    legacy = yaml.safe_load(LEGACY_STRATEGY_YAML.read_text(encoding="utf-8"))
    extreme = legacy["strategy"]["entry"]["params"]["extreme_atr_mult"]

    assert extreme == EXPECTED_EXTREME_ATR_MULT
    assert math.trunc(extreme * 1000) == EXPECTED_ABS_BINDING


@pytest.mark.parametrize(("tree", "stem", "key", "sign"), TREES, ids=_tree_ids())
def test_the_strategy_rule_actually_reads_the_bound_key(
    tree: str, stem: str, key: str, sign: int
) -> None:
    """A bound value nothing references is a number that cannot change an outcome."""
    strategy = yaml.safe_load(
        (CONFIG_ROOT / tree / "strategies" / f"{stem}.yaml").read_text(encoding="utf-8")
    )
    entry_rule = strategy["policy"]["rules"][0]

    z_compares = [
        compare
        for compare in entry_rule["all_of"]
        if compare["left"].get("ref") == ["capsule", "resolved_values", "z_x1000"]
    ]

    assert len(z_compares) == 1, f"{tree}: expected exactly one z_x1000 comparison"
    compare = z_compares[0]
    assert compare["right"]["ref"] == ["config", key]
    assert compare["op"] == ("GE" if sign > 0 else "LE")


@pytest.mark.parametrize("tree", _tree_ids())
def test_fields_yaml_compares_each_side_with_the_matching_operator(tree: str) -> None:
    """The threshold is only half the declaration -- the operator is the other half."""
    document = load_fields_file(CONFIG_ROOT / tree / "fields.yaml")
    by_name = {spec.name: spec for spec in document.fields}

    assert by_name["z_short_side"].op_name == "ge"
    assert by_name["z_long_side"].op_name == "le"


def test_every_shipped_tenant_tree_is_covered_by_this_module() -> None:
    """A tree added later must not be silently skipped by this module's TREES."""
    discovered_bindings = {
        path.parent.relative_to(CONFIG_ROOT).as_posix()
        for path in CONFIG_ROOT.rglob("strategy_bindings.yaml")
    }
    discovered_fields = {
        path.parent.relative_to(CONFIG_ROOT).as_posix()
        for path in CONFIG_ROOT.rglob("fields.yaml")
    }

    assert discovered_bindings == set(_tree_ids()), (
        "a tenant tree with strategy_bindings.yaml is not in TREES (or vice "
        f"versa): found {sorted(discovered_bindings)}"
    )
    assert discovered_fields == set(
        _tree_ids()
    ), f"a tenant tree with fields.yaml is not in TREES: {sorted(discovered_fields)}"
