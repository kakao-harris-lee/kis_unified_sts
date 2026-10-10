"""Unit tests for the CP-3 TENANT render manifests (plan
``docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md`` §4.2, PR-B).

The resident half of that plan lives in ``test_render_paper_config.py``: it pins the resident
manifest's slots, the template shape rules ①–④, and the ``declared``/``external`` modes against
SYNTHETIC trees built by re-manifesting the resident VALUES. This file is the other half — the
two COMMITTED tenant trees (``config/tos_runtime/cp3-setup-d-long`` and ``…-short``), rendered
for real.

**These tests live under the LEGACY ``tests/`` tree on purpose** (design 2026-09-23 §4 item 1):
the script is outside ``tos/`` and is gated by the legacy ``test`` workflow, not by ``tos-gate``.

**Firewall**: this file is outside ``tos/`` and therefore must not import ``tos`` or
``tos_runtime`` (``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R). The two runtime facts this
file needs — "the rendered strategy loads through the production loader" and "the fifteen
critical-input fields still load at ``max_age_ms`` 800" — are measured in a SUBPROCESS, exactly
as ``render_paper_config.py`` itself measures its two.

**No real account number ever appears here**, and nothing is written outside ``tmp_path``: in
particular no ``~/.config/tos/cp3-*`` or ``~/.local/state/tos/cp3-*-data`` directory is created
(plan §2.5 — the designated tenant stores' first genesis belongs to the ③ producer's real data,
and this suite must not be the thing that creates them).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = _REPO_ROOT / "scripts" / "tos"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402

_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"

#: A fake account, never a real one. Ten digits, the length the guard requires.
_FAKE_ACCOUNT = "9999999999"
#: A mini contract code — the tenant product class (kickoff decision 2: ``A056xx``). The full
#: contract ``101S6000`` is the parity dataset's and is deliberately not used here.
_FAKE_INSTRUMENT = "A05610"
_FAKE_REVISION = "0" * 40

#: ``tree -> (direction, strategy file, entry-rule direction token)``.
_TENANT_TREES: dict[str, tuple[str, str]] = {
    "cp3-setup-d-long": ("LONG", "strategies/setup_d_long.strategy.yaml"),
    "cp3-setup-d-short": ("SHORT", "strategies/setup_d_short.strategy.yaml"),
}
_TREE_IDS = tuple(_TENANT_TREES)

#: The direction-bound value sources, as the renderer names them. Mirrored here rather than
#: imported so that a change to the renderer's own set shows up as a failure in this file
#: (which pins the four slots that carry them) instead of silently following it.
_DIRECTION_SOURCES = frozenset(
    {"direction", "direction_action_class", "direction_side"}
)


# ---------------------------------------------------------------------------
# Expected slots — the per-tree pin (plan §2.1 "키 집합 핀", §4.2 first bullet)
# ---------------------------------------------------------------------------


def _expected_slots(tree: str) -> tuple[tuple[str, str, str, str], ...]:
    """The FULL ``(file, key, anchor, replacement)`` tuples this tree's manifest must declare.

    **Why the whole tuple and not the key names.** Once the slot table is data, the renderer's
    old self-check compares the manifest to itself and cannot go red (plan §2.1, review M1). A
    key-name pin restores only part of the force: a manifest that keeps the key
    ``construction.yaml::account`` while re-aiming its anchor AND template at a different leaf
    of the same file passes template rules ①–④ and a key-name pin alike.
    :func:`test_red_proof_a_re_aimed_tenant_slot_is_caught_only_by_this_pin` measures exactly
    that.

    Built from the two per-tree facts (the direction token and the strategy file name) rather
    than written out twice, because the two literals would then differ in 20 places where only
    four are meaningful — and a reader comparing them by eye is the failure mode the resident
    README's own count-line tests exist to prevent. The SHAPE of every tuple is still a
    literal; only the two tokens are substituted, and
    :func:`test_the_two_trees_expected_slots_differ_in_exactly_the_direction_and_strategy_rows`
    pins which rows those are.
    """
    direction, strategy = _TENANT_TREES[tree]
    action_class = {"LONG": "NEW_LONG", "SHORT": "NEW_SHORT"}[direction]
    side = {"LONG": "BUY", "SHORT": "SELL"}[direction]
    return (
        (
            "venue_constraint_policy.yaml",
            "venue_constraint_policy.yaml::scope.accounts",
            '  accounts: ["TBD"]',
            '  accounts: ["{value}"]',
        ),
        (
            "venue_constraint_policy.yaml",
            "venue_constraint_policy.yaml::scope.instruments",
            '  instruments: ["TBD"]',
            '  instruments: ["{value}"]',
        ),
        (
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::scope.accounts",
            '  accounts: ["TBD"]',
            '  accounts: ["{value}"]',
        ),
        (
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::scope.instruments",
            '  instruments: ["TBD"]',
            '  instruments: ["{value}"]',
        ),
        (
            "order_construction_policy.yaml",
            "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
            f'        value: "{direction}"',
            '        value: "{value}"',
        ),
        (
            "aggregate_risk_policy.yaml",
            "aggregate_risk_policy.yaml::account_scope",
            'account_scope: ["TBD"]',
            'account_scope: ["{value}"]',
        ),
        (
            "aggregate_risk_policy.yaml",
            "aggregate_risk_policy.yaml::instrument_scope",
            'instrument_scope: ["TBD"]',
            'instrument_scope: ["{value}"]',
        ),
        (
            "action_flow_policy.yaml",
            "action_flow_policy.yaml::account_scope",
            'account_scope: ["TBD"]',
            'account_scope: ["{value}"]',
        ),
        (
            "construction.yaml",
            "construction.yaml::account",
            'account: "TBD"',
            'account: "{value}"',
        ),
        (
            "construction.yaml",
            "construction.yaml::instrument",
            'instrument: "TBD"',
            'instrument: "{value}"',
        ),
        (
            "construction.yaml",
            "construction.yaml::action_class",
            f'action_class: "{action_class}"',
            'action_class: "{value}"',
        ),
        (
            "construction.yaml",
            "construction.yaml::outbound_side",
            f'outbound_side: "{side}"',
            'outbound_side: "{value}"',
        ),
        (
            strategy,
            f"{strategy}::policy.rules[0].decision.target.account",
            '          account: &account "TBD"',
            '          account: &account "{value}"',
        ),
        (
            strategy,
            f"{strategy}::policy.rules[0].decision.target.instrument",
            '          instrument: &instrument "TBD"',
            '          instrument: &instrument "{value}"',
        ),
        (
            strategy,
            f"{strategy}::policy.rules[0].decision.target.direction",
            f"          direction: {direction}",
            "          direction: {value}",
        ),
        (
            "marketfeed.yaml",
            "marketfeed.yaml::instruments",
            'instruments: ["TBD"]',
            'instruments: ["{value}"]',
        ),
        (
            "marketfeed.yaml",
            "marketfeed.yaml::account",
            'account: "TBD"',
            'account: "{value}"',
        ),
        (
            "marketfeed.yaml",
            "marketfeed.yaml::direction",
            f'direction: "{direction}"',
            'direction: "{value}"',
        ),
        (
            "marketfeed.yaml",
            "marketfeed.yaml::journal_path",
            'journal_path: "TBD"',
            'journal_path: "{value}"',
        ),
        (
            "finality.yaml",
            "finality.yaml::source_revision",
            "source_revision: null",
            'source_revision: "{value}"',
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tree(tree: str) -> Path:
    return _CONFIG_ROOT / tree


def _slot_tuples(
    manifest: rpc.RenderManifest,
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (slot.file, slot.rule_key, slot.anchor, slot.replacement)
        for slot in manifest.slots
    )


def _manifest_dict(tree: str) -> dict[str, Any]:
    raw = yaml.safe_load(
        (_tree(tree) / rpc.RENDER_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert isinstance(raw, dict)
    return raw


def _copy_tree(tree: str, destination: Path) -> Path:
    """A writable copy of a committed tenant tree, for the mutation red proofs."""
    shutil.copytree(_tree(tree), destination)
    return destination


def _write_manifest(tree_dir: Path, manifest: dict[str, Any]) -> None:
    (tree_dir / rpc.RENDER_MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _slot_index(manifest: dict[str, Any], file_name: str, key: str) -> int:
    for index, slot in enumerate(manifest["slots"]):
        if slot["file"] == file_name and slot["key"] == key:
            return index
    raise AssertionError(f"no slot {file_name}::{key} in the manifest")


def _journal(tmp_path: Path) -> Path:
    """A stand-in for the ③ producer's output.

    The renderer checks only that the path EXISTS — the content contract belongs to the
    producer (plan §2.4) — so this file is deliberately a single inert line rather than an
    invented observation.
    """
    path = tmp_path / "upstream_journal.jsonl"
    path.write_text(
        json.dumps(
            {
                "raw_event_id": "not-an-observation",
                "instrument": _FAKE_INSTRUMENT,
                "as_of_ms": 0,
                "fields": {},
                "source_id": "test-placeholder-for-the-external-producer",
                "received_ms": 0,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _render(
    source: Path, out: Path, *, direction: str, journal_path: Path
) -> rpc.RenderResult:
    return rpc.render(
        source,
        out,
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction=direction,
        journal_path=journal_path,
    )


def _designated_paths() -> tuple[Path, ...]:
    """The tenant stores each tree's README §8 DESIGNATES but does not create.

    Their first genesis belongs to the ③ producer's real data (plan §2.5), so this suite must
    not be what brings them into existence.
    """
    return tuple(
        Path.home() / parent / f"{tree}{suffix}"
        for tree in _TREE_IDS
        for parent, suffix in (
            (".config/tos", "-config"),
            (".local/state/tos", "-data"),
        )
    )


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Both tenant trees, rendered ONCE into ``tmp_path`` with the fake account.

    Module-scoped because each render runs two runtime subprocesses
    (``print-policy-digests`` and the activation read-back) and every assertion below is a
    READ of the result.

    The ``designated_before`` snapshot is taken here, before the first render, so
    :func:`test_this_suite_creates_no_designated_tenant_directory` can assert what THIS SESSION
    changed rather than that the paths are absent. An absence assertion would turn permanently
    red the day an operator legitimately creates one, and would accuse this suite of it
    (the 2026-10-02 #846 shape).
    """
    base = tmp_path_factory.mktemp("tenant-render")
    before = {path: path.exists() for path in _designated_paths()}
    journal = _journal(base)
    out_dirs: dict[str, Any] = {"designated_before": before}
    for tree, (direction, _strategy) in _TENANT_TREES.items():
        out = base / f"out-{tree}"
        _render(_tree(tree), out, direction=direction, journal_path=journal)
        out_dirs[tree] = out
    return out_dirs


