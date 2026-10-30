"""Late-bound step 6/7 input providers backed by the runtime risk-state service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.engine import StageRequest

from tos_runtime.compose._types import RiskStateConfigError
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.risk.ledger_stages import CloseProofCommitFence
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
)
from tos_runtime.riskstate.service import RiskStateService


@dataclass
class RiskStateProviders:
    """The shared service cell and the three callbacks that close over it."""

    files_exist: bool
    cell: dict[str, RiskStateService | None]
    aggregate_inputs: Callable[[StageRequest], AggregateRiskDecisionInputs | None]
    action_flow_inputs: Callable[[StageRequest], ActionFlowDecisionInputs | None]
    close_fence: Callable[[StageRequest], CloseProofCommitFence | None]


def build_risk_state_providers(
    *,
    config_dir: Path,
    aggregate_risk_inputs_provider: (
        Callable[[StageRequest], AggregateRiskDecisionInputs | None] | None
    ),
    action_flow_inputs_provider: (
        Callable[[StageRequest], ActionFlowDecisionInputs | None] | None
    ),
) -> RiskStateProviders:
    """Build caller-preserving providers over one late-bound service cell.

    A missing pair of governed policy files is allowed only when both input
    callbacks are supplied explicitly; otherwise boot must refuse rather than
    run with permanently UNKNOWN step 6/7 decisions.
    """
    risk_state_files_exist = (
        config_dir / AGGREGATE_RISK_POLICY_CONFIG_NAME
    ).is_file() and (config_dir / ACTION_FLOW_POLICY_CONFIG_NAME).is_file()
    if not risk_state_files_exist and (
        aggregate_risk_inputs_provider is None or action_flow_inputs_provider is None
    ):
        raise RiskStateConfigError(
            f"{config_dir}: aggregate_risk_policy.yaml/action_flow_policy.yaml are not both "
            "present, and at least one of aggregate_risk_inputs_provider/"
            "action_flow_inputs_provider was left None — refusing to boot with a permanently "
            "UNKNOWN step 6/7 (TOS risk state service wave plan §3)"
        )

    risk_state_cell: dict[str, RiskStateService | None] = {"service": None}

    def _aggregate_provider(
        request: StageRequest,
    ) -> AggregateRiskDecisionInputs | None:
        if aggregate_risk_inputs_provider is not None:
            return aggregate_risk_inputs_provider(request)
        service = risk_state_cell["service"]
        return None if service is None else service.aggregate_inputs_for(request)

    def _action_flow_provider(request: StageRequest) -> ActionFlowDecisionInputs | None:
        if action_flow_inputs_provider is not None:
            return action_flow_inputs_provider(request)
        service = risk_state_cell["service"]
        return None if service is None else service.action_flow_inputs_for(request)

    def _close_fence_provider(request: StageRequest) -> CloseProofCommitFence | None:
        service = risk_state_cell["service"]
        return None if service is None else service.take_close_fence(request)

    return RiskStateProviders(
        files_exist=risk_state_files_exist,
        cell=risk_state_cell,
        aggregate_inputs=_aggregate_provider,
        action_flow_inputs=_action_flow_provider,
        close_fence=_close_fence_provider,
    )
