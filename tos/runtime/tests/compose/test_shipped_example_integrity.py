"""Closes the A-0b class (docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md
§0.1.4 / §4 W-A row A-0b): a shipped ``tos/runtime/config/*.example.yaml`` file that satisfies
only SOME of the readers that parse it.

``safety_activation.example.yaml`` filled in exactly the ``activation:``/``not_expired:`` schema
:mod:`tos_runtime.safety.profile` reads, and silently had NO ``members:`` key at all — the SEPARATE
top-level key :func:`tos_runtime.venue.activation.load_activation_members` reads from the SAME
document. A copy of the shipped example refused to boot, but every existing test that touched this
file only ever checked "does loading it refuse" (true either way — a missing key and a present-
but-null key produce the identical named-TBD refusal in every loader this codebase has, by
convention: ``raw.get(key) is None`` cannot tell them apart), so nothing caught it. This module is
the general fix: every shipped example, checked against every one of its real readers, for
STRUCTURAL completeness independently of the loaders' own (identical either way) refusal
behavior — see :mod:`tests.compose.example_integrity`'s own module docstring for the
full mechanism, and :mod:`tests.compose.example_integrity_registry` for the per-config
registry this sweeps.

Supersedes the narrower ``test_shipped_example_file_is_all_null_and_therefore_refuses`` tests in
``test_construction_config.py``, ``test_marketfeed_intake_kind_wiring.py``, and
``transport/kis_quote/test_config.py`` — those now call
:func:`tests.compose.example_integrity.assert_required_paths_present` too (same
underlying check, keeping each loader's own regression pin local to its own test module) rather
than duplicating this sweep's registry-driven parametrization.
"""

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
    CUSTODY_MANIFEST_LOADER,
    EVIDENCE_RETENTION_LOADER,
    EXAMPLE_LOADERS,
    EXAMPLE_REQUIRED_PATHS,
    EXAMPLE_TEMPLATE_ONLY,
    EXAMPLE_TOUCHPOINTS,
)

#: The other three ways a config's own value-leak coverage is asserted, beyond
#: EXAMPLE_LOADERS/EXAMPLE_TEMPLATE_ONLY — each has its own dedicated test below. Kept as an
#: explicit set (not just "everything not in the other two") so
#: test_every_registered_example_has_value_leak_coverage can name a gap precisely instead of
#: silently passing on one (PR #737 review, HIGH finding: the multi-reader/multi-path-constructor
#: exclusion comment above EXAMPLE_LOADERS once *claimed* coverage that did not exist).
_LOADS_SUCCESSFULLY_DEDICATED_TESTS = frozenset(
    {"custody.manifest", "evidence_retention"}
)
_MULTI_READER_DEDICATED_TESTS = frozenset({"safety_activation", "risk"})


def _shipped_example_stems() -> list[str]:
    return sorted(
        path.name[: -len(".example.yaml")] for path in CONFIG_DIR.glob("*.example.yaml")
    )


def test_every_shipped_example_is_registered() -> None:
    """Every ``*.example.yaml`` this repo actually ships must have a
    :data:`EXAMPLE_REQUIRED_PATHS` entry — a NEW example file added without one would silently
    get ZERO structural coverage from this module, the exact kind of quiet gap A-0b closes.
    Parametrizing on a fixed list computed at collection time would not go red for a file added
    after that list was written; comparing live-glob-against-registry, every run, does.
    """
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
    """Every ``EXAMPLE_REQUIRED_PATHS`` entry has EXACTLY ONE value-leak check assigned to it —
    ``EXAMPLE_LOADERS`` ("still refuses"), ``EXAMPLE_TEMPLATE_ONLY`` ("every leaf is null/[]"), or
    one of the two small dedicated-test sets below (custody.manifest/evidence_retention's "loads
    successfully", safety_activation/risk's own multi-reader tests).

    This is the completeness guard PR #737's review found missing: ``EXAMPLE_LOADERS``'s own
    module comment *claimed* ``safety_envelope``/``safety_profile`` "get their own targeted
    test", but nothing actually asserted that claim — a filled-in real value passed the whole
    suite silently. A hardcoded exclusion list is exactly the "레지스트리 + 고정 안 된 위성"
    class this repo has already hit once; this test is what makes a THIRD such gap go red
    instead of silently shipping: add a new example (or move one between categories) without
    updating exactly one of these four sets, and this fails immediately, naming the config —
    which is exactly how this same test caught ``evidence_retention`` missing a category the
    FIRST time it ran, before this docstring was even finished.
    """
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
    """The shipped example for ``stem`` carries every key path its real reader(s) require as an
    explicit key (``null`` is fine) — see ``example_integrity.assert_required_paths_present``.

    Mutation check (run by hand, not in CI — see A-0b completion report): deleting
    ``members:`` from ``safety_activation.example.yaml`` turns this red for
    ``stem="safety_activation"``; restoring it turns this green again.
    """
    assert_required_paths_present(stem, EXAMPLE_REQUIRED_PATHS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_TOUCHPOINTS))
