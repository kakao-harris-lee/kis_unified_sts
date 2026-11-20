"""Order-capable probes — 모의투자 ONLY, dry-run unless ``--confirm``."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tools.broker_probes.common import (
    MOCK_BASE_URL,
    REFUSED_SINGLE_SHOT,
    STATUS_RATE_LIMITED,
    STATUS_TRANSIENT_TRANSPORT,
    TRANSIENT_TRANSPORT,
    Outcome,
    Pacer,
    ProbeError,
    ProbeRun,
    Retries,
    assert_mock_host,
    assert_mock_trading_tr,
    assert_no_live_futures_config,
    build_auth_config,
    call_evidence,
    classify_answer,
    dry_run_banner,
    http_json,
    http_json_with_headers,
    is_rate_limited,
    probe_token_cache_dir,
    record_retry,
    redact,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    retry_evidence,
    retry_once,
    rt_cd_of,
    summarize_latencies,
    transient_kind,
    transport_excerpt,
    transport_transient_types,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_FUT_ORDER_PATH = "/uapi/domestic-futureoption/v1/trading/order"
_FUT_CANCEL_PATH = "/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
_FUT_INQUIRE_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-ccnl"
_STOCK_ORDER_PATH = "/uapi/domestic-stock/v1/trading/order-cash"
_STOCK_CANCEL_PATH = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
_STOCK_BALANCE_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"
_STOCK_DAILY_CCLD_PATH = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
_FUT_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_STOCK_PRICE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"

_EXECUTION_CONFIG = Path(__file__).resolve().parents[2] / "config" / "execution.yaml"

_STOCK_QUOTE_UNIT_FIELD = "aspr_unit"

_STOCK_ORD_DVSN: dict[str, str] = {
    "limit": "00",
    "market": "01",
}

_STOCK_DAILY_CCLD_TR_MOCK = "VTTC0081R"

_STOCK_CANCEL_TR_MOCK = "VTTC0013U"

_STOCK_CANCEL_DVSN_CANCEL = "02"

_STOCK_CANCEL_QTY_ALL = "Y"

_STOCK_EXCG_KRX = "KRX"

_STOCK_ORD_UNPR_MARKET = "0"

_NMPR_FIELDS = ("NMPR_TYPE_CD", "KRX_NMPR_CNDT_CD")

_NMPR_ARMS: dict[str, tuple[str, str]] = {
    "explicit": ("01", "0"),
    "legacy_blank": ("", ""),
}

POLICY_VERSION = "p-8-transient-policy/1"

DEFAULT_PACE_S = 1.1


class _CallPacer(Pacer):
    """Minimum-interval gate in front of the probe client's only socket."""


def pace_interval_s(args: argparse.Namespace) -> float:
    """The pacing interval for this run, in seconds (``0`` disables pacing)."""
    return max(0.0, float(getattr(args, "pace_s", DEFAULT_PACE_S)))


def effective_interval_ms(requested_ms: float, args: argparse.Namespace) -> float:
    """A requested inter-call interval, floored by the pacer, in ms."""
    return max(float(requested_ms), pace_interval_s(args) * 1000.0)


_ODNO_ABSENT = "absent:no-odno"

_ODNO_FORMAT_KEY = "odno_wire_format"


def odno_key(raw: Any) -> str:
    """Canonical comparison key for a KIS order number (ODNO)."""
    text = str(raw if raw is not None else "").strip()
    if not text:
        return _ODNO_ABSENT
    if not (text.isascii() and text.isdigit()):
        raise ProbeError(
            f"ODNO {text!r} is not numeric. This harness will not guess at an "
            "identifier encoding: record the raw value and settle the format "
            "before treating it as an order number."
        )
    return text.lstrip("0") or "0"


def _odno_encoding(raw: str) -> dict[str, Any]:
    """One verbatim ODNO plus the padding shape that makes it non-comparable."""
    lead = raw[:1]
    encoding: dict[str, Any] = {
        "verbatim": raw,
        "length": len(raw),
        "leading_pad": ("space" if lead == " " else "zero" if lead == "0" else "none"),
    }
    try:
        encoding["canonical_key"] = odno_key(raw)
    except ProbeError as exc:
        encoding["canonical_key_error"] = str(exc)
    return encoding


def record_odno_wire_format(
    run: ProbeRun, submitted: list[str], rows: list[dict[str, Any]]
) -> None:
    """Record how each broker surface encoded an ODNO in THIS run."""
    existing = run.measurements.get(_ODNO_FORMAT_KEY)
    if isinstance(existing, dict) and existing.get("paired"):
        return
    submit_samples = [str(o) for o in submitted if str(o).strip()]
    row_samples = [
        str(r.get("odno", "")) for r in rows if str(r.get("odno", "")).strip()
    ]
    record: dict[str, Any] = {
        "paired": bool(submit_samples and row_samples),
        "submit_response_field": "output.ODNO (order accept response)",
        "query_row_field": "output1[].odno (inquire-ccnl row)",
        "submit_response_samples": [_odno_encoding(s) for s in submit_samples[:3]],
        "query_row_samples": [_odno_encoding(s) for s in row_samples[:3]],
        "identity_matching": (
            "The two surfaces disagree on padding, so matching a submitted order "
            "against a query row must canonicalize BOTH sides (strip whitespace, "
            "then strip leading zeros). A raw strip-and-compare evaluates "
            "'762' == '0000000762' and never matches: artifact "
            "P-5-20260731T002112Z reported 1 CENSORED trial and n=0 for exactly "
            "that reason while the cleanup cancel of the same ODNO returned "
            "rt_cd=0, proving the order existed and the query had returned it."
        ),
        "reported_identifiers": (
            "Measurements that list ODNOs report canonical keys (leading zeros "
            "stripped). The verbatim wire forms are the samples above."
        ),
        "scope": (
            "One 모의투자 account, one session, mock environment. Recorded as the "
            "encoding observed here — not as a general KIS guarantee, and not "
            "extrapolated to 실전."
        ),
    }
    if not record["paired"]:
        record["incomplete"] = (
            "only one surface produced an ODNO in this run, so the two encodings "
            "were not observed side by side here. The paired sample is in artifact "
            "P-5-20260731T002112Z. Recorded rather than omitted."
        )
    run.measure(_ODNO_FORMAT_KEY, record)


@dataclass
class Placed:
    odno: str
    sent_at_monotonic: float
    body: dict[str, Any]
    krx_fwdg_ord_orgno: str = ""

    @property
    def key(self) -> str:
        """This order's canonical identity, for matching against a query row."""
        return odno_key(self.odno)


@dataclass(frozen=True)
class Tick:
    """A valid price increment plus the evidence that established it."""

    size: Decimal
    source: str


@dataclass(frozen=True)
class TickPrice:
    """A limit price snapped to a broker-valid tick."""

    value: float
    wire: str
    tick: Tick
    unrounded: float
    rounding: str

    def describe(self) -> dict[str, Any]:
        """The artifact record: the price, the tick, and where the tick came from."""
        return {
            "wire_value": self.wire,
            "unrounded": self.unrounded,
            "tick_size": str(self.tick.size),
            "tick_source": self.tick.source,
            "rounding": self.rounding,
            "rounding_rationale": (
                "away from the touch — a resting probe depends on the order NOT "
                "filling, so a snap must never move the price toward the touch; "
                "P-11's marketable order is the mirror case and snaps further in"
            ),
        }


def _tick_wire(value: Decimal) -> str:
    """A snapped price as the clean decimal string a request body will carry."""
    return format(value.normalize(), "f")


def snap_to_tick(price: float, tick: Tick, *, side: str, marketable: bool) -> TickPrice:
    """Snap ``price`` to a multiple of ``tick``, always AWAY from the touch."""
    if side not in ("BUY", "SELL"):
        raise ProbeError(f"unknown order side {side!r} (expected 'BUY' or 'SELL')")
    if tick.size <= 0:
        raise ProbeError(
            f"tick size must be positive, got {tick.size} from {tick.source}"
        )
    round_down = (side == "BUY") != marketable
    multiple = (Decimal(str(price)) / tick.size).to_integral_value(
        rounding=ROUND_FLOOR if round_down else ROUND_CEILING
    )
    snapped = multiple * tick.size
    if snapped <= 0 or snapped % tick.size != 0:
        raise ProbeError(
            f"snapped price {snapped} is not a positive multiple of tick "
            f"{tick.size} ({tick.source}); refusing to send it"
        )
    wire = _tick_wire(snapped)
    if Decimal(wire) != snapped:
        raise ProbeError(
            f"wire string {wire!r} does not represent snapped price {snapped} "
            "exactly; refusing to send a float artifact to the broker"
        )
    return TickPrice(
        value=float(snapped),
        wire=wire,
        tick=tick,
        unrounded=price,
        rounding="floor" if round_down else "ceiling",
    )


def build_stock_order_body(
    cano: str,
    acnt_prdt_cd: str,
    symbol: str,
    qty: int,
    price: TickPrice | None = None,
    *,
    order_type: str = "limit",
) -> dict[str, str]:
    """The ``order-cash`` request body — 지정가 or 시장가."""
    ord_dvsn = _STOCK_ORD_DVSN.get(order_type)
    if ord_dvsn is None:
        raise ProbeError(
            f"unknown stock order type {order_type!r} "
            f"(expected one of {sorted(_STOCK_ORD_DVSN)})"
        )
    if order_type == "limit" and price is None:
        raise ProbeError("a 지정가 (limit) stock order needs a tick-snapped price")
    if order_type == "market" and price is not None:
        raise ProbeError(
            "a 시장가 (market) stock order must not carry a limit price "
            f"(got {price.wire!r}); ORD_UNPR is {_STOCK_ORD_UNPR_MARKET!r} by spec"
        )
    return {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": symbol,
        "ORD_DVSN": ord_dvsn,
        "ORD_QTY": str(qty),
        "ORD_UNPR": _STOCK_ORD_UNPR_MARKET if price is None else price.wire,
    }


def build_stock_cancel_body(
    cano: str,
    acnt_prdt_cd: str,
    *,
    orgn_odno: str,
    krx_fwdg_ord_orgno: str,
    remaining_qty: int,
) -> dict[str, str]:
    """The ``order-rvsecncl`` 취소 request body for a stock order."""
    if not str(orgn_odno).strip():
        raise ProbeError(
            "a stock cancel needs the 원주문번호 (ORGN_ODNO) from the accept "
            "response; refusing to send an empty one"
        )
    if not str(krx_fwdg_ord_orgno).strip():
        raise ProbeError(
            "a stock cancel needs the 거래소코드 (KRX_FWDG_ORD_ORGNO) from the "
            "accept response — order_rvsecncl declares it [필수] and refuses an "
            "empty value, so an empty one here would surface as a broker rejection"
        )
    if remaining_qty <= 0:
        raise ProbeError(
            f"a stock cancel needs a positive 잔여수량 (got {remaining_qty}); "
            "nothing is resting, so there is nothing to cancel"
        )
    return {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "KRX_FWDG_ORD_ORGNO": str(krx_fwdg_ord_orgno),
        "ORGN_ODNO": str(orgn_odno),
        "ORD_DVSN": _STOCK_ORD_DVSN["limit"],
        "RVSE_CNCL_DVSN_CD": _STOCK_CANCEL_DVSN_CANCEL,
        "ORD_QTY": str(remaining_qty),
        "ORD_UNPR": _STOCK_ORD_UNPR_MARKET,
        "QTY_ALL_ORD_YN": _STOCK_CANCEL_QTY_ALL,
        "EXCG_ID_DVSN_CD": _STOCK_EXCG_KRX,
    }


