"""proof_admissible multi fail-closed + structural completeness (design #23 §6.5/§6.6).

``proof_admissible`` (CUR-EV-004 substrate) admits **only** on the full positive conjunction:
structurally complete AND ``result is CURRENT`` AND ``single_use_consumed is False`` AND
``is_expired is False`` AND ``local_latch_clear is True``. The v1.1 MAJOR-3 seal is central: the
single-use / expiry gates require **explicit ``is False``** — a ``None`` (unknown-consumed /
unknown-expiry) must NOT be admitted (``is not True`` would fail open — the #22 MAJOR-2 re-seal).

Regime tag: predicate substrate only; CUR-EV-004 NOT_IMPLEMENTED (≥ EV-L2 component-fault +
+Security; per-send transaction / wall-clock age are runtime); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.cur import (
    ProofResult,
    proof_admissible,
    proof_structurally_complete,
)

from ._cur_strategies import clean_coordinates, clean_proof


def test_clean_proof_is_admissible() -> None:
    """(§6.6 both-ways) A genuinely admissible proof passes."""
    assert proof_admissible(clean_proof()) is True


def test_none_proof_is_inadmissible() -> None:
    """(§6.6) A None proof ⇒ inadmissible."""
    assert proof_admissible(None) is False


def test_non_current_result_is_inadmissible() -> None:
    """(§6.6 / §12 "Only CURRENT") RESTRICTED / UNKNOWN / None result ⇒ inadmissible."""
    assert proof_admissible(clean_proof(result=ProofResult.RESTRICTED)) is False
    assert proof_admissible(clean_proof(result=ProofResult.UNKNOWN)) is False
    assert proof_admissible(clean_proof(result=None)) is False


def test_consumed_proof_is_inadmissible_including_none() -> None:
    """(§6.6 v1.1 MAJOR-3) single_use_consumed must be explicit False — True AND None both deny."""
    assert proof_admissible(clean_proof(single_use_consumed=True)) is False
    # the #22 MAJOR-2 re-seal: a None (unknown-consumed) is NOT admitted.
    assert proof_admissible(clean_proof(single_use_consumed=None)) is False
    assert proof_admissible(clean_proof(single_use_consumed=False)) is True


def test_expired_proof_is_inadmissible_including_none() -> None:
    """(§6.6 / §6.10) is_expired must be explicit False — True AND None both deny."""
    assert proof_admissible(clean_proof(is_expired=True)) is False
    assert proof_admissible(clean_proof(is_expired=None)) is False
    assert proof_admissible(clean_proof(is_expired=False)) is True


def test_latch_not_clear_is_inadmissible_including_none() -> None:
    """(§6.6 / §5.7) local_latch_clear must be positively True — False AND None both deny."""
    assert (
        proof_admissible(
            clean_proof(coordinates=clean_coordinates(local_latch_clear=False))
        )
        is False
    )
    assert (
        proof_admissible(
            clean_proof(coordinates=clean_coordinates(local_latch_clear=None))
        )
        is False
    )
    assert (
        proof_admissible(
            clean_proof(coordinates=clean_coordinates(local_latch_clear=True))
        )
        is True
    )


def test_structurally_incomplete_proof_is_inadmissible() -> None:
    """(§6.5/§6.6) A structurally incomplete proof (∅ bound generations) ⇒ inadmissible."""
    assert proof_admissible(clean_proof(bound_generations=())) is False


def test_proof_structurally_complete_both_ways() -> None:
    """(§6.5) A complete proof passes; None / ∅ bound generations fail."""
    assert proof_structurally_complete(clean_proof()) is True
    assert proof_structurally_complete(None) is False
    assert proof_structurally_complete(clean_proof(bound_generations=())) is False
