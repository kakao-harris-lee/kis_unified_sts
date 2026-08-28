"""MANDATED test-only seam cross-check: afg <-> brokercap (design #16 §3.4(d), M7).

design #16 **M7** promoted brokercap from "coordinate-dependent" to a **dedicated
produced-bool slot**: two brokercap predicates produce exactly the booleans afg's
predicates consume by injection —

* ``same_order_retry_allowed`` (``predicates.py:377``) -> afg ``no_blind_retry``'s
  ``idempotency_proven`` argument (capability axis ``SUBMISSION_IDEMPOTENCY``,
  ``vocabulary.py:71``);
* ``rate_admission_ok`` (``predicates.py:437``) -> afg's shared-limit / admission gating
  (capability axis ``RATE_LIMITS``).

afg does **not** import ``tos.brokercap`` at runtime (the §7.1 allowlist closure test
asserts its absence) and does **not** judge broker capability: ADR-002-022 §21 line 447
"Broker documentation ... are evidence inputs, not permission", and brokercap's own
``_base.py:19`` records that a capability "creates no action-flow [capacity]". This file
imports both as a **test** to lock the produced-bool polarity and the fail-closed parity.

Broker-agnostic: no concrete broker is named anywhere (project memory
``tos-spec-broker-agnostic``); the profile below is a structural fixture, and the per-broker
rate / burst / queue **numbers** are a Broker Capability Profile INSTANCE, not a
Verification-Profile key (design #16 §8.1, M4).

Causal isolation: each polarity assertion fixes a valid baseline and flips one input.

A test-only cross-import is **not** a runtime package edge (design #16 §3.4(d)/§7.1).
"""

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


# ---------------------------------------------------------------------------
# same_order_retry_allowed -> no_blind_retry (idempotency produced-bool slot)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# rate_admission_ok -> shared-limit conservatism (rate produced-bool slot)
# ---------------------------------------------------------------------------


def test_rate_admission_ok_polarity() -> None:
    """(seam §17.2:926-933) Only ordinary-below-ceiling + reserved headroom produces ``True``."""
    assert rate_admission_ok(True, True) is True
    for below, reserved in ((False, True), (True, False), (None, True), (True, None)):
        assert rate_admission_ok(below, reserved) is False


def test_rate_evidence_feeds_shared_limit_conservatism_without_creating_permission() -> (
    None
):
    """(§21:447) Broker rate evidence is an *input*: it never narrows the conservative scope.

    ``rate_admission_ok`` produces the independence-shaped bool afg injects; when it is
    ``False`` / ``None`` the shared limit expands to the smallest containing scope, and
    when the broker's documented scope is not verified-complete the limit widens to the
    largest credible containing scope regardless of how favourable the rate evidence is.
    """
    favourable = rate_admission_ok(True, True)
    assert favourable is True
    # Documented scope verified + favourable evidence => the narrow claim may stand.
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE,
            favourable,
        )
        is ActionFlowScopeKind.ACCOUNT
    )
    # Causal isolation: flip ONLY the documented-scope status => widen to the largest.
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.INCOMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE,
            favourable,
        )
        is ActionFlowScopeKind.GLOBAL
    )
    # Causal isolation: flip ONLY the rate evidence => expand to the smallest containing.
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