def _futures_tick(symbol: str) -> Tick:
    """The tick for a futures ``symbol``, from the repo's contract-spec registry."""
    from shared.instruments.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )

    registry = ContractSpecRegistry.from_yaml(str(_EXECUTION_CONFIG))
    try:
        spec = resolve_contract_spec(symbol, registry)
    except ValueError as exc:
        raise ProbeError(
            f"no contract spec for --symbol {symbol}: {exc}. Register the prefix in "
            "config/execution.yaml::futures_contract_spec rather than hardcoding a "
            "tick in the probe."
        ) from exc
    return Tick(
        size=Decimal(str(spec.tick_size_points)),
        source=(
            f"config/execution.yaml::futures_contract_spec.{spec.name}"
            f".tick_size_points (matched symbol_prefix {spec.symbol_prefix!r})"
        ),
    )


def _stock_tick(output: dict[str, Any], symbol: str) -> Tick:
    """The 호가단위 the broker itself reported for a stock ``symbol``."""
    raw = output.get(_STOCK_QUOTE_UNIT_FIELD)
    try:
        size = Decimal(str(raw).strip())
    except (ArithmeticError, ValueError):
        size = Decimal(0)
    if size <= 0 or size != size.to_integral_value():
        raise ProbeError(
            f"could not establish a 호가단위 (quote unit) for {symbol}: TR "
            f"FHKST01010100 returned {_STOCK_QUOTE_UNIT_FIELD}={raw!r}. This repo "
            "holds no KRX price-band table and will not guess one, and ORD_UNPR is "
            "int-truncated on the wire (Q-WIRE-1) so a fractional unit is "
            "unrepresentable. Report this as a BLOCKED precondition — do not "
            "re-run with a hand-picked price."
        )
    return Tick(
        size=size,
        source=(
            f"broker-reported 호가단위: TR FHKST01010100 (v1_국내주식-008, "
            f"/uapi/domestic-stock/v1/quotations/inquire-price) "
            f"output.{_STOCK_QUOTE_UNIT_FIELD}={raw!r}"
        ),
    )


