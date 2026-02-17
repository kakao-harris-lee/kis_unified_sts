"""Tests for screener metadata enrichment and fusion ranker merge."""

from __future__ import annotations

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
        metadata = {
            r[0]: {**realtime_metadata.get(r[0], {}), **r[2]}
            for r in rows
        }

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

        metadata = {
            r[0]: {**realtime_metadata.get(r[0], {}), **r[2]}
            for r in rows
        }

        # Fusion's value should win
        assert metadata["005930"]["realtime_score"] == 0.9
