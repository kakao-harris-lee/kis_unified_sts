"""§5 — the Transport boundary and the synthetic paper transport.

Design #34 §5.2/§5.4/§13 targets: a single-shot port against which ``Q-IDEMP-1`` (three-attempt
resend) and ``Q-IDEMP-2`` (token-expiry resend wrapper) are **unrepresentable**; a deterministic
fill band; a partial fill represented as a partial fill; and an outcome kind **derived from the
magnitudes** rather than declared.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1). A synthetic result is not
evidence that any broker accepted anything — no broker was contacted.
"""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from tos.brokeradapter import (
    NON_FILL_DECLARABLE_KINDS,
    OutboundSendRequest,
    SyntheticFillPolicy,
    SyntheticPaperTransport,
    Transport,
    synthetic_transport_nature_fields,
)
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import EgressResultKind, InstrumentKey, build_attempt_request
from tos.ordering import OrderingEvent

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
LOT = Decimal("2")


def _key() -> InstrumentKey:
    """The suite's dispatch key."""
    return InstrumentKey(account="acct-1", instrument="ES")


def _attempt(sequence: int = 1):
    """A content-addressed attempt request."""
    return build_attempt_request(
        conformance_proof_digest=f"proof-{sequence}",
        action_flow_permit_identity=f"permit-{sequence}",
        reference=OrderingEvent(
            event_id=f"ev-{sequence}", quorum_commit_index=sequence
        ),
        scheme=SCHEME,
    )


def _send(
    transport: SyntheticPaperTransport, quantity: Decimal | None, sequence: int = 1
):
    """Run one single-shot send through ``transport``."""
    return transport.send_once(
        _attempt(sequence),
        instrument_key=_key(),
        coordinates=(("endpoint", "synthetic://paper"), ("account", "acct-1")),
        quantity=quantity,
        price=Decimal("4200"),
        side="BUY",
    )


# ---------------------------------------------------------------------------
# the single-shot seal (§5.4 / Q-IDEMP-1 / Q-IDEMP-2)
# ---------------------------------------------------------------------------


def test_the_transport_protocol_has_exactly_one_method() -> None:
    """(§5.4) One method, one attempt, one result — a retry loop has nothing to iterate."""
    methods = [name for name in vars(Transport) if not name.startswith("_")]
    assert methods == ["send_once"]


def test_the_send_signature_admits_no_retry_or_idempotency_parameter() -> None:
    """(§5.4) No retry count, no attempt index, no idempotency key, no resend flag."""
    parameters = set(inspect.signature(Transport.send_once).parameters)
    assert parameters == {
        "self",
        "attempt",
        "instrument_key",
        "coordinates",
        "quantity",
        "price",
        "side",
        "reference",
    }
    for forbidden in (
        "retry",
        "retries",
        "attempts",
        "idempotency_key",
        "resend",
        "max_tries",
    ):
        assert forbidden not in parameters


def test_the_send_signature_admits_no_credential_or_session_parameter() -> None:
    """(§5.4 Q-IDEMP-2 / ADR-002-013 §1) Authentication is not part of a send."""
    parameters = set(inspect.signature(Transport.send_once).parameters)
    for forbidden in (
        "token",
        "credential",
        "app_key",
        "app_secret",
        "session",
        "auth",
    ):
        assert forbidden not in parameters


def test_the_synthetic_transport_satisfies_the_protocol_structurally() -> None:
    """(§5.1) The Protocol is structural — the synthetic implementation is a runtime instance."""
    transport = SyntheticPaperTransport(
        SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    )
    assert isinstance(transport, Transport)


