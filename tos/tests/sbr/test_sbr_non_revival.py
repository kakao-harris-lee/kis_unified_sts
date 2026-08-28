"""recovery_completion_revives_nothing — unconditional non-revival (design #17 §5.7; SBR-EV-012).

Regime tag: predicate / model substrate only; SBR-EV-012 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.sbr import RecoveryReadinessDecision, recovery_completion_revives_nothing

from ._sbr_strategies import issue_decision


def test_revives_nothing_is_unconditionally_true() -> None:
    """(§21 line 526 / SBR-INV-014 line 198) No revival vector revives prior authority."""
    assert recovery_completion_revives_nothing() is True


def test_every_revival_vector_still_revives_nothing() -> None:
    """(SBR-INV-014) completion / health / evidence-repair / replay-match / human-ack revive nothing."""
    assert (
        recovery_completion_revives_nothing(
            completion_signal=True,
            health_recovered=True,
            evidence_repaired=True,
            replay_matched=True,
            human_acknowledged=True,
            prior_authority=object(),
        )
        is True
    )


@given(
    completion=st.booleans(),
    health=st.booleans(),
    evidence=st.booleans(),
    replay=st.booleans(),
    human=st.booleans(),
)
def test_property_no_revival_input_changes_the_answer(
    completion: bool,
    health: bool,
    evidence: bool,
    replay: bool,
    human: bool,
) -> None:
    """(property, accept-and-discard) No combination of revival inputs ever yields revival."""
    assert (
        recovery_completion_revives_nothing(
            completion_signal=completion,
            health_recovered=health,
            evidence_repaired=evidence,
            replay_matched=replay,
            human_acknowledged=human,
        )
        is True
    )


def test_model_provides_no_generation_to_authority_revival_operation() -> None:
    """(§5.7 structural) The readiness model has NO generation-increase -> authority restore path.

    The absence is the seal: there is no method / field that maps a newer recovery_generation
    back into a prior authority — a fresh governed re-arm is mandatory (SBR-INV-014 line 200).
    """
    forbidden = {
        "revive",
        "restore_authority",
        "reactivate",
        "reinstate_prior_authority",
        "rearm",
        "grant_authority",
    }
    assert forbidden.isdisjoint(dir(RecoveryReadinessDecision))
    # And a decision carries only an all-false authority effect (no revival surface).
    decision = issue_decision()
    assert decision.authority_effect.grants_rearm is False
    assert decision.authority_effect.issues_live_auth is False
