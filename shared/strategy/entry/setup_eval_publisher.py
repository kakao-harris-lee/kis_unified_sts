"""Best-effort setup evaluation publishing for the futures entry paths.

Two producers write here: the monolithic orchestrator's Setup A/C/D entry
adapters (``shared/strategy/entry/setup_*_adapter.py``) and the decoupled
``services/decision_engine`` daemon. They must NOT share a key while the
decoupled chain runs in shadow alongside the orchestrator — a shadow row that
overwrote the orchestrator's would make both unreadable — so every key is
suffixable via ``key_suffix``. The daemon passes ``":shadow"`` outside live mode,
following this repo's REDIS KEY convention (colon-delimited:
``risk:state:futures:shadow``, ``shared/streaming/trading_state.py::_key``) —
note that STREAMS use a dotted ``.shadow`` suffix instead
(``signal.candidate.futures.shadow``); the two namespaces do not share a rule.
The default ``""`` reproduces the orchestrator's historical keys byte-for-byte.

Publishing is best-effort and NEVER raises, but it is not silent: a swallowed
Redis error is logged at WARNING once per producer state change (latched, reset
on the next success) and reported to the caller through the ``bool`` return, so
a supervising daemon can surface a degraded-observability condition instead of
believing every write landed.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from shared.risk.log_throttle import setup_eval_throttle_key
from shared.strategy.gates.adapter_helper import acquire_infra_clients
from shared.strategy.market_time import now_kst

logger = logging.getLogger(__name__)

# Redis hash holding each futures setup's latest per-cycle evaluation outcome so
# "why didn't futures trade today?" is answerable at a glance. Best-effort only.
# Producers append a ``key_suffix`` to this base (see the module docstring).
SETUP_EVAL_KEY = "trading:futures:setup_eval"

# TTL for the latest-state hash (repo default operational TTL, 24h). The
# per-day history list below keeps a longer window on purpose — it is the
# restart-surviving record of a day's terminal reason.
SETUP_EVAL_TTL_SECONDS = 24 * 60 * 60

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

# In-process dedup: last in-window history STATE appended per (date_kst, key).
# Redis remains the durable record across restarts. The stored state is the
# reason's structural kind, not the raw reason — see
# ``shared.risk.log_throttle.setup_eval_reason_kind``: reasons embed live
# measurements (``not_extreme(z=+0.42,need±1.8)``), so keying on the raw string
# made "state changed" true on essentially every tick and appended one Redis
# list row per cycle instead of one per real state change.
_history_state: dict[tuple[str, str], str] = {}

AcquireClients = Callable[[], tuple[Any, Any]]
NowFn = Callable[[], datetime]


class EvalLog(Protocol):
    """The logger surface this module actually uses.

    Typed as a Protocol rather than ``logging.Logger`` so a caller can pass a
    shim that changes ONE level's behaviour (e.g. the decision_engine's
    ``_ThrottledInfoLog``, which gates ``info`` and forwards the rest) without
    subclassing ``Logger`` or being lied to by the annotation.
    """

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None: ...


# Last publish-failure state per producer (name+key_suffix). A Redis outage
# holds for many cycles, so the swallowed error is reported once per state
# change rather than once per tick; a successful write clears the latch so the
# NEXT outage warns again.
_last_publish_failure: dict[str, str] = {}


def is_in_window_eval(outcome: str, reason: str) -> bool:
    """Return True when an eval reflects an actionable in-window outcome."""
    if outcome != "reject":
        return True
    return not reason.startswith(_OUT_OF_WINDOW_REJECT_PREFIXES)


def append_setup_eval_history(
    redis: Any,
    name: str,
    outcome: str,
    reason: str,
    ts_kst: datetime,
    *,
    key_suffix: str = "",
) -> bool:
    """Append an in-window eval to the per-day history list, deduped by state.

    ``key_suffix`` isolates a producer's history list from the orchestrator's
    (``""`` = the orchestrator's historical key). The list key is
    ``<prefix><suffix>:<date_kst>``, so the date stays the last segment.

    Returns True when there is nothing left to do — the append happened, was
    deduped, or is disabled — and lets any Redis exception propagate to
    ``publish_setup_eval``'s guard, which is what turns it into a False result.
    """
    if not SETUP_EVAL_HISTORY_ENABLED or redis is None:
        return True
    if not is_in_window_eval(outcome, reason):
        return True

    date_kst = ts_kst.date().isoformat()
    # Structural state (measurements stripped) — a reason whose only change is
    # its embedded numbers is the SAME state and must not append a second row.
    state = setup_eval_throttle_key(name, outcome, reason)
    dedup_key = (date_kst, f"{name}{key_suffix}")
    if _history_state.get(dedup_key) == state:
        return True
    _history_state[dedup_key] = state

    key = f"{SETUP_EVAL_HISTORY_KEY_PREFIX}{key_suffix}:{date_kst}"
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
    return True


def publish_setup_eval(
    name: str,
    outcome: str,
    reason: str,
    *,
    acquire_clients: AcquireClients | None = None,
    now_fn: NowFn | None = None,
    log: EvalLog | None = None,
    key_suffix: str = "",
) -> bool:
    """Log on state change and publish latest setup evaluation to Redis.

    ``key_suffix`` namespaces BOTH Redis keys (hash and per-day history list)
    so two producers can write concurrently without overwriting each other; the
    default ``""`` is the orchestrator adapters' historical key set.

    Returns True when the write landed (or there was no client to write to,
    which is the deliberately-unwired case), False when a Redis error was
    swallowed. The exception is never re-raised — setup-eval publishing must
    not affect entry or exit decisions — but it IS reported: at WARNING once
    per producer state change, and to the caller through this return value.
    Reporting it only at DEBUG made an outage indistinguishable from a healthy
    write, which is the defect this signature exists to prevent.

    ``acquire_clients`` and ``now_fn`` are injectable so compatibility wrappers
    can preserve existing monkeypatch points while this module remains the
    single owner of eval state.
    """
    target_log = log if log is not None else logger
    producer_key = f"{name}{key_suffix}"
    # Structural state (measurements stripped): a reason whose only change is
    # its embedded numbers is the SAME state, so the orchestrator path stops
    # re-logging one INFO line per measurement.
    state = setup_eval_throttle_key(name, outcome, reason)
    if _last_eval_log.get(producer_key) != state:
        _last_eval_log[producer_key] = state
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
            eval_key = f"{SETUP_EVAL_KEY}{key_suffix}"
            redis.hset(
                eval_key,
                name,
                json.dumps(
                    {
                        "outcome": outcome,
                        "reason": reason,
                        "ts_kst": now.isoformat(),
                    }
                ),
            )
            redis.expire(eval_key, SETUP_EVAL_TTL_SECONDS)
            append_setup_eval_history(
                redis, name, outcome, reason, now, key_suffix=key_suffix
            )
    except Exception as exc:  # noqa: BLE001 - observability must never break entries
        failure = f"{type(exc).__name__}: {exc}"
        if _last_publish_failure.get(producer_key) != failure:
            _last_publish_failure[producer_key] = failure
            target_log.warning(
                "[%s] setup-eval publish failed; observability degraded "
                "(entries unaffected): %s",
                producer_key,
                failure,
                exc_info=True,
            )
        return False

    # Clear the latch so the NEXT outage warns again. Recovery is NOT logged
    # here: ``target_log.info`` is the caller's throttled eval-line channel
    # (see the decision_engine's _ThrottledInfoLog), which would swallow the
    # notice on exactly the ticks it matters. Callers that care learn about
    # recovery from the ``True`` return.
    _last_publish_failure.pop(producer_key, None)
    return True


_is_in_window_eval = is_in_window_eval
_append_setup_eval_history = append_setup_eval_history
_publish_setup_eval = publish_setup_eval

__all__ = [
    "SETUP_EVAL_HISTORY_ENABLED",
    "SETUP_EVAL_TTL_SECONDS",
    "EvalLog",
    "_last_publish_failure",
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
