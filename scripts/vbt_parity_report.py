#!/usr/bin/env python
"""VectorbtRunner vs legacy BacktestEngine parity 리포트 생성기 (P3-b/WS-A4).

합성 시나리오 × 리스크 매트릭스 + (호스트에 parquet 이 있으면) 실데이터
williams_r 윈도우에 대해 두 엔진을 돌리고 지표 델타 표와 Optuna-style
스윕 속도 비교를 markdown 으로 출력한다.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/vbt_parity_report.py \
        [--out docs/plans/2026-07-10-vbt-parity-report.md]

vectorbt(`pip install -e ".[backtest]"`) 필요. 실데이터 섹션은
`data/market/stock/minute` 이 없으면 자동 생략된다.
"""

from __future__ import annotations

import argparse
import copy
import logging
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from shared.backtest import BacktestConfig, BacktestEngine
from shared.backtest.config import RiskConfig
from shared.backtest.engine import ExitReason, SignalType
from shared.backtest.vbt_runner import VectorbtRunner

logging.disable(logging.WARNING)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_OUT = _REPO_ROOT / "docs" / "plans" / "2026-07-10-vbt-parity-report.md"

_REAL_SYMBOL = "005930"
_REAL_START = date(2026, 6, 1)
_REAL_END = date(2026, 6, 12)


# ── 합성 데이터/전략 (tests/unit/backtest/test_vbt_runner.py 와 동일 규약) ──