class MockTradingClient:
    """Minimal, safety-gated KIS 모의투자 trading client for probes."""

    def __init__(
        self,
        creds: Any,
        auth_manager: Any,
        run: ProbeRun,
        timeout: float = 15.0,
        pace_s: float = DEFAULT_PACE_S,
    ):
        import requests

        self.creds = creds
        self.auth = auth_manager
        self.run = run
        self.session = requests.Session()
        self.timeout = timeout
        self.tr_ids = self._load_tr_ids()
        self.pacer = _CallPacer(pace_s)
        self._last_send_monotonic: float | None = None

    @staticmethod
    def _load_tr_ids() -> dict[str, str]:
        from shared.execution.tr_ids import get_tr_ids

        return get_tr_ids()

    def close(self) -> None:
        self.session.close()

    def _headers(self, tr_id: str) -> dict[str, str]:
        headers = dict(self.auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        return headers

    def _request(
        self,
        method: str,
        url: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        """The one place this client opens a socket — and so the one paced site."""
        assert_mock_host(url)
        headers = self._headers(tr_id)
        self._last_send_monotonic = self.pacer.wait()
        return http_json(
            self.session,
            method,
            url,
            headers=headers,
            params=params,
            json_body=body,
            timeout=self.timeout,
        )

    def last_send_instant(self) -> float:
        """Monotonic instant the most recent request was released to the wire."""
        if self._last_send_monotonic is None:
            raise ProbeError(
                "last_send_instant() called before any request was issued — "
                "there is no send to timestamp"
            )
        return self._last_send_monotonic

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
        return self._request(method, url, tr_id, params=params, body=body)

    def trading_get_with_headers(
        self,
        path: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        tr_cont: str = "",
    ) -> tuple[int, dict[str, Any], float, str, Mapping[str, str]]:
        """:meth:`trading_call` for a GET whose answer is in the RESPONSE headers."""
        url = f"{MOCK_BASE_URL}{path}"
        assert_mock_host(url)
        assert_mock_trading_tr(tr_id)
        headers = self._headers(tr_id)
        if tr_cont:
            headers["tr_cont"] = tr_cont
        self._last_send_monotonic = self.pacer.wait()
        return http_json_with_headers(
            self.session,
            "GET",
            url,
            headers=headers,
            params=params,
            timeout=self.timeout,
        )

    def quote_call(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Read-only quotations call (host-gated; TR prefix rule does not apply)."""
        url = f"{MOCK_BASE_URL}{path}"
        assert_mock_host(url)
        _status, parsed, _ms, _text = self._request("GET", url, tr_id, params=params)
        return parsed

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

    def stock_quote(self, symbol: str) -> tuple[float, Tick]:
        """Last price AND the broker's own 호가단위, from one inquire-price call."""
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
        return float(value), _stock_tick(out, symbol)

    def futures_order_body(
        self,
        symbol: str,
        qty: int,
        price: TickPrice,
        side: str,
        *,
        required_fields: str = "explicit",
    ) -> dict[str, str]:
        """Mirror of ``executor.py:458-471`` (futures order body)."""
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
            "UNIT_PRICE": price.wire,
            "NMPR_TYPE_CD": nmpr_type_cd,
            "KRX_NMPR_CNDT_CD": krx_nmpr_cndt_cd,
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": "01",
        }

    def stock_order_body(
        self,
        symbol: str,
        qty: int,
        price: TickPrice | None = None,
        *,
        order_type: str = "limit",
    ) -> dict[str, str]:
        """This session's account bound to :func:`build_stock_order_body`."""
        return build_stock_order_body(
            self.creds.cano,
            self.creds.acnt_prdt_cd,
            symbol,
            qty,
            price,
            order_type=order_type,
        )

    def stock_cancel_body(
        self, *, orgn_odno: str, krx_fwdg_ord_orgno: str, remaining_qty: int
    ) -> dict[str, str]:
        """This session's account bound to :func:`build_stock_cancel_body`."""
        return build_stock_cancel_body(
            self.creds.cano,
            self.creds.acnt_prdt_cd,
            orgn_odno=orgn_odno,
            krx_fwdg_ord_orgno=krx_fwdg_ord_orgno,
            remaining_qty=remaining_qty,
        )

    def submit_stock_verbose(
        self, body: dict[str, str], *, side: str
    ) -> tuple[Placed | None, int, dict[str, Any], str, float]:
        """POST ``order-cash`` and keep the HTTP status and the raw body."""
        tr_key = {"BUY": "stock_krx_buy_mock", "SELL": "stock_krx_sell_mock"}.get(side)
        if tr_key is None:
            raise ProbeError(f"unknown stock order side {side!r} (expected BUY/SELL)")
        status, parsed, ms, text = self.trading_call(
            "POST", _STOCK_ORDER_PATH, self.tr_ids[tr_key], body=body
        )
        sent = self.last_send_instant()
        output = parsed.get("output") or {}
        odno = str(output.get("ODNO") or "").strip()
        placed = (
            Placed(
                odno=odno,
                sent_at_monotonic=sent,
                body=dict(body),
                krx_fwdg_ord_orgno=str(output.get("KRX_FWDG_ORD_ORGNO") or "").strip(),
            )
            if status == 200 and rt_cd_of(parsed) == "0" and odno
            else None
        )
        return placed, status, parsed, text, ms

    def cancel_stock_verbose(
        self, *, orgn_odno: str, krx_fwdg_ord_orgno: str, remaining_qty: int
    ) -> tuple[int, dict[str, Any], str, float, dict[str, str]]:
        """POST the stock 취소 (``VTTC0013U``), keeping status, body and request."""
        body = self.stock_cancel_body(
            orgn_odno=orgn_odno,
            krx_fwdg_ord_orgno=krx_fwdg_ord_orgno,
            remaining_qty=remaining_qty,
        )
        assert_mock_trading_tr(_STOCK_CANCEL_TR_MOCK)
        status, parsed, ms, text = self.trading_call(
            "POST", _STOCK_CANCEL_PATH, _STOCK_CANCEL_TR_MOCK, body=body
        )
        return status, parsed, text, ms, body

    def submit_futures(
        self, body: dict[str, str]
    ) -> tuple[Placed | None, dict[str, Any], float]:
        """The parsed submit. Status and raw text are dropped — see"""
        placed, _status, parsed, _text, ms = self.submit_futures_verbose(body)
        return placed, parsed, ms

    def submit_futures_verbose(
        self, body: dict[str, str]
    ) -> tuple[Placed | None, int, dict[str, Any], str, float]:
        """:meth:`submit_futures` plus the HTTP status and the raw body."""
        tr_id = self.tr_ids["futures_order_day_mock"]
        status, parsed, ms, text = self.trading_call(
            "POST", _FUT_ORDER_PATH, tr_id, body=body
        )
        sent = self.last_send_instant()
        odno = str((parsed.get("output") or {}).get("ODNO") or "").strip()
        placed = (
            Placed(odno, sent, body)
            if status == 200 and parsed.get("rt_cd") == "0" and odno
            else None
        )
        return placed, status, parsed, text, ms

    def cancel_futures(self, odno: str, qty: int) -> dict[str, Any]:
        """Cancel — ``RVSE_CNCL_DVSN_CD='02'`` (executor.py:689)."""
        return self._rvsecncl(odno, qty, dvsn="02", price=None)[1]

    def cancel_futures_verbose(
        self, odno: str, qty: int
    ) -> tuple[int, dict[str, Any], str]:
        """Cancel, keeping the HTTP status and raw body."""
        return self._rvsecncl(odno, qty, dvsn="02", price=None)

    def replace_futures(self, odno: str, qty: int, price: TickPrice) -> dict[str, Any]:
        """Amend — ``RVSE_CNCL_DVSN_CD='01'``. Never exercised by the runtime"""
        return self.replace_futures_verbose(odno, qty, price)[1]

    def replace_futures_verbose(
        self, odno: str, qty: int, price: TickPrice
    ) -> tuple[int, dict[str, Any], str]:
        """:meth:`replace_futures` plus the HTTP status and the raw body, for"""
        return self._rvsecncl(odno, qty, dvsn="01", price=price)

    def _rvsecncl(
        self, odno: str, qty: int, *, dvsn: str, price: TickPrice | None
    ) -> tuple[int, dict[str, Any], str]:
        if dvsn == "01" and price is None:
            raise ProbeError(
                "an amend (RVSE_CNCL_DVSN_CD='01') needs a tick-snapped price"
            )
        tr_id = self.tr_ids["futures_cancel_day_mock"]
        body = {
            "ORD_PRCS_DVSN_CD": "02",
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "RVSE_CNCL_DVSN_CD": dvsn,
            "ORGN_ODNO": odno,
            "ORD_QTY": str(qty),
            "UNIT_PRICE": price.wire if price is not None else "0",
            "NMPR_TYPE_CD": "01",
            "KRX_NMPR_CNDT_CD": "0",
            "RMN_QTY_YN": "Y",
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            "ORD_DVSN_CD": "01",
        }
        status, parsed, _ms, text = self.trading_call(
            "POST", _FUT_CANCEL_PATH, tr_id, body=body
        )
        return status, parsed, text

    def _inquire_futures_call(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk200: str = "",
        nk200: str = "",
    ) -> tuple[int, dict[str, Any], str]:
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
        status, parsed, _ms, text = self.trading_call(
            "GET", _FUT_INQUIRE_PATH, tr_id, params=params
        )
        return status, parsed, text

    def inquire_futures(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk200: str = "",
        nk200: str = "",
    ) -> dict[str, Any]:
        """The parsed open-order listing. Raises on a transport failure."""
        _status, parsed, _text = self._inquire_futures_call(
            symbol, odno=odno, day_offset=day_offset, fk200=fk200, nk200=nk200
        )
        return parsed

    def inquire_futures_classified(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk200: str = "",
        nk200: str = "",
    ) -> Outcome:
        """:meth:`inquire_futures`, classified instead of raising."""
        try:
            status, parsed, text = self._inquire_futures_call(
                symbol, odno=odno, day_offset=day_offset, fk200=fk200, nk200=nk200
            )
        except transport_transient_types() as exc:
            return Outcome(
                kind=STATUS_TRANSIENT_TRANSPORT,
                http_status=0,
                parsed={},
                text=transport_excerpt(exc),
                payload=[],
            )
        rows = parsed.get("output1")
        return Outcome(
            kind=classify_answer(status, parsed, text),
            http_status=status,
            parsed=parsed,
            text=text,
            payload=rows if isinstance(rows, list) else [],
        )

    def stock_balance(self, *, fk: str = "", nk: str = "") -> dict[str, Any]:
        """The parsed balance page. See :meth:`stock_balance_verbose`."""
        return self.stock_balance_verbose(fk=fk, nk=nk)[1]

    def stock_balance_verbose(
        self, *, fk: str = "", nk: str = ""
    ) -> tuple[int, dict[str, Any], str, float]:
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
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk,
        }
        status, parsed, ms, text = self.trading_call(
            "GET", _STOCK_BALANCE_PATH, tr_id, params=params
        )
        return status, parsed, text, ms

    def stock_daily_ccld(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk: str = "",
        nk: str = "",
    ) -> dict[str, Any]:
        """The parsed inquiry page. See :meth:`stock_daily_ccld_verbose`."""
        return self.stock_daily_ccld_verbose(
            symbol, odno=odno, day_offset=day_offset, fk=fk, nk=nk
        )[1]

    def stock_daily_ccld_verbose(
        self,
        symbol: str,
        *,
        odno: str = "",
        day_offset: int = 0,
        fk: str = "",
        nk: str = "",
    ) -> tuple[int, dict[str, Any], str, float]:
        """주식일별주문체결조회 — read-only execution inquiry (mock ``VTTC0081R``)."""
        tr_id = _STOCK_DAILY_CCLD_TR_MOCK
        assert_mock_trading_tr(tr_id)
        day = (datetime.now(KST) - timedelta(days=day_offset)).date().strftime("%Y%m%d")
        params = {
            "CANO": self.creds.cano,
            "ACNT_PRDT_CD": self.creds.acnt_prdt_cd,
            "INQR_STRT_DT": day,
            "INQR_END_DT": day,
            "SLL_BUY_DVSN_CD": "00",
            "PDNO": symbol,
            "CCLD_DVSN": "00",
            "INQR_DVSN": "00",
            "INQR_DVSN_3": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": odno,
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": fk,
            "CTX_AREA_NK100": nk,
            "EXCG_ID_DVSN_CD": "KRX",
        }
        status, parsed, ms, text = self.trading_call(
            "GET", _STOCK_DAILY_CCLD_PATH, tr_id, params=params
        )
        return status, parsed, text, ms


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
    return run, MockTradingClient(creds, auth, run, pace_s=pace_interval_s(args))


def _resting_price(
    client: MockTradingClient, args: argparse.Namespace
) -> tuple[TickPrice, str]:
    """A tick-valid limit price far enough from the touch that it will not fill."""
    side = "BUY"
    if args.asset == "futures":
        last = client.futures_last_price(args.symbol)
        tick = _futures_tick(args.symbol)
    else:
        last, tick = client.stock_quote(args.symbol)
    price = last * (1.0 - args.price_offset_pct / 100.0)
    if price <= 0:
        raise ProbeError("computed resting price <= 0; check --price-offset-pct")
    return snap_to_tick(price, tick, side=side, marketable=False), side


_CLEANUP_CANCELLED = "CANCELLED"
_CLEANUP_NOTHING_TO_CANCEL = "NOTHING_TO_CANCEL_NO_LIVE_ROW"
_CLEANUP_STILL_LIVE = "REJECTED_AND_STILL_LIVE"
_CLEANUP_LIVENESS_UNKNOWN = "REJECTED_LIVENESS_UNDETERMINED"
_CLEANUP_THROTTLED = "REJECTED_THROTTLE_NOT_CLEARED"
_CLEANUP_EXCEPTION = "CANCEL_CALL_RAISED"

_CLEANUP_LIVENESS_NOTE = (
    "Cleanup consumes the qty>0 liveness predicate with the OPPOSITE polarity to "
    "coexistence_ms. Here a missing live row silences an error, so a surface that "
    "under-reports liveness is fail-OPEN, and the 2026-08-01 'the bias is the safe "
    "one' argument does NOT carry over. That is why this lookup requires rt_cd=0, "
    "walks the continuation keys to the end of the book (P-5b measured this same "
    "surface at 15 rows/page with continuation), refuses to answer on a truncated "
    "or unreadable walk, and is never consulted at all for a throttled cancel."
)

_CLEANUP_ATTEMPTS = 3

_CLEANUP_RETRY_S = 1.5


def _transient_recorder(
    run: ProbeRun | None, retries: Retries | None
) -> Callable[[dict[str, Any], str], None]:
    """Where a transient goes. Built ONCE per walk, never per page."""
    if run is None:
        return lambda _evidence, _kind: None
    if retries is not None:
        return record_retry(run, retries)

    def _observe(evidence: dict[str, Any], _kind: str) -> None:
        run.observe(retry_evidence=evidence)

    return _observe


def _live_odno_keys(
    client: MockTradingClient,
    symbol: str,
    max_pages: int,
    *,
    run: ProbeRun | None = None,
    retries: Retries | None = None,
) -> tuple[dict[str, dict[str, Any]] | None, dict[str, Any]]:
    """Every order the open-order surface shows with ``qty > 0``."""
    live: dict[str, dict[str, Any]] = {}
    evidence: dict[str, Any] = {"pages_walked": 0, "rows_seen": 0}
    cursor = {"fk": "", "nk": ""}
    on_transient = _transient_recorder(run, retries)

    def _page_call() -> Outcome:
        return client.inquire_futures_classified(
            symbol, fk200=cursor["fk"], nk200=cursor["nk"]
        )

    for page in range(max(int(max_pages), 1)):
        try:
            outcome, _attempts, _retried = retry_once(
                _page_call,
                on_transient,
                client.pacer,
                wait_s=client.pacer.interval_s,
                phase="cleanup_liveness",
            )
        except Exception as exc:  # noqa: BLE001 - a transport failure is not an answer
            evidence["outcome"] = f"QUERY_RAISED: {type(exc).__name__}"
            return None, evidence
        if outcome.kind is not None:
            evidence["outcome"] = "QUERY_NOT_AN_ANSWER"
            evidence["status_kind"] = outcome.kind
            evidence["rt_cd"] = outcome.parsed.get("rt_cd")
            evidence["msg_cd"] = outcome.parsed.get("msg_cd")
            evidence["msg1"] = outcome.parsed.get("msg1")
            evidence["http_status"] = outcome.http_status
            return None, evidence
        listing = outcome.parsed
        if not isinstance(listing, dict):
            evidence["outcome"] = "MALFORMED_RESPONSE"
            return None, evidence
        evidence["pages_walked"] = page + 1
        rt_cd = rt_cd_of(listing)
        if rt_cd != "0":
            evidence["outcome"] = "NOT_A_POSITIVE_ANSWER"
            evidence["rt_cd"] = rt_cd
            evidence["msg_cd"] = listing.get("msg_cd")
            evidence["msg1"] = listing.get("msg1")
            return None, evidence
        rows = listing.get("output1")
        if not isinstance(rows, list):
            evidence["outcome"] = "OUTPUT1_NOT_A_LIST"
            return None, evidence
        for row in rows:
            if not isinstance(row, dict):
                evidence["outcome"] = "UNREADABLE_ROW"
                return None, evidence
            try:
                key = odno_key(row.get("odno"))
                qty = int(float(row.get("qty") or 0))
            except (ProbeError, TypeError, ValueError):
                evidence["outcome"] = "UNREADABLE_ROW"
                return None, evidence
            if qty > 0:
                live[key] = row
        evidence["rows_seen"] += len(rows)
        next_fk = str(listing.get("ctx_area_fk200") or "").strip()
        next_nk = str(listing.get("ctx_area_nk200") or "").strip()
        if not next_fk and not next_nk:
            evidence["outcome"] = "COMPLETE_WALK"
            return live, evidence
        if not rows:
            evidence["outcome"] = "EMPTY_PAGE_WITH_CONTINUATION_KEY"
            return None, evidence
        if (next_fk, next_nk) == (cursor["fk"], cursor["nk"]):
            evidence["outcome"] = "CONTINUATION_KEYS_DID_NOT_ADVANCE"
            return None, evidence
        cursor["fk"], cursor["nk"] = next_fk, next_nk
    evidence["outcome"] = "PAGE_BUDGET_EXHAUSTED_BOOK_INCOMPLETE"
    return None, evidence


def _cancel_one(
    client: MockTradingClient,
    run: ProbeRun,
    odno: str,
    qty: int,
    symbol: str | None,
    max_pages: int,
    retries: Retries | None = None,
) -> str:
    """Cancel one probe-created order and return its ``_CLEANUP_*`` disposition."""
    try:
        key: str | None = odno_key(odno)
    except ProbeError:
        key = None
    live_keys: dict[str, dict[str, Any]] | None = None
    liveness: dict[str, Any] = {}
    throttled = False
    result: dict[str, Any] = {}
    for attempt in range(1, _CLEANUP_ATTEMPTS + 1):
        try:
            status, result, text = client.cancel_futures_verbose(odno, qty)
        except Exception as exc:  # noqa: BLE001 - cleanup must never mask results
            run.error(f"CLEANUP EXCEPTION for {odno}: {type(exc).__name__}: {exc}")
            return _CLEANUP_EXCEPTION
        if result.get("rt_cd") == "0":
            run.observe(
                cleanup_cancel=odno,
                ok=True,
                msg=result.get("msg1"),
                disposition=_CLEANUP_CANCELLED,
                attempt=attempt,
            )
            return _CLEANUP_CANCELLED
        throttled = is_rate_limited(status, result, text)
        if not throttled:
            live_keys, liveness = (
                _live_odno_keys(client, symbol, max_pages, run=run, retries=retries)
                if symbol
                else (None, {"outcome": "NO_SYMBOL_TO_QUERY"})
            )
            if live_keys is not None and key is not None and key not in live_keys:
                run.observe(
                    cleanup_cancel=odno,
                    ok=False,
                    msg=result.get("msg1"),
                    disposition=_CLEANUP_NOTHING_TO_CANCEL,
                    attempt=attempt,
                    liveness_evidence=liveness,
                    liveness_source=(
                        "inquire-ccnl answered rt_cd=0 for the whole book and showed "
                        "no row with qty>0 for this ODNO — nothing was left to cancel"
                    ),
                )
                return _CLEANUP_NOTHING_TO_CANCEL
        if attempt < _CLEANUP_ATTEMPTS:
            time.sleep(_CLEANUP_RETRY_S * attempt)
            continue
        if throttled:
            disposition = _CLEANUP_THROTTLED
        elif live_keys is not None:
            disposition = _CLEANUP_STILL_LIVE
        else:
            disposition = _CLEANUP_LIVENESS_UNKNOWN
        run.observe(
            cleanup_cancel=odno,
            ok=False,
            msg=result.get("msg1"),
            disposition=disposition,
            attempt=attempt,
            liveness_evidence=liveness or {"outcome": "NOT_CONSULTED_THROTTLED"},
        )
        run.error(
            f"CLEANUP FAILED — order {odno} may still be resting. "
            f"Cancel it manually: {result.get('msg1')}"
        )
        return disposition
    return _CLEANUP_LIVENESS_UNKNOWN  # pragma: no cover - loop always returns


def _cleanup(
    client: MockTradingClient | None,
    run: ProbeRun,
    odnos: list[str],
    qty: int,
    *,
    symbol: str | None = None,
    max_pages: int = 10,
    retries: Retries | None = None,
) -> dict[str, str]:
    """Cancel every order the probe created and classify each outcome."""
    dispositions: dict[str, str] = {}
    if client is None:
        return dispositions
    seen: list[str] = []
    for odno in odnos:
        if odno and odno not in seen:
            seen.append(odno)
    if len(seen) < len([o for o in odnos if o]):
        run.observe(
            cleanup_duplicate_odnos_collapsed=len([o for o in odnos if o]) - len(seen),
            reading="the probe recorded one ODNO more than once — an amend that "
            "rests under the same number does this — and it is cancelled once",
        )
    for odno in seen:
        dispositions[odno] = _cancel_one(
            client, run, odno, qty, symbol, max_pages, retries
        )
    if dispositions:
        run.measure("cleanup_liveness_note", _CLEANUP_LIVENESS_NOTE)
    return dispositions


_UNACCOUNTED_KEY = "unaccounted_live_orders"

_ROW_PRICE_FIELDS = ("ord_unpr", "ord_idx")
_ROW_SIDE_FIELD = "sll_buy_dvsn_cd"

_SIDE_BUY = "02"


def _row_matches_this_trial(
    row: dict[str, Any], *, symbol: str, qty: int, price: TickPrice
) -> tuple[bool, list[str], list[str]]:
    """Could this open-order row be the order THIS trial placed?"""
    checked: list[str] = []
    unavailable: list[str] = []
    matches = True

    row_pdno = str(row.get("pdno") or "").strip()
    if row_pdno:
        checked.append("pdno")
        matches = matches and row_pdno == symbol
    else:
        unavailable.append("pdno")

    raw_qty = str(row.get("ord_qty") or "").strip()
    if raw_qty:
        checked.append("ord_qty")
        try:
            matches = matches and int(float(raw_qty)) == qty
        except (TypeError, ValueError):
            matches = False
    else:
        unavailable.append("ord_qty")

    side = str(row.get(_ROW_SIDE_FIELD) or "").strip()
    if side:
        checked.append(_ROW_SIDE_FIELD)
        matches = matches and side == _SIDE_BUY
    else:
        unavailable.append(_ROW_SIDE_FIELD)

    for field in _ROW_PRICE_FIELDS:
        raw_price = str(row.get(field) or "").strip()
        if not raw_price:
            continue
        checked.append(field)
        try:
            matches = matches and Decimal(raw_price) == Decimal(price.wire)
        except (ArithmeticError, TypeError, ValueError):
            matches = False
        break
    else:
        unavailable.append("|".join(_ROW_PRICE_FIELDS))

    return matches, checked, unavailable


def _cancellable_odno(query_row_value: str) -> str:
    """The wire form to send as ``ORGN_ODNO`` for a row seen only in a QUERY."""
    stripped = query_row_value.strip()
    return stripped.rjust(len(query_row_value), "0")


def _cleanup_unaccounted(
    client: MockTradingClient,
    run: ProbeRun,
    *,
    symbol: str,
    qty: int,
    price: TickPrice,
    max_pages: int,
    known: set[str],
    may_cancel: bool,
    retries: Retries | None = None,
) -> None:
    """Account for anything live on ``symbol`` that this trial did not place."""
    live, evidence = _live_odno_keys(
        client, symbol, max_pages, run=run, retries=retries
    )
    if live is None:
        run.measure(
            _UNACCOUNTED_KEY,
            {
                "status": "UNDETERMINED",
                "liveness_evidence": evidence,
                "reading": "the open-order surface did not answer for the whole "
                "book, so whether an unaccounted order is resting could not be "
                "established — check the account by hand",
            },
        )
        run.error(
            f"ORDER STATE UNKNOWN and the book walk did not answer either "
            f"({evidence.get('outcome')}) — check {symbol} on the account by "
            "hand before running P-8 again"
        )
        return

    candidates: dict[str, str] = {}
    foreign: list[str] = []
    criteria: dict[str, Any] = {}
    for key, row in live.items():
        if key in known:
            continue
        matches, checked, unavailable = _row_matches_this_trial(
            row, symbol=symbol, qty=qty, price=price
        )
        criteria = {"checked": checked, "not_carried_by_the_row": unavailable}
        if matches:
            candidates[key] = str(row.get("odno") or "")
        else:
            foreign.append(key)

    if foreign:
        run.measure(
            "foreign_live_rows_present",
            {
                "status": "FOREIGN_LIVE_ROWS_PRESENT",
                "canonical_keys": sorted(foreign),
                "match_criteria": criteria,
                "reading": "live on this symbol, not placed by this trial, and "
                "not matching this trial's order body — another probe's or the "
                "operator's. NOT touched.",
            },
        )
        run.error(
            f"FOREIGN LIVE ROW(S) on {symbol}: {sorted(foreign)} — left alone. "
            "They do not match this trial's order body."
        )

    if not candidates:
        run.measure(
            _UNACCOUNTED_KEY,
            {
                "status": "NONE_FOUND",
                "liveness_evidence": evidence,
                "match_criteria": criteria,
                "reading": "the surface answered for the whole book and no live "
                "row both (a) was unknown to this trial and (b) matched its "
                "order body",
            },
        )
        return

    sent = {key: _cancellable_odno(raw) for key, raw in candidates.items()}
    record: dict[str, Any] = {
        "liveness_evidence": evidence,
        "canonical_keys": sorted(candidates),
        "query_row_verbatim": {k: candidates[k] for k in sorted(candidates)},
        "match_criteria": criteria,
        "odno_form_note": (
            "the query surface space-pads and the order surface zero-pads "
            "(odno_wire_format); an unaccounted row has no accept response, "
            "so a cancelled form is RECONSTRUCTED from the row by re-padding "
            "with zeros to the same width"
        ),
        "reading": "live on this symbol, unknown to this trial, and matching "
        "its order body — the order the lost call left behind is the leading "
        "reading, and it is not the only one",
    }
    if not may_cancel:
        record["status"] = "FOUND_NOT_CANCELLED"
        record["cancel_odno_would_send"] = {k: sent[k] for k in sorted(sent)}
        record["reading"] += (
            ". NOT cancelled: --cancel-unaccounted was not given, and this "
            "account is shared by the campaign"
        )
        run.measure(_UNACCOUNTED_KEY, record)
        run.error(
            f"UNACCOUNTED LIVE ORDER(S) on {symbol}: {sorted(candidates)} — "
            "matching this trial's order body and NOT cancelled (no "
            "--cancel-unaccounted). Cancel them before running P-8 again."
        )
        return

    record["status"] = "FOUND"
    record["cancel_odno_sent"] = {k: sent[k] for k in sorted(sent)}
    dispositions = {
        odno: _cancel_one(client, run, odno, qty, symbol, max_pages, retries)
        for odno in sent.values()
    }
    record["cleanup_dispositions"] = dispositions
    run.measure(_UNACCOUNTED_KEY, record)
    run.error(
        f"UNACCOUNTED LIVE ORDER(S) on {symbol}: {sorted(candidates)} — "
        f"matching this trial's order body, cancelled under "
        f"--cancel-unaccounted. Dispositions: {dispositions}"
    )


def _require_symbol(args: argparse.Namespace) -> None:
    if not args.symbol:
        raise ProbeError("--symbol is required (e.g. 101S6000 futures, 005930 stock)")


def probe_p2(args: argparse.Namespace) -> ProbeRun:
    """P-2 SUBMISSION_IDEMPOTENCY — does an identical body produce two ODNOs?"""
    spec = get("P-2")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="two identical futures order bodies",
            gap_ms=effective_interval_ms(args.gap_ms, args),
        )
        return run
    odnos: list[str] = []
    try:
        price, side = _resting_price(client, args)
        body = client.futures_order_body(args.symbol, args.quantity, price, side)
        run.observe(order_body=body, resting_price=price.wire, side=side)
        run.measure("limit_price_tick", price.describe())

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
        record_odno_wire_format(run, distinct, rows)
        observed = sorted(
            {odno_key(r.get("odno")) for r in rows} & {odno_key(o) for o in distinct}
        )

        run.measure("gap_ms", effective_interval_ms(args.gap_ms, args))
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
            "gap_semantics",
            "gap_ms is the EFFECTIVE gap: --pace-s floors --gap-ms, so a requested "
            "gap below the pacing interval never reached the wire. Bracket the "
            "window against this value, and to probe a gap below --pace-s you must "
            "lower --pace-s as well — accepting the throttling risk that implies.",
        )
        run.measure(
            "window_semantics",
            "A single ODNO does NOT establish deduplication_window_ms = gap. It "
            "establishes only that the window is >= gap. Bracket it: the largest "
            "deduping gap is a lower bound, the smallest non-deduping gap an upper bound.",
        )
    finally:
        _cleanup(client, run, odnos, args.quantity, symbol=args.symbol)
        client.close()
    return run


