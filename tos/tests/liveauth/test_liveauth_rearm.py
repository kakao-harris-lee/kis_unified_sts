"""Re-arm consumption + drift regression + no-automatic-rearm (§6.4; REARM-AC-002/003).

Quorum path directly consumes ``rearm_gate(...).armable`` (14 prerequisites + strict SoD);
the SAFE-053 variant path re-expresses the 13 environmental prerequisites locally, kept in
lock-step with ``authority._REARM_PREREQUISITES`` by an item-for-item **drift regression
test** (M1). Each conjunct (environment, dual control, fresh identity, control-plane
verifiability) is load-bearing; no recovery / timeout / restart flag can re-arm; and the
outcome is non-authorizing (authority_effect all-false). [REARM-EV-002/003 substrate]
"""

from __future__ import annotations

import pytest
from tos.authority import RearmChecklist
from tos.authority.predicates import _REARM_PREREQUISITES
from tos.liveauth import (
    no_automatic_rearm,
    rearm_admissible,
)
from tos.liveauth.predicates import (
    _SOD_PREREQUISITE,
    _VARIANT_ENVIRONMENTAL_PREREQUISITES,
)

from ._liveauth_strategies import (
    armable_checklist,
    quorum_attestation,
    solo_variant_attestation,
    variant_checklist,
)

_FRESH = "new-1"
_PRIOR = frozenset({"old-1"})


# ---------------------------------------------------------------------------
# Drift regression (M1) — the safety anchor
# ---------------------------------------------------------------------------


def test_variant_prerequisites_match_authority_minus_sod() -> None:
    """(drift regression, M1) The variant list == authority's 14 minus the SoD element.

    Silent divergence between the liveauth-local re-expression and
    ``authority._REARM_PREREQUISITES`` is exactly the safety gap this test closes.
    """
    expected = tuple(p for p in _REARM_PREREQUISITES if p != _SOD_PREREQUISITE)
    assert expected == _VARIANT_ENVIRONMENTAL_PREREQUISITES


def test_sod_prerequisite_is_the_single_excluded_item() -> None:
    """(drift regression) The SoD element is in authority's list but excluded from variant."""
    assert _SOD_PREREQUISITE in _REARM_PREREQUISITES
    assert _SOD_PREREQUISITE not in _VARIANT_ENVIRONMENTAL_PREREQUISITES
    assert len(_VARIANT_ENVIRONMENTAL_PREREQUISITES) == len(_REARM_PREREQUISITES) - 1
    assert len(_VARIANT_ENVIRONMENTAL_PREREQUISITES) == 13


# ---------------------------------------------------------------------------
# Quorum path — direct rearm_gate consumption
# ---------------------------------------------------------------------------


def test_quorum_rearm_admissible() -> None:
    """(guard fires True) A complete quorum re-arm is admissible."""
    outcome = rearm_admissible(
        armable_checklist(), quorum_attestation(), _FRESH, _PRIOR, True
    )
    assert outcome.admissible is True


@pytest.mark.parametrize("prerequisite", _REARM_PREREQUISITES)
def test_quorum_all_but_one_prerequisite_blocks(prerequisite: str) -> None:
    """(canary, all-but-one) Dropping any of the 14 quorum prerequisites blocks re-arm."""
    outcome = rearm_admissible(
        armable_checklist(**{prerequisite: False}),
        quorum_attestation(),
        _FRESH,
        _PRIOR,
        True,
    )
    assert outcome.admissible is False


def test_quorum_same_principal_blocks() -> None:
    """(canary strict SoD) The quorum path fails when the same principal both enlarges + arms."""
    checklist = armable_checklist(
        limit_enlarger_principal="same", armer_principal="same"
    )
    attestation = quorum_attestation(
        armer_principal="same", limit_change_approver_principal="same"
    )
    outcome = rearm_admissible(checklist, attestation, _FRESH, _PRIOR, True)
    assert outcome.admissible is False


# ---------------------------------------------------------------------------
# Variant path — local re-expression
# ---------------------------------------------------------------------------


def test_variant_rearm_admissible() -> None:
    """(guard fires True) A complete SAFE-053 solo-variant re-arm is admissible."""
    outcome = rearm_admissible(
        variant_checklist(), solo_variant_attestation(), _FRESH, _PRIOR, True
    )
    assert outcome.admissible is True


