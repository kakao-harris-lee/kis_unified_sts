"""P-BAL — balance-query pagination probe. READ-ONLY BY CONSTRUCTION.

Why this probe exists
---------------------
``shared/kis/client.py`` reads exactly ONE page of every balance query and has no
way to notice that it did:

* stock (``get_stock_balance``, ``:901-1021``) sends empty ``CTX_AREA_FK100`` /
  ``CTX_AREA_NK100`` (``:931-932``), never reads the response continuation keys,
  never inspects the ``tr_cont`` response header, never checks the row count, and
  logs nothing on the success path;
* futures (``get_futures_balance``, ``:1023-1114``) does the same with
  ``CTX_AREA_FK200`` / ``CTX_AREA_NK200`` (``:1055-1056``).

A correct continuation walk already exists in the same file —
``fetch_invest_opinion`` (``:303-356``) loops until the ``tr_cont`` response
header stops being ``"M"`` (``:354``) — so the omission is a local defect, not a
missing capability.

Why it matters, and how far the consequence is actually established
-------------------------------------------------------------------
``services/trading/broker_verification.py`` consumes a balance read and has a
DESTRUCTIVE branch: when ``remove_redis_only`` is enabled (``:105``, gated at
``:121-127``) a position the broker "does not have" is dropped from tracking via
``remove_position(reason="broker_absent")`` (``:187-190``). If the balance read is
truncated, a genuinely held position beyond the page boundary is indistinguishable
from an absent one.

That consequence is **INFERENCE** today: the balance page size has never been
measured. This probe measures it — and is written so that it cannot accidentally
upgrade the inference. See :func:`truncation_verdict`.

Safety model
------------
Strictly GET-only, and structurally so:

* :data:`ALLOWLIST` is the complete set of calls this module may ever make. It
  contains three balance-inquiry entries and nothing else.
* :func:`_get` is the ONLY transport. It calls
  :func:`~tools.broker_probes.common.assert_read_only_call` (GET ∧ TR id ∧ URL
  path) *before* it touches the session, for every environment — the real host is
  not a special case here, it is the default target.
* There is no POST/PUT/PATCH/DELETE helper, no order-body builder, and this
  module deliberately does not import :mod:`tools.broker_probes.probes_order`
  (which does have order paths). ``tests/tools/test_broker_probes_balance.py``
  asserts all of that structurally against the module's own AST, so the property
  is committed rather than asserted in prose.

Nothing in this module can mutate an order, in mock or in real.
"""

from __future__ import annotations

import argparse
import hashlib
import time
from dataclasses import dataclass
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
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

# ---------------------------------------------------------------------------
# TR ids and paths — READ from shared/kis/client.py, not guessed
# ---------------------------------------------------------------------------

#: 주식 잔고조회 path — ``shared/kis/client.py:935``.
_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

#: 선물옵션 잔고조회 path — ``shared/kis/client.py:1059``.
_FUT_BALANCE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-balance"

#: ``shared/kis/client.py:919`` — ``"TTTC8434R" if self.config.is_real else
#: "VTTC8434R"``. The runtime picks between these two for the same path.
_STOCK_TR_REAL = "TTTC8434R"
_STOCK_TR_MOCK = "VTTC8434R"

#: ``shared/kis/client.py:1048`` — the futures balance TR has no mock variant;
#: ``:1031-1033`` refuses the call outright when ``is_real`` is false.
_FUT_TR_REAL = "CTFO6118R"

#: Complete read-only allowlist. A call not matching an entry is refused by
#: :func:`~tools.broker_probes.common.assert_read_only_call` before any socket is
#: opened. There is deliberately NO mock-futures entry: the broker does not serve
#: that query (see :data:`_MOCK_FUTURES_SKIP_REASON`), so admitting it would be
#: admitting a call that cannot succeed.
ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        _STOCK_TR_REAL,
        _STOCK_BALANCE_PATH,
        "P-BAL real stock balance — the target that matters. The destructive "
        "consumer (services/trading/broker_verification.py:187-190) runs against "
        "the live stock environment. Read-only inquiry; TR/path from "
        "shared/kis/client.py:919,935.",
    ),
    ReadOnlyCall(
        _STOCK_TR_MOCK,
        _STOCK_BALANCE_PATH,
        "P-BAL mock stock balance — same path, mock TR (client.py:919). Useful as "
        "a shape rehearsal; a mock row count does not transfer to real "
        "(ADR-002-004 §13.14).",
    ),
    ReadOnlyCall(
        _FUT_TR_REAL,
        _FUT_BALANCE_PATH,
        "P-BAL real futures balance — day-session TR (client.py:1048,1059). The "
        "night sibling CTFN6118R lives on a different path and is N-16's subject; "
        "it is NOT on this allowlist.",
    ),
)


