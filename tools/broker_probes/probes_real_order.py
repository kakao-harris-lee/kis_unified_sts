"""REAL-MONEY order-emitting probe — the ONLY module here that can place a live order."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import yaml

from tools.broker_probes import probes_order
from tools.broker_probes._tick_math import (
    corroborate_tick as _corroborate_tick,
)
from tools.broker_probes._tick_math import (
    decimal_field as _decimal_field,
)
from tools.broker_probes.common import (
    ENV_REAL,
    REAL_BASE_URL,
    REAL_HOST,
    ProbeError,
    ProbeRun,
    ReadOnlyCall,
    SafetyViolation,
    account_fingerprint,
    assert_no_live_futures_config,
    assert_read_only_call,
    build_auth_config,
    dry_run_banner,
    http_json,
    is_rate_limited,
    mask_account,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    summarize_latencies,
    warn_shared_token_cache,
)
from tools.broker_probes.probes_order import (
    DEFAULT_PACE_S,
    Tick,
    TickPrice,
    _CallPacer,
    effective_interval_ms,
    odno_key,
    record_odno_wire_format,
    snap_to_tick,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MARKET_SCHEDULE_CONFIG = _REPO_ROOT / "config" / "market_schedule.yaml"


_ORDER_PATH = "/uapi/domestic-futureoption/v1/trading/order"
_CANCEL_PATH = "/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
_INQUIRE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-ccnl"

_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_PRICE_TR = "FHMIF10000000"

_DEPOSIT_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-deposit"
_DEPOSIT_TR = "CTRP6550R"

_BALANCE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
_BALANCE_TR = "CTFO6118R"

_PSBL_ORDER_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-psbl-order"
_PSBL_ORDER_TR = "TTTO5105R"

_INQUIRE_TR_REAL = "TTTO5201R"

PREFLIGHT_ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        _DEPOSIT_TR,
        _DEPOSIT_PATH,
        "선물옵션 총자산현황 — order-available cash/total. Read-only inquiry; "
        "the abort condition 'order-available amount is zero or unreadable' is "
        "derived from it.",
    ),
    ReadOnlyCall(
        _BALANCE_TR,
        _BALANCE_PATH,
        "선물옵션 잔고현황 — current positions. Read-only inquiry; the abort "
        "condition 'any position already exists' is derived from it.",
    ),
    ReadOnlyCall(
        _PSBL_ORDER_TR,
        _PSBL_ORDER_PATH,
        "선물옵션 주문가능 — order-available QUANTITY at the intended resting "
        "price. Read-only inquiry, requires a price but places nothing.",
    ),
    ReadOnlyCall(
        _PRICE_TR,
        _PRICE_PATH,
        "선물옵션 시세 — touch, daily price band (futs_mxpr/futs_llam) and "
        "circuit-breaker band. Quotations endpoint; no account fields.",
    ),
    ReadOnlyCall(
        _INQUIRE_TR_REAL,
        _INQUIRE_PATH,
        "선물옵션 주문체결내역조회 — pre-existing open orders on the account. "
        "A GET on a /trading/ path; reads only. Cross-checked against the "
        "audited SoT by assert_inquire_tr_matches_sot().",
    ),
)


def assert_inquire_tr_matches_sot() -> str:
    """Cross-check :data:`_INQUIRE_TR_REAL` against the audited TR-id SoT."""
    from shared.execution.tr_ids import get_tr_ids

    sot = get_tr_ids()["futures_inquire_day_real"]
    if sot != _INQUIRE_TR_REAL:
        raise SafetyViolation(
            f"the stage-1 allowlist carries inquire TR {_INQUIRE_TR_REAL!r} but "
            f"the audited SoT (shared/execution/tr_ids.py, overlaid by "
            f"config/kis/tr_ids.yaml) now says {sot!r}. Refusing to run with a "
            "stale allowlist — update the constant in a reviewed change."
        )
    return sot


REAL_ORDER_CONFIRM_FLAG = "--i-understand-this-places-real-orders"
_CONFIRM_DEST = "i_understand_this_places_real_orders"

HARD_MAX_QUANTITY = 1

HARD_MAX_SAMPLES = 10

DEFAULT_REAL_SAMPLES = 3

HARD_MAX_RAMP_ATTEMPTS = 4

HARD_MAX_CANCEL_RETRIES = 5

HARD_MAX_STAGE1_AGE_S = 3600.0

HARD_MAX_PAGES = 10

DEFAULT_REAL_RESTING_OFFSET_PCT = 5.0

DEFAULT_MIN_TOUCH_DISTANCE_PCT = 3.0

DEFAULT_MIN_SESSION_REMAINING_S = 1800.0


VERDICT_PREFLIGHT_READY = "READY_FOR_STAGE_2"
VERDICT_COMPLETED = "COMPLETED"

ABORT_FINGERPRINT_MISMATCH = "ABORT_ACCOUNT_FINGERPRINT_MISMATCH"
ABORT_MARKET_CLOSED = "ABORT_MARKET_CLOSED"
ABORT_SESSION_TOO_SHORT = "ABORT_SESSION_REMAINING_TOO_SHORT"
ABORT_ORDER_AVAILABLE_ZERO = "ABORT_ORDER_AVAILABLE_ZERO_OR_UNREADABLE"
ABORT_POSITION_EXISTS = "ABORT_POSITION_ALREADY_EXISTS"
ABORT_OPEN_ORDERS_EXIST = "ABORT_PREEXISTING_OPEN_ORDERS"
ABORT_ACCOUNT_STATE_UNREADABLE = "ABORT_ACCOUNT_STATE_UNREADABLE"
ABORT_INSTRUMENT_UNRESOLVED = "ABORT_INSTRUMENT_OR_TICK_UNRESOLVED"
ABORT_NOT_SMALLEST_CONTRACT = "ABORT_NOT_SMALLEST_REGISTERED_CONTRACT"
ABORT_TOUCH_UNREADABLE = "ABORT_TOUCH_PRICE_UNREADABLE"
ABORT_PRICE_BAND_UNREADABLE = "ABORT_PRICE_BAND_UNREADABLE"
ABORT_PRICE_OUTSIDE_BAND = "ABORT_RESTING_PRICE_OUTSIDE_DAILY_BAND"
ABORT_PRICE_TOO_CLOSE = "ABORT_RESTING_PRICE_TOO_CLOSE_TO_TOUCH"
ABORT_PRICE_OFF_TICK = "ABORT_RESTING_PRICE_NOT_A_TICK_MULTIPLE"
ABORT_NOTIONAL_CAP = "ABORT_NOTIONAL_CAP_EXCEEDED"
ABORT_CUMULATIVE_NOTIONAL_CAP = "ABORT_CUMULATIVE_NOTIONAL_CAP_EXCEEDED"
ABORT_SAMPLE_CAP = "ABORT_SAMPLE_CAP_EXCEEDED"
ABORT_QUANTITY_CAP = "ABORT_QUANTITY_CAP_EXCEEDED"
ABORT_FILL_DETECTED = "ABORT_FILL_DETECTED"
ABORT_FILL_STATE_UNKNOWN = "ABORT_FILL_STATE_UNKNOWN"
ABORT_CANCEL_FAILED = "ABORT_CANCEL_FAILED_ORDER_MAY_BE_RESTING"
ABORT_STAGE1_MISSING = "ABORT_STAGE1_ARTIFACT_MISSING_OR_UNREADABLE"
ABORT_STAGE1_UNUSABLE = "ABORT_STAGE1_ARTIFACT_NOT_A_PASSING_PREFLIGHT"
ABORT_STAGE1_STALE = "ABORT_STAGE1_ARTIFACT_STALE"
ABORT_SUBMIT_REJECTED = "ABORT_SUBMIT_REJECTED"


class RealOrderAbort(ProbeError):
    """A guard stopped the run. The abort IS the result, so it gets an artifact."""

    def __init__(self, verdict: str, message: str) -> None:
        super().__init__(f"{verdict}: {message}")
        self.verdict = verdict
        self.detail = message


def assert_real_host(url: str) -> None:
    """Reject any URL that is not the KIS REAL (실전) REST host."""
    host = urlparse(url).hostname or ""
    if host != REAL_HOST:
        raise SafetyViolation(
            f"real-order probe refused: host {host!r} is not the real host "
            f"{REAL_HOST!r} (url={url!r}). This probe measures the REAL "
            "environment; a call to any other host would mislabel the result."
        )


def assert_real_trading_tr(tr_id: str) -> None:
    """Reject a trading TR that is not a real (non-``V``-prefixed) TR."""
    tr = (tr_id or "").strip().upper()
    if not tr:
        raise SafetyViolation("empty tr_id passed to a real trading call")
    if tr.startswith("V"):
        raise SafetyViolation(
            f"trading TR {tr!r} is a MOCK (V-prefixed) TR and must not be sent "
            "to the real host (config/kis/tr_ids.yaml: real = TTT*/STTN*/CTF*, "
            "mock = VTT*/VTF*)."
        )


def assert_real_order_confirmation(args: argparse.Namespace) -> None:
    """Refuse live mode without the long-form authorisation flag."""
    if not getattr(args, "confirm", False):
        return
    if getattr(args, _CONFIRM_DEST, False) is not True:
        raise SafetyViolation(
            "REFUSED: live mode on a REAL brokerage account requires the "
            f"explicit flag {REAL_ORDER_CONFIRM_FLAG}. It is spelled out in full "
            "and argparse abbreviation is disabled for this probe, so no prefix "
            "of it will do. Re-read docs/runbooks/kis-capability-probes.md "
            "§5.7 before passing it."
        )


def _int_field(container: Any, key: str) -> int | None:
    value = _decimal_field(container, key)
    if value is None:
        return None
    try:
        return int(value)
    except (ArithmeticError, ValueError):
        return None


def _rows(parsed: Any, key: str = "output1") -> list[dict[str, Any]]:
    rows = parsed.get(key) if isinstance(parsed, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _ok(parsed: Any) -> bool:
    """True only when the broker explicitly said ``rt_cd == "0"``."""
    return isinstance(parsed, dict) and str(parsed.get("rt_cd", "")).strip() == "0"


def _reject(parsed: Any) -> str:
    if not isinstance(parsed, dict):
        return "non-dict response"
    return (
        f"rt_cd={parsed.get('rt_cd')!r} msg_cd={parsed.get('msg_cd')!r} "
        f"msg1={str(parsed.get('msg1', ''))[:200]!r}"
    )


def assert_account_fingerprint(actual: str, expected: str) -> None:
    """Refuse unless the wired account is the one the operator named."""
    expected_clean = (expected or "").strip().lower()
    if not expected_clean:
        raise RealOrderAbort(
            ABORT_FINGERPRINT_MISMATCH,
            "--expect-account-fingerprint is required. Read the fingerprint off "
            "a prior artifact's credentials.account_fingerprint and pass it; the "
            "probe will not infer which account it is allowed to trade.",
        )
    if actual != expected_clean:
        raise RealOrderAbort(
            ABORT_FINGERPRINT_MISMATCH,
            f"wired account fingerprint {actual!r} != expected "
            f"{expected_clean!r}. The environment is pointing at a different "
            "account than the one authorised. Do not re-run with the observed "
            "value — fix the credential wiring.",
        )


def market_session_state(now: datetime) -> dict[str, Any]:
    """The futures day-session state, read from config (never hardcoded hours)."""
    state: dict[str, Any] = {
        "now_kst": now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "config/market_schedule.yaml::market_schedule.futures.regular",
        "open": False,
        "reason": "",
        "seconds_remaining": None,
    }
    try:
        data = yaml.safe_load(_MARKET_SCHEDULE_CONFIG.read_text(encoding="utf-8")) or {}
        regular = data["market_schedule"]["futures"]["regular"]
        open_h, open_m = (int(p) for p in str(regular["open"]).split(":"))
        close_h, close_m = (int(p) for p in str(regular["close"]).split(":"))
        holidays = {str(d).strip() for d in (data.get("holidays") or [])}
    except Exception as exc:  # noqa: BLE001 — fail-closed, and say why
        state["reason"] = (
            f"could not read the session window: {type(exc).__name__}: {exc}"
        )
        return state

    opens = now.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    closes = now.replace(hour=close_h, minute=close_m, second=0, microsecond=0)
    state["window_kst"] = f"{regular['open']}-{regular['close']}"
    state["is_weekend"] = now.weekday() >= 5
    state["is_holiday"] = now.strftime("%Y-%m-%d") in holidays
    state["seconds_remaining"] = max(0.0, (closes - now).total_seconds())
    if state["is_weekend"]:
        state["reason"] = "KST date is a weekend"
    elif state["is_holiday"]:
        state["reason"] = "KST date is in config/market_schedule.yaml::holidays"
    elif not (opens <= now <= closes):
        state["reason"] = (
            f"local KST time {now:%H:%M} is outside the futures day session "
            f"{state['window_kst']}"
        )
    else:
        state["open"] = True
        state["reason"] = "inside the futures day session"
    return state


def assert_market_open(now: datetime, *, min_remaining_s: float) -> dict[str, Any]:
    """Refuse outside the futures day session, and refuse near the close."""
    state = market_session_state(now)
    if not state["open"]:
        raise RealOrderAbort(ABORT_MARKET_CLOSED, str(state["reason"]))
    remaining = float(state["seconds_remaining"] or 0.0)
    if remaining < float(min_remaining_s):
        raise RealOrderAbort(
            ABORT_SESSION_TOO_SHORT,
            f"only {remaining:.0f}s of the session remain, below the required "
            f"{min_remaining_s:.0f}s. A cancel is not accepted after the close, "
            "so the run is refused rather than started.",
        )
    return state


def assert_order_available(deposit_output: Any, parsed: Any) -> dict[str, Any]:
    """Refuse unless the broker reports a positive order-available amount."""
    if not _ok(parsed):
        raise RealOrderAbort(
            ABORT_ACCOUNT_STATE_UNREADABLE,
            f"{_DEPOSIT_TR} did not answer cleanly ({_reject(parsed)}); the "
            "order-available amount is unestablished, which is not the same as "
            "'sufficient'.",
        )
    cash = _decimal_field(deposit_output, "ord_psbl_cash")
    total = _decimal_field(deposit_output, "ord_psbl_tota")
    record = {
        "tr_id": _DEPOSIT_TR,
        "ord_psbl_cash": str(cash) if cash is not None else None,
        "ord_psbl_tota": str(total) if total is not None else None,
        "dnca_tota": str(_decimal_field(deposit_output, "dnca_tota") or ""),
        "unreadable_means_refused": (
            "A missing or unparseable field is recorded as null and refused. It "
            "is never folded into 0, and 0 is never read as 'probably fine'."
        ),
    }
    usable = total if total is not None else cash
    if usable is None or usable <= 0:
        raise RealOrderAbort(
            ABORT_ORDER_AVAILABLE_ZERO,
            f"order-available amount is zero or unreadable ({record}). Stage 2 "
            "cannot be authorised. Per operator policy the real futures account "
            "is deliberately never funded, so a true zero is a TERMINAL verdict "
            "(not a fundable state). Only if the amount is UNREADABLE (not a "
            "genuine zero) fix the wiring and re-run stage 1.",
        )
    record["order_available_krw"] = str(usable)
    return record


def assert_flat_account(parsed: Any) -> dict[str, Any]:
    """Refuse unless the account holds no futures position at all."""
    if not _ok(parsed):
        raise RealOrderAbort(
            ABORT_ACCOUNT_STATE_UNREADABLE,
            f"{_BALANCE_TR} did not answer cleanly ({_reject(parsed)}); the "
            "position state is unestablished. Refusing, because 'no rows "
            "returned' and 'query failed' look identical downstream.",
        )
    rows = _rows(parsed)
    held: list[dict[str, Any]] = []
    for row in rows:
        qty = _int_field(row, "cblc_qty")
        if qty is None or qty != 0:
            held.append(
                {
                    "shtn_pdno": str(row.get("shtn_pdno", "")).strip(),
                    "sll_buy_dvsn_name": str(row.get("sll_buy_dvsn_name", "")).strip(),
                    "cblc_qty": None if qty is None else qty,
                    "lqd_psbl_qty": _int_field(row, "lqd_psbl_qty"),
                }
            )
    record = {
        "tr_id": _BALANCE_TR,
        "row_count": len(rows),
        "held_rows": held,
        "empty_semantics": (
            "An empty output1 means 'no positions', not 'no such fields'. The "
            "row count is recorded explicitly so an empty response is never "
            "mistaken for an unanswered one."
        ),
    }
    if held:
        raise RealOrderAbort(
            ABORT_POSITION_EXISTS,
            f"the account already holds {len(held)} futures position row(s): "
            f"{held}. Flatten manually and re-run stage 1 — a fill on this "
            "account could not be attributed to the probe otherwise.",
        )
    return record


def assert_no_preexisting_open_orders(parsed: Any, symbol: str) -> dict[str, Any]:
    """Refuse if the account already has orders in today's order/fill listing."""
    if not _ok(parsed):
        raise RealOrderAbort(
            ABORT_ACCOUNT_STATE_UNREADABLE,
            f"the open-order listing did not answer cleanly ({_reject(parsed)}); "
            "pre-existing orders are unestablished.",
        )
    rows = _rows(parsed)
    record = {
        "row_count": len(rows),
        "symbol_queried": symbol,
        "sample_odnos": [str(r.get("odno", "")).strip() for r in rows[:5]],
        "predicate": (
            "presence of ANY row for today, not qty>0 — the campaign showed "
            "qty>0 does not mean cancellable (2026-07-31 semantics #2)."
        ),
    }
    if rows:
        raise RealOrderAbort(
            ABORT_OPEN_ORDERS_EXIST,
            f"today's order listing already has {len(rows)} row(s) for {symbol} "
            f"(odno sample {record['sample_odnos']}). Resolve them by hand: a "
            "second order source on this account makes fill attribution and the "
            "cancel verification unsound.",
        )
    return record


