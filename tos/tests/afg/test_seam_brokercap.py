"""MANDATED test-only seam cross-check: afg <-> brokercap (design #16 §3.4(d), M7)."""

from __future__ import annotations

from tos.afg import (
    ActionFlowResult,
    ActionFlowScopeKind,
    DocumentedScopeStatus,
    no_blind_retry,
    shared_limit_conservative,
)
from tos.brokercap import (
    BrokerCapabilityProfile,
    CapabilityDeclaration,
    CapabilityDimension,
    CapabilityStatus,
    rate_admission_ok,
    same_order_retry_allowed,
)

_CREDIBLE = frozenset(
    {
        ActionFlowScopeKind.GLOBAL,
        ActionFlowScopeKind.BROKER,
        ActionFlowScopeKind.ACCOUNT,
    }
)


def _profile(status: CapabilityStatus) -> BrokerCapabilityProfile:
    """A structural, broker-agnostic profile declaring one idempotency status."""
    return BrokerCapabilityProfile(
        declarations=(
            CapabilityDeclaration(
                dimension=CapabilityDimension.SUBMISSION_IDEMPOTENCY,
                status=status,
            ),
        )
    )


def _retry(idempotency_proven: bool | None) -> bool:
    return no_blind_retry(
        "SEND_FAILED_PROVEN",
        "NONE_OBSERVED",
        idempotency_proven,
        5,
        complete_evidence_capability_coverage_authority=True,
        blind_failover_attempted=False,
    )


def test_verified_idempotency_plus_identity_window_proof_permits_retry() -> None:
    """(seam + §12.5:652) VERIFIED idempotency + identity/window proof => both sides permit."""
    produced = same_order_retry_allowed(
        _profile(CapabilityStatus.VERIFIED),
        idempotency_proven_for_identity_and_window=True,
    )
    assert produced is True
    assert _retry(produced) is True


def test_unverified_idempotency_denies_on_both_sides() -> None:
    """(seam - §12.4:640) Any non-VERIFIED status produces ``False``; afg then refuses."""
    for status in (
        CapabilityStatus.DOCUMENTED_NOT_VERIFIED,
        CapabilityStatus.CONTRADICTORY,
        CapabilityStatus.UNKNOWN,
        CapabilityStatus.UNSUPPORTED,
        CapabilityStatus.EXPIRED,
    ):
        produced = same_order_retry_allowed(
            _profile(status), idempotency_proven_for_identity_and_window=True
        )
        assert produced is False, status
        assert _retry(produced) is False


def test_absent_profile_produces_false_and_afg_refuses() -> None:
    """(fail-closed parity) A ``None`` profile => ``False`` => no retry."""
    produced = same_order_retry_allowed(
        None, idempotency_proven_for_identity_and_window=True
    )
    assert produced is False
    assert _retry(produced) is False


def test_missing_identity_window_proof_produces_false() -> None:
    """(causal isolation) Only the identity/window proof changes; both sides flip together."""
    verified = _profile(CapabilityStatus.VERIFIED)
    assert (
        same_order_retry_allowed(
            verified, idempotency_proven_for_identity_and_window=True
        )
        is True
    )
    for value in (False, None):
        produced = same_order_retry_allowed(
            verified, idempotency_proven_for_identity_and_window=value
        )
        assert produced is False
        assert _retry(produced) is False


def test_afg_normalizes_a_none_idempotency_flag_closed() -> None:
    """(truthy seal) afg's ``is not True`` normalization refuses a ``None`` idempotency."""
    assert _retry(None) is False


def test_rate_admission_ok_polarity() -> None:
    """(seam §17.2:926-933) Only ordinary-below-ceiling + reserved headroom produces ``True``."""
    assert rate_admission_ok(True, True) is True
    for below, reserved in ((False, True), (True, False), (None, True), (True, None)):
        assert rate_admission_ok(below, reserved) is False


def test_rate_evidence_feeds_shared_limit_conservatism_without_creating_permission() -> (
    None
):
    """(§21:447) Broker rate evidence is an *input*: it never narrows the conservative scope."""
    favourable = rate_admission_ok(True, True)
    assert favourable is True
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE,
            favourable,
        )
        is ActionFlowScopeKind.ACCOUNT
    )
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.INCOMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE,
            favourable,
        )
        is ActionFlowScopeKind.GLOBAL
    )
    unfavourable = rate_admission_ok(False, True)
    assert unfavourable is False
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            ActionFlowScopeKind.GLOBAL,
            _CREDIBLE,
            unfavourable,
        )
        is ActionFlowScopeKind.ACCOUNT
    )


def test_no_broker_is_named_in_the_afg_surface() -> None:
    """(broker-agnostic) The afg vocabulary names capability *axes*, never a broker."""
    from tos.afg import ActionFlowDimensionKind
    from tos.afg import ActionFlowScopeKind as Scope

    tokens = {kind.value for kind in ActionFlowDimensionKind} | {
        scope.value for scope in Scope
    }
    for banned in ("KIS", "IBKR", "BINANCE", "UPBIT", "ALPACA"):
        assert not any(banned in token for token in tokens)
    assert ActionFlowResult.UNKNOWN is ActionFlowResult.UNKNOWN