def probe_p5(args: argparse.Namespace) -> ProbeRun:
    """P-5 OPEN_ORDER_QUERY — order-accept to query-visible convergence latency."""
    spec = get("P-5")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send=f"{args.samples} resting orders, polling inquire-ccnl every "
            f"{effective_interval_ms(args.poll_ms, args)}ms"
        )
        return run
    odnos: list[str] = []
    samples: list[float] = []
    try:
        price, side = _resting_price(client, args)
        run.measure("limit_price_tick", price.describe())
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
                record_odno_wire_format(run, [placed.odno], rows)
                if any(odno_key(r.get("odno")) == placed.key for r in rows):
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
            client.cancel_futures(placed.odno, args.quantity)
            odnos.remove(placed.odno)
            time.sleep(args.inter_trial_s)
        run.measure(
            "B_broker_query_consistency_candidate",
            summarize_latencies(
                samples, margin_pct=args.margin_pct, label="accept_to_visible_ms"
            ),
        )
        run.measure("poll_granularity_ms", effective_interval_ms(args.poll_ms, args))
        run.measure(
            "granularity_note",
            "Each sample carries up to one poll interval of additive error. The "
            "approved bound must exceed max_observed + poll_granularity_ms, not just "
            "max_observed. poll_granularity_ms is the EFFECTIVE interval "
            "max(--poll-ms, --pace-s): the pacer floors polling, so a smaller "
            "--poll-ms did not happen and recording it would understate the additive "
            "error — and therefore the bound (runbook §8.3).",
        )
        run.measure(
            "censored_trials", len([o for o in run.observations if o.get("censored")])
        )
    finally:
        _cleanup(client, run, odnos, args.quantity, symbol=args.symbol)
        client.close()
    return run


