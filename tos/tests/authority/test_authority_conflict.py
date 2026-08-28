"""SA-EV-015 (substrate) — same-capability-id / different-bytes conflict + idempotency.

Because ``capability_id`` is orthogonal to ``canonical_digest`` (design §3.1,
``id != f(digest)``), a same-id / different-bytes capability pair is a Critical integrity
conflict (§18.3 forgery / replay) and a same-id / same-bytes pair is an idempotent
duplicate (§9.3 legitimate re-submission). The classifier is the promoted
``tos.canonical.classify_record_pair`` applied to capability pairs — REUSED, not
redefined.
"""

from __future__ import annotations

from hypothesis import given
from tos.authority import SafetyAuthorityCapability
from tos.canonical import RecordPairKind, classify_record_pair

from ._authority_strategies import REQUIRED_FIELD_TEXT, issue_capability


def _classify(a, b) -> RecordPairKind:
    """Classify two capabilities by (capability_id, canonical_digest)."""
    return classify_record_pair(
        a.capability_id, a.canonical_digest, b.capability_id, b.canonical_digest
    )


def test_all_kinds_reachable_on_capability_pairs() -> None:
    """NOT_COMPARABLE / IDEMPOTENT_DUP / CRITICAL_CONFLICT / DISTINCT all reachable."""
    a = issue_capability(capability_id="cap-1", issuer_identity="iss-1")
    dup = issue_capability(capability_id="cap-1", issuer_identity="iss-1")  # same bytes
    conflict = issue_capability(capability_id="cap-1", issuer_identity="iss-2")  # diff
    distinct = issue_capability(
        capability_id="cap-2", issuer_identity="iss-1"
    )  # diff id

    assert _classify(a, dup) is RecordPairKind.IDEMPOTENT_DUP
    assert _classify(a, conflict) is RecordPairKind.CRITICAL_CONFLICT
    assert _classify(a, distinct) is RecordPairKind.DISTINCT
    # A DRAFT capability (null digest) is not a ledger citizen => NOT_COMPARABLE.
    draft = SafetyAuthorityCapability(capability_id="cap-1")
    assert draft.canonical_digest is None
    assert _classify(a, draft) is RecordPairKind.NOT_COMPARABLE


def test_id_orthogonal_to_digest_keeps_conflict_reachable() -> None:
    """(regression lock) id != f(digest): same capability id + different bytes conflicts.

    If identity were derived from the digest, same-id would imply same-bytes and
    CRITICAL_CONFLICT (forgery / replay detection, §18.3) would be unreachable.
    """
    a = issue_capability(capability_id="cap-1", issuer_identity="iss-1")
    b = issue_capability(capability_id="cap-1", issuer_identity="iss-2")
    assert a.capability_id == b.capability_id
    assert a.canonical_digest != b.canonical_digest  # id did NOT track the digest
    assert _classify(a, b) is RecordPairKind.CRITICAL_CONFLICT


@given(env_a=REQUIRED_FIELD_TEXT, env_b=REQUIRED_FIELD_TEXT)
def test_conflict_iff_same_id_and_different_bytes(env_a: str, env_b: str) -> None:
    """Property: same-id conflict <=> canonical bytes differ (§4.5)."""
    a = issue_capability(capability_id="cap-1", environment_and_mode=env_a)
    b = issue_capability(capability_id="cap-1", environment_and_mode=env_b)
    kind = _classify(a, b)
    if a.canonical_digest == b.canonical_digest:
        assert kind is RecordPairKind.IDEMPOTENT_DUP
    else:
        assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_conflict_preserves_both_records() -> None:
    """A conflict contains + preserves both records; neither is merged / overwritten."""
    a = issue_capability(capability_id="cap-1", issuer_identity="iss-1")
    b = issue_capability(capability_id="cap-1", issuer_identity="iss-2")
    assert _classify(a, b) is RecordPairKind.CRITICAL_CONFLICT
    assert a.issuer_identity == "iss-1"
    assert b.issuer_identity == "iss-2"
    assert a is not b