@dataclass(frozen=True)
class _Target:
    """One (asset, environment) balance surface this probe knows how to walk."""

    asset: str
    is_real: bool
    tr_id: str
    path: str
    #: Continuation-key suffix: stock uses ``CTX_AREA_*K100``
    #: (``client.py:931-932``), futures ``CTX_AREA_*K200`` (``:1055-1056``).
    ctx_suffix: str
    #: Per-row holding-quantity field the RUNTIME filters on — stock ``hldg_qty``
    #: (``client.py:1002``), futures ``cblc_qty`` (``:1091``). Rows with a
    #: non-positive value are dropped by the runtime but still occupy a page, so
    #: raw and runtime-visible counts are recorded separately.
    row_qty_field: str


#: Mock futures is deliberately absent — see :data:`_MOCK_FUTURES_SKIP_REASON`.
_TARGETS: dict[tuple[str, bool], _Target] = {
    ("stock", True): _Target(
        "stock", True, _STOCK_TR_REAL, _STOCK_BALANCE_PATH, "100", "hldg_qty"
    ),
    ("stock", False): _Target(
        "stock", False, _STOCK_TR_MOCK, _STOCK_BALANCE_PATH, "100", "hldg_qty"
    ),
    ("futures", True): _Target(
        "futures", True, _FUT_TR_REAL, _FUT_BALANCE_PATH, "200", "cblc_qty"
    ),
}

_MOCK_FUTURES_SKIP_REASON = (
    "the broker does not serve a futures balance query on 모의투자 — "
    "shared/kis/client.py:1026 states '모의서버는 선물 잔고조회 미지원. "
    "is_real=True 필수' and the guard at :1031-1033 returns an empty list before "
    "any request is built. The same fact is already carried as a P-11 "
    "prerequisite in tools/broker_probes/registry.py. This is a SKIP, not an "
    "error: the probe could not observe, and a broker-unsupported query must not "
    "be recorded as 'no truncation risk'."
)

# ---------------------------------------------------------------------------
# tr_cont semantics
# ---------------------------------------------------------------------------

#: ``tr_cont`` response values with evidence for "more follows".
#: ``shared/kis/client.py:354`` breaks its continuation loop on
#: ``response_tr_cont != "M"``; KIS's official ``inquire_balance`` example
#: (open-trading-api ``examples_llm/domestic_stock/inquire_balance/
#: inquire_balance.py``) recurses on ``tr_cont in ("M", "F")`` and logs
#: "Data fetch complete." on every other value. A NON-EMPTY value outside this
#: tuple is therefore the broker's end-of-set signal (P-BAL-20260731T083102Z
#: observed ``"D"`` on the real stock endpoint with a static padded cursor
#: still present in the body); an ABSENT header establishes nothing and the
#: walk falls back to the continuation keys. The raw value is still recorded
#: verbatim per page, so an unfamiliar code shows up as a finding rather than
#: being silently folded into a boolean.
_TR_CONT_MORE_CODE_EVIDENCED = ("M", "F")

#: Request-side value for a follow-up page — ``shared/kis/client.py:356``.
_TR_CONT_REQUEST_NEXT = "N"

#: The broker's empty-result-set notation ("조회할 내용이 없습니다"). Wave-3
#: established this msg_cd as 빈-응답 on futures trading TRs (N-16, campaign
#: README), and the endpoints disagree on the rt_cd that accompanies it: the
#: real STOCK balance pairs it with rt_cd='0' (P-BAL-20260731T084147Z), the
#: real FUTURES balance with rt_cd='7' (P-BAL-20260731T114054Z). An empty set
#: is an answer, not a rejection — but ONLY this exact msg_cd is read that way;
#: every other non-zero rt_cd stays a rejection.
_MSG_EMPTY_RESULT_SET = "KIOK0560"

# ---------------------------------------------------------------------------
# Termination causes — the whole point of the probe (§8.4 honest negatives)
# ---------------------------------------------------------------------------

#: The broker itself signalled end-of-set (no continuation key came back, or
#: the ``tr_cont`` response header carried a non-empty non-more code).
_TERM_BROKER_END = "BROKER_END_OF_SET"
#: OUR ``--max-pages`` cap cut the walk. A total row count is NOT established.
_TERM_CAP = "OUR_MAX_PAGES_CAP"
#: A broker rejection or a non-advancing continuation key stopped the walk.
_TERM_ERROR = "ERROR"

_TERMINATION_CAUSES = (_TERM_BROKER_END, _TERM_CAP, _TERM_ERROR)

# ---------------------------------------------------------------------------
# Truncation-risk verdict — three-valued, computed from the data
# ---------------------------------------------------------------------------

#: Holdings provably exceed one page: the runtime's single-page read truncates.
_RISK_DEMONSTRATED = "TRUNCATION_RISK_DEMONSTRATED"
#: A page size is known AND the broker's own end-of-set was reached below it.
_RISK_NOT_DEMONSTRATED = "TRUNCATION_RISK_NOT_DEMONSTRATED"
#: Neither of the above is established. The honest outcome on a small account.
_RISK_UNESTABLISHED = "TRUNCATION_RISK_UNESTABLISHED"

