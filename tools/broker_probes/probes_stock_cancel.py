"""P-SC — 주식 MOCK 취소 행 모양과 늦은 체결 관측 (#948 순서 1, #980).

What is unmeasured, and why it blocks
-------------------------------------
#939 (PR-3b) left the stock cancel path fail-closed: the fill observer records
``FILL_OBSERVER_CANCEL_UNSUPPORTED`` once and leaves the reservation standing,
because nobody knows what a cancel LOOKS LIKE on the query surface. The broker
profile says so in as many words — ``capabilities.replace_semantics._kis
.replace_probe_2026_07_31.orgn_odno_wire_form.reading``:

    ⚠ 정정으로 생성된 행에서 이 필드가 실제로 원주문 ODNO 를 담는지는
    **확인하지 않았다** (P-8 은 조회 행을 아티팩트에 남기지 않았다) — 추정 금지.

Until that is measured, #948 step 2 (the observer's cancel classification and
the reconciler's non-execution MATCHED condition) and #980 (a cancelled
remainder after a partial entry fill) cannot be built without guessing. This
probe measures it and nothing else: it writes no capability value and proposes
no bound.

What it establishes
-------------------
Per trial, from the 주식일별주문체결조회 rows (``VTTC0081R``) read verbatim
before the cancel and repeatedly after it:

* **cancel_shape** — one of :data:`_SHAPE_ORIGINAL_FLAGGED`,
  :data:`_SHAPE_SEPARATE_ROW`, :data:`_SHAPE_BOTH`, :data:`_SHAPE_NONE` or
  :data:`_SHAPE_UNDETERMINED`. The last two are distinct: "the surface answered
  and showed neither" is an observation, "the surface did not answer" is not.
* **orgn_odno_wire_form** on a row the cancel produced, if any — the field the
  profile says is unverified.
* **late_fill_after_cancel_ack** — whether 총체결수량 grew after the cancel was
  acknowledged, over :attr:`Observation.cancel_window_s`. A window that shows
  none records that it saw none, never that none can happen.

What it does NOT establish
--------------------------
One 모의투자 account, one symbol, one session. Mock is not 실전
(§6.2 / ADR-002-004 §13.14), and an absence inside a 60 s window is not proof
of non-existence (VP-002:756, the same rule ``B_broker_query_consistency``
already carries).

Safety model
------------
Mock-only in CODE, not in a runner: every call goes through
``MockTradingClient``, whose single transport asserts
:func:`~tools.broker_probes.common.assert_mock_host` and whose trading calls
assert :func:`~tools.broker_probes.common.assert_mock_trading_tr`. On top of
that this module refuses before the first socket when the environment names a
REAL market (:func:`assert_mock_only_env`), when the account is not flat
(:func:`assert_flat_start`), when the clock is outside the configured KRX
window or the day is not a trading day (:func:`assert_session_window`), and
when the order-call budget is spent (:class:`OrderBudget`). The cleanup runs on
every exit path and records its own outcome.

Every limit — pacing, order budget, quantity cap, window, observation length —
comes from :data:`DEFAULT_CONFIG_PATH` with **no defaults**; a missing key is a
refusal.
"""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from datetime import time as clock_time
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

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Where the limits live. See the file's own header for why they are YAML.
DEFAULT_CONFIG_PATH = (
    _REPO_ROOT / "config" / "broker_probes" / "stock_cancel_probe.yaml"
)

#: Handshake with the tracked runner template ``runners/run_p_sc.sh``, read the
#: same way ``probes_order.POLICY_VERSION`` is: the runner imports this module
#: and compares, so a runner copied out of another tree aborts with a reason
#: instead of mis-reading an older probe's output.
#:
#: ``/1`` is the first contract: P-SC prints the anchored :data:`_STOP_PREFIX`,
#: :data:`_SHAPE_PREFIX` and :data:`_FLAT_PREFIX` lines on every path it can
#: leave by, and classifies a lost order POST as
#: :data:`_STOP_ORDER_STATE_UNKNOWN` rather than letting the exception escape.
POLICY_VERSION = "p-sc-cancel-shape/1"

#: The config schema this module reads. A file declaring anything else is
#: refused rather than partially understood.
SCHEMA_VERSION = 1

