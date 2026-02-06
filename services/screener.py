"""Stock universe screener service.

- Polls KIS ranking APIs every second (configurable)
- Selects Top-N "aggressive" symbols (by trade value + gainers)
- Publishes to Redis:
  - Stream: `system:universe` (xadd via StreamPublisher)
  - Key: `system:universe:latest` (JSON snapshot for fast bootstrap)

Environment variables:
  - `KIS_APP_KEY`, `KIS_APP_SECRET`, `KIS_IS_REAL` ("true"/"false")
  - `SCREENER_INTERVAL_SECONDS` (default: 1.0)
  - `SCREENER_RANK_LIMIT` (default: 30)
  - `SCREENER_TOP_N` (default: 20)
  - `SCREENER_WEIGHT_TRADE_VALUE` (default: 0.6)
  - `SCREENER_WEIGHT_GAINER` (default: 0.4)
  - `SCREENER_NOTIFY_INTERVAL_SECONDS` (default: 1800)
  - `UNIVERSE_STREAM` (default: system:universe)
  - `UNIVERSE_LATEST_KEY` (default: system:universe:latest)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from shared.kis import KISAuthConfig
from shared.kis.ranking_client import KISRankingClient
from shared.streaming.client import RedisClient
from shared.streaming.publisher import StreamPublisher
from services.monitoring.notifier import TelegramConfig, TelegramNotifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScreenerConfig:
    interval_seconds: float = float(os.environ.get("SCREENER_INTERVAL_SECONDS", "1.0"))
    rank_limit: int = int(os.environ.get("SCREENER_RANK_LIMIT", "30"))
    top_n: int = int(os.environ.get("SCREENER_TOP_N", "20"))
    weight_trade_value: float = float(os.environ.get("SCREENER_WEIGHT_TRADE_VALUE", "0.6"))
    weight_gainer: float = float(os.environ.get("SCREENER_WEIGHT_GAINER", "0.4"))
    notify_interval_seconds: float = float(
        os.environ.get("SCREENER_NOTIFY_INTERVAL_SECONDS", "1800")
    )

    universe_stream: str = os.environ.get("UNIVERSE_STREAM", "system:universe")
    universe_latest_key: str = os.environ.get(
        "UNIVERSE_LATEST_KEY", "system:universe:latest"
    )

    telegram_enabled: bool = os.environ.get(
        "SCREENER_TELEGRAM_ENABLED", "false"
    ).lower() == "true"


def _rank_to_score(rank: int, max_rank: int) -> float:
    if max_rank <= 0:
        return 0.0
    if rank <= 0:
        return 0.0
    # Higher score for better rank (1 is best)
    return (max_rank - rank + 1) / max_rank


def _select_top_codes(
    sources: dict[str, Any],
    *,
    rank_limit: int,
    top_n: int,
    weight_trade_value: float,
    weight_gainer: float,
) -> tuple[list[str], dict[str, float], dict[str, dict[str, Any]]]:
    # Normalize inputs
    volume_rows = list(sources.get("kospi_volume", [])) + list(sources.get("kosdaq_volume", []))
    gainer_rows = list(sources.get("kospi_gainer", [])) + list(sources.get("kosdaq_gainer", []))

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
        score_by_code[code] = score_by_code.get(code, 0.0) + weight_trade_value * _rank_to_score(i, rank_limit)
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
        score_by_code[code] = score_by_code.get(code, 0.0) + weight_gainer * _rank_to_score(i, rank_limit)
        if code not in info_by_code:
            info_by_code[code] = {
                "name": str(row.get("name", "")).strip(),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
            }

    # Final selection
    codes = [
        code for code, _score in sorted(score_by_code.items(), key=lambda kv: kv[1], reverse=True)
    ][:top_n]

    # Normalize scores to 0-1 for readability
    if codes:
        max_score = max(score_by_code[c] for c in codes) or 1.0
        normalized_scores = {c: round(score_by_code[c] / max_score, 6) for c in codes}
    else:
        normalized_scores = {}

    return codes, normalized_scores, info_by_code


async def run_screener(config: ScreenerConfig) -> None:
    kis_is_real = os.environ.get("KIS_IS_REAL", "true").lower() == "true"
    kis_config = KISAuthConfig(is_real=kis_is_real)
    ranking = KISRankingClient(kis_config)

    redis_client = RedisClient.get_client()
    publisher = StreamPublisher(config.universe_stream)

    last_codes: list[str] = []
    last_notified_codes: set[str] = set()
    last_notify_time: float = 0.0
    notify_interval = max(0.0, config.notify_interval_seconds)
    notifier: TelegramNotifier | None = None
    if config.telegram_enabled:
        tg_cfg = TelegramConfig.from_env()
        if tg_cfg.is_configured:
            notifier = TelegramNotifier(tg_cfg)
        else:
            logger.warning("Screener telegram enabled but credentials missing")

    logger.info(
        "Stock screener started "
        f"(interval={config.interval_seconds}s, top_n={config.top_n}, rank_limit={config.rank_limit})"
    )

    try:
        while True:
            started = time.time()
            try:
                sources = await ranking.get_all_aggressive_sources(limit=config.rank_limit)
                codes, scores, info = _select_top_codes(
                    sources,
                    rank_limit=config.rank_limit,
                    top_n=config.top_n,
                    weight_trade_value=config.weight_trade_value,
                    weight_gainer=config.weight_gainer,
                )

                if codes and codes != last_codes:
                    names = {c: info[c]["name"] for c in codes if c in info}
                    payload = {
                        "codes": codes,
                        "scores": scores,
                        "names": names,
                        "generated_at": datetime.now().isoformat(),
                        "sources": {
                            "counts": {k: len(v) for k, v in sources.items()},
                        },
                    }
                    publisher.publish(payload)
                    redis_client.set(config.universe_latest_key, json.dumps(payload, ensure_ascii=False))

                    current_set = set(codes)
                    now = time.time()
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
                            added_names = [f"{info.get(c, {}).get('name', c)}" for c in added]
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
                    logger.info(f"Published new universe: {len(codes)} codes")
            except Exception as e:
                logger.warning(f"Screener iteration failed: {e}")

            elapsed = time.time() - started
            sleep_for = max(0.0, config.interval_seconds - elapsed)
            await asyncio.sleep(sleep_for)
    finally:
        await ranking.close()
        if notifier:
            await notifier.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = ScreenerConfig()
    asyncio.run(run_screener(config))


if __name__ == "__main__":
    main()
