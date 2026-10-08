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

* **KIS 측 호가수량한도.** ``VTTO5105R``'s ``ord_psbl_qty`` is 주문가능수량 per
  the official spec: a function of 예수금·증거금 **and of that leg's own price,
  side and order-type parameters** — ``probes_real_order.py``'s
  :data:`_ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION` names where that is
  written down: "reasons that are about the parameters and not the account". ⚠ **No ``ord_psbl_qty``
  observation exists in this repo yet**: P-R5-PRE's 2026-08-03 run aborted on the
  deposit leg (``CTRP6550R`` ``ord_psbl_cash``/``ord_psbl_tota`` = 0) **before**
  that leg ran (``P-R5-PRE-20260803T002732Z.json``), so nothing here may cite it
  for what a zero 주문가능수량 means. The structural cap of 별표 17의2 and any
  lower member limit under 시행세칙 제61조제3항 are visible only by SENDING an
  order and reading the rejection — outside this probe's GET-only scope (design
  v2 §4.3 / §7 ④ keep it as a separate P-VL-2 option). The rulebook rows are
  recorded as CONTEXT in :data:`KRX_PREFIX_TABLE` and decide nothing.
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
``tests/tools/test_broker_probes_ca.py`` carries. Both are order-capable:
``probes_order`` POSTs 모의 orders for the seven ``emits_orders=True`` specs, and
``probes_real_order`` is the only module here that can place a **REAL-money**
order. The two pure helpers this probe reuses were relocated to the stdlib-only
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

#: Where the repo writes down that a zero 주문가능수량 can be about the LEG's
#: parameters rather than the account. SYMBOL-anchored on purpose: the first
#: draft of this module cited ``probes_real_order.py:1651-1658`` and **this PR
#: staled its own citation** by relocating two helpers out of that file, moving
#: the block 34 lines up. A function name survives edits above it; a line range
#: does not. ``tests/tools/test_broker_probes_pvl.py`` locates the quoted
#: sentence inside that function and fails if it moves OUT of it, so the anchor
#: cannot rot silently either.
_ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION = (
    "probes_real_order.py::_preflight_instrument_state, the 'interpretation' key "
    "— \"this leg's own parameters (price, side, order type) could produce a 0 "
    'for reasons that are about the parameters and not the account"'
)

#: Committed parsed-text evidence for every rule value below (design v2 §2.3).
#: The HWP binaries are not committed; the README in this directory carries the
#: 판·bookid·sha256 binding and the 법무포털 reproduction recipe. Line references
#: in the table point into these files, so a reviewer re-derives a number
#: without trusting this module's prose.
_EVIDENCE_DIR = "docs/broker-profiles/evidence/2026-10-08-krx-venue-limits/"

#: The ONE table keyed by ``--symbol`` prefix. Every per-product fact lives here
#: — the registry product name, the 별표 17의2 row, and the 호가가격단위's 호 —
#: because the review found the previous shape (three dicts side by side) could
#: drift silently: move ``A05`` off ``kospi200_mini`` in ``config/execution.yaml``
#: and the artifact would carry the mini 10,000 row beside a 0.05 tick with
#: nothing complaining. ``registry_product`` is cross-checked against the spec
#: ``resolve_contract_spec`` returns, and a mismatch REFUSES
#: (:func:`resolve_instrument`).
#:
#: ``A05`` is 미니코스피200선물거래 and is what the resident paper session runs;
#: ``101``/``A01`` are 코스피200선물거래 (continuous-backtest and live
#: front-month codes, both registered on ``kospi200_full``). Any other prefix is
#: refused: this probe's TRs and its 별표 rows are specific to KOSPI200 index
#: futures.
#:
#: **Quantity rows are CONTEXT ONLY.** No leg passes or fails on them and this
#: probe cannot observe them (see the module docstring). They are recorded so the
#: artifact names WHICH 별표 17의2 row governs ``--symbol`` instead of leaving a
#: reader to assume the full-size contract's number applies to a mini leaf.
#: Values are the 공표 규정값, with the two 단서 of design v2 §2.2 attached: 회원
#: may set a LOWER limit (시행세칙 제61조제3항) and 거래소 may change them
#: (제61조제1항 단서). 누적호가수량한도 (제61조제2항) is a DIFFERENT limit applying
#: only to 회원 자기거래계좌·사후위탁증거금계좌, never to a 위탁계좌 like
#: paper/모의 — deliberately absent.
_QUANTITY_LIMIT_CAVEATS = (
    "회원은 시행세칙 제61조제3항으로 더 낮게 정할 수 있고, 거래소는 제61조제1항 "
    "단서로 변경할 수 있다. 공표 규정값이지 불변식이 아니다. 누적호가수량한도"
    "(제61조제2항)는 위탁계좌에 적용되지 않으므로 여기 없다."
)
_QUANTITY_LIMIT_CHAIN = (
    "업무규정 제71조 → 시행세칙 제61조제1항 → 별표 17의2 제1호 "
    "(별표 최종개정 2025-05-29)"
)

