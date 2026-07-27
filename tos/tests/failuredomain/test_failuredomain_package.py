"""Public-surface + module-layout regressions for ``tos.failuredomain`` (design #27 §2/§3.4/§5).

Asserts the package exports exactly the surface design #27 §3.4 promises — four coordinate enums +
the ``∅`` marker + the ``SafetyCellScope`` coordinate + the two document-level record shapes + the
all-false authority block + the sibling-token anchor + **exactly three** predicates — and nothing
else. Over- and under-export are both caught, because over-authoring is this package's declared
biggest hazard (design #27 §9.4-4) and under-export would silently drop a mandated coordinate.

Regime tag: structural substrate; closes no FD-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tos.failuredomain as fd

_FD_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "failuredomain"
)

#: The complete promised surface (design #27 §3.4) — nothing more, nothing less.
_EXPECTED_SURFACE: frozenset[str] = frozenset(
    {
        # base (re-exported core + the §2.2 all-false block)
        "AllFalseFailureDomainAuthority",
        "ArtifactIntegrityError",
        "FrozenModel",
        # vocabulary — 4 coordinate enums + the ∅ marker + the §6.2 token anchor
        "SIBLING_OWNER_TOKENS",
        "ExplicitlyAnalyzedEmpty",
        "FailureBehaviorKind",
        "FailureDomainKind",
        "IsolationClaimStatus",
        "IsolationKind",
        # state — the ADR §4.3 coordinate
        "SafetyCellScope",
        # records — the two document-level shapes + their authority block
        "FailureDomainAllocationEntry",
        "FailureDomainAuthorityEffect",
        "IsolationClaim",
        # predicates — exactly three (design #27 §4)
        "decision_sole_sourced_from_volatile",
        "new_risk_blocked_by_unproven_isolation",
        "unproven_isolation_is_common_mode",
    }
)

#: The standard six-module layout every sibling package uses.
_EXPECTED_MODULES: frozenset[str] = frozenset(
    {"__init__", "_base", "predicates", "records", "state", "vocabulary"}
)


def test_the_exported_surface_is_exactly_the_promised_one() -> None:
    """(§3.4) ``__all__`` == the design's surface — over-export and under-export both caught."""
    assert set(fd.__all__) == _EXPECTED_SURFACE
    assert len(fd.__all__) == len(_EXPECTED_SURFACE)
    assert len(set(fd.__all__)) == len(fd.__all__)  # no duplicate entry


@pytest.mark.parametrize("name", sorted(_EXPECTED_SURFACE))
def test_every_promised_export_is_importable(name: str) -> None:
    """(§3.4) Each promised symbol actually resolves on the package."""
    assert hasattr(fd, name), name


def test_no_public_attribute_escapes_all() -> None:
    """(§3.4) Nothing public leaks past ``__all__`` — no accidental surface growth.

    Submodule names are excluded: they become attributes of the package as a side effect of the
    ``from tos.failuredomain.x import ...`` statements in ``__init__``. So is ``annotations``, the
    ``__future__`` feature object every module in the repo carries.
    """
    leaked = sorted(
        name
        for name in dir(fd)
        if not name.startswith("_")
        and name not in _EXPECTED_SURFACE
        and name not in _EXPECTED_MODULES
        and name != "annotations"
    )
    assert leaked == [], f"public surface grew beyond __all__: {leaked}"


def test_the_module_layout_is_the_standard_six() -> None:
    """(§0.4c) The package uses the sibling-standard six-module layout."""
    modules = {path.stem for path in _FD_SRC.glob("*.py")}
    assert modules == _EXPECTED_MODULES


def test_surface_counts_are_exactly_as_designed() -> None:
    """(§3.4 counts) 4 coordinate enums + 1 marker + 1 coordinate record + 2 shapes + 3 predicates."""
    coordinate_enums = {
        "FailureDomainKind",
        "FailureBehaviorKind",
        "IsolationClaimStatus",
        "IsolationKind",
    }
    record_shapes = {"FailureDomainAllocationEntry", "IsolationClaim"}
    predicates = {
        "decision_sole_sourced_from_volatile",
        "new_risk_blocked_by_unproven_isolation",
        "unproven_isolation_is_common_mode",
    }
    assert len(coordinate_enums) == 4
    assert len(record_shapes) == 2
    assert len(predicates) == 3
    assert coordinate_enums | record_shapes | predicates <= _EXPECTED_SURFACE
    # the member counts the design fixes verbatim (22 / 9 / 3 / 3).
    assert (
        len(fd.FailureDomainKind),
        len(fd.FailureBehaviorKind),
        len(fd.IsolationClaimStatus),
        len(fd.IsolationKind),
    ) == (22, 9, 3, 3)


def test_the_sibling_token_anchor_is_exported_and_non_trivial() -> None:
    """(§6.2) The drift-lock anchor ships with the package, not only with the tests."""
    assert isinstance(fd.SIBLING_OWNER_TOKENS, frozenset)
    assert len(fd.SIBLING_OWNER_TOKENS) == 42


def test_no_runtime_matrix_container_is_exported() -> None:
    """(§0.2) The matrix is a document-level *row shape*; there is no runtime matrix object.

    ADR §5 allocation, common-mode analysis, enforcement wiring and containment measurement all
    belong to the approved deployment profile (ADR §22 gate 1) and the runtime — not here.
    """
    for forbidden in (
        "FailureDomainAllocationMatrix",
        "AllocationMatrix",
        "MatrixRegistry",
        "allocation_matrix",
        "build_matrix",
        "validate_matrix",
    ):
        assert not hasattr(fd, forbidden)