# --- anchored output lines the runner parses --------------------------------
_STOP_PREFIX = "PSC_STOP="
_SHAPE_PREFIX = "PSC_CANCEL_SHAPE="
_FLAT_PREFIX = "PSC_FLAT_AT_END="

_STOP_NONE = "none"
_STOP_DRY_RUN = "dry_run"
_STOP_REJECTED = "rejected"
_STOP_RATE_LIMITED = "rate_limited"
_STOP_ORDER_STATE_UNKNOWN = "order_state_unknown"
_STOP_QUERY_UNANSWERED = "query_unanswered"

# --- the thing being measured ----------------------------------------------
#: The cancel appeared as a flag on the ORIGINAL row (``cncl_yn='Y'``), and no
#: separate row pointed at it through ``orgn_odno``.
_SHAPE_ORIGINAL_FLAGGED = "ORIGINAL_ROW_FLAGGED"
#: A SEPARATE row appeared whose ``orgn_odno`` canonicalises to the original
#: order's number, and the original row itself was not flagged.
_SHAPE_SEPARATE_ROW = "SEPARATE_ROW_WITH_ORGN_ODNO"
#: Both of the above.
_SHAPE_BOTH = "BOTH"
#: The surface ANSWERED (``rt_cd=0``) throughout and showed neither.
_SHAPE_NONE = "NEITHER_OBSERVED"
#: The surface never answered, or answered only before the cancel. Not the same
#: as :data:`_SHAPE_NONE`, and the difference is the whole point: #948 cannot be
#: built on "we did not see it" read as "it does not happen".
_SHAPE_UNDETERMINED = "UNDETERMINED"

#: How a flat-account or open-order read ended. The two unhealthy ones are the
#: shared constants, not re-spellings: ``classify_answer`` returns those exact
#: strings, and a second spelling here is a second place to get the precedence
#: wrong (the #825 F4 defect).
_READ_OK = "OK"
_READ_REFUSED = "REFUSED"
_READ_RATE_LIMITED = STATUS_RATE_LIMITED
_READ_TRANSIENT = STATUS_TRANSIENT
_READ_CAPPED = "PAGE_CAP"
_READ_TRUNCATED = "PAGE_ROW_CAP"

#: Read statuses a caller may draw a conclusion FROM. Anything else means the
#: surface did not answer, and absence on it establishes nothing.
_READ_ANSWERED = (_READ_OK, _READ_TRUNCATED)

#: How the trial-B partial-fill attempt turned out. "Not producible on mock" is
#: a finding, so each way of not producing one is named rather than collapsed.
_PARTIAL_OBSERVED = "PARTIAL_FILL_OBSERVED"
_PARTIAL_FILLED_FULLY = "NOT_PRODUCIBLE__FILLED_FULLY"
_PARTIAL_NO_FILL = "NOT_PRODUCIBLE__NO_FILL"
_PARTIAL_UNDETERMINED = "NOT_PRODUCIBLE__FILL_UNDETERMINED"

#: How the cleanup ended. Mirrors ``probes_order``'s cleanup vocabulary.
_CLEAN_FLAT = "FLAT"
_CLEAN_NOTHING_TO_DO = "ALREADY_FLAT_NOTHING_TO_DO"
_CLEAN_STILL_LIVE = "ORDER_STILL_LIVE"
_CLEAN_STILL_HELD = "SHARES_STILL_HELD"
_CLEAN_UNKNOWN = "UNDETERMINED"
_CLEAN_BUDGET_SPENT = "REFUSED_ORDER_BUDGET_SPENT"

