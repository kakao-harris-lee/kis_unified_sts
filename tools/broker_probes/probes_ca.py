"""P-CA — corporate-action reflection probe. READ-ONLY BY CONSTRUCTION, GET-only."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from tools.broker_probes.common import (
    BODY_EXCERPT_MAX_CHARS,
    ENV_MOCK,
    ENV_REAL,
    MOCK_BASE_URL,
    REAL_BASE_URL,
    STATUS_RATE_LIMITED,
    STATUS_TRANSIENT,
    STATUS_TRANSIENT_LEDGER_THROTTLE,
    STATUS_TRANSIENT_TRANSPORT,
    TRANSIENT_LEDGER_THROTTLE,
    TRANSIENT_TRANSPORT,
    Outcome,
    Pacer,
    ProbeError,
    ProbeRun,
    ReadOnlyCall,
    Retries,
    assert_read_only_call,
    build_auth_config,
    call_evidence,
    classify_answer,
    dry_run_banner,
    is_ledger_throttled,
    probe_token_cache_dir,
    record_retry,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    retry_evidence,
    retry_once,
    transient_kind,
    transport_excerpt,
    transport_transient_types,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

_STOCK_TR_REAL = "TTTC8434R"
_STOCK_TR_MOCK = "VTTC8434R"

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

_EVENT_CLASSES: tuple[str, ...] = (
    "cash_dividend",
    "stock_dividend",
    "bonus_issue",
    "paidin_capin",
    "split",
    "merger",
    "cap_dcrs",
)

_EVENT_CLASS_KSDINFO_KEY: dict[str, str] = {
    "cash_dividend": "dividend",
    "stock_dividend": "dividend",
    "bonus_issue": "bonus_issue",
    "paidin_capin": "paidin_capin",
    "split": "rev_split",
    "merger": "merger_split",
    "cap_dcrs": "cap_dcrs",
}

ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        _STOCK_TR_REAL,
        _STOCK_BALANCE_PATH,
        "P-CA real stock balance snapshot — hldg_qty (quantity leg) / "
        "dnca_tot_amt (cash leg) baseline + poll. TR/path from "
        "shared/kis/client.py:919,935 (P-BAL precedent; that module was "
        "removed 2026-11-13 — read it in git history).",
    ),
    ReadOnlyCall(
        _STOCK_TR_MOCK,
        _STOCK_BALANCE_PATH,
        "P-CA mock stock balance snapshot — same path, mock TR "
        "(client.py:919, in git history since 2026-11-13).",
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


POLICY_VERSION = "p-ca-retry-policy/2"

DEFAULT_PACE_S = 1.1


class _Pacer(Pacer):
    """Minimum-interval gate before every broker call. See module note above."""

    def derive(self, interval_s: float) -> _Pacer:
        """A pacer on a new interval that still owes THIS pacer's gap."""
        successor = _Pacer(interval_s)
        successor._next_allowed_at = self._next_allowed_at
        return successor


def _now() -> datetime:
    """The current wall-clock instant, timezone-aware. A seam for tests."""
    return datetime.now(UTC)


def _reference_now() -> datetime:
    """'Now' for the future-time check only (:func:`_parse_operator_time`) —"""
    return datetime.now(UTC)


_KST_OFFSET = "+09:00"


def _offset_str(value: datetime) -> str:
    """``value``'s UTC offset as ``+HH:MM``/``-HH:MM`` — ``strftime('%z')`` with"""
    offset = value.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset else 0
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


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
    reference_only: bool
    reference_from: str
    reference_to: str
    reference_rows_from: str
    t0_offsets: dict[str, str]


def _parse_operator_time(
    raw: str, flag: str, *, allow_future: bool = False
) -> tuple[datetime | None, str | None]:
    """Parse one operator time. Returns ``(value, offset)``."""
    raw = (raw or "").strip()
    if not raw:
        return None, None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ProbeError(f"{flag} must be ISO-8601 (got {raw!r}): {exc}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProbeError(
            f"{flag} must carry a UTC offset (got {raw!r}) — KST is "
            f"'{_KST_OFFSET}', e.g. 2026-09-30T09:00:00{_KST_OFFSET}. A naive "
            "timestamp cannot be safely compared against the (UTC, aware) poll "
            "clock."
        )
    now = _reference_now()
    if parsed > now and not allow_future:
        raise ProbeError(
            f"{flag} is in the future ({raw!r} > {now.isoformat()}) — P-CA "
            "pairs a poll against a time that has ALREADY passed; a future t0 "
            "would record a negative latency. Use --reference-only to look the "
            "event up in the ksdinfo reference table without polling anything."
        )
    return parsed, _offset_str(parsed)