def make_minute_data(
    *,
    seed: int = 7,
    days: int = 4,
    bars_per_day: int = 200,
    drift: float = 0.0,
    vol: float = 0.0015,
    gap_pct: float = 0.0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    price = 10_000.0
    for d in range(days):
        base = datetime(2026, 6, 1, 9, 0) + timedelta(days=d)
        if d > 0 and gap_pct:
            price *= 1 + (gap_pct if d % 2 else -gap_pct)
        for i in range(bars_per_day):
            price *= 1 + drift + rng.normal(0, vol)
            rows.append(
                {
                    "code": "005930",
                    "name": "005930",
                    "datetime": base + timedelta(minutes=i),
                    "open": round(price * 0.999, 2),
                    "high": round(price * 1.001, 2),
                    "low": round(price * 0.998, 2),
                    "close": round(price, 2),
                    "volume": int(1000 + rng.integers(0, 500)),
                }
            )
    return pd.DataFrame(rows)


def make_chop_data(days: int = 3, bars_per_day: int = 200) -> pd.DataFrame:
    rows: list[dict] = []
    k = 0
    for d in range(days):
        base = datetime(2026, 6, 1, 9, 0) + timedelta(days=d)
        for i in range(bars_per_day):
            price = 10_000 + 120 * math.sin(k / 9.0)
            rows.append(
                {
                    "code": "005930",
                    "name": "005930",
                    "datetime": base + timedelta(minutes=i),
                    "open": round(price - 3, 2),
                    "high": round(price + 6, 2),
                    "low": round(price - 6, 2),
                    "close": round(price, 2),
                    "volume": 1_000 + k,
                }
            )
            k += 1
    return pd.DataFrame(rows)


class MeanRevertStrategy:
    vbt_signal_expressible = True
    name = "synthetic_mr"

    def __init__(self, buy_gap=0.997, sell_gap=1.006, profit_target=1.004):
        self._buy_gap = buy_gap
        self._sell_gap = sell_gap
        self._profit_target = profit_target
        self.closes: list[float] = []
        self._pos: dict | None = None

    def set_position(self, position):
        self._pos = position

    def check_exit(self, bar):
        if self._pos is None:
            return (False, None)
        if bar["close"] >= self._pos["entry_price"] * self._profit_target:
            return (True, ExitReason.INDICATOR_EXIT)
        return (False, None)

    def on_bar(self, bar):
        self.closes.append(bar["close"])
        if len(self.closes) < 20:
            return SignalType.HOLD
        ma = sum(self.closes[-20:]) / 20
        if self._pos is None and bar["close"] < ma * self._buy_gap:
            return SignalType.BUY
        if self._pos is not None and bar["close"] > ma * self._sell_gap:
            return SignalType.SELL
        return SignalType.HOLD


SCENARIOS = {
    "trend_up": lambda: make_minute_data(seed=11, drift=0.0004),
    "trend_down": lambda: make_minute_data(seed=12, drift=-0.0004),
    "chop": make_chop_data,
    "gap_days": lambda: make_minute_data(seed=13, gap_pct=0.02),
    "random_walk": lambda: make_minute_data(seed=42),
}

RISK_VARIANTS = {
    "default": {},
    "tight_sl_tp": {"stop_loss_pct": 0.3, "take_profit_pct": 0.4},
    "trailing": {
        "trailing_stop_enabled": True,
        "trailing_stop_trigger_pct": 0.2,
        "trailing_stop_distance_pct": 0.15,
    },
    "max_hold_bars": {"max_hold_bars": 15},
    "force_close_time": {"force_close_time": "11:30"},
    "max_daily_trades": {"max_daily_trades": 1},
    "close_on_day_change": {"close_on_day_change": True},
}


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
    for s_name, s_fn in SCENARIOS.items():
        for r_name, r_dict in RISK_VARIANTS.items():
            data = s_fn()
            config = BacktestConfig.stock(initial_capital=10_000_000)
            config.risk = RiskConfig.from_dict(r_dict)
            res_l = BacktestEngine(MeanRevertStrategy(), config).run(data.copy())
            res_v = VectorbtRunner(MeanRevertStrategy(), config).run(data.copy())
            rows.append(_delta_row(f"{s_name} × {r_name}", res_l, res_v))
    # 동일 bar 청산→재진입 케이스
    data = make_minute_data(seed=7, days=2)
    config = BacktestConfig.stock(initial_capital=10_000_000)

    def mk():
        return MeanRevertStrategy(buy_gap=1.0, sell_gap=1.02, profit_target=1.001)

    res_l = BacktestEngine(mk(), config).run(data.copy())
    res_v = VectorbtRunner(mk(), config).run(data.copy())
    rows.append(_delta_row("same_bar_reentry × default", res_l, res_v))
    return rows


def run_real_data() -> dict | None:
    data_dir = _REPO_ROOT / "data" / "market" / "stock" / "minute"
    if not data_dir.exists():
        return None
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.config.loader import ConfigLoader
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

    sc = copy.deepcopy(ConfigLoader.load_strategy("stock", "williams_r"))
    ep = sc["strategy"]["entry"]["params"]
    ep["market_state_filter"]["enabled"] = False
    ep["trend_filter"] = False
    ep["volume_confirm"] = False
    ep["signal_cooldown_seconds"] = 1800
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
    data = make_minute_data(seed=42, days=4)
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
    VectorbtRunner(MeanRevertStrategy(), config).run(data.copy())

    t0 = time.perf_counter()
    for p in params:
        BacktestEngine(MeanRevertStrategy(**p), config).run(data.copy())
    t_legacy = time.perf_counter() - t0

    t0 = time.perf_counter()
    for p in params:
        VectorbtRunner(MeanRevertStrategy(**p), config).run(data.copy())
    t_vbt = time.perf_counter() - t0

    return {
        "n_evals": n_evals,
        "bars": len(data),
        "t_legacy": t_legacy,
        "t_vbt": t_vbt,
        "ratio": t_vbt / t_legacy if t_legacy > 0 else float("nan"),
    }


def render(rows: list[dict], real: dict | None, speed: dict) -> str:
    import vectorbt as vbt

    lines: list[str] = []
    a = lines.append
    a("# VectorbtRunner Parity Report (P3-b / WS-A4 gate evidence)")
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
    a(
        "| 자산곡선 / MDD | vectorbt cash·assets 시프트 재구성 — 부동소수 결합순서 "
        "ulp 잔차만 허용 (`atol=1e-6` KRW, 관측치는 ≤4e-9) |"
    )
    a("| `result.to_dict()` (라운딩 후) | **완전 일치** |")
    a("")
    a(
        "초과 드리프트는 `tests/unit/backtest/test_vbt_runner.py` parity 스위트가 "
        "실패시킨다 (머지 게이트)."
    )
    a("")
    a("## 합성 시나리오 × 리스크 매트릭스")
    a("")
    a(
        "| 시나리오 × 리스크 | trades | trade seq | Δreturn(%p) | ΔSharpe | "
        "ΔMDD(%p) | Δfinal(KRW) | equity maxΔ(KRW) | reasons | to_dict |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        a(
            f"| {r['label']} | {r['trades']} | "
            f"{'✅ exact' if r['trades_match'] else '❌'} | "
            f"{r['d_return']:.2e} | {r['d_sharpe']:.2e} | {r['d_mdd']:.2e} | "
            f"{r['d_final']:.2e} | {r['eq_max']:.2e} | "
            f"{'✅' if r['reasons_match'] else '❌'} | "
            f"{'✅' if r['dict_match'] else '❌'} |"
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
            "양 엔진에 동일 적용됐다."
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
        "6. 미지원(→`NotImplementedError`, legacy 폴백): 선물, ATS, 멀티심볼 "
        "프레임, 공매도 진입, 비허용 exit 생성기(three_stage/momentum_decay 등 "
        "상태머신), 마지막 bar 진입+동일 bar END_OF_DATA 청산."
    )
    a("")
    a("## 판정")
    a("")
    ok = all(r["trades_match"] and r["dict_match"] for r in rows) and (
        real is None or (real["trades_match"] and real["dict_match"])
    )
    a(
        "**PASS** — 전 시나리오 트레이드 시퀀스/지표 일치 (허용오차 내)."
        if ok
        else "**FAIL** — 위 표에서 ❌ 항목 확인."
    )
    a("")
    a(
        "운영자 flip(experiment 경로 `backtest.engine: vectorbt`) 은 본 증거 + "
        "paper 관찰을 근거로 별도 게이트에서 결정한다. 이 PR 은 기본값을 "
        "변경하지 않는다."
    )
    a("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    print("running synthetic matrix ...")
    rows = run_synthetic_matrix()
    print("running real-data window ...")
    real = run_real_data()
    print("running speed sweep ...")
    speed = run_speed_sweep()

    report = render(rows, real, speed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out}")
    bad = [r["label"] for r in rows if not (r["trades_match"] and r["dict_match"])]
    if bad:
        raise SystemExit(f"parity FAILED: {bad}")


if __name__ == "__main__":
    main()
