"""P-VL — venue price-band / quantity limits, GET-only on 모의투자 (MOCK_VTS).

Design: ``docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md``
§4 (legs, timing, artifact) and §5 (verdicts). CP-3 decision 9 picked the KRX
rulebook as the PRIMARY source for ``max_quantity``; this probe is the
**corroboration**, not the source.

What it closes (design §4.1):

* **L1** — the five price fields of 선물옵션 시세 ``FHMIF10000000``, so the band
  semantics stop being inference: whether 기준가격 is the previous settlement
  price (``futs_sdpr``) rather than the previous close (``futs_prdy_clpr``), and
  whether every quoted price is a multiple of the registered tick.
* **L2** — whether the broker's reported band reproduces 시행세칙 제56조's own
  arithmetic (기준가격 × 비율, 상한가 내림 / 하한가 올림). No network.
* **L3** — that the 모의 account can order at least one contract at the touch.

What it CANNOT close — stated first, design §4.3:

* **KIS 측 호가수량한도.** ``VTTO5105R``'s ``ord_psbl_qty`` is derived from
  예수금/증거금, not from the venue's structural limit (P-R5-PRE 2026-08-03: a
  zero-deposit account reports 0). The 2,000-contract 호가수량한도 of 별표 17의2,
  and any lower member limit KIS sets under 시행세칙 제61조제3항, are visible
  only by SENDING an order and reading the rejection. That is outside this
  probe's GET-only scope (design §7 ④ keeps it as a separate P-VL-2 option).
* **2/3단계 확대 의미론.** Escalation depends on a 기준종목 touching its own
  limit; a probe cannot cause it. Observed or not observed, never induced.
* **The runtime supply of a band.** This probe observes values; wiring a band
  into ``VenueConstraintSnapshot`` is design §6, a separate decision.

Safety model. This module is read-only by construction and mock-only by
construction, and both properties are structural rather than documentary:

1. :data:`ALLOWLIST` is a three-way gate (method ``GET`` + TR id + URL path)
   enforced by :func:`~tools.broker_probes.common.assert_read_only_call` before
   the session is touched, so a refused call opens no socket.
2. Every URL is built from :data:`~tools.broker_probes.common.MOCK_BASE_URL` and
   passed through :func:`~tools.broker_probes.common.assert_mock_host`, which
   raises :class:`~tools.broker_probes.common.SafetyViolation` for any other
   host. The real host is unreachable from this module.
3. The one ``/trading/`` TR is additionally checked by
   :func:`~tools.broker_probes.common.assert_mock_trading_tr` (모의 trading TRs
   are ``V``-prefixed), so a real trading TR cannot be smuggled in.

The register declares this probe ``requires_confirm=False`` (design §4), which is
the ONE place P-VL differs from every other networked probe in
``tools/broker_probes``: runbook safety control #4 (``--confirm`` 없이는 브로커
무접촉, ``docs/runbooks/kis-capability-probes.md:86``) does not apply to it. The
three controls above are what stands in its place, and
``tests/tools/test_broker_probes_pvl.py`` asserts each one against this module's
own AST and against a refused real-host client rather than against this comment.
Note the scope of that AST claim: the mandated reuse of
``probes_real_order._corroborate_tick`` / ``resolve_smallest_contract`` puts
order-emitting modules in this file's IMPORT GRAPH, so the read-only property is
a property of *this module's* transport, not of everything it imports.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from datetime import time as clock_time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeError,
    ProbeRun,
    ReadOnlyCall,
    assert_mock_host,
    assert_mock_trading_tr,
    assert_read_only_call,
    build_auth_config,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    rt_cd_of,
    warn_shared_token_cache,
)

# Pacing is shared, not re-derived: 1.1 s is P-13's measured clean query rate
# (artifact ``P-13-20260729T063120Z``, clean 1.0 rps / throttled 2.0 rps
# ``EGW00201``). ``probes_balance`` keeps a local copy of this number to keep
# order-submitting code out of its import graph; that reason does not apply here
# because the design mandates reusing ``probes_real_order``'s pure functions,
# which already imports ``probes_order``. A second copy would be duplication
# without buying any isolation.
from tools.broker_probes.probes_order import DEFAULT_PACE_S
from tools.broker_probes.probes_real_order import (
    _corroborate_tick,
    _decimal_field,
    resolve_smallest_contract,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Endpoints — TR ids cited to the official KIS example wrappers (design §1)
# ---------------------------------------------------------------------------

#: 선물옵션 시세 [v1_국내선물-006]. Official wrapper
#: ``examples_llm/domestic_futureoption/inquire_price/inquire_price.py`` — its
#: own ``env_dv`` table gives ``FHMIF10000000`` for BOTH real and demo, so there
#: is no mock variant of this TR to choose.
_PRICE_PATH = "/uapi/domestic-futureoption/v1/quotations/inquire-price"
_PRICE_TR = "FHMIF10000000"

#: 선물옵션 주문가능 [v1_국내선물-005]. Official wrapper
#: ``examples_llm/domestic_futureoption/inquire_psbl_order/inquire_psbl_order.py``
#: — its ``env_dv`` table gives a ``TTT``-prefixed id for ``real`` and
#: ``VTTO5105R`` for ``demo``; required params ``CANO`` /
#: ``ACNT_PRDT_CD`` / ``PDNO`` / ``SLL_BUY_DVSN_CD`` / ``UNIT_PRICE`` /
#: ``ORD_DVSN_CD``. Only the DEMO id appears here: this probe is MOCK_VTS, and
#: that wrapper's REAL id (the ``TTT``-prefixed twin) is deliberately absent
#: from this file, so it cannot be spelled into the allowlist by a copy-paste.
#: ``tests/tools/test_broker_probes_pvl.py`` asserts that absence over the whole
#: file text — which is why this comment names the twin by prefix, not by id.
_PSBL_PATH = "/uapi/domestic-futureoption/v1/trading/inquire-psbl-order"
_PSBL_TR = "VTTO5105R"

#: Complete read-only allowlist. The probe's only transport is a GET gated on
#: this tuple, so an order mutation is structurally unreachable even if a path
#: or TR id arrives from the command line.
ALLOWLIST: tuple[ReadOnlyCall, ...] = (
    ReadOnlyCall(
        _PRICE_TR,
        _PRICE_PATH,
        "선물옵션 시세 — 현재가/전일종가/기준가/상한가/하한가. Quotations "
        "endpoint; carries no account fields.",
    ),
    ReadOnlyCall(
        _PSBL_TR,
        _PSBL_PATH,
        "선물옵션 주문가능 (DEMO TR) — 주문가능수량 at a given UNIT_PRICE. A GET "
        "on a /trading/ path; it requires a price but places nothing.",
    ),
)

#: ``SLL_BUY_DVSN_CD`` for 매수 (design §4.1 L3-L5 all probe the BUY side).
_SLL_BUY_DVSN_BUY = "02"

#: ``ORD_DVSN_CD`` for 지정가, the only order type the paper venue policy admits
#: (``config/tos_runtime/paper/venue_constraint_policy.yaml`` ``allowed_order_types:
#: ["LIMIT"]``).
_ORD_DVSN_LIMIT = "01"

#: The 선물옵션 상품코드 of a futures account. P-R5-PRE (2026-08-03) established
#: this the hard way: the ``03`` account is the futures one, and a mis-wired
#: product code is the defect that campaign spent a run finding.
_FUTURES_PRODUCT_CODE = "03"

# ---------------------------------------------------------------------------
# Rule constants — KRX 파생상품시장 업무규정 시행세칙 제164차 (2026-07-06 시행)
# ---------------------------------------------------------------------------

#: 가격제한비율, 주가지수선물거래 — 별표 14 제1호 (최종개정 2025-05-29): 1단계
#: 8% · 2단계 15% · 3단계 20%. Design §2.1.
RULE_RATIO_STAGES: tuple[tuple[int, Decimal], ...] = (
    (1, Decimal("0.08")),
    (2, Decimal("0.15")),
    (3, Decimal("0.20")),
)

#: 호가가격단위 of 코스피200선물거래 — 시행세칙 제4조의9제1호 (최종개정
#: 2024-11-01): 0.05 포인트. This is the value design §4.1 L2 names, and the
#: value the deployed paper policy carries as ``tick_size: 5`` at the ×100
#: integer scale. It is the FULL contract's tick: a 미니 leaf has its own
#: 호가가격단위, which is why :func:`band_stage_matches` sweeps the registry tick
#: alongside this one instead of assuming they agree.
RULE_TICK_POINTS = Decimal("0.05")

#: 상·하한가 산출 — 시행세칙 제56조제1항·제2항 단서: 상한가는 호가가격단위로
#: 내림, 하한가는 올림.
_RULE_BAND_ROUNDING = (
    "시행세칙 제56조제1항·제2항 단서 — 상한가 = 기준가격 + 기준가격×비율 을 "
    "호가가격단위로 내림, 하한가 = 기준가격 − 기준가격×비율 을 올림"
)

#: 단계 확대가 불가능한 창 — 시행세칙 제56조의2제2항 (최종개정 2026-06-11):
#: 야간거래와 08:45~09:00 은 1단계만. A sample taken inside it has a DETERMINED
#: expected band; a sample outside it does not.
_NO_ESCALATION_START = clock_time(8, 45)
_NO_ESCALATION_END = clock_time(9, 0)

#: CONTINUOUS 세션 — the one phase ``config/tos_runtime/paper/calendar.yaml:56``
#: declares for ``krx-index-futures`` (08:45-15:45 KST).
_SESSION_START = clock_time(8, 45)
_SESSION_END = clock_time(15, 45)

#: The five L1 fields, in the order design §4.1 lists them. Every one must be a
#: positive number and an exact multiple of the registered tick.
_L1_PRICE_FIELDS: tuple[str, ...] = (
    "futs_prpr",
    "futs_prdy_clpr",
    "futs_sdpr",
    "futs_mxpr",
    "futs_llam",
)

#: Verdict tokens. L4/L5 are observation-only by design §5 — they get a token
#: that is NOT a judgement, so a reader cannot mistake "recorded" for "passed".
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_RECORDED = "OBSERVATION_ONLY_NO_VERDICT"


# ---------------------------------------------------------------------------
# Pure arithmetic — Decimal only, never float
# ---------------------------------------------------------------------------


def floor_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Largest multiple of ``tick`` that is ``<= value``. EXACT.

    Integer-quotient arithmetic on ``Decimal`` rather than ``value / tick``:
    division runs under the 28-digit context and can land a boundary value on
    the wrong side, which is precisely the class of error the tick campaign paid
    for once already (``7443 * 0.05 == 372.15000000000003``).
    """
    _require_positive_tick(tick)
    if value < 0:
        raise ProbeError(f"floor_to_tick is for prices; got a negative {value}")
    whole, _remainder = divmod(value, tick)
    return whole * tick


