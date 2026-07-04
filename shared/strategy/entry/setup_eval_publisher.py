"""Best-effort setup evaluation publishing for futures entry adapters."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from shared.strategy.gates.adapter_helper import acquire_infra_clients
from shared.strategy.market_time import now_kst

logger = logging.getLogger(__name__)

# Redis hash holding each futures setup's latest per-cycle evaluation outcome so
# "why didn't futures trade today?" is answerable at a glance. Best-effort only.
SETUP_EVAL_KEY = "trading:futures:setup_eval"

# Last (outcome, reason) logged per setup, so INFO fires only on state changes.
_last_eval_log: dict[str, str] = {}

# Per-KST-day history list settings. The latest-state hash is refreshed every
# cycle; history is appended only for in-window state changes so restarts do not
# erase the day's terminal reject reason.
SETUP_EVAL_HISTORY_KEY_PREFIX = os.environ.get(
    "SETUP_EVAL_HISTORY_KEY_PREFIX", "trading:futures:setup_eval:history"
)
SETUP_EVAL_HISTORY_TTL_SECONDS = int(
    os.environ.get("SETUP_EVAL_HISTORY_TTL_SECONDS", str(7 * 24 * 60 * 60))
)
SETUP_EVAL_HISTORY_ENABLED = os.environ.get(
    "SETUP_EVAL_HISTORY_ENABLED", "true"
).strip().lower() not in {"0", "false", "no", "off"}

_OUT_OF_WINDOW_REJECT_PREFIXES = (
    "no_market_context",
    "outside_time_window",
    "after_cutoff",
)

# In-process throttle: last in-window history state appended per (date_kst,
# setup). Redis remains the durable record across restarts.
_history_state: dict[tuple[str, str], str] = {}

AcquireClients = Callable[[], tuple[Any, Any]]
NowFn = Callable[[], datetime]


def is_in_window_eval(outcome: str, reason: str) -> bool:
    """Return True when an eval reflects an actionable in-window outcome."""
    if outcome != "reject":
        return True
    return not reason.startswith(_OUT_OF_WINDOW_REJECT_PREFIXES)


def append_setup_eval_history(
    redis: Any, name: str, outcome: str, reason: str, ts_kst: datetime
) -> None:
    """Append an in-window eval to the per-day history list, throttled by state.

    This helper is intentionally best-effort and is normally called from inside
    ``publish_setup_eval``'s broad observability guard.
    """
    if not SETUP_EVAL_HISTORY_ENABLED or redis is None:
        return
    if not is_in_window_eval(outcome, reason):
        return

    date_kst = ts_kst.date().isoformat()
    state = f"{outcome}:{reason}"
    if _history_state.get((date_kst, name)) == state:
        return
    _history_state[(date_kst, name)] = state

    key = f"{SETUP_EVAL_HISTORY_KEY_PREFIX}:{date_kst}"
    redis.rpush(
        key,
        json.dumps(
            {
                "date_kst": date_kst,
                "setup": name,
                "outcome": outcome,
                "reason": reason,
                "ts_kst": ts_kst.isoformat(),
            }
        ),
    )
    redis.expire(key, SETUP_EVAL_HISTORY_TTL_SECONDS)


def publish_setup_eval(
    name: str,
    outcome: str,
    reason: str,
    *,
    acquire_clients: AcquireClients | None = None,
    now_fn: NowFn | None = None,
    log: logging.Logger | None = None,
) -> None:
    """Log on state change and publish latest setup evaluation to Redis.

    Observability failures are swallowed so setup evaluation publishing never
    affects entry or exit decisions. ``acquire_clients`` and ``now_fn`` are
    injectable so compatibility wrappers can preserve existing monkeypatch
    points while this module remains the single owner of eval state.
    """
    target_log = log if log is not None else logger
    state = f"{outcome}:{reason}"
    if _last_eval_log.get(name) != state:
        _last_eval_log[name] = state
        if outcome == "reject":
            target_log.info("[%s] no signal this cycle: %s", name, reason)
        else:
            target_log.info("[%s] signal %s: %s", name, outcome, reason)

    try:
        clients_fn = acquire_clients or acquire_infra_clients
        current_time_fn = now_fn or now_kst
        redis, _ = clients_fn()
        if redis is not None:
            now = current_time_fn()
            redis.hset(
                SETUP_EVAL_KEY,
                name,
                json.dumps(
                    {
                        "outcome": outcome,
                        "reason": reason,
                        "ts_kst": now.isoformat(),
                    }
                ),
            )
            redis.expire(SETUP_EVAL_KEY, 86_400)
            append_setup_eval_history(redis, name, outcome, reason, now)
    except Exception:  # noqa: BLE001 - observability must never break entries
        target_log.debug("[%s] setup-eval publish failed", name, exc_info=True)


_is_in_window_eval = is_in_window_eval
_append_setup_eval_history = append_setup_eval_history
_publish_setup_eval = publish_setup_eval

__all__ = [
    "SETUP_EVAL_HISTORY_ENABLED",
    "SETUP_EVAL_HISTORY_KEY_PREFIX",
    "SETUP_EVAL_HISTORY_TTL_SECONDS",
    "SETUP_EVAL_KEY",
    "_append_setup_eval_history",
    "_history_state",
    "_is_in_window_eval",
    "_last_eval_log",
    "_publish_setup_eval",
    "append_setup_eval_history",
    "is_in_window_eval",
    "publish_setup_eval",
]
