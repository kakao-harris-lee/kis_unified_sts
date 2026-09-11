"""Tests for :mod:`tos_runtime.safety.protective` (Phase 5 W3.2 plan §2 decision 8,
lane d2). Fixtures are local to this file, never added to ``conftest.py``:
``tos/runtime/tests/safety/`` is a shared worktree where several lanes land
tests concurrently (this file is lane d2's own), so a fixture this file
alone needs stays here rather than risking a merge conflict or an
accidental cross-lane dependency in the shared ``conftest.py``."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from tos.egress import RestrictiveLatchState
from tos.time import HealthState
from tos_runtime.safety.protective import (
    UNEVALUATED_PROTECTIVE_FACTS,
    ProtectiveActionService,
    ProtectiveVerdict,
)


class _RecordingEvidenceRecorder:
    """A :class:`~tos_runtime.safety.protective.ProtectiveEvidenceRecorder` spy — never
    a real evidence store (this suite is hermetic)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.calls.append((kind, dict(fields)))


def _service(
    *,
    latch: RestrictiveLatchState = RestrictiveLatchState.CLEAR,
    incident_clear: bool | None = True,
    time_state: HealthState = HealthState.TRUSTED,
    recorder: _RecordingEvidenceRecorder | None = None,
) -> tuple[ProtectiveActionService, _RecordingEvidenceRecorder]:
    rec = recorder if recorder is not None else _RecordingEvidenceRecorder()
    service = ProtectiveActionService(
        latch_state=lambda: latch,
        incident_clear=lambda: incident_clear,
        time_health_state=lambda: time_state,
        evidence_recorder=rec,
    )
    return service, rec


# ---------------------------------------------------------------------------
# derestriction_admissible — always False given the disclosed missing sources
# ---------------------------------------------------------------------------


def test_derestriction_admissible_is_false_even_at_the_best_case() -> None:
    """Even with every REAL source at its most permissive reading (latch CLEAR, time
    TRUSTED, incident clear), the kernel's own §8.5 line 402 "all four affirmative"
    requirement is never met — three of the five ``DeRestrictionInputs`` facts have no
    real runtime source in this lane (module docstring) and stay ``None``, so
    :func:`~tos.protective.derestriction_admissible` fails closed. This is the disclosed
    consequence, not a bug."""
    service, _ = _service(
        latch=RestrictiveLatchState.CLEAR,
        incident_clear=True,
        time_state=HealthState.TRUSTED,
    )
    verdict = service.verdict()
    assert verdict.derestriction_admissible is False


def test_reasons_include_safety_authority_current_when_time_not_trusted() -> None:
    service, _ = _service(time_state=HealthState.UNTRUSTED)
    verdict = service.verdict()
    assert "safety_authority_current" in verdict.reasons


def test_reasons_omit_safety_authority_current_when_time_trusted() -> None:
    service, _ = _service(time_state=HealthState.TRUSTED)
    verdict = service.verdict()
    assert "safety_authority_current" not in verdict.reasons


def test_reasons_include_hard_and_runtime_profile_valid_when_latch_deny_latched() -> (
    None
):
    service, _ = _service(latch=RestrictiveLatchState.DENY_LATCHED)
    verdict = service.verdict()
    assert "hard_and_runtime_profile_valid" in verdict.reasons


def test_reasons_omit_hard_and_runtime_profile_valid_when_latch_clear() -> None:
    service, _ = _service(latch=RestrictiveLatchState.CLEAR)
    verdict = service.verdict()
    assert "hard_and_runtime_profile_valid" not in verdict.reasons


def test_reasons_include_dominating_halt_or_incident_when_incident_not_clear() -> None:
    service, _ = _service(incident_clear=False)
    verdict = service.verdict()
    assert "dominating_halt_or_incident" in verdict.reasons


def test_reasons_include_dominating_halt_or_incident_when_incident_clear_is_unknown() -> (
    None
):
    """A ``None`` (unresolved) incident-mesh reading collapses to the SAME restrictive
    reading as a positively-denied one — never relaxed toward "no dominating incident"
    (module docstring's own fail-closed rule)."""
    service, _ = _service(incident_clear=None)
    verdict = service.verdict()
    assert "dominating_halt_or_incident" in verdict.reasons


def test_reasons_omit_dominating_halt_or_incident_when_incident_clear() -> None:
    service, _ = _service(incident_clear=True)
    verdict = service.verdict()
    assert "dominating_halt_or_incident" not in verdict.reasons


def test_derestriction_admissible_always_in_reasons_when_false() -> None:
    service, _ = _service()
    verdict = service.verdict()
    assert verdict.derestriction_admissible is False
    assert "derestriction_admissible" in verdict.reasons


# ---------------------------------------------------------------------------
# protective_capacity_exhausted — always True given no profile/budget producer
# ---------------------------------------------------------------------------


def test_capacity_exhausted_is_always_true_given_no_profile_or_budget_source() -> None:
    service, _ = _service()
    verdict = service.verdict()
    assert verdict.capacity_exhausted is True
    assert "capacity_exhausted" in verdict.reasons


