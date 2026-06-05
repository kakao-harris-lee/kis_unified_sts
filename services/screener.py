"""Stock universe screener service.

- Polls KIS ranking APIs every second (configurable)
- Selects Top-N "aggressive" symbols (by trade value + gainers)
- Publishes to Redis:
  - Stream: `system:universe` (xadd via StreamPublisher)
  - Key: `system:universe:latest` (JSON snapshot for fast bootstrap)

Environment variables:
  - `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_IS_REAL` ("true"/"false")
  - `SCREENER_INTERVAL_SECONDS` (default: 5.0)
  - `SCREENER_RANK_LIMIT` (default: 30)
  - `SCREENER_TOP_N` (default: 20)
  - `SCREENER_WEIGHT_TRADE_VALUE` (default: 0.6)
  - `SCREENER_WEIGHT_GAINER` (default: 0.4)
  - `SCREENER_NOTIFY_INTERVAL_SECONDS` (default: 1800)
  - `UNIVERSE_STREAM` (default: system:universe)
  - `UNIVERSE_LATEST_KEY` (default: system:universe:latest)
  - `SCREENER_TREND_CONFIRM_ENABLED` (default: true)
  - `SCREENER_TREND_CONFIRM_MIN_MINUTES_AFTER_OPEN` (default: 7)
  - `SCREENER_TREND_CONFIRM_MAX_SCAN_CODES` (default: 20)
  - `SCREENER_TREND_CONFIRM_BAR_COUNT` (default: 8)
  - `SCREENER_TREND_CONFIRM_MIN_RETURN_PCT` (default: 0.35)
  - `SCREENER_TREND_CONFIRM_MIN_POSITIVE_RATIO` (default: 0.57)
  - `SCREENER_TREND_CONFIRM_MIN_RISING_LOWS_RATIO` (default: 0.50)
  - `SCREENER_TREND_CONFIRM_MAX_PULLBACK_PCT` (default: 0.45)
  - `SCREENER_TREND_CONFIRM_MAX_SINGLE_BAR_VOLUME_SHARE` (default: 0.55)
  - `SCREENER_TREND_CONFIRM_CACHE_SECONDS` (default: 90)
  - `SCREENER_TREND_CONFIRM_FAIL_OPEN` (default: true)
  - `SCREENER_PUBLISH_HEARTBEAT_SECONDS` (default: 60)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, ClassVar

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from pydantic import Field

from services.monitoring.notifier import TelegramConfig, TelegramNotifier
from shared.collector.prev_day_volume import PrevDayVolumeCache
from shared.config.base import ServiceConfigBase
from shared.exceptions import APIError, InfrastructureError, TradingSystemError
from shared.kis import KISAuthConfig
from shared.kis.client import KISClient
from shared.kis.ranking_client import KISRankingClient
from shared.scanner.trade_trend_priority import TradeTrendPriorityRanker
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


class ScreenerConfig(ServiceConfigBase):
    """Stock screener configuration.

    Loads from environment variables with SCREENER_ prefix.
    For non-prefixed vars (UNIVERSE_STREAM, etc.), use direct env var names.
    """

    _env_prefix: ClassVar[str | None] = "SCREENER_"

    # Screening parameters
    interval_seconds: float = Field(
        default=5.0, description="Polling interval in seconds"
    )
    rank_limit: int = Field(
        default=30, description="Number of stocks to fetch from each ranking"
    )
    top_n: int = Field(default=20, description="Number of top stocks to select")
    weight_trade_value: float = Field(
        default=0.6, description="Weight for trade value ranking"
    )
    weight_gainer: float = Field(default=0.4, description="Weight for gainer ranking")
    notify_interval_seconds: float = Field(
        default=1800.0, description="Notification interval in seconds"
    )
    publish_heartbeat_seconds: float = Field(
        default=60.0, description="Republish unchanged snapshots"
    )

    # Redis keys (not prefixed with SCREENER_)
    universe_stream: str = Field(
        default="system:universe", description="Redis stream key for universe updates"
    )
    universe_latest_key: str = Field(
        default="system:universe:latest",
        description="Redis key for latest universe snapshot",
    )

    # Dip candidate parameters
    dip_top_n: int = Field(default=20, description="Number of dip candidates to select")
    dip_min_drop_pct: float = Field(
        default=-2.0, description="Minimum drop percentage for dip candidates"
    )
    dip_latest_key: str = Field(
        default="system:dip_candidates:latest",
        description="Redis key for dip candidates",
    )

    # Telegram notification
    telegram_enabled: bool = Field(
        default=False, description="Enable Telegram notifications"
    )

    # Trend confirmation parameters
    trend_confirm_enabled: bool = Field(
        default=True, description="Enable trend confirmation filter"
    )
    trend_confirm_min_minutes_after_open: int = Field(
        default=7, description="Minutes after market open before applying trend filter"
    )
    trend_confirm_max_scan_codes: int = Field(
        default=20, description="Maximum number of codes to scan for trend confirmation"
    )
    trend_confirm_bar_count: int = Field(
        default=8, description="Number of minute bars to analyze"
    )
    trend_confirm_min_return_pct: float = Field(
        default=0.35, description="Minimum return percentage required"
    )
    trend_confirm_min_positive_ratio: float = Field(
        default=0.57, description="Minimum ratio of positive candles"
    )
    trend_confirm_min_rising_lows_ratio: float = Field(
        default=0.50, description="Minimum ratio of rising lows"
    )
    trend_confirm_max_pullback_pct: float = Field(
        default=0.45, description="Maximum pullback percentage allowed"
    )
    trend_confirm_max_single_bar_volume_share: float = Field(
        default=0.55, description="Maximum volume share in single bar"
    )
    trend_confirm_cache_seconds: float = Field(
        default=90.0, description="Cache duration for trend confirmations"
    )
    trend_confirm_fail_open: bool = Field(
        default=True, description="Keep original universe if all codes rejected"
    )

    @classmethod
    def from_env(
        cls, env_prefix: str | None = None, **overrides: Any
    ) -> "ScreenerConfig":
        """Load configuration from environment variables.

        Handles special non-prefixed environment variables:
        - UNIVERSE_STREAM → universe_stream
        - UNIVERSE_LATEST_KEY → universe_latest_key
        - DIP_CANDIDATES_LATEST_KEY → dip_latest_key
        """
        # Load standard prefixed env vars
        config_dict = cls._extract_env_vars(env_prefix or cls._env_prefix or "")

        # Handle non-prefixed environment variables
        if "UNIVERSE_STREAM" in os.environ:
            config_dict["universe_stream"] = os.environ["UNIVERSE_STREAM"]
        if "UNIVERSE_LATEST_KEY" in os.environ:
            config_dict["universe_latest_key"] = os.environ["UNIVERSE_LATEST_KEY"]
        if "DIP_CANDIDATES_LATEST_KEY" in os.environ:
            config_dict["dip_latest_key"] = os.environ["DIP_CANDIDATES_LATEST_KEY"]

        # Apply any overrides
        config_dict.update(overrides)

        return cls(**config_dict)


def _rank_to_score(rank: int, max_rank: int) -> float:
    if max_rank <= 0:
        return 0.0
    if rank <= 0:
        return 0.0
    # Higher score for better rank (1 is best)
    return (max_rank - rank + 1) / max_rank


def _code_set_signature(codes: list[str]) -> str:
    """Stable code-set signature for publish de-dupe."""
    return json.dumps(sorted(str(code) for code in codes), ensure_ascii=False)


def _should_publish_snapshot(
    *,
    signature: str,
    last_signature: str | None,
    now: float,
    last_publish_time: float,
    heartbeat_seconds: float,
) -> bool:
    if signature != last_signature:
        return True
    if heartbeat_seconds <= 0:
        return False
    return (now - last_publish_time) >= heartbeat_seconds


def _select_top_codes(
    sources: dict[str, Any],
    *,
    rank_limit: int,
    top_n: int,
    weight_trade_value: float,
    weight_gainer: float,
    trade_trend_ranker: TradeTrendPriorityRanker | None = None,
) -> tuple[
    list[str],
    dict[str, float],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    # Normalize inputs
    volume_rows = list(sources.get("kospi_volume", [])) + list(
        sources.get("kosdaq_volume", [])
    )
    gainer_rows = list(sources.get("kospi_gainer", [])) + list(
        sources.get("kosdaq_gainer", [])
    )

    # Trade-value ranking: KIS "volume-rank" returns trade_value per row.
    # We re-rank by trade_value to approximate "거래대금 순위".
    volume_sorted_by_value = sorted(
        volume_rows,
        key=lambda r: float(r.get("trade_value", 0) or 0),
        reverse=True,
    )[:rank_limit]

    score_by_code: dict[str, float] = {}
    info_by_code: dict[str, dict[str, Any]] = {}

    for i, row in enumerate(volume_sorted_by_value, start=1):
        code = str(row.get("code", "")).strip()
        if not code:
            continue
        score_by_code[code] = score_by_code.get(
            code, 0.0
        ) + weight_trade_value * _rank_to_score(i, rank_limit)
        if code not in info_by_code:
            info_by_code[code] = {
                "name": str(row.get("name", "")).strip(),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
            }

    for i, row in enumerate(gainer_rows[:rank_limit], start=1):
        code = str(row.get("code", "")).strip()
        if not code:
            continue
        score_by_code[code] = score_by_code.get(
            code, 0.0
        ) + weight_gainer * _rank_to_score(i, rank_limit)
        if code not in info_by_code:
            info_by_code[code] = {
                "name": str(row.get("name", "")).strip(),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
            }

    ranked_scores = score_by_code
    priority_metadata: dict[str, dict[str, Any]] = {}
    priority_summary: dict[str, Any] = {"enabled": False, "status": "not_configured"}

    if trade_trend_ranker is not None:
        rank_result = trade_trend_ranker.rank_codes(
            list(score_by_code.keys()), score_by_code
        )
        ranked_all_codes = rank_result.codes
        ranked_scores = rank_result.scores
        priority_metadata = rank_result.metadata
        priority_summary = rank_result.summary
    else:
        ranked_all_codes = [
            code
            for code, _score in sorted(
                score_by_code.items(), key=lambda kv: kv[1], reverse=True
            )
        ]

    # Final selection
    codes = ranked_all_codes[:top_n]

    # Normalize scores to 0-1 for readability
    if codes:
        max_score = max(ranked_scores[c] for c in codes) or 1.0
        normalized_scores = {c: round(ranked_scores[c] / max_score, 6) for c in codes}
    else:
        normalized_scores = {}

    selected_priority_metadata = {
        code: priority_metadata[code] for code in codes if code in priority_metadata
    }

    return (
        codes,
        normalized_scores,
        info_by_code,
        selected_priority_metadata,
        priority_summary,
    )


def _select_dip_candidates(
    sources: dict[str, Any],
    *,
    top_n: int,
    min_drop_pct: float,
) -> tuple[list[str], dict[str, float], dict[str, dict[str, Any]]]:
    """Select stocks with significant drops (for mean-reversion strategies).

    Combines KOSPI + KOSDAQ loser rows, filters by minimum drop percentage,
    and ranks by drop magnitude (most negative first).
    """
    loser_rows = list(sources.get("kospi_loser", [])) + list(
        sources.get("kosdaq_loser", [])
    )

    # Filter by minimum drop and sort by magnitude (most negative first)
    filtered = [
        r for r in loser_rows if float(r.get("change_pct", 0) or 0) <= min_drop_pct
    ]
    filtered.sort(key=lambda r: float(r.get("change_pct", 0) or 0))

    info_by_code: dict[str, dict[str, Any]] = {}
    codes: list[str] = []

    for row in filtered[:top_n]:
        code = str(row.get("code", "")).strip()
        if not code or code in info_by_code:
            continue
        codes.append(code)
        info_by_code[code] = {
            "name": str(row.get("name", "")).strip(),
            "price": row.get("price", 0),
            "change_pct": row.get("change_pct", 0),
        }

    # Score: normalize drop magnitude to 0-1 (most dropped = 1.0)
    if codes:
        drops = [abs(float(info_by_code[c]["change_pct"])) for c in codes]
        max_drop = max(drops) or 1.0
        scores = {
            c: round(abs(float(info_by_code[c]["change_pct"])) / max_drop, 6)
            for c in codes
        }
    else:
        scores = {}

    return codes, scores, info_by_code


def _normalize_scores_for_codes(
    scores: dict[str, float],
    codes: list[str],
) -> dict[str, float]:
    """Re-normalize scores for filtered code list."""
    if not codes:
        return {}
    selected = {c: float(scores.get(c, 0.0) or 0.0) for c in codes}
    max_score = max(selected.values()) if selected else 0.0
    if max_score <= 0:
        return dict.fromkeys(codes, 0.0)
    return {c: round(selected[c] / max_score, 6) for c in codes}


def _in_trend_confirmation_window(
    now_kst: datetime, min_minutes_after_open: int
) -> bool:
    """Return True only after market open cool-down and before close."""
    market_open = now_kst.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close = now_kst.replace(hour=15, minute=20, second=0, microsecond=0)
    if now_kst < market_open + timedelta(minutes=max(0, min_minutes_after_open)):
        return False
    return now_kst <= market_close


def _evaluate_bull_trend_profile(
    bars: list[dict[str, Any]],
    *,
    min_return_pct: float,
    min_positive_ratio: float,
    min_rising_lows_ratio: float,
    max_pullback_pct: float,
    max_single_bar_volume_share_limit: float,
) -> dict[str, Any]:
    """Evaluate whether minute bars show persistent bullish trend.

    This filters out early-session fake moves:
    - one-shot volume spike without continuation
    - fast pump followed by deep pullback
    - weak follow-through below VWAP
    """
    cleaned: list[dict[str, float]] = []
    for b in bars:
        try:
            o = float(b.get("open", 0) or 0)
            h = float(b.get("high", 0) or 0)
            low_px = float(b.get("low", 0) or 0)
            c = float(b.get("close", 0) or 0)
            v = float(b.get("volume", 0) or 0)
        except (TypeError, ValueError):
            continue
        if o <= 0 or h <= 0 or low_px <= 0 or c <= 0:
            continue
        cleaned.append(
            {"open": o, "high": h, "low": low_px, "close": c, "volume": max(0.0, v)}
        )

    bars_count = len(cleaned)
    if bars_count < 3:
        return {
            "passed": False,
            "reason": "insufficient_bars",
            "bars": bars_count,
        }

    first_open = cleaned[0]["open"]
    last_close = cleaned[-1]["close"]
    return_pct = (last_close - first_open) / first_open * 100.0

    positive_count = sum(1 for b in cleaned if b["close"] > b["open"])
    positive_ratio = positive_count / bars_count

    rising_lows = sum(
        1 for i in range(1, bars_count) if cleaned[i]["low"] >= cleaned[i - 1]["low"]
    )
    rising_lows_ratio = rising_lows / max(1, bars_count - 1)

    session_high = max(b["high"] for b in cleaned)
    pullback_pct = (session_high - last_close) / session_high * 100.0

    total_volume = sum(b["volume"] for b in cleaned)
    max_single_bar_volume_share = 0.0
    if total_volume > 0:
        max_single_bar_volume_share = max(b["volume"] / total_volume for b in cleaned)

    vwap = last_close
    if total_volume > 0:
        vwap = sum(b["close"] * b["volume"] for b in cleaned) / total_volume
    vwap_gap_pct = (last_close - vwap) / vwap * 100.0 if vwap > 0 else 0.0

    if return_pct < min_return_pct:
        reason = "insufficient_return"
    elif positive_ratio < min_positive_ratio:
        reason = "insufficient_positive_candles"
    elif rising_lows_ratio < min_rising_lows_ratio:
        reason = "weak_low_trend"
    elif pullback_pct > max_pullback_pct:
        reason = "deep_pullback"
    elif max_single_bar_volume_share > max_single_bar_volume_share_limit:
        reason = "single_bar_volume_spike"
    elif last_close < vwap:
        reason = "below_vwap"
    else:
        reason = "confirmed"

    passed = reason == "confirmed"
    return {
        "passed": passed,
        "reason": reason,
        "bars": bars_count,
        "return_pct": round(return_pct, 4),
        "positive_ratio": round(positive_ratio, 4),
        "rising_lows_ratio": round(rising_lows_ratio, 4),
        "pullback_pct": round(pullback_pct, 4),
        "max_single_bar_volume_share": round(max_single_bar_volume_share, 4),
        "vwap_gap_pct": round(vwap_gap_pct, 4),
    }


async def _apply_trend_confirmation(
    *,
    codes: list[str],
    info_by_code: dict[str, dict[str, Any]],
    config: ScreenerConfig,
    kis_client: KISClient | None,
    cache: dict[str, tuple[float, dict[str, Any]]],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Filter ranked candidates by minute-bar trend confirmation."""
    if not codes or not config.trend_confirm_enabled or kis_client is None:
        return codes, {}

    max_scan = max(1, min(config.trend_confirm_max_scan_codes, len(codes)))
    to_scan = codes[:max_scan]
    diagnostics: dict[str, dict[str, Any]] = {}
    confirmed: list[str] = []
    now_ts = time.time()

    for idx, code in enumerate(to_scan):
        cached = cache.get(code)
        if cached and cached[0] > now_ts:
            result = dict(cached[1])
        else:
            if getattr(kis_client, "is_rate_limited", False):
                diagnostics[code] = {
                    "passed": False,
                    "reason": "kis_rate_limited",
                    "bars": 0,
                }
                remaining = codes[idx:]
                if config.trend_confirm_fail_open and not confirmed:
                    logger.warning(
                        "Trend confirmation skipped during KIS rate-limit; fail-open keeps original universe"
                    )
                    return codes, diagnostics
                return confirmed + remaining, diagnostics

            bars = await kis_client.get_minute_bars(
                code, count=config.trend_confirm_bar_count
            )
            if not bars and getattr(kis_client, "is_rate_limited", False):
                result = {
                    "passed": False,
                    "reason": "kis_rate_limited",
                    "bars": 0,
                }
                diagnostics[code] = result
                cache[code] = (
                    now_ts + max(1.0, min(config.trend_confirm_cache_seconds, 10.0)),
                    dict(result),
                )
                remaining = codes[idx + 1 :]
                if config.trend_confirm_fail_open and not confirmed:
                    logger.warning(
                        "Trend confirmation hit KIS rate-limit; fail-open keeps original universe"
                    )
                    return codes, diagnostics
                return confirmed + [code] + remaining, diagnostics
            result = _evaluate_bull_trend_profile(
                bars,
                min_return_pct=config.trend_confirm_min_return_pct,
                min_positive_ratio=config.trend_confirm_min_positive_ratio,
                min_rising_lows_ratio=config.trend_confirm_min_rising_lows_ratio,
                max_pullback_pct=config.trend_confirm_max_pullback_pct,
                max_single_bar_volume_share_limit=config.trend_confirm_max_single_bar_volume_share,
            )
            cache[code] = (
                now_ts + max(1.0, config.trend_confirm_cache_seconds),
                dict(result),
            )

        diagnostics[code] = result
        if bool(result.get("passed")):
            confirmed.append(code)
            info_by_code.setdefault(code, {})["trend_confirmation"] = dict(result)

    # Only scanned slice is filterable; keep unscanned tail as-is so
    # trend_confirm_max_scan_codes does not implicitly cap universe size.
    unscanned = codes[max_scan:]
    filtered = confirmed + unscanned
    if filtered:
        return filtered, diagnostics
    if config.trend_confirm_fail_open:
        logger.warning(
            "Trend confirmation rejected all %s scanned codes; fail-open keeps original universe",
            len(to_scan),
        )
        return codes, diagnostics
    return [], diagnostics


