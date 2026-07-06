"""Futures structured-context v2 publisher — one-shot, run via scheduler (KST).

Composes the Phase A contract state, market structure, Market Risk Score, and
Phase B margin read-models into one structured context so strategy/gate code
reads a single ``futures:context:latest`` hash instead of four. Read-only: no
market data is computed here, and no order path is touched.

Every upstream input is optional — a missing/empty hash degrades the context
(``missing_components``) but never blocks publication (plan §C).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from services.futures_context.config import FuturesContextConfig
from shared.config.runtime_defaults import redis_url_from_env
from shared.models.futures_context import (
    BasisRegimeThresholds,
    ForeignFlowThresholds,
    FuturesMarketContextV2,
    build_futures_context,
    context_to_fields,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_MODES = ("premarket", "intraday", "close")


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _read_hash(redis: Any, key: str, label: str) -> dict[str, Any]:
    try:
        raw = redis.hgetall(key) or {}
    except Exception as exc:  # noqa: BLE001 — a degraded input must not kill the run
        logger.warning("%s read failed (%s): %s", label, key, exc)
        return {}
    return {str(k): v for k, v in dict(raw).items()}


def resolve_tick_value(config: FuturesContextConfig) -> float | None:
    """tick_value_krw for the reference product from config/execution.yaml.

    The execution spec is the single source of contract constants; None when
    unavailable (recorded as a missing component by the builder).
    """
    try:
        from shared.config.loader import ConfigLoader

        execution_yaml = ConfigLoader.load("execution.yaml")
        specs = (
            execution_yaml.get("futures_contract_spec", {})
            if isinstance(execution_yaml, dict)
            else {}
        )
        spec = specs.get(config.reference_spec_key)
        if isinstance(spec, Mapping):
            value = spec.get("tick_value_krw")
            return float(value) if value is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("tick value resolution failed: %s", exc)
    return None


def build_state(
    config: FuturesContextConfig, redis: Any, *, asof_ts: datetime
) -> FuturesMarketContextV2:
    """Read the four upstream hashes and fold them into one context."""
    inputs = config.inputs
    contract = _read_hash(redis, inputs.contract_latest_key, "contract")
    structure = _read_hash(redis, inputs.structure_latest_key, "structure")
    risk = _read_hash(redis, inputs.risk_latest_key, "risk")
    margin = _read_hash(redis, inputs.margin_latest_key, "margin")
    tick_value = resolve_tick_value(config)

    return build_futures_context(
        product=config.product,
        contract=contract,
        structure=structure,
        risk=risk,
        margin=margin,
        tick_value_krw=tick_value,
        basis_thresholds=BasisRegimeThresholds(
            fair_band_points=config.basis_regime.fair_band_points,
            deep_band_points=config.basis_regime.deep_band_points,
        ),
        foreign_thresholds=ForeignFlowThresholds(
            neutral_qty=config.foreign_flow_regime.neutral_qty,
            strong_qty=config.foreign_flow_regime.strong_qty,
        ),
        asof_ts=asof_ts,
    )


def publish_state(
    redis: Any, config: FuturesContextConfig, context: FuturesMarketContextV2
) -> None:
    """Publish ``futures:context:latest`` (hash) + ``stream:futures.context``."""
    fields = context_to_fields(context)
    redis_cfg = config.redis
    redis.delete(redis_cfg.latest_key)
    redis.hset(redis_cfg.latest_key, mapping=fields)
    redis.expire(redis_cfg.latest_key, redis_cfg.latest_ttl_seconds)

    event = {
        "roll_state": context.roll_state or "",
        "basis_regime": context.basis_regime or "",
        "foreign_flow_regime": context.foreign_flow_regime or "",
        "market_risk_band": context.market_risk_band or "",
        "margin_risk_level": context.margin_risk_level or "",
        "degraded": "true" if context.degraded else "false",
        "asof_ts": context.asof_ts.isoformat(),
    }
    redis.xadd(
        redis_cfg.stream_key, event, maxlen=redis_cfg.stream_maxlen, approximate=True
    )
    redis.expire(redis_cfg.stream_key, redis_cfg.stream_ttl_seconds)


def run_publish(
    *,
    config: FuturesContextConfig,
    redis: Any,
    mode: str = "intraday",
    now: datetime | None = None,
) -> FuturesMarketContextV2 | None:
    """Compose + publish one structured futures context (see module doc)."""
    if not config.enabled:
        logger.info("futures context publisher disabled (config)")
        return None

    current = now or _now_kst()
    context = build_state(config, redis, asof_ts=current)

    logger.info(
        "futures context %s: roll=%s basis=%s foreign=%s band=%s margin=%s"
        " degraded=%s missing=%s",
        mode,
        context.roll_state or "-",
        context.basis_regime or "-",
        context.foreign_flow_regime or "-",
        context.market_risk_band or "-",
        context.margin_risk_level or "-",
        context.degraded,
        json.dumps(list(context.missing_components), ensure_ascii=False),
    )

    try:
        publish_state(redis, config, context)
    except Exception:  # noqa: BLE001
        logger.exception("futures context publish failed")
    return context


def _cli(args: argparse.Namespace) -> int:
    config = FuturesContextConfig.load_or_default()

    import redis as redis_lib

    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    try:
        run_publish(config=config, redis=redis_client, mode=args.mode)
        return 0
    finally:
        redis_client.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(
        description="Futures structured-context v2 publisher"
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="intraday",
        choices=_MODES,
        help="one-shot mode (informational label in logs/stream)",
    )
    args = parser.parse_args()
    return _cli(args)


if __name__ == "__main__":
    sys.exit(main())
