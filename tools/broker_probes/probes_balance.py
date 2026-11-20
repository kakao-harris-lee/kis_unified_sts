"""P-BAL — balance-query pagination probe. READ-ONLY BY CONSTRUCTION."""

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

_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"

_FUT_BALANCE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-balance"

_STOCK_TR_REAL = "TTTC8434R"
_STOCK_TR_MOCK = "VTTC8434R"

_FUT_TR_REAL = "CTFO6118R"

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
    ctx_suffix: str
    row_qty_field: str


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


_TR_CONT_MORE_CODE_EVIDENCED = ("M", "F")

_TR_CONT_REQUEST_NEXT = "N"

_MSG_EMPTY_RESULT_SET = "KIOK0560"


_TERM_BROKER_END = "BROKER_END_OF_SET"
_TERM_CAP = "OUR_MAX_PAGES_CAP"
_TERM_ERROR = "ERROR"

_TERMINATION_CAUSES = (_TERM_BROKER_END, _TERM_CAP, _TERM_ERROR)


_RISK_DEMONSTRATED = "TRUNCATION_RISK_DEMONSTRATED"
_RISK_NOT_DEMONSTRATED = "TRUNCATION_RISK_NOT_DEMONSTRATED"
_RISK_UNESTABLISHED = "TRUNCATION_RISK_UNESTABLISHED"

_VERDICTS = (_RISK_DEMONSTRATED, _RISK_NOT_DEMONSTRATED, _RISK_UNESTABLISHED)

_PAGE_SIZE_MEASURED = "MEASURED_MULTI_PAGE_WALK"
_PAGE_SIZE_OPERATOR = "OPERATOR_SUPPLIED_PRIOR_MEASUREMENT"
_PAGE_SIZE_UNESTABLISHED = "UNESTABLISHED"

DEFAULT_INTER_PAGE_S = 1.1


def truncation_verdict(
    *,
    page_row_counts: list[int],
    termination: str,
    known_page_size: int = 0,
    known_page_size_source: str = "",
) -> dict[str, Any]:
    """Derive the three-valued truncation verdict from the walk. PURE function."""
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
    """The ONLY transport in this module. GET, allowlisted, headers preserved."""
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
    """Mirror the runtime's balance params, with the continuation keys USABLE."""
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
    """Find one continuation key and record WHERE it was found."""
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
    """Non-reversible correlator for a continuation cursor."""
    if not value:
        return ""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _positive_qty_rows(rows: list[Any], qty_field: str) -> int:
    """Count rows the RUNTIME would keep (``qty > 0``) — ``client.py:1002``/``:1091``."""
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


def probe_pbal(args: argparse.Namespace) -> ProbeRun:
    """P-BAL BALANCE_PAGINATION — page size, continuation behaviour, truncation risk."""
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
