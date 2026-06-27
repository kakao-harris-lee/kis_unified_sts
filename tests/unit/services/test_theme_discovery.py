from __future__ import annotations

import importlib
import json
import sys
import types
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass(frozen=True)
class _FakeThemeScoreInput:
    relative_strength: float = 0.0
    trading_value_score: float = 0.0
    volume_surge_score: float = 0.0
    catalyst_score: float = 0.0
    theme_breadth_score: float = 0.0
    intraday_persistence: float = 0.0
    freshness_score: float = 0.0
    market_signal_count: int = 0
    catalyst_signal_count: int = 0
    risk_flags: list[str] | None = None


def _fake_classify_theme_candidate(score_input: _FakeThemeScoreInput):
    risk_flags = set(score_input.risk_flags or [])
    hard_blocked = bool(risk_flags & {"investment_warning", "trading_halt"})
    leader_score = round(
        min(
            1.0,
            0.55 * float(score_input.relative_strength)
            + 0.20 * float(score_input.trading_value_score)
            + 0.15 * float(score_input.catalyst_score)
            + 0.10 * float(score_input.theme_breadth_score),
        ),
        6,
    )
    if hard_blocked:
        state = "quarantine"
    elif leader_score >= 0.70 and score_input.catalyst_signal_count > 0:
        state = "active"
    else:
        state = "watch"
    return SimpleNamespace(
        leader_score=leader_score,
        state=state,
        hard_blocked=hard_blocked,
        risk_penalty=1.0 if hard_blocked else 0.0,
    )


def _load_theme_discovery(monkeypatch: pytest.MonkeyPatch):
    import shared

    theme_pkg = types.ModuleType("shared.theme_universe")
    scoring_mod = types.ModuleType("shared.theme_universe.scoring")
    scoring_mod.ThemeScoreInput = _FakeThemeScoreInput
    scoring_mod.classify_theme_candidate = _fake_classify_theme_candidate
    theme_pkg.scoring = scoring_mod

    monkeypatch.setitem(sys.modules, "shared.theme_universe", theme_pkg)
    monkeypatch.setitem(sys.modules, "shared.theme_universe.scoring", scoring_mod)
    monkeypatch.setattr(shared, "theme_universe", theme_pkg, raising=False)
    sys.modules.pop("services.theme_discovery", None)
    return importlib.import_module("services.theme_discovery")


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int | None]] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        return True


class FakePublisher:
    def __init__(self, stream_name: str) -> None:
        self.stream_name = stream_name
        self.published: list[dict[str, Any]] = []

    def publish(self, payload: dict[str, Any]) -> str:
        self.published.append(payload)
        return "0-1"


def _service(module, redis: FakeRedis):
    publisher = FakePublisher("system:theme_targets")
    config = module.ThemeDiscoveryConfig(
        redis_keys={
            "universe": "system:universe:latest",
            "themes_latest": "system:themes:latest",
            "targets_latest": "system:theme_targets:latest",
            "targets_stream": "system:theme_targets",
        },
        ttl_seconds=321,
        top_n=10,
        thresholds={
            "theme_breadth_full_count": 2,
            "keyword_catalyst_score": 0.9,
            "default_intraday_persistence": 0.6,
        },
        keyword_themes={
            "ai_hbm": {
                "label": "AI HBM",
                "keywords": ["ai", "hbm", "memory"],
            },
            "ai_power_infra": {
                "label": "AI Power Infra",
                "keywords": ["data center", "power", "transformer"],
            },
            "shipbuilding_defense": {
                "label": "Shipbuilding Defense",
                "keywords": ["shipbuilding", "defense"],
            },
            "physical_ai": {
                "label": "Physical AI",
                "keywords": ["robot", "physical ai"],
            },
        },
    )
    return module.ThemeDiscoveryService(
        config,
        redis_client=redis,
        publisher=publisher,
    ), publisher


