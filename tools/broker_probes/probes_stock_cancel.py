"""P-SC — 주식 MOCK 취소 행 모양과 늦은 체결 관측 (#948 순서 1, #980)."""

from __future__ import annotations

import argparse
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as clock_time
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from tools.broker_probes.common import (
    STATUS_RATE_LIMITED,
    STATUS_TRANSIENT,
    ProbeError,
    ProbeRun,
    SafetyViolation,
    account_fingerprint,
    call_evidence,
    classify_answer,
    rt_cd_of,
    transport_excerpt,
    transport_transient_types,
)
from tools.broker_probes.probes_order import (
    KST,
    MockTradingClient,
    Placed,
    Tick,
    TickPrice,
    _ccld_int,
    _odno_encoding,
    _setup,
    _stock_holding_qty,
    build_stock_cancel_body,
    odno_key,
    snap_to_tick,
)
from tools.broker_probes.registry import get

# The ONE reading of «does this row still have quantity that can fill». It lives in
# mock_flat_check because that is the tool the operator runs to declare the account flat;
# importing it here keeps this probe from growing a second, looser interpretation of
# cncl_yn (#1158 리뷰 · #948). That module's own imports are stdlib-only, so this does not
# pull the ops stack into the probe.
from tools.tos_cp3.ops.mock_flat_check import (
    cancel_confirmed_qty,
    cancel_parent_odnos,
    row_has_working_quantity,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    _REPO_ROOT / "config" / "broker_probes" / "stock_cancel_probe.yaml"
)

POLICY_VERSION = "p-sc-cancel-shape/1"

SCHEMA_VERSION = 1

_STOP_PREFIX = "PSC_STOP="
_SHAPE_PREFIX = "PSC_CANCEL_SHAPE="
_FLAT_PREFIX = "PSC_FLAT_AT_END="

_STOP_NONE = "none"
_STOP_DRY_RUN = "dry_run"
_STOP_REJECTED = "rejected"
_STOP_RATE_LIMITED = "rate_limited"
_STOP_ORDER_STATE_UNKNOWN = "order_state_unknown"
_STOP_QUERY_UNANSWERED = "query_unanswered"
_STOP_CANCEL_NOT_CONFIRMED = "cancel_not_confirmed"
_STOP_CANCEL_NOT_SENDABLE = "cancel_not_sendable"
_STOP_PROBE_ERROR = "probe_error"

_SHAPE_ORIGINAL_FLAGGED = "ORIGINAL_ROW_FLAGGED"
_SHAPE_SEPARATE_ROW = "SEPARATE_ROW_WITH_ORGN_ODNO"
_SHAPE_BOTH = "BOTH"
_SHAPE_NONE = "NEITHER_OBSERVED"
_SHAPE_UNDETERMINED = "UNDETERMINED"

_READ_OK = "OK"
_READ_REFUSED = "REFUSED"
_READ_RATE_LIMITED = STATUS_RATE_LIMITED
_READ_TRANSIENT = STATUS_TRANSIENT
_READ_CAPPED = "PAGE_CAP"
_READ_TRUNCATED = "PAGE_ROW_CAP"

_READ_ANSWERED = (_READ_OK, _READ_TRUNCATED)

_PARTIAL_OBSERVED = "PARTIAL_FILL_OBSERVED"
_PARTIAL_FILLED_FULLY = "NOT_PRODUCIBLE__FILLED_FULLY"
_PARTIAL_NO_FILL = "NOT_PRODUCIBLE__NO_FILL"
_PARTIAL_UNDETERMINED = "NOT_PRODUCIBLE__FILL_UNDETERMINED"

_CLEAN_FLAT = "FLAT"
_CLEAN_NOTHING_TO_DO = "ALREADY_FLAT_NOTHING_TO_DO"
_CLEAN_STILL_LIVE = "ORDER_STILL_LIVE"
_CLEAN_STILL_HELD = "SHARES_STILL_HELD"
_CLEAN_UNKNOWN = "UNDETERMINED"
_CLEAN_BUDGET_SPENT = "REFUSED_ORDER_BUDGET_SPENT"

_REAL_MARKET_ENV = ("KIS_STOCK_MARKET", "KIS_FUTURES_MARKET")
_REAL_TRADING_ENV = "KIS_REAL_TRADING"
_TRUTHY = {"1", "true", "yes", "on"}

# The day's KIS 개장일여부 answer is cached where the CP-3 cron tenant gate caches
# it (tools/tos_cp3/runners/cp3_tenant_daily.sh:394 and its `STATE` default), so a
# P-SC run on a morning the cron already asked costs no second broker call — KIS
# asks for 「가급적 1일 1회 호출」 and this host answers that per host, not per tool.
_MARKET_OPEN_CACHE_ENV = "CP3_DAILY_MARKET_OPEN_CACHE"
_MARKET_OPEN_STATE_ENV = "CP3_DAILY_STATE"
_MARKET_OPEN_STATE_DEFAULT = "~/.local/state/tos"
_MARKET_OPEN_CACHE_LEAF = "market-open"

_MARKET_OPEN_ASKED = "KIS_ANSWERED"
_MARKET_OPEN_FALLBACK = "CALENDAR_FALLBACK"


@dataclass(frozen=True)
class SessionLimits:
    """When the probe may run at all."""

    calendar_path: Path
    start: clock_time
    end: clock_time
    market_open_producer_config: Path


@dataclass(frozen=True)
class CleanupLimits:
    cancel_attempts: int
    retry_s: float


@dataclass(frozen=True)
class Limits:
    pace_s: float
    pace_s_floor: float
    max_order_calls: int
    max_quantity: int
    cleanup: CleanupLimits


@dataclass(frozen=True)
class Observation:
    cancel_window_s: float
    poll_interval_s: float


@dataclass(frozen=True)
class FlatCheck:
    balance_max_pages: int
    ccld_page_row_cap: int


@dataclass(frozen=True)
class TrialLimits:
    enabled: bool
    quantity: int
    price_offset_pct: float


def _repo_relative(path: Path) -> str:
    """``path`` relative to the repo root when it is inside it, else as given."""
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


@dataclass(frozen=True)
class Config:
    path: Path
    session: SessionLimits
    limits: Limits
    observation: Observation
    flat_check: FlatCheck
    trial_a: TrialLimits
    trial_b: TrialLimits

    @property
    def enabled_trials(self) -> int:
        return 1 + (1 if self.trial_b.enabled else 0)

    @property
    def flatten_reserve(self) -> int:
        """Order calls the capped sell-back can need, worst case."""
        total = self.trial_a.quantity + (
            self.trial_b.quantity if self.trial_b.enabled else 0
        )
        return math.ceil(total / self.limits.max_quantity)

    def describe(self) -> dict[str, Any]:
        """The effective limits, for the artifact."""
        return {
            "config_path": _repo_relative(self.path),
            "schema_version": SCHEMA_VERSION,
            "session": {
                "calendar_path": _repo_relative(self.session.calendar_path),
                "window_kst": f"{self.session.start:%H:%M}-{self.session.end:%H:%M}",
                "market_open_producer_config": _repo_relative(
                    self.session.market_open_producer_config
                ),
            },
            "limits": {
                "pace_s": self.limits.pace_s,
                "pace_s_floor": self.limits.pace_s_floor,
                "max_order_calls": self.limits.max_order_calls,
                "flatten_reserve": self.flatten_reserve,
                "max_quantity": self.limits.max_quantity,
                "cleanup_cancel_attempts": self.limits.cleanup.cancel_attempts,
                "cleanup_retry_s": self.limits.cleanup.retry_s,
            },
            "observation": {
                "cancel_window_s": self.observation.cancel_window_s,
                "poll_interval_s": self.observation.poll_interval_s,
            },
            "flat_check": {
                "balance_max_pages": self.flat_check.balance_max_pages,
                "ccld_page_row_cap": self.flat_check.ccld_page_row_cap,
            },
            "trials": {
                "a": {
                    "quantity": self.trial_a.quantity,
                    "price_offset_pct": self.trial_a.price_offset_pct,
                },
                "b": {
                    "enabled": self.trial_b.enabled,
                    "quantity": self.trial_b.quantity,
                    "price_offset_pct": self.trial_b.price_offset_pct,
                },
            },
        }


def _require(block: Any, key: str, where: str) -> Any:
    """One key of a config mapping, or a refusal naming the path."""
    if not isinstance(block, dict):
        raise ProbeError(
            f"{where} must be a mapping in the P-SC config, got {type(block).__name__}"
        )
    if key not in block:
        raise ProbeError(
            f"{where}.{key} is missing from the P-SC config and has no default"
        )
    return block[key]


