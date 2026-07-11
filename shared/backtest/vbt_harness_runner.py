"""VbtHarnessRunner — vectorbt cross-check wrapper for the futures harness (P3-d).

Composition wrapper, **not** a resolve-pass duplicate
=====================================================

Unlike :class:`~shared.backtest.vbt_runner.VectorbtRunner` (the stock path,
P3-a/b/c), which re-derives the whole ledger through a vectorbt
``Portfolio``, this class does **not** reimplement the futures fill/exit
semantics. The production :class:`~shared.backtest.decision_harness.
BacktestDecisionHarness` remains the single source of truth: ``run`` executes
the real harness unchanged and returns its :class:`HarnessResult` verbatim.
The vectorbt layer only builds an *independent* ``vbt.Portfolio.from_orders``
ledger from the harness's own trade records and asserts it reproduces the
harness's tick accounting (a redundant-computation parity check).

Honest value note
------------------
(a) This wrapper adds an **independent from_orders ledger verification** of the
    harness's per-trade tick P&L, entry/exit bars, prices, direction and size.
    It does **not** replace the harness. The harness has no equity curve /
    Sharpe / MDD to migrate (its consumers — walk-forward scripts, experiment
    reports — read only tick sums and per-setup stats), so there is no metric
    surface to move onto vectorbt. The value is a second, structurally
    different computation of the same P&L that must agree.
(b) ``backtest.legacy_exit`` (the stock-path escape hatch) is **N/A** here.
    The harness has no strategy-config exit generators — every Signal carries
    its own ``stop_loss`` / ``take_profit`` / ``valid_until`` and the fill
    simulator resolves them directly. "Opt-in" to vectorbt is simply choosing
    this class over :class:`BacktestDecisionHarness`; the escape hatch is
    choosing the harness directly. There is no per-strategy flag to honour.
(c) **Dual regime**: :class:`BacktestDecisionHarness` stays the default for all
    consumers. This class is an opt-in verification tool (parity report +
    tests); nothing routes to it by default.

Same-bar carve-out
------------------
``vbt.Portfolio.from_orders`` holds at most one order per (bar, column). A
harness trade whose fill and exit land on the **same** bar (session boundary
forcing EOD close on the fill bar, or the last-bar fallback) therefore cannot
be expressed as an entry+exit pair in one column. Such trades are verified
**analytically** instead: the harness marks their exit at that bar's close, so
the cross-check asserts ``exit_price == close[fill_bar_index]`` and folds their
tick P&L into the headline-sum invariant. Only multi-bar trades
(``exit_bar_index > fill_bar_index``) are routed through ``from_orders`` — one
column each.

vectorbt is a ``backtest`` extra dependency (excluded from the runtime image),
so it is never imported at module top level — only lazily inside
:meth:`VbtHarnessRunner._cross_check`. plan:
docs/plans/2026-07-08-new-architecture-refactoring-plan.md §5 (P3-d).
"""

from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from shared.backtest.decision_harness import (
    BacktestDecisionHarness,
    HarnessResult,
    TradeRecord,
)
from shared.backtest.market_context_replay import MarketContextReplay

# from_orders 원장 대조는 결정론적 산술이므로 엄격한 허용오차를 쓴다
# (VectorbtRunner 의 _CROSS_CHECK_RTOL 1e-6 보다 타이트 — 여기서는 두 원장이
# 부동소수 결합순서까지 사실상 동일하기 때문).
_PARITY_RTOL: float = 1e-9
_PARITY_ATOL: float = 1e-9

# vbt 1.0.0 trades.records 계약 (empirical probe 로 고정): 롱=0 / 숏=1,
# status 1 = closed. size 는 부호 없이 양수로 기록된다.
_DIRECTION_LONG_CODE: int = 0
_DIRECTION_SHORT_CODE: int = 1
_STATUS_CLOSED: int = 1

# from_orders 진입 현금 — 숏 진입도 커버하도록 넉넉히(체결가는 명시 price 배열이
# 지배하므로 실제 자본은 결과에 영향 없음; 모든 트레이드가 청산 완료라 마킹만).
_INIT_CASH: float = 1e12


class VbtHarnessNotSupportedError(NotImplementedError):
    """이 환경에서는 vectorbt 대조를 수행할 수 없다 — harness 를 직접 쓸 것.

    현재 유일 사유는 vectorbt 미설치(``backtest`` extra 없는 런타임/호스트)다.
    :class:`~shared.backtest.vbt_runner.VectorbtNotSupportedError` 와 같은
    계약 — 정적으로 판별해 harness 실행을 낭비하지 않는다."""

    def __init__(self, detail: str):
        super().__init__(f"use BacktestDecisionHarness: {detail}")


