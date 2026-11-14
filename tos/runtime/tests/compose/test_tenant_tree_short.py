"""The CP-3 **SHORT** tenant tree (``config/tos_runtime/cp3-setup-d-short/``) and its symmetry"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.marketfeed.policy import (
    CriticalInputPolicyConfigError,
    load_critical_input_policy,
)
from tos_runtime.venue import (
    VenuePolicyConfigError,
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from .test_deploy_policies import (
    _ADOPTED_LOT,
    _ADOPTED_MIN_QTY,
    _ADOPTED_TENANT_MAX_QTY,
    _B1A_FIELD_POLICY,
    _RESIDENT_TICK,
    _TENANT_MAX_AGE_MS,
    _TENANT_TICK,
    _filled,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_LONG_DIR = _CONFIG_ROOT / "cp3-setup-d-long"
_SHORT_DIR = _CONFIG_ROOT / "cp3-setup-d-short"

_LEGACY_STRATEGY_YAML = (
    _REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

_RETIRED_AT_LEGACY_FINAL = frozenset({"shared/strategy/entry/setup_d_adapter.py"})


def _retired_aware_source(relative: str) -> str | None:
    """The working-tree text of ``relative``, or ``None`` once L6 retired it."""
    path = _REPO_ROOT / relative
    if path.is_file():
        return path.read_text(encoding="utf-8")
    assert relative in _RETIRED_AT_LEGACY_FINAL, (
        f"{relative} is read by this test but is not in the tree and is not recorded as "
        "retired at tag `legacy-final`"
    )
    return None


_LONG_STRATEGY_REL = "strategies/setup_d_long.strategy.yaml"
_SHORT_STRATEGY_REL = "strategies/setup_d_short.strategy.yaml"

_SHORT_VENUE_POLICY_ID = "vcp-paper-cp3-setup-d-short-krx-index-futures"
_SHORT_CIP_POLICY_ID = "tos-paper-cp3-setup-d-short-critical-input-g1"
_SHORT_CIP_ISSUER_ID = "tos-paper-cp3-setup-d-short-critical-input-issuer-g1"
_SHORT_OCP_POLICY_ID = "ocp-paper-cp3-setup-d-short-krx-index-futures"

_IDENTICAL_TO_LONG = frozenset(
    {
        "action_flow_policy.yaml",
        "aggregate_risk_policy.yaml",
        "fields.yaml",
        "authority.yaml",
        "broker_scopes.yaml",
        "calendar.yaml",
        "coordinator_preconditions.yaml",
        "currentness.yaml",
        "egress_coordinates.yaml",
        "engine.yaml",
        "engine_driver.yaml",
        "evidence_cold_backup.yaml",
        "finality.yaml",
        "monitor_coverage.yaml",
        "release.yaml",
        "risk.yaml",
        "risk_attestations.yaml",
        "time.yaml",
    }
)

_DIFFERS_FROM_LONG: dict[str, frozenset[str]] = {
    "construction.yaml": frozenset({"action_class", "outbound_side"}),
    "marketfeed.yaml": frozenset({"direction"}),
    "order_construction_policy.yaml": frozenset(
        {"policy_id", "_runtime.construction.axes"}
    ),
    "venue_constraint_policy.yaml": frozenset(
        {
            "policy_id",
            "_runtime.band_source",
            "_runtime.price_scale",
        }
    ),
    "critical_input_policy.yaml": frozenset({"policy_id", "issuer_principal_id"}),
    "strategy_bindings.yaml": frozenset({"strategies"}),
    "RENDER.yaml": frozenset({"tree_id", "direction.value", "slots"}),
}

_FOLDED_PREFIXES: frozenset[tuple[str, str]] = frozenset(
    {
        ("order_construction_policy.yaml", "_runtime.construction.axes"),
        ("strategy_bindings.yaml", "strategies"),
        ("RENDER.yaml", "slots"),
        ("venue_constraint_policy.yaml", "_runtime.band_source"),
    }
)

_SHORT_ONLY = frozenset({_SHORT_STRATEGY_REL})
_LONG_ONLY = frozenset({_LONG_STRATEGY_REL})

_PROSE_DIFFERS = frozenset({"README.md"})


def _files(directory: Path) -> frozenset[str]:
    return frozenset(
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    )


def _mapping(directory: Path, rel: str) -> dict[str, Any]:
    raw = yaml.safe_load((directory / rel).read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{rel} did not load as a mapping"
    return raw


def _write(path: Path, raw: dict[str, Any]) -> Path:
    """Dump a filled policy document under ``tmp_path`` for a loader to read."""
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


def _leaves(node: Any, prefix: str = "") -> dict[str, Any]:
    """Every non-mapping node as ``{dotted.path: value}``. A list is ONE leaf -- so a reordered"""
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out.update(_leaves(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: node}


def _differing_paths(rel: str) -> set[str]:
    """Every parsed-YAML path that differs between the two trees, folded onto its declared"""
    long_leaves = _leaves(_mapping(_LONG_DIR, rel))
    short_leaves = _leaves(_mapping(_SHORT_DIR, rel))
    raw = {
        key
        for key in set(long_leaves) | set(short_leaves)
        if key not in long_leaves
        or key not in short_leaves
        or long_leaves[key] != short_leaves[key]
    }
    declared = _DIFFERS_FROM_LONG[rel]
    folded: set[str] = set()
    for key in raw:
        prefix = next(
            (d for d in declared if key == d or key.startswith(f"{d}.")), None
        )
        folded.add(prefix if prefix is not None else key)
    return folded


def test_short_tree_classification_is_exhaustive() -> None:
    """README §3's three sets must cover the tree exactly -- no file unclassified, no classified"""
    short_files = _files(_SHORT_DIR)
    long_files = _files(_LONG_DIR)
    shared = _IDENTICAL_TO_LONG | set(_DIFFERS_FROM_LONG) | _PROSE_DIFFERS

    classified = shared | _SHORT_ONLY
    assert classified == short_files, (
        f"unclassified in the SHORT tree: {sorted(short_files - classified)}; "
        f"classified but absent: {sorted(classified - short_files)}"
    )
    long_classified = shared | _LONG_ONLY
    assert long_classified == long_files, (
        f"unclassified in the LONG tree: {sorted(long_files - long_classified)}; "
        f"classified but absent: {sorted(long_classified - long_files)}"
    )

    categories = (
        _IDENTICAL_TO_LONG,
        frozenset(_DIFFERS_FROM_LONG),
        _PROSE_DIFFERS,
        _SHORT_ONLY,
        _LONG_ONLY,
    )
    for index, first in enumerate(categories):
        for second in categories[index + 1 :]:
            assert not first & second, f"classified twice: {sorted(first & second)}"

    checked = (
        _IDENTICAL_TO_LONG
        | frozenset(_DIFFERS_FROM_LONG)
        | _PROSE_DIFFERS
        | _SHORT_ONLY
        | _LONG_ONLY
    )
    assert classified | long_classified == checked

    assert len(_IDENTICAL_TO_LONG) == 18
    assert len(_DIFFERS_FROM_LONG) == 7
    assert len(_PROSE_DIFFERS) == 1
    assert len(short_files) == len(long_files) == 27


