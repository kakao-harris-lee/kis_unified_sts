"""P-CA — corporate-action reflection probe. READ-ONLY BY CONSTRUCTION, GET-only.

Why this probe exists
----------------------
``docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md`` §5.2 defines P-CA as
the opportunistic, operator-in-the-loop half of the two-probe pair that feeds the
``B_non_trade_event_detect`` / ``B_non_trade_reconcile`` adjacent bound keys
(``registry.py::ADJACENT_BOUND_KEYS``). N-19
(``docs/plans/2026-09-10-tos-p02-n19-ca-spec-collation.md``) is the documentary
half: it found that KIS exposes 12 GET-only 예탁원정보(ksdinfo) reference TRs
(§2.1) that carry CA *schedule* fields, but that NONE of them, and no field of the
주식잔고조회 balance TR (``TTTC8434R``/``VTTC8434R``), documents WHEN a corporate
action is reflected in balance/position/체결통보. ``hldg_qty`` (quantity) and
``dnca_tot_amt`` (예수금총금액 — cash/deposit total, N-19 §2.3) are therefore the
only INDIRECT observation surface for that reflection: this probe polls them.

ADR-002-010 §8:171 forbids collapsing the seven CA times into one "corporate
action date" (``tos/src/tos/nontrade/records.py:359-366`` keeps them as separate
fields). This probe honours that: it pairs each leg it can observe with the ONE
of the seven times that leg's rationale calls for (design doc §5.2 table), and it
never emits a single scalar. ``measurements.class_leg_table`` is the only
aggregate this probe writes; the two VP-002 keys stay ``NOT_ESTABLISHED`` — a
Bounds-Approver judgement, never something this probe writes for itself
(``common.py::ProbeRun`` docstring, "Probes measure; humans approve.").

Falsification-first (design doc §5.2, §8.4 / VP-002:772 "observed 0 != 0"): an
unobserved leg within the polling window is recorded as CENSORED, never as a
zero latency. A leg's absence from ``class_leg_table`` with a value is not
evidence the reflection is instantaneous.

Safety model
------------
Strictly GET-only, and structurally so — mirrors ``probes_balance.py`` (P-BAL):

* :data:`ALLOWLIST` is the complete set of calls this module may ever make: the
  two balance-inquiry TRs (real/mock) plus the 12 ksdinfo reference TRs. There is
  no order/cancel/amend path anywhere in this file.
* :func:`_get` is the ONLY transport, and calls
  :func:`~tools.broker_probes.common.assert_read_only_call` (GET (+ TR id (+ URL
  path) *before* the session is touched.
* This module does not import :mod:`tools.broker_probes.probes_order` or
  :mod:`tools.broker_probes.probes_real_order` (both carry order paths).
  ``tests/tools/test_broker_probes_ca.py`` pins all of this against the module's
  own AST, the same way ``test_broker_probes_balance.py`` does for P-BAL.

Futures are refused outright (design doc §5.2 prerequisite 4 / §4): the mock
server does not serve a futures balance query at all
(``shared/kis/client.py:1031`` NOTE, guard ``:1047``), and the real futures
account is never funded with margin (CLAUDE.md Non-Negotiable Rules) — there is
no environment in which a futures CA reflection could be observed here.

Nothing in this module can mutate an order, in mock or in real.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tools.broker_probes.common import (
    ENV_MOCK,
    ENV_REAL,
    MOCK_BASE_URL,
    REAL_BASE_URL,
    ProbeError,
    ProbeRun,
    ReadOnlyCall,
    assert_read_only_call,
    build_auth_config,
    dry_run_banner,
    is_rate_limited,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

# ---------------------------------------------------------------------------
# TR ids and paths — READ from open-trading-api SDK examples (N-19 memo §2.1),
# not guessed. The balance pair mirrors probes_balance.py exactly.
# ---------------------------------------------------------------------------

#: 주식 잔고조회 path — shared/kis/client.py:935 (same surface P-BAL reads).
_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

#: shared/kis/client.py:919 — "TTTC8434R" if self.config.is_real else "VTTC8434R".
_STOCK_TR_REAL = "TTTC8434R"
_STOCK_TR_MOCK = "VTTC8434R"

#: The 12 예탁원정보(ksdinfo) reference TRs (N-19 memo §2.1, VERIFIED via local
#: open-trading-api SDK checkout, accessed 2026-09-10). All GET, account-independent
#: (no CANO/ACNT_PRDT_CD parameter — these are reference-data lookups, not account
#: queries). MOCK(VTS) support is UNKNOWN for every one of them (N-19 §2.1 — the
#: wrapper never branches real/mock for this family, which the memo explicitly
#: warns is NOT evidence either way; ``--reference-check`` is this probe's first
#: live feasibility observation of that open question).
_KSDINFO_BASE = "/uapi/domestic-stock/v1/ksdinfo"
_KSDINFO_TRS: dict[str, tuple[str, str]] = {
    "dividend": ("HHKDB669102C0", f"{_KSDINFO_BASE}/dividend"),
    "bonus_issue": ("HHKDB669101C0", f"{_KSDINFO_BASE}/bonus-issue"),
    "paidin_capin": ("HHKDB669100C0", f"{_KSDINFO_BASE}/paidin-capin"),
    "cap_dcrs": ("HHKDB669106C0", f"{_KSDINFO_BASE}/cap-dcrs"),
    "merger_split": ("HHKDB669104C0", f"{_KSDINFO_BASE}/merger-split"),
    "rev_split": ("HHKDB669105C0", f"{_KSDINFO_BASE}/rev-split"),
    "forfeit": ("HHKDB669109C0", f"{_KSDINFO_BASE}/forfeit"),
    "list_info": ("HHKDB669107C0", f"{_KSDINFO_BASE}/list-info"),
    "pub_offer": ("HHKDB669108C0", f"{_KSDINFO_BASE}/pub-offer"),
    "mand_deposit": ("HHKDB669110C0", f"{_KSDINFO_BASE}/mand-deposit"),
    "purreq": ("HHKDB669103C0", f"{_KSDINFO_BASE}/purreq"),
    "sharehld_meet": ("HHKDB669111C0", f"{_KSDINFO_BASE}/sharehld-meet"),
}

#: CLI ``--event-class`` values (design doc §5.2 + N-19 §2.2 structure table).
_EVENT_CLASSES: tuple[str, ...] = (
    "cash_dividend",
    "stock_dividend",
    "bonus_issue",
    "paidin_capin",
    "split",
    "merger",
    "cap_dcrs",
)

#: Which ksdinfo TR answers ``--reference-check`` for a given ``--event-class``.
#: "split" maps to 액면교체(rev_split — 액면분할/병합), "merger" to 합병/분할
#: (merger_split), matching N-19 §2.1's class column verbatim.
_EVENT_CLASS_KSDINFO_KEY: dict[str, str] = {
    "cash_dividend": "dividend",
    "stock_dividend": "dividend",
    "bonus_issue": "bonus_issue",
    "paidin_capin": "paidin_capin",
    "split": "rev_split",
    "merger": "merger_split",
    "cap_dcrs": "cap_dcrs",
}

#: Complete read-only allowlist. A call not matching an entry is refused by
#: :func:`~tools.broker_probes.common.assert_read_only_call` before any socket is
#: opened. There is deliberately no futures entry — see the module docstring.
ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        _STOCK_TR_REAL,
        _STOCK_BALANCE_PATH,
        "P-CA real stock balance snapshot — hldg_qty (quantity leg) / "
        "dnca_tot_amt (cash leg) baseline + poll. TR/path from "
        "shared/kis/client.py:919,935 (P-BAL precedent).",
    ),
    ReadOnlyCall(
        _STOCK_TR_MOCK,
        _STOCK_BALANCE_PATH,
        "P-CA mock stock balance snapshot — same path, mock TR (client.py:919).",
    ),
) + tuple(
    ReadOnlyCall(
        tr_id,
        path,
        f"P-CA ksdinfo reference-check ({key}) — N-19 §2.1, GET-only, "
        "account-independent (no CANO/ACNT_PRDT_CD parameter).",
    )
    for key, (tr_id, path) in _KSDINFO_TRS.items()
)


# ---------------------------------------------------------------------------
# Pacing — LOCAL re-implementation, deliberately not an import of
# probes_order._CallPacer / DEFAULT_PACE_S: importing that module would put
# order-mutating code in this module's import graph, exactly the property
# test_module_does_not_import_the_order_probe_module pins (P-BAL precedent,
# probes_balance.py's DEFAULT_INTER_PAGE_S comment makes the same call).
# ---------------------------------------------------------------------------

#: Default minimum interval between ANY two broker calls this probe makes.
#: Same measured value P-13/P-BAL use (clean 1.0 rps, P-13-20260729T063120Z);
#: 1.1s sits just above it.
DEFAULT_PACE_S = 1.1


class _Pacer:
    """Minimum-interval gate before every broker call. See module note above."""

    def __init__(self, interval_s: float) -> None:
        self.interval_s = max(0.0, float(interval_s))
        self._next_allowed_at: float | None = None

    def wait(self) -> float:
        now = time.monotonic()
        if self._next_allowed_at is not None and now < self._next_allowed_at:
            time.sleep(self._next_allowed_at - now)
            now = time.monotonic()
        self._next_allowed_at = now + self.interval_s
        return now


def _now() -> datetime:
    """The current wall-clock instant, timezone-aware. A seam for tests.

    Poll timestamps must be compared against operator-supplied ISO-8601 KST
    instants (``--ex-time`` etc.), so ``time.monotonic()`` cannot serve here —
    unlike P-EXT, whose t0 is also taken from ``time.monotonic()``.
    """
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Trial parameters — parsed and validated once, up front
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Trial:
    """Everything one P-CA invocation needs, validated before any network call."""

    symbol: str
    event_class: str
    is_real: bool
    window_s: float
    poll_ms: float
    pace_s: float
    effective_poll_ms: float
    ex_time: datetime | None
    effective_time: datetime | None
    payable_time: datetime | None
    settlement_time_raw: str
    reference_check: bool


def _parse_operator_time(raw: str, flag: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProbeError(f"{flag} must be ISO-8601 (got {raw!r}): {exc}") from None


def _parse_trial(args: argparse.Namespace) -> _Trial:
    """Validate and parse every CLI input. Raises :class:`ProbeError` on any
    precondition violation, before a single network call is possible."""
    asset = str(getattr(args, "asset", "") or "").strip().lower()
    if asset == "futures":
        raise ProbeError(
            "선물 제외 — 정의서 §5.2 prerequisite 4 (모의 선물잔고 미지원 "
            "shared/kis/client.py:1031 NOTE·가드 :1047, 실선물 무증거금·무보유 "
            f"— CLAUDE.md Non-Negotiable Rules): --asset {asset!r}는 허용되지 않는다"
        )
    if asset != "stock":
        raise ProbeError(f"--asset must be 'stock' (got {asset!r}) — P-CA는 주식 전용")

    symbol = str(getattr(args, "symbol", "") or "").strip()
    if not symbol:
        raise ProbeError("--symbol is required (e.g. 005930)")

    event_class = str(getattr(args, "event_class", "") or "").strip()
    if event_class not in _EVENT_CLASSES:
        raise ProbeError(
            f"--event-class must be one of {_EVENT_CLASSES} (got {event_class!r})"
        )

    env = str(getattr(args, "env", "") or "mock").strip().lower()
    if env not in {"mock", "real"}:
        raise ProbeError(f"--env must be 'mock' or 'real' (got {env!r})")

    window_s = float(getattr(args, "window_s", 0) or 0)
    if window_s <= 0:
        raise ProbeError("--window-s must be > 0")
    poll_ms = float(getattr(args, "poll_ms", 0) or 0)
    if poll_ms < 0:
        raise ProbeError("--poll-ms must be >= 0")
    pace_s = float(getattr(args, "pace_s", 0) or 0)
    if pace_s < 0:
        raise ProbeError("--pace-s must be >= 0")

    return _Trial(
        symbol=symbol,
        event_class=event_class,
        is_real=env == "real",
        window_s=window_s,
        poll_ms=poll_ms,
        pace_s=pace_s,
        effective_poll_ms=max(poll_ms, pace_s * 1000.0),
        ex_time=_parse_operator_time(getattr(args, "ex_time", ""), "--ex-time"),
        effective_time=_parse_operator_time(
            getattr(args, "effective_time", ""), "--effective-time"
        ),
        payable_time=_parse_operator_time(
            getattr(args, "payable_time", ""), "--payable-time"
        ),
        settlement_time_raw=str(getattr(args, "settlement_time", "") or "").strip(),
        reference_check=bool(getattr(args, "reference_check", False)),
    )


def _legs_to_track(trial: _Trial) -> list[tuple[str, str, datetime]]:
    """(leg name, t0 field name, t0 instant) for every leg an operator time was
    supplied for. Design doc §5.2 table: quantity leg pairs with ``ex_time`` only
    for ``cash_dividend`` (기준가/수량 adjustment leg); every other class pairs
    the quantity leg with ``effective_time`` (수량 변환 leg). Cash leg always
    pairs with ``payable_time``."""
    qty_field = "ex_time" if trial.event_class == "cash_dividend" else "effective_time"
    qty_t0 = trial.ex_time if qty_field == "ex_time" else trial.effective_time
    legs: list[tuple[str, str, datetime]] = []
    if qty_t0 is not None:
        legs.append(("quantity", qty_field, qty_t0))
    if trial.payable_time is not None:
        legs.append(("cash", "payable_time", trial.payable_time))
    return legs


# ---------------------------------------------------------------------------
# Transport — the ONLY one in this module
# ---------------------------------------------------------------------------


def _get(
    session: Any,
    auth: Any,
    *,
    base_url: str,
    path: str,
    tr_id: str,
    params: dict[str, Any],
) -> tuple[int, dict[str, Any], str, float]:
    """The ONLY transport in this module. GET, allowlisted.

    The allowlist assertion runs BEFORE the session is touched, so a refused call
    opens no socket. Returns ``(status, parsed_body, raw_text, elapsed_ms)``.
    """
    url = f"{base_url}{path}"
    assert_read_only_call("GET", url, tr_id, ALLOWLIST)
    headers = dict(auth.get_auth_headers())
    headers["tr_id"] = tr_id
    headers["custtype"] = "P"
    started = time.monotonic()
    response = session.request("GET", url, headers=headers, params=params, timeout=20.0)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    text = response.text
    try:
        parsed = response.json()
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {"output": parsed}
    return int(response.status_code), parsed, text, elapsed_ms


def _balance_params(creds: Any) -> dict[str, str]:
    """Mirror the runtime's stock balance params (client.py:921-933).

    A single-page snapshot only: P-CA does not paginate (P-BAL already measures
    pagination behaviour) — empty continuation keys, exactly page 1.
    """
    return {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }


def _ksdinfo_window() -> tuple[str, str]:
    """Default ``F_DT``/``T_DT`` window: 30 days back, 180 days forward (KST)."""
    from datetime import timedelta

    kst_now = datetime.now(UTC) + timedelta(hours=9)
    f_dt = (kst_now - timedelta(days=30)).strftime("%Y%m%d")
    t_dt = (kst_now + timedelta(days=180)).strftime("%Y%m%d")
    return f_dt, t_dt


def _ksdinfo_params(key: str, symbol: str) -> dict[str, str]:
    """Param shapes read verbatim from the open-trading-api SDK per-TR wrapper.

    Not every ksdinfo TR takes the same params (N-19 §2.1): ``dividend`` and
    ``paidin_capin`` add ``GB1``, ``dividend`` alone adds ``HIGH_GB``, and
    ``rev_split`` adds ``MARKET_GB`` instead. The common trio is
    ``CTS``/``F_DT``/``T_DT``/``SHT_CD``.
    """
    f_dt, t_dt = _ksdinfo_window()
    params: dict[str, str] = {"CTS": "", "F_DT": f_dt, "T_DT": t_dt, "SHT_CD": symbol}
    if key in ("dividend", "paidin_capin"):
        params["GB1"] = "0"
    if key == "dividend":
        params["HIGH_GB"] = " "
    if key == "rev_split":
        params["MARKET_GB"] = "0"
    return params


def _read_position(parsed: dict[str, Any], symbol: str) -> tuple[int, float]:
    """Read ``(hldg_qty for symbol, dnca_tot_amt account total)`` from a balance body."""
    rows = parsed.get("output1")
    rows = rows if isinstance(rows, list) else []
    qty = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("pdno") or "").strip() == symbol:
            try:
                qty = int(float(row.get("hldg_qty") or 0))
            except (TypeError, ValueError):
                qty = 0
            break
    out2 = parsed.get("output2")
    cash = 0.0
    if isinstance(out2, list) and out2 and isinstance(out2[0], dict):
        try:
            cash = float(out2[0].get("dnca_tot_amt") or 0)
        except (TypeError, ValueError):
            cash = 0.0
    return qty, cash


# ---------------------------------------------------------------------------
# Procedure steps — each kept small and independently readable/testable
# ---------------------------------------------------------------------------


def _do_baseline(
    run: ProbeRun,
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    pacer: _Pacer,
    symbol: str,
) -> tuple[int, float] | None:
    """One paced GET balance snapshot. Returns ``(qty, cash)`` or ``None`` if the
    run should stop here (rate-limited, rejected, or no holding)."""
    pacer.wait()
    status, parsed, text, elapsed_ms = _get(
        session,
        auth,
        base_url=base_url,
        path=_STOCK_BALANCE_PATH,
        tr_id=tr_id,
        params=_balance_params(creds),
    )
    run.observe(
        baseline_call={
            "http_status": status,
            "rt_cd": parsed.get("rt_cd"),
            "elapsed_ms": round(elapsed_ms, 1),
        }
    )
    if is_rate_limited(status, parsed, text):
        run.error(
            f"rate-limited on baseline balance call (status={status}); "
            "stopping — no retry"
        )
        return None
    rt_cd = str(parsed.get("rt_cd") or "").strip()
    if rt_cd != "0":
        run.error(
            f"baseline balance call rejected: rt_cd={rt_cd!r} "
            f"msg_cd={parsed.get('msg_cd')!r} msg1={parsed.get('msg1')!r}"
        )
        return None

    qty, cash = _read_position(parsed, symbol)
    run.measure("baseline", {"hldg_qty": qty, "dnca_tot_amt": cash})
    if qty <= 0:
        run.skip(
            "no holding — cannot establish",
            f"{symbol} has hldg_qty={qty} at baseline. A CA reflection latency "
            "cannot be measured without a pre-existing holding (design doc "
            "§5.2 prerequisite 3 / P-BAL precedent).",
        )
        return None
    return qty, cash


def _do_reference_check(
    run: ProbeRun,
    session: Any,
    auth: Any,
    base_url: str,
    pacer: _Pacer,
    trial: _Trial,
) -> None:
    """One paced GET to the ksdinfo TR matching ``--event-class``, BEFORE polling."""
    ksd_key = _EVENT_CLASS_KSDINFO_KEY[trial.event_class]
    ksd_tr, ksd_path = _KSDINFO_TRS[ksd_key]
    pacer.wait()
    status, parsed, text, _elapsed_ms = _get(
        session,
        auth,
        base_url=base_url,
        path=ksd_path,
        tr_id=ksd_tr,
        params=_ksdinfo_params(ksd_key, trial.symbol),
    )
    if is_rate_limited(status, parsed, text):
        run.error(
            f"rate-limited on reference-check call (status={status}); "
            "stopping — no retry"
        )
        raise _RateLimited
    rt_cd = str(parsed.get("rt_cd") or "").strip()
    if rt_cd != "0":
        detail = f"{rt_cd}/{parsed.get('msg_cd')}:{parsed.get('msg1')}"
        key = "mock_reference_support" if not trial.is_real else "reference_check_error"
        run.observe(**{key: f"UNSUPPORTED_OR_ERROR:{detail}"})
        return
    rows = parsed.get("output1")
    run.observe(reference_dates=rows if isinstance(rows, list) else [])
    if not trial.is_real:
        run.observe(mock_reference_support="SUPPORTED")


class _RateLimited(ProbeError):
    """Internal control-flow signal: a rate limit was already recorded via
    ``run.error`` and the caller must stop without any further broker call."""


def _poll_loop(
    run: ProbeRun,
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    trial: _Trial,
    baseline_qty: int,
    baseline_cash: float,
    legs: list[tuple[str, str, datetime]],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Poll balance until every leg is observed or ``--window-s`` expires.

    Returns ``(found, polls_used)`` — ``found`` maps leg name to its measurement
    record for every leg detected live; a leg absent from ``found`` was CENSORED.
    """
    pending = {name: (t0_field, t0_dt) for name, t0_field, t0_dt in legs}
    found: dict[str, dict[str, Any]] = {}
    poll_pacer = _Pacer(trial.effective_poll_ms / 1000.0)
    polls_used = 0
    deadline = time.monotonic() + trial.window_s

    while pending and time.monotonic() < deadline:
        poll_pacer.wait()
        polls_used += 1
        status, parsed, text, _elapsed_ms = _get(
            session,
            auth,
            base_url=base_url,
            path=_STOCK_BALANCE_PATH,
            tr_id=tr_id,
            params=_balance_params(creds),
        )
        if is_rate_limited(status, parsed, text):
            run.error(
                f"rate-limited during poll #{polls_used} (status={status}); "
                "stopping — no retry"
            )
            break
        rt_cd = str(parsed.get("rt_cd") or "").strip()
        if rt_cd != "0":
            run.error(
                f"poll #{polls_used} rejected: rt_cd={rt_cd!r} "
                f"msg_cd={parsed.get('msg_cd')!r}"
            )
            break

        qty, cash = _read_position(parsed, trial.symbol)
        now = _now()
        run.observe(poll={"index": polls_used, "hldg_qty": qty, "dnca_tot_amt": cash})
        for name, observed, baseline in (
            ("quantity", qty, baseline_qty),
            ("cash", cash, baseline_cash),
        ):
            if name in pending and observed != baseline:
                t0_field, t0_dt = pending.pop(name)
                record = {
                    "event_class": trial.event_class,
                    "leg": name,
                    "t0_field": t0_field,
                    "t0": t0_dt.isoformat(),
                    "t1": now.isoformat(),
                    "latency_ms": (now - t0_dt).total_seconds() * 1000.0,
                    "poll_interval_ms_effective": trial.effective_poll_ms,
                    "candidate_only": True,
                    f"baseline_{name if name == 'quantity' else 'cash'}": baseline,
                    f"observed_{name if name == 'quantity' else 'cash'}": observed,
                }
                found[name] = record
                run.measure(f"legs.{trial.event_class}.{name}", record)

    return found, polls_used