def ceil_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Smallest multiple of ``tick`` that is ``>= value``. EXACT."""
    _require_positive_tick(tick)
    if value < 0:
        raise ProbeError(f"ceil_to_tick is for prices; got a negative {value}")
    whole, remainder = divmod(value, tick)
    return whole * tick if remainder == 0 else (whole + 1) * tick


def _require_positive_tick(tick: Decimal) -> None:
    if tick <= 0:
        raise ProbeError(f"tick size must be positive (got {tick})")


def band_expectation(sdpr: Decimal, *, ratio: Decimal, tick: Decimal) -> dict[str, Any]:
    """제56조's own arithmetic for one (ratio, tick) pair. PURE, no network.

    Returns the two expected limits plus every input, so a reviewer recomputes
    the numbers from the artifact without rerunning anything.
    """
    if sdpr <= 0:
        raise ProbeError(f"기준가격 must be positive (got {sdpr})")
    return {
        "basis_price": str(sdpr),
        "ratio": str(ratio),
        "tick_points": str(tick),
        "expected_upper": str(floor_to_tick(sdpr * (Decimal(1) + ratio), tick)),
        "expected_lower": str(ceil_to_tick(sdpr * (Decimal(1) - ratio), tick)),
        "rounding_rule": _RULE_BAND_ROUNDING,
    }


def band_stage_matches(
    *,
    sdpr: Decimal,
    observed_upper: Decimal,
    observed_lower: Decimal,
    ticks: dict[str, Decimal],
) -> dict[str, Any]:
    """Which (stage ratio, tick) combination reproduces the observed band.

    Design §5 L2 licenses exactly this move for the ratio: on a mismatch,
    recompute at 15%/20% and record *which stage matched*, with no
    interpretation. The tick is swept the same way for the same reason — the
    0.05 호가가격단위 of :data:`RULE_TICK_POINTS` belongs to 코스피200선물거래,
    while the symbol actually under probe may be a 미니 leaf with its own unit,
    and guessing which applies would be the interpretation this probe refuses to
    make. Both candidates are computed; the matches are listed; nothing is
    concluded here.
    """
    combinations: list[dict[str, Any]] = []
    for stage, ratio in RULE_RATIO_STAGES:
        for tick_name, tick in ticks.items():
            expectation = band_expectation(sdpr, ratio=ratio, tick=tick)
            upper_ok = Decimal(expectation["expected_upper"]) == observed_upper
            lower_ok = Decimal(expectation["expected_lower"]) == observed_lower
            combinations.append(
                {
                    "stage": stage,
                    "tick_name": tick_name,
                    **expectation,
                    "upper_matches": upper_ok,
                    "lower_matches": lower_ok,
                    "both_match": upper_ok and lower_ok,
                }
            )
    matched = [
        {
            "stage": c["stage"],
            "tick_name": c["tick_name"],
            "tick_points": c["tick_points"],
        }
        for c in combinations
        if c["both_match"]
    ]
    return {
        "observed_upper": str(observed_upper),
        "observed_lower": str(observed_lower),
        "candidates": combinations,
        "matching_combinations": matched,
        "any_match": bool(matched),
        "source": (
            "ratios: 별표 14 제1호 (주가지수선물거래 1/2/3단계 8/15/20%) · "
            "rounding: 시행세칙 제56조제1항·제2항 단서 · "
            "기준가격: 시행세칙 제55조제1항제2호 (직전 거래일의 정산가격)"
        ),
        "not_an_interpretation": (
            "A matching combination records WHICH arithmetic reproduces the "
            "broker's numbers. It does not establish that the venue used that "
            "stage or that unit, and a non-match does not establish that the "
            "rule is wrong — 기준가격 or the rounding could differ instead."
        ),
    }


def kst_sample_window(now: datetime) -> dict[str, Any]:
    """The KST wall clock of a sample and which rule windows contain it."""
    local = now.astimezone(KST)
    hhmm = local.time()
    inside_no_escalation = _NO_ESCALATION_START <= hhmm < _NO_ESCALATION_END
    return {
        "sampled_at_kst": local.isoformat(),
        "inside_no_escalation_window": inside_no_escalation,
        "no_escalation_window_kst": "08:45-09:00",
        "no_escalation_source": "시행세칙 제56조의2제2항 (최종개정 2026-06-11)",
        "inside_continuous_session": _SESSION_START <= hhmm < _SESSION_END,
        "continuous_session_kst": "08:45-15:45",
        "continuous_session_source": "config/tos_runtime/paper/calendar.yaml:56",
        "expected_stage_is_determined": inside_no_escalation,
        "why": (
            "Inside 08:45-09:00 only stage 1 can be in force, so L2's expected "
            "band is determined. Outside it, a 2/3단계 band is admissible and a "
            "mismatch against the 8% arithmetic is not by itself a defect."
        ),
    }


# ---------------------------------------------------------------------------
# Transport — the ONLY one in this module
# ---------------------------------------------------------------------------


class MockQueryClient:
    """GET-only client pinned to the 모의투자 host. No order path exists on it.

    Deliberately NOT ``probes_real_order.PreflightClient``: that client fixes
    its base URL to ``REAL_BASE_URL`` behind ``assert_real_host`` (design §1),
    and loosening it would weaken a real-money guard to serve a mock probe.
    Deliberately NOT routed through
    :func:`~tools.broker_probes.common.http_json` either: that helper drops the
    response headers, and the ``Date`` header is one of the things design §4.1
    L1 records — the same reason ``probes_balance._get`` and P-16 go to the
    transport directly.

    ``base_url`` is a parameter so a test can hand it the real host and observe
    the refusal. In production there is exactly one caller and it passes nothing.
    """

    def __init__(
        self,
        creds: Any,
        auth: Any,
        session: Any,
        *,
        base_url: str = MOCK_BASE_URL,
        pace_s: float = DEFAULT_PACE_S,
    ) -> None:
        self.creds = creds
        self._auth = auth
        self._session = session
        self._base_url = base_url
        self._pace_s = max(0.0, float(pace_s))
        self._last_call_monotonic: float | None = None

    def get(
        self, *, path: str, tr_id: str, params: dict[str, Any]
    ) -> tuple[int, dict[str, Any], dict[str, str], str, float]:
        """One paced, allowlisted, host-pinned GET.

        Every guard runs BEFORE the session is touched, so a refused call opens
        no socket.

        Returns:
            ``(status, parsed_body, response_headers, raw_text, elapsed_ms)``.
        """
        url = f"{self._base_url}{path}"
        assert_mock_host(url)
        assert_read_only_call("GET", url, tr_id, ALLOWLIST)
        if "/trading/" in path:
            assert_mock_trading_tr(tr_id)

        self._wait_for_pace()
        headers = dict(self._auth.get_auth_headers())
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        started = time.monotonic()
        response = self._session.request(
            "GET", url, headers=headers, params=params, timeout=15.0
        )
        elapsed_ms = (time.monotonic() - started) * 1000.0
        self._last_call_monotonic = time.monotonic()
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

    def _wait_for_pace(self) -> None:
        if self._last_call_monotonic is None or self._pace_s <= 0:
            return
        remaining = self._pace_s - (time.monotonic() - self._last_call_monotonic)
        if remaining > 0:
            time.sleep(remaining)


def _psbl_params(creds: Any, symbol: str, unit_price: Decimal) -> dict[str, str]:
    """``VTTO5105R`` request params, every field from the official wrapper.

    ``CANO`` / ``ACNT_PRDT_CD`` come from the environment-resolved account
    (``KIS_FUTURES_ACCOUNT_NO``), never from a literal; ``redact`` masks both
    before anything is persisted or printed.
    """
    return {
        "CANO": creds.cano,
        "ACNT_PRDT_CD": creds.acnt_prdt_cd,
        "PDNO": symbol,
        "SLL_BUY_DVSN_CD": _SLL_BUY_DVSN_BUY,
        "UNIT_PRICE": format(unit_price, "f"),
        "ORD_DVSN_CD": _ORD_DVSN_LIMIT,
    }


def _psbl_observation(
    status: int, parsed: dict[str, Any], headers: dict[str, str], elapsed_ms: float
) -> dict[str, Any]:
    """The four ``VTTO5105R`` fields design §4.1 records, plus the answer code.

    Verbatim: a refusal is transcribed, not classified. P-CA's lesson is the
    reason — reading ``held=0`` as "flat" when the query had been refused cost
    that campaign a whole observation.
    """
    output = parsed.get("output")
    output = output if isinstance(output, dict) else {}
    return {
        "http_status": status,
        "rt_cd": rt_cd_of(parsed),
        "msg_cd": str(parsed.get("msg_cd") or ""),
        "msg1": str(parsed.get("msg1") or "").strip(),
        "ord_psbl_qty_raw": output.get("ord_psbl_qty"),
        "tot_psbl_qty_raw": output.get("tot_psbl_qty"),
        "bass_idx_raw": output.get("bass_idx"),
        "elapsed_ms": round(elapsed_ms, 1),
        "broker_date_header": headers.get("Date", ""),
    }


def _integral_quantity(raw: Any, field: str) -> int:
    """A quantity field as an exact non-negative integer, or a loud refusal.

    A contract count that is not an integer is not a small formatting surprise:
    ``ord_psbl_qty`` is the number that decides whether one contract can be
    sent, and a fractional or unparsable value means the field is not what this
    probe believes it is. Fail-closed and loudly, never round.
    """
    value = _decimal_field({field: raw}, field)
    if value is None:
        raise ProbeError(
            f"{field}={raw!r} is not a readable number. The broker answered "
            "rt_cd=0, so a missing or unparsable quantity means the field name "
            "or response shape is not what this probe assumes — re-read the "
            "official wrapper rather than treating it as zero."
        )
    if value != value.to_integral_value():
        raise ProbeError(
            f"{field}={raw!r} is not an integer. Quantities here are CONTRACTS "
            "(config/tos_runtime/paper/venue_constraint_policy.yaml "
            "quantity_unit: CONTRACTS); a fractional contract count cannot be "
            "rounded into one."
        )
    if value < 0:
        raise ProbeError(f"{field}={raw!r} is negative; a contract count cannot be")
    return int(value)


# ---------------------------------------------------------------------------
# Legs
# ---------------------------------------------------------------------------


def _leg_l1(
    client: MockQueryClient, run: ProbeRun, symbol: str, tick: Any
) -> dict[str, Decimal]:
    """L1 — the five 시세 fields, the ``Date`` header and the tick corroboration.

    Raises on anything design §5 lists as an L1 failure: ``rt_cd != 0``, a field
    that is absent or non-positive, or a quoted price that is not a multiple of
    the registered tick.
    """
    status, parsed, headers, _text, elapsed_ms = client.get(
        path=_PRICE_PATH,
        tr_id=_PRICE_TR,
        params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": symbol},
    )
    window = kst_sample_window(datetime.now(KST))
    rt_cd = rt_cd_of(parsed)
    output = parsed.get("output1")
    output = output if isinstance(output, dict) else {}

    run.observe(
        leg="L1",
        tr_id=_PRICE_TR,
        http_status=status,
        rt_cd=rt_cd,
        msg_cd=str(parsed.get("msg_cd") or ""),
        msg1=str(parsed.get("msg1") or "").strip(),
        broker_date_header=headers.get("Date", ""),
        elapsed_ms=round(elapsed_ms, 1),
        **window,
    )
    run.measure("l1_sample_window", window)

    if rt_cd != "0":
        raise ProbeError(
            f"L1 {_PRICE_TR} answered rt_cd={rt_cd!r} "
            f"msg_cd={parsed.get('msg_cd')!r} msg1={parsed.get('msg1')!r}. Every "
            "later leg reads its prices from this response, so there is nothing "
            "to measure — the refusal is the whole observation."
        )

    prices: dict[str, Decimal] = {}
    unusable: list[str] = []
    for field in _L1_PRICE_FIELDS:
        value = _decimal_field(output, field)
        if value is None or value <= 0:
            unusable.append(f"{field}={output.get(field)!r}")
        else:
            prices[field] = value
    run.measure(
        "l1_quote_fields",
        {
            "tr_id": _PRICE_TR,
            "source": (
                "examples_llm/domestic_futureoption/inquire_price/inquire_price.py "
                "(env_dv: FHMIF10000000 for both real and demo)"
            ),
            "values": {field: str(value) for field, value in prices.items()},
            "unusable": unusable,
            "field_meanings": {
                "futs_prpr": "현재가",
                "futs_prdy_clpr": "전일종가",
                "futs_sdpr": "기준가격 (시행세칙 제55조제1항제2호: 직전 거래일의 정산가격)",
                "futs_mxpr": "상한가",
                "futs_llam": "하한가",
            },
        },
    )
    if unusable:
        raise ProbeError(
            f"L1 {_PRICE_TR} returned no usable value for {', '.join(unusable)}. "
            "Design §5 requires all five fields positive; a zero or absent field "
            "is recorded, never substituted."
        )

    basis_is_settlement = prices["futs_sdpr"] != prices["futs_prdy_clpr"]
    run.measure(
        "l1_basis_price_distinguishable",
        {
            "futs_sdpr": str(prices["futs_sdpr"]),
            "futs_prdy_clpr": str(prices["futs_prdy_clpr"]),
            "differ": basis_is_settlement,
            "meaning": (
                "시행세칙 제55조제1항제2호 says 기준가격 is the previous trading "
                "day's SETTLEMENT price, not its close. When the two fields "
                "differ, this sample distinguishes them. When they are equal, "
                "the sample is simply uninformative on that question — equality "
                "is not evidence that the rule is wrong."
            ),
        },
    )

    corroboration = _corroborate_tick(output, tick, _L1_PRICE_FIELDS)
    run.measure("l1_tick_corroboration", corroboration)
    if not corroboration["corroborated"]:
        raise ProbeError(
            "L1 tick corroboration FAILED: the broker quoted "
            f"{corroboration['non_multiples']}, which are not multiples of the "
            f"registered tick {corroboration['tick_size_points']} "
            f"({tick.source}). The registry is CONTRADICTED; no band arithmetic "
            "may be done against a tick the venue's own quotes deny."
        )
    return prices


def _leg_l2(
    run: ProbeRun, prices: dict[str, Decimal], tick: Any, window: dict[str, Any]
) -> bool:
    """L2 — 제56조 arithmetic against the observed band. No network. Never raises.

    Design §5: a mismatch is REPORTED with the alternative stages recomputed. It
    is not an exception, because a 2/3단계 band outside the no-escalation window
    is a legitimate market state, not a harness defect.
    """
    report = band_stage_matches(
        sdpr=prices["futs_sdpr"],
        observed_upper=prices["futs_mxpr"],
        observed_lower=prices["futs_llam"],
        ticks={
            "rule_tick_0.05_kospi200_futures": RULE_TICK_POINTS,
            f"registry_tick_{tick.size}": Decimal(str(tick.size)),
        },
    )
    declared = band_expectation(
        prices["futs_sdpr"], ratio=RULE_RATIO_STAGES[0][1], tick=RULE_TICK_POINTS
    )
    stage1_rule_tick_matches = any(
        c["both_match"]
        for c in report["candidates"]
        if c["stage"] == 1 and c["tick_points"] == str(RULE_TICK_POINTS)
    )
    report["declared_expectation"] = declared
    report["declared_expectation_matches"] = stage1_rule_tick_matches
    report["declared_expectation_note"] = (
        "The declared expectation is design §4.1 L2 verbatim: 비율 0.08, 틱 0.05. "
        "It is the PASS criterion only for a sample inside the no-escalation "
        "window on a 코스피200선물 leaf."
    )
    report["registry_tick"] = {
        "tick_points": str(tick.size),
        "source": tick.source,
        "differs_from_rule_tick": Decimal(str(tick.size)) != RULE_TICK_POINTS,
    }
    run.measure("l2_band_rule_arithmetic", report)

    passed = bool(stage1_rule_tick_matches)
    if not passed:
        matched = report["matching_combinations"]
        run.measure(
            "l2_mismatch_record",
            {
                "recorded_not_interpreted": (
                    "The 8%/0.05 arithmetic did not reproduce the observed band. "
                    "Candidates that did are listed; if none did, 기준가격 may not "
                    "be the settlement price, or the rounding or the unit differs. "
                    "This probe records the fact and names the possibilities; it "
                    "does not choose between them."
                ),
                "matching_combinations": matched,
                "inside_no_escalation_window": window["inside_no_escalation_window"],
            },
        )
    return passed


def _leg_psbl(
    client: MockQueryClient,
    run: ProbeRun,
    *,
    leg: str,
    symbol: str,
    unit_price: Decimal,
    price_meaning: str,
    enforce_integral: bool,
) -> dict[str, Any]:
    """One ``VTTO5105R`` call (L3, L4 or L5). Records verbatim.

    Args:
        enforce_integral: L3 only. When the broker answers ``rt_cd=0``, the
            quantity fields must parse as exact non-negative integers or the leg
            raises. L4 and L5 are observation-only by design §5, so they pass
            ``False`` and transcribe whatever came back.
    """
    status, parsed, headers, _text, elapsed_ms = client.get(
        path=_PSBL_PATH,
        tr_id=_PSBL_TR,
        params=_psbl_params(client.creds, symbol, unit_price),
    )
    window = kst_sample_window(datetime.now(KST))
    record = _psbl_observation(status, parsed, headers, elapsed_ms)
    record["leg"] = leg
    record["tr_id"] = _PSBL_TR
    record["unit_price_sent"] = format(unit_price, "f")
    record["unit_price_meaning"] = price_meaning
    record["sampled_at_kst"] = window["sampled_at_kst"]
    record["answered"] = record["rt_cd"] == "0"
    run.observe(**record)

    if enforce_integral and record["answered"]:
        record["ord_psbl_qty"] = _integral_quantity(
            record["ord_psbl_qty_raw"], "ord_psbl_qty"
        )
        record["tot_psbl_qty"] = _integral_quantity(
            record["tot_psbl_qty_raw"], "tot_psbl_qty"
        )
    return record


# ---------------------------------------------------------------------------
# P-VL
# ---------------------------------------------------------------------------


def probe_pvl(args: argparse.Namespace) -> ProbeRun:
    """P-VL MARKET_INSTRUMENT_CONSTRAINTS — band semantics, GET-only, 모의투자.

    Five legs (design §4.1): L1 시세 fields, L2 제56조 arithmetic (offline),
    L3/L4/L5 주문가능 at the touch, at the lower limit and one tick above the
    upper limit. L1-L3 carry verdicts; L4 and L5 are observation-only.

    The probe closes band SEMANTICS on 모의투자. It does not and cannot close the
    structural 호가수량한도 — see this module's docstring and design §4.3. A
    reader who takes ``ord_psbl_qty`` for a venue limit has misread it: that
    number is derived from 예수금.
    """
    spec = get("P-VL")
    symbol = str(getattr(args, "symbol", "") or "").strip()
    if not symbol:
        raise ProbeError(
            "--symbol is required: the contract month the resident paper session "
            "is actually running (the leaf name under ~/.local/state/tos/"
            "paper-data/). There is no default — a literal here would silently "
            "probe a different month from the one under observation."
        )
    pace_s = float(getattr(args, "pace_s", DEFAULT_PACE_S))
    if pace_s < 0:
        raise ProbeError(f"--pace-s must be >= 0 (got {pace_s})")

    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live",
        environment=spec.environment,
        args=vars(args),
    )
    run.observe(
        read_only_attestation=(
            "GET-only against the allowlist in "
            "tools/broker_probes/probes_venue_limits.py::ALLOWLIST, on the mock "
            "host only (assert_mock_host). No order path exists in this module."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in ALLOWLIST],
    )
    run.measure(
        "confirm_gate",
        {
            "requires_confirm": False,
            "why": (
                "Design §4 registers P-VL requires_confirm=False. Runbook safety "
                "control #4 (docs/runbooks/kis-capability-probes.md:86) therefore "
                "does not gate this probe; the three structural controls that do "
                "are listed in structural_controls."
            ),
            "structural_controls": [
                "assert_read_only_call: GET + TR id + path, checked before the "
                "session is touched",
                "assert_mock_host on every URL, built from MOCK_BASE_URL",
                "assert_mock_trading_tr on the one /trading/ TR (모의 = V-prefixed)",
            ],
            "confirm_flag_was_passed": bool(getattr(args, "confirm", False)),
        },
    )
    run.measure(
        "cannot_establish",
        {
            "kis_quantity_limit": (
                "ord_psbl_qty is derived from 예수금/증거금, not from the venue "
                "limit (P-R5-PRE 2026-08-03: zero-deposit account reports 0). The "
                "2,000-contract 호가수량한도 (별표 17의2 제1호) and any lower "
                "member limit under 시행세칙 제61조제3항 are observable only by "
                "sending an order — outside this probe's GET-only scope."
            ),
            "stage_2_3_escalation": (
                "Escalation depends on a 기준종목 reaching its own limit; a probe "
                "cannot cause it. Observed or not observed, never induced."
            ),
            "runtime_band_supply": (
                "This probe observes band values. Wiring a band into "
                "VenueConstraintSnapshot is design §6, a separate decision."
            ),
        },
    )

    contract, tick, contract_record = resolve_smallest_contract(symbol)
    run.measure("resolved_contract", contract_record)
    run.measure(
        "symbol_vs_policy_product",
        {
            "resolved_product": contract_record["resolved_product"],
            "registry_tick_points": str(tick.size),
            "rule_tick_points_kospi200_futures": str(RULE_TICK_POINTS),
            "deployed_paper_policy_tick": (
                "config/tos_runtime/paper/venue_constraint_policy.yaml "
                "_model_view.shape_constraints.tick_size: 5 (= 0.05 at the ×100 "
                "integer scale)"
            ),
            "note": (
                "resolve_smallest_contract refuses any symbol that is not the "
                "smallest registered contract — a real-money rule this probe "
                "inherits by reusing it (design §4). The consequence is that "
                "P-VL can only probe the smallest leaf, whose 호가가격단위 may "
                "differ from the 0.05 of 코스피200선물거래 that design §2.1 and "
                "the deployed policy carry. That is recorded here, not resolved: "
                "the 2,000-contract value of 별표 17의2 제1호 belongs to "
                "코스피200선물거래, and which row of that 별표 governs the "
                "resolved product is an operator question, not a probe output."
            ),
        },
    )

    warn_shared_token_cache()
    creds = resolve_credentials("futures", is_real=False)
    run.credentials = creds.describe()
    require_account(creds)
    run.measure(
        "account_product_code_is_futures_03",
        {
            "matches": creds.acnt_prdt_cd == _FUTURES_PRODUCT_CODE,
            "expected": _FUTURES_PRODUCT_CODE,
            "source": (
                "P-R5-PRE 2026-08-03 — 선물옵션 상품코드 is 03; the account number "
                "itself is never recorded, only this comparison"
            ),
        },
    )

    import requests

    from shared.kis.auth import KISAuthManager

    cfg = build_auth_config(creds, probe_token_cache_dir(args.token_cache_dir))
    auth = KISAuthManager(cfg, use_singleton=False)
    session = requests.Session()
    client = MockQueryClient(creds, auth, session, pace_s=pace_s)

    verdicts: dict[str, str] = {}
    try:
        prices = _leg_l1(client, run, symbol, tick)
        verdicts["L1"] = VERDICT_PASS

        window = run.measurements["l1_sample_window"]
        verdicts["L2"] = (
            VERDICT_PASS if _leg_l2(run, prices, tick, window) else VERDICT_FAIL
        )

        l3 = _leg_psbl(
            client,
            run,
            leg="L3",
            symbol=symbol,
            unit_price=prices["futs_prpr"],
            price_meaning="futs_prpr (현재가) — the touch",
            enforce_integral=True,
        )
        run.measure("l3_psbl_at_touch", l3)
        if not l3["answered"]:
            verdicts["L3"] = VERDICT_FAIL
            run.measure(
                "l3_refusal_record",
                {
                    "recorded_not_interpreted": (
                        "The query was refused, so no quantity was observed. A "
                        "refusal is NOT 'zero available' — reading it that way is "
                        "the P-CA held=0 error."
                    ),
                    "rt_cd": l3["rt_cd"],
                    "msg_cd": l3["msg_cd"],
                    "msg1": l3["msg1"],
                },
            )
        elif l3.get("ord_psbl_qty", 0) >= 1:
            verdicts["L3"] = VERDICT_PASS
        else:
            verdicts["L3"] = VERDICT_FAIL
            run.measure(
                "l3_zero_quantity_record",
                {
                    "ord_psbl_qty": l3.get("ord_psbl_qty"),
                    "recorded_not_interpreted": (
                        "Zero order-available quantity at the touch means 예수금 "
                        "0 or a margin constraint on this account. It says nothing "
                        "about the venue's structural quantity limit."
                    ),
                },
            )

        l4 = _leg_psbl(
            client,
            run,
            leg="L4",
            symbol=symbol,
            unit_price=prices["futs_llam"],
            price_meaning="futs_llam (하한가) — the lower band edge, inclusive?",
            enforce_integral=False,
        )
        run.measure(
            "l4_psbl_at_lower_limit",
            {
                **l4,
                "verdict": VERDICT_RECORDED,
                "why_no_verdict": (
                    "Design §5: L4 is observation only. Whether the broker admits "
                    "the band edge is recorded; no PASS/FAIL is defined because "
                    "neither answer contradicts anything this probe asserts."
                ),
            },
        )
        verdicts["L4"] = VERDICT_RECORDED

        l5_price = prices["futs_mxpr"] + Decimal(str(tick.size))
        l5 = _leg_psbl(
            client,
            run,
            leg="L5",
            symbol=symbol,
            unit_price=l5_price,
            price_meaning=(
                f"futs_mxpr + 1 tick ({tick.size}) — one tick ABOVE the upper band "
                "edge, i.e. outside the band"
            ),
            enforce_integral=False,
        )
        run.measure(
            "l5_psbl_above_upper_limit",
            {
                **l5,
                "verdict": VERDICT_RECORDED,
                "price_derivation": {
                    "futs_mxpr": str(prices["futs_mxpr"]),
                    "tick_added": str(tick.size),
                    "tick_source": tick.source,
                    "design_literal": (
                        "design §4.1 L5 writes 'futs_mxpr + 0.05 (상한가 + 1틱)'. "
                        "The 1-tick intent is honoured with the tick registered "
                        "for THIS symbol; 0.05 is 코스피200선물거래's unit."
                    ),
                },
                "why_no_verdict": (
                    "Design §5: L5's refusal or acceptance is recorded verbatim "
                    "and never interpreted. An rt_cd != 0 here is an observation, "
                    "not a failure of this probe — the question of whether the "
                    "GET surface validates the band is exactly what is open."
                ),
            },
        )
        verdicts["L5"] = VERDICT_RECORDED
    finally:
        run.measure("leg_verdicts", verdicts)
        session.close()

    run.measure(
        "p02_disposition_proposal",
        {
            "field": (
                "capabilities.market_and_instrument_constraints."
                "price_band_tick_lot_and_quantity_semantics"
            ),
            "current": "UNKNOWN",
            "proposed": "PARTIAL",
            "established_if_l1_l2_pass": [
                "band semantics on 모의투자: 기준가격 field identity, the stage "
                "ratio that reproduces the band, and the 내림/올림 rounding",
                "tick: every broker-quoted price is a multiple of the registered "
                "tick (corroboration, not a broker-published tick value)",
            ],
            "still_unestablished": [
                "the structural 호가수량한도 (별표 17의2) — regulation value only, "
                "broker-side limit unconfirmed",
                "any member limit KIS sets under 시행세칙 제61조제3항",
                "2/3단계 확대 의미론",
                "the runtime supply path for a band (design §6)",
            ],
            "rule": (
                "Design §5: do not flip UNKNOWN to VERIFIED in one word. Record "
                "PARTIAL and enumerate the unestablished axes."
            ),
        },
    )
    return run


def add_venue_limits_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pace-s",
        type=float,
        default=DEFAULT_PACE_S,
        help=(
            "Seconds between calls. Default 1.1 s is P-13's measured clean query "
            "rate (artifact P-13-20260729T063120Z)."
        ),
    )


def write(run: ProbeRun, spec: ProbeSpec, args: argparse.Namespace) -> None:
    run.write(spec, resolve_out_dir(args))