KRX_PREFIX_TABLE: dict[str, dict[str, Any]] = {
    "A05": {
        "registry_product": "kospi200_mini",
        "product": "미니코스피200선물거래",
        "regular_session_contracts": 10000,
        "night_session_contracts": 5000,
        # 별표 17의2 제1호 의 괄호 값 — 해당 상품이 유동성관리상품으로 지정된
        # 경우에만 적용된다. 지정 여부는 이 프로브가 관측하지 않는다.
        "liquidity_managed_regular_contracts": 1000,
        "liquidity_managed_night_contracts": 500,
        "source": _QUANTITY_LIMIT_CHAIN,
        "evidence": (
            f"{_EVIDENCE_DIR}byeolpyo17-2_order_quantity_limits.txt:41-45 "
            "(미니코스피200선물거래 행) · 괄호 의미 비고 :118"
        ),
        "caveats": _QUANTITY_LIMIT_CAVEATS,
        "tick_article": "시행세칙 제4조의9제2호 (미니 0.02 포인트, 최종개정 2024-11-01)",
    },
    "101": {
        "registry_product": "kospi200_full",
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
        "tick_article": "시행세칙 제4조의9제1호 (전체 0.05 포인트, 최종개정 2024-11-01)",
    },
}
#: ``A01`` is the live front-month code for the SAME product as ``101``
#: (``config/execution.yaml`` registers both on ``kospi200_full``), so it shares
#: the row rather than restating it.
KRX_PREFIX_TABLE["A01"] = KRX_PREFIX_TABLE["101"]

#: Accepted ``--symbol`` prefixes, derived from the table so the two can never
#: disagree about which families exist.
ACCEPTED_PREFIXES: tuple[str, ...] = tuple(KRX_PREFIX_TABLE)

#: Prefixes whose product is the mini — derived, so 제55조제1항 단서's scope and
#: the 별표 row cannot disagree about which leaves are mini.
_MINI_PREFIX_SET: frozenset[str] = frozenset(
    prefix
    for prefix, row in KRX_PREFIX_TABLE.items()
    if row["registry_product"] == "kospi200_mini"
)

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
#:
#: ⚠ 제55조제1항 **단서**: for a 분기월 mini contract the 기준가격 is the
#: 코스피200선물's, not its own previous settlement. So on a Mar/Jun/Sep/Dec mini
#: leaf, ``futs_sdpr != futs_prdy_clpr`` does NOT distinguish "settlement vs
#: close" — the two could differ because the basis came from another product.
#: :func:`_leg_l1` records that qualification instead of claiming the stronger
#: reading.
_RULE_BASIS_PRICE = (
    "시행세칙 제55조제1항제2호 — 기준가격은 직전 거래일의 정산가격(규정 제96조); "
    "제55조제4항으로 호가가격단위에 가장 가까운 값(동일하면 높은 쪽)으로 조정; "
    "제55조제1항 단서 — 분기월 mini 는 같은 최종거래일 코스피200선물의 기준가격"
)

#: Quarterly contract months, where 제55조제1항 단서 applies to a mini leaf.
_QUARTERLY_MONTHS: frozenset[int] = frozenset({3, 6, 9, 12})

#: 단계 확대가 불가능한 창 — 시행세칙 제56조의2제2항: 야간거래와 08:45~09:00 은
#: 1단계만. A sample taken inside it has a DETERMINED expected band; a sample
#: outside it does not. These are REGULATION literals (the 세칙 names the two
#: clock times), not a schedule, so they stay here rather than in YAML.
_NO_ESCALATION_START = clock_time(8, 45)
_NO_ESCALATION_END = clock_time(9, 0)
#: 제56조의2 의 개정일은 **둘**이다: 제2항 본문 2025-05-29, 제2항제1호가목
#: 2026-06-11 (design v2 §2.1). 하나만 적으면 다른 절의 날짜를 이 절에 붙이게 된다.
_NO_ESCALATION_SOURCE = (
    "시행세칙 제56조의2제2항 (본문 최종개정 2025-05-29 · 제2항제1호가목 2026-06-11)"
)