def _parse_reference_date(raw: str, flag: str) -> str:
    """One ``YYYYMMDD`` ksdinfo window override, or ``""`` when not supplied."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if len(raw) != 8 or not raw.isdigit():
        raise ProbeError(f"{flag} must be YYYYMMDD (got {raw!r})")
    try:
        datetime.strptime(raw, "%Y%m%d")
    except ValueError as exc:
        raise ProbeError(f"{flag} is not a real date (got {raw!r}): {exc}") from None
    return raw


def _parse_trial(args: argparse.Namespace) -> _Trial:
    """Validate and parse every CLI input. Raises :class:`ProbeError` on any"""
    asset = str(getattr(args, "asset", "") or "").strip().lower()
    if asset == "futures":
        raise ProbeError(
            "선물 제외 — 정의서 §5.2 prerequisite 4 (모의 선물잔고 미지원 "
            "shared/kis/client.py:1031 NOTE·가드 :1047 — 2026-11-13 삭제, "
            "git 이력 참조, 실선물 무증거금·무보유 "
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

    reference_only = bool(getattr(args, "reference_only", False))

    window_s = float(getattr(args, "window_s", 0) or 0)
    if window_s <= 0 and not reference_only:
        raise ProbeError("--window-s must be > 0")
    poll_ms = float(getattr(args, "poll_ms", 0) or 0)
    if poll_ms < 0:
        raise ProbeError("--poll-ms must be >= 0")
    pace_s = float(getattr(args, "pace_s", 0) or 0)
    if pace_s < 0:
        raise ProbeError("--pace-s must be >= 0")

    reference_from = _parse_reference_date(
        getattr(args, "reference_from", ""), "--reference-from"
    )
    reference_to = _parse_reference_date(
        getattr(args, "reference_to", ""), "--reference-to"
    )
    t0_offsets: dict[str, str] = {}
    ex_time, ex_offset = _parse_operator_time(
        getattr(args, "ex_time", ""), "--ex-time", allow_future=reference_only
    )
    effective_time, effective_offset = _parse_operator_time(
        getattr(args, "effective_time", ""),
        "--effective-time",
        allow_future=reference_only,
    )
    payable_time, payable_offset = _parse_operator_time(
        getattr(args, "payable_time", ""),
        "--payable-time",
        allow_future=reference_only,
    )
    for flag_name, offset in (
        ("ex_time", ex_offset),
        ("effective_time", effective_offset),
        ("payable_time", payable_offset),
    ):
        if offset is not None:
            t0_offsets[flag_name] = offset

    trial = _Trial(
        symbol=symbol,
        event_class=event_class,
        is_real=env == "real",
        window_s=window_s,
        poll_ms=poll_ms,
        pace_s=pace_s,
        effective_poll_ms=max(poll_ms, pace_s * 1000.0),
        ex_time=ex_time,
        effective_time=effective_time,
        payable_time=payable_time,
        settlement_time_raw=str(getattr(args, "settlement_time", "") or "").strip(),
        reference_check=bool(getattr(args, "reference_check", False)) or reference_only,
        reference_only=reference_only,
        reference_from=reference_from,
        reference_to=reference_to,
        reference_rows_from=str(getattr(args, "reference_rows_from", "") or "").strip(),
        t0_offsets=t0_offsets,
    )
    _assert_reference_window_is_not_empty(trial)
    return trial


def _assert_reference_window_is_not_empty(trial: _Trial) -> None:
    """Refuse a ksdinfo window that cannot contain anything, before the call."""
    window = _ksdinfo_window(trial)
    if window["f_dt"] <= window["t_dt"]:
        return
    overrides = window["operator_overrides"]
    raise ProbeError(
        f"the ksdinfo window is empty: F_DT={window['f_dt']} is after "
        f"T_DT={window['t_dt']} "
        f"(operator overrides: {', '.join(overrides) or 'none'}; the other "
        f"end is derived from {window['anchor_source']}). An empty window "
        "answers zero rows, which is indistinguishable from 'this event is "
        "not in the reference table'."
    )


def _legs_to_track(trial: _Trial) -> list[tuple[str, str, datetime]]:
    """(leg name, t0 field name, t0 instant) for every leg ACTUALLY observable"""
    legs: list[tuple[str, str, datetime]] = []
    if trial.event_class != "cash_dividend" and trial.effective_time is not None:
        legs.append(("quantity", "effective_time", trial.effective_time))
    if trial.payable_time is not None:
        legs.append(("cash", "payable_time", trial.payable_time))
    return legs


def _observable_leg_names(event_class: str) -> tuple[str, ...]:
    """Which legs this probe COULD observe for ``event_class``, whether or not"""
    if event_class == "cash_dividend":
        return ("cash",)
    return ("quantity", "cash")


def _get(
    session: Any,
    auth: Any,
    *,
    base_url: str,
    path: str,
    tr_id: str,
    params: dict[str, Any],
) -> tuple[int, dict[str, Any], str, float]:
    """The ONLY transport in this module. GET, allowlisted."""
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


def _balance_params(creds: Any, *, fk: str = "", nk: str = "") -> dict[str, str]:
    """Mirror the runtime's stock balance params (client.py:921-933), with the"""
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
        "CTX_AREA_FK100": fk,
        "CTX_AREA_NK100": nk,
    }


_KSDINFO_LOOKBACK_DAYS = 120
_KSDINFO_LOOKAHEAD_DAYS = 180


def _ksdinfo_anchor(trial: _Trial) -> tuple[datetime | None, str]:
    """The EARLIEST operator time supplied, and the flag it came from."""
    supplied = [
        (value, name)
        for value, name in (
            (trial.ex_time, "ex_time"),
            (trial.effective_time, "effective_time"),
            (trial.payable_time, "payable_time"),
        )
        if value is not None
    ]
    if not supplied:
        return None, "run_time"
    return min(supplied, key=lambda pair: pair[0])


def _ksdinfo_window(trial: _Trial) -> dict[str, Any]:
    """``F_DT``/``T_DT`` for this trial's ksdinfo GET, and where they came from."""
    from datetime import timedelta

    kst_now = datetime.now(UTC) + timedelta(hours=9)
    anchor, anchor_source = _ksdinfo_anchor(trial)
    if anchor is None:
        low = high = kst_now
    else:
        anchor_kst = anchor.astimezone(UTC) + timedelta(hours=9)
        low, high = min(kst_now, anchor_kst), max(kst_now, anchor_kst)

    derived_f = (low - timedelta(days=_KSDINFO_LOOKBACK_DAYS)).strftime("%Y%m%d")
    derived_t = (high + timedelta(days=_KSDINFO_LOOKAHEAD_DAYS)).strftime("%Y%m%d")
    overrides = [
        name
        for name, value in (
            ("F_DT", trial.reference_from),
            ("T_DT", trial.reference_to),
        )
        if value
    ]
    return {
        "f_dt": trial.reference_from or derived_f,
        "t_dt": trial.reference_to or derived_t,
        "anchor": anchor.isoformat() if anchor is not None else None,
        "anchor_source": anchor_source,
        "lookback_days": _KSDINFO_LOOKBACK_DAYS,
        "lookahead_days": _KSDINFO_LOOKAHEAD_DAYS,
        "operator_overrides": overrides,
    }


