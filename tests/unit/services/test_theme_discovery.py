from __future__ import annotations

import importlib
import json
from datetime import datetime, timedelta
from typing import Any


def _load_theme_discovery():
    from services import theme_discovery

    return importlib.reload(theme_discovery)


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
    return (
        module.ThemeDiscoveryService(
            config,
            redis_client=redis,
            publisher=publisher,
        ),
        publisher,
    )


def test_run_once_publishes_theme_targets_and_theme_summary() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "generated_at": datetime.now().isoformat(),
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
    assert target_payload["metadata"]["000660"]["state"] == "active"
    assert (
        target_payload["metadata"]["000660"]["leader_score"]
        == target_payload["scores"]["000660"]
    )
    assert target_payload["metadata"]["000660"]["theme_id"] == "ai_hbm"
    assert target_payload["metadata"]["000660"]["theme_label"] == "AI HBM"
    assert target_payload["metadata"]["000660"]["theme_state"] == "active"
    assert target_payload["metadata"]["034020"]["state"] == "watch"
    assert target_payload["metadata"]["034020"]["theme_state"] == "watch"
    assert target_payload["metadata"]["010140"]["state"] == "quarantine"
    assert target_payload["metadata"]["010140"]["theme_state"] == "quarantine"
    assert target_payload["state_counts"] == {
        "active": 1,
        "watch": 1,
        "quarantine": 1,
    }
    assert target_payload["quarantined_codes"] == ["010140"]
    assert target_payload["theme_catalog"]["ai_hbm"]["label"] == "AI HBM"

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


def test_malformed_json_is_tolerated() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    redis.values["system:universe:latest"] = "{not json"

    assert service.run_once() is False
    assert redis.set_calls == []
    assert publisher.published == []


def test_run_once_publishes_empty_snapshot_when_no_themes_match() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "generated_at": "2026-06-27T09:00:00",
            "codes": ["999999"],
            "scores": {"999999": 0.8},
            "names": {"999999": "Unrelated commerce"},
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    assert target_payload["codes"] == []
    assert target_payload["scores"] == {}
    assert target_payload["metadata"] == {}
    assert target_payload["themes"] == {}
    assert target_payload["state_counts"] == {
        "active": 0,
        "watch": 0,
        "quarantine": 0,
    }
    assert target_payload["source"]["matched_count"] == 0
    assert target_payload["theme_catalog"]["ai_hbm"]["label"] == "AI HBM"
    assert publisher.published == [target_payload]


def test_run_once_publishes_empty_snapshot_when_universe_is_stale() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, publisher = _service(module, redis)
    service.config.max_universe_age_seconds = 60.0
    redis.values["system:universe:latest"] = json.dumps(
        {
            "generated_at": (datetime.now() - timedelta(seconds=120)).isoformat(),
            "codes": ["000660"],
            "scores": {"000660": 0.95},
            "names": {"000660": "SK Hynix HBM AI memory"},
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    assert target_payload["codes"] == []
    assert target_payload["metadata"] == {}
    assert target_payload["state_counts"] == {
        "active": 0,
        "watch": 0,
        "quarantine": 0,
    }
    assert target_payload["source"]["status"] == "stale_universe"
    assert target_payload["source"]["universe_age_seconds"] >= 60.0
    assert target_payload["source"]["max_universe_age_seconds"] == 60.0
    assert publisher.published == [target_payload]


def test_malformed_optional_fields_fail_open() -> None:
    module = _load_theme_discovery()
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


def test_watch_active_and_quarantine_states_are_preserved() -> None:
    module = _load_theme_discovery()
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
    assert target_payload["metadata"]["A1"]["state"] == "active"
    assert target_payload["metadata"]["A1"]["theme_state"] == "active"
    assert target_payload["metadata"]["W1"]["state"] == "watch"
    assert target_payload["metadata"]["W1"]["theme_state"] == "watch"
    assert target_payload["metadata"]["Q1"]["state"] == "quarantine"
    assert target_payload["metadata"]["Q1"]["theme_state"] == "quarantine"
    assert target_payload["state_counts"] == {
        "active": 1,
        "watch": 1,
        "quarantine": 1,
    }


def test_theme_discovery_output_flows_into_fusion_ranker() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, _publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "codes": ["A1", "Q1"],
            "scores": {"A1": 0.95, "Q1": 0.99},
            "names": {
                "A1": "HBM AI memory leader",
                "Q1": "Shipbuilding defense leader",
            },
            "metadata": {
                "A1": {},
                "Q1": {"risk_flags": ["trading_halt"]},
            },
        }
    )

    assert service.run_once() is True
    theme_payload = json.loads(redis.values["system:theme_targets:latest"])

    from services.fusion_ranker import FusionRanker, FusionRankerConfig

    class FusionRedis:
        def __init__(self, data: dict[str, dict[str, Any]]) -> None:
            self.data = data
            self.writes: dict[str, str] = {}

        def get(self, key: str) -> str | None:
            payload = self.data.get(key)
            return json.dumps(payload) if payload is not None else None

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            _ = ex
            self.writes[key] = value

    class FusionPublisher:
        def __init__(self) -> None:
            self.payloads: list[dict[str, Any]] = []

        def publish(self, payload: dict[str, Any]) -> None:
            self.payloads.append(payload)

    ranker = FusionRanker.__new__(FusionRanker)
    ranker.config = FusionRankerConfig(
        weight_realtime=1.0,
        weight_llm=0.0,
        weight_recency=0.0,
        weight_swing=0.0,
        weight_theme=1.0,
        theme_active_state_bonus=0.0,
    )
    ranker._last_seen = {}
    ranker._first_seen = {}
    ranker._last_payload_fingerprint = ""
    ranker.redis = FusionRedis(
        {
            "system:universe:latest": {
                "codes": ["Q1"],
                "scores": {"Q1": 0.99},
            },
            "system:theme_targets:latest": theme_payload,
            "system:daily_indicators:latest": {"indicators": {"A1": {}, "Q1": {}}},
        }
    )
    ranker.publisher = FusionPublisher()

    assert ranker.run_once() is True
    fused_payload = ranker.publisher.payloads[-1]

    assert fused_payload["codes"] == ["A1"]
    assert "Q1" not in fused_payload["metadata"]
    assert fused_payload["metadata"]["A1"]["state"] == "active"
    assert fused_payload["metadata"]["A1"]["theme_id"] == "ai_hbm"
    assert fused_payload["metadata"]["A1"]["theme_label"] == "AI HBM"
    assert fused_payload["sources"]["theme_targets"]["active_count"] == 1
    assert fused_payload["sources"]["theme_targets"]["quarantine_count"] == 1


def test_now_iso_is_timezone_aware() -> None:
    module = _load_theme_discovery()

    parsed = datetime.fromisoformat(module._now_iso())

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None


def test_run_once_emits_timezone_aware_generated_at() -> None:
    module = _load_theme_discovery()
    redis = FakeRedis()
    service, _publisher = _service(module, redis)
    redis.values["system:universe:latest"] = json.dumps(
        {
            "generated_at": datetime.now().isoformat(),
            "codes": ["999999"],
            "scores": {"999999": 0.8},
            "names": {"999999": "Unrelated commerce"},
        }
    )

    assert service.run_once() is True

    target_payload = json.loads(redis.values["system:theme_targets:latest"])
    parsed = datetime.fromisoformat(target_payload["generated_at"])
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() is not None


def test_default_yaml_loads_required_keyword_themes() -> None:
    module = _load_theme_discovery()

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
