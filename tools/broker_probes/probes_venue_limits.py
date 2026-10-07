"""P-VL — venue price-band / quantity limits, GET-only on 모의투자 (MOCK_VTS).

Design: ``docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md``
**v2** (PR #879 head ``de3c7e98``) — §2.0 (which product's 별표 row applies),
§4 (legs, timing, artifact), §5 (verdicts). CP-3 decision 9 picked the KRX
rulebook as the PRIMARY source for ``max_quantity``; this probe is the
**corroboration**, not the source.

v2 corrected two things this module follows: the deployed product is
미니코스피200선물 (``A056xx``), so the 별표 17의2 row and the 호가가격단위 are the
mini ones; and the probe is ``requires_confirm=True`` like every other networked
probe. Rule values are bound to the committed evidence texts under
:data:`_EVIDENCE_DIR`, not to a web summary.

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
  zero-deposit account reports 0). The 호가수량한도 of 별표 17의2 and any lower
  member limit KIS sets under 시행세칙 제61조제3항 are visible only by SENDING an
  order and reading the rejection. That is outside this probe's GET-only scope
  (design §7 ④ keeps it as a separate P-VL-2 option). The rulebook rows are
  recorded as CONTEXT in :data:`KRX_QUANTITY_LIMIT_BY_PREFIX` and decide nothing.
* **2/3단계 확대 의미론.** Escalation depends on a 기준종목 touching its own
  limit; a probe cannot cause it. Observed or not observed, never induced.
* **The runtime supply of a band.** This probe observes values; wiring a band
  into ``VenueConstraintSnapshot`` is design §6, a separate decision.

Safety model. Read-only by construction and mock-only by construction, both
structural rather than documentary:

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
4. ``--confirm`` gates broker contact, as it does for every networked probe in
   this register including the read-only ones (P-16, P-13).

**This module imports no order-capable module.** ``probes_order`` and
``probes_real_order`` are both absent from its graph, which
``tests/tools/test_broker_probes_pvl.py::test_module_does_not_import_order_capable_modules``
asserts against this file's AST — the same canary
``tests/tools/test_broker_probes_ca.py`` carries. The two pure helpers this
probe reuses were relocated to the stdlib-only
:mod:`tools.broker_probes._tick_math` for exactly that reason; importing them
from ``probes_real_order`` would have pulled both order paths in, because that
module imports ``probes_order`` at module level.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from datetime import datetime
from datetime import time as clock_time
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from tools.broker_probes._tick_math import corroborate_tick, decimal_field
from tools.broker_probes.common import (
    MOCK_BASE_URL,
    ProbeError,
    ProbeRun,
    ReadOnlyCall,
    assert_mock_host,
    assert_mock_trading_tr,
    assert_read_only_call,
    build_auth_config,
    dry_run_banner,
    probe_token_cache_dir,
    require_account,
    resolve_credentials,
    resolve_out_dir,
    rt_cd_of,
    warn_shared_token_cache,
)
from tools.broker_probes.registry import ProbeSpec, get

KST = ZoneInfo("Asia/Seoul")

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Default pause between calls, in seconds.
#:
#: Measured, not guessed: P-13 (artifact ``P-13-20260729T063120Z``) bracketed the
#: mock account's query class at clean 1.0 rps / throttled 2.0 rps (``EGW00201``).
#: 1.1 s sits just above the measured clean rate. Deliberately a local constant
#: rather than an import of ``probes_order.DEFAULT_PACE_S`` — importing that
#: module would put order-submitting code in this module's graph and destroy the
#: structural read-only property this file exists to guarantee. ``probes_balance``
#: and ``probes_ca`` keep their own copies for the same reason.
DEFAULT_PACE_S = 1.1

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
#: ``VTTO5105R`` for ``demo``; required params ``CANO`` / ``ACNT_PRDT_CD`` /
#: ``PDNO`` / ``SLL_BUY_DVSN_CD`` / ``UNIT_PRICE`` / ``ORD_DVSN_CD``. Only the
#: DEMO id appears here: this probe is MOCK_VTS, and that wrapper's REAL id is
#: deliberately absent from this file so it cannot be spelled into the allowlist
#: by a copy-paste. ``tests/tools/test_broker_probes_pvl.py`` asserts that
#: absence over the whole file text — which is why this comment names the twin
#: by prefix, not by id.
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
# Instrument resolution — config, never a literal
# ---------------------------------------------------------------------------

#: ``futures_contract_spec`` lives here. Read through
#: ``shared.instruments.contract_spec``, the same registry the runtime uses, so
#: the tick this probe corroborates is the tick the runtime would trade on. A
#: local path constant rather than ``probes_order._EXECUTION_CONFIG``: that
#: module is order-capable and must stay out of this graph.
_EXECUTION_CONFIG = _REPO_ROOT / "config" / "execution.yaml"

#: The deployed paper venue policy, read ONLY to record its ``tick_size`` beside
#: the registry's and report whether they agree. The probe never treats this
#: value as the truth — see :func:`resolve_instrument`.
_PAPER_VENUE_POLICY = (
    _REPO_ROOT / "config" / "tos_runtime" / "paper" / "venue_constraint_policy.yaml"
)

#: The paper policy states its own price scale in its header: "tick_size 5 =
#: 0.05 index points at the ×100 integer price scale"
#: (``config/tos_runtime/paper/venue_constraint_policy.yaml:11-13``). The kernel
#: treats venue ints as opaque-scaled
#: (``tos/runtime/src/tos_runtime/venue/_venue_policy_loader.py:185-191``), so
#: there is no named constant upstream to import — this is the policy file's own
#: declared convention, cited rather than assumed.
_POLICY_PRICE_SCALE = Decimal(100)

#: Accepted ``--symbol`` families, by prefix. ``A05`` is 미니코스피200선물거래 and
#: is what the resident paper session runs; ``101``/``A01`` are
#: 코스피200선물거래 (continuous-backtest and live front-month codes
#: respectively, both registered on ``kospi200_full`` in
#: ``config/execution.yaml``). Any other prefix is refused: this probe's TRs and
#: its 별표 rows are specific to KOSPI200 index futures.
_MINI_PREFIXES: tuple[str, ...] = ("A05",)
_FULL_PREFIXES: tuple[str, ...] = ("101", "A01")

# ---------------------------------------------------------------------------
# Rule constants — KRX 파생상품시장 업무규정 시행세칙 제164차 (2026-07-06 시행)
# ---------------------------------------------------------------------------

#: Committed parsed-text evidence for every rule value below (design v2 §2.3).
#: The HWP binaries are not committed; the README in this directory carries the
#: 판·bookid·sha256 binding and the 법무포털 reproduction recipe. Line references
#: in the constants point into these files, so a reviewer re-derives a number
#: without trusting this module's prose.
_EVIDENCE_DIR = "docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/"

#: 호가수량한도 (1 호가당 최대 계약 수) per product — 업무규정 제71조 → 시행세칙
#: 제61조제1항 → **별표 17의2 제1호** (별표 최종개정 2025-05-29). CONTEXT ONLY:
#: no leg passes or fails on these numbers, and the probe cannot observe them
#: (see this module's docstring). They are recorded so the artifact names WHICH
#: row governs ``--symbol`` instead of leaving a reader to assume the 2,000 of
#: the full-size contract applies to a mini leaf.
#:
#: Two 단서 travel with every value (design §2.2): 회원(증권사) may set a LOWER
#: limit under 시행세칙 제61조제3항, and 거래소 may change these for market
#: management (제61조제1항 단서). 누적호가수량한도 (제61조제2항) is a DIFFERENT
#: limit applying only to 회원 자기거래계좌·사후위탁증거금계좌, never to a
#: 위탁계좌 like paper/모의 — it is deliberately absent here.
_QUANTITY_LIMIT_CAVEATS = (
    "회원은 시행세칙 제61조제3항으로 더 낮게 정할 수 있고, 거래소는 제61조제1항 "
    "단서로 변경할 수 있다. 공표 규정값이지 불변식이 아니다. 누적호가수량한도"
    "(제61조제2항)는 위탁계좌에 적용되지 않으므로 여기 없다."
)
_QUANTITY_LIMIT_CHAIN = (
    "업무규정 제71조 → 시행세칙 제61조제1항 → 별표 17의2 제1호 "
    "(별표 최종개정 2025-05-29)"
)

KRX_QUANTITY_LIMIT_BY_PREFIX: dict[str, dict[str, Any]] = {
    **{
        prefix: {
            "product": "미니코스피200선물거래",
            "regular_session_contracts": 10000,
            "night_session_contracts": 5000,
            # 별표 17의2 제1호 의 괄호 값 — 해당 상품이 유동성관리상품으로
            # 지정된 경우에만 적용된다. 지정 여부는 이 프로브가 관측하지 않는다.
            "liquidity_managed_regular_contracts": 1000,
            "liquidity_managed_night_contracts": 500,
            "source": _QUANTITY_LIMIT_CHAIN,
            "evidence": (
                f"{_EVIDENCE_DIR}byeolpyo17-2_order_quantity_limits.txt:41-45 "
                "(미니코스피200선물거래 행) · 괄호 의미 비고 :118"
            ),
            "caveats": _QUANTITY_LIMIT_CAVEATS,
        }
        for prefix in _MINI_PREFIXES
    },
    **{
        prefix: {
            "product": "코스피200선물거래",
            "regular_session_contracts": 2000,
            "night_session_contracts": 1000,
            "liquidity_managed_regular_contracts": 200,
            "liquidity_managed_night_contracts": 100,
            "source": _QUANTITY_LIMIT_CHAIN,
            "evidence": (
                f"{_EVIDENCE_DIR}byeolpyo17-2_order_quantity_limits.txt:29-33 "
                "(코스피200선물거래 행) · 괄호 의미 비고 :118"
            ),
            "caveats": _QUANTITY_LIMIT_CAVEATS,
        }
        for prefix in _FULL_PREFIXES
    },
}

#: 호가가격단위's article, per product — 시행세칙 제4조의9: 제1호 is the full
#: contract's 0.05, 제2호 the mini's 0.02 (design v2 §2.1). Recorded so the
#: artifact cites the 호 that actually governs ``--symbol`` rather than the one
#: a reader might assume. The VALUE still comes from the repo registry, never
#: from this table — these are citations, not a second source of truth.
_TICK_ARTICLE_BY_PREFIX: dict[str, str] = {
    **dict.fromkeys(
        _MINI_PREFIXES, "시행세칙 제4조의9제2호 (미니 0.02 포인트, 최종개정 2024-11-01)"
    ),
    **dict.fromkeys(
        _FULL_PREFIXES, "시행세칙 제4조의9제1호 (전체 0.05 포인트, 최종개정 2024-11-01)"
    ),
}

#: 가격제한비율, 주가지수선물거래 — 업무규정 제70조 → 시행세칙 제56조·제56조의2 →
#: **별표 14 제1호** (별표 최종개정 2025-05-29): 1단계 8% · 2단계 15% · 3단계 20%.
#: One table for both products: 별표 14 제1호 is keyed on 주가지수선물거래, which
#: covers 코스피200선물거래 and 미니코스피200선물거래 alike — and 제56조의2
#: 제2항제1호 단서 applies the same ratios to the mini (design v2 §2.1).
#: Evidence: ``byeolpyo14_price_limit_ratios.txt:19-25`` under
#: :data:`_EVIDENCE_DIR`.
KRX_PRICE_LIMIT_STAGES: tuple[tuple[int, Decimal], ...] = (
    (1, Decimal("0.08")),
    (2, Decimal("0.15")),
    (3, Decimal("0.20")),
)

#: 상·하한가 산출 — 시행세칙 제56조제1항·제2항 단서.
_RULE_BAND_ROUNDING = (
    "시행세칙 제56조제1항·제2항 단서 — 상한가 = 기준가격 + 기준가격×비율 을 "
    "호가가격단위로 내림, 하한가 = 기준가격 − 기준가격×비율 을 올림"
)

#: 기준가격 — 시행세칙 제55조제1항제2호: 직전 거래일의 **정산가격**, not the
#: close. 제55조제4항 then adjusts it to the NEAREST 호가가격단위 (the higher one
#: on a tie), which is why a 기준가격 that is itself off-grid would already be a
#: finding rather than an input (design v2 §2.1).
_RULE_BASIS_PRICE = (
    "시행세칙 제55조제1항제2호 — 기준가격은 직전 거래일의 정산가격(규정 제96조); "
    "제55조제4항으로 호가가격단위에 가장 가까운 값(동일하면 높은 쪽)으로 조정"
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


@dataclass(frozen=True)
class VenueTick:
    """A price increment with the evidence that established it.

    Structurally a :class:`tools.broker_probes._tick_math.TickLike`, which is
    the contract :func:`~tools.broker_probes._tick_math.corroborate_tick`
    accepts. Deliberately NOT ``probes_order.Tick``: naming that class would
    mean importing an order-capable module, which is the whole point of the
    ``_tick_math`` relocation. The Protocol exists so each module can carry its
    own tick without that import.
    """

    size: Decimal
    source: str


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
        "basis_price_rule": _RULE_BASIS_PRICE,
    }


def band_stage_matches(
    *,
    sdpr: Decimal,
    observed_upper: Decimal,
    observed_lower: Decimal,
    tick: Decimal,
) -> dict[str, Any]:
    """Which 별표 14 stage ratio reproduces the observed band, at ``tick``.

    Design §5 L2 licenses exactly this: on a mismatch, recompute at 15%/20% and
    record *which stage matched*, with no interpretation. The tick is a single
    value because it is RESOLVED, not guessed — ``--symbol``'s own 호가가격단위
    from ``config/execution.yaml`` (see :func:`resolve_instrument`).
    """
    candidates: list[dict[str, Any]] = []
    for stage, ratio in KRX_PRICE_LIMIT_STAGES:
        expectation = band_expectation(sdpr, ratio=ratio, tick=tick)
        upper_ok = Decimal(expectation["expected_upper"]) == observed_upper
        lower_ok = Decimal(expectation["expected_lower"]) == observed_lower
        candidates.append(
            {
                "stage": stage,
                **expectation,
                "upper_matches": upper_ok,
                "lower_matches": lower_ok,
                "both_match": upper_ok and lower_ok,
            }
        )
    matched = [c["stage"] for c in candidates if c["both_match"]]
    return {
        "observed_upper": str(observed_upper),
        "observed_lower": str(observed_lower),
        "tick_points": str(tick),
        "candidates": candidates,
        "matching_stages": matched,
        "any_match": bool(matched),
        "source": (
            "ratios: 별표 14 제1호 (주가지수선물거래 1/2/3단계 8/15/20%) · "
            f"rounding: {_RULE_BAND_ROUNDING} · basis: {_RULE_BASIS_PRICE}"
        ),
        "not_an_interpretation": (
            "A matching stage records WHICH arithmetic reproduces the broker's "
            "numbers. It does not establish that the venue used that stage, and a "
            "non-match does not establish that the rule is wrong — 기준가격 or the "
            "rounding could differ instead."
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
# Instrument resolution
# ---------------------------------------------------------------------------


def _symbol_prefix(symbol: str) -> str:
    """The accepted KOSPI200-futures prefix ``symbol`` starts with, or refuse.

    Fail-closed on an unknown family: this probe's TRs are 선물옵션 and its
    rulebook rows are 주가지수선물거래 rows, so a symbol from any other product
    would be measured against the wrong 별표 row with no sign that it happened.
    """
    for prefix in (*_MINI_PREFIXES, *_FULL_PREFIXES):
        if symbol.startswith(prefix):
            return prefix
    raise ProbeError(
        f"--symbol {symbol!r} is not a KOSPI200 index-futures code. Accepted "
        f"prefixes: {', '.join((*_MINI_PREFIXES, *_FULL_PREFIXES))} "
        "(mini / full-size). This probe's TRs and its 별표 17의2 · 별표 14 rows "
        "are specific to that product family."
    )


def _policy_tick_record() -> dict[str, Any]:
    """The deployed paper policy's ``tick_size``, recorded — never the truth.

    Read so the artifact can state whether the policy and the contract registry
    agree about ``--symbol``'s 호가가격단위. As of 2026-10-08 they DISAGREE for a
    mini leaf: the policy carries 5 (= 0.05, the full-size unit) while the
    registry carries 0.02. Surfacing that is the probe's job; resolving it is
    the operator's.
    """
    import yaml

    raw = yaml.safe_load(_PAPER_VENUE_POLICY.read_text(encoding="utf-8"))
    shape = ((raw or {}).get("_model_view") or {}).get("shape_constraints") or {}
    value = decimal_field(shape, "tick_size")
    return {
        "policy_path": str(_PAPER_VENUE_POLICY.relative_to(_REPO_ROOT)),
        "tick_size_scaled_int": shape.get("tick_size"),
        "price_scale": str(_POLICY_PRICE_SCALE),
        "scale_source": (
            "the policy file's own header — 'tick_size 5 = 0.05 index points at "
            "the ×100 integer price scale' (venue_constraint_policy.yaml:11-13)"
        ),
        "tick_points": (
            str(value / _POLICY_PRICE_SCALE) if value is not None else None
        ),
    }


def resolve_instrument(symbol: str) -> tuple[VenueTick, dict[str, Any]]:
    """Resolve ``--symbol``'s tick from config and record every comparison.

    The tick comes from ``config/execution.yaml::futures_contract_spec`` through
    ``shared.instruments.contract_spec`` — the same registry the runtime reads,
    matched by ``symbol_prefix``. It is NOT taken from the deployed paper
    policy's ``tick_size`` and NOT a literal: a mini leaf's 호가가격단위 is 0.02
    while the policy carries the full-size 0.05, and a probe that assumed either
    one would manufacture a band mismatch or miss a real one.

    Returns:
        The resolved tick, and a record carrying the registry value, the policy
        value, ``tick_registry_matches_policy``, and the 별표 17의2 row for the
        matched prefix.

    Raises:
        ProbeError: the prefix is not a KOSPI200 index-futures family, the
            registry has no spec for it, or the registered tick is non-positive.
    """
    from shared.instruments.contract_spec import (
        ContractSpecRegistry,
        resolve_contract_spec,
    )

    prefix = _symbol_prefix(symbol)
    try:
        registry = ContractSpecRegistry.from_yaml(str(_EXECUTION_CONFIG))
        spec = resolve_contract_spec(symbol, registry)
    except Exception as exc:  # noqa: BLE001 — an unresolved instrument refuses
        raise ProbeError(
            f"no contract spec for --symbol {symbol} in {_EXECUTION_CONFIG}: "
            f"{exc}. Register the prefix rather than hardcoding a tick."
        ) from exc

    size = Decimal(str(spec.tick_size_points))
    if size <= 0:
        raise ProbeError(
            f"tick_size_points for {spec.name} is {size}; a non-positive tick "
            "cannot be corroborated against."
        )
    source = (
        f"config/execution.yaml::futures_contract_spec.{spec.name}"
        f".tick_size_points (matched symbol_prefix {spec.symbol_prefix!r})"
    )
    tick = VenueTick(size=size, source=source)

    policy = _policy_tick_record()
    policy_points = policy.get("tick_points")
    record = {
        "symbol": symbol,
        "matched_prefix": prefix,
        "resolved_product": spec.name,
        "registry_tick_points": str(size),
        "registry_tick_source": source,
        "paper_policy_tick": policy,
        "registry_tick_rule_article": _TICK_ARTICLE_BY_PREFIX[prefix],
        "tick_registry_matches_policy": (
            policy_points is not None and Decimal(policy_points) == size
        ),
        "disagreement_note": (
            "A False here is an OBSERVATION, not a probe failure. The registry "
            "tick governs this probe's arithmetic because it is keyed on "
            "--symbol's own product; the policy's value is recorded beside it so "
            "the drift is visible. Which one the deployed policy should carry is "
            "an operator decision, not a probe output."
        ),
        "why_the_drift_matters_later": (
            "Design v2 §2.0 names the consequence: today the band is null so "
            "step 3 is UNKNOWN and the mismatch is masked, but the moment a band "
            "arrives (design §6) tos/src/tos/venue/predicates.py would judge a "
            "mini leaf's NORMAL 0.02-grid quotes INADMISSIBLE against a 0.05 "
            "policy tick. Recorded so the drift is not read as cosmetic; the "
            "disposition is an operator item on the §6 wave, not this probe's."
        ),
        "krx_quantity_limit_row": KRX_QUANTITY_LIMIT_BY_PREFIX[prefix],
        "krx_quantity_limit_is_context_only": (
            "This row is CONTEXT. No leg passes or fails on it and this probe "
            "cannot observe it — ord_psbl_qty is 예수금-derived. It is recorded so "
            "a reader sees WHICH 별표 17의2 row governs --symbol instead of "
            "assuming the full-size contract's number applies to a mini leaf."
        ),
    }
    return tick, record


# ---------------------------------------------------------------------------
# Transport — the ONLY one in this module
# ---------------------------------------------------------------------------


class MockQueryClient:
    """GET-only client pinned to the 모의투자 host. No order path exists on it.

    Deliberately not routed through
    :func:`~tools.broker_probes.common.http_json`: that helper drops the
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
    """The ``VTTO5105R`` fields design §4.1 records, plus the answer code.

    The keys are the design table's own names — ``ord_psbl_qty`` /
    ``tot_psbl_qty`` / ``bass_idx`` / ``rt_cd`` / ``msg_cd`` / ``msg1`` — so a
    reviewer reading §4.1 beside the artifact matches them one to one. Their
    values are what the broker sent, UNPARSED: a refusal is transcribed, not
    classified. P-CA's lesson is the reason — reading ``held=0`` as "flat" when
    the query had been refused cost that campaign a whole observation.

    L3 additionally publishes ``ord_psbl_qty_int`` / ``tot_psbl_qty_int``
    (see :func:`_integral_quantity`). Those are DERIVED, which is why they carry
    a different name instead of overwriting the transcript.
    """
    output = parsed.get("output")
    output = output if isinstance(output, dict) else {}
    return {
        "http_status": status,
        "rt_cd": rt_cd_of(parsed),
        "msg_cd": str(parsed.get("msg_cd") or ""),
        "msg1": str(parsed.get("msg1") or "").strip(),
        "ord_psbl_qty": output.get("ord_psbl_qty"),
        "tot_psbl_qty": output.get("tot_psbl_qty"),
        "bass_idx": output.get("bass_idx"),
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
    value = decimal_field({field: raw}, field)
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
    client: MockQueryClient, run: ProbeRun, symbol: str, tick: VenueTick
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
        value = decimal_field(output, field)
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
                "futs_sdpr": f"기준가격 ({_RULE_BASIS_PRICE})",
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

    run.measure(
        "l1_basis_price_distinguishable",
        {
            "futs_sdpr": str(prices["futs_sdpr"]),
            "futs_prdy_clpr": str(prices["futs_prdy_clpr"]),
            "differ": prices["futs_sdpr"] != prices["futs_prdy_clpr"],
            "meaning": (
                f"{_RULE_BASIS_PRICE}, not its close. When the two fields differ, "
                "this sample distinguishes them. When they are equal, the sample "
                "is simply uninformative on that question — equality is not "
                "evidence that the rule is wrong."
            ),
        },
    )

    corroboration = corroborate_tick(output, tick, _L1_PRICE_FIELDS)
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
    run: ProbeRun, prices: dict[str, Decimal], tick: VenueTick, window: dict[str, Any]
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
        tick=tick.size,
    )
    stage1, stage1_ratio = KRX_PRICE_LIMIT_STAGES[0]
    report["declared_expectation"] = band_expectation(
        prices["futs_sdpr"], ratio=stage1_ratio, tick=tick.size
    )
    passed = stage1 in report["matching_stages"]
    report["declared_expectation_matches"] = passed
    report["declared_expectation_note"] = (
        "The declared expectation is design §4.1 L2: 1단계 비율 8% at --symbol's "
        "own 호가가격단위. It is the PASS criterion, and it is the DETERMINED "
        "expectation only for a sample inside the no-escalation window."
    )
    report["tick_provenance"] = tick.source
    run.measure("l2_band_rule_arithmetic", report)

    if not passed:
        run.measure(
            "l2_mismatch_record",
            {
                "recorded_not_interpreted": (
                    "The 1단계 8% arithmetic did not reproduce the observed band. "
                    "Stages that did are listed; if none did, 기준가격 may not be "
                    "the settlement price, or the rounding or the unit differs. "
                    "This probe records the fact and names the possibilities; it "
                    "does not choose between them."
                ),
                "matching_stages": report["matching_stages"],
                "tick_points": str(tick.size),
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
        record["ord_psbl_qty_int"] = _integral_quantity(
            record["ord_psbl_qty"], "ord_psbl_qty"
        )
        record["tot_psbl_qty_int"] = _integral_quantity(
            record["tot_psbl_qty"], "tot_psbl_qty"
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
    # ``--asset`` is a COMMON argument, so ``--asset stock`` parses fine and
    # would otherwise be ignored: every TR below is 선물옵션 and the credentials
    # are resolved as futures unconditionally. Silently honouring the futures
    # account under a stock flag is the kind of mismatch that makes an artifact
    # lie about what it measured, so refuse it instead.
    asset = str(getattr(args, "asset", "futures") or "futures").strip().lower()
    if asset != "futures":
        raise ProbeError(
            f"--asset {asset!r} is not available for P-VL: every TR here is "
            "선물옵션 (FHMIF10000000 / VTTO5105R) and the credentials resolve "
            "as futures. Re-run with --asset futures."
        )

    run = ProbeRun(
        probe_id=spec.probe_id,
        title=spec.title,
        mode="live" if args.confirm else "dry-run",
        environment=spec.environment,
        args=vars(args),
    )
    run.observe(
        read_only_attestation=(
            "GET-only against the allowlist in "
            "tools/broker_probes/probes_venue_limits.py::ALLOWLIST, on the mock "
            "host only (assert_mock_host). No order path exists in this module "
            "and it imports no order-capable module."
        ),
        allowlist=[{"tr_id": e.tr_id, "path": e.path} for e in ALLOWLIST],
    )
    run.measure(
        "structural_controls",
        [
            "assert_read_only_call: GET + TR id + path, checked before the "
            "session is touched, so a refused call opens no socket",
            "assert_mock_host on every URL, built from MOCK_BASE_URL",
            "assert_mock_trading_tr on the one /trading/ TR (모의 = V-prefixed)",
            "--confirm gates broker contact (runbook safety control #4), as it "
            "does for every networked probe including read-only ones",
            "no order-capable module in this module's import graph",
        ],
    )
    run.measure(
        "cannot_establish",
        {
            "kis_quantity_limit": (
                "ord_psbl_qty is derived from 예수금/증거금, not from the venue "
                "limit (P-R5-PRE 2026-08-03: zero-deposit account reports 0). The "
                "호가수량한도 of 별표 17의2 and any lower member limit under "
                "시행세칙 제61조제3항 are observable only by sending an order — "
                "outside this probe's GET-only scope. The rulebook row for "
                "--symbol is recorded as CONTEXT and decides nothing."
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

    tick, instrument = resolve_instrument(symbol)
    run.measure("resolved_instrument", instrument)

    warn_shared_token_cache()
    creds = resolve_credentials("futures", is_real=False)
    run.credentials = creds.describe()

    if not args.confirm:
        dry_run_banner(spec)
        run.observe(
            would_send=(
                f"5 read-only GETs on the mock host for {symbol}: one "
                f"{_PRICE_TR} 시세 call, then three {_PSBL_TR} 주문가능 calls at "
                f"the touch, at 하한가, and at 상한가 + one tick ({tick.size}). "
                "L2 is offline arithmetic and sends nothing."
            ),
            resolved_tick_points=str(tick.size),
            resolved_tick_source=tick.source,
        )
        return run

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
        elif l3["ord_psbl_qty_int"] >= 1:
            # Not ``l3["ord_psbl_qty"]``: that key holds the broker's own
            # UNPARSED string, so comparing it to 1 would be a type error on a
            # good answer and a string comparison on a bad one. The verdict
            # reads the value ``_integral_quantity`` already proved is an exact
            # contract count. Not ``.get(..., 0)`` either — a default would turn
            # a missing key into "zero available", the P-CA error in a new hat;
            # the key is guaranteed present because ``answered`` is true here.
            verdicts["L3"] = VERDICT_PASS
        else:
            verdicts["L3"] = VERDICT_FAIL
            run.measure(
                "l3_zero_quantity_record",
                {
                    "ord_psbl_qty": l3["ord_psbl_qty_int"],
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

        l5_price = prices["futs_mxpr"] + tick.size
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
                    "rule": (
                        "design §4.1 L5 asks for 상한가 + 1틱. The tick is the one "
                        "registered for THIS symbol, not a literal: a mini leaf's "
                        "호가가격단위 is not the full-size contract's."
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
