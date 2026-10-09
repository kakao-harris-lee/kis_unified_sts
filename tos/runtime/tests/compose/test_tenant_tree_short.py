"""The CP-3 **SHORT** tenant tree (``config/tos_runtime/cp3-setup-d-short/``) and its symmetry
with the LONG one.

CP-3 kickoff ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §4 decision 4 settled that
LONG and SHORT are **two separate deployments**, each with its own config tree and data dir --
not one tree plus a render flag, the way the RESIDENT boot-proof deployment does it. Decision 3
is the other half: direction never shares a data dir (runbook ``docs/runbooks/tos-paper-boot.md``
§7.10 3, and §5 ⑤ -- an activation record does not bind direction, so a mixed corpus cannot be
split apart afterwards).

What this file is for: **nothing in the runtime cross-checks the direction slots.** A
``marketfeed.yaml::direction`` that disagrees with the OCP's ``DIRECTION`` axis boots silently
with the wrong token folded into every capsule's ``SafetyCriticalFacts``, and the digests cannot
tell the two trees apart -- measured 2026-10-09 and worse than the OCP header's own KNOWN
LIMITATION claims: the OCP ``canonical_digest`` is unchanged by the DIRECTION axis AND by the
``policy_id``, so only the activation key's ``member_id`` distinguishes the two OCPs. These
assertions are the only mechanical thing standing between a half-flipped tree and a boot.

Hermetic (D1.4): the real files are only READ; every write lands under ``tmp_path``.
"""

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