# ---------------------------------------------------------------------------
# The manifests themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_tenant_manifest_declares_the_tenant_modes(tree: str) -> None:
    """``declared`` + ``external`` — the two modes that make this a TENANT tree (plan §2.3,
    §2.4). The resident tree declares the other two, pinned in ``test_render_paper_config.py``.
    """
    direction, _strategy = _TENANT_TREES[tree]
    manifest = rpc.load_manifest(_tree(tree))
    assert manifest.tree_id == tree
    assert manifest.direction_mode == "declared"
    assert manifest.direction_value == direction
    assert manifest.journal_mode == "external"


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_tenant_manifest_slots_are_pinned_as_full_tuples(tree: str) -> None:
    """Adding, removing, reordering or re-aiming a tenant slot turns this RED and requires
    :func:`_expected_slots` to be edited."""
    assert _slot_tuples(rpc.load_manifest(_tree(tree))) == _expected_slots(tree)


def test_the_two_trees_expected_slots_differ_in_exactly_the_direction_and_strategy_rows() -> (
    None
):
    """:func:`_expected_slots` substitutes two tokens into one literal shape; this says which
    rows those tokens reach, so "the two trees' slot tables are the same table" is checkable
    rather than assumed. Four direction rows + three strategy-file rows = seven."""
    long_slots = _expected_slots("cp3-setup-d-long")
    short_slots = _expected_slots("cp3-setup-d-short")
    assert len(long_slots) == len(short_slots) == 20
    differing = {
        long_row[1].split("::", 1)[1]
        for long_row, short_row in zip(long_slots, short_slots, strict=True)
        if long_row != short_row
    }
    assert differing == {
        "_runtime.construction.axes.DIRECTION",
        "action_class",
        "outbound_side",
        "direction",
        "policy.rules[0].decision.target.account",
        "policy.rules[0].decision.target.instrument",
        "policy.rules[0].decision.target.direction",
    }


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_red_proof_a_re_aimed_tenant_slot_is_caught_only_by_this_pin(
    tree: str, tmp_path: Path
) -> None:
    """**The red proof for the pin above, built so nothing else can mask it** (#838).

    The mutation keeps the slot's KEY (``construction.yaml::account``) and moves both its
    anchor and its template onto a different leaf of the same file — the plan's own red proof
    (§2.1: "앵커만 바꾸면 템플릿의 키 접두가 앵커와 달라 규칙 ③ 이 먼저 거부하므로 핀의
    기여를 보이지 못한다"). Three things are measured, in order, and only the third fires:

    1. the manifest LOADS — template rules ①–④ accept it;
    2. the set of rule KEYS is unchanged — a key-name pin would also stay green;
    3. the full-tuple pin differs.
    """
    manifest = _manifest_dict(tree)
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = 'instrument_class: "krx-index-futures"'
    manifest["slots"][index]["replacement"] = 'instrument_class: "{value}"'
    mutated = _copy_tree(tree, tmp_path / tree)
    _write_manifest(mutated, manifest)

    loaded = rpc.load_manifest(mutated)  # 1 — rules ①–④ do not refuse this

    assert {slot.rule_key for slot in loaded.slots} == {
        key for _file, key, _anchor, _replacement in _expected_slots(tree)
    }  # 2 — a key-name pin stays green
    assert _slot_tuples(loaded) != _expected_slots(tree)  # 3 — only this pin is red