def probe_p5b(args: argparse.Namespace) -> ProbeRun:
    """P-5b OPEN_ORDER_QUERY — continuation-key (CTX_AREA_FK200/NK200) behaviour."""
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


_P8_COEXISTENCE_LIVENESS_NOTE = (
    "'live' here means visible on the inquire-ccnl surface with qty>0. That is "
    "survival ON THE QUERY SURFACE and an UPPER approximation of real survival, so "
    "coexistence_ms is quoted as an UPPER BOUND only. For this consumer the bias is "
    "fail-closed: over-stating coexistence over-states the protection-overlap "
    "hazard that B_protective_request_complete defends. The dangerous direction — "
    "missing a live leg and declaring atomicity — came from ODNO normalization and "
    "was fixed in 55c3d162. This argument is SCOPED TO coexistence_ms: cleanup "
    "consumes the same predicate with the opposite polarity and needs its own "
    "guards, which is what cleanup_liveness_note records."
)

_P8_CONSUMPTION_NOTE = (
    "A fill produces the SAME observation — an original that is not live and "
    "cannot be cancelled — and P-8 does not query the execution surface, so this "
    "field states the STRUCTURAL fact only and names no cause. The amend taking "
    "the quantity is the leading reading because the order is placed "
    "--price-offset-pct away from the touch specifically to avoid filling, but "
    "'unlikely to fill' is not 'did not fill'. To attribute the cause, add the "
    "execution inquiry P-11 already calls (_FILL_EVIDENCE_SOURCE)."
)


_P8_STOP_PREFIX = "P8_STOP="
_P8_COEXISTENCE_PREFIX = "P8_COEXISTENCE="

_P8_STOP_NONE = "none"

_P8_STOP_REJECTED = "rejected"

_P8_STOP_RATE_LIMITED = "rate_limited"

_P8_STOP_ORDER_STATE_UNKNOWN = "order_state_unknown"

_P8_STOP_TRANSIENT = "transient"

_P8_STOP_QUERY_UNANSWERED = "query_unanswered"

_EMPTY_BOOK_MSG_CD = "KIOK0560"

_P8_STOP_UNKNOWN = "unknown"

_P8_STOP_DRY_RUN = "dry_run"

_P8_COEXISTENCE_MEASURED = "measured"
_P8_COEXISTENCE_NOT_MEASURED = "not_measured"


def _print_p8_verdict(stop: str, measured: bool) -> None:
    """The two anchored lines. Called from ``probe_p8``'s ``finally``, so they"""
    print(f"{_P8_STOP_PREFIX}{stop}")
    print(
        f"{_P8_COEXISTENCE_PREFIX}"
        f"{_P8_COEXISTENCE_MEASURED if measured else _P8_COEXISTENCE_NOT_MEASURED}"
    )


_P8_NO_RETRY_REASON: dict[str, str] = {
    "quote": (
        "retrying a price lookup only moves the trial's clock — nothing is "
        "resting yet, and a broker that cannot answer a price query is not "
        "one to start placing orders against"
    ),
    "submit": ("a resent submit is the duplicate-order hazard P-2 exists to measure"),
    "amend": "a resent amend could consume the original's quantity twice",
}


def _record_write_transport_stop(run: ProbeRun, phase: str, exc: BaseException) -> str:
    """Classify a transport failure on a single-shot call, without retrying."""
    excerpt = transport_excerpt(exc)
    run.observe(
        retry_evidence=retry_evidence(
            phase=phase,
            kind=TRANSIENT_TRANSPORT,
            status=STATUS_TRANSIENT_TRANSPORT,
            http_status=0,
            parsed={},
            text=excerpt,
            poll_index=None,
            retried=False,
            not_retried_because=REFUSED_SINGLE_SHOT,
        )
    )
    why = _P8_NO_RETRY_REASON.get(
        phase, "it is a single-shot call with no safe second attempt"
    )
    if phase == "quote":
        run.error(
            f"TRANSPORT STOP ({phase}) — {excerpt}. No answer arrived, so this "
            f"trial produced no coexistence sample. It was not retried because "
            f"{why}. No order was placed, so nothing is resting and the series "
            "may continue."
        )
        return f"{_P8_STOP_TRANSIENT}:{TRANSIENT_TRANSPORT}"
    run.error(
        f"ORDER STATE UNKNOWN ({phase}) — {excerpt}. No answer arrived, so "
        f"this probe does NOT know whether the broker accepted the {phase}. "
        f"It was not retried because {why}. The book is walked below and "
        "anything live that this trial cannot account for is cancelled; the "
        "series stops either way, because placing another order on top of an "
        "order whose state is unknown is the one thing this harness must not "
        "do."
    )
    return _P8_STOP_ORDER_STATE_UNKNOWN


_P8_STOP_NARRATION: dict[str, str] = {
    _P8_STOP_TRANSIENT: (
        "This is NOT a broker rejection: the submit and the amend were both "
        "answered, and the series stop condition is a refused order. See the "
        "retry_evidence observations for the broker's verbatim response."
    ),
    _P8_STOP_RATE_LIMITED: (
        "The stop is our own call rate (HTTP 429 / EGW00201), which stays a "
        "no-retry stop and does end the series. See the "
        "coexistence_poll_rate_limited observation for the broker's verbatim "
        "response."
    ),
    _P8_STOP_QUERY_UNANSWERED: (
        "The broker refused no order and our call rate was not the problem: "
        "the open-order surface answered rt_cd!=0 to every poll. See the "
        "coexistence_poll_not_answered observations and "
        "coexistence_not_answered_codes."
    ),
}


def _window_note(elapsed: bool, window_s: float) -> str:
    """What to say about the window, from the FACT and not from the stop."""
    if elapsed:
        return (
            f"--visibility-timeout-s={window_s}s DID elapse — the window was "
            "spent in full."
        )
    return (
        f"Polling stopped early, so --visibility-timeout-s={window_s}s did "
        "NOT elapse."
    )


def _classify_order_answer(
    run: ProbeRun, phase: str, status: int, parsed: dict[str, Any], text: str
) -> str | None:
    """A ``P8_STOP`` token when the order POST's ANSWER ends the trial, else"""
    kind = classify_answer(status, parsed, text)
    if kind is None:
        return None
    evidence = call_evidence(
        status_kind=kind, http_status=status, parsed=parsed, text=text
    )
    run.observe(order_call_refused=evidence, phase=phase)
    if kind == STATUS_RATE_LIMITED:
        run.error(
            f"RATE LIMITED on the {phase} (HTTP 429 / EGW00201) — that is OUR "
            "call rate, not a broker rejection of this order, and it stays a "
            "no-retry stop. See the order_call_refused observation."
        )
        return _P8_STOP_RATE_LIMITED
    run.error(
        f"LEDGER THROTTLE on the {phase} (EGW00215) — the broker answered, "
        "but this is the one surface where being wrong about acceptance "
        "leaves a live order, so the book is walked before stopping. See the "
        "order_call_refused observation."
    )
    return _P8_STOP_ORDER_STATE_UNKNOWN


def _poll_coexistence(
    run: ProbeRun,
    client: MockTradingClient,
    args: argparse.Namespace,
    *,
    original_odno: str,
    original_key: str,
    new_odno: str,
    retries: Retries,
) -> tuple[float | None, str | None, int, bool]:
    """Poll the open-order surface for as long as both legs are live."""
    coexist_last: float | None = None
    answered = 0
    unanswered = 0
    not_answered_codes: dict[str, int] = {}
    recorded_codes: set[str] = set()
    deadline = time.monotonic() + args.visibility_timeout_s
    retry_wait_s = effective_interval_ms(args.poll_ms, args) / 1000.0
    on_transient = record_retry(run, retries)
    polls = 0

    def _call() -> Outcome:
        return client.inquire_futures_classified(args.symbol)

    def _window_still_open() -> bool:
        return bool(time.monotonic() < deadline)

    try:
        while time.monotonic() < deadline:
            outcome, attempts, _retried = retry_once(
                _call,
                on_transient,
                client.pacer,
                wait_s=retry_wait_s,
                phase="coexistence_poll",
                poll_index_base=polls,
                can_retry=_window_still_open,
            )
            polls += attempts
            kind = transient_kind(outcome.kind)
            if kind is not None:
                if attempts == 1:
                    break
                return (
                    coexist_last,
                    f"{_P8_STOP_TRANSIENT}:{kind}",
                    answered,
                    not _window_still_open(),
                )
            if outcome.kind == STATUS_RATE_LIMITED:
                run.observe(
                    coexistence_poll_rate_limited=call_evidence(
                        status_kind=outcome.kind,
                        http_status=outcome.http_status,
                        parsed=outcome.parsed,
                        text=outcome.text,
                    ),
                    poll_index=polls,
                )
                return (
                    coexist_last,
                    _P8_STOP_RATE_LIMITED,
                    answered,
                    not _window_still_open(),
                )
            if rt_cd_of(outcome.parsed) != "0":
                unanswered += 1
                code = str(outcome.parsed.get("msg_cd") or "").strip() or "<no msg_cd>"
                not_answered_codes[code] = not_answered_codes.get(code, 0) + 1
                if code not in recorded_codes:
                    recorded_codes.add(code)
                    run.observe(
                        coexistence_poll_not_answered=call_evidence(
                            status_kind="QUERY_REJECTED",
                            http_status=outcome.http_status,
                            parsed=outcome.parsed,
                            text=outcome.text,
                        ),
                        poll_index=polls,
                        reading="first poll with this msg_cd; later ones are "
                        "counted in coexistence_not_answered_codes",
                    )
                time.sleep(args.poll_ms / 1000.0)
                continue
            answered += 1
            rows = outcome.payload
            record_odno_wire_format(run, [original_odno, new_odno], rows)
            live = {
                odno_key(r.get("odno"))
                for r in rows
                if int(float(r.get("qty") or 0)) > 0
            }
            both = (
                original_key in live and bool(new_odno) and odno_key(new_odno) in live
            )
            if both:
                coexist_last = time.monotonic()
            elif coexist_last is not None:
                break
            time.sleep(args.poll_ms / 1000.0)
    finally:
        run.measure("coexistence_polls_used", polls)
        run.measure("coexistence_polls_answered", answered)
        run.measure("coexistence_polls_not_answered", unanswered)
        if not_answered_codes:
            run.measure("coexistence_not_answered_codes", dict(not_answered_codes))
    if answered == 0 and unanswered > 0:
        if set(not_answered_codes) <= {_EMPTY_BOOK_MSG_CD}:
            return coexist_last, None, answered, True
        return coexist_last, _P8_STOP_QUERY_UNANSWERED, answered, True
    return coexist_last, None, answered, not _window_still_open()