def resolve_smallest_contract(symbol: str) -> tuple[Any, Tick, dict[str, Any]]:
    """Resolve ``symbol``'s contract spec and refuse anything but the smallest."""
    from shared.instruments.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )

    config_path = probes_order._EXECUTION_CONFIG
    try:
        registry = ContractSpecRegistry.from_yaml(str(config_path))
        spec = resolve_contract_spec(symbol, registry)
    except Exception as exc:  # noqa: BLE001 — an unresolved instrument aborts
        raise RealOrderAbort(
            ABORT_INSTRUMENT_UNRESOLVED,
            f"no contract spec for --symbol {symbol} in {config_path}: {exc}. "
            "Register the prefix rather than hardcoding a multiplier or tick.",
        ) from exc

    multipliers = {
        name: int(s.multiplier_krw_per_point) for name, s in registry.specs.items()
    }
    smallest = min(multipliers.values()) if multipliers else 0
    largest = max(multipliers.values()) if multipliers else 0
    record = {
        "resolved_product": spec.name,
        "resolved_multiplier_krw_per_point": int(spec.multiplier_krw_per_point),
        "registered_multipliers": multipliers,
        "smallest_registered_multiplier": smallest,
        "multiplier_ratio_to_largest": (
            f"{int(spec.multiplier_krw_per_point)}/{largest}" if largest else None
        ),
        "tick_size_points": str(spec.tick_size_points),
        "source": (
            f"{config_path}::futures_contract_spec.{spec.name} "
            f"(matched symbol_prefix {spec.symbol_prefix!r})"
        ),
    }
    if int(spec.multiplier_krw_per_point) != smallest:
        raise RealOrderAbort(
            ABORT_NOT_SMALLEST_CONTRACT,
            f"--symbol {symbol} resolves to {spec.name} (multiplier "
            f"{spec.multiplier_krw_per_point}), which is not the smallest "
            f"registered contract (multiplier {smallest}). A real-money probe "
            f"takes the smallest available contract size. Registered: "
            f"{multipliers}.",
        )
    tick = Tick(size=Decimal(str(spec.tick_size_points)), source=str(record["source"]))
    if tick.size <= 0:
        raise RealOrderAbort(
            ABORT_INSTRUMENT_UNRESOLVED,
            f"tick_size_points for {spec.name} is {tick.size}; a non-positive "
            "tick cannot be snapped to.",
        )
    return spec, tick, record


