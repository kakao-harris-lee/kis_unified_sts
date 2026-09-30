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
leg is never a zero latency. It is CENSORED when the polling window actually
elapsed, and ABORTED when polling stopped early (rate limit, rejection, page
cap) — two different epistemic states that must never share a label, because a
CENSORED row asserts an absence over the full window and an ABORTED row asserts
nothing at all (2026-09-17 incident, :func:`_finalize`).

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

This module has a SECOND entry point, :func:`check_holding`
(``python -m tools.broker_probes.probes_ca --check-holding``): the runner's
pre-flight "is the symbol held, and do we actually KNOW?" gate. It reuses
:func:`_read_balance` and therefore the same allowlist, pagination and
classification — see its own docstring for why the runtime client could not
answer that question.

Nothing in this module can mutate an order, in mock or in real.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Callable
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

    def derive(self, interval_s: float) -> _Pacer:
        """A pacer on a new interval that still owes THIS pacer's gap.

        The polling loop paces on ``--poll-ms`` rather than ``--pace-s``, but a
        freshly constructed pacer carries no outstanding gap, so its first call
        would follow the setup phase's last call (the baseline walk, or the
        ``--reference-check`` GET) with no interval at all. The broker answers
        such a pair with a rate limit, which stops the run: the 2026-09-17
        SK텔레콤 trial lost its whole cash leg to CENSORED off one poll.
        """
        successor = _Pacer(interval_s)
        successor._next_allowed_at = self._next_allowed_at
        return successor

    def defer(self, seconds: float) -> None:
        """Push the next allowed call ``seconds`` out from NOW.

        The transient-error retry (:func:`_retry_once`) has to wait a
        WHOLE interval before trying again, and ``wait()`` alone does not give
        that: the failed attempt already armed the gap before it went out, so by
        the time a 20s read timeout surfaces, ``wait()`` owes only the remainder
        (10s of a 30s interval — the 2026-09-30 trial-3 shape). Deferring from
        NOW makes the following ``wait()`` sleep the full interval, which is
        where the wait lives — this method never sleeps itself, so there is
        exactly one sleep site per call.

        It never SHORTENS an outstanding gap: a longer pending interval wins.
        """
        target = time.monotonic() + max(0.0, float(seconds))
        if self._next_allowed_at is None or target > self._next_allowed_at:
            self._next_allowed_at = target


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

#: A balance read that failed for a reason NOT attributable to this probe's own
#: call rate, and is therefore worth ONE retry (2026-09-30 P-CA trial 2: four
#: attempts, four stops, zero cash-leg observations — two transport read
#: timeouts, one ``EGW00215`` ledger throttle, one runner guard defect). The
#: "stop at once, never retry" rule these fell under was written for
#: 2026-09-17, whose cause WAS our own pacing (``EGW00201``); none of the
#: 09-30 stops was (no co-resident process on the account — evidence README
#: 09-30 block, "제거 논증"). ``EGW00201``/HTTP 429 keep the old rule (plan §3).
#:
#: The two sub-kinds are separate ``_read_balance`` statuses rather than an
#: extra tuple element, so the classification travels through the existing
#: 6-tuple and every existing caller and test keeps its arity.
_BAL_TRANSIENT = "TRANSIENT"
_TRANSIENT_TRANSPORT = "transport"
_TRANSIENT_LEDGER_THROTTLE = "ledger_throttle"
_BAL_TRANSIENT_TRANSPORT = f"{_BAL_TRANSIENT}:{_TRANSIENT_TRANSPORT}"
_BAL_TRANSIENT_LEDGER_THROTTLE = f"{_BAL_TRANSIENT}:{_TRANSIENT_LEDGER_THROTTLE}"

_BAL_TRANSIENT_KINDS: dict[str, str] = {
    _BAL_TRANSIENT_TRANSPORT: _TRANSIENT_TRANSPORT,
    _BAL_TRANSIENT_LEDGER_THROTTLE: _TRANSIENT_LEDGER_THROTTLE,
}

#: 원장에서 허용 가능한 초당 거래건수를 초과하였습니다 — the LEDGER-side throttle,
#: which the mock server answers with HTTP 500 and ``rt_cd='1'``
#: (P-CA-20260930T015946Z.json poll #14, verbatim). It is NOT ``EGW00201``:
#: ``is_rate_limited`` (common.py) never sees it, so before this change it fell
#: through to :data:`_BAL_REJECTED` and stopped the run on the spot.
_LEDGER_THROTTLE_MSG_CD = "EGW00215"