def test_capacity_exhausted_true_is_the_disclosed_consequence_of_the_two_none_sourced_inputs() -> (
    None
):
    """MEDIUM disposition (W3.2 review): pins that ``capacity_exhausted=True`` is not an
    isolated fact but the documented consequence of the two genuinely-absent inputs
    ``protective_capacity_exhausted(None, budget_remaining=None)`` is called with — both
    named in ``UNEVALUATED_PROTECTIVE_FACTS`` and both recorded in the durable
    ``PROTECTIVE_VERDICT`` evidence payload alongside the exhausted result, so a reader of
    either surface can see the fact and its cause together."""
    service, recorder = _service()
    verdict = service.verdict()

    assert "protective_capacity_profile" in verdict.unevaluated
    assert "protective_capacity_budget_remaining" in verdict.unevaluated
    assert verdict.capacity_exhausted is True

    _kind, fields = recorder.calls[0]
    assert fields["capacity_exhausted"] is True
    assert "protective_capacity_profile" in fields["unevaluated"]
    assert "protective_capacity_budget_remaining" in fields["unevaluated"]


# ---------------------------------------------------------------------------
# protective_classification — never called
# ---------------------------------------------------------------------------


def test_classification_is_always_none() -> None:
    service, _ = _service()
    verdict = service.verdict()
    assert verdict.classification is None


# ---------------------------------------------------------------------------
# unevaluated — exact, pinned set
# ---------------------------------------------------------------------------


def test_unevaluated_is_exactly_the_documented_set() -> None:
    service, _ = _service()
    verdict = service.verdict()
    assert verdict.unevaluated == UNEVALUATED_PROTECTIVE_FACTS
    assert set(verdict.unevaluated) == {
        "reconciled_authoritative_state",
        "critical_input_trust_restored",
        "explicit_safety_authority_decision",
        "protective_capacity_profile",
        "protective_capacity_budget_remaining",
        "protective_classification",
        "mode_permits_protective",
        "replacement_predicates",
    }


# ---------------------------------------------------------------------------
# evidence — PROTECTIVE_VERDICT recorded exactly once per verdict() call
# ---------------------------------------------------------------------------


def test_protective_verdict_evidence_recorded_once_per_call() -> None:
    service, recorder = _service()
    service.verdict()
    assert len(recorder.calls) == 1
    kind, fields = recorder.calls[0]
    assert kind == "PROTECTIVE_VERDICT"
    assert fields["derestriction_admissible"] is False
    assert fields["capacity_exhausted"] is True
    assert fields["classification"] is None


def test_protective_verdict_evidence_recorded_once_per_verdict_call_not_globally() -> (
    None
):
    service, recorder = _service()
    service.verdict()
    service.verdict()
    assert len(recorder.calls) == 2


def test_describe_calls_verdict_exactly_once_worth_of_evidence() -> None:
    service, recorder = _service()
    service.describe()
    assert len(recorder.calls) == 1


# ---------------------------------------------------------------------------
# M5 — the digest must change when the verdict changes
# ---------------------------------------------------------------------------


def test_digest_changes_when_latch_state_changes() -> None:
    clear_service, _ = _service(latch=RestrictiveLatchState.CLEAR)
    denied_service, _ = _service(latch=RestrictiveLatchState.DENY_LATCHED)
    clear_digest = clear_service.verdict().protective_classification_digest
    denied_digest = denied_service.verdict().protective_classification_digest
    assert clear_digest is not None
    assert denied_digest is not None
    assert clear_digest != denied_digest


def test_digest_changes_when_incident_clear_changes() -> None:
    clear_service, _ = _service(incident_clear=True)
    denied_service, _ = _service(incident_clear=False)
    assert (
        clear_service.verdict().protective_classification_digest
        != denied_service.verdict().protective_classification_digest
    )


def test_digest_is_stable_for_the_same_inputs() -> None:
    service, _ = _service()
    first = service.verdict().protective_classification_digest
    second = service.verdict().protective_classification_digest
    assert first == second


def test_protective_classification_digest_method_matches_verdict_field() -> None:
    service, _ = _service()
    verdict = service.verdict()
    # A fresh call — same inputs, so the digest must be identical (test_digest_is_stable
    # above already pins that), and the convenience method returns exactly this field.
    assert (
        service.protective_classification_digest()
        == verdict.protective_classification_digest
    )


# ---------------------------------------------------------------------------
# zero execution path — no transport, no RCL mutation
# ---------------------------------------------------------------------------


def test_constructor_has_no_transport_or_mutation_port() -> None:
    """Structural pin: the constructor accepts only read ports — no adapter / transport
    / RCL-log / mutation-shaped parameter exists to ever be called."""
    params = set(inspect.signature(ProtectiveActionService.__init__).parameters)
    forbidden_substrings = ("send", "cancel", "adapter", "transport", "mutate", "log")
    for name in params:
        for forbidden in forbidden_substrings:
            assert (
                forbidden not in name.lower()
            ), f"unexpected transport/mutation-shaped constructor parameter: {name!r}"


def test_service_exposes_no_send_or_mutation_method() -> None:
    public_methods = {
        name for name in dir(ProtectiveActionService) if not name.startswith("_")
    }
    assert public_methods == {"verdict", "protective_classification_digest", "describe"}


def test_describe_states_zero_execution_path() -> None:
    service, _ = _service()
    description = service.describe()
    assert "none" in description["execution_path"]
    assert (
        "transport" in description["execution_path"]
        or "RCL" in description["execution_path"]
    )


def test_describe_is_secret_free() -> None:
    service, _ = _service()
    description = service.describe()
    for key in description:
        assert "secret" not in key.lower()
        assert "token" not in key.lower()
        assert "password" not in key.lower()


def test_verdict_is_frozen_dataclass_instance() -> None:
    service, _ = _service()
    verdict = service.verdict()
    assert isinstance(verdict, ProtectiveVerdict)
    # frozen — attempting to mutate raises.
    raised = False
    try:
        verdict.derestriction_admissible = True  # type: ignore[misc]
    except Exception:
        raised = True
    assert raised
