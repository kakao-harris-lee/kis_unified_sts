"""Tests for screener metadata enrichment and fusion ranker merge."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from services.fusion_ranker import FusionRanker, FusionRankerConfig


class TestFusionRankerExtractRealtime:
    """Verify _extract_realtime passes through screener metadata."""

    def _make_ranker(self) -> FusionRanker:
        """Create a FusionRanker with dummy config (no Redis needed)."""
        config = FusionRankerConfig()
        ranker = FusionRanker.__new__(FusionRanker)
        ranker.config = config
        ranker._last_seen = {}
        ranker._first_seen = {}
        return ranker

    def test_extract_realtime_returns_metadata(self):
        ranker = self._make_ranker()
        payload = {
            "codes": ["005930", "000660"],
            "scores": {"005930": 0.9, "000660": 0.7},
            "names": {"005930": "삼성전자", "000660": "SK하이닉스"},
            "metadata": {
                "005930": {"prev_day_volume": 10_000_000},
                "000660": {"prev_day_volume": 5_000_000},
            },
        }

        codes, scores, names, metadata = ranker._extract_realtime(payload)

        assert codes == ["005930", "000660"]
        assert "005930" in metadata
        assert metadata["005930"]["prev_day_volume"] == 10_000_000
        assert metadata["000660"]["prev_day_volume"] == 5_000_000

    def test_extract_realtime_no_metadata_returns_empty_dict(self):
        ranker = self._make_ranker()
        payload = {
            "codes": ["005930"],
            "scores": {"005930": 0.9},
            "names": {"005930": "삼성전자"},
            # No "metadata" key
        }

        codes, scores, names, metadata = ranker._extract_realtime(payload)

        assert codes == ["005930"]
        assert metadata == {}

    def test_extract_realtime_malformed_metadata_ignored(self):
        ranker = self._make_ranker()
        payload = {
            "codes": ["005930"],
            "scores": {"005930": 0.9},
            "names": {},
            "metadata": "not_a_dict",  # malformed
        }

        codes, scores, names, metadata = ranker._extract_realtime(payload)
        assert metadata == {}


class TestFusionMetadataMerge:
    """Verify that screener metadata (prev_day_volume) flows through to fusion output."""

    def test_screener_metadata_preserved_in_fusion_metadata(self):
        """Simulate the metadata merge logic from run_once."""
        # Screener-origin metadata
        realtime_metadata: dict[str, dict[str, Any]] = {
            "005930": {"prev_day_volume": 10_000_000},
            "000660": {"prev_day_volume": 5_000_000},
        }

        # Fusion-generated per-code metadata (from scoring loop)
        rows = [
            ("005930", 0.85, {"realtime_score": 0.9, "llm_quality": 0.8}),
            ("000660", 0.70, {"realtime_score": 0.7, "llm_quality": 0.6}),
        ]

        # This is the exact merge logic from run_once
        metadata = {r[0]: {**realtime_metadata.get(r[0], {}), **r[2]} for r in rows}

        # prev_day_volume from screener should be present
        assert metadata["005930"]["prev_day_volume"] == 10_000_000
        assert metadata["000660"]["prev_day_volume"] == 5_000_000

        # Fusion-own fields should also be present
        assert metadata["005930"]["realtime_score"] == 0.9
        assert metadata["000660"]["llm_quality"] == 0.6

    def test_fusion_fields_override_screener_on_conflict(self):
        """If both screener and fusion have same key, fusion wins."""
        realtime_metadata: dict[str, dict[str, Any]] = {
            "005930": {"realtime_score": 0.5},  # screener version
        }
        rows = [
            ("005930", 0.85, {"realtime_score": 0.9}),  # fusion version
        ]

        metadata = {r[0]: {**realtime_metadata.get(r[0], {}), **r[2]} for r in rows}

        # Fusion's value should win
        assert metadata["005930"]["realtime_score"] == 0.9


class TestFusionDailyIndicatorCoverage:
    def _make_ranker(
        self,
        payloads: dict[str, dict[str, Any]],
        config: FusionRankerConfig | None = None,
    ) -> FusionRanker:
        config = config or FusionRankerConfig()
        ranker = FusionRanker.__new__(FusionRanker)
        ranker.config = config
        ranker._last_seen = {}
        ranker._first_seen = {}
        ranker._last_payload_fingerprint = ""

        class FakeRedis:
            def __init__(self, data: dict[str, dict[str, Any]]) -> None:
                self.data = data
                self.writes: dict[str, str] = {}

            def get(self, key: str) -> str | None:
                payload = self.data.get(key)
                return json.dumps(payload) if payload is not None else None

            def set(self, key: str, value: str, ex: int | None = None) -> None:
                _ = ex
                self.writes[key] = value

        class FakePublisher:
            def __init__(self) -> None:
                self.payloads: list[dict[str, Any]] = []

            def publish(self, payload: dict[str, Any]) -> None:
                self.payloads.append(payload)

        ranker.redis = FakeRedis(payloads)
        ranker.publisher = FakePublisher()
        return ranker

    def test_run_once_filters_uncovered_realtime_and_llm_final_codes(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["005930", "000660", "123456"],
                    "scores": {"005930": 0.9, "000660": 0.8, "123456": 0.7},
                },
                "system:llm_quality:latest": {
                    "quality": {"005930": 0.9, "000660": 0.9, "999999": 1.0},
                    "final_codes": ["999999", "000660"],
                    "risk_flags": {},
                    "excluded": {},
                },
                "system:daily_indicators:latest": {
                    "indicators": {"005930": {}, "000660": {}}
                },
            }
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["005930", "000660"]
        assert "123456" not in payload["metadata"]
        assert "999999" not in payload["metadata"]
        coverage = payload["sources"]["daily_indicator_coverage"]
        assert coverage["enabled"] is True
        assert coverage["input_count"] == 4
        assert coverage["covered_count"] == 2
        assert coverage["coverage_filtered_count"] == 2
        assert coverage["missing_sample"] == ["123456", "999999"]

    def test_run_once_admits_llm_only_quality_code_with_daily_coverage(self):
        ranker = self._make_ranker(
            {
                "system:llm_quality:latest": {
                    "quality": {"080220": 0.9, "001740": 0.4},
                    "names": {"080220": "제주반도체", "001740": "SK네트웍스"},
                    "metadata": {
                        "080220": {
                            "entry_price": 112900.0,
                            "stop_loss": 104997.0,
                            "take_profit": 126448.0,
                        }
                    },
                    "final_codes": [],
                    "risk_flags": {},
                    "excluded": {},
                },
                "system:daily_indicators:latest": {
                    "indicators": {"080220": {"daily_close": 111700.0}}
                },
            },
            FusionRankerConfig(
                weight_realtime=0.0,
                weight_llm=1.0,
                weight_recency=0.0,
                weight_swing=0.0,
                llm_only_top_n=5,
                llm_only_min_quality=0.5,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["080220"]
        assert payload["names"]["080220"] == "제주반도체"
        assert payload["metadata"]["080220"]["llm_only"] is True
        assert payload["metadata"]["080220"]["llm_final"] is False
        assert payload["metadata"]["080220"]["entry_price"] == 112900.0
        assert payload["metadata"]["080220"]["stop_loss"] == 104997.0
        assert payload["metadata"]["080220"]["take_profit"] == 126448.0
        assert payload["sources"]["llm_only_top_n"] == 5
        assert payload["sources"]["llm_only_min_quality"] == 0.5

    def test_daily_coverage_missing_key_is_fail_open(self):
        rows = [
            ("005930", 0.9, {}),
            ("999999", 0.8, {}),
        ]

        filtered, stats = FusionRanker._apply_daily_indicator_coverage(rows, None)

        assert filtered == rows
        assert stats["enabled"] is False
        assert stats["coverage_filtered_count"] == 0

    def test_run_once_applies_swing_discovery_component(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["005930", "000660"],
                    "scores": {"005930": 0.0, "000660": 0.0},
                    "metadata": {
                        "005930": {"swing_discovery": {"score": 0.25}},
                        "000660": {"swing_discovery": {"score": 0.95}},
                    },
                },
                "system:llm_quality:latest": {
                    "quality": {},
                    "risk_flags": {},
                    "excluded": {},
                },
                "system:daily_indicators:latest": {
                    "indicators": {"005930": {}, "000660": {}}
                },
            },
            FusionRankerConfig(
                weight_realtime=0.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=1.0,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["000660", "005930"]
        assert payload["scores"]["000660"] == 0.95
        assert payload["metadata"]["000660"]["swing_discovery_score"] == 0.95
        assert payload["sources"]["weights"]["swing"] == 1.0


class TestFusionThemeTargets:
    def _make_ranker(
        self,
        payloads: dict[str, dict[str, Any]],
        config: FusionRankerConfig | None = None,
    ) -> FusionRanker:
        config = config or FusionRankerConfig()
        ranker = FusionRanker.__new__(FusionRanker)
        ranker.config = config
        ranker._last_seen = {}
        ranker._first_seen = {}
        ranker._last_payload_fingerprint = ""

        class FakeRedis:
            def __init__(self, data: dict[str, dict[str, Any]]) -> None:
                self.data = data
                self.writes: dict[str, str] = {}

            def get(self, key: str) -> str | None:
                payload = self.data.get(key)
                return json.dumps(payload) if payload is not None else None

            def set(self, key: str, value: str, ex: int | None = None) -> None:
                _ = ex
                self.writes[key] = value

        class FakePublisher:
            def __init__(self) -> None:
                self.payloads: list[dict[str, Any]] = []

            def publish(self, payload: dict[str, Any]) -> None:
                self.payloads.append(payload)

        ranker.redis = FakeRedis(payloads)
        ranker.publisher = FakePublisher()
        return ranker

    def test_run_once_admits_active_theme_code_with_daily_coverage(self):
        ranker = self._make_ranker(
            {
                "system:theme_targets:latest": {
                    "generated_at": datetime.now().isoformat(),
                    "codes": ["000660"],
                    "scores": {"000660": 0.82},
                    "names": {"000660": "SK하이닉스"},
                    "metadata": {
                        "000660": {
                            "state": "active",
                            "theme_id": "ai_hbm",
                            "leader_score": 0.82,
                            "reason": "HBM theme leader",
                        }
                    },
                    "themes": {"ai_hbm": {"label": "AI/HBM"}},
                },
                "system:daily_indicators:latest": {
                    "indicators": {"000660": {"daily_close": 284500.0}}
                },
            },
            FusionRankerConfig(
                weight_realtime=0.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=1.0,
                theme_active_state_bonus=0.0,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["000660"]
        assert payload["scores"]["000660"] == 0.82
        assert payload["names"]["000660"] == "SK하이닉스"
        assert payload["metadata"]["000660"]["theme_id"] == "ai_hbm"
        assert payload["metadata"]["000660"]["theme_label"] == "AI/HBM"
        assert payload["metadata"]["000660"]["theme_active"] is True
        assert payload["sources"]["theme_targets"]["active_count"] == 1
        assert payload["sources"]["theme_targets"]["generated_at"]
        assert payload["sources"]["weights"]["theme"] == 1.0

    def test_run_once_excludes_quarantined_theme_code_from_final_rows(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["005930", "000660"],
                    "scores": {"005930": 0.99, "000660": 0.6},
                },
                "system:theme_targets:latest": {
                    "codes": ["005930"],
                    "scores": {"005930": 1.0},
                    "metadata": {
                        "005930": {
                            "state": "quarantine",
                            "theme_id": "risk_theme",
                            "reason": "investment warning",
                        }
                    },
                },
                "system:daily_indicators:latest": {
                    "indicators": {"005930": {}, "000660": {}}
                },
            },
            FusionRankerConfig(
                weight_realtime=1.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=1.0,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["000660"]
        assert "005930" not in payload["metadata"]
        assert payload["sources"]["theme_targets"]["quarantine_count"] == 1

    def test_run_once_excludes_producer_shape_quarantine_metadata(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["005930", "000660"],
                    "scores": {"005930": 0.99, "000660": 0.6},
                },
                "system:theme_targets:latest": {
                    # ThemeDiscoveryService excludes quarantined codes from
                    # tradable codes but keeps them visible in metadata.
                    "codes": ["000660"],
                    "scores": {"000660": 0.7},
                    "metadata": {
                        "000660": {"state": "active", "theme_id": "ai_hbm"},
                        "005930": {
                            "state": "quarantine",
                            "theme_id": "risk_theme",
                            "risk_flags": ["investment_warning"],
                        },
                    },
                    "quarantined_codes": ["005930"],
                },
                "system:daily_indicators:latest": {
                    "indicators": {"005930": {}, "000660": {}}
                },
            },
            FusionRankerConfig(
                weight_realtime=1.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=0.0,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["000660"]
        assert "005930" not in payload["metadata"]
        assert payload["sources"]["theme_targets"]["quarantine_count"] == 1

    def test_run_once_ignores_stale_theme_target_snapshot(self):
        ranker = self._make_ranker(
            {
                "system:theme_targets:latest": {
                    "generated_at": (
                        datetime.now() - timedelta(seconds=120)
                    ).isoformat(),
                    "codes": ["000660"],
                    "scores": {"000660": 0.82},
                    "names": {"000660": "SK하이닉스"},
                    "metadata": {
                        "000660": {
                            "state": "active",
                            "theme_id": "ai_hbm",
                            "leader_score": 0.82,
                        }
                    },
                },
                "system:daily_indicators:latest": {
                    "indicators": {"000660": {"daily_close": 284500.0}}
                },
            },
            FusionRankerConfig(
                weight_realtime=0.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=1.0,
                theme_stale_seconds=60.0,
            ),
        )

        assert ranker.run_once() is False
        assert ranker.publisher.payloads == []

    def test_run_once_ignores_theme_snapshot_with_stale_source_universe(self):
        ranker = self._make_ranker(
            {
                "system:theme_targets:latest": {
                    "generated_at": datetime.now().isoformat(),
                    "source": {
                        "universe_generated_at": (
                            datetime.now() - timedelta(seconds=120)
                        ).isoformat()
                    },
                    "codes": ["000660"],
                    "scores": {"000660": 0.82},
                    "names": {"000660": "SK하이닉스"},
                    "metadata": {
                        "000660": {
                            "state": "active",
                            "theme_id": "ai_hbm",
                            "leader_score": 0.82,
                        }
                    },
                },
                "system:daily_indicators:latest": {
                    "indicators": {"000660": {"daily_close": 284500.0}}
                },
            },
            FusionRankerConfig(
                weight_realtime=0.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=1.0,
                theme_stale_seconds=60.0,
            ),
        )

        assert ranker.run_once() is False
        assert ranker.publisher.payloads == []

    def test_run_once_missing_theme_key_preserves_existing_realtime_behavior(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["005930"],
                    "scores": {"005930": 0.7},
                    "names": {"005930": "삼성전자"},
                },
                "system:daily_indicators:latest": {"indicators": {"005930": {}}},
            },
            FusionRankerConfig(
                weight_realtime=1.0,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=1.0,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]

        assert payload["codes"] == ["005930"]
        assert payload["scores"]["005930"] == 0.7
        assert "theme_score" not in payload["metadata"]["005930"]
        assert payload["sources"]["theme_targets"]["candidate_count"] == 0

    def test_run_once_preserves_theme_metadata_for_existing_realtime_code(self):
        ranker = self._make_ranker(
            {
                "system:universe:latest": {
                    "codes": ["000660"],
                    "scores": {"000660": 0.2},
                    "metadata": {"000660": {"prev_day_volume": 5_000_000}},
                },
                "system:theme_targets:latest": {
                    "codes": ["000660"],
                    "scores": {"000660": 0.5},
                    "metadata": {
                        "000660": {
                            "state": "active",
                            "theme_id": "ai_hbm",
                            "theme_label": "AI/HBM",
                            "leader_score": 0.78,
                            "reason": "theme breadth and relative strength",
                        }
                    },
                    "themes": {"ai_hbm": {"label": "AI/HBM"}},
                },
                "system:daily_indicators:latest": {"indicators": {"000660": {}}},
            },
            FusionRankerConfig(
                weight_realtime=0.5,
                weight_llm=0.0,
                weight_recency=0.0,
                weight_swing=0.0,
                weight_theme=0.5,
                theme_active_state_bonus=0.1,
            ),
        )

        assert ranker.run_once() is True
        payload = ranker.publisher.payloads[-1]
        metadata = payload["metadata"]["000660"]

        assert payload["scores"]["000660"] == 0.4
        assert metadata["prev_day_volume"] == 5_000_000
        assert metadata["state"] == "active"
        assert metadata["theme_id"] == "ai_hbm"
        assert metadata["theme_label"] == "AI/HBM"
        assert metadata["leader_score"] == 0.78
        assert metadata["reason"] == "theme breadth and relative strength"
        assert metadata["theme_score"] == 0.5
        assert metadata["theme_effective_score"] == 0.6
        assert metadata["theme_active"] is True
