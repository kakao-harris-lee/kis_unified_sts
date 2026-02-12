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
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FusionRankerConfig:
    realtime_key: str = os.environ.get("UNIVERSE_LATEST_KEY", "system:universe:latest")
    llm_quality_key: str = os.environ.get("LLM_QUALITY_LATEST_KEY", "system:llm_quality:latest")
    output_key: str = os.environ.get("TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest")
    output_stream: str = os.environ.get("TRADE_TARGETS_STREAM", "system:trade_targets")

    interval_seconds: float = float(os.environ.get("FUSION_INTERVAL_SECONDS", "15"))
    top_n: int = int(os.environ.get("FUSION_TOP_N", "30"))

    weight_realtime: float = float(os.environ.get("FUSION_WEIGHT_REALTIME", "0.55"))
    weight_llm: float = float(os.environ.get("FUSION_WEIGHT_LLM", "0.35"))
    weight_recency: float = float(os.environ.get("FUSION_WEIGHT_RECENCY", "0.10"))

    fresh_window_seconds: float = float(os.environ.get("FUSION_FRESH_WINDOW_SECONDS", "600"))
    stale_seconds: float = float(os.environ.get("FUSION_STALE_SECONDS", "1800"))
    llm_stale_seconds: float = float(os.environ.get("FUSION_LLM_STALE_SECONDS", "43200"))
    llm_risk_penalty_per_hit: float = float(
        os.environ.get("FUSION_LLM_RISK_PENALTY_PER_HIT", "0.08")
    )
    llm_final_bonus: float = float(os.environ.get("FUSION_LLM_FINAL_BONUS", "0.12"))
    min_llm_quality: float = float(os.environ.get("FUSION_MIN_LLM_QUALITY", "0.0"))
    block_negative: bool = os.environ.get("FUSION_BLOCK_NEGATIVE", "true").lower() == "true"


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
    run_fusion_ranker(FusionRankerConfig())


if __name__ == "__main__":
    main()