def _is_ledger_throttled(parsed: dict[str, Any]) -> bool:
    """``msg_cd`` is exactly :data:`_LEDGER_THROTTLE_MSG_CD`.

    Field-exact, deliberately not the substring sweep over
    ``msg_cd``/``msg1``/raw body that ``is_rate_limited`` does for
    ``EGW00201``: the ledger throttle is worth a retry, so a body that merely
    MENTIONS the code (an operator note echoed back, a future envelope that
    quotes it) must not buy one.
    """
    return str(parsed.get("msg_cd") or "").strip() == _LEDGER_THROTTLE_MSG_CD


def _transport_transient_types() -> tuple[type[BaseException], ...]:
    """The exception types :func:`_get`'s transport actually raises for a
    timeout or a failed connection — and ONLY those.

    The line is "no intact answer arrived, and our call rate is not why".
    ``_get`` raises from TWO places, and both are in the set:

    * ``session.request`` — ``Timeout`` (covers ``ReadTimeout``, the one the
      2026-09-30 trials 3 and 4 died on, and ``ConnectTimeout``) and
      ``ConnectionError`` (covers ``SSLError``, ``ProxyError``).
    * ``response.text`` — the body is streamed, so a connection cut or a
      corrupt encoding surfaces only when the body is READ, as
      ``ChunkedEncodingError`` (a chunked body cut before its terminating
      chunk) or ``ContentDecodingError`` (a gzip body that will not decode).
      Both mean a truncated transfer, which is the same failure as a read
      timeout arriving a few bytes later; neither is a misconfiguration.

    Everything else ``requests`` can raise — ``TooManyRedirects``,
    ``InvalidURL``, ``MissingSchema``, ``URLRequired`` — is a defect in this
    probe or its configuration. Retrying one produces the identical failure
    twice and hides it behind a doubled stop reason, so those still surface as
    a failed run.

    Imported lazily for the same reason :func:`probe_pca` imports ``requests``
    lazily: ``--list``/``--dry-run`` and the registry import this module and
    must not pay for (or require) the HTTP stack.
    """
    import requests

    return (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
        requests.exceptions.ChunkedEncodingError,
        requests.exceptions.ContentDecodingError,
    )


#: Anything from ``?`` to the next whitespace in a transport exception message.
#: ``requests``' ``ConnectionError`` renders the URL it failed on IN FULL —
#: "Max retries exceeded with url: /uapi/...?CANO=12345678&ACNT_PRDT_CD=01..." —
#: and these artifacts are committed under ``docs/broker-profiles/evidence/``.
#: ``redact()`` (common.py:228) keys on field NAMES and cannot reach inside a
#: raw string leaf, and :func:`_call_evidence`'s excerpt cap only bounds the
#: length, so without this the account number would reach the corpus through
#: the one field that carries a broker string verbatim. Over-redaction is the
#: safe direction: the diagnosis a reader needs is the exception CLASS and the
#: timeout value, both of which sit before the ``?``.
_QUERY_STRING_IN_MESSAGE = re.compile(r"\?\S*")


def _transport_excerpt(exc: BaseException) -> str:
    """One transport exception rendered for the artifact, query string removed."""
    return _QUERY_STRING_IN_MESSAGE.sub("?<redacted>", f"{type(exc).__name__}: {exc}")


def _transient_kind(status: str | None) -> str | None:
    """``"transport"``/``"ledger_throttle"`` for a transient status, else ``None``."""
    return _BAL_TRANSIENT_KINDS.get(status or "")


def _get_classified(
    session: Any,
    auth: Any,
    *,
    base_url: str,
    path: str,
    tr_id: str,
    params: dict[str, Any],
) -> tuple[str | None, int, dict[str, Any], str]:
    """One GET plus the ONLY copy of this probe's retry/no-retry precedence.

    Returns ``(status_kind, http_status, parsed, text)``; ``status_kind`` is
    ``None`` when the call came back intact and the CALLER has to interpret it
    (``rt_cd``, pagination, rows). Otherwise it is one of
    :data:`_BAL_TRANSIENT_TRANSPORT` / :data:`_BAL_RATE_LIMITED` /
    :data:`_BAL_TRANSIENT_LEDGER_THROTTLE`.

    The ORDER is the policy, and it lives here so that it cannot differ
    between the balance path and the ksdinfo path (independent review F4: it
    already did — a 429 body carrying ``EGW00215`` bought a retry on the
    reference check and stopped the run at once on the balance walk):

    1. no answer at all ⇒ transient (retry once);
    2. ``is_rate_limited`` — HTTP 429 or ``EGW00201`` ⇒ WE called too fast, the
       2026-09-17 cause; stop, never retry (plan §3);
    3. ``EGW00215`` ⇒ the LEDGER-side throttle, not our rate ⇒ transient.

    2 before 3 is load-bearing: a body can carry both signals, and the
    account-protection rule has to win.
    """
    try:
        http_status, parsed, text, _elapsed_ms = _get(
            session,
            auth,
            base_url=base_url,
            path=path,
            tr_id=tr_id,
            params=params,
        )
    except _transport_transient_types() as exc:
        # No answer arrived, so there is no body and no HTTP status: 0 is this
        # module's "no call completed" marker. The excerpt carries the
        # exception class, never the request.
        return _BAL_TRANSIENT_TRANSPORT, 0, {}, _transport_excerpt(exc)
    if is_rate_limited(http_status, parsed, text):
        return _BAL_RATE_LIMITED, http_status, parsed, text
    if _is_ledger_throttled(parsed):
        return _BAL_TRANSIENT_LEDGER_THROTTLE, http_status, parsed, text
    return None, http_status, parsed, text


