"""Fusion ranker service.

Combines:
  - real-time screener universe (`system:universe:latest`)
  - batch LLM quality snapshot (`system:llm_quality:latest`)

Publishes fused targets to:
  - Stream: `system:trade_targets`
  - Key: `system:trade_targets:latest`
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import Field

if TYPE_CHECKING:
    from typing import Self

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigLoader
from shared.exceptions import InfrastructureError, TradingSystemError
from shared.strategy.market_time import is_regular_session_open
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


class FusionRankerConfig(ServiceConfigBase):
    """Fusion ranker configuration.

    Combines real-time screener universe with LLM quality snapshots
    to produce ranked trade targets.
    """

    _default_config_file: ClassVar[str] = "fusion_ranker.yaml"

    # Redis keys
    realtime_key: str = Field(
        default="system:universe:latest",
        description="Redis key for real-time screener universe",
    )
    llm_quality_key: str = Field(
        default="system:llm_quality:latest",
        description="Redis key for LLM quality snapshot",
    )
    output_key: str = Field(
        default="system:trade_targets:latest",
        description="Redis key for fused trade targets",
    )
    output_stream: str = Field(
        default="system:trade_targets",
        description="Redis stream for fused trade targets",
    )
    daily_indicators_key: str = Field(
        default="system:daily_indicators:latest",
        description="Redis key for daily indicator coverage",
    )

    # Ranking parameters
    interval_seconds: float = Field(
        default=15.0,
        description="Fusion cycle interval in seconds",
    )
    top_n: int = Field(
        default=30,
        description="Number of top targets to publish",
    )

    # Fusion weights
    weight_realtime: float = Field(
        default=0.55,
        description="Weight for real-time screener score",
    )
    weight_llm: float = Field(
        default=0.35,
        description="Weight for LLM quality score",
    )
    weight_recency: float = Field(
        default=0.10,
        description="Weight for recency component",
    )

    # Staleness parameters
    fresh_window_seconds: float = Field(
        default=600.0,
        description="Fresh window for recency scoring (seconds)",
    )
    stale_seconds: float = Field(
        default=1800.0,
        description="Staleness threshold for real-time data (seconds)",
    )
    llm_stale_seconds: float = Field(
        default=43200.0,
        description="Staleness threshold for LLM data (seconds)",
    )

    # LLM adjustments
    llm_risk_penalty_per_hit: float = Field(
        default=0.08,
        description="Penalty per LLM risk flag",
    )
    llm_final_bonus: float = Field(
        default=0.12,
        description="Bonus for LLM final picks",
    )
    min_llm_quality: float = Field(
        default=0.0,
        description="Minimum LLM quality threshold",
    )
    block_negative: bool = Field(
        default=True,
        description="Block symbols with negative LLM signals",
    )

    @classmethod
    def from_yaml(
        cls,
        path: str | None = None,
        section: str | None = None,
        *,
        apply_env_overrides: bool = False,
        env_prefix: str | None = None,
    ) -> Self:
        """Load configuration from YAML file.

        This override handles the nested YAML structure (redis_keys, ranking,
        weights, staleness, llm_adjustments) and flattens it to match the
        flat field structure of this config class.

        Args:
            path: YAML file path (relative to config directory).
                  If None, uses _default_config_file.
            section: Not used for this config (YAML has custom structure)
            apply_env_overrides: If True, apply environment variable overrides
            env_prefix: Environment variable prefix for overrides

        Returns:
            Config instance with values from YAML
        """
        # Determine config file path
        if path is None:
            path = cls._default_config_file

        # Load YAML via ConfigLoader
        raw = ConfigLoader.load(path)

        # Extract nested sections
        keys = raw.get("redis_keys", {})
        ranking = raw.get("ranking", {})
        weights = raw.get("weights", {})
        staleness = raw.get("staleness", {})
        llm_adj = raw.get("llm_adjustments", {})

        # Build flat config dict
        config_data = {
            # Redis keys
            "realtime_key": keys.get("realtime"),
            "llm_quality_key": keys.get("llm_quality"),
            "output_key": keys.get("output"),
            "output_stream": keys.get("output_stream"),
            "daily_indicators_key": keys.get("daily_indicators"),
            # Ranking
            "interval_seconds": ranking.get("interval_seconds"),
            "top_n": ranking.get("top_n"),
            # Weights
            "weight_realtime": weights.get("realtime"),
            "weight_llm": weights.get("llm"),
            "weight_recency": weights.get("recency"),
            # Staleness
            "fresh_window_seconds": staleness.get("fresh_window_seconds"),
            "stale_seconds": staleness.get("stale_seconds"),
            "llm_stale_seconds": staleness.get("llm_stale_seconds"),
            # LLM adjustments
            "llm_risk_penalty_per_hit": llm_adj.get("risk_penalty_per_hit"),
            "llm_final_bonus": llm_adj.get("final_bonus"),
            "min_llm_quality": llm_adj.get("min_quality"),
            "block_negative": llm_adj.get("block_negative"),
        }

        # Remove None values to use defaults
        config_data = {k: v for k, v in config_data.items() if v is not None}

        # Apply environment variable overrides if requested
        if apply_env_overrides:
            prefix = env_prefix if env_prefix is not None else cls._env_prefix
            if prefix:
                env_overrides = cls._extract_env_vars(prefix)
                config_data.update(env_overrides)

        # Create and validate config instance
        return cls(**config_data)


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.debug("Failed to parse JSON: %s", exc)
        return {}


def _normalize_scores_by_rank(codes: list[str]) -> dict[str, float]:
    n = len(codes)
    if n <= 0:
        return {}
    if n == 1:
        return {codes[0]: 1.0}
    return {code: round((n - i - 1) / (n - 1), 6) for i, code in enumerate(codes)}


class FusionRanker:
    def __init__(self, config: FusionRankerConfig):
        self.config = config
        self.redis = RedisClient.get_client()
        self.publisher = StreamPublisher(config.output_stream)
        self._first_seen: dict[str, float] = {}
        self._last_seen: dict[str, float] = {}
        self._last_payload_fingerprint: str = ""

    @staticmethod
    def _parse_generated_at(payload: dict[str, Any]) -> datetime | None:
        raw = payload.get("generated_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except (ValueError, TypeError) as exc:
            logger.debug("Failed to parse generated_at timestamp: %s", exc)
            return None

    def _extract_realtime(
        self, payload: dict[str, Any]
    ) -> tuple[list[str], dict[str, float], dict[str, str], dict[str, dict[str, Any]]]:
        codes_raw = payload.get("codes", [])
        codes = [str(c).strip() for c in codes_raw if str(c).strip()]

        raw_scores = payload.get("scores", {})
        scores: dict[str, float] = {}
        if isinstance(raw_scores, dict):
            for code in codes:
                s = raw_scores.get(code)
                if isinstance(s, (int, float)):
                    scores[code] = float(s)
        if not scores:
            scores = _normalize_scores_by_rank(codes)

        names_raw = payload.get("names", {})
        names = (
            {
                str(k): str(v)
                for k, v in names_raw.items()
                if isinstance(k, str) and isinstance(v, str)
            }
            if isinstance(names_raw, dict)
            else {}
        )

        # Pass through per-symbol metadata from screener (e.g. prev_day_volume)
        metadata_raw = payload.get("metadata", {})
        metadata: dict[str, dict[str, Any]] = {}
        if isinstance(metadata_raw, dict):
            for k, v in metadata_raw.items():
                if isinstance(k, str) and isinstance(v, dict):
                    metadata[k] = dict(v)

        return codes, scores, names, metadata

    def _extract_llm(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, float], dict[str, list[str]], set[str], dict[str, str], str]:
        quality_raw = payload.get("quality", {})
        quality = (
            {
                str(k): max(0.0, min(1.0, float(v)))
                for k, v in quality_raw.items()
                if isinstance(v, (int, float))
            }
            if isinstance(quality_raw, dict)
            else {}
        )

        risk_raw = payload.get("risk_flags", {})
        risk_flags = (
            {
                str(k): [str(x) for x in v if str(x)]
                for k, v in risk_raw.items()
                if isinstance(v, list)
            }
            if isinstance(risk_raw, dict)
            else {}
        )

        excluded_raw = payload.get("excluded", {})
        excluded = set()
        if isinstance(excluded_raw, dict):
            for code, reasons in excluded_raw.items():
                if not isinstance(reasons, list):
                    continue
                if any(
                    str(r).startswith(
                        ("blacklist:", "keyword:", "preferred_share", "name_keyword:")
                    )
                    for r in reasons
                ):
                    excluded.add(str(code))

        names_raw = payload.get("names", {})
        names = (
            {
                str(k): str(v)
                for k, v in names_raw.items()
                if isinstance(k, str) and isinstance(v, str)
            }
            if isinstance(names_raw, dict)
            else {}
        )

        snapshot_id = str(payload.get("snapshot_id", "")).strip()
        return quality, risk_flags, excluded, names, snapshot_id

    def _recency_component(self, code: str, now: float) -> float:
        first = self._first_seen.get(code)
        if first is None:
            self._first_seen[code] = now
            return 1.0

        age = now - first
        if age <= self.config.fresh_window_seconds:
            return max(0.0, 1.0 - (age / max(self.config.fresh_window_seconds, 1.0)))

        last = self._last_seen.get(code, now)
        if now - last >= self.config.stale_seconds:
            return -1.0
        return 0.0

    def _load_daily_indicator_coverage(self) -> set[str] | None:
        """Return covered symbols, or None when the coverage key is absent."""
        raw = self.redis.get(self.config.daily_indicators_key)
        if raw is None:
            return None
        payload = _parse_json(raw)
        indicators = payload.get("indicators")
        if not isinstance(indicators, dict):
            return set()
        return {str(code).strip() for code in indicators if str(code).strip()}

    @staticmethod
    def _apply_daily_indicator_coverage(
        rows: list[tuple[str, float, dict[str, Any]]],
        covered_symbols: set[str] | None,
    ) -> tuple[list[tuple[str, float, dict[str, Any]]], dict[str, Any]]:
        if covered_symbols is None:
            return rows, {
                "enabled": False,
                "daily_indicator_count": None,
                "input_count": len(rows),
                "covered_count": len(rows),
                "coverage_filtered_count": 0,
                "missing_sample": [],
            }

        filtered = [row for row in rows if row[0] in covered_symbols]
        missing = [row[0] for row in rows if row[0] not in covered_symbols]
        return filtered, {
            "enabled": True,
            "daily_indicator_count": len(covered_symbols),
            "input_count": len(rows),
            "covered_count": len(filtered),
            "coverage_filtered_count": len(missing),
            "missing_sample": missing[:10],
        }

    def _publish_payload(self, payload: dict[str, Any]) -> bool:
        fingerprint = json.dumps(payload.get("codes", []), ensure_ascii=False)
        if fingerprint == self._last_payload_fingerprint:
            return False

        self.publisher.publish(payload)
        self.redis.set(
            self.config.output_key,
            json.dumps(payload, ensure_ascii=False),
            ex=86400,
        )
        self._last_payload_fingerprint = fingerprint
        logger.info(f"Published fused trade targets: {len(payload.get('codes', []))}")
        return True

    def run_once(self) -> bool:
        realtime_payload = _parse_json(self.redis.get(self.config.realtime_key))
        if not realtime_payload:
            logger.debug("Fusion skipped: realtime universe not available")
            return False

        llm_payload = _parse_json(self.redis.get(self.config.llm_quality_key))

        realtime_codes, realtime_scores, realtime_names, realtime_metadata = (
            self._extract_realtime(realtime_payload)
        )
        llm_quality, llm_risk_flags, llm_excluded, llm_names, llm_snapshot_id = (
            self._extract_llm(llm_payload)
        )

        if not realtime_codes:
            return False

        now = time.time()
        for c in realtime_codes:
            self._last_seen[c] = now

        # include a small number of final LLM picks even if they are not yet in realtime ranking
        llm_final = llm_payload.get("final_codes", [])
        llm_final_codes = [str(c).strip() for c in llm_final if str(c).strip()]
        llm_final_set = set(llm_final_codes)
        union = list(dict.fromkeys(realtime_codes + llm_final_codes))

        llm_generated_at = self._parse_generated_at(llm_payload)
        llm_age_seconds = None
        llm_freshness = 1.0
        if llm_generated_at is not None:
            llm_age_seconds = max(
                0.0, (datetime.now() - llm_generated_at).total_seconds()
            )
            llm_freshness = max(
                0.0,
                1.0 - (llm_age_seconds / max(self.config.llm_stale_seconds, 1.0)),
            )

        rows: list[tuple[str, float, dict[str, Any]]] = []
        for code in union:
            rt = float(realtime_scores.get(code, 0.0))
            lq = float(llm_quality.get(code, 0.0))
            if lq < self.config.min_llm_quality:
                continue
            if self.config.block_negative and code in llm_excluded:
                continue

            risk_hits = llm_risk_flags.get(code, [])
            risk_penalty = min(
                0.5, len(risk_hits) * max(0.0, self.config.llm_risk_penalty_per_hit)
            )
            llm_confidence = max(0.0, 1.0 - risk_penalty)
            if code in llm_final_set:
                llm_confidence = min(1.0, llm_confidence + self.config.llm_final_bonus)

            effective_lq = lq * llm_freshness * llm_confidence

            rec = self._recency_component(code, now)
            score = (
                self.config.weight_realtime * rt
                + self.config.weight_llm * effective_lq
                + self.config.weight_recency * rec
            )
            final_score = max(0.0, min(1.0, score))

            rows.append(
                (
                    code,
                    round(final_score, 6),
                    {
                        "realtime_score": round(rt, 6),
                        "llm_quality": round(lq, 6),
                        "llm_effective_quality": round(effective_lq, 6),
                        "llm_confidence": round(llm_confidence, 6),
                        "llm_freshness": round(llm_freshness, 6),
                        "llm_age_seconds": (
                            round(llm_age_seconds, 2)
                            if llm_age_seconds is not None
                            else None
                        ),
                        "llm_snapshot_id": llm_snapshot_id,
                        "recency_component": round(rec, 6),
                        "risk_flags": risk_hits,
                    },
                )
            )

        if not rows:
            logger.debug("Fusion skipped: no rows after filtering")
            return False

        covered_symbols = self._load_daily_indicator_coverage()
        rows, coverage_stats = self._apply_daily_indicator_coverage(
            rows,
            covered_symbols,
        )

        rows.sort(key=lambda x: x[1], reverse=True)
        rows = rows[: self.config.top_n]

        codes = [r[0] for r in rows]
        scores = {r[0]: r[1] for r in rows}
        # Merge screener metadata (e.g. prev_day_volume) under fusion scores
        metadata = {r[0]: {**realtime_metadata.get(r[0], {}), **r[2]} for r in rows}
        names = {c: realtime_names.get(c, llm_names.get(c, "")) for c in codes}

        payload = {
            "generated_at": datetime.now().isoformat(),
            "codes": codes,
            "scores": scores,
            "names": names,
            "metadata": metadata,
            "sources": {
                "realtime_key": self.config.realtime_key,
                "llm_quality_key": self.config.llm_quality_key,
                "daily_indicators_key": self.config.daily_indicators_key,
                "daily_indicator_coverage": coverage_stats,
                "coverage_filtered_count": coverage_stats["coverage_filtered_count"],
            },
        }

        return self._publish_payload(payload)


def run_fusion_ranker(config: FusionRankerConfig) -> None:
    fusion = FusionRanker(config)
    logger.info(
        "Fusion ranker started "
        f"(interval={config.interval_seconds}s, top_n={config.top_n}, output={config.output_key})"
    )

    try:
        while True:
            if not is_regular_session_open():
                # Idle outside the KRX regular session (no fresh ranking inputs).
                time.sleep(60)
                continue
            started = time.time()
            try:
                fusion.run_once()
            except InfrastructureError as e:
                logger.warning(f"Fusion run failed (infrastructure): {e}")
            except TradingSystemError as e:
                logger.warning(f"Fusion run failed (trading system): {e}")
            except Exception as e:
                logger.warning(f"Fusion run failed (unexpected): {e}", exc_info=True)

            elapsed = time.time() - started
            sleep_seconds = max(0.05, config.interval_seconds - elapsed)
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Fusion ranker stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_fusion_ranker(FusionRankerConfig.from_yaml())


if __name__ == "__main__":
    main()