@dataclass(frozen=True)
class RestingPlan:
    """One tick-valid, band-valid, cap-valid resting order, with its evidence."""

    symbol: str
    side: str
    quantity: int
    price: TickPrice
    touch: float
    band_low: Decimal
    band_high: Decimal
    min_distance_pct: float
    multiplier_krw_per_point: int
    notional_krw: Decimal

    def describe(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "touch": self.touch,
            "resting_price": self.price.wire,
            "distance_pct_from_touch": round(
                (self.touch - self.price.value) / self.touch * 100.0, 4
            ),
            "min_distance_pct_required": self.min_distance_pct,
            "daily_band": [str(self.band_low), str(self.band_high)],
            "tick": self.price.describe(),
            "multiplier_krw_per_point": self.multiplier_krw_per_point,
            "notional_krw": str(self.notional_krw),
            "notional_arithmetic": (
                "max(touch, resting_price) x multiplier_krw_per_point x quantity "
                "— the touch is used when it is the greater of the two so the "
                "recorded exposure is never understated by the resting discount."
            ),
        }


def notional_krw(
    *, touch: float, price: TickPrice, multiplier: int, quantity: int
) -> Decimal:
    """Conservative KRW exposure of one order: the greater price leg is used."""
    reference = max(Decimal(str(touch)), Decimal(price.wire))
    return reference * Decimal(int(multiplier)) * Decimal(int(quantity))


def plan_resting_order(
    *,
    symbol: str,
    touch: float,
    band_low: Decimal | None,
    band_high: Decimal | None,
    tick: Tick,
    multiplier: int,
    quantity: int,
    offset_pct: float,
    min_distance_pct: float,
) -> RestingPlan:
    """Compute a resting BUY limit and assert every property before it can be sent."""
    side = "BUY"
    if touch <= 0:
        raise RealOrderAbort(
            ABORT_TOUCH_UNREADABLE,
            f"touch price for {symbol} is {touch!r}; a resting price cannot be "
            "derived from it.",
        )
    if band_low is None or band_high is None or band_low <= 0 or band_high <= band_low:
        raise RealOrderAbort(
            ABORT_PRICE_BAND_UNREADABLE,
            f"the daily price band for {symbol} is unreadable "
            f"(futs_llam={band_low!r}, futs_mxpr={band_high!r}). Report this "
            "rather than lowering the guard: a limit outside the band is "
            "rejected and the order is spent without a measurement.",
        )

    raw = touch * (1.0 - float(offset_pct) / 100.0)
    if raw <= 0:
        raise RealOrderAbort(
            ABORT_PRICE_TOO_CLOSE,
            f"computed resting price {raw!r} is non-positive; check "
            f"--price-offset-pct={offset_pct}.",
        )
    try:
        price = snap_to_tick(raw, tick, side=side, marketable=False)
    except ProbeError as exc:
        raise RealOrderAbort(ABORT_PRICE_OFF_TICK, str(exc)) from exc

    assert_resting_plan_price(
        price=price,
        touch=touch,
        tick=tick,
        band_low=band_low,
        band_high=band_high,
        min_distance_pct=min_distance_pct,
    )
    return RestingPlan(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        touch=touch,
        band_low=band_low,
        band_high=band_high,
        min_distance_pct=float(min_distance_pct),
        multiplier_krw_per_point=int(multiplier),
        notional_krw=notional_krw(
            touch=touch, price=price, multiplier=multiplier, quantity=quantity
        ),
    )


def assert_resting_plan_price(
    *,
    price: TickPrice,
    touch: float,
    tick: Tick,
    band_low: Decimal,
    band_high: Decimal,
    min_distance_pct: float,
) -> None:
    """The three price assertions, factored out so the send path can re-take them."""
    exact = Decimal(price.wire)
    if exact % tick.size != 0:
        raise RealOrderAbort(
            ABORT_PRICE_OFF_TICK,
            f"resting price {price.wire} is not a multiple of tick {tick.size} "
            f"({tick.source}); refusing to send it.",
        )
    floor_price = Decimal(str(touch)) * (
        Decimal(1) - Decimal(str(min_distance_pct)) / Decimal(100)
    )
    if exact > floor_price:
        raise RealOrderAbort(
            ABORT_PRICE_TOO_CLOSE,
            f"resting BUY {price.wire} is closer to the touch {touch} than the "
            f"required {min_distance_pct}% (floor {floor_price}). A resting "
            "probe depends on the order NOT filling; refusing to send it.",
        )
    if not (band_low <= exact <= band_high):
        raise RealOrderAbort(
            ABORT_PRICE_OUTSIDE_BAND,
            f"resting price {price.wire} is outside the broker-reported daily "
            f"band [{band_low}, {band_high}]; the order would be rejected.",
        )


@dataclass
class RunBudget:
    """The single gate every order in this run passes through."""

    max_samples: int
    max_notional_krw: Decimal
    max_cumulative_notional_krw: Decimal
    orders_sent: int = 0
    cumulative_notional_krw: Decimal = Decimal(0)

    def authorize(self, plan: RestingPlan) -> None:
        if plan.quantity > HARD_MAX_QUANTITY:
            raise RealOrderAbort(
                ABORT_QUANTITY_CAP,
                f"quantity {plan.quantity} exceeds the hard cap "
                f"{HARD_MAX_QUANTITY}. This ceiling is not configurable.",
            )
        if plan.notional_krw > self.max_notional_krw:
            raise RealOrderAbort(
                ABORT_NOTIONAL_CAP,
                f"order notional {plan.notional_krw} KRW exceeds "
                f"--max-notional-krw {self.max_notional_krw}. Arithmetic: "
                f"max(touch, price) x multiplier x qty = "
                f"{plan.notional_krw}.",
            )
        if self.orders_sent + 1 > self.max_samples:
            raise RealOrderAbort(
                ABORT_SAMPLE_CAP,
                f"this would be order {self.orders_sent + 1} of an authorised "
                f"{self.max_samples}.",
            )
        projected = self.cumulative_notional_krw + plan.notional_krw
        if projected > self.max_cumulative_notional_krw:
            raise RealOrderAbort(
                ABORT_CUMULATIVE_NOTIONAL_CAP,
                f"cumulative notional would reach {projected} KRW, over the "
                f"authorised {self.max_cumulative_notional_krw}.",
            )
        self.orders_sent += 1
        self.cumulative_notional_krw = projected

    def describe(self) -> dict[str, Any]:
        return {
            "max_samples": self.max_samples,
            "max_notional_krw": str(self.max_notional_krw),
            "max_cumulative_notional_krw": str(self.max_cumulative_notional_krw),
            "orders_sent": self.orders_sent,
            "cumulative_notional_krw": str(self.cumulative_notional_krw),
            "cumulative_is_turnover_not_exposure": (
                "Cumulative notional bounds total TURNOVER. Peak exposure is "
                "bounded separately and structurally: exactly one order is live "
                "at a time because each is cancelled and verified before the "
                "next is planned, and quantity is capped at "
                f"{HARD_MAX_QUANTITY} contract."
            ),
        }