#: Why :func:`_poll_loop` stopped. ``None`` means it ran to its natural end —
#: ``--window-s`` genuinely elapsed, or every leg was observed — which is the
#: ONLY state in which an unobserved leg is CENSORED (:func:`_finalize`).
#: Anything else means the run stopped early and learned nothing about the
#: remaining legs: the 2026-09-17 SK텔레콤 trial stopped on poll #1 after ~1s
#: yet labelled its cash leg "CENSORED — no broker-reflect observed within
#: --window-s=28800.0s", asserting an 8-hour absence that was never observed.
_STOP_RATE_LIMITED = "rate_limited"
_STOP_REJECTED = "rejected"
_STOP_PAGE_CAP = "page_cap"
#: Two consecutive transport failures (:data:`_BAL_TRANSIENT_TRANSPORT`). A
#: doubled LEDGER throttle reports :data:`_STOP_RATE_LIMITED` instead — it IS a
#: rate limit, just not one keyed on ``EGW00201`` — so a reader of the row does
#: not have to know which code the broker used to know the run was throttled.
_STOP_TRANSIENT = "transient"

#: Cap on the verbatim broker body carried by a FAILED call's evidence record.
#: The excerpt is GATED first (:func:`_call_evidence`), and the gate is PAYLOAD-
#: BASED and FAIL-CLOSED: the body is recorded only when the call both failed
#: (``rt_cd != '0'``) AND carries no ``output1``/``output2``. Asking only "did
#: the broker say success?" recorded the body on every OTHER answer, so a body
#: the probe MISCLASSIFIES still reached the artifact — ``rt_cd`` absent or
#: ``null``, or ``rt_cd`` as the JSON number ``0`` (``str(0 or '')`` is ``''``,
#: not ``'0'``, because ``0`` is falsy), each wrote holdings plus the raw
#: ``ctx_area_*`` cursors into a committed artifact. Keying on the payload
#: instead is safe in BOTH directions: a body carrying holdings is never
#: diagnostic (it is the success page, not the signal that stopped the run),
#: and the failures worth recording — HTTP 429, ``EGW00201``, ``APBK0919``, an
#: HTML gateway page — carry no ``output1``/``output2`` at all. Verified against
#: the committed corpus: EVERY non-empty ``raw_excerpt`` under
#: ``docs/broker-profiles/evidence/`` is a bare ``rt_cd``/``msg_cd``/``msg1`` or
#: ``error_code`` envelope, none with a non-empty ``output1``/``output2``. So
#: this gate suppresses no excerpt the corpus has ever found diagnostic.
#: This cap then bounds whatever survives the gate. Capped rather than trusted:
#: the excerpt is recorded unparsed, and an HTML gateway error page would
#: otherwise bloat every artifact — 300 chars (the same cap the sibling probes
#: use: ``probes_balance.py:749``, ``probes_real.py:232,315,389,490``)
#: comfortably covers the ``rt_cd``/``msg_cd``/``msg1`` envelope that identifies
#: WHICH rate-limit signal fired (HTTP 429 vs EGW00201 in the body), which is
#: exactly what the 2026-09-17 artifact could not say afterwards. Request params
#: and headers are never recorded here — they carry the account number and the
#: bearer token.
_BODY_EXCERPT_MAX_CHARS = 300


