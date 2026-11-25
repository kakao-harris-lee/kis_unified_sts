"""Operator-attested step 6/7 admission witnesses with no Phase 2 producer"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from tos.afg import generation_fenced
from tos.engine import StageRequest

from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs

__all__ = [
    "RiskAttestationConfigError",
    "RiskAttestations",
    "load_risk_attestations",
    "wrap_aggregate_risk_inputs_provider",
    "wrap_action_flow_inputs_provider",
]

_FIELDS: tuple[str, ...] = (
    "numerically_safe",
    "valuation_ok",
    "all_fields_attributed",
    "limit_source_is_injected_envelope",
    "economic_commitment_exclusive",
    "flow_commitment_exclusive",
)


class RiskAttestationConfigError(Exception):
    """Raised when the risk-attestations config is missing, malformed, or"""


@dataclass(frozen=True)
class RiskAttestations:
    """The six operator-attested step 6/7 admission witnesses (module"""

    numerically_safe: bool
    valuation_ok: bool
    all_fields_attributed: bool
    limit_source_is_injected_envelope: bool
    economic_commitment_exclusive: bool
    flow_commitment_exclusive: bool


def _require_bool(raw: Any, field: str, path: Path) -> bool:
    block = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise RiskAttestationConfigError(
            f"{path}: risk-attestations config missing a mapping entry "
            f"for {field!r} — refusing to start"
        )
    value = block.get("attested")
    if not isinstance(value, bool):
        raise RiskAttestationConfigError(
            f"{path}: {field!r}.attested is still null (named-TBD) or not a "
            "bool — refusing to start until an operator attests a concrete "
            "value"
        )
    return value


def load_risk_attestations(path: Path) -> RiskAttestations:
    """Load + fail-closed-validate the six operator-attested step 6/7"""
    if not path.is_file():
        raise RiskAttestationConfigError(
            f"risk-attestations config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RiskAttestationConfigError(
            f"risk-attestations config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RiskAttestationConfigError(
            f"risk-attestations config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise RiskAttestationConfigError(
            f"risk-attestations config file must be a top-level mapping: {path}"
        )
    values = {field: _require_bool(raw, field, path) for field in _FIELDS}
    return RiskAttestations(**values)


def _restrictive_merge(caller_value: Any, attested_value: bool) -> Any:
    """The more restrictive of a caller's own claim and the operator"""
    if caller_value is None or caller_value is True:
        return attested_value
    return caller_value


def wrap_aggregate_risk_inputs_provider(
    provider: Callable[[StageRequest], AggregateRiskDecisionInputs | None],
    attestations: RiskAttestations,
) -> Callable[[StageRequest], AggregateRiskDecisionInputs | None]:
    """Wrap a caller-supplied step 6 inputs provider: the four attested"""

    def _wrapped(request: StageRequest) -> AggregateRiskDecisionInputs | None:
        inputs = provider(request)
        if inputs is None:
            return None
        return replace(
            inputs,
            numerically_safe=_restrictive_merge(
                inputs.numerically_safe, attestations.numerically_safe
            ),
            valuation_ok=_restrictive_merge(
                inputs.valuation_ok, attestations.valuation_ok
            ),
            all_fields_attributed=_restrictive_merge(
                inputs.all_fields_attributed, attestations.all_fields_attributed
            ),
            limit_source_is_injected_envelope=_restrictive_merge(
                inputs.limit_source_is_injected_envelope,
                attestations.limit_source_is_injected_envelope,
            ),
        )

    return _wrapped


def wrap_action_flow_inputs_provider(
    provider: Callable[[StageRequest], ActionFlowDecisionInputs | None],
    attestations: RiskAttestations,
    current_generation_provider: Callable[[StageRequest], int],
) -> Callable[[StageRequest], ActionFlowDecisionInputs | None]:
    """Wrap a caller-supplied step 7 inputs provider: three fields are"""

    def _wrapped(request: StageRequest) -> ActionFlowDecisionInputs | None:
        inputs = provider(request)
        if inputs is None:
            return None
        try:
            current_generation = current_generation_provider(request)
        except (StaleEpochRead, sqlite3.Error, OSError):
            return None
        return replace(
            inputs,
            limit_source_is_injected_envelope=_restrictive_merge(
                inputs.limit_source_is_injected_envelope,
                attestations.limit_source_is_injected_envelope,
            ),
            economic_commitment_exclusive=_restrictive_merge(
                inputs.economic_commitment_exclusive,
                attestations.economic_commitment_exclusive,
            ),
            flow_commitment_exclusive=_restrictive_merge(
                inputs.flow_commitment_exclusive,
                attestations.flow_commitment_exclusive,
            ),
            generation_current=generation_fenced(
                inputs.decision_generation, current_generation
            ),
        )

    return _wrapped
