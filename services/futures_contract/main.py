"""Futures contract / roll-state publisher — one-shot, run via scheduler (KST).

Publishes a single Redis contract so new-entry, hedge, and night-capture all
read the SAME front/next/night codes and roll classification:

* ``futures:contract:latest`` (hash, TTL 24h; 48h on premarket/close so it
  survives long weekends) — the read-model consumed by the dashboard health
  card, FuturesMarketContextV2 (Phase C), and HedgeAdvisorV2 (Phase D).
* ``stream:futures.contract`` (stream, maxlen + TTL) — roll-state transition
  audit trail.

Shadow/read-only: this lane computes calendar contract state and the night
symbol; it touches NO order path and changes NO strategy behavior. Roll-window
thresholds live in config/futures_contract.yaml.

The night front/next symbols are resolved (in priority order) from:
  1. config/futures_contract.yaml::night_master.night_front_symbol (manual
     override, when set), else
  2. config/night_futures.yaml::night_close_capture.tr_key/product_code (the
     manually-maintained night code the collector already uses).
When ``night_master.enabled`` and no symbol resolves, ``roll_state=unknown``
(live fail-closed downstream; paper fail-open trace).
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.futures_contract.config import FuturesContractConfig
from shared.config.runtime_defaults import redis_url_from_env
from shared.instruments.futures import (
    FuturesContractState,
    compute_contract_state,
    contract_state_to_fields,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

# Premarket/close runs use the longer TTL so the contract survives long
# weekends and holidays (§4.1: 48h fallback on close/premarket schedules).
_LONG_TTL_MODES = frozenset({"premarket", "close"})
_MODES = ("premarket", "intraday", "close")


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def resolve_night_symbols(
    config: FuturesContractConfig,
) -> tuple[str | None, str | None]:
    """Resolve (night_front, night_next) from config override → night collector.

    The manual override in ``config/futures_contract.yaml`` wins when set;
    otherwise the night front falls back to the collector's ``tr_key``
    (``config/night_futures.yaml``), which the operator already maintains on
    contract roll. There is no reliable next-month night code source, so
    ``night_next`` is only ever the explicit override.
    """
    night = config.night_master
    front = (night.night_front_symbol or "").strip() or None
    nxt = (night.night_next_symbol or "").strip() or None
    if front is not None:
        return front, nxt

    # Fall back to the night collector's manually-rolled tr_key.
    try:
        from services.night_futures_collector.config import NightCloseCaptureConfig

        night_cfg = NightCloseCaptureConfig.from_yaml()
        collector_front = (night_cfg.tr_key or "").strip() or None
        return collector_front, nxt
    except Exception as exc:  # noqa: BLE001 — degraded resolution must not kill the run
        logger.warning("night collector config unavailable: %s", exc)
        return None, nxt


def build_state(
    config: FuturesContractConfig,
    *,
    target_date: date,
    asof_ts: datetime,
) -> FuturesContractState:
    """Compute the contract state for ``target_date`` from config + night code."""
    night_front, night_next = resolve_night_symbols(config)
    source = "manual_override" if config.night_master.night_front_symbol else "calendar"
    return compute_contract_state(
        product=config.product,
        target_date=target_date,
        asof_ts=asof_ts,
        pre_roll_days=config.roll.pre_roll_days,
        block_front_new_entries_days=config.roll.block_front_new_entries_days,
        require_roll_on_expiry_day=config.roll.require_roll_on_expiry_day,
        night_front_symbol=night_front,
        night_next_symbol=night_next,
        night_required=config.night_master.enabled,
        source=source,
    )


def publish_state(
    redis: Any,
    config: FuturesContractConfig,
    state: FuturesContractState,
    *,
    long_ttl: bool = False,
) -> None:
    """Publish ``futures:contract:latest`` (hash) + ``stream:futures.contract``."""
    fields = contract_state_to_fields(state)
    redis_cfg = config.redis
    ttl = (
        redis_cfg.latest_ttl_fallback_seconds
        if long_ttl
        else redis_cfg.latest_ttl_seconds
    )
    # delete-then-hset so stale fields from a previous publish never linger.
    redis.delete(redis_cfg.latest_key)
    redis.hset(redis_cfg.latest_key, mapping=fields)
    redis.expire(redis_cfg.latest_key, ttl)

    event = {
        "product": state.product,
        "front_symbol": state.front_symbol,
        "roll_state": state.roll_state,
        "roll_reason": state.roll_reason,
        "days_to_expiry": str(state.days_to_expiry),
        "asof_ts": state.asof_ts.isoformat(),
    }
    redis.xadd(
        redis_cfg.stream_key,
        event,
        maxlen=redis_cfg.stream_maxlen,
        approximate=True,
    )
    redis.expire(redis_cfg.stream_key, redis_cfg.stream_ttl_seconds)


def run_publish(
    *,
    config: FuturesContractConfig,
    redis: Any,
    mode: str = "intraday",
    trade_date: date | None = None,
    now: datetime | None = None,
) -> int:
    """Compute and publish one contract-state snapshot.

    Returns 0 on success (including the disabled no-op), 1 on publish failure.
    """
    if not config.enabled:
        logger.info("futures contract publisher disabled (config)")
        return 0

    current = now or _now_kst()
    day = trade_date or current.date()
    state = build_state(config, target_date=day, asof_ts=current)

    try:
        publish_state(redis, config, state, long_ttl=mode in _LONG_TTL_MODES)
    except Exception:  # noqa: BLE001
        logger.exception("futures contract publish failed")
        return 1

    logger.info(
        "futures contract %s: date=%s product=%s front=%s next=%s night=%s"
        " dte=%d roll_state=%s (%s) new_entry_allowed=%s hedge_allowed=%s",
        mode,
        day,
        state.product,
        state.front_symbol,
        state.next_symbol,
        state.night_front_symbol or "-",
        state.days_to_expiry,
        state.roll_state,
        state.roll_reason,
        state.new_entry_front_allowed,
        state.hedge_front_allowed,
    )
    return 0


def _cli(args: argparse.Namespace) -> int:
    config = FuturesContractConfig.load_or_default()

    import redis as redis_lib

    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        return run_publish(config=config, redis=redis_client, mode=args.mode)
    finally:
        redis_client.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Futures contract / roll-state publisher"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="intraday",
        choices=_MODES,
        help="one-shot mode (premarket/close use the 48h TTL fallback)",
    )
    args = parser.parse_args()
    return _cli(args)


if __name__ == "__main__":
    sys.exit(main())