def _finalize(
    run: ProbeRun,
    trial: _Trial,
    legs: list[tuple[str, str, datetime]],
    found: dict[str, dict[str, Any]],
    polls_used: int,
) -> None:
    """Build ``class_leg_table`` — the ONLY aggregate this probe emits — and
    skip every CENSORED leg explicitly (never a value, never a zero)."""
    class_leg_table: list[dict[str, Any]] = []
    for name, t0_field, t0_dt in legs:
        if name in found:
            row = dict(found[name])
            row["status"] = "OBSERVED"
        else:
            row = {
                "event_class": trial.event_class,
                "leg": name,
                "t0_field": t0_field,
                "t0": t0_dt.isoformat(),
                "status": "CENSORED",
                "window_s": trial.window_s,
                "candidate_only": True,
            }
            run.skip(
                f"legs.{trial.event_class}.{name}",
                "CENSORED — no broker-reflect observed within "
                f"--window-s={trial.window_s}s (polls_used={polls_used}). "
                "Absence of an observed reflection is not evidence of zero "
                "latency (VP-002:772 'observed 0 != 0').",
            )
        class_leg_table.append(row)

    run.measure("class_leg_table", class_leg_table)
    run.measure("polls_used", polls_used)
    run.measure("poll_interval_ms_effective", trial.effective_poll_ms)
    run.measure(
        # The framework's own provenance_class (common.py::ProbeRun.to_dict)
        # only distinguishes mode/errors, not per-leg observation — a window
        # that legitimately CENSORS every leg is neither an error nor a full
        # measurement. This supplements it with the framework's own
        # MEASURED/NOT_MEASURED vocabulary (no third value exists there);
        # "at least one leg observed live" is the honest per-leg signal.
        "leg_provenance_class",
        "MEASURED" if found else "NOT_MEASURED",
    )
    run.measure(
        "no_aggregate_scalar_note",
        "B_non_trade_event_detect / B_non_trade_reconcile are never written as "
        "a single scalar by this probe — the source_and_broker_specific "
        "estimand is undefined (design doc §11 MODERATE-7). "
        "measurements.class_leg_table is the only aggregate emitted; both "
        "VP-002 keys stay NOT_ESTABLISHED pending a Bounds-Approver.",
    )


