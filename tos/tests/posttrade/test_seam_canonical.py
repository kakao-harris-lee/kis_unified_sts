"""Seam: ``tos.posttrade`` <-> ``tos.canonical`` — the one primitive both forgery axes rest on.

``tos.canonical`` is a **core** dependency, not a sibling: this package imports it (design
#24 §0.3). The seam test therefore checks something different from the sibling seams — that
the ``classify_record_pair`` contract this package anchors on has not drifted:

* the measured **signature** (four positional arguments plus two keyword-only idempotency
  ids, ``canonical/record_pair.py:52``) still accepts the call
  :func:`~tos.posttrade.obligation_commit_idempotent` makes;
* all **five** ``RecordPairKind`` members are still the ones the §4.6 truth table maps, and
  the mapping is exhaustive over the live enum;
* each of the five kinds is reachable from a real pair of
  :class:`~tos.posttrade.EconomicObligationRecord` values, so the mapping is not merely
  well-typed but actually exercised end to end.

**Proposition identity (design #24 §0.4e).** ``classify_record_pair`` is a *shared primitive*
with **four** independent downstreams — iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY``
(authorization-token single-use), rcl ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command),
nontrade ``CorrectionReversalOutcome.IDEMPOTENT_REPLAY`` (economic-event application), and
this package's ``ObligationCommitOutcome.IDEMPOTENT_REPLAY`` (fill-to-obligation commit).
Structurally isomorphic, propositionally distinct; none imports another.

Test-only sibling imports are not runtime package edges (design #24 §7.1).
"""

from __future__ import annotations

import inspect

from tos.canonical import ArtifactStatus, RecordPairKind, classify_record_pair
from tos.posttrade import EconomicObligationRecord, ObligationCommitOutcome
from tos.posttrade.predicates import _RECORD_PAIR_OUTCOME

from ._posttrade_strategies import clean_obligation_record


def test_classify_record_pair_signature_is_four_positional_plus_two_keyword() -> None:
    """(§4.6 measured contract) The call shape this package makes is still the real one."""
    parameters = list(inspect.signature(classify_record_pair).parameters.values())
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    keyword_only = [
        parameter
        for parameter in parameters
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    ]
    assert [parameter.name for parameter in positional] == [
        "a_identity",
        "a_digest",
        "b_identity",
        "b_digest",
    ]
    assert [parameter.name for parameter in keyword_only] == [
        "a_idempotency_id",
        "b_idempotency_id",
    ]


def test_the_five_record_pair_kinds_are_still_the_five_mapped() -> None:
    """(§4.6 drift lock) A new canonical member would fail here, not fall through."""
    assert {member.name for member in RecordPairKind} == {
        "IDEMPOTENT_DUP",
        "CRITICAL_CONFLICT",
        "DIVERGENT_EMISSION",
        "DISTINCT",
        "NOT_COMPARABLE",
    }
    assert set(_RECORD_PAIR_OUTCOME) == set(RecordPairKind)


def test_every_kind_is_reachable_from_real_obligation_records() -> None:
    """(end to end) The five cells are exercised on genuine issued / draft artifacts."""
    genuine = clean_obligation_record(obligation_id="OBL-A", idempotency_key="IDEM-A")
    same_bytes = clean_obligation_record(
        obligation_id="OBL-A", idempotency_key="IDEM-A"
    )
    primary_forgery = clean_obligation_record(
        obligation_id="OBL-A", idempotency_key="IDEM-A", obligation_type="TAX_LEG"
    )
    key_forgery = clean_obligation_record(
        obligation_id="OBL-B", idempotency_key="IDEM-A", obligation_type="FEE_LEG"
    )
    unrelated = clean_obligation_record(
        obligation_id="OBL-C", idempotency_key="IDEM-C", obligation_type="OTHER_LEG"
    )
    draft = EconomicObligationRecord(
        obligation_id="OBL-A", status=ArtifactStatus.DRAFT, idempotency_key="IDEM-A"
    )

    def classify(first: EconomicObligationRecord, second: EconomicObligationRecord):
        return classify_record_pair(
            first.obligation_id,
            first.canonical_digest,
            second.obligation_id,
            second.canonical_digest,
            a_idempotency_id=first.idempotency_key,
            b_idempotency_id=second.idempotency_key,
        )

    reached = {
        classify(same_bytes, genuine),
        classify(primary_forgery, genuine),
        classify(key_forgery, genuine),
        classify(unrelated, genuine),
        classify(draft, genuine),
    }
    assert reached == set(RecordPairKind)


def test_the_two_forgery_axes_are_distinguished_by_the_primitive() -> None:
    """(§0.4f) ``id != f(digest)`` is what keeps the two axes separately detectable."""
    genuine = clean_obligation_record(obligation_id="OBL-A", idempotency_key="IDEM-A")
    primary_forgery = clean_obligation_record(
        obligation_id="OBL-A", idempotency_key="IDEM-A", obligation_type="TAX_LEG"
    )
    key_forgery = clean_obligation_record(
        obligation_id="OBL-B", idempotency_key="IDEM-A", obligation_type="FEE_LEG"
    )
    assert (
        classify_record_pair(
            primary_forgery.obligation_id,
            primary_forgery.canonical_digest,
            genuine.obligation_id,
            genuine.canonical_digest,
            a_idempotency_id=primary_forgery.idempotency_key,
            b_idempotency_id=genuine.idempotency_key,
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )
    assert (
        classify_record_pair(
            key_forgery.obligation_id,
            key_forgery.canonical_digest,
            genuine.obligation_id,
            genuine.canonical_digest,
            a_idempotency_id=key_forgery.idempotency_key,
            b_idempotency_id=genuine.idempotency_key,
        )
        is RecordPairKind.DIVERGENT_EMISSION
    )


def test_the_four_downstreams_are_different_types_on_different_axes() -> None:
    """(§0.4e phantom-edge block) Same token, four propositions, four types.

    Imported **in the test only**; none of the four packages imports another.
    """
    from tos.iap import ConsumptionOutcome
    from tos.nontrade import CorrectionReversalOutcome
    from tos.rcl import ApplyReason

    ours = ObligationCommitOutcome.IDEMPOTENT_REPLAY
    theirs = (
        ConsumptionOutcome.IDEMPOTENT_REPLAY,
        ApplyReason.IDEMPOTENT_REPLAY,
        CorrectionReversalOutcome.IDEMPOTENT_REPLAY,
    )
    assert len(theirs) == 3, "four independent downstreams: ours plus these three"
    for sibling_member in theirs:
        assert sibling_member.value == ours.value  # the token overlaps ...
        assert type(sibling_member) is not type(ours)  # ... the type never does
        assert sibling_member is not ours
