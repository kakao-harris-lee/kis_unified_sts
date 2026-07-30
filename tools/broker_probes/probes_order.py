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
  fill and demands an extra ``--allow-fill`` flag. It is also the one probe that
  defaults to a 시장가 (market) order — a marketable *limit* was accepted and then
  never filled on 모의투자 (``P-11-20260730T002715Z.json``), which censored the
  measurement it exists to take. ``--stock-order-type limit`` restores the old
  shape for comparison.
* Every limit price is snapped to a valid tick before it goes on the wire — see
  :func:`snap_to_tick`. An off-tick price is not a degraded trial, it is no trial
  at all: artifact ``P-5-20260730T000608Z.json`` lost trial 0 to
  ``모의투자 주문처리가 안되었습니다(호가단위 오류)`` and reported ``n=0``.
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

Call pacing
-----------
Every call this module makes passes through :class:`_CallPacer`, which enforces a
minimum ``--pace-s`` interval between any two of them. This is not politeness: at
the mock account's measured ceiling (P-13 — clean 1.0 rps, throttled 2.0 rps) an
unpaced quote-then-submit pair is already over the line, and a throttled submit
destroys the trial rather than degrading it. Artifact
``P-5-20260729T235001Z.json`` is the concrete loss — trial 0 rejected with
``초당 거래건수를 초과하였습니다``, ``n=0``, ``NOT_MEASURED``.

Pacing changes what the probes must *record*. See :func:`effective_interval_ms`:
a ``--poll-ms`` or ``--gap-ms`` below the pacing interval does not happen, so the
recorded granularity is the effective interval, never the requested one.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
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
    redact,
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

#: Contract-spec SoT for futures tick sizes. The block is annotated "모든 계약
#: 상수는 여기서 로드 — 코드에 하드코딩 금지", so no tick literal appears in this
#: module; :func:`_futures_tick` reads it through the registry instead.
_EXECUTION_CONFIG = Path(__file__).resolve().parents[2] / "config" / "execution.yaml"

#: Broker-reported 호가단위 in the domestic-stock current-price response.
#:
#: TR ``FHKST01010100`` (``v1_국내주식-008``,
#: ``/uapi/domestic-stock/v1/quotations/inquire-price``), field ``output.aspr_unit``
#: — official wrapper ``examples_llm/domestic_stock/inquire_price/
#: chk_inquire_price.py``, ``COLUMN_MAPPING``: ``'aspr_unit': '호가단위'``.
#:
#: This is the only stock tick source the probe will accept. The repo carries no
#: KRX price-band table and this module must not invent one, so if the broker does
#: not report a unit the stock probe fails loudly (see :func:`_stock_tick`).
_STOCK_QUOTE_UNIT_FIELD = "aspr_unit"

#: Probe order type -> stock ``ORD_DVSN`` (주문구분) wire code.
#:
#: Official source (KIS ``open-trading-api`` ``examples_llm``, read 2026-07-30 via
#: ``kis-code-assistant-mcp``):
#: ``domestic_stock/inquire_psbl_order/inquire_psbl_order.py`` — 매수가능조회, TR
#: ``v1_국내주식-007`` (real ``TTTC8908R`` / mock ``VTTC8908R``). Two docstring
#: locations in that file enumerate the pair:
#:
#: * body, "2) 매수가능수량 확인": "특정 종목 전량매수 시 가능수량을 확인하실 경우
#:   ORD_DVSN:00(지정가)는 종목증거금율이 반영되지 않습니다. 따라서 "반드시"
#:   ORD_DVSN:01(시장가)로 지정하여 종목증거금율이 반영된 가능수량을 확인하시기
#:   바랍니다."
#: * ``Args``: ``ord_dvsn (str): [필수] 주문구분 (ex. 01 : 시장가)``
#:
#: The cross-reference is necessary because ``order_cash`` — 주식주문(현금), TR
#: ``v1_국내주식-001``, real ``TTTC0012U`` / mock ``VTTC0012U`` for 매수, the TR this
#: probe actually POSTs to — enumerates NO ``ORD_DVSN`` value: its ``Args`` line is a
#: bare ``ord_dvsn (str): [필수] 주문구분``. ``shared/execution/executor.py:58-61``
#: cites the same source for the same reason ("order_cash enumerates no ORD_DVSN
#: value").
#:
#: WARNING — the two asset classes give "01" OPPOSITE meanings: stock ``ORD_DVSN``
#: "01" is 시장가 (market), while futures ``ORD_DVSN_CD`` "01" is 지정가 (limit) and
#: 시장가 is "02" (``executor.py:63-72``; the futures code is sent by
#: :meth:`MockTradingClient.futures_order_body`). Never carry a code across. Like
#: the runtime's tables this one deliberately has no default entry: an unknown
#: order type is refused rather than coerced into a code that could turn a resting
#: limit into a market order.
_STOCK_ORD_DVSN: dict[str, str] = {
    "limit": "00",  # 지정가
    "market": "01",  # 시장가
}

