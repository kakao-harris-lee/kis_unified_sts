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
    assert_shipped_example_still_refuses,
    assert_touchpoints_match,
    call_loader,
)
from .example_integrity_registry import (
    CUSTODY_MANIFEST_LOADER,
    EXAMPLE_LOADERS,
    EXAMPLE_REQUIRED_PATHS,
    EXAMPLE_TOUCHPOINTS,
)


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
    deliberately excluded here (multi-reader, multi-path-constructor, or optional-file configs
    each get their own targeted test below)."""
    assert_shipped_example_still_refuses(stem, EXAMPLE_LOADERS[stem])


def test_custody_manifest_example_loads_successfully() -> None:
    """``custody.manifest.example.yaml`` is the one shipped example confirmed to be a genuinely
    loadable instance already (every leaf ``CustodyManifest.load`` requires carries a concrete
    illustrative value; only the optional ``expected_sha256`` pins are ``null``) — see
    ``example_integrity_registry.CUSTODY_MANIFEST_LOADER``'s own comment."""
    call_loader(CUSTODY_MANIFEST_LOADER, CONFIG_DIR / "custody.manifest.example.yaml")


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