def _original_not_cancellable(
    odnos: list[str],
    dispositions: dict[str, str],
    *,
    amend_accepted: bool,
    new_odno: str,
) -> bool | None:
    """Was the original order un-cancellable after the amend, on verified evidence?"""
    if not amend_accepted or not new_odno or len(odnos) < 2:
        return None
    disposition = dispositions.get(odnos[0])
    if disposition == _CLEANUP_NOTHING_TO_CANCEL:
        return True
    if disposition == _CLEANUP_CANCELLED:
        return False
    return None


def probe_p8(args: argparse.Namespace) -> ProbeRun:
    """P-8 REPLACE_OR_AMEND — ``RVSE_CNCL_DVSN_CD='01'`` semantics."""
    spec = get("P-8")
    _require_symbol(args)
    run, client = _setup(spec, args)
    if client is None:
        run.observe(
            would_send="submit -> RVSE_CNCL_DVSN_CD=01 amend -> poll both ODNOs"
        )
        _print_p8_verdict(_P8_STOP_DRY_RUN, False)
        return run
    retries = Retries(run)
    odnos: list[str] = []
    amend_accepted = False
    new_odno_seen = ""
    stop = _P8_STOP_UNKNOWN
    measured = False
    resting_price: TickPrice | None = None
    try:
        try:
            price, side = _resting_price(client, args)
        except transport_transient_types() as exc:
            stop = _record_write_transport_stop(run, "quote", exc)
            return run
        resting_price = price
        try:
            body = client.futures_order_body(args.symbol, args.quantity, price, side)
            placed, submit_status, raw, submit_text, _ms = (
                client.submit_futures_verbose(body)
            )
        except transport_transient_types() as exc:
            stop = _record_write_transport_stop(run, "submit", exc)
            return run
        refused = _classify_order_answer(run, "submit", submit_status, raw, submit_text)
        if refused is not None:
            stop = refused
            return run
        if placed is None:
            stop = _P8_STOP_REJECTED
            run.error(f"submit rejected rt_cd={raw.get('rt_cd')} msg={raw.get('msg1')}")
            return run
        odnos.append(placed.odno)
        new_price = snap_to_tick(
            price.value * 0.99, price.tick, side=side, marketable=False
        )
        try:
            amend_status, amend, amend_text = client.replace_futures_verbose(
                placed.odno, args.quantity, new_price
            )
            amended_at = client.last_send_instant()
        except transport_transient_types() as exc:
            stop = _record_write_transport_stop(run, "amend", exc)
            return run
        refused = _classify_order_answer(run, "amend", amend_status, amend, amend_text)
        if refused is not None:
            stop = refused
            return run
        new_odno = str((amend.get("output") or {}).get("ODNO") or "").strip()
        amend_accepted = amend.get("rt_cd") == "0"
        new_odno_seen = new_odno
        run.observe(
            original_odno=placed.odno,
            amend_rt_cd=amend.get("rt_cd"),
            amend_msg=amend.get("msg1"),
            new_odno=new_odno,
            new_price=new_price.wire,
        )
        run.measure("limit_price_tick", price.describe())
        run.measure("amend_price_tick", new_price.describe())
        if new_odno:
            odnos.append(new_odno)
        run.measure("replace_issues_new_odno", bool(new_odno))
        run.measure("replace_rejected", amend.get("rt_cd") != "0")

        coexist_last, poll_stop, answered, window_elapsed = _poll_coexistence(
            run,
            client,
            args,
            original_odno=placed.odno,
            original_key=placed.key,
            new_odno=new_odno,
            retries=retries,
        )
        if poll_stop is not None:
            stop = poll_stop
            if coexist_last is not None:
                run.observe(
                    coexistence_seen_before_stop=True,
                    reading="both legs were live on at least one poll before the "
                    "loop stopped; the interval was never bounded, so no "
                    "coexistence_ms is reported",
                )
            detail = _P8_STOP_NARRATION[stop.split(":", 1)[0]]
            run.error(
                f"POLLING STOPPED (stop_reason={stop}) — no coexistence "
                f"sample. {detail}"
            )
            run.skip(
                "measurements.coexistence_ms",
                f"ABORTED — the coexistence poll produced no usable sample "
                f"(stop_reason={stop}) after "
                f"{run.measurements.get('coexistence_polls_used')} poll "
                f"attempt(s), of which {answered} answered. "
                f"{_window_note(window_elapsed, args.visibility_timeout_s)} "
                "Nothing is asserted about the replace interval: an unobserved "
                "interval is not a zero one (VP-002:772 'observed 0 != 0').",
            )
            return run

        stop = _P8_STOP_NONE
        nothing_observed = []
        if not amend_accepted:
            nothing_observed.append(
                "the broker REJECTED the amend (replace_rejected=True), so no "
                "replace happened and there is no interval to measure"
            )
        if not new_odno:
            nothing_observed.append(
                "no new ODNO was issued, so the second leg the measurement "
                "compares against never existed"
            )
        if answered == 0:
            nothing_observed.append(
                "not one poll came back rt_cd=0, so the surface was never "
                "actually read"
            )
        if nothing_observed:
            measured = False
            run.skip(
                "measurements.coexistence_ms",
                "NOT OBSERVED — the poll loop ran to its end but measured "
                "nothing: " + "; ".join(nothing_observed) + ". "
                f"{_window_note(window_elapsed, args.visibility_timeout_s)} "
                "Absence of an observed interval is not an interval of zero "
                "(VP-002:772 'observed 0 != 0'), so this trial contributes "
                "nothing to the N>=5 that mode_determination needs.",
            )
            return run

        measured = True
        run.measure(
            "coexistence_ms",
            round((coexist_last - amended_at) * 1000.0, 2) if coexist_last else 0.0,
        )
        run.measure("poll_granularity_ms", effective_interval_ms(args.poll_ms, args))
        run.measure("liveness_predicate_note", _P8_COEXISTENCE_LIVENESS_NOTE)
        run.measure(
            "mode_determination",
            "Map to ReplaceSemantics only after N>=5 trials agree. A single trial "
            "showing zero coexistence does NOT prove atomicity — polling can miss "
            "an interval shorter than poll_granularity_ms, which is the EFFECTIVE "
            "interval max(--poll-ms, --pace-s) and not the requested --poll-ms. "
            "Count only trials that carry coexistence_ms: a trial whose "
            "stop_reason is not 'none' observed an unknown part of the interval "
            "and contributes nothing, in either direction.",
        )
    finally:
        dispositions = _cleanup(
            client,
            run,
            odnos,
            args.quantity,
            symbol=args.symbol,
            max_pages=args.max_pages,
            retries=retries,
        )
        if stop == _P8_STOP_ORDER_STATE_UNKNOWN and resting_price is not None:
            known = set()
            for odno in odnos:
                try:
                    known.add(odno_key(odno))
                except ProbeError:  # pragma: no cover - odnos come from the wire
                    continue
            _cleanup_unaccounted(
                client,
                run,
                symbol=args.symbol,
                qty=args.quantity,
                price=resting_price,
                max_pages=args.max_pages,
                known=known,
                may_cancel=bool(getattr(args, "cancel_unaccounted", False)),
                retries=retries,
            )
        if dispositions:
            run.measure("cleanup_dispositions", dispositions)
            run.measure(
                "original_not_cancellable_after_amend",
                _original_not_cancellable(
                    odnos,
                    dispositions,
                    amend_accepted=amend_accepted,
                    new_odno=new_odno_seen,
                ),
            )
            run.measure("amend_consumption_note", _P8_CONSUMPTION_NOTE)
        run.measure("stop_reason", stop)
        _print_p8_verdict(stop, measured and not run.errors)
        client.close()
    return run


_FILL_OBSERVED = "FILLED_AND_REFLECTED"
_FILL_NOT_REFLECTED = "FILLED_BUT_BALANCE_NOT_REFLECTED_IN_WINDOW"
_FILL_NOT_FILLED = "NOT_FILLED_NOTHING_TO_MEASURE"
_FILL_UNDETERMINED = "UNDETERMINED_FILL_EVIDENCE_UNAVAILABLE"

_FILL_EVIDENCE_SOURCE = (
    "주식일별주문체결조회 — /uapi/domestic-stock/v1/trading/inquire-daily-ccld, "
    "[v1_국내주식-005], mock VTTC0081R (real TTTC0081R), read-only GET, one page in "
    "역순 (INQR_DVSN=00) with CCLD_DVSN=00 (전체) so an unfilled order still appears. "
    "The fill facts are the row's tot_ccld_qty (총체결수량), rmn_qty (잔여수량) and "
    "cncl_yn (취소여부), recorded verbatim. ord_tmd is 주문시각 (order time) per the "
    "official COLUMN_MAPPING — NOT a fill timestamp — and it is HHMMSS, 1-second "
    "resolution, so no sub-second lag may be derived from it; it is kept for time "
    "context only."
)

_CCLD_ROW_FIELDS: tuple[str, ...] = (
    "ord_dt",
    "odno",
    "orgn_odno",
    "ord_dvsn_name",
    "sll_buy_dvsn_cd",
    "pdno",
    "ord_qty",
    "ord_unpr",
    "ord_tmd",
    "tot_ccld_qty",
    "tot_ccld_amt",
    "avg_prvs",
    "rmn_qty",
    "cncl_yn",
    "rjct_qty",
)


def _ccld_int(row: dict[str, Any], field: str) -> int | None:
    """One 수량 field of a ccld row as an int, or ``None`` if it is not one."""
    raw = row.get(field)
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(str(raw).strip()))
    except ValueError:
        return None


def _ccld_row_key(row: dict[str, Any]) -> str | None:
    """A ccld row's ODNO as a canonical key, or ``None`` when it is not numeric."""
    try:
        return odno_key(row.get("odno"))
    except ProbeError:
        return None


