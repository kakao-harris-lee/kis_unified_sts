"""Dimension vocabulary — verbatim enums, membership, global string distinctness (§2.2/§4.1).

Each dimension enum matches its ADR-002-005 cardinality; ``RECONCILED`` is a Knowledge
value only and ``UNKNOWN`` a Broker value only (§1 line 27); the five dimension enums
(the four local + rcl ``CapacityState``) share NO string value, which is what makes a
dimension-swap fail StrEnum coercion (design #8 §2.2/§4.2 dimension-swap substrate).
[STATE-EV-001 slice]
"""

from __future__ import annotations

from tos.orthostate import (
    WEAK_BASES,
    BrokerOrderState,
    ConservatismBasis,
    IntentState,
    KnowledgeState,
    StateDimension,
    TransitionAuthority,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState

_DIMENSION_ENUMS = (
    IntentState,
    TransmissionAttemptState,
    BrokerOrderState,
    KnowledgeState,
    CapacityState,
)


def test_dimension_cardinalities_match_adr() -> None:
    """Each dimension enum has exactly its ADR-002-005 §5-§9 member count."""
    assert len(list(IntentState)) == 7
    assert len(list(TransmissionAttemptState)) == 8
    assert len(list(BrokerOrderState)) == 9
    assert len(list(KnowledgeState)) == 7
    assert len(list(CapacityState)) == 9  # rcl REUSE


def test_reconciled_is_knowledge_only() -> None:
    """(canary §1 line 27) RECONCILED is a Knowledge value, never a Broker value."""
    assert "RECONCILED" in {s.value for s in KnowledgeState}
    assert "RECONCILED" not in {s.value for s in BrokerOrderState}


def test_unknown_is_broker_not_knowledge() -> None:
    """(canary §1 line 27) UNKNOWN is a first-class Broker value; Knowledge has none."""
    assert "UNKNOWN" in {s.value for s in BrokerOrderState}
    assert "UNKNOWN" not in {s.value for s in KnowledgeState}


def test_attempt_none_is_a_real_value() -> None:
    """(canary NONE != None) TransmissionAttemptState.NONE is a legitimate member."""
    assert TransmissionAttemptState.NONE.value == "NONE"
    assert TransmissionAttemptState.NONE in set(TransmissionAttemptState)


def test_global_string_value_pairwise_disjoint_across_five_dimensions() -> None:
    """(design invariant §2.2) No state string appears in two of the five dimension enums."""
    seen: dict[str, str] = {}
    for enum in _DIMENSION_ENUMS:
        for member in enum:
            assert member.value not in seen, (
                f"string value {member.value!r} shared by "
                f"{enum.__name__} and {seen[member.value]} — dimension-swap fail-open"
            )
            seen[member.value] = enum.__name__
    # 7 + 8 + 9 + 7 + 9 = 40 globally distinct values.
    assert len(seen) == 40


def test_state_dimension_and_authority_enums_complete() -> None:
    """StateDimension names all five axes; TransitionAuthority names the six §12 roles."""
    assert {d.value for d in StateDimension} == {
        "INTENT",
        "TRANSMISSION_ATTEMPT",
        "BROKER_ORDER",
        "KNOWLEDGE",
        "CAPACITY",
    }
    assert len(list(TransitionAuthority)) == 6


def test_weak_bases_are_wider_than_rcl_weak_causes() -> None:
    """(design #8 §0.4c) orthostate WEAK_BASES ⊋ rcl WEAK_CAUSES (local_cache/recovery added)."""
    from tos.rcl import WEAK_CAUSES

    weak_values = {b.value for b in WEAK_BASES}
    rcl_weak_values = {c.value for c in WEAK_CAUSES}
    assert weak_values == {
        "TIMEOUT",
        "ABSENCE",
        "LOCAL_CACHE",
        "OPERATOR_ASSERTION",
        "RECOVERY_RECONNECT",
    }
    # LOCAL_CACHE / RECOVERY_RECONNECT are the deliberate additions absent from rcl.
    assert "LOCAL_CACHE" in weak_values and "LOCAL_CACHE" not in rcl_weak_values
    assert (
        "RECOVERY_RECONNECT" in weak_values
        and "RECOVERY_RECONNECT" not in rcl_weak_values
    )
    assert all(b in WEAK_BASES for b in ConservatismBasis if b.value in weak_values)
