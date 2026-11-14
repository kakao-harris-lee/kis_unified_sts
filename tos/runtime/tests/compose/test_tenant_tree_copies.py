"""Copy-drift guard: the CP-3 tenant trees' byte copies of the RESIDENT"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_RESIDENT_DIR = _CONFIG_ROOT / "paper"

_IDENTICAL_BOTH = frozenset(
    {
        "action_flow_policy.yaml",
        "aggregate_risk_policy.yaml",
        "authority.yaml",
        "broker_scopes.yaml",
        "calendar.yaml",
        "coordinator_preconditions.yaml",
        "currentness.yaml",
        "egress_coordinates.yaml",
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

_IDENTICAL_LONG_ONLY = frozenset({"marketfeed.yaml"})
_DIFFERS_SHORT_ONLY: dict[str, str] = {
    "marketfeed.yaml": (
        "direction LONG -> SHORT (decision 4) -- it rides into every capsule's "
        "SafetyCriticalFacts, so this tree cannot share the resident copy"
    ),
}

_DIFFERS_FROM_RESIDENT: dict[str, str] = {
    "venue_constraint_policy.yaml": (
        "max_quantity null -> 10000 (decision 9 (a), 2026-10-08) + tick_size 5 -> 2 "
        "(mini regulation 시행세칙 제4조의9 제2호, 2026-10-09) + tenant policy_id. LONG only, "
        "2026-10-16: _runtime.price_scale 100 + _runtime.band_source (kind producer_journal) "
        "-- the band 원천 경로 변경 plan's §4 'LONG tenant 만' switch-on; the resident tree's "
        "observations are synthetic, so a band there would make every attempt INADMISSIBLE"
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
        "template DATA prose differs -- the tick 5 -> 2 correction rewrote the "
        "unit_multiplier_currency_and_numeric_rules line (DR-0002 §2.1 template DATA, never "
        "interpreted by the runtime), so this is NOT comment-only. Since 2026-11-04 the typed "
        "content differs too: #1025 added ZERO_POSITION to admitted_quantity_bases, a content "
        "revision, so policy_generation went 3 -> 4 and with it the canonical_digest (measured: "
        "resident c90444b9... gen 3, LONG/SHORT 1d0ecc72... gen 4 -- equal to each other). The "
        "shared policy_id stays: (kind, member_id, generation) still tells the two documents "
        "apart. The SHORT tree also flips the DIRECTION axis and renames policy_id"
    ),
    "RENDER.yaml": (
        "not a copy candidate at all -- a render manifest describes ITS OWN tree's slots and "
        "modes (plan 2026-10-09 §2.1). The resident one declares direction.mode 'substitute' + "
        "journal.mode 'synthetic_bootproof'; a tenant tree is committed PER DIRECTION and takes "
        "its observations from the ③ producer, so it declares 'declared' + 'external' and its "
        "strategy slots name this tree's own Setup D file with the §2.2 YAML-anchor spelling. "
        "Landed in PR-B of that plan (2026-10-10), which is the step the _RESIDENT_ONLY entry "
        "this replaced was staged to force"
    ),
}

_TENANT_ONLY_COMMON = frozenset({"README.md", "strategy_bindings.yaml", "fields.yaml"})
_TENANT_STRATEGY = {
    "cp3-setup-d-long": "strategies/setup_d_long.strategy.yaml",
    "cp3-setup-d-short": "strategies/setup_d_short.strategy.yaml",
}

_RESIDENT_ONLY: dict[str, str] = {
    "strategies/bootproof_band.strategy.yaml": (
        "the resident boot-proof strategy; each tenant tree carries its own Setup D strategy "
        "instead, and loading two would refuse"
    ),
}

_TENANT_TREES = tuple(_TENANT_STRATEGY)

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
    """Every name this tree accounts for."""
    return (
        _identical_set(tree)
        | frozenset(_differs_set(tree))
        | _TENANT_ONLY_COMMON
        | {_TENANT_STRATEGY[tree]}
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_classification_is_exhaustive(tree: str) -> None:
    """Every file in each tenant tree is classified, and every classified name exists."""
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
    """No name may be classified yet exempt from both drift checks -- and no name may be in both."""
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
    assert identical | differs | tenant_only == _classified(tree)
    unchecked = _classified(tree) - identical - differs - tenant_only
    assert not unchecked, (
        f"{tree}: {sorted(unchecked)} are classified but no assertion compares them to the "
        f"resident tree — put each in _identical_set or _differs_set for this tree"
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_resident_tree_is_fully_covered(tree: str) -> None:
    """Read from the RESIDENT side: every resident file is either copied, declared divergent, or"""
    resident = _files(_RESIDENT_DIR)
    accounted = (
        _identical_set(tree) | frozenset(_differs_set(tree)) | frozenset(_RESIDENT_ONLY)
    )
    assert accounted == resident, (
        f"{tree}: resident files not accounted for {sorted(resident - accounted)}; "
        f"accounted but not in the resident tree {sorted(accounted - resident)}"
    )


@pytest.mark.parametrize("tree", _TENANT_TREES)
def test_release_yaml_is_byte_identical_to_the_resident_pin(tree: str) -> None:
    """``release.yaml`` carries ``expected_code_digest``. Asserted separately from the bulk copy"""
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
    """The bulk claim: every file declared a resident copy still is one, byte for byte."""
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
    """The mirror half: a file listed as divergent must really differ."""
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
    """Each resident-only file is NOT in a tenant tree, and the strategy's replacement is."""
    for rel, reason in _RESIDENT_ONLY.items():
        path = _CONFIG_ROOT / tree / rel
        why = f"{tree}/{rel} is resident-only and must not be copied here -- {reason}"
        assert not path.exists(), why
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


