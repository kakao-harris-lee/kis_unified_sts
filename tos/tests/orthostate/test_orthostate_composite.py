"""Composite + transition records — representability, completeness, swap, conflict (§2/§4).

The five §14 composites are all constructible and digest-deterministic (STATE-EV-001
representability slice); the five dimension fields are required non-Optional with no
default (missing => ValidationError; NONE != None); a dimension-swap fails StrEnum
coercion (global string distinctness); dropping any required covered path fails issuance;
identity is independent of the digest so a same-id / different-bytes pair is a
CRITICAL_CONFLICT; and the records are frozen with no dimension-mutation method
(representation != effect). [STATE-EV-001 slice — /2 durable persistence deferred]
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import tos.orthostate as orthostate
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.orthostate import (
    ArtifactStatus,
    BrokerOrderState,
    CompositeState,
    DimensionTransitionRecord,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
)
from tos.rcl import CapacityState

from ._orthostate_strategies import (
    ALL_14_FIXTURES,
    SCHEME,
    composite_required_kwargs,
    issue_composite,
    issue_transition_record,
    transition_required_kwargs,
)

_DIMENSION_FIELDS = (
    "intent_state",
    "transmission_attempt_state",
    "broker_order_state",
    "knowledge_state",
    "capacity_state",
)

_ARTIFACTS: list[tuple[type, Callable[..., dict[str, Any]]]] = [
    (CompositeState, composite_required_kwargs),
    (DimensionTransitionRecord, transition_required_kwargs),
]


# ---------------------------------------------------------------------------
# §14 representability + digest determinism (STATE-EV-001 slice)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", ALL_14_FIXTURES, ids=lambda c: c.composite_state_id)
def test_all_14_fixtures_are_representable(fixture: CompositeState) -> None:
    """(STATE-EV-001) Every §14 composite is a constructible, issued frozen product.

    Representability is a SEPARATE claim from coupling-cleanliness (design #8 §5.0): all
    five construct; only three are coupling-clean (see test_orthostate_coupling).
    """
    assert fixture.status is ArtifactStatus.ISSUED
    assert fixture.canonical_digest is not None
    assert fixture.composite_state_id is not None


def test_disagreement_composite_is_representable() -> None:
    """(ADR §2 line 43) Broker=UNKNOWN ∧ Knowledge=CONFLICTED ∧ Capacity=POTENTIALLY_LIVE holds."""
    c = issue_composite(
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.UNKNOWN,
        knowledge_state=KnowledgeState.CONFLICTED,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )
    assert c.status is ArtifactStatus.ISSUED


def test_composite_digest_is_deterministic() -> None:
    """Two issued composites with the same covered content share the same digest."""
    a = issue_composite()
    b = issue_composite()
    assert a.canonical_digest == b.canonical_digest


def test_distinct_dimensions_change_the_digest() -> None:
    """A different dimension value yields a different digest (covered coverage canary)."""
    a = issue_composite(capacity_state=CapacityState.ATTEMPT_BOUND)
    b = issue_composite(capacity_state=CapacityState.POTENTIALLY_LIVE)
    assert a.canonical_digest != b.canonical_digest


# ---------------------------------------------------------------------------
# Completeness — required non-Optional dimensions; NONE != None (§4.4)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", _DIMENSION_FIELDS)
def test_missing_dimension_field_is_unconstructable(field: str) -> None:
    """(canary §4.4) Omitting any of the five dimension fields fails construction (no default)."""
    kwargs = composite_required_kwargs()
    del kwargs[field]
    with pytest.raises(ValidationError):
        CompositeState.issue(scheme=SCHEME, **kwargs)


def test_attempt_none_value_constructs_but_missing_field_does_not() -> None:
    """(canary NONE != None) The value NONE is accepted; a missing field is rejected."""
    ok = issue_composite(transmission_attempt_state=TransmissionAttemptState.NONE)
    assert ok.transmission_attempt_state is TransmissionAttemptState.NONE
    kwargs = composite_required_kwargs()
    kwargs["transmission_attempt_state"] = None
    with pytest.raises(ValidationError):
        CompositeState.issue(scheme=SCHEME, **kwargs)


def test_issued_composite_requires_all_five_concrete() -> None:
    """(STATE-EV-001) An ISSUED composite has all five dimensions concrete + a real id."""
    c = issue_composite()
    for field in _DIMENSION_FIELDS:
        assert getattr(c, field) is not None
    assert c.missing_required_fields() == []


# ---------------------------------------------------------------------------
# Dimension-swap structural canary (§4.2)
# ---------------------------------------------------------------------------

_SWAP_CASES = [
    ("broker_order_state", IntentState.PROPOSED),
    ("knowledge_state", BrokerOrderState.UNKNOWN),
    ("intent_state", KnowledgeState.RECONCILED),
    ("capacity_state", TransmissionAttemptState.SEND_STARTED),
    ("transmission_attempt_state", CapacityState.POTENTIALLY_LIVE),
    ("broker_order_state", KnowledgeState.QUARANTINED),
]


@pytest.mark.parametrize("field,foreign_value", _SWAP_CASES)
def test_dimension_swap_is_rejected(field: str, foreign_value: object) -> None:
    """(canary §4.2) A value from another dimension fails StrEnum coercion in this field."""
    kwargs = composite_required_kwargs()
    kwargs[field] = foreign_value
    with pytest.raises(ValidationError):
        CompositeState.issue(scheme=SCHEME, **kwargs)


# ---------------------------------------------------------------------------
# Required-covered drop-one (both records) (§2.3/§2.4)
# ---------------------------------------------------------------------------


def _required_cases() -> list[Any]:
    cases: list[Any] = []
    for cls, kwargs_fn in _ARTIFACTS:
        for path in cls._REQUIRED_COVERED:  # type: ignore[attr-defined]
            cases.append(
                pytest.param(cls, kwargs_fn, path, id=f"{cls.__name__}:{path}")
            )
    return cases


@pytest.mark.parametrize("cls,kwargs_fn,path", _required_cases())
def test_missing_required_covered_rejects_issuance(
    cls: type, kwargs_fn: Callable[..., dict[str, Any]], path: str
) -> None:
    """Dropping any required covered path makes an ISSUED record unconstructable (§3.2)."""
    kwargs = kwargs_fn()
    kwargs[path] = None
    with pytest.raises(ValidationError):
        cls.issue(scheme=SCHEME, **kwargs)  # type: ignore[attr-defined]


def test_every_record_has_non_vacuous_required_covered() -> None:
    """No ledger citizen has an empty _REQUIRED_COVERED (fail-open guard)."""
    for cls, _ in _ARTIFACTS:
        assert cls._REQUIRED_COVERED, f"{cls.__name__} has a vacuous _REQUIRED_COVERED"


@pytest.mark.parametrize("bad_id", [None, "TBD"])
def test_issued_record_requires_independent_id(bad_id: object) -> None:
    """An issued composite needs a concrete independent id (never null / 'TBD') (§2.1/§3.1)."""
    with pytest.raises(ValidationError):
        CompositeState.issue(
            scheme=SCHEME, **composite_required_kwargs(composite_state_id=bad_id)
        )


# ---------------------------------------------------------------------------
# Same-id / different-bytes conflict — fresh-id-per-observation (§2.3/§4.5)
# ---------------------------------------------------------------------------


def _classify_composites(a: CompositeState, b: CompositeState) -> RecordPairKind:
    return classify_record_pair(
        a.composite_state_id,
        a.canonical_digest,
        b.composite_state_id,
        b.canonical_digest,
    )


def test_same_id_diff_bytes_is_critical_conflict() -> None:
    """(canary §4.5) A same-composite-id / different-dimension pair is a CRITICAL_CONFLICT.

    A legitimate transition must be a NEW observation (new id); a same-id byte change is
    a forgery / replay, detectable only because id ⊥ digest (§3.1).
    """
    a = issue_composite(
        composite_state_id="cs-x", broker_order_state=BrokerOrderState.WORKING
    )
    b = issue_composite(
        composite_state_id="cs-x", broker_order_state=BrokerOrderState.PARTIALLY_FILLED
    )
    assert a.canonical_digest != b.canonical_digest
    assert _classify_composites(a, b) is RecordPairKind.CRITICAL_CONFLICT


def test_same_id_same_bytes_is_idempotent_dup() -> None:
    """(canary) A same-id / same-bytes pair is an idempotent duplicate, not a conflict."""
    a = issue_composite(composite_state_id="cs-y")
    b = issue_composite(composite_state_id="cs-y")
    assert _classify_composites(a, b) is RecordPairKind.IDEMPOTENT_DUP


def test_fresh_id_per_observation_is_distinct() -> None:
    """(canary §2.3) Two observations with different ids are DISTINCT (a legitimate transition)."""
    a = issue_composite(
        composite_state_id="cs-o1", broker_order_state=BrokerOrderState.WORKING
    )
    b = issue_composite(
        composite_state_id="cs-o2", broker_order_state=BrokerOrderState.PARTIALLY_FILLED
    )
    assert _classify_composites(a, b) is RecordPairKind.DISTINCT


def test_transition_record_same_id_diff_bytes_conflicts() -> None:
    """(canary §4.5) A same-transition-id / different-bytes pair is a CRITICAL_CONFLICT."""
    a = issue_transition_record(transition_id="tr-x", basis="broker-evidence")
    b = issue_transition_record(transition_id="tr-x", basis="operator-override")
    assert a.canonical_digest != b.canonical_digest
    kind = classify_record_pair(
        a.transition_id, a.canonical_digest, b.transition_id, b.canonical_digest
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT


# ---------------------------------------------------------------------------
# Frozen + no mutation surface (§4.6 representation != effect)
# ---------------------------------------------------------------------------


def test_composite_is_frozen() -> None:
    """An issued composite cannot be mutated in place (frozen; append-only §2.0)."""
    c = issue_composite()
    with pytest.raises(ValidationError):
        c.broker_order_state = BrokerOrderState.FILLED  # type: ignore[misc]


def test_no_dimension_mutation_method_on_records() -> None:
    """(canary §4.6) No record exposes a method that mutates another dimension / normalizes.

    Representation != effect: state changes occur only through an owning authority's
    committed transition, never by a method on the record (ADR-002-005 §12 line 191).
    """
    for record in (issue_composite(), issue_transition_record()):
        forbidden = [
            name
            for name in dir(record)
            if not name.startswith("_")
            and any(
                token in name.lower()
                for token in (
                    "mutate",
                    "set_",
                    "advance",
                    "normalize",
                    "repair",
                    "delete",
                )
            )
        ]
        assert forbidden == [], f"{type(record).__name__} mutation surface: {forbidden}"


def test_package_exposes_no_normalize_operation() -> None:
    """(canary §5.5) The package exposes no 'nearest legal composite' normalize operation."""
    names = [
        name
        for name in dir(orthostate)
        if any(
            token in name.lower() for token in ("normalize", "repair", "coerce_legal")
        )
    ]
    assert names == []
