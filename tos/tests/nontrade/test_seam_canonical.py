"""MANDATED seam cross-check: nontrade <-> canonical ``classify_record_pair`` (§3.4(d)).

``tos.canonical`` is one of this package's only two **runtime** imports, so this file is not
a firewall exception — it is the *behavioural* lock on the primitive the correction
idempotency is anchored to. Design #21 §0.4e records the decisive judgment: NT-EV-010's
proposition is **economic-event re-application harmlessness**, which is a *different*
proposition from iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (authorization-token
single-use consumption) and rcl ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command). All
three are independent downstreams of this one primitive and none imports another — the
phantom edge is blocked at the source.

This file drives all **five** ``RecordPairKind`` members live (never from a table of
remembered values) and asserts that the nontrade mapping folds each one the way the
measured canonical semantics demand.
"""

from __future__ import annotations

import pytest
from tos.canonical import RecordPairKind, classify_record_pair
from tos.nontrade import CorrectionReversalOutcome, correction_reversal_idempotent
from tos.nontrade.predicates import _RECORD_PAIR_OUTCOME

from ._nontrade_strategies import issue_correction

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


# ---------------------------------------------------------------------------
# The five canonical members, driven live
# ---------------------------------------------------------------------------


def test_all_five_record_pair_kinds_are_reachable_from_the_real_classifier() -> None:
    """(§7 seam) Each kind is produced by an actual call, not asserted from memory."""
    produced = {
        classify_record_pair(
            "id-1", _DIGEST_A, "id-1", _DIGEST_A
        ): "same id, same bytes",
        classify_record_pair(
            "id-1", _DIGEST_A, "id-1", _DIGEST_B
        ): "same id, diff bytes",
        classify_record_pair(
            "id-1",
            _DIGEST_A,
            "id-2",
            _DIGEST_B,
            a_idempotency_id="k",
            b_idempotency_id="k",
        ): "same key, diff bytes",
        classify_record_pair(
            "id-1",
            _DIGEST_A,
            "id-2",
            _DIGEST_B,
            a_idempotency_id="k1",
            b_idempotency_id="k2",
        ): "no shared axis",
        classify_record_pair("id-1", None, "id-2", _DIGEST_B): "pre-issuance digest",
    }
    assert set(produced) == set(
        RecordPairKind
    ), f"the seam did not exercise every member: {produced}"


@pytest.mark.parametrize("kind", list(RecordPairKind))
def test_every_canonical_kind_has_a_nontrade_folding(kind: RecordPairKind) -> None:
    """(C2) The mapping is exhaustive — a new canonical member breaks the build, loudly."""
    assert kind in _RECORD_PAIR_OUTCOME
    assert _RECORD_PAIR_OUTCOME[kind] in set(CorrectionReversalOutcome)


def test_the_measured_semantics_match_the_contract_wording() -> None:
    """(§4.6) The two forgery axes are measured, not assumed.

    ``CRITICAL_CONFLICT`` is the **primary-id** axis and ``DIVERGENT_EMISSION`` is the
    **idempotency-key** axis. The v1.0 contract had them the other way round, so this is
    the regression that pins the direction against the live classifier.
    """
    assert (
        classify_record_pair("id-1", _DIGEST_A, "id-1", _DIGEST_B)
        is RecordPairKind.CRITICAL_CONFLICT
    )
    assert (
        classify_record_pair(
            "id-1",
            _DIGEST_A,
            "id-2",
            _DIGEST_B,
            a_idempotency_id="k",
            b_idempotency_id="k",
        )
        is RecordPairKind.DIVERGENT_EMISSION
    )
    # ...and the primary axis wins when both are shared: a same-id pair never degrades to
    # the idempotency branch.
    assert (
        classify_record_pair(
            "id-1",
            _DIGEST_A,
            "id-1",
            _DIGEST_B,
            a_idempotency_id="k",
            b_idempotency_id="k",
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_the_signature_is_four_positional_plus_two_keyword() -> None:
    """(§4.6) The measured calling convention — a positional idempotency id would misbind.

    Passing the idempotency ids positionally is a ``TypeError``, so a future refactor that
    reorders the call cannot silently swap the digest and the key.
    """
    with pytest.raises(TypeError):
        classify_record_pair("id-1", _DIGEST_A, "id-2", _DIGEST_B, "k", "k")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# The nontrade predicate over the live classifier
# ---------------------------------------------------------------------------


def test_the_nontrade_predicate_folds_the_live_classification() -> None:
    """(§5.3) Real records through the real classifier, into the nontrade outcome."""
    first = issue_correction()
    same_bytes = issue_correction()
    forged_same_id = issue_correction(correction_kind="REVERSAL")
    same_key_other_id = issue_correction(
        correction_id="nt-corr-b", correction_kind="REVERSAL"
    )

    for prior, expected_kind, expected_outcome in (
        (
            same_bytes,
            RecordPairKind.IDEMPOTENT_DUP,
            CorrectionReversalOutcome.IDEMPOTENT_REPLAY,
        ),
        (
            forged_same_id,
            RecordPairKind.CRITICAL_CONFLICT,
            CorrectionReversalOutcome.REJECTED_CONFLICT,
        ),
        (
            same_key_other_id,
            RecordPairKind.DIVERGENT_EMISSION,
            CorrectionReversalOutcome.REJECTED_CONFLICT,
        ),
    ):
        kind = classify_record_pair(
            first.correction_id,
            first.canonical_digest,
            prior.correction_id,
            prior.canonical_digest,
            a_idempotency_id=first.idempotency_key,
            b_idempotency_id=prior.idempotency_key,
        )
        assert kind is expected_kind
        assert (
            correction_reversal_idempotent(first, prior, True) is expected_outcome
        ), f"{kind} folded incorrectly"


def test_causal_isolation_only_the_classification_moves_the_outcome() -> None:
    """(seam polarity) Flip exactly one input and both sides flip together."""
    first = issue_correction()
    assert (
        correction_reversal_idempotent(first, issue_correction(), True)
        is CorrectionReversalOutcome.IDEMPOTENT_REPLAY
    )
    # a single covered-byte change on the prior — nothing else — flips both sides
    forged = issue_correction(correction_kind="REVERSAL")
    assert forged.correction_id == first.correction_id
    assert forged.canonical_digest != first.canonical_digest
    assert (
        correction_reversal_idempotent(first, forged, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )


def test_the_no_last_write_wins_property_survives_the_fold() -> None:
    """(``record_pair.py:68``) Contain both — the fold never picks a winner.

    A merge / last-write-wins implementation would have produced a *pass* for one of the
    two orderings; both orderings reject.
    """
    first = issue_correction()
    forged = issue_correction(correction_kind="REVERSAL")
    assert (
        correction_reversal_idempotent(first, forged, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )
    assert (
        correction_reversal_idempotent(forged, first, True)
        is CorrectionReversalOutcome.REJECTED_CONFLICT
    )


def test_nontrade_does_not_re_author_the_classifier() -> None:
    """(§0.2/§3.5) The primitive is consumed, never reimplemented."""
    from tos import nontrade as nontrade_pkg

    for forbidden in ("classify_record_pair", "RecordPairKind"):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is re-exported from nontrade — it is canonical's, and "
            "re-exporting it would invite a local reimplementation"
        )