# ---------------------------------------------------------------------------
# P-CA
# ---------------------------------------------------------------------------


def _build_run(spec: ProbeSpec, args: argparse.Namespace, trial: _Trial) -> ProbeRun:
    """Construct the artifact and record the attestation — before any network call."""
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        # NOT spec.environment: §6.2 forbids citing a MOCK_VTS artifact in a
        # REAL_PROD document, so the artifact must record what was ACTUALLY
        # contacted (P-BAL precedent, probes_balance.py:611-614).
        environment=ENV_REAL if trial.is_real else ENV_MOCK,
        args=vars(args),
    )
    run.observe(
        read_only_attestation=(
            "This probe can issue GET requests only, against the allowlist in "
            "tools/broker_probes/probes_ca.py::ALLOWLIST (2 balance TRs + 12 "
            "ksdinfo reference TRs). No order path exists in this module and it "
            "does not import one."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in ALLOWLIST],
        event_class=trial.event_class,
        symbol=trial.symbol,
    )
    if trial.settlement_time_raw:
        run.observe(
            settlement_time_recorded=trial.settlement_time_raw,
            settlement_time_note=(
                "recorded only — settlement_time is a futures-only leg (design "
                "doc §5.2 statistic table) and this probe refuses --asset "
                "futures, so it is never paired with a measurement here."
            ),
        )
    return run


