"""Per-reason log throttle shared by the stock and futures market-risk gates.

Both consumer-side gate wirings emit an observational shadow-mode log (would
the gate have blocked this entry?) that repeats every evaluation cycle for as
long as the underlying band/reason holds. Logging every cycle would flood the
logs, so both sides throttle to at most once per configured interval — but
independently *per reason* (e.g. per band label), not behind one global
timestamp, so a newly-appearing reason is never masked by an unrelated
reason's recent log.

:func:`gate_log_throttle_key` derives the cache key both consumers pass to
:class:`ReasonLogThrottle` from STRUCTURAL fields (band, side) rather than
the gate decision's free-text ``reason`` string, which embeds ``score`` and
would otherwise reset the throttle on every gate refresh.

:func:`setup_eval_throttle_key` does the same job for the futures setup-eval
observability: a setup's ``last_reject_reason`` embeds live measurements
(``not_extreme(z=+0.42,need±1.8)``), so the raw string is a different key on
almost every tick — it would defeat the throttle AND grow the cache without
bound. Keying on the reason's structural prefix (everything before the first
``(``) collapses one cause to one slot.

Consumers:
- ``services/stock_strategy/daemon_market_risk.py`` (``_log_market_risk_would_block``)
- ``services/decision_engine/main.py`` (``_maybe_log_shadow_gate``,
  ``_publish_setup_eval``)
- ``shared/strategy/entry/setup_eval_publisher.py`` (history-append dedup)
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "ReasonLogThrottle",
    "gate_log_throttle_key",
    "setup_eval_reason_kind",
    "setup_eval_throttle_key",
]


@dataclass
class ReasonLogThrottle:
    """Throttles log emission to at most once per ``interval_seconds`` per reason.

    ``now`` is caller-supplied (monotonic or wall clock, whichever the caller
    already uses) so this stays a pure cache with no clock dependency of its
    own.
    """

    interval_seconds: float
    _last_logged: dict[str, float] = field(default_factory=dict, init=False)

    def should_log(self, reason: str, now: float) -> bool:
        """Return True (and record ``now``) iff ``reason`` may log now.

        The first observation of any reason always logs. A subsequent
        observation of the SAME reason logs again only once
        ``interval_seconds`` has elapsed since it last logged.
        """
        last = self._last_logged.get(reason)
        if last is not None and now - last < self.interval_seconds:
            return False
        self._last_logged[reason] = now
        return True


def gate_log_throttle_key(
    *, band: str | None, reason: str, side: str | None = None
) -> str:
    """Throttle key for a market-risk-gate shadow-observation log.

    Built from STRUCTURAL fields only: ``band`` (the reaction-matrix band
    label, e.g. ``"HIGH"``) is the primary key. ``reason`` is used only as a
    fallback for fail-open paths that carry no band at all (missing hash,
    stale, gate off, ...) — those still need a stable per-cause key, and
    ``reason`` is the only distinguishing field they carry.

    Deliberately never parses ``score`` out of ``reason`` (a free-text string
    like ``"market_risk band=HIGH score=74.2 rule=block_new_long"``): score
    changes on every gate refresh — a 30-min cron cadence today, but that
    interval is itself config, not a contract — and keying on the full
    ``reason`` string would silently reset the throttle on every such tick,
    which is exactly the bug this function exists to prevent.

    ``side`` (e.g. ``signal.direction``) distinguishes two structurally
    different verdicts that would otherwise collide under the same band —
    e.g. HIGH blocking new longs while allowing shorts at a reduced size.
    Pass it when the caller has it directly (never parsed out of ``reason``);
    omit it for asymmetric-free callers (stock is long-only).

    Both branches are namespaced (``band:...`` / ``reason:...``) so a
    fail-open ``reason`` string can never collide with a band label that
    happens to read the same (e.g. a reason literally equal to ``"HIGH"``
    would otherwise share a cache slot with band ``HIGH``).
    """
    base = f"band:{band}" if band is not None else f"reason:{reason}"
    return f"{base}:{side}" if side is not None else base


def setup_eval_reason_kind(reason: str) -> str:
    """Return the STRUCTURAL kind of a setup-eval reason (measurements stripped).

    Setup reject reasons are built as ``kind(measurements)`` — e.g.
    ``not_extreme(z=+0.42,need±1.8)``, ``vol_below_gate(0.85<0.9)``,
    ``outside_time_window(297m∉[10,60])``, ``low_confidence(0.55<0.6)`` — while
    others carry no measurement at all (``no_atr``, ``no_vwap``,
    ``no_market_context``).
    The parenthesised part changes on essentially every 60 s tick, so it must
    not participate in any identity used for throttling or deduplication:

      * as a throttle key it would reset the throttle every tick, i.e. no
        throttle at all, and grow ``ReasonLogThrottle``'s cache without bound;
      * as a history-dedup key it appends one Redis list row per tick instead
        of one per state change.

    Only the leading kind is returned; the full reason (numbers included) is
    still what gets logged and stored, so no diagnostic detail is lost.

    Non-``str`` input is coerced rather than rejected: this sits on the
    best-effort observability path (a caller may hand it a signal attribute
    that is not yet a string), and the previous key construction was an f-string
    that accepted anything. Raising here would turn a logging concern into a
    trading-path exception.
    """
    text = reason if isinstance(reason, str) else str(reason)
    head, _, _ = text.partition("(")
    return head.strip() or text


def setup_eval_throttle_key(name: str, outcome: str, reason: str) -> str:
    """Throttle/dedup key for one setup's evaluation outcome.

    Built from the setup's registry name, the outcome (``reject``/``fired``)
    and the reason's structural kind only — see
    :func:`setup_eval_reason_kind` for why the measurements are dropped.
    Namespaced like :func:`gate_log_throttle_key` so it cannot collide with a
    gate key in a shared cache.
    """
    return f"setup_eval:{name}:{outcome}:{setup_eval_reason_kind(reason)}"
