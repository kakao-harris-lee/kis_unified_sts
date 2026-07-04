"""Compatibility facade for futures setup entry adapters.

The adapter classes live in focused owner modules:

* :mod:`shared.strategy.entry.setup_a_adapter`
* :mod:`shared.strategy.entry.setup_c_adapter`
* :mod:`shared.strategy.entry.setup_d_adapter`

This module preserves the historical import surface and private monkeypatch
hooks used by existing tests and operator tooling.
"""

from __future__ import annotations

import logging
import os

from shared.decision.daily_bias import DailyBiasProvider
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry import setup_eval_publisher as _setup_eval_publisher
from shared.strategy.entry.setup_a_adapter import SetupAEntryAdapter
from shared.strategy.entry.setup_c_adapter import SetupCEntryAdapter
from shared.strategy.entry.setup_context_builder import build_setup_market_context
from shared.strategy.entry.setup_d_adapter import SetupDEntryAdapter
from shared.strategy.entry.setup_entry_configs import (
    LLMTuningConfig,
    SetupAEntryConfig,
    SetupAForecastIntegrationConfig,
    SetupCEntryConfig,
    SetupCForecastIntegrationConfig,
    SetupDEntryConfig,
)
from shared.strategy.entry.setup_llm_gate import (
    apply_llm_tuning_setup_a,
    apply_llm_tuning_setup_c,
    apply_llm_veto,
    get_llm_context,
    normalise_regime_label,
    resolve_regime_label,
    send_veto_alert_background,
)
from shared.strategy.entry.setup_signal_mapper import (
    decision_signal_to_orchestrator_signal,
)
from shared.strategy.gates.adapter_helper import (
    acquire_infra_clients,
    apply_regime_gate,
)
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy.market_time import now_kst

logger = logging.getLogger(__name__)

__all__ = [
    "DailyBiasProvider",
    "EntryContext",
    "EntrySignalGenerator",
    "GateConfig",
    "LLMTuningConfig",
    "SetupAEntryAdapter",
    "SetupAEntryConfig",
    "SetupAForecastIntegrationConfig",
    "SetupCEntryAdapter",
    "SetupCEntryConfig",
    "SetupCForecastIntegrationConfig",
    "SetupDEntryAdapter",
    "SetupDEntryConfig",
]

# ---------------------------------------------------------------------------
# Extracted helper compatibility aliases
# ---------------------------------------------------------------------------

_build_market_context = build_setup_market_context
_decision_signal_to_orchestrator_signal = decision_signal_to_orchestrator_signal

# Compatibility facade attribute used by existing tests/operator monkeypatches.
_apply_regime_gate_compat = apply_regime_gate

# ---------------------------------------------------------------------------
# LLM helper compatibility aliases
# ---------------------------------------------------------------------------

_get_llm_context = get_llm_context
_normalise_regime_label = normalise_regime_label
_resolve_regime_label = resolve_regime_label
_apply_llm_tuning_setup_a = apply_llm_tuning_setup_a
_apply_llm_tuning_setup_c = apply_llm_tuning_setup_c
_apply_llm_veto = apply_llm_veto
_send_veto_alert_background = send_veto_alert_background

# ---------------------------------------------------------------------------
# Setup-eval publisher compatibility wrappers
# ---------------------------------------------------------------------------

SETUP_EVAL_KEY = _setup_eval_publisher.SETUP_EVAL_KEY
SETUP_EVAL_HISTORY_KEY_PREFIX = _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX
SETUP_EVAL_HISTORY_TTL_SECONDS = _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS
SETUP_EVAL_HISTORY_ENABLED = _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED
_last_eval_log = _setup_eval_publisher._last_eval_log
_history_state = _setup_eval_publisher._history_state
_is_in_window_eval = _setup_eval_publisher.is_in_window_eval
_append_setup_eval_history = _setup_eval_publisher.append_setup_eval_history


def _publish_setup_eval(name: str, outcome: str, reason: str) -> None:
    """Compatibility wrapper for setup evaluation publishing.

    Existing tests and operators monkeypatch this module's infrastructure hooks,
    so pass those hooks into the extracted publisher instead of calling it as a
    direct alias.
    """
    _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX = os.environ.get(
        "SETUP_EVAL_HISTORY_KEY_PREFIX",
        _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX,
    )
    _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS = int(
        os.environ.get(
            "SETUP_EVAL_HISTORY_TTL_SECONDS",
            str(_setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS),
        )
    )
    _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED = os.environ.get(
        "SETUP_EVAL_HISTORY_ENABLED", "true"
    ).strip().lower() not in {"0", "false", "no", "off"}
    globals()[
        "SETUP_EVAL_HISTORY_KEY_PREFIX"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_KEY_PREFIX
    globals()[
        "SETUP_EVAL_HISTORY_TTL_SECONDS"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_TTL_SECONDS
    globals()[
        "SETUP_EVAL_HISTORY_ENABLED"
    ] = _setup_eval_publisher.SETUP_EVAL_HISTORY_ENABLED
    _setup_eval_publisher.publish_setup_eval(
        name,
        outcome,
        reason,
        acquire_clients=acquire_infra_clients,
        now_fn=now_kst,
        log=logger,
    )
