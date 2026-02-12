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
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.config.loader import ConfigLoader
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FusionRankerConfig:
    realtime_key: str = "system:universe:latest"
    llm_quality_key: str = "system:llm_quality:latest"
    output_key: str = "system:trade_targets:latest"
    output_stream: str = "system:trade_targets"

    interval_seconds: float = 15.0
    top_n: int = 30

    weight_realtime: float = 0.55
    weight_llm: float = 0.35
    weight_recency: float = 0.10

    fresh_window_seconds: float = 600.0
    stale_seconds: float = 1800.0
    llm_stale_seconds: float = 43200.0
    llm_risk_penalty_per_hit: float = 0.08
    llm_final_bonus: float = 0.12
    min_llm_quality: float = 0.0
    block_negative: bool = True

    @classmethod
    def from_yaml(cls) -> "FusionRankerConfig":
        """Load configuration from config/fusion_ranker.yaml."""
        raw = ConfigLoader.load("fusion_ranker.yaml")
        keys = raw.get("redis_keys", {})
        ranking = raw.get("ranking", {})
        weights = raw.get("weights", {})
        staleness = raw.get("staleness", {})
        llm_adj = raw.get("llm_adjustments", {})

        return cls(
            realtime_key=keys.get("realtime", cls.realtime_key),
            llm_quality_key=keys.get("llm_quality", cls.llm_quality_key),
            output_key=keys.get("output", cls.output_key),
            output_stream=keys.get("output_stream", cls.output_stream),
            interval_seconds=float(ranking.get("interval_seconds", cls.interval_seconds)),
            top_n=int(ranking.get("top_n", cls.top_n)),
            weight_realtime=float(weights.get("realtime", cls.weight_realtime)),
            weight_llm=float(weights.get("llm", cls.weight_llm)),
            weight_recency=float(weights.get("recency", cls.weight_recency)),
            fresh_window_seconds=float(
                staleness.get("fresh_window_seconds", cls.fresh_window_seconds)
            ),
            stale_seconds=float(staleness.get("stale_seconds", cls.stale_seconds)),
            llm_stale_seconds=float(
                staleness.get("llm_stale_seconds", cls.llm_stale_seconds)
            ),
            llm_risk_penalty_per_hit=float(
                llm_adj.get("risk_penalty_per_hit", cls.llm_risk_penalty_per_hit)
            ),
            llm_final_bonus=float(llm_adj.get("final_bonus", cls.llm_final_bonus)),
            min_llm_quality=float(llm_adj.get("min_quality", cls.min_llm_quality)),
            block_negative=bool(llm_adj.get("block_negative", cls.block_negative)),
        )


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
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
        except Exception:
            return None

    def _extract_realtime(self, payload: dict[str, Any]) -> tuple[list[str], dict[str, float], dict[str, str]]:
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
        names = {
            str(k): str(v)
            for k, v in names_raw.items()
            if isinstance(k, str) and isinstance(v, str)
        } if isinstance(names_raw, dict) else {}

        return codes, scores, names

    def _extract_llm(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, float], dict[str, list[str]], set[str], dict[str, str], str]:
        quality_raw = payload.get("quality", {})
        quality = {
            str(k): max(0.0, min(1.0, float(v)))
            for k, v in quality_raw.items()
            if isinstance(v, (int, float))
        } if isinstance(quality_raw, dict) else {}

        risk_raw = payload.get("risk_flags", {})
        risk_flags = {
            str(k): [str(x) for x in v if str(x)]
            for k, v in risk_raw.items()
            if isinstance(v, list)
        } if isinstance(risk_raw, dict) else {}

        excluded_raw = payload.get("excluded", {})
        excluded = set()
        if isinstance(excluded_raw, dict):
            for code, reasons in excluded_raw.items():
                if not isinstance(reasons, list):
                    continue
                if any(
                    str(r).startswith(("blacklist:", "keyword:", "preferred_share", "name_keyword:"))
                    for r in reasons
                ):
                    excluded.add(str(code))

        names_raw = payload.get("names", {})
        names = {
            str(k): str(v)
            for k, v in names_raw.items()
            if isinstance(k, str) and isinstance(v, str)
        } if isinstance(names_raw, dict) else {}

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

    def run_once(self) -> bool:
        realtime_payload = _parse_json(self.redis.get(self.config.realtime_key))
        if not realtime_payload:
            logger.debug("Fusion skipped: realtime universe not available")
            return False

        llm_payload = _parse_json(self.redis.get(self.config.llm_quality_key))

        realtime_codes, realtime_scores, realtime_names = self._extract_realtime(realtime_payload)
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
                        "llm_age_seconds": round(llm_age_seconds, 2)
                        if llm_age_seconds is not None
                        else None,
                        "llm_snapshot_id": llm_snapshot_id,
                        "recency_component": round(rec, 6),
                        "risk_flags": risk_hits,
                    },
                )
            )

        if not rows:
            logger.debug("Fusion skipped: no rows after filtering")
            return False

        rows.sort(key=lambda x: x[1], reverse=True)
        rows = rows[: self.config.top_n]

        codes = [r[0] for r in rows]
        scores = {r[0]: r[1] for r in rows}
        metadata = {r[0]: r[2] for r in rows}
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
            },
        }

        fingerprint = json.dumps(payload.get("codes", []), ensure_ascii=False)
        if fingerprint == self._last_payload_fingerprint:
            return False

        self.publisher.publish(payload)
        self.redis.set(self.config.output_key, json.dumps(payload, ensure_ascii=False))
        self._last_payload_fingerprint = fingerprint
        logger.info(f"Published fused trade targets: {len(codes)}")
        return True


def run_fusion_ranker(config: FusionRankerConfig) -> None:
    fusion = FusionRanker(config)
    logger.info(
        "Fusion ranker started "
        f"(interval={config.interval_seconds}s, top_n={config.top_n}, output={config.output_key})"
    )

    try:
        while True:
            started = time.time()
            try:
                fusion.run_once()
            except Exception as e:
                logger.warning(f"Fusion run failed: {e}")

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