def _req_float(block: Any, key: str, where: str, *, positive: bool = True) -> float:
    raw = _require(block, key, where)
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"{where}.{key}={raw!r} is not a number") from exc
    if positive and value <= 0:
        raise ProbeError(f"{where}.{key}={value} must be positive")
    return value


def _req_int(block: Any, key: str, where: str, *, minimum: int = 1) -> int:
    raw = _require(block, key, where)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ProbeError(f"{where}.{key}={raw!r} is not an integer")
    if raw < minimum:
        raise ProbeError(f"{where}.{key}={raw} must be >= {minimum}")
    return raw


def _req_hhmm(block: Any, key: str, where: str) -> clock_time:
    raw = str(_require(block, key, where))
    try:
        hour, minute = raw.split(":")
        return clock_time(int(hour), int(minute))
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"{where}.{key}={raw!r} is not HH:MM") from exc


def load_config(path: Path | str | None = None) -> Config:
    """Read and validate the P-SC limits."""
    target = Path(path) if path else DEFAULT_CONFIG_PATH
    target = target.expanduser()
    if not target.is_absolute():
        target = (_REPO_ROOT / target).resolve()
    if not target.is_file():
        raise ProbeError(f"P-SC config not found: {target}")
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProbeError(f"P-SC config {target} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ProbeError(f"P-SC config {target} must be a mapping at the top level")
    declared = data.get("schema_version")
    if declared != SCHEMA_VERSION:
        raise ProbeError(
            f"P-SC config {target} declares schema_version={declared!r}; this module "
            f"reads {SCHEMA_VERSION}. A config written for another schema is refused "
            "rather than read key by key"
        )

    session_block = _require(data, "session", "P-SC config")
    window_block = _require(session_block, "window", "session")
    calendar_raw = Path(str(_require(session_block, "calendar_path", "session")))
    calendar_path = (
        calendar_raw if calendar_raw.is_absolute() else _REPO_ROOT / calendar_raw
    )
    if not calendar_path.is_file():
        raise ProbeError(f"session.calendar_path does not exist: {calendar_path}")
    producer_raw = Path(
        str(_require(session_block, "market_open_producer_config", "session"))
    )
    producer_path = (
        producer_raw if producer_raw.is_absolute() else _REPO_ROOT / producer_raw
    )
    if not producer_path.is_file():
        raise ProbeError(
            f"session.market_open_producer_config does not exist: {producer_path}. "
            "The KIS 개장일여부 gate reads ONE key out of it — `env_file`, the REAL "
            "stock credential pair's file — and a missing file is a configuration "
            "error, not a broker outage, so it is refused rather than fallen back"
        )
    start = _req_hhmm(window_block, "start", "session.window")
    end = _req_hhmm(window_block, "end", "session.window")
    if start >= end:
        raise ProbeError(
            f"session.window start {start:%H:%M} is not before end {end:%H:%M} — "
            "a window that does not advance admits nothing and would read as a "
            "permanent refusal rather than a configuration error"
        )

    limits_block = _require(data, "limits", "P-SC config")
    cleanup_block = _require(limits_block, "cleanup", "limits")
    pace_floor = _req_float(limits_block, "pace_s_floor", "limits")
    pace_s = _req_float(limits_block, "pace_s", "limits")
    if pace_s < pace_floor:
        raise ProbeError(
            f"limits.pace_s={pace_s} is below limits.pace_s_floor={pace_floor}. "
            "The floor is in the same file on purpose: a bound written in code "
            "beside a value in YAML is two sources for one limit"
        )
    limits = Limits(
        pace_s=pace_s,
        pace_s_floor=pace_floor,
        max_order_calls=_req_int(limits_block, "max_order_calls", "limits"),
        max_quantity=_req_int(limits_block, "max_quantity", "limits"),
        cleanup=CleanupLimits(
            cancel_attempts=_req_int(
                cleanup_block, "cancel_attempts", "limits.cleanup"
            ),
            retry_s=_req_float(cleanup_block, "retry_s", "limits.cleanup"),
        ),
    )

    obs_block = _require(data, "observation", "P-SC config")
    observation = Observation(
        cancel_window_s=_req_float(obs_block, "cancel_window_s", "observation"),
        poll_interval_s=_req_float(obs_block, "poll_interval_s", "observation"),
    )

    flat_block = _require(data, "flat_check", "P-SC config")
    flat_check = FlatCheck(
        balance_max_pages=_req_int(flat_block, "balance_max_pages", "flat_check"),
        ccld_page_row_cap=_req_int(flat_block, "ccld_page_row_cap", "flat_check"),
    )

    trials_block = _require(data, "trials", "P-SC config")
    a_block = _require(trials_block, "a", "trials")
    b_block = _require(trials_block, "b", "trials")
    enabled = _require(b_block, "enabled", "trials.b")
    if not isinstance(enabled, bool):
        raise ProbeError(f"trials.b.enabled={enabled!r} must be a boolean")
    trial_a = TrialLimits(
        enabled=True,
        quantity=_req_int(a_block, "quantity", "trials.a"),
        price_offset_pct=_req_float(a_block, "price_offset_pct", "trials.a"),
    )
    trial_b = TrialLimits(
        enabled=enabled,
        quantity=_req_int(b_block, "quantity", "trials.b"),
        price_offset_pct=_req_float(b_block, "price_offset_pct", "trials.b"),
    )
    for name, trial in (("a", trial_a), ("b", trial_b)):
        if trial.quantity > limits.max_quantity:
            raise ProbeError(
                f"trials.{name}.quantity={trial.quantity} exceeds "
                f"limits.max_quantity={limits.max_quantity}"
            )
        if trial.price_offset_pct >= 100.0:
            raise ProbeError(
                f"trials.{name}.price_offset_pct={trial.price_offset_pct} would put a "
                "resting BUY at or below zero"
            )

    cfg = Config(
        path=target,
        session=SessionLimits(
            calendar_path=calendar_path,
            start=start,
            end=end,
            market_open_producer_config=producer_path,
        ),
        limits=limits,
        observation=observation,
        flat_check=flat_check,
        trial_a=trial_a,
        trial_b=trial_b,
    )
    floor = cfg.flatten_reserve + 2 * cfg.enabled_trials
    if limits.max_order_calls < floor:
        raise ProbeError(
            f"limits.max_order_calls={limits.max_order_calls} is below the "
            f"minimum {floor} this configuration needs: 2 calls (submit + cancel) "
            f"for each of {cfg.enabled_trials} enabled trial(s) plus "
            f"{cfg.flatten_reserve} reserved flatten call(s) "
            f"(ceil(total trial quantity / limits.max_quantity)). A budget that "
            "cannot fund the flatten ends the run holding shares it bought"
        )
    return cfg


def _now() -> datetime:
    """The run clock, KST. A function so tests can replace it."""
    return datetime.now(KST)


def assert_mock_only_env() -> dict[str, Any]:
    """Refuse when the environment names a REAL market or arms real trading."""
    seen: dict[str, str] = {}
    for name in _REAL_MARKET_ENV:
        raw = os.getenv(name, "").strip()
        if raw:
            seen[name] = raw
        if raw and raw.lower() != "mock":
            raise SafetyViolation(
                f"{name}={raw!r} names a non-mock market. P-SC sends 모의투자 orders "
                "only, and a REAL app key on the mock host is still a REAL "
                "credential. Source .env.mock, not the paper .env"
            )
    raw_real = os.getenv(_REAL_TRADING_ENV, "").strip()
    if raw_real:
        seen[_REAL_TRADING_ENV] = raw_real
        if raw_real.lower() in _TRUTHY:
            raise SafetyViolation(
                f"{_REAL_TRADING_ENV}={raw_real!r} arms real trading — refusing to run "
                "an order-emitting probe in that environment"
            )
    return {
        "checked": list(_REAL_MARKET_ENV) + [_REAL_TRADING_ENV],
        "observed": seen,
        "verdict": "MOCK_ONLY",
    }


def _holidays(cfg: Config) -> frozenset[date]:
    """The closed days the configured calendar declares."""
    from tools.tos_cp3 import session_day as sd

    data = yaml.safe_load(cfg.session.calendar_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProbeError(f"{cfg.session.calendar_path}: top level is not a mapping")
    try:
        return sd.holidays_of(data)
    except sd.SessionDayError as exc:
        raise ProbeError(f"{cfg.session.calendar_path}: {exc}") from exc


def _market_open_cache_dir() -> Path:
    """Where the day's KIS 개장일여부 answer lives — the cron gate's convention."""
    raw = os.getenv(_MARKET_OPEN_CACHE_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    state = os.getenv(_MARKET_OPEN_STATE_ENV, "").strip() or _MARKET_OPEN_STATE_DEFAULT
    return Path(state).expanduser() / _MARKET_OPEN_CACHE_LEAF


def _ask_kis_open(cfg: Config, day: date) -> tuple[str | None, str]:
    """*day*'s ``opnd_yn`` (``"Y"``/``"N"``) and its source, or ``(None, why not)``.

    The one broker call this probe's day gate makes, and it is not this module's:
    ``tools/tos_cp3/ops/market_open.py`` (#1143) owns the KIS 국내휴장일조회 read,
    its allowlist assertion, its once-a-day cache and its credential handling.
    GET only, REAL key, no order path — nothing here sends anything.
    """
    from tools.tos_cp3.ops import market_open as mo

    # SAFETY: `market_open.fetch_opnd_yn` builds its credential object straight
    # from the producer's `env_file` and never writes to `os.environ` (#1151
    # review). This restore is the second lock on the same door: P-SC sends
    # 모의투자 orders with whatever the environment names, so a REAL key left
    # behind by this call — by a future transport, a library, anything on the way —
    # would become an ORDER key. The environment is put back exactly as it was,
    # before `_setup` resolves anything.
    saved = dict(os.environ)
    try:
        return mo.broker_answer(
            day,
            cache_dir=_market_open_cache_dir(),
            cache_only=False,
            producer_config=cfg.session.market_open_producer_config,
            repo_root=_REPO_ROOT,
            timeout_s=mo.DEFAULT_TIMEOUT_S,
        )
    except (mo.MarketOpenUnreadable, OSError) as exc:
        # A cache dir that cannot be made or locked is the same kind of «could not
        # ask» as a broker that did not answer: never a silent admit, never a
        # traceback — the calendar rule decides, and the record says it did.
        return None, f"KIS unreadable ({type(exc).__name__}: {exc})"
    finally:
        for key in set(os.environ) - set(saved):
            os.environ.pop(key, None)
        os.environ.update(saved)


def assert_session_window(cfg: Config, now: datetime) -> dict[str, Any]:
    """Refuse outside the configured KRX window, and on a non-trading day.

    A non-trading day is two things: one the calendar lists (or a weekend), and
    one only the broker knows — KIS 국내휴장일조회 (#1149). When KIS cannot be read
    the calendar rule alone decides, exactly as it did before, and the returned
    record says which of the two answered.
    """
    from tools.tos_cp3 import session_day as sd
    from tools.tos_cp3.ops import market_open as mo

    kst = now.astimezone(KST)
    holidays = _holidays(cfg)
    # SAFETY: 연도 커버리지 거부는 2026-11-20 에 없어졌다(운영자 지시 — 「캘린더 관리가
    # 리스크가 안 되어도 돼」 · #1147 이 생산자에서 먼저 걷었다). 주문을 막는 거부는
    # 그대로다 — 주말이거나 달력에 적힌 휴장일이면 아래에서 거부한다. 달라진 것은
    # 적히지 않은 평일이 어느 해든 거래일로 읽히는 것뿐이다.
    if not sd.is_trading_day(kst.date(), holidays):
        raise ProbeError(
            f"{kst:%Y-%m-%d} (KST) is not a KRX trading day per "
            f"{cfg.session.calendar_path.name} — weekday={kst.strftime('%a')}, "
            f"declared_holiday={kst.date() in holidays}"
        )
    if not (cfg.session.start <= kst.time() <= cfg.session.end):
        raise ProbeError(
            f"{kst:%H:%M:%S} KST is outside the configured window "
            f"{cfg.session.start:%H:%M}-{cfg.session.end:%H:%M}. P-SC sends orders, "
            "so the window is a refusal and not a warning"
        )
    # The calendar lists the holidays somebody wrote down; KIS knows the ones
    # nobody did (#1149 — 2027-01-01 is the example). Asked LAST, after the three
    # local refusals: those cost no broker call, and a run that is refused anyway
    # must not spend a credential. The answer is the cron tenant gate's, cached in
    # the same directory, so the two gates on this host cannot disagree.
    answer, source = _ask_kis_open(cfg, kst.date())
    if answer == mo.OPEN_NO:
        raise ProbeError(
            f"{kst:%Y-%m-%d} (KST): KIS 국내휴장일조회 answered opnd_yn=N — KRX did "
            f"not open on a weekday {cfg.session.calendar_path.name} does not list "
            f"({source}). P-SC sends MOCK orders and a closed market fills none of "
            "them, so this is a refusal and not a warning. Add the date to that "
            "calendar's `holidays` so every gate on this host agrees"
        )
    return {
        "now_kst": kst.isoformat(),
        "trading_day": True,
        "window_kst": f"{cfg.session.start:%H:%M}-{cfg.session.end:%H:%M}",
        "calendar": _repo_relative(cfg.session.calendar_path),
        "holidays_declared": len(holidays),
        "market_open": {
            "verdict": (
                _MARKET_OPEN_ASKED if answer is not None else _MARKET_OPEN_FALLBACK
            ),
            "opnd_yn": answer,
            "source": source,
            "tr_id": mo.HOLIDAY_TR,
            "producer_config": _repo_relative(cfg.session.market_open_producer_config),
            "cache_dir": str(_market_open_cache_dir()),
        },
    }


class OrderBudget:
    """A hard cap on order-emitting POSTs for one run."""

    def __init__(self, limit: int, *, reserved_for_flatten: int = 0) -> None:
        self.limit = int(limit)
        self.reserved = max(0, int(reserved_for_flatten))
        self.spent: list[str] = []
        self.reserve_spent: list[str] = []

    @property
    def remaining(self) -> int:
        """General-purpose calls left. The reserve is NOT included."""
        return self.limit - self.reserved - len(self.spent)

    @property
    def reserve_remaining(self) -> int:
        return self.reserved - len(self.reserve_spent)

    def can_spend(self, *, from_reserve: bool = False) -> bool:
        """Whether :meth:`spend` would succeed, without spending anything."""
        if from_reserve and self.reserve_remaining > 0:
            return True
        return self.remaining > 0

    def spend(self, what: str, *, from_reserve: bool = False) -> None:
        """Charge one order call, or refuse."""
        if from_reserve and self.reserve_remaining > 0:
            self.reserve_spent.append(what)
            return
        if self.remaining <= 0:
            pool = (
                f"{self.limit} calls, {self.reserved} of them reserved for the "
                f"flatten ({self.reserve_remaining} of the reserve left)"
            )
            raise SafetyViolation(
                f"order-call budget exhausted ({pool}: "
                f"{', '.join(self.spent + self.reserve_spent)}) — refusing to "
                f"send {what!r}. Raise limits.max_order_calls in the P-SC config "
                "if the plan really needs more, and say why"
            )
        self.spent.append(what)

    def describe(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "reserved_for_flatten": self.reserved,
            "used": len(self.spent) + len(self.reserve_spent),
            "general_used": len(self.spent),
            "reserve_used": len(self.reserve_spent),
            "calls": list(self.spent) + list(self.reserve_spent),
        }


_VerboseGet = Callable[..., tuple[int, dict[str, Any], str, float]]


def _classified(
    call: _VerboseGet, /, *args: Any, **kwargs: Any
) -> tuple[str | None, int, dict[str, Any], str]:
    """Run one verbose GET and fold transport failures into the shared classification."""
    try:
        status, parsed, text, _ms = call(*args, **kwargs)
    except transport_transient_types() as exc:
        return _READ_TRANSIENT, 0, {}, transport_excerpt(exc)
    return classify_answer(status, parsed, text), status, parsed, text


def _unhealthy_status(kind: str) -> str:
    """Map a ``classify_answer`` kind onto this module's read vocabulary."""
    return _READ_TRANSIENT if kind.startswith(STATUS_TRANSIENT) else _READ_RATE_LIMITED


def read_holding(client: MockTradingClient, symbol: str, cfg: Config) -> dict[str, Any]:
    """Walk the balance until ``symbol``'s row is found or the broker ends the set."""
    fk = nk = ""
    record: dict[str, Any] = {
        "surface": "주식잔고조회 VTTC8434R (/uapi/domestic-stock/v1/trading/inquire-balance)",
        "symbol": symbol,
        "pages_read": 0,
    }
    for _page in range(cfg.flat_check.balance_max_pages):
        kind, http_status, parsed, text = _classified(
            client.stock_balance_verbose, fk=fk, nk=nk
        )
        record["pages_read"] += 1
        if kind is not None:
            return record | {
                "status": _unhealthy_status(kind),
                "qty": None,
                "evidence": call_evidence(
                    status_kind=kind, http_status=http_status, parsed=parsed, text=text
                ),
            }
        if rt_cd_of(parsed) != "0":
            return record | {
                "status": _READ_REFUSED,
                "qty": None,
                "evidence": call_evidence(
                    status_kind=_READ_REFUSED,
                    http_status=http_status,
                    parsed=parsed,
                    text=text,
                ),
            }
        rows = parsed.get("output1")
        rows = rows if isinstance(rows, list) else []
        if any(str(r.get("pdno", "")).strip() == symbol for r in rows):
            return record | {
                "status": _READ_OK,
                "qty": _stock_holding_qty(rows, symbol),
            }
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not next_fk and not next_nk:
            return record | {"status": _READ_OK, "qty": 0}
        fk, nk = next_fk, next_nk
    return record | {
        "status": _READ_CAPPED,
        "qty": None,
        "page_cap": cfg.flat_check.balance_max_pages,
        "note": (
            "the walk hit flat_check.balance_max_pages before the broker ended the "
            "set, so whether the symbol is held is UNDETERMINED — never 'not held'"
        ),
    }


def _row_is_live(
    row: dict[str, Any], *, cancel_parents: frozenset[str] = frozenset()
) -> bool:
    """A row that still has quantity working on the book — ``mock_flat_check``'s ONE reading."""
    return row_has_working_quantity(row, cancel_parents=cancel_parents)


def _live_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The rows of ONE read that still have quantity working, judged against that whole read."""
    parents = cancel_parent_odnos(rows)
    return [r for r in rows if _row_is_live(r, cancel_parents=parents)]


def _confirmation_basis(row: dict[str, Any]) -> str:
    """Which rule closed this row, for the artifact."""
    remaining = _ccld_int(row, "rmn_qty")
    ordered = _ccld_int(row, "ord_qty")
    filled = _ccld_int(row, "tot_ccld_qty")
    confirmed = cancel_confirmed_qty(row)
    if remaining is not None and remaining > 0:
        return f"취소확인수량 cncl_cfrm_qty={confirmed} covers rmn_qty={remaining}"
    if ordered is not None and filled is not None and ordered - filled > 0:
        return (
            f"rmn_qty=0 and the 주문수량 − 총체결수량 shortfall {ordered - filled} is "
            f"accounted for (cncl_yn={row.get('cncl_yn')!r}, "
            f"rjct_qty={_ccld_int(row, 'rjct_qty')}, cncl_cfrm_qty={confirmed}, "
            "or another row of this read names this one as its 원주문)"
        )
    return f"nothing was outstanding (rmn_qty={remaining!r}, ord_qty == tot_ccld_qty)"


def read_order_rows(
    client: MockTradingClient, symbol: str, cfg: Config, *, walk: bool
) -> dict[str, Any]:
    """One (or every) page of 주식일별주문체결조회 for ``symbol``, rows verbatim."""
    fk = nk = ""
    rows: list[dict[str, Any]] = []
    page_counts: list[int] = []
    record: dict[str, Any] = {
        "surface": (
            "주식일별주문체결조회 VTTC0081R "
            "(/uapi/domestic-stock/v1/trading/inquire-daily-ccld), CCLD_DVSN=00 전체, "
            "INQR_DVSN=00 역순"
        ),
        "symbol": symbol,
        "walked": walk,
    }
    pages = cfg.flat_check.balance_max_pages if walk else 1
    for _page in range(pages):
        kind, http_status, parsed, text = _classified(
            client.stock_daily_ccld_verbose, symbol, fk=fk, nk=nk
        )
        if kind is not None:
            return record | {
                "status": _unhealthy_status(kind),
                "rows": rows,
                "rows_returned": page_counts,
                "evidence": call_evidence(
                    status_kind=kind, http_status=http_status, parsed=parsed, text=text
                ),
            }
        if rt_cd_of(parsed) != "0":
            return record | {
                "status": _READ_REFUSED,
                "rows": rows,
                "rows_returned": page_counts,
                "evidence": call_evidence(
                    status_kind=_READ_REFUSED,
                    http_status=http_status,
                    parsed=parsed,
                    text=text,
                ),
            }
        page = parsed.get("output1")
        page = page if isinstance(page, list) else []
        rows.extend(page)
        page_counts.append(len(page))
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not walk:
            status = (
                _READ_TRUNCATED
                if len(page) >= cfg.flat_check.ccld_page_row_cap
                else _READ_OK
            )
            return record | {
                "status": status,
                "rows": rows,
                "rows_returned": page_counts,
                "live_rows": _live_rows(rows),
                "continuation_pending": bool(next_fk or next_nk),
            }
        if not next_fk and not next_nk:
            return record | {
                "status": _READ_OK,
                "rows": rows,
                "rows_returned": page_counts,
                "live_rows": _live_rows(rows),
            }
        fk, nk = next_fk, next_nk
    return record | {
        "status": _READ_CAPPED,
        "rows": rows,
        "rows_returned": page_counts,
        "live_rows": _live_rows(rows),
        "page_cap": pages,
        "note": (
            "the walk hit the page cap before the broker ended the set, so "
            "'no order is open' is UNDETERMINED"
        ),
    }


def assert_flat_start(
    client: MockTradingClient, symbol: str, cfg: Config
) -> dict[str, Any]:
    """Refuse unless the account provably holds none of ``symbol`` and has no open order."""
    holding = read_holding(client, symbol, cfg)
    orders = read_order_rows(client, symbol, cfg, walk=True)
    record: dict[str, Any] = {"holding": holding, "orders": orders}
    if holding.get("status") != _READ_OK:
        raise ProbeError(
            f"cannot establish that {symbol} is unheld: balance read ended "
            f"{holding.get('status')}. A read that did not answer is not a flat "
            f"account. Record: {holding}"
        )
    if holding.get("qty"):
        raise ProbeError(
            f"the account already holds {holding['qty']} share(s) of {symbol}. P-SC "
            "starts flat so its cancel and flatten cannot touch anything that was "
            "already there"
        )
    if orders.get("status") != _READ_OK:
        raise ProbeError(
            f"cannot establish that no {symbol} order is open: the execution "
            f"inquiry ended {orders.get('status')}. Record: "
            f"{ {k: v for k, v in orders.items() if k != 'rows'} }"
        )
    live = orders.get("live_rows") or []
    if live:
        raise ProbeError(
            f"{len(live)} open {symbol} order row(s) are already on the book "
            f"(first odno={live[0].get('odno')!r}). P-SC will not place an order "
            "beside an order it did not place"
        )
    record["verdict"] = "FLAT"
    return record


def _cancel_row_summary(
    row: dict[str, Any], *, cancel_parents: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """The fields #948 순서 1 asks for, named, for a row a cancel may have produced."""
    return {
        "odno": row.get("odno"),
        "orgn_odno": row.get("orgn_odno"),
        "ord_qty": _ccld_int(row, "ord_qty"),
        "tot_ccld_qty": _ccld_int(row, "tot_ccld_qty"),
        "rmn_qty": _ccld_int(row, "rmn_qty"),
        "cncl_yn": row.get("cncl_yn"),
        "cancel_confirmed_qty": cancel_confirmed_qty(row),
        "still_working": row_has_working_quantity(row, cancel_parents=cancel_parents),
    }


def _row_view(
    row: dict[str, Any], *, cancel_parents: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """One query row, verbatim, plus the two identifier encodings."""
    return {
        "raw": dict(row),
        "odno_encoding": _odno_encoding(str(row.get("odno", ""))),
        "orgn_odno_encoding": _odno_encoding(str(row.get("orgn_odno", ""))),
        "live": _row_is_live(row, cancel_parents=cancel_parents),
    }


def _snapshot(
    client: MockTradingClient,
    symbol: str,
    cfg: Config,
    *,
    label: str,
    original_key: str,
    t0_monotonic: float,
) -> dict[str, Any]:
    """One read of the order surface, classified against the original ODNO."""
    read = read_order_rows(client, symbol, cfg, walk=False)
    rows = read.get("rows") or []
    parents = cancel_parent_odnos(rows)
    view = partial(_row_view, cancel_parents=parents)
    original: dict[str, Any] | None = None
    derived: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for row in rows:
        try:
            own = odno_key(row.get("odno"))
            parent = odno_key(row.get("orgn_odno"))
        except ProbeError as exc:
            unreadable.append(view(row) | {"odno_key_error": str(exc)})
            continue
        if own == original_key:
            if original is None:
                original = view(row)
            else:
                derived.append(view(row) | {"duplicate_of_original_odno": True})
        elif parent == original_key:
            derived.append(view(row))
    snapshot = {
        "label": label,
        "t_offset_ms": round((time.monotonic() - t0_monotonic) * 1000.0, 1),
        "read_status": read.get("status"),
        "rows_returned": read.get("rows_returned"),
        "continuation_pending": read.get("continuation_pending"),
        "rows": [view(r) for r in rows],
        "original_row": original,
        "derived_rows": derived,
        "unreadable_rows": unreadable,
        "cancel_parent_odnos": sorted(parents),
        "original_cncl_yn": (original or {}).get("raw", {}).get("cncl_yn"),
        "original_rmn_qty": _ccld_int((original or {}).get("raw", {}), "rmn_qty"),
        "original_tot_ccld_qty": _ccld_int(
            (original or {}).get("raw", {}), "tot_ccld_qty"
        ),
        "original_cancel_confirmed_qty": (
            None if original is None else cancel_confirmed_qty(original["raw"])
        ),
        "original_still_working": (
            None
            if original is None
            else row_has_working_quantity(original["raw"], cancel_parents=parents)
        ),
        "derived_row_summaries": [
            _cancel_row_summary(d["raw"], cancel_parents=parents) for d in derived
        ],
    }
    if "evidence" in read:
        snapshot["evidence"] = read["evidence"]
    return snapshot


def classify_cancel_shape(
    snapshots: list[dict[str, Any]], original_key: str
) -> dict[str, Any]:
    """What shape the cancel took, across every post-cancel snapshot."""
    answered = [s for s in snapshots if s.get("read_status") in _READ_ANSWERED]
    untruncated = [s for s in answered if s.get("read_status") == _READ_OK]
    flagged = [
        s
        for s in answered
        if str((s.get("original_row") or {}).get("raw", {}).get("cncl_yn", ""))
        .strip()
        .upper()
        == "Y"
    ]
    with_derived = [s for s in answered if s.get("derived_rows")]
    if not answered:
        shape = _SHAPE_UNDETERMINED
    elif flagged and with_derived:
        shape = _SHAPE_BOTH
    elif flagged:
        shape = _SHAPE_ORIGINAL_FLAGGED
    elif with_derived:
        shape = _SHAPE_SEPARATE_ROW
    elif untruncated:
        shape = _SHAPE_NONE
    else:
        shape = _SHAPE_UNDETERMINED
    derived_forms = [
        row["orgn_odno_encoding"]
        for snapshot in with_derived
        for row in snapshot["derived_rows"]
    ]
    return {
        "shape": shape,
        "original_odno_key": original_key,
        "snapshots_total": len(snapshots),
        "snapshots_answered": len(answered),
        "snapshots_untruncated": len(untruncated),
        "snapshots_with_cncl_yn_Y": len(flagged),
        "snapshots_with_orgn_odno_row": len(with_derived),
        "first_flagged_t_offset_ms": flagged[0]["t_offset_ms"] if flagged else None,
        "first_derived_t_offset_ms": (
            with_derived[0]["t_offset_ms"] if with_derived else None
        ),
        "derived_row_orgn_odno_forms": derived_forms[:5],
        "profile_field_under_test": (
            "capabilities.replace_semantics._kis.replace_probe_2026_07_31"
            ".orgn_odno_wire_form — the draft records '추정 금지' because P-8 kept no "
            "query rows. derived_row_orgn_odno_forms is the first measurement of "
            "that field on a row a cancel produced; an empty list means no such row "
            "was observed in this window, not that none exists"
        ),
        "scope": (
            "one 모의투자 stock account, one symbol, one session. MOCK artifacts "
            "cannot be cited for 실전 (§6.2 / ADR-002-004 §13.14), and absence "
            "inside the window is not proof of non-existence (VP-002:756)"
        ),
    }


def classify_cancel_confirmed(
    snapshots: list[dict[str, Any]], original_key: str
) -> dict[str, Any]:
    """Did the original order stop working? Separate from the cancel SHAPE."""
    answered = [s for s in snapshots if s.get("read_status") in _READ_ANSWERED]
    rows_seen = 0
    for snapshot in answered:
        row = (snapshot.get("original_row") or {}).get("raw") or {}
        if not row:
            continue
        rows_seen += 1
        # The same read's own parent set, so «confirmed» here and «live» in `live_rows`
        # cannot disagree about a shortfall another row of that read explains (#948 리뷰 M1).
        parents = frozenset(snapshot.get("cancel_parent_odnos") or ())
        if not row_has_working_quantity(row, cancel_parents=parents):
            return {
                "confirmed": True,
                "original_odno_key": original_key,
                "at_t_offset_ms": snapshot["t_offset_ms"],
                "basis": _confirmation_basis(row),
                "row": row,
            }
    if not answered:
        reason = "no snapshot of the order surface answered"
    elif rows_seen == 0:
        reason = (
            "the original order's row never appeared on any answered snapshot, "
            "so whether it stopped working is unknown — CCLD_DVSN=00 should show "
            "it either way, which makes this an unanswered question"
        )
    else:
        reason = (
            "the original row kept a working remainder — rmn_qty > 0 that no 취소확인수량 "
            "(cncl_cfrm_qty) covers. cncl_yn=Y alone does NOT close it: the cancel is "
            "ACCEPTED, not the remainder withdrawn, and the row can still fill (#1158 리뷰)"
        )
    return {
        "confirmed": False,
        "original_odno_key": original_key,
        "snapshots_answered": len(answered),
        "snapshots_with_original_row": rows_seen,
        "reason": reason,
        "consequence": (
            "no further order is placed on this account by this run; the cleanup "
            "tries to cancel and the artifact records what it found"
        ),
    }


def classify_late_fill(
    *,
    filled_before_cancel: int | None,
    snapshots: list[dict[str, Any]],
    cancel_ack_rt_cd: str,
) -> dict[str, Any]:
    """Whether 총체결수량 grew AFTER the cancel was acknowledged."""
    series = [
        {
            "t_offset_ms": s["t_offset_ms"],
            "tot_ccld_qty": s.get("original_tot_ccld_qty"),
            "rmn_qty": s.get("original_rmn_qty"),
            "cncl_yn": s.get("original_cncl_yn"),
            "read_status": s.get("read_status"),
        }
        for s in snapshots
    ]
    observed = [p for p in series if isinstance(p["tot_ccld_qty"], int)]
    verdict = "NO_LATE_FILL_OBSERVED"
    grew_at: float | None = None
    peak: int | None = None
    if not observed:
        verdict = "UNDETERMINED_NO_FILL_QUANTITY_READ"
    else:
        peak = max(int(p["tot_ccld_qty"]) for p in observed)
        baseline = filled_before_cancel if filled_before_cancel is not None else 0
        for point in observed:
            if int(point["tot_ccld_qty"]) > baseline:
                grew_at = float(point["t_offset_ms"])
                verdict = "LATE_FILL_OBSERVED_AFTER_CANCEL_ACK"
                break
        if filled_before_cancel is None and verdict == "NO_LATE_FILL_OBSERVED":
            verdict = "UNDETERMINED_NO_PRE_CANCEL_BASELINE"
    return {
        "verdict": verdict,
        "cancel_ack_rt_cd": cancel_ack_rt_cd,
        "filled_qty_before_cancel": filled_before_cancel,
        "peak_filled_qty_after_cancel": peak,
        "first_growth_t_offset_ms": grew_at,
        "series": series,
        "measurement_gap_note": (
            "filled_qty_before_cancel was read one paced call before the cancel "
            "POST, so growth first seen afterwards may have occurred in that gap. "
            "The gap is limits.pace_s; t_offset_ms is measured from the cancel's "
            "own pacer release instant"
        ),
        "feeds": (
            "B_late_fill_observation (VP-002:725) as an OBSERVATION only — one "
            "session cannot set a hard maximum, and nothing here is a bound "
            "candidate"
        ),
    }


def _submit(
    client: MockTradingClient,
    run: ProbeRun,
    budget: OrderBudget,
    body: dict[str, str],
    *,
    side: str,
    label: str,
    max_quantity: int,
    from_reserve: bool = False,
) -> tuple[Placed | None, str, dict[str, Any]]:
    """One order POST. Returns ``(placed, stop_reason, record)``."""
    try:
        quantity = int(body["ORD_QTY"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ProbeError(f"order body has no readable ORD_QTY: {body!r}") from exc
    if quantity > max_quantity:
        raise SafetyViolation(
            f"refusing to send {label!r}: ORD_QTY={quantity} exceeds "
            f"limits.max_quantity={max_quantity}. Split it or raise the cap in "
            "the P-SC config and say why"
        )
    budget.spend(label, from_reserve=from_reserve)
    record: dict[str, Any] = {"label": label, "side": side, "body": dict(body)}
    try:
        placed, status, parsed, text, ms = client.submit_stock_verbose(body, side=side)
    except transport_transient_types() as exc:
        record |= {
            "outcome": _STOP_ORDER_STATE_UNKNOWN,
            "transport_excerpt": transport_excerpt(exc),
        }
        run.observe(submit=record)
        return None, _STOP_ORDER_STATE_UNKNOWN, record
    kind = classify_answer(status, parsed, text)
    record |= {
        "http_status": status,
        "rt_cd": rt_cd_of(parsed),
        "msg_cd": parsed.get("msg_cd"),
        "msg1": parsed.get("msg1"),
        "elapsed_ms": round(ms, 1),
        "output": parsed.get("output"),
    }
    if kind is not None:
        record |= {
            "outcome": _STOP_RATE_LIMITED,
            "evidence": call_evidence(
                status_kind=kind, http_status=status, parsed=parsed, text=text
            ),
        }
        run.observe(submit=record)
        return None, _STOP_RATE_LIMITED, record
    if placed is None:
        record |= {
            "outcome": _STOP_REJECTED,
            "evidence": call_evidence(
                status_kind=_STOP_REJECTED, http_status=status, parsed=parsed, text=text
            ),
        }
        run.observe(submit=record)
        return None, _STOP_REJECTED, record
    record |= {
        "outcome": _STOP_NONE,
        "odno_encoding": _odno_encoding(placed.odno),
        "krx_fwdg_ord_orgno": placed.krx_fwdg_ord_orgno,
    }
    run.observe(submit=record)
    return placed, _STOP_NONE, record


def _cancel(
    client: MockTradingClient,
    run: ProbeRun,
    budget: OrderBudget,
    placed: Placed,
    *,
    remaining_qty: int,
    label: str,
) -> tuple[str, dict[str, Any], float]:
    """One cancel POST. Returns ``(stop_reason, record, ack_monotonic)``."""
    record: dict[str, Any] = {"label": label, "remaining_qty_sent": remaining_qty}
    try:
        body_preview = client.stock_cancel_body(
            orgn_odno=placed.odno,
            krx_fwdg_ord_orgno=placed.krx_fwdg_ord_orgno,
            remaining_qty=remaining_qty,
        )
    except ProbeError as exc:
        record |= {
            "outcome": _STOP_CANCEL_NOT_SENDABLE,
            "not_sendable_because": str(exc),
            "orgn_odno": placed.odno,
            "krx_fwdg_ord_orgno": placed.krx_fwdg_ord_orgno,
        }
        run.observe(cancel=record)
        return _STOP_CANCEL_NOT_SENDABLE, record, time.monotonic()
    budget.spend(label)
    try:
        status, parsed, text, ms, body = client.cancel_stock_verbose(
            orgn_odno=placed.odno,
            krx_fwdg_ord_orgno=placed.krx_fwdg_ord_orgno,
            remaining_qty=remaining_qty,
        )
    except transport_transient_types() as exc:
        record |= {
            "outcome": _STOP_ORDER_STATE_UNKNOWN,
            "transport_excerpt": transport_excerpt(exc),
            "request_body": body_preview,
        }
        run.observe(cancel=record)
        return _STOP_ORDER_STATE_UNKNOWN, record, time.monotonic()
    ack_at = client.last_send_instant()
    kind = classify_answer(status, parsed, text)
    record |= {
        "request_body": body,
        "http_status": status,
        "rt_cd": rt_cd_of(parsed),
        "msg_cd": parsed.get("msg_cd"),
        "msg1": parsed.get("msg1"),
        "elapsed_ms": round(ms, 1),
        "output": parsed.get("output"),
    }
    if kind is not None:
        record |= {
            "outcome": _STOP_RATE_LIMITED,
            "evidence": call_evidence(
                status_kind=kind, http_status=status, parsed=parsed, text=text
            ),
        }
        run.observe(cancel=record)
        return _STOP_RATE_LIMITED, record, ack_at
    accepted = status == 200 and rt_cd_of(parsed) == "0"
    record["outcome"] = _STOP_NONE if accepted else _STOP_REJECTED
    if not accepted:
        record["evidence"] = call_evidence(
            status_kind=_STOP_REJECTED, http_status=status, parsed=parsed, text=text
        )
    run.observe(cancel=record)
    return record["outcome"], record, ack_at


def _observe_window(
    client: MockTradingClient,
    cfg: Config,
    *,
    symbol: str,
    original_key: str,
    t0: float,
) -> list[dict[str, Any]]:
    """Snapshot the order surface at t+0 and then until the window closes."""
    interval = max(cfg.observation.poll_interval_s, cfg.limits.pace_s)
    snapshots = [
        _snapshot(
            client,
            symbol,
            cfg,
            label="t+0",
            original_key=original_key,
            t0_monotonic=t0,
        )
    ]
    index = 1
    while time.monotonic() - t0 < cfg.observation.cancel_window_s:
        target = t0 + index * interval
        now = time.monotonic()
        if target > now:
            if target - t0 > cfg.observation.cancel_window_s:
                break
            time.sleep(target - now)
        snapshots.append(
            _snapshot(
                client,
                symbol,
                cfg,
                label=f"poll{index}",
                original_key=original_key,
                t0_monotonic=t0,
            )
        )
        index += 1
    return snapshots


_SIDE_BUY = "02"


def _own_filled_qty(
    client: MockTradingClient, symbol: str, cfg: Config, keys: set[str]
) -> dict[str, Any]:
    """How much THIS run's own BUY orders are recorded as having filled."""
    read = read_order_rows(client, symbol, cfg, walk=False)
    if read.get("status") not in _READ_ANSWERED:
        return {
            "readable": False,
            "qty": 0,
            "read_status": read.get("status"),
            "note": (
                "the execution inquiry did not answer, so how much this run "
                "bought is unknown and the sell-back is capped at 0"
            ),
        }
    total = 0
    rows = 0
    for row in read.get("rows") or []:
        try:
            key = odno_key(row.get("odno"))
        except ProbeError:
            continue
        if key not in keys:
            continue
        if str(row.get("sll_buy_dvsn_cd", "")).strip() != _SIDE_BUY:
            continue
        rows += 1
        total += _ccld_int(row, "tot_ccld_qty") or 0
    return {
        "readable": True,
        "qty": total,
        "own_rows_matched": rows,
        "read_status": read.get("status"),
    }


def _cleanup(
    client: MockTradingClient | None,
    run: ProbeRun,
    budget: OrderBudget,
    cfg: Config,
    *,
    symbol: str,
    placed: list[Placed],
) -> dict[str, Any]:
    """Cancel this run's own resting orders, sell back what they filled, verify flat."""
    record: dict[str, Any] = {"cancels": [], "sell_back": None}
    if client is None:
        return record | {
            "status": _CLEAN_NOTHING_TO_DO,
            "reason": "dry-run, nothing sent",
        }
    if not placed:
        return record | {
            "status": _CLEAN_NOTHING_TO_DO,
            "reason": (
                "this run placed no accepted order — a refusal before the first "
                "submit, so there is nothing of its own to cancel or sell back. "
                "Any holding or open row the account carries is NOT this run's "
                "and is left alone"
            ),
        }
    keys = {p.key for p in placed}
    by_key = {p.key: p for p in placed}
    try:
        for attempt in range(cfg.limits.cleanup.cancel_attempts):
            read = read_order_rows(client, symbol, cfg, walk=False)
            if read.get("status") not in _READ_ANSWERED:
                record["cancels"].append(
                    {"attempt": attempt, "skipped": read.get("status")}
                )
                time.sleep(cfg.limits.cleanup.retry_s)
                continue
            live = []
            for row in read.get("live_rows") or []:
                try:
                    if odno_key(row.get("odno")) in keys:
                        live.append(row)
                except ProbeError:
                    continue
            if not live:
                break
            for row in live:
                key = odno_key(row.get("odno"))
                remaining = _ccld_int(row, "rmn_qty") or 0
                if not budget.can_spend():
                    record["cancels"].append(
                        {
                            "attempt": attempt,
                            "odno_key": key,
                            "outcome": _CLEAN_BUDGET_SPENT,
                        }
                    )
                    continue
                outcome, _cancel_record, _ack = _cancel(
                    client,
                    run,
                    budget,
                    by_key[key],
                    remaining_qty=remaining,
                    label=f"cleanup-cancel-{key}-attempt{attempt}",
                )
                record["cancels"].append(
                    {"attempt": attempt, "odno_key": key, "outcome": outcome}
                )
                if outcome == _STOP_CANCEL_NOT_SENDABLE:
                    record["cancel_not_sendable"] = (
                        "this run's own order cannot be cancelled through this "
                        "harness at all — see trial_*.krx_fwdg_ord_orgno_absent. "
                        "Cancel it by hand"
                    )
            time.sleep(cfg.limits.cleanup.retry_s)
    except Exception as exc:  # noqa: BLE001 - phase 1 must not skip phases 2-4
        record["cancels_exception"] = f"{type(exc).__name__}: {exc}"

    own_filled: dict[str, Any] = {"readable": False, "qty": 0}
    holding: dict[str, Any] = {}
    try:
        own_filled = _own_filled_qty(client, symbol, cfg, keys)
        record["own_filled_qty"] = own_filled
        holding = read_holding(client, symbol, cfg)
        record["holding_after_cancels"] = holding
    except Exception as exc:  # noqa: BLE001 - phase 2 must not skip phases 3-4
        record["holding_read_exception"] = f"{type(exc).__name__}: {exc}"

    try:
        held = holding.get("qty")
        sell_qty = 0
        if holding.get("status") == _READ_OK and isinstance(held, int) and held > 0:
            sell_qty = min(held, own_filled["qty"] if own_filled["readable"] else 0)
        if sell_qty > 0:
            record["sell_back"] = _flatten(
                client, run, budget, cfg, symbol=symbol, qty=sell_qty
            )
            final = read_holding(client, symbol, cfg)
            record["holding_final"] = final
            if final.get("status") != _READ_OK:
                record["status"] = _CLEAN_UNKNOWN
            elif final.get("qty"):
                record["status"] = _CLEAN_STILL_HELD
            else:
                record["status"] = _CLEAN_FLAT
        elif holding.get("status") != _READ_OK:
            record["status"] = _CLEAN_UNKNOWN
        elif held:
            record["status"] = _CLEAN_STILL_HELD
            record["not_this_runs_holding"] = (
                f"{held} share(s) held and own_filled_qty={own_filled} — the "
                "sell-back is capped at what this run's own orders filled, so "
                "nothing was sold. Settle this by hand"
            )
        else:
            record["status"] = _CLEAN_FLAT
    except Exception as exc:  # noqa: BLE001 - phase 3 must not skip phase 4
        record["status"] = _CLEAN_UNKNOWN
        record["sell_back_exception"] = f"{type(exc).__name__}: {exc}"

    try:
        orders = read_order_rows(client, symbol, cfg, walk=False)
        own_live, other_live = 0, 0
        for row in orders.get("live_rows") or []:
            try:
                own_live += 1 if odno_key(row.get("odno")) in keys else 0
            except ProbeError:
                other_live += 1
                continue
            other_live += 0 if odno_key(row.get("odno")) in keys else 1
        record["orders_final_status"] = orders.get("status")
        record["orders_final_live"] = own_live + other_live
        record["orders_final_live_own"] = own_live
        record["orders_final_live_other"] = other_live
        if record["orders_final_live"]:
            record["status"] = _CLEAN_STILL_LIVE
        elif orders.get("status") not in _READ_ANSWERED:
            record["status"] = _CLEAN_UNKNOWN
    except Exception as exc:  # noqa: BLE001 - the last phase, same rule
        record["status"] = _CLEAN_UNKNOWN
        record["orders_final_exception"] = f"{type(exc).__name__}: {exc}"

    record.setdefault("status", _CLEAN_UNKNOWN)
    record["budget"] = budget.describe()
    return record


def _flatten(
    client: MockTradingClient,
    run: ProbeRun,
    budget: OrderBudget,
    cfg: Config,
    *,
    symbol: str,
    qty: int,
) -> dict[str, Any]:
    """Sell ``qty`` back in orders of at most ``limits.max_quantity`` each."""
    chunks: list[dict[str, Any]] = []
    remaining = qty
    while remaining > 0:
        chunk = min(remaining, cfg.limits.max_quantity)
        if not budget.can_spend(from_reserve=True):
            chunks.append({"qty": chunk, "outcome": _CLEAN_BUDGET_SPENT})
            break
        body = client.stock_order_body(symbol, chunk, order_type="market")
        _sold, outcome, submit_record = _submit(
            client,
            run,
            budget,
            body,
            side="SELL",
            label=f"flatten-sell-{chunk}",
            max_quantity=cfg.limits.max_quantity,
            from_reserve=True,
        )
        chunks.append({"qty": chunk, "outcome": outcome, "submit": submit_record})
        if outcome != _STOP_NONE:
            break
        remaining -= chunk
    bad = [c for c in chunks if c["outcome"] != _STOP_NONE]
    return {
        "qty": qty,
        "outcome": bad[0]["outcome"] if bad else _STOP_NONE,
        "max_quantity": cfg.limits.max_quantity,
        "orders": len(chunks),
        "chunks": chunks,
        "quantity_unsold": remaining,
    }


def _buy_price(
    client: MockTradingClient, symbol: str, offset_pct: float, *, marketable: bool
) -> tuple[TickPrice, float, Tick]:
    """A tick-valid BUY limit ``offset_pct`` away from the touch, from a quote."""
    last, tick = client.stock_quote(symbol)
    sign = 1.0 if marketable else -1.0
    raw = last * (1.0 + sign * offset_pct / 100.0)
    if raw <= 0:
        raise ProbeError(
            f"a BUY {offset_pct}% from {last} is not a positive price for {symbol}"
        )
    return snap_to_tick(raw, tick, side="BUY", marketable=marketable), last, tick


def _trial(
    client: MockTradingClient,
    run: ProbeRun,
    budget: OrderBudget,
    cfg: Config,
    *,
    symbol: str,
    name: str,
    trial: TrialLimits,
    marketable: bool,
    placed_out: list[Placed],
) -> tuple[str, dict[str, Any]]:
    """One submit → observe → cancel → observe cycle. Returns ``(stop, record)``."""
    price, last, _tick = _buy_price(
        client, symbol, trial.price_offset_pct, marketable=marketable
    )
    record: dict[str, Any] = {
        "trial": name,
        "quantity": trial.quantity,
        "marketable": marketable,
        "last_price": last,
        "limit_price_tick": price.describe(),
    }
    body = client.stock_order_body(symbol, trial.quantity, price, order_type="limit")
    placed, stop, submit_record = _submit(
        client,
        run,
        budget,
        body,
        side="BUY",
        label=f"{name}-submit",
        max_quantity=cfg.limits.max_quantity,
    )
    if placed is None or stop != _STOP_NONE:
        return stop, record | {"stopped_at": "submit"}
    placed_out.append(placed)
    record["odno"] = placed.odno
    record["odno_key"] = placed.key
    record["krx_fwdg_ord_orgno"] = placed.krx_fwdg_ord_orgno

    if not placed.krx_fwdg_ord_orgno:
        record["krx_fwdg_ord_orgno_absent"] = (
            "the accept response carried no KRX_FWDG_ORD_ORGNO (거래소코드), which "
            "order_rvsecncl ([v1_국내주식-003]) declares [필수] and refuses as "
            "empty. No cancel can be BUILT for this order, so none is sent and "
            "no further order is placed. The order is resting and the cleanup "
            "records what it could and could not do — settle it by hand"
        )
        record["accept_output"] = submit_record.get("output")
        return _STOP_CANCEL_NOT_SENDABLE, record | {"stopped_at": "cancel_not_sendable"}

    pre = _snapshot(
        client,
        symbol,
        cfg,
        label="pre-cancel",
        original_key=placed.key,
        t0_monotonic=placed.sent_at_monotonic,
    )
    record["pre_cancel"] = pre
    filled_before = pre.get("original_tot_ccld_qty")
    remaining = pre.get("original_rmn_qty")
    if pre.get("read_status") not in _READ_ANSWERED:
        remaining = trial.quantity
    elif pre.get("original_row") is None:
        remaining = trial.quantity
        record["pre_cancel_row_absent"] = (
            "the accepted order was not on the returned page. CCLD_DVSN=00 should "
            "show it whether or not it filled, so this is an unanswered question "
            "and not evidence of anything; the cancel is sent for the full quantity"
        )
    elif not isinstance(remaining, int) or remaining <= 0:
        remaining = trial.quantity

    if marketable:
        record["partial_fill"] = _classify_partial(
            filled_before, trial.quantity, pre.get("read_status")
        )

    stop, cancel_record, ack_at = _cancel(
        client, run, budget, placed, remaining_qty=remaining, label=f"{name}-cancel"
    )
    record["cancel"] = cancel_record
    if stop != _STOP_NONE:
        return stop, record | {"stopped_at": "cancel"}

    snapshots = _observe_window(
        client, cfg, symbol=symbol, original_key=placed.key, t0=ack_at
    )
    record["post_cancel_snapshots"] = snapshots
    record["cancel_shape"] = classify_cancel_shape(snapshots, placed.key)
    record["cancel_confirmed"] = classify_cancel_confirmed(snapshots, placed.key)
    record["late_fill"] = classify_late_fill(
        filled_before_cancel=filled_before,
        snapshots=snapshots,
        cancel_ack_rt_cd=str(cancel_record.get("rt_cd", "")),
    )
    if record["cancel_shape"]["snapshots_answered"] == 0:
        return _STOP_QUERY_UNANSWERED, record | {"stopped_at": "observation"}
    if not record["cancel_confirmed"]["confirmed"]:
        return _STOP_CANCEL_NOT_CONFIRMED, record | {"stopped_at": "confirmation"}
    return _STOP_NONE, record


def _classify_partial(
    filled: int | None, ordered: int, read_status: str | None
) -> dict[str, Any]:
    """Name the trial-B outcome. "Not producible" is a finding, not a failure."""
    if read_status not in _READ_ANSWERED or filled is None:
        outcome = _PARTIAL_UNDETERMINED
    elif filled == 0:
        outcome = _PARTIAL_NO_FILL
    elif filled >= ordered:
        outcome = _PARTIAL_FILLED_FULLY
    else:
        outcome = _PARTIAL_OBSERVED
    return {
        "outcome": outcome,
        "ordered_qty": ordered,
        "filled_qty_before_cancel": filled,
        "read_status": read_status,
        "note": (
            "P-11 measured that a 모의 marketable LIMIT did not fill at all "
            "(P-11-20260730T002715Z) while a 시장가 order filled fully at once "
            f"(P-11-20260731T015709Z), so {_PARTIAL_NO_FILL} is the expected "
            "outcome here. #980 needs the PARTIAL shape; if it is not producible "
            "on mock, that is what this records"
        ),
    }


def _print_lines(stop: str, shape: str, flat: str) -> None:
    """The three anchored lines the runner template reads. Exactly one of each."""
    print(f"{_STOP_PREFIX}{stop}")
    print(f"{_SHAPE_PREFIX}{shape}")
    print(f"{_FLAT_PREFIX}{flat}")


def _flat_token(cleanup: dict[str, Any]) -> str:
    status = cleanup.get("status")
    if status == _CLEAN_FLAT:
        return "yes"
    if status in (_CLEAN_STILL_HELD, _CLEAN_STILL_LIVE):
        return "no"
    return "unknown"


def _why_skip_b(cfg: Config, selector: str, stop: str) -> str | None:
    """Why trial B must not run, or ``None`` when it may. One reader, three reasons."""
    if not cfg.trial_b.enabled:
        return "trials.b.enabled is false in the P-SC config"
    if selector not in ("both", "b"):
        return f"--trial {selector}"
    if stop != _STOP_NONE:
        return (
            f"trial A stopped with {stop}; placing another order on top of that "
            "state is the one thing this probe must not do"
        )
    return None


def _dry_run(run: ProbeRun, args: argparse.Namespace, cfg: Config) -> None:
    """Print the bodies that WOULD be sent, with no credentials and no socket."""
    cano, acnt = "<CANO>", "<PRDT>"
    run.observe(
        dry_run_order_body={
            "note": (
                "ORD_UNPR is filled at run time from the quote GET and the "
                "broker-reported 호가단위; there is no literal price anywhere"
            ),
            "symbol": args.symbol,
            "trial_a_quantity": cfg.trial_a.quantity,
            "trial_b_quantity": cfg.trial_b.quantity if cfg.trial_b.enabled else None,
        },
        dry_run_cancel_body=build_stock_cancel_body(
            cano,
            acnt,
            orgn_odno="<ODNO from the accept response>",
            krx_fwdg_ord_orgno="<KRX_FWDG_ORD_ORGNO from the accept response>",
            remaining_qty=cfg.trial_a.quantity,
        ),
    )
    _print_lines(_STOP_DRY_RUN, _SHAPE_UNDETERMINED, "unknown")


def probe_psc(args: argparse.Namespace) -> ProbeRun:
    """P-SC — 주식 MOCK 취소 행 모양 + 늦은 체결 관측 (#948 순서 1)."""
    spec = get("P-SC")
    if args.asset != "stock":
        raise ProbeError(
            f"P-SC is a STOCK probe (got --asset {args.asset!r}). The surfaces it "
            "reads — VTTC0081R, VTTC8434R — and the TR it cancels through "
            "(VTTC0013U) are all 국내주식"
        )
    if not str(args.symbol or "").strip():
        raise ProbeError("P-SC needs --symbol (e.g. 005930); there is no default")

    cfg = load_config(getattr(args, "config", None))
    env_record = assert_mock_only_env()
    args.pace_s = cfg.limits.pace_s
    session_record = assert_session_window(cfg, _now()) if args.confirm else None

    run, client = _setup(spec, args)
    run.measure("config", cfg.describe())
    run.measure("mock_only_env_gate", env_record)
    if session_record is not None:
        run.measure("session_gate", session_record)
    else:
        run.skip(
            "session/day gate",
            "dry-run: the window and trading-day refusal gate the LIVE run only, "
            "and a dry run must stay runnable at any hour",
        )
    budget = OrderBudget(
        cfg.limits.max_order_calls, reserved_for_flatten=cfg.flatten_reserve
    )

    if client is None:
        _dry_run(run, args, cfg)
        return run

    run.measure(
        "account", {"fingerprint": account_fingerprint(client.creds.account_no)}
    )
    placed: list[Placed] = []
    stop = _STOP_NONE
    shapes: list[str] = []
    cleanup: dict[str, Any] = {}
    abortable: tuple[type[BaseException], ...] = (
        ProbeError,
        *transport_transient_types(),
    )
    try:
        run.measure("flat_start", assert_flat_start(client, args.symbol, cfg))
        if args.trial in ("both", "a"):
            stop, record_a = _trial(
                client,
                run,
                budget,
                cfg,
                symbol=args.symbol,
                name="trial_a",
                trial=cfg.trial_a,
                marketable=False,
                placed_out=placed,
            )
            run.measure("trial_a", record_a)
            if "cancel_shape" in record_a:
                shapes.append(record_a["cancel_shape"]["shape"])
        else:
            run.skip("trial A", f"--trial {args.trial}")

        skip_b = _why_skip_b(cfg, args.trial, stop)
        if skip_b is None:
            stop, record_b = _trial(
                client,
                run,
                budget,
                cfg,
                symbol=args.symbol,
                name="trial_b",
                trial=cfg.trial_b,
                marketable=True,
                placed_out=placed,
            )
            run.measure("trial_b", record_b)
            if "cancel_shape" in record_b:
                shapes.append(record_b["cancel_shape"]["shape"])
        else:
            run.skip("trial B", skip_b)
    except SafetyViolation:
        raise
    except abortable as exc:
        if not placed:
            raise
        stop = _STOP_PROBE_ERROR
        run.error(f"{type(exc).__name__} after {len(placed)} accepted order(s): {exc}")
        run.measure(
            "aborted_after_first_order",
            {
                "exception": f"{type(exc).__name__}: {exc}",
                "accepted_orders": len(placed),
                "note": (
                    "trials ended here. Whatever measurement had completed is "
                    "above; the cleanup below says what state the account is in"
                ),
            },
        )
    finally:
        cleanup = _cleanup(client, run, budget, cfg, symbol=args.symbol, placed=placed)
        run.measure("cleanup", cleanup)
        run.measure("order_call_budget", budget.describe())
        shape = shapes[0] if shapes else _SHAPE_UNDETERMINED
        if len(set(shapes)) > 1:
            run.measure(
                "cancel_shape_disagreement",
                {
                    "shapes": shapes,
                    "note": (
                        "the two trials saw different cancel shapes; the anchored "
                        "line carries trial A's and the per-trial records carry both"
                    ),
                },
            )
        _print_lines(stop, shape, _flat_token(cleanup))
        client.close()
    return run


def add_stock_cancel_args(parser: argparse.ArgumentParser) -> None:
    """P-SC's own flags. Every LIMIT lives in the YAML config, not here."""
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to the P-SC limits (default: "
            f"{DEFAULT_CONFIG_PATH.relative_to(_REPO_ROOT)}). Pacing, the order-call "
            "budget, the quantity cap, the session window and the observation "
            "length all come from there and have NO code defaults."
        ),
    )
    parser.add_argument(
        "--trial",
        choices=("both", "a", "b"),
        default="both",
        help=(
            "Which trials to run. 'a' is the resting-order cancel, 'b' the "
            "partial-fill attempt. Trial B also needs trials.b.enabled in the "
            "config; this flag can only narrow, never widen."
        ),
    )
