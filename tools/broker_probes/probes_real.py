"""REAL-token probes — READ-ONLY BY CONSTRUCTION (N-16, N-18).

These are the only probes in the package that touch the real
(``openapi.koreainvestment.com``) host. They therefore carry a stricter guard
than the mock probes:

* Every request goes through :func:`~tools.broker_probes.common.assert_read_only_call`,
  a three-way allowlist over (HTTP method, TR id, URL path). GET only.
* :data:`ALLOWLIST` is the complete set of calls this module may ever make. It
  contains no ``/trading/`` write path and no order TR. Adding one would require
  editing this constant, which is a reviewable change.
* There is no POST helper in this module. ``_get`` is the only transport.

Operator approval is required before running either probe: they consume a real
production credential. Neither places, amends nor cancels an order.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from tools.broker_probes.common import (
    REAL_BASE_URL,
    ProbeRun,
    ReadOnlyCall,
    SafetyViolation,
    assert_read_only_call,
    build_auth_config,
    dry_run_banner,
    http_json,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_PROGRAM_TRADE_PATH = "/uapi/domestic-stock/v1/quotations/comp-program-trade-daily"
_FUT_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
#: Night futures balance path. The DAY-session sibling is ``inquire-balance``;
#: the NIGHT TR ``CTFN6118R`` is served from a distinct ``inquire-ngt-balance``
#: endpoint. Confirmed by the N-17 spec collation, item #16
#: (``docs/plans/2026-07-29-tos-p02-n17-spec-collation.md:60``): "선물 야간
#: ``CTFN6118R``(실전 전용) ``/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance``
#: [국내선물-010]". The earlier wiring here pointed at the day path — a defect
#: this constant corrects.
_NIGHT_BALANCE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-ngt-balance"
_INDEX_CHART_PATH = "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice"

# --- FHKST03030200 parameter values -----------------------------------------
# Names come from collation #16-adjacent item #14 (:58); the VALUES below are the
# official example wrapper's own Example block for ``inquire_time_indexchartprice``
# (해외지수분봉조회 [v1_해외주식-031]). Nothing here is invented: market div code
# "N" = 해외지수 (X = 환율, KX = 원화환율), hour class "0" = 정규장 (1 = 시간외),
# past-data flag is a Y/N enumeration. ``SPX`` is the spec's own worked example
# symbol and is therefore the only VERIFIED notation on this TR.
_INDEX_MARKET_DIV_CODE = "N"
_INDEX_HOUR_CLS_CODE = "0"
_INDEX_PW_DATA_INCU_YN = "Y"
_INDEX_CONTROL_SYMBOL = "SPX"

#: Complete read-only allowlist. Any call not matching an entry is refused.
ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        "FHPPG04600001",
        _PROGRAM_TRADE_PATH,
        "N-18a program-trade daily — per-call row cap (roadmap :340-341, :391)",
    ),
    ReadOnlyCall(
        "FHMIF10000000",
        _FUT_PRICE_PATH,
        "N-18c futures current price — night-code response (roadmap :340-341)",
    ),
    ReadOnlyCall(
        "FHKST03030200",
        _INDEX_CHART_PATH,
        "N-18b — collation #14 확정·로드맵 후보 HHDFC55020100 반증. "
        "해외지수분봉조회 [v1_해외주식-031]; TR id and path from "
        "docs/plans/2026-07-29-tos-p02-n17-spec-collation.md:58, which found the "
        "roadmap:395 candidate HHDFC55020100 absent from the spec index. "
        "Read-only quotation endpoint; no /trading/ path, no account fields.",
    ),
    ReadOnlyCall(
        "CTFN6118R",
        _NIGHT_BALANCE_PATH,
        "N-16 night futures balance — response schema only (plan §1 T2:36). "
        "Read-only inquiry; the day-session sibling CTFO6118R is used the same "
        "way at shared/kis/client.py:1049 but on the DAY path "
        "(/trading/inquire-balance). The night path is inquire-ngt-balance per "
        "collation #16 (2026-07-29-tos-p02-n17-spec-collation.md:60).",
    ),
)


def _get(
    session: Any,
    auth: Any,
    path: str,
    tr_id: str,
    params: dict[str, Any],
    *,
    tr_cont: str = "",
) -> tuple[int, dict[str, Any], str, str]:
    """The ONLY transport in this module. GET, allowlisted, real host."""
    url = f"{REAL_BASE_URL}{path}"
    assert_read_only_call("GET", url, tr_id, ALLOWLIST)
    headers = dict(auth.get_auth_headers())
    headers["tr_id"] = tr_id
    headers["custtype"] = "P"
    if tr_cont:
        headers["tr_cont"] = tr_cont
    status, parsed, _ms, text = http_json(
        session, "GET", url, headers=headers, params=params, timeout=20.0
    )
    return status, parsed, text, ""


def _setup(
    spec: ProbeSpec, args: argparse.Namespace, *, asset: str = "futures"
) -> tuple[ProbeRun, Any, Any]:
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    warn_shared_token_cache()
    creds = resolve_credentials(asset, is_real=True)
    run.credentials = creds.describe()
    run.observe(
        read_only_attestation=(
            "This probe can issue GET requests only, against the allowlist in "
            "tools/broker_probes/probes_real.py::ALLOWLIST. No order path exists "
            "in this module."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in ALLOWLIST],
    )
    if not args.confirm:
        dry_run_banner(spec)
        return run, None, None
    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    return run, KISAuthManager(cfg, use_singleton=False), requests.Session()


# ---------------------------------------------------------------------------
# N-16 — night futures balance schema
# ---------------------------------------------------------------------------


def probe_n16(args: argparse.Namespace) -> ProbeRun:
    """N-16 ``CTFN6118R`` night futures balance — one call, schema capture only.

    Measures: the response schema (key lists of ``output1``/``output2``,
    ``rt_cd``/``msg_cd``/``msg1``). No numeric bound.

    Why REAL: mock serves no futures balance at all
    (``shared/kis/client.py:1030-1032``), and the night TR family exists only in
    the real namespace (``shared/execution/tr_ids.py:40-50`` has ``night_real``
    with no ``night_mock`` counterpart — quirk Q-MIC-1).

    Why it matters: ``config/kis/tr_ids.yaml`` carries zero balance TRs, so the
    audit item in ``docs/runbooks/futures-legal-review.md`` cannot be satisfied
    (plan §2:64-65). Editing ``tr_ids.yaml`` is a SEPARATE commit — this probe
    only establishes the schema.

    Session gating: the night session is 18:00-05:00 KST
    (``config/market_schedule.yaml:29-33``). Outside it, the probe refuses to run
    rather than record a possibly-empty response as the schema.
    """
    spec = get("N-16")
    run, auth, session = _setup(spec, args, asset="futures")
    if auth is None:
        run.observe(would_send="1 GET CTFN6118R inquire-ngt-balance")
        return run
    creds = resolve_credentials("futures", is_real=True)
    require_account(creds)

    now = datetime.now(KST)
    in_night = now.hour >= 18 or now.hour < 5
    if not in_night and not args.ignore_session_window:
        run.skip(
            "CTFN6118R call",
            f"local KST time {now:%H:%M} is outside the night session window "
            "18:00-05:00 (config/market_schedule.yaml:29-33). A response taken "
            "outside the window may not exercise the night schema. Re-run inside "
            "the window, or pass --ignore-session-window and label the artifact "
            "accordingly.",
        )
        session.close()
        return run
    try:
        # Param set is the OFFICIAL one for this TR ([국내선물-010]
        # examples_llm/domestic_futureoption/inquire_ngt_balance/inquire_ngt_balance.py),
        # NOT the day-sibling's: the first real-credential run
        # (N-16-20260729T132547Z) returned rt_cd=7 APMP0001 "증거금구분코드은(는)
        # 필수입력 항목입니다" against the previous day-path mirror (SORT_SQN),
        # which is itself an N-16 finding — the night TR requires MGNA_DVSN and
        # EXCC_STAT_CD and does not document SORT_SQN. The two code values below
        # are the official docstring's own example pair ("01:개시", "1:정산"),
        # not invented.
        params = {
            "CANO": creds.cano,
            "ACNT_PRDT_CD": creds.acnt_prdt_cd,
            "MGNA_DVSN": "01",
            "EXCC_STAT_CD": "1",
            "ACNT_PWD": "",
            "CTX_AREA_FK200": "",
            "CTX_AREA_NK200": "",
        }
        status, parsed, text, _ = _get(
            session, auth, _NIGHT_BALANCE_PATH, "CTFN6118R", params
        )
        out1 = parsed.get("output1")
        out2 = parsed.get("output2")
        run.observe(
            http_status=status,
            rt_cd=parsed.get("rt_cd"),
            msg_cd=parsed.get("msg_cd"),
            msg1=parsed.get("msg1"),
            raw_excerpt=("" if parsed.get("rt_cd") == "0" else text[:300]),
        )
        run.measure("top_level_keys", sorted(parsed.keys()))
        run.measure(
            "output1_keys",
            (
                sorted(out1[0].keys())
                if isinstance(out1, list) and out1
                else (sorted(out1.keys()) if isinstance(out1, dict) else [])
            ),
        )
        run.measure(
            "output2_keys",
            (
                sorted(out2[0].keys())
                if isinstance(out2, list) and out2
                else (sorted(out2.keys()) if isinstance(out2, dict) else [])
            ),
        )
        run.measure("output1_row_count", len(out1) if isinstance(out1, list) else None)
        run.measure("session_window_kst", f"{now:%Y-%m-%d %H:%M} (night={in_night})")
        run.measure(
            "empty_response_caveat",
            "An empty output1 means 'no night positions', NOT 'no such fields'. "
            "Only a non-empty row establishes the row schema; record the emptiness "
            "explicitly rather than inferring an empty schema.",
        )
        run.measure(
            "followup",
            "config/kis/tr_ids.yaml has zero balance TRs (plan §2:64). Adding "
            "CTFN6118R/CTFO6118R there is a SEPARATE commit, gated on this schema.",
        )
    finally:
        session.close()
    return run


# ---------------------------------------------------------------------------
# N-18 — real-token read-only trio
# ---------------------------------------------------------------------------


def _index_chart_leg(
    session: Any, auth: Any, run: ProbeRun, leg: str, symbol: str
) -> dict[str, Any]:
    """One ``FHKST03030200`` call for N-18b. A failure IS the observation.

    Never raises for a broker- or transport-level failure: the whole point of
    the SOX legs is that the notation is UNVERIFIED, so a rejection code is the
    finding, not an accident. A :class:`SafetyViolation` still propagates — that
    would mean the allowlist refused the call, which is a harness defect and
    must not be swallowed.
    """
    params = {
        "FID_COND_MRKT_DIV_CODE": _INDEX_MARKET_DIV_CODE,
        "FID_INPUT_ISCD": symbol,
        "FID_HOUR_CLS_CODE": _INDEX_HOUR_CLS_CODE,
        "FID_PW_DATA_INCU_YN": _INDEX_PW_DATA_INCU_YN,
    }
    outcome: dict[str, Any] = {"leg": leg, "symbol": symbol}
    try:
        status, parsed, text, _ = _get(
            session, auth, _INDEX_CHART_PATH, "FHKST03030200", params
        )
    except SafetyViolation:
        raise
    except Exception as exc:  # noqa: BLE001 — a dead call is still evidence
        outcome["transport_error"] = f"{type(exc).__name__}: {exc}"
        run.observe(sub_probe="N-18b", **outcome)
        return outcome
    rows = parsed.get("output2")
    rows = rows if isinstance(rows, list) else []
    head = parsed.get("output1")
    outcome.update(
        http_status=status,
        rt_cd=parsed.get("rt_cd"),
        msg_cd=parsed.get("msg_cd"),
        msg1=parsed.get("msg1"),
        row_count=len(rows),
        output1_keys=(sorted(head.keys()) if isinstance(head, dict) else []),
        sample_row_keys=(
            sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
        ),
        raw_excerpt=("" if parsed.get("rt_cd") == "0" else text[:300]),
    )
    run.observe(sub_probe="N-18b", **outcome)
    return outcome


def probe_n18(args: argparse.Namespace) -> ProbeRun:
    """N-18 — the three residual REAL-token read-only calls. NO ORDERS.

    Sub-probes:
      * **N-18a** ``FHPPG04600001`` per-call row cap — how many daily
        program-trade rows one call returns (drives backfill chunk sizing).
        Method: request a range wide enough to exceed any plausible cap with
        ``tr_cont`` unset, then count rows; the count IS the cap only if a
        continuation flag came back, otherwise it is merely "fewer rows than the
        cap existed in the range".
      * **N-18b** ``FHKST03030200`` overseas-index minute chart — SOX symbol
        notation. N-17 resolved the TR: collation item #14
        (``docs/plans/2026-07-29-tos-p02-n17-spec-collation.md:58``) confirms
        해외지수분봉조회 [v1_해외주식-031] at
        ``/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice`` and
        **refutes** the roadmap:395 candidate ``HHDFC55020100`` (absent from the
        spec index). Method: one control leg with the spec's own worked-example
        symbol ``SPX`` to prove the TR answers under this credential, then one
        leg per SOX candidate spelling. The candidate spellings are UNVERIFIED —
        the response codes are the finding either way, so no leg may raise.
      * **N-18c** ``FHMIF10000000`` night-code response — does the day-session
        current-price TR serve an 8-char night KOSPI200 code? An error or stale
        day data is itself the finding (it confirms night quotes are WS-only).

    Prior art: ``scripts/analysis/phase0_kis_probes.py`` runs the same three
    calls. It is left untouched; it prints to stdout and produces no JSON
    evidence artifact, which is why this harness re-implements them under the
    read-only guard with a persisted artifact.
    """
    spec = get("N-18")
    run, auth, session = _setup(spec, args, asset="futures")
    if auth is None:
        n_index = 1 + len([s for s in args.sox_symbols.split(",") if s.strip()])
        run.observe(
            would_send=(
                f"GET calls: 1x FHPPG04600001, {n_index}x FHKST03030200 "
                f"(SPX control + SOX candidates {args.sox_symbols!r}), "
                "up to 2x FHMIF10000000"
            )
        )
        return run
    try:
        # --- N-18a: program-trade daily row cap -------------------------
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=args.program_range_days)
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_MRKT_CLS_CODE": "K",
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
        }
        status, parsed, text, _ = _get(
            session, auth, _PROGRAM_TRADE_PATH, "FHPPG04600001", params
        )
        rows = parsed.get("output")
        rows = (
            rows
            if isinstance(rows, list)
            else (
                parsed.get("output1") if isinstance(parsed.get("output1"), list) else []
            )
        )
        run.observe(
            sub_probe="N-18a",
            http_status=status,
            rt_cd=parsed.get("rt_cd"),
            msg1=parsed.get("msg1"),
            row_count=len(rows),
            raw_excerpt=("" if parsed.get("rt_cd") == "0" else text[:300]),
        )
        run.measure("n18a_range_days", args.program_range_days)
        run.measure("n18a_single_call_rows", len(rows))
        run.measure("n18a_sample_row_keys", sorted(rows[0].keys()) if rows else [])
        run.measure(
            "n18a_cap_determination",
            "The row count is the per-call CAP only if the requested range plainly "
            "contained more trading days than rows returned. Otherwise it is just "
            "the number of rows available. Compare row_count against the trading "
            "days in the range before recording a cap.",
        )
        time.sleep(args.inter_call_s)

        # --- N-18b: overseas-index TR + SOX symbol notation --------------
        # TR id / path / parameter names: collation #14
        # (docs/plans/2026-07-29-tos-p02-n17-spec-collation.md:58). Parameter
        # VALUES: the spec's own worked example (see the _INDEX_* constants).
        run.measure("n18b_tr_id", "FHKST03030200")
        run.measure("n18b_path", _INDEX_CHART_PATH)
        run.measure(
            "n18b_source",
            "docs/plans/2026-07-29-tos-p02-n17-spec-collation.md:58 (item #14, "
            "확정). The roadmap:395 candidate HHDFC55020100 was NOT found in the "
            "spec index and is thereby refuted, not merely unverified.",
        )
        run.measure(
            "n18b_params_sent",
            {
                "FID_COND_MRKT_DIV_CODE": _INDEX_MARKET_DIV_CODE,
                "FID_INPUT_ISCD": "<per-leg symbol>",
                "FID_HOUR_CLS_CODE": _INDEX_HOUR_CLS_CODE,
                "FID_PW_DATA_INCU_YN": _INDEX_PW_DATA_INCU_YN,
            },
        )
        control = _index_chart_leg(
            session, auth, run, "control_spx", _INDEX_CONTROL_SYMBOL
        )
        run.measure("n18b_control_leg", control)
        run.measure(
            "n18b_control_meaning",
            f"{_INDEX_CONTROL_SYMBOL} is the notation the spec itself uses as the "
            "worked example, so this leg establishes whether the TR responds AT "
            "ALL under this credential. If the control leg fails, a failing SOX "
            "leg says nothing about SOX notation — it says the TR is unavailable.",
        )
        time.sleep(args.inter_call_s)

        candidates = [s.strip() for s in args.sox_symbols.split(",") if s.strip()]
        sox_legs: list[dict[str, Any]] = []
        if not candidates:
            run.skip(
                "N-18b SOX candidate legs",
                "--sox-symbols was emptied; only the SPX control leg ran. The TR "
                "itself is now exercised, but no SOX notation was tested.",
            )
        for symbol in candidates:
            sox_legs.append(
                _index_chart_leg(session, auth, run, "sox_candidate", symbol)
            )
            time.sleep(args.inter_call_s)
        run.measure("n18b_sox_candidates", candidates)
        run.measure("n18b_sox_legs", sox_legs)
        run.measure(
            "n18b_symbol_notation_caveat",
            "⚠ THE SOX SYMBOL NOTATION IS UNVERIFIED. Collation #14 establishes "
            "the TR id, the path and the four parameter names, and it establishes "
            "SPX as an index symbol on the FID_INPUT_ISCD field — it does NOT "
            "establish how SOX is spelled. Every candidate above is a guess at the "
            "notation, so the per-leg rt_cd/msg_cd/msg1 IS the N-18b output: a "
            "success identifies the working notation, and the set of failures "
            "records which spellings the broker rejects. Do not record a failing "
            "candidate as 'SOX is unavailable' — record it as 'this spelling was "
            "rejected'. The forward source for SOX remains Yahoo ^SOX "
            "(config/macro_sources.yaml:16), which needs no KIS call.",
        )

        # --- N-18c: night-code current price ----------------------------
        for label, code in (("day", args.day_symbol), ("night", args.night_symbol)):
            if not code:
                run.skip(f"N-18c {label} leg", "no symbol supplied")
                continue
            status, parsed, text, _ = _get(
                session,
                auth,
                _FUT_PRICE_PATH,
                "FHMIF10000000",
                {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code},
            )
            out = parsed.get("output1") or {}
            run.observe(
                sub_probe="N-18c",
                leg=label,
                symbol=code,
                http_status=status,
                rt_cd=parsed.get("rt_cd"),
                msg1=parsed.get("msg1"),
                futs_prpr=out.get("futs_prpr") if isinstance(out, dict) else None,
                futs_prdy_clpr=(
                    out.get("futs_prdy_clpr") if isinstance(out, dict) else None
                ),
                raw_excerpt=("" if parsed.get("rt_cd") == "0" else text[:300]),
            )
            time.sleep(args.inter_call_s)
        run.measure(
            "n18c_interpretation",
            "A night-code ERROR or day-stale data means REST does not serve the "
            "night session, which confirms the WS-only night capture design. A "
            "successful fresh night quote would refute it. Record the rt_cd/msg1 "
            "verbatim either way.",
        )
        run.measure(
            "order_attestation",
            "Zero order-mutating calls were possible: this module's only transport "
            "is a GET restricted to ALLOWLIST.",
        )
    finally:
        session.close()
    return run


def add_real_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--program-range-days",
        type=int,
        default=150,
        help="N-18a: calendar span requested (~100 trading days).",
    )
    parser.add_argument(
        "--day-symbol",
        default="",
        help="N-18c day-session futures code (e.g. the code in config/market_structure.yaml).",
    )
    parser.add_argument(
        "--night-symbol",
        default="",
        help="N-18c night futures code (e.g. the tr_key in config/night_futures.yaml).",
    )
    parser.add_argument(
        "--sox-symbols",
        default="SOX,.SOX,^SOX",
        help=(
            "N-18b: comma-separated SOX notation candidates tried on "
            "FHKST03030200. UNVERIFIED spellings — the broker's accept/reject "
            "code per candidate IS the probe output. The SPX control leg (the "
            "spec's own example symbol) always runs and is not listed here. "
            "Pass an empty string to run the control leg only."
        ),
    )
    parser.add_argument("--inter-call-s", type=float, default=1.0)
    parser.add_argument(
        "--ignore-session-window",
        action="store_true",
        help="N-16: run outside 18:00-05:00 KST and label the artifact.",
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
