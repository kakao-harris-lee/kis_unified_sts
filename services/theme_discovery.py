"""Theme discovery producer.

Reads the existing screener universe snapshot and emits paper-safe theme target
snapshots. The service is read-only with respect to trading state: it only reads
``system:universe:latest`` and writes derived diagnostic/target Redis payloads.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase
from shared.payloads import (
    clamp01 as _clamp01,
)
from shared.payloads import (
    normalize_scores_by_rank as _normalize_scores_by_rank,
)
from shared.payloads import (
    parse_json_dict as _parse_json,
)
from shared.strategy.market_time import is_regular_session_open
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher
from shared.theme_universe.scoring import (
    HARD_RISK_FLAGS,
    ThemeScoreInput,
    ThemeScoringConfig,
    ThemeScoringWeights,
    classify_theme_candidate,
)

logger = logging.getLogger(__name__)


DEFAULT_REDIS_KEYS = {
    "universe": "system:universe:latest",
    "themes_latest": "system:themes:latest",
    "targets_latest": "system:theme_targets:latest",
    "targets_stream": "system:theme_targets",
}
# Default generic keywords that must not, on their own, admit a theme match.
# Configuration may override via ``ThemeDiscoveryConfig.generic_keywords``.
DEFAULT_GENERIC_THEME_KEYWORDS = ("ai",)


class ThemeScoringWeightsConfig(BaseModel):
    """YAML-facing weights for theme leader scoring."""

    relative_strength: float = 0.25
    trading_value: float = 0.20
    volume_surge: float = 0.15
    catalyst: float = 0.15
    theme_breadth: float = 0.10
    intraday_persistence: float = 0.10
    freshness: float = 0.05


class ThemeScoringConfigModel(BaseModel):
    """YAML-facing theme scoring configuration."""

    weights: ThemeScoringWeightsConfig = Field(
        default_factory=ThemeScoringWeightsConfig
    )
    active_threshold: float = 0.70
    soft_penalty_per_flag: float = 0.08
    soft_penalty_cap: float = 0.35
    hard_risk_flags: list[str] = Field(default_factory=lambda: sorted(HARD_RISK_FLAGS))

    def to_scoring_config(self) -> ThemeScoringConfig:
        return ThemeScoringConfig(
            weights=ThemeScoringWeights(
                relative_strength=self.weights.relative_strength,
                trading_value=self.weights.trading_value,
                volume_surge=self.weights.volume_surge,
                catalyst=self.weights.catalyst,
                theme_breadth=self.weights.theme_breadth,
                intraday_persistence=self.weights.intraday_persistence,
                freshness=self.weights.freshness,
            ),
            active_threshold=self.active_threshold,
            soft_penalty_per_flag=self.soft_penalty_per_flag,
            soft_penalty_cap=self.soft_penalty_cap,
            hard_risk_flags=frozenset(
                str(flag).strip() for flag in self.hard_risk_flags if str(flag).strip()
            )
            or HARD_RISK_FLAGS,
        )


class ThemeKeywordConfig(BaseModel):
    """Keyword configuration for one theme bucket."""

    label: str = ""
    keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Substrings that suppress this theme (homonym/false-positive guard)",
    )


def _keyword_matches(keyword: str, haystack: str) -> bool:
    """Return True if ``keyword`` occurs in ``haystack`` (both casefolded).

    ASCII keywords require word boundaries so a short token cannot match inside a
    larger word (e.g. ``power`` inside ``empower``). Non-ASCII (e.g. Korean)
    keywords keep substring matching because Korean theme names are compound and
    word boundaries would miss legitimate mid-token matches.
    """
    needle = str(keyword).casefold()
    if not needle:
        return False
    if needle.isascii():
        return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None
    return needle in haystack


class ThemeDiscoveryConfig(ServiceConfigBase):
    """Configuration for the read-only theme discovery producer."""

    _default_config_file: ClassVar[str] = "theme_discovery.yaml"

    redis_keys: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_REDIS_KEYS))
    interval_seconds: float = Field(
        default=15.0,
        gt=0.0,
        description="Producer polling interval in seconds",
    )
    ttl_seconds: int = Field(
        default=86400,
        gt=0,
        description="TTL for latest Redis snapshots",
    )
    top_n: int = Field(
        default=20,
        gt=0,
        description="Maximum non-quarantined theme targets to publish",
    )
    max_universe_age_seconds: float = Field(
        default=1800.0,
        gt=0.0,
        description="Maximum accepted age for the upstream universe snapshot",
    )
    thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "minimum_screener_score": 0.0,
            "theme_breadth_full_count": 3.0,
            "keyword_catalyst_score": 0.85,
            "default_intraday_persistence": 0.6,
            "default_freshness_score": 1.0,
            "volume_power_source_floor": 0.8,
        }
    )
    generic_keywords: list[str] = Field(
        default_factory=lambda: list(DEFAULT_GENERIC_THEME_KEYWORDS),
        description="Keywords that must not, alone, admit a theme match",
    )
    scoring: ThemeScoringConfigModel = Field(default_factory=ThemeScoringConfigModel)
    keyword_themes: dict[str, ThemeKeywordConfig] = Field(default_factory=dict)

    def redis_key(self, name: str) -> str:
        return self.redis_keys.get(name, DEFAULT_REDIS_KEYS[name])

    def threshold(self, name: str, default: float) -> float:
        try:
            return float(self.thresholds.get(name, default))
        except (TypeError, ValueError):
            return default

    def generic_keyword_set(self) -> set[str]:
        return {
            str(keyword).casefold()
            for keyword in self.generic_keywords
            if str(keyword).strip()
        }

    def scoring_config(self) -> ThemeScoringConfig:
        return self.scoring.to_scoring_config()


def _parse_timestamp(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        logger.debug("Failed to parse timestamp: %s", exc)
        return None


def _age_seconds(raw: Any) -> float | None:
    timestamp = _parse_timestamp(raw)
    if timestamp is None:
        return None
    now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
    return max(0.0, (now - timestamp).total_seconds())


def _extract_codes(payload: dict[str, Any]) -> list[str]:
    raw_codes = payload.get("codes", [])
    if not isinstance(raw_codes, list):
        return []
    return list(
        dict.fromkeys(str(code).strip() for code in raw_codes if str(code).strip())
    )


def _extract_scores(payload: dict[str, Any], codes: list[str]) -> dict[str, float]:
    raw_scores = payload.get("scores", {})
    scores: dict[str, float] = {}
    if isinstance(raw_scores, dict):
        for code in codes:
            if code in raw_scores:
                scores[code] = _clamp01(raw_scores.get(code))
    if scores:
        # Some codes had real scores: codes missing from the screener's score map
        # have no relative-strength evidence, so floor them at 0.0 rather than a
        # rank-position fallback that could outrank a genuinely low-scored code.
        for code in codes:
            scores.setdefault(code, 0.0)
        return scores
    # No real scores at all: fall back to rank ordering across the full list.
    return _normalize_scores_by_rank(codes)


def _extract_string_map(payload: dict[str, Any], key: str) -> dict[str, str]:
    raw = payload.get(key, {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(code): str(value)
        for code, value in raw.items()
        if str(code).strip() and value is not None
    }


def _extract_metadata(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("metadata", {})
    if not isinstance(raw, dict):
        return {}
    return {
        str(code): dict(value)
        for code, value in raw.items()
        if str(code).strip() and isinstance(value, dict)
    }


def _extract_risk_flags(metadata: dict[str, Any], extra: Any = None) -> list[str]:
    flags: list[str] = []
    for value in (metadata.get("risk_flags"), metadata.get("risks"), extra):
        if isinstance(value, list):
            flags.extend(str(flag) for flag in value if str(flag).strip())
        elif isinstance(value, str) and value.strip():
            flags.append(value.strip())
    return list(dict.fromkeys(flags))


def _text_fragments(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        fragments: list[str] = []
        for key, nested in value.items():
            if key in {"risk_flags", "risks", "source_hits"}:
                continue
            fragments.extend(_text_fragments(nested))
        return fragments
    if isinstance(value, list):
        fragments = []
        for nested in value:
            fragments.extend(_text_fragments(nested))
        return fragments
    return [str(value)]


def _get_nested(metadata: dict[str, Any], key: str) -> Any:
    current: Any = metadata
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _metadata_score(metadata: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        value = _get_nested(metadata, key)
        score = _clamp01(value)
        if score > 0.0:
            return score
    return 0.0


def _source_hits(metadata: dict[str, Any]) -> list[str]:
    value = metadata.get("source_hits")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


class ThemeDiscoveryService:
    """Build theme targets from screener universe metadata."""

    def __init__(
        self,
        config: ThemeDiscoveryConfig,
        *,
        redis_client: Any | None = None,
        publisher: Any | None = None,
    ) -> None:
        self.config = config
        self.redis = (
            redis_client if redis_client is not None else RedisClient.get_client()
        )
        self.publisher = (
            publisher
            if publisher is not None
            else StreamPublisher(config.redis_key("targets_stream"))
        )
        self._generic_keywords = config.generic_keyword_set()
        self._scoring_config = config.scoring_config()

    def _match_themes(
        self,
        *,
        code: str,
        name: str,
        metadata: dict[str, Any],
    ) -> dict[str, list[str]]:
        haystack = " ".join([code, name, *_text_fragments(metadata)]).casefold()
        matches: dict[str, list[str]] = {}
        for theme_id, theme in self.config.keyword_themes.items():
            exclusions = [
                str(token).casefold()
                for token in theme.exclude_keywords
                if str(token).strip()
            ]
            if any(token in haystack for token in exclusions):
                # Explicitly suppressed for this theme (e.g. known homonym).
                continue
            needles = list(theme.keywords)
            needles.append(theme_id)
            hits = [
                keyword
                for keyword in needles
                if keyword and _keyword_matches(keyword, haystack)
            ]
            specific_hits = [
                hit for hit in hits if str(hit).casefold() not in self._generic_keywords
            ]
            if hits and not specific_hits:
                continue
            if hits:
                matches[theme_id] = list(dict.fromkeys(str(hit) for hit in hits))
        return matches

    def _build_score_input(
        self,
        *,
        score: float,
        metadata: dict[str, Any],
        matched_themes: list[str],
        theme_counts: dict[str, int],
        risk_flags: list[str],
    ) -> ThemeScoreInput:
        source_hits = _source_hits(metadata)
        market_signal_count = 1
        market_signal_count += len(source_hits)
        if metadata.get("trend_confirmed") is True:
            market_signal_count += 1
        if any(
            key in metadata for key in ("volume_power", "trading_value", "trade_value")
        ):
            market_signal_count += 1

        volume_surge_score = _metadata_score(
            metadata,
            (
                "volume_surge_score",
                "volume_power_score",
                "swing_discovery.score",
                "volume_power",
            ),
        )
        if "volume_power" in source_hits:
            volume_surge_score = max(
                volume_surge_score,
                _clamp01(self.config.threshold("volume_power_source_floor", 0.8)),
            )

        breadth_full_count = max(
            1.0,
            self.config.threshold("theme_breadth_full_count", 3.0),
        )
        theme_breadth_score = max(
            (
                _clamp01(theme_counts.get(theme_id, 0) / breadth_full_count)
                for theme_id in matched_themes
            ),
            default=0.0,
        )

        intraday_persistence = _metadata_score(
            metadata,
            ("intraday_persistence", "trend_return_pct", "trend_vwap_gap_pct"),
        )
        if intraday_persistence <= 0.0:
            intraday_persistence = _clamp01(
                self.config.threshold("default_intraday_persistence", 0.6)
            )

        return ThemeScoreInput(
            relative_strength=score,
            trading_value_score=max(
                score,
                _metadata_score(
                    metadata,
                    ("trading_value_score", "trade_value_score", "trading_value"),
                ),
            ),
            volume_surge_score=volume_surge_score,
            catalyst_score=(
                _clamp01(self.config.threshold("keyword_catalyst_score", 0.85))
                if matched_themes
                else 0.0
            ),
            theme_breadth_score=theme_breadth_score,
            intraday_persistence=intraday_persistence,
            freshness_score=_clamp01(
                self.config.threshold("default_freshness_score", 1.0)
            ),
            market_signal_count=market_signal_count,
            catalyst_signal_count=len(matched_themes),
            risk_flags=risk_flags,
        )

    def _publish(
        self,
        *,
        target_payload: dict[str, Any],
        theme_payload: dict[str, Any],
    ) -> None:
        ttl = int(self.config.ttl_seconds)
        self.redis.set(
            self.config.redis_key("themes_latest"),
            json.dumps(theme_payload, ensure_ascii=False),
            ex=ttl,
        )
        self.redis.set(
            self.config.redis_key("targets_latest"),
            json.dumps(target_payload, ensure_ascii=False),
            ex=ttl,
        )
        self.publisher.publish(target_payload)

    def _build_empty_target_payload(
        self,
        *,
        generated_at: str,
        universe_key: str,
        universe: dict[str, Any],
        input_count: int,
        source_status: str,
        universe_age_seconds: float | None = None,
    ) -> dict[str, Any]:
        return {
            "generated_at": generated_at,
            "source": {
                "universe_key": universe_key,
                "universe_generated_at": universe.get("generated_at"),
                "universe_age_seconds": (
                    round(universe_age_seconds, 2)
                    if universe_age_seconds is not None
                    else None
                ),
                "max_universe_age_seconds": self.config.max_universe_age_seconds,
                "status": source_status,
                "input_count": input_count,
                "matched_count": 0,
                "top_n": self.config.top_n,
            },
            "codes": [],
            "scores": {},
            "names": {},
            "metadata": {},
            "themes": {},
            "theme_catalog": {
                theme_id: {
                    "label": theme.label or theme_id,
                    "keywords": list(theme.keywords),
                }
                for theme_id, theme in self.config.keyword_themes.items()
            },
            "state_counts": {"active": 0, "watch": 0, "quarantine": 0},
            "quarantined_codes": [],
        }

    def run_once(self) -> bool:
        """Read the latest universe snapshot and publish derived theme targets."""

        universe_key = self.config.redis_key("universe")
        universe = _parse_json(self.redis.get(universe_key))
        if not universe:
            logger.debug("Theme discovery skipped: universe snapshot unavailable")
            return False

        codes = _extract_codes(universe)
        if not codes:
            logger.debug("Theme discovery skipped: universe snapshot has no codes")
            return False

        universe_age_seconds = _age_seconds(universe.get("generated_at"))
        if (
            universe_age_seconds is not None
            and universe_age_seconds > self.config.max_universe_age_seconds
        ):
            generated_at = datetime.now().isoformat()
            state_counts = {"active": 0, "watch": 0, "quarantine": 0}
            theme_payload = self._build_theme_payload(
                generated_at=generated_at,
                candidates=[],
                target_metadata={},
                target_themes={},
                state_counts=state_counts,
                universe_key=universe_key,
            )
            target_payload = self._build_empty_target_payload(
                generated_at=generated_at,
                universe_key=universe_key,
                universe=universe,
                input_count=len(codes),
                source_status="stale_universe",
                universe_age_seconds=universe_age_seconds,
            )
            self._publish(target_payload=target_payload, theme_payload=theme_payload)
            logger.info(
                "Published empty theme targets: stale universe age=%.1fs max=%.1fs",
                universe_age_seconds,
                self.config.max_universe_age_seconds,
            )
            return True

        scores = _extract_scores(universe, codes)
        names = _extract_string_map(universe, "names")
        metadata_by_code = _extract_metadata(universe)
        extra_risk_flags = universe.get("risk_flags", {})
        if not isinstance(extra_risk_flags, dict):
            extra_risk_flags = {}

        raw_matches: dict[str, dict[str, list[str]]] = {}
        minimum_screener_score = self.config.threshold("minimum_screener_score", 0.0)
        for code in codes:
            if scores.get(code, 0.0) < minimum_screener_score:
                continue
            matches = self._match_themes(
                code=code,
                name=names.get(code, ""),
                metadata=metadata_by_code.get(code, {}),
            )
            if matches:
                raw_matches[code] = matches

        if not raw_matches:
            generated_at = datetime.now().isoformat()
            state_counts = {"active": 0, "watch": 0, "quarantine": 0}
            theme_payload = self._build_theme_payload(
                generated_at=generated_at,
                candidates=[],
                target_metadata={},
                target_themes={},
                state_counts=state_counts,
                universe_key=universe_key,
            )
            target_payload = self._build_empty_target_payload(
                generated_at=generated_at,
                universe_key=universe_key,
                universe=universe,
                input_count=len(codes),
                source_status="no_matches",
                universe_age_seconds=universe_age_seconds,
            )
            self._publish(target_payload=target_payload, theme_payload=theme_payload)
            logger.info("Published empty theme targets: no keyword theme matches")
            return True

        theme_counts: dict[str, int] = {}
        for matches in raw_matches.values():
            for theme_id in matches:
                theme_counts[theme_id] = theme_counts.get(theme_id, 0) + 1

        generated_at = datetime.now().isoformat()
        target_metadata: dict[str, dict[str, Any]] = {}
        target_themes: dict[str, list[str]] = {}
        all_names: dict[str, str] = {}
        state_counts = {"active": 0, "watch": 0, "quarantine": 0}
        candidates: list[dict[str, Any]] = []

        for code, matches in raw_matches.items():
            metadata = dict(metadata_by_code.get(code, {}))
            matched_themes = list(matches)
            risk_flags = _extract_risk_flags(
                metadata,
                extra_risk_flags.get(code),
            )
            score_input = self._build_score_input(
                score=scores.get(code, 0.0),
                metadata=metadata,
                matched_themes=matched_themes,
                theme_counts=theme_counts,
                risk_flags=risk_flags,
            )
            result = classify_theme_candidate(score_input, self._scoring_config)
            state = result.state
            leader_score = _clamp01(result.leader_score)
            hard_blocked = result.hard_blocked
            state_counts[state] += 1
            primary_theme_id = matched_themes[0] if matched_themes else ""
            primary_theme = self.config.keyword_themes.get(primary_theme_id)
            primary_theme_label = (
                primary_theme.label if primary_theme is not None else primary_theme_id
            )

            enriched_metadata = {
                **metadata,
                "screener_score": scores.get(code, 0.0),
                "matched_themes": matched_themes,
                "theme_keyword_hits": matches,
                "state": state,
                "leader_score": leader_score,
                "theme_id": primary_theme_id,
                "theme_label": primary_theme_label,
                "theme_state": state,
                "theme_leader_score": leader_score,
                "hard_blocked": hard_blocked,
                "risk_penalty": result.risk_penalty,
                "risk_flags": risk_flags,
            }
            target_metadata[code] = enriched_metadata
            target_themes[code] = matched_themes
            all_names[code] = names.get(code, "")
            candidates.append(
                {
                    "code": code,
                    "score": leader_score,
                    "state": state,
                    "hard_blocked": hard_blocked,
                    "themes": matched_themes,
                }
            )

        candidates.sort(key=lambda row: row["score"], reverse=True)
        target_candidates = [row for row in candidates if row["state"] != "quarantine"][
            : self.config.top_n
        ]
        target_codes = [str(row["code"]) for row in target_candidates]
        target_scores = {str(row["code"]): row["score"] for row in target_candidates}
        quarantined_codes = [
            str(row["code"]) for row in candidates if row["state"] == "quarantine"
        ]

        theme_payload = self._build_theme_payload(
            generated_at=generated_at,
            candidates=candidates,
            target_metadata=target_metadata,
            target_themes=target_themes,
            state_counts=state_counts,
            universe_key=universe_key,
        )
        target_payload = {
            "generated_at": generated_at,
            "source": {
                "universe_key": universe_key,
                "universe_generated_at": universe.get("generated_at"),
                "universe_age_seconds": (
                    round(universe_age_seconds, 2)
                    if universe_age_seconds is not None
                    else None
                ),
                "max_universe_age_seconds": self.config.max_universe_age_seconds,
                "status": "matched",
                "input_count": len(codes),
                "matched_count": len(candidates),
                "top_n": self.config.top_n,
            },
            "codes": target_codes,
            "scores": target_scores,
            "names": all_names,
            "metadata": target_metadata,
            "themes": target_themes,
            "theme_catalog": theme_payload["themes"],
            "state_counts": dict(state_counts),
            "quarantined_codes": quarantined_codes,
        }

        self._publish(target_payload=target_payload, theme_payload=theme_payload)
        logger.info(
            "Published theme targets: %s targets, %s quarantined",
            len(target_codes),
            len(quarantined_codes),
        )
        return True

    def _build_theme_payload(
        self,
        *,
        generated_at: str,
        candidates: list[dict[str, Any]],
        target_metadata: dict[str, dict[str, Any]],
        target_themes: dict[str, list[str]],
        state_counts: dict[str, int],
        universe_key: str,
    ) -> dict[str, Any]:
        themes: dict[str, dict[str, Any]] = {}
        for theme_id, theme in self.config.keyword_themes.items():
            themes[theme_id] = {
                "label": theme.label or theme_id,
                "keywords": list(theme.keywords),
                "codes": [],
                "quarantined_codes": [],
                "scores": {},
                "state_counts": {"active": 0, "watch": 0, "quarantine": 0},
                "keyword_hits": {},
            }

        for candidate in candidates:
            code = str(candidate["code"])
            state = str(candidate["state"])
            for theme_id in target_themes.get(code, []):
                summary = themes.setdefault(
                    theme_id,
                    {
                        "label": theme_id,
                        "keywords": [],
                        "codes": [],
                        "quarantined_codes": [],
                        "scores": {},
                        "state_counts": {"active": 0, "watch": 0, "quarantine": 0},
                        "keyword_hits": {},
                    },
                )
                if state == "quarantine":
                    summary["quarantined_codes"].append(code)
                else:
                    summary["codes"].append(code)
                summary["scores"][code] = candidate["score"]
                summary["state_counts"][state] = (
                    summary["state_counts"].get(state, 0) + 1
                )
                summary["keyword_hits"][code] = (
                    target_metadata[code]
                    .get(
                        "theme_keyword_hits",
                        {},
                    )
                    .get(theme_id, [])
                )

        for summary in themes.values():
            summary["codes"].sort(
                key=lambda code: summary["scores"].get(code, 0.0),
                reverse=True,
            )
            summary["quarantined_codes"].sort(
                key=lambda code: summary["scores"].get(code, 0.0),
                reverse=True,
            )

        return {
            "generated_at": generated_at,
            "source": {"universe_key": universe_key},
            "themes": themes,
            "state_counts": dict(state_counts),
        }


def run_theme_discovery(config: ThemeDiscoveryConfig) -> None:
    service = ThemeDiscoveryService(config)
    logger.info(
        "Theme discovery started (interval=%ss, top_n=%s, targets=%s)",
        config.interval_seconds,
        config.top_n,
        config.redis_key("targets_latest"),
    )
    try:
        while True:
            if not is_regular_session_open():
                # Idle outside the KRX regular session: the upstream universe
                # snapshot is not refreshed, so there is nothing new to derive.
                time.sleep(60)
                continue
            started = time.time()
            try:
                service.run_once()
            except Exception as exc:
                logger.warning("Theme discovery cycle failed: %s", exc, exc_info=True)
            elapsed = time.time() - started
            time.sleep(max(0.05, config.interval_seconds - elapsed))
    except KeyboardInterrupt:
        logger.info("Theme discovery stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_theme_discovery(ThemeDiscoveryConfig.from_yaml())


if __name__ == "__main__":
    main()
