"""Order-capable probes — 모의투자 ONLY, dry-run unless ``--confirm``.

Probes here: P-2, P-5, P-5b, P-8, P-11, P-EXT, P-FQP, P-NMPR.

Every request in this module goes through :class:`MockTradingClient`, which calls
``assert_mock_host()`` and ``assert_mock_trading_tr()`` before opening a socket.
A real-host URL or a non-``V`` trading TR raises :class:`SafetyViolation` — there
is no flag that turns that off.

Order shape and quantity discipline
-----------------------------------
* Quantity defaults to 1 (the minimum) and is never derived from account equity.
* Limit prices are placed ``--price-offset-pct`` AWAY from the touch so the order
  rests unfilled and can be cancelled. P-11 is the single exception: it needs a
  fill and demands an extra ``--allow-fill`` flag.
* Every probe cancels what it created in a ``finally`` block and shouts (with the
  ODNO) if a cancel fails, so an operator can clean up by hand.

Request bodies mirror ``shared/execution/executor.py`` (``:386-393`` stock order,
``:458-471`` futures order, ``:685-699`` cancel/replace, ``:623-636`` inquire) so
that what is measured is what the runtime actually sends. TR ids come from
``shared/execution/tr_ids.py::get_tr_ids`` — the audited SoT — not from literals.

The one deliberate departure is P-NMPR's B-arm, which reconstructs the *pre*-fix
futures body (both [필수] quote fields blank, executor.py before ``76d43ae9``).
It exists precisely to test a shape the runtime no longer sends; see
:meth:`MockTradingClient.futures_order_body`.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeError,
    ProbeRun,
    assert_mock_host,
    assert_mock_trading_tr,
    assert_no_live_futures_config,
    build_auth_config,
    dry_run_banner,
    http_json,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    summarize_latencies,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_FUT_ORDER_PATH = "/uapi/domestic-futureoption/v1/trading/order"
_FUT_CANCEL_PATH = "/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
_FUT_INQUIRE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-ccnl"
_STOCK_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
_FUT_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_STOCK_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"

#: The two [필수] futures quote fields P-NMPR puts under test, in the order the
#: arm tuples below use.
_NMPR_FIELDS = ("NMPR_TYPE_CD", "KRX_NMPR_CNDT_CD")

#: P-NMPR arm -> the ``_NMPR_FIELDS`` pair that arm sends. Single source for both
#: the live body builder and the dry-run report, so the two cannot drift.
#: ``explicit`` is what the runtime sends today for ``ORD_DVSN_CD="01"``
#: (executor.py:104-115); ``legacy_blank`` is the pre-``76d43ae9`` shape.
_NMPR_ARMS: dict[str, tuple[str, str]] = {
    "explicit": ("01", "0"),  # 지정가 + 호가조건 없음
    "legacy_blank": ("", ""),
}


@dataclass
class Placed:
    odno: str
    sent_at_monotonic: float
    body: dict[str, Any]


class MockTradingClient:
    """Minimal, safety-gated KIS 모의투자 trading client for probes.

    Not a replacement for ``OrderExecutor``: it deliberately omits the retry,
    rate-limit and fill-monitor wrappers because those are part of the behaviour
    under measurement (draft §5 Q-IDEMP-1/2, Q-RATE-1).
    """

    def __init__(
        self, creds: Any, auth_manager: Any, run: ProbeRun, timeout: float = 15.0
    ):
        import requests

        self.creds = creds
        self.auth = auth_manager
        self.run = run
        self.session = requests.Session()
        self.timeout = timeout
        self.tr_ids = self._load_tr_ids()

    @staticmethod
    def _load_tr_ids() -> dict[str, str]:
        from shared.execution.tr_ids import get_tr_ids

        return get_tr_ids()

    def close(self) -> None:
        self.session.close()

    # -- headers ---------------------------------------------------------
    def _headers(self, tr_id: str) -> dict[str, str]:
        headers = dict(self.auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        return headers

    # -- guarded transports ---------------------------------------------
    def trading_call(
        self,
        method: str,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        """Any call that touches ``/trading/`` — double-gated (host + TR)."""
        url = f"{MOCK_BASE_URL}{path}"
        assert_mock_host(url)
        assert_mock_trading_tr(tr_id)
        return http_json(
            self.session,
            method,
            url,
            headers=self._headers(tr_id),
            params=params,
            json_body=body,
            timeout=self.timeout,
        )

    def quote_call(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Read-only quotations call (host-gated; TR prefix rule does not apply)."""
        url = f"{MOCK_BASE_URL}{path}"
        assert_mock_host(url)
        _status, parsed, _ms, _text = http_json(
            self.session,
            "GET",
            url,
            headers=self._headers(tr_id),
            params=params,
            timeout=self.timeout,
        )
        return parsed

    # -- domain helpers --------------------------------------------------
    def futures_last_price(self, symbol: str) -> float:
        data = self.quote_call(
            _FUT_PRICE_PATH,
            "FHMIF10000000",
            {"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol},
        )
        out = data.get("output1") or {}
        for key in ("futs_prpr", "futs_prdy_clpr", "stck_prpr"):
            value = out.get(key)
            if value not in (None, "", "0"):
                return float(value)
        raise ProbeError(
            f"could not read a futures price for {symbol}: rt_cd={data.get('rt_cd')}"
        )

    def stock_last_price(self, symbol: str) -> float:
        data = self.quote_call(
            _STOCK_PRICE_PATH,
            "FHKST01010100",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        )
        out = data.get("output") or {}
        value = out.get("stck_prpr")
        if value in (None, "", "0"):
            raise ProbeError(
                f"could not read a stock price for {symbol}: rt_cd={data.get('rt_cd')}"
            )
        return float(value)

    def futures_order_body(
        self,
        symbol: str,
        qty: int,
        price: float,
        side: str,
        *,
        required_fields: str = "explicit",
    ) -> dict[str, str]:
        """Mirror of ``executor.py:458-471`` (futures order body).

        The A-arm pair ``("01", "0")`` is not chosen here — it is what
        ``executor.py:104-115`` ``_FUTURES_NMPR_CODES`` maps ``ORD_DVSN_CD="01"``
        to, and both values come from the official wrapper's own enumeration:
        ``examples_llm/domestic_futureoption/order/order.py`` (TR
        ``v1_국내선물-001``, mock ``VTTO1101U``), ``Args`` — ``nmpr_type_cd
        (str): [필수] 호가유형코드 (ex. 01:지정가, ...)`` and ``krx_nmpr_cndt_cd
        (str): [필수] 한국거래소호가조건코드 (ex. 0:없음, 3:IOC, 4:FOK)``. That
        same file raises ``ValueError`` when either is ``""`` — which is what
        makes the B-arm worth sending.

        Args:
            required_fields: Which shape to build for the two [필수] quote
                fields.

                * ``"explicit"`` (default) — the current production shape:
                  ``NMPR_TYPE_CD``/``KRX_NMPR_CNDT_CD`` derived from
                  ``ORD_DVSN_CD`` (``executor.py:923`` ``_futures_quote_type_codes``).
                * ``"legacy_blank"`` — the pre-fix shape that sent both [필수]
                  fields as ``""``. Kept **only** as the B-arm of P-NMPR: it is
                  the one thing that can answer whether the broker's implicit
                  default for a blank actually equals ``01``/``0``. Never make
                  this the default.

        Raises:
            ProbeError: unknown ``required_fields`` mode.
        """
        codes = _NMPR_ARMS.get(required_fields)
        if codes is None:
            raise ProbeError(
                f"unknown required_fields mode {required_fields!r} "
                f"(expected one of {sorted(_NMPR_ARMS)})"
            )
        nmpr_type_cd, krx_nmpr_cndt_cd = codes
        return {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "SLL_BUY_DVSN_CD": "02" if side == "BUY" else "01",
            "SHTN_PDNO": symbol,
            "ORD_QTY": str(qty),
            "UNIT_PRICE": str(price),
            "NMPR_TYPE_CD": nmpr_type_cd,
            "KRX_NMPR_CNDT_CD": krx_nmpr_cndt_cd,
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            # 지정가 — executor.py:887 ``_map_futures_order_type`` maps internal
            # OrderType.LIMIT ("00") to futures ORD_DVSN_CD "01".
            "ORD_DVSN_CD": "01",
        }

    def stock_order_body(self, symbol: str, qty: int, price: float) -> dict[str, str]:
        """Mirror of ``executor.py:386-393`` (note ORD_UNPR int-truncation, Q-WIRE-1)."""
        return {
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "PDNO": symbol,
            "ORD_DVSN": "00",  # 지정가
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(int(price)),
        }

    def submit_futures(
        self, body: dict[str, str]
    ) -> tuple[Placed | None, dict[str, Any], float]:
        tr_id = self.tr_ids["futures_order_day_mock"]
        sent = time.monotonic()
        status, parsed, ms, _text = self.trading_call(
            "POST", _FUT_ORDER_PATH, tr_id, body=body
        )
        odno = str((parsed.get("output") or {}).get("ODNO") or "").strip()
        placed = (
            Placed(odno, sent, body)
            if status == 200 and parsed.get("rt_cd") == "0" and odno
            else None
        )
        return placed, parsed, ms

    def cancel_futures(self, odno: str, qty: int) -> dict[str, Any]:
        """Cancel — ``RVSE_CNCL_DVSN_CD='02'`` (executor.py:689)."""
        return self._rvsecncl(odno, qty, dvsn="02", price=0.0)

    def replace_futures(self, odno: str, qty: int, price: float) -> dict[str, Any]:
        """Amend — ``RVSE_CNCL_DVSN_CD='01'``. Never exercised by the runtime
        (draft §3.1 row 8: the literal appears once, value ``"02"`` only)."""
        return self._rvsecncl(odno, qty, dvsn="01", price=price)

    def _rvsecncl(
        self, odno: str, qty: int, *, dvsn: str, price: float
    ) -> dict[str, Any]:
        tr_id = self.tr_ids["futures_cancel_day_mock"]
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "RVSE_CNCL_DVSN_CD": dvsn,
            "ORGN_ODNO": odno,
            "ORD_QTY": str(qty),
            "UNIT_PRICE": str(price) if dvsn == "01" else "0",
            "NMPR_TYPE_CD": "01",
            "KRX_NMPR_CNDT_CD": "0",
            "RMN_QTY_YN": "Y",
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": "01",
        }
        _status, parsed, _ms, _text = self.trading_call(
            "POST", _FUT_CANCEL_PATH, tr_id, body=body
        )
        return parsed

    def inquire_futures(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk200: str = "",
        nk200: str = "",
    ) -> dict[str, Any]:
        """Mirror of ``executor.py:623-636`` but with usable continuation keys."""
        tr_id = self.tr_ids["futures_inquire_day_mock"]
        day = (datetime.now(KST) - timedelta(days=day_offset)).date().strftime("%Y%m%d")
        params = {
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "STRT_ORD_DT": day,
            "END_ORD_DT": day,
            "SLL_BUY_DVSN_CD": "00",
            "CCLD_NCCS_DVSN": "00",
            "SORT_SQN": "DS",
            "STRT_ODNO": odno,
            "PDNO": symbol,
            "MKET_ID_CD": "",
            "CTX_AREA_FK200": fk200,
            "CTX_AREA_NK200": nk200,
        }
        _status, parsed, _ms, _text = self.trading_call(
            "GET", _FUT_INQUIRE_PATH, tr_id, params=params
        )
        return parsed

    def stock_balance(self) -> dict[str, Any]:
        """Mirror of ``shared/kis/client.py:920-933`` params, mock TR."""
        tr_id = "VTTC8434R"
        assert_mock_trading_tr(tr_id)
        params = {
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
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
        _status, parsed, _ms, _text = self.trading_call(
            "GET", _STOCK_BALANCE_PATH, tr_id, params=params
        )
        return parsed


# ---------------------------------------------------------------------------
# Setup / teardown helpers
# ---------------------------------------------------------------------------


def _setup(
    spec: ProbeSpec, args: argparse.Namespace
) -> tuple[ProbeRun, MockTradingClient | None]:
    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    assert_no_live_futures_config()
    warn_shared_token_cache()
    creds = resolve_credentials(args.asset, is_real=False)
    require_account(creds)
    run.credentials = creds.describe()
    if not args.confirm:
        dry_run_banner(spec)
        return run, None
    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    return run, MockTradingClient(creds, auth, run)


def _resting_price(
    client: MockTradingClient, args: argparse.Namespace
) -> tuple[float, str]:
    """A limit price far enough from the touch that the order will not fill."""
    if args.asset == "futures":
        last = client.futures_last_price(args.symbol)
        side = "BUY"
        price = round(last * (1.0 - args.price_offset_pct / 100.0), 2)
    else:
        last = client.stock_last_price(args.symbol)
        side = "BUY"
        price = float(int(last * (1.0 - args.price_offset_pct / 100.0)))
    if price <= 0:
        raise ProbeError("computed resting price <= 0; check --price-offset-pct")
    return price, side


def _cleanup(
    client: MockTradingClient | None, run: ProbeRun, odnos: list[str], qty: int
) -> None:
    if client is None:
        return
    for odno in odnos:
        if not odno:
            continue
        try:
            result = client.cancel_futures(odno, qty)
            ok = result.get("rt_cd") == "0"
            run.observe(cleanup_cancel=odno, ok=ok, msg=result.get("msg1"))
            if not ok:
                run.error(
                    f"CLEANUP FAILED — order {odno} may still be resting. "
                    f"Cancel it manually: {result.get('msg1')}"
                )
        except Exception as exc:  # noqa: BLE001 - cleanup must never mask results
            run.error(f"CLEANUP EXCEPTION for {odno}: {type(exc).__name__}: {exc}")


def _require_symbol(args: argparse.Namespace) -> None:
    if not args.symbol:
        raise ProbeError("--symbol is required (e.g. 101S6000 futures, 005930 stock)")


# ---------------------------------------------------------------------------
# P-2 — submission idempotency
# ---------------------------------------------------------------------------


def probe_p2(args: argparse.Namespace) -> ProbeRun:
    """P-2 SUBMISSION_IDEMPOTENCY — does an identical body produce two ODNOs?

    Measures: ``capabilities.submission_idempotency.status`` and
    ``deduplication_window_ms``. Feeds no Verification-Profile bound directly;
    it decides whether the runtime's blind-retry paths (draft §5 Q-IDEMP-1/2)
    are a duplicate-order hazard or a broker-absorbed no-op.

    Method: send byte-identical order bodies ``--gap-ms`` apart, then count
    distinct ODNOs via inquire-ccnl. Two ODNOs => no dedup (UNSUPPORTED, and the
    window is undefined — not 0). One ODNO => rerun with a larger gap to bracket
    the window; report the bracket, never a point estimate.
    """
    spec = get("P-2")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(would_send="two identical futures order bodies", gap_ms=args.gap_ms)
        return run
    odnos: list[str] = []
    try:
        price, side = _resting_price(client, args)
        body = client.futures_order_body(args.symbol, args.quantity, price, side)
        run.observe(order_body=body, resting_price=price, side=side)

        first, raw1, ms1 = client.submit_futures(body)
        time.sleep(args.gap_ms / 1000.0)
        second, raw2, ms2 = client.submit_futures(dict(body))

        for placed in (first, second):
            if placed:
                odnos.append(placed.odno)
        run.observe(
            submit_1={"rt_cd": raw1.get("rt_cd"), "msg1": raw1.get("msg1"), "ms": ms1}
        )
        run.observe(
            submit_2={"rt_cd": raw2.get("rt_cd"), "msg1": raw2.get("msg1"), "ms": ms2}
        )

        distinct = sorted({o for o in odnos if o})
        time.sleep(args.settle_seconds)
        listing = client.inquire_futures(args.symbol)
        rows = (
            listing.get("output1") if isinstance(listing.get("output1"), list) else []
        )
        observed = sorted(
            {str(r.get("odno", "")).strip() for r in rows} & set(distinct)
        )

        run.measure("gap_ms", args.gap_ms)
        run.measure("distinct_odno_count", len(distinct))
        run.measure("odno_confirmed_in_query", observed)
        run.measure(
            "verdict",
            (
                "NO_DEDUP (2 accepted ODNOs)"
                if len(distinct) == 2
                else (
                    "DEDUP_OR_REJECT (1 accepted ODNO) — rerun with a larger --gap-ms "
                    "to find the upper edge of the window"
                    if len(distinct) == 1
                    else "INCONCLUSIVE (0 accepted ODNOs — check rt_cd/msg1)"
                )
            ),
        )
        run.measure(
            "window_semantics",
            "A single ODNO does NOT establish deduplication_window_ms = gap. It "
            "establishes only that the window is >= gap. Bracket it: the largest "
            "deduping gap is a lower bound, the smallest non-deduping gap an upper bound.",
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-5 — accept -> visible-in-query convergence
# ---------------------------------------------------------------------------


def probe_p5(args: argparse.Namespace) -> ProbeRun:
    """P-5 OPEN_ORDER_QUERY — order-accept to query-visible convergence latency.

    Measures: ``capabilities.open_order_query.eventual_consistency_bound_ms``.
    Feeds: ``B_broker_query_consistency`` (VP-002:752, semantics
    ``broker_specific``, failure_response ``CONSERVATIVE_UNKNOWN``, rationale
    "absence within it is not proof of non-existence").

    Method: for each trial, timestamp t0 at the ODNO-bearing accept response,
    then poll inquire-ccnl every ``--poll-ms`` until the ODNO appears; t1-t0 is
    the sample. Because the bound is a hard maximum, the candidate is
    ``max x (1+margin)`` — never a percentile. Polling granularity is an additive
    error term: it is recorded so the approver can widen the margin accordingly.
    """
    spec = get("P-5")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send=f"{args.samples} resting orders, polling inquire-ccnl every {args.poll_ms}ms"
        )
        return run
    odnos: list[str] = []
    samples: list[float] = []
    try:
        price, side = _resting_price(client, args)
        for trial in range(args.samples):
            body = client.futures_order_body(args.symbol, args.quantity, price, side)
            placed, raw, _ms = client.submit_futures(body)
            if placed is None:
                run.error(
                    f"trial {trial}: submit rejected rt_cd={raw.get('rt_cd')} msg={raw.get('msg1')}"
                )
                break
            odnos.append(placed.odno)
            deadline = time.monotonic() + args.visibility_timeout_s
            seen_at: float | None = None
            polls = 0
            while time.monotonic() < deadline:
                polls += 1
                listing = client.inquire_futures(args.symbol, odno=placed.odno)
                rows = (
                    listing.get("output1")
                    if isinstance(listing.get("output1"), list)
                    else []
                )
                if any(str(r.get("odno", "")).strip() == placed.odno for r in rows):
                    seen_at = time.monotonic()
                    break
                time.sleep(args.poll_ms / 1000.0)
            if seen_at is None:
                run.error(
                    f"trial {trial}: ODNO {placed.odno} never appeared within "
                    f"{args.visibility_timeout_s}s — this is a CENSORED sample and "
                    "must not be dropped when computing the maximum"
                )
                run.observe(trial=trial, censored=True, polls=polls)
                continue
            latency_ms = (seen_at - placed.sent_at_monotonic) * 1000.0
            samples.append(latency_ms)
            run.observe(
                trial=trial,
                odno=placed.odno,
                latency_ms=round(latency_ms, 2),
                polls=polls,
            )
            # Cancel immediately so the next trial starts from a clean book.
            client.cancel_futures(placed.odno, args.quantity)
            odnos.remove(placed.odno)
            time.sleep(args.inter_trial_s)
        run.measure(
            "B_broker_query_consistency_candidate",
            summarize_latencies(
                samples, margin_pct=args.margin_pct, label="accept_to_visible_ms"
            ),
        )
        run.measure("poll_granularity_ms", args.poll_ms)
        run.measure(
            "granularity_note",
            "Each sample carries up to one poll interval of additive error. The "
            "approved bound must exceed max_observed + poll_ms, not just max_observed.",
        )
        run.measure(
            "censored_trials", len([o for o in run.observations if o.get("censored")])
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-5b — pagination / completeness
# ---------------------------------------------------------------------------


def probe_p5b(args: argparse.Namespace) -> ProbeRun:
    """P-5b OPEN_ORDER_QUERY — continuation-key (CTX_AREA_FK200/NK200) behaviour.

    Measures: ``capabilities.open_order_query.completeness`` / ``pagination``.
    Resolves quirk Q-OOQ-1 (draft §5:165) — the runtime sends empty continuation
    keys and ignores the response keys, so it always reads page 1 only. That is
    the concrete instance of ``ONE_OPEN_ORDER_QUERY_OMISSION``.

    Read-only: it issues no order. It needs enough same-day history to exceed one
    page, so run it after P-5.
    """
    spec = get("P-5b")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="paged inquire-ccnl walk using response continuation keys"
        )
        return run
    try:
        pages: list[dict[str, Any]] = []
        fk200 = nk200 = ""
        for page in range(args.max_pages):
            listing = client.inquire_futures(args.symbol, fk200=fk200, nk200=nk200)
            rows = (
                listing.get("output1")
                if isinstance(listing.get("output1"), list)
                else []
            )
            next_fk = str(listing.get("ctx_area_fk200") or "").strip()
            next_nk = str(listing.get("ctx_area_nk200") or "").strip()
            pages.append(
                {
                    "page": page,
                    "rows": len(rows),
                    "rt_cd": listing.get("rt_cd"),
                    "next_fk200_present": bool(next_fk),
                    "next_nk200_present": bool(next_nk),
                    "first_odno": str(rows[0].get("odno", "")).strip() if rows else "",
                    "last_odno": str(rows[-1].get("odno", "")).strip() if rows else "",
                }
            )
            run.observe(**pages[-1])
            if not rows or (not next_fk and not next_nk):
                break
            if (next_fk, next_nk) == (fk200, nk200):
                run.error(
                    "continuation keys did not advance — possible infinite page loop; stopping"
                )
                break
            fk200, nk200 = next_fk, next_nk
            time.sleep(args.inter_trial_s)
        run.measure("pages_walked", len(pages))
        run.measure("page_size_observed", max((p["rows"] for p in pages), default=0))
        run.measure(
            "continuation_supported",
            any(p["next_fk200_present"] or p["next_nk200_present"] for p in pages),
        )
        run.measure(
            "completeness_note",
            "If total rows across pages exceeds page 1, the runtime's single-page "
            "read (executor.py:562-563, 575-579) is structurally incomplete and "
            "open_order_query.completeness must NOT be declared complete.",
        )
        if len(pages) == 1 and pages[0]["rows"] == 0:
            run.skip(
                "pagination determination",
                "no rows in the query window — inconclusive, not 'single page'. "
                "Re-run after P-5 has generated history.",
            )
    finally:
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-8 — replace / amend
# ---------------------------------------------------------------------------


def probe_p8(args: argparse.Namespace) -> ProbeRun:
    """P-8 REPLACE_OR_AMEND — ``RVSE_CNCL_DVSN_CD='01'`` semantics.

    Measures: ``capabilities.replace_semantics.mode`` (one of the ReplaceSemantics
    values) and the old/new coexistence interval.
    Feeds: ``B_protective_request_complete`` (VP-002:743) — a protective replace
    that leaves both legs live for an interval is exactly the protection-overlap
    hazard.

    Method: place a resting order, amend its price, then poll inquire-ccnl and
    record (a) whether a NEW ODNO was issued, (b) whether the original ODNO
    remains visible/live, and (c) for how long both are simultaneously live.
    A non-zero coexistence interval means replacement is NOT atomic and the
    profile must not declare an atomic replace mode.
    """
    spec = get("P-8")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="submit -> RVSE_CNCL_DVSN_CD=01 amend -> poll both ODNOs"
        )
        return run
    odnos: list[str] = []
    try:
        price, side = _resting_price(client, args)
        body = client.futures_order_body(args.symbol, args.quantity, price, side)
        placed, raw, _ms = client.submit_futures(body)
        if placed is None:
            run.error(f"submit rejected rt_cd={raw.get('rt_cd')} msg={raw.get('msg1')}")
            return run
        odnos.append(placed.odno)
        new_price = round(price * 0.99, 2)
        amended_at = time.monotonic()
        amend = client.replace_futures(placed.odno, args.quantity, new_price)
        new_odno = str((amend.get("output") or {}).get("ODNO") or "").strip()
        run.observe(
            original_odno=placed.odno,
            amend_rt_cd=amend.get("rt_cd"),
            amend_msg=amend.get("msg1"),
            new_odno=new_odno,
            new_price=new_price,
        )
        if new_odno:
            odnos.append(new_odno)

        coexist_last: float | None = None
        deadline = time.monotonic() + args.visibility_timeout_s
        while time.monotonic() < deadline:
            listing = client.inquire_futures(args.symbol)
            rows = (
                listing.get("output1")
                if isinstance(listing.get("output1"), list)
                else []
            )
            live = {
                str(r.get("odno", "")).strip()
                for r in rows
                if int(float(r.get("qty") or 0)) > 0
            }
            both = placed.odno in live and bool(new_odno) and new_odno in live
            if both:
                coexist_last = time.monotonic()
            elif coexist_last is not None:
                break
            time.sleep(args.poll_ms / 1000.0)

        run.measure("replace_issues_new_odno", bool(new_odno))
        run.measure("replace_rejected", amend.get("rt_cd") != "0")
        run.measure(
            "coexistence_ms",
            round((coexist_last - amended_at) * 1000.0, 2) if coexist_last else 0.0,
        )
        run.measure(
            "mode_determination",
            "Map to ReplaceSemantics only after N>=5 trials agree. A single trial "
            "showing zero coexistence does NOT prove atomicity — polling can miss "
            "an interval shorter than --poll-ms.",
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-11 — balance reflection
# ---------------------------------------------------------------------------


def probe_p11(args: argparse.Namespace) -> ProbeRun:
    """P-11 POSITIONS_BALANCES_MARGIN — fill to balance-reflection lag.

    Measures: ``capabilities.position_balance_margin.consistency_model``.
    Feeds: ``B_broker_query_consistency`` (VP-002:752) and informs feasibility of
    ``B_startup_reconciliation`` (VP-002:239, already APPROVED at 60000).

    STOCK ONLY on 모의: futures balance inquiry is unsupported on the mock server
    (``shared/kis/client.py:1030-1032``), so the futures leg is skipped with that
    citation rather than silently producing a wrong number.

    This probe intentionally FILLS. It therefore requires ``--allow-fill`` in
    addition to ``--confirm``.
    """
    spec = get("P-11")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if args.asset == "futures":
        run.skip(
            "futures balance leg",
            "모의투자 does not serve futures balance inquiry "
            "(shared/kis/client.py:1030-1032: 'NOT supported on mock server; "
            "is_real=True required'). Run the stock leg on mock; the futures leg "
            "is REAL-only and out of scope for P0-2 mock measurement.",
        )
        if client:
            client.close()
        return run
    if client is None:
        run.observe(would_send="marketable stock order, then poll inquire-balance")
        return run
    if not args.allow_fill:
        run.skip(
            "fill leg",
            "--allow-fill not given. P-11 needs a real fill to time the balance "
            "update; refusing to place a marketable order without explicit intent.",
        )
        client.close()
        return run
    try:
        last = client.stock_last_price(args.symbol)
        # Marketable limit: cross the touch by the offset so it fills promptly.
        price = float(int(last * (1.0 + args.price_offset_pct / 100.0)))
        body = client.stock_order_body(args.symbol, args.quantity, price)
        run.observe(order_body=body, last_price=last, marketable_price=price)
        sent = time.monotonic()
        tr_id = client.tr_ids["stock_krx_buy_mock"]
        status, parsed, _ms, _text = client.trading_call(
            "POST", _STOCK_ORDER_PATH, tr_id, body=body
        )
        odno = str((parsed.get("output") or {}).get("ODNO") or "").strip()
        run.observe(
            submit_status=status,
            rt_cd=parsed.get("rt_cd"),
            msg1=parsed.get("msg1"),
            odno=odno,
        )
        if parsed.get("rt_cd") != "0":
            run.error("stock order not accepted; cannot measure balance lag")
            return run

        baseline = client.stock_balance()
        base_rows = (
            baseline.get("output1") if isinstance(baseline.get("output1"), list) else []
        )
        base_qty = sum(
            int(float(r.get("hldg_qty") or 0))
            for r in base_rows
            if str(r.get("pdno", "")).strip() == args.symbol
        )
        run.observe(baseline_holding_qty=base_qty)

        reflected_at: float | None = None
        deadline = time.monotonic() + args.visibility_timeout_s
        while time.monotonic() < deadline:
            snapshot = client.stock_balance()
            rows = (
                snapshot.get("output1")
                if isinstance(snapshot.get("output1"), list)
                else []
            )
            qty = sum(
                int(float(r.get("hldg_qty") or 0))
                for r in rows
                if str(r.get("pdno", "")).strip() == args.symbol
            )
            if qty > base_qty:
                reflected_at = time.monotonic()
                break
            time.sleep(args.poll_ms / 1000.0)

        if reflected_at is None:
            run.error(
                "balance never reflected the order within the timeout — CENSORED. "
                "Do not record a bound from a censored trial."
            )
        else:
            lag_ms = (reflected_at - sent) * 1000.0
            run.measure(
                "submit_to_balance_reflection",
                summarize_latencies(
                    [lag_ms], margin_pct=args.margin_pct, label="submit_to_balance_ms"
                ),
            )
            run.measure(
                "n_note",
                "n=1 per invocation. Re-run --samples times and take the maximum "
                "across artifacts before proposing a bound.",
            )
        run.measure(
            "position_left_open",
            f"symbol={args.symbol} qty={args.quantity} — the probe does NOT flatten "
            "the position. Close it manually on 모의투자.",
        )
    finally:
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-EXT — external activity detection
# ---------------------------------------------------------------------------


def probe_pext(args: argparse.Namespace) -> ProbeRun:
    """P-EXT external_activity — detection latency for an order we did not send.

    Measures: ``external_activity.detection_bound_ms`` /
    ``containment_bound_ms``.
    Feeds: ``B_external_activity_detect`` (VP-002:221, ``value_ms: null``,
    ``hard_maximum``, "for a poll-only broker this is bounded by the poll
    interval") and constrains ``B_external_activity_contain`` (VP-002:230,
    already APPROVED at 1000).

    Operator in the loop: place an order on HTS/MTS for the SAME 모의 account and
    press Enter at the moment of submission. The probe polls inquire-ccnl and
    timestamps the first observation of an unknown ODNO.

    The measured number is dominated by the poll interval by construction — the
    system has zero account-event push subscriptions (draft §3.1 row 10: grep for
    ``H0STCNI|H0IFCNI|체결통보`` over shared/ services/ cli/ returns 0 hits). Record
    the poll interval next to the value; the bound cannot be tightened below it
    without a push subscription.
    """
    spec = get("P-EXT")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="poll-only observation loop; operator places the manual order"
        )
        return run
    try:
        listing = client.inquire_futures(args.symbol)
        rows = (
            listing.get("output1") if isinstance(listing.get("output1"), list) else []
        )
        known = {str(r.get("odno", "")).strip() for r in rows}
        run.observe(known_odno_count=len(known))
        print(
            "\n  >>> Place ONE order on HTS/MTS for this 모의 account now.\n"
            "  >>> Press Enter AT THE MOMENT you submit it."
        )
        input("  [Enter at submit] ")
        submitted_at = time.monotonic()
        detected_at: float | None = None
        polls = 0
        deadline = submitted_at + args.visibility_timeout_s
        while time.monotonic() < deadline:
            polls += 1
            snapshot = client.inquire_futures(args.symbol)
            rows = (
                snapshot.get("output1")
                if isinstance(snapshot.get("output1"), list)
                else []
            )
            new = {str(r.get("odno", "")).strip() for r in rows} - known
            if new:
                detected_at = time.monotonic()
                run.observe(new_odno_count=len(new))
                break
            time.sleep(args.poll_ms / 1000.0)
        if detected_at is None:
            run.error("no external order observed within the timeout — CENSORED trial")
        else:
            run.measure(
                "B_external_activity_detect_candidate",
                summarize_latencies(
                    [(detected_at - submitted_at) * 1000.0],
                    margin_pct=args.margin_pct,
                    label="manual_submit_to_detect_ms",
                ),
            )
        run.measure("poll_interval_ms", args.poll_ms)
        run.measure("polls_used", polls)
        run.measure(
            "human_timestamp_error",
            "The t0 comes from a human keypress; assume +/- several hundred ms and "
            "fold it into the margin. Repeat >= 5 trials.",
        )
        run.measure(
            "push_absence_note",
            "Detection is poll-bounded: no account-event push subscription exists "
            "(draft §3.1 row 10). The bound cannot go below the poll interval.",
        )
    finally:
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-FQP — final quantity proof / late fill
# ---------------------------------------------------------------------------