_VERDICTS = (_RISK_DEMONSTRATED, _RISK_NOT_DEMONSTRATED, _RISK_UNESTABLISHED)

_PAGE_SIZE_MEASURED = "MEASURED_MULTI_PAGE_WALK"
_PAGE_SIZE_OPERATOR = "OPERATOR_SUPPLIED_PRIOR_MEASUREMENT"
_PAGE_SIZE_UNESTABLISHED = "UNESTABLISHED"

#: Default pause between pages, in seconds.
#:
#: Measured, not guessed: P-13 (artifact ``P-13-20260729T063120Z``) bracketed the
#: mock account's query class at clean 1.0 rps / throttled 2.0 rps (``EGW00201``).
#: 1.1 s sits just above the measured clean rate. Deliberately a local constant
#: rather than an import of ``probes_order.DEFAULT_PACE_S``: importing that module
#: would put order-submitting code in this module's import graph and weaken the
#: structural read-only property this file exists to guarantee.
DEFAULT_INTER_PAGE_S = 1.1


def truncation_verdict(
    *,
    page_row_counts: list[int],
    termination: str,
    known_page_size: int = 0,
    known_page_size_source: str = "",
) -> dict[str, Any]:
    """Derive the three-valued truncation verdict from the walk. PURE function.

    The verdict is computed from the observations, never self-reported, because
    the failure mode this probe exists to avoid is a comfortable summary. With a
    small account a single page of ``k`` rows is consistent with **any** page size
    ``>= k``; it is not evidence that the page size is ``k``, and it is not
    evidence that there is no truncation risk.

    Rules:

    * A page size is MEASURED only when a second page was actually returned and
      page 1 was the largest page (``pages >= 2``, ``rows[0] > 0``, and no later
      page larger than page 1). One page never establishes a page size.
    * ``known_page_size`` lets a prior measurement be carried in. It is recorded
      with source :data:`_PAGE_SIZE_OPERATOR` and always loses to a measurement
      taken in this run; a disagreement between the two is reported, not merged.
    * :data:`_RISK_NOT_DEMONSTRATED` additionally requires that the BROKER
      signalled end-of-set. If our own ``--max-pages`` cap ended the walk, "rows
      seen so far are below the page size" is not evidence that the account's
      holdings are — concluding otherwise is the fail-open direction.
    * A total holdings count is reported only when ``termination`` is
      :data:`_TERM_BROKER_END`. Otherwise only a lower bound exists.

    Args:
        page_row_counts: Raw row count per walked page, in walk order.
        termination: One of :data:`_TERMINATION_CAUSES`.
        known_page_size: A page size established by an earlier run, or 0.
        known_page_size_source: Provenance for ``known_page_size``; required by
            the caller whenever the value is used (see :func:`probe_pbal`).

    Returns:
        A dict carrying the verdict plus every input it was derived from, so a
        reviewer can recompute it without rerunning the probe.
    """
    if termination not in _TERMINATION_CAUSES:
        raise ProbeError(
            f"unknown termination cause {termination!r} "
            f"(expected one of {_TERMINATION_CAUSES})"
        )

    counts = [int(c) for c in page_row_counts]
    pages_walked = len(counts)
    rows_seen = sum(counts)
    total_established = termination == _TERM_BROKER_END

    first = counts[0] if counts else 0
    later_pages_fit = all(c <= first for c in counts[1:])
    measured_size = (
        first if (pages_walked >= 2 and first > 0 and later_pages_fit) else None
    )

    if measured_size is not None:
        page_size: int | None = measured_size
        page_size_source = _PAGE_SIZE_MEASURED
    elif known_page_size > 0:
        page_size = int(known_page_size)
        page_size_source = _PAGE_SIZE_OPERATOR
    else:
        page_size = None
        page_size_source = _PAGE_SIZE_UNESTABLISHED

    if page_size is None:
        verdict = _RISK_UNESTABLISHED
        largest = max(counts) if counts else 0
        why = (
            (
                f"A single page of {largest} row(s) is consistent with ANY page "
                f"size >= {largest}"
            )
            if pages_walked <= 1
            else (
                f"No page here was demonstrably full, so the largest observed "
                f"page ({largest} row(s)) is consistent with ANY page size >= "
                f"{largest}"
            )
        )
        rationale = (
            f"{pages_walked} page(s) walked, {rows_seen} row(s) seen, no page size "
            f"established. {why}: the page size is NOT {largest}, and {largest} is "
            "recorded as a LOWER BOUND (page_size_lower_bound). This run neither "
            "demonstrates nor refutes the truncation risk at "
            "shared/kis/client.py:931-932."
        )
    elif rows_seen > page_size:
        verdict = _RISK_DEMONSTRATED
        rationale = (
            f"{rows_seen} row(s) observed across {pages_walked} page(s) exceed the "
            f"page size {page_size} ({page_size_source}). The runtime reads page 1 "
            "only, so rows beyond it are invisible to it — and to "
            "services/trading/broker_verification.py, whose remove_redis_only "
            "branch (:187-190) drops an invisible position as broker_absent. The "
            "consequence is no longer inference for this account."
        )
    elif total_established:
        verdict = _RISK_NOT_DEMONSTRATED
        rationale = (
            f"the broker signalled end-of-set after {rows_seen} row(s), below the "
            f"page size {page_size} ({page_size_source}). Truncation is not "
            "reachable at this holdings count. This is a bound on THIS account at "
            "THIS moment, not a property of the code: the defect at "
            "shared/kis/client.py:931-932 is unchanged and becomes live as soon as "
            f"holdings exceed {page_size}."
        )
    else:
        verdict = _RISK_UNESTABLISHED
        rationale = (
            f"page size {page_size} ({page_size_source}) is known, but the walk "
            f"ended on {termination} rather than the broker's end-of-set, so the "
            f"{rows_seen} row(s) seen are a LOWER BOUND on holdings, not a total. "
            "'Rows seen so far are below the page size' is therefore not evidence "
            "that holdings are — reporting NOT_DEMONSTRATED here would be "
            "fail-open."
        )

    result: dict[str, Any] = {
        "verdict": verdict,
        "rationale": rationale,
        "termination_cause": termination,
        "pages_walked": pages_walked,
        "page_row_counts": counts,
        "page_size": page_size,
        "page_size_source": page_size_source,
        "page_size_lower_bound": (
            (max(counts) if counts else 0) if page_size is None else None
        ),
        "holdings_total": rows_seen if total_established else None,
        "holdings_total_lower_bound": rows_seen,
        "holdings_total_established": total_established,
        "operator_supplied_page_size": (
            int(known_page_size) if known_page_size else None
        ),
        "operator_supplied_page_size_source": known_page_size_source or None,
    }
    if (
        measured_size is not None
        and known_page_size > 0
        and int(known_page_size) != measured_size
    ):
        result["page_size_disagreement"] = (
            f"this run measured {measured_size} but --known-page-size said "
            f"{known_page_size} ({known_page_size_source!r}). The measurement is "
            "used; the disagreement is reported rather than averaged — one of the "
            "two observations is about a different account, TR or moment."
        )
    if pages_walked >= 2 and not later_pages_fit:
        result["page_size_shape_note"] = (
            "a later page returned MORE rows than page 1, so page 1 was not a full "
            "page and its row count is not the page size. Page size left "
            "unestablished from the walk."
        )
    return result


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
    tr_cont: str = "",
) -> tuple[int, dict[str, Any], dict[str, str], str, float]:
    """The ONLY transport in this module. GET, allowlisted, headers preserved.

    Deliberately not routed through
    :func:`~tools.broker_probes.common.http_json`: that helper discards the
    response headers, and the ``tr_cont`` response header is one of the four
    things this probe exists to observe. Reading it directly mirrors
    ``shared/kis/client.py:341`` (``fetch_invest_opinion``) and
    ``probes_query.py``'s ``Date``-header read in P-16 — both go to the transport
    for a header the shared helper drops.

    The allowlist assertion runs BEFORE the session is touched, so a refused call
    opens no socket.

    Returns:
        ``(status, parsed_body, response_headers, raw_text, elapsed_ms)``.
    """
    url = f"{base_url}{path}"
    assert_read_only_call("GET", url, tr_id, ALLOWLIST)
    headers = dict(auth.get_auth_headers())
    headers["tr_id"] = tr_id
    headers["custtype"] = "P"
    if tr_cont:
        headers["tr_cont"] = tr_cont
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
    return (
        int(response.status_code),
        parsed,
        dict(response.headers),
        text,
        elapsed_ms,
    )


