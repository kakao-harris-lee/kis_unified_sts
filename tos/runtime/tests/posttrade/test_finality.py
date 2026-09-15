"""Hermetic tests for :class:`tos_runtime.posttrade.finality.SyntheticFinalityProducer` (TOS
Phase 3 Wave 2 Lane C-R; plan §2.2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
from tos.posttrade import (
    FinalityDimensionKind,
    ObligationLegDirection,
    PostTradeObligationLifecycleState,
)
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
KEY = InstrumentKey(account="acct-1", instrument="101S06")


def _config() -> FinalityConfig:
    return FinalityConfig(
        currency="KRW",
        value_date="2026-09-09",
        source_revision="synthetic-rev-1",
        proof_recipe_id="synthetic-recipe-1",
        release_proof_wait_ms=60_000,
    )


def _producer() -> SyntheticFinalityProducer:
    return SyntheticFinalityProducer(config=_config(), scheme=SCHEME)


def _fill_payload(
    *,
    kind: EgressResultKind,
    filled: str,
    remaining: str,
    attempt_id: str = "attempt-1",
) -> EgressResultPayload:
    return EgressResultPayload(
        instrument_key=KEY,
        attempt_id=attempt_id,
        kind=kind,
        filled_quantity=Decimal(filled),
        remaining_quantity=Decimal(remaining),
    )


def test_full_fill_produces_valid_proof() -> None:
    payload = _fill_payload(kind=EgressResultKind.FULL_FILL, filled="10", remaining="0")

    result = _producer().produce(payload)

    assert result is not None
    assert (
        result.record.lifecycle_state
        is PostTradeObligationLifecycleState.FINALITY_PROVEN
    )
    assert result.record.leg_direction_set() == {ObligationLegDirection.RECEIPT}
    assert result.record.leg_magnitudes[ObligationLegDirection.RECEIPT] == Decimal("10")
    assert result.proof.finality_class is FinalityDimensionKind.ORDER_FQP
    assert result.proof.amount == Decimal("10")
    assert result.proof.obligation_ref == result.record.obligation_id
    assert (
        result.proof.does_not_prove
    )  # non-empty — every OTHER dimension is disclaimed
    assert FinalityDimensionKind.ORDER_FQP.value not in result.proof.does_not_prove


def test_partial_fill_kind_widened_into_eligible_kinds_is_still_refused_by_remaining_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Independent review finding #6, mutation M6 (2026-09-09), RED before the fix.

    The reviewer's own M6 mutation widens ``_ELIGIBLE_KINDS`` to also admit
    ``PARTIAL_FILL`` and constructs "a complete ``SyntheticFinalityResult`` that passes all
    three kernel gates" — none of ``obligation_leg_set_complete`` /
    ``finality_dimensions_orthogonal`` / ``finality_proof_class_specific`` ever inspects
    ``remaining_quantity``, so before this fix the kind-membership check was the ONLY thing
    standing between a partial fill and a full ``ORDER_FQP`` ("zero remaining") proof.

    This is the ONLY reachable way to exercise the fix directly: the kernel's own
    ``EgressResultPayload`` validator (``tos/src/tos/engine/records.py``) already refuses to
    construct a ``FULL_FILL``-kind payload with a nonzero ``remaining_quantity`` at all
    (structural derivation, RFC-005 §11) — so a genuinely malformed FULL_FILL can never reach
    this producer under today's ``_ELIGIBLE_KINDS``; the gap is specifically "what protects the
    ``ORDER_FQP`` claim if a FUTURE edit admits another kind", exactly what M6 mutates.
    """
    import tos_runtime.posttrade.finality as finality_module

    monkeypatch.setattr(
        finality_module,
        "_ELIGIBLE_KINDS",
        frozenset({EgressResultKind.FULL_FILL, EgressResultKind.PARTIAL_FILL}),
    )
    payload = _fill_payload(
        kind=EgressResultKind.PARTIAL_FILL, filled="5", remaining="5"
    )
    assert _producer().produce(payload) is None


def test_partial_fill_produces_no_proof() -> None:
    payload = _fill_payload(
        kind=EgressResultKind.PARTIAL_FILL, filled="5", remaining="5"
    )
    assert _producer().produce(payload) is None


def test_cancel_ack_produces_no_proof() -> None:
    payload = EgressResultPayload(
        instrument_key=KEY, attempt_id="attempt-1", kind=EgressResultKind.CANCEL_ACK
    )
    assert _producer().produce(payload) is None


def test_expired_produces_no_proof() -> None:
    payload = EgressResultPayload(
        instrument_key=KEY, attempt_id="attempt-1", kind=EgressResultKind.EXPIRED
    )
    assert _producer().produce(payload) is None


def test_ack_reject_unknown_timeout_produce_no_proof() -> None:
    for kind in (
        EgressResultKind.ACK,
        EgressResultKind.REJECT,
        EgressResultKind.UNKNOWN,
        EgressResultKind.TIMEOUT,
    ):
        payload = EgressResultPayload(
            instrument_key=KEY, attempt_id="attempt-1", kind=kind
        )
        assert _producer().produce(payload) is None


def test_two_full_fills_for_different_attempts_get_distinct_idempotency_keys() -> None:
    producer = _producer()
    first = producer.produce(
        _fill_payload(
            kind=EgressResultKind.FULL_FILL,
            filled="1",
            remaining="0",
            attempt_id="attempt-a",
        )
    )
    second = producer.produce(
        _fill_payload(
            kind=EgressResultKind.FULL_FILL,
            filled="1",
            remaining="0",
            attempt_id="attempt-b",
        )
    )
    assert first is not None and second is not None
    assert first.record.obligation_id != second.record.obligation_id
    assert first.proof.proof_id != second.proof.proof_id


def test_same_attempt_is_deterministic() -> None:
    """Re-review discipline: no uuid4/timestamp identity — the same attempt always reproduces
    the same obligation/proof id (content-addressed via ``derive_id``, the
    ``ActionFlowGovernor.issue_permit`` precedent)."""
    payload = _fill_payload(kind=EgressResultKind.FULL_FILL, filled="1", remaining="0")
    producer = _producer()
    first = producer.produce(payload)
    second = producer.produce(payload)
    assert first is not None and second is not None
    assert first.record.obligation_id == second.record.obligation_id
    assert first.proof.proof_id == second.proof.proof_id


@pytest.mark.parametrize(
    "missing_key", ["currency", "value_date", "source_revision", "proof_recipe_id"]
)
def test_config_missing_key_refuses(tmp_path, missing_key: str) -> None:
    import yaml
    from tos_runtime.posttrade.config import FinalityConfigError, load_finality_config

    raw = {
        "currency": "KRW",
        "value_date": "2026-09-09",
        "source_revision": "rev-1",
        "proof_recipe_id": "recipe-1",
    }
    raw[missing_key] = None
    path = tmp_path / "finality.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FinalityConfigError):
        load_finality_config(path)


def test_config_loads_example_file_shape() -> None:
    """The example config's own null placeholders must all be refused (fail-closed at rest)."""
    from pathlib import Path

    from tos_runtime.posttrade.config import FinalityConfigError, load_finality_config

    example = Path(__file__).resolve().parents[2] / "config" / "finality.example.yaml"
    with pytest.raises(FinalityConfigError):
        load_finality_config(example)