def probe_pfqp(args: argparse.Namespace) -> ProbeRun:
    """P-FQP final_quantity_proof — post-cancel late-event observation window.

    Measures: ``final_quantity_proof.recipes[]`` inputs and
    ``late_event_window_ms``.
    Feeds: ``B_final_quantity_proof`` (VP-002:716, "time within which final filled
    qty + zero remaining can be established ... drives RELEASE_PENDING_PROOF") and
    ``B_late_fill_observation`` (VP-002:725, "maximum credible interval in which a
    late fill may still arrive after a claimed terminal state").

    Method: place a resting order, cancel it, then keep polling for
    ``--late-window-s`` and record every quantity change observed AFTER the cancel
    ack. Two numbers come out: the time to reach a stable (filled, remaining=0)
    reading, and the latest post-terminal change seen.

    Honest-negative rule: observing zero late changes does NOT license
    ``late_event_window_ms: 0``. Absence within a window is not proof of
    non-existence (VP-002:756). Zero observations => "not established"; the field
    stays null and the capability stays UNKNOWN.
    """
    spec = get("P-FQP")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(would_send=f"submit -> cancel -> poll for {args.late_window_s}s")
        return run
    odnos: list[str] = []
    try:
        price, side = _resting_price(client, args)
        body = client.futures_order_body(args.symbol, args.quantity, price, side)
        placed, raw, _ms = client.submit_futures(body)
        if placed is None:
            run.error(f"submit rejected rt_cd={raw.get('rt_cd')} msg={raw.get('msg1')}")
            return run
        odnos.append(placed.odno)

        cancel_result = client.cancel_futures(placed.odno, args.quantity)
        cancel_at = time.monotonic()
        cancel_odno = str((cancel_result.get("output") or {}).get("ODNO") or "").strip()
        run.observe(
            original_odno=placed.odno,
            cancel_rt_cd=cancel_result.get("rt_cd"),
            cancel_returns_new_odno=cancel_odno,
            quirk="Q-CXL-1: a cancel ack carries its OWN ODNO and proves nothing "
            "about the original order's final quantity (draft §5:186).",
        )
        if cancel_result.get("rt_cd") == "0":
            odnos.remove(placed.odno)

        stable_at: float | None = None
        last_reading: tuple[int, int] | None = None
        changes: list[dict[str, Any]] = []
        deadline = cancel_at + args.late_window_s
        while time.monotonic() < deadline:
            listing = client.inquire_futures(args.symbol, odno=placed.odno)
            rows = (
                listing.get("output1")
                if isinstance(listing.get("output1"), list)
                else []
            )
            row = next(
                (r for r in rows if str(r.get("odno", "")).strip() == placed.odno), None
            )
            if row is not None:
                filled = int(float(row.get("tot_ccld_qty") or 0))
                remaining = int(float(row.get("qty") or 0))
                reading = (filled, remaining)
                if last_reading is not None and reading != last_reading:
                    changes.append(
                        {
                            "at_ms_after_cancel": round(
                                (time.monotonic() - cancel_at) * 1000.0, 2
                            ),
                            "from": list(last_reading),
                            "to": list(reading),
                        }
                    )
                if reading != last_reading:
                    run.observe(reading_filled=filled, reading_remaining=remaining)
                last_reading = reading
                if remaining == 0 and stable_at is None:
                    stable_at = time.monotonic()
            time.sleep(args.poll_ms / 1000.0)

        run.measure(
            "B_final_quantity_proof_candidate",
            summarize_latencies(
                [(stable_at - placed.sent_at_monotonic) * 1000.0] if stable_at else [],
                margin_pct=args.margin_pct,
                label="submit_to_filled_plus_zero_remaining_ms",
            ),
        )
        run.measure("post_terminal_changes", changes)
        run.measure(
            "B_late_fill_observation_candidate",
            {
                "observed_changes": len(changes),
                "latest_change_ms_after_cancel": max(
                    (c["at_ms_after_cancel"] for c in changes), default=None
                ),
                "observation_window_s": args.late_window_s,
                "verdict": (
                    "NOT_ESTABLISHED — zero late changes observed. Per VP-002:756 "
                    "absence within a window is not proof of non-existence, so the "
                    "field stays null and the capability stays UNKNOWN."
                    if not changes
                    else "OBSERVED — take the maximum across trials, add margin, and "
                    "confirm the observation window exceeded that maximum."
                ),
                "window_adequacy": (
                    "The observation window must be strictly longer than the largest "
                    "change seen; otherwise the window itself is the binding limit."
                ),
            },
        )
        run.measure(
            "fqp_markers_required",
            [
                "no_later_change_asserted (ADR §15.4 marker — cannot be asserted from a "
                "single trial)",
                "late_event_window_defined (requires an approved B_late_fill_observation)",
            ],
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


def probe_nmpr_ab(args: argparse.Namespace) -> ProbeRun:
    """P-NMPR — does a blank [필수] quote field mean the same as ``01``/``0``?

    Origin: N-17 §2 소견 2. Until 2026-07-29 the runtime sent ``NMPR_TYPE_CD``
    and ``KRX_NMPR_CNDT_CD`` as ``""`` even though the KIS wrapper marks both
    [필수] and refuses a blank with ``ValueError``. The runtime now derives both
    from ``ORD_DVSN_CD``. That fix was made in the "preserve observed behaviour"
    direction, which leaves exactly one question unanswered: **is the broker's
    implicit default for a blank actually 01/0, or something else?**

    Method: place the same non-marketable resting limit twice — arm A with the
    explicit codes, arm B with the pre-fix blanks — and compare what the broker
    does with each. Both arms are cancelled in ``_cleanup``.

    Reading the result honestly:

    * Acceptance parity alone does **not** prove semantic equality. It proves
      the broker tolerates a blank. Equality would additionally require the
      query surface to echo the two fields back — if it does not, the answer
      stays UNKNOWN and this probe has narrowed nothing but the rejection case.
    * A rejected B-arm is the strong outcome: it proves the pre-fix body was
      contract-violating and the fix is load-bearing.
    """
    spec = get("P-NMPR")
    _require_symbol(args)
    if args.asset != "futures":
        raise ProbeError("P-NMPR is a futures-only probe (--asset futures)")
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="two futures order bodies differing ONLY in the two "
            "[필수] quote fields (explicit 01/0 vs pre-fix blanks)",
            arm_a_explicit=dict(zip(_NMPR_FIELDS, _NMPR_ARMS["explicit"], strict=True)),
            arm_b_legacy_blank=dict(
                zip(_NMPR_FIELDS, _NMPR_ARMS["legacy_blank"], strict=True)
            ),
            every_other_field="identical, built by futures_order_body() as a "
            "mirror of executor.py:458-471; the limit price is read from the "
            "touch at --confirm time and so is absent from a dry run",
        )
        return run
    odnos: list[str] = []
    try:
        price, side = _resting_price(client, args)
        body_a = client.futures_order_body(
            args.symbol, args.quantity, price, side, required_fields="explicit"
        )
        body_b = client.futures_order_body(
            args.symbol, args.quantity, price, side, required_fields="legacy_blank"
        )
        differing = sorted(k for k in body_a if body_a[k] != body_b[k])
        run.observe(
            arm_a_body=body_a,
            arm_b_body=body_b,
            differing_fields=differing,
            resting_price=price,
            side=side,
        )
        if differing != ["KRX_NMPR_CNDT_CD", "NMPR_TYPE_CD"]:
            raise ProbeError(
                "A/B arms differ in fields other than the two under test: "
                f"{differing} — the comparison would not be attributable"
            )

        placed_a, raw_a, ms_a = client.submit_futures(body_a)
        time.sleep(args.inter_trial_s)
        placed_b, raw_b, ms_b = client.submit_futures(body_b)
        for placed in (placed_a, placed_b):
            if placed:
                odnos.append(placed.odno)

        run.measure(
            "arm_a_explicit",
            {"rt_cd": raw_a.get("rt_cd"), "msg1": raw_a.get("msg1"), "ms": ms_a},
        )
        run.measure(
            "arm_b_blank",
            {"rt_cd": raw_b.get("rt_cd"), "msg1": raw_b.get("msg1"), "ms": ms_b},
        )

        time.sleep(args.settle_seconds)
        listing = client.inquire_futures(args.symbol)
        rows = (
            listing.get("output1") if isinstance(listing.get("output1"), list) else []
        )
        by_odno = {str(r.get("odno", "")).strip(): r for r in rows}
        row_a = by_odno.get(placed_a.odno) if placed_a else None
        row_b = by_odno.get(placed_b.odno) if placed_b else None
        run.measure("arm_a_row", row_a)
        run.measure("arm_b_row", row_b)

        echoes = sorted(
            k
            for k in (row_a or {})
            if k.lower() in {"nmpr_type_cd", "krx_nmpr_cndt_cd"}
        )
        run.measure("query_echoes_quote_fields", echoes)
        if row_a and row_b:
            run.measure(
                "row_field_differences",
                sorted(
                    k
                    for k in set(row_a) | set(row_b)
                    if k not in {"odno", "ord_tmd"} and row_a.get(k) != row_b.get(k)
                ),
            )

        a_ok, b_ok = placed_a is not None, placed_b is not None
        if a_ok and not b_ok:
            verdict = (
                "BLANK_REJECTED — the pre-fix body is contract-violating. The "
                "explicit-code fix is load-bearing, not cosmetic."
            )
        elif a_ok and b_ok and not echoes:
            verdict = (
                "BOTH_ACCEPTED, ECHO_ABSENT — the broker tolerates a blank, but "
                "the query surface does not return NMPR_TYPE_CD/KRX_NMPR_CNDT_CD, "
                "so 'blank == 01/0' remains UNKNOWN. Acceptance is not equality."
            )
        elif a_ok and b_ok:
            verdict = (
                "BOTH_ACCEPTED, ECHO_PRESENT — compare arm_a_row/arm_b_row on the "
                "echoed fields; equal echoes establish the implicit default, "
                "unequal echoes establish that the blank meant something else."
            )
        elif not a_ok:
            verdict = (
                "INCONCLUSIVE — the explicit arm itself was rejected; fix the "
                "precondition (price/session/symbol) before reading arm B."
            )
        else:
            verdict = "INCONCLUSIVE — neither arm was accepted."
        run.measure("verdict", verdict)
        run.measure(
            "scope",
            "모의투자 only. Per N-17 #13 the mock server has no night-session "
            "write path, so this result must not be extrapolated to REAL night.",
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


def add_order_args(parser: argparse.ArgumentParser) -> None:
    """Extra flags used by the order-capable probes."""
    parser.add_argument(
        "--gap-ms", type=float, default=200.0, help="P-2: gap between the twin sends."
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=2.0,
        help="P-2: wait before counting ODNOs.",
    )
    parser.add_argument(
        "--poll-ms",
        type=float,
        default=200.0,
        help="Polling interval for convergence probes.",
    )
    parser.add_argument(
        "--inter-trial-s",
        type=float,
        default=1.0,
        help="Pause between trials (broker courtesy).",
    )
    parser.add_argument(
        "--visibility-timeout-s",
        type=float,
        default=30.0,
        help="Give up on a trial after this.",
    )
    parser.add_argument(
        "--late-window-s",
        type=float,
        default=120.0,
        help="P-FQP: post-cancel observation window.",
    )
    parser.add_argument(
        "--max-pages", type=int, default=10, help="P-5b: pagination walk cap."
    )
    parser.add_argument(
        "--allow-fill",
        action="store_true",
        help="P-11 only: authorise a marketable order that is expected to FILL.",
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
