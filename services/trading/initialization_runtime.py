"""Initialization owner helpers for trading orchestrator compatibility runtime."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionLayerInputs:
    asset_class: str
    use_real_broker: bool
    futures_live_enabled: bool


def execution_layer_mode(inputs: ExecutionLayerInputs) -> str:
    """Return the execution layer mode label without constructing dependencies."""
    if inputs.asset_class == "futures" and inputs.futures_live_enabled:
        return "futures_live"
    if inputs.use_real_broker:
        return "real_broker"
    return "paper"


def should_require_futures_contract_validation(asset_class: str) -> bool:
    """Return true when startup/real-entry paths need futures contract validation."""
    return asset_class == "futures"