def _ksdinfo_params(key: str, symbol: str, window: dict[str, Any]) -> dict[str, str]:
    """Param shapes read verbatim from the open-trading-api SDK per-TR wrapper."""
    f_dt, t_dt = str(window["f_dt"]), str(window["t_dt"])
    params: dict[str, str] = {"CTS": "", "F_DT": f_dt, "T_DT": t_dt, "SHT_CD": symbol}
    if key in ("dividend", "paidin_capin"):
        params["GB1"] = "0"
    if key == "dividend":
        params["HIGH_GB"] = " "
    if key == "rev_split":
        params["MARKET_GB"] = "0"
    return params


def _find_symbol_qty(rows: list[Any], symbol: str) -> int | None:
    """``hldg_qty`` for ``symbol``'s row on THIS page, or ``None`` if the row is"""
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("pdno") or "").strip() == symbol:
            try:
                return int(float(row.get("hldg_qty") or 0))
            except (TypeError, ValueError):
                return 0
    return None


def _read_cash_total(parsed: dict[str, Any]) -> float:
    """Account-level ``dnca_tot_amt`` (예수금총금액) from a balance body."""
    out2 = parsed.get("output2")
    if isinstance(out2, list) and out2 and isinstance(out2[0], dict):
        try:
            return float(out2[0].get("dnca_tot_amt") or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


_MAX_BALANCE_PAGES = 5

_BAL_OK = "OK"
_BAL_RATE_LIMITED = STATUS_RATE_LIMITED
_BAL_REJECTED = "REJECTED"
_BAL_CAPPED = "CAPPED"

_BAL_TRANSIENT = STATUS_TRANSIENT
_TRANSIENT_TRANSPORT = TRANSIENT_TRANSPORT
_TRANSIENT_LEDGER_THROTTLE = TRANSIENT_LEDGER_THROTTLE
_BAL_TRANSIENT_TRANSPORT = STATUS_TRANSIENT_TRANSPORT
_BAL_TRANSIENT_LEDGER_THROTTLE = STATUS_TRANSIENT_LEDGER_THROTTLE

_is_ledger_throttled = is_ledger_throttled
_transport_transient_types = transport_transient_types
_transport_excerpt = transport_excerpt
_transient_kind = transient_kind


def _get_classified(
    session: Any,
    auth: Any,
    *,
    base_url: str,
    path: str,
    tr_id: str,
    params: dict[str, Any],
) -> tuple[str | None, int, dict[str, Any], str]:
    """One GET through this module's transport, classified by the shared policy."""
    try:
        http_status, parsed, text, _elapsed_ms = _get(
            session,
            auth,
            base_url=base_url,
            path=path,
            tr_id=tr_id,
            params=params,
        )
    except transport_transient_types() as exc:
        return STATUS_TRANSIENT_TRANSPORT, 0, {}, transport_excerpt(exc)
    return classify_answer(http_status, parsed, text), http_status, parsed, text


_STOP_RATE_LIMITED = "rate_limited"
_STOP_REJECTED = "rejected"
_STOP_PAGE_CAP = "page_cap"
_STOP_TRANSIENT = "transient"

_BODY_EXCERPT_MAX_CHARS = BODY_EXCERPT_MAX_CHARS
_call_evidence = call_evidence


def _read_balance(
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    symbol: str,
    pacer: _Pacer,
) -> tuple[str, int, float, dict[str, Any], str, int]:
    """Walk balance pages (capped at :data:`_MAX_BALANCE_PAGES`) until"""
    fk = nk = ""
    cash = 0.0
    parsed: dict[str, Any] = {}
    text = ""
    http_status = 0
    for _page in range(_MAX_BALANCE_PAGES):
        pacer.wait()
        kind, http_status, parsed, text = _get_classified(
            session,
            auth,
            base_url=base_url,
            path=_STOCK_BALANCE_PATH,
            tr_id=tr_id,
            params=_balance_params(creds, fk=fk, nk=nk),
        )
        if kind is not None:
            return kind, 0, cash, parsed, text, http_status
        rt_cd = str(parsed.get("rt_cd") or "").strip()
        if rt_cd != "0":
            return _BAL_REJECTED, 0, cash, parsed, text, http_status
        rows = parsed.get("output1")
        rows = rows if isinstance(rows, list) else []
        cash = _read_cash_total(parsed)
        found_qty = _find_symbol_qty(rows, symbol)
        if found_qty is not None:
            return _BAL_OK, found_qty, cash, parsed, text, http_status
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not next_fk and not next_nk:
            return _BAL_OK, 0, cash, parsed, text, http_status
        fk, nk = next_fk, next_nk
    return _BAL_CAPPED, 0, cash, parsed, text, http_status


_Retries = Retries
_retry_evidence = retry_evidence
_Outcome = Outcome
_retry_once = retry_once


def _balance_outcome(
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    symbol: str,
    pacer: _Pacer,
) -> _Outcome:
    """:func:`_read_balance` as an :class:`_Outcome`, for :func:`_retry_once`."""
    status, qty, cash, parsed, text, http_status = _read_balance(
        session, auth, base_url, tr_id, creds, symbol, pacer
    )
    return _Outcome(
        kind=status,
        http_status=http_status,
        parsed=parsed,
        text=text,
        payload=(qty, cash),
    )


def _ksdinfo_outcome(
    session: Any,
    auth: Any,
    base_url: str,
    pacer: _Pacer,
    ksd_key: str,
    symbol: str,
    window: dict[str, Any],
) -> _Outcome:
    """One paced ksdinfo GET as an :class:`_Outcome`."""
    ksd_tr, ksd_path = _KSDINFO_TRS[ksd_key]
    pacer.wait()
    kind, http_status, parsed, text = _get_classified(
        session,
        auth,
        base_url=base_url,
        path=ksd_path,
        tr_id=ksd_tr,
        params=_ksdinfo_params(ksd_key, symbol, window),
    )
    return _Outcome(kind=kind, http_status=http_status, parsed=parsed, text=text)


_record_retry = record_retry


def _do_baseline(
    run: ProbeRun,
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    pacer: _Pacer,
    symbol: str,
    retries: _Retries,
    retry_wait_s: float,
) -> tuple[int, float] | None:
    """Paced, paginated balance snapshot (:func:`_read_balance`), retried once"""
    outcome, _attempts, _retried = _retry_once(
        lambda: _balance_outcome(session, auth, base_url, tr_id, creds, symbol, pacer),
        _record_retry(run, retries),
        pacer,
        wait_s=retry_wait_s,
        phase="baseline",
    )
    status, http_status, parsed, text = (
        outcome.kind,
        outcome.http_status,
        outcome.parsed,
        outcome.text,
    )
    qty, cash = outcome.payload
    run.observe(
        baseline_call=_call_evidence(
            status_kind=status or "", http_status=http_status, parsed=parsed, text=text
        )
    )
    if status == _BAL_RATE_LIMITED:
        run.error("rate-limited on baseline balance call; stopping — no retry")
        return None
    transient = _transient_kind(status)
    if transient is not None:
        run.error(
            f"baseline balance call failed twice in a row with a transient "
            f"{transient} error (one retry, {retry_wait_s}s apart); stopping"
        )
        return None
    if status == _BAL_REJECTED:
        run.error(
            f"baseline balance call rejected: rt_cd={parsed.get('rt_cd')!r} "
            f"msg_cd={parsed.get('msg_cd')!r} msg1={parsed.get('msg1')!r}"
        )
        return None
    if status == _BAL_CAPPED:
        run.error(
            f"baseline balance read hit the {_MAX_BALANCE_PAGES}-page cap "
            f"without finding {symbol}'s row or a broker end-of-set signal — "
            "INCONCLUSIVE, not 'no holding' (a truncated read must never be "
            "reported as an absent position, finding F6)."
        )
        return None

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
    retries: _Retries,
) -> None:
    """One paced GET to the ksdinfo TR matching ``--event-class``, BEFORE"""
    ksd_key = _EVENT_CLASS_KSDINFO_KEY[trial.event_class]
    window = _ksdinfo_window(trial)
    run.observe(reference_window=window)
    print(f"{_REFERENCE_WINDOW_PREFIX}{window['f_dt']}-{window['t_dt']}")
    outcome, _attempts, _retried = _retry_once(
        lambda: _ksdinfo_outcome(
            session, auth, base_url, pacer, ksd_key, trial.symbol, window
        ),
        _record_retry(run, retries),
        pacer,
        wait_s=trial.effective_poll_ms / 1000.0,
        phase="reference_check",
    )
    status, parsed = outcome.http_status, outcome.parsed
    transient = _transient_kind(outcome.kind)
    if transient is not None:
        run.error(
            f"reference-check call failed twice in a row with a transient "
            f"{transient} error; stopping"
        )
        print(f"{_REFERENCE_STATUS_PREFIX}{_REF_TRANSIENT_STOP}:{transient}")
        raise _StopRun
    if outcome.kind == _BAL_RATE_LIMITED:
        run.error(
            f"rate-limited on reference-check call (status={status}); "
            "stopping — no retry"
        )
        print(f"{_REFERENCE_STATUS_PREFIX}{_REF_RATE_LIMITED}:http_{status}")
        raise _RateLimited
    rt_cd = str(parsed.get("rt_cd") or "").strip()
    if rt_cd != "0":
        detail = f"{rt_cd}/{parsed.get('msg_cd')}:{parsed.get('msg1')}"
        key = "mock_reference_support" if not trial.is_real else "reference_check_error"
        run.observe(**{key: f"UNSUPPORTED_OR_ERROR:{detail}"})
        token = _reference_refusal_status(status, parsed)
        if token == _REF_ERROR:
            run.error(
                f"reference-check call did not complete: http={status} "
                f"body={_one_line(detail)}"
            )
        print(f"{_REFERENCE_STATUS_PREFIX}{token}:http_{status}/{_one_line(detail)}")
        return
    rows = parsed.get("output1")
    rows = rows if isinstance(rows, list) else []
    run.observe(reference_dates=rows)
    if not trial.is_real:
        run.observe(mock_reference_support="SUPPORTED")
    _print_reference_rows(rows)