#: CONTINUOUS 세션 — READ from the calendar, never a literal. CLAUDE.md puts
#: schedules in YAML, and the artifact cited ``calendar.yaml`` while the module
#: carried its own copy of the times. ``_session_window()`` reads the one phase
#: that file declares for ``krx-index-futures``.
_CALENDAR_CONFIG = _REPO_ROOT / "config" / "tos_runtime" / "paper" / "calendar.yaml"
_SESSION_INSTRUMENT_CLASS = "krx-index-futures"
_SESSION_PHASE = "CONTINUOUS"

#: The 주문가능 legs, in call order. :data:`GET_CALL_COUNT` is derived from this
#: rather than written down twice: the review found "5 read-only GETs" in
#: ``would_send`` beside a test asserting a 4-element call list, because L2 sends
#: nothing and the prose had counted it.
_PSBL_LEG_IDS: tuple[str, ...] = ("L3", "L4", "L5")

#: Quote calls per run — one 시세 call feeds every later leg.
_QUOTE_CALL_COUNT = 1

#: Total GETs one ``--confirm`` run issues. L2 is offline and adds none.
GET_CALL_COUNT = _QUOTE_CALL_COUNT + len(_PSBL_LEG_IDS)

#: Common CLI args this probe parses and never reads. ``add_common_args`` is
#: shared, so they cannot simply be dropped; naming them keeps a reader from
#: mistaking an inert default for a setting that was honoured.
_INERT_COMMON_ARGS: frozenset[str] = frozenset(
    {"quantity", "price_offset_pct", "samples", "margin_pct"}
)

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

#: L1 abort codes, recorded verbatim in ``errors`` so the artifact names which
#: guard stopped the run.
ABORT_L1_REFUSED = "ABORT_L1_QUOTE_REFUSED"
ABORT_L1_FIELD_UNUSABLE = "ABORT_L1_PRICE_FIELD_UNUSABLE"
ABORT_L1_TICK_CONTRADICTED = "ABORT_L1_TICK_CONTRADICTED_BY_BROKER_QUOTES"


