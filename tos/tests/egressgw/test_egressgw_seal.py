"""``SendSeal`` unit tests (Phase 4 작업 6, design §1.4).

Exercises :mod:`tos.egressgw.seal` directly — construction rejection (every required field),
the coordinate/field combined validator, the ``claim_principal == active_principal`` A2
enforcement, digest determinism, and :func:`seal_matches_outbound`'s polarity. Gateway-level
ordering / claim / mutation coverage lives in ``test_egressgw_gateway.py``.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError
from tos.egressgw import (
    SendSeal,
    SendSealUnconstructable,
    build_send_seal,
    outbound_coordinates,
    seal_matches_outbound,
)

from ._egressgw_fixtures import SCHEME, authorized_coordinates, happy_context

# ---------------------------------------------------------------------------
# build_send_seal — every required fact rejects None (design §1.4)
# ---------------------------------------------------------------------------

_MISSING_FIELD_CASES: list[tuple[str, dict[str, Any]]] = [
    ("instrument_key", {"instrument_key": None}),
    ("request identity (egress_request absent)", {"egress_request": None}),
    ("capsule_egress_request_digest", {"capsule_egress_request_digest": None}),
    ("claim_principal (context.principal)", {"principal": None}),
    ("authorized coordinates absent", {"authorized_coordinates": None}),
    ("endpoint", {"authorized_coordinates": authorized_coordinates(endpoint=None)}),
    (
        "route_identity",
        {"authorized_coordinates": authorized_coordinates(route_identity=None)},
    ),
    ("capability_nonce", {"capability_nonce": None}),
    ("action_flow_permit_nonce", {"action_flow_permit_nonce": None}),
    ("outbound_quantity", {"outbound_quantity": None}),
    ("outbound_price", {"outbound_price": None}),
    ("outbound_side", {"outbound_side": None}),
]


@pytest.mark.parametrize(
    ("label", "override"),
    _MISSING_FIELD_CASES,
    ids=[label for label, _ in _MISSING_FIELD_CASES],
)
def test_build_send_seal_rejects_each_missing_required_fact(
    label: str, override: dict[str, Any]
) -> None:
    """(design §1.1 "None 불허 · 생성 자체가 거부") Any one absent fact makes the seal unconstructable."""
    attempt, context = happy_context(**override)
    with pytest.raises(SendSealUnconstructable):
        build_send_seal(
            context=context,
            attempt=attempt,
            coordinates=outbound_coordinates(context),
            scheme=SCHEME,
        )
    del label


def test_build_send_seal_succeeds_on_the_unmodified_happy_context() -> None:
    """(control) The baseline fixture is fully sealable — every missing-field case above is real."""
    attempt, context = happy_context()
    seal = build_send_seal(
        context=context,
        attempt=attempt,
        coordinates=outbound_coordinates(context),
        scheme=SCHEME,
    )
    assert isinstance(seal, SendSeal)
    assert seal.attempt_id == attempt.attempt_id


# ---------------------------------------------------------------------------
# the combined coordinate/field validator (design §1.1)
# ---------------------------------------------------------------------------


def test_build_send_seal_rejects_a_coordinate_value_that_disagrees_with_its_field() -> (
    None
):
    """A tampered outbound coordinate the seal has no matching field for is unconstructable."""
    attempt, context = happy_context()
    coordinates = outbound_coordinates(context)
    tampered = tuple(
        (name, "tampered-value") if name == "endpoint" else (name, value)
        for name, value in coordinates
    )
    with pytest.raises(
        SendSealUnconstructable, match="failed its own construction-time validation"
    ):
        build_send_seal(
            context=context, attempt=attempt, coordinates=tampered, scheme=SCHEME
        )


def test_build_send_seal_rejects_a_coordinate_name_the_seal_has_no_field_for() -> None:
    """An outbound coordinate shape other than the fixed 10-name order is unconstructable."""
    attempt, context = happy_context()
    coordinates = outbound_coordinates(context)
    truncated = coordinates[
        :-1
    ]  # drop "active_principal" — the shape no longer matches
    with pytest.raises(SendSealUnconstructable):
        build_send_seal(
            context=context, attempt=attempt, coordinates=truncated, scheme=SCHEME
        )


# ---------------------------------------------------------------------------
# claim_principal == active_principal (design §1.1 A2 — measured-equal, so enforced)
# ---------------------------------------------------------------------------


def test_claim_principal_must_equal_active_principal() -> None:
    """A seal whose claim principal diverges from the sealed active principal is unconstructable.

    Every measured fixture (``happy_context``, the slice fixtures) binds the two identically —
    this proves the validator itself, independent of whether any fixture happens to trip it.
    """
    attempt, context = happy_context()
    seal = build_send_seal(
        context=context,
        attempt=attempt,
        coordinates=outbound_coordinates(context),
        scheme=SCHEME,
    )
    tampered = dict(seal.model_dump())
    tampered["active_principal"] = "someone-else"
    # Keep the coordinate/field validator satisfied so it is the principal-equality validator,
    # not the coordinate one, that fires.
    tampered["outbound_coordinates"] = tuple(
        (name, "someone-else") if name == "active_principal" else (name, value)
        for name, value in tampered["outbound_coordinates"]
    )
    with pytest.raises(ValidationError, match="claim_principal"):
        SendSeal.model_validate(tampered)


# ---------------------------------------------------------------------------
# digest determinism (design §1.4)
# ---------------------------------------------------------------------------


def test_seal_digests_are_deterministic_over_the_same_inputs() -> None:
    """Two seals built from the identical context/attempt/coordinates carry identical digests."""
    attempt, context = happy_context()
    coordinates = outbound_coordinates(context)
    seal_a = build_send_seal(
        context=context, attempt=attempt, coordinates=coordinates, scheme=SCHEME
    )
    seal_b = build_send_seal(
        context=context, attempt=attempt, coordinates=coordinates, scheme=SCHEME
    )
    assert seal_a.seal_digest == seal_b.seal_digest
    assert seal_a.outbound_request_digest == seal_b.outbound_request_digest


@pytest.mark.parametrize(
    ("label", "override"),
    [
        ("outbound_quantity", {"outbound_quantity": Decimal("40")}),
        ("outbound_side", {"outbound_side": "SELL"}),
        (
            "principal (claim + active, kept equal per A2)",
            {
                "principal": "a-different-egressgw-principal",
                "authorized_coordinates": authorized_coordinates(
                    active_principal="a-different-egressgw-principal"
                ),
            },
        ),
    ],
    ids=["outbound_quantity", "outbound_side", "principal"],
)
def test_seal_digests_change_when_any_one_field_changes(
    label: str, override: dict[str, Any]
) -> None:
    """Any single covered-field change yields a different digest (no accidental collapse)."""
    attempt, context = happy_context()
    baseline = build_send_seal(
        context=context,
        attempt=attempt,
        coordinates=outbound_coordinates(context),
        scheme=SCHEME,
    )
    changed_attempt, changed_context = happy_context(**override)
    changed = build_send_seal(
        context=changed_context,
        attempt=changed_attempt,
        coordinates=outbound_coordinates(changed_context),
        scheme=SCHEME,
    )
    assert changed.seal_digest != baseline.seal_digest
    assert changed.outbound_request_digest != baseline.outbound_request_digest
    del label


# ---------------------------------------------------------------------------
# seal_matches_outbound polarity (design §1.4)
# ---------------------------------------------------------------------------


def test_seal_matches_outbound_is_true_for_the_seals_own_values() -> None:
    attempt, context = happy_context()
    coordinates = outbound_coordinates(context)
    seal = build_send_seal(
        context=context, attempt=attempt, coordinates=coordinates, scheme=SCHEME
    )
    assert (
        seal_matches_outbound(
            seal,
            coordinates=coordinates,
            quantity=context.outbound_quantity,
            price=context.outbound_price,
            side=context.outbound_side,
            instrument_key=context.instrument_key,
            attempt_id=attempt.attempt_id,
        )
        is True
    )


@pytest.mark.parametrize(
    "field",
    ["coordinates", "quantity", "price", "side", "instrument_key", "attempt_id"],
)
def test_seal_matches_outbound_is_false_when_any_single_value_diverges(
    field: str,
) -> None:
    attempt, context = happy_context()
    coordinates = outbound_coordinates(context)
    seal = build_send_seal(
        context=context, attempt=attempt, coordinates=coordinates, scheme=SCHEME
    )
    kwargs: dict[str, Any] = {
        "coordinates": coordinates,
        "quantity": context.outbound_quantity,
        "price": context.outbound_price,
        "side": context.outbound_side,
        "instrument_key": context.instrument_key,
        "attempt_id": attempt.attempt_id,
    }
    divergent = {
        "coordinates": (("endpoint", "tampered"),),
        "quantity": Decimal("999"),
        "price": Decimal("1"),
        "side": "SELL",
        "instrument_key": None,
        "attempt_id": "attempt-somebody-else",
    }
    kwargs[field] = divergent[field]
    assert seal_matches_outbound(seal, **kwargs) is False