class VbtHarnessParityError(RuntimeError):
    """harness 원장 ↔ from_orders 원장 대조 불일치 (내부 불변식 위반).

    "표현 불가"(:class:`VbtHarnessNotSupportedError`)가 아니라 **대조 로직 자체의
    결함** 신호다. harness 결과는 이미 확정돼 반환 가능한 상태이므로, 이 예외는
    from_orders 매핑/대조가 harness 의 tick 회계를 재현하지 못했음을 뜻한다 —
    조사 대상."""


@dataclass
class _OrderArrays:
    """``from_orders`` 입력 배열 + 트레이드 분류 결과 (순수 numpy).

    Attributes:
        size: ``(n_bars, n_cols)`` 주문 수량 (+진입/-청산, NaN=주문 없음).
            멀티바 트레이드 i 당 1컬럼: 진입 ``dir*s`` / 청산 ``-dir*s``.
        price: ``(n_bars, n_cols)`` 주문 체결 가격 (NaN=주문 없음).
        multibar: ``exit_bar_index > fill_bar_index`` 트레이드 (컬럼 i ↔
            multibar[i] 대응 — from_orders 대상).
        samebar: ``exit_bar_index == fill_bar_index`` 트레이드 (from_orders 로
            표현 불가 — 해석적 carve-out 대상).
        n_cols: ``len(multibar)`` (vbt 컬럼 수).
    """

    size: np.ndarray
    price: np.ndarray
    multibar: list[TradeRecord]
    samebar: list[TradeRecord]
    n_cols: int


def _build_order_arrays(trades: list[TradeRecord], n_bars: int) -> _OrderArrays:
    """harness 트레이드 레코드 → ``from_orders`` 주문 배열 (순수 numpy).

    멀티바 트레이드(``exit_bar_index > fill_bar_index``)만 컬럼으로 인코딩한다.
    같은-bar 트레이드(``==``)는 한 컬럼/한 bar 에 진입+청산 2주문을 담을 수 없어
    제외하고 :attr:`_OrderArrays.samebar` 로 넘긴다(호출자가 해석적으로 검증).

    Args:
        trades: harness ``HarnessResult.trades`` — 모든 레코드의
            ``fill_bar_index`` / ``exit_bar_index`` 가 채워져 있어야 한다
            (:meth:`VbtHarnessRunner._cross_check` 가 선행 보장).
        n_bars: replay DataFrame 길이(주문 배열의 행 수).

    Returns:
        :class:`_OrderArrays`.
    """
    multibar = [t for t in trades if t.exit_bar_index > t.fill_bar_index]  # type: ignore[operator]
    samebar = [t for t in trades if t.exit_bar_index == t.fill_bar_index]
    n_cols = len(multibar)

    size = np.full((n_bars, n_cols), np.nan, dtype=np.float64)
    price = np.full((n_bars, n_cols), np.nan, dtype=np.float64)
    for i, t in enumerate(multibar):
        direction = 1.0 if t.direction == "long" else -1.0
        contracts = float(t.size_contracts)
        fill_idx = int(t.fill_bar_index)  # type: ignore[arg-type]
        exit_idx = int(t.exit_bar_index)  # type: ignore[arg-type]
        # 진입: 롱=+수량 / 숏=-수량 (direction="both", size_type="amount").
        size[fill_idx, i] = direction * contracts
        price[fill_idx, i] = t.fill_price
        # 청산: 반대 부호 동일 수량 (풀포지션 종료).
        size[exit_idx, i] = -direction * contracts
        price[exit_idx, i] = t.exit_price

    return _OrderArrays(
        size=size,
        price=price,
        multibar=multibar,
        samebar=samebar,
        n_cols=n_cols,
    )