class VenueLimitAbort(ProbeError):
    """A guard stopped the run AFTER the network answered. The abort IS a result.

    Distinct from a plain :class:`~tools.broker_probes.common.ProbeError`, which
    ``run.py`` turns into exit 4 with **no artifact** — correct for a
    precondition that failed before any contact, wrong for L1, whose three
    guards fire on a response the probe has already paid a call for. In the
    08:50±3분 window a single ``rt_cd≠0`` (what P-CA hit four times on 09-30)
    would otherwise leave zero evidence that the probe ran at all.

    Same polarity as ``probes_real_order.RealOrderAbort`` (":348-356" — "the
    abort IS the result, so it gets an artifact"). :func:`probe_pvl` catches it,
    records it through ``run.error``, marks L1 FAIL and RETURNS the run, so
    ``run.py`` writes the artifact on the normal path.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


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


def _session_window() -> tuple[clock_time, clock_time, str]:
    """The CONTINUOUS window for ``krx-index-futures``, READ from the calendar.

    The artifact used to cite ``calendar.yaml`` beside two literals this module
    carried. CLAUDE.md puts schedules in YAML, so the times come from the file
    the citation names and a drift between them is impossible rather than
    unnoticed.

    Raises:
        ProbeError: the calendar declares no such phase for that instrument
            class. Fail-closed: a missing window would otherwise read as "the
            sample was outside the session", which is a different claim.
    """
    import yaml

    try:
        raw = yaml.safe_load(_CALENDAR_CONFIG.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProbeError(f"cannot read {_CALENDAR_CONFIG}: {exc}") from exc
    sessions = ((raw or {}).get("sessions") or {}).get(_SESSION_INSTRUMENT_CLASS)
    for entry in sessions or []:
        if isinstance(entry, dict) and entry.get("phase") == _SESSION_PHASE:
            start = str(entry.get("start", ""))
            end = str(entry.get("end", ""))
            try:
                hh1, mm1 = (int(part) for part in start.split(":"))
                hh2, mm2 = (int(part) for part in end.split(":"))
            except ValueError as exc:
                raise ProbeError(
                    f"{_CALENDAR_CONFIG} {_SESSION_INSTRUMENT_CLASS} "
                    f"{_SESSION_PHASE} has unparsable start/end "
                    f"{start!r}/{end!r}: {exc}"
                ) from exc
            return (
                clock_time(hh1, mm1),
                clock_time(hh2, mm2),
                f"{_CALENDAR_CONFIG.name}::sessions.{_SESSION_INSTRUMENT_CLASS} "
                f"{_SESSION_PHASE} {start}-{end}",
            )
    raise ProbeError(
        f"{_CALENDAR_CONFIG} declares no {_SESSION_PHASE} phase for "
        f"{_SESSION_INSTRUMENT_CLASS}; the sample window cannot be stated."
    )


def kst_sample_window(now: datetime) -> dict[str, Any]:
    """The KST wall clock of a sample and which rule windows contain it."""
    local = now.astimezone(KST)
    hhmm = local.time()
    inside_no_escalation = _NO_ESCALATION_START <= hhmm < _NO_ESCALATION_END
    session_start, session_end, session_source = _session_window()
    return {
        "sampled_at_kst": local.isoformat(),
        "inside_no_escalation_window": inside_no_escalation,
        "no_escalation_window_kst": (
            f"{_NO_ESCALATION_START:%H:%M}-{_NO_ESCALATION_END:%H:%M}"
        ),
        "no_escalation_source": _NO_ESCALATION_SOURCE,
        "inside_continuous_session": session_start <= hhmm < session_end,
        "continuous_session_kst": f"{session_start:%H:%M}-{session_end:%H:%M}",
        "continuous_session_source": session_source,
        "expected_stage_is_determined": inside_no_escalation,
        "why": (
            "Inside the no-escalation window only stage 1 can be in force, so "
            "L2's expected band is DETERMINED and a mismatch is a FAIL. Outside "
            "it, a 2/3단계 band is admissible, so a mismatch is recorded with "
            "the stage that matched and carries no verdict (design v2 §4.2: "
            "「그날의 확대 사실을 기록만」)."
        ),
    }


# ---------------------------------------------------------------------------
# Instrument resolution
# ---------------------------------------------------------------------------


def _is_quarterly_mini(symbol: str) -> bool:
    """Is ``symbol`` a 분기월 mini leaf, where 제55조제1항 단서 applies?

    KIS futures codes carry the contract month in the 5th character (``A05610``
    → month ``1``, ``A05612`` → December via ``C``). Rather than decode that
    encoding — which this repo has no committed reference for — the check is
    deliberately CONSERVATIVE: anything that cannot be read as a non-quarterly
    month counts as quarterly, so the caveat is attached when in doubt and the
    stronger reading is never claimed by accident.
    """
    if _symbol_prefix(symbol) not in _MINI_PREFIX_SET:
        return False
    month = _contract_month(symbol)
    return month is None or month in _QUARTERLY_MONTHS


def _contract_month(symbol: str) -> int | None:
    """The contract month in a KIS futures code, or ``None`` if unreadable.

    The codes this probe accepts are ``<prefix><year digit><2-digit month>``:
    ``A05610`` is the October 2026 mini leaf (the resident one), ``A05603`` is
    March, and ``A01609`` is the September full-size contract that
    ``tests/tools/test_broker_probes_tick.py`` already uses. ``None`` means "do
    not claim to know", which :func:`_is_quarterly_mini` treats as quarterly so
    the stronger basis-price reading is never claimed by accident.
    """
    tail = symbol[len(_symbol_prefix(symbol)) :]
    if len(tail) < 3 or not tail[:3].isdigit():
        return None
    month = int(tail[1:3])
    return month if 1 <= month <= 12 else None


def _symbol_prefix(symbol: str) -> str:
    """The accepted KOSPI200-futures prefix ``symbol`` starts with, or refuse.

    Fail-closed on an unknown family: this probe's TRs are 선물옵션 and its
    rulebook rows are 주가지수선물거래 rows, so a symbol from any other product
    would be measured against the wrong 별표 row with no sign that it happened.
    """
    for prefix in ACCEPTED_PREFIXES:
        if symbol.startswith(prefix):
            return prefix
    raise ProbeError(
        f"--symbol {symbol!r} is not a KOSPI200 index-futures code. Accepted "
        f"prefixes: {', '.join(ACCEPTED_PREFIXES)} (mini / full-size). This "
        "probe's TRs and its 별표 17의2 · 별표 14 rows are specific to that "
        "product family."
    )


def _repo_relative(path: Path) -> str:
    """``path`` relative to the repo root when it is inside it, else as given.

    The artifact should cite a repo path, but a test that points the loader at a
    temporary file must not crash on ``relative_to``.
    """
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def _policy_tick_record() -> dict[str, Any]:
    """The deployed paper policy's ``tick_size``, recorded — never the truth.

    Read so the artifact can state whether the policy and the contract registry
    agree about ``--symbol``'s 호가가격단위. As of 2026-10-08 they DISAGREE for a
    mini leaf: the policy carries 5 (= 0.05, the full-size unit) while the
    registry carries 0.02. Surfacing that is the probe's job; resolving it is
    the operator's.
    """
    import yaml

    try:
        raw = yaml.safe_load(_PAPER_VENUE_POLICY.read_text(encoding="utf-8"))
    except OSError as exc:
        # A bare FileNotFoundError here would surface as an unhandled traceback
        # and run.py's generic handler, naming neither the file nor why it is
        # read. The comparison is the point, so say what is missing.
        raise ProbeError(
            f"cannot read the deployed paper venue policy {_PAPER_VENUE_POLICY}: "
            f"{exc}. It is read only to record its tick_size beside the "
            "registry's; pass a repo checkout that contains it."
        ) from exc
    shape = ((raw or {}).get("_model_view") or {}).get("shape_constraints") or {}
    value = decimal_field(shape, "tick_size")
    return {
        "policy_path": _repo_relative(_PAPER_VENUE_POLICY),
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

    row = KRX_PREFIX_TABLE[prefix]
    # The cross-check finding 8 asked for. The 별표 row and the tick come from
    # two different files (this table and config/execution.yaml), and before this
    # guard a symbol_prefix edit could pair the mini 10,000 row with the
    # full-size 0.05 tick in one artifact, silently. Refuse instead: a product
    # disagreement means one of the two tables is wrong and the probe cannot tell
    # which.
    registered_prefixes = tuple(
        part.strip() for part in str(spec.symbol_prefix).split(",") if part.strip()
    )
    if row["registry_product"] != spec.name or prefix not in registered_prefixes:
        raise ProbeError(
            f"--symbol {symbol} matched prefix {prefix!r}, which this module's "
            f"별표 table binds to product {row['registry_product']!r} "
            f"({row['product']}), but config/execution.yaml resolved it to "
            f"{spec.name!r} with symbol_prefix {spec.symbol_prefix!r}. The 별표 "
            "17의2 row and the 호가가격단위 would describe different products in "
            "one artifact. Reconcile KRX_PREFIX_TABLE with "
            "config/execution.yaml::futures_contract_spec before measuring."
        )

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
        "registry_tick_rule_article": row["tick_article"],
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
        "krx_quantity_limit_row": {
            key: value for key, value in row.items() if key != "tick_article"
        },
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
        raise VenueLimitAbort(
            ABORT_L1_REFUSED,
            f"L1 {_PRICE_TR} answered rt_cd={rt_cd!r} "
            f"msg_cd={parsed.get('msg_cd')!r} msg1={parsed.get('msg1')!r}. Every "
            "later leg reads its prices from this response, so there is nothing "
            "to measure — the refusal is the whole observation.",
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
            # Design §4.1 lists the ``Date`` header among L1's measurements, so
            # it belongs here and not only in the observation stream.
            "broker_date_header": headers.get("Date", ""),
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
        raise VenueLimitAbort(
            ABORT_L1_FIELD_UNUSABLE,
            f"L1 {_PRICE_TR} returned no usable value for {', '.join(unusable)}. "
            "Design §5 requires all five fields positive; a zero or absent field "
            "is recorded, never substituted.",
        )

    quarterly = _is_quarterly_mini(symbol)
    run.measure(
        "l1_basis_price_distinguishable",
        {
            "futs_sdpr": str(prices["futs_sdpr"]),
            "futs_prdy_clpr": str(prices["futs_prdy_clpr"]),
            "differ": prices["futs_sdpr"] != prices["futs_prdy_clpr"],
            "distinguishes_settlement_from_close": (
                prices["futs_sdpr"] != prices["futs_prdy_clpr"] and not quarterly
            ),
            "quarterly_mini_leaf": quarterly,
            "meaning": (
                f"{_RULE_BASIS_PRICE}. When the two fields differ, this sample "
                "distinguishes 정산가 from 종가. When they are equal, the sample "
                "is simply uninformative — equality is not evidence that the "
                "rule is wrong."
            ),
            "quarterly_caveat": (
                "⚠ On a 분기월 mini leaf (제55조제1항 단서) the 기준가격 is the "
                "코스피200선물's, not this contract's own settlement price, so a "
                "difference here may be about the OTHER product and does not "
                "distinguish 정산가 from 종가. "
                "distinguishes_settlement_from_close is False for that reason, "
                "not because the fields matched."
            ),
        },
    )

    corroboration = corroborate_tick(output, tick, _L1_PRICE_FIELDS)
    run.measure("l1_tick_corroboration", corroboration)
    if not corroboration["corroborated"]:
        raise VenueLimitAbort(
            ABORT_L1_TICK_CONTRADICTED,
            "L1 tick corroboration FAILED: the broker quoted "
            f"{corroboration['non_multiples']}, which are not multiples of the "
            f"registered tick {corroboration['tick_size_points']} "
            f"({tick.source}). The registry is CONTRADICTED; no band arithmetic "
            "may be done against a tick the venue's own quotes deny.",
        )
    return prices


def _leg_l2(
    run: ProbeRun, prices: dict[str, Decimal], tick: VenueTick, window: dict[str, Any]
) -> str:
    """L2 — 제56조 arithmetic against the observed band. No network. Never raises.

    THREE-way, because the design takes two samples with different epistemic
    standing (§4.2):

    * inside the no-escalation window, stage 1 is the only admissible band, so a
      mismatch is a genuine :data:`VERDICT_FAIL`;
    * outside it, a 2/3단계 band is a legitimate market state. The old code
      scored that ``FAIL`` while its own docstring called it legitimate — the
      review's finding 5. It now returns :data:`VERDICT_RECORDED` with the stage
      that matched, which is exactly what §4.2 asks for
      (「그날의 확대 사실을 기록만」).

    A mismatch is never an exception either way: the probe cannot choose the
    escalation state it finds.
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
    matched = stage1 in report["matching_stages"]
    determined = bool(window["expected_stage_is_determined"])
    if matched:
        verdict = VERDICT_PASS
    elif determined:
        verdict = VERDICT_FAIL
    else:
        verdict = VERDICT_RECORDED
    report["declared_expectation_matches"] = matched
    report["expected_stage_is_determined"] = determined
    report["verdict"] = verdict
    report["declared_expectation_note"] = (
        "The declared expectation is design §4.1 L2: 1단계 비율 8% at --symbol's "
        "own 호가가격단위. It is the PASS criterion. It is only the DETERMINED "
        "expectation inside the no-escalation window — outside it a 2/3단계 band "
        "is admissible, so a mismatch is recorded without a verdict."
    )
    report["tick_provenance"] = tick.source
    run.measure("l2_band_rule_arithmetic", report)

    if not matched:
        run.measure(
            "l2_mismatch_record",
            {
                "verdict": verdict,
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
                "why_this_verdict": (
                    "FAIL — the sample is inside the no-escalation window, where "
                    "stage 1 is the only admissible band."
                    if determined
                    else "No verdict — outside the no-escalation window a 2/3단계 "
                    "band is a legitimate market state, so the matched stage is "
                    "recorded as the day's escalation fact (design v2 §4.2)."
                ),
            },
        )
    return verdict


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
        # ``ord_psbl_qty`` is the number L3's verdict reads, so an unreadable or
        # fractional one is fatal. ``tot_psbl_qty`` carries NO verdict in design
        # §5, and raising on it used to abort the run before L4 and L5 ever ran —
        # trading two observations for a field nothing judges. It is transcribed,
        # and its unreadability is recorded rather than thrown.
        record["ord_psbl_qty_int"] = _integral_quantity(
            record["ord_psbl_qty"], "ord_psbl_qty"
        )
        try:
            record["tot_psbl_qty_int"] = _integral_quantity(
                record["tot_psbl_qty"], "tot_psbl_qty"
            )
        except ProbeError as exc:
            record["tot_psbl_qty_unreadable"] = str(exc)
    return record


