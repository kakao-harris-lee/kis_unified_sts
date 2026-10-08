"""Copy-drift guard: the CP-3 tenant trees' byte copies of the RESIDENT
``config/tos_runtime/paper/`` tree must stay byte copies.

**The failure this exists to prevent.** Both tenant trees
(``config/tos_runtime/cp3-setup-d-long/`` and ``cp3-setup-d-short/``) were built as byte copies
of the resident tree plus a short, declared list of differences -- and that copied set includes
``release.yaml``, which carries ``expected_code_digest``. Any PR that touches runtime code
re-derives that pin, but it re-derives it in the file the resident session reads: the resident
tree's. The tenant copies would silently keep the OLD digest, and the first tenant boot would
ABORT on a mismatch nothing had flagged -- the resident session re-derives and compares daily
(runbook ``docs/runbooks/tos-paper-boot.md`` §5 ①), the tenant trees have never booted, so there
was no lane in which the staleness could surface before the boot that fails.

Before this file, nothing checked it. ``test_tenant_tree_short.py`` compares the two TENANT
trees against each other, which is blind to this entirely: a stale ``release.yaml`` copied into
both trees is perfectly symmetric.

**Why an exhaustive literal rather than "compare everything that looks the same".** A guard that
derives its own expectation from the files it checks passes no matter what the files say. So the
three sets below are written out, and :func:`test_classification_is_exhaustive` asserts their
union is exactly the tree -- adding a file to a tenant tree without classifying it is a failure,
which is the only way the "every copy is still a copy" claim can stay true as the trees grow.

Scope note: this file is about identity with the RESIDENT tree. The tenant-vs-tenant symmetry
and the direction slots live in ``test_tenant_tree_short.py``; the adopted VALUES live in
``test_deploy_policies.py``.

Hermetic (D1.4): the real files are only READ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_RESIDENT_DIR = _CONFIG_ROOT / "paper"

#: Copied byte-for-byte from the resident tree, in BOTH tenant trees. These are the resident
#: deployment's approved values, and "copy" is the mechanically checkable property that lets the
#: tenant trees inherit that approval without re-arguing each value.
_IDENTICAL_BOTH = frozenset(
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

#: ``marketfeed.yaml`` is a resident copy in the LONG tree and a DIVERGENCE in the SHORT one
#: (which flips ``direction``). Split across two literals rather than folded into either set,
#: because that asymmetry is exactly the kind of fact a shared literal would hide -- and because
#: a name that is in neither per-tree set would be *classified but unchecked*, which is how the
#: first cut of this file let the SHORT ``marketfeed.yaml`` quietly revert to a resident copy
#: (caught by its own red proof, 2026-10-09).
_IDENTICAL_LONG_ONLY = frozenset({"marketfeed.yaml"})
_DIFFERS_SHORT_ONLY: dict[str, str] = {
    "marketfeed.yaml": (
        "direction LONG -> SHORT (decision 4) -- it rides into every capsule's "
        "SafetyCriticalFacts, so this tree cannot share the resident copy"
    ),
}

#: Diverged from the resident tree in BOTH tenant trees, with the reason. The reason is part of
#: the literal because "this file differs" is not a disposition --
#: ``config/tos_runtime/README.md``'s rule is that a value without a citation does not belong in
#: these trees, and a divergence is a value.
_DIFFERS_FROM_RESIDENT: dict[str, str] = {
    "venue_constraint_policy.yaml": (
        "max_quantity null -> 10000 (decision 9 (a), 2026-10-08) + tick_size 5 -> 2 "
        "(mini regulation 시행세칙 제4조의9 제2호, 2026-10-09) + tenant policy_id"
    ),
    "critical_input_policy.yaml": (
        "not a copy at all -- the resident file declares the boot-proof fixture's THREE fields, "
        "these declare B1a's FIFTEEN tenant upstream fields + tenant policy_id"
    ),
    "construction.yaml": (
        "price_field_key/shape_price_field_key 'close' -> 'close_x100' (review H1: the resident "
        "key is not declared by this tree's critical_input_policy)"
    ),
    "engine.yaml": (
        "comment-only -- the resident comment cites the resident strategy (bootproof_band), "
        "which is false in a tree that does not contain it"
    ),
    "order_construction_policy.yaml": (
        "comment-only in the LONG tree; the SHORT tree also flips the DIRECTION axis and renames "
        "policy_id"
    ),
}

#: Present only in a tenant tree.
_TENANT_ONLY_COMMON = frozenset({"README.md", "strategy_bindings.yaml"})
_TENANT_STRATEGY = {
    "cp3-setup-d-long": "strategies/setup_d_long.strategy.yaml",
    "cp3-setup-d-short": "strategies/setup_d_short.strategy.yaml",
}

#: Present only in the RESIDENT tree -- the boot-proof strategy the tenant strategy replaces.
#: Asserted as an absence, because "the tenant tree does not carry the resident strategy" is what
#: makes the ``engine.yaml`` comment divergence above necessary rather than cosmetic.
_RESIDENT_ONLY = frozenset({"strategies/bootproof_band.strategy.yaml"})

_TENANT_TREES = tuple(_TENANT_STRATEGY)

#: The one file whose staleness is a BOOT ABORT rather than a stale comment, called out on its
#: own so the failure message can say what to do. ``tos-gate``'s kernel digest and the resident
#: session's daily re-derivation both read the RESIDENT copy; nothing reads these.
_CODE_DIGEST_PIN = "release.yaml"


def _files(directory: Path) -> frozenset[str]:
    return frozenset(
        str(path.relative_to(directory))
        for path in directory.rglob("*")
        if path.is_file()
    )


def _identical_set(tree: str) -> frozenset[str]:
    """The files THIS tree declares byte-identical to the resident tree."""
    if tree == "cp3-setup-d-long":
        return _IDENTICAL_BOTH | _IDENTICAL_LONG_ONLY
    return _IDENTICAL_BOTH


def _differs_set(tree: str) -> dict[str, str]:
    """The files THIS tree declares divergent, mapped to the reason."""
    if tree == "cp3-setup-d-long":
        return dict(_DIFFERS_FROM_RESIDENT)
    return {**_DIFFERS_FROM_RESIDENT, **_DIFFERS_SHORT_ONLY}


def _classified(tree: str) -> frozenset[str]:
    """Every name this tree accounts for.

    Built from the per-tree identical/differs sets ONLY -- never from a union that includes a
    name neither of them covers. That is the invariant
    :func:`test_every_classified_file_is_either_checked_as_a_copy_or_as_a_divergence` asserts
    directly, because a classified-but-unchecked name satisfies the exhaustiveness test while
    being exempt from every drift check."""
    return (
        _identical_set(tree)
        | frozenset(_differs_set(tree))
        | _TENANT_ONLY_COMMON
        | {_TENANT_STRATEGY[tree]}
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_classification_is_exhaustive(tree: str) -> None:
    """Every file in each tenant tree is classified, and every classified name exists.

    This is the assertion that keeps the rest of this file honest. Without it, a new file added
    to a tenant tree -- a copy of a resident file, say -- would simply not be checked, and
    "every declared copy is still a copy" would be true of a shrinking set."""
    present = _files(_CONFIG_ROOT / tree)
    classified = _classified(tree)
    assert classified == present, (
        f"{tree}: unclassified files {sorted(present - classified)}; "
        f"classified but absent {sorted(classified - present)}. Add each new file to exactly "
        f"one of _IDENTICAL_BOTH / _IDENTICAL_LONG_ONLY / _DIFFERS_FROM_RESIDENT / "
        f"_TENANT_ONLY_COMMON in this file, with its reason if it differs."
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_every_classified_file_is_either_checked_as_a_copy_or_as_a_divergence(
    tree: str,
) -> None:
    """No name may be classified yet exempt from both drift checks -- and no name may be in both.

    This is not a restatement of :func:`test_classification_is_exhaustive`. That test asks "is
    every file named somewhere"; this one asks "does being named actually subject the file to a
    check". The first cut of this file failed exactly here: ``marketfeed.yaml`` was unioned into
    the SHORT tree's classified set so exhaustiveness passed, but it was in neither the SHORT
    tree's identical set nor its divergence set, so reverting it to a byte copy of the resident
    file -- undoing the direction flip that is the whole point of the SHORT tree -- was green.
    A name in a classification literal is worth nothing on its own; it has to land in a set some
    assertion iterates."""
    identical = _identical_set(tree)
    differs = frozenset(_differs_set(tree))
    tenant_only = _TENANT_ONLY_COMMON | {_TENANT_STRATEGY[tree]}

    overlap = identical & differs
    assert (
        not overlap
    ), f"{tree}: {sorted(overlap)} are declared BOTH byte-identical and divergent"
    assert not (identical | differs) & tenant_only, (
        f"{tree}: {sorted((identical | differs) & tenant_only)} are declared tenant-only AND "
        f"compared against the resident tree"
    )
    # The checked set is exactly the classified set minus the tenant-only files (which have no
    # resident counterpart to compare against, asserted by the resident-coverage test).
    assert identical | differs | tenant_only == _classified(tree)
    unchecked = _classified(tree) - identical - differs - tenant_only
    assert not unchecked, (
        f"{tree}: {sorted(unchecked)} are classified but no assertion compares them to the "
        f"resident tree — put each in _identical_set or _differs_set for this tree"
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_resident_tree_is_fully_covered(tree: str) -> None:
    """Read from the RESIDENT side: every resident file is either copied, declared divergent, or
    declared absent from this tenant tree.

    The other direction of the same claim, and not redundant: a resident file that NO tenant
    file corresponds to would pass :func:`test_classification_is_exhaustive` silently (nothing in
    the tenant tree is unclassified), and a future resident addition would then be missing from
    the tenant trees with no test saying so."""
    resident = _files(_RESIDENT_DIR)
    accounted = _identical_set(tree) | frozenset(_differs_set(tree)) | _RESIDENT_ONLY
    assert accounted == resident, (
        f"{tree}: resident files not accounted for {sorted(resident - accounted)}; "
        f"accounted but not in the resident tree {sorted(accounted - resident)}"
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_release_yaml_is_byte_identical_to_the_resident_pin(tree: str) -> None:
    """``release.yaml`` carries ``expected_code_digest``. Asserted separately from the bulk copy
    check so that THIS failure message says what to do.

    A runtime-code PR re-derives this pin in the resident tree, because that is the file the
    resident session reads and compares every morning. These copies are read by nothing until a
    tenant boots -- so a stale copy is invisible until the boot that aborts on it."""
    tenant = _CONFIG_ROOT / tree / _CODE_DIGEST_PIN
    resident = _RESIDENT_DIR / _CODE_DIGEST_PIN
    assert tenant.read_bytes() == resident.read_bytes(), (
        f"{tree}/{_CODE_DIGEST_PIN} has drifted from {resident.relative_to(_REPO_ROOT)}. "
        f"If a runtime-code change re-derived expected_code_digest, **re-derive it in BOTH "
        f"tenant trees in the SAME PR** -- otherwise the first tenant boot ABORTs on a digest "
        f"mismatch and nothing else in this suite would have caught it."
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_declared_copies_are_byte_identical_to_the_resident_tree(tree: str) -> None:
    """The bulk claim: every file declared a resident copy still is one, byte for byte.

    BYTE identity, not parsed equality -- "copy" is what the trees' READMEs claim, and a
    re-indented or re-commented file is no longer that. Reported as a collected list rather than
    failing on the first mismatch, because a resident-side edit typically drifts several files at
    once and seeing one name at a time turns one fix into several rounds."""
    drifted = [
        rel
        for rel in sorted(_identical_set(tree))
        if (_CONFIG_ROOT / tree / rel).read_bytes()
        != (_RESIDENT_DIR / rel).read_bytes()
    ]
    assert not drifted, (
        f"{tree}: these files are declared byte-identical to "
        f"{_RESIDENT_DIR.relative_to(_REPO_ROOT)} but have drifted: {drifted}. Either the "
        f"resident file changed (update the tenant copies in the SAME PR) or the tenant copy was "
        f"edited on purpose (move it to _DIFFERS_FROM_RESIDENT with its reason)."
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_declared_divergences_actually_diverge(tree: str) -> None:
    """The mirror half: a file listed as divergent must really differ.

    A stale entry here is not harmless -- it is a file that silently stopped being checked for
    drift while still carrying a written reason explaining a difference it no longer has.
    """
    same = [
        rel
        for rel in sorted(_differs_set(tree))
        if (_CONFIG_ROOT / tree / rel).read_bytes()
        == (_RESIDENT_DIR / rel).read_bytes()
    ]
    assert not same, (
        f"{tree}: these files are declared divergent from the resident tree but are byte-"
        f"identical to it: {same}. Move them to the identical set -- a divergence entry that "
        f"does not diverge exempts a real copy from the drift check."
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_resident_only_files_are_absent_from_the_tenant_tree(tree: str) -> None:
    """The resident boot-proof strategy is NOT in a tenant tree, and its replacement is.

    Both halves together: if ``bootproof_band.strategy.yaml`` were copied in, the tree would
    load TWO strategies, and the ``engine.yaml`` divergence reason above ("the resident comment
    cites a strategy this tree does not contain") would be false."""
    for rel in _RESIDENT_ONLY:
        assert not (
            _CONFIG_ROOT / tree / rel
        ).exists(), f"{tree}/{rel} is the RESIDENT boot-proof strategy and must not be copied here"
    assert (_CONFIG_ROOT / tree / _TENANT_STRATEGY[tree]).is_file()
    strategies = {
        str(path.relative_to(_CONFIG_ROOT / tree))
        for path in (_CONFIG_ROOT / tree / "strategies").iterdir()
        if path.is_file()
    }
    assert strategies == {_TENANT_STRATEGY[tree]}, (
        f"{tree}/strategies/ holds {sorted(strategies)}; exactly one strategy file is expected "
        f"(the loader's stray-file rule refuses the whole directory otherwise)"
    )


def test_the_counts_each_tree_readme_states() -> None:
    """The counts the trees' READMEs write out, asserted against the literals above so the prose
    and the classification cannot drift apart."""
    assert len(_identical_set("cp3-setup-d-long")) == 23
    assert len(_differs_set("cp3-setup-d-long")) == 5
    assert len(_identical_set("cp3-setup-d-short")) == 22
    assert len(_differs_set("cp3-setup-d-short")) == 6
    for tree in _TENANT_TREES:
        assert len(_files(_CONFIG_ROOT / tree)) == 31