def _fill_evidence(client: MockTradingClient, symbol: str, odno: str) -> dict[str, Any]:
    """Ask the execution inquiry whether ``odno`` filled. Never raises."""
    record: dict[str, Any] = {
        "source": _FILL_EVIDENCE_SOURCE,
        "queried_symbol": symbol,
        "queried_odno": odno,
    }
    try:
        key = odno_key(odno)
    except ProbeError as exc:
        return record | {
            "filled": None,
            "available": False,
            "missing": f"the submitted ODNO is not a comparable order number: {exc}",
        }
    record["queried_odno_key"] = key
    try:
        parsed = client.stock_daily_ccld(symbol)
    except Exception as exc:  # noqa: BLE001 - an inquiry failure must not mask results
        return record | {
            "filled": None,
            "available": False,
            "missing": (
                "the execution inquiry did not complete: "
                f"{type(exc).__name__}: {exc}"
            ),
        }
    rows = parsed.get("output1") if isinstance(parsed.get("output1"), list) else []
    record["rt_cd"] = parsed.get("rt_cd")
    record["msg1"] = parsed.get("msg1")
    record["rows_returned"] = len(rows)
    record["row_cap_note"] = (
        "모의 serves at most 15 rows per call and this probe reads ONE page in 역순, "
        "so a seconds-old order is on it. rows_returned is recorded so a truncated "
        "page stays visible instead of being read as a non-fill."
    )
    if parsed.get("rt_cd") != "0":
        return record | {
            "filled": None,
            "available": False,
            "missing": (
                f"the execution inquiry was refused: rt_cd={parsed.get('rt_cd')!r} "
                f"msg1={parsed.get('msg1')!r}"
            ),
        }
    matched = [r for r in rows if _ccld_row_key(r) == key]
    record["matched_rows"] = len(matched)
    if not matched:
        return record | {
            "filled": None,
            "available": False,
            "missing": (
                f"no row for ODNO {key} on the returned page "
                f"({len(rows)} row(s) for {symbol}). An accepted order should appear "
                "here whether or not it filled (CCLD_DVSN=00), so an absent row is "
                "NOT evidence of a non-fill — it is an unanswered question."
            ),
        }
    row = matched[0]
    record["row"] = {f: row.get(f) for f in _CCLD_ROW_FIELDS if f in row}
    record["row_odno_encoding"] = _odno_encoding(str(row.get("odno", "")))
    filled_qty = _ccld_int(row, "tot_ccld_qty")
    record["filled_qty"] = filled_qty
    record["remaining_qty"] = _ccld_int(row, "rmn_qty")
    record["cancelled"] = row.get("cncl_yn")
    if len(matched) > 1:
        record["multiple_rows_note"] = (
            f"{len(matched)} rows carried this ODNO; the first (역순 = newest) was "
            "used and the others are visible in rows_returned. One submitted order "
            "should yield one row, so this is recorded rather than smoothed over."
        )
    if filled_qty is None:
        return record | {
            "filled": None,
            "available": True,
            "missing": (
                "the row was found but its tot_ccld_qty is "
                f"{row.get('tot_ccld_qty')!r} — not a quantity, so whether the order "
                "filled is unanswered rather than answered 'no'."
            ),
        }
    return record | {"filled": filled_qty > 0, "available": True}


def _stock_holding_qty(rows: list[dict[str, Any]], symbol: str) -> int:
    """Total 보유수량 for ``symbol`` across the balance rows."""
    return sum(
        int(float(r.get("hldg_qty") or 0))
        for r in rows
        if str(r.get("pdno", "")).strip() == symbol
    )


def _market_price_record() -> dict[str, Any]:
    """The ``limit_price_tick`` slot for a 시장가 run: an explicit bypass, not a gap."""
    return {
        "applicable": False,
        "wire_value": _STOCK_ORD_UNPR_MARKET,
        "unrounded": None,
        "tick_size": None,
        "tick_source": (
            "NOT APPLICABLE — this run sent a 시장가 order "
            f"(ORD_DVSN={_STOCK_ORD_DVSN['market']}), which carries no limit price. "
            "No 호가단위 was requested and none was used: the inquire-price quote "
            "call was skipped entirely, so nothing here came from a tick table."
        ),
        "rounding": None,
        "rounding_rationale": (
            "no snapping was attempted — there is no price to snap. Bypassing the "
            "tick machinery also removes its failure mode: a 시장가 order cannot be "
            "rejected with 호가단위 오류, and a broker that does not report "
            f"output.{_STOCK_QUOTE_UNIT_FIELD} can no longer block this probe."
        ),
    }


def _fill_case_record(
    *,
    reflected: bool,
    fill: dict[str, Any],
    symbol: str,
    baseline_qty: int,
    observed_qty: int,
    window_s: float,
    polls: int,
    poll_interval_ms: float,
    lag_ms: float | None,
) -> dict[str, Any]:
    """State which of the FOUR cases the run represents, from both sources."""
    filled = fill.get("filled")
    common: dict[str, Any] = {
        "symbol": symbol,
        "baseline_holding_qty": baseline_qty,
        "final_holding_qty": observed_qty,
        "balance_reflected": reflected,
        "window_s": window_s,
        "polls": polls,
        "poll_interval_ms_effective": poll_interval_ms,
        "execution_inquiry": fill,
        "basis": (
            "TWO independent sources. Fill: the execution inquiry above. Balance "
            "reflection: inquire-balance (VTTC8434R) holdings for this symbol, "
            "baseline read BEFORE the submit. Neither alone can separate a non-fill "
            "from a reflection lag."
        ),
    }
    if filled is None:
        record = common | {
            "case": _FILL_UNDETERMINED,
            "missing": fill.get("missing"),
            "interpretation": (
                "the execution inquiry produced no usable answer, so this run "
                "CANNOT tell whether (a) the order never filled, or (b) it filled "
                f"and the {symbol} balance did or did not reflect it inside the "
                f"{window_s}s window. No bound may be derived under any reading. "
                f"What is missing: {fill.get('missing')}"
            ),
        }
        if reflected and lag_ms is not None:
            record |= {
                "balance_rise_unattributed_ms": round(lag_ms, 3),
                "balance_rise_note": (
                    f"the {symbol} holding DID rise {baseline_qty} -> {observed_qty} "
                    "inside the window, but with no execution-inquiry confirmation "
                    "the rise cannot be attributed to this probe's own fill — "
                    "external activity on the same symbol would look identical "
                    "(that is what P-EXT exists to detect). Recorded as an "
                    "unattributed observation and deliberately NOT as "
                    "submit_to_balance_reflection; no bound may be derived from it."
                ),
            }
        return record
    if not filled:
        return common | {
            "case": _FILL_NOT_FILLED,
            "interpretation": (
                "the execution inquiry reports the order did NOT fill "
                f"(tot_ccld_qty={fill.get('filled_qty')}, "
                f"rmn_qty={fill.get('remaining_qty')}, "
                f"cncl_yn={fill.get('cancelled')!r}). There was no fill for the "
                "balance to reflect, so this run measures nothing — an ABSENT "
                "measurement, not a censored one. Widening --balance-timeout-s "
                "would change nothing: nothing was pending."
            ),
        }
    if reflected:
        return common | {
            "case": _FILL_OBSERVED,
            "interpretation": (
                "the execution inquiry reports the order FILLED "
                f"(tot_ccld_qty={fill.get('filled_qty')}, "
                f"rmn_qty={fill.get('remaining_qty')}) and the {symbol} holding rose "
                f"{baseline_qty} -> {observed_qty} inside the {window_s}s window, so "
                "submit_to_balance_reflection is a real reflection sample. Read it "
                "with resolution_floor: a reflection seen on the first poll is an "
                "UPPER bound, not a point value."
            ),
        }
    return common | {
        "case": _FILL_NOT_REFLECTED,
        "interpretation": (
            "the execution inquiry reports the order FILLED "
            f"(tot_ccld_qty={fill.get('filled_qty')}, "
            f"rmn_qty={fill.get('remaining_qty')}, "
            f"ord_tmd={(fill.get('row') or {}).get('ord_tmd')!r}) but the {symbol} "
            f"holding stayed at {baseline_qty} for the whole {window_s}s window. "
            "This is the honest negative: a fill that demonstrably happened was not "
            "reflected in this balance surface inside the window — either the "
            "reflection lag exceeds the window, or this query does not reflect it at "
            "all. submit_to_balance_ms stays null, because a reflection that was "
            "never observed is not a measurement. If baseline_holding_qty already "
            "equals final_holding_qty here, check that the baseline was read BEFORE "
            "the submit (it is, since P-11-20260731T015709Z) — a baseline read after "
            "a 시장가 fill already contains it, and then no window can ever be long "
            "enough."
        ),
    }


def _resolution_floor_record(
    *, poll_interval_ms: float, reflected_on_poll: int | None, lag_ms: float | None
) -> dict[str, Any]:
    """What the smallest lag this probe can resolve is, and what that costs."""
    first_poll = reflected_on_poll == 1
    record: dict[str, Any] = {
        "poll_interval_ms_effective": poll_interval_ms,
        "smallest_resolvable_lag_ms": poll_interval_ms,
        "floor_source": (
            "the poll interval is max(--poll-ms, --pace-s x 1000) — the pacer will "
            "not release two calls closer together, so a smaller --poll-ms did not "
            "happen (§5.3.1). Lowering --pace-s to sharpen this re-opens the "
            "throttling failure that voided P-5-20260729T235001Z."
        ),
        "reflected_on_poll": reflected_on_poll,
        "sample_is_upper_bound": True,
        "statement": (
            "Every polled sample here is an UPPER bound on the true reflection lag: "
            "the reflection happened somewhere inside the interval that ended when "
            "the poll saw it. P-11 therefore cannot report a reflection faster than "
            f"{poll_interval_ms} ms as a value — only as '<= {poll_interval_ms} ms'."
        ),
    }
    if first_poll:
        record |= {
            "first_poll_reflection": True,
            "upper_bound_only_ms": round(lag_ms, 3) if lag_ms is not None else None,
            "do_not_report_as_measured": (
                "the reflection was already visible on the FIRST poll, so the "
                f"recorded submit_to_balance_ms (~{poll_interval_ms} ms) is this "
                "probe's DETECTION FLOOR, not the broker's lag. The true lag lies in "
                f"[0, {poll_interval_ms}] ms. Report 'reflection <= one effective "
                "poll interval'; do NOT feed the number to a hard_maximum bound as a "
                "measured lag, and do not widen a bound to accommodate it."
            ),
        }
    elif reflected_on_poll is not None:
        record["bracket_ms"] = [
            round(max(0.0, (reflected_on_poll - 1) * poll_interval_ms), 3),
            round(reflected_on_poll * poll_interval_ms, 3),
        ]
    return record


def _p11_dry_run(run: ProbeRun, args: argparse.Namespace, order_type: str) -> None:
    """Report the request P-11 would send, without contacting the broker."""
    plan = (
        f"read the inquire-balance baseline FIRST, then a stock {order_type} order "
        f"(ORD_DVSN={_STOCK_ORD_DVSN[order_type]}), then poll inquire-balance every "
        f"{effective_interval_ms(args.poll_ms, args)}ms for up to "
        f"{args.balance_timeout_s}s, then ONE read-only 주식일별주문체결조회 "
        f"({_STOCK_DAILY_CCLD_TR_MOCK}) to confirm whether the order filled"
    )
    if order_type != "market":
        run.observe(would_send=plan, order_type=order_type, order_body=None)
        print(
            f"\n  would send: {plan}\n"
            "  body not shown — a 지정가 price is derived from a live quote."
        )
        return
    creds = resolve_credentials(args.asset, is_real=False)
    body = build_stock_order_body(
        creds.cano, creds.acnt_prdt_cd, args.symbol, args.quantity, order_type="market"
    )
    run.observe(would_send=plan, order_type=order_type, order_body=body)
    print(f"\n  would send POST {_STOCK_ORDER_PATH}")
    print(f"  {json.dumps(redact(body), ensure_ascii=False)}")


