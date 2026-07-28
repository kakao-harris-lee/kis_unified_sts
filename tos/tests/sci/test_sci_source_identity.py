"""Yolk 1 — ``source_identity_exact_and_reviewed`` both-ways canaries (§9/§15 step 2; design #29 §5.1).

Each AND clause is fired **individually** (a guard that never fires is not a guard) and the clean
fixture is shown to pass genuinely (a predicate that denies everything is not a predicate).

Regime tag: release-admission predicate/model substrate only; **closes no SCI-EV** — SCI-EV-001 is
``EV-L1/3+Security`` and the real effective-principal resistance is hag plus +Security.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given

from ._sci_strategies import TRIBOOL, clean_source_manifest

_IDENTITY_DIGESTS = (
    "source_revision_digest",
    "source_tree_digest",
    "source_history_head_digest",
)


def test_clean_source_manifest_passes() -> None:
    """(both-ways) The genuinely complete fixture passes — the predicate is not vacuously False."""
    assert sci.source_identity_exact_and_reviewed(clean_source_manifest()) is True


def test_absent_manifest_denies() -> None:
    """(§5.1 item 1 ∅-seal) A ``None`` manifest denies."""
    assert sci.source_identity_exact_and_reviewed(None) is False


@pytest.mark.parametrize("field", _IDENTITY_DIGESTS)
@pytest.mark.parametrize("bad", [None, "TBD", "latest", "HEAD", "repo/path:tag", "   "])
def test_non_exact_identity_denies(field: str, bad: str | None) -> None:
    """(§5.1 item 2 / SCI-INV-002 line 159) Absent, placeholder, or mutable identity denies.

    This is the NEW-3 regression: an earlier draft described the mutable-name check without wiring
    it, so ``source_revision_digest="latest"`` would have passed.
    """
    assert (
        sci.source_identity_exact_and_reviewed(clean_source_manifest(**{field: bad}))
        is False
    )


def test_repository_identity_is_not_an_identity_gate() -> None:
    """(§1 line 19) A mutable repository *name* does not by itself deny — it is not identity.

    §1 line 19: "A branch, tag, package name, registry path, service label, mutable image tag,
    ``latest``, local cache, successful build, passing scan, or historical signature is not artifact
    identity." The manifest may carry a human-readable repository name; the three digests carry
    identity. Gating on the name would be the *wrong* proposition.
    """
    assert (
        sci.source_identity_exact_and_reviewed(
            clean_source_manifest(repository_identity="main")
        )
        is True
    )


@pytest.mark.parametrize(
    "verdict",
    [sci.IndependenceResult.COMMON_MODE, sci.IndependenceResult.UNKNOWN, None],
)
def test_unproven_independence_denies(verdict: sci.IndependenceResult | None) -> None:
    """(§5.1 item 3 / §9 line 267) COMMON_MODE, UNKNOWN, and absent are all restrictive.

    The reviewer-set digest is cleared alongside because the §2.3 coexistence seal only permits an
    ``INDEPENDENT`` claim when the reviewer set is present.
    """
    manifest = clean_source_manifest(
        effective_principal_independence_result=verdict,
        reviewer_effective_principal_set_digest="d-reviewer-set",
    )
    assert sci.source_identity_exact_and_reviewed(manifest) is False


@given(flag=TRIBOOL)
def test_history_rewrite_is_negative_polarity(flag: bool | None) -> None:
    """(§5.1 item 4 / §9 line 269) Only an explicit ``False`` clears; ``None`` and ``True`` deny."""
    manifest = clean_source_manifest(history_rewrite_detected=flag)
    assert sci.source_identity_exact_and_reviewed(manifest) is (flag is False)


@given(flag=TRIBOOL)
def test_review_current_is_positive_polarity(flag: bool | None) -> None:
    """(§5.1 item 4) Only an explicit ``True`` clears ``review_current``."""
    manifest = clean_source_manifest(review_current=flag)
    assert sci.source_identity_exact_and_reviewed(manifest) is (flag is True)


@pytest.mark.parametrize("bad", [None, "TBD", "latest"])
def test_missing_continuity_proof_denies(bad: str | None) -> None:
    """(§5.1 item 4 / §9 line 269) The history-continuity proof digest is load-bearing."""
    manifest = clean_source_manifest(source_history_continuity_proof_digest=bad)
    assert sci.source_identity_exact_and_reviewed(manifest) is False


@given(flag=TRIBOOL)
def test_closure_complete_is_positive_polarity(flag: bool | None) -> None:
    """(§5.1 item 5 / SCI-INV-003) Only an explicit ``True`` clears the source closure."""
    manifest = clean_source_manifest(closure_complete=flag)
    assert sci.source_identity_exact_and_reviewed(manifest) is (flag is True)


@pytest.mark.parametrize(
    "digest", sorted(sci.SourceRevisionManifest.SOURCE_CLOSURE_DIGESTS)
)
@pytest.mark.parametrize("bad", [None, "TBD", "latest"])
def test_every_source_closure_digest_is_individually_load_bearing(
    digest: str, bad: str | None
) -> None:
    """(§5.1 item 5 / §9 line 265) Each of the eight closure digests denies on its own.

    SCI-INV-003 line 163: "Unknown or omitted input is restrictive." A field-group that is present
    in the model but never read would be exactly the WDR MAJOR-1 defect.
    """
    manifest = clean_source_manifest(**{digest: bad})
    assert sci.source_identity_exact_and_reviewed(manifest) is False


def test_source_closure_anchor_has_eight_dimensions() -> None:
    """(§4 / §9 line 265) The closure anchor is the eight template digests, no more, no less."""
    assert len(sci.SourceRevisionManifest.SOURCE_CLOSURE_DIGESTS) == 8
    assert set(sci.SourceRevisionManifest.SOURCE_CLOSURE_DIGESTS) <= set(
        sci.SourceRevisionManifest.model_fields
    )