#: Env vars that name a REAL market. Values read by the runtime at
#: ``services/market_ingest/main.py:782`` and ``services/screener.py:931``
#: (``KIS_STOCK_MARKET``) and ``.env.example:332`` (``KIS_REAL_TRADING``). The
#: paper stack really does run ``KIS_STOCK_MARKET=real`` for stock quotes, so a
#: probe that inherited the paper ``.env`` instead of ``.env.mock`` would be
#: holding a REAL app key — which is what this refuses.
_REAL_MARKET_ENV = ("KIS_STOCK_MARKET", "KIS_FUTURES_MARKET")
_REAL_TRADING_ENV = "KIS_REAL_TRADING"
_TRUTHY = {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Config — every limit, no defaults
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionLimits:
    """When the probe may run at all."""

    calendar_path: Path
    covered_years: tuple[int, ...]
    start: clock_time
    end: clock_time


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
    """``path`` relative to the repo root when it is inside it, else as given.

    Relative when possible so an artifact is comparable across checkouts (the
    repo lives at a different absolute path in every detached worktree), and
    absolute otherwise rather than raising: ``--config`` and a calendar path
    may legitimately point outside the tree, and an artifact must not fail to
    be WRITTEN because of how a path was spelled.
    """
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

    def describe(self) -> dict[str, Any]:
        """The effective limits, for the artifact.

        Recorded in full rather than by path: an artifact read a year from now
        has to say what the run was ALLOWED to do, and the file may have moved
        on. ``config_path`` is relative to the repo root so it is comparable
        across checkouts.
        """
        return {
            "config_path": _repo_relative(self.path),
            "schema_version": SCHEMA_VERSION,
            "session": {
                "calendar_path": _repo_relative(self.session.calendar_path),
                "covered_years": list(self.session.covered_years),
                "window_kst": f"{self.session.start:%H:%M}-{self.session.end:%H:%M}",
            },
            "limits": {
                "pace_s": self.limits.pace_s,
                "pace_s_floor": self.limits.pace_s_floor,
                "max_order_calls": self.limits.max_order_calls,
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
    """One key of a config mapping, or a refusal naming the path.

    There is no ``default``: this config carries limits, and a limit that
    silently falls back is the shape the runner templates refuse by design
    ("a template ships no instance defaults", ``runners/_common.sh``).
    """
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
    """Read and validate the P-SC limits.

    Raises:
        ProbeError: the file is missing or unreadable, declares another
            ``schema_version``, omits any key, or carries a value this module
            refuses — a window that does not advance, a pace below its own
            declared floor, a trial quantity above the cap.
    """
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
    years_raw = _require(session_block, "covered_years", "session")
    if not isinstance(years_raw, list) or not years_raw:
        raise ProbeError("session.covered_years must be a non-empty list of years")
    covered_years = tuple(int(y) for y in years_raw)
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

    return Config(
        path=target,
        session=SessionLimits(
            calendar_path=calendar_path,
            covered_years=covered_years,
            start=start,
            end=end,
        ),
        limits=limits,
        observation=observation,
        flat_check=flat_check,
        trial_a=trial_a,
        trial_b=trial_b,
    )


# ---------------------------------------------------------------------------
# Gates that run before the first socket
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """The run clock, KST. A function so tests can replace it.

    There is deliberately no CLI override: a flag that moved this clock would
    be a documented way past :func:`assert_session_window`.
    """
    return datetime.now(KST)


def assert_mock_only_env() -> dict[str, Any]:
    """Refuse when the environment names a REAL market or arms real trading.

    The host and TR seals (``assert_mock_host`` / ``assert_mock_trading_tr``)
    already make a REAL *endpoint* unreachable through this harness. They do
    not look at the CREDENTIAL: a REAL app key pointed at the mock host is a
    real credential on the wire, and this repo's paper stack genuinely exports
    ``KIS_STOCK_MARKET=real`` for stock quotes (memory ``stock-needs-real-kis-
    key``), so sourcing the paper ``.env`` instead of ``.env.mock`` is a live
    mistake rather than a hypothetical one.

    Returns:
        What was seen, for the artifact — names and values only, never a key.

    Raises:
        SafetyViolation: any ``*_MARKET`` var is set to something other than
            ``mock``, or ``KIS_REAL_TRADING`` is truthy.
    """
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
    """The closed days the configured calendar declares.

    Read through ``tools/tos_cp3/session_day`` rather than parsed here: that
    module is the legacy side's single reader of this key, and it refuses a
    ``datetime`` entry that would never compare equal to the date asked about
    (review-1003 MEDIUM). A second parser would be a second chance to get that
    wrong.
    """
    from tools.tos_cp3 import session_day as sd

    data = yaml.safe_load(cfg.session.calendar_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProbeError(f"{cfg.session.calendar_path}: top level is not a mapping")
    try:
        return sd.holidays_of(data)
    except sd.SessionDayError as exc:
        raise ProbeError(f"{cfg.session.calendar_path}: {exc}") from exc


def assert_session_window(cfg: Config, now: datetime) -> dict[str, Any]:
    """Refuse outside the configured KRX window, and on a non-trading day.

    Returns:
        The gate's record, for the artifact.

    Raises:
        ProbeError: ``now`` is outside the years the holiday set declares it
            covers, falls on a weekend or a declared holiday, or sits outside
            ``session.window``.
    """
    from tools.tos_cp3 import session_day as sd

    kst = now.astimezone(KST)
    holidays = _holidays(cfg)
    try:
        sd.assert_covers(
            kst.date(),
            covered_years=cfg.session.covered_years,
            where=cfg.session.calendar_path,
        )
    except sd.SessionDayError as exc:
        raise ProbeError(str(exc)) from exc
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
    return {
        "now_kst": kst.isoformat(),
        "trading_day": True,
        "window_kst": f"{cfg.session.start:%H:%M}-{cfg.session.end:%H:%M}",
        "calendar": _repo_relative(cfg.session.calendar_path),
        "holidays_declared": len(holidays),
    }


class OrderBudget:
    """A hard cap on order-emitting POSTs for one run.

    Not a courtesy counter: :meth:`spend` raises
    :class:`~tools.broker_probes.common.SafetyViolation`, which ``run.py``
    neither catches nor writes an artifact for. The budget exists because every
    other limit here bounds ONE call (a price, a quantity, an interval) and
    none of them bounds how many times a loop may send one.
    """

    def __init__(self, limit: int) -> None:
        self.limit = int(limit)
        self.spent: list[str] = []

    @property
    def remaining(self) -> int:
        return self.limit - len(self.spent)

    def spend(self, what: str) -> None:
        if self.remaining <= 0:
            raise SafetyViolation(
                f"order-call budget exhausted ({self.limit} calls: "
                f"{', '.join(self.spent)}) — refusing to send {what!r}. Raise "
                "limits.max_order_calls in the P-SC config if the plan really "
                "needs more, and say why"
            )
        self.spent.append(what)

    def describe(self) -> dict[str, Any]:
        return {"limit": self.limit, "used": len(self.spent), "calls": list(self.spent)}


# ---------------------------------------------------------------------------
# Reading the two account surfaces
# ---------------------------------------------------------------------------


_VerboseGet = Callable[..., tuple[int, dict[str, Any], str, float]]


def _classified(
    call: _VerboseGet, /, *args: Any, **kwargs: Any
) -> tuple[str | None, int, dict[str, Any], str]:
    """Run one verbose GET and fold transport failures into the shared classification.

    ``kind`` is ``None`` when an intact answer arrived and the caller must read
    ``rt_cd``; otherwise it is the status the no-retry policy reads
    (:func:`~tools.broker_probes.common.classify_answer`) — which is why the
    ``call`` has to be a *verbose* client method: ``is_rate_limited`` needs the
    HTTP status and the raw body, and a parsed dict alone hides a 429.

    The callable is passed with its keyword arguments rather than wrapped in a
    lambda so a page-walk loop cannot close over a cursor variable it is about
    to reassign.
    """
    try:
        status, parsed, text, _ms = call(*args, **kwargs)
    except transport_transient_types() as exc:
        # No answer, so no body and no HTTP status: 0 is the "no call completed"
        # marker. The excerpt carries the exception class only — requests
        # renders the failed URL in full, and that URL carries CANO.
        return _READ_TRANSIENT, 0, {}, transport_excerpt(exc)
    return classify_answer(status, parsed, text), status, parsed, text


def _unhealthy_status(kind: str) -> str:
    """Map a ``classify_answer`` kind onto this module's read vocabulary.

    ``startswith`` on :data:`~tools.broker_probes.common.STATUS_TRANSIENT`
    rather than an equality test, because the transient kinds are prefixed
    (``TRANSIENT:ledger_throttle``) and a reader that enumerated them would
    silently misclassify a kind added later.
    """
    return _READ_TRANSIENT if kind.startswith(STATUS_TRANSIENT) else _READ_RATE_LIMITED


def read_holding(client: MockTradingClient, symbol: str, cfg: Config) -> dict[str, Any]:
    """Walk the balance until ``symbol``'s row is found or the broker ends the set.

    The walk, rather than one page, for the reason ``probes_ca._read_balance``
    walks: a single page cannot tell "not held" from "held on page 2", and the
    2026-09-30 P-CA attempt logged ``held qty=0`` for a query that had in fact
    errored. A capped or refused walk returns a status that is NOT ``OK`` and
    never a quantity, so a caller cannot read it as "flat".
    """
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
            # Broker end-of-set and the symbol was on no page walked: genuinely
            # absent, not truncated.
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


def _row_is_live(row: dict[str, Any]) -> bool:
    """A row that still has quantity working on the book.

    ``rmn_qty > 0`` AND not flagged cancelled. Both halves are needed and
    neither is sufficient: #948's whole question is whether a cancel shows up
    as the flag or as a separate row, so a reader that trusted only one of them
    would be assuming the answer.
    """
    remaining = _ccld_int(row, "rmn_qty")
    cancelled = str(row.get("cncl_yn", "")).strip().upper() == "Y"
    return remaining is not None and remaining > 0 and not cancelled


def read_order_rows(
    client: MockTradingClient, symbol: str, cfg: Config, *, walk: bool
) -> dict[str, Any]:
    """One (or every) page of 주식일별주문체결조회 for ``symbol``, rows verbatim.

    Args:
        walk: Walk the continuation keys. ``True`` for the flat-start check,
            where "no order is open" has to be established or refused. ``False``
            for the observation snapshots, which read ONE page in 역순 (newest
            first) — a seconds-old order is on it, and spending a paced call per
            extra page would stretch every snapshot past its poll interval.

    Returns:
        ``status``, the verbatim ``rows``, the derived ``live_rows``, and
        ``rows_returned`` per page. A single-page read whose row count reaches
        ``flat_check.ccld_page_row_cap`` is :data:`_READ_TRUNCATED`: the page
        was full, so absence on it establishes nothing.
    """
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
                "live_rows": [r for r in rows if _row_is_live(r)],
                "continuation_pending": bool(next_fk or next_nk),
            }
        if not next_fk and not next_nk:
            return record | {
                "status": _READ_OK,
                "rows": rows,
                "rows_returned": page_counts,
                "live_rows": [r for r in rows if _row_is_live(r)],
            }
        fk, nk = next_fk, next_nk
    return record | {
        "status": _READ_CAPPED,
        "rows": rows,
        "rows_returned": page_counts,
        "live_rows": [r for r in rows if _row_is_live(r)],
        "page_cap": pages,
        "note": (
            "the walk hit the page cap before the broker ended the set, so "
            "'no order is open' is UNDETERMINED"
        ),
    }


def assert_flat_start(
    client: MockTradingClient, symbol: str, cfg: Config
) -> dict[str, Any]:
    """Refuse unless the account provably holds none of ``symbol`` and has no open order.

    "Provably" is the operative word, and it is why a capped walk, a refusal, a
    throttle and a truncated page are all refusals here rather than passes. A
    probe that assumed flat because a read failed would cancel an order it did
    not place, or sell shares the operator was holding.

    Raises:
        ProbeError: either surface says not-flat, or could not say.
    """
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


# ---------------------------------------------------------------------------
# The measurement itself
# ---------------------------------------------------------------------------


def _row_view(row: dict[str, Any]) -> dict[str, Any]:
    """One query row, verbatim, plus the two identifier encodings.

    Verbatim because #948 asks for the row shape and a filtered copy would
    answer a question nobody asked. The two ``*_encoding`` entries are derived,
    not substituted: the raw ``odno``/``orgn_odno`` strings stay in ``raw``.
    """
    return {
        "raw": dict(row),
        "odno_encoding": _odno_encoding(str(row.get("odno", ""))),
        "orgn_odno_encoding": _odno_encoding(str(row.get("orgn_odno", ""))),
        "live": _row_is_live(row),
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
    """One read of the order surface, classified against the original ODNO.

    ``original_row`` is the row whose own ``odno`` IS the submitted order;
    ``derived_rows`` are rows whose ``orgn_odno`` points at it. Both sides go
    through :func:`~tools.broker_probes.probes_order.odno_key`, because the
    accept response and the query row disagree on padding and a raw compare
    evaluates ``'762' == '0000000762'`` — the defect that censored P-5.
    """
    read = read_order_rows(client, symbol, cfg, walk=False)
    rows = read.get("rows") or []
    original: dict[str, Any] | None = None
    derived: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for row in rows:
        try:
            own = odno_key(row.get("odno"))
            parent = odno_key(row.get("orgn_odno"))
        except ProbeError as exc:
            # A row this harness cannot read as an order number IS the
            # observation worth keeping; it must not destroy the snapshot.
            unreadable.append(_row_view(row) | {"odno_key_error": str(exc)})
            continue
        if own == original_key:
            if original is None:
                original = _row_view(row)
            else:
                derived.append(_row_view(row) | {"duplicate_of_original_odno": True})
        elif parent == original_key:
            derived.append(_row_view(row))
    snapshot = {
        "label": label,
        "t_offset_ms": round((time.monotonic() - t0_monotonic) * 1000.0, 1),
        "read_status": read.get("status"),
        "rows_returned": read.get("rows_returned"),
        "continuation_pending": read.get("continuation_pending"),
        "rows": [_row_view(r) for r in rows],
        "original_row": original,
        "derived_rows": derived,
        "unreadable_rows": unreadable,
        "original_cncl_yn": (original or {}).get("raw", {}).get("cncl_yn"),
        "original_rmn_qty": _ccld_int((original or {}).get("raw", {}), "rmn_qty"),
        "original_tot_ccld_qty": _ccld_int(
            (original or {}).get("raw", {}), "tot_ccld_qty"
        ),
    }
    if "evidence" in read:
        snapshot["evidence"] = read["evidence"]
    return snapshot


def classify_cancel_shape(
    snapshots: list[dict[str, Any]], original_key: str
) -> dict[str, Any]:
    """What shape the cancel took, across every post-cancel snapshot.

    The verdict is taken over the WHOLE window rather than from the last
    snapshot: the flag and the derived row need not appear at the same instant,
    and #948's consumer (the fill observer's cancel classification) has to know
    that both can be seen, not which was visible last.
    """
    answered = [s for s in snapshots if s.get("read_status") in _READ_ANSWERED]
    # A page that came back FULL may have dropped the rows this verdict is
    # about, so "neither was seen" cannot be concluded from truncated pages
    # alone. Positive observations still count from them — a row that IS there
    # is there — which is why only the negative arm requires an untruncated read.
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


def classify_late_fill(
    *,
    filled_before_cancel: int | None,
    snapshots: list[dict[str, Any]],
    cancel_ack_rt_cd: str,
) -> dict[str, Any]:
    """Whether 총체결수량 grew AFTER the cancel was acknowledged.

    The uncertainty is stated rather than smoothed: the pre-cancel reading is
    one paced call old by the time the cancel goes out, so a growth seen
    afterwards may have happened in that gap. Both the gap and the first
    post-ack snapshot's reading are recorded so a reader can see which.
    """
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


# ---------------------------------------------------------------------------
# Order-emitting steps
# ---------------------------------------------------------------------------


def _submit(
    client: MockTradingClient,
    run: ProbeRun,
    budget: OrderBudget,
    body: dict[str, str],
    *,
    side: str,
    label: str,
) -> tuple[Placed | None, str, dict[str, Any]]:
    """One order POST. Returns ``(placed, stop_reason, record)``.

    ``stop_reason`` is :data:`_STOP_NONE` only when the broker accepted. A lost
    POST is :data:`_STOP_ORDER_STATE_UNKNOWN` and never retried: the order may
    be resting right now under an ODNO this probe never saw, and a resend is
    the duplicate-order hazard.
    """
    budget.spend(label)
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
    """One cancel POST. Returns ``(stop_reason, record, ack_monotonic)``.

    ``ack_monotonic`` is the pacer release instant of the cancel — the only
    honest t0 for the observation window, because a timestamp taken before the
    pacing gate would charge the pacing sleep to the broker.
    """
    budget.spend(label)
    record: dict[str, Any] = {"label": label, "remaining_qty_sent": remaining_qty}
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
    """Snapshot the order surface at t+0 and then until the window closes.

    The effective interval is ``max(observation.poll_interval_s, limits.pace_s)``
    — the pacer is the floor, and a requested interval below it would be
    reported as something the probe did not do.
    """
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


#: 매수 in ``sll_buy_dvsn_cd``. Same code the open-order matcher in
#: ``probes_order`` uses (``_SIDE_BUY``), re-declared rather than imported so
#: this module's one use site is readable beside the field it reads.
_SIDE_BUY = "02"


def _own_filled_qty(
    client: MockTradingClient, symbol: str, cfg: Config, keys: set[str]
) -> dict[str, Any]:
    """How much THIS run's own BUY orders are recorded as having filled.

    The cap on the sell-back. ``readable`` is false when the surface did not
    answer, and the caller then sells nothing: an unreadable inquiry must not
    license a market sell, because the quantity it would license is the
    account's whole holding.
    """
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
    """Cancel this run's own resting orders, sell back what they filled, verify flat.

    Runs on EVERY exit path, including a failed one, and records its own
    outcome rather than raising: an exception here would replace the finding
    the run exists to produce with a cleanup traceback, and the operator still
    needs to know what the account looks like.

    **It only ever undoes this run's own orders.** Both halves are bounded by
    ``placed``: a cancel is sent only for a live row whose ODNO this run
    submitted, and the sell-back quantity is capped at what THOSE orders are
    recorded as having filled. Flattening "whatever the account holds" would be
    correct only while the flat-start proof held, and the one path where it
    does NOT hold is the path where that proof FAILED — which is exactly when
    the cleanup runs over somebody else's shares. A probe must not sell a
    holding it did not buy.
    """
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
                if budget.remaining <= 0:
                    record["cancels"].append(
                        {
                            "attempt": attempt,
                            "odno_key": key,
                            "outcome": _CLEAN_BUDGET_SPENT,
                        }
                    )
                    continue
                outcome, cancel_record, _ack = _cancel(
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
            time.sleep(cfg.limits.cleanup.retry_s)

        own_filled = _own_filled_qty(client, symbol, cfg, keys)
        record["own_filled_qty"] = own_filled
        holding = read_holding(client, symbol, cfg)
        record["holding_after_cancels"] = holding
        held = holding.get("qty")
        sell_qty = 0
        if holding.get("status") == _READ_OK and isinstance(held, int) and held > 0:
            # The cap, not the holding: never sell more than this run bought.
            sell_qty = min(held, own_filled["qty"] if own_filled["readable"] else 0)
        if sell_qty > 0:
            if budget.remaining <= 0:
                record["sell_back"] = {"outcome": _CLEAN_BUDGET_SPENT, "qty": sell_qty}
            else:
                # 시장가 so the flatten does not itself leave a resting order.
                # P-11 measured that a 모의 marketable LIMIT does not fill while a
                # 시장가 order fills at once (P-11-20260730T002715Z vs
                # P-11-20260731T015709Z), so a limit sell-back would end the run
                # with BOTH shares and an open order.
                body = client.stock_order_body(symbol, sell_qty, order_type="market")
                _sold, outcome, sell_record = _submit(
                    client,
                    run,
                    budget,
                    body,
                    side="SELL",
                    label=f"flatten-sell-{sell_qty}",
                )
                record["sell_back"] = {
                    "outcome": outcome,
                    "qty": sell_qty,
                    "submit": sell_record,
                }
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
            # Shares are held and none of them are this run's. Nothing is sold,
            # and the run says so rather than reporting a flat account.
            record["status"] = _CLEAN_STILL_HELD
            record["not_this_runs_holding"] = (
                f"{held} share(s) held and own_filled_qty={own_filled} — the "
                "sell-back is capped at what this run's own orders filled, so "
                "nothing was sold. Settle this by hand"
            )
        else:
            record["status"] = _CLEAN_FLAT

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
        # Counted separately, not ignored. A row the CANCEL produced is not in
        # `keys` either — and since what such a row looks like is precisely what
        # this probe is measuring, any live row on this symbol at the end is
        # reported fail-closed and left for a human rather than cancelled.
        record["orders_final_live_other"] = other_live
        if record["orders_final_live"]:
            record["status"] = _CLEAN_STILL_LIVE
        elif orders.get("status") not in _READ_ANSWERED:
            record["status"] = _CLEAN_UNKNOWN
    except Exception as exc:  # noqa: BLE001 - a cleanup failure must not mask results
        # Including SafetyViolation. Raising out of the caller's `finally` would
        # replace the finding the run exists to produce with a cleanup
        # traceback, and the operator would lose the one thing they need most
        # here: what state the account is in. The budget is still a hard cap —
        # every spend site below checks `remaining` first, so reaching this arm
        # through the budget means a bug worth recording, not worth re-raising.
        record["status"] = _CLEAN_UNKNOWN
        record["exception"] = f"{type(exc).__name__}: {exc}"
    record["budget"] = budget.describe()
    return record


# ---------------------------------------------------------------------------
# Trials
# ---------------------------------------------------------------------------


def _buy_price(
    client: MockTradingClient, symbol: str, offset_pct: float, *, marketable: bool
) -> tuple[TickPrice, float, Tick]:
    """A tick-valid BUY limit ``offset_pct`` away from the touch, from a quote.

    The price is DERIVED, never configured: one quote GET carries both the last
    price and the broker's own 호가단위 (``aspr_unit``), and
    :func:`~tools.broker_probes.probes_order.snap_to_tick` moves it away from
    the touch — further below for a resting order (so the snap can only widen
    the gap that keeps it unfilled) and further across for a marketable one (so
    it is not snapped back out of the market).

    Raises:
        ProbeError: the computed price is not positive, or no 호가단위 could be
            established for the symbol.
    """
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
    placed, stop, _submit_record = _submit(
        client, run, budget, body, side="BUY", label=f"{name}-submit"
    )
    if placed is None or stop != _STOP_NONE:
        return stop, record | {"stopped_at": "submit"}
    placed_out.append(placed)
    record["odno"] = placed.odno
    record["odno_key"] = placed.key
    record["krx_fwdg_ord_orgno"] = placed.krx_fwdg_ord_orgno

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
        # Nothing read, so the cancel has no observed remainder. Send the full
        # quantity: QTY_ALL_ORD_YN="Y" cancels the remainder regardless, and the
        # order quantity is the largest it could be.
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
    if stop in (_STOP_RATE_LIMITED, _STOP_ORDER_STATE_UNKNOWN):
        return stop, record | {"stopped_at": "cancel"}

    snapshots = _observe_window(
        client, cfg, symbol=symbol, original_key=placed.key, t0=ack_at
    )
    record["post_cancel_snapshots"] = snapshots
    record["cancel_shape"] = classify_cancel_shape(snapshots, placed.key)
    record["late_fill"] = classify_late_fill(
        filled_before_cancel=filled_before,
        snapshots=snapshots,
        cancel_ack_rt_cd=str(cancel_record.get("rt_cd", "")),
    )
    if record["cancel_shape"]["snapshots_answered"] == 0:
        return _STOP_QUERY_UNANSWERED, record | {"stopped_at": "observation"}
    # A REJECTED cancel is a measurement (it says the broker would not cancel
    # this order), so it does not stop the run — the shape classification above
    # already recorded what the surface showed.
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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
    """Why trial B must not run, or ``None`` when it may. One reader, three reasons.

    Order matters only for the message: a disabled trial is the operator's
    decision and a stopped trial A is the broker's, and both have to be stated
    rather than left as an absent record.
    """
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
    """P-SC — 주식 MOCK 취소 행 모양 + 늦은 체결 관측 (#948 순서 1).

    Order of operations is load-bearing and in this order for a reason:

    1. config (so every later limit exists), 2. the REAL-environment refusal
    (before credentials are resolved), 3. the session/day gate (before the
    first socket), 4. ``_setup`` (credentials, token cache, the paced client),
    5. the flat-start proof (GET only), 6. trial A, 7. trial B, 8. cleanup in a
    ``finally``.

    Steps 2, 3 and 5 are refusals rather than warnings, and 8 runs even when an
    earlier step raised.
    """
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
    # The client's pacer reads args.pace_s, so the YAML value becomes the
    # effective floor AND is recorded in the artifact's args.
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
    budget = OrderBudget(cfg.limits.max_order_calls)

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
    try:
        run.measure("flat_start", assert_flat_start(client, args.symbol, cfg))
        # Trial A first and unconditionally unless --trial narrowed it away: it
        # is the one that answers #948, and B spends a fill on top of it.
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