def _balance_params(
    target: _Target, creds: Any, *, fk: str = "", nk: str = ""
) -> dict[str, str]:
    """Mirror the runtime's balance params, with the continuation keys USABLE.

    Stock: ``shared/kis/client.py:921-933``. Futures: ``:1051-1057``. Every field
    is transcribed from there, with exactly two documented divergences:

    * ``CTX_AREA_FK*`` / ``CTX_AREA_NK*`` carry the previous page's keys instead
      of being hard-wired to empty strings. That difference IS the defect under
      measurement.
    * Futures adds ``MGNA_DVSN`` and ``EXCC_STAT_CD``, which the runtime omits.
      REAL_PROD rejects the runtime's exact param set with rt_cd=7 APMP0001
      "증거금구분코드은(는) 필수입력 항목입니다" (measured:
      P-BAL-20260731T084304Z) — and mock serves no futures balance at all, so
      the runtime's futures-balance request has never succeeded against any
      broker. KIS's official inquire_balance example (open-trading-api
      ``examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py``)
      marks both fields [필수]; the values below are that example's
      documented examples (01: 게시 margin, 1: 정산). Without them the probe
      cannot measure pagination, because no page is ever served.
    """
    if target.asset == "stock":
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
            f"CTX_AREA_FK{target.ctx_suffix}": fk,
            f"CTX_AREA_NK{target.ctx_suffix}": nk,
        }
    return {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        "SORT_SQN": "DS",
        "MGNA_DVSN": "01",
        "EXCC_STAT_CD": "1",
        f"CTX_AREA_FK{target.ctx_suffix}": fk,
        f"CTX_AREA_NK{target.ctx_suffix}": nk,
    }


