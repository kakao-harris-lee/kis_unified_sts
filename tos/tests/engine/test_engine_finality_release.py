"""``ProvisionalReservationLedger.release`` + ``FinalityProofRef`` (kernel round #3 §2 decision 5,
``docs/plans/2026-09-12-tos-kernel-round-3-plan.md``).

Four things this file locks that nothing else does:

* **Release is gated on the typed token alone** — a response kind, a bare string, or any other
  non-:class:`~tos.engine.state.FinalityProofRef` argument raises ``TypeError`` (mutation M5: no
  response-kind/string path exists to ``RELEASED``).
* **Release requires a terminal knowledge state** — a reservation still ``POTENTIALLY_LIVE`` (no
  settlement evidence yet) is refused (``False``, not an exception); only ``FILLED`` /
  ``REJECTED`` / ``CANCEL_ACKNOWLEDGED`` / ``EXPIRED`` knowledge admits release.
* **Release is idempotent and matches by token alone** — calling it twice on the same attempt
  returns ``False`` the second time, and it finds the reservation across every scope the ledger
  holds by ``attempt_id`` alone, never a caller-supplied ``InstrumentKey``.
* **``resolution_generation`` extends the duplicate-detection signature (ⓖ)** — a byte-identical
  repeat of an already-applied result is ``DUPLICATE`` only when its ``resolution_generation``
  also matches; a genuinely re-resolved TIMEOUT arriving at a NEW generation is a fresh, applied
  result, not folded into ``DUPLICATE``.

Regime tag: authoring evidence only; closes no EV (design #31 §1.1).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.engine.records import EgressResultPayload
from tos.engine.state import (
    FinalityProofRef,
    ProvisionalReservationLedger,
)
from tos.engine.vocabulary import EgressKnowledge, EgressResultKind, ResultDisposition
from tos.rcl import CapacityState

from ._engine_fixtures import instrument_key

_ATTEMPT = "release-attempt-1"


def _live_ledger(
    *, max_unresolved_send_per_scope: int = 1
) -> tuple[ProvisionalReservationLedger, object]:
    """A ledger with one scope projected all the way to ``POTENTIALLY_LIVE`` — the state every
    ordinary flow reaches right before an egress result lands."""
    ledger = ProvisionalReservationLedger(
        max_unresolved_send_per_scope=max_unresolved_send_per_scope
    )
    key = instrument_key()
    ledger.commit_unbound(key, proposal_id="proposal-1")
    ledger.bind_attempt(key, attempt_id=_ATTEMPT)
    ledger.mark_potentially_live(key)
    return ledger, key


def _proof(**overrides: object) -> FinalityProofRef:
    base: dict[str, object] = {
        "attempt_id": _ATTEMPT,
        "proof_digest": "proof-digest-1",
        "evidence_seq": 1,
        "resolution_generation": 1,
    }
    base.update(overrides)
    return FinalityProofRef(**base)


# ===========================================================================
# mutation M5 — the type gate
# ===========================================================================


@pytest.mark.parametrize(
    "bogus",
    [
        "EGRESS_RESULT",
        EgressResultKind.FULL_FILL,
        None,
        {"attempt_id": _ATTEMPT},
        _ATTEMPT,
    ],
)
def test_release_requires_a_finality_proof_ref_type(bogus: object) -> None:
    """(mutation M5) No response-kind/string/dict path reaches ``RELEASED`` — only the typed
    token does. Every one of these looks plausible (a kind, the attempt id itself, a dict shaped
    like one) and every one must be refused the same way."""
    ledger, _ = _live_ledger()
    with pytest.raises(TypeError):
        ledger.release(bogus)  # type: ignore[arg-type]


# ===========================================================================
# terminal-state gate
# ===========================================================================


def test_release_refuses_a_still_live_reservation() -> None:
    """A ``POTENTIALLY_LIVE`` reservation carries no settlement evidence yet — refused, not an
    exception."""
    ledger, key = _live_ledger()
    assert ledger.release(_proof()) is False
    assert ledger.outstanding(key) is not None
    assert ledger.outstanding(key).capacity_state is CapacityState.POTENTIALLY_LIVE


def test_release_refuses_a_partial_fill() -> None:
    """A partial fill may still receive more fills — not terminal (module docstring)."""
    ledger, key = _live_ledger()
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=EgressResultKind.PARTIAL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("1"),
        )
    )
    assert ledger.outstanding(key).knowledge is EgressKnowledge.PARTIALLY_FILLED
    assert ledger.release(_proof()) is False
    assert ledger.outstanding(key).capacity_state is not CapacityState.RELEASED


def test_release_refuses_a_quarantined_reservation() -> None:
    """An unresolved ``QUARANTINED_UNKNOWN`` carries no positive evidence — refused."""
    ledger, key = _live_ledger()
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key, attempt_id=_ATTEMPT, kind=EgressResultKind.TIMEOUT
        )
    )
    assert ledger.outstanding(key).capacity_state is CapacityState.QUARANTINED_UNKNOWN
    assert ledger.release(_proof()) is False


@pytest.mark.parametrize(
    ("kind", "fills"),
    [
        (
            EgressResultKind.FULL_FILL,
            {"filled_quantity": Decimal("2"), "remaining_quantity": Decimal("0")},
        ),
        (EgressResultKind.REJECT, {}),
        (EgressResultKind.CANCEL_ACK, {}),
        (EgressResultKind.EXPIRED, {}),
    ],
)
def test_release_succeeds_from_every_terminal_knowledge_state(kind, fills) -> None:
    """(kernel round #3 §2 decision 5) Exactly the four terminal knowledge states the plan names
    (FULL_FILL/CANCEL_ACK/EXPIRED/REJECT) admit release."""
    ledger, key = _live_ledger()
    ledger.apply_egress_result(
        EgressResultPayload(instrument_key=key, attempt_id=_ATTEMPT, kind=kind, **fills)
    )
    assert ledger.release(_proof()) is True
    assert ledger.outstanding(key).capacity_state is CapacityState.RELEASED


# ===========================================================================
# idempotency + token-only matching
# ===========================================================================


def test_release_is_idempotent_false_on_the_second_call() -> None:
    ledger, key = _live_ledger()
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("2"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert ledger.release(_proof()) is True
    assert ledger.release(_proof(proof_digest="a-different-proof")) is False
    assert ledger.outstanding(key).capacity_state is CapacityState.RELEASED


def test_release_matches_by_attempt_id_across_every_scope_not_by_caller_supplied_key() -> (
    None
):
    """ "Release by token only" — the caller need not know which scope holds the attempt."""
    ledger = ProvisionalReservationLedger(max_unresolved_send_per_scope=1)
    key_a = instrument_key(account="acct-a", instrument="instr-a")
    key_b = instrument_key(account="acct-b", instrument="instr-b")
    ledger.commit_unbound(key_a, proposal_id="p-a")
    ledger.bind_attempt(key_a, attempt_id="attempt-a")
    ledger.mark_potentially_live(key_a)
    ledger.commit_unbound(key_b, proposal_id="p-b")
    ledger.bind_attempt(key_b, attempt_id="attempt-b")
    ledger.mark_potentially_live(key_b)
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key_b,
            attempt_id="attempt-b",
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
        )
    )
    ref = FinalityProofRef(
        attempt_id="attempt-b",
        proof_digest="proof-b",
        evidence_seq=1,
        resolution_generation=1,
    )
    assert ledger.release(ref) is True
    assert ledger.outstanding(key_b).capacity_state is CapacityState.RELEASED
    # Scope A is untouched — release only ever finds the ONE matching attempt_id.
    assert ledger.outstanding(key_a).capacity_state is CapacityState.POTENTIALLY_LIVE


def test_release_refuses_an_unmatched_attempt_id() -> None:
    ledger, key = _live_ledger()
    ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
        )
    )
    ref = FinalityProofRef(
        attempt_id="no-such-attempt",
        proof_digest="p",
        evidence_seq=1,
        resolution_generation=1,
    )
    assert ledger.release(ref) is False
    assert ledger.outstanding(key).capacity_state is CapacityState.POSITION_CONSUMED


# ===========================================================================
# ⓖ — resolution_generation extends the dedup signature
# ===========================================================================


def test_a_repeated_timeout_at_a_new_generation_is_not_a_duplicate() -> None:
    """(ⓖ) The SAME TIMEOUT result (byte-identical in every field but ``resolution_generation``)
    arriving again at a NEW generation is a fresh, applied result — not folded into ``DUPLICATE``.
    Before round #3 the 5-tuple signature had no generation axis at all, so this exact scenario
    (a quarantine-resolution consumer re-resolving the same TIMEOUT at a later generation) would
    have been misread as a mere resend."""
    ledger, key = _live_ledger()
    first = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=EgressResultKind.TIMEOUT,
            resolution_generation=1,
        )
    )
    assert first.disposition is ResultDisposition.APPLIED

    second = ledger.apply_egress_result(
        EgressResultPayload(
            instrument_key=key,
            attempt_id=_ATTEMPT,
            kind=EgressResultKind.TIMEOUT,
            resolution_generation=2,
        )
    )
    assert second.disposition is ResultDisposition.APPLIED, (
        "a TIMEOUT re-arriving at a NEW resolution_generation must be applied, not folded into "
        "DUPLICATE (ⓖ)"
    )


def test_a_repeated_timeout_at_the_same_generation_is_a_duplicate() -> None:
    """The mirror of the above: byte-identical in every field, generation included, IS a
    duplicate — round #3 only adds a new axis, it does not remove the existing guard."""
    ledger, key = _live_ledger()
    payload = EgressResultPayload(
        instrument_key=key,
        attempt_id=_ATTEMPT,
        kind=EgressResultKind.TIMEOUT,
        resolution_generation=1,
    )
    first = ledger.apply_egress_result(payload)
    assert first.disposition is ResultDisposition.APPLIED
    second = ledger.apply_egress_result(payload)
    assert second.disposition is ResultDisposition.DUPLICATE


def test_repeated_results_with_no_generation_tracked_behave_exactly_as_before() -> None:
    """The honest default (``resolution_generation=None`` on both) behaves exactly like the
    pre-round-#3 5-tuple signature: two ``None`` results with otherwise-identical fields still
    compare equal, so an ordinary producer that never stamps a generation is unaffected.
    """
    ledger, key = _live_ledger()
    payload = EgressResultPayload(
        instrument_key=key, attempt_id=_ATTEMPT, kind=EgressResultKind.TIMEOUT
    )
    assert payload.resolution_generation is None
    first = ledger.apply_egress_result(payload)
    assert first.disposition is ResultDisposition.APPLIED
    second = ledger.apply_egress_result(payload)
    assert second.disposition is ResultDisposition.DUPLICATE