def _dry_run_would_send(trial: _Trial) -> str:
    tr_id = _STOCK_TR_MOCK if not trial.is_real else _STOCK_TR_REAL
    return (
        f"one read-only GET balance snapshot for {trial.symbol} ({tr_id}); "
        "optionally one ksdinfo reference-check GET; then a bounded poll loop "
        f"of balance GETs at effective interval {trial.effective_poll_ms:.0f}ms "
        f"up to --window-s={trial.window_s}s"
    )


def probe_pca(args: argparse.Namespace) -> ProbeRun:
    """P-CA CORPORATE_ADMINISTRATIVE_EVENTS — opportunistic GET-only reflection latency.

    Per (event_class x leg): pairs a broker-reflect poll (t1) with the ONE of the
    seven ADR §8 times that leg's rationale names as t0 (design doc §5.2 table),
    per :func:`_legs_to_track`. Procedure (design doc §5.2 ⑤): baseline balance
    snapshot -> optional ``--reference-check`` -> operator ``[Enter]`` prompt
    (P-EXT form) -> bounded poll loop (:func:`_poll_loop`) -> per-leg
    OBSERVED/CENSORED classification (:func:`_finalize`). No aggregate scalar is
    ever written for ``B_non_trade_event_detect``/``B_non_trade_reconcile`` —
    both stay ``NOT_ESTABLISHED``, a Bounds-Approver decision this probe cannot
    make.
    """
    spec = get("P-CA")
    trial = _parse_trial(args)
    run = _build_run(spec, args, trial)

    if not args.confirm:
        dry_run_banner(spec)
        run.observe(would_send=_dry_run_would_send(trial))
        return run

    warn_shared_token_cache()
    creds = resolve_credentials("stock", is_real=trial.is_real)
    run.credentials = creds.describe()
    require_account(creds)

    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()
    base_url = REAL_BASE_URL if trial.is_real else MOCK_BASE_URL
    tr_id = _STOCK_TR_REAL if trial.is_real else _STOCK_TR_MOCK
    pacer = _Pacer(trial.pace_s)

    try:
        baseline = _do_baseline(
            run, session, auth, base_url, tr_id, creds, pacer, trial.symbol
        )
        if baseline is None:
            return run
        baseline_qty, baseline_cash = baseline

        if trial.reference_check:
            try:
                _do_reference_check(run, session, auth, base_url, pacer, trial)
            except _RateLimited:
                return run

        legs = _legs_to_track(trial)
        if not legs:
            run.skip(
                "leg polling",
                "no operator time supplied (--ex-time/--effective-time/"
                "--payable-time) — nothing to pair a broker-reflect poll "
                "against",
            )
            return run

        print(
            f"\n  >>> P-CA: {trial.symbol} is held (baseline qty={baseline_qty}). "
            "Wait for the first relevant CA time to pass, then press Enter to "
            "begin polling.\n"
        )
        input("  [Enter when the first relevant time has passed] ")

        found, polls_used = _poll_loop(
            run,
            session,
            auth,
            base_url,
            tr_id,
            creds,
            trial,
            baseline_qty,
            baseline_cash,
            legs,
        )
        _finalize(run, trial, legs, found, polls_used)
    finally:
        session.close()
    return run