def _call_evidence(
    *, status_kind: str, http_status: int, parsed: dict[str, Any], text: str
) -> dict[str, Any]:
    """Verbatim broker evidence for one balance call, for the artifact.

    ``is_rate_limited`` fires on EITHER HTTP 429 OR ``EGW00201`` in the body, so
    a bare "rate-limited" string cannot be diagnosed after the fact; this record
    carries both signals plus the rejection envelope (2026-09-17 incident).

    Record shape mirrors ``probes_balance.py:749`` (and
    ``probes_real.py:232,315,389,490``) — a local twin of the same decision,
    not a divergence from it, so change the two together. The gate is the point:
    a SUCCESSFUL balance body carries holdings (``pdno``, ``pchs_avg_pric``,
    ``evlu_amt``), the account cash total (``dnca_tot_amt``) and the raw
    ``ctx_area_fk100``/``ctx_area_nk100`` cursors that
    ``probes_balance.py:529-540`` fingerprints rather than stores — and these
    artifacts are committed under ``docs/broker-profiles/evidence/``. The gate
    here is STRICTER than the sibling probes': it fails closed on the payload
    rather than trusting ``rt_cd`` alone, because a body this probe
    MISCLASSIFIES (``rt_cd`` absent/``null``, or the JSON number ``0``) is
    exactly the body an ``rt_cd``-only gate lets through
    (:data:`_BODY_EXCERPT_MAX_CHARS`).
    """
    raw = parsed.get("rt_cd")
    rt_cd = "" if raw is None else str(raw).strip()
    carries_payload = any(bool(parsed.get(k)) for k in ("output1", "output2"))
    return {
        "status_kind": status_kind,
        "http_status": http_status,
        "rt_cd": parsed.get("rt_cd"),
        "msg_cd": parsed.get("msg_cd"),
        "msg1": parsed.get("msg1"),
        # A gate, not a filter: redact() (common.py:228-243) keys on field NAMES
        # and cannot reach inside a raw string leaf, so a length cap alone would
        # still commit account-derived material to the evidence corpus. The
        # _BAL_CAPPED stop is the case that makes this load-bearing — its last
        # page is a SUCCESSFUL balance page, i.e. the whole holdings body.
        "body_excerpt": (
            ""
            if rt_cd == "0" or carries_payload
            else (text or "")[:_BODY_EXCERPT_MAX_CHARS]
        ),
    }


def _read_balance(
    session: Any,
    auth: Any,
    base_url: str,
    tr_id: str,
    creds: Any,
    symbol: str,
    pacer: _Pacer,
) -> tuple[str, int, float, dict[str, Any], str, int]:
    """Walk balance pages (capped at :data:`_MAX_BALANCE_PAGES`) until
    ``symbol``'s row is found or the broker signals end-of-set. Returns
    ``(status, qty, cash, parsed_last_page, text_last_page, http_status)`` where
    ``status`` is one of :data:`_BAL_OK` / :data:`_BAL_RATE_LIMITED` /
    :data:`_BAL_REJECTED` / :data:`_BAL_CAPPED` (F6: capped ⇒ INCONCLUSIVE,
    never "not held") / :data:`_BAL_TRANSIENT_TRANSPORT` /
    :data:`_BAL_TRANSIENT_LEDGER_THROTTLE`. ``http_status`` is the transport
    status of the LAST page fetched — the caller records it verbatim
    (:func:`_call_evidence`); it is ``0`` when no answer arrived at all.

    A transient return ABANDONS the page walk in progress: the continuation
    cursors of a page that failed are not resumable, so the retry
    (:func:`_retry_once`) starts the walk again from page 1."""
    fk = nk = ""
    cash = 0.0
    parsed: dict[str, Any] = {}
    text = ""
    # Bound before the loop so the _BAL_CAPPED return below is always defined;
    # 0 is "no call completed", which no real transport status can be.
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
            # Rate-limited or transient — decided once, in _get_classified.
            # The rt_cd check below is what EGW00215 used to fall through to
            # (rt_cd='1' ⇒ _BAL_REJECTED ⇒ immediate stop, 09-30 poll #14).
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
            # Broker end-of-set and the symbol was never on any page walked —
            # genuinely absent, not truncated.
            return _BAL_OK, 0, cash, parsed, text, http_status
        fk, nk = next_fk, next_nk
    return _BAL_CAPPED, 0, cash, parsed, text, http_status


# ---------------------------------------------------------------------------
# Transient-error retry — ONE retry, one full poll interval apart (plan §2.1)
# ---------------------------------------------------------------------------