_REFERENCE_WINDOW_PREFIX = "REFERENCE_WINDOW="
_REFERENCE_STATUS_PREFIX = "REFERENCE_STATUS="
_REFERENCE_ROWS_PREFIX = "REFERENCE_ROWS="
_REFERENCE_ROW_PREFIX = "REFERENCE_ROW="

_REF_OK = "OK"
_REF_NO_ROWS = "NO_ROWS"
_REF_UNSUPPORTED = "UNSUPPORTED"
_REF_ERROR = "ERROR"
_REF_TRANSIENT_STOP = "TRANSIENT_STOP"
_REF_RATE_LIMITED = "RATE_LIMITED"
REFERENCE_STATUSES: tuple[str, ...] = (
    _REF_OK,
    _REF_NO_ROWS,
    _REF_UNSUPPORTED,
    _REF_ERROR,
    _REF_TRANSIENT_STOP,
    _REF_RATE_LIMITED,
)


def _reference_refusal_status(http_status: int | None, parsed: dict[str, Any]) -> str:
    """``UNSUPPORTED`` or ``ERROR`` for a ksdinfo answer with ``rt_cd != '0'``."""
    answered = http_status == 200 and "rt_cd" in parsed
    return _REF_UNSUPPORTED if answered else _REF_ERROR