def build_real_futures_order_body(
    *,
    cano: str,
    acnt_prdt_cd: str,
    plan: RestingPlan,
) -> dict[str, str]:
    """The ONLY order-body builder that targets a real account."""
    return {
        "ORD_PRCS_DVSN_CD": "02",
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "SLL_BUY_DVSN_CD": "02" if plan.side == "BUY" else "01",
        "SHTN_PDNO": plan.symbol,
        "ORD_QTY": str(plan.quantity),
        "UNIT_PRICE": plan.price.wire,
        "NMPR_TYPE_CD": "01",
        "KRX_NMPR_CNDT_CD": "0",
        "CTAC_TLNO": "",
        "FUOP_ITEM_DVSN_CD": "",
        "ORD_DVSN_CD": "01",
    }


class PreflightClient:
    """Stage 1's transport. GET-only, allowlisted, paced. No order path exists."""

    def __init__(self, creds: Any, auth_manager: Any, *, pace_s: float) -> None:
        import requests

        self.creds = creds
        self.auth = auth_manager
        self.session = requests.Session()
        self.pacer = _CallPacer(pace_s)

    def close(self) -> None:
        self.session.close()

    def get(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> tuple[int, dict[str, Any], str]:
        url = f"{REAL_BASE_URL}{path}"
        assert_real_host(url)
        assert_read_only_call("GET", url, tr_id, PREFLIGHT_ALLOWLIST)
        headers = dict(self.auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        self.pacer.wait()
        status, parsed, _ms, text = http_json(
            self.session, "GET", url, headers=headers, params=params, timeout=20.0
        )
        return status, parsed, text


class RealOrderClient:
    """Stage 2's transport. Can POST an order to a real account."""

    def __init__(
        self,
        creds: Any,
        auth_manager: Any,
        run: ProbeRun,
        budget: RunBudget,
        *,
        pace_s: float,
        timeout: float = 15.0,
    ) -> None:
        import requests

        from shared.execution.tr_ids import get_tr_ids

        self.creds = creds
        self.auth = auth_manager
        self.run = run
        self.budget = budget
        self.session = requests.Session()
        self.timeout = timeout
        self.tr_ids = get_tr_ids()
        self.pacer = _CallPacer(pace_s)
        self._last_send_monotonic: float | None = None

    def close(self) -> None:
        self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        """The one socket site: host-asserted, header-first, then paced, then sent."""
        assert_real_host(url)
        headers = dict(self.auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        self._last_send_monotonic = self.pacer.wait()
        return http_json(
            self.session,
            method,
            url,
            headers=headers,
            params=params,
            json_body=body,
            timeout=self.timeout,
        )

    def last_send_instant(self) -> float:
        if self._last_send_monotonic is None:
            raise ProbeError("last_send_instant() called before any request")
        return self._last_send_monotonic

    def trading_call(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        url = f"{REAL_BASE_URL}{path}"
        assert_real_host(url)
        assert_real_trading_tr(tr_id)
        return self._request(method, url, tr_id, params=params, body=body)

    def quote_call(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        url = f"{REAL_BASE_URL}{path}"
        assert_real_host(url)
        _status, parsed, _ms, _text = self._request("GET", url, tr_id, params=params)
        return parsed

    def quote(self, symbol: str) -> dict[str, Any]:
        return self.quote_call(
            _PRICE_PATH,
            _PRICE_TR,
            {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol},
        )

    def submit_resting(
        self, plan: RestingPlan
    ) -> tuple[str | None, dict[str, Any], int]:
        """Authorise, re-assert, build, send. In that order, with no shortcut."""
        assert_resting_plan_price(
            price=plan.price,
            touch=plan.touch,
            tick=plan.price.tick,
            band_low=plan.band_low,
            band_high=plan.band_high,
            min_distance_pct=plan.min_distance_pct,
        )
        self.budget.authorize(plan)
        body = build_real_futures_order_body(
            cano=self.creds.cano, acnt_prdt_cd=self.creds.acnt_prdt_cd, plan=plan
        )
        tr_id = self.tr_ids["futures_order_day_real"]
        status, parsed, _ms, _text = self.trading_call(
            "POST", _ORDER_PATH, tr_id, body=body
        )
        odno = str((parsed.get("output") or {}).get("ODNO") or "").strip()
        accepted = status == 200 and _ok(parsed) and bool(odno)
        self.run.observe(
            submit={
                "tr_id": tr_id,
                "http_status": status,
                "rt_cd": parsed.get("rt_cd"),
                "msg_cd": parsed.get("msg_cd"),
                "msg1": parsed.get("msg1"),
                "odno": odno or None,
                "body": body,
            }
        )
        return (odno if accepted else None), parsed, status

    def cancel(self, odno: str, qty: int) -> dict[str, Any]:
        """``RVSE_CNCL_DVSN_CD='02'`` — cancel, mirroring ``executor.py``."""
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "RVSE_CNCL_DVSN_CD": "02",
            "ORGN_ODNO": odno,
            "ORD_QTY": str(qty),
            "UNIT_PRICE": "0",
            "NMPR_TYPE_CD": "01",
            "KRX_NMPR_CNDT_CD": "0",
            "RMN_QTY_YN": "Y",
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": "01",
        }
        tr_id = self.tr_ids["futures_cancel_day_real"]
        _status, parsed, _ms, _text = self.trading_call(
            "POST", _CANCEL_PATH, tr_id, body=body
        )
        return parsed

    def inquire(
        self,
        symbol: str,
        *,
        odno: str = "",
        fk200: str = "",
        nk200: str = "",
    ) -> dict[str, Any]:
        """Mirror of ``executor.py``'s inquire-ccnl params, with usable ctx keys."""
        tr_id = assert_inquire_tr_matches_sot()
        day = datetime.now(KST).date().strftime("%Y%m%d")
        params = {
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "STRT_ORD_DT": day,
            "END_ORD_DT": day,
            "SLL_BUY_DVSN_CD": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN": "DS",
            "STRT_ODNO": odno,
            "PDNO": symbol,
            "MKET_ID_CD": "",
            "CTX_AREA_FK200": fk200,
            "CTX_AREA_NK200": nk200,
        }
        _status, parsed, _ms, _text = self.trading_call(
            "GET", _INQUIRE_PATH, tr_id, params=params
        )
        return parsed


FILL_NONE = "NO_FILL"
FILL_PARTIAL_OR_FULL = "FILLED"
FILL_UNKNOWN = "UNKNOWN"


def classify_fill(row: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Read a fill state off one inquire-ccnl row. Never guesses."""
    filled = _int_field(row, "tot_ccld_qty")
    record = {
        "tot_ccld_qty": filled,
        "qty_remaining": _int_field(row, "qty"),
        "ord_qty": _int_field(row, "ord_qty"),
        "avg_idx": str(_decimal_field(row, "avg_idx") or ""),
        "odno": str(row.get("odno", "")).strip(),
    }
    if filled is None:
        return FILL_UNKNOWN, record
    if filled > 0:
        return FILL_PARTIAL_OR_FULL, record
    return FILL_NONE, record


def assert_no_fill(row: dict[str, Any], *, context: str) -> dict[str, Any]:
    """Abort the run on a fill, or on an unreadable fill state."""
    state, record = classify_fill(row)
    if state == FILL_PARTIAL_OR_FULL:
        raise RealOrderAbort(
            ABORT_FILL_DETECTED,
            f"FILL DETECTED at {context}: {record}. The run stops here and "
            "places no further order. The account now holds a position — "
            "flatten it manually (runbook §5.7) and record the fill.",
        )
    if state == FILL_UNKNOWN:
        raise RealOrderAbort(
            ABORT_FILL_STATE_UNKNOWN,
            f"fill state UNREADABLE at {context}: {record}. Refusing to read an "
            "unanswered field as 'did not fill'. Stop, inspect the account, and "
            "report the row verbatim.",
        )
    return record


def _preflight_setup(
    spec: ProbeSpec, args: argparse.Namespace
) -> tuple[ProbeRun, PreflightClient | None, Any]:
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    assert_no_live_futures_config()
    warn_shared_token_cache()
    creds = resolve_credentials("futures", is_real=True)
    require_account(creds)
    run.credentials = creds.describe()
    run.observe(
        read_only_attestation=(
            "Stage 1 can issue GET requests only, against "
            "tools/broker_probes/probes_real_order.py::PREFLIGHT_ALLOWLIST. It "
            "never constructs an order body: build_real_futures_order_body is "
            "unreachable from this code path."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in PREFLIGHT_ALLOWLIST],
    )
    if not args.confirm:
        dry_run_banner(spec)
        return run, None, creds
    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    client = PreflightClient(
        creds,
        KISAuthManager(cfg, use_singleton=False),
        pace_s=probes_order.pace_interval_s(args),
    )
    return run, client, creds


def _preflight_market_and_instrument(
    run: ProbeRun, args: argparse.Namespace
) -> tuple[int, Tick]:
    session = assert_market_open(
        datetime.now(KST), min_remaining_s=float(args.min_session_remaining_s)
    )
    run.measure("market_session", session)
    contract, tick, contract_record = resolve_smallest_contract(args.symbol)
    run.measure("contract", contract_record)
    run.measure(
        "tick_provenance",
        {
            "tick_size_points": str(tick.size),
            "source": tick.source,
            "why_not_broker_reported": (
                "The futures 시세 TR FHMIF10000000 reports no 호가단위 field — "
                "its documented response has none (official wrapper "
                "chk_inquire_price.py COLUMN_MAPPING, read 2026-07-31). Unlike "
                "the stock path, which snaps to the broker's own aspr_unit, the "
                "futures tick can only come from the contract registry. It is "
                "therefore CORROBORATED against the broker's own quoted values "
                "instead: see tick_corroboration."
            ),
        },
    )
    return int(contract.multiplier_krw_per_point), tick


def probe_real_preflight(args: argparse.Namespace) -> ProbeRun:
    """P-R5-PRE — GET-only preflight for the real-money order probe. ZERO risk."""
    spec = get("P-R5-PRE")
    if not args.symbol:
        raise ProbeError("--symbol is required (e.g. A05609 for the mini contract)")
    run, client, creds = _preflight_setup(spec, args)
    try:
        if client is None:
            run.observe(
                would_send=(
                    f"GET x5: {_DEPOSIT_TR}, {_BALANCE_TR}, {_PRICE_TR}, "
                    f"{_PSBL_ORDER_TR}, futures_inquire_day_real. No POST exists."
                )
            )
            return run
        assert_account_fingerprint(
            str(run.credentials.get("account_fingerprint", "")),
            args.expect_account_fingerprint,
        )
        run.measure(
            "account_identity",
            {
                "account_masked": mask_account(creds.account_no),
                "account_fingerprint": account_fingerprint(creds.account_no),
                "expected_fingerprint": args.expect_account_fingerprint.strip().lower(),
                "matched": True,
                "raw_account_never_recorded": True,
            },
        )
        multiplier, tick = _preflight_market_and_instrument(run, args)
        _preflight_broker_state(run, args, client, tick, multiplier)
        run.measure("preflight_verdict", VERDICT_PREFLIGHT_READY)
        run.measure(
            "stage_2_authorisation",
            "This artifact is a PRECONDITION for stage 2, not an authorisation "
            "to run it. Stage 2 additionally requires --confirm, "
            f"{REAL_ORDER_CONFIRM_FLAG}, --max-notional-krw, and it re-takes "
            "every assertion above against the live broker.",
        )
    except RealOrderAbort as abort:
        run.error(str(abort))
        run.measure("preflight_verdict", abort.verdict)
        run.measure(
            "abort_is_a_result",
            "Stage 1 stopped and recorded why. This artifact must NOT be passed "
            "to stage 2 — stage 2 requires preflight_verdict == "
            f"{VERDICT_PREFLIGHT_READY!r} and refuses anything else.",
        )
    finally:
        if client is not None:
            client.close()
        _record_scope(run)
    return run


def _preflight_broker_state(
    run: ProbeRun,
    args: argparse.Namespace,
    client: PreflightClient,
    tick: Tick,
    multiplier: int,
) -> None:
    """The five GET legs, in cheapest-refusal-first order."""
    _status, deposit, _text = client.get(
        _DEPOSIT_PATH,
        _DEPOSIT_TR,
        {"CANO": client.creds.cano, "ACNT_PRDT_CD": client.creds.acnt_prdt_cd},
    )
    run.measure(
        "order_available", assert_order_available(deposit.get("output"), deposit)
    )
    run.measure(
        "trading_tr_reachable",
        {
            "tr_id": _DEPOSIT_TR,
            "rt_cd": deposit.get("rt_cd"),
            "msg_cd": deposit.get("msg_cd"),
            "meaning": (
                "A clean answer on a real TRADING TR is what establishes that "
                "this credential is a REAL trading credential. Quote-TR success "
                "does not: the campaign observed the real domain answering mock "
                "app-keys on FHPPG04600001/FHKST03030200/FHMIF10000000 while "
                "rejecting CTFN6118R with EGW02004."
            ),
        },
    )

    _status, balance, _text = client.get(
        _BALANCE_PATH,
        _BALANCE_TR,
        {
            "CANO": client.creds.cano,
            "ACNT_PRDT_CD": client.creds.acnt_prdt_cd,
            "MGNA_DVSN": "01",
            "EXCC_STAT_CD": "1",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    run.measure("positions", assert_flat_account(balance))
    _preflight_instrument_state(run, args, client, tick, multiplier)


def _preflight_instrument_state(
    run: ProbeRun,
    args: argparse.Namespace,
    client: PreflightClient,
    tick: Tick,
    multiplier: int,
) -> None:
    """The instrument legs: touch + band + plan, order-available qty, open orders."""
    _status, quote, _text = client.get(
        _PRICE_PATH,
        _PRICE_TR,
        {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": args.symbol},
    )
    plan = _plan_from_quote(run, args, quote, tick, multiplier)
    run.measure("resting_plan", plan.describe())
    run.measure(
        "tick_corroboration",
        _corroborate_tick(
            quote.get("output1") or {},
            tick,
            ("futs_prpr", "futs_prdy_clpr", "futs_mxpr", "futs_llam", "futs_sdpr"),
        ),
    )

    _status, psbl, _text = client.get(
        _PSBL_ORDER_PATH,
        _PSBL_ORDER_TR,
        {
            "CANO": client.creds.cano,
            "ACNT_PRDT_CD": client.creds.acnt_prdt_cd,
            "PDNO": args.symbol,
            "SLL_BUY_DVSN_CD": "02",
            "UNIT_PRICE": plan.price.wire,
            "ORD_DVSN_CD": "01",
        },
    )
    psbl_out = psbl.get("output") if isinstance(psbl.get("output"), dict) else {}
    run.measure(
        "order_available_quantity",
        {
            "tr_id": _PSBL_ORDER_TR,
            "rt_cd": psbl.get("rt_cd"),
            "at_price": plan.price.wire,
            "ord_psbl_qty": _int_field(psbl_out, "ord_psbl_qty"),
            "tot_psbl_qty": _int_field(psbl_out, "tot_psbl_qty"),
            "lqd_psbl_qty1": _int_field(psbl_out, "lqd_psbl_qty1"),
            "bass_idx": str(_decimal_field(psbl_out, "bass_idx") or ""),
            "interpretation": (
                "A quantity of 0 here would mean the account cannot send even "
                "one contract at this price. It is recorded rather than made an "
                "abort condition on its own: the funded-ness refusal already "
                "comes from the order-available AMOUNT, and this leg's own "
                "parameters (price, side, order type) could produce a 0 for "
                "reasons that are about the parameters and not the account."
            ),
        },
    )

    inquire_tr = assert_inquire_tr_matches_sot()
    day = datetime.now(KST).date().strftime("%Y%m%d")
    _status, listing, _text = client.get(
        _INQUIRE_PATH,
        inquire_tr,
        {
            "CANO": client.creds.cano,
            "ACNT_PRDT_CD": client.creds.acnt_prdt_cd,
            "STRT_ORD_DT": day,
            "END_ORD_DT": day,
            "SLL_BUY_DVSN_CD": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN": "DS",
            "STRT_ODNO": "",
            "PDNO": args.symbol,
            "MKET_ID_CD": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        },
    )
    run.measure(
        "preexisting_open_orders",
        assert_no_preexisting_open_orders(listing, args.symbol),
    )


def _plan_from_quote(
    run: ProbeRun,
    args: argparse.Namespace,
    quote: Any,
    tick: Tick,
    multiplier: int,
) -> RestingPlan:
    """Build the resting plan from a 시세 response, aborting on anything missing."""
    if not _ok(quote):
        raise RealOrderAbort(
            ABORT_TOUCH_UNREADABLE,
            f"{_PRICE_TR} did not answer cleanly ({_reject(quote)}).",
        )
    out = quote.get("output1") if isinstance(quote.get("output1"), dict) else {}
    touch = None
    for key in ("futs_prpr", "futs_prdy_clpr", "futs_sdpr"):
        candidate = _decimal_field(out, key)
        if candidate is not None and candidate > 0:
            touch = float(candidate)
            run.measure("touch_field_used", key)
            break
    if touch is None:
        raise RealOrderAbort(
            ABORT_TOUCH_UNREADABLE,
            f"no positive price in {_PRICE_TR}.output1 "
            "(futs_prpr/futs_prdy_clpr/futs_sdpr all absent or zero).",
        )
    return plan_resting_order(
        symbol=args.symbol,
        touch=touch,
        band_low=_decimal_field(out, "futs_llam"),
        band_high=_decimal_field(out, "futs_mxpr"),
        tick=tick,
        multiplier=int(multiplier),
        quantity=int(args.quantity),
        offset_pct=float(args.price_offset_pct),
        min_distance_pct=float(args.min_touch_distance_pct),
    )


def load_stage1_artifact(
    path_text: str, *, max_age_s: float, expect_fingerprint: str, symbol: str
) -> dict[str, Any]:
    """Load and validate a stage-1 artifact. Passing is necessary, not sufficient."""
    if not str(path_text or "").strip():
        raise RealOrderAbort(
            ABORT_STAGE1_MISSING,
            "--stage1-artifact is required for live mode: stage 2 will not run "
            "without a preflight a human has reviewed.",
        )
    path = Path(path_text).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — an unreadable precondition aborts
        raise RealOrderAbort(
            ABORT_STAGE1_MISSING,
            f"could not read stage-1 artifact {path}: {type(exc).__name__}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise RealOrderAbort(ABORT_STAGE1_MISSING, f"{path} is not a JSON object")

    measurements = payload.get("measurements")
    measurements = measurements if isinstance(measurements, dict) else {}
    credentials = payload.get("credentials")
    credentials = credentials if isinstance(credentials, dict) else {}
    problems: list[str] = []
    if payload.get("probe_id") != "P-R5-PRE":
        problems.append(f"probe_id is {payload.get('probe_id')!r}, not 'P-R5-PRE'")
    if payload.get("mode") != "live":
        problems.append(f"mode is {payload.get('mode')!r}, not 'live' (a dry run)")
    if payload.get("environment") != ENV_REAL:
        problems.append(
            f"environment is {payload.get('environment')!r}, not {ENV_REAL}"
        )
    if measurements.get("preflight_verdict") != VERDICT_PREFLIGHT_READY:
        problems.append(
            f"preflight_verdict is {measurements.get('preflight_verdict')!r}, not "
            f"{VERDICT_PREFLIGHT_READY!r}"
        )
    if payload.get("errors"):
        problems.append(f"the preflight recorded errors: {payload['errors']}")
    fingerprint = str(credentials.get("account_fingerprint", "")).strip().lower()
    if fingerprint != str(expect_fingerprint or "").strip().lower():
        problems.append(
            f"the preflight ran against fingerprint {fingerprint!r}, not the "
            f"expected {expect_fingerprint!r}"
        )
    planned_symbol = ""
    plan_record = measurements.get("resting_plan")
    if isinstance(plan_record, dict):
        planned_symbol = str(plan_record.get("symbol", ""))
    if planned_symbol != symbol:
        problems.append(
            f"the preflight planned {planned_symbol!r}, not --symbol {symbol!r}"
        )
    if problems:
        raise RealOrderAbort(
            ABORT_STAGE1_UNUSABLE,
            f"stage-1 artifact {path} is not a passing preflight for this run: "
            + "; ".join(problems),
        )

    age_s = _artifact_age_s(payload)
    if age_s is None:
        raise RealOrderAbort(
            ABORT_STAGE1_STALE,
            f"stage-1 artifact {path} carries no parseable finished_at_utc, so "
            "its freshness cannot be established.",
        )
    if age_s > float(max_age_s):
        raise RealOrderAbort(
            ABORT_STAGE1_STALE,
            f"stage-1 artifact {path} is {age_s:.0f}s old, over the "
            f"{max_age_s:.0f}s limit. Account state has had time to change: "
            "re-run stage 1.",
        )
    return {
        "path": str(path),
        "artifact_id": payload.get("artifact_id"),
        "age_s": round(age_s, 1),
        "max_age_s": float(max_age_s),
        "preflight_verdict": measurements.get("preflight_verdict"),
        "account_fingerprint": fingerprint,
        "revalidation_note": (
            "Every assertion in this file is re-taken live below. The file "
            "proves a human ran and reviewed a preflight; it is not evidence "
            "about the account's CURRENT state."
        ),
    }


def _artifact_age_s(payload: dict[str, Any]) -> float | None:
    stamp = payload.get("finished_at_utc") or payload.get("started_at_utc")
    try:
        finished = datetime.fromisoformat(str(stamp))
    except (TypeError, ValueError):
        return None
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - finished).total_seconds())


@dataclass
class _TrialOutcome:
    latency_ms: float | None = None
    censored: bool = False
    polls: int = 0
    odno: str = ""
    fill: dict[str, Any] = field(default_factory=dict)


def _build_budget(args: argparse.Namespace) -> RunBudget:
    """Turn the CLI caps into the run's single authorisation gate."""
    if args.samples > HARD_MAX_SAMPLES:
        raise RealOrderAbort(
            ABORT_SAMPLE_CAP,
            f"--samples {args.samples} exceeds the hard cap {HARD_MAX_SAMPLES}.",
        )
    if args.samples < 1:
        raise RealOrderAbort(ABORT_SAMPLE_CAP, "--samples must be at least 1.")
    if args.quantity > HARD_MAX_QUANTITY:
        raise RealOrderAbort(
            ABORT_QUANTITY_CAP,
            f"--quantity {args.quantity} exceeds the hard cap " f"{HARD_MAX_QUANTITY}.",
        )
    if args.order_class_ramp_attempts > HARD_MAX_RAMP_ATTEMPTS:
        raise RealOrderAbort(
            ABORT_SAMPLE_CAP,
            f"--order-class-ramp-attempts {args.order_class_ramp_attempts} "
            f"exceeds the hard cap {HARD_MAX_RAMP_ATTEMPTS}.",
        )
    if args.max_notional_krw is None or Decimal(str(args.max_notional_krw)) <= 0:
        raise RealOrderAbort(
            ABORT_NOTIONAL_CAP,
            "--max-notional-krw is required and must be positive. Compute it "
            "from the stage-1 artifact: multiplier x touch x quantity, plus "
            "whatever headroom you are willing to authorise.",
        )
    per_order = Decimal(str(args.max_notional_krw))
    total_orders = int(args.samples) + int(args.order_class_ramp_attempts)
    cumulative = (
        Decimal(str(args.max_cumulative_notional_krw))
        if args.max_cumulative_notional_krw is not None
        else per_order * Decimal(total_orders)
    )
    if cumulative <= 0:
        raise RealOrderAbort(
            ABORT_CUMULATIVE_NOTIONAL_CAP,
            "--max-cumulative-notional-krw must be positive.",
        )
    return RunBudget(
        max_samples=total_orders,
        max_notional_krw=per_order,
        max_cumulative_notional_krw=cumulative,
    )


def probe_real_order(args: argparse.Namespace) -> ProbeRun:
    """P-R5 — REAL-MONEY accept→query-visible latency. Places real orders."""
    spec = get("P-R5")
    if not args.symbol:
        raise ProbeError("--symbol is required (e.g. A05609 for the mini contract)")
    assert_real_order_confirmation(args)
    assert_no_live_futures_config()
    warn_shared_token_cache()

    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    creds = resolve_credentials("futures", is_real=True)
    require_account(creds)
    run.credentials = creds.describe()
    client: RealOrderClient | None = None
    unresolved: list[str] = []
    try:
        budget = _build_budget(args)
        run.measure("budget", budget.describe())
        assert_account_fingerprint(
            str(run.credentials.get("account_fingerprint", "")),
            args.expect_account_fingerprint,
        )
        if not args.confirm:
            _dry_run_report(run, args, spec)
            return run
        run.measure(
            "stage1_artifact",
            load_stage1_artifact(
                args.stage1_artifact,
                max_age_s=min(float(args.stage1_max_age_s), HARD_MAX_STAGE1_AGE_S),
                expect_fingerprint=args.expect_account_fingerprint,
                symbol=args.symbol,
            ),
        )
        from shared.kis.auth import KISAuthManager

        cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
        client = RealOrderClient(
            creds,
            KISAuthManager(cfg, use_singleton=False),
            run,
            budget,
            pace_s=probes_order.pace_interval_s(args),
        )
        _run_stage2(run, args, client, budget, unresolved)
        run.measure("verdict", VERDICT_COMPLETED)
    except RealOrderAbort as abort:
        run.error(str(abort))
        run.measure("verdict", abort.verdict)
        run.measure(
            "abort_is_a_result",
            "The run stopped and recorded why. provenance_class is NOT_MEASURED "
            "because errors is non-empty, so nothing here can be cited as a "
            "measurement — but the abort itself is evidence and is preserved.",
        )
    finally:
        if client is not None:
            _final_sweep(client, run, args, unresolved)
            client.close()
        _record_scope(run)
    return run


def _run_stage2(
    run: ProbeRun,
    args: argparse.Namespace,
    client: RealOrderClient,
    budget: RunBudget,
    unresolved: list[str],
) -> None:
    """Re-validate live, then measure, then ramp, then walk one page set."""
    run.measure(
        "market_session_revalidated",
        assert_market_open(
            datetime.now(KST), min_remaining_s=float(args.min_session_remaining_s)
        ),
    )
    contract, tick, contract_record = resolve_smallest_contract(args.symbol)
    run.measure("contract", contract_record)
    multiplier = int(contract.multiplier_krw_per_point)

    latencies: list[float] = []
    for trial in range(int(args.samples)):
        plan = _plan_for_trial(run, args, client, tick, multiplier)
        if trial == 0:
            run.measure("resting_plan_first_trial", plan.describe())
        outcome = _one_trial(run, args, client, plan, trial, unresolved)
        if outcome.latency_ms is not None:
            latencies.append(outcome.latency_ms)
        time.sleep(float(args.inter_trial_s))

    run.measure(
        "B_broker_query_consistency_candidate_real",
        summarize_latencies(
            latencies, margin_pct=float(args.margin_pct), label="accept_to_visible_ms"
        ),
    )
    run.measure("poll_granularity_ms", effective_interval_ms(args.poll_ms, args))
    run.measure(
        "granularity_note",
        "Each sample carries up to one poll interval of additive error, and the "
        "recorded granularity is the EFFECTIVE interval max(--poll-ms, "
        "--pace-s): the pacer floors polling, so a smaller --poll-ms did not "
        "happen. An approved bound must exceed max_observed + this value "
        "(runbook §8.3); recording the requested interval would understate the "
        "additive error, and that direction of error is fail-open.",
    )
    run.measure(
        "runtime_calibration_target",
        {
            "config_key": "config/execution.yaml::futures_fill_check_timeout_seconds",
            "current_value_s": 1.0,
            "mock_reference_p50_ms": 2632.9,
            "mock_reference_artifact": "P-5-20260731T014143Z",
            "instruction": (
                "The measurement above is the real-environment input this key "
                "was waiting for (wave-3b D-2 NOT-IN-SCOPE). It does NOT change "
                "the key: the change is a separate reviewed commit, and the "
                "value it should take is a decision about the runtime's fill "
                "policy, not a number this probe emits."
            ),
        },
    )
    run.measure(
        "censored_trials", sum(1 for o in run.observations if o.get("censored"))
    )
    _order_class_ramp(run, args, client, tick, multiplier, unresolved)
    _page_size_walk(run, args, client)


def _plan_for_trial(
    run: ProbeRun,
    args: argparse.Namespace,
    client: RealOrderClient,
    tick: Tick,
    multiplier: int,
) -> RestingPlan:
    """One quote, then one plan. The quote is paced like everything else."""
    quote = client.quote(args.symbol)
    return _plan_from_quote(run, args, quote, tick, multiplier)


def _one_trial(
    run: ProbeRun,
    args: argparse.Namespace,
    client: RealOrderClient,
    plan: RestingPlan,
    trial: int,
    unresolved: list[str],
) -> _TrialOutcome:
    """Submit, measure visibility, check for a fill, cancel, verify. Abort on any doubt."""
    outcome = _TrialOutcome()
    odno, parsed, _status = client.submit_resting(plan)
    if odno is None:
        raise RealOrderAbort(
            ABORT_SUBMIT_REJECTED,
            f"trial {trial}: the broker refused the order ({_reject(parsed)}). "
            "Stopping rather than retrying: a rejection on a real account is a "
            "precondition finding, and the campaign's rule is to report a "
            "호가단위/limit rejection verbatim instead of adjusting the price by "
            "hand.",
        )
    outcome.odno = odno
    unresolved.append(odno)
    t0 = client.last_send_instant()
    deadline = time.monotonic() + float(args.visibility_timeout_s)
    seen_at: float | None = None
    while time.monotonic() < deadline:
        outcome.polls += 1
        listing = client.inquire(args.symbol, odno=odno)
        rows = _rows(listing)
        record_odno_wire_format(run, [odno], rows)
        mine = [r for r in rows if odno_key(r.get("odno")) == odno_key(odno)]
        if mine:
            seen_at = time.monotonic()
            outcome.fill = assert_no_fill(mine[0], context=f"trial {trial} visibility")
            break
        time.sleep(float(args.poll_ms) / 1000.0)

    if seen_at is None:
        outcome.censored = True
        run.error(
            f"trial {trial}: ODNO {odno} never appeared within "
            f"{args.visibility_timeout_s}s — a CENSORED sample, which must not "
            "be dropped when computing the maximum."
        )
        run.observe(trial=trial, censored=True, polls=outcome.polls, odno=odno)
    else:
        outcome.latency_ms = (seen_at - t0) * 1000.0
        run.observe(
            trial=trial,
            odno=odno,
            latency_ms=round(outcome.latency_ms, 2),
            polls=outcome.polls,
            fill=outcome.fill,
        )
    _cancel_and_verify(run, args, client, plan, odno, trial, unresolved)
    return outcome


def _cancel_and_verify(
    run: ProbeRun,
    args: argparse.Namespace,
    client: RealOrderClient,
    plan: RestingPlan,
    odno: str,
    trial: int,
    unresolved: list[str],
) -> None:
    """Cancel, retry within a bounded budget, verify, and abort the run if it fails."""
    attempts = min(int(args.cancel_retry_attempts), HARD_MAX_CANCEL_RETRIES)
    last = ""
    for attempt in range(1, attempts + 1):
        parsed = client.cancel(odno, plan.quantity)
        ok = _ok(parsed)
        last = _reject(parsed)
        run.observe(
            cancel={
                "trial": trial,
                "attempt": attempt,
                "odno": odno,
                "accepted": ok,
                "msg1": parsed.get("msg1"),
            }
        )
        if ok:
            verification = client.inquire(args.symbol, odno=odno)
            mine = [
                r
                for r in _rows(verification)
                if odno_key(r.get("odno")) == odno_key(odno)
            ]
            if mine:
                assert_no_fill(mine[0], context=f"trial {trial} post-cancel")
            run.observe(
                cancel_verified={
                    "trial": trial,
                    "odno": odno,
                    "rows_for_odno": len(mine),
                    "authority": (
                        "the broker's cancel response is the authority on "
                        "cancellability (2026-07-31 semantics #2); the row is "
                        "read only to confirm no fill happened."
                    ),
                }
            )
            if odno in unresolved:
                unresolved.remove(odno)
            return
        time.sleep(probes_order.pace_interval_s(args))
    raise RealOrderAbort(
        ABORT_CANCEL_FAILED,
        f"trial {trial}: CANCEL FAILED after {attempts} attempts for ODNO "
        f"{odno} (last: {last}). ⚠ THIS ORDER MAY STILL BE RESTING ON A REAL "
        "ACCOUNT. Cancel it by hand via HTS/MTS now. No further order is placed.",
    )


def _order_class_ramp(
    run: ProbeRun,
    args: argparse.Namespace,
    client: RealOrderClient,
    tick: Tick,
    multiplier: int,
    unresolved: list[str],
) -> None:
    """A short, bounded SUBMIT-class pacing ramp. Stops at the first throttle."""
    attempts = int(args.order_class_ramp_attempts)
    if attempts <= 0:
        run.skip(
            "order-class pacing ramp",
            "--order-class-ramp-attempts is 0, so no order-class rate "
            "observation was taken. The order-class limit stays UNESTABLISHED; "
            "do not substitute P-13's query-class value for it.",
        )
        return
    base = probes_order.pace_interval_s(args)
    steps: list[dict[str, Any]] = []
    throttled_at_ms: float | None = None
    clean_at_ms: float | None = None
    for step in range(attempts):
        interval_s = max(
            float(args.order_class_ramp_floor_s),
            base - step * float(args.order_class_ramp_step_s),
        )
        plan = _plan_for_trial(run, args, client, tick, multiplier)
        time.sleep(interval_s)
        odno, parsed, status = client.submit_resting(plan)
        rate_limited = is_rate_limited(
            status, parsed, str(parsed.get("msg1", ""))
        ) or _is_throttle(parsed)
        record = {
            "step": step,
            "submit_interval_ms": round(interval_s * 1000.0, 1),
            "accepted": odno is not None,
            "throttled": rate_limited,
            "rt_cd": parsed.get("rt_cd"),
            "msg_cd": parsed.get("msg_cd"),
            "msg1": parsed.get("msg1"),
        }
        steps.append(record)
        run.observe(order_class_ramp=record)
        if odno is not None:
            unresolved.append(odno)
            clean_at_ms = round(interval_s * 1000.0, 1)
            _cancel_and_verify(run, args, client, plan, odno, 1000 + step, unresolved)
        if rate_limited:
            throttled_at_ms = round(interval_s * 1000.0, 1)
            break
        if odno is None:
            break
    run.measure(
        "order_class_rate_observation",
        {
            "endpoint_class": "submit (선물옵션 주문) — CANCEL class NOT measured",
            "steps": steps,
            "clean_submit_interval_ms": clean_at_ms,
            "throttled_submit_interval_ms": throttled_at_ms,
            "bracket_semantics": (
                "clean_submit_interval_ms is an UPPER bound on the interval the "
                "broker tolerates (it worked) and throttled_submit_interval_ms a "
                "LOWER bound on what it refuses. Report the bracket, never a "
                "point estimate, and never as an approved value."
            ),
            "candidate_only": True,
            "no_extrapolation": (
                "This is the SUBMIT class on ONE real account in ONE session. It "
                "does not transfer to the CANCEL class, to the QUERY class "
                "(P-13), to another account, or to 모의투자."
            ),
        },
    )


def _is_throttle(parsed: Any) -> bool:
    """The broker's throttle fingerprint, as the runtime already recognises it."""
    if not isinstance(parsed, dict):
        return False
    blob = f"{parsed.get('msg_cd', '')} {parsed.get('msg1', '')}"
    return "EGW00201" in blob or "초당 거래건수를 초과" in blob


def _page_size_walk(
    run: ProbeRun, args: argparse.Namespace, client: RealOrderClient
) -> None:
    """One GET-only continuation walk, so the REAL page size is observed once."""
    max_pages = min(int(args.max_pages), HARD_MAX_PAGES)
    pages: list[dict[str, Any]] = []
    fk200 = nk200 = ""
    stopped_by_us = False
    for page in range(max_pages):
        listing = client.inquire(args.symbol, fk200=fk200, nk200=nk200)
        rows = _rows(listing)
        next_fk = str(listing.get("ctx_area_fk200") or "").strip()
        next_nk = str(listing.get("ctx_area_nk200") or "").strip()
        pages.append(
            {
                "page": page,
                "rows": len(rows),
                "rt_cd": listing.get("rt_cd"),
                "next_fk200_present": bool(next_fk),
                "next_nk200_present": bool(next_nk),
            }
        )
        run.observe(page_walk=pages[-1])
        if not rows or (not next_fk and not next_nk):
            break
        if (next_fk, next_nk) == (fk200, nk200):
            run.error("continuation keys did not advance — stopping the page walk")
            break
        fk200, nk200 = next_fk, next_nk
        if page == max_pages - 1:
            stopped_by_us = True
    run.measure(
        "real_page_size",
        {
            "pages_walked": len(pages),
            "page_size_observed": max((p["rows"] for p in pages), default=0),
            "continuation_supported": any(
                p["next_fk200_present"] or p["next_nk200_present"] for p in pages
            ),
            "total_rows_established": not stopped_by_us,
            "walk_terminated_by_our_max_pages": stopped_by_us,
            "honesty_note": (
                "If walk_terminated_by_our_max_pages is true the total row "
                "count is UNESTABLISHED — we stopped, the broker did not. Only "
                "the per-page size is established, and only as observed here."
            ),
            "mock_does_not_transfer": (
                "Mock observed 15 rows/page (P-5b-20260731T014917Z) against an "
                "official 'up to 100'. That is a MOCK observation; this walk "
                "neither inherits nor confirms it."
            ),
        },
    )


def _final_sweep(
    client: RealOrderClient,
    run: ProbeRun,
    args: argparse.Namespace,
    unresolved: list[str],
) -> None:
    """Last-chance cancel for anything still registered, then shout about leftovers."""
    for odno in list(unresolved):
        try:
            parsed = client.cancel(odno, int(args.quantity))
            ok = _ok(parsed)
            run.observe(final_sweep_cancel=odno, accepted=ok, msg=parsed.get("msg1"))
            if ok:
                unresolved.remove(odno)
        except Exception as exc:  # noqa: BLE001 — a sweep must never mask results
            run.observe(final_sweep_exception=f"{type(exc).__name__}: {exc}")
    if unresolved:
        run.error(
            "⚠ UNRESOLVED REAL ORDERS: "
            + ", ".join(unresolved)
            + " — these may still be RESTING on a real account. Cancel them by "
            "hand via HTS/MTS immediately (runbook §5.7)."
        )


def _dry_run_report(run: ProbeRun, args: argparse.Namespace, spec: ProbeSpec) -> None:
    """Show the exact live-mode preconditions without contacting the broker."""
    dry_run_banner(spec)
    run.observe(
        would_send=(
            f"{args.samples} resting BUY limit order(s) + "
            f"{args.order_class_ramp_attempts} ramp order(s) on a REAL account, "
            "each cancelled and verified immediately"
        ),
        live_mode_requires=[
            "--confirm",
            REAL_ORDER_CONFIRM_FLAG,
            "--expect-account-fingerprint <hex>",
            "--max-notional-krw <krw>",
            "--stage1-artifact <path to a fresh READY P-R5-PRE artifact>",
        ],
        body_shape=(
            "The order body is built only in live mode, from a plan that has "
            "passed the distance/tick/band assertions and the budget. A dry run "
            "has no quote and therefore no plan and no body."
        ),
    )


def _record_scope(run: ProbeRun) -> None:
    """The scope note every artifact from this module carries."""
    run.measure(
        "scope_and_transfer",
        {
            "environment": ENV_REAL,
            "account_scope": "ONE real futures account, ONE session",
            "does_not_transfer_to_mock": (
                "These values are REAL_PROD observations. They must not be "
                "written into a 모의투자 (MOCK_VTS) declaration, and the mock "
                "campaign's numbers must not be written here. The inheritance "
                "prohibition runs both ways."
            ),
            "approval": (
                "approval_status is UNAPPROVED_CANDIDATE. Sample adequacy is the "
                "Bounds-Approver's judgement, not this probe's — and n here is "
                f"small by design (hard cap {HARD_MAX_SAMPLES}) because every "
                "sample costs real exposure."
            ),
        },
    )


def add_real_order_args(parser: argparse.ArgumentParser) -> None:
    """Flags for the two real-money stages."""
    parser.allow_abbrev = False
    parser.set_defaults(
        price_offset_pct=DEFAULT_REAL_RESTING_OFFSET_PCT,
        samples=DEFAULT_REAL_SAMPLES,
    )
    parser.add_argument(
        REAL_ORDER_CONFIRM_FLAG,
        dest=_CONFIRM_DEST,
        action="store_true",
        help=(
            "REQUIRED for live mode. Acknowledges that this probe submits orders "
            "to a REAL brokerage account with real capital at risk. No "
            "abbreviation of this flag is accepted."
        ),
    )
    parser.add_argument(
        "--expect-account-fingerprint",
        default="",
        help=(
            "REQUIRED. The SHA-256 account fingerprint the probe is authorised "
            "to trade (12 hex chars, as printed in any prior artifact's "
            "credentials.account_fingerprint). A mismatch aborts, so a "
            "mis-wired credential cannot reach an unintended account."
        ),
    )
    parser.add_argument(
        "--max-notional-krw",
        type=float,
        default=None,
        help=(
            "REQUIRED for live mode, no default. Per-order ceiling in KRW, "
            "checked against max(touch, resting_price) x "
            "multiplier_krw_per_point x quantity."
        ),
    )
    parser.add_argument(
        "--max-cumulative-notional-krw",
        type=float,
        default=None,
        help=(
            "Ceiling on total TURNOVER across the run. Defaults to "
            "--max-notional-krw x (samples + ramp attempts). Peak EXPOSURE is "
            "bounded structurally instead: one order is live at a time."
        ),
    )
    parser.add_argument(
        "--stage1-artifact",
        default="",
        help=(
            "REQUIRED for live mode. Path to a fresh P-R5-PRE artifact whose "
            "preflight_verdict is READY_FOR_STAGE_2. Stage 2 re-takes every "
            "assertion in it against the live broker."
        ),
    )
    parser.add_argument(
        "--stage1-max-age-s",
        type=float,
        default=1800.0,
        help=(
            "How stale a stage-1 artifact may be (default 1800 s, hard cap "
            f"{HARD_MAX_STAGE1_AGE_S:.0f} s). Account state changes; an old "
            "preflight attests to a state that no longer holds."
        ),
    )
    parser.add_argument(
        "--min-touch-distance-pct",
        type=float,
        default=DEFAULT_MIN_TOUCH_DISTANCE_PCT,
        help=(
            "Independent floor on how far the computed resting price must sit "
            f"from the touch (default {DEFAULT_MIN_TOUCH_DISTANCE_PCT}%%). "
            "Deliberately a different number from --price-offset-pct: lowering "
            "the offset does not lower this assertion."
        ),
    )
    parser.add_argument(
        "--min-session-remaining-s",
        type=float,
        default=DEFAULT_MIN_SESSION_REMAINING_S,
        help=(
            "Refuse to start with less than this much session left (default "
            f"{DEFAULT_MIN_SESSION_REMAINING_S:.0f} s). A cancel is not accepted "
            "after the close."
        ),
    )
    parser.add_argument(
        "--cancel-retry-attempts",
        type=int,
        default=3,
        help=(
            f"Bounded cancel retries (default 3, hard cap "
            f"{HARD_MAX_CANCEL_RETRIES}). Exhausting them aborts the whole run "
            "and reports the ODNO."
        ),
    )
    parser.add_argument(
        "--order-class-ramp-attempts",
        type=int,
        default=2,
        help=(
            f"SUBMIT-class pacing ramp steps (default 2, hard cap "
            f"{HARD_MAX_RAMP_ATTEMPTS}, 0 disables). Each step is a full guarded "
            "trial; the ramp stops at the first throttle."
        ),
    )
    parser.add_argument(
        "--order-class-ramp-step-s",
        type=float,
        default=0.3,
        help="How much to tighten the submit interval per ramp step.",
    )
    parser.add_argument(
        "--order-class-ramp-floor-s",
        type=float,
        default=0.4,
        help=(
            "Floor on the ramped submit interval. The ramp probes for a throttle "
            "boundary; it does not try to find the breaking point."
        ),
    )
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=(
            f"Minimum interval between ANY two broker calls (default "
            f"{DEFAULT_PACE_S}s), quote/submit/cancel/inquire alike. Same "
            "measured basis as the mock harness (P-13 bracketed the query class "
            "at clean 1.0 rps / throttled 2.0 rps); the order class is known to "
            "be TIGHTER, which is what --order-class-ramp-attempts observes."
        ),
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=200.0,
        help=(
            "Requested visibility poll interval. Floored by --pace-s; the "
            "artifact records the EFFECTIVE value."
        ),
    )
    parser.add_argument(
        "--visibility-timeout-s",
        type=float,
        default=30.0,
        help="Give up on a trial after this. Expiry stays CENSORED.",
    )
    parser.add_argument(
        "--inter-trial-s", type=float, default=2.0, help="Pause between trials."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help=(
            f"End-of-run continuation walk cap (default 5, hard cap "
            f"{HARD_MAX_PAGES}). If our cap ends the walk, the total row count "
            "is recorded as UNESTABLISHED."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