def test_the_counts_the_short_readme_states_are_read_from_it() -> None:
    """PARSE the SHORT README's §3 count line and compare it to the classification above."""
    readme = (_SHORT_DIR / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"(\d+) 파일 = 바이트 동일 (\d+) \+ YAML 이 다름 (\d+) \+ 산문이 다름 (\d+)"
        r"\(`README\.md`\) \+ SHORT 전용 (\d+)",
        readme,
    )
    assert match is not None, (
        "the SHORT README's §3 count line is gone or reworded -- this test reads it, so the "
        "sentence is load-bearing; update the regex together with the prose"
    )
    total, identical, yaml_differs, prose_differs, short_only = (
        int(group) for group in match.groups()
    )

    assert identical == len(_IDENTICAL_TO_LONG)
    assert yaml_differs == len(_DIFFERS_FROM_LONG)
    assert prose_differs == len(_PROSE_DIFFERS)
    assert short_only == len(_SHORT_ONLY)
    assert total == len(_files(_SHORT_DIR))
    assert identical + yaml_differs + prose_differs + short_only == total


@pytest.mark.parametrize("rel", sorted(_IDENTICAL_TO_LONG))
def test_identical_set_is_byte_identical_to_the_long_tree(rel: str) -> None:
    """BYTE identity, not parsed equality: these files are copies, and "copy" is a property a"""
    assert (_SHORT_DIR / rel).read_bytes() == (_LONG_DIR / rel).read_bytes(), (
        f"{rel} is classified byte-identical to the LONG tree but differs. If this was "
        f"deliberate, move it to _DIFFERS_FROM_LONG with the key paths that may differ."
    )