class _Retries:
    """Counts the retries this run spent, and keeps ``measurements.retries``
    current at EVERY exit path.

    A run that retried is still labelled OBSERVED/CENSORED/ABORTED exactly as
    before — the retry changes no verdict. What it changes is the timing a
    reader reconstructs from the artifact, by up to one poll interval per
    retry, so the count has to be in the artifact whatever happens: it is
    published on construction (all zeros, so "no retries" is stated rather
    than inferred from a missing key) and republished on every increment,
    because the baseline and reference-check phases can stop the run long
    before :func:`_finalize` would get to write anything.
    """

    def __init__(self, run: ProbeRun) -> None:
        self._run = run
        self._counts: dict[str, int] = {
            _TRANSIENT_TRANSPORT: 0,
            _TRANSIENT_LEDGER_THROTTLE: 0,
        }
        self._publish()

    def bump(self, kind: str) -> None:
        self._counts[kind] = self._counts.get(kind, 0) + 1
        self._publish()

    def as_dict(self) -> dict[str, int]:
        return dict(self._counts)

    def _publish(self) -> None:
        self._run.measure("retries", self.as_dict())


def _retry_evidence(
    *,
    phase: str,
    kind: str,
    status: str,
    http_status: int,
    parsed: dict[str, Any],
    text: str,
    poll_index: int | None,
    retried: bool,
) -> dict[str, Any]:
    """The record written for EVERY transient, retried or not.

    Same shape and the same payload gate as :func:`_call_evidence` (a
    successful balance body is never excerpted), plus which phase it happened
    in, which poll (when there was one), and whether a retry followed. A run
    must be reconstructible down to "when, and how many times", which is the
    whole reason the retry is capped at one — and ``retried: false`` is how the
    two refusals are told apart from a retry: the second consecutive transient,
    and a transient that surfaced after ``--window-s`` had already elapsed.

    The key this lands under is ``retry_evidence``, not ``poll_retry_evidence``:
    three of the four phases that can write one are not the poll loop, and a
    harvester filtering on the key would have counted baseline and
    reference-check retries as poll retries (independent review F8).
    """
    record: dict[str, Any] = {
        "phase": phase,
        "transient_kind": kind,
        "retried": retried,
    }
    if poll_index is not None:
        record["poll_index"] = poll_index
    record.update(
        _call_evidence(
            status_kind=status, http_status=http_status, parsed=parsed, text=text
        )
    )
    return record


@dataclass(frozen=True)
class _Outcome:
    """One broker call, already run through :func:`_get_classified`.

    ``kind`` is the status the retry policy reads: ``None`` means "the caller
    interprets this" (the balance walk's own OK/REJECTED/CAPPED verdicts reuse
    the field, since they are equally "not transient"). ``payload`` carries
    whatever the phase needs beyond the envelope — ``(qty, cash)`` for a
    balance read, nothing for the ksdinfo reference check.
    """

    kind: str | None
    http_status: int
    parsed: dict[str, Any]
    text: str
    payload: Any = None


def _retry_once(
    call: Callable[[], _Outcome],
    on_transient: Callable[[dict[str, Any], str], None],
    pacer: _Pacer,
    *,
    wait_s: float,
    phase: str,
    poll_index_base: int | None = None,
    can_retry: Callable[[], bool] | None = None,
) -> tuple[_Outcome, int, bool]:
    """Run ``call``; on a transient outcome wait one whole interval and run it
    exactly once more. Returns ``(outcome, attempts, retried)`` — ``attempts``
    is 1 or 2, and ``retried`` says whether a second attempt was actually made.

    ``can_retry`` lets a caller REFUSE the retry for a reason of its own. The
    poll loop passes the window deadline: a transient surfacing after
    ``--window-s`` has elapsed must not buy another interval of waiting plus
    another call, or a CENSORED verdict ends up resting on a poll made outside
    the window it claims to cover (independent review F5 — window 60s, poll at
    58s, 20s timeout, 30s defer, retry at 108s).

    The caller sees a transient ``kind`` back only when BOTH attempts were
    transient — the "second consecutive transient" stop of plan §2.1. This is
    the ONLY retry loop in the module (independent review F5: the balance and
    ksdinfo phases each had their own, and they had already drifted apart on
    the EGW00201-vs-EGW00215 precedence).

    Exactly one retry, exactly one interval apart (:meth:`_Pacer.defer`). No
    backoff, no tunable attempt count: each of the three 2026-09-30 stops was a
    SINGLE failure, so one retry would have carried all three, and every extra
    knob blurs the "when, and how many times" the artifact has to answer.

    ``on_transient`` receives ``(evidence, kind)`` for EVERY transient — the
    retried one and the one that ends the phase — so the phase decides where
    that goes: the probe records it on the run and counts only the retries, the
    pre-flight holding check just prints it. Recording both is the point: a
    transient that bought no retry is exactly the case a reader needs to see.
    """
    attempts = 0
    while True:
        attempts += 1
        outcome = call()
        kind = _transient_kind(outcome.kind)
        if kind is None:
            return outcome, attempts, attempts > 1
        retrying = attempts < 2 and (can_retry is None or can_retry())
        on_transient(
            _retry_evidence(
                phase=phase,
                kind=kind,
                status=outcome.kind or "",
                http_status=outcome.http_status,
                parsed=outcome.parsed,
                text=outcome.text,
                poll_index=(
                    None if poll_index_base is None else poll_index_base + attempts
                ),
                retried=retrying,
            ),
            kind,
        )
        if not retrying:
            return outcome, attempts, attempts > 1
        pacer.defer(wait_s)


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
) -> _Outcome:
    """One paced ksdinfo GET as an :class:`_Outcome`.

    It goes through the same :func:`_get_classified` as the balance walk, so
    HTTP 429 / ``EGW00201`` stop the run here too rather than buying a retry.
    """
    ksd_tr, ksd_path = _KSDINFO_TRS[ksd_key]
    pacer.wait()
    kind, http_status, parsed, text = _get_classified(
        session,
        auth,
        base_url=base_url,
        path=ksd_path,
        tr_id=ksd_tr,
        params=_ksdinfo_params(ksd_key, symbol),
    )
    return _Outcome(kind=kind, http_status=http_status, parsed=parsed, text=text)


