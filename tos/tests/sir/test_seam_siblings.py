"""MANDATED test-only seam cross-check — the committed forward seam (design #28 §3.6/§7.2).

SIR is a **greenfield producer with one committed forward concept-seam**. The concept
``tos.sir`` produces — "a dominating open incident restriction is present" — is already consumed by two
landed siblings:

* ``protective/records.py:202`` declares the ``bool | None`` slot with the docstring at ``:181-183``
  ("must be positively ``False`` ... ADR-002-027 / SIR-INV-015 injected verdict"), and
  ``protective/predicates.py:395`` clears de-restriction **only** on a positive ``False``;
* ``sbr/predicates.py:731`` denies recovery whenever that same coordinate "is not ``False``".

Both consumptions are an **anonymous** ``bool | None`` and neither references a ``tos.sir`` type — which
is exactly why the sibling edge is **0** and the seam is forward rather than an inbound deferral. This
file imports the real sibling predicates as a **test** to witness the polarity alignment; the
import-closure test proves ``tos.protective`` and ``tos.sbr`` are **absent** from the sir runtime closure.

**The seam is a polarity alignment, not a wiring.** sir produces only the *incident component*; the HALT
component is authority-owned (ADR §7 line 229) and the *combination* plus the injection into the
consumer's slot is downstream's. The design #28 §3.6 ambiguity prescription forbids sir from authoring
or assigning the consumers' combined coordinate at all, and this file re-asserts that absence beside the
§4.1 canary.

Regime tag: structural / injected-coordinate seam substrate only; closes **no** SIR-EV; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

from pathlib import Path

import tos.sir as s
from tos.protective import DeRestrictionInputs, derestriction_admissible
from tos.sbr import halt_dominates_recovery

from ._sir_strategies import clean_active_set, clean_member, empty_active_set

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOS_SRC = _REPO_ROOT / "tos" / "src" / "tos"
_SIR_SRC = _TOS_SRC / "sir"

#: The consumers' **combined** dominance coordinate name (protective / sbr owned slot).
_CONSUMER_SLOT = "dominating_halt_or_incident"


def _clear_de_restriction_inputs(**overrides: object) -> DeRestrictionInputs:
    """A protective §8.5 input set whose every other conjunct clears, so the seam field is isolated."""
    kwargs: dict[str, object] = {
        "reconciled_authoritative_state": True,
        "safety_authority_current": True,
        "hard_and_runtime_profile_valid": True,
        "critical_input_trust_restored": True,
        "explicit_safety_authority_decision": True,
        _CONSUMER_SLOT: False,
    }
    kwargs.update(overrides)
    return DeRestrictionInputs(**kwargs)


# --- the consumer slot really exists, with the polarity design #28 §4.3 records ---


def test_protective_declares_the_consumer_slot_as_an_anonymous_tribool() -> None:
    """(§3.6 / §0.4b) The protective slot is a plain ``bool | None`` — **not** a ``tos.sir`` type.

    This is the whole basis of the "forward seam, sibling edge 0" judgement: were the slot typed as a
    ``tos.sir`` model, protective would be deferring incident *content* to this package and sir would be
    a deferee rather than a producer.
    """
    annotation = DeRestrictionInputs.model_fields[_CONSUMER_SLOT].annotation
    assert annotation == (bool | None)
    assert all(
        not getattr(part, "__module__", "").startswith("tos.sir")
        for part in getattr(annotation, "__args__", ())
    )


def test_protective_clears_only_on_a_positive_false() -> None:
    """(``protective/predicates.py:395``) De-restriction clears **only** on a positive ``False``."""
    assert derestriction_admissible(_clear_de_restriction_inputs()) is True
    for denying in (True, None):
        assert (
            derestriction_admissible(
                _clear_de_restriction_inputs(**{_CONSUMER_SLOT: denying})
            )
            is False
        )


def test_sbr_denies_unless_a_positive_false() -> None:
    """(``sbr/predicates.py:731``) Recovery is dominated unless the coordinate is a positive ``False``."""
    assert halt_dominates_recovery(False, False, False) is False
    for denying in (True, None):
        assert halt_dominates_recovery(False, denying, False) is True


# --- sir's incident component aligns with that polarity --------------------


def test_sir_incident_component_negation_matches_the_consumer_clear_direction() -> None:
    """(§3.6) ``not dominating_open_incident_present(...)`` lines up with the consumers' ``is False``.

    A **necessary component only**: the consumers' slot is satisfied when there is no dominating HALT
    *and* no dominating incident. sir supplies the incident half; feeding it to the consumer is the
    downstream runtime's job, and this test performs that composition explicitly to show the alignment
    without sir ever doing it.
    """
    # no incident (the canonical explicit-empty set) ⇒ the incident component is positively absent
    empty = empty_active_set()
    incident_component = s.dominating_open_incident_present(empty)
    assert incident_component is False
    composed = not incident_component  # the downstream runtime's composition, not sir's
    assert (
        derestriction_admissible(
            _clear_de_restriction_inputs(**{_CONSUMER_SLOT: not composed})
        )
        is True
    )
    # an open incident ⇒ the incident component is present ⇒ the consumers deny
    open_set = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open",
                lifecycle_state=s.IncidentLifecycleState.CONTAINING,
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
            ),
        )
    )
    assert s.dominating_open_incident_present(open_set) is True
    assert (
        derestriction_admissible(_clear_de_restriction_inputs(**{_CONSUMER_SLOT: True}))
        is False
    )
    assert halt_dominates_recovery(False, True, False) is True


def test_sir_unprovable_set_maps_to_the_consumers_deny_side() -> None:
    """(§3.6 fail-closed alignment) An unprovable set yields the component the consumers deny on."""
    assert s.dominating_open_incident_present(None) is True
    assert s.dominating_open_incident_present(clean_active_set(is_current=None)) is True


# --- sir does NOT author or assign the consumers' combined coordinate ------


def test_sir_never_names_the_consumer_slot() -> None:
    """(§3.6 ambiguity prescription / §4.1 canary) sir owns the incident component only."""
    offenders = [
        f"{path.name}"
        for path in sorted(_SIR_SRC.rglob("*.py"))
        if _CONSUMER_SLOT in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"{_CONSUMER_SLOT!r} appears in a sir source — the HALT half is authority-owned and the "
        f"combination is downstream's (design #28 §3.6): {offenders}"
    )
    assert not hasattr(s, _CONSUMER_SLOT)


def test_sir_reauthors_no_protective_or_sbr_judgement() -> None:
    """(§3.5 / §3.4) sir re-authors no protective classification and no recovery-barrier judgement."""
    for name in (
        "derestriction_admissible",
        "protective_classification",
        "DeRestrictionInputs",
        "halt_dominates_recovery",
        "IsolationFacts",
    ):
        assert not hasattr(s, name), (
            f"{name} is protective / sbr owned — sir consumes their verdicts as injected coordinates "
            "and re-authors none of them (design #28 §3.5)"
        )


def test_committed_consumer_lines_still_carry_the_seam() -> None:
    """(anti-phantom, existence side) The cited consumer lines really contain the cited coordinate.

    The #27 FD lesson has two halves: an *absence* claim must be grepped, and so must an *existence*
    claim. design #28 §3.6 cites four exact locations for the committed forward seam; this asserts each
    file still carries the coordinate, so a sibling refactor that renamed or removed it would surface
    here rather than leaving the design document quietly wrong.
    """
    for relative in (
        "protective/records.py",
        "protective/predicates.py",
        "sbr/predicates.py",
    ):
        text = (_TOS_SRC / relative).read_text(encoding="utf-8")
        assert _CONSUMER_SLOT in text, (
            f"{relative} no longer carries {_CONSUMER_SLOT!r} — the design #28 §3.6 forward-seam "
            "citation has drifted"
        )


def test_wdr_still_consumes_the_incident_generation_as_an_opaque_coordinate() -> None:
    """(anti-phantom, existence side) wdr still self-witnesses the injected Incident Generation.

    design #28 §0.4b clade 3 cites ``wdr/predicates.py:14`` and ``wdr/state.py:48-49`` as wdr's own
    testimony that it consumes the -027 Incident Generation as an **injected opaque coordinate** — an
    anonymous scalar, not a ``tos.sir`` type. That is one of the two pillars of the "greenfield producer,
    sibling edge 0" judgement, so the testimony is locked here.
    """
    for relative in ("wdr/predicates.py", "wdr/state.py"):
        text = (_TOS_SRC / relative).read_text(encoding="utf-8").lower()
        assert "-027" in text and "incident generation" in text, (
            f"{relative} no longer witnesses the injected -027 incident generation — the design #28 "
            "§0.4b clade-3 citation has drifted"
        )
        assert "import tos.sir" not in text and "from tos.sir" not in text, (
            f"{relative} now imports tos.sir — that would make the seam inbound, not forward "
            "(design #28 §0.4b)"
        )