@pytest.mark.parametrize("rel", sorted(_PROSE_DIFFERS))
def test_prose_files_differ_and_each_describes_its_own_tree(rel: str) -> None:
    """The prose category's own check, so it is not merely classified."""
    short_text = (_SHORT_DIR / rel).read_text(encoding="utf-8")
    long_text = (_LONG_DIR / rel).read_text(encoding="utf-8")
    assert short_text != long_text

    assert short_text.startswith("# config/tos_runtime/cp3-setup-d-short/")
    assert long_text.startswith("# config/tos_runtime/cp3-setup-d-long/")
    assert "SHORT 배포" in short_text and "LONG 배포" in long_text
    assert "### 3.3 ✅ SHORT parity — **닫혔다" in short_text
    assert "LEGACY_ONLY_ENTRY" in short_text
    assert "### 3.3" not in long_text
    assert "LEGACY_ONLY_ENTRY" not in long_text


def test_the_band_source_block_is_long_only_and_fully_pinned() -> None:
    """The narrowing test for the ``_runtime.band_source`` fold (2026-10-16, CP-3 band 원천"""
    long_runtime = _mapping(_LONG_DIR, "venue_constraint_policy.yaml")["_runtime"]
    short_runtime = _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")["_runtime"]

    assert "band_source" not in short_runtime
    assert "price_scale" not in short_runtime
    assert long_runtime["price_scale"] == 100
    assert long_runtime["band_source"] == {
        "kind": "producer_journal",
        "instrument": "TBD",
        "price_scale": 100,
        "bound": "trading_date_kst",
        "read_on": ["boot", "phase_change"],
        "failure": "unknown",
        "band_journal_path": "TBD",
        "approved_source_prefixes": ["TBD"],
    }


def test_every_folded_prefix_has_a_narrowing_test() -> None:
    """``_FOLDED_PREFIXES`` must be exactly the declared paths that are not leaf scalars."""
    folded: set[tuple[str, str]] = set()
    for rel, paths in _DIFFERS_FROM_LONG.items():
        leaves = _leaves(_mapping(_LONG_DIR, rel))
        for path in paths:
            value = leaves.get(path)
            is_prefix = any(key.startswith(f"{path}.") for key in leaves)
            if is_prefix or isinstance(value, (list, dict)):
                folded.add((rel, path))
    assert folded == _FOLDED_PREFIXES, (
        f"folded declared prefixes without a recorded narrowing test: "
        f"{sorted(folded - _FOLDED_PREFIXES)}; recorded but no longer folded: "
        f"{sorted(_FOLDED_PREFIXES - folded)}. Each folded prefix needs its own test that "
        f"compares the subtree minus the direction-bearing part."
    )


def test_the_axes_list_differs_only_in_its_DIRECTION_entry() -> None:
    """``_runtime.construction.axes`` is ONE leaf to :func:`_leaves` (a list), so declaring that"""
    long_axes = _mapping(_LONG_DIR, "order_construction_policy.yaml")["_runtime"][
        "construction"
    ]["axes"]
    short_axes = _mapping(_SHORT_DIR, "order_construction_policy.yaml")["_runtime"][
        "construction"
    ]["axes"]

    assert len(long_axes) == len(short_axes)
    for axes in (long_axes, short_axes):
        assert sum(entry["axis"] == "DIRECTION" for entry in axes) == 1
    without_direction = [
        [entry for entry in axes if entry["axis"] != "DIRECTION"]
        for axes in (long_axes, short_axes)
    ]
    assert without_direction[0] == without_direction[1], (
        "the two trees' axes differ outside the DIRECTION entry: "
        f"LONG {without_direction[0]} vs SHORT {without_direction[1]}"
    )
    assert [entry["axis"] for entry in long_axes] == [
        entry["axis"] for entry in short_axes
    ]


