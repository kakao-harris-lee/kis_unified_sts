#!/usr/bin/env python
"""Futures position reconciliation report — operator-invoked, advisory only.

Compares the live KIS broker's open futures positions against the Redis
snapshot at ``trading:futures:positions`` and records the divergence
verdict for an operator to read and act on.

**This script's exit code is still advisory — it blocks nothing on its own.**

The sentinel file it writes, however, is now a real barrier:
``services.order_router.main`` reads it (``config/kill_switch.yaml::
kill_switch.recovery_sentinel_path``, a separate file from the
kill-switch sentinel at ``kill_switch.sentinel_path``) and refuses to
enter — or continue — its consume loop while the file exists, both on
startup and on each loop iteration. A divergent broker view therefore
**does** prevent the order router from starting or continuing until an
operator clears the sentinel.

The reconciliation itself is still worth running: VirtualBroker is
in-memory and was coherent with Redis by construction, whereas the live
KIS broker keeps its own state and can drift (process kill mid-fill,
manual KIS order, partial cancel). Detecting that drift before an operator
resumes live trading has real value — but every consequence of the finding
is manual, carried out by the operator reading this output.

Outputs, all advisory:

- exit code 0 — broker and Redis agree.
- exit code 2 — ``KIS_FUTURES_MARKET`` is unset or not a recognized value;
  no verdict reached. This is a configuration error, not a broker failure —
  an unset value is rejected rather than silently defaulting to the real
  KIS endpoint (see ``shared.execution.futures_instrument.
  resolve_futures_market_from_env``).
- exit code 3 — divergence found; sentinel written; Telegram alert sent.
- exit code 4 — broker query failed; no verdict reached.
- exit code 5 — divergence found, but the sentinel could NOT be written
  (permission/path failure at the resolved sentinel path); the write path
  and the order_router *read* path (``kill_switch.recovery_sentinel_path``)
  must always be the same file, so this no longer silently falls back to a
  different path — it fails loudly instead. A distinct Telegram alert is
  sent stating the sentinel was not written; operator must investigate the
  path/permissions and re-run.
- sentinel file: the host-side path derived from
  ``config/kill_switch.yaml::kill_switch.recovery_sentinel_path`` via
  ``shared.config.runtime_defaults.host_path_for_container_runtime_path``
  (override with ``--sentinel-path``), holding a JSON divergence record.

Clearing: after operator review, delete the file (``rm <sentinel-path>``)
before the order router's next start or loop iteration. There is no
``scripts/recover_positions_clear.sh``; earlier revisions of this
docstring pointed at one that was never written.

Registered as LEGACY-007 in
``tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.csv``. The named consumer
and fail polarity that turning this into an actual barrier required are
now in place: ``services.order_router.main`` is that consumer, and its
polarity is fail-closed (refuse to proceed while the sentinel exists).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.kill_switch.config import KillSwitchConfig
from shared.config.runtime_defaults import host_path_for_container_runtime_path
from shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Single source of truth: config/kill_switch.yaml::kill_switch.recovery_sentinel_path
# (see services/order_router/main.py, which now consumes this same sentinel —
# LEGACY-007). No silent literal fallback: if config loading itself fails,
# that's a real environment problem and should raise, not paper over a
# possibly-stale hardcoded path.
#
# The config value is container-side (``/app/data/runtime/...`` — what
# order_router, running inside the futures-order-router container, actually
# reads). This script runs on the host, not in a container, so it must write
# to the host-side equivalent — derived from that same container path via
# the shared mount-mapping helper, never a second hardcoded literal. That
# keeps the read path (order_router's config) and the write path (this
# script) from silently diverging onto two different files.
DEFAULT_SENTINEL_PATH = str(
    host_path_for_container_runtime_path(
        KillSwitchConfig.from_yaml().recovery_sentinel_path
    )
)


@dataclass(frozen=True)
class _Position:
    symbol: str
    side: str  # "long" | "short"
    quantity: int

    @classmethod
    def from_redis_dict(cls, d: dict[str, Any]) -> _Position:
        side = str(d.get("side", "long")).lower()
        if side in ("buy", "BUY"):
            side = "long"
        elif side in ("sell", "SELL"):
            side = "short"
        return cls(
            symbol=str(d.get("symbol", d.get("code", ""))),
            side=side,
            quantity=int(d.get("quantity", 0)),
        )

    @classmethod
    def from_kis_dict(cls, d: dict[str, Any]) -> _Position:
        side_raw = str(d.get("side", "")).lower()
        # KIS futures balance encodes side as "1" (sell/short) or "2" (buy/long)
        # in some TR responses; the higher-level kis client normalizes to a string.
        if side_raw in ("buy", "long", "2"):
            side = "long"
        elif side_raw in ("sell", "short", "1"):
            side = "short"
        else:
            side = side_raw or "long"
        return cls(
            symbol=str(d.get("code", d.get("symbol", ""))),
            side=side,
            quantity=int(d.get("quantity", 0)),
        )


def reconcile(
    redis_positions: list[dict[str, Any]],
    broker_positions: list[dict[str, Any]],
) -> tuple[list[_Position], list[_Position], list[tuple[_Position, _Position]]]:
    """Compute (broker_only, redis_only, mismatched) divergence sets.

    - ``broker_only``: position exists at the broker, not in Redis (e.g.
      manual KIS order placed during downtime).
    - ``redis_only``: position exists in Redis, not at broker (e.g.
      broker auto-cancelled while daemon was offline).
    - ``mismatched``: same symbol on both sides, but quantity or side
      differs.
    """
    redis_pos = [_Position.from_redis_dict(d) for d in redis_positions]
    broker_pos = [_Position.from_kis_dict(d) for d in broker_positions]

    by_symbol_redis = {p.symbol: p for p in redis_pos}
    by_symbol_broker = {p.symbol: p for p in broker_pos}

    broker_only = [
        p for p in broker_pos if p.symbol not in by_symbol_redis and p.quantity > 0
    ]
    redis_only = [
        p for p in redis_pos if p.symbol not in by_symbol_broker and p.quantity > 0
    ]
    mismatched: list[tuple[_Position, _Position]] = []
    for sym, rp in by_symbol_redis.items():
        bp = by_symbol_broker.get(sym)
        if bp is None:
            continue
        if rp.side != bp.side or rp.quantity != bp.quantity:
            mismatched.append((rp, bp))

    return broker_only, redis_only, mismatched


class SentinelWriteError(RuntimeError):
    """Raised when the recovery sentinel cannot be written at its resolved path.

    Deliberately fails loudly rather than falling back to a different path:
    services/order_router/main.py reads exactly one configured path
    (``kill_switch.recovery_sentinel_path``, mapped to its host equivalent —
    see ``DEFAULT_SENTINEL_PATH`` above). A silent fallback to a second,
    different path would make the write path diverge from the read path and
    the fail-closed guard would never arm without anyone noticing.
    """


def _resolve_sentinel_path(requested: str | None) -> Path:
    """Resolve the sentinel path and verify it is writable.

    Raises:
        SentinelWriteError: the resolved path's parent directory could not
            be created, or is not writable. No fallback path is attempted —
            see :class:`SentinelWriteError`.
    """
    candidate = Path(requested) if requested else Path(DEFAULT_SENTINEL_PATH)
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        # Test write-permission with a probe file
        probe = candidate.parent / ".kis_recovery_probe"
        probe.write_text("ok")
        probe.unlink()
        return candidate
    except (PermissionError, OSError) as e:
        raise SentinelWriteError(
            f"sentinel path {candidate} is not writable: {e}"
        ) from e


def write_sentinel(
    sentinel_path: Path,
    *,
    broker_only: list[_Position],
    redis_only: list[_Position],
    mismatched: list[tuple[_Position, _Position]],
) -> None:
    payload = {
        "broker_only": [p.__dict__ for p in broker_only],
        "redis_only": [p.__dict__ for p in redis_only],
        "mismatched": [
            {"redis": rp.__dict__, "broker": bp.__dict__} for rp, bp in mismatched
        ],
    }
    sentinel_path.write_text(json.dumps(payload, indent=2))
    logger.critical(
        "Divergence recorded to %s — order_router refuses to start or "
        "continue while this file exists. Operator review required before "
        "clearing it (rm %s).",
        sentinel_path,
        sentinel_path,
    )


async def _fetch_redis_positions() -> list[dict[str, Any]]:
    from shared.streaming.trading_state import TradingStateReader

    return TradingStateReader("futures").get_positions()


async def _fetch_broker_positions() -> list[dict[str, Any]]:
    from shared.execution.futures_instrument import resolve_futures_market_from_env
    from shared.kis.auth import KISAuthConfig
    from shared.kis.client import KISClient

    # No silent default: an unset/unrecognized KIS_FUTURES_MARKET raises
    # ConfigurationError instead of resolving to the real endpoint.
    is_real = resolve_futures_market_from_env() == "real"
    auth_config = KISAuthConfig(
        app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
        app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
        is_real=is_real,
    )
    # KISClient builds/reuses its own KISAuthManager singleton from config
    # (KISAuthManager.get_instance(config)); it takes config only.
    client = KISClient(config=auth_config)
    try:
        positions = await client.get_futures_balance(
            account_no=os.environ.get("KIS_FUTURES_ACCOUNT_NO", "")
        )
    finally:
        await client.close()
    # Filter zero-quantity entries (closed positions still appear in some KIS responses)
    return [p for p in positions if int(p.get("quantity", 0)) > 0]


async def _send_telegram(summary: str) -> None:
    try:
        from shared.notification.telegram import TelegramNotifier

        notifier = TelegramNotifier(
            bot_token=os.environ.get("TELEGRAM_FUTURES_BOT_TOKEN", ""),
            chat_id=os.environ.get("TELEGRAM_FUTURES_CHAT_ID", ""),
        )
        await notifier.send_message(summary, is_critical=True)
    except Exception:
        logger.exception("Telegram alert failed")


async def _build_and_run(args: argparse.Namespace) -> int:
    redis_positions = await _fetch_redis_positions()
    logger.info("Redis reports %d open futures positions", len(redis_positions))
    try:
        broker_positions = await _fetch_broker_positions()
    except ConfigurationError as e:
        logger.error("Configuration error — no reconciliation verdict reached: %s", e)
        return 2
    except Exception:
        logger.exception("Broker query failed — no reconciliation verdict reached")
        return 4
    logger.info("Broker reports %d open futures positions", len(broker_positions))

    broker_only, redis_only, mismatched = reconcile(redis_positions, broker_positions)
    if not broker_only and not redis_only and not mismatched:
        logger.info("Position state coherent — broker and Redis agree.")
        return 0

    try:
        sentinel_path = _resolve_sentinel_path(args.sentinel_path)
    except SentinelWriteError as e:
        logger.error(
            "Divergence detected but the recovery sentinel could NOT be "
            "written: %s. order_router's fail-closed guard did NOT arm — "
            "operator must fix the path/permissions and re-run.",
            e,
        )
        await _send_telegram(
            "POSITION RECOVERY: broker/Redis divergence detected, but the "
            f"recovery sentinel could NOT be written ({e}). The order_router "
            "fail-closed guard did NOT arm. Operator action required "
            "immediately."
        )
        return 5

    write_sentinel(
        sentinel_path,
        broker_only=broker_only,
        redis_only=redis_only,
        mismatched=mismatched,
    )

    summary_parts = [
        "POSITION RECOVERY: broker/Redis divergence detected. The recovery "
        "sentinel has been written — order_router refuses to start or "
        "continue until an operator reviews this and clears it "
        f"(rm {sentinel_path})."
    ]
    if broker_only:
        summary_parts.append(f"  broker-only: {len(broker_only)} positions")
        for p in broker_only:
            summary_parts.append(f"    {p.symbol} {p.side} qty={p.quantity}")
    if redis_only:
        summary_parts.append(f"  redis-only: {len(redis_only)} positions")
        for p in redis_only:
            summary_parts.append(f"    {p.symbol} {p.side} qty={p.quantity}")
    if mismatched:
        summary_parts.append(f"  mismatched: {len(mismatched)}")
        for rp, bp in mismatched:
            summary_parts.append(
                f"    {rp.symbol} redis={rp.side}/{rp.quantity} broker={bp.side}/{bp.quantity}"
            )
    summary = "\n".join(summary_parts)
    logger.warning("\n%s", summary)
    await _send_telegram(summary)
    return 3


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sentinel-path",
        default=None,
        help=f"Override sentinel file path (default: {DEFAULT_SENTINEL_PATH})",
    )
    args = parser.parse_args()
    return asyncio.run(_build_and_run(args))


if __name__ == "__main__":
    sys.exit(main())