def _read_ctx_key(
    body: dict[str, Any], headers: dict[str, str], kind: str, suffix: str
) -> tuple[str, str]:
    """Find one continuation key and record WHERE it was found.

    The runtime never reads these keys, so the repo carries no evidence of their
    casing or location on the balance TRs. Rather than assume, this looks for both
    spellings in the body and then in the headers, and returns the location it
    actually used. ``("", "")`` means no spelling was present anywhere — which is
    an observation ("the broker returned no continuation key"), not a lookup
    failure to paper over.
    """
    lower = f"ctx_area_{kind.lower()}{suffix}"
    upper = f"CTX_AREA_{kind.upper()}{suffix}"
    for name in (lower, upper):
        if name in body:
            return str(body.get(name) or "").strip(), f"body:{name}"
    for name in (lower, upper):
        if name in headers:
            return str(headers.get(name) or "").strip(), f"header:{name}"
    return "", ""


def _key_fingerprint(value: str) -> str:
    """Non-reversible correlator for a continuation cursor.

    Fingerprinted rather than stored raw by default: a continuation cursor is
    broker-opaque and may embed account-derived material, and ``redact()`` only
    masks field names it already knows. The fingerprint is enough for the thing
    that matters here — telling whether a key ADVANCED between pages, per key.
    Pass ``--record-raw-continuation-keys`` to add the raw values.
    """
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _positive_qty_rows(rows: list[Any], qty_field: str) -> int:
    """Count rows the RUNTIME would keep (``qty > 0``) — ``client.py:1002``/``:1091``.

    Recorded alongside the raw count because pagination is over raw rows while the
    destructive consumer only ever sees the filtered ones. Conflating the two
    would make a page look emptier than it is.
    """
    kept = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            if int(float(row.get(qty_field) or 0)) > 0:
                kept += 1
        except (TypeError, ValueError):
            continue
    return kept


# ---------------------------------------------------------------------------
# P-BAL
# ---------------------------------------------------------------------------