def test_the_bindings_subtree_differs_only_in_the_direction_bearing_names() -> None:
    """``strategies`` is the other declared prefix that folds a whole subtree -- same hazard as"""
    long_strategies = _mapping(_LONG_DIR, "strategy_bindings.yaml")["strategies"]
    short_strategies = _mapping(_SHORT_DIR, "strategy_bindings.yaml")["strategies"]

    assert len(long_strategies) == len(short_strategies) == 1
    (long_stem, long_entry), (short_stem, short_entry) = (
        next(iter(long_strategies.items())),
        next(iter(short_strategies.items())),
    )
    assert long_stem == "setup_d_long.strategy"
    assert short_stem == "setup_d_short.strategy"

    assert set(long_entry) == set(short_entry) == {"config_binding_version", "bindings"}
    assert long_entry["config_binding_version"] == short_entry["config_binding_version"]

    assert len(long_entry["bindings"]) == len(short_entry["bindings"]) == 1
    (long_key, long_value), (short_key, short_value) = (
        next(iter(long_entry["bindings"].items())),
        next(iter(short_entry["bindings"].items())),
    )
    assert long_key == "z_entry_max_x1000"
    assert short_key == "z_entry_min_x1000"
    assert long_value + short_value == 0


def test_the_render_manifest_slot_list_differs_only_in_the_direction_bearing_rows() -> (
    None
):
    """``slots`` is a LIST, so :func:`_leaves` folds the whole render manifest's rule table into"""
    long_slots_all = _mapping(_LONG_DIR, "RENDER.yaml")["slots"]
    short_slots = _mapping(_SHORT_DIR, "RENDER.yaml")["slots"]

    long_band = [row for row in long_slots_all if "band_source" in row["key"]]
    short_band = [row for row in short_slots if "band_source" in row["key"]]
    assert [row["key"] for row in long_band] == [
        "_runtime.band_source.instrument",
        "_runtime.band_source.band_journal_path",
        "_runtime.band_source.approved_source_prefixes",
    ]
    assert short_band == []

    long_slots = [row for row in long_slots_all if "band_source" not in row["key"]]
    assert len(long_slots) == len(short_slots) == 20
    for row in (*long_slots, *short_slots):
        assert set(row) == {"file", "key", "anchor", "replacement", "value"}

    def _normalise(slots: list[dict[str, str]], direction: str) -> list[dict[str, str]]:
        """The rows with this tree's direction token and strategy file name erased."""
        tokens = {
            "LONG": ("LONG", "NEW_LONG", "BUY", "setup_d_long"),
            "SHORT": ("SHORT", "NEW_SHORT", "SELL", "setup_d_short"),
        }[direction]
        out = []
        for row in slots:
            normalised = {}
            for key, value in row.items():
                for token, placeholder in zip(
                    tokens,
                    ("<DIR>", "<ACTION_CLASS>", "<SIDE>", "<STRATEGY>"),
                    strict=True,
                ):
                    value = value.replace(token, placeholder)
                normalised[key] = value
            out.append(normalised)
        return out

    assert _normalise(long_slots, "LONG") == _normalise(short_slots, "SHORT")

    differing = [
        long_row["key"]
        for long_row, short_row in zip(long_slots, short_slots, strict=True)
        if long_row != short_row
    ]
    assert sorted(differing) == sorted(
        [
            "_runtime.construction.axes.DIRECTION",
            "action_class",
            "outbound_side",
            "direction",
            "policy.rules[0].decision.target.account",
            "policy.rules[0].decision.target.instrument",
            "policy.rules[0].decision.target.direction",
        ]
    ), differing