#: ``ORD_UNPR`` for a 시장가 stock order — the field is present but is not a price.
#:
#: ``order_cash`` makes ``ORD_UNPR`` mandatory: it raises
#: ``ValueError("ord_unpr is required")`` on ``""``, so the key cannot be dropped.
#: The same docstring states what the broker does when an order carries no price —
#: "※ ORD_UNPR(주문단가)가 없는 주문은 상한가로 주문금액을 선정하고 이후 체결이되면
#: 체결금액로 정산됩니다." — it prices the order itself and settles at the fill.
#: ``"0"`` is the encoding that satisfies both constraints (present, not a limit
#: price), and is what the runtime already sends for a priceless order:
#: ``executor.py:393`` ``"ORD_UNPR": str(int(order.price)) if order.price else "0"``.
_STOCK_ORD_UNPR_MARKET = "0"

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

#: Default minimum interval between any two broker calls, in seconds.
#:
#: Measured, not guessed: P-13 (artifact ``P-13-20260729T063120Z``, campaign
#: ``docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/``) bracketed this
#: mock account's query class at clean 1.0 rps / throttled 2.0 rps (``EGW00201``).
#: 1.1 s sits just above the measured clean rate — the slowest rate that is known
#: to work, rather than the fastest that has not yet been seen to fail.
DEFAULT_PACE_S = 1.1


class _CallPacer:
    """Minimum-interval gate in front of the probe client's only socket.

    Contract: :meth:`wait` blocks until the next call is permitted and returns the
    instant it was released. The first call is never delayed — an empty pacer has
    no previous call to be too close to.

    The released instant is the *only* honest t0 for a latency measurement.
    A timestamp taken before the gate would include the pacing sleep and charge it
    to the broker; on a 1.1 s pace that inflates every accept-to-visible sample by
    roughly 1100 ms, which for a ``hard_maximum`` bound propagates straight into
    an over-wide approved value.
    """

    def __init__(self, interval_s: float) -> None:
        self.interval_s = max(0.0, float(interval_s))
        self._next_allowed_at: float | None = None

    def wait(self) -> float:
        """Block out the remainder of the interval; return the release instant."""
        now = time.monotonic()
        if self._next_allowed_at is not None and now < self._next_allowed_at:
            # Sleep the REMAINDER only. A fixed per-call sleep would also charge
            # the probe for time already spent in the previous request.
            time.sleep(self._next_allowed_at - now)
            now = time.monotonic()
        self._next_allowed_at = now + self.interval_s
        return now


def pace_interval_s(args: argparse.Namespace) -> float:
    """The pacing interval for this run, in seconds (``0`` disables pacing)."""
    return max(0.0, float(getattr(args, "pace_s", DEFAULT_PACE_S)))


