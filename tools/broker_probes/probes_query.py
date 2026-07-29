"""Read-only 모의투자 probes and the offline structural probe.

Probes here: P-1 (offline, no network) and P-16 (read-only quotations sampling).

Neither can mutate an order: P-1 opens no socket at all, and P-16 only issues
GETs against ``/quotations/`` paths on the mock host.
"""

from __future__ import annotations

import argparse
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeError,
    ProbeRun,
    assert_mock_host,
    build_auth_config,
    dry_run_banner,
    probe_token_cache_dir,
    resolve_credentials,
    resolve_out_dir,
    summarize_latencies,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_STOCK_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
_FUT_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"

#: Request-field inventory as it is actually sent by the runtime. Transcribed
#: from ``shared/execution/executor.py`` with the line each block occupies, so a
#: reviewer can re-verify without running anything. This is a code observation,
#: not a broker specification — the authoritative field list is N-17's job.
_CODE_OBSERVED_REQUEST_FIELDS = {
    "stock_order_cash (executor.py:315-322)": [
        "CANO",
        "ACNT_PRDT_CD",
        "PDNO",
        "ORD_DVSN",
        "ORD_QTY",
        "ORD_UNPR",
    ],
    "futures_order (executor.py:386-399)": [
        "ORD_PRCS_DVSN_CD",
        "CANO",
        "ACNT_PRDT_CD",
        "SLL_BUY_DVSN_CD",
        "SHTN_PDNO",
        "ORD_QTY",
        "UNIT_PRICE",
        "NMPR_TYPE_CD",
        "KRX_NMPR_CNDT_CD",
        "CTAC_TLNO",
        "FUOP_ITEM_DVSN_CD",
        "ORD_DVSN_CD",
    ],
    "futures_rvsecncl (executor.py:613-627)": [
        "ORD_PRCS_DVSN_CD",
        "CANO",
        "ACNT_PRDT_CD",
        "RVSE_CNCL_DVSN_CD",
        "ORGN_ODNO",
        "ORD_QTY",
        "UNIT_PRICE",
        "NMPR_TYPE_CD",
        "KRX_NMPR_CNDT_CD",
        "RMN_QTY_YN",
        "CTAC_TLNO",
        "FUOP_ITEM_DVSN_CD",
        "ORD_DVSN_CD",
    ],
}


# ---------------------------------------------------------------------------
# P-1 — order identity (offline structural probe)
# ---------------------------------------------------------------------------


def probe_p1(args: argparse.Namespace) -> ProbeRun:
    """P-1 ORDER_IDENTITY — is there a client-supplied order-id field?

    Measures: ``capabilities.client_generated_order_id.status``
    (UNKNOWN -> UNSUPPORTED or VERIFIED).

    This probe issues NO request. Behavioural probing cannot answer the question:
    absence of an echo proves nothing about the field's existence in the spec.
    What it can do honestly is two things:

    1. record the exact request-field inventory the runtime sends today
       (:data:`_CODE_OBSERVED_REQUEST_FIELDS`), and
    2. re-verify by grep that no client-identifier field appears in any order
       body in the repo — an anti-phantom check for the *absence* claim in the
       draft memo §3.1 row 1.

    The authoritative determination is N-17 (official-spec cross-check). Until
    N-17 lands, the honest status is UNKNOWN, not UNSUPPORTED: our not sending a
    field is not evidence that the broker offers none.
    """
    spec = get("P-1")
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live",
        environment=spec.environment,
        args=vars(args),
    )
    from pathlib import Path

    repo = Path(__file__).resolve().parents[2]
    executor = repo / "shared" / "execution" / "executor.py"
    if not executor.exists():
        raise ProbeError(f"expected {executor} to exist")
    text = executor.read_text(encoding="utf-8")

    # Anti-phantom: verify the ABSENCE claim by grep, not by assertion.
    candidates = ["ORD_ID", "CLNT_ORD", "CLIENT_ORDER", "CLORDID", "USER_ORD", "MY_ORD"]
    found = {
        token: len(re.findall(token, text, flags=re.IGNORECASE)) for token in candidates
    }
    present = {k: v for k, v in found.items() if v}

    run.measure("code_observed_request_fields", _CODE_OBSERVED_REQUEST_FIELDS)
    run.measure("client_identifier_token_grep", found)
    run.measure(
        "absence_verified",
        not present,
    )
    run.measure(
        "broker_assigned_identifier",
        "ODNO is read from the response (executor.py:335, :412) — the identifier "
        "originates at the broker.",
    )
    run.measure(
        "status_determination",
        "UNKNOWN until N-17. 'We do not send one' does not establish 'the broker "
        "offers none'. Only the official order-request field list can promote this "
        "to UNSUPPORTED or VERIFIED.",
    )
    run.measure("blocked_on", "N-17 (runbook §7 checklist item 1)")
    if present:
        run.error(
            f"unexpected client-identifier tokens present: {present} — re-read the code"
        )
    return run


# ---------------------------------------------------------------------------
# P-16 — broker time
# ---------------------------------------------------------------------------