def _record_retry(
    run: ProbeRun, retries: _Retries
) -> Callable[[dict[str, Any], str], None]:
    """The probe's ``on_transient``: observe EVERY transient, count the RETRIES.

    The two differ, and conflating them is how a counter stops meaning
    anything: ``measurements.retries`` answers "how much extra waiting did this
    run spend", which a transient that bought no retry did not.
    """

    def _record(evidence: dict[str, Any], kind: str) -> None:
        run.observe(retry_evidence=evidence)
        if evidence.get("retried"):
            retries.bump(kind)

    return _record


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
    retries: _Retries,
    retry_wait_s: float,
) -> tuple[int, float] | None:
    """Paced, paginated balance snapshot (:func:`_read_balance`), retried once
    on a transient error. Returns ``(qty, cash)`` or ``None`` if the run should
    stop here (rate-limited, transient twice over, rejected, capped, or no
    holding).

    The retry belongs here and not only in the poll loop because the 2026-09-30
    trial 4 died on this very call — the FIRST GET of the run — and left an
    artifact with no baseline at all.
    """
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
    """One paced GET to the ksdinfo TR matching ``--event-class``, BEFORE
    polling; retried once on a transient error.

    A transient that survives the retry STOPS the run (:class:`_StopRun`), as a
    rate limit here always has: the reference check is optional, but two
    consecutive failures on it say the path to the broker is unhealthy right
    now, and the polling loop is a far longer walk down that same path. Before
    this change a transport exception here did not stop the run politely — it
    escaped the probe entirely (``run.py`` rc 5).
    """
    ksd_key = _EVENT_CLASS_KSDINFO_KEY[trial.event_class]
    outcome, _attempts, _retried = _retry_once(
        lambda: _ksdinfo_outcome(session, auth, base_url, pacer, ksd_key, trial.symbol),
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
        raise _StopRun
    if outcome.kind == _BAL_RATE_LIMITED:
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


class _StopRun(ProbeError):
    """Signal: the reason is ALREADY recorded via ``run.error``; stop and write
    the artifact as it stands. Never propagates out of :func:`probe_pca`, so it
    never reaches ``run.py``'s catch-all failure path."""


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
    """Poll balance until every leg is observed or ``--window-s`` expires.

    Returns ``(found, polls_used, polls_completed, polled_elapsed_s,
    stop_reason)`` — ``found`` maps leg name to its measurement record for every
    leg detected live. ``stop_reason`` is ``None`` when the loop ran to its
    natural end (window elapsed, or every leg observed), in which case a leg
    absent from ``found`` is CENSORED; otherwise it is one of
    :data:`_STOP_RATE_LIMITED` / :data:`_STOP_REJECTED` / :data:`_STOP_PAGE_CAP`
    / :data:`_STOP_TRANSIENT` and the remaining legs were ABORTED, not censored
    (:func:`_finalize`).

    A transient failure costs one extra ATTEMPT and no completed poll:
    ``polls_used`` counts both tries, ``polls_completed`` counts the one that
    came back with a balance. A poll only stops the loop when its retry fails
    transiently too.
    """
    pending = {name: (t0_field, t0_dt) for name, t0_field, t0_dt in legs}
    found: dict[str, dict[str, Any]] = {}
    poll_pacer = pacer.derive(trial.effective_poll_ms / 1000.0)
    # Two counters, because one number cannot mean both (review M2): the
    # 2026-09-17 artifact's "polls_used=1" was the ATTEMPT that rate-limited, so
    # a reader who took it for "one poll observed nothing" read an observation
    # into a run that made none. polls_used counts attempts (the failed one that
    # ends the run included, so it stays the index poll_stop_evidence reports);
    # polls_completed counts the polls that came back with a usable balance.
    polls_used = 0
    polls_completed = 0
    stop_reason: str | None = None
    # M3: the ABORTED row must carry how long polling ACTUALLY ran, not just the
    # requested --window-s it never reached (an ~1s run carrying window_s=28800).
    started_at = time.monotonic()
    deadline = started_at + trial.window_s
    # Hoisted (review F9): neither depends on loop state, and a 16-hour window
    # at 30s polls would otherwise build ~1,920 of each for nothing.
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
            # F5: a transient that surfaces after the window has elapsed must
            # not buy another interval of waiting plus another call — the
            # retry is allowed on exactly the terms a fresh poll would be.
            can_retry=window_still_open,
        )
        status, http_status, parsed, text = (
            outcome.kind,
            outcome.http_status,
            outcome.parsed,
            outcome.text,
        )
        qty, cash = outcome.payload
        # Every ATTEMPT counts, the retried one included — polls_used is the
        # index poll_stop_evidence / poll_retry_evidence report, so a reader
        # can line the records up against it.
        polls_used += attempts
        transient = _transient_kind(status)
        if transient is not None and not retried:
            # The retry was REFUSED because --window-s had already elapsed, so
            # the loop ends the way it would have ended anyway: stop_reason
            # stays None, because the window genuinely ran its course and that
            # is exactly what CENSORED asserts. The transient itself is in the
            # artifact as a retry_evidence record with retried=false; it is not
            # a stop reason, because it did not stop anything (review F5).
            break
        if status in (_BAL_RATE_LIMITED, _BAL_REJECTED, _BAL_CAPPED) or transient:
            # ONE verbatim evidence record per stop, so a later reader can tell
            # HTTP 429 from EGW00201 and read the broker's own words (the
            # 2026-09-17 artifact recorded neither).
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
                    # F3: TIMING ALONE — no broker-side CA reference on the row.
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
    """Build ``class_leg_table`` — the ONLY aggregate this probe emits — and
    skip every unobserved leg explicitly (never a value, never a zero).

    An unobserved leg is CENSORED only when ``stop_reason`` is ``None``: the
    window truly elapsed, so absence is an informative-but-not-zero observation.
    When polling stopped early the leg is ABORTED instead — a different
    epistemic state, in which nothing at all was observed about the leg and the
    window never elapsed (2026-09-17 incident: an ~1s run claimed an 8-hour
    censoring window).

    Because ``class_leg_table`` is the only aggregate emitted, each row has to
    be self-sufficient: it carries ``polled_elapsed_s`` (how long polling
    ACTUALLY ran) beside ``window_s`` (what was REQUESTED), so the 2026-09-17
    row's ``window_s=28800.0`` on a one-second run cannot be read as a window
    that elapsed (review M3).
    """
    class_leg_table: list[dict[str, Any]] = []
    for name, t0_field, t0_dt in legs:
        if name in found:
            row = dict(found[name])
            row["status"] = "OBSERVED"
        else:
            # No "candidate_only" here (F5): that flag means "a value exists,
            # unapproved" — a CENSORED/ABORTED row has NO value to flag as a
            # candidate (and no t1/latency_ms either).
            row = {
                "event_class": trial.event_class,
                "leg": name,
                "t0_field": t0_field,
                "t0": t0_dt.isoformat(),
                "status": "CENSORED" if stop_reason is None else "ABORTED",
                # window_s is what was REQUESTED; polled_elapsed_s is what
                # actually ran. On an ABORTED row the two differ by orders of
                # magnitude, and the row is the only aggregate a reader gets.
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
    # polls_used counts ATTEMPTS and keeps its name for the artifacts already
    # committed under docs/broker-profiles/evidence/; polls_completed is the
    # count a reader actually wants when the run stopped early (review M2).
    run.measure("polls_used", polls_used)
    run.measure("polls_completed", polls_completed)
    run.measure("polled_elapsed_s", polled_elapsed_s)
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


def _open_broker_session(
    *, is_real: bool, token_cache_dir: Any
) -> tuple[Any, Any, str, str, Any]:
    """Resolve credentials and open the ONE broker session shape this module
    uses. Returns ``(session, auth, base_url, tr_id, creds)``.

    Both entry points go through here — :func:`probe_pca` and
    :func:`check_holding` (independent review F6: the pre-flight gate had a
    line-for-line copy of this and had already drifted, dropping
    :func:`warn_shared_token_cache`). The caller closes the session.

    ``requests`` and ``KISAuthManager`` are imported lazily for the reason the
    module docstring gives: ``--list``/``--dry-run`` and the registry import
    this module and must not pay for (or require) the HTTP stack.
    """
    warn_shared_token_cache()
    creds = resolve_credentials("stock", is_real=is_real)
    require_account(creds)

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

    session, auth, base_url, tr_id, creds = _open_broker_session(
        is_real=trial.is_real, token_cache_dir=args.token_cache_dir
    )
    run.credentials = creds.describe()
    pacer = _Pacer(trial.pace_s)
    retries = _Retries(run)

    try:
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

        if trial.reference_check:
            try:
                _do_reference_check(run, session, auth, base_url, pacer, trial, retries)
            except _StopRun:
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


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))