def test_the_counts_the_long_readme_states_are_read_from_it() -> None:
    """PARSE the LONG README's own count line and compare it to the classification."""
    readme = (_CONFIG_ROOT / "cp3-setup-d-long" / "README.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"이 트리는 (\d+) 파일이다: 바이트 동일 (\d+) \+ 다름 (\d+) \+ tenant 전용 (\d+)",
        readme,
    )
    assert match is not None, (
        "the LONG README's §3 count line is gone or reworded -- this test reads it, so the "
        "sentence is load-bearing; update the regex together with the prose"
    )
    total, identical, differs, tenant_only = (int(g) for g in match.groups())

    assert identical == len(_identical_set("cp3-setup-d-long"))
    assert differs == len(_differs_set("cp3-setup-d-long"))
    assert tenant_only == len(
        _TENANT_ONLY_COMMON | {_TENANT_STRATEGY["cp3-setup-d-long"]}
    )
    assert total == len(_files(_CONFIG_ROOT / "cp3-setup-d-long"))
    assert identical + differs + tenant_only == total


def test_the_resident_copy_count_the_short_readme_states_is_read_from_it() -> None:
    """PARSE the SHORT README's §3.0 sentence about the RESIDENT baseline."""
    readme = (_CONFIG_ROOT / "cp3-setup-d-short" / "README.md").read_text(
        encoding="utf-8"
    )
    match = re.search(
        r"바이트 동일한 (\d+) 개\*{0,2} 가운데 \*{0,2}(\d+) 개가 상주", readme
    )
    assert (
        match is not None
    ), "the SHORT README's §3.0 resident-copy sentence is gone or reworded -- this test reads it"
    identical_to_long, resident_copies = (int(g) for g in match.groups())

    short_files = _files(_CONFIG_ROOT / "cp3-setup-d-short")
    long_files = _files(_CONFIG_ROOT / "cp3-setup-d-long")
    same_as_long = {
        rel
        for rel in short_files & long_files
        if (_CONFIG_ROOT / "cp3-setup-d-short" / rel).read_bytes()
        == (_CONFIG_ROOT / "cp3-setup-d-long" / rel).read_bytes()
    }
    also_resident = {
        rel
        for rel in same_as_long
        if (_RESIDENT_DIR / rel).is_file()
        and (_RESIDENT_DIR / rel).read_bytes()
        == (_CONFIG_ROOT / "cp3-setup-d-short" / rel).read_bytes()
    }
    assert identical_to_long == len(same_as_long)
    assert resident_copies == len(also_resident)
    remainder = same_as_long - also_resident
    assert len(remainder) == identical_to_long - resident_copies
    assert remainder == {"engine.yaml", "fields.yaml"}, remainder
    for name in sorted(remainder):
        assert f"`{name}`" in readme, f"the SHORT README does not name {name}"
