"""Decision-generation pin for the CP-3 tenants that run on a PERSISTENT data leaf.

**The incident this exists to stop** (CLAUDE.md R5). 2026-11-12 08:53 the KIS-MOCK stock
tenant session ``stock-r1-20261112`` was refused at boot: ``run: refused —
compose_paper_runtime raised EngineReplayDiverged: engine replay diverged for 1075 of 1075
compared events``. PR #1056 had added a fourth decision rule (``R4-M2-PROBE-ENTRY-LONG``)
and the ``m2_probe_entry_enabled`` binding to
``config/tos_runtime/cp3-setup-d-stock-005930/`` while that tenant keeps ONE durable data
leaf across days (``~/.local/state/tos/cp3-setup-d-stock-005930-data/005930``, born
2026-11-06). :func:`tos_runtime.compose._boot_integrity.verify_engine_replay_or_halt`
re-derives every recorded decision outcome against TODAY's strategy at every boot, so a
3-rule ledger re-derived under a 4-rule strategy diverged on all 1075 events — and that
refusal wrote 1075 permanent ``REPLAY_DIVERGED`` rows, which
``tos_runtime.recovery.inputs._replay_verdict_ok`` requires to be ZERO. The leaf was left
UN-BOOTABLE and had to be archived so the next session could genesis-create a fresh one.

Neither the author nor the reviewer connected «the decision contract changed» to «the
persistent leaf must be re-genesis'd first» — the PR body even cited the continuing leaf, to
dismiss a different concern. Nothing in CI said it either. This file is that lane: each
tenant's parsed decision contract is pinned to a committed token in
``config/tos_runtime/decision_generations.yaml``, so the change goes red at PR time and the
bump is the explicit, reviewable act that says "new decision generation ⇒ re-genesis the
leaf before this deploys" (runbook ``docs/runbooks/tos-paper-boot.md`` §7.2-f).

**Why the PARSED contract and not the bytes.** A comment or formatting edit does not change
what the engine decides and does not diverge a replay, so it must not force a re-genesis — a
byte pin would cry wolf until someone bumps the token without reading it. The digest folds
the kernel's OWN canonical digest of each ``strategies/*.strategy.yaml``
(:func:`tos.dsl.serialization.parse_strategy`, which also refuses an unknown key) and the
runtime's OWN parsed ``strategy_bindings.yaml``
(:func:`tos_runtime.strategy.bindings.load_strategy_bindings`) — the same two readers the
boot path uses, so the pin cannot drift from what actually decides.

Scope: the three tenants ``tools/tos_cp3/runners/cp3_tenant_daily.sh`` runs, each on its own
persistent durable set whose first genesis is the operator's call. The resident
``config/tos_runtime/paper/`` tree is not one of them — it rolls its leaf per instrument
(runbook §7.6), so a decision change there meets a fresh leaf on the next roll.

Hermetic (D1.4): the committed files are only READ; the mutation proofs write under
``tmp_path`` alone.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.dsl.serialization import parse_strategy
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_REGISTRY = _CONFIG_ROOT / "decision_generations.yaml"
_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "cp3_tenant_daily.sh"

#: The CP-3 tenants that run on a PERSISTENT data leaf. Written out rather than derived from
#: the runner at import time: a guard that derives its own expectation from the thing it
#: checks passes no matter what that thing says.
#: :func:`test_the_registry_covers_exactly_the_runners_persistent_leaf_tenants` is what keeps
#: this literal honest — a fourth tenant in the runner fails there, not silently nowhere.
_PERSISTENT_LEAF_TENANTS = (
    "cp3-setup-d-long",
    "cp3-setup-d-short",
    "cp3-setup-d-stock-005930",
)

#: The stock tree's fourth rule and its toggle — PR #1056, the change this guard exists for.
_PROBE_RULE_PREFIX = "R4-M2-PROBE-ENTRY-LONG:"
_PROBE_BINDING = "m2_probe_entry_enabled"
_STOCK = "cp3-setup-d-stock-005930"


# ---------------------------------------------------------------------------------------
# The digest + the pin predicate
# ---------------------------------------------------------------------------------------
def decision_digest(tree: Path) -> str:
    """The digest of ``tree``'s PARSED decision contract (module docstring).

    Raises:
        AssertionError: ``strategies/`` holds a file that is not a strategy file. The
            strategy loader's own stray-file rule refuses the whole directory for such a
            file at boot; skipping it silently here would leave the digest blind to a
            renamed strategy.
    """
    strategy_dir = tree / "strategies"
    digests: dict[str, str] = {}
    for path in sorted(strategy_dir.iterdir()):
        assert path.name.endswith(".strategy.yaml"), (
            f"{path}: not a strategy file — the strategy loader refuses the whole "
            "directory for a stray file, so this digest will not quietly skip it"
        )
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        canonical = parse_strategy(raw).canonical_digest
        # ``canonical_digest`` is typed optional on the artifact, but ``parse_strategy``
        # returns an ISSUED strategy, so it is always derived here. Folding a ``None`` in
        # would make the pin agree with itself while measuring nothing.
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
    payload = json.dumps(
        {"strategies": digests, "bindings": bindings},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pin_problem(tenant: str, tree: Path, entry: dict[str, Any]) -> str | None:
    """``None`` iff ``entry`` still pins ``tree``'s decision contract; else what to do.

    Split out from the test so the #1056 regression proof below can drive the very same
    predicate with the pre-#1056 token — asserting that the check goes red, not merely that
    two digests differ.
    """
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


# ---------------------------------------------------------------------------------------
# The pin
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("tenant", _PERSISTENT_LEAF_TENANTS)
def test_the_committed_decision_generation_still_pins_the_tree(tenant: str) -> None:
    """The guard itself: the tree's parsed decision contract is the pinned one.

    Red on exactly the #1056 shape — a rule or decision binding changed and the token did
    not. The failure text is the handover: bump + re-genesis, with the measured digest to
    paste.
    """
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
    """The tenant list is the runner's, so a fourth tenant cannot land uncovered.

    ``cp3_tenant_daily.sh`` is the single caller that boots these three on a durable set it
    refuses to create itself ("the first genesis is the operator's call"). Reading its own
    ``TREE=`` assignments — rather than a second hand-kept list — is what makes "every
    persistent-leaf tenant is pinned" a checkable claim instead of a comment.
    """
    text = _RUNNER.read_text(encoding="utf-8")
    declared: set[str] = set()
    for value in re.findall(r"^\s*TREE=(\S+)", text, flags=re.MULTILINE):
        # The futures branch spells both directions as one assignment, `cp3-setup-d-$lc`.
        if "$lc" in value:
            declared |= {value.replace("$lc", lc) for lc in ("long", "short")}
        else:
            declared.add(value)
    assert declared, f"{_RUNNER}: no TREE= assignment found — did the runner move?"
    assert declared == set(_PERSISTENT_LEAF_TENANTS), declared
    assert set(_registry()) == set(_PERSISTENT_LEAF_TENANTS), set(_registry())
    for tenant in _PERSISTENT_LEAF_TENANTS:
        assert (_CONFIG_ROOT / tenant).is_dir(), tenant


# ---------------------------------------------------------------------------------------
# What the pin catches, and what it must NOT cry wolf over
# ---------------------------------------------------------------------------------------
def _rewrite_stock_tree(
    destination: Path,
    *,
    drop_probe_rule: bool = False,
    probe_enabled: bool | None = None,
    comment_header: str = "",
) -> Path:
    """A re-serialized copy of the stock tree's decision contract under ``destination``.

    Re-serializing from the parsed YAML (rather than copying bytes) is deliberate: every
    variant below differs from the committed file in formatting — anchors resolved, folded
    scalars re-wrapped, keys re-ordered, comments gone — so a digest that moved for any of
    *those* reasons would show up as the no-op case failing.
    """
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
    return destination


def test_the_1056_change_against_an_unbumped_token_is_caught(tmp_path: Path) -> None:
    """The regression: PR #1056's exact input, red.

    ``pre`` is the 3-rule contract the 2026-11-06 stock leaf was born under (R4 and its
    toggle removed). Its digest is what ``decision_generations.yaml`` would have carried as
    generation 1 — so checking the COMMITTED (4-rule) tree against that token is literally
    #1056: the decision contract moved, the token did not. Without this lane that input
    merges, and the next boot poisons the leaf.
    """
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


def test_toggling_the_probe_binding_moves_the_decision_digest(tmp_path: Path) -> None:
    """``m2_probe_entry_enabled: true -> false`` is a decision change like any other.

    It is the one-line PR the stock tree's own header schedules for after M2, and it changes
    which decisions the engine emits — so it needs its own generation and its own
    re-genesis, exactly like R4's addition did.
    """
    on = _rewrite_stock_tree(tmp_path / "on", probe_enabled=True)
    off = _rewrite_stock_tree(tmp_path / "off", probe_enabled=False)
    assert decision_digest(on) != decision_digest(off)


def test_a_comment_only_edit_does_not_move_the_decision_digest(tmp_path: Path) -> None:
    """The cry-wolf case: formatting and comments are not a decision change.

    The copy is re-serialized (anchors resolved, folded scalars re-wrapped, keys sorted,
    every comment dropped) and then given fresh comments of its own. A byte pin would be red
    here; the parsed pin is not, so a documentation edit never asks anyone to archive a leaf.
    """
    commented = _rewrite_stock_tree(
        tmp_path / "commented",
        probe_enabled=True,
        comment_header="# a comment-only edit — no decision changes here\n#\n",
    )
    assert decision_digest(commented) == decision_digest(_CONFIG_ROOT / _STOCK)