def test_run_once_publishes_theme_targets_and_theme_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_theme_discovery(monkeypatch)
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "generated_at": "2026-06-27T09:00:00",
            "codes": ["000660", "034020", "010140", "999999"],
            "scores": {
                "000660": 0.95,
                "034020": 0.82,
                "010140": 0.91,
                "999999": 0.20,
            },
            "names": {
                "000660": "SK Hynix HBM AI memory",
                "034020": "AI data center power transformer",
                "010140": "Shipbuilding defense leader",
                "999999": "Unrelated commerce",
            },
            "metadata": {
                "000660": {
                    "source_hits": ["volume_power"],
                    "volume_power": 80,
                    "note": "HBM capacity expansion",
                },
                "034020": {"sector": "power grid for data center"},
                "010140": {"risk_flags": ["investment_warning"]},
                "999999": {"note": "no theme"},
            },
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    assert target_payload["generated_at"]
    assert target_payload["source"]["universe_key"] == "system:universe:latest"
    assert target_payload["codes"] == ["000660", "034020"]
    assert target_payload["names"]["000660"] == "SK Hynix HBM AI memory"
    assert target_payload["scores"]["000660"] >= target_payload["scores"]["034020"]
    assert target_payload["themes"]["000660"] == ["ai_hbm"]
    assert target_payload["themes"]["034020"] == ["ai_power_infra"]
    assert target_payload["metadata"]["000660"]["note"] == "HBM capacity expansion"
    assert target_payload["metadata"]["000660"]["theme_state"] == "active"
    assert target_payload["metadata"]["010140"]["theme_state"] == "quarantine"
    assert target_payload["state_counts"] == {
        "active": 2,
        "watch": 0,
        "quarantine": 1,
    }
    assert target_payload["quarantined_codes"] == ["010140"]

    theme_payload = json.loads(redis.values["system:themes:latest"])
    assert theme_payload["themes"]["ai_hbm"]["codes"] == ["000660"]
    assert theme_payload["themes"]["shipbuilding_defense"]["quarantined_codes"] == [
        "010140"
    ]

    assert publisher.stream_name == "system:theme_targets"
    assert publisher.published == [target_payload]
    assert {call[0]: call[2] for call in redis.set_calls} == {
        "system:themes:latest": 321,
        "system:theme_targets:latest": 321,
    }


def test_malformed_json_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_theme_discovery(monkeypatch)
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    redis.values["system:universe:latest"] = "{not json"

    assert service.run_once() is False
    assert redis.set_calls == []
    assert publisher.published == []


def test_malformed_optional_fields_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_theme_discovery(monkeypatch)
    redis = FakeRedis()
    service, _publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "codes": ["000660"],
            "scores": ["bad"],
            "names": {"000660": "HBM AI platform"},
            "metadata": {"000660": ["bad"]},
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    assert target_payload["codes"] == ["000660"]
    assert 0.0 < target_payload["scores"]["000660"] <= 1.0
    assert target_payload["metadata"]["000660"]["screener_score"] == 1.0
    assert target_payload["metadata"]["000660"]["matched_themes"] == ["ai_hbm"]


def test_watch_active_and_quarantine_states_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_theme_discovery(monkeypatch)
    redis = FakeRedis()
    service, _publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "codes": ["A1", "W1", "Q1"],
            "scores": {"A1": 0.95, "W1": 0.35, "Q1": 0.95},
            "names": {
                "A1": "HBM AI memory leader",
                "W1": "Physical AI robot component",
                "Q1": "Shipbuilding defense leader",
            },
            "metadata": {
                "A1": {},
                "W1": {},
                "Q1": {"risk_flags": ["trading_halt"]},
            },
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    assert target_payload["codes"] == ["A1", "W1"]
    assert target_payload["metadata"]["A1"]["theme_state"] == "active"
    assert target_payload["metadata"]["W1"]["theme_state"] == "watch"
    assert target_payload["metadata"]["Q1"]["theme_state"] == "quarantine"
    assert target_payload["state_counts"] == {
        "active": 1,
        "watch": 1,
        "quarantine": 1,
    }


def test_default_yaml_loads_required_keyword_themes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_theme_discovery(monkeypatch)

    config = module.ThemeDiscoveryConfig.from_yaml()

    assert config.redis_keys["universe"] == "system:universe:latest"
    assert config.redis_keys["targets_stream"] == "system:theme_targets"
    assert config.interval_seconds > 0
    assert config.ttl_seconds > 0
    assert config.top_n > 0
    assert {
        "ai_hbm",
        "ai_power_infra",
        "shipbuilding_defense",
        "physical_ai",
    }.issubset(config.keyword_themes)