def add_ca_args(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(asset="stock")
    parser.add_argument(
        "--env",
        choices=("mock", "real"),
        default="mock",
        help=(
            "Which environment to read (default 'mock' — policy-safe, low-cost "
            "default per design doc §5.2 M-3). A MOCK_VTS artifact is never "
            "REAL_PROD-citable (§6.2 / ADR-002-004 §13.14); --env real requires "
            "operator-approved real credentials in the environment."
        ),
    )
    parser.add_argument(
        "--event-class",
        choices=_EVENT_CLASSES,
        default="",
        help="Corporate-action class this trial observes (required).",
    )
    parser.add_argument(
        "--ex-time",
        default="",
        help=(
            "ISO-8601 KST (e.g. 2026-09-30T09:00:00+09:00) — 배당락/권리락. t0 "
            "for the quantity leg when --event-class=cash_dividend."
        ),
    )
    parser.add_argument(
        "--effective-time",
        default="",
        help=(
            "ISO-8601 KST — 신주 효력(상장/등록)일. t0 for the quantity leg for "
            "every --event-class other than cash_dividend."
        ),
    )
    parser.add_argument(
        "--payable-time",
        default="",
        help="ISO-8601 KST — 지급일. t0 for the cash leg (dnca_tot_amt change).",
    )
    parser.add_argument(
        "--settlement-time",
        default="",
        help=(
            "ISO-8601 KST — 결제 시점. Recorded verbatim, never measured: "
            "settlement is a futures-only leg (design doc §5.2) and this probe "
            "refuses --asset futures."
        ),
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=5000.0,
        help=(
            "Requested polling interval (default 5000ms). Floored by --pace-s "
            "— the effective interval max(--poll-ms, --pace-s*1000) is what "
            "gets recorded, not the requested value."
        ),
    )
    parser.add_argument(
        "--window-s",
        type=float,
        default=3600.0,
        help=(
            "Maximum polling seconds per trial (default 3600 = 1h). Expiry "
            "records CENSORED for every leg still pending — never a value."
        ),
    )
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=(
            f"Minimum interval between ANY two broker calls (default "
            f"{DEFAULT_PACE_S}s) — baseline, reference-check and every poll "
            "alike. Local re-implementation of the measured P-13/P-BAL pace; "
            "see the module note on why probes_order is not imported here."
        ),
    )
    parser.add_argument(
        "--reference-check",
        action="store_true",
        help=(
            "Also call the ksdinfo TR matching --event-class once BEFORE "
            "polling and record its raw dates as observations.reference_dates "
            "— the first live MOCK feasibility observation N-19 §3 asks for."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