#: The legacy strategy YAML the entry threshold is derived FROM -- read, never restated. A
#: test-local ``1.8`` would stay green after someone edited that file, and the shipped
#: derivation would then be false (the 2026-10-08 review lesson on the B1b copy of this test).
_LEGACY_STRATEGY_YAML = (
    _REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

_LONG_STRATEGY_REL = "strategies/setup_d_long.strategy.yaml"
_SHORT_STRATEGY_REL = "strategies/setup_d_short.strategy.yaml"

#: SHORT-specific policy ids. The rename criterion is the one the LONG tree's README states --
#: **did the content diverge** -- not "is this a different tree". The venue and critical-input
#: policies diverge in content from the resident/LONG ones already; the OCP joins them HERE,
#: because this tree's DIRECTION axis differs. The aggregate-risk and action-flow policies are
#: byte-identical across all three trees and deliberately keep their shared ids: "same id, same
#: digest" is a TRUE statement that they ARE the same document.
_SHORT_VENUE_POLICY_ID = "vcp-paper-cp3-setup-d-short-krx-index-futures"
_SHORT_CIP_POLICY_ID = "tos-paper-cp3-setup-d-short-critical-input-g1"
_SHORT_CIP_ISSUER_ID = "tos-paper-cp3-setup-d-short-critical-input-issuer-g1"
_SHORT_OCP_POLICY_ID = "ocp-paper-cp3-setup-d-short-krx-index-futures"

#: ``README.md`` §3's table, as the machine-readable literal that table says it is. Exhaustive
#: over the tree: :func:`test_short_tree_classification_is_exhaustive` asserts the union is
#: exactly the file set, so adding a file without classifying it goes red.
#:
#: BYTE-IDENTICAL to the LONG tree. Every file with no direction content and no identity of its
#: own -- including ``release.yaml`` (the ``expected_code_digest`` pin), which is why a
#: runtime-code PR has to re-derive it in BOTH tenant trees, not just the resident one.
_IDENTICAL_TO_LONG = frozenset(
    {
        "action_flow_policy.yaml",
        "aggregate_risk_policy.yaml",
        "authority.yaml",
        "broker_scopes.yaml",
        "calendar.yaml",
        "coordinator_preconditions.yaml",
        "currentness.yaml",
        "currentness_dimensions.yaml",
        "egress_coordinates.yaml",
        "engine.yaml",
        "engine_driver.yaml",
        "evidence_cold_backup.yaml",
        "finality.yaml",
        "monitor_coverage.yaml",
        "release.yaml",
        "risk.yaml",
        "risk_attestations.yaml",
        "safety_activation.yaml",
        "safety_deviations.yaml",
        "safety_envelope.yaml",
        "safety_incidents.yaml",
        "safety_profile.yaml",
        "time.yaml",
    }
)

#: DIFFERS from the LONG tree, with the parsed-YAML key paths that are ALLOWED to differ. A
#: path not listed here differing is a failure -- that is what makes this a guard rather than a
#: description. Comments are invisible to this comparison by construction (it reads parsed
#: YAML), which is deliberate: re-wording a header must not need a test edit, while moving a
#: value must.
#:
#: ⚠ **Two of these paths fold a whole subtree, and a declared prefix exempts everything under
#: it** (review M2, measured 2026-10-09): ``_runtime.construction.axes`` is a LIST, which
#: :func:`_leaves` treats as one leaf, so declaring it also exempted the TIF axis beside
#: DIRECTION -- a SHORT-tree ``DAY`` -> ``IOC`` edit was green. ``strategies`` folds a dict for
#: the same reason. Neither is narrowed by this table (it cannot express "this list, minus one
#: entry"); each has its own dedicated test instead:
#: :func:`test_the_axes_list_differs_only_in_its_DIRECTION_entry` and
#: :func:`test_the_bindings_subtree_differs_only_in_the_direction_bearing_names`. **A new folded
#: prefix added here needs the same treatment** -- the entry below records which paths are
#: folded so that obligation is visible at the declaration site, not only in a commit message.
_DIFFERS_FROM_LONG: dict[str, frozenset[str]] = {
    "construction.yaml": frozenset({"action_class", "outbound_side"}),
    "marketfeed.yaml": frozenset({"direction"}),
    "order_construction_policy.yaml": frozenset(
        {"policy_id", "_runtime.construction.axes"}
    ),
    "venue_constraint_policy.yaml": frozenset({"policy_id"}),
    "critical_input_policy.yaml": frozenset({"policy_id", "issuer_principal_id"}),
    "strategy_bindings.yaml": frozenset({"strategies"}),
}

#: The declared paths above that FOLD a subtree, and therefore need a narrowing test of their
#: own (see the ⚠ on ``_DIFFERS_FROM_LONG``).
#: :func:`test_every_folded_prefix_has_a_narrowing_test` keeps this honest.
_FOLDED_PREFIXES: frozenset[tuple[str, str]] = frozenset(
    {
        ("order_construction_policy.yaml", "_runtime.construction.axes"),
        ("strategy_bindings.yaml", "strategies"),
    }
)

#: Present in exactly one tree. ONLY the strategy file: it is renamed, not edited in place, so
#: the DSL entry comparison cannot be flipped by a one-line render substitution (kickoff §5 3 ④).
#:
#: ``README.md`` is deliberately NOT here. The first cut put it in these sets, which was a false
#: statement -- both trees have one -- and worse, it made the file *classified but unchecked*:
#: every assertion below iterates the identical set or the differs set, so a name parked in a
#: third set no assertion reads is exempt from all of them. That is the same hole
#: ``test_tenant_tree_copies.py`` grew and its red proof caught; it gets its own category and its
#: own assertion here instead.
_SHORT_ONLY = frozenset({_SHORT_STRATEGY_REL})
_LONG_ONLY = frozenset({_LONG_STRATEGY_REL})

#: Present in BOTH trees and expected to differ, but not comparable as parsed YAML. Checked by
#: :func:`test_prose_files_differ_and_each_describes_its_own_tree` rather than by the key-path
#: equality above -- a Markdown file has no key paths, and asserting only "it differs" would
#: pass on two READMEs that both describe the LONG tree.
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
    """Every non-mapping node as ``{dotted.path: value}``. A list is ONE leaf -- so a reordered
    or re-valued list shows up as that path differing, never as a silent partial match.
    """
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out.update(_leaves(value, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: node}


def _differing_paths(rel: str) -> set[str]:
    """Every parsed-YAML path that differs between the two trees, folded onto its declared
    prefix.

    "Differs" covers a changed value AND a path present in only one tree -- the latter matters
    for ``strategy_bindings.yaml``, where the direction is encoded in the KEY NAMES
    (``setup_d_long.strategy`` / ``z_entry_max_x1000`` vs their SHORT spellings), so the two
    files do not share a key set at all.

    Folding is what makes a whole-subtree declaration (``strategies``,
    ``_runtime.construction.axes``) expressible without listing leaves that are allowed to
    appear or vanish. A path with no declared prefix is returned UNFOLDED, so it shows up as an
    extra item in the caller's equality assertion rather than being absorbed."""
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


# ---------------------------------------------------------------------------
# The classification itself
# ---------------------------------------------------------------------------


def test_short_tree_classification_is_exhaustive() -> None:
    """README §3's three sets must cover the tree exactly -- no file unclassified, no classified
    file missing. This is what keeps the table from drifting into a description of a past tree:
    adding a file to either tenant tree without saying which set it joins fails here."""
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

    # No name may sit in two categories -- overlap is how a file ends up checked by the wrong
    # assertion (or, with a third set no assertion reads, by none at all).
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

    # ... and every classified name lands in a set some assertion below actually iterates.
    checked = (
        _IDENTICAL_TO_LONG
        | frozenset(_DIFFERS_FROM_LONG)
        | _PROSE_DIFFERS
        | _SHORT_ONLY
        | _LONG_ONLY
    )
    assert classified | long_classified == checked

    # MEASURED 2026-10-09: the two trees share 23 byte-identical files; 6 YAML files diverge in
    # declared key paths; README.md diverges as prose; each tree has its own strategy file.
    assert len(_IDENTICAL_TO_LONG) == 23
    assert len(_DIFFERS_FROM_LONG) == 6
    assert len(_PROSE_DIFFERS) == 1
    assert len(short_files) == len(long_files) == 31


def test_the_counts_the_short_readme_states_are_read_from_it() -> None:
    """PARSE the SHORT README's §3 count line and compare it to the classification above.

    Review L3: asserting integer literals that match other integer literals guards nothing --
    the prose the comment claimed to pin was never opened. The numbers now come OUT of the file.

    This file's baseline is the LONG tree, which is what the SHORT README's §3 line states
    (``LONG 과 바이트 동일``). The SHORT README's §3.0 sentence is about the RESIDENT baseline
    instead, and is parsed by ``test_tenant_tree_copies.py``."""
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
    # The stated parts must add up to the stated total -- four numbers that each match a set
    # but do not sum to the file count would mean a category is missing from the sentence.
    assert identical + yaml_differs + prose_differs + short_only == total


@pytest.mark.parametrize("rel", sorted(_IDENTICAL_TO_LONG))
def test_identical_set_is_byte_identical_to_the_long_tree(rel: str) -> None:
    """BYTE identity, not parsed equality: these files are copies, and "copy" is a property a
    byte comparison can check while a parsed one cannot (a re-indented or re-commented copy is
    no longer the thing the LONG tree's README says it is)."""
    assert (_SHORT_DIR / rel).read_bytes() == (_LONG_DIR / rel).read_bytes(), (
        f"{rel} is classified byte-identical to the LONG tree but differs. If this was "
        f"deliberate, move it to _DIFFERS_FROM_LONG with the key paths that may differ."
    )


@pytest.mark.parametrize("rel", sorted(_PROSE_DIFFERS))
def test_prose_files_differ_and_each_describes_its_own_tree(rel: str) -> None:
    """The prose category's own check, so it is not merely classified.

    Two assertions, because either alone is weak. "They differ" alone passes on two READMEs that
    both describe the LONG deployment (a copy with one word changed). "Each names its own tree"
    alone passes on a SHORT README that is otherwise a verbatim LONG copy carrying LONG's
    declared differences as if they were its own."""
    short_text = (_SHORT_DIR / rel).read_text(encoding="utf-8")
    long_text = (_LONG_DIR / rel).read_text(encoding="utf-8")
    assert short_text != long_text

    assert short_text.startswith("# config/tos_runtime/cp3-setup-d-short/")
    assert long_text.startswith("# config/tos_runtime/cp3-setup-d-long/")
    # Each describes its OWN direction's deployment, not the other's.
    assert "SHORT 배포" in short_text and "LONG 배포" in long_text
    # The SHORT README carries the parity RECORD -- its own §3.3 section, with the measured
    # evidence. The LONG one may (and does) point AT that record; a cross-reference is not the
    # record, so the distinguishing assertion is on the section heading and the measured token,
    # not on the phrase (which appears in both, deliberately).
    # 2026-10-09: the heading moved from "공백" (gap) to "닫혔다" (closed) when the SHORT
    # parity run landed. Asserted on the stable prefix plus the verdict token, so the record
    # cannot be deleted and cannot silently revert to claiming a gap that no longer exists.
    assert "### 3.3 ✅ SHORT parity — **닫혔다" in short_text
    assert "LEGACY_ONLY_ENTRY" in short_text
    assert "### 3.3" not in long_text
    assert "LEGACY_ONLY_ENTRY" not in long_text


def test_every_folded_prefix_has_a_narrowing_test() -> None:
    """``_FOLDED_PREFIXES`` must be exactly the declared paths that are not leaf scalars.

    This is the part that survives me: a future declared path that happens to fold a list or a
    dict gets caught here instead of silently exempting its subtree the way the axes list did.
    Computed from the shipped documents, never from a second hand-written list."""
    folded: set[tuple[str, str]] = set()
    for rel, paths in _DIFFERS_FROM_LONG.items():
        leaves = _leaves(_mapping(_LONG_DIR, rel))
        for path in paths:
            value = leaves.get(path)
            # A declared path is "folded" when it is NOT a single scalar leaf: either it is a
            # prefix of other leaves (a dict) or its own value is a container (a list).
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
    """``_runtime.construction.axes`` is ONE leaf to :func:`_leaves` (a list), so declaring that
    path "may differ" exempts the whole list -- including the TIF axis riding beside DIRECTION.

    Measured 2026-10-09 (review M2): a SHORT-tree TIF edit ``DAY`` -> ``IOC`` stayed green under
    the declared-path comparison alone. This narrows it to what the declaration actually means:
    remove the DIRECTION entry and the remaining axes must be EQUAL between the two trees, and
    the list must be the same LENGTH (so an axis cannot be added or dropped on one side).
    """
    long_axes = _mapping(_LONG_DIR, "order_construction_policy.yaml")["_runtime"][
        "construction"
    ]["axes"]
    short_axes = _mapping(_SHORT_DIR, "order_construction_policy.yaml")["_runtime"][
        "construction"
    ]["axes"]

    assert len(long_axes) == len(short_axes)
    # Exactly one DIRECTION entry per tree -- asserted here too, because "remove the DIRECTION
    # entry" is only a well-defined operation if there is exactly one to remove.
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
    # The axis NAMES are the same set in both, DIRECTION included -- so the narrowed comparison
    # above cannot be satisfied by an axis that simply vanished from one tree.
    assert [entry["axis"] for entry in long_axes] == [
        entry["axis"] for entry in short_axes
    ]


def test_the_bindings_subtree_differs_only_in_the_direction_bearing_names() -> None:
    """``strategies`` is the other declared prefix that folds a whole subtree -- same hazard as
    the axes list, so it gets the same treatment.

    Here the KEY NAMES themselves carry the direction (``setup_d_long.strategy`` /
    ``z_entry_max_x1000`` vs their SHORT spellings), so the subtrees cannot be compared
    path-for-path. What CAN be compared is the shape with those names normalised away: one
    strategy entry, one binding under it, the same ``config_binding_version``, and the binding
    values mirroring to zero (the last two also pinned by the binding tests below, deliberately
    -- this one exists so the folded prefix is not the only thing standing there)."""
    long_strategies = _mapping(_LONG_DIR, "strategy_bindings.yaml")["strategies"]
    short_strategies = _mapping(_SHORT_DIR, "strategy_bindings.yaml")["strategies"]

    assert len(long_strategies) == len(short_strategies) == 1
    (long_stem, long_entry), (short_stem, short_entry) = (
        next(iter(long_strategies.items())),
        next(iter(short_strategies.items())),
    )
    assert long_stem == "setup_d_long.strategy"
    assert short_stem == "setup_d_short.strategy"

    # Same keys at the entry level -- so one tree cannot grow a field the other lacks.
    assert set(long_entry) == set(short_entry) == {"config_binding_version", "bindings"}
    assert long_entry["config_binding_version"] == short_entry["config_binding_version"]

    # One binding each, mirrored. The NAMES differ by design; the magnitudes must match.
    assert len(long_entry["bindings"]) == len(short_entry["bindings"]) == 1
    (long_key, long_value), (short_key, short_value) = (
        next(iter(long_entry["bindings"].items())),
        next(iter(short_entry["bindings"].items())),
    )
    assert long_key == "z_entry_max_x1000"
    assert short_key == "z_entry_min_x1000"
    assert long_value + short_value == 0


@pytest.mark.parametrize("rel", sorted(_DIFFERS_FROM_LONG))
def test_differing_files_differ_in_exactly_the_declared_key_paths(rel: str) -> None:
    """The guard, stated as an equality rather than a subset: the set of parsed-YAML paths that
    differ must EQUAL the declared set.

    Equality in both directions is the point. A superset means an undeclared value moved
    (the half-flipped tree this file exists to catch). A subset means a declared direction slot
    did NOT get flipped -- which is the same bug seen from the other side, and a subset check
    would call it green."""
    assert _differing_paths(rel) == _DIFFERS_FROM_LONG[rel]


# ---------------------------------------------------------------------------
# Direction: the five places it lives (runbook §7.10 3 + two this tree adds)
# ---------------------------------------------------------------------------


def test_short_direction_is_consistent_across_every_slot_that_carries_one() -> None:
    """All five direction slots agree on SHORT, and each pairs with the shape the OCP declares.

    The runbook §7.10 3 checklist names three (``construction.yaml``'s
    ``action_class``/``outbound_side``, the OCP's DIRECTION axis, the strategy file's
    ``direction``); this tree adds ``marketfeed.yaml::direction`` (it rides into every capsule's
    ``SafetyCriticalFacts``) and the DSL entry comparison plus its binding (below)."""
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
    """The mirror half. Landing the SHORT tree must not have edited the LONG one -- a single
    `sed` across ``config/tos_runtime/`` is exactly how that happens."""
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
    """Each slot is ONE line, in both trees.

    Why a line count and not just the parsed value: a render that rewrites these slots has to
    anchor on them, and ``render_paper_config.py::_apply_rules`` requires its anchor to match
    **exactly once** (kickoff §5 3 ④'s measured finding about the strategy file). A duplicated
    slot line would leave the parsed assertions above green while the anchor rule refuses.
    Asserted for both trees so neither can drift into an un-anchorable shape.

    The comparison is **exact whole-line equality**, deliberately -- it is what ``_apply_rules``
    itself does (``matches = [i for i, line in enumerate(lines) if line == rule.anchor]``,
    measured 2026-10-09). A looser comparison here (stripping whitespace, say) would accept a
    trailing-space line that the renderer then fails to match, which is the "check and thing
    checked read different values" failure the root ``CLAUDE.md`` names. A commented-out old
    value is correctly NOT an occurrence, for the same reason: the renderer would not match it
    either."""
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
    """The two meanings of the ``direction`` token, pinned so they cannot silently converge.

    A FLAT rule's ``direction`` is the direction of the **closing action**
    (``tos/src/tos/dsl/proposal.py::build_flat``'s own argument docstring), so closing a short
    is ``LONG`` -- you buy. The OCP's ``action_class_shape`` keys ``CLOSE`` by the direction of
    the **position being closed**, so closing a short is ``CLOSE.SHORT``, whose side is ``BUY``.
    Same fact, opposite spelling.

    They never meet at runtime -- ``resolve_construction_direction`` reads a CLOSE's direction
    off the OCP axis, never off the proposal -- but a reader checking one against the other
    would conclude the tree is inverted. This asserts BOTH spellings at once, in both trees, so
    "fixing" either one to match the other fails here."""
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
            # The CLOSING ACTION's direction -- the opposite of the position held.
            assert target["direction"] == closing_direction
            assert target["direction"] != entry_direction

        # ... and the OCP's opposite spelling for the same close, in the same tree.
        shape = _mapping(directory, "order_construction_policy.yaml")["_runtime"][
            "construction"
        ]["action_class_shape"]
        assert shape["CLOSE"][entry_direction]["position_effect"] == "CLOSE"
        # Closing a long sells; closing a short buys.
        assert shape["CLOSE"]["LONG"]["side"] == "SELL"
        assert shape["CLOSE"]["SHORT"]["side"] == "BUY"


# ---------------------------------------------------------------------------
# The entry comparison and its binding
# ---------------------------------------------------------------------------


def test_short_entry_comparison_is_the_positive_side_through_its_binding() -> None:
    """The fifth direction slot: the DSL comparison's operator, its operand, and the binding key.

    SHORT reads ``z_x1000 >= +threshold`` where LONG reads ``z_x1000 <= -threshold``. The DSL
    has no ``abs()`` (DSL-G1), so each direction gets ONE side -- which is the whole reason the
    two trees have separate strategy files rather than one shared file (kickoff decision 4).
    The threshold is an operand reference, never a literal in the rule."""
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
        # A reference, not a const -- a literal here would bypass the binding entirely.
        assert "const" not in compare["right"]
        assert compare["right"]["ref"] == ["config", key]

        # The binding file declares that key, under this strategy file's own stem, and the
        # loader refuses an unreferenced key (resolve.py rule 4) -- so a leftover key from the
        # other direction cannot sit here unnoticed.
        bindings = _mapping(directory, "strategy_bindings.yaml")["strategies"]
        stem = Path(rel).name.removesuffix(".yaml")
        assert set(bindings) == {stem}
        assert set(bindings[stem]["bindings"]) == {key}


def test_short_z_entry_binding_is_plus_trunc_extreme_atr_mult_times_1000() -> None:
    """``z_entry_min_x1000 == +trunc(extreme_atr_mult x 1000)``, the SHORT mirror of the LONG
    binding's equality -- with ``extreme_atr_mult`` READ from the legacy strategy YAML.

    Reading it is the point. A test-local ``1.8`` would stay green after someone retuned that
    file, and the derivation this tree ships in ``strategy_bindings.yaml``'s header would then be
    a false statement about a value nothing checks. The same discipline the B1b copy of this
    test adopted after its 2026-10-08 review.

    ``trunc`` toward zero is B1a's own quantizer for ``z_x1000``
    (``produce_fields.scaled_int_toward_zero``), which makes both thresholds CONSERVATIVE: the
    legacy ``abs(z) >= 1.8`` admits ``z = +1.8000...``, and integer ``+1799`` fails ``GE +1800``
    exactly as ``-1799`` fails ``LE -1800``."""
    legacy = yaml.safe_load(_LEGACY_STRATEGY_YAML.read_text(encoding="utf-8"))
    extreme = legacy["strategy"]["entry"]["params"]["extreme_atr_mult"]
    threshold = int(extreme * 1000)  # trunc toward zero; 1.8 -> 1800

    short_bindings = _mapping(_SHORT_DIR, "strategy_bindings.yaml")["strategies"][
        "setup_d_short.strategy"
    ]["bindings"]
    long_bindings = _mapping(_LONG_DIR, "strategy_bindings.yaml")["strategies"][
        "setup_d_long.strategy"
    ]["bindings"]

    assert short_bindings["z_entry_min_x1000"] == threshold
    assert long_bindings["z_entry_max_x1000"] == -threshold
    # Exact mirrors: the pair sums to zero. A one-sided retune breaks the symmetry CLAUDE.md's
    # non-negotiable requires, and neither assertion above catches that on its own.
    assert short_bindings["z_entry_min_x1000"] + long_bindings["z_entry_max_x1000"] == 0

    # And the binding version both files declare matches their strategy file's own
    # (resolve.py rule 2) -- a mismatch is a boot refusal, not a silent fallback.
    for directory, rel, stem in (
        (_SHORT_DIR, _SHORT_STRATEGY_REL, "setup_d_short.strategy"),
        (_LONG_DIR, _LONG_STRATEGY_REL, "setup_d_long.strategy"),
    ):
        declared = _mapping(directory, rel)["config_binding_version"]
        bound = _mapping(directory, "strategy_bindings.yaml")["strategies"][stem][
            "config_binding_version"
        ]
        assert declared == bound


# ---------------------------------------------------------------------------
# Identity and the values inherited from the LONG tree
# ---------------------------------------------------------------------------


def test_short_tree_policy_ids_are_short_specific() -> None:
    """Every policy whose CONTENT diverges gets its own ``policy_id``; the ones that are the
    same document keep the shared id.

    The criterion is the LONG tree's: "did the content diverge", not "is this a different tree".
    The OCP joins the renamed set HERE because this tree's DIRECTION axis differs -- and the
    rename is load-bearing for a measured reason: the OCP's ``canonical_digest`` is unchanged by
    the axis AND by the id (measured 2026-10-09), so the activation key's ``member_id`` is the
    ONLY thing that can tell a LONG OCP from a SHORT one."""
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

    # Distinct from the LONG tree's, for all three.
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

    # Generation stays 1 everywhere: this is a DIFFERENT deployment's policy, not the next
    # generation of the LONG one.
    assert (
        _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")["policy_generation"] == 1
    )
    assert cip["policy_generation"] == 1

    # The byte-identical policies deliberately keep their shared ids -- asserted so a future
    # "rename everything in the tenant tree" sweep has to argue with this instead of passing.
    for rel in ("aggregate_risk_policy.yaml", "action_flow_policy.yaml"):
        assert (
            _mapping(_SHORT_DIR, rel)["policy_id"]
            == _mapping(_LONG_DIR, rel)["policy_id"]
        )


def test_policy_digests_cannot_tell_the_two_trees_apart(tmp_path: Path) -> None:
    """MEASURED 2026-10-09: neither the OCP's nor the VCP's ``canonical_digest`` distinguishes
    the LONG tree from the SHORT one -- so the ``policy_id`` renames are the ONLY mechanism that
    does, and this is the test that makes that statement checkable.

    Two different reasons, which is why both halves are here:

    * The **OCP** digest is blind to the content that differs: flipping the ``DIRECTION`` axis
      leaves it unchanged, and so does changing ``policy_id``. The file's own header records the
      first as a KNOWN LIMITATION (DR-0002 §2.3 binds the digest to
      policy_id/generation/version); the measurement shows it does not even track the id.
    * The **VCP** digest DOES cover ``_model_view.shape_constraints`` -- pinned below, because
      that is what makes the tick correction a digest-changing edit. But it does not cover
      ``policy_id``, and the two trees' shapes are IDENTICAL (same tick, lot, quantity bounds,
      same null band). So it is equal across the trees for a completely different reason, and
      "the VCP digest covers the content" must not be read as "it tells the deployments apart".

    Without this test, both READMEs' claims about why the renames matter are prose about a
    property nothing checks -- and a future change that made one digest discriminating would
    leave that prose quietly false."""
    long_ocp = load_order_construction_policy(
        _write(
            tmp_path / "long_ocp.yaml",
            _filled(
                _LONG_DIR / "order_construction_policy.yaml",
                environment="paper",
                account="a",
                instrument="i",
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
            ),
        ),
        scheme=_SCHEME,
    )
    # Different ids, different DIRECTION axis -- same digest.
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
    # Different ids, IDENTICAL shapes -- same digest.
    assert long_vcp.policy.policy_id != short_vcp.policy.policy_id
    assert long_vcp.policy.shape_constraints == short_vcp.policy.shape_constraints
    assert long_vcp.policy.canonical_digest == short_vcp.policy.canonical_digest

    # ... and the VCP digest IS shape-sensitive, so the equality above is about equal shapes and
    # not about a digest that ignores everything. Without this clause the two asserts above
    # would also pass on a VCP digest derived from nothing at all.
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
    """Same operator-fill gate as the LONG tree: ``accounts``/``instruments`` are ``"TBD"`` as
    committed and the loader refuses them."""
    with pytest.raises(VenuePolicyConfigError):
        load_venue_constraint_policy(
            _SHORT_DIR / "venue_constraint_policy.yaml", scheme=_SCHEME
        )


def test_short_tree_inherits_the_tenant_values(tmp_path: Path) -> None:
    """The values commits (a) and (b) landed in the LONG tree are in this one too -- the
    corrected mini ``tick_size`` and the adopted ``max_age_ms``.

    This is the assertion that makes the SHORT tree a copy of the CURRENT LONG tree rather than
    of some earlier one: a tree branched before those commits would carry tick 5 and fifteen
    ``null``s, and nothing else here would notice."""
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
    # The band is still null here too -- landing a SHORT tree opened no send path.
    assert shape.price_min is None and shape.price_max is None

    policy = load_critical_input_policy(
        _SHORT_DIR / "critical_input_policy.yaml", scheme=_SCHEME
    )
    assert [field.field_key for field in policy.fields] == list(_B1A_FIELD_POLICY)
    assert {field.max_age_ms for field in policy.fields} == {_TENANT_MAX_AGE_MS}


def test_short_tree_critical_input_policy_still_refuses_a_null_max_age_ms(
    tmp_path: Path,
) -> None:
    """The null-refusal guard applies to this tree as well -- the fill did not retire it here
    either. Same shape as the LONG tree's: ONE leaf nulled, the last one."""
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
    """The cross-check neither loader can perform, applied to this tree -- the LONG tree's H1
    defect (a ``price_field_key`` naming a field the tree does not declare) must not reappear
    via the copy."""
    construction = _mapping(_SHORT_DIR, "construction.yaml")
    declared = {
        entry["field_key"]
        for entry in _mapping(_SHORT_DIR, "critical_input_policy.yaml")["fields"]
    }
    for key_name in ("price_field_key", "shape_price_field_key"):
        assert construction[key_name] in declared, (key_name, construction[key_name])


def test_short_tree_scope_authorizes_both_directions() -> None:
    """The non-negotiable long/short symmetry rule as a mechanical pin, mirrored from the
    resident suite: committing ONE direction on the composition axis must not narrow either
    policy's own authorized action classes."""
    ocp = _mapping(_SHORT_DIR, "order_construction_policy.yaml")
    assert set(ocp["scope"]["action_classes"]) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    shape = ocp["_runtime"]["construction"]["action_class_shape"]
    assert set(shape) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}
    assert set(shape["CLOSE"]) == {"LONG", "SHORT"}
    venue = _mapping(_SHORT_DIR, "venue_constraint_policy.yaml")
    assert set(venue["scope"]["action_classes"]) == {"NEW_LONG", "NEW_SHORT", "CLOSE"}


def test_short_tree_records_its_parity_result() -> None:
    """README §3.3: the SHORT parity run and its two remaining qualifications.

    Until 2026-10-09 this tree's §3.3 recorded a GAP ("this direction has no parity
    evidence"). The run landed, so what has to survive a later edit changed with it, and the
    assertions below are the new record rather than the old one:

    * the measured SHORT numbers (176/176 rule level, UNRESOLVED 0) and the declared
      difference that now absorbs the LONG half (``B1b-D5`` via ``LEGACY_ONLY_ENTRY``);
    * the qualification that what ran was the B1b copy, not this tree's own file (its
      coordinates are ``"TBD"``, so it cannot be loaded as committed);
    * the ``short_blocked_regimes`` disposition -- the deletion is real for the DEPLOYMENT but
      CANNOT appear in this comparison, because the guard sits in ``setup_d_adapter`` after
      ``check()`` returns and B2 drives ``check()`` directly. A reader who loses that sentence
      will read ``B1b-D8``'s zero as "the guard was harmless".
    """
    prose = (_SHORT_DIR / "README.md").read_text(encoding="utf-8")
    assert "B1b-D5" in prose
    assert "176/176" in prose
    assert "UNRESOLVED 0" in prose
    assert "LEGACY_ONLY_ENTRY" in prose
    assert "short_blocked_regimes" in prose
    assert "setup_d_adapter" in prose
    assert "B1b-D8" in prose

    # And the asymmetry the README claims is still true of the legacy YAML it cites -- a claim
    # about another file is only a guard if it reads that file.
    legacy = yaml.safe_load(_LEGACY_STRATEGY_YAML.read_text(encoding="utf-8"))
    params = legacy["strategy"]["entry"]["params"]
    assert params[
        "short_blocked_regimes"
    ], "README §3.3 claims the legacy strategy blocks SHORT in some regimes; it no longer does"
    assert not params[
        "long_blocked_regimes"
    ], "README §3.3 claims the guard was SHORT-only; long_blocked_regimes is now non-empty"

    # The disposition is a claim about ANOTHER file's call order, so it is read there too: if
    # the regime block ever moves ahead of check(), B2 would start seeing it and the README's
    # "cannot appear in this comparison" becomes false.
    adapter = _REPO_ROOT / "shared" / "strategy" / "entry" / "setup_d_adapter.py"
    source = adapter.read_text(encoding="utf-8")
    assert source.index("self._setup.check(") < source.index("short_blocked_regimes"), (
        "the regime block moved ahead of check(); README §3.3 2 now claims something false "
        "about what a B1a/B2/B1b comparison can see"
    )
