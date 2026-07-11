#!/usr/bin/env python
"""VectorbtRunner vs legacy BacktestEngine parity 리포트 생성기 (P3-b/WS-A4).

합성 시나리오 × 리스크 매트릭스 + (호스트에 parquet 이 있으면) 실데이터
williams_r 윈도우에 대해 두 엔진을 돌리고 지표 델타 표와 Optuna-style
스윕 속도 비교를 markdown 으로 출력한다.

시나리오/전략/완화설정은 머지 게이트인
``tests/unit/backtest/test_vbt_runner.py`` / ``test_vbt_runner_realdata.py``
에서 **직접 import** 한다 — 리포트가 게이트와 다른 매트릭스를 돌려 놓고
PASS 를 찍는 드리프트를 구조적으로 차단하기 위함이다.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/vbt_parity_report.py \
        [--out docs/plans/2026-07-10-vbt-parity-report.md]

vectorbt(`pip install -e ".[backtest]"`) + dev extra 필요. 실데이터 섹션은
`data/market/stock/minute` 이 없으면 자동 생략된다. 어느 한 셀이라도
parity 가 깨지면 exit code 1 (실데이터 포함).
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.config import RiskConfig
from shared.backtest.vbt_harness_runner import (
    VbtHarnessParityError,
    _build_order_arrays,
)
from shared.backtest.vbt_runner import VectorbtRunner

# 게이트 테스트의 시나리오/전략/윈도우를 그대로 소비한다 (드리프트 차단).
from tests.unit.backtest.test_vbt_harness_runner import (
    HARNESS_PARITY_SCENARIOS,
    run_harness_and_runner,
)
from tests.unit.backtest.test_vbt_runner import (
    _REAL_EXIT_FACTORIES,
    _REAL_EXIT_RISK,
    _REAL_EXIT_SCENARIOS,
    _RISK_VARIANTS,
    _SCENARIOS,
    _make_minute_data,
    _MeanRevertStrategy,
)
from tests.unit.backtest.test_vbt_runner_realdata import (
    _END as _REAL_END,
)
from tests.unit.backtest.test_vbt_runner_realdata import (
    _START as _REAL_START,
)
from tests.unit.backtest.test_vbt_runner_realdata import (
    _SYMBOL as _REAL_SYMBOL,
)
from tests.unit.backtest.test_vbt_runner_realdata import (
    _load_config as _load_relaxed_williams_r_config,
)

logging.disable(logging.WARNING)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "plans" / "2026-07-10-vbt-parity-report.md"


def _delta_row(label, res_l, res_v):
    trades_match = (
        all(a.to_dict() == b.to_dict() for a, b in zip(res_l.trades, res_v.trades))
        and res_l.total_trades == res_v.total_trades
    )
    eq_l = np.array([v for _, v in res_l.equity_curve])
    eq_v = np.array([v for _, v in res_v.equity_curve])
    eq_max = float(np.max(np.abs(eq_l - eq_v))) if len(eq_l) else 0.0
    return {
        "label": label,
        "trades": res_l.total_trades,
        "trades_match": trades_match,
        "d_return": abs(res_l.total_return_pct - res_v.total_return_pct),
        "d_sharpe": abs(res_l.sharpe_ratio - res_v.sharpe_ratio),
        "d_mdd": abs(res_l.max_drawdown_pct - res_v.max_drawdown_pct),
        "d_final": abs(res_l.final_capital - res_v.final_capital),
        "eq_max": eq_max,
        "reasons_match": res_l.exit_reasons == res_v.exit_reasons,
        "dict_match": res_l.to_dict() == res_v.to_dict(),
    }


def run_synthetic_matrix() -> list[dict]:
    rows = []
    for s_name, s_fn in _SCENARIOS.items():
        data = s_fn()  # 시나리오당 1회 생성 (리스크 변형과 무관)
        for r_name, r_dict in _RISK_VARIANTS.items():
            config = BacktestConfig.stock(initial_capital=10_000_000)
            config.risk = RiskConfig.from_dict(r_dict)
            res_l = BacktestEngine(_MeanRevertStrategy(), config).run(data.copy())
            res_v = VectorbtRunner(_MeanRevertStrategy(), config).run(data.copy())
            rows.append(_delta_row(f"{s_name} × {r_name}", res_l, res_v))
    # 동일 bar 청산→재진입 케이스 (게이트 테스트와 동일 파라미터)
    data = _make_minute_data(seed=7, days=2)
    config = BacktestConfig.stock(initial_capital=10_000_000)

    def mk():
        return _MeanRevertStrategy(buy_gap=1.0, sell_gap=1.02, profit_target=1.001)

    res_l = BacktestEngine(mk(), config).run(data.copy())
    res_v = VectorbtRunner(mk(), config).run(data.copy())
    rows.append(_delta_row("same_bar_reentry × default", res_l, res_v))
    return rows


def run_real_exit_matrix() -> list[dict]:
    """P3-c 허용목록 exit(실 클래스) 매트릭스 — 게이트 픽스처 그대로 소비.

    atr_dynamic / atr_dynamic_decay(배포 momentum_breakout 설정) /
    chandelier_exit 를 TestRealExitParity 와 동일한 시나리오 × 리스크로 이중
    구동한다. 이 행들도 exit code 판정(_all_pass)에 포함된다.
    """
    rows = []
    for e_name, factory in _REAL_EXIT_FACTORIES.items():
        for s_name, s_fn in _REAL_EXIT_SCENARIOS.items():
            data = s_fn()
            for r_name, r_dict in _REAL_EXIT_RISK.items():
                config = BacktestConfig.stock(initial_capital=10_000_000)
                config.risk = RiskConfig.from_dict(r_dict)
                res_l = BacktestEngine(factory(), config).run(data.copy())
                res_v = VectorbtRunner(factory(), config).run(data.copy())
                rows.append(_delta_row(f"{e_name} × {s_name} × {r_name}", res_l, res_v))
    return rows


def run_futures_matrix() -> list[dict]:
    """P3-d 선물 harness 매트릭스 — harness 원장 ↔ from_orders 원장 대조.

    주식 섹션(legacy `BacktestEngine` vs `VectorbtRunner` 두 **독립 엔진** 비교)과
    달리, 여기서는 harness 가 유일 엔진이다. 검증 대상은 harness(SoT)의 트레이드
    레코드로 세운 ``vbt.Portfolio.from_orders`` 원장이 harness 의 tick 회계를
    재현하는지 — **같은 계산의 두 원장 구성**이지 두 엔진의 결과 비교가 아니다.
    게이트 픽스처(``test_vbt_harness_runner``)를 그대로 소비해 리포트/게이트
    드리프트를 구조적으로 차단한다. 이 행들도 exit code 판정(_futures_all_pass)에
    포함된다.
    """
    rows = []
    for label, factory in HARNESS_PARITY_SCENARIOS.items():
        df, script, sizer, eq = factory()
        try:
            _, runner_result = run_harness_and_runner(
                df, script, sizer=sizer, account_equity_krw=eq
            )
            trades = runner_result.trades
            parity_ok = True
        except VbtHarnessParityError:
            trades = []
            parity_ok = False
        arrays = _build_order_arrays(trades, len(df))
        rows.append(
            {
                "label": label,
                "trades": len(trades),
                "multibar": len(arrays.multibar),
                "samebar": len(arrays.samebar),
                "parity_ok": parity_ok,
            }
        )
    return rows


def run_real_data() -> dict | None:
    data_dir = _REPO_ROOT / "data" / "market" / "stock" / "minute"
    if not data_dir.exists():
        return None
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.storage.market_data_store import load_market_bars_for_backtest
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()
    df = load_market_bars_for_backtest(
        symbol=_REAL_SYMBOL,
        asset_class="stock",
        timeframe="minute",
        start=_REAL_START,
        end=_REAL_END,
    )
    if df.empty:
        return None

    sc = _load_relaxed_williams_r_config()
    bt = sc["strategy"]["backtest"]
    pp = sc["strategy"]["position"]["params"]
    config = BacktestConfig.stock(
        initial_capital=float(bt["initial_capital"]),
        order_amount_per_stock=float(pp.get("order_amount_per_stock", 0)) or None,
        max_positions=int(pp.get("max_positions", 5)),
    )
    config.risk = RiskConfig.from_dict(bt["risk"])

    def adapter():
        return BacktestStrategyAdapter(StrategyFactory.create(sc), sc)

    t0 = time.perf_counter()
    res_l = BacktestEngine(adapter(), config).run(df.copy())
    t1 = time.perf_counter()
    res_v = VectorbtRunner(adapter(), config).run(df.copy())
    t2 = time.perf_counter()
    row = _delta_row(
        f"williams_r × {_REAL_SYMBOL} minute {_REAL_START}~{_REAL_END}", res_l, res_v
    )
    row["bars"] = len(df)
    row["t_legacy"] = t1 - t0
    row["t_vbt"] = t2 - t1
    row["exit_reasons"] = res_l.exit_reasons
    return row


def run_speed_sweep(n_evals: int = 20) -> dict:
    """Optuna-style 파라미터 스윕 (n_evals × 양 엔진) 벽시계 비교."""
    data = _make_minute_data(seed=42, days=4)
    rng = np.random.default_rng(0)
    params = [
        {
            "buy_gap": float(1 - rng.uniform(0.001, 0.006)),
            "profit_target": float(1 + rng.uniform(0.001, 0.008)),
        }
        for _ in range(n_evals)
    ]
    config = BacktestConfig.stock(initial_capital=10_000_000)

    # warmup (vectorbt/numba JIT 1회 비용 제외)
    VectorbtRunner(_MeanRevertStrategy(), config).run(data.copy())

    t0 = time.perf_counter()
    for p in params:
        BacktestEngine(_MeanRevertStrategy(**p), config).run(data.copy())
    t_legacy = time.perf_counter() - t0

    t0 = time.perf_counter()
    for p in params:
        VectorbtRunner(_MeanRevertStrategy(**p), config).run(data.copy())
    t_vbt = time.perf_counter() - t0

    return {
        "n_evals": n_evals,
        "bars": len(data),
        "t_legacy": t_legacy,
        "t_vbt": t_vbt,
        "ratio": t_vbt / t_legacy if t_legacy > 0 else float("nan"),
    }


def render(
    rows: list[dict],
    exit_rows: list[dict],
    real: dict | None,
    speed: dict,
    futures_rows: list[dict],
) -> str:
    import vectorbt as vbt

    lines: list[str] = []
    a = lines.append
    a("# VectorbtRunner Parity Report (P3-b/P3-c / WS-A4 gate evidence)")
    a("")
    a(
        f"- 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST, "
        f"`scripts/vbt_parity_report.py`"
    )
    a(
        f"- vectorbt {vbt.__version__} / legacy `shared/backtest/engine.py` "
        f"BacktestEngine"
    )
    a(
        "- Plan: `docs/plans/2026-07-08-new-architecture-refactoring-plan.md` §5, "
        "`docs/plans/2026-07-05-indicator-engine-and-stream-schema-roadmap.md` §WS-A4"
    )
    a(
        "- 러너: `shared/backtest/vbt_runner.py` (opt-in `strategy.backtest.engine: "
        "vectorbt`; 기본값 legacy)"
    )
    a(
        "- 시나리오·전략·완화설정은 머지 게이트 테스트 모듈에서 직접 import — "
        "리포트와 게이트가 항상 같은 매트릭스를 돌린다."
    )
    a(
        "- CI: 게이트 잡(`test`)은 vectorbt 미설치라 vectorbt-의존 parity 케이스를 "
        "skip 하고 마스킹/게이트/seam 계층만 강제한다. parity 스위트 전체는 "
        "advisory `backtest-extra` 레인과 이 스크립트(배포 호스트)에서 돈다 — "
        "**운영자 flip 전 재실행 필수** (exit code 가 실데이터 포함 전 셀 판정)."
    )
    a("")
    a("## 허용오차 정책")
    a("")
    a("| 항목 | 정책 |")
    a("|---|---|")
    a(
        "| 트레이드 시퀀스 (시각/가격/수량/pnl/사유) | **완전 일치** (`to_dict()` 동등) |"
    )
    a(
        "| final capital / Sharpe / Sortino / exit_reasons | **bit-동일** (resolver 가 "
        "legacy 연산 순서 유지) |"
    )
    # 관측 잔차는 하드코딩하지 않고 이번 실행의 실측치에서 계산한다 —
    # 표와 헤드라인이 어긋난 채 커밋되는 드리프트 방지 (리뷰 지적 사항).
    all_synth = rows + exit_rows
    synth_eq_max = max(r["eq_max"] for r in all_synth) if all_synth else 0.0
    real_obs = f", 실데이터 ≤{real['eq_max']:.1e}" if real is not None else ""
    a(
        "| 자산곡선 / MDD | vectorbt cash·assets 시프트 재구성 — 부동소수 결합순서 "
        "ulp 잔차만 허용 (합성 `atol=1e-6` KRW / 실데이터 1e8 자본 스케일 "
        f"`atol=1e-4` KRW; 이번 실행 관측치: 합성 ≤{synth_eq_max:.1e}"
        f"{real_obs}) |"
    )
    a("| `result.to_dict()` (라운딩 후) | **완전 일치** |")
    a("")
    a(
        "초과 드리프트는 `tests/unit/backtest/test_vbt_runner.py` parity 스위트가 "
        "실패시킨다 (머지 게이트)."
    )
    a("")

    def _matrix_table(matrix_rows: list[dict]) -> None:
        a(
            "| 케이스 | trades | trade seq | Δreturn(%p) | ΔSharpe | "
            "ΔMDD(%p) | Δfinal(KRW) | equity maxΔ(KRW) | reasons | to_dict |"
        )
        a("|---" * 10 + "|")
        for r in matrix_rows:
            a(
                f"| {r['label']} | {r['trades']} | "
                f"{'✅ exact' if r['trades_match'] else '❌'} | "
                f"{r['d_return']:.2e} | {r['d_sharpe']:.2e} | {r['d_mdd']:.2e} | "
                f"{r['d_final']:.2e} | {r['eq_max']:.2e} | "
                f"{'✅' if r['reasons_match'] else '❌'} | "
                f"{'✅' if r['dict_match'] else '❌'} |"
            )

    a("## 합성 시나리오 × 리스크 매트릭스 (P3-b, 합성 진입+청산 전략)")
    a("")
    _matrix_table(rows)
    a("")
    a("## 실 exit 생성기 매트릭스 (P3-c 허용목록 증거)")
    a("")
    a(
        "실제 exit 클래스 인스턴스(ATRDynamicExit / ChandelierExit — "
        "`atr_dynamic_decay` 는 배포 momentum_breakout 의 exit 설정 그대로)를 "
        "TestRealExitParity 와 동일한 픽스처로 이중 구동. 트레이드 시퀀스는 "
        "가격 포함 **완전 일치** 기준이다(러너가 트레이드 가격을 resolver "
        "이벤트의 bar 종가 원본에서 채움)."
    )
    a("")
    _matrix_table(exit_rows)
    a("")
    a("## 선물 harness 매트릭스 (P3-d — resolver 원장 ↔ from_orders 원장)")
    a("")
    a(
        "`shared/backtest/vbt_harness_runner.py::VbtHarnessRunner` 는 선물 harness의 "
        "**컴포지션 래퍼**다 — `BacktestDecisionHarness` 가 여전히 SoT(결과 무변형 "
        "반환)이고, 이 섹션은 그 harness 트레이드 레코드로 세운 "
        "`vbt.Portfolio.from_orders` 원장이 harness 의 tick 회계를 재현하는지를 "
        "검증한다. **주의**: 위 주식 섹션과 달리 이것은 legacy-vs-vbt 두 독립 "
        "엔진 비교가 아니라 **harness resolver 원장 ↔ from_orders 원장 구성** "
        "대조다(harness 가 유일 엔진). 멀티바 트레이드(`exit_bar > fill_bar`)만 "
        "컬럼당 1개로 `from_orders` 에 태우고, 같은-bar 트레이드(`==`, EOD-on-fill/"
        "last-bar)는 표현 불가라 종가 일치로 해석 검증한다. 픽스처는 게이트 "
        "`tests/unit/backtest/test_vbt_harness_runner.py` 를 그대로 import."
    )
    a("")
    a("| 케이스 | trades | multibar | samebar | parity |")
    a("|---|---|---|---|---|")
    for r in futures_rows:
        a(
            f"| {r['label']} | {r['trades']} | {r['multibar']} | "
            f"{r['samebar']} | {'✅' if r['parity_ok'] else '❌'} |"
        )
    a("")
    if real is not None:
        a("## 실데이터 — williams_r (활성 주식 전략, 레지스트리 경로)")
        a("")
        a(
            f"- 데이터: `{_REAL_SYMBOL}` 실 분봉 parquet {real['bars']} bars, "
            f"{_REAL_START} ~ {_REAL_END} (KST)"
        )
        a(
            "- 경로: `StrategyFactory` → `BacktestStrategyAdapter` → 양 엔진 "
            "(fresh adapter 각각)"
        )
        a(
            "- 엔트리 게이트 완화: `market_state_filter/trend_filter/volume_confirm` "
            "off, cooldown 1800s — 해당 필터는 이 윈도우에서 신호를 전부 차단"
            "(backtest 경로는 일봉 미시딩 → trend_filter 상시 False). parity 는 "
            "*동일 신호에 대한 체결/포트폴리오 계층* 검증이므로 유효하며, 완화는 "
            "양 엔진에 동일 적용됐다 (설정 소스: test_vbt_runner_realdata._load_config)."
        )
        a("")
        a("| 항목 | 값 |")
        a("|---|---|")
        a(f"| trades | {real['trades']} ({real['exit_reasons']}) |")
        a(f"| trade seq | {'✅ exact' if real['trades_match'] else '❌'} |")
        a(
            f"| Δreturn / ΔSharpe / ΔMDD | {real['d_return']:.2e} / "
            f"{real['d_sharpe']:.2e} / {real['d_mdd']:.2e} |"
        )
        a(f"| Δfinal capital | {real['d_final']:.2e} KRW |")
        a(f"| equity maxΔ | {real['eq_max']:.2e} KRW |")
        a(f"| to_dict 일치 | {'✅' if real['dict_match'] else '❌'} |")
        a(
            f"| 실행 시간 | legacy {real['t_legacy']:.1f}s / vectorbt "
            f"{real['t_vbt']:.1f}s |"
        )
        a("")
    a("## 속도 — Optuna-style 스윕 (비게이트, 참고용)")
    a("")
    a(
        f"- 합성 {speed['bars']} bars × {speed['n_evals']} param evals, "
        "JIT warmup 제외"
    )
    a(
        f"- 경량 합성 전략: legacy {speed['t_legacy']:.2f}s / vectorbt runner "
        f"{speed['t_vbt']:.2f}s → **vectorbt 가 {speed['ratio']:.2f}× 느림** "
        f"(eval 당 vbt Portfolio 구성 고정 오버헤드 "
        f"~{(speed['t_vbt'] - speed['t_legacy']) / speed['n_evals'] * 1000:.0f}ms)"
    )
    if real is not None and real.get("t_legacy"):
        a(
            f"- 실전략(williams_r, {real['bars']} bars): legacy "
            f"{real['t_legacy']:.1f}s / vectorbt {real['t_vbt']:.1f}s → "
            f"**{real['t_vbt'] / real['t_legacy']:.2f}×** — 시그널 생성(어댑터/"
            "지표)이 지배해 오버헤드가 상쇄됨"
        )
    a("")
    a(
        "**정직한 결론**: 현 단계 러너는 시그널 생성을 legacy 와 동일한 어댑터 "
        "순차 패스로 수행하므로(신호 parity 를 구조적으로 보장하기 위한 설계) "
        "스윕 가속은 아직 없다 — 트리비얼 전략에선 오히려 vbt 고정비만큼 느리고, "
        "실전략에선 동률이다. 본격적 벡터화 가속은 P1/P2(선언형 조건 → boolean "
        "배열 사전계산)가 어댑터 순차 패스를 대체할 때 실현된다 — plan §5 P3-a "
        "첫 항목. 이 PR 의 가치는 속도가 아니라 **계약 이전**(BacktestResult 를 "
        "vectorbt Portfolio 원장으로 채우는 검증된 경로 + parity 게이트)이다."
    )
    a("")
    a("## Fill-model 매핑 노트 (요약)")
    a("")
    a("`shared/backtest/vbt_runner.py` 모듈 docstring 이 정본. 요점:")
    a("")
    a(
        "1. 체결 시점: legacy 는 시그널 bar 의 **종가**에 즉시 체결 — "
        "`Portfolio.from_orders(price=close)` 로 재현. look-ahead 없음 "
        "(진입이 legacy 보다 이른 bar 에 체결될 수 없음)."
    )
    a(
        "2. 한국 비용 모델(매도세 비대칭)은 vbt `fees`(양측 비율)로 표현 불가 → "
        "주문별 절대 `fixed_fees` 로 정확 매핑 (현금 흐름 잔차 0)."
    )
    a(
        "3. legacy `BacktestTrade.pnl` 은 진입비 제외 규약 → vbt 트레이드 pnl "
        "+ entry_fees 로 보정 (cross-check 로 강제)."
    )
    a(
        "4. Sharpe/Sortino 는 legacy 자체 정의(일별 실현 PnL KRW) 재현 — "
        "vbt 네이티브 통계 전환은 legacy 제거 시 별도 결정."
    )
    a(
        "5. 동일 bar 청산→재진입: 2컬럼 cash-sharing 그룹 + per-bar `call_seq` 로 "
        "매핑 (매도 정산 후 매수 순서 보존)."
    )
    a(
        "6. 미지원(→`NotImplementedError`, legacy 폴백): vectorbt 미설치 환경, "
        "선물, ATS, 멀티심볼 프레임, 공매도 진입, regime gate 경로, "
        "DailyBacktestAdapter(일봉 어댑터) 경로(parity 미검증 — daily 전략은 "
        "exit 가 허용목록에 있어도 legacy), 허용목록 밖 exit 생성기(허용목록 = "
        "williams_r_exit / atr_dynamic / chandelier_exit — P3-c 확장; "
        "three_stage 는 부분청산이라 구조적 표현 불가로 영구 제외), 마지막 bar "
        "진입+동일 bar END_OF_DATA 청산. 상태머신 exit 강제 전략은 "
        "`backtest.legacy_exit: true` 로 legacy 를 명시 강제할 수 있다(P3-c "
        "escape hatch). 러너 내부 cross-check 불일치(`VectorbtParityError`)도 "
        "seam 에서 legacy 폴백된다(심볼 드랍 아님, 조사용 경고)."
    )
    a("")
    a("## 판정")
    a("")
    stock_ok = _all_pass(rows + exit_rows, real)
    futures_ok = _futures_all_pass(futures_rows)
    a(
        "**PASS** — 주식(합성 + 실 exit 생성기 + 실데이터) 트레이드 시퀀스/지표 "
        "일치 **및** 선물 harness resolver 원장 ↔ from_orders 원장 tick 회계 일치 "
        "(허용오차 내)."
        if (stock_ok and futures_ok)
        else "**FAIL** — 위 표에서 ❌ 항목 확인 "
        f"(주식 {'PASS' if stock_ok else 'FAIL'} / "
        f"선물 {'PASS' if futures_ok else 'FAIL'})."
    )
    a("")
    a(
        "운영자 flip(experiment 경로 `backtest.engine: vectorbt`) 은 본 증거 + "
        "paper 관찰을 근거로 별도 게이트에서 결정한다. 이 PR 은 기본값을 "
        "변경하지 않는다."
    )
    a("")
    return "\n".join(lines)


def _all_pass(rows: list[dict], real: dict | None) -> bool:
    """합성 + 실데이터 전 셀 판정 (exit code 와 markdown 판정의 단일 소스)."""
    ok = all(r["trades_match"] and r["dict_match"] for r in rows)
    if real is not None:
        ok = ok and real["trades_match"] and real["dict_match"]
    return ok


def _futures_all_pass(rows: list[dict]) -> bool:
    """선물 harness 매트릭스 전 셀 parity 판정 (exit code/markdown 단일 소스)."""
    return all(r["parity_ok"] for r in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    print("running synthetic matrix ...")
    rows = run_synthetic_matrix()
    print("running real-exit matrix (P3-c) ...")
    exit_rows = run_real_exit_matrix()
    print("running futures harness matrix (P3-d) ...")
    futures_rows = run_futures_matrix()
    print("running real-data window ...")
    real = run_real_data()
    print("running speed sweep ...")
    speed = run_speed_sweep()

    report = render(rows, exit_rows, real, speed, futures_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out}")
    all_rows = rows + exit_rows
    stock_ok = _all_pass(all_rows, real)
    futures_ok = _futures_all_pass(futures_rows)
    if not (stock_ok and futures_ok):
        bad = [
            r["label"] for r in all_rows if not (r["trades_match"] and r["dict_match"])
        ]
        if real is not None and not (real["trades_match"] and real["dict_match"]):
            bad.append(real["label"])
        bad += [f"futures:{r['label']}" for r in futures_rows if not r["parity_ok"]]
        raise SystemExit(f"parity FAILED: {bad}")


if __name__ == "__main__":
    main()
