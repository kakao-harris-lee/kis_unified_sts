"""Rate-limit, session and credential probes — 모의투자, no order mutation."""

from __future__ import annotations

import argparse
import time
from typing import Any

from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeError,
    ProbeRun,
    assert_mock_host,
    build_auth_config,
    dry_run_banner,
    http_json,
    is_rate_limited,
    probe_token_cache_dir,
    resolve_credentials,
    resolve_out_dir,
    summarize_latencies,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

_STOCK_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
_FUT_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_TOKEN_PATH = "/oauth2/tokenP"
_APPROVAL_PATH = "/oauth2/Approval"
_WS_URL_MOCK = "ws://ops.koreainvestment.com:31000"


def _setup(spec: ProbeSpec, args: argparse.Namespace) -> tuple[ProbeRun, Any]:
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    warn_shared_token_cache()
    creds = resolve_credentials(args.asset, is_real=False)
    run.credentials = creds.describe()
    return run, creds


def probe_p13(args: argparse.Namespace) -> ProbeRun:
    """P-13 RATE_LIMITS — stepwise ramp to the first throttle, then recovery time."""
    spec = get("P-13")
    run, creds = _setup(spec, args)
    if not args.confirm:
        dry_run_banner(spec)
        run.observe(
            would_send=f"read-only {args.endpoint_class} calls ramping "
            f"{args.start_rps}->{args.max_rps} rps in {args.step_rps} steps"
        )
        return run
    if args.endpoint_class != "query":
        raise ProbeError(
            "only --endpoint-class query is implemented. submit/cancel rate "
            "classes would emit orders; measure them with a dedicated, "
            "separately-reviewed run (runbook §5, HIGH risk)."
        )
    if not args.symbol:
        raise ProbeError("--symbol is required (a benign quotations target)")

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

    def one_call() -> tuple[bool, int, dict[str, Any], str]:
        headers = dict(auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        status, parsed, _ms, text = http_json(
            session, "GET", url, headers=headers, params=params, timeout=10.0
        )
        return is_rate_limited(status, parsed, text), status, parsed, text

    throttle_at: float | None = None
    throttled_rate: float | None = None
    last_clean_rate: float | None = None
    signal: dict[str, Any] = {}
    try:
        rate = float(args.start_rps)
        while rate <= args.max_rps:
            interval = 1.0 / rate
            planned = max(1, int(rate * args.hold_seconds))
            sent = 0
            hit = False
            for _ in range(planned):
                limited, status, parsed, text = one_call()
                sent += 1
                if limited:
                    hit = True
                    throttle_at = time.monotonic()
                    throttled_rate = rate
                    signal = {
                        "http_status": status,
                        "msg_cd": parsed.get("msg_cd"),
                        "msg1": parsed.get("msg1"),
                        "raw_excerpt": text[:200],
                    }
                    break
                time.sleep(interval)
            run.observe(step_rps=rate, calls_sent=sent, throttled=hit)
            if hit:
                print(
                    f"  limit signal at {rate} rps after {sent} calls — stopping ramp immediately"
                )
                break
            last_clean_rate = rate
            rate += args.step_rps
            time.sleep(args.step_gap_seconds)

        if throttle_at is None:
            run.measure(
                "verdict",
                f"no limit signal up to {args.max_rps} rps — the broker limit is "
                "ABOVE the tested ceiling. hard_limits stays empty; do NOT record "
                "the ceiling as the limit.",
            )
        else:
            recovered_at: float | None = None
            attempts = 0
            deadline = throttle_at + args.recovery_timeout_s
            while time.monotonic() < deadline:
                time.sleep(args.recovery_poll_s)
                attempts += 1
                limited, status, parsed, _text = one_call()
                if not limited and status == 200 and parsed.get("rt_cd") == "0":
                    recovered_at = time.monotonic()
                    break
            if recovered_at is None:
                run.error(
                    f"did not recover within {args.recovery_timeout_s}s — CENSORED; "
                    "the recovery bound is at least this large"
                )
            else:
                run.measure(
                    "B_rate_limit_recovery_candidate",
                    summarize_latencies(
                        [(recovered_at - throttle_at) * 1000.0],
                        margin_pct=args.margin_pct,
                        label="throttle_to_first_success_ms",
                    ),
                )
                run.measure("recovery_poll_granularity_s", args.recovery_poll_s)
                run.measure("recovery_attempts", attempts)
        run.measure("throttled_at_rps", throttled_rate)
        run.measure("highest_clean_rps", last_clean_rate)
        run.measure("limit_signal", signal)
        run.measure(
            "scope_note",
            "hard_limits must be recorded WITH its scope: this observation is for "
            f"one account, one session, endpoint_class={args.endpoint_class}, "
            "asset=" + args.asset + ", on 모의투자 only. VP-002:762 scopes "
            "B_rate_limit_recovery 'per broker, account, session, and endpoint class'.",
        )
        run.measure(
            "lower_bound_note",
            "highest_clean_rps is a LOWER BOUND on the broker limit, not the limit. "
            "throttled_at_rps is an UPPER BOUND. Record the interval, not a point.",
        )
        run.measure(
            "self_imposed_caps_are_not_evidence",
            "config/execution.yaml (5 rps) and shared/execution/rate_limiter.py "
            "(20 rps default) are our own caps, not measured broker limits "
            "(draft §5 Q-RATE-1). They must not be copied into hard_limits.",
        )
    finally:
        session.close()
    return run


def probe_p14(args: argparse.Namespace) -> ProbeRun:
    """P-14 SESSION_CONNECTION_MODEL — concurrent WS sessions and subscription cap."""
    spec = get("P-14")
    run, creds = _setup(spec, args)
    if not args.confirm:
        dry_run_banner(spec)
        run.observe(
            would_open=f"up to {args.max_sessions} WS sessions and "
            f"{args.max_subscriptions} subscriptions against {_WS_URL_MOCK}"
        )
        return run
    if not args.symbol:
        raise ProbeError("--symbol is required (subscription target, e.g. 005930)")

    import requests
    import websocket

    approval_url = f"{MOCK_BASE_URL}{_APPROVAL_PATH}"
    assert_mock_host(approval_url)
    resp = requests.post(
        approval_url,
        json={
            "grant_type": "client_credentials",
            "appkey": creds.app_key,
            "secretkey": creds.app_secret,
        },
        headers={"content-type": "application/json"},
        timeout=15,
    )
    data = resp.json() if resp.content else {}
    approval_key = data.get("approval_key")
    if not approval_key:
        run.error(f"approval key not issued: {data.get('msg_cd')} {data.get('msg1')}")
        return run
    run.observe(approval_key_issued=True, transport=_WS_URL_MOCK, plaintext_ws=True)

    conns: list[Any] = []
    try:
        accepted = 0
        for index in range(args.max_sessions):
            try:
                conn = websocket.create_connection(_WS_URL_MOCK, timeout=10)
                conns.append(conn)
                accepted += 1
            except Exception as exc:  # noqa: BLE001 - the refusal IS the finding
                run.observe(
                    session_index=index,
                    refused=True,
                    error=f"{type(exc).__name__}: {exc}",
                )
                break
            time.sleep(args.inter_trial_s)
        run.measure("concurrent_sessions_accepted", accepted)
        run.measure(
            "concurrent_sessions_verdict",
            f"accepted {accepted}; ceiling tested was {args.max_sessions}. If "
            "accepted == max_sessions the cap is ABOVE the tested ceiling — do not "
            "record the ceiling as the cap.",
        )
        run.measure(
            "displacement_check",
            "MANUAL: confirm whether opening session N invalidated session N-1 "
            "(watch for a server close frame on the earlier connections). A "
            "displacing broker means concurrent_sessions is effectively 1.",
        )

        if not conns:
            run.skip("subscription cap", "no WebSocket session was established")
        else:
            conn = conns[0]
            subscribed = 0
            for index in range(args.max_subscriptions):
                frame = {
                    "header": {
                        "approval_key": approval_key,
                        "custtype": "P",
                        "tr_type": "1",
                        "content-type": "utf-8",
                    },
                    "body": {"input": {"tr_id": "H0STCNT0", "tr_key": args.symbol}},
                }
                try:
                    import json as _json

                    conn.send(_json.dumps(frame))
                    reply = conn.recv()
                    subscribed += 1
                    if "msg_cd" in str(reply) and "OPSP" in str(reply):
                        run.observe(
                            subscription_index=index, rejected_reply=str(reply)[:200]
                        )
                        break
                except Exception as exc:  # noqa: BLE001
                    run.observe(
                        subscription_index=index, error=f"{type(exc).__name__}: {exc}"
                    )
                    break
                time.sleep(0.05)
            run.measure("subscriptions_accepted", subscribed)
            run.measure(
                "subscription_cap_note",
                "config/streaming.yaml:50 asserts 'KIS 제한: 41' as a comment. The "
                "draft memo §5:211-216 classes that as unverified. Only this "
                "observation may promote or refute it.",
            )
            run.measure(
                "single_symbol_caveat",
                "Subscribing the SAME tr_key repeatedly may be deduplicated by the "
                "broker, so this count may understate the cap. Establishing a true "
                "cap needs DISTINCT symbols per subscription, which this probe does "
                "not yet support (--symbol takes one code). Record the count as a "
                "single-symbol observation, not as the subscription limit.",
            )
    finally:
        for conn in conns:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    return run


def _issue_token_raw(
    session: Any, creds: Any
) -> tuple[int, dict[str, Any], float, str]:
    """Raw ``/oauth2/tokenP`` POST — deliberately unwrapped."""
    url = f"{creds.base_url}{_TOKEN_PATH}"
    assert_mock_host(url)
    return http_json(
        session,
        "POST",
        url,
        headers={"content-type": "application/json"},
        json_body={
            "grant_type": "client_credentials",
            "appkey": creds.app_key,
            "appsecret": creds.app_secret,
        },
        timeout=20.0,
    )


def probe_p15(args: argparse.Namespace) -> ProbeRun:
    """P-15 CREDENTIALS_AUTHORIZATION — reissue twice inside one minute."""
    spec = get("P-15")
    run, creds = _setup(spec, args)
    if not args.confirm:
        dry_run_banner(spec)
        run.observe(would_send="two /oauth2/tokenP POSTs separated by --reissue-gap-s")
        return run
    import requests

    session = requests.Session()
    try:
        s1, d1, ms1, t1 = _issue_token_raw(session, creds)
        run.observe(
            attempt=1,
            http_status=s1,
            ms=round(ms1, 1),
            has_access_token="access_token" in d1,
            expires_in=d1.get("expires_in"),
            msg_cd=d1.get("msg_cd"),
            msg1=d1.get("msg1"),
            raw_excerpt=("" if "access_token" in d1 else t1[:200]),
        )
        time.sleep(args.reissue_gap_s)
        s2, d2, ms2, t2 = _issue_token_raw(session, creds)
        run.observe(
            attempt=2,
            http_status=s2,
            ms=round(ms2, 1),
            has_access_token="access_token" in d2,
            expires_in=d2.get("expires_in"),
            msg_cd=d2.get("msg_cd"),
            msg1=d2.get("msg1"),
            raw_excerpt=("" if "access_token" in d2 else t2[:200]),
        )
        run.measure("reissue_gap_s", args.reissue_gap_s)
        run.measure(
            "second_attempt_rejected",
            "access_token" not in d2,
        )
        run.measure(
            "rejection_semantics",
            {"http_status": s2, "msg_cd": d2.get("msg_cd"), "msg1": d2.get("msg1")},
        )
        run.measure(
            "expires_in_observed",
            {
                "attempt_1": d1.get("expires_in"),
                "attempt_2": d2.get("expires_in"),
                "note": "The runtime falls back to 86400 when expires_in is absent "
                "(shared/kis/auth.py:472, :583). That fallback is OUR default, "
                "not a broker guarantee — record only what the broker returned.",
            },
        )
        if "access_token" in d2:
            run.measure(
                "verdict",
                "The documented 1-per-minute reissue limit was NOT observed at this "
                "gap. Either the limit is not enforced on 모의, or it applies at a "
                "different granularity. Widen the gap sweep before concluding.",
            )
    finally:
        session.close()
    return run


_N15_HELD_TOKEN_NOTE = (
    "reissue_refusal_window and held_token_usable are DIFFERENT measurements. "
    "invalidate() unlinks a local cache file (shared/kis/auth.py:396-405); it does "
    "not revoke the token at the broker. A process that kept the token string in "
    "memory may keep transacting through the whole refusal window. Only the window "
    "in which NO usable credential exists feeds B_egress_hard_fence."
)

_HELD_OK = "ACCEPTED"
_HELD_REJECTED = "REJECTED"
_HELD_UNKNOWN = "UNDETERMINED"

_N15_REJECTION_REACHABILITY_NOTE = (
    "REJECTED is asserted only on HTTP 401/403. KIS also signals failures as "
    "200+rt_cd!=0, and if a token rejection arrives in THAT shape this probe "
    "records UNDETERMINED, not REJECTED — the mapping is unmeasured and inventing "
    "it would let a business rejection masquerade as a credential failure. So "
    "REJECTED may be unreachable on this surface. An all-UNDETERMINED tally means "
    "the question was not answered; it does NOT mean the held token kept working, "
    "and nothing may be written into B_egress_hard_fence from it. To make REJECTED "
    "reachable, first measure the rejection code by presenting a known-bad token."
)


def _held_token_usable(
    session: Any, creds: Any, token: str, args: argparse.Namespace
) -> tuple[str, dict[str, Any]]:
    """Is the token this process already holds still accepted by the broker?"""
    is_futures = args.asset == "futures"
    path = _FUT_PRICE_PATH if is_futures else _STOCK_PRICE_PATH
    url = f"{MOCK_BASE_URL}{path}"
    assert_mock_host(url)
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": creds.app_key,
        "appsecret": creds.app_secret,
        "tr_id": "FHMIF10000000" if is_futures else "FHKST01010100",
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": "F" if is_futures else "J",
        "FID_INPUT_ISCD": args.symbol,
    }
    try:
        status, parsed, _ms, text = http_json(
            session, "GET", url, headers=headers, params=params, timeout=10.0
        )
    except Exception as exc:  # noqa: BLE001 - a transport failure is not a verdict
        return _HELD_UNKNOWN, {"transport_error": f"{type(exc).__name__}: {exc}"}
    evidence = {
        "http_status": status,
        "rt_cd": parsed.get("rt_cd"),
        "msg_cd": parsed.get("msg_cd"),
        "msg1": parsed.get("msg1"),
        "raw_excerpt": text[:160],
    }
    if is_rate_limited(status, parsed, text):
        return _HELD_UNKNOWN, evidence
    if status == 200 and parsed.get("rt_cd") == "0":
        return _HELD_OK, evidence
    if status in (401, 403):
        return _HELD_REJECTED, evidence
    return _HELD_UNKNOWN, evidence