def effective_interval_ms(requested_ms: float, args: argparse.Namespace) -> float:
    """A requested inter-call interval, floored by the pacer, in ms.

    The pacer will not release two calls closer together than ``--pace-s``, so a
    ``--poll-ms`` or ``--gap-ms`` below it is silently widened. Probes must record
    THIS value rather than the requested one:

    * a polled sample carries up to one *effective* poll interval of additive
      error, and runbook §8.3 makes that error part of the approved bound — an
      understated granularity understates the bound, which is fail-open;
    * P-2's deduplication bracket is set by the gap that actually reached the
      wire, so recording the requested gap would mis-bracket the window.
    """
    return max(float(requested_ms), pace_interval_s(args) * 1000.0)


@dataclass
class Placed:
    odno: str
    #: Pacer release instant of the submit — post-sleep, immediately pre-wire.
    sent_at_monotonic: float
    body: dict[str, Any]


# ---------------------------------------------------------------------------
# Tick discipline — a limit price the broker will accept
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tick:
    """A valid price increment plus the evidence that established it.

    ``source`` is carried into every artifact so a reviewer can see where the
    number came from without re-deriving it. Neither field is ever a literal in
    this module: a futures tick comes from ``config/execution.yaml``, a stock tick
    from the broker's own quote response.

    Attributes:
        size: The minimum price increment, as an exact :class:`~decimal.Decimal`.
        source: Human-readable provenance, recorded in the artifact.
    """

    size: Decimal
    source: str


@dataclass(frozen=True)
class TickPrice:
    """A limit price snapped to a broker-valid tick.

    Attributes:
        value: The snapped price as a float — an exact multiple of ``tick.size``.
        wire: The exact string the request body carries. Built from the snapped
            Decimal and never from float arithmetic, so a ``0.05`` multiple
            cannot reach the broker as ``372.15000000000003``.
        tick: The increment used, with its provenance.
        unrounded: The price before snapping, for the artifact record.
        rounding: ``"floor"`` or ``"ceiling"`` — which way the snap moved.
    """

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
    """A snapped price as the clean decimal string a request body will carry.

    ``normalize()`` drops the trailing zero a ``0.05`` snap leaves behind
    (``372.10`` -> ``372.1``, the same shape as the ``str(price)`` the runtime
    sends at ``executor.py:471``) but can flip an integral value into scientific
    notation (``70100`` -> ``7.01E+4``), which no broker parser would take. The
    format is therefore forced to fixed-point.
    """
    return format(value.normalize(), "f")