_REFERENCE_FIELD_MAX_CHARS = 16


def _reference_field(value: Any) -> str:
    """One broker-supplied date, fit for the anchored line the runner parses."""
    text = str(value if value is not None else "")
    return "".join(ch for ch in text if ch.isdigit())[:_REFERENCE_FIELD_MAX_CHARS]


def _print_reference_rows(rows: list[Any]) -> None:
    """``REFERENCE_ROWS=<n>`` then one ``REFERENCE_ROW=`` line per row."""
    emitted = [
        f"{_reference_field(row.get('record_date'))}|"
        f"{_reference_field(row.get('divi_pay_dt'))}"
        for row in rows
        if isinstance(row, dict)
    ]
    print(f"{_REFERENCE_STATUS_PREFIX}{_REF_OK if emitted else _REF_NO_ROWS}")
    print(f"{_REFERENCE_ROWS_PREFIX}{len(emitted)}")
    for line in emitted:
        print(f"{_REFERENCE_ROW_PREFIX}{line}")


_REFERENCE_OBSERVATION_KEYS: tuple[str, ...] = (
    "reference_dates",
    "reference_window",
    "mock_reference_support",
    "reference_check_error",
)


def _adopt_reference_rows(run: ProbeRun, trial: _Trial) -> None:
    """Copy a ``--reference-only`` artifact's reference observations into this"""
    import json
    from pathlib import Path

    source = Path(trial.reference_rows_from)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProbeError(
            f"--reference-rows-from {trial.reference_rows_from!r} could not be "
            f"read as a probe artifact: {exc}"
        ) from None
    if not isinstance(payload, dict):
        raise ProbeError(
            f"--reference-rows-from {trial.reference_rows_from!r} is not a "
            "probe artifact object"
        )
    observations = payload.get("observations")
    adopted: dict[str, Any] = {}
    for entry in observations if isinstance(observations, list) else []:
        if not isinstance(entry, dict):
            continue
        for key in _REFERENCE_OBSERVATION_KEYS:
            if key in entry:
                adopted[key] = entry[key]
    if "reference_dates" not in adopted:
        raise ProbeError(
            f"--reference-rows-from {trial.reference_rows_from!r} carries no "
            "reference_dates observation — it is not a completed "
            "--reference-only artifact, and this run would otherwise poll a "
            "window while claiming reference data it does not have."
        )
    run.observe(**adopted)
    run.observe(
        reference_rows_provenance=(
            "observations.reference_dates (and the reference_window / "
            "mock_reference_support beside it) were ADOPTED VERBATIM from "
            f"{payload.get('artifact_id', source.name)}, a --reference-only "
            "run made by this trial's runner before polling started. This run "
            "sent no ksdinfo GET of its own: the pre-check already made it, "
            "and asking twice adds a broker call and one more place a "
            "transient can stop the trial (#831 round 2, F5)."
        )
    )


def _do_reference_only(
    run: ProbeRun,
    session: Any,
    auth: Any,
    base_url: str,
    pacer: _Pacer,
    trial: _Trial,
    retries: _Retries,
) -> None:
    """``--reference-only`` (#830): the ksdinfo GET, and nothing else."""
    run.observe(
        reference_only=True,
        reference_only_note=(
            "--reference-only: ONE ksdinfo GET for --event-class "
            f"{trial.event_class}, no balance call, no holding requirement, no "
            "polling. --window-s is accepted and IGNORED (nothing is polled); "
            "--poll-ms is NOT ignored — it is the wait before the single "
            "retry of a transient failure, the same interval every other "
            "phase uses. An operator time is accepted even when it is in the "
            "FUTURE — nothing is paired against it; it only anchors the "
            "ksdinfo F_DT/T_DT window (observations.reference_window)."
        ),
    )
    try:
        _do_reference_check(run, session, auth, base_url, pacer, trial, retries)
    except _StopRun:
        return
    finally:
        for leg in _observable_leg_names(trial.event_class):
            run.skip(
                f"legs.{trial.event_class}.{leg}",
                "REFERENCE_ONLY — --reference-only looks the event up in the "
                "ksdinfo reference table and stops. This leg was not "
                "OBSERVED, not CENSORED and not ABORTED: no balance was read, "
                "so no window ran and nothing at all was observed about it. "
                "See observations.reference_dates for what the broker's "
                "reference table says, and run the probe WITHOUT "
                "--reference-only to measure a reflection latency.",
            )
        run.measure("leg_provenance_class", "NOT_MEASURED")
        run.measure(
            "no_aggregate_scalar_note",
            "B_non_trade_event_detect / B_non_trade_reconcile are never "
            "written as a single scalar by this probe, and a --reference-only "
            "run measures no latency at all — it records the broker's "
            "declared CA dates, nothing more. Both VP-002 keys stay "
            "NOT_ESTABLISHED.",
        )


class _StopRun(ProbeError):
    """Signal: the reason is ALREADY recorded via ``run.error``; stop and write"""


