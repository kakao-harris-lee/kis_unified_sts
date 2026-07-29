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
_NIGHT_BALANCE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-balance"

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
        "CTFN6118R",
        _NIGHT_BALANCE_PATH,
        "N-16 night futures balance — response schema only (plan §1 T2:36). "
        "Read-only inquiry; the day-session sibling CTFO6118R is used the same "
        "way at shared/kis/client.py:1049.",
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
        run.observe(would_send="1 GET CTFN6118R inquire-balance")
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
        params = {
            "CANO": creds.cano,
            "ACNT_PRDT_CD": creds.acnt_prdt_cd,
            "SORT_SQN": "DS",
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


def probe_n18(args: argparse.Namespace) -> ProbeRun:
    """N-18 — the three residual REAL-token read-only calls. NO ORDERS.

    Sub-probes:
      * **N-18a** ``FHPPG04600001`` per-call row cap — how many daily
        program-trade rows one call returns (drives backfill chunk sizing).
        Method: request a range wide enough to exceed any plausible cap with
        ``tr_cont`` unset, then count rows; the count IS the cap only if a
        continuation flag came back, otherwise it is merely "fewer rows than the
        cap existed in the range".
      * **N-18b** SOX symbol notation — SKIPPED by default. The KIS overseas-index
        TR is not implemented anywhere in this repo; the only reference is
        ``docs/plans/2026-07-02-unified-investment-system-roadmap.md:395`` naming
        ``HHDFC55020100`` as a *candidate*. Inventing a TR id and path here would
        be exactly the phantom-citation failure the P0-2 discipline forbids, so
        the sub-probe declares the skip and defers to N-17.
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
        run.observe(
            would_send="3 GET calls: FHPPG04600001, (SOX skipped), FHMIF10000000"
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

        # --- N-18b: SOX symbol notation ---------------------------------
        run.skip(
            "N-18b SOX symbol notation (KIS overseas index TR)",
            "No KIS overseas-index TR is implemented in this repo; the only "
            "reference is roadmap:395 naming HHDFC55020100 as a candidate, which "
            "is not a verified TR id or path. Asserting one here would be a "
            "phantom citation. Resolve the TR id + path under N-17 first, add it "
            "to ALLOWLIST, then re-run. The forward source for SOX is Yahoo ^SOX "
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
    parser.add_argument("--inter-call-s", type=float, default=1.0)
    parser.add_argument(
        "--ignore-session-window",
        action="store_true",
        help="N-16: run outside 18:00-05:00 KST and label the artifact.",
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
