"""Re-arm gate — non-authorizing conjunctive checklist + SoD (§6.6; SA-EV-010).

All 14 prerequisites must be positively True AND the two dual-control principals must
differ for ``armable``; any False / None / shared-principal => not armable; and even an
armable verdict grants no authority (its authority_effect is all-false). SA-INV-013/014.
"""

from __future__ import annotations

import pytest
from tos.authority import RearmChecklist, RearmVerdict, rearm_gate
from tos.authority.predicates import _REARM_PREREQUISITES


def armable_checklist(**overrides: object) -> RearmChecklist:
    """A checklist with all 14 prerequisites True and distinct dual-control principals."""
    base: dict[str, object] = dict.fromkeys(_REARM_PREREQUISITES, True)
    base["limit_enlarger_principal"] = "principal-A"
    base["armer_principal"] = "principal-B"
    base.update(overrides)
    return RearmChecklist(**base)


def test_all_prerequisites_and_distinct_principals_is_armable() -> None:
    """(guard fires True) All 14 True + distinct principals => armable."""
    verdict = rearm_gate(armable_checklist())
    assert verdict.armable is True


def test_checklist_has_exactly_fourteen_prerequisites() -> None:
    """The conjunctive checklist is the ADR §17.1 14-item set (no silent shrinkage)."""
    assert len(_REARM_PREREQUISITES) == 14


@pytest.mark.parametrize("prerequisite", _REARM_PREREQUISITES)
def test_dropping_any_single_prerequisite_blocks_rearm(prerequisite: str) -> None:
    """(canary) Each of the 14 prerequisites is load-bearing: False on any => not armable."""
    verdict = rearm_gate(armable_checklist(**{prerequisite: False}))
    assert verdict.armable is False


@pytest.mark.parametrize("prerequisite", _REARM_PREREQUISITES)
def test_unknown_none_prerequisite_blocks_rearm(prerequisite: str) -> None:
    """(canary SA-INV-013) A None (UNKNOWN) prerequisite => not armable (no automatic re-arm)."""
    verdict = rearm_gate(armable_checklist(**{prerequisite: None}))
    assert verdict.armable is False


def test_same_principal_violates_separation_of_duties() -> None:
    """(canary SA-INV-014) The same principal for enlargement and arming => not armable."""
    verdict = rearm_gate(
        armable_checklist(limit_enlarger_principal="same", armer_principal="same")
    )
    assert verdict.armable is False


def test_missing_principal_blocks_rearm() -> None:
    """(canary SA-INV-014) A missing dual-control principal => not armable (SoD unverifiable)."""
    assert rearm_gate(armable_checklist(limit_enlarger_principal=None)).armable is False
    assert rearm_gate(armable_checklist(armer_principal=None)).armable is False


def test_default_checklist_is_not_armable() -> None:
    """A default (all-None) checklist is not armable — never a vacuous re-arm."""
    assert rearm_gate(RearmChecklist()).armable is False


def test_armable_verdict_is_non_authorizing() -> None:
    """(canary SA-INV-013) An armable verdict grants NO authority (authority_effect all-false).

    ``armable=True`` reports only that prerequisites are met; it does not re-arm — re-arm
    then issues new capabilities under the current epoch (§17.3), which re-run §5.2.
    """
    verdict = rearm_gate(armable_checklist())
    assert verdict.armable is True
    effect = verdict.authority_effect
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)


def test_verdict_authority_effect_all_false_even_when_not_armable() -> None:
    """A not-armable verdict is likewise non-authorizing."""
    verdict = rearm_gate(RearmChecklist())
    assert isinstance(verdict, RearmVerdict)
    effect = verdict.authority_effect
    assert all(getattr(effect, name) is False for name in type(effect).model_fields)
