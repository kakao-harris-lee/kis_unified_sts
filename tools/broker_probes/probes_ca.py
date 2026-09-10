"""P-CA — corporate-action reflection probe. READ-ONLY BY CONSTRUCTION, GET-only.

Why this probe exists (``docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md``
§5.2): it is the opportunistic half of the two-probe pair feeding the
``B_non_trade_event_detect`` / ``B_non_trade_reconcile`` adjacent bound keys
(``registry.py::ADJACENT_BOUND_KEYS``). N-19
(``docs/plans/2026-09-10-tos-p02-n19-ca-spec-collation.md``) is the documentary
half: KIS exposes 12 GET-only 예탁원정보(ksdinfo) reference TRs (§2.1) carrying
CA *schedule* fields, but none of them — nor any field of the 주식잔고조회
balance TR (``TTTC8434R``/``VTTC8434R``) — documents WHEN a CA is reflected in
balance/position. ``hldg_qty`` (quantity) and ``dnca_tot_amt`` (예수금총금액 —
cash/deposit total, N-19 §2.3) are the only INDIRECT observation surface: this
probe polls them.

ADR-002-010 §8:171 forbids collapsing the seven CA times into one "corporate
action date" (``tos/src/tos/nontrade/records.py:359-366`` keeps them separate).
This probe honours that: it pairs each OBSERVABLE leg with the one of the seven
times its rationale calls for (§5.2 table / :func:`_legs_to_track`) and never
emits a single scalar — ``measurements.class_leg_table`` is the only aggregate
this probe writes. Both VP-002 keys stay ``NOT_ESTABLISHED``, a Bounds-Approver
judgement (``common.py::ProbeRun``: "Probes measure; humans approve.").

Falsification-first (§5.2, §8.4 / VP-002:772 "observed 0 != 0"): an unobserved
leg within the polling window is CENSORED, never a zero latency.

Attribution caveat (independent review finding F3): a detected balance change
is attributed to the CA being measured by TIMING ALONE — the row carries no
broker-side reference to the specific event. See ``attribution_caveat``
(:func:`_finalize`) and runbook §5.8.

Safety model — strictly GET-only, and structurally so (mirrors P-BAL):

* :data:`ALLOWLIST` is the complete set of calls this module may ever make: the
  two balance TRs (real/mock) plus the 12 ksdinfo reference TRs. No
  order/cancel/amend path exists anywhere in this file.
* :func:`_get` is the ONLY transport and calls
  :func:`~tools.broker_probes.common.assert_read_only_call` before the session
  is touched.
* This module does not import :mod:`tools.broker_probes.probes_order` or
  :mod:`tools.broker_probes.probes_real_order` (both carry order paths) —
  ``tests/tools/test_broker_probes_ca.py`` pins this against the module's own
  AST, as ``test_broker_probes_balance.py`` does for P-BAL.

Futures are refused outright (§5.2 prerequisite 4): the mock server does not
serve a futures balance query at all (``shared/kis/client.py:1031`` NOTE, guard
``:1047``), and the real futures account is never funded with margin
(CLAUDE.md Non-Negotiable Rules).

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


def _reference_now() -> datetime:
    """'Now' for the future-time check only (:func:`_parse_operator_time`) —
    a SEPARATE seam from :func:`_now` so a test's scripted poll clock is never
    silently consumed by argument validation that runs before polling starts.
    """
    return datetime.now(UTC)


#: KST — the offset every ``--ex-time``/``--effective-time``/``--payable-time``
#: help string promises. A different (still valid) offset is accepted, never
#: silently treated as KST (finding F8) — see :func:`_parse_operator_time`.
_KST_OFFSET = "+09:00"


def _offset_str(value: datetime) -> str:
    """``value``'s UTC offset as ``+HH:MM``/``-HH:MM`` — ``strftime('%z')`` with
    the colon ``isoformat()`` already uses elsewhere in this module, so the two
    representations of the same offset never disagree in an artifact."""
    offset = value.utcoffset()
    total_minutes = int(offset.total_seconds() // 60) if offset else 0
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    return f"{sign}{total_minutes // 60:02d}:{total_minutes % 60:02d}"


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
    #: Per-flag UTC offset actually supplied (e.g. ``{"effective_time": "+09:00"}``)
    #: — F8: recorded and warned on when != KST, never silently normalized.
    t0_offsets: dict[str, str]


def _parse_operator_time(raw: str, flag: str) -> tuple[datetime | None, str | None]:
    """Parse one operator time. Returns ``(value, offset)``.

    Two preconditions beyond "is it ISO-8601" (independent review F1/F2): a
    naive value would crash ``now - t0_dt`` in :func:`_poll_loop` AFTER the
    window is spent — reject it here, before any network call; a future value
    would record a negative latency — reject it too, against
    :func:`_reference_now`.
    """
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
    if parsed > now:
        raise ProbeError(
            f"{flag} is in the future ({raw!r} > {now.isoformat()}) — P-CA "
            "pairs a poll against a time that has ALREADY passed; a future t0 "
            "would record a negative latency."
        )
    return parsed, _offset_str(parsed)


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

    t0_offsets: dict[str, str] = {}
    ex_time, ex_offset = _parse_operator_time(getattr(args, "ex_time", ""), "--ex-time")
    effective_time, effective_offset = _parse_operator_time(
        getattr(args, "effective_time", ""), "--effective-time"
    )
    payable_time, payable_offset = _parse_operator_time(
        getattr(args, "payable_time", ""), "--payable-time"
    )
    for flag_name, offset in (
        ("ex_time", ex_offset),
        ("effective_time", effective_offset),
        ("payable_time", payable_offset),
    ):
        if offset is not None:
            t0_offsets[flag_name] = offset

    return _Trial(
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
        reference_check=bool(getattr(args, "reference_check", False)),
        t0_offsets=t0_offsets,
    )


def _legs_to_track(trial: _Trial) -> list[tuple[str, str, datetime]]:
    """(leg name, t0 field name, t0 instant) for every leg ACTUALLY observable
    on the balance surface. ``cash_dividend``'s 기준가-조정(ex) leg is a PRICE
    adjustment — N-19 §2.3 confirms no balance field carries a price, so it is
    NEVER tracked here (finding F4; :func:`probe_pca` emits an explicit
    ``NOT_OBSERVABLE_ON_BALANCE_SURFACE`` skip for it instead of a silent
    CENSOR). Every other class's quantity leg (수량 변환) pairs with
    ``effective_time``. Cash leg always pairs with ``payable_time``.
    """
    legs: list[tuple[str, str, datetime]] = []
    if trial.event_class != "cash_dividend" and trial.effective_time is not None:
        legs.append(("quantity", "effective_time", trial.effective_time))
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


def _balance_params(creds: Any, *, fk: str = "", nk: str = "") -> dict[str, str]:
    """Mirror the runtime's stock balance params (client.py:921-933), with the
    continuation keys USABLE (finding F6 — see :func:`_read_balance`)."""
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


def _find_symbol_qty(rows: list[Any], symbol: str) -> int | None:
    """``hldg_qty`` for ``symbol``'s row on THIS page, or ``None`` if the row is
    not on this page — distinct from "found, and it is 0" (finding F6)."""
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


#: Cap on balance pages walked per read (baseline snapshot or each poll).
#: Finding F6: a single-page read cannot distinguish "not held" from "held on
#: a later page" (shared/kis/client.py's own defect, measured by P-BAL). A
#: single-symbol lookup needs far fewer pages than P-BAL's exhaustive walk;
#: hitting the cap is an ERROR (:data:`_BAL_CAPPED`), never "no holding".
_MAX_BALANCE_PAGES = 5

_BAL_OK = "OK"
_BAL_RATE_LIMITED = "RATE_LIMITED"
_BAL_REJECTED = "REJECTED"
_BAL_CAPPED = "CAPPED"


def _read_balance(
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    symbol: str,
    pacer: _Pacer,
) -> tuple[str, int, float, dict[str, Any], str]:
    """Walk balance pages (capped at :data:`_MAX_BALANCE_PAGES`) until
    ``symbol``'s row is found or the broker signals end-of-set. Returns
    ``(status, qty, cash, parsed_last_page, text_last_page)`` where ``status``
    is one of :data:`_BAL_OK` / :data:`_BAL_RATE_LIMITED` / :data:`_BAL_REJECTED`
    / :data:`_BAL_CAPPED` (F6: capped ⇒ INCONCLUSIVE, never "not held")."""
    fk = nk = ""
    cash = 0.0
    parsed: dict[str, Any] = {}
    text = ""
    for _page in range(_MAX_BALANCE_PAGES):
        pacer.wait()
        status, parsed, text, _elapsed_ms = _get(
            session,
            auth,
            base_url=base_url,
            path=_STOCK_BALANCE_PATH,
            tr_id=tr_id,
            params=_balance_params(creds, fk=fk, nk=nk),
        )
        if is_rate_limited(status, parsed, text):
            return _BAL_RATE_LIMITED, 0, cash, parsed, text
        rt_cd = str(parsed.get("rt_cd") or "").strip()
        if rt_cd != "0":
            return _BAL_REJECTED, 0, cash, parsed, text
        rows = parsed.get("output1")
        rows = rows if isinstance(rows, list) else []
        cash = _read_cash_total(parsed)
        found_qty = _find_symbol_qty(rows, symbol)
        if found_qty is not None:
            return _BAL_OK, found_qty, cash, parsed, text
        next_fk = str(parsed.get("ctx_area_fk100") or "").strip()
        next_nk = str(parsed.get("ctx_area_nk100") or "").strip()
        if not next_fk and not next_nk:
            # Broker end-of-set and the symbol was never on any page walked —
            # genuinely absent, not truncated.
            return _BAL_OK, 0, cash, parsed, text
        fk, nk = next_fk, next_nk
    return _BAL_CAPPED, 0, cash, parsed, text


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
    """Paced, paginated balance snapshot (:func:`_read_balance`). Returns
    ``(qty, cash)`` or ``None`` if the run should stop here (rate-limited,
    rejected, capped, or no holding)."""
    status, qty, cash, parsed, _text = _read_balance(
        session, auth, base_url, tr_id, creds, symbol, pacer
    )
    run.observe(baseline_call={"status_kind": status, "rt_cd": parsed.get("rt_cd")})
    if status == _BAL_RATE_LIMITED:
        run.error("rate-limited on baseline balance call; stopping — no retry")
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
        polls_used += 1
        status, qty, cash, parsed, _text = _read_balance(
            session, auth, base_url, tr_id, creds, trial.symbol, poll_pacer
        )
        if status == _BAL_RATE_LIMITED:
            run.error(f"rate-limited during poll #{polls_used}; stopping — no retry")
            break
        if status == _BAL_REJECTED:
            run.error(
                f"poll #{polls_used} rejected: rt_cd={parsed.get('rt_cd')!r} "
                f"msg_cd={parsed.get('msg_cd')!r}"
            )
            break
        if status == _BAL_CAPPED:
            run.error(
                f"poll #{polls_used} hit the {_MAX_BALANCE_PAGES}-page cap "
                f"without finding {trial.symbol}'s row — INCONCLUSIVE, stopping "
                "(finding F6: a truncated read is not evidence of no change)."
            )
            break

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
                    # F3: TIMING ALONE — no broker-side CA reference on the row.
                    "attribution": "UNVERIFIED_ACCOUNT_LEVEL_CHANGE",
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
            # No "candidate_only" here (F5): that flag means "a value exists,
            # unapproved" — a CENSORED row has NO value to flag as a candidate.
            row = {
                "event_class": trial.event_class,
                "leg": name,
                "t0_field": t0_field,
                "t0": t0_dt.isoformat(),
                "status": "CENSORED",
                "window_s": trial.window_s,
            }
            run.skip(
                f"legs.{trial.event_class}.{name}",
                "CENSORED — no broker-reflect observed within "
                f"--window-s={trial.window_s}s (polls_used={polls_used}). "
                "Absence of an observed reflection is not evidence of zero "
                "latency (VP-002:772 'observed 0 != 0').",
            )
        class_leg_table.append(row)

    run.observe(
        # F3: OBSERVED rows are timing-only attribution — see each row's
        # "attribution": "UNVERIFIED_ACCOUNT_LEVEL_CHANGE" (_poll_loop). This is
        # the one-sentence artifact-level caveat an approval reader must see
        # before citing any OBSERVED row as this CA's effect.
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
    run.measure("poll_interval_ms_effective", trial.effective_poll_ms)
    run.measure(
        # Supplements the framework's own mode/errors-only provenance_class
        # (common.py::ProbeRun.to_dict) with a per-leg signal: a window that
        # legitimately CENSORS every leg is neither an error nor a measurement.
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
    return (
        f"one read-only GET balance snapshot for {trial.symbol} ({tr_id}); "
        "optionally one ksdinfo reference-check GET; then a bounded poll loop "
        f"of balance GETs at effective interval {trial.effective_poll_ms:.0f}ms "
        f"up to --window-s={trial.window_s}s"
    )


def probe_pca(args: argparse.Namespace) -> ProbeRun:
    """P-CA CORPORATE_ADMINISTRATIVE_EVENTS — opportunistic GET-only reflection latency.

    Procedure (design doc §5.2 ⑤): baseline balance snapshot -> optional
    ``--reference-check`` -> operator ``[Enter]`` prompt (P-EXT form) -> bounded
    poll loop (:func:`_poll_loop`) -> per-leg OBSERVED/CENSORED classification
    (:func:`_finalize`). No aggregate scalar is ever written for
    ``B_non_trade_event_detect``/``B_non_trade_reconcile`` — a Bounds-Approver
    decision this probe cannot make.
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

        if trial.event_class == "cash_dividend":
            # F4: the 기준가-조정(ex) leg is a PRICE adjustment — never CENSOR
            # it silently (:func:`_legs_to_track` never tracks it at all); say
            # explicitly why it is unobservable, every cash_dividend run.
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


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