def probe_pbal(args: argparse.Namespace) -> ProbeRun:
    """P-BAL BALANCE_PAGINATION — page size, continuation behaviour, truncation risk.

    Establishes, and records separately:

    1. **Page size** — rows returned in page 1, and whether that number is a page
       size at all (it is not, unless a second page followed).
    2. **Continuation behaviour** — whether non-empty continuation keys came back,
       where they were found, and what the ``tr_cont`` response header said.
    3. **Walk** — per-page row counts and per-KEY advance, up to ``--max-pages``.
       Both keys are recorded every page, because the prior campaign found a case
       where only one of two keys moved; a single boolean would have hidden it.
    4. **Termination cause** — broker end-of-set / our cap / error, explicitly. A
       total row count is reported ONLY on broker end-of-set. P-5b's artifact had
       to say "total unestablished" because our cap ended its walk; that is a
       first-class outcome here, not a footnote.
    5. **Truncation-risk verdict** — three-valued, from :func:`truncation_verdict`.

    Read-only in every environment. There is no order path in this module.
    """
    spec = get("P-BAL")
    asset = str(getattr(args, "asset", "") or "").strip().lower()
    env = str(getattr(args, "env", "") or "").strip().lower()
    if asset not in {"stock", "futures"}:
        raise ProbeError(f"--asset must be 'stock' or 'futures' (got {asset!r})")
    if env not in {"real", "mock"}:
        raise ProbeError(f"--env must be 'real' or 'mock' (got {env!r})")
    if int(args.max_pages) < 1:
        raise ProbeError("--max-pages must be >= 1")
    known_size = int(args.known_page_size or 0)
    if known_size < 0:
        raise ProbeError("--known-page-size must be >= 0 (0 = not supplied)")
    if known_size and not str(args.known_page_size_source or "").strip():
        raise ProbeError(
            "--known-page-size requires --known-page-size-source (the artifact_id "
            "or document the prior measurement came from). An unsourced page size "
            "would enter the verdict as if it had been measured here."
        )
    is_real = env == "real"

    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        # NOT spec.environment: the artifact must state the environment that was
        # actually contacted, because §6.2 forbids citing a MOCK_VTS artifact in a
        # REAL_PROD document (ADR-002-004 §13.14).
        environment=ENV_REAL if is_real else ENV_MOCK,
        args=vars(args),
    )
    run.observe(
        read_only_attestation=(
            "This probe can issue GET requests only, against the allowlist in "
            "tools/broker_probes/probes_balance.py::ALLOWLIST. No order path "
            "exists in this module and it does not import one."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in ALLOWLIST],
    )

    target = _TARGETS.get((asset, is_real))
    if target is None:
        # Before credential resolution on purpose: a missing-credential
        # ProbeError would replace the informative skip with a noisy failure.
        run.skip(f"{asset} balance walk on {env}", _MOCK_FUTURES_SKIP_REASON)
        run.measure("target_supported", False)
        run.measure("truncation_risk", None)
        return run
    run.measure("target_supported", True)

    warn_shared_token_cache()
    creds = resolve_credentials(asset, is_real=is_real)
    run.credentials = creds.describe()
    run.measure(
        "target",
        {
            "asset": target.asset,
            "environment": ENV_REAL if is_real else ENV_MOCK,
            "tr_id": target.tr_id,
            "path": target.path,
            "continuation_key_pair": [
                f"CTX_AREA_FK{target.ctx_suffix}",
                f"CTX_AREA_NK{target.ctx_suffix}",
            ],
            "row_qty_field": target.row_qty_field,
            "tr_id_source": (
                "shared/kis/client.py:919 (stock real/mock split), :1048 (futures)"
            ),
        },
    )

    if not args.confirm:
        dry_run_banner(spec)
        run.observe(
            would_send=(
                f"up to {args.max_pages} read-only GET {target.tr_id} calls on "
                f"{target.path}, following CTX_AREA_FK{target.ctx_suffix}/"
                f"NK{target.ctx_suffix} from each response"
            )
        )
        return run

    require_account(creds)

    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()
    base_url = REAL_BASE_URL if is_real else MOCK_BASE_URL

    pages: list[dict[str, Any]] = []
    termination = _TERM_ERROR
    termination_detail = "the walk did not execute"
    fk = nk = ""
    prev_fp = {"fk": "", "nk": ""}
    # True when the final request repeated the previous cursor position: the
    # page is preserved in observations but its rows are the SAME rows again
    # and must never enter a total (that would double-count holdings).
    duplicate_final_page = False
    try:
        for index in range(int(args.max_pages)):
            status, parsed, resp_headers, text, elapsed_ms = _get(
                session,
                auth,
                base_url=base_url,
                path=target.path,
                tr_id=target.tr_id,
                params=_balance_params(target, creds, fk=fk, nk=nk),
                tr_cont=_TR_CONT_REQUEST_NEXT if index else "",
            )
            rows = parsed.get("output1")
            rows = rows if isinstance(rows, list) else []
            rt_cd = str(parsed.get("rt_cd") or "").strip()
            next_fk, fk_where = _read_ctx_key(
                parsed, resp_headers, "fk", target.ctx_suffix
            )
            next_nk, nk_where = _read_ctx_key(
                parsed, resp_headers, "nk", target.ctx_suffix
            )
            tr_cont_out = str(resp_headers.get("tr_cont") or "").strip()

            key_records: dict[str, Any] = {}
            for kind, value, where in (
                ("fk", next_fk, fk_where),
                ("nk", next_nk, nk_where),
            ):
                fingerprint = _key_fingerprint(value)
                entry: dict[str, Any] = {
                    "present": bool(value),
                    "length": len(value),
                    "fingerprint": fingerprint,
                    "found_at": where,
                    # None on page 0: there is no previous page to advance from,
                    # so "advanced" would be a claim about nothing.
                    "advanced": (
                        None
                        if index == 0
                        else bool(fingerprint) and fingerprint != prev_fp[kind]
                    ),
                }
                if args.record_raw_continuation_keys:
                    entry["raw"] = value
                key_records[kind] = entry

            record: dict[str, Any] = {
                "page": index,
                "http_status": status,
                "rt_cd": rt_cd,
                "msg_cd": parsed.get("msg_cd"),
                "msg1": parsed.get("msg1"),
                "elapsed_ms": round(elapsed_ms, 1),
                "rows": len(rows),
                "rows_with_positive_qty": _positive_qty_rows(
                    rows, target.row_qty_field
                ),
                "output2_present": "output2" in parsed,
                "tr_cont_response": tr_cont_out,
                "tr_cont_more_code_evidenced": tr_cont_out
                in _TR_CONT_MORE_CODE_EVIDENCED,
                "continuation_keys": key_records,
                "raw_excerpt": "" if rt_cd == "0" else text[:300],
            }
            pages.append(record)
            run.observe(**record)
            prev_fp = {
                "fk": key_records["fk"]["fingerprint"],
                "nk": key_records["nk"]["fingerprint"],
            }

            is_duplicate_refetch = index > 0 and (next_fk, next_nk) == (fk, nk)

            if rt_cd != "0":
                if str(parsed.get("msg_cd") or "").strip() == _MSG_EMPTY_RESULT_SET:
                    termination = _TERM_BROKER_END
                    termination_detail = (
                        f"page {index} answered rt_cd={rt_cd!r} with "
                        f"msg_cd={_MSG_EMPTY_RESULT_SET!r} "
                        f"({str(parsed.get('msg1') or '').strip()!r}) — the "
                        "broker's empty-result-set notation, not a rejection "
                        "(wave-3 N-16 precedent; the stock sibling pairs the "
                        "same msg_cd with rt_cd='0'). Zero rows are an answer; "
                        "they establish nothing about pagination and the "
                        "page-size skip records that."
                    )
                    break
                termination = _TERM_ERROR
                termination_detail = (
                    f"the broker rejected page {index}: rt_cd={rt_cd!r} "
                    f"msg_cd={parsed.get('msg_cd')!r} msg1={parsed.get('msg1')!r}. "
                    "Nothing about pagination is established by a rejected call."
                )
                run.error(termination_detail)
                break
            if tr_cont_out and tr_cont_out not in _TR_CONT_MORE_CODE_EVIDENCED:
                termination = _TERM_BROKER_END
                termination_detail = (
                    f"page {index} answered tr_cont={tr_cont_out!r}, which is "
                    "not a more-follows code — the BROKER signalled end-of-set. "
                    "KIS's official inquire_balance example continues only on "
                    "tr_cont in ('M', 'F') and treats every other value as "
                    "fetch-complete; shared/kis/client.py:354 stops on the same "
                    "header. Continuation keys are recorded verbatim but not "
                    "walked past this signal, so the row total across counted "
                    "pages is a total, not a lower bound."
                )
                duplicate_final_page = is_duplicate_refetch
                if duplicate_final_page:
                    termination_detail += (
                        " The final page repeated the previous cursor position, "
                        "so its rows are excluded from all totals — they are the "
                        "same rows seen again, not new holdings."
                    )
                break
            if not next_fk and not next_nk:
                if tr_cont_out in _TR_CONT_MORE_CODE_EVIDENCED:
                    termination = _TERM_ERROR
                    termination_detail = (
                        f"page {index} answered tr_cont={tr_cont_out!r} (more "
                        "follows) but returned no continuation key in body or "
                        "headers — there is no cursor to request the next page "
                        "with. The row total is a lower bound, not a total."
                    )
                    run.error(termination_detail)
                    break
                termination = _TERM_BROKER_END
                termination_detail = (
                    f"page {index} returned no continuation key in body or "
                    "headers, so the BROKER signalled end-of-set. The row total "
                    "across walked pages is therefore a total, not a lower bound."
                )
                break
            if (next_fk, next_nk) == (fk, nk):
                termination = _TERM_ERROR
                termination_detail = (
                    f"continuation keys did not advance on page {index} while "
                    f"tr_cont={tr_cont_out!r} did not signal end-of-set — a "
                    "further request would repeat this page. Stopped rather than "
                    "loop; the total is unestablished."
                )
                duplicate_final_page = True
                run.error(termination_detail)
                break
            fk, nk = next_fk, next_nk
            if index + 1 < int(args.max_pages):
                time.sleep(float(args.inter_page_s))
        else:
            termination = _TERM_CAP
            termination_detail = (
                f"the walk stopped at OUR OWN --max-pages={args.max_pages} cap "
                "while the broker was still returning continuation keys. This is "
                "not end-of-set: no total row count is established (P-5b's "
                "artifact hit the same wall and had to say so)."
            )

        counted_pages = pages[:-1] if duplicate_final_page else pages
        verdict = truncation_verdict(
            page_row_counts=[int(p["rows"]) for p in counted_pages],
            termination=termination,
            known_page_size=known_size,
            known_page_size_source=str(args.known_page_size_source or ""),
        )
        run.measure("termination_cause", termination)
        run.measure("termination_detail", termination_detail)
        run.measure("truncation_risk", verdict)
        run.measure("pages_walked", len(pages))
        run.measure("duplicate_final_page_excluded_from_totals", duplicate_final_page)
        run.measure("max_pages_requested", int(args.max_pages))
        run.measure(
            "rows_with_positive_qty_total",
            sum(int(p["rows_with_positive_qty"]) for p in counted_pages),
        )
        run.measure(
            "continuation_supported",
            any(
                p["continuation_keys"]["fk"]["present"]
                or p["continuation_keys"]["nk"]["present"]
                for p in pages
            ),
        )
        run.measure(
            "continuation_key_locations",
            sorted(
                {
                    p["continuation_keys"][kind]["found_at"]
                    for p in pages
                    for kind in ("fk", "nk")
                    if p["continuation_keys"][kind]["found_at"]
                }
            ),
        )
        asymmetry = [
            {
                "page": p["page"],
                "fk_advanced": p["continuation_keys"]["fk"]["advanced"],
                "nk_advanced": p["continuation_keys"]["nk"]["advanced"],
            }
            for p in pages
            if p["continuation_keys"]["fk"]["advanced"]
            is not p["continuation_keys"]["nk"]["advanced"]
            and p["page"] > 0
        ]
        run.measure("continuation_key_asymmetry", asymmetry)
        run.measure(
            "continuation_key_asymmetry_note",
            "Pages where exactly one of the two continuation keys advanced. The "
            "prior campaign saw this shape, which is why both keys are recorded "
            "per page instead of one 'keys advanced' boolean. A non-empty list "
            "does NOT by itself mean the walk was wrong — it means the pair is "
            "not a single cursor and must not be treated as one.",
        )
        run.measure(
            "tr_cont_header_observed",
            any(bool(p["tr_cont_response"]) for p in pages),
        )
        run.measure(
            "tr_cont_access_note",
            "The tr_cont response header is read directly from the transport by "
            "this module's _get(): common.http_json discards response headers and "
            "cannot answer this question. shared/kis/client.py:341 reads the same "
            "header the same way for fetch_invest_opinion; the balance methods "
            "(:901-1114) never read it at all. 'M' and 'F' are interpreted as "
            "'more' (client.py:354; KIS's official inquire_balance example "
            "recurses on both) and any other NON-EMPTY value ends the walk as "
            "the broker's end-of-set signal — every value is also recorded "
            "verbatim per page.",
        )
        run.measure(
            "runtime_defect",
            "shared/kis/client.py:931-932 (stock) and :1055-1056 (futures) send "
            "empty continuation keys and the surrounding methods never read the "
            "response keys, the tr_cont header, or the row count. A correct walk "
            "already exists at :303-356 (fetch_invest_opinion). Futures has a "
            "second, independent defect: the runtime omits MGNA_DVSN and "
            "EXCC_STAT_CD, which REAL_PROD requires (rt_cd=7 APMP0001, measured "
            "P-BAL-20260731T084304Z) — its futures balance query therefore "
            "always folds to [] on the real domain, before pagination even "
            "starts. This probe supplements both fields per KIS's official "
            "inquire_balance example in order to measure at all.",
        )
        run.measure(
            "runtime_consumer",
            "services/trading/broker_verification.py reads a balance "
            "(:78 stock / :80 futures) and, when remove_redis_only is enabled "
            "(:105, gated :121-127), drops a position the balance did not show "
            "via remove_position(reason='broker_absent') (:187-190). Whether a "
            "truncated read can reach that branch is answered by "
            "measurements.truncation_risk.verdict and by nothing else in this "
            "artifact.",
        )
        run.measure(
            "scope",
            "One account, one TR, one moment. A page size is a property of the "
            "broker endpoint, but 'holdings below the page size' is a property of "
            "THIS account right now and expires the moment a position is opened. "
            "A MOCK_VTS run establishes nothing about REAL_PROD "
            "(ADR-002-004 §13.14).",
        )

        if verdict["holdings_total_lower_bound"] == 0:
            run.skip(
                "page-size determination",
                "the account returned zero balance rows, so there was nothing to "
                "paginate. This is inconclusive, not 'single page' and not 'no "
                "truncation risk'. Re-run against an account that holds "
                "positions.",
            )
    finally:
        session.close()
    return run