async def run_screener(config: ScreenerConfig) -> None:
    kis_is_real = os.environ.get("KIS_IS_REAL", "true").lower() == "true"
    kis_config = KISAuthConfig(is_real=kis_is_real)
    ranking = KISRankingClient(kis_config)
    trend_kis_client = KISClient(kis_config) if config.trend_confirm_enabled else None
    trend_confirm_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    redis_client = RedisClient.get_client()
    publisher = StreamPublisher(config.universe_stream)
    trade_trend_ranker = TradeTrendPriorityRanker.from_default_config()

    last_codes: list[str] = []
    last_notified_codes: set[str] = set()
    last_notify_time: float = 0.0
    notify_interval = max(0.0, config.notify_interval_seconds)
    publish_heartbeat = max(0.0, config.publish_heartbeat_seconds)
    last_universe_signature: str | None = None
    last_universe_publish_time: float = 0.0
    last_dip_signature: str | None = None
    last_dip_publish_time: float = 0.0
    notifier: TelegramNotifier | None = None
    if config.telegram_enabled:
        # Screener is stock-only: route explicitly to TELEGRAM_STOCK_*.
        # Avoids the silent fallback `TelegramConfig.from_env()` would do
        # if TELEGRAM_BOT_TOKEN happened to be unset / pointed elsewhere.
        from shared.notification.telegram import resolve_domain_credentials

        token, chat_id = resolve_domain_credentials("stock")
        if token and chat_id:
            notifier = TelegramNotifier(TelegramConfig(token=token, chat_id=chat_id))
        else:
            logger.warning(
                "Screener telegram enabled but TELEGRAM_STOCK_* credentials missing"
            )

    # Pre-load previous-day volumes for opening_volume_surge strategy.
    prev_vol_cache = PrevDayVolumeCache()
    try:
        await prev_vol_cache.warm_all_async()
    except InfrastructureError as e:
        logger.warning("Failed to warm prev-day volume cache (infrastructure): %s", e)
    except Exception as e:
        logger.warning(
            "Failed to warm prev-day volume cache (unexpected): %s", e, exc_info=True
        )

    logger.info(
        "Stock screener started "
        f"(interval={config.interval_seconds}s, top_n={config.top_n}, "
        f"rank_limit={config.rank_limit}, trend_confirm={config.trend_confirm_enabled})"
    )

    try:
        while True:
            started = time.time()
            try:
                sources = await ranking.get_all_aggressive_sources(
                    limit=config.rank_limit
                )
                (
                    codes,
                    scores,
                    info,
                    priority_metadata,
                    priority_summary,
                ) = _select_top_codes(
                    sources,
                    rank_limit=config.rank_limit,
                    top_n=config.top_n,
                    weight_trade_value=config.weight_trade_value,
                    weight_gainer=config.weight_gainer,
                    trade_trend_ranker=trade_trend_ranker,
                )
                trend_diagnostics: dict[str, dict[str, Any]] = {}
                if (
                    codes
                    and config.trend_confirm_enabled
                    and trend_kis_client is not None
                ):
                    now_kst = datetime.now(tz=KST)
                    if _in_trend_confirmation_window(
                        now_kst, config.trend_confirm_min_minutes_after_open
                    ):
                        filtered_codes, trend_diagnostics = (
                            await _apply_trend_confirmation(
                                codes=codes,
                                info_by_code=info,
                                config=config,
                                kis_client=trend_kis_client,
                                cache=trend_confirm_cache,
                            )
                        )
                        if filtered_codes != codes:
                            logger.info(
                                "Trend confirmation filtered candidates: %s -> %s",
                                len(codes),
                                len(filtered_codes),
                            )
                        codes = filtered_codes[: config.top_n]
                        scores = _normalize_scores_for_codes(scores, codes)
                        priority_metadata = {
                            code: priority_metadata[code]
                            for code in codes
                            if code in priority_metadata
                        }

                if codes and codes != last_codes:
                    # Lazy-fill prev-day volumes for any new codes
                    await prev_vol_cache.ensure_async(codes)

                if codes:
                    names = {c: info[c]["name"] for c in codes if c in info}
                    metadata = prev_vol_cache.build_metadata(codes)
                    for code, extra in priority_metadata.items():
                        metadata.setdefault(code, {}).update(extra)
                    for code in codes:
                        diag = trend_diagnostics.get(code)
                        if not diag:
                            continue
                        code_meta = metadata.setdefault(code, {})
                        code_meta["trend_confirmed"] = bool(diag.get("passed", False))
                        code_meta["trend_reason"] = str(diag.get("reason", ""))
                        code_meta["trend_return_pct"] = float(
                            diag.get("return_pct", 0.0)
                        )
                        code_meta["trend_pullback_pct"] = float(
                            diag.get("pullback_pct", 0.0)
                        )
                        code_meta["trend_vwap_gap_pct"] = float(
                            diag.get("vwap_gap_pct", 0.0)
                        )
                        code_meta["trend_single_bar_volume_share"] = float(
                            diag.get("max_single_bar_volume_share", 0.0)
                        )
                    payload = {
                        "codes": codes,
                        "scores": scores,
                        "names": names,
                        "metadata": metadata,
                        "generated_at": datetime.now().isoformat(),
                        "sources": {
                            "counts": {k: len(v) for k, v in sources.items()},
                            "trade_trend_priority": priority_summary,
                        },
                    }
                    now = time.time()
                    signature = _code_set_signature(codes)
                    if _should_publish_snapshot(
                        signature=signature,
                        last_signature=last_universe_signature,
                        now=now,
                        last_publish_time=last_universe_publish_time,
                        heartbeat_seconds=publish_heartbeat,
                    ):
                        publisher.publish(payload)
                        redis_client.set(
                            config.universe_latest_key,
                            json.dumps(payload, ensure_ascii=False),
                            ex=86400,
                        )
                        last_universe_signature = signature
                        last_universe_publish_time = now
                        logger.info(f"Published new universe: {len(codes)} codes")

                    current_set = set(codes)
                    set_changed = current_set != last_notified_codes
                    enough_time = (now - last_notify_time) >= notify_interval

                    if notifier and set_changed and enough_time:
                        added = current_set - last_notified_codes
                        removed = last_notified_codes - current_set
                        msg_lines = [
                            "🔎 <b>Screener Update</b>",
                            f"⏱️ {payload['generated_at']}",
                            f"종목 수: {len(codes)}",
                        ]
                        if last_notified_codes and added:
                            added_names = [
                                f"{info.get(c, {}).get('name', c)}" for c in added
                            ]
                            msg_lines.append(f"🆕 편입: {', '.join(added_names)}")
                        if last_notified_codes and removed:
                            removed_names = [f"{c}" for c in removed]
                            msg_lines.append(f"🔻 제외: {', '.join(removed_names)}")
                        msg_lines.append("")
                        for idx, code in enumerate(codes, start=1):
                            stock_info = info.get(code, {})
                            name = stock_info.get("name", "")
                            price = stock_info.get("price", 0)
                            change_pct = stock_info.get("change_pct", 0)
                            sign = "+" if change_pct >= 0 else ""
                            msg_lines.append(
                                f"{idx}. {name} ({code}) {price:,.0f}원 {sign}{change_pct:.2f}%"
                            )
                        await notifier.send("\n".join(msg_lines))
                        last_notified_codes = current_set
                        last_notify_time = now

                    last_codes = codes

                # Dip candidates (for mean-reversion strategies)
                dip_codes, dip_scores, dip_info = _select_dip_candidates(
                    sources,
                    top_n=config.dip_top_n,
                    min_drop_pct=config.dip_min_drop_pct,
                )
                if dip_codes:
                    dip_payload = {
                        "codes": dip_codes,
                        "scores": dip_scores,
                        "names": {
                            c: dip_info[c]["name"] for c in dip_codes if c in dip_info
                        },
                        "info": dip_info,
                        "generated_at": datetime.now().isoformat(),
                    }
                    now = time.time()
                    dip_signature = _code_set_signature(dip_codes)
                    if _should_publish_snapshot(
                        signature=dip_signature,
                        last_signature=last_dip_signature,
                        now=now,
                        last_publish_time=last_dip_publish_time,
                        heartbeat_seconds=publish_heartbeat,
                    ):
                        redis_client.set(
                            config.dip_latest_key,
                            json.dumps(dip_payload, ensure_ascii=False),
                            ex=86400,
                        )
                        last_dip_signature = dip_signature
                        last_dip_publish_time = now
                        logger.info(f"Published dip candidates: {len(dip_codes)} codes")

            except APIError as e:
                logger.warning(f"Screener iteration failed (API error): {e}")
            except InfrastructureError as e:
                logger.warning(f"Screener iteration failed (infrastructure): {e}")
            except TradingSystemError as e:
                logger.warning(f"Screener iteration failed (trading system): {e}")
            except Exception as e:
                logger.warning(
                    f"Screener iteration failed (unexpected): {e}", exc_info=True
                )

            elapsed = time.time() - started
            sleep_for = max(0.0, config.interval_seconds - elapsed)
            await asyncio.sleep(sleep_for)
    finally:
        await ranking.close()
        if trend_kis_client:
            await trend_kis_client.close()
        if notifier:
            await notifier.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = ScreenerConfig.from_env()
    asyncio.run(run_screener(config))


if __name__ == "__main__":
    main()
