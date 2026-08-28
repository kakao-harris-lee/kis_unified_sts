"""All-false monitoring authority — construction seal + predicate second layer (STM-INV-001; §1 line 25).

``monitoring artifact != authority``. The fourteen-flag block is forced ``false`` at construction, and
:func:`~tos.stm.predicates.all_false_monitoring_authority` re-derives the same fact for a
``model_construct`` bypass (design #30 §2.3 defence in depth). Every one of the seven digest-bound
artifacts and the §17 restrictive signal carries the block.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.stm import (
    ALL_FALSE_AUTHORITY_VERBS,
    AllFalseMonitoringAuthority,
    ArtifactIntegrityError,
    all_false_monitoring_authority,
    economic_effect_outlives_monitor_state,
)

from ._stm_strategies import (
    clean_alert,
    clean_coverage_manifest,
    clean_escalation,
    clean_gap,
    clean_policy,
    clean_signal,
    clean_snapshot,
    clean_telemetry_manifest,
)

_FLAGS = tuple(AllFalseMonitoringAuthority.model_fields)


def test_the_block_has_exactly_fourteen_flags() -> None:
    """(§7.2 (c), appendix K) §1 line 25's twelve verbs + capacity + protective = 14 (過 0 · 不 0)."""
    assert len(_FLAGS) == 14
    assert len(ALL_FALSE_AUTHORITY_VERBS) == 14


def test_the_default_block_is_all_false() -> None:
    """(STM-INV-001 line 159) The default authority effect grants nothing."""
    authority = AllFalseMonitoringAuthority()
    assert all(getattr(authority, name) is False for name in _FLAGS)
    assert all_false_monitoring_authority(authority) is True


@pytest.mark.parametrize("flag", _FLAGS)
def test_any_true_flag_is_unconstructable(flag: str) -> None:
    """(construction seal) A ``True`` authority flag makes the block unconstructable."""
    # pydantic wraps the model-validator error, so both shapes are accepted (the sir precedent).
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        AllFalseMonitoringAuthority(**{flag: True})


@pytest.mark.parametrize("flag", _FLAGS)
def test_the_predicate_catches_a_model_construct_bypass(flag: str) -> None:
    """(second layer, design #30 §2.3) ``model_construct`` skips validators — the predicate does not."""
    forged = AllFalseMonitoringAuthority.model_construct(**{flag: True})
    assert getattr(forged, flag) is True
    assert all_false_monitoring_authority(forged) is False


def test_absent_authority_denies() -> None:
    """(∅-seal) An absent block cannot prove non-authority."""
    assert all_false_monitoring_authority(None) is False


@pytest.mark.parametrize(
    "artifact",
    [
        clean_policy(),
        clean_telemetry_manifest(),
        clean_coverage_manifest(),
        clean_snapshot(),
        clean_gap(),
        clean_alert(),
        clean_escalation(),
        clean_signal(),
    ],
)
def test_every_artifact_carries_an_all_false_block(artifact: object) -> None:
    """(STM-INV-001) All seven digest-bound artifacts + the §17 signal are non-authorizing."""
    assert all_false_monitoring_authority(artifact.authority_effect) is True  # type: ignore[attr-defined]


def test_satisfies_preventive_control_is_present_and_false() -> None:
    """(M6, STM-INV-014 line 211) Evidence is not prevention — the flag exists and is false."""
    assert "satisfies_preventive_control" in _FLAGS
    assert AllFalseMonitoringAuthority().satisfies_preventive_control is False


def test_classifies_protective_is_present_and_false() -> None:
    """(§7 line 236) "alert severity is not protective classification"."""
    assert "classifies_protective" in _FLAGS
    assert AllFalseMonitoringAuthority().classifies_protective is False


def test_economic_effect_is_read_as_an_authority_shape_not_an_expiry_flag() -> None:
    """(§19 line 431; the #26 WDR v1.2 lesson) The two vehicle flags are what is asserted false."""
    assert economic_effect_outlives_monitor_state(AllFalseMonitoringAuthority()) is True
    for flag in ("creates_capacity", "establishes_broker_finality"):
        forged = AllFalseMonitoringAuthority.model_construct(**{flag: True})
        assert economic_effect_outlives_monitor_state(forged) is False
    assert economic_effect_outlives_monitor_state(None) is False


@pytest.mark.parametrize("forged_value", [None, 1, "yes", "False"])
def test_a_forged_non_boolean_authority_flag_denies(forged_value: object) -> None:
    """(second layer, mutation-witness) ``is False`` — never ``is not True`` — on the authority flags.

    The declared flags are bare ``bool``, so for a *validated* block ``is False`` and ``is not True``
    agree and a polarity mutation would look equivalent. ``model_construct`` breaks that tie: it skips
    validation entirely, so a forged block can carry ``None``, an int or a string. Under ``is not True``
    every one of those would read as "not granting", which is exactly the fail-open the second layer
    exists to catch; under ``is False`` they all deny.
    """
    forged = AllFalseMonitoringAuthority.model_construct(creates_capacity=forged_value)
    assert forged.creates_capacity is not True
    assert all_false_monitoring_authority(forged) is False
    assert economic_effect_outlives_monitor_state(forged) is False