class _RateLimited(_StopRun):
    """Signal: a rate limit was already recorded via ``run.error``; stop, no retry."""


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
    pacer: _Pacer,
    retries: _Retries,
) -> tuple[dict[str, dict[str, Any]], int, int, float, str | None]:
    """Poll balance until every leg is observed or ``--window-s`` expires."""
    pending = {name: (t0_field, t0_dt) for name, t0_field, t0_dt in legs}
    found: dict[str, dict[str, Any]] = {}
    poll_pacer = pacer.derive(trial.effective_poll_ms / 1000.0)
    polls_used = 0
    polls_completed = 0
    stop_reason: str | None = None
    started_at = time.monotonic()
    deadline = started_at + trial.window_s
    on_transient = _record_retry(run, retries)

    def read_balance_now() -> _Outcome:
        return _balance_outcome(
            session, auth, base_url, tr_id, creds, trial.symbol, poll_pacer
        )

    def window_still_open() -> bool:
        return time.monotonic() < deadline

    while pending and window_still_open():
        outcome, attempts, retried = _retry_once(
            read_balance_now,
            on_transient,
            poll_pacer,
            wait_s=trial.effective_poll_ms / 1000.0,
            phase="poll",
            poll_index_base=polls_used,
            can_retry=window_still_open,
        )
        status, http_status, parsed, text = (
            outcome.kind,
            outcome.http_status,
            outcome.parsed,
            outcome.text,
        )
        qty, cash = outcome.payload
        polls_used += attempts
        transient = _transient_kind(status)
        if transient is not None and not retried:
            break
        if status in (_BAL_RATE_LIMITED, _BAL_REJECTED, _BAL_CAPPED) or transient:
            run.observe(
                poll_stop_evidence={
                    "poll_index": polls_used,
                    **_call_evidence(
                        status_kind=status or "",
                        http_status=http_status,
                        parsed=parsed,
                        text=text,
                    ),
                }
            )
        if status == _BAL_RATE_LIMITED:
            run.error(f"rate-limited during poll #{polls_used}; stopping — no retry")
            stop_reason = _STOP_RATE_LIMITED
            break
        if transient is not None:
            run.error(
                f"poll #{polls_used} failed twice in a row with a transient "
                f"{transient} error (one retry, "
                f"{trial.effective_poll_ms / 1000.0}s apart); stopping"
            )
            stop_reason = (
                _STOP_TRANSIENT
                if transient == _TRANSIENT_TRANSPORT
                else _STOP_RATE_LIMITED
            )
            break
        if status == _BAL_REJECTED:
            run.error(
                f"poll #{polls_used} rejected: rt_cd={parsed.get('rt_cd')!r} "
                f"msg_cd={parsed.get('msg_cd')!r}"
            )
            stop_reason = _STOP_REJECTED
            break
        if status == _BAL_CAPPED:
            run.error(
                f"poll #{polls_used} hit the {_MAX_BALANCE_PAGES}-page cap "
                f"without finding {trial.symbol}'s row — INCONCLUSIVE, stopping "
                "(finding F6: a truncated read is not evidence of no change)."
            )
            stop_reason = _STOP_PAGE_CAP
            break

        polls_completed += 1
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
                    "attribution": "UNVERIFIED_ACCOUNT_LEVEL_CHANGE",
                    f"baseline_{name if name == 'quantity' else 'cash'}": baseline,
                    f"observed_{name if name == 'quantity' else 'cash'}": observed,
                }
                found[name] = record
                run.measure(f"legs.{trial.event_class}.{name}", record)

    return (
        found,
        polls_used,
        polls_completed,
        round(time.monotonic() - started_at, 3),
        stop_reason,
    )