def add_balance_args(parser: argparse.ArgumentParser) -> None:
    # The shared --asset default is futures, but the target that matters here is
    # real stock: that is the environment the destructive consumer runs against.
    parser.set_defaults(asset="stock")
    parser.add_argument(
        "--env",
        choices=("real", "mock"),
        default="real",
        help=(
            "Which environment to read. Default 'real': the destructive consumer "
            "(broker_verification remove_redis_only) runs against live stock, so "
            "real stock is the target that matters. GET-only in both."
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help=(
            "Cap on pages walked (default 10). If the walk stops here the "
            "termination cause is recorded as OUR cap and NO total row count is "
            "reported."
        ),
    )
    parser.add_argument(
        "--inter-page-s",
        type=float,
        default=DEFAULT_INTER_PAGE_S,
        help=(
            f"Pause between pages (default {DEFAULT_INTER_PAGE_S}s — just above "
            "the clean 1.0 rps P-13 measured for the query class). Lowering it "
            "reopens the throttle that invalidated earlier runs."
        ),
    )
    parser.add_argument(
        "--known-page-size",
        type=int,
        default=0,
        help=(
            "A page size established by an EARLIER measurement (0 = none). It "
            "loses to a page size measured in this run and requires "
            "--known-page-size-source."
        ),
    )
    parser.add_argument(
        "--known-page-size-source",
        default="",
        help=(
            "Provenance for --known-page-size (artifact_id or document). Required "
            "whenever --known-page-size is non-zero, so a carried-in value can "
            "never be mistaken for one measured here."
        ),
    )
    parser.add_argument(
        "--record-raw-continuation-keys",
        action="store_true",
        help=(
            "Also store raw continuation-key values in the artifact. Off by "
            "default: the cursors are broker-opaque and redact() does not know "
            "their field names. Fingerprints already answer 'did this key "
            "advance'."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
