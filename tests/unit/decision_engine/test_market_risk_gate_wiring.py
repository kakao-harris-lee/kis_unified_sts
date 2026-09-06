"""Tests for services.decision_engine.config.DecisionEngineMarketRiskGateWiring.

O14-③ (roadmap §8 follow-up): the futures decision_engine's shadow-gate log
interval was a ctor-only default with no YAML key and no config-driven wiring
(CLAUDE.md non-negotiable: thresholds/intervals live in YAML, not hardcoded
branches). This mirrors the stock-side
``services/stock_strategy/market_risk.py::MarketRiskGateWiringConfig``
pattern: load once at startup, defaults on any YAML problem, never blocks
daemon construction.
"""

from __future__ import annotations

from pathlib import Path

import fakeredis
import fakeredis.aioredis

from services.decision_engine.config import DecisionEngineMarketRiskGateWiring
from services.decision_engine.main import _build_daemon

REPO_ROOT = Path(__file__).resolve().parents[3]
DECISION_ENGINE_YAML = REPO_ROOT / "config" / "decision_engine.yaml"


def test_default_matches_the_prior_ctor_hardcoded_value():
    config = DecisionEngineMarketRiskGateWiring()
    assert config.would_block_log_interval_seconds == 300.0


def test_loads_the_shipped_yaml_section():
    config = DecisionEngineMarketRiskGateWiring.from_yaml(str(DECISION_ENGINE_YAML))
    assert config.would_block_log_interval_seconds == 300.0


def test_load_or_default_falls_back_when_yaml_absent(tmp_path):
    config = DecisionEngineMarketRiskGateWiring.load_or_default(
        str(tmp_path / "absent.yaml")
    )
    assert config.would_block_log_interval_seconds == 300.0


def test_load_or_default_reads_a_custom_interval(tmp_path):
    custom_yaml = tmp_path / "decision_engine.yaml"
    custom_yaml.write_text(
        "market_risk_gate:\n  would_block_log_interval_seconds: 45.0\n"
    )
    config = DecisionEngineMarketRiskGateWiring.load_or_default(str(custom_yaml))
    assert config.would_block_log_interval_seconds == 45.0


# ---------------------------------------------------------------------------
# O14-③ (review finding 4): end-to-end wiring — _build_and_run's construction
# seam, extracted into _build_daemon, must actually carry the loaded wiring
# config's interval into the daemon's throttle. Deleting the
# ``shadow_gate_log_interval_seconds=`` argument at the call site left every
# prior test green; this test fails if that argument (or the load call
# feeding it) is ever dropped again.
# ---------------------------------------------------------------------------


def test_build_daemon_carries_the_loaded_wiring_interval_into_the_throttle(
    monkeypatch,
):
    monkeypatch.setattr(
        DecisionEngineMarketRiskGateWiring,
        "load_or_default",
        classmethod(lambda cls: cls(would_block_log_interval_seconds=77.0)),
    )

    async def _stub_context_provider():
        return None

    daemon = _build_daemon(
        redis_client=fakeredis.aioredis.FakeRedis(db=1),
        setups=[],
        context_provider=_stub_context_provider,
        candidate_stream="signal.candidate.futures",
        market_risk_redis=fakeredis.FakeRedis(db=1, decode_responses=True),
        volatility_publisher=None,
    )

    assert daemon._shadow_gate_log_throttle.interval_seconds == 77.0