def _finalize(
    run: ProbeRun,
    trial: _Trial,
    legs: list[tuple[str, str, datetime]],
    found: dict[str, dict[str, Any]],
    polls_used: int,
    polls_completed: int,
    polled_elapsed_s: float,
    stop_reason: str | None,
) -> None:
    """Build ``class_leg_table`` — the ONLY aggregate this probe emits — and"""
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
                "status": "CENSORED" if stop_reason is None else "ABORTED",
                "window_s": trial.window_s,
                "polled_elapsed_s": polled_elapsed_s,
            }
            if stop_reason is None:
                run.skip(
                    f"legs.{trial.event_class}.{name}",
                    "CENSORED — no broker-reflect observed within "
                    f"--window-s={trial.window_s}s (polls_used={polls_used}). "
                    "Absence of an observed reflection is not evidence of zero "
                    "latency (VP-002:772 'observed 0 != 0').",
                )
            else:
                row["stop_reason"] = stop_reason
                row["polls_used"] = polls_used
                row["polls_completed"] = polls_completed
                run.skip(
                    f"legs.{trial.event_class}.{name}",
                    f"ABORTED — polling stopped early (stop_reason={stop_reason}, "
                    f"polls_used={polls_used} (attempts), "
                    f"polls_completed={polls_completed}); polling ran "
                    f"{polled_elapsed_s}s, so --window-s={trial.window_s}s did "
                    "NOT elapse. This is not even a censored observation: the "
                    "window never ran, so nothing at all was observed about this "
                    "leg. See the poll_stop_evidence observation for the broker's "
                    "verbatim response.",
                )
        class_leg_table.append(row)

    run.observe(
        attribution_caveat=(
            "OBSERVED rows in class_leg_table are UNVERIFIED_ACCOUNT_LEVEL_CHANGE: "
            "detected by TIMING ALONE (a balance change during the polling "
            "window), not by any broker-side reference to this corporate "
            "action on the row — a concurrent order fill, deposit/withdrawal, "
            "or unrelated corporate action on the SAME account within the "
            "window is indistinguishable from the event being measured "
            "(runbook §5.8 prerequisite: operator attests no such activity)."
        )
    )
    run.measure("class_leg_table", class_leg_table)
    run.measure("polls_used", polls_used)
    run.measure("polls_completed", polls_completed)
    run.measure("polled_elapsed_s", polled_elapsed_s)
    run.measure("poll_interval_ms_effective", trial.effective_poll_ms)
    run.measure(
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


def _open_broker_session(
    *,
    is_real: bool,
    token_cache_dir: Any,
    on_credentials: Callable[[Any], None] | None = None,
) -> tuple[Any, Any, str, str, Any]:
    """Resolve credentials and open the ONE broker session shape this module"""
    warn_shared_token_cache()
    creds = resolve_credentials("stock", is_real=is_real)
    require_account(creds)
    if on_credentials is not None:
        on_credentials(creds)

    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()
    base_url = REAL_BASE_URL if is_real else MOCK_BASE_URL
    tr_id = _STOCK_TR_REAL if is_real else _STOCK_TR_MOCK
    return session, auth, base_url, tr_id, creds


def _build_run(spec: ProbeSpec, args: argparse.Namespace, trial: _Trial) -> ProbeRun:
    """Construct the artifact and record the attestation — before any network call."""
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
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
    if trial.t0_offsets:
        run.observe(t0_offsets=dict(trial.t0_offsets))
        for flag_name, offset in trial.t0_offsets.items():
            if offset != _KST_OFFSET:
                print(
                    f"  WARNING: --{flag_name.replace('_', '-')} offset {offset} "
                    f"is not KST ({_KST_OFFSET}) — recorded verbatim, NOT "
                    "normalized. Every other operator time and the poll clock "
                    "are UTC/KST; mixing offsets miscomputes latency_ms."
                )
    return run


def _dry_run_would_send(trial: _Trial) -> str:
    tr_id = _STOCK_TR_MOCK if not trial.is_real else _STOCK_TR_REAL
    if trial.reference_only:
        ksd_tr, ksd_path = _KSDINFO_TRS[_EVENT_CLASS_KSDINFO_KEY[trial.event_class]]
        window = _ksdinfo_window(trial)
        return (
            f"one read-only ksdinfo GET for {trial.symbol} ({ksd_tr} {ksd_path}, "
            f"F_DT={window['f_dt']} T_DT={window['t_dt']}, anchored on "
            f"{window['anchor_source']}) and NOTHING else — no balance call, no "
            "polling (--reference-only)"
        )
    return (
        f"one read-only GET balance snapshot for {trial.symbol} ({tr_id}); "
        "optionally one ksdinfo reference-check GET; then a bounded poll loop "
        f"of balance GETs at effective interval {trial.effective_poll_ms:.0f}ms "
        f"up to --window-s={trial.window_s}s"
    )


def probe_pca(args: argparse.Namespace) -> ProbeRun:
    """P-CA CORPORATE_ADMINISTRATIVE_EVENTS — opportunistic GET-only reflection latency."""
    spec = get("P-CA")
    trial = _parse_trial(args)
    run = _build_run(spec, args, trial)

    if not args.confirm:
        dry_run_banner(spec)
        run.observe(would_send=_dry_run_would_send(trial))
        return run

    if trial.reference_rows_from:
        _adopt_reference_rows(run, trial)

    def _record_credentials(resolved: Any) -> None:
        run.credentials = resolved.describe()

    session, auth, base_url, tr_id, creds = _open_broker_session(
        is_real=trial.is_real,
        token_cache_dir=args.token_cache_dir,
        on_credentials=_record_credentials,
    )
    pacer = _Pacer(trial.pace_s)
    retries = _Retries(run)

    try:
        if trial.reference_only:
            _do_reference_only(run, session, auth, base_url, pacer, trial, retries)
            return run

        baseline = _do_baseline(
            run,
            session,
            auth,
            base_url,
            tr_id,
            creds,
            pacer,
            trial.symbol,
            retries,
            trial.effective_poll_ms / 1000.0,
        )
        if baseline is None:
            return run
        baseline_qty, baseline_cash = baseline

        if trial.reference_check and not trial.reference_rows_from:
            try:
                _do_reference_check(run, session, auth, base_url, pacer, trial, retries)
            except _StopRun:
                return run

        if trial.event_class == "cash_dividend":
            run.skip(
                "legs.cash_dividend.ex",
                "NOT_OBSERVABLE_ON_BALANCE_SURFACE — 기준가 조정은 잔고 TR로 "
                "관측 불가(N-19 §2.3: 주식잔고조회 72필드 중 가격 필드 없음); "
                "현금 leg만 관측 가능.",
            )

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

        found, polls_used, polls_completed, polled_elapsed_s, stop_reason = _poll_loop(
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
            pacer,
            retries,
        )
        _finalize(
            run,
            trial,
            legs,
            found,
            polls_used,
            polls_completed,
            polled_elapsed_s,
            stop_reason,
        )
    finally:
        session.close()
    return run


def add_ca_args(parser: argparse.ArgumentParser) -> None:
    parser.set_defaults(asset="stock")
    parser.add_argument(
        "--env",
        choices=("mock", "real"),
        default="mock",
        help="Environment to read (default 'mock', §5.2 M-3). MOCK_VTS is never REAL_PROD-citable (§6.2).",
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
        help="ISO-8601 KST — 배당락/권리락. Validated only, never paired with a leg (N-19 §2.3 — 기준가 조정은 잔고 TR로 관측 불가).",
    )
    parser.add_argument(
        "--effective-time",
        default="",
        help="ISO-8601 KST — 신주 효력(상장/등록)일. t0 for the quantity leg, every class but cash_dividend.",
    )
    parser.add_argument(
        "--payable-time",
        default="",
        help="ISO-8601 KST — 지급일. t0 for the cash leg (dnca_tot_amt change).",
    )
    parser.add_argument(
        "--settlement-time",
        default="",
        help="ISO-8601 KST — 결제 시점. Recorded verbatim, never measured (futures-only leg; --asset futures is refused).",
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=5000.0,
        help="Requested polling interval (default 5000ms), floored by --pace-s.",
    )
    parser.add_argument(
        "--window-s",
        type=float,
        default=3600.0,
        help="Max polling seconds per trial (default 3600). Expiry ⇒ CENSORED, never a value.",
    )
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=f"Min interval between ANY two broker calls (default {DEFAULT_PACE_S}s).",
    )
    parser.add_argument(
        "--reference-check",
        action="store_true",
        help="Also GET the ksdinfo TR for --event-class BEFORE polling (N-19 §3 MOCK feasibility observation).",
    )
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help=(
            "Do ONLY the ksdinfo reference GET: no balance call, no holding "
            "requirement, no polling. A FUTURE --payable-time/--ex-time/"
            "--effective-time is accepted in this mode (nothing is paired "
            "against it; it anchors the F_DT/T_DT window). Implies "
            "--reference-check; --window-s/--poll-ms are ignored."
        ),
    )
    parser.add_argument(
        "--reference-from",
        default="",
        help=(
            "YYYYMMDD — override the ksdinfo F_DT. The derived window is "
            f"anchor-{_KSDINFO_LOOKBACK_DAYS}d and filters on the row's 기준일, "
            "which precedes 지급일 by an issuer-specific gap."
        ),
    )
    parser.add_argument(
        "--reference-to",
        default="",
        help=f"YYYYMMDD — override the ksdinfo T_DT (derived: anchor+{_KSDINFO_LOOKAHEAD_DAYS}d).",
    )
    parser.add_argument(
        "--reference-rows-from",
        default="",
        help=(
            "Path to a --reference-only artifact. Adopt its reference_dates / "
            "reference_window / mock_reference_support observations VERBATIM "
            "instead of sending the ksdinfo GET again — for a runner that "
            "already made the call in a pre-check. Mutually exclusive with "
            "the GET: --reference-check becomes a no-op when this is given."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))


