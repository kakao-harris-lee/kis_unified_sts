"""All-false incident authority — SIR-INV-001 structural seal (design #28 §2.4/§6.8).

SIR-INV-001 line 158 verbatim: "Policy, signal, record, severity, plan, task, message, timeline,
evidence, review, and closure artifacts create **no** capacity, protection, Safety Authority, Live
Authorization, Transmission Capability, broker permission, HALT clear, production scope, or re-arm
authority" (+ §7 line 231 protective self-labelling; §7 line 237 recovery readiness). Every one of the
six digest-bound artifacts carries an :class:`~tos.sir._base.AllFalseIncidentAuthority` whose every flag
is forced ``False`` at construction, and the predicate layer re-derives the same fact for a
``model_construct`` bypass (two layers, design #28 §2.3).

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.sir as s

from ._sir_strategies import (
    clean_active_set,
    clean_closure_decision,
    clean_handoff,
    clean_plan,
    clean_policy,
    clean_record,
)

#: The eleven §7 / SIR-INV-001 authority axes, **independently transcribed** from the ADR (design #28
#: §2.4). ``過 0 · 不 0`` — a new flag or a dropped flag fails here.
_ADR_AUTHORITY_AXES: frozenset[str] = frozenset(
    {
        "creates_capacity",  # INV-001 "capacity"
        "creates_protection",  # INV-001 "protection"
        "creates_safety_authority",  # INV-001 "Safety Authority"
        "issues_live_authorization",  # INV-001 "Live Authorization"
        "creates_transmission_capability",  # INV-001 "Transmission Capability"
        "grants_broker_permission",  # INV-001 "broker permission"
        "clears_halt",  # INV-001 "HALT clear"
        "creates_production_scope",  # INV-001 "production scope"
        "re_arms",  # INV-001 "re-arm authority"
        "classifies_protective_action",  # §7 line 231 "cannot self-label an action protective"
        "establishes_recovery_readiness",  # §7 line 237 "cannot declare readiness"
    }
)


def test_authority_block_covers_exactly_the_adr_axes() -> None:
    """(SIR-INV-001; §7) The all-false block declares exactly the eleven ADR authority axes."""
    assert frozenset(s.AllFalseIncidentAuthority.model_fields) == _ADR_AUTHORITY_AXES
    assert len(_ADR_AUTHORITY_AXES) == 11


def test_default_block_is_all_false() -> None:
    """(SIR-INV-001) The default authority block asserts nothing."""
    authority = s.AllFalseIncidentAuthority()
    assert all(getattr(authority, name) is False for name in _ADR_AUTHORITY_AXES)
    assert s.all_false_incident_authority(authority) is True


@pytest.mark.parametrize("flag", sorted(_ADR_AUTHORITY_AXES))
def test_any_true_flag_is_unconstructable(flag: str) -> None:
    """(SIR-INV-001) Each authority flag set ``True`` makes the block unconstructable."""
    with pytest.raises((s.ArtifactIntegrityError, ValueError)):
        s.AllFalseIncidentAuthority(**{flag: True})


@pytest.mark.parametrize("flag", sorted(_ADR_AUTHORITY_AXES))
def test_model_construct_bypass_is_caught_by_the_predicate(flag: str) -> None:
    """(2-layer §2.3) A ``model_construct`` forged grant is re-caught by the predicate layer."""
    kwargs = dict.fromkeys(_ADR_AUTHORITY_AXES, False)
    kwargs[flag] = True
    forged = s.AllFalseIncidentAuthority.model_construct(**kwargs)
    assert s.all_false_incident_authority(forged) is False


@pytest.mark.parametrize("flag", sorted(_ADR_AUTHORITY_AXES))
def test_model_construct_unknown_flag_is_caught_by_the_predicate(flag: str) -> None:
    """(§4.3 / 2-layer §2.3) A forged **unknown** (``None``) authority flag is not "no authority".

    Each flag is declared a bare ``bool`` with a ``False`` default, so ``None`` can only arrive through
    the ``model_construct`` escape hatch. Reading the block with ``is not True`` would accept that
    ``None`` as "does not grant" — the #18/#22/#23/#25 fail-open in its authority-block form. The
    predicate therefore requires each flag to be **positively** ``False``.
    """
    kwargs: dict[str, object] = dict.fromkeys(_ADR_AUTHORITY_AXES, False)
    kwargs[flag] = None
    forged = s.AllFalseIncidentAuthority.model_construct(**kwargs)
    assert s.all_false_incident_authority(forged) is False


def test_absent_authority_block_denies() -> None:
    """(∅-seal) An absent authority block is undecidable ⇒ deny."""
    assert s.all_false_incident_authority(None) is False


def test_every_artifact_carries_an_all_false_block() -> None:
    """(SIR-INV-001) All six digest-bound artifacts carry a genuinely all-false authority effect."""
    for artifact in (
        clean_policy(),
        clean_record(),
        clean_active_set(),
        clean_plan(),
        clean_handoff(),
        clean_closure_decision(),
    ):
        assert s.all_false_incident_authority(artifact.authority_effect) is True


def test_incident_system_holds_no_route() -> None:
    """(SIR-INV-006 line 178; §15 line 414; §22 line 538) No transmission capability, no broker route."""
    assert s.incident_system_no_route(s.AllFalseIncidentAuthority()) is True
    assert s.incident_system_no_route(None) is False
    forged = s.AllFalseIncidentAuthority.model_construct(
        **{
            **dict.fromkeys(_ADR_AUTHORITY_AXES, False),
            "grants_broker_permission": True,
        }
    )
    assert s.incident_system_no_route(forged) is False


def test_economic_effect_outlives_incident_state_uses_the_authority_shape() -> None:
    """(SIR-INV-013 line 206; the #26 WDR v1.2 lesson) The judgement is on the shape, not an expiry flag.

    Consuming ``is_expired is False`` as a clear would let an expiry be read as "economic effect gone"
    and invert SIR-INV-013. The predicate instead requires the two authority flags that would have to be
    true for an incident-state transition to erase economic effect — capacity release and protective
    re-labelling — to be positively ``False``. No expiry surface exists in the package at all.
    """
    assert (
        s.economic_effect_outlives_incident_state(s.AllFalseIncidentAuthority()) is True
    )
    assert s.economic_effect_outlives_incident_state(None) is False
    for flag in ("creates_capacity", "classifies_protective_action"):
        forged = s.AllFalseIncidentAuthority.model_construct(
            **{**dict.fromkeys(_ADR_AUTHORITY_AXES, False), flag: True}
        )
        assert s.economic_effect_outlives_incident_state(forged) is False
    for forbidden in ("is_expired", "expiry_clears_effect", "expires"):
        assert not hasattr(
            s, forbidden
        ), f"{forbidden} would re-open the INV-012/013 inversion the #26 WDR v1.2 errata closed"