def test_the_transport_source_contains_no_loop_around_its_own_send() -> None:
    """(§5.4 structural) There is no resend loop inside the transport implementation."""
    import ast
    from pathlib import Path

    import tos.brokeradapter.synthetic as synthetic

    tree = ast.parse(Path(synthetic.__file__).read_text(encoding="utf-8"))
    send = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "send_once"
    )
    loops = [n for n in ast.walk(send) if isinstance(n, (ast.For, ast.While))]
    assert loops == [], (
        "send_once contains a loop — the three-attempt resend of "
        "shared/execution/executor.py:225-232 (Q-IDEMP-1) must stay unrepresentable"
    )


def test_the_transport_holds_no_credential_route_or_session_attribute() -> None:
    """(§4.5 / ADR-002-013 §1) Network 0, credentials 0, route 0 — structurally."""
    transport = SyntheticPaperTransport(
        SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    )
    for name in vars(transport):
        lowered = name.lower()
        for fragment in (
            "credential",
            "token",
            "session",
            "socket",
            "route",
            "url",
            "host",
        ):
            assert fragment not in lowered, f"the synthetic transport holds {name!r}"


def test_the_declared_nature_flags_are_all_explicit_false() -> None:
    """(§4.2) The synthetic transport can honestly declare all three negative-polarity flags."""
    fields = synthetic_transport_nature_fields()
    assert fields == {
        "reaches_broker": False,
        "credential_bearing": False,
        "route_bearing": False,
    }
    assert all(value is False for value in fields.values())


# ---------------------------------------------------------------------------
# determinism (§5.2)
# ---------------------------------------------------------------------------


def test_two_runs_over_the_same_inputs_agree_exactly() -> None:
    """(§5.2) No clock, no RNG, no ambient state — the band is a pure function."""
    policy = SyntheticFillPolicy(fill_numerator=1, fill_denominator=3, lot_size=LOT)
    first = _send(SyntheticPaperTransport(policy), Decimal("30"))
    second = _send(SyntheticPaperTransport(policy), Decimal("30"))
    assert first == second


@settings(max_examples=50, deadline=None)
@given(
    quantity=st.integers(min_value=1, max_value=1000),
    numerator=st.integers(min_value=0, max_value=10),
)
def test_the_fill_never_exceeds_the_authorized_quantity(
    quantity: int, numerator: int
) -> None:
    """(§5.2) The band fills at most what was authorized, always in whole lots."""
    policy = SyntheticFillPolicy(
        fill_numerator=numerator, fill_denominator=10, lot_size=LOT
    )
    result = _send(SyntheticPaperTransport(policy), Decimal(quantity))
    if result.filled_quantity is not None:
        assert result.filled_quantity <= Decimal(quantity)
        assert result.filled_quantity % LOT == 0
        assert result.remaining_quantity is not None
        assert result.filled_quantity + result.remaining_quantity == Decimal(quantity)


# ---------------------------------------------------------------------------
# structural derivation of the outcome kind (구조 파생 > 자기신고)
# ---------------------------------------------------------------------------


def test_a_full_band_derives_a_full_fill() -> None:
    """(§5.5) remaining == 0 ⇒ FULL_FILL, derived from the magnitudes."""
    policy = SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=LOT)
    result = _send(SyntheticPaperTransport(policy), Decimal("20"))
    assert result.kind is EgressResultKind.FULL_FILL
    assert result.remaining_quantity == Decimal("0")


def test_a_half_band_derives_a_partial_fill_that_stays_partial() -> None:
    """(RFC-005 §11:338-339) A partial is a partial; the filled part is never re-requested."""
    policy = SyntheticFillPolicy(fill_numerator=1, fill_denominator=2, lot_size=LOT)
    result = _send(SyntheticPaperTransport(policy), Decimal("20"))
    assert result.kind is EgressResultKind.PARTIAL_FILL
    assert result.filled_quantity == Decimal("10")
    assert result.remaining_quantity == Decimal("10")


def test_a_zero_band_is_an_acknowledgement_not_a_zero_fill() -> None:
    """(design #31 §2.2) Only fill kinds carry magnitudes; nothing filled is an ACK."""
    policy = SyntheticFillPolicy(fill_numerator=0, fill_denominator=1, lot_size=LOT)
    result = _send(SyntheticPaperTransport(policy), Decimal("20"))
    assert result.kind is EgressResultKind.ACK
    assert result.filled_quantity is None


