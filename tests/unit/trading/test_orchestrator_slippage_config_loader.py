"""Characterization tests — F-9 Gate 1b control-parity closure §2-A.

Pins that ``TradingOrchestrator._init_futures_slippage_controller`` (after
being refactored to call the new shared
``shared.execution.slippage_control.load_futures_slippage_config`` helper)
produces byte-identical ``SlippageControlConfig`` values to the pre-refactor
inline logic that lived in the orchestrator (config-dict pop + deep-merge of
``paper_override`` only when ``paper_trading`` and the override's own
``enabled`` flag are both true).

The pre-refactor algorithm is duplicated here independently (not imported
from the shared module) so this test is not tautological — if the shared
loader ever silently changed behavior, this would catch the drift against
the real ``config/execution.yaml``.
"""

from __future__ import annotations

from typing import Any

import pytest

from shared.config.loader import ConfigLoader
from shared.execution.slippage_control import (
    SlippageControlConfig,
    load_futures_slippage_config,
)


def _legacy_deep_merge(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _legacy_deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _legacy_load(exec_cfg: dict, *, paper_trading: bool) -> SlippageControlConfig:
    """Pre-refactor orchestrator inline logic (services/trading/orchestrator.py
    ``_init_futures_slippage_controller``, before this arc's refactor)."""
    raw = exec_cfg.get("futures_slippage_control", {})
    raw = {} if not isinstance(raw, dict) else dict(raw)

    paper_override = raw.pop("paper_override", None)
    if paper_trading and isinstance(paper_override, dict):
        if bool(paper_override.get("enabled", False)):
            override_payload = {
                k: v for k, v in paper_override.items() if k != "enabled"
            }
            raw = _legacy_deep_merge(raw, override_payload)

    return SlippageControlConfig.from_dict(raw)


@pytest.mark.parametrize("paper_trading", [True, False])
def test_loader_matches_legacy_inline_logic_against_real_yaml(paper_trading):
    exec_cfg = ConfigLoader.load("execution.yaml")

    expected = _legacy_load(exec_cfg, paper_trading=paper_trading)
    actual = load_futures_slippage_config(exec_cfg, paper_trading=paper_trading)

    assert actual == expected


@pytest.mark.parametrize("paper_trading", [True, False])
def test_orchestrator_init_wires_controller_matching_the_shared_loader(paper_trading):
    """The orchestrator's post-refactor `_init_futures_slippage_controller`
    must wire a controller whose config equals what the shared loader
    produces for the same YAML + paper_trading flag."""
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
    config.paper_trading = paper_trading
    orch = TradingOrchestrator(config)

    orch._init_futures_slippage_controller()

    expected = load_futures_slippage_config(
        ConfigLoader.load("execution.yaml"), paper_trading=paper_trading
    )
    assert orch._futures_slippage_controller is not None
    assert orch._futures_slippage_controller.config == expected


def test_orchestrator_init_disables_controller_on_bad_coercion_value(monkeypatch):
    """Regression (review 2026-09-07): a malformed numeric override (e.g. the
    real-world ``FUTURES_PAPER_MAX_SPREAD_TICKS=six`` case) must be
    warn-and-disable, exactly like the pre-refactor inline logic — not an
    exception that propagates out of ``run_trading_startup_sequence`` and
    kills ``trader-futures`` at boot.

    Collapsing the merge step and ``SlippageControlConfig.from_dict``'s
    ``int()``/``float()`` coercion into one function (the first cut of the
    §2-A refactor) put both under the orchestrator's *first* ``try``, which
    only catches config-*load* errors (``InvalidConfigError`` etc.) — a
    coercion ``ValueError`` then escaped uncaught. The fix splits the loader
    into ``load_futures_slippage_raw`` (merge only, used under the first
    ``try``) + ``SlippageControlConfig.from_dict`` (called under the second
    ``try``, which already catches ``ValueError``/``TypeError``).
    """
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    bad_cfg = {
        "futures_slippage_control": {
            "enabled": True,
            "max_spread_ticks": "six",  # int("six") -> ValueError
        }
    }
    monkeypatch.setattr(ConfigLoader, "load", lambda *args, **kwargs: bad_cfg)

    config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
    config.paper_trading = True
    orch = TradingOrchestrator(config)

    orch._init_futures_slippage_controller()  # must not raise

    assert orch._futures_slippage_controller is None