def test_the_two_render_manifests_declare_the_same_tenant_modes() -> None:
    """Both tenant manifests are ``declared`` + ``external``; only the declared VALUE differs"""
    long_manifest = _mapping(_LONG_DIR, "RENDER.yaml")
    short_manifest = _mapping(_SHORT_DIR, "RENDER.yaml")
    assert long_manifest["tree_id"] == "cp3-setup-d-long"
    assert short_manifest["tree_id"] == "cp3-setup-d-short"
    for manifest in (long_manifest, short_manifest):
        assert manifest["direction"]["mode"] == "declared"
        assert manifest["journal"]["mode"] == "external"
    assert long_manifest["direction"]["value"] == "LONG"
    assert short_manifest["direction"]["value"] == "SHORT"


@pytest.mark.parametrize("rel", sorted(_DIFFERS_FROM_LONG))
def test_differing_files_differ_in_exactly_the_declared_key_paths(rel: str) -> None:
    """The guard, stated as an equality rather than a subset: the set of parsed-YAML paths that"""
    assert _differing_paths(rel) == _DIFFERS_FROM_LONG[rel]


def test_short_direction_is_consistent_across_every_slot_that_carries_one() -> None:
    """All five direction slots agree on SHORT, and each pairs with the shape the OCP declares."""
    ocp = _mapping(_SHORT_DIR, "order_construction_policy.yaml")
    axes = ocp["_runtime"]["construction"]["axes"]
    direction_axes = [entry for entry in axes if entry["axis"] == "DIRECTION"]
    assert len(direction_axes) == 1
    assert direction_axes[0]["value"] == "SHORT"

    construction = _mapping(_SHORT_DIR, "construction.yaml")
    shape = ocp["_runtime"]["construction"]["action_class_shape"]
    assert construction["action_class"] == "NEW_SHORT"
    assert shape["NEW_SHORT"]["SHORT"]["side"] == construction["outbound_side"]
    assert construction["outbound_side"] == "SELL"

    assert _mapping(_SHORT_DIR, "marketfeed.yaml")["direction"] == "SHORT"

    strategy = _mapping(_SHORT_DIR, _SHORT_STRATEGY_REL)
    entry = strategy["policy"]["rules"][0]["decision"]["target"]
    assert entry["direction"] == "SHORT"
    assert entry["position_effect"] == shape["NEW_SHORT"]["SHORT"]["position_effect"]


def test_long_tree_still_says_long_in_all_five() -> None:
    """The mirror half. Landing the SHORT tree must not have edited the LONG one -- a single"""
    ocp = _mapping(_LONG_DIR, "order_construction_policy.yaml")
    axes = [
        e for e in ocp["_runtime"]["construction"]["axes"] if e["axis"] == "DIRECTION"
    ]
    assert [e["value"] for e in axes] == ["LONG"]
    construction = _mapping(_LONG_DIR, "construction.yaml")
    assert construction["action_class"] == "NEW_LONG"
    assert construction["outbound_side"] == "BUY"
    assert _mapping(_LONG_DIR, "marketfeed.yaml")["direction"] == "LONG"
    strategy = _mapping(_LONG_DIR, _LONG_STRATEGY_REL)
    assert strategy["policy"]["rules"][0]["decision"]["target"]["direction"] == "LONG"


def test_each_direction_slot_occurs_exactly_once_in_its_file() -> None:
    """Each slot is ONE line, in both trees."""
    slots = (
        (_SHORT_DIR, "construction.yaml", 'action_class: "NEW_SHORT"'),
        (_SHORT_DIR, "construction.yaml", 'outbound_side: "SELL"'),
        (_SHORT_DIR, "marketfeed.yaml", 'direction: "SHORT"'),
        (_SHORT_DIR, "order_construction_policy.yaml", '        value: "SHORT"'),
        (_LONG_DIR, "construction.yaml", 'action_class: "NEW_LONG"'),
        (_LONG_DIR, "construction.yaml", 'outbound_side: "BUY"'),
        (_LONG_DIR, "marketfeed.yaml", 'direction: "LONG"'),
        (_LONG_DIR, "order_construction_policy.yaml", '        value: "LONG"'),
    )
    for directory, rel, needle in slots:
        lines = (directory / rel).read_text(encoding="utf-8").split("\n")
        hits = [index for index, line in enumerate(lines) if line == needle]
        assert len(hits) == 1, (
            f"{directory.name}/{rel}: the exact line {needle!r} occurs {len(hits)} times "
            f"(lines {[i + 1 for i in hits]}), expected exactly 1 — "
            f"render_paper_config.py::_apply_rules refuses anything but one match"
        )