def test_a_fill_kind_can_never_be_declared_by_policy() -> None:
    """(구조 파생 > 자기신고) A producer cannot label a partial as a full fill."""
    assert EgressResultKind.FULL_FILL not in NON_FILL_DECLARABLE_KINDS
    assert EgressResultKind.PARTIAL_FILL not in NON_FILL_DECLARABLE_KINDS
    for kind in (EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL):
        with pytest.raises(ValidationError, match="DERIVED from the magnitudes"):
            SyntheticFillPolicy(declared_kind=kind)


@pytest.mark.parametrize("kind", sorted(NON_FILL_DECLARABLE_KINDS))
def test_a_non_fill_outcome_may_be_declared(kind: EgressResultKind) -> None:
    """(both ways) ACK / REJECT / UNKNOWN / TIMEOUT are scenario inputs, not derivations."""
    result = _send(
        SyntheticPaperTransport(SyntheticFillPolicy(declared_kind=kind)), Decimal("20")
    )
    assert result.kind is kind
    assert result.filled_quantity is None


# ---------------------------------------------------------------------------
# fail-closed policy shapes
# ---------------------------------------------------------------------------


def test_a_policy_with_neither_mode_is_unconstructable() -> None:
    """(fail-closed) An undetermined transport is not a transport."""
    with pytest.raises(
        ValidationError, match="neither an outcome nor a complete fill band"
    ):
        SyntheticFillPolicy()


def test_a_policy_with_both_modes_is_unconstructable() -> None:
    """(fail-closed) Two modes have no single deterministic answer."""
    with pytest.raises(ValidationError, match="both an outcome and a fill band"):
        SyntheticFillPolicy(
            declared_kind=EgressResultKind.ACK,
            fill_numerator=1,
            fill_denominator=2,
            lot_size=LOT,
        )


def test_a_band_without_a_lot_is_unconstructable() -> None:
    """(§3.1 discipline mirrored) A fill is floored to whole lots, never silently rounded."""
    with pytest.raises(ValidationError, match="positive injected lot"):
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=2)


def test_a_band_above_one_is_unconstructable() -> None:
    """(fail-closed) A band cannot fill more than what was authorized."""
    with pytest.raises(ValidationError, match=r"\[0, fill_denominator\]"):
        SyntheticFillPolicy(fill_numerator=3, fill_denominator=2, lot_size=LOT)


def test_an_absent_quantity_is_unknown_never_a_rejection() -> None:
    """(RFC-005 §11:322-323) Nothing was established about a broker's disposition."""
    policy = SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=LOT)
    result = _send(SyntheticPaperTransport(policy), None)
    assert result.kind is EgressResultKind.UNKNOWN


# ---------------------------------------------------------------------------
# attempt identity (design #31 §2.1(ii))
# ---------------------------------------------------------------------------


def test_the_result_always_names_the_attempt_it_was_handed() -> None:
    """(design #31 §2.1(ii)) A transport can never transition someone else's reservation."""
    policy = SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    transport = SyntheticPaperTransport(policy)
    attempt = _attempt(7)
    result = transport.send_once(
        attempt, instrument_key=_key(), coordinates=(), quantity=None, price=None
    )
    assert result.attempt_id == attempt.attempt_id


def test_the_request_retains_the_opaque_coordinates_in_order() -> None:
    """(RFC-002 §10.8:739) The adapter receives coordinates; it does not reinterpret them."""
    policy = SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    transport = SyntheticPaperTransport(policy)
    _send(transport, Decimal("20"))
    (request,) = transport.requests
    assert isinstance(request, OutboundSendRequest)
    assert request.coordinates == (
        ("endpoint", "synthetic://paper"),
        ("account", "acct-1"),
    )
    assert request.coordinate("account") == "acct-1"
    assert request.coordinate("absent") is None