def snap_to_tick(price: float, tick: Tick, *, side: str, marketable: bool) -> TickPrice:
    """Snap ``price`` to a multiple of ``tick``, always AWAY from the touch.

    The direction is derived from ``side``/``marketable`` rather than passed in by
    the caller, because getting it backwards is the one failure here with a
    trading consequence. The resting probes (P-2, P-5, P-8, P-FQP, P-NMPR) depend
    on the order sitting unfilled, and a snap toward the touch narrows the
    ``--price-offset-pct`` gap that keeps it there. P-11 is the mirror case: it is
    deliberately marketable and must not be snapped back out of the market.

    ====  ==========  ========  ==================================
    side  marketable  rounding  rests / crosses
    ====  ==========  ========  ==================================
    BUY   False       floor     below the touch, moved lower
    BUY   True        ceiling   above the touch, moved higher
    SELL  False       ceiling   above the touch, moved higher
    SELL  True        floor     below the touch, moved lower
    ====  ==========  ========  ==================================

    Args:
        price: The unrounded, probe-computed limit price.
        tick: The increment to snap to, with its provenance.
        side: ``"BUY"`` or ``"SELL"``.
        marketable: True when the price is deliberately across the touch.

    Returns:
        The snapped price, its wire string, and the tick provenance.

    Raises:
        ProbeError: unknown ``side``, a non-positive tick, a snapped price that is
            not a positive multiple of the tick, or a wire string that does not
            represent the snapped price exactly.
    """
    if side not in ("BUY", "SELL"):
        raise ProbeError(f"unknown order side {side!r} (expected 'BUY' or 'SELL')")
    if tick.size <= 0:
        raise ProbeError(
            f"tick size must be positive, got {tick.size} from {tick.source}"
        )
    # A resting BUY sits below the touch and a resting SELL above it; a marketable
    # order sits on the opposite side of each. Away-from-touch is therefore "down"
    # for exactly the two combinations where those two facts agree.
    round_down = (side == "BUY") != marketable
    # Integer-multiple arithmetic in Decimal: `multiple * tick` is exact, whereas
    # the float form of the same product yields 7443 * 0.05 == 372.15000000000003.
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
    """The ``order-cash`` request body — 지정가 or 시장가.

    Mirror of ``executor.py:386-393`` (note ORD_UNPR int-truncation, Q-WIRE-1).
    For a limit order ``price.wire`` is byte-identical to the runtime's
    ``str(int(price))``: :func:`_stock_tick` refuses a fractional 호가단위, so a
    snapped stock price is always a whole number of won and the truncation is a
    no-op. What the truncation used to do on its own — produce a 1원 granularity
    that no KRX price band allows — is what made this body ``호가단위 오류`` bait.

    A module-level function rather than only a method because the dry-run has no
    client and must still be able to show the exact body it would send. For a
    market order that is the whole body: no quote is needed to build it.

    Args:
        cano: 종합계좌번호 (account prefix).
        acnt_prdt_cd: 계좌상품코드 (account suffix).
        symbol: 종목코드.
        qty: 주문수량.
        price: The tick-snapped limit price. Required for ``order_type="limit"``
            and forbidden for ``"market"``.
        order_type: ``"limit"`` (지정가) or ``"market"`` (시장가), resolved to a
            wire code through :data:`_STOCK_ORD_DVSN`.

    Raises:
        ProbeError: unknown ``order_type``, a limit order with no price, or a
            market order handed one.
    """
    ord_dvsn = _STOCK_ORD_DVSN.get(order_type)
    if ord_dvsn is None:
        raise ProbeError(
            f"unknown stock order type {order_type!r} "
            f"(expected one of {sorted(_STOCK_ORD_DVSN)})"
        )
    # Both directions are refused, not defaulted. A missing price must never
    # become a market order by omission, and a market order that quietly carried
    # a limit price would report a 시장가 fill it never took.
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


