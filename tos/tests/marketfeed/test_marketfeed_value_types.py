"""§7.2-12 — value typing: integer tick-scale first, Decimal refused, fractions fail-closed (§2.5)."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest
from tos.dsl import (
    VALUE_NAMESPACE,
    Compare,
    CompareOp,
    EvaluationConfig,
    Operand,
    ScalarValue,
    build_environment,
    eval_compare,
)
from tos.marketfeed import (
    PreimageEntry,
    ValueRejectionReason,
    project_scalar,
    publish_context_value_view,
)

from ._marketfeed_fixtures import (
    BAR_ONE_AS_OF,
    CLOSE_BAR_ONE,
    INTEGRITY_ERRORS,
    SCHEME,
    candidate,
    evaluation,
    issue_capsule,
    issue_snapshot,
    observation,
    preimage,
)

_CONFIG = EvaluationConfig(config_version="cfg-1", bindings={})


def _publish_one(field_key: str, token: object):
    """Publish a single-value bar carrying ``token`` under ``field_key``."""
    payload = preimage(**{field_key: token})
    obs = observation(raw_event_id="raw-1", payload=payload, as_of=BAR_ONE_AS_OF)
    snapshot = issue_snapshot(
        observations=(obs,), field_evaluations=(evaluation(field_key),)
    )
    capsule = issue_capsule(snapshot)
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=snapshot,
        candidates=(candidate(field_key, "raw-1", payload),),
        scheme=SCHEME,
    )
    return capsule, resolution


@pytest.mark.parametrize("token", [0, 1, -1, CLOSE_BAR_ONE, True, False, "REGULAR", ""])
def test_admitted_token_shapes_project_unchanged(token: object) -> None:
    """(§2.5) int / bool / str project to themselves — no rounding, no parsing, no coercion."""
    value, reason = project_scalar(token)  # type: ignore[arg-type]
    assert reason is None
    assert value == token
    assert type(value) is type(token)


@pytest.mark.parametrize("token", [1.5, 0.1, -2.75, 4512500.0, 0.0])
def test_every_float_token_is_fail_closed(token: float) -> None:
    """(§2.5 ★ carried MINOR) The fractional path is refused until the projection rule is ratified."""
    value, reason = project_scalar(token)
    assert value is None
    assert reason is ValueRejectionReason.NON_DETERMINISTIC_NUMERIC


def test_a_numeric_looking_string_stays_a_string() -> None:
    """(§2.5) No silent string → number parsing; a str compares with EQ/NE only."""
    value, reason = project_scalar("4512500")
    assert reason is None
    assert value == "4512500"
    assert isinstance(value, str)


@pytest.mark.parametrize("magnitude", [Decimal("1.5"), Decimal("100"), Decimal("0")])
def test_a_decimal_token_is_refused_before_any_coercion(magnitude: Decimal) -> None:
    """(§2.5 ★ mutation canary) The Decimal guard fires; pydantic never gets to widen it to float."""
    with pytest.raises(INTEGRITY_ERRORS, match="Decimal"):
        PreimageEntry(key="close", value=cast(ScalarValue, magnitude))


def test_the_decimal_guard_does_not_over_reject_the_admitted_shapes() -> None:
    """(#26 WDR MAJOR-1 lesson) The guard rejects Decimal and nothing else."""
    for token in (CLOSE_BAR_ONE, True, "REGULAR"):
        assert PreimageEntry(key="close", value=token).value == token


def test_an_integer_tick_value_publishes_and_orders() -> None:
    """(§2.5) The preferred numeric form reaches the environment and supports LT/GT."""
    capsule, resolution = _publish_one("close", CLOSE_BAR_ONE)
    assert [value.value for value in resolution.values] == [CLOSE_BAR_ONE]
    env = build_environment(capsule, _CONFIG, resolved_context=resolution.view)
    ordered = Compare(
        left=Operand(ref=("capsule", VALUE_NAMESPACE, "close")),
        op=CompareOp.GT,
        right=Operand(const=CLOSE_BAR_ONE - 1),
    )
    assert eval_compare(ordered, env) is True


def test_a_float_value_never_reaches_the_environment() -> None:
    """(§2.5 ★) The fractional path is refused at publication, not merely discouraged in prose."""
    capsule, resolution = _publish_one("close", 4_512_500.5)
    assert resolution.values == ()
    assert {entry.reason for entry in resolution.rejected} == {
        ValueRejectionReason.NON_DETERMINISTIC_NUMERIC
    }
    env = build_environment(capsule, _CONFIG, resolved_context=resolution.view)
    assert env["capsule"][VALUE_NAMESPACE] == {}


def test_a_state_value_publishes_as_a_string_and_compares_by_equality() -> None:
    """(§2.5) ``session == "REGULAR"`` — the spike's own predicate shape."""
    capsule, resolution = _publish_one("session", "REGULAR")
    env = build_environment(capsule, _CONFIG, resolved_context=resolution.view)
    equality = Compare(
        left=Operand(ref=("capsule", VALUE_NAMESPACE, "session")),
        op=CompareOp.EQ,
        right=Operand(const="REGULAR"),
    )
    assert eval_compare(equality, env) is True


def test_a_bool_value_publishes_but_never_orders() -> None:
    """(§2.5, ``vocabulary.py:366-368``) A flag is compared, never ranked as a magnitude."""
    capsule, resolution = _publish_one("halted", False)
    assert [value.value for value in resolution.values] == [False]
    env = build_environment(capsule, _CONFIG, resolved_context=resolution.view)
    ref = Operand(ref=("capsule", VALUE_NAMESPACE, "halted"))
    assert (
        eval_compare(
            Compare(left=ref, op=CompareOp.EQ, right=Operand(const=False)), env
        )
        is True
    )
    for op in (CompareOp.LT, CompareOp.LE, CompareOp.GT, CompareOp.GE):
        assert (
            eval_compare(Compare(left=ref, op=op, right=Operand(const=1)), env) is False
        )