# ---------------------------------------------------------------------------
# Direction consistency (plan §2.3 — the verify-only slots)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_every_direction_slot_is_verify_only_and_matches_the_committed_tree(
    tree: str,
) -> None:
    """For each direction-bound slot: the line the DECLARED direction makes is byte-identical
    to the committed anchor, and that anchor occurs EXACTLY ONCE in the committed file.

    That pair is the whole direction check for a ``declared`` tree. ``_apply_rules`` then
    rewrites each of these lines with itself, so a tree whose direction token had drifted in
    any one of the four places refuses with "matched 0 times" instead of rendering a mixed
    deployment — the activation digests do not bind DIRECTION and would not notice
    (``render_paper_config.py::_policy_digest_lines`` docstring, review-797 LOW-6).
    """
    direction, _strategy = _TENANT_TREES[tree]
    manifest = rpc.load_manifest(_tree(tree))
    direction_slots = [
        slot for slot in manifest.slots if slot.value in _DIRECTION_SOURCES
    ]
    # FIVE places, not four: the runbook §7.10 3 checklist names three
    # (``construction.yaml::action_class`` / ``outbound_side``, the OCP ``DIRECTION`` axis, the
    # strategy file's entry ``direction``) and this tree adds ``marketfeed.yaml::direction``,
    # which rides into every capsule's ``SafetyCriticalFacts`` (kickoff §5 3, "방향이 사는
    # 자리 다섯" — its fifth, the entry comparison's side and binding, is not a render slot).
    assert len(direction_slots) == 5
    assert {slot.value for slot in direction_slots} == _DIRECTION_SOURCES
    assert {slot.rule_key for slot in direction_slots} == {
        "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
        "construction.yaml::action_class",
        "construction.yaml::outbound_side",
        "marketfeed.yaml::direction",
        f"{_TENANT_TREES[tree][1]}::policy.rules[0].decision.target.direction",
    }

    tokens = rpc._DIRECTION_TOKENS[direction]
    values = {
        "direction": direction,
        "direction_action_class": tokens["action_class"],
        "direction_side": tokens["side"],
    }
    for slot in direction_slots:
        line = slot.replacement.replace("{value}", values[slot.value])
        assert line == slot.anchor, (
            f"{tree}: slot {slot.rule_key} is not verify-only — the declared direction "
            f"{direction!r} makes {line!r} but the committed anchor is {slot.anchor!r}"
        )
        text = (_tree(tree) / slot.file).read_text(encoding="utf-8")
        occurrences = text.split("\n").count(slot.anchor)
        assert occurrences == 1, (
            f"{tree}: anchor {slot.anchor!r} occurs {occurrences} times in {slot.file} — "
            f"exactly one is required"
        )


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_red_proof_the_other_trees_manifest_is_refused(
    tree: str, tmp_path: Path
) -> None:
    """**Red proof 1 of plan §4.2's direction bullet**: the SHORT tree under a LONG manifest
    (and the mirror).

    The manifest is the OTHER tree's, with only the one tree-specific file name adapted — the
    strategy file, which this tree does carry under a different name. Without that adaptation
    ``load_manifest`` would refuse at "slot target missing from the tree", which is a weaker
    refusal that says nothing about direction and would MASK the clause under test.

    Measured in order, so the firing clause is named:

    1. the manifest LOADS;
    2. ``_slot_rules`` SUCCEEDS — the foreign manifest is internally consistent (its anchors
       and its declared direction agree with each other), so the self-contradiction clause is
       not what catches this;
    3. the render refuses at ``_apply_rules`` with "matched 0 times" on the FIRST direction
       slot in manifest order.

    ⚠ The plan names this refusal as "``action_class: \"NEW_LONG\"`` 0회 매칭". That statement
    is true — step 4 measures it directly — but it is not the slot that fires, because the OCP
    ``DIRECTION`` axis sits earlier in the slot list and refuses first. Asserting the plan's
    wording instead of the measured one would be a test that passes for the wrong reason.
    """
    other = next(name for name in _TREE_IDS if name != tree)
    other_direction, other_strategy = _TENANT_TREES[other]
    _own_direction, own_strategy = _TENANT_TREES[tree]

    manifest = _manifest_dict(other)
    for slot in manifest["slots"]:
        if slot["file"] == other_strategy:
            slot["file"] = own_strategy
    mutated = _copy_tree(tree, tmp_path / tree)
    _write_manifest(mutated, manifest)

    loaded = rpc.load_manifest(mutated)  # 1
    assert loaded.direction_value == other_direction

    rpc._slot_rules(  # 2 — internally consistent; this is not the clause that fires
        loaded,
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction=other_direction,
        journal_path=_journal(tmp_path),
    )

    first_direction_slot = next(
        slot for slot in loaded.slots if slot.value in _DIRECTION_SOURCES
    )
    with pytest.raises(rpc.RenderError) as excinfo:  # 3
        _render(
            mutated,
            tmp_path / "out",
            direction=other_direction,
            journal_path=_journal(tmp_path),
        )
    message = str(excinfo.value)
    assert "matched 0 times" in message, message
    assert first_direction_slot.rule_key in message, message

    # 4 — the plan's own wording, measured directly rather than asserted through the message.
    action_class_slot = next(
        slot for slot in loaded.slots if slot.value == "direction_action_class"
    )
    construction = (mutated / "construction.yaml").read_text(encoding="utf-8")
    assert construction.split("\n").count(action_class_slot.anchor) == 0


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_red_proof_a_tree_whose_construction_carries_the_other_direction_is_refused(
    tree: str, tmp_path: Path
) -> None:
    """**Red proof 2**: this tree's own manifest, but ``construction.yaml`` still carries the
    OTHER direction's tokens (the plan's "SHORT 트리 + ``NEW_LONG`` construction").

    This is the half the manifest-to-manifest comparison cannot see: both manifests agree,
    only the VALUES drifted. Without the verify-only slots the render would succeed, the five
    digests would be unchanged, activation would pass, and nothing would refuse.
    """
    direction, _strategy = _TENANT_TREES[tree]
    other = next(name for name in _TREE_IDS if name != tree)
    other_direction, _ = _TENANT_TREES[other]
    tokens = rpc._DIRECTION_TOKENS[direction]
    other_tokens = rpc._DIRECTION_TOKENS[other_direction]

    mutated = _copy_tree(tree, tmp_path / tree)
    construction = mutated / "construction.yaml"
    text = construction.read_text(encoding="utf-8")
    text = text.replace(
        f'action_class: "{tokens["action_class"]}"',
        f'action_class: "{other_tokens["action_class"]}"',
    ).replace(
        f'outbound_side: "{tokens["side"]}"',
        f'outbound_side: "{other_tokens["side"]}"',
    )
    construction.write_text(text, encoding="utf-8")

    with pytest.raises(rpc.RenderError) as excinfo:
        _render(
            mutated,
            tmp_path / "out",
            direction=direction,
            journal_path=_journal(tmp_path),
        )
    message = str(excinfo.value)
    assert "matched 0 times" in message, message
    assert "construction.yaml::action_class" in message, message


