"""Closes the A-0b class (docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md"""

from __future__ import annotations

import pytest

from .example_integrity import (
    CONFIG_DIR,
    assert_required_paths_present,
    assert_shipped_example_is_a_template,
    assert_shipped_example_still_refuses,
    assert_touchpoints_match,
    call_loader,
)
from .example_integrity_registry import (
    EXAMPLE_LOADERS,
    EXAMPLE_REQUIRED_PATHS,
    EXAMPLE_TEMPLATE_ONLY,
    EXAMPLE_TOUCHPOINTS,
    LOADS_SUCCESSFULLY_LOADERS,
    MULTI_READER_CHECKS,
)

_LOADS_SUCCESSFULLY_DEDICATED_TESTS = frozenset(LOADS_SUCCESSFULLY_LOADERS)
_MULTI_READER_DEDICATED_TESTS = frozenset(MULTI_READER_CHECKS)


def _shipped_example_stems() -> list[str]:
    return sorted(
        path.name[: -len(".example.yaml")] for path in CONFIG_DIR.glob("*.example.yaml")
    )


def test_every_shipped_example_is_registered() -> None:
    """Every ``*.example.yaml`` this repo actually ships must have a"""
    shipped = set(_shipped_example_stems())
    registered = set(EXAMPLE_REQUIRED_PATHS)
    missing = shipped - registered
    assert not missing, (
        f"shipped example(s) {sorted(missing)} have no EXAMPLE_REQUIRED_PATHS entry in "
        "example_integrity_registry.py — add one (see that module's own docstring for how "
        "the existing entries were built)."
    )
    stale = registered - shipped
    assert not stale, (
        f"EXAMPLE_REQUIRED_PATHS registers {sorted(stale)}, which no longer ships as a "
        "*.example.yaml file — remove the stale entry."
    )


def test_every_registered_example_has_value_leak_coverage() -> None:
    """Every ``EXAMPLE_REQUIRED_PATHS`` entry has EXACTLY ONE value-leak check assigned to it —"""
    all_registered = set(EXAMPLE_REQUIRED_PATHS)
    covered = (
        set(EXAMPLE_LOADERS)
        | EXAMPLE_TEMPLATE_ONLY
        | _LOADS_SUCCESSFULLY_DEDICATED_TESTS
        | _MULTI_READER_DEDICATED_TESTS
    )
    uncovered = all_registered - covered
    assert not uncovered, (
        f"{sorted(uncovered)} have NO value-leak check at all — a real, concrete value could "
        "leak into the shipped example and every test in this module would stay green. Assign "
        "each to EXAMPLE_LOADERS (if the loader still refuses when called directly), "
        "EXAMPLE_TEMPLATE_ONLY (if it does not — see that constant's own docstring), or add a "
        "dedicated test and register it in one of the two sets above test_shipped_example_"
        "integrity.py's own test_every_registered_example_has_value_leak_coverage."
    )
    orphaned = covered - all_registered
    assert not orphaned, (
        f"{sorted(orphaned)} are covered by a value-leak check but have no "
        "EXAMPLE_REQUIRED_PATHS entry — either it no longer ships, or the required-paths "
        "registry is missing it (see test_every_shipped_example_is_registered)."
    )
    categories = [
        set(EXAMPLE_LOADERS),
        EXAMPLE_TEMPLATE_ONLY,
        _LOADS_SUCCESSFULLY_DEDICATED_TESTS,
        _MULTI_READER_DEDICATED_TESTS,
    ]
    for i, first in enumerate(categories):
        for second in categories[i + 1 :]:
            overlap = first & second
            assert not overlap, (
                f"{sorted(overlap)} appear in more than one value-leak-check category — that "
                "hides which check (if either) was actually kept up to date; assign each config "
                "to exactly one category."
            )


@pytest.mark.parametrize("stem", sorted(EXAMPLE_REQUIRED_PATHS))
def test_required_key_paths_present(stem: str) -> None:
    """The shipped example for ``stem`` carries every key path its real reader(s) require as an"""
    assert_required_paths_present(stem, EXAMPLE_REQUIRED_PATHS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_TOUCHPOINTS))
def test_touchpoints_have_not_drifted(stem: str) -> None:
    """The live set of ``tos_runtime`` source files referencing ``"{stem}.yaml"`` still matches"""
    assert_touchpoints_match(stem, EXAMPLE_TOUCHPOINTS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_LOADERS))
def test_shipped_example_still_refuses_to_load(stem: str) -> None:
    """Every single-reader shipped example still refuses to load as-shipped — see"""
    assert_shipped_example_still_refuses(stem, EXAMPLE_LOADERS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_TEMPLATE_ONLY))
def test_shipped_example_is_a_template(stem: str) -> None:
    """Every leaf of these shipped examples is ``null``/``[]`` — see"""
    assert_shipped_example_is_a_template(stem)


def test_the_template_only_lane_is_empty_and_says_so() -> None:
    """``EXAMPLE_TEMPLATE_ONLY`` has no members since plan S2-a removed the two all-optional"""
    assert not EXAMPLE_TEMPLATE_ONLY, sorted(EXAMPLE_TEMPLATE_ONLY)


@pytest.mark.parametrize("stem", sorted(LOADS_SUCCESSFULLY_LOADERS))
def test_shipped_example_loads_successfully(stem: str) -> None:
    """``custody.manifest``/``evidence_retention`` are confirmed to be genuinely loadable"""
    call_loader(LOADS_SUCCESSFULLY_LOADERS[stem], CONFIG_DIR / f"{stem}.example.yaml")


@pytest.mark.parametrize("stem", sorted(MULTI_READER_CHECKS))
def test_multi_reader_example_still_refuses_on_both_readers(stem: str) -> None:
    """``risk`` has multiple independent real readers (this module's own docstring) — every one"""
    MULTI_READER_CHECKS[stem]()
