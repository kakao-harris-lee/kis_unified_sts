"""Shared futures instrument selection.

All futures daemons should resolve their active contract through this module so
paper/live/shadow services do not drift on product or symbol selection.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Literal, NamedTuple
from zoneinfo import ZoneInfo

from shared.exceptions import ConfigurationError
from shared.instruments.futures import (
    KOSPI200_LEGACY_PREFIX,
    KOSPI200_PREFIX,
    KOSPI_MINI_LEGACY_PREFIX,
    KOSPI_MINI_PREFIX,
    get_expiry_date,
    get_front_month_code,
    parse_code,
)

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: ``FuturesInstrumentConfig.source`` when ``FUTURES_STRATEGY_SYMBOL`` pins the
#: contract. A pinned contract never rolls automatically.
EXPLICIT_SYMBOL_SOURCE = "FUTURES_STRATEGY_SYMBOL"

#: Exit status of a decoupled futures daemon that stopped because the front
#: month rolled. Compose ``restart: unless-stopped`` restarts on any status, so
#: the value only has to be distinguishable in ``docker inspect``/logs from a
#: clean stop (0) and a usage error (64): 75 is sysexits ``EX_TEMPFAIL``.
FRONT_MONTH_ROLL_EXIT_CODE = 75

DEFAULT_FUTURES_PRODUCT = "mini"
SUPPORTED_FUTURES_PRODUCTS = frozenset({"mini", "kospi200"})

# KIS_FUTURES_MARKET aliases -> normalized market label. "mock" is the
# repo-wide convention for KIS's own 모의투자 (paper) account (see
# .env.example, KISAuthConfig.is_real docstring: "실전투자 여부 (False: 모의투자)");
# "paper" is accepted too so operator-facing flags/env can use either word
# for the same thing. Anything outside this map is rejected rather than
# silently treated as one side or the other.
_FUTURES_MARKET_ALIASES: dict[str, Literal["paper", "real"]] = {
    "real": "real",
    "mock": "paper",
    "paper": "paper",
}


@dataclass(frozen=True)
class FuturesInstrumentConfig:
    """Resolved futures instrument metadata."""

    symbol: str
    product: str
    source: str


@dataclass(frozen=True)
class FuturesProductContractValidation:
    ok: bool
    product: str
    expected_tick_size: float
    actual_tick_size: float
    message: str
    invalid_reasons: tuple[str, ...] = ()
    symbol: str | None = None
    symbol_source: str | None = None


_PRODUCT_TICK_SIZE = {
    "mini": 0.02,
    "kospi200": 0.05,
}

_SYMBOL_PREFIX_CONTRACTS = {
    KOSPI200_PREFIX: ("kospi200", _PRODUCT_TICK_SIZE["kospi200"]),
    KOSPI200_LEGACY_PREFIX: ("kospi200", _PRODUCT_TICK_SIZE["kospi200"]),
    KOSPI_MINI_PREFIX: ("mini", _PRODUCT_TICK_SIZE["mini"]),
    KOSPI_MINI_LEGACY_PREFIX: ("mini", _PRODUCT_TICK_SIZE["mini"]),
}


class _ParsedTickSize(NamedTuple):
    value: float
    error: str | None = None


def normalize_futures_product(value: str | None) -> str:
    """Normalize FUTURES_TRADING_PRODUCT with mini as the safe runtime default."""
    product = (value or DEFAULT_FUTURES_PRODUCT).strip().lower()
    if product not in SUPPORTED_FUTURES_PRODUCTS:
        return DEFAULT_FUTURES_PRODUCT
    return product


def _env_tick_size(value: str | None, default: float) -> _ParsedTickSize:
    if value is None or not str(value).strip():
        return _ParsedTickSize(default)
    raw_value = str(value).strip()
    try:
        return _ParsedTickSize(float(raw_value))
    except ValueError:
        return _ParsedTickSize(
            default,
            f"invalid FUTURES_SLIPPAGE_TICK_SIZE={raw_value!r}",
        )


def _symbol_prefix_contract(symbol: str) -> tuple[str, float] | None:
    normalized_symbol = symbol.strip().upper()
    for prefix, contract in _SYMBOL_PREFIX_CONTRACTS.items():
        if normalized_symbol.startswith(prefix):
            return contract
    return None


def validate_futures_runtime_product_contract(
    *,
    environ: Mapping[str, str] | None = None,
) -> FuturesProductContractValidation:
    env = os.environ if environ is None else environ
    raw_product = env.get("FUTURES_TRADING_PRODUCT")
    requested_product = (raw_product or "").strip().lower()
    product = normalize_futures_product(raw_product)
    expected_tick = _PRODUCT_TICK_SIZE[product]
    parsed_tick = _env_tick_size(env.get("FUTURES_SLIPPAGE_TICK_SIZE"), 0.02)
    actual_tick = parsed_tick.value
    invalid_reasons: list[str] = []
    if requested_product and requested_product not in SUPPORTED_FUTURES_PRODUCTS:
        allowed_products = ", ".join(sorted(SUPPORTED_FUTURES_PRODUCTS))
        invalid_reasons.append(
            f"unsupported FUTURES_TRADING_PRODUCT={raw_product!r}; "
            f"supported products: {allowed_products}"
        )
    if parsed_tick.error is not None:
        invalid_reasons.append(parsed_tick.error)
    if abs(actual_tick - expected_tick) >= 1e-9:
        invalid_reasons.append(
            f"{product} requires FUTURES_SLIPPAGE_TICK_SIZE={expected_tick:.2f}; "
            f"got {actual_tick:.2f}"
        )
    explicit_symbol = (env.get("FUTURES_STRATEGY_SYMBOL") or "").strip()
    symbol_source = "FUTURES_STRATEGY_SYMBOL" if explicit_symbol else None
    symbol_contract = (
        _symbol_prefix_contract(explicit_symbol) if explicit_symbol else None
    )
    if symbol_contract is not None:
        symbol_product, symbol_tick = symbol_contract
        if product != symbol_product or abs(actual_tick - symbol_tick) >= 1e-9:
            invalid_reasons.append(
                f"FUTURES_STRATEGY_SYMBOL={explicit_symbol} requires "
                f"product={symbol_product} and "
                f"FUTURES_SLIPPAGE_TICK_SIZE={symbol_tick:.2f}; "
                f"got product={product} and FUTURES_SLIPPAGE_TICK_SIZE={actual_tick:.2f}"
            )
    ok = not invalid_reasons
    message = "futures product contract ok" if ok else "; ".join(invalid_reasons)
    return FuturesProductContractValidation(
        ok=ok,
        product=product,
        expected_tick_size=expected_tick,
        actual_tick_size=actual_tick,
        message=message,
        invalid_reasons=tuple(invalid_reasons),
        symbol=explicit_symbol or None,
        symbol_source=symbol_source,
    )


def resolve_futures_instrument_from_env(
    *,
    environ: Mapping[str, str] | None = None,
    target_date: date | None = None,
) -> FuturesInstrumentConfig:
    """Resolve the futures contract from env with an explicit symbol override.

    ``target_date`` defaults to today in KST (not the host clock's date), so a
    daemon restarted by a front-month roll resolves the same contract the
    once-per-KST-day check (:func:`run_with_front_month_watch`) compared against
    — even if its container TZ is not Asia/Seoul.
    """
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    explicit_symbol = (env.get("FUTURES_STRATEGY_SYMBOL") or "").strip()
    if explicit_symbol:
        return FuturesInstrumentConfig(
            symbol=explicit_symbol,
            product=product,
            source=EXPLICIT_SYMBOL_SOURCE,
        )
    if target_date is None:
        target_date = datetime.now(KST).date()
    return FuturesInstrumentConfig(
        symbol=get_front_month_code(product=product, target_date=target_date),
        product=product,
        source="FUTURES_TRADING_PRODUCT",
    )


def front_month_changed(
    current_symbol: str,
    product: str,
    today: date,
    *,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return the new front-month code if ``current_symbol`` is no longer front.

    Returns ``None`` when ``current_symbol`` is still the front contract on
    ``today`` (a KST trade date — the expiry day itself is still front), or
    when ``FUTURES_STRATEGY_SYMBOL`` pins the contract explicitly.
    """
    env = os.environ if environ is None else environ
    if (env.get(EXPLICIT_SYMBOL_SOURCE) or "").strip():
        return None
    front = get_front_month_code(
        product=normalize_futures_product(product), target_date=today
    )
    return None if front == current_symbol.strip() else front


def front_month_roll_message(old_symbol: str, new_symbol: str) -> str:
    """The single WARNING text every futures process logs on a front-month roll.

    ``expiry`` is the new contract's expiry, i.e. when the next roll happens.
    Never raises: an unparseable code reports ``expiry unknown`` so the roll
    itself is not blocked by its own log line.
    """
    try:
        year, month = parse_code(new_symbol)
        expiry = get_expiry_date(year, month).isoformat()
    except (ValueError, IndexError):
        expiry = "unknown"
    return f"futures front-month rolled: {old_symbol} -> {new_symbol} (expiry {expiry})"


def _parse_hhmm(value: Any) -> time:
    hour, minute = str(value).strip().split(":")[:2]
    return time(int(hour), int(minute))


@dataclass(frozen=True)
class FrontMonthRolloverSchedule:
    """KST daily front-month check for long-lived decoupled futures daemons.

    Loaded from ``config/market_schedule.yaml::market_schedule.futures.
    front_month_rollover``; the dataclass defaults are the fallback when the
    block or a key is absent (same convention as ``MarketSchedule.load_from_yaml``).
    A non-positive poll interval falls back to the default (it would busy-spin
    every daemon), and a ``check_time`` not before ``futures.regular.open`` is
    kept but warned about (the roll restart would land inside the session).
    """

    check_time: time = time(8, 30)
    poll_interval_seconds: float = 60.0

    @classmethod
    def from_yaml(cls) -> FrontMonthRolloverSchedule:
        from shared.config.loader import ConfigLoader

        default = cls()
        defaults_text = (
            f"{default.check_time:%H:%M} KST every "
            f"{default.poll_interval_seconds:.0f}s"
        )
        try:
            data: Any = ConfigLoader.load("market_schedule.yaml")
            futures = data["market_schedule"]["futures"]
            raw = futures.get("front_month_rollover")
            if not raw:
                logger.info(
                    "front_month_rollover not configured in market_schedule.yaml; "
                    "using defaults (%s)",
                    defaults_text,
                )
                return default
            check_time = (
                _parse_hhmm(raw["check_time"])
                if "check_time" in raw
                else default.check_time
            )
            poll_interval_seconds = float(
                raw.get("poll_interval_seconds", default.poll_interval_seconds)
            )
            open_raw = (futures.get("regular") or {}).get("open")
            futures_open = _parse_hhmm(open_raw) if open_raw else None
        except Exception as exc:  # noqa: BLE001 — a bad config must not kill a daemon
            logger.warning(
                "front_month_rollover schedule unreadable (%s); using defaults (%s)",
                exc,
                defaults_text,
            )
            return default

        if not math.isfinite(poll_interval_seconds) or poll_interval_seconds <= 0:
            logger.warning(
                "front_month_rollover.poll_interval_seconds=%s must be a positive "
                "number; using %.0fs",
                poll_interval_seconds,
                default.poll_interval_seconds,
            )
            poll_interval_seconds = default.poll_interval_seconds
        if futures_open is not None and check_time >= futures_open:
            logger.warning(
                "front_month_rollover.check_time %s KST is not before the futures "
                "open %s KST; a roll restart would land inside the session",
                check_time.strftime("%H:%M"),
                futures_open.strftime("%H:%M"),
            )
        return cls(check_time=check_time, poll_interval_seconds=poll_interval_seconds)


async def run_with_front_month_watch(
    run: Callable[[], Awaitable[None]],
    stop: Callable[[], Awaitable[None]],
    instrument: FuturesInstrumentConfig,
    *,
    daemon_name: str,
    schedule: FrontMonthRolloverSchedule | None = None,
    environ: Mapping[str, str] | None = None,
    now_fn: Callable[[], datetime] = lambda: datetime.now(KST),
) -> int:
    """Run a decoupled futures daemon until it stops or its contract expires.

    A daemon resolves its contract once at start, so a process that outlives an
    expiry keeps consuming the dead code (2026-09-11: A01609 expired 09-10,
    zero ticks all morning). Alongside ``run()``, this checks once per KST day,
    at or after ``schedule.check_time``, whether ``instrument.symbol`` is still
    the front month. On a roll it logs the WARNING, awaits ``stop()`` and
    returns :data:`FRONT_MONTH_ROLL_EXIT_CODE`, so the process exits and compose
    restarts it on the new code. The daemons hold no cross-session state, so a
    restart is the whole roll. Returns 0 when ``run()`` ends for any other
    reason (a signal). A pinned ``FUTURES_STRATEGY_SYMBOL`` disables the check.
    """
    if instrument.source == EXPLICIT_SYMBOL_SOURCE:
        logger.info(
            "%s: front-month rollover check disabled — %s=%s pins the contract",
            daemon_name,
            EXPLICIT_SYMBOL_SOURCE,
            instrument.symbol,
        )
        await run()
        return 0

    schedule = schedule or FrontMonthRolloverSchedule.from_yaml()
    logger.info(
        "%s: front-month rollover check active — symbol=%s product=%s, daily at "
        "%s KST",
        daemon_name,
        instrument.symbol,
        instrument.product,
        schedule.check_time.strftime("%H:%M"),
    )
    rolled_to: str | None = None

    async def _watch() -> None:
        # Every Exception is caught per iteration: an asyncio task that raises
        # dies silently, which would leave the daemon unwatched for good and
        # re-raise at shutdown (a clean SIGTERM exiting 1). CancelledError is a
        # BaseException, so cancellation still ends the task.
        nonlocal rolled_to
        last_checked: date | None = None
        last_failure: str | None = None
        while True:
            try:
                if rolled_to is None:
                    now = now_fn().astimezone(KST)
                    if last_checked != now.date() and now.time() >= schedule.check_time:
                        new_symbol = front_month_changed(
                            instrument.symbol,
                            instrument.product,
                            now.date(),
                            environ=environ,
                        )
                        last_checked = now.date()
                        if new_symbol is not None:
                            rolled_to = new_symbol
                            logger.warning(
                                front_month_roll_message(instrument.symbol, new_symbol)
                            )
                            logger.warning(
                                "%s: exiting with status %d so compose restarts it "
                                "on %s",
                                daemon_name,
                                FRONT_MONTH_ROLL_EXIT_CODE,
                                new_symbol,
                            )
                if rolled_to is not None:
                    await stop()  # retried on the next poll if it raises
                    return
                if last_failure is not None:
                    logger.info("%s: front-month check recovered", daemon_name)
                    last_failure = None
            except Exception as exc:  # noqa: BLE001 — log and keep watching
                failure = f"{type(exc).__name__}: {exc}"
                if failure != last_failure:  # one traceback per distinct failure
                    logger.exception(
                        "%s: front-month check failed; retrying every %.0fs",
                        daemon_name,
                        schedule.poll_interval_seconds,
                    )
                    last_failure = failure
            await asyncio.sleep(schedule.poll_interval_seconds)

    watch_task = asyncio.create_task(_watch(), name=f"{daemon_name}-front-month-watch")
    try:
        await run()
    finally:
        watch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watch_task
    return FRONT_MONTH_ROLL_EXIT_CODE if rolled_to is not None else 0


def resolve_futures_market_from_env(
    *,
    environ: Mapping[str, str] | None = None,
) -> Literal["paper", "real"]:
    """Resolve ``KIS_FUTURES_MARKET`` with no silent default in either direction.

    CLAUDE.md non-negotiable: the real futures account is never funded and
    real-money order paths are policy-blocked, so an unset (or
    unrecognized) ``KIS_FUTURES_MARKET`` must never silently resolve to the
    real broker. This replaces the prior inline pattern used across
    ``scripts/trading/{flatten_all,recover_positions}.py`` —
    ``os.environ.get("KIS_FUTURES_MARKET", "real")`` — which defaulted an
    unset env var straight to the real KIS endpoint.

    Accepts ``real`` for the real (실전투자) endpoint, and ``mock`` or
    ``paper`` — synonyms for KIS's own 모의투자 (paper trading) account — for
    the non-real endpoint, all case-insensitive. Any other value, including
    unset or blank, raises.

    This selects the market-DATA endpoint only — a paper deployment
    routinely sets ``KIS_FUTURES_MARKET=real`` because KIS's mock server
    serves no futures data at all. Real-money order placement is gated
    separately by ``config/execution.yaml::execution.trading_mode`` (driven
    by the ``TRADING_MODE`` env var — ``FUTURES_EXECUTOR_TRADING_MODE`` in
    compose), never by this function's result.

    Args:
        environ: mapping to read from instead of ``os.environ`` (for tests).

    Returns:
        ``"real"`` or ``"paper"``.

    Raises:
        ConfigurationError: ``KIS_FUTURES_MARKET`` is unset, blank, or not
            one of the recognized values.
    """
    env = os.environ if environ is None else environ
    raw = env.get("KIS_FUTURES_MARKET")
    if raw is None or not raw.strip():
        raise ConfigurationError(
            "KIS_FUTURES_MARKET is not set. An unset value must never "
            "silently resolve to the real market — set it explicitly to "
            "'real' or 'mock'/'paper'."
        )
    resolved = _FUTURES_MARKET_ALIASES.get(raw.strip().lower())
    if resolved is None:
        allowed = ", ".join(sorted(set(_FUTURES_MARKET_ALIASES)))
        raise ConfigurationError(
            f"KIS_FUTURES_MARKET={raw!r} is not a recognized value; "
            f"expected one of: {allowed}"
        )
    return resolved
