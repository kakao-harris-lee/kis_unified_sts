"""``tos_runtime.compose._risk_attestations`` tests (re-review finding F4,
2026-09-08). Hermetic — real config files under ``tmp_path``, real
``AggregateRiskDecisionInputs``/``ActionFlowDecisionInputs`` construction
(never a mock of the kernel dataclasses)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.are import RiskScopeKind
from tos_runtime.compose._risk_attestations import (
    RiskAttestationConfigError,
    RiskAttestations,
    load_risk_attestations,
    wrap_action_flow_inputs_provider,
    wrap_aggregate_risk_inputs_provider,
)
from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs

from . import _fixtures as fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _valid_risk_attestations() -> dict:
    return {
        "numerically_safe": {"attested": True},
        "valuation_ok": {"attested": True},
        "all_fields_attributed": {"attested": True},
        "limit_source_is_injected_envelope": {"attested": True},
        "economic_commitment_exclusive": {"attested": True},
        "flow_commitment_exclusive": {"attested": True},
    }


def _write(path: Path, content: dict) -> None:
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


# ============================================================================
# loader refuses a still-null (named-TBD) field, for every field
# ============================================================================


@pytest.mark.parametrize(
    "field",
    [
        "numerically_safe",
        "valuation_ok",
        "all_fields_attributed",
        "limit_source_is_injected_envelope",
        "economic_commitment_exclusive",
        "flow_commitment_exclusive",
    ],
)
def test_a_still_null_field_refuses_to_load(tmp_path: Path, field: str) -> None:
    raw = _valid_risk_attestations()
    raw[field]["attested"] = None
    path = tmp_path / "risk_attestations.yaml"
    _write(path, raw)
    with pytest.raises(RiskAttestationConfigError):
        load_risk_attestations(path)


def test_missing_file_refuses_to_load(tmp_path: Path) -> None:
    with pytest.raises(RiskAttestationConfigError):
        load_risk_attestations(tmp_path / "does-not-exist.yaml")


def test_a_valid_file_loads(tmp_path: Path) -> None:
    path = tmp_path / "risk_attestations.yaml"
    _write(path, _valid_risk_attestations())
    attestations = load_risk_attestations(path)
    assert attestations == RiskAttestations(
        numerically_safe=True,
        valuation_ok=True,
        all_fields_attributed=True,
        limit_source_is_injected_envelope=True,
        economic_commitment_exclusive=True,
        flow_commitment_exclusive=True,
    )


# ============================================================================
# wrap_aggregate_risk_inputs_provider: RESTRICTIVE MERGE, not an
# unconditional override (fixed 2026-09-08 -- an unconditional override was
# itself a fail-open: an attestation of True could silently flip a caller's
# own genuine False/UNKNOWN claim back to admitting).
# ============================================================================


def _aggregate_inputs_with(
    *,
    all_fields_attributed,
    numerically_safe,
    valuation_ok,
    limit_source_is_injected_envelope,
) -> AggregateRiskDecisionInputs:
    return AggregateRiskDecisionInputs(
        cells=fx.adverse_scenario_cells(),
        required_scenario_kinds=frozenset(
            {"ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"}  # type: ignore[arg-type]
        ),
        applicable_risk_scopes=("ACCOUNT",),
        all_fields_attributed=all_fields_attributed,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        numerically_safe=numerically_safe,
        valuation_ok=valuation_ok,
        injected_envelope_max=fx.aggregate_risk_effective_limit(),
        limit_source_is_injected_envelope=limit_source_is_injected_envelope,
        effective_limit=fx.aggregate_risk_effective_limit(),
    )


def _all_true_risk_attestations() -> RiskAttestations:
    return RiskAttestations(
        numerically_safe=True,
        valuation_ok=True,
        all_fields_attributed=True,
        limit_source_is_injected_envelope=True,
        economic_commitment_exclusive=True,
        flow_commitment_exclusive=True,
    )


def _all_false_risk_attestations() -> RiskAttestations:
    return RiskAttestations(
        numerically_safe=False,
        valuation_ok=False,
        all_fields_attributed=False,
        limit_source_is_injected_envelope=False,
        economic_commitment_exclusive=False,
        flow_commitment_exclusive=False,
    )


def test_aggregate_wrapper_defers_to_attestation_when_caller_has_no_opinion() -> None:
    """Caller ``None`` (only possible for the two Optional fields) or a
    caller ``True`` claim: the attestation governs."""
    wrapped = wrap_aggregate_risk_inputs_provider(
        lambda _request: _aggregate_inputs_with(
            all_fields_attributed=None,
            numerically_safe=True,
            valuation_ok=True,
            limit_source_is_injected_envelope=None,
        ),
        _all_true_risk_attestations(),
    )
    result = wrapped(None)
    assert result is not None
    assert result.all_fields_attributed is True
    assert result.numerically_safe is True
    assert result.valuation_ok is True
    assert result.limit_source_is_injected_envelope is True


def test_aggregate_wrapper_never_overrides_the_callers_own_restrictive_claim() -> None:
    """A caller's own definite non-``True`` claim (``False`` here) is NEVER
    overridden upward, even when the operator attestation is ``True`` — the
    fail-open the re-review flagged."""
    wrapped = wrap_aggregate_risk_inputs_provider(
        lambda _request: _aggregate_inputs_with(
            all_fields_attributed=False,
            numerically_safe=False,
            valuation_ok=False,
            limit_source_is_injected_envelope=False,
        ),
        _all_true_risk_attestations(),
    )
    result = wrapped(None)
    assert result is not None
    assert result.all_fields_attributed is False
    assert result.numerically_safe is False
    assert result.valuation_ok is False
    assert result.limit_source_is_injected_envelope is False


def test_aggregate_wrapper_attestation_downgrades_callers_naive_true() -> None:
    """An operator attestation of ``False`` is a real, authoritative fact —
    it downgrades a caller's bare ``True`` literal (never a stronger claim
    than the attestation itself)."""
    wrapped = wrap_aggregate_risk_inputs_provider(
        lambda _request: _aggregate_inputs_with(
            all_fields_attributed=True,
            numerically_safe=True,
            valuation_ok=True,
            limit_source_is_injected_envelope=True,
        ),
        _all_false_risk_attestations(),
    )
    result = wrapped(None)
    assert result is not None
    assert result.all_fields_attributed is False
    assert result.numerically_safe is False
    assert result.valuation_ok is False
    assert result.limit_source_is_injected_envelope is False


def test_aggregate_wrapper_passes_through_none() -> None:
    attestations = RiskAttestations(
        numerically_safe=True,
        valuation_ok=True,
        all_fields_attributed=True,
        limit_source_is_injected_envelope=True,
        economic_commitment_exclusive=True,
        flow_commitment_exclusive=True,
    )
    wrapped = wrap_aggregate_risk_inputs_provider(lambda _request: None, attestations)
    assert wrapped(None) is None


# ============================================================================
# wrap_action_flow_inputs_provider: RESTRICTIVE MERGE for the 3 attested
# fields (same fix as the aggregate wrapper above), and generation_current
# is ALWAYS derived (never attested, never the caller's literal, never
# merged).
# ============================================================================


def _action_flow_inputs_with(
    *,
    limit_source_is_injected_envelope,
    economic_commitment_exclusive,
    flow_commitment_exclusive,
    decision_generation: int = 5,
) -> ActionFlowDecisionInputs:
    return ActionFlowDecisionInputs(
        cause=None,
        snapshot=None,
        required_scopes=frozenset(),
        producer_self_declared_scope=False,
        observed_amplification=None,
        requested_limit=fx.action_flow_requested_limit(),
        injected_envelope_max=fx.action_flow_envelope_max(),
        limit_source_is_injected_envelope=limit_source_is_injected_envelope,
        economic_ref="economic-ref-test",
        flow_vector=fx.action_flow_requested_limit(),
        committed_flow_vectors=(),
        hard_limit=fx.action_flow_envelope_max(),
        runtime_limit=fx.action_flow_envelope_max(),
        economic_commitment_exclusive=economic_commitment_exclusive,
        flow_commitment_exclusive=flow_commitment_exclusive,
        generation_current=False,  # always discarded/re-derived; irrelevant here
        applicable_action_flow_scopes=("ACCOUNT",),
        decision_generation=decision_generation,
    )


def test_action_flow_wrapper_defers_to_attestation_when_caller_has_no_opinion() -> None:
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=None,
            economic_commitment_exclusive=None,
            flow_commitment_exclusive=None,
        ),
        _all_true_risk_attestations(),
        current_generation_provider=lambda _request: 5,
    )
    result = wrapped(None)
    assert result is not None
    assert result.limit_source_is_injected_envelope is True
    assert result.economic_commitment_exclusive is True
    assert result.flow_commitment_exclusive is True


def test_action_flow_wrapper_never_overrides_the_callers_own_restrictive_claim() -> (
    None
):
    """A caller's own ``False`` is NEVER overridden upward, even when the
    operator attestation is ``True`` — the fail-open the re-review flagged."""
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=False,
            economic_commitment_exclusive=False,
            flow_commitment_exclusive=False,
        ),
        _all_true_risk_attestations(),
        current_generation_provider=lambda _request: 5,
    )
    result = wrapped(None)
    assert result is not None
    assert result.limit_source_is_injected_envelope is False
    assert result.economic_commitment_exclusive is False
    assert result.flow_commitment_exclusive is False


def test_action_flow_wrapper_attestation_downgrades_callers_naive_true() -> None:
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=True,
            economic_commitment_exclusive=True,
            flow_commitment_exclusive=True,
        ),
        _all_false_risk_attestations(),
        current_generation_provider=lambda _request: 5,
    )
    result = wrapped(None)
    assert result is not None
    assert result.limit_source_is_injected_envelope is False
    assert result.economic_commitment_exclusive is False
    assert result.flow_commitment_exclusive is False


def test_action_flow_wrapper_derives_generation_current_false_on_mismatch() -> None:
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=True,
            economic_commitment_exclusive=True,
            flow_commitment_exclusive=True,
            decision_generation=5,
        ),
        _all_true_risk_attestations(),
        current_generation_provider=lambda _request: 9,
    )
    result = wrapped(None)
    assert result is not None
    assert result.generation_current is False  # 5 != 9, generation_fenced fails


def test_action_flow_wrapper_derives_generation_current_true_on_match() -> None:
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=True,
            economic_commitment_exclusive=True,
            flow_commitment_exclusive=True,
            decision_generation=5,
        ),
        _all_true_risk_attestations(),
        current_generation_provider=lambda _request: 5,
    )
    result = wrapped(None)
    assert result is not None
    assert result.generation_current is True  # 5 == 5, generation_fenced holds


def test_action_flow_wrapper_maps_stale_epoch_read_to_none() -> None:
    def _raise(_request: object) -> int:
        raise StaleEpochRead("stale for test")

    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: _action_flow_inputs_with(
            limit_source_is_injected_envelope=True,
            economic_commitment_exclusive=True,
            flow_commitment_exclusive=True,
        ),
        _all_true_risk_attestations(),
        current_generation_provider=_raise,
    )
    assert wrapped(None) is None


def test_action_flow_wrapper_passes_through_none() -> None:
    wrapped = wrap_action_flow_inputs_provider(
        lambda _request: None,
        _all_true_risk_attestations(),
        current_generation_provider=lambda _request: 1,
    )
    assert wrapped(None) is None
