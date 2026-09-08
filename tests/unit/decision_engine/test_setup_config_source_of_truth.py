"""One source of truth for Setup A/C/D parameters: the strategy YAML files.

Background (plan 2026-09-08-setup-d-decoupled-port §0-2). Three copies of the
Setup A/C/D parameters existed at once and all three disagreed:

  1. the Pydantic field defaults on ``SetupAConfig`` / ``SetupCConfig`` /
     ``SetupDConfig`` — what the decoupled decision_engine daemon ACTUALLY ran,
     because it constructed ``Setup*()`` with no config;
  2. ``config/decision_engine.yaml``'s ``setup_*`` sections — dead config that
     no code loaded; and
  3. ``config/strategies/futures/<name>.yaml`` ``strategy.entry.params`` — the
     values the monolithic orchestrator's Setup adapters ran in paper.

The fix pointed the core configs' ``_default_config_file`` / ``_default_section``
at (3) and deleted (2). These tests keep it that way: a new core field that is
not represented in the strategy YAML, or a resurrected ``decision_engine.yaml``
setup section, fails here rather than silently reintroducing a second operating
point.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
STRATEGIES_DIR = CONFIG_DIR / "strategies" / "futures"

_CASES = [
    (SetupAGapReversion, SetupAConfig),
    (SetupCEventReaction, SetupCConfig),
    (SetupDVWAPReversion, SetupDConfig),
]

#: Core config fields deliberately NOT required in the strategy YAML.
#: Empty today: every field of all three configs is present in its strategy
#: file. Adding a name here is an explicit decision that the field is
#: default-only, not a way to silence this test.
_CORE_ONLY_FIELDS: dict[str, frozenset[str]] = {}


def _entry_params(registry_name: str) -> dict:
    document = yaml.safe_load(
        (STRATEGIES_DIR / f"{registry_name}.yaml").read_text(encoding="utf-8")
    )
    return document["strategy"]["entry"]["params"]


@pytest.mark.parametrize("setup_cls, config_cls", _CASES, ids=lambda c: c.__name__)
def test_core_config_points_at_the_strategy_yaml(setup_cls, config_cls) -> None:
    """The no-arg ``from_yaml()`` must resolve the deployed strategy file.

    ``SetupCConfig.from_yaml()`` is called with no arguments by
    ``services/dashboard/routes/event_context.py`` and
    ``scripts/walk_forward_phase3.py``; those call sites must land on the same
    parameters the runtime uses.
    """
    assert (
        config_cls._default_config_file
        == f"strategies/futures/{setup_cls.REGISTRY_NAME}.yaml"
    )
    assert config_cls._default_section == "strategy.entry.params"


@pytest.mark.parametrize("setup_cls, config_cls", _CASES, ids=lambda c: c.__name__)
def test_every_core_field_is_present_in_the_strategy_yaml(
    setup_cls, config_cls
) -> None:
    """Drift guard: a core field absent from the YAML would run on its default."""
    params = _entry_params(setup_cls.REGISTRY_NAME)
    allowed = _CORE_ONLY_FIELDS.get(setup_cls.REGISTRY_NAME, frozenset())
    missing = sorted(set(config_cls.model_fields) - set(params) - set(allowed))
    assert not missing, (
        f"{config_cls.__name__} fields missing from "
        f"config/strategies/futures/{setup_cls.REGISTRY_NAME}.yaml "
        f"strategy.entry.params: {missing}. Add them to the YAML (preferred) or "
        "record them in _CORE_ONLY_FIELDS with a reason — otherwise the runtime "
        "silently runs a Pydantic default nobody reviewed."
    )


@pytest.mark.parametrize("setup_cls, config_cls", _CASES, ids=lambda c: c.__name__)
def test_loaded_values_equal_the_strategy_yaml_values(setup_cls, config_cls) -> None:
    """Loaded config == YAML, field by field (not just 'the file resolved')."""
    params = _entry_params(setup_cls.REGISTRY_NAME)
    loaded = config_cls.from_yaml().model_dump()
    for field, value in sorted(params.items()):
        if field not in loaded:
            continue  # adapter-only key (llm_tuning, regime_gate, ...) — ignored
        assert loaded[field] == value, f"{setup_cls.REGISTRY_NAME}.{field}"


def test_deployed_values_differ_from_the_pydantic_defaults() -> None:
    """The YAML operating point is materially different from the bare defaults.

    If this ever stops being true the drift is gone, but so is the evidence that
    the daemon reads YAML at all — these three were the largest disagreements
    measured on 2026-09-08 and they are what the port fixed.
    """
    assert (
        SetupAConfig.from_yaml().stop_atr_mult
        == _entry_params("setup_a_gap_reversion")["stop_atr_mult"]
    )
    assert SetupAConfig.from_yaml().stop_atr_mult != SetupAConfig().stop_atr_mult

    assert (
        SetupDConfig.from_yaml().min_confidence
        == _entry_params("setup_d_vwap_reversion")["min_confidence"]
    )
    assert SetupDConfig.from_yaml().min_confidence != SetupDConfig().min_confidence

    assert (
        SetupDConfig.from_yaml().reversal_confirm_enabled
        is not SetupDConfig().reversal_confirm_enabled
    )


def test_decision_engine_yaml_holds_no_setup_parameter_sections() -> None:
    """The dead config is gone and must not come back.

    ``market_risk_gate`` stays — it is this daemon's own consumer-side wiring
    and is loaded by ``services/decision_engine/config.py``.
    """
    document = yaml.safe_load(
        (CONFIG_DIR / "decision_engine.yaml").read_text(encoding="utf-8")
    )
    resurrected = sorted(
        setup_cls.REGISTRY_NAME
        for setup_cls, _ in _CASES
        if setup_cls.REGISTRY_NAME in document
    )
    assert not resurrected, (
        f"config/decision_engine.yaml has setup parameter sections again: "
        f"{resurrected}. Setup parameters live in config/strategies/futures/*.yaml "
        "(strategy.entry.params) — a second copy here is unread and drifts."
    )
    assert "market_risk_gate" in document