_HELD_PREFIX = "HELD="
_HOLDING_FAILED_PREFIX = "HOLDING_QUERY_FAILED="
_POLICY_PREFIX = "POLICY_VERSION="


def _holding_failure_detail(outcome: _Outcome) -> str:
    """The short reason after the status kind."""
    if outcome.kind == _BAL_CAPPED:
        return f"page_cap:{_MAX_BALANCE_PAGES}"
    rt_cd = str(outcome.parsed.get("rt_cd") or "").strip()
    msg_cd = str(outcome.parsed.get("msg_cd") or "").strip()
    if rt_cd != "0" and msg_cd:
        return _one_line(msg_cd)
    return _one_line((outcome.text or "").split(":", 1)[0]) or "unknown"


def _one_line(text: str) -> str:
    """Broker text, fit for the single anchored line the runner parses."""
    return " ".join((text or "").split())[:_BODY_EXCERPT_MAX_CHARS]


def _print_holding_transient(
    wait_s: float,
) -> Callable[[dict[str, Any], str], None]:
    """The pre-flight's ``on_transient``: say what happened on stderr, and say"""

    def _print(evidence: dict[str, Any], kind: str) -> None:
        detail = evidence.get("body_excerpt") or evidence.get("msg_cd") or "no detail"
        tail = (
            f"retrying once in {wait_s}s"
            if evidence.get("retried")
            else "no retry left"
        )
        print(f"holding check: transient {kind} ({detail}); {tail}", file=sys.stderr)

    return _print


def check_holding(argv: list[str] | None = None) -> int:
    """Answer "is ``--symbol`` held, and do we actually KNOW?" for a runner."""
    parser = argparse.ArgumentParser(
        prog="python -m tools.broker_probes.probes_ca",
        description=(
            "P-CA pre-flight: is --symbol held? Prints HELD=<n> or "
            "HOLDING_QUERY_FAILED=<kind>:<detail>. GET-only, same allowlist "
            "as the probe."
        ),
    )
    parser.add_argument(
        "--check-holding",
        action="store_true",
        required=True,
        help="Required — this module's only command line is the holding check.",
    )
    parser.add_argument("--env", choices=("mock", "real"), required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--token-cache-dir", default=None)
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=f"Min interval between calls (default {DEFAULT_PACE_S}s).",
    )
    parser.add_argument(
        "--retry-wait-ms",
        type=float,
        default=None,
        help=(
            "Wait before the single retry, in ms. Pass the trial's --poll-ms: "
            "a ledger throttle (EGW00215) is answered by waiting a whole "
            "polling interval, not by asking again at the per-second cadence "
            "that just tripped it. Defaults to --pace-s, which is only right "
            "when there is no trial interval to borrow."
        ),
    )
    args = parser.parse_args(argv)

    try:
        session, auth, base_url, tr_id, creds = _open_broker_session(
            is_real=args.env == "real", token_cache_dir=args.token_cache_dir
        )
    except ProbeError as exc:
        print(f"{_HOLDING_FAILED_PREFIX}PRECONDITION:{exc}")
        return 2

    pacer = _Pacer(args.pace_s)
    retry_wait_s = (
        args.pace_s if args.retry_wait_ms is None else args.retry_wait_ms / 1000.0
    )
    print(f"{_POLICY_PREFIX}{POLICY_VERSION}")

    try:
        outcome, _attempts, _retried = _retry_once(
            lambda: _balance_outcome(
                session, auth, base_url, tr_id, creds, args.symbol, pacer
            ),
            _print_holding_transient(retry_wait_s),
            pacer,
            wait_s=retry_wait_s,
            phase="holding_check",
        )
    finally:
        session.close()

    if outcome.kind != _BAL_OK:
        print(
            f"{_HOLDING_FAILED_PREFIX}{outcome.kind}:"
            f"{_holding_failure_detail(outcome)}"
        )
        return 1
    qty, _cash = outcome.payload
    print(f"{_HELD_PREFIX}{qty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(check_holding())