def _backoff_schedule(args: argparse.Namespace) -> list[float]:
    """Sleep before each reissue retry, in order."""
    delays: list[float] = []
    delay = max(float(args.reissue_poll_s), 0.0)
    for _ in range(max(int(args.blackout_max_attempts) - 1, 0)):
        delays.append(min(delay, float(args.blackout_backoff_max_s)))
        delay *= max(float(args.blackout_backoff_factor), 1.0)
    return delays


def probe_n15(args: argparse.Namespace) -> ProbeRun:
    """N-15 token blackout — 1-minute reissue limit x invalidate→retry interaction."""
    spec = get("N-15")
    run, creds = _setup(spec, args)
    if not args.confirm:
        dry_run_banner(spec)
        run.observe(
            would_do="issue -> invalidate -> widening reissue attempts until "
            "success, sampling held-token usability at each step"
        )
        return run
    import requests

    from shared.kis.auth import KISAuthManager

    cache_dir = probe_token_cache_dir(args.token_cache_dir)
    cfg = build_auth_config(creds, cache_dir)
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()
    schedule = _backoff_schedule(args)
    run.observe(
        private_token_cache=str(cache_dir),
        safety_note="invalidate() unlinks the cache file (shared/kis/auth.py:402-405); "
        "the probe uses its own directory so runtime workers are unaffected.",
        token_calls_budget_per_trial=int(args.blackout_max_attempts),
        backoff_schedule_s=[round(d, 1) for d in schedule],
    )
    if not args.symbol:
        run.skip(
            "held-token usability",
            "--symbol not given, so no authenticated read was available to ask "
            "whether the token already held still authorizes. The reissue window "
            "below is therefore NOT a usable-credential window and must not be "
            "read as one.",
        )
    blackouts: list[float] = []
    pre_existing_bounds: list[float] = []
    censored_trials = 0
    max_refused_gap_s = 0.0
    held_samples: list[str] = []
    token_calls = 0
    try:
        for trial in range(args.trials):
            held_token = ""
            origin = "POST_INVALIDATE"
            try:
                held_token = auth.get_token()
            except Exception as exc:  # noqa: BLE001 - a refusal here IS the observation
                origin = "PRE_EXISTING_REFUSAL"
                run.observe(
                    trial=trial,
                    initial_token="REFUSED",
                    detail=f"{type(exc).__name__}: {exc}",
                    reading="a blackout was already in progress when this trial "
                    "started, so the window recorded below is a LOWER bound on it "
                    "— its start is unobserved",
                )
            started_at = time.monotonic()
            if origin == "POST_INVALIDATE" and not args.blackout_observe_only:
                auth.invalidate()
            attempts = 0
            first_success: float | None = None
            rejections: list[dict[str, Any]] = []
            last_attempt_at = started_at
            for step in range(int(args.blackout_max_attempts)):
                if time.monotonic() - started_at > args.blackout_timeout_s:
                    break
                attempts += 1
                token_calls += 1
                now = time.monotonic()
                gap_s = now - last_attempt_at
                last_attempt_at = now
                status, data, _ms, text = _issue_token_raw(session, creds)
                if "access_token" in data:
                    first_success = time.monotonic()
                    break
                max_refused_gap_s = max(max_refused_gap_s, gap_s)
                held_state, held_evidence = (
                    _held_token_usable(session, creds, held_token, args)
                    if (held_token and args.symbol)
                    else (_HELD_UNKNOWN, {"reason": "no held token or no --symbol"})
                )
                held_samples.append(held_state)
                rejections.append(
                    {
                        "attempt": attempts,
                        "at_ms": round((time.monotonic() - started_at) * 1000.0, 1),
                        "gap_since_prev_attempt_s": round(gap_s, 1),
                        "http_status": status,
                        "msg_cd": data.get("msg_cd"),
                        "msg1": data.get("msg1"),
                        "raw_excerpt": text[:160],
                        "held_token": held_state,
                        "held_token_evidence": held_evidence,
                    }
                )
                if step < len(schedule):
                    time.sleep(schedule[step])
            if first_success is None:
                censored_trials += 1
                run.error(
                    f"trial {trial}: no successful reissue within "
                    f"{round(time.monotonic() - started_at, 1)}s over {attempts} "
                    "attempts — CENSORED; the refusal window is at least this long"
                )
            elif origin == "PRE_EXISTING_REFUSAL":
                pre_existing_bounds.append((first_success - started_at) * 1000.0)
            else:
                blackouts.append((first_success - started_at) * 1000.0)
            run.observe(
                trial=trial,
                origin=origin,
                observe_only=bool(args.blackout_observe_only),
                attempts=attempts,
                rejections=rejections,
            )
            time.sleep(args.inter_trial_s)

        run.measure(
            "token_blackout_window_candidate",
            summarize_latencies(
                blackouts, margin_pct=args.margin_pct, label="invalidate_to_reissue_ms"
            ),
        )
        run.measure(
            "token_blackout_window_candidate_origin",
            "POST_INVALIDATE trials only — PRE_EXISTING_REFUSAL samples are "
            "reported separately under pre_existing_refusal_lower_bound_ms and are "
            "NOT summarised here, because their start instant is unobserved and "
            "pooling them would understate a hard-maximum bound.",
        )
        run.measure(
            "pre_existing_refusal_lower_bound_ms",
            (
                {
                    "samples": [round(v, 1) for v in pre_existing_bounds],
                    "max": (
                        round(max(pre_existing_bounds), 1)
                        if pre_existing_bounds
                        else None
                    ),
                    "provenance": "CENSORED_LOWER_BOUND — the blackout was already "
                    "under way when the trial started, so each sample is a LOWER bound "
                    "on that trial's true window and none of them may be summarised as "
                    "a measured value",
                }
                if pre_existing_bounds
                else None
            ),
        )
        run.measure(
            "reissue_refusal_lower_bound",
            _refusal_lower_bound(censored_trials, blackouts, pre_existing_bounds),
        )
        run.measure("reissue_refusal_survived_gap_s", round(max_refused_gap_s, 1))
        run.measure("token_endpoint_calls_made", token_calls)
        run.measure("held_token_usability_samples", _tally(held_samples))
        run.measure("held_token_note", _N15_HELD_TOKEN_NOTE)
        run.measure(
            "held_token_rejection_reachability", _N15_REJECTION_REACHABILITY_NOTE
        )
        run.measure("reissue_poll_schedule_s", [round(d, 1) for d in schedule])
        run.measure(
            "interaction_verdict",
            "A refusal window > 0 confirms the plan §2:68 interaction risk ONLY "
            "when held_token_usability_samples shows the previously issued token "
            "was also rejected. A refusal window with the held token still "
            "ACCEPTED is a reissue cooldown, not an egress blackout, and must not "
            "be written into B_egress_hard_fence as one. A window ~= 0 means the "
            "limit did not bind on this attempt — it does NOT prove it is absent.",
        )
        run.measure(
            "shared_app_key_scope",
            "The reissue limit is per app key, and every worker shares it "
            "(config/kis/auth.yaml:7-8). The measured blackout applies to the "
            "whole fleet, not one process.",
        )
    finally:
        session.close()
    return run