def _futures_tick(symbol: str) -> Tick:
    """The tick for a futures ``symbol``, from the repo's contract-spec registry.

    ``resolve_contract_spec`` maps by ``symbol_prefix``, so the value follows the
    ``--symbol`` actually used (``A01``/``101`` -> full contract, ``A05`` -> mini)
    rather than being fixed to one product.

    Raises:
        ProbeError: no registered spec matches ``symbol``.
    """
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
    """The 호가단위 the broker itself reported for a stock ``symbol``.

    Read from the quote response the probe already made rather than from a table:
    the repo holds no KRX price band and inventing one would either waste a rate
    slot on a 호가단위 오류 rejection or, worse, be silently accepted at the wrong
    granularity for some other price band.

    The unit must be a whole number of won because the runtime's stock wire field
    is int-truncated (``ORD_UNPR = str(int(price))``, quirk Q-WIRE-1) — a
    fractional unit could not survive that, so it is refused rather than truncated.

    Raises:
        ProbeError: the field is absent, non-numeric, non-positive, or fractional,
            i.e. no tick unit could be established.
    """
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
    """Minimal, safety-gated KIS 모의투자 trading client for probes.

    Not a replacement for ``OrderExecutor``: it deliberately omits the retry,
    rate-limit and fill-monitor wrappers because those are part of the behaviour
    under measurement (draft §5 Q-IDEMP-1/2, Q-RATE-1).

    The one thing it does add is :class:`_CallPacer`. That is not the runtime's
    rate limiter and measures nothing — it is a fixed floor on the interval
    between this client's own calls, present because exceeding the account's
    measured ceiling does not perturb a measurement, it voids it (the submit is
    rejected and the trial produces no sample at all).
    """

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

    # -- headers ---------------------------------------------------------
    def _headers(self, tr_id: str) -> dict[str, str]:
        headers = dict(self.auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        return headers

    # -- the single paced transport --------------------------------------
    def _request(
        self,
        method: str,
        url: str,
        tr_id: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any], float, str]:
        """The one place this client opens a socket — and so the one paced site.

        Both public transports funnel through here, which is what makes the pacing
        unbypassable: a call type added later cannot forget to pace, because there
        is nowhere else to send a request from.

        Ordering matters and is deliberate:

        1. headers first. ``get_auth_headers`` may itself issue a token request,
           and a token round-trip must not land between the release instant and
           the wire. Absorbing it into the pacing wait instead costs nothing —
           token issuance is a different endpoint class from the one P-13
           measured, and the pacer still separates *this* client's calls.
        2. then the pacing gate, which sleeps out whatever remains of the
           interval.
        3. then the stamp, then the request — with nothing between them.
        """
        assert_mock_host(url)  # last line of defence; the callers gate too
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
        """Monotonic instant the most recent request was released to the wire.

        This is the correct t0 for every latency a probe derives from a call it
        made itself. Capturing ``time.monotonic()`` before the call instead would
        fold the pacing sleep into the measurement and report it as broker
        latency.

        Raises:
            ProbeError: no request has been issued yet.
        """
        if self._last_send_monotonic is None:
            raise ProbeError(
                "last_send_instant() called before any request was issued — "
                "there is no send to timestamp"
            )
        return self._last_send_monotonic

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
        return self._request(method, url, tr_id, params=params, body=body)

    def quote_call(
        self, path: str, tr_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Read-only quotations call (host-gated; TR prefix rule does not apply)."""
        url = f"{MOCK_BASE_URL}{path}"
        assert_mock_host(url)
        _status, parsed, _ms, _text = self._request("GET", url, tr_id, params=params)
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

    def stock_quote(self, symbol: str) -> tuple[float, Tick]:
        """Last price AND the broker's own 호가단위, from one inquire-price call.

        Both come out of the same response deliberately: a second call just for
        the tick would spend another slot of the measured rate budget (P-13: clean
        1.0 rps) on a number the first response already carried.

        Raises:
            ProbeError: no usable price, or no establishable quote unit.
        """
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
            price: A tick-snapped price. ``UNIT_PRICE`` carries ``price.wire``,
                which has the same shape as the runtime's ``str(price)`` but is
                guaranteed to be an exact tick multiple — an off-tick value is
                rejected outright with ``호가단위 오류``.
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
            "UNIT_PRICE": price.wire,
            "NMPR_TYPE_CD": nmpr_type_cd,
            "KRX_NMPR_CNDT_CD": krx_nmpr_cndt_cd,
            "CTAC_TLNO": "",
            "FUOP_ITEM_DVSN_CD": "",
            # 지정가 — executor.py:887 ``_map_futures_order_type`` maps internal
            # OrderType.LIMIT ("00") to futures ORD_DVSN_CD "01".
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

    def submit_futures(
        self, body: dict[str, str]
    ) -> tuple[Placed | None, dict[str, Any], float]:
        tr_id = self.tr_ids["futures_order_day_mock"]
        status, parsed, ms, _text = self.trading_call(
            "POST", _FUT_ORDER_PATH, tr_id, body=body
        )
        # t0 comes from the pacer, not from before the call: the pacing sleep
        # happens inside _request and would otherwise be measured as broker
        # latency. P-5 and P-FQP both subtract this from a later observation.
        sent = self.last_send_instant()
        odno = str((parsed.get("output") or {}).get("ODNO") or "").strip()
        placed = (
            Placed(odno, sent, body)
            if status == 200 and parsed.get("rt_cd") == "0" and odno
            else None
        )
        return placed, parsed, ms

    def cancel_futures(self, odno: str, qty: int) -> dict[str, Any]:
        """Cancel — ``RVSE_CNCL_DVSN_CD='02'`` (executor.py:689)."""
        return self._rvsecncl(odno, qty, dvsn="02", price=None)

    def replace_futures(self, odno: str, qty: int, price: TickPrice) -> dict[str, Any]:
        """Amend — ``RVSE_CNCL_DVSN_CD='01'``. Never exercised by the runtime
        (draft §3.1 row 8: the literal appears once, value ``"02"`` only).

        The amend price needs the same tick discipline as the original submit: an
        off-tick amend is rejected exactly like an off-tick submit, and a rejected
        amend makes P-8 report replace semantics it never observed.
        """
        return self._rvsecncl(odno, qty, dvsn="01", price=price)

    def _rvsecncl(
        self, odno: str, qty: int, *, dvsn: str, price: TickPrice | None
    ) -> dict[str, Any]:
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
    return run, MockTradingClient(creds, auth, run, pace_s=pace_interval_s(args))


def _resting_price(
    client: MockTradingClient, args: argparse.Namespace
) -> tuple[TickPrice, str]:
    """A tick-valid limit price far enough from the touch that it will not fill.

    The snap is away from the touch, so it can only widen the
    ``--price-offset-pct`` gap that keeps the order resting, never narrow it.

    Raises:
        ProbeError: the computed price is non-positive, or no tick could be
            established for the instrument.
    """
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
        observed = sorted(
            {str(r.get("odno", "")).strip() for r in rows} & set(distinct)
        )

        # The effective gap, not the requested one: the pacer floors the sleep
        # below, and the dedup bracket is set by the gap that reached the wire.
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
        # Amend further DOWN, i.e. further from the touch: the amended order must
        # keep resting for the coexistence window to be observable at all.
        new_price = snap_to_tick(
            price.value * 0.99, price.tick, side=side, marketable=False
        )
        amend = client.replace_futures(placed.odno, args.quantity, new_price)
        # Same rule as submit_futures: t0 is the pacer's release instant, so the
        # pacing sleep before the amend is not counted into coexistence_ms.
        amended_at = client.last_send_instant()
        new_odno = str((amend.get("output") or {}).get("ODNO") or "").strip()
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
        run.measure("poll_granularity_ms", effective_interval_ms(args.poll_ms, args))
        run.measure(
            "mode_determination",
            "Map to ReplaceSemantics only after N>=5 trials agree. A single trial "
            "showing zero coexistence does NOT prove atomicity — polling can miss "
            "an interval shorter than poll_granularity_ms, which is the EFFECTIVE "
            "interval max(--poll-ms, --pace-s) and not the requested --poll-ms.",
        )
    finally:
        _cleanup(client, run, odnos, args.quantity)
        client.close()
    return run


# ---------------------------------------------------------------------------
# P-11 — balance reflection
# ---------------------------------------------------------------------------

#: ``measurements.fill_case`` verdicts. A run is one of exactly these two, and the
#: second is a statement about what the harness cannot see — never a measurement.
_FILL_OBSERVED = "FILLED_AND_REFLECTED"
_FILL_UNDETERMINED = "UNDETERMINED_NON_FILL_OR_LAG_BEYOND_WINDOW"

#: What would separate the two halves of :data:`_FILL_UNDETERMINED`.
#:
#: Named rather than added: an execution inquiry is a ``/trading/`` path, and this
#: module does not grow trading-namespace surface for an interpretation aid. The
#: manual re-check below is what today's operator actually did.
_FILL_RESOLUTION_PATH = (
    "A stock execution inquiry — 주식일별주문체결조회, "
    "/uapi/domestic-stock/v1/trading/inquire-daily-ccld (real TTTC8001R / mock "
    "VTTC8001R) — would separate the two by reporting filled quantity for the ODNO "
    "directly. This harness deliberately does not add that trading-namespace path. "
    "Until it does, resolve out of band: re-read the balance after the run and see "
    "whether the holding ever moved. Artifact P-11-20260730T002715Z needed exactly "
    "that manual re-check (~18 min later, holding unchanged at the baseline) to "
    "establish that its CENSORED result was a NON-FILL and not a reflection lag."
)


def _market_price_record() -> dict[str, Any]:
    """The ``limit_price_tick`` slot for a 시장가 run: an explicit bypass, not a gap.

    The key is kept so a reviewer comparing artifacts always finds tick
    provenance where the limit path puts it. An absent key would have to be
    *interpreted*; ``applicable: False`` states the reason instead.
    """
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
    symbol: str,
    baseline_qty: int,
    observed_qty: int,
    window_s: float,
    polls: int,
    poll_interval_ms: float,
) -> dict[str, Any]:
    """State plainly which of the two cases the run represents, or that it cannot.

    The artifact that motivated this record (``P-11-20260730T002715Z``) recorded a
    censored window and nothing else, so "the order never filled" and "the order
    filled and the balance lagged" were indistinguishable without an out-of-band
    check. The distinction is the difference between a broker consistency finding
    and no finding at all, so it is written down rather than left to a reader.
    """
    common: dict[str, Any] = {
        "symbol": symbol,
        "baseline_holding_qty": baseline_qty,
        "final_holding_qty": observed_qty,
        "window_s": window_s,
        "polls": polls,
        "poll_interval_ms_effective": poll_interval_ms,
        "basis": (
            "inquire-balance (VTTC8434R) holdings are the ONLY fill evidence this "
            "harness collects; it has no execution-inquiry path."
        ),
    }
    if reflected:
        return common | {
            "case": _FILL_OBSERVED,
            "interpretation": (
                f"the {symbol} holding rose {baseline_qty} -> {observed_qty}, so the "
                "order both FILLED and was reflected in the balance inside the "
                "window. submit_to_balance_reflection is a real fill-to-reflection "
                "sample."
            ),
        }
    return common | {
        "case": _FILL_UNDETERMINED,
        "interpretation": (
            f"the {symbol} holding stayed at {baseline_qty} for the whole "
            f"{window_s}s window. This run CANNOT tell whether (a) the order never "
            "filled, or (b) it filled and the balance reflection lagged past the "
            "window — the balance reports the same thing in both cases. No bound "
            "may be derived from this run under either reading."
        ),
        "resolves_with": _FILL_RESOLUTION_PATH,
    }


def _p11_dry_run(run: ProbeRun, args: argparse.Namespace, order_type: str) -> None:
    """Report the request P-11 would send, without contacting the broker.

    A 시장가 body needs no quote, so the dry-run can show it byte for byte — which
    is the point: the defect this probe was fixed for was an unnoticed
    ``ORD_DVSN``/``ORD_UNPR`` pair. A 지정가 body cannot be shown, because its price
    comes from a live quote.
    """
    plan = (
        f"stock {order_type} order (ORD_DVSN={_STOCK_ORD_DVSN[order_type]}), then "
        f"poll inquire-balance every {effective_interval_ms(args.poll_ms, args)}ms "
        f"for up to {args.balance_timeout_s}s"
    )
    if order_type != "market":
        run.observe(would_send=plan, order_type=order_type, order_body=None)
        print(
            f"\n  would send: {plan}\n"
            "  body not shown — a 지정가 price is derived from a live quote."
        )
        return
    # Re-resolved rather than threaded out of _setup: it is a pure env read, and
    # every order probe shares that helper's two-value signature.
    creds = resolve_credentials(args.asset, is_real=False)
    body = build_stock_order_body(
        creds.cano, creds.acnt_prdt_cd, args.symbol, args.quantity, order_type="market"
    )
    run.observe(would_send=plan, order_type=order_type, order_body=body)
    # redact() before printing: the body carries the real account number, and a
    # dry-run must not put it on an operator's terminal.
    print(f"\n  would send POST {_STOCK_ORDER_PATH}")
    print(f"  {json.dumps(redact(body), ensure_ascii=False)}")


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

    Why the order type defaults to 시장가
    ------------------------------------
    The measurement is a *fill*-to-reflection lag, so a run that does not fill
    yields nothing at all. The marketable-limit default did not fill: artifact
    ``P-11-20260730T002715Z.json`` was ACCEPTED (``rt_cd=0``, ODNO ``0000008686``,
    ``ORD_DVSN="00"``, ``ORD_UNPR="232500"`` — a limit 10% above the 211,000 touch,
    correctly tick-snapped) and the holding never moved; an out-of-band balance
    read ~18 minutes later still showed the unchanged baseline. Being *marketable
    in price* is evidently not the same as being *filled* on 모의투자, so
    ``--stock-order-type`` defaults to ``market`` and asks the broker for a fill
    instead of pricing one. ``--stock-order-type limit`` keeps the old shape
    reachable for comparison.

    A side effect worth naming: the market path makes no quote call, so it depends
    on no tick at all. ``--price-offset-pct``, :func:`snap_to_tick` and the
    ``aspr_unit`` precondition are all limit-path-only.

    Fill versus balance lag
    -----------------------
    ``measurements.fill_case`` says which of the two a run represents. The balance
    query is the harness's only holdings source, so a window that expires with the
    holding unchanged is *undetermined* — a non-fill and a lag beyond the window
    look identical from here. That is recorded as an interpretation caveat naming
    what would resolve it, never as a bound.
    """
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
            # No quote: a 시장가 order carries no price, so there is nothing to
            # price it against and no tick to establish. That also saves a call
            # out of the measured rate budget (P-13: clean 1.0 rps).
            body = client.stock_order_body(
                args.symbol, args.quantity, order_type="market"
            )
            run.observe(order_body=body, order_type=order_type)
            run.measure("limit_price_tick", _market_price_record())
        else:
            last, tick = client.stock_quote(args.symbol)
            # Marketable limit: cross the touch by the offset so it fills promptly.
            # The snap goes UP for the same reason the resting probes snap down —
            # away from the touch, which here means further INTO the market, never
            # back out of it.
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
        tr_id = client.tr_ids["stock_krx_buy_mock"]
        status, parsed, _ms, _text = client.trading_call(
            "POST", _STOCK_ORDER_PATH, tr_id, body=body
        )
        # Pacer release instant, not a pre-call timestamp: submit_to_balance_ms
        # must not include the pacing sleep that preceded this submit.
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
        polls = 0
        final_qty = base_qty
        # --balance-timeout-s, not the shared --visibility-timeout-s: this window
        # has to contain a real balance update, and the pacer floors polling at
        # --pace-s, so the shared 30s default buys only ~27 polls.
        deadline = time.monotonic() + args.balance_timeout_s
        while time.monotonic() < deadline:
            polls += 1
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
            final_qty = qty
            if qty > base_qty:
                reflected_at = time.monotonic()
                break
            time.sleep(args.poll_ms / 1000.0)

        run.measure(
            "fill_case",
            _fill_case_record(
                reflected=reflected_at is not None,
                symbol=args.symbol,
                baseline_qty=base_qty,
                observed_qty=final_qty,
                window_s=args.balance_timeout_s,
                polls=polls,
                poll_interval_ms=effective_interval_ms(args.poll_ms, args),
            ),
        )
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
                "poll_granularity_ms", effective_interval_ms(args.poll_ms, args)
            )
            run.measure(
                "granularity_note",
                "The sample carries up to one poll interval of additive error, so "
                "an approved bound must exceed it plus poll_granularity_ms — which "
                "is the EFFECTIVE interval max(--poll-ms, --pace-s), because the "
                "pacer floors polling and a smaller --poll-ms did not happen "
                "(runbook §8.3).",
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