def test_touchpoints_have_not_drifted(stem: str) -> None:
    """The live set of ``tos_runtime`` source files referencing ``"{stem}.yaml"`` still matches
    the recorded set in ``example_integrity_registry.EXAMPLE_TOUCHPOINTS`` — see
    ``example_integrity.assert_touchpoints_match`` for what adding/removing a touch point means
    and what to do about it."""
    assert_touchpoints_match(stem, EXAMPLE_TOUCHPOINTS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_LOADERS))
def test_shipped_example_still_refuses_to_load(stem: str) -> None:
    """Every single-reader shipped example still refuses to load as-shipped — see
    ``example_integrity_registry.EXAMPLE_LOADERS``'s own module comment for why this runs
    ALONGSIDE (never instead of) ``test_required_key_paths_present``, and for which configs are
    deliberately excluded here (each has its own value-leak check instead — see
    ``test_every_registered_example_has_value_leak_coverage``'s own docstring for the full map).
    """
    assert_shipped_example_still_refuses(stem, EXAMPLE_LOADERS[stem])


@pytest.mark.parametrize("stem", sorted(EXAMPLE_TEMPLATE_ONLY))
def test_shipped_example_is_a_template(stem: str) -> None:
    """Every leaf of these shipped examples is ``null``/``[]`` — see
    ``example_integrity_registry.EXAMPLE_TEMPLATE_ONLY``'s own docstring for why "still refuses
    to load" cannot substitute for this here (PR #737 review, HIGH finding).

    Mutation check (run by hand — see the A-0b HIGH-remediation report): replacing
    ``safety_envelope.example.yaml`` wholesale with concrete-looking values (a real
    ``envelope_id``, a non-empty ``permitted_scope``, etc.) turned this red; restoring it turned
    it green again, with the rest of the suite unaffected either way (confirming the earlier gap:
    that mutation left every OTHER test in this module green)."""
    assert_shipped_example_is_a_template(stem)


def test_custody_manifest_example_loads_successfully() -> None:
    """``custody.manifest.example.yaml`` is confirmed to be a genuinely loadable instance already
    (every leaf ``CustodyManifest.load`` requires carries a concrete illustrative value; only the
    optional ``expected_sha256`` pins are ``null``) — see
    ``example_integrity_registry.CUSTODY_MANIFEST_LOADER``'s own comment."""
    call_loader(CUSTODY_MANIFEST_LOADER, CONFIG_DIR / "custody.manifest.example.yaml")


def test_evidence_retention_example_loads_successfully() -> None:
    """``evidence_retention.example.yaml`` also loads successfully as-shipped — its own header
    comment states a per-class retention floor is legitimately, PERMANENTLY nullable, so there is
    no "still refuses" behavior to assert; see
    ``example_integrity_registry.EVIDENCE_RETENTION_LOADER``'s own comment for the full reasoning
    (and for why ``test_every_registered_example_has_value_leak_coverage`` caught this file
    missing a category before this test existed)."""
    call_loader(
        EVIDENCE_RETENTION_LOADER, CONFIG_DIR / "evidence_retention.example.yaml"
    )


def test_safety_activation_still_refuses_on_both_independent_readers() -> None:
    """``safety_activation.example.yaml`` has TWO independent readers (the A-0b defect this
    module exists because of — see this module's own docstring): both must still refuse to load
    the shipped, all-``null`` template."""
    from tos_runtime.safety.profile import SafetyProfileConfigError, _load_documents
    from tos_runtime.venue.activation import (
        ActivationMembersConfigError,
        load_activation_members,
    )

    example_path = CONFIG_DIR / "safety_activation.example.yaml"
    with pytest.raises(ActivationMembersConfigError):
        load_activation_members(example_path)
    with pytest.raises(SafetyProfileConfigError):
        _load_documents(
            CONFIG_DIR / "safety_envelope.example.yaml",
            CONFIG_DIR / "safety_profile.example.yaml",
            example_path,
        )


def test_risk_example_still_refuses_on_both_independent_readers() -> None:
    """``risk.example.yaml`` has TWO independent readers (this module's own docstring): both
    must still refuse to load the shipped, all-``null`` template."""
    from tos_runtime.compose._currentness_wiring import _load_action_flow_envelope
    from tos_runtime.risk.aggregate import (
        AggregateRiskConfigError,
        load_adverse_scenario_set,
        load_required_scenario_kinds,
    )

    example_path = CONFIG_DIR / "risk.example.yaml"
    with pytest.raises(AggregateRiskConfigError):
        load_adverse_scenario_set(example_path)
    with pytest.raises(AggregateRiskConfigError):
        load_required_scenario_kinds(example_path)
    with pytest.raises(AggregateRiskConfigError):
        _load_action_flow_envelope(example_path)