def probe_p16(args: argparse.Namespace) -> ProbeRun:
    """P-16 BROKER_TIME — broker clock vs local KST skew.

    Measures: ``capabilities.broker_time.timezone`` / ``precision`` / skew bound.

    Context (draft §3.1 row 16): ``grep server_time|broker_time`` over
    ``shared/kis/`` returns 0 hits — the runtime uses the local clock everywhere
    (``executor.py:546``, ``:449``, ``:452``). If the broker does not expose a
    server timestamp at all, that itself is the finding and BROKER_TIME stays
    UNKNOWN.

    Method: repeated read-only quotations calls; for each, capture the HTTP
    ``Date`` header and any timestamp-looking body field, and compute the signed
    skew against the local KST clock taken at request midpoint.

    Statistic: the bound is ``max |skew|`` plus margin, but the SIGN distribution
    is reported separately — a consistently one-sided skew is a different hazard
    from symmetric jitter and must not be collapsed into an absolute value.
    Network round-trip is an unavoidable additive error; half the round-trip is
    recorded per sample so the approver can discount it.
    """
    spec = get("P-16")
    if not args.symbol:
        raise ProbeError("--symbol is required (a benign quotations target)")
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live",
        environment=spec.environment,
        args=vars(args),
    )
    warn_shared_token_cache()
    creds = resolve_credentials(args.asset, is_real=False)
    run.credentials = creds.describe()
    if not args.confirm:
        run.mode = "dry-run"
        dry_run_banner(spec)
        run.observe(
            would_send=f"{args.samples} read-only quotations GETs on the mock host"
        )
        return run

    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()

    is_futures = args.asset == "futures"
    path = _FUT_PRICE_PATH if is_futures else _STOCK_PRICE_PATH
    tr_id = "FHMIF10000000" if is_futures else "FHKST01010100"
    params = (
        {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": args.symbol}
        if is_futures
        else {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": args.symbol}
    )
    url = f"{MOCK_BASE_URL}{path}"
    assert_mock_host(url)

    skews: list[float] = []
    abs_skews: list[float] = []
    header_seen = False
    body_time_keys: set[str] = set()
    try:
        for index in range(args.samples):
            headers = dict(auth.get_auth_headers())
            headers["tr_id"] = tr_id
            headers["custtype"] = "P"
            t_start = time.time()
            response = session.get(url, headers=headers, params=params, timeout=10)
            t_end = time.time()
            midpoint = (t_start + t_end) / 2.0
            rtt_ms = (t_end - t_start) * 1000.0
            date_header = response.headers.get("Date", "")
            skew_ms: float | None = None
            if date_header:
                header_seen = True
                try:
                    from email.utils import parsedate_to_datetime

                    broker_dt = parsedate_to_datetime(date_header)
                    skew_ms = (broker_dt.timestamp() - midpoint) * 1000.0
                except Exception as exc:  # noqa: BLE001
                    run.observe(sample=index, date_header_parse_error=str(exc))
            try:
                body = response.json()
            except ValueError:
                body = {}
            output = body.get("output1") or body.get("output") or {}
            if isinstance(output, dict):
                body_time_keys |= {
                    key
                    for key in output
                    if any(tok in key.lower() for tok in ("tm", "time", "hour", "dt"))
                }
            if skew_ms is not None:
                skews.append(skew_ms)
                abs_skews.append(abs(skew_ms))
            run.observe(
                sample=index,
                date_header=date_header,
                skew_ms=round(skew_ms, 1) if skew_ms is not None else None,
                rtt_ms=round(rtt_ms, 1),
                local_kst=datetime.now(KST).isoformat(),
            )
            time.sleep(args.inter_trial_s)

        if not header_seen:
            run.skip(
                "skew measurement",
                "no HTTP Date header returned — the broker exposes no usable "
                "server clock on this endpoint. BROKER_TIME stays UNKNOWN "
                "(consistent with the 0-hit grep in draft §3.1 row 16).",
            )
        run.measure(
            "abs_skew_bound_candidate",
            summarize_latencies(
                abs_skews, margin_pct=args.margin_pct, label="abs_skew_ms"
            ),
        )
        run.measure(
            "signed_skew",
            {
                "n": len(skews),
                "min_ms": round(min(skews), 1) if skews else None,
                "max_ms": round(max(skews), 1) if skews else None,
                "all_same_sign": bool(skews)
                and (all(s >= 0 for s in skews) or all(s <= 0 for s in skews)),
                "note": "A one-sided skew is a systematic offset (correctable); "
                "a two-sided spread is jitter (not correctable). They imply "
                "different treatments and must not be merged.",
            },
        )
        run.measure(
            "rtt_confound",
            "The HTTP Date header has 1-second granularity, so a sub-second skew is "
            "not resolvable from it. Treat any |skew| below ~1000 ms as 'within "
            "header resolution', not as a measurement.",
        )
        run.measure("body_timestamp_like_keys", sorted(body_time_keys))
        run.measure(
            "precision_determination",
            "Record precision from the field actually used, not from the finest "
            "field present. If only HHMMSS fields exist, precision is 1 s.",
        )
    finally:
        session.close()
    return run


def add_query_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--inter-trial-s", type=float, default=1.0, help="Pause between samples."
    )
    parser.add_argument(
        "--poll-ms", type=float, default=200.0, help="Unused by P-1; kept for symmetry."
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