def test_every_call_is_recorded_so_a_second_send_would_be_visible() -> None:
    """(§5.4) One call per attempt — the record is what makes "sent twice" observable."""
    policy = SyntheticFillPolicy(declared_kind=EgressResultKind.ACK)
    transport = SyntheticPaperTransport(policy)
    _send(transport, Decimal("20"), sequence=1)
    assert len(transport.requests) == 1
    _send(transport, Decimal("20"), sequence=2)
    assert len(transport.requests) == 2
    assert (
        transport.requests[0].attempt.attempt_id
        != transport.requests[1].attempt.attempt_id
    )


# ---------------------------------------------------------------------------
# 작업 7 — adapter 1 outbound -> 1 result contract lock (slice plan §5-A)
#
# The stronger "same attempt sent twice is refused" invariant is already pinned at the
# *gateway* layer, not here: ``tos/tests/egressgw/test_egressgw_gateway.py::
# test_the_same_attempt_is_never_sent_twice`` (the single-use claim, gateway.py step 16,
# ``ATTEMPT_ALREADY_CONSUMED``). This package's ``Transport`` is deliberately a dumb
# single-shot port with no dedup state of its own — the negative-grep below fixes that
# absence at the *implementation* level (no retry primitive can be written against it),
# which is this package's part of the contract.
# ---------------------------------------------------------------------------


def _retry_primitive_offenders(source: str) -> list[str]:
    """Return every ``sleep()`` call, retry-named identifier, ``for ... in range(...)``
    loop, or self-recursive ``send_once`` call found in ``source`` (AST scan)."""
    import ast

    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if isinstance(func, ast.Attribute):
                name = func.attr
            if name == "sleep":
                offenders.append(f"line {node.lineno}: sleep() call")
            if name == "send_once":
                offenders.append(f"line {node.lineno}: send_once() call")
        elif isinstance(node, ast.Name) and "retry" in node.id.lower():
            offenders.append(f"line {node.lineno}: retry-named identifier {node.id!r}")
        elif isinstance(node, ast.arg) and "retry" in node.arg.lower():
            offenders.append(f"line {node.lineno}: retry-named argument {node.arg!r}")
        elif (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            offenders.append(f"line {node.lineno}: 'for ... in range(...)' loop")
    return offenders


def test_the_transport_implementation_source_has_no_retry_primitive() -> None:
    """(negative-grep, slice plan §5-A task 7b) No ``sleep()``, no retry-named identifier,
    no ``for _ in range`` resend loop, and no second (self-recursive) ``send_once`` call
    anywhere in the synthetic paper transport's implementation source — the mechanical
    evidence that Q-IDEMP-1 (three-attempt resend) cannot be reintroduced here."""
    from pathlib import Path

    import tos.brokeradapter.synthetic as synthetic

    source = Path(synthetic.__file__).read_text(encoding="utf-8")
    offenders = _retry_primitive_offenders(source)
    assert (
        offenders == []
    ), f"retry/resend primitives found in synthetic.py: {offenders}"


def test_retry_primitive_scan_detects_a_planted_violation() -> None:
    """The negative-grep above is not vacuously green: a planted sleep/retry/range-loop/
    self-recursive send_once source is actually flagged."""
    planted = (
        "import time\n"
        "def send_once(self, attempt):\n"
        "    retry_count = 0\n"
        "    for _ in range(3):\n"
        "        time.sleep(1)\n"
        "        retry_count += 1\n"
        "        result = self.send_once(attempt)\n"
        "    return result\n"
    )
    offenders = _retry_primitive_offenders(planted)
    joined = " ".join(offenders)
    assert "sleep() call" in joined
    assert "retry-named identifier" in joined
    assert "'for ... in range(...)' loop" in joined
    assert "send_once() call" in joined