def test_flat_rule_direction_is_the_closing_action_not_the_position() -> None:
    """The two meanings of the ``direction`` token, pinned so they cannot silently converge."""
    for directory, rel, entry_direction, closing_direction in (
        (_SHORT_DIR, _SHORT_STRATEGY_REL, "SHORT", "LONG"),
        (_LONG_DIR, _LONG_STRATEGY_REL, "LONG", "SHORT"),
    ):
        strategy = _mapping(directory, rel)
        rules = strategy["policy"]["rules"]
        assert len(rules) == 3
        assert rules[0]["decision"]["target"]["direction"] == entry_direction
        for rule in rules[1:]:
            target = rule["decision"]["target"]
            assert target["kind"] == "FLAT"
            assert target["position_effect"] == "CLOSE"
            assert target["direction"] == closing_direction
            assert target["direction"] != entry_direction

        shape = _mapping(directory, "order_construction_policy.yaml")["_runtime"][
            "construction"
        ]["action_class_shape"]
        assert shape["CLOSE"][entry_direction]["position_effect"] == "CLOSE"
        assert shape["CLOSE"]["LONG"]["side"] == "SELL"
        assert shape["CLOSE"]["SHORT"]["side"] == "BUY"


def test_short_entry_comparison_is_the_positive_side_through_its_binding() -> None:
    """The fifth direction slot: the DSL comparison's operator, its operand, and the binding key."""
    for directory, rel, op, key in (
        (_SHORT_DIR, _SHORT_STRATEGY_REL, "GE", "z_entry_min_x1000"),
        (_LONG_DIR, _LONG_STRATEGY_REL, "LE", "z_entry_max_x1000"),
    ):
        entry_rule = _mapping(directory, rel)["policy"]["rules"][0]
        z_compares = [
            compare
            for compare in entry_rule["all_of"]
            if compare["left"].get("ref") == ["capsule", "resolved_values", "z_x1000"]
        ]
        assert len(z_compares) == 1, f"{rel}: expected exactly one z_x1000 comparison"
        compare = z_compares[0]
        assert compare["op"] == op
        assert "const" not in compare["right"]
        assert compare["right"]["ref"] == ["config", key]

        bindings = _mapping(directory, "strategy_bindings.yaml")["strategies"]
        stem = Path(rel).name.removesuffix(".yaml")
        assert set(bindings) == {stem}
        assert set(bindings[stem]["bindings"]) == {key}


def test_short_z_entry_binding_is_plus_trunc_extreme_atr_mult_times_1000() -> None:
    """``z_entry_min_x1000 == +trunc(extreme_atr_mult x 1000)``, the SHORT mirror of the LONG"""
    legacy = yaml.safe_load(_LEGACY_STRATEGY_YAML.read_text(encoding="utf-8"))
    extreme = legacy["strategy"]["entry"]["params"]["extreme_atr_mult"]
    threshold = int(extreme * 1000)

    short_bindings = _mapping(_SHORT_DIR, "strategy_bindings.yaml")["strategies"][
        "setup_d_short.strategy"
    ]["bindings"]
    long_bindings = _mapping(_LONG_DIR, "strategy_bindings.yaml")["strategies"][
        "setup_d_long.strategy"
    ]["bindings"]

    assert short_bindings["z_entry_min_x1000"] == threshold
    assert long_bindings["z_entry_max_x1000"] == -threshold
    assert short_bindings["z_entry_min_x1000"] + long_bindings["z_entry_max_x1000"] == 0

    for directory, rel, stem in (
        (_SHORT_DIR, _SHORT_STRATEGY_REL, "setup_d_short.strategy"),
        (_LONG_DIR, _LONG_STRATEGY_REL, "setup_d_long.strategy"),
    ):
        declared = _mapping(directory, rel)["config_binding_version"]
        bound = _mapping(directory, "strategy_bindings.yaml")["strategies"][stem][
            "config_binding_version"
        ]
        assert declared == bound