# ---------------------------------------------------------------------------
# Pre-flight holding check — the runner's gate, on THIS module's reader
# ---------------------------------------------------------------------------
#
# Independent review F1/F2. The runner used to ask
# ``shared/kis/client.py::get_stock_balance`` whether the symbol was held, and
# that function is the wrong instrument twice over:
#
# * it returns ``[]`` on EVERY failure — non-200, non-JSON, ``rt_cd != '0'``,
#   and a catch-all ``except Exception`` — so a broker-side failure and an
#   empty account are the SAME answer. That is precisely the 2026-09-30 10:58
#   misdiagnosis ("held qty=0" for a query that had errored after 32s; a direct
#   GET two minutes later showed qty 1), i.e. the defect the runner claimed to
#   fix was reproduced by the tool the fix was built on.
# * it sends empty ``CTX_AREA_FK100``/``NK100`` and never follows the
#   continuation cursors, so it reads PAGE 1 ONLY. The mock stock account holds
#   25 rows across 2 pages; a target on page 2 reads as "not held" — the F6
#   trap this module's own :func:`_read_balance` was written to close.
#
# So the gate runs on :func:`_read_balance`: paced, paginated, and classifying.
# It prints exactly one machine-readable line for the runner to parse.

#: The two lines the runner parses. Anything else on stdout is diagnostic.
_HELD_PREFIX = "HELD="
_HOLDING_FAILED_PREFIX = "HOLDING_QUERY_FAILED="