def _tally(samples: list[str]) -> dict[str, int]:
    """Count each held-token disposition, keeping every state visible at zero."""
    return {
        state: samples.count(state)
        for state in (_HELD_OK, _HELD_REJECTED, _HELD_UNKNOWN)
    }


def _refusal_lower_bound(
    censored_trials: int,
    blackouts: list[float],
    pre_existing_bounds: list[float],
) -> dict[str, Any] | None:
    """The censored-trial bound, so a timed-out run still carries its evidence."""
    if censored_trials <= 0:
        return None
    return {
        "censored_trials": censored_trials,
        "completed_trials": len(blackouts),
        "pre_existing_origin_trials": len(pre_existing_bounds),
        "reading": "the reissue refusal lasted AT LEAST the elapsed time named in "
        "each CENSORED error; this run puts no upper bound on the true window",
        "provenance": "CENSORED_LOWER_BOUND — the artifact is NOT_MEASURED and this "
        "value may be cited only together with that fact",
    }


def add_auth_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--endpoint-class", choices=("query", "submit", "cancel"), default="query"
    )
    parser.add_argument("--start-rps", type=float, default=1.0)
    parser.add_argument("--step-rps", type=float, default=1.0)
    parser.add_argument(
        "--max-rps",
        type=float,
        default=25.0,
        help="Hard ceiling; the ramp never exceeds it.",
    )
    parser.add_argument("--hold-seconds", type=float, default=3.0)
    parser.add_argument("--step-gap-seconds", type=float, default=2.0)
    parser.add_argument("--recovery-poll-s", type=float, default=1.0)
    parser.add_argument("--recovery-timeout-s", type=float, default=120.0)
    parser.add_argument("--max-sessions", type=int, default=5)
    parser.add_argument("--max-subscriptions", type=int, default=45)
    parser.add_argument("--reissue-gap-s", type=float, default=5.0)
    parser.add_argument(
        "--reissue-poll-s",
        type=float,
        default=15.0,
        help="First gap between N-15 reissue attempts; the base of the backoff, "
        "not the whole schedule. Was 5.0 — that spent 36 token calls per 180 s "
        "on a shared app key and learned nothing.",
    )
    parser.add_argument(
        "--blackout-backoff-factor",
        type=float,
        default=2.0,
        help="Multiplier applied to the N-15 reissue gap after each refusal. "
        "1.0 reproduces the old fixed-interval poll.",
    )
    parser.add_argument("--blackout-backoff-max-s", type=float, default=120.0)
    parser.add_argument(
        "--blackout-max-attempts",
        type=int,
        default=12,
        help="Token-endpoint calls N-15 may make per trial. This is the quota "
        "budget the rest of the campaign has to live with — P-13 shares it.",
    )
    parser.add_argument(
        "--blackout-observe-only",
        action="store_true",
        help="N-15: never call invalidate(); only observe when reissue becomes "
        "available again. Use when a blackout is already in progress, or when the "
        "probe's own cache must not be disturbed.",
    )
    parser.add_argument(
        "--blackout-timeout-s",
        type=float,
        default=1200.0,
        help="Wall-clock ceiling for one N-15 trial. Was 180 s, which is shorter "
        "than the ≥8.8 min refusal observed on 2026-07-29 and therefore censored "
        "every run by construction. 1200 s is chosen to exceed the default backoff "
        "schedule's own span (1065 s to the 12th attempt) so the ceiling does not "
        "silently truncate the budget it is paired with.",
    )
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--inter-trial-s", type=float, default=1.0)


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
