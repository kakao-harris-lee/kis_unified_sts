"""Unit tests for :mod:`tos_runtime.recovery.barrier` (TOS Phase 5 W1; plan §2 decision 2).

Constructs :class:`~tos_runtime.recovery.inputs.RecoveryInputs` directly (no sqlite I/O needed —
the barrier itself is a pure fold over already-assembled inputs) so these tests isolate the
barrier's own decision from :mod:`tos_runtime.recovery.inputs`' assembly (covered separately by
``test_inputs.py``).
"""

from __future__ import annotations

import pytest
from tos.sbr.vocabulary import ReadinessVerdict
from tos_runtime.recovery import barrier as barrier_module
from tos_runtime.recovery.barrier import (
    RECON_UNAVAILABLE,
    RecoveryBarrier,
    RecoveryBarrierInvariantError,
)
from tos_runtime.recovery.inputs import RecoveryInputs
from tos_runtime.recovery.legacy_receipts import LegacyReceiptFacts
from tos_runtime.recovery.possibly_live import PossiblyLiveAttempt

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _clean_inputs(**overrides: object) -> RecoveryInputs:
    base: dict[str, object] = {
        "rcl_writer_epoch": 1,
        "rcl_runtime_generation": 1,
        "open_reservations": (),
        "evidence_tip_seq": 1,
        "evidence_tip_key_generation": 1,
        "legacy_receipts": LegacyReceiptFacts(count=0, event_ids=()),
        "inbox_unconsumed_count": 0,
        "possibly_live_attempts": (),
        "composite_state_incomplete_attempt_ids": (),
        "custody_environment_label": "non-live-test",
        "custody_manifest_digest": "a" * 64,
    }
    base.update(overrides)
    return RecoveryInputs(**base)  # type: ignore[arg-type]


def test_clean_inputs_resolve_to_ready() -> None:
    verdict = RecoveryBarrier.verdict(_clean_inputs())
    assert verdict.readiness_verdict is ReadinessVerdict.READY
    assert verdict.ready is True
    assert verdict.possibly_live_reconciliation == {}


def test_genesis_boot_with_no_evidence_or_generation_is_also_ready() -> None:
    """The genuinely-empty-store case (:mod:`tos_runtime.recovery.inputs`'s own genesis
    reading) is a legitimate consistency, not a failure."""
    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            evidence_tip_seq=None,
            evidence_tip_key_generation=None,
            rcl_runtime_generation=None,
        )
    )
    assert verdict.readiness_verdict is ReadinessVerdict.READY


def test_possibly_live_attempt_holds_the_barrier() -> None:
    attempt = PossiblyLiveAttempt(
        event_id="event-x",
        inbox_seq=1,
        handling_started_evidence_seq=1,
        handling_started_generation=1,
    )
    verdict = RecoveryBarrier.verdict(_clean_inputs(possibly_live_attempts=(attempt,)))
    assert verdict.readiness_verdict is ReadinessVerdict.NOT_READY
    assert verdict.ready is False
    assert verdict.possibly_live_reconciliation == {"event-x": RECON_UNAVAILABLE}
    assert "possibly-live" in verdict.reason


def test_legacy_receipt_holds_the_barrier() -> None:
    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            legacy_receipts=LegacyReceiptFacts(count=1, event_ids=("event-y",))
        )
    )
    assert verdict.readiness_verdict is ReadinessVerdict.NOT_READY
    assert "legacy" in verdict.reason


def test_incomplete_composite_state_holds_the_barrier() -> None:
    verdict = RecoveryBarrier.verdict(
        _clean_inputs(composite_state_incomplete_attempt_ids=("event-z",))
    )
    assert verdict.readiness_verdict is ReadinessVerdict.NOT_READY
    assert "composite" in verdict.reason


def test_generation_evidence_inconsistency_holds_the_barrier() -> None:
    """One present, the other absent — neither the "both present" nor the "genesis, both
    absent" case."""
    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            evidence_tip_seq=None,
            evidence_tip_key_generation=None,
            rcl_runtime_generation=1,
        )
    )
    assert verdict.readiness_verdict is ReadinessVerdict.NOT_READY


def test_readiness_verdict_is_truthy_untestable() -> None:
    """The kernel's own truthy-sentinel seal (design #17 §2.2(1)) — a bare ``bool()`` must
    raise, never silently pass as truthy."""
    verdict = RecoveryBarrier.verdict(_clean_inputs())
    with pytest.raises(TypeError):
        bool(verdict.readiness_verdict)


def test_authority_effect_is_all_false() -> None:
    verdict = RecoveryBarrier.verdict(_clean_inputs())
    effect = verdict.authority_effect
    assert effect.creates_capacity is False
    assert effect.issues_live_auth is False
    assert effect.issues_capability is False
    assert effect.classifies_protective is False
    assert effect.transmits_broker is False
    assert effect.grants_rearm is False


def test_authority_separation_invariant_failure_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F8 (independent review, 2026-09-10): the defence-in-depth re-check used to be a bare
    ``assert`` — silently stripped under ``python -O``. It must now be an explicit check that
    raises :class:`~tos_runtime.recovery.barrier.RecoveryBarrierInvariantError`, not swallowed by
    interpreter flags."""
    monkeypatch.setattr(
        barrier_module, "recovery_authority_separated", lambda *_args, **_kwargs: False
    )
    with pytest.raises(RecoveryBarrierInvariantError):
        RecoveryBarrier.verdict(_clean_inputs())


def test_completion_revives_nothing_invariant_failure_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same defence-in-depth discipline (F8) for the second re-check."""
    monkeypatch.setattr(
        barrier_module,
        "recovery_completion_revives_nothing",
        lambda *_args, **_kwargs: False,
    )
    with pytest.raises(RecoveryBarrierInvariantError):
        RecoveryBarrier.verdict(_clean_inputs())


def test_multiple_hold_reasons_are_all_named() -> None:
    attempt = PossiblyLiveAttempt(
        event_id="event-x",
        inbox_seq=1,
        handling_started_evidence_seq=1,
        handling_started_generation=1,
    )
    verdict = RecoveryBarrier.verdict(
        _clean_inputs(
            possibly_live_attempts=(attempt,),
            legacy_receipts=LegacyReceiptFacts(count=1, event_ids=("event-y",)),
        )
    )
    assert "possibly-live" in verdict.reason
    assert "legacy" in verdict.reason