def _holding_failure_detail(outcome: _Outcome) -> str:
    """The short reason after the status kind.

    ``msg_cd`` only when the broker actually REJECTED the call (``rt_cd`` not
    ``'0'``). The page cap is the case that forced this (review F4): its
    ``parsed`` is the last SUCCESSFUL page, so keying on "is there a body"
    printed a success code — ``CAPPED:KIOK0510`` — as the reason a run was
    abandoned, and a reader looking that code up finds 정상처리.
    """
    if outcome.kind == _BAL_CAPPED:
        return f"page_cap:{_MAX_BALANCE_PAGES}"
    rt_cd = str(outcome.parsed.get("rt_cd") or "").strip()
    msg_cd = str(outcome.parsed.get("msg_cd") or "").strip()
    if rt_cd != "0" and msg_cd:
        return msg_cd
    head = (outcome.text or "").split(":", 1)[0].strip()
    return head or "unknown"


def check_holding(argv: list[str] | None = None) -> int:
    """Answer "is ``--symbol`` held, and do we actually KNOW?" for a runner.

    Prints ONE of two anchored lines and exits accordingly:

    * ``HELD=<n>`` and 0 — the balance walk completed. ``n`` may be 0, and
      then it is a real "not held", not a failure wearing its clothes.
    * ``HOLDING_QUERY_FAILED=<status kind>:<detail>`` and non-zero — anything
      else: rate limit, rejection, page cap, or two consecutive transients.

    Transients get the same single retry as the probe itself, one pacing
    interval apart, so one read timeout does not cost a whole trial window.
    """
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
        help=(
            f"Min interval between calls, and the wait before the single "
            f"retry (default {DEFAULT_PACE_S}s). No separate retry constant: "
            "the pre-flight has no polling interval to borrow."
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

    try:
        outcome, _attempts, _retried = _retry_once(
            lambda: _balance_outcome(
                session, auth, base_url, tr_id, creds, args.symbol, pacer
            ),
            lambda evidence, kind: print(
                f"holding check: transient {kind} "
                f"({evidence.get('body_excerpt') or evidence.get('msg_cd')}); "
                f"retrying once in {args.pace_s}s",
                file=sys.stderr,
            ),
            pacer,
            wait_s=args.pace_s,
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