def test_short_tree_policy_ids_are_short_specific() -> None:
    """Every policy whose CONTENT diverges gets its own ``policy_id``; the ones that are the"""
    assert (
        _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")["policy_id"]
        == _SHORT_VENUE_POLICY_ID
    )
    cip = _mapping(_SHORT_DIR, "critical_input_policy.yaml")
    assert cip["policy_id"] == _SHORT_CIP_POLICY_ID
    assert cip["issuer_principal_id"] == _SHORT_CIP_ISSUER_ID
    assert (
        _mapping(_SHORT_DIR, "order_construction_policy.yaml")["policy_id"]
        == _SHORT_OCP_POLICY_ID
    )

    for rel, key in (
        ("venue_constraint_policy.yaml", "policy_id"),
        ("critical_input_policy.yaml", "policy_id"),
        ("critical_input_policy.yaml", "issuer_principal_id"),
        ("order_construction_policy.yaml", "policy_id"),
    ):
        assert _mapping(_SHORT_DIR, rel)[key] != _mapping(_LONG_DIR, rel)[key], (
            rel,
            key,
        )

    assert (
        _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")["policy_generation"] == 1
    )
    assert cip["policy_generation"] == 1

    for rel in ("aggregate_risk_policy.yaml", "action_flow_policy.yaml"):
        assert (
            _mapping(_SHORT_DIR, rel)["policy_id"]
            == _mapping(_LONG_DIR, rel)["policy_id"]
        )


def test_policy_digests_cannot_tell_the_two_trees_apart(tmp_path: Path) -> None:
    """MEASURED 2026-10-09: neither the OCP's nor the VCP's ``canonical_digest`` distinguishes"""
    long_ocp = load_order_construction_policy(
        _write(
            tmp_path / "long_ocp.yaml",
            _filled(
                _LONG_DIR / "order_construction_policy.yaml",
                environment="paper",
                account="a",
                instrument="i",
                admits_flat_exit=True,
            ),
        ),
        scheme=_SCHEME,
    )
    short_ocp = load_order_construction_policy(
        _write(
            tmp_path / "short_ocp.yaml",
            _filled(
                _SHORT_DIR / "order_construction_policy.yaml",
                environment="paper",
                account="a",
                instrument="i",
                direction="SHORT",
                admits_flat_exit=True,
            ),
        ),
        scheme=_SCHEME,
    )
    assert long_ocp.policy.policy_id != short_ocp.policy.policy_id
    assert long_ocp.policy.canonical_digest == short_ocp.policy.canonical_digest

    long_raw = _filled(
        _LONG_DIR / "venue_constraint_policy.yaml",
        environment="paper",
        account="a",
        instrument="i",
    )
    short_raw = _filled(
        _SHORT_DIR / "venue_constraint_policy.yaml",
        environment="paper",
        account="a",
        instrument="i",
    )
    long_vcp = load_venue_constraint_policy(
        _write(tmp_path / "long_vcp.yaml", long_raw), scheme=_SCHEME
    )
    short_vcp = load_venue_constraint_policy(
        _write(tmp_path / "short_vcp.yaml", short_raw), scheme=_SCHEME
    )
    assert long_vcp.policy.policy_id != short_vcp.policy.policy_id
    assert long_vcp.policy.shape_constraints == short_vcp.policy.shape_constraints
    assert long_vcp.policy.canonical_digest == short_vcp.policy.canonical_digest

    mutated = {
        **short_raw,
        "_model_view": {
            **short_raw["_model_view"],
            "shape_constraints": {
                **short_raw["_model_view"]["shape_constraints"],
                "tick_size": _RESIDENT_TICK,
            },
        },
    }
    mutated_vcp = load_venue_constraint_policy(
        _write(tmp_path / "mutated_vcp.yaml", mutated), scheme=_SCHEME
    )
    assert mutated_vcp.policy.canonical_digest != short_vcp.policy.canonical_digest


def test_short_tree_venue_policy_refuses_until_the_operator_fills_the_scope() -> None:
    """Same operator-fill gate as the LONG tree: ``accounts``/``instruments`` are ``"TBD"`` as"""
    with pytest.raises(VenuePolicyConfigError):
        load_venue_constraint_policy(
            _SHORT_DIR / "venue_constraint_policy.yaml", scheme=_SCHEME
        )