class VbtHarnessRunner:
    """:class:`BacktestDecisionHarness` drop-in + from_orders parity 대조 (P3-d).

    생성자 시그니처와 :meth:`run` 계약은 :class:`BacktestDecisionHarness` 와 동일
    하다(drop-in). :meth:`run` 은 (0) vectorbt 정적 게이트 → (1) **실제** harness
    실행(SoT, 결과 무변형) → (2) 트레이드 레코드로 ``from_orders`` 원장을 구성해
    tick 회계 일치 대조 → (3) harness 결과 반환. 대조 실패는
    :class:`VbtHarnessParityError`.

    Usage:
        runner = VbtHarnessRunner(setups, filter_layer, state, tick_size)
        result = runner.run(replay)  # HarnessResult (harness 와 동일)
    """

    def __init__(
        self,
        setups: list[Any],
        filter_layer: Any,
        state: Any,
        tick_size_points: float,
        *,
        sizer: Any | None = None,
        account_equity_krw: float = 0.0,
    ) -> None:
        """:class:`BacktestDecisionHarness` 와 동일 인자.

        Args:
            setups: 평가할 Setup 인스턴스 목록.
            filter_layer: 후보 시그널에 적용할 RiskFilterLayer.
            state: 불변 RiskStateSnapshot.
            tick_size_points: 틱 크기(슬리피지 + tick P&L 환산 + 대조).
            sizer: 선택 PositionSizer(주입 시 계약 수 산정).
            account_equity_krw: 사이저에 전달할 계좌 자본.
        """
        # harness 를 즉시 구성(실행은 run() 에서만) — tick_size 검증 등 harness
        # 생성자 계약을 그대로 물려받고, run() 이 정적 게이트를 harness.run() 앞에
        # 두어 vbt 미설치 시 harness 를 구동하지 않는다.
        self._harness = BacktestDecisionHarness(
            setups,
            filter_layer,
            state,
            tick_size_points,
            sizer=sizer,
            account_equity_krw=account_equity_krw,
        )
        self._tick_size = tick_size_points

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, replay: MarketContextReplay) -> HarnessResult:
        """harness 실행 + from_orders 대조 — :meth:`BacktestDecisionHarness.run` 계약.

        Args:
            replay: 과거 데이터에 대한 :class:`MarketContextReplay`.

        Returns:
            :class:`HarnessResult` — **harness 원본 결과 그대로** (무변형).

        Raises:
            VbtHarnessNotSupportedError: vectorbt 미설치 — harness 를 구동하기
                *전에* 정적으로 거부한다(호출자는 harness 를 직접 쓸 것).
            VbtHarnessParityError: from_orders 원장이 harness tick 회계와
                불일치(내부 불변식 위반).
        """
        # 0. 정적 게이트 — harness 실행 *전에* vectorbt 가용성을 판별한다.
        #    find_spec 자체가 던지는 예외(마스킹 finder / 깨진 설치)도 "미설치"로
        #    취급한다 (VectorbtRunner._ensure_supported 와 동일 방어).
        try:
            vbt_available = importlib.util.find_spec("vectorbt") is not None
        except (ImportError, ValueError):
            vbt_available = False
        if not vbt_available:
            raise VbtHarnessNotSupportedError(
                "vectorbt not installed — pip install -e '.[backtest]'"
            )

        # 1. 실제 production harness 실행 — 결과가 SoT, 무변형 반환.
        result = self._harness.run(replay)

        # 2. 독립 from_orders 원장으로 tick 회계 재현 검증.
        self._cross_check(result, replay.df)

        # 3. harness 결과 그대로 반환.
        return result

    # ------------------------------------------------------------------
    # Parity cross-check
    # ------------------------------------------------------------------

    def _cross_check(self, result: HarnessResult, df: pd.DataFrame) -> None:
        """harness 원장 ↔ from_orders 원장의 tick 회계 일치를 강제(불변식).

        멀티바 트레이드는 ``from_orders`` 로, 같은-bar 트레이드는 해석적으로
        검증하고, 마지막에 헤드라인 tick 합 불변식으로 두 경로를 봉합한다.
        """
        trades = result.trades

        # 인덱스가 채워져 있어야 한다 — _simulate_fill 산출 레코드만 대상.
        for t in trades:
            if t.fill_bar_index is None or t.exit_bar_index is None:
                raise VbtHarnessParityError(
                    "trade record missing fill/exit bar index "
                    f"(setup={t.setup_type}, bar={t.bar_index}) — not produced "
                    "by _simulate_fill?"
                )

        n_bars = len(df)
        closes = df["close"].to_numpy(dtype=float)
        tick = self._tick_size
        arrays = _build_order_arrays(trades, n_bars)

        # 분류 완전성: 모든 트레이드는 멀티바 또는 같은-bar 중 정확히 하나.
        if len(arrays.multibar) + len(arrays.samebar) != len(trades):
            raise VbtHarnessParityError(
                "trade classification incomplete: "
                f"{len(arrays.multibar)} multibar + {len(arrays.samebar)} "
                f"samebar != {len(trades)} total (exit_bar_index < "
                "fill_bar_index?)"
            )

        # 같은-bar carve-out (해석적): harness 는 이들 청산을 체결 bar 종가로
        # 마킹한다(EOD-on-fill-bar / last-bar fallback 양 경로). from_orders 는
        # 컬럼/bar 당 1주문이라 표현 불가 → 종가 일치만 직접 확인.
        for t in arrays.samebar:
            fill_idx = int(t.fill_bar_index)  # type: ignore[arg-type]
            if not math.isclose(
                float(t.exit_price),
                float(closes[fill_idx]),
                rel_tol=_PARITY_RTOL,
                abs_tol=_PARITY_ATOL,
            ):
                raise VbtHarnessParityError(
                    "same-bar trade exit price "
                    f"{t.exit_price} != fill-bar close {closes[fill_idx]} "
                    f"(setup={t.setup_type}, bar={t.bar_index})"
                )

        # 멀티바 트레이드 원장 대조 (컬럼이 있을 때만 vbt 구동).
        records_pnl_sum = 0.0
        if arrays.n_cols > 0:
            records_pnl_sum = self._verify_multibar_ledger(arrays, closes, tick)

        # 헤드라인 tick-PnL 합 불변식: from_orders pnl 합 + 같은-bar tick 합
        # == 전체 트레이드 tick 합. (멀티바/같은-bar 두 경로를 봉합.)
        samebar_pnl = sum(t.ticks_net * tick * t.size_contracts for t in arrays.samebar)
        all_pnl = sum(t.ticks_net * tick * t.size_contracts for t in trades)
        if not math.isclose(
            records_pnl_sum + samebar_pnl,
            all_pnl,
            rel_tol=_PARITY_RTOL,
            abs_tol=max(_PARITY_ATOL, abs(all_pnl) * _PARITY_RTOL),
        ):
            raise VbtHarnessParityError(
                "headline tick-PnL sum mismatch: "
                f"from_orders {records_pnl_sum} + samebar {samebar_pnl} "
                f"!= all-trades {all_pnl}"
            )

    def _verify_multibar_ledger(
        self, arrays: _OrderArrays, closes: np.ndarray, tick: float
    ) -> float:
        """멀티바 트레이드를 ``from_orders`` 원장과 대조 — pnl 합을 반환.

        vectorbt 는 이 시점에만 lazy import 한다(모듈 최상위 import 금지).
        """
        import vectorbt as vbt  # noqa: PLC0415 — backtest extra, lazy by contract

        # close 는 harness df 종가를 N컬럼으로 타일링(open 포지션 마킹용;
        # 모든 트레이드가 청산 완료라 체결 pnl 은 명시 price 배열이 지배).
        close_nxn = np.tile(closes.reshape(-1, 1), (1, arrays.n_cols))
        portfolio = vbt.Portfolio.from_orders(
            close=pd.DataFrame(close_nxn),
            size=pd.DataFrame(arrays.size),
            price=pd.DataFrame(arrays.price),
            size_type="amount",
            direction="both",
            fees=0.0,
            fixed_fees=0.0,
            slippage=0.0,  # 슬리피지는 fill_price 에 이미 내재 — 이중계상 금지.
            init_cash=_INIT_CASH,
            cash_sharing=False,
            group_by=False,
        )
        records = portfolio.trades.records

        # 1. 개수 + 청산 상태.
        if len(records) != arrays.n_cols:
            raise VbtHarnessParityError(
                "vbt trade count " f"{len(records)} != multibar count {arrays.n_cols}"
            )
        if int((records["status"] != _STATUS_CLOSED).sum()) != 0:
            raise VbtHarnessParityError(
                "open trade in vbt records (expected all closed)"
            )

        # 2. col 순 정렬 → 컬럼 i ↔ multibar[i] 대응.
        rec_sorted = records.sort_values("col").reset_index(drop=True)

        # 3. 행별 대조 (idx/price/direction/size/pnl).
        for t, row in zip(arrays.multibar, rec_sorted.itertuples(index=False)):
            dir_code = (
                _DIRECTION_LONG_CODE if t.direction == "long" else _DIRECTION_SHORT_CODE
            )
            # ticks_net 은 계약당 → tick_size × size_contracts 로 총 pnl 환산.
            expected_pnl = t.ticks_net * tick * t.size_contracts
            ok = (
                int(row.entry_idx) == int(t.fill_bar_index)  # type: ignore[arg-type]
                and int(row.exit_idx) == int(t.exit_bar_index)  # type: ignore[arg-type]
                and int(row.direction) == dir_code
                and math.isclose(
                    float(row.entry_price),
                    float(t.fill_price),
                    rel_tol=_PARITY_RTOL,
                    abs_tol=_PARITY_ATOL,
                )
                and math.isclose(
                    float(row.exit_price),
                    float(t.exit_price),
                    rel_tol=_PARITY_RTOL,
                    abs_tol=_PARITY_ATOL,
                )
                and math.isclose(
                    float(row.size),
                    float(t.size_contracts),
                    rel_tol=_PARITY_RTOL,
                    abs_tol=_PARITY_ATOL,
                )
                and math.isclose(
                    float(row.pnl),
                    expected_pnl,
                    rel_tol=_PARITY_RTOL,
                    abs_tol=max(_PARITY_ATOL, abs(expected_pnl) * _PARITY_RTOL),
                )
            )
            if not ok:
                raise VbtHarnessParityError(
                    "from_orders parity mismatch for multibar trade "
                    f"(setup={t.setup_type}, fill_bar={t.fill_bar_index}, "
                    f"exit_bar={t.exit_bar_index}): vbt row={row} vs "
                    f"harness ticks_net={t.ticks_net} size={t.size_contracts}"
                )

        return float(records["pnl"].sum())
