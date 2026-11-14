"""Decision-generation pin for the CP-3 tenants that run on a PERSISTENT data leaf."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.dsl.serialization import parse_strategy
from tos.engine.admission import policy_work_steps
from tos_runtime.compose._engine_config import load_engine_config
from tos_runtime.compose._finalize_wiring import _ENGINE_CONFIG_NAME
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_REGISTRY = _CONFIG_ROOT / "decision_generations.yaml"
_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "cp3_tenant_daily.sh"

_PERSISTENT_LEAF_TENANTS = (
    "cp3-setup-d-long",
    "cp3-setup-d-short",
    "cp3-setup-d-stock-005930",
)

_PROBE_RULE_PREFIX = "R4-M2-PROBE-ENTRY-LONG:"
_PROBE_BINDING = "m2_probe_entry_enabled"
_STOCK = "cp3-setup-d-stock-005930"


def decision_digest(tree: Path) -> str:
    """The digest of ``tree``'s PARSED decision contract (module docstring)."""
    strategy_dir = tree / "strategies"
    digests: dict[str, str] = {}
    for path in sorted(strategy_dir.iterdir()):
        assert path.name.endswith(".strategy.yaml"), (
            f"{path}: not a strategy file — the strategy loader refuses the whole "
            "directory for a stray file, so this digest will not quietly skip it"
        )
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        canonical = parse_strategy(raw).canonical_digest
        assert (
            canonical is not None
        ), f"{path}: parse_strategy issued no canonical digest"
        digests[path.name] = canonical
    assert digests, f"{strategy_dir}: no strategy files"

    loaded = load_strategy_bindings(tree / STRATEGY_BINDINGS_FILE_NAME)
    bindings = {
        stem: entry.model_dump(mode="json")
        for stem, entry in sorted(loaded.strategies.items())
    }
    engine = dataclasses.asdict(load_engine_config(tree / _ENGINE_CONFIG_NAME))
    payload = json.dumps(
        {"strategies": digests, "bindings": bindings, "engine": engine},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pin_problem(tenant: str, tree: Path, entry: dict[str, Any]) -> str | None:
    """``None`` iff ``entry`` still pins ``tree``'s decision contract; else what to do."""
    measured = decision_digest(tree)
    if measured == entry["decision_digest"]:
        return None
    return (
        f"decision contract changed for persistent-leaf tenant {tenant!r}\n"
        f"  committed: generation {entry['generation']}  {entry['decision_digest']}\n"
        f"  measured : {measured}\n"
        "\n"
        "This tenant reuses ONE durable data leaf across days, and every boot re-derives the\n"
        "whole recorded decision ledger against TODAY's strategy\n"
        "(tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt). A changed\n"
        "decision contract therefore makes the next boot refuse with EngineReplayDiverged and\n"
        "write PERMANENT REPLAY_DIVERGED rows, which leaves the leaf un-bootable\n"
        "(tos_runtime.recovery.inputs._replay_verdict_ok requires that count to be zero).\n"
        "That is the 2026-11-12 stock refusal — 1075 of 1075 events, PR #1056.\n"
        "\n"
        "To land this change, IN THIS PR:\n"
        "  1. in config/tos_runtime/decision_generations.yaml, bump this tenant's\n"
        f"     'generation' to {entry['generation'] + 1} and set its 'decision_digest'\n"
        "     to the measured value above; AND\n"
        "  2. archive that tenant's data leaf so the next session genesis-creates a fresh\n"
        "     one, BEFORE this deploys — docs/runbooks/tos-paper-boot.md §7.2-f ('genesis').\n"
        "Step 2 is the point; step 1 without it still poisons the leaf."
    )


def _registry() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(_REGISTRY.read_text(encoding="utf-8"))
    assert isinstance(raw, dict), f"{_REGISTRY}: not a top-level mapping"
    tenants = raw.get("tenants")
    assert isinstance(tenants, dict), f"{_REGISTRY}: 'tenants' is not a mapping"
    return tenants


@pytest.mark.parametrize("tenant", _PERSISTENT_LEAF_TENANTS)
def test_the_committed_decision_generation_still_pins_the_tree(tenant: str) -> None:
    """The guard itself: the tree's parsed decision contract is the pinned one."""
    problem = _pin_problem(tenant, _CONFIG_ROOT / tenant, _registry()[tenant])
    assert problem is None, problem


@pytest.mark.parametrize("tenant", _PERSISTENT_LEAF_TENANTS)
def test_every_persistent_leaf_tenant_pins_a_well_formed_token(tenant: str) -> None:
    """A token is a generation number AND a digest — neither half is optional."""
    entry = _registry()[tenant]
    assert set(entry) == {"generation", "decision_digest"}, entry
    assert isinstance(entry["generation"], int) and not isinstance(
        entry["generation"], bool
    ), entry["generation"]
    assert entry["generation"] >= 1, entry["generation"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", entry["decision_digest"]), entry[
        "decision_digest"
    ]


def test_the_registry_covers_exactly_the_runners_persistent_leaf_tenants() -> None:
    """The tenant list is the runner's, so a fourth tenant cannot land uncovered."""
    text = _RUNNER.read_text(encoding="utf-8")
    declared: set[str] = set()
    for value in re.findall(r"^\s*TREE=(\S+)", text, flags=re.MULTILINE):
        if "$lc" in value:
            declared |= {value.replace("$lc", lc) for lc in ("long", "short")}
        else:
            declared.add(value)
    assert declared, f"{_RUNNER}: no TREE= assignment found — did the runner move?"
    assert declared == set(_PERSISTENT_LEAF_TENANTS), declared
    assert set(_registry()) == set(_PERSISTENT_LEAF_TENANTS), set(_registry())
    for tenant in _PERSISTENT_LEAF_TENANTS:
        assert (_CONFIG_ROOT / tenant).is_dir(), tenant


def _rewrite_stock_tree(
    destination: Path,
    *,
    drop_probe_rule: bool = False,
    probe_enabled: bool | None = None,
    budget_steps: int | None = None,
    comment_header: str = "",
) -> Path:
    """A re-serialized copy of the stock tree's decision contract under ``destination``."""
    source = _CONFIG_ROOT / _STOCK
    (destination / "strategies").mkdir(parents=True)

    name = "setup_d_long.strategy.yaml"
    strategy = yaml.safe_load(
        (source / "strategies" / name).read_text(encoding="utf-8")
    )
    rules = strategy["policy"]["rules"]
    probe = [
        index
        for index, rule in enumerate(rules)
        if rule["decision"]["rationale"].startswith(_PROBE_RULE_PREFIX)
    ]
    assert probe == [len(rules) - 1], (
        f"the stock tree's {_PROBE_RULE_PREFIX} rule is no longer the last rule "
        f"(found at {probe}) — these proofs describe PR #1056's shape"
    )
    if drop_probe_rule:
        del rules[probe[0]]
    (destination / "strategies" / name).write_text(
        comment_header + yaml.safe_dump(strategy, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )

    bindings = yaml.safe_load(
        (source / STRATEGY_BINDINGS_FILE_NAME).read_text(encoding="utf-8")
    )
    values = bindings["strategies"]["setup_d_long.strategy"]["bindings"]
    assert values[_PROBE_BINDING] is True, values
    if drop_probe_rule:
        del values[_PROBE_BINDING]
    elif probe_enabled is not None:
        values[_PROBE_BINDING] = probe_enabled
    (destination / STRATEGY_BINDINGS_FILE_NAME).write_text(
        comment_header + yaml.safe_dump(bindings, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )

    engine = yaml.safe_load((source / _ENGINE_CONFIG_NAME).read_text(encoding="utf-8"))
    assert engine["dsl_evaluation_budget_steps"] == 64, engine
    if budget_steps is not None:
        engine["dsl_evaluation_budget_steps"] = budget_steps
    (destination / _ENGINE_CONFIG_NAME).write_text(
        comment_header + yaml.safe_dump(engine, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    return destination


def test_the_1056_change_against_an_unbumped_token_is_caught(tmp_path: Path) -> None:
    """The regression: PR #1056's exact input, red."""
    pre = _rewrite_stock_tree(tmp_path / "pre-1056", drop_probe_rule=True)
    generation_1 = decision_digest(pre)
    assert generation_1 != decision_digest(_CONFIG_ROOT / _STOCK), (
        "adding R4 + its binding did not move the decision digest — this guard would have "
        "slept through #1056"
    )

    problem = _pin_problem(
        _STOCK,
        _CONFIG_ROOT / _STOCK,
        {"generation": 1, "decision_digest": generation_1},
    )
    assert problem is not None
    assert "decision contract changed" in problem
    assert "genesis" in problem and "§7.2-f" in problem
    assert generation_1 in problem and decision_digest(_CONFIG_ROOT / _STOCK) in problem


def test_starving_the_dsl_budget_under_an_unbumped_token_is_caught(
    tmp_path: Path,
) -> None:
    """The review finding: ``engine.yaml``'s bounds are replay inputs too."""
    name = "setup_d_long.strategy.yaml"
    strategy = parse_strategy(
        yaml.safe_load(
            (_CONFIG_ROOT / _STOCK / "strategies" / name).read_text(encoding="utf-8")
        )
    )
    assert strategy.policy is not None
    assert policy_work_steps(strategy.policy) == 31

    starved = _rewrite_stock_tree(
        tmp_path / "budget-30", probe_enabled=True, budget_steps=30
    )
    problem = _pin_problem(_STOCK, starved, _registry()[_STOCK])
    assert problem is not None
    assert "decision contract changed" in problem and "§7.2-f" in problem


def test_toggling_the_probe_binding_moves_the_decision_digest(tmp_path: Path) -> None:
    """``m2_probe_entry_enabled: true -> false`` is a decision change like any other."""
    on = _rewrite_stock_tree(tmp_path / "on", probe_enabled=True)
    off = _rewrite_stock_tree(tmp_path / "off", probe_enabled=False)
    assert decision_digest(on) != decision_digest(off)


def test_a_comment_only_edit_does_not_move_the_decision_digest(tmp_path: Path) -> None:
    """The cry-wolf case: formatting and comments are not a decision change."""
    commented = _rewrite_stock_tree(
        tmp_path / "commented",
        probe_enabled=True,
        comment_header="# a comment-only edit — no decision changes here\n#\n",
    )
    assert decision_digest(commented) == decision_digest(_CONFIG_ROOT / _STOCK)