@pytest.mark.parametrize("prerequisite", _VARIANT_ENVIRONMENTAL_PREREQUISITES)
def test_variant_all_but_one_prerequisite_blocks(prerequisite: str) -> None:
    """(canary, all-but-one) Dropping any of the 13 variant prerequisites blocks re-arm."""
    outcome = rearm_admissible(
        variant_checklist(**{prerequisite: False}),
        solo_variant_attestation(),
        _FRESH,
        _PRIOR,
        True,
    )
    assert outcome.admissible is False


def test_variant_incomplete_variant_blocks() -> None:
    """(canary) A solo variant missing one control blocks re-arm (dual control unmet)."""
    from ._liveauth_strategies import full_variant

    attestation = solo_variant_attestation(
        variant=full_variant(independent_nonauthorizing_attestation_current=None)
    )
    outcome = rearm_admissible(variant_checklist(), attestation, _FRESH, _PRIOR, True)
    assert outcome.admissible is False


# ---------------------------------------------------------------------------
# Cross-cutting conjuncts
# ---------------------------------------------------------------------------


def test_reused_identity_blocks() -> None:
    """(canary) A reused (non-fresh) authorization id blocks re-arm."""
    outcome = rearm_admissible(
        armable_checklist(), quorum_attestation(), "old-1", _PRIOR, True
    )
    assert outcome.admissible is False


def test_none_identity_blocks() -> None:
    """(canary) A None new authorization id blocks re-arm."""
    outcome = rearm_admissible(
        armable_checklist(), quorum_attestation(), None, _PRIOR, True
    )
    assert outcome.admissible is False


@pytest.mark.parametrize("verifiable", [None, False])
def test_unverifiable_control_plane_blocks(verifiable: bool | None) -> None:
    """(canary) An unverifiable / partitioned control plane blocks re-arm (§6.6)."""
    outcome = rearm_admissible(
        armable_checklist(), quorum_attestation(), _FRESH, _PRIOR, verifiable
    )
    assert outcome.admissible is False


def test_unknown_path_blocks() -> None:
    """(canary) A None / unset dual-control path fails closed (no environmental expression)."""
    attestation = quorum_attestation(path=None)
    outcome = rearm_admissible(armable_checklist(), attestation, _FRESH, _PRIOR, True)
    assert outcome.admissible is False


def test_default_checklist_not_admissible() -> None:
    """A default (all-None) checklist is never admissible — no vacuous re-arm."""
    outcome = rearm_admissible(
        RearmChecklist(), quorum_attestation(), _FRESH, _PRIOR, True
    )
    assert outcome.admissible is False


def test_outcome_authority_effect_all_false() -> None:
    """(canary §4.1) An admissible re-arm outcome grants NO authority (all-false effect)."""
    outcome = rearm_admissible(
        armable_checklist(), quorum_attestation(), _FRESH, _PRIOR, True
    )
    assert outcome.admissible is True
    effect = outcome.authority_effect
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)


def test_not_admissible_outcome_also_all_false() -> None:
    """A not-admissible outcome is likewise non-authorizing."""
    outcome = rearm_admissible(
        RearmChecklist(), quorum_attestation(), _FRESH, _PRIOR, True
    )
    effect = outcome.authority_effect
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)


# ---------------------------------------------------------------------------
# No automatic re-arm (REARM-AC-003)
# ---------------------------------------------------------------------------


def test_no_automatic_rearm_is_always_true() -> None:
    """(canary REARM-AC-003) No recovery / timeout / restart signal can re-arm."""
    assert (
        no_automatic_rearm(
            health_recovered=True,
            timeout_elapsed=True,
            reconciliation_completed=True,
            leader_elected=True,
            restart_completed=True,
        )
        is True
    )
    assert (
        no_automatic_rearm(
            health_recovered=None,
            timeout_elapsed=None,
            reconciliation_completed=None,
            leader_elected=None,
            restart_completed=None,
        )
        is True
    )


def test_rearm_admissible_does_not_read_automatic_signals() -> None:
    """(canary, structural) rearm_admissible's signature carries no automatic-re-arm flag.

    The health / timeout / reconciliation / leader-election / restart signals are
    structurally UNREAD — the model provides no code path turning one into admissibility.
    """
    import inspect

    params = set(inspect.signature(rearm_admissible).parameters)
    for forbidden in (
        "health_recovered",
        "timeout_elapsed",
        "reconciliation_completed",
        "leader_elected",
        "restart_completed",
    ):
        assert forbidden not in params