# ---------------------------------------------------------------------------
# The YAML anchor / alias form (plan §2.2)
# ---------------------------------------------------------------------------


def _yaml_body(text: str) -> str:
    """``text`` with every whole-line comment dropped.

    These files' HEADERS talk ABOUT the tokens the assertions below look for (``"TBD"``,
    ``&account``, ``*account``) — a substring test over the whole file therefore matches the
    prose and says nothing about the document. Measured: the first cut of
    :func:`test_the_rendered_tenant_strategy_loads_through_the_production_loader` failed on its
    own header sentence.
    """
    return "\n".join(
        line for line in text.split("\n") if not line.lstrip().startswith("#")
    )


def _leaf_values(node: Any) -> list[Any]:
    """Every scalar leaf of a parsed document, depth-first."""
    if isinstance(node, dict):
        return [leaf for value in node.values() for leaf in _leaf_values(value)]
    if isinstance(node, list):
        return [leaf for value in node for leaf in _leaf_values(value)]
    return [node]


def _strategy_targets(path: Path) -> list[dict[str, Any]]:
    """Every rule target in a strategy file, PARSED — so an alias is already resolved."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    targets = []
    for rule in document["policy"]["rules"]:
        target = rule["decision"].get("target")
        if target:
            targets.append(target)
    return targets


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_committed_strategy_carries_one_anchor_line_and_two_aliases(
    tree: str,
) -> None:
    """The textual half of plan §2.2: the renderer's "exactly one anchor match" invariant holds
    because the coordinate line it anchors on occurs once, while the leaf it fills occurs three
    times after parsing."""
    _direction, strategy = _TENANT_TREES[tree]
    lines = (_tree(tree) / strategy).read_text(encoding="utf-8").split("\n")
    for name in ("account", "instrument"):
        assert lines.count(f'          {name}: &{name} "TBD"') == 1
        assert lines.count(f"          {name}: *{name}") == 2
    targets = _strategy_targets(_tree(tree) / strategy)
    assert len(targets) == 3
    assert [t["account"] for t in targets] == ["TBD"] * 3
    assert [t["instrument"] for t in targets] == ["TBD"] * 3


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_every_rendered_rule_target_shares_one_account_and_one_instrument(
    tree: str, rendered: dict[str, Any]
) -> None:
    """Plan §4.2 / review L4: the post-parse equality the alias form is FOR.

    The "a missing alias leaves ``TBD``" refusal only catches a revert to the named-TBD token;
    a DIFFERENT literal in R2 renders cleanly and loads cleanly. This says all three targets
    carry the same two coordinates, whatever they are.
    """
    _direction, strategy = _TENANT_TREES[tree]
    targets = _strategy_targets(rendered[tree] / strategy)
    assert len(targets) == 3
    assert {t["account"] for t in targets} == {_FAKE_ACCOUNT}
    assert {t["instrument"] for t in targets} == {_FAKE_INSTRUMENT}


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_red_proof_a_literal_account_in_r2_survives_render_and_loader_and_only_the_equality_catches_it(
    tree: str, tmp_path: Path
) -> None:
    """**The red proof for the equality above** (plan §4.2: "레드 증명: R2 에 ``A05611``
    리터럴"), built so nothing else can mask it.

    Measured in order:

    1. the render SUCCEEDS — the anchor still matches exactly once, so ``_apply_rules`` is not
       what catches this;
    2. no ``TBD`` survives — so the loader's named-TBD refusal is not what catches it either;
    3. the three targets no longer share one account.
    """
    _direction, strategy = _TENANT_TREES[tree]
    mutated = _copy_tree(tree, tmp_path / tree)
    path = mutated / strategy
    lines = path.read_text(encoding="utf-8").split("\n")
    second = [
        i for i, line in enumerate(lines) if line == "          account: *account"
    ][0]
    lines[second] = '          account: "A05611"'
    path.write_text("\n".join(lines), encoding="utf-8")

    out = tmp_path / "out"
    _render(
        mutated, out, direction=_TENANT_TREES[tree][0], journal_path=_journal(tmp_path)
    )  # 1

    document = yaml.safe_load((out / strategy).read_text(encoding="utf-8"))
    assert "TBD" not in _leaf_values(document)  # 2

    targets = _strategy_targets(out / strategy)
    assert {t["account"] for t in targets} == {_FAKE_ACCOUNT, "A05611"}  # 3


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_red_proof_reverting_an_alias_to_tbd_renders_but_the_loader_refuses(
    tree: str, tmp_path: Path
) -> None:
    """**Plan §2.2's named failing input**: R3's ``account: *account`` reverted to ``"TBD"``.

    The render SUCCEEDS (the anchor is R1's and still matches once) — and then the production
    strategy loader refuses, naming the leaf. That is the point of the alias design: a missed
    alias needs no new guard, because ``first_named_tbd_leaf`` already walks the PARSED
    document.
    """
    _direction, strategy = _TENANT_TREES[tree]
    mutated = _copy_tree(tree, tmp_path / tree)
    path = mutated / strategy
    lines = path.read_text(encoding="utf-8").split("\n")
    last = [i for i, line in enumerate(lines) if line == "          account: *account"][
        -1
    ]
    lines[last] = '          account: "TBD"'
    path.write_text("\n".join(lines), encoding="utf-8")

    out = tmp_path / "out"
    _render(
        mutated, out, direction=_TENANT_TREES[tree][0], journal_path=_journal(tmp_path)
    )
    assert (out / strategy).is_file()

    completed = _run_runtime(_LOAD_STRATEGY, out)
    assert completed.returncode != 0, completed.stdout
    message = completed.stderr or completed.stdout
    assert "policy.rules[2]" in message and "account" in message, message
    assert "TBD" in message, message


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_alias_form_parses_exactly_like_three_literals(
    tree: str, rendered: dict[str, Any]
) -> None:
    """Plan §2.2's second claim: the aliases change the NOTATION, never the meaning.

    The rendered file (anchor + two aliases) is compared against a version of itself with every
    alias written out as the literal value. Byte-different, parse-identical — which is also why
    the B1b ↔ deployed drift guard
    (``tos/runtime/cp3/tests/test_cp3_short_strategy_content.py``) accepts the alias form
    unchanged: it compares ``yaml.safe_load`` output, not text.
    """
    _direction, strategy = _TENANT_TREES[tree]
    aliased_text = (rendered[tree] / strategy).read_text(encoding="utf-8")
    literal_text = (
        aliased_text.replace(
            f'          account: &account "{_FAKE_ACCOUNT}"',
            f'          account: "{_FAKE_ACCOUNT}"',
        )
        .replace(
            f'          instrument: &instrument "{_FAKE_INSTRUMENT}"',
            f'          instrument: "{_FAKE_INSTRUMENT}"',
        )
        .replace("          account: *account", f'          account: "{_FAKE_ACCOUNT}"')
        .replace(
            "          instrument: *instrument",
            f'          instrument: "{_FAKE_INSTRUMENT}"',
        )
    )
    assert literal_text != aliased_text
    aliased_body, literal_body = _yaml_body(aliased_text), _yaml_body(literal_text)
    for token in ("&account", "*account", "&instrument", "*instrument"):
        assert token in aliased_body, token
        assert token not in literal_body, token
    assert yaml.safe_load(literal_text) == yaml.safe_load(aliased_text)


# ---------------------------------------------------------------------------
# The real render (plan §4.2 — activation, digests, --check, no journal)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_tenant_render_activates_and_prints_five_policy_kinds(
    tree: str, rendered: dict[str, Any]
) -> None:
    """``print-policy-digests`` prints all five kinds — the four ``compose`` calls
    ``require_member_activated`` for, plus ``CRITICAL_INPUT_POLICY``, which this deployment
    adopted — and the activation read-back re-derives every one of them in a FRESH process.

    The read-back is inside :func:`render_paper_config.render`, so reaching this fixture at all
    means it passed; the assertions below name what it covered.
    """
    manifest_path = rendered[tree] / rpc.RENDERED_NAME
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in payload["policy_digests"]}
    assert kinds == {
        "VENUE_CONSTRAINT_POLICY",
        "ORDER_CONSTRUCTION_POLICY",
        "AGGREGATE_RISK_POLICY",
        "ACTION_FLOW_POLICY",
        "CRITICAL_INPUT_POLICY",
    }
    assert payload["activation_check"]
    assert payload["tree_id"] == tree
    assert payload["direction"] == _TENANT_TREES[tree][0]
    assert _FAKE_ACCOUNT not in manifest_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_tenant_render_writes_no_bootproof_journal(
    tree: str, rendered: dict[str, Any]
) -> None:
    """``journal.mode: external`` — the renderer invents no observations (plan §2.4), and
    ``marketfeed.yaml`` points at the path it was GIVEN."""
    assert not (rendered[tree] / rpc.JOURNAL_NAME).exists()
    marketfeed = yaml.safe_load(
        (rendered[tree] / "marketfeed.yaml").read_text(encoding="utf-8")
    )
    journal_path = Path(marketfeed["journal_path"])
    assert journal_path.name == "upstream_journal.jsonl"
    assert journal_path.is_file()
    assert rendered[tree] not in journal_path.parents


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_check_is_clean_on_a_tenant_render(tree: str, rendered: dict[str, Any]) -> None:
    """``--check`` against a correct tenant render reports nothing — in particular it does not
    report the absent ``bootproof_journal.jsonl`` as a missing artifact (plan §7), and it does
    not report the byte-copied ``RENDER.yaml`` as an unexpected file."""
    assert rpc.check(_tree(tree), rendered[tree]) == []
    assert (rendered[tree] / rpc.RENDER_MANIFEST_NAME).read_bytes() == (
        _tree(tree) / rpc.RENDER_MANIFEST_NAME
    ).read_bytes()


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_check_catches_an_edit_outside_the_tenant_slots(
    tree: str, rendered: dict[str, Any], tmp_path: Path
) -> None:
    """The mirror half: a hand edit anywhere that is not a registered slot is named.

    Applied to a COPY of the rendered directory so the module-scoped fixture stays pristine for
    the other assertions.
    """
    copy = tmp_path / "edited"
    shutil.copytree(rendered[tree], copy)
    risk = copy / "risk.yaml"
    lines = risk.read_text(encoding="utf-8").split("\n")
    index = next(
        i
        for i, line in enumerate(lines)
        if line and not line.lstrip().startswith("#") and ":" in line
    )
    lines[index] = lines[index] + "  # hand edit"
    risk.write_text("\n".join(lines), encoding="utf-8")

    problems = rpc.check(_tree(tree), copy)
    assert any(f"risk.yaml:{index + 1}" in problem for problem in problems), problems


# ---------------------------------------------------------------------------
# The rendered tree, through the PRODUCTION loaders (subprocess — firewall)
# ---------------------------------------------------------------------------

_LOAD_STRATEGY = """
import json, sys
from pathlib import Path
from tos.dsl.serialization import parse_strategy
from tos.engine.admission import strategy_admissible
from tos_runtime.strategy.loader import load_strategies

config_dir = Path(sys.argv[1])
loaded = load_strategies(
    config_dir / "strategies", parse=parse_strategy, admit=strategy_admissible
)
print(json.dumps([str(item.path.name) for item in loaded.strategies]))
"""

_LOAD_CRITICAL_INPUT_POLICY = """
import json, sys
from pathlib import Path
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.marketfeed.policy import load_critical_input_policy

config_dir = Path(sys.argv[1])
loaded = load_critical_input_policy(
    config_dir / "critical_input_policy.yaml",
    scheme=get_scheme(EV_L1_PROVISIONAL_VERSION),
)
print(
    json.dumps(
        {
            "policy_id": loaded.policy_id,
            "max_age_ms": sorted({f.max_age_ms for f in loaded.fields}),
            "field_keys": [f.field_key for f in loaded.fields],
        }
    )
)
"""


def _run_runtime(script: str, config_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run ``script`` against ``config_dir`` in a SUBPROCESS.

    This file may not import ``tos``/``tos_runtime`` (module docstring, firewall rule (e)), so
    every runtime fact is measured the way ``render_paper_config.py`` measures its own two.
    """
    return subprocess.run(
        [sys.executable, "-B", "-c", script, str(config_dir)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=rpc._subprocess_env(),
    )


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_rendered_tenant_strategy_loads_through_the_production_loader(
    tree: str, rendered: dict[str, Any]
) -> None:
    """The committed tree does NOT load (every coordinate is the named-TBD token — that is the
    operator-fill gate); the RENDERED tree does.

    Both halves in one test, because the second alone would not say that the gate is still
    there, and the first alone would not say that the render opens it.
    """
    _direction, strategy = _TENANT_TREES[tree]

    committed = _run_runtime(_LOAD_STRATEGY, _tree(tree))
    assert committed.returncode != 0, committed.stdout
    assert "TBD" in (committed.stderr or committed.stdout)

    loaded = _run_runtime(_LOAD_STRATEGY, rendered[tree])
    assert loaded.returncode == 0, loaded.stderr
    assert json.loads(loaded.stdout) == [Path(strategy).name]
    document = yaml.safe_load((rendered[tree] / strategy).read_text(encoding="utf-8"))
    assert "TBD" not in _leaf_values(document)


@pytest.mark.parametrize("tree", _TREE_IDS)
def test_the_rendered_tenant_critical_input_policy_still_declares_fifteen_fields_at_800(
    tree: str, rendered: dict[str, Any]
) -> None:
    """Plan §2.4's binding requirement, re-measured against the RENDERED tree.

    ``max_age_ms`` = 800 is the kernel's conservative freshness budget minus the declared
    Σ delay, and the render does not touch it — this says so by loading the rendered copy
    rather than the committed one.
    """
    completed = _run_runtime(_LOAD_CRITICAL_INPUT_POLICY, rendered[tree])
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["max_age_ms"] == [800]
    assert len(payload["field_keys"]) == 15
    assert len(set(payload["field_keys"])) == 15
    assert tree in payload["policy_id"]


# ---------------------------------------------------------------------------
# Nothing designated was created (plan §2.5)
# ---------------------------------------------------------------------------


def test_this_suite_creates_no_designated_tenant_directory(
    rendered: dict[str, Any],
) -> None:
    """Plan §2.5 / README §8: the designated tenant config and data directories are created by
    the FIRST REAL boot with the ③ producer's data, never by a test.

    Asserted as a BEFORE/AFTER comparison of their existence, not as absence: whether this host
    already has one is not this suite's business, and an absence assertion would go permanently
    red — and accuse this suite — the day an operator legitimately creates one.
    """
    before: dict[Path, bool] = rendered["designated_before"]
    after = {path: path.exists() for path in _designated_paths()}
    created = sorted(str(path) for path in after if after[path] and not before[path])
    assert not created, (
        f"this suite brought {created} into existence — the designated tenant store's first "
        f"genesis belongs to the ③ producer's real data (plan §2.5), not to a render"
    )
    for tree in _TREE_IDS:
        out = rendered[tree]
        assert not any(
            path == out or path in out.parents for path in _designated_paths()
        ), out