def test_short_tree_inherits_the_tenant_values(tmp_path: Path) -> None:
    """The values commits (a) and (b) landed in the LONG tree are in this one too -- the"""
    raw = _filled(
        _SHORT_DIR / "venue_constraint_policy.yaml",
        environment="paper",
        account="acct-x",
        instrument="inst-x",
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True))
    shape = load_venue_constraint_policy(path, scheme=_SCHEME).policy.shape_constraints
    assert shape.tick_size == _TENANT_TICK
    assert shape.max_quantity == _ADOPTED_TENANT_MAX_QTY
    assert shape.lot_size == _ADOPTED_LOT
    assert shape.min_quantity == _ADOPTED_MIN_QTY
    assert shape.price_min is None and shape.price_max is None

    policy = load_critical_input_policy(
        _SHORT_DIR / "critical_input_policy.yaml", scheme=_SCHEME
    )
    assert [field.field_key for field in policy.fields] == list(_B1A_FIELD_POLICY)
    assert {field.max_age_ms for field in policy.fields} == {_TENANT_MAX_AGE_MS}


def test_short_tree_critical_input_policy_still_refuses_a_null_max_age_ms(
    tmp_path: Path,
) -> None:
    """The null-refusal guard applies to this tree as well -- the fill did not retire it here"""
    raw = _mapping(_SHORT_DIR, "critical_input_policy.yaml")
    assert raw["fields"][-1]["field_key"] == "eod"
    raw["fields"][-1]["max_age_ms"] = None
    path = tmp_path / "critical_input_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(CriticalInputPolicyConfigError) as excinfo:
        load_critical_input_policy(path, scheme=_SCHEME)
    assert "max_age_ms" in str(excinfo.value)


def test_short_tree_construction_price_field_keys_are_declared_critical_inputs() -> (
    None
):
    """The cross-check neither loader can perform, applied to this tree -- the LONG tree's H1"""
    construction = _mapping(_SHORT_DIR, "construction.yaml")
    declared = {
        entry["field_key"]
        for entry in _mapping(_SHORT_DIR, "critical_input_policy.yaml")["fields"]
    }
    for key_name in ("price_field_key", "shape_price_field_key"):
        assert construction[key_name] in declared, (key_name, construction[key_name])


def test_short_tree_scope_authorizes_both_directions() -> None:
    """The non-negotiable long/short symmetry rule as a mechanical pin, mirrored from the"""
    ocp = _mapping(_SHORT_DIR, "order_construction_policy.yaml")
    assert set(ocp["scope"]["action_classes"]) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    shape = ocp["_runtime"]["construction"]["action_class_shape"]
    assert set(shape) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    assert set(shape["CLOSE"]) == {"LONG", "SHORT"}
    venue = _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")
    assert set(venue["scope"]["action_classes"]) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}


def test_short_tree_records_its_parity_result() -> None:
    """README §3.3: the SHORT parity run and its two remaining qualifications."""
    prose = (_SHORT_DIR / "README.md").read_text(encoding="utf-8")
    assert "B1b-D5" in prose
    assert "176/176" in prose
    assert "UNRESOLVED 0" in prose
    assert "LEGACY_ONLY_ENTRY" in prose
    assert "short_blocked_regimes" in prose
    assert "setup_d_adapter" in prose
    assert "B1b-D8" in prose

    legacy = yaml.safe_load(_LEGACY_STRATEGY_YAML.read_text(encoding="utf-8"))
    params = legacy["strategy"]["entry"]["params"]
    assert params[
        "short_blocked_regimes"
    ], "README §3.3 claims the legacy strategy blocks SHORT in some regimes; it no longer does"
    assert not params[
        "long_blocked_regimes"
    ], "README §3.3 claims the guard was SHORT-only; long_blocked_regimes is now non-empty"

    source = _retired_aware_source("shared/strategy/entry/setup_d_adapter.py")
    if source is not None:
        assert source.index("self._setup.check(") < source.index(
            "short_blocked_regimes"
        ), (
            "the regime block moved ahead of check(); README §3.3 2 now claims something "
            "false about what a B1a/B2/B1b comparison can see"
        )