def probe_p11(args: argparse.Namespace) -> ProbeRun:
    """P-11 POSITIONS_BALANCES_MARGIN — fill to balance-reflection lag."""
    spec = get("P-11")
    _require_symbol(args)
    order_type = args.stock_order_type
    if order_type not in _STOCK_ORD_DVSN:
        raise ProbeError(
            f"unknown --stock-order-type {order_type!r} "
            f"(expected one of {sorted(_STOCK_ORD_DVSN)})"
        )
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
        _p11_dry_run(run, args, order_type)
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
        if order_type == "market":
            body = client.stock_order_body(
                args.symbol, args.quantity, order_type="market"
            )
            run.observe(order_body=body, order_type=order_type)
            run.measure("limit_price_tick", _market_price_record())
        else:
            last, tick = client.stock_quote(args.symbol)
            price = snap_to_tick(
                last * (1.0 + args.price_offset_pct / 100.0),
                tick,
                side="BUY",
                marketable=True,
            )
            body = client.stock_order_body(
                args.symbol, args.quantity, price, order_type="limit"
            )
            run.observe(
                order_body=body,
                order_type=order_type,
                last_price=last,
                marketable_price=price.wire,
            )
            run.measure("limit_price_tick", price.describe())
        baseline = client.stock_balance()
        base_rows = (
            baseline.get("output1") if isinstance(baseline.get("output1"), list) else []
        )
        base_qty = _stock_holding_qty(base_rows, args.symbol)
        run.observe(baseline_holding_qty=base_qty, baseline_read="before submit")

        tr_id = client.tr_ids["stock_krx_buy_mock"]
        status, parsed, _ms, _text = client.trading_call(
            "POST", _STOCK_ORDER_PATH, tr_id, body=body
        )
        sent = client.last_send_instant()
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

        reflected_at: float | None = None
        reflected_on_poll: int | None = None
        polls = 0
        final_qty = base_qty
        deadline = time.monotonic() + args.balance_timeout_s
        while time.monotonic() < deadline:
            polls += 1
            snapshot = client.stock_balance()
            rows = (
                snapshot.get("output1")
                if isinstance(snapshot.get("output1"), list)
                else []
            )
            final_qty = _stock_holding_qty(rows, args.symbol)
            if final_qty > base_qty:
                reflected_at = time.monotonic()
                reflected_on_poll = polls
                break
            time.sleep(args.poll_ms / 1000.0)

        lag_ms = None if reflected_at is None else (reflected_at - sent) * 1000.0
        poll_interval_ms = effective_interval_ms(args.poll_ms, args)
        fill = _fill_evidence(client, args.symbol, odno)
        run.measure(
            "fill_case",
            _fill_case_record(
                reflected=reflected_at is not None,
                fill=fill,
                symbol=args.symbol,
                baseline_qty=base_qty,
                observed_qty=final_qty,
                window_s=args.balance_timeout_s,
                polls=polls,
                poll_interval_ms=poll_interval_ms,
                lag_ms=lag_ms,
            ),
        )
        run.measure(
            "resolution_floor",
            _resolution_floor_record(
                poll_interval_ms=poll_interval_ms,
                reflected_on_poll=reflected_on_poll,
                lag_ms=lag_ms,
            ),
        )
        case = run.measurements["fill_case"]["case"]
        if case == _FILL_NOT_REFLECTED:
            run.error(
                "balance never reflected the order within the timeout — CENSORED. "
                "Do not record a bound from a censored trial."
            )
        elif case == _FILL_NOT_FILLED:
            run.error(
                "the order did not fill (execution inquiry: "
                f"tot_ccld_qty={fill.get('filled_qty')}, "
                f"rmn_qty={fill.get('remaining_qty')}) — there was no fill for the "
                "balance to reflect, so this run yields no sample. This is an ABSENT "
                "measurement, not a censored one: do not widen --balance-timeout-s."
            )
        elif case == _FILL_UNDETERMINED:
            run.error(
                "the execution inquiry could not establish whether the order filled "
                f"({fill.get('missing')}) — UNDETERMINED. Do not record a bound from "
                "an unconfirmed trial."
            )
        elif lag_ms is not None:
            run.measure(
                "submit_to_balance_reflection",
                summarize_latencies(
                    [lag_ms], margin_pct=args.margin_pct, label="submit_to_balance_ms"
                )
                | {
                    "value_semantics": (
                        "UPPER BOUND on the reflection lag, not a point value — the "
                        "reflection happened somewhere inside the poll interval that "
                        "ended when it was seen. See resolution_floor; a first-poll "
                        "reflection carries no lower-bound information at all."
                    ),
                    "fill_confirmed_by": _FILL_EVIDENCE_SOURCE,
                },
            )
            run.measure(
                "n_note",
                "n=1 per invocation. Re-run --samples times and take the maximum "
                "across artifacts before proposing a bound.",
            )
            run.measure("poll_granularity_ms", poll_interval_ms)
            run.measure(
                "granularity_note",
                "The sample carries up to one poll interval of additive error, so "
                "an approved bound must exceed it plus poll_granularity_ms — which "
                "is the EFFECTIVE interval max(--poll-ms, --pace-s), because the "
                "pacer floors polling and a smaller --poll-ms did not happen "
                "(runbook §8.3). When the reflection landed on the first poll the "
                "sample IS that granularity and bounds nothing below it — read "
                "resolution_floor before proposing any value.",
            )
        run.measure(
            "position_left_open",
            f"symbol={args.symbol} qty={args.quantity} — the probe does NOT flatten "
            "the position. Close it manually on 모의투자.",
        )
    finally:
        client.close()
    return run


def probe_pext(args: argparse.Namespace) -> ProbeRun:
    """P-EXT external_activity — detection latency for an order we did not send."""
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
        known = {odno_key(r.get("odno")) for r in rows}
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
            new = {odno_key(r.get("odno")) for r in rows} - known
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
        run.measure("poll_interval_ms", effective_interval_ms(args.poll_ms, args))
        run.measure("polls_used", polls)
        run.measure(
            "human_timestamp_error",
            "The t0 comes from a human keypress; assume +/- several hundred ms and "
            "fold it into the margin. Repeat >= 5 trials.",
        )
        run.measure(
            "push_absence_note",
            "Detection is poll-bounded: no account-event push subscription exists "
            "(draft §3.1 row 10). The bound cannot go below poll_interval_ms, which "
            "is the EFFECTIVE interval max(--poll-ms, --pace-s) — with pacing active "
            "the pacer, not --poll-ms, is what sets the floor.",
        )
    finally:
        client.close()
    return run


def probe_pfqp(args: argparse.Namespace) -> ProbeRun:
    """P-FQP final_quantity_proof — post-cancel late-event observation window."""
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
        run.measure("limit_price_tick", price.describe())
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
            record_odno_wire_format(run, [placed.odno], rows)
            row = next((r for r in rows if odno_key(r.get("odno")) == placed.key), None)
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
        run.measure("poll_granularity_ms", effective_interval_ms(args.poll_ms, args))
        run.measure(
            "granularity_note",
            "Both candidates are polled observations and so carry up to one "
            "poll_granularity_ms of additive error (runbook §8.3). That value is the "
            "EFFECTIVE interval max(--poll-ms, --pace-s), not the requested "
            "--poll-ms: the pacer floors polling, and it also bounds how finely a "
            "post-terminal change can be located in time.",
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
        _cleanup(client, run, odnos, args.quantity, symbol=args.symbol)
        client.close()
    return run


def probe_nmpr_ab(args: argparse.Namespace) -> ProbeRun:
    """P-NMPR — does a blank [필수] quote field mean the same as ``01``/``0``?"""
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
            resting_price=price.wire,
            side=side,
        )
        run.measure("limit_price_tick", price.describe())
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
        record_odno_wire_format(
            run, [p.odno for p in (placed_a, placed_b) if p is not None], rows
        )
        by_odno = {odno_key(r.get("odno")): r for r in rows}
        row_a = by_odno.get(placed_a.key) if placed_a else None
        row_b = by_odno.get(placed_b.key) if placed_b else None
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
        _cleanup(client, run, odnos, args.quantity, symbol=args.symbol)
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
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=(
            f"Minimum interval between ANY two broker calls (default {DEFAULT_PACE_S}s) "
            "— quote, submit, cancel and inquire alike. The default is measured, not "
            "chosen: P-13 bracketed this mock account's query class at clean 1.0 rps / "
            "throttled 2.0 rps (EGW00201, artifact P-13-20260729T063120Z), so "
            f"{DEFAULT_PACE_S}s sits just above the measured clean rate. A --poll-ms or "
            "--gap-ms below this interval is floored to it and the probe records the "
            "floored value. Lowering it re-opens the throttling failure that produced "
            "P-5-20260729T235001Z (n=0, NOT_MEASURED)."
        ),
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
        "--cancel-unaccounted",
        action="store_true",
        help=(
            "P-8 only: after a lost submit or amend, CANCEL live rows that "
            "match this trial's order body but that the probe never saw "
            "placed. Off by default: the 모의 account is shared by the whole "
            "campaign, so a row the probe cannot account for may belong to "
            "another probe or to the operator, and cancelling it destroys "
            "that measurement. Without this flag such rows are recorded in "
            "measurements.unaccounted_live_orders as FOUND_NOT_CANCELLED and "
            "the series stops so a human can look. Rows that do NOT match the "
            "order body are never cancelled, flag or no flag."
        ),
    )
    parser.add_argument(
        "--allow-fill",
        action="store_true",
        help="P-11 only: authorise a marketable order that is expected to FILL.",
    )
    parser.add_argument(
        "--stock-order-type",
        choices=tuple(_STOCK_ORD_DVSN),
        default="market",
        help=(
            "P-11 only: 주문구분 for the fill order. Default 'market' "
            f"(ORD_DVSN={_STOCK_ORD_DVSN['market']}, 시장가) because a marketable "
            "LIMIT did not fill on 모의투자 — artifact P-11-20260730T002715Z was "
            "accepted at a correctly tick-snapped price 10% above the touch and the "
            "holding never moved, censoring the measurement. 'limit' "
            f"(ORD_DVSN={_STOCK_ORD_DVSN['limit']}, 지정가) restores that shape for "
            "comparison and is the only mode that uses --price-offset-pct or needs "
            "a broker-reported 호가단위."
        ),
    )
    parser.add_argument(
        "--balance-timeout-s",
        type=float,
        default=120.0,
        help=(
            "P-11 only: how long to poll inquire-balance for the fill to appear. "
            "Separate from --visibility-timeout-s because that default (30s) is "
            "shared with probes that poll a cheap order listing, while the pacer "
            "floors polling at --pace-s — 30s is only ~27 balance polls, short "
            "enough to censor a slow-but-real update. Expiry stays CENSORED; it is "
            "never converted into a measurement."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
