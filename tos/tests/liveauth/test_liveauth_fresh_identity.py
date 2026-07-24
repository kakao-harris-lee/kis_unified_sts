"""Fresh authorization identity + same-id/different-bytes conflict (§5.5, §4.6).

A re-arm's new authorization id must be present and not a reuse of any prior id. Because
``authorization_id`` is orthogonal to ``canonical_digest`` (id != f(digest)), a same-id /
different-bytes authorization is a detectable Critical conflict and a same-id / same-bytes
authorization is an idempotent duplicate. [REARM-EV-004 substrate]
"""

from __future__ import annotations

from hypothesis import given
from tos.canonical import RecordPairKind, classify_record_pair
from tos.liveauth import LiveAuthorization, fresh_authorization_identity

from ._liveauth_strategies import REQUIRED_FIELD_TEXT, issue_authorization


def test_concrete_new_id_with_empty_prior_is_fresh() -> None:
    """(guard fires True) The first authorization (empty prior set) is fresh."""
    assert fresh_authorization_identity("auth-1", frozenset()) is True


def test_new_id_not_in_prior_is_fresh() -> None:
    """A new id distinct from every prior id is fresh."""
    assert fresh_authorization_identity("auth-2", frozenset({"auth-1"})) is True


def test_reused_prior_id_is_not_fresh() -> None:
    """(canary) Reusing a prior authorization id is not fresh (§1 line 42 non-revival)."""
    assert (
        fresh_authorization_identity("auth-1", frozenset({"auth-1", "auth-0"})) is False
    )


def test_none_id_is_not_fresh() -> None:
    """(canary) A None new id fails closed."""
    assert fresh_authorization_identity(None, frozenset()) is False
    assert fresh_authorization_identity(None, frozenset({"auth-1"})) is False


def _classify(a: LiveAuthorization, b: LiveAuthorization) -> RecordPairKind:
    """Classify two authorizations by (authorization_id, canonical_digest)."""
    return classify_record_pair(
        a.authorization_id, a.canonical_digest, b.authorization_id, b.canonical_digest
    )


def test_all_kinds_reachable_on_authorization_pairs() -> None:
    """IDEMPOTENT_DUP / CRITICAL_CONFLICT / DISTINCT / NOT_COMPARABLE all reachable."""
    a = issue_authorization(authorization_id="auth-1", issuer_identity="iss-1")
    dup = issue_authorization(authorization_id="auth-1", issuer_identity="iss-1")
    conflict = issue_authorization(authorization_id="auth-1", issuer_identity="iss-2")
    distinct = issue_authorization(authorization_id="auth-2", issuer_identity="iss-1")

    assert _classify(a, dup) is RecordPairKind.IDEMPOTENT_DUP
    assert _classify(a, conflict) is RecordPairKind.CRITICAL_CONFLICT
    assert _classify(a, distinct) is RecordPairKind.DISTINCT
    draft = LiveAuthorization(authorization_id="auth-1")
    assert draft.canonical_digest is None
    assert _classify(a, draft) is RecordPairKind.NOT_COMPARABLE


def test_id_orthogonal_to_digest_keeps_conflict_reachable() -> None:
    """(regression lock) id != f(digest): same authorization id + different bytes conflicts.

    If identity were derived from the digest, same-id would imply same-bytes and the
    forgery / replay CRITICAL_CONFLICT (§8.3) would be unreachable.
    """
    a = issue_authorization(authorization_id="auth-1", issuer_identity="iss-1")
    b = issue_authorization(authorization_id="auth-1", issuer_identity="iss-2")
    assert a.authorization_id == b.authorization_id
    assert a.canonical_digest != b.canonical_digest
    assert _classify(a, b) is RecordPairKind.CRITICAL_CONFLICT


@given(iss_a=REQUIRED_FIELD_TEXT, iss_b=REQUIRED_FIELD_TEXT)
def test_conflict_iff_same_id_and_different_bytes(iss_a: str, iss_b: str) -> None:
    """Property: same-id conflict <=> canonical bytes differ (§4.6)."""
    a = issue_authorization(authorization_id="auth-1", issuer_identity=iss_a)
    b = issue_authorization(authorization_id="auth-1", issuer_identity=iss_b)
    kind = _classify(a, b)
    if a.canonical_digest == b.canonical_digest:
        assert kind is RecordPairKind.IDEMPOTENT_DUP
    else:
        assert kind is RecordPairKind.CRITICAL_CONFLICT
