"""Yolk 3 — ``closure_complete_or_restrictive`` both-ways canaries (§11; design #29 §5.3).

The seventeen §11 dimensions are checked **individually**: a dimension present in the model but
never read would be the WDR MAJOR-1 field-group defect. The ∅ closure is denied in both directions
(§0.5-2 / C2 — the ADR nowhere sanctions an explicitly-empty closure).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — SCI-EV-003 is
``EV-L1/2/3+Security``.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import TRIBOOL, clean_closure_manifest

_CLOSURE_DIMENSIONS = sorted(sci.DependencyClosureDigestSet.model_fields)


def test_clean_closure_passes() -> None:
    """(both-ways) The genuinely complete seventeen-dimension fixture passes."""
    assert sci.closure_complete_or_restrictive(clean_closure_manifest()) is True


def test_absent_manifest_denies() -> None:
    """(§5.3 item 1 ∅-seal) A ``None`` manifest denies."""
    assert sci.closure_complete_or_restrictive(None) is False


def test_empty_closure_denies() -> None:
    """(§5.3 item 1 / §0.5-2 C2) An ∅ closure denies — never a vacuous pass.

    §1 line 17: "Missing, stale, conflicting, ambiguous, **incompletely closed**, unapproved, or
    unverifiable supply-chain state grants zero eligibility for dependent new risk." The ADR
    sanctions no explicitly-empty closure, so ∅ is denial in **both** directions.
    """
    blanked = dict.fromkeys(_CLOSURE_DIMENSIONS)
    assert (
        sci.closure_complete_or_restrictive(clean_closure_manifest(**blanked)) is False
    )


def test_closure_dimension_anchor_is_seventeen() -> None:
    """(§4.9) The §11 closure anchor has exactly seventeen dimensions."""
    assert len(_CLOSURE_DIMENSIONS) == 17
    assert set(_CLOSURE_DIMENSIONS) <= set(
        sci.DependencyToolchainClosureManifest.model_fields
    )


@pytest.mark.parametrize("dimension", _CLOSURE_DIMENSIONS)
@pytest.mark.parametrize("bad", [None, "TBD", "latest"])
def test_every_closure_dimension_is_individually_load_bearing(
    dimension: str, bad: str | None
) -> None:
    """(§5.3 item 2 / SCI-INV-005) Each of the seventeen dimensions denies on its own."""
    assert (
        sci.closure_complete_or_restrictive(clean_closure_manifest(**{dimension: bad}))
        is False
    )


@pytest.mark.parametrize("bad", [None, "TBD", "latest"])
def test_resolution_policy_digest_is_load_bearing(bad: str | None) -> None:
    """(§5.3 item 2 / §11 line 287) The resolution policy is the exclusion-set source of truth."""
    assert (
        sci.closure_complete_or_restrictive(
            clean_closure_manifest(resolution_policy_digest=bad)
        )
        is False
    )


@pytest.mark.parametrize("bad", [None, "TBD", "latest"])
def test_correction_state_digest_is_load_bearing(bad: str | None) -> None:
    """(§5.3 item 2 / §11 line 289) "unresolved correction is restrictive"."""
    assert (
        sci.closure_complete_or_restrictive(
            clean_closure_manifest(correction_and_revocation_state_digest=bad)
        )
        is False
    )


@pytest.mark.parametrize(
    "field",
    [
        "transitive_closure_complete",
        "all_content_digests_verified",
        "all_sources_approved",
        "all_corrections_and_revocations_current",
    ],
)
@given(flag=TRIBOOL)
def test_completeness_flags_are_positive_polarity(
    field: str, flag: bool | None
) -> None:
    """(§5.3 item 3) Every completeness claim clears only on an explicit ``True``."""
    manifest = clean_closure_manifest(**{field: flag})
    assert sci.closure_complete_or_restrictive(manifest) is (flag is True)


@pytest.mark.parametrize(
    "field",
    [
        "floating_version_permitted",
        "undeclared_network_resolution_permitted",
        "runtime_dynamic_resolution_permitted",
    ],
)
@given(flag=TRIBOOL)
def test_permission_flags_are_negative_polarity(field: str, flag: bool | None) -> None:
    """(§5.3 item 4 / §11 line 289) Only an explicit ``False`` clears; ``None`` denies.

    These three are **policy permissions**, not observed states (design #29 §5.0 / M1) — reading
    them with ``is not True`` would let a ``None`` (unknown policy) pass as clear.
    """
    manifest = clean_closure_manifest(**{field: flag})
    assert sci.closure_complete_or_restrictive(manifest) is (flag is False)


def test_transitive_closure_complete_is_the_field_actually_read() -> None:
    """(M1) The template names it ``transitive_closure_complete``, not ``closure_complete``.

    ``closure_complete`` belongs to the SOURCE-REVISION-MANIFEST; reading the wrong one here would
    be a phantom field that silently never fires.
    """
    fields = set(sci.DependencyToolchainClosureManifest.model_fields)
    assert "transitive_closure_complete" in fields
    assert "closure_complete" not in fields
    assert "closure_complete" in set(sci.SourceRevisionManifest.model_fields)