def disposition_token(verdicts: dict[str, str]) -> str:
    """The P0-2 field's value, DERIVED from the leg verdicts. PURE.

    Design v2 §5 rejects a one-word status by name and gives the profile's own
    idiom: a self-describing compound token in the shape of
    ``:4432 DAY_AND_NIGHT_TR_SURFACE_PRESENT__OTHER_COVERAGE_UNKNOWN``, with the
    observed and unobserved axes written INTO the token. The previous
    ``PARTIAL`` was the exact word the design refuses.

    Derived, not chosen, so an L2 that did not pass cannot ship a token claiming
    ``BAND_SEMANTICS_OBSERVED_ON_MOCK``:

    * **band axis** — ``OBSERVED_ON_MOCK`` only when L1 and L2 both PASS;
      ``L2_STAGE_RECORDED_ONLY`` when L2 carries no verdict (outside the
      no-escalation window); ``CONTRADICTED_ON_MOCK`` on an L2 FAIL;
      ``NOT_OBSERVED`` when L1 never produced prices.
    * **tick axis** — ``FROM_REGULATION_NOT_BROKER`` only when L1 PASSed, i.e.
      the corroboration actually ran against broker quotes. The value is still a
      repo/regulation value and the broker never published it, which is why the
      token says so and the profile's ``:2426-2430`` note stays intact.
    * **quantity axis** — always ``RULE_VALUE_BROKER_UNCONFIRMED``: this probe
      cannot observe a venue cap at all (module docstring, design v2 §4.3).
    """
    l1 = verdicts.get("L1")
    l2 = verdicts.get("L2")
    if l1 != VERDICT_PASS:
        band = "BAND_SEMANTICS_NOT_OBSERVED"
    elif l2 == VERDICT_PASS:
        band = "BAND_SEMANTICS_OBSERVED_ON_MOCK"
    elif l2 == VERDICT_RECORDED:
        band = "BAND_SEMANTICS_L2_STAGE_RECORDED_ONLY"
    else:
        band = "BAND_SEMANTICS_CONTRADICTED_ON_MOCK"
    tick = (
        "TICK_FROM_REGULATION_NOT_BROKER"
        if l1 == VERDICT_PASS
        else "TICK_UNCORROBORATED"
    )
    return f"{band}__{tick}__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED"


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
        "inert_common_args",
        {
            "ignored": sorted(_INERT_COMMON_ARGS),
            "why": (
                "add_common_args gives every probe the same CLI, so these parse "
                "and land in args but this probe never reads them: it issues a "
                "fixed GET plan, places nothing, and proposes no numeric bound. "
                "Named here because an artifact carrying '--samples 30' beside 4 "
                "calls reads like a discarded setting rather than an unused flag."
            ),
        },
    )
    run.measure(
        "verdict_and_error_relation",
        (
            "Every FAIL verdict is ALSO recorded through run.error, so "
            "errors == [] means no leg failed and provenance_class MEASURED is "
            "earned. The runbook treats an empty errors list as a complete run "
            "(§5.5), and a probe that scored a FAIL while shipping errors: [] "
            "would have made that reading false. L4/L5 carry no verdict and "
            "therefore never produce an error."
        ),
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
                "ord_psbl_qty is 주문가능수량 per the official spec: a function "
                "of 예수금·증거금 AND of this leg's own price, side and "
                "order-type parameters "
                f"({_ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION}). It is not "
                "the venue's structural limit. The 호가수량한도 of 별표 17의2 and "
                "any lower member limit under 시행세칙 제61조제3항 are observable "
                "only by sending an order and reading the rejection — outside "
                "this probe's GET-only scope. The rulebook row for --symbol is "
                "recorded as CONTEXT and decides nothing."
            ),
            "no_prior_ord_psbl_qty_observation": (
                "This repo holds NO ord_psbl_qty observation yet. P-R5-PRE's "
                "2026-08-03 run aborted on the deposit leg (CTRP6550R "
                "ord_psbl_cash/ord_psbl_tota = 0) BEFORE the 주문가능 leg ran "
                "(P-R5-PRE-20260803T002732Z.json), so no artifact here supports "
                "any claim about what a zero 주문가능수량 means. Design v2 §4.3 "
                "says this explicitly; an earlier draft of this module cited that "
                "run for the opposite and was wrong."
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
                f"{GET_CALL_COUNT} read-only GETs on the mock host for {symbol}: "
                f"{_QUOTE_CALL_COUNT} {_PRICE_TR} 시세 call, then "
                f"{len(_PSBL_LEG_IDS)} {_PSBL_TR} 주문가능 calls "
                f"({', '.join(_PSBL_LEG_IDS)}) at the touch, at 하한가, and at "
                f"상한가 + one tick ({tick.size}). L2 is offline arithmetic and "
                "sends nothing, so it adds no call."
            ),
            get_call_count=GET_CALL_COUNT,
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
        verdicts["L2"] = _leg_l2(run, prices, tick, window)
        if verdicts["L2"] == VERDICT_FAIL:
            report = run.measurements["l2_band_rule_arithmetic"]
            run.error(
                "L2 FAIL — inside the no-escalation window the observed band "
                f"({report['observed_lower']} / {report['observed_upper']}) does "
                "not match 제56조 at 1단계 8% and tick "
                f"{report['tick_points']}; matching stages: "
                f"{report['matching_stages']}"
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
            run.error(
                f"L3 FAIL — {_PSBL_TR} refused the query: rt_cd={l3['rt_cd']!r} "
                f"msg_cd={l3['msg_cd']!r} msg1={l3['msg1']!r}. No quantity was "
                "observed; this is NOT 'zero available'."
            )
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
            run.error(
                f"L3 FAIL — {_PSBL_TR} answered rt_cd={l3['rt_cd']!r} with "
                f"ord_psbl_qty={l3['ord_psbl_qty']!r} (< 1 contract). Says "
                "nothing about the venue's structural quantity limit."
            )
            run.measure(
                "l3_zero_quantity_record",
                {
                    "ord_psbl_qty": l3["ord_psbl_qty_int"],
                    "recorded_not_interpreted": (
                        "A zero 주문가능수량 is RECORDED, not explained. Design "
                        "v2 §5 names three causes and this probe cannot "
                        "distinguish them: (1) 예수금 0, (2) a 증거금 constraint "
                        "on this account, (3) THIS LEG'S OWN parameters — the "
                        "price, side and order type it sent "
                        f"({_ORD_PSBL_QTY_PARAMETER_DEPENDENCE_CITATION}). "
                        "Whichever it is, it "
                        "says nothing about the venue's structural quantity "
                        "limit."
                    ),
                    "candidate_causes": [
                        "예수금 0",
                        "증거금 constraint on this account",
                        "this leg's own price/side/order-type parameters",
                    ],
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
    except VenueLimitAbort as abort:
        # The abort IS the result. Recording it through run.error marks the
        # artifact NOT_MEASURED and RETURNING the run lets run.py write it on
        # the normal path — rather than exit 4 with the L1 measurements, the
        # credentials and the sample window all discarded.
        verdicts["L1"] = VERDICT_FAIL
        run.error(str(abort))
        run.measure(
            "l1_abort",
            {
                "code": abort.code,
                "message": str(abort),
                "why_the_artifact_still_exists": (
                    "Design §5 says an L1 failure is recorded 「아티팩트에 "
                    "그대로」. probes_real_order's RealOrderAbort established the "
                    "polarity: a guard that fires AFTER the broker answered has "
                    "observed something, so it gets an artifact. A bare "
                    "ProbeError would have exited 4 and written nothing."
                ),
            },
        )
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
            "proposed": disposition_token(verdicts),
            "derived_from": dict(verdicts),
            "still_unestablished": [
                "the structural 호가수량한도 (별표 17의2) — regulation value only, "
                "broker-side limit unconfirmed",
                "any member limit KIS sets under 시행세칙 제61조제3항",
                "2/3단계 확대 의미론",
                "the runtime supply path for a band (design §6)",
            ],
            "rule": (
                "Design v2 §5: the profile's idiom is a self-describing COMPOUND "
                "token (:4432 shape), not a one-word status — 'PARTIAL' is "
                "refused there by name. The token above is DERIVED from "
                "derived_from, so a leg that did not pass cannot claim an "
                "observed axis. See disposition_token()."
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
