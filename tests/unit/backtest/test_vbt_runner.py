"""VectorbtRunner 테스트 — import 격리 / expressibility 게이트 / parity (P3-a/b).

3개 층위:

1. **Import 격리**: vectorbt 가 설치돼 있지 않아도(`sys.meta_path` 마스킹
   서브프로세스) `import shared.backtest` / `shared.backtest.vbt_runner` 와
   expressibility 게이트가 동작해야 한다 — vectorbt 는 lazy import 계약.
2. **Expressibility 게이트**: 미지원 조합(선물/ATS/멀티심볼/비허용 exit/
   공매도/opt-in 누락)은 vectorbt 를 건드리기 전에 NotImplementedError 를
   던져 legacy 폴백을 유도한다. (이 층위도 vectorbt 불필요.)
3. **Parity 게이트 (P3-b)**: 합성 시나리오(추세/횡보/갭) × 리스크 설정
   매트릭스에서 legacy BacktestEngine 과 트레이드 시퀀스/지표가 일치해야
   한다. vectorbt 필요 → `pytest.importorskip`.
"""

from __future__ import annotations

import math
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.backtest.config import BacktestConfig, RiskConfig
from shared.backtest.engine import BacktestEngine, ExitReason, SignalType
from shared.backtest.vbt_runner import (
    EXPRESSIBLE_EXIT_GENERATORS,
    VectorbtRunner,
)

pytestmark = pytest.mark.backtest

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Synthetic data builders — deterministic scenarios
# ---------------------------------------------------------------------------


def _make_minute_data(
    *,
    seed: int = 7,
    days: int = 4,
    bars_per_day: int = 200,
    drift: float = 0.0,
    vol: float = 0.0015,
    gap_pct: float = 0.0,
    code: str = "005930",
) -> pd.DataFrame:
    """분봉 합성 OHLCV. gap_pct != 0 이면 일 경계마다 ±갭을 교대로 넣는다."""
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
                    "code": code,
                    "name": code,
                    "datetime": base + timedelta(minutes=i),
                    "open": round(price * 0.999, 2),
                    "high": round(price * 1.001, 2),
                    "low": round(price * 0.998, 2),
                    "close": round(price, 2),
                    "volume": int(1000 + rng.integers(0, 500)),
                }
            )
    return pd.DataFrame(rows)


def _make_chop_data(days: int = 3, bars_per_day: int = 200) -> pd.DataFrame:
    """결정론적 사인파 횡보장."""
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


# ---------------------------------------------------------------------------
# Synthetic strategies (StrategyProtocol + optional check_exit/set_position)
# ---------------------------------------------------------------------------


class _MeanRevertStrategy:
    """20-bar MA 대비 이탈 진입/복귀 청산 — 결정론적, 포지션 동기화 사용.

    ``check_exit`` 는 진입가 대비 수익 목표(engine 이 동기화해 준 포지션
    상태의 결정론적 함수)로, legacy/vbt 러너 양쪽에서 동일하게 평가된다.
    """

    vbt_signal_expressible = True

    def __init__(
        self,
        *,
        buy_gap: float = 0.997,
        sell_gap: float = 1.006,
        profit_target: float = 1.004,
        name: str = "synthetic_mr",
    ):
        self.name = name
        self._buy_gap = buy_gap
        self._sell_gap = sell_gap
        self._profit_target = profit_target
        self.closes: list[float] = []
        self._pos: dict | None = None

    def set_position(self, position: dict | None) -> None:
        self._pos = position

    def check_exit(self, bar: dict) -> tuple[bool, ExitReason | None]:
        if self._pos is None:
            return (False, None)
        if bar["close"] >= self._pos["entry_price"] * self._profit_target:
            return (True, ExitReason.INDICATOR_EXIT)
        return (False, None)

    def on_bar(self, bar: dict) -> SignalType:
        self.closes.append(bar["close"])
        if len(self.closes) < 20:
            return SignalType.HOLD
        ma = sum(self.closes[-20:]) / 20
        if self._pos is None and bar["close"] < ma * self._buy_gap:
            return SignalType.BUY
        if self._pos is not None and bar["close"] > ma * self._sell_gap:
            return SignalType.SELL
        return SignalType.HOLD


class _ShortSeller:
    """플랫 상태에서 SELL 을 내는 전략 — 러너는 명시 거부해야 한다."""

    name = "short_seller"
    vbt_signal_expressible = True

    def __init__(self) -> None:
        self._count = 0

    def on_bar(self, bar: dict) -> SignalType:
        self._count += 1
        return SignalType.SELL if self._count >= 5 else SignalType.HOLD


class _LastBarBuyer:
    """마지막 bar 에서만 BUY — 동일 bar 진입+END_OF_DATA 강제청산 충돌 유도."""

    name = "last_bar_buyer"
    vbt_signal_expressible = True

    def __init__(self, last_idx: int) -> None:
        self._last_idx = last_idx
        self._i = -1

    def on_bar(self, bar: dict) -> SignalType:
        self._i += 1
        return SignalType.BUY if self._i == self._last_idx else SignalType.HOLD


class _FakeExitGenerator:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeTradingStrategy:
    def __init__(self, exit_name: str) -> None:
        self.exit = _FakeExitGenerator(exit_name)


class _FakeAdapter:
    """BacktestStrategyAdapter 모양의 스텁 (`_strategy` 노출)."""

    name = "fake_adapter"

    def __init__(self, exit_name: str) -> None:
        self._strategy = _FakeTradingStrategy(exit_name)

    def on_bar(self, bar: dict) -> SignalType:
        return SignalType.HOLD


# ---------------------------------------------------------------------------
# Parity assertion helper
# ---------------------------------------------------------------------------


def _assert_parity(res_legacy, res_vbt) -> None:
    # 트레이드 시퀀스: 시각/가격/수량/pnl/사유까지 dict 레벨 완전 일치.
    assert res_legacy.total_trades == res_vbt.total_trades
    for a, b in zip(res_legacy.trades, res_vbt.trades):
        assert a.to_dict() == b.to_dict()

    # 자본/지표: legacy 연산 순서를 따르므로 bit-동일 기대.
    assert res_legacy.final_capital == res_vbt.final_capital
    assert res_legacy.sharpe_ratio == res_vbt.sharpe_ratio
    assert res_legacy.sortino_ratio == res_vbt.sortino_ratio
    assert res_legacy.exit_reasons == res_vbt.exit_reasons

    # 직렬화 계약 (라운딩 포함) 동일.
    assert res_legacy.to_dict() == res_vbt.to_dict()

    # 자산곡선: vectorbt cash/assets 시프트 재구성 — 부동소수 결합순서
    # 차이로 ulp 수준 오차만 허용 (문서화된 잔차; vbt_runner docstring §6).
    ts_l = [t for t, _ in res_legacy.equity_curve]
    ts_v = [t for t, _ in res_vbt.equity_curve]
    assert ts_l == ts_v
    eq_l = np.array([v for _, v in res_legacy.equity_curve])
    eq_v = np.array([v for _, v in res_vbt.equity_curve])
    np.testing.assert_allclose(eq_v, eq_l, rtol=0, atol=1e-6)

    # MDD 는 자산곡선 파생 → 동일 잔차 허용.
    assert math.isclose(
        res_legacy.max_drawdown_pct, res_vbt.max_drawdown_pct, abs_tol=1e-9
    )


# ---------------------------------------------------------------------------
# 1. Import isolation — vectorbt 없이 동작해야 하는 것들
# ---------------------------------------------------------------------------


class TestImportIsolation:
    def test_shared_backtest_imports_with_vectorbt_masked(self):
        """`import shared.backtest`(+vbt_runner, 게이트)는 vectorbt 없이 동작.

        서브프로세스에서 meta_path 훅으로 vectorbt import 를 차단해
        '미설치' 환경을 재현한다 (mission 계약: lazy import).
        """
        code = "\n".join(
            [
                "import sys",
                "import importlib.abc",
                "class _Block(importlib.abc.MetaPathFinder):",
                "    def find_spec(self, name, path=None, target=None):",
                "        if name == 'vectorbt' or name.startswith('vectorbt.'):",
                "            raise ImportError('vectorbt masked for test')",
                "        return None",
                "sys.meta_path.insert(0, _Block())",
                "sys.modules.pop('vectorbt', None)",
                "import shared.backtest",
                "from shared.backtest.vbt_runner import (",
                "    VectorbtNotSupportedError, VectorbtRunner)",
                "from shared.backtest.config import BacktestConfig",
                "import pandas as pd",
                "from datetime import datetime",
                "df = pd.DataFrame([{'datetime': datetime(2026, 6, 1, 9, 0),",
                "    'open': 1.0, 'high': 1.0, 'low': 1.0, 'close': 1.0,",
                "    'volume': 1}])",
                "runner = VectorbtRunner(object(), BacktestConfig.futures())",
                "try:",
                "    runner.run(df)",
                "except VectorbtNotSupportedError:",
                "    pass",
                "else:",
                "    raise SystemExit('expected VectorbtNotSupportedError')",
                "print('MASKED-IMPORT-OK')",
            ]
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        assert "MASKED-IMPORT-OK" in proc.stdout


# ---------------------------------------------------------------------------
# 2. Expressibility 게이트 — vectorbt 불필요 (lazy import 이전에 거부)
# ---------------------------------------------------------------------------


class TestExpressibilityGate:
    def test_empty_data_raises_value_error(self):
        runner = VectorbtRunner(_MeanRevertStrategy(), BacktestConfig.stock())
        with pytest.raises(ValueError, match="Empty data"):
            runner.run(pd.DataFrame())

    def test_futures_config_denied(self):
        runner = VectorbtRunner(_MeanRevertStrategy(), BacktestConfig.futures())
        with pytest.raises(NotImplementedError, match="legacy engine required"):
            runner.run(_make_minute_data(days=1))

    def test_ats_enabled_denied(self):
        config = BacktestConfig.stock(ats_enabled=True)
        runner = VectorbtRunner(_MeanRevertStrategy(), config)
        with pytest.raises(NotImplementedError, match="ATS"):
            runner.run(_make_minute_data(days=1))

    def test_multi_symbol_frame_denied(self):
        df = pd.concat(
            [
                _make_minute_data(days=1, code="005930"),
                _make_minute_data(days=1, code="000660"),
            ],
            ignore_index=True,
        )
        runner = VectorbtRunner(_MeanRevertStrategy(), BacktestConfig.stock())
        with pytest.raises(NotImplementedError, match="multi-symbol"):
            runner.run(df)

    @pytest.mark.parametrize("exit_name", ["three_stage", "momentum_decay"])
    def test_stateful_exit_generator_denied(self, exit_name):
        assert exit_name not in EXPRESSIBLE_EXIT_GENERATORS
        runner = VectorbtRunner(_FakeAdapter(exit_name), BacktestConfig.stock())
        with pytest.raises(NotImplementedError, match=exit_name):
            runner.run(_make_minute_data(days=1))

    def test_unknown_protocol_without_opt_in_denied(self):
        class _NoOptIn:
            name = "anonymous"

            def on_bar(self, bar):
                return SignalType.HOLD

        runner = VectorbtRunner(_NoOptIn(), BacktestConfig.stock())
        with pytest.raises(NotImplementedError, match="vbt_signal_expressible"):
            runner.run(_make_minute_data(days=1))

    def test_short_entry_denied_mid_run(self):
        runner = VectorbtRunner(_ShortSeller(), BacktestConfig.stock())
        with pytest.raises(NotImplementedError, match="short entry"):
            runner.run(_make_minute_data(days=1))

    def test_last_bar_entry_forced_close_collision_denied(self):
        df = _make_minute_data(days=1, bars_per_day=50)
        runner = VectorbtRunner(_LastBarBuyer(len(df) - 1), BacktestConfig.stock())
        with pytest.raises(NotImplementedError, match="collision"):
            runner.run(df)

    def test_gate_refusal_precedes_adapter_state(self):
        """정적 게이트는 어댑터를 건드리기 전에 거부한다 → 폴백 안전."""
        strategy = _MeanRevertStrategy()
        runner = VectorbtRunner(strategy, BacktestConfig.futures())
        with pytest.raises(NotImplementedError):
            runner.run(_make_minute_data(days=1))
        assert strategy.closes == []  # on_bar 미호출


# ---------------------------------------------------------------------------
# 3. Parity 게이트 (P3-b) — vectorbt 필요
# ---------------------------------------------------------------------------


def _run_both(data: pd.DataFrame, config: BacktestConfig, make_strategy):
    res_legacy = BacktestEngine(make_strategy(), config).run(data.copy())
    res_vbt = VectorbtRunner(make_strategy(), config).run(data.copy())
    return res_legacy, res_vbt


_SCENARIOS = {
    "trend_up": lambda: _make_minute_data(seed=11, drift=0.0004),
    "trend_down": lambda: _make_minute_data(seed=12, drift=-0.0004),
    "chop": _make_chop_data,
    "gap_days": lambda: _make_minute_data(seed=13, gap_pct=0.02),
    "random_walk": lambda: _make_minute_data(seed=42),
}

_RISK_VARIANTS = {
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


class TestParityGate:
    @pytest.fixture(autouse=True)
    def _require_vectorbt(self):
        pytest.importorskip("vectorbt")

    @pytest.mark.parametrize("scenario", sorted(_SCENARIOS))
    @pytest.mark.parametrize("risk_name", sorted(_RISK_VARIANTS))
    def test_scenario_risk_matrix_parity(self, scenario, risk_name):
        data = _SCENARIOS[scenario]()
        config = BacktestConfig.stock(initial_capital=10_000_000)
        config.risk = RiskConfig.from_dict(_RISK_VARIANTS[risk_name])
        res_legacy, res_vbt = _run_both(data, config, _MeanRevertStrategy)
        _assert_parity(res_legacy, res_vbt)

    def test_parity_produces_trades_somewhere(self):
        """매트릭스가 공허(0거래) parity 로만 통과하지 않는지 고정."""
        total = 0
        for scenario in _SCENARIOS.values():
            config = BacktestConfig.stock(initial_capital=10_000_000)
            res = BacktestEngine(_MeanRevertStrategy(), config).run(scenario())
            total += res.total_trades
        assert total > 0

    def test_same_bar_exit_reentry_parity(self):
        """legacy 의 동일 bar 청산→재진입을 2컬럼 라우팅이 재현하는지."""

        # 넓은 재진입 갭 + 낮은 목표수익 → 청산 bar 에서 재매수 유도.
        def make():
            return _MeanRevertStrategy(buy_gap=1.0, sell_gap=1.02, profit_target=1.001)

        data = _make_minute_data(seed=7, days=2)
        config = BacktestConfig.stock(initial_capital=10_000_000)
        res_legacy, res_vbt = _run_both(data, config, make)
        assert res_legacy.total_trades > 2
        # 실제로 동일 bar 청산→재진입이 발생했는지 확인 (전제조건).
        exits = {t.exit_time for t in res_legacy.trades}
        entries = {t.entry_time for t in res_legacy.trades}
        assert exits & entries, "scenario must produce same-bar exit→re-entry"
        _assert_parity(res_legacy, res_vbt)

    def test_fixed_order_amount_sizing_parity(self):
        data = _make_minute_data(seed=21)
        config = BacktestConfig.stock(
            initial_capital=10_000_000, order_amount_per_stock=1_000_000
        )
        res_legacy, res_vbt = _run_both(data, config, _MeanRevertStrategy)
        assert res_legacy.total_trades > 0
        _assert_parity(res_legacy, res_vbt)

    def test_position_size_multiplier_parity(self):
        """entry signal metadata 의 position_size_multiplier 반영 parity."""

        class _Sized(_MeanRevertStrategy):
            def on_bar(self, bar):
                signal = super().on_bar(bar)
                if signal == SignalType.BUY:

                    class _Sig:
                        metadata = {"position_size_multiplier": 0.35}

                    self.last_entry_signal = _Sig()
                return signal

        data = _make_minute_data(seed=31)
        config = BacktestConfig.stock(initial_capital=10_000_000)
        res_legacy, res_vbt = _run_both(data, config, _Sized)
        assert res_legacy.total_trades > 0
        _assert_parity(res_legacy, res_vbt)

    def test_zero_trade_window_parity(self):
        """무거래 구간에서도 자산곡선/지표 계약 동일."""

        class _Hold:
            name = "hold"
            vbt_signal_expressible = True

            def on_bar(self, bar):
                return SignalType.HOLD

        data = _make_minute_data(seed=5, days=2)
        config = BacktestConfig.stock()
        res_legacy = BacktestEngine(_Hold(), config).run(data.copy())
        res_vbt = VectorbtRunner(_Hold(), config).run(data.copy())
        assert res_vbt.total_trades == 0
        _assert_parity(res_legacy, res_vbt)


# ---------------------------------------------------------------------------
# 4. Experiment runner seam — opt-in + 폴백
# ---------------------------------------------------------------------------


def _synthetic_daily(symbol: str, start, end) -> pd.DataFrame:
    """test_experiment_runner 와 동일한 결정론적 일봉 빌더."""
    dates = pd.bdate_range(start=start, end=end)
    rows = []
    for i, ts in enumerate(dates):
        base = 10_000 + i * 8 + 120 * math.sin(i / 6.0)
        rows.append(
            {
                "datetime": ts.to_pydatetime(),
                "code": symbol,
                "open": base,
                "high": base * 1.012,
                "low": base * 0.988,
                "close": base * (1.004 if i % 3 else 0.996),
                "volume": 100_000 + (i % 7) * 5_000,
            }
        )
    return pd.DataFrame(rows)


def _daily_loader(*, symbol, asset_class, timeframe, start, end):
    return _synthetic_daily(symbol, start, end)


def _patch_engine_key(monkeypatch, engine: str) -> None:
    """실제 전략 YAML 을 로드하되 strategy.backtest.engine 만 주입."""
    import copy

    from shared.config.loader import ConfigLoader

    real_load = ConfigLoader.load_strategy.__func__

    def patched(cls, asset_class, strategy_name, use_cache=True):
        cfg = copy.deepcopy(real_load(cls, asset_class, strategy_name, use_cache))
        cfg.setdefault("strategy", {}).setdefault("backtest", {})["engine"] = engine
        return cfg

    monkeypatch.setattr(ConfigLoader, "load_strategy", classmethod(patched))


class TestExperimentSeam:
    def _spec(self):
        from shared.backtest.experiment_runner import ExperimentSpec

        return ExperimentSpec.from_dict(
            {
                "id": "vbt_seam",
                "strategies": [{"type": "registry", "name": "pattern_pullback"}],
                "symbols": ["005930"],
                "start": "2024-06-01",
                "end": "2026-06-01",
                "initial_capital": 10_000_000,
            }
        )

    def test_default_path_without_engine_key_is_legacy(self):
        from shared.backtest.experiment_runner import run_stock_experiment

        report = run_stock_experiment(
            self._spec(), bar_loader=_daily_loader, now=datetime(2026, 6, 1)
        )
        assert report["summaries"][0]["engine"] == "backtest_engine"

    def test_unsupported_exit_falls_back_to_legacy(self, monkeypatch):
        """engine=vectorbt 라도 비허용 exit(pattern_pullback)면 legacy 폴백.

        게이트가 vectorbt lazy import *이전에* 거부하므로 이 테스트는
        vectorbt 설치 여부와 무관하게 통과해야 한다.
        """
        from shared.backtest.experiment_runner import run_stock_experiment

        now = datetime(2026, 6, 1)
        baseline = run_stock_experiment(self._spec(), bar_loader=_daily_loader, now=now)

        _patch_engine_key(monkeypatch, "vectorbt")
        report = run_stock_experiment(self._spec(), bar_loader=_daily_loader, now=now)

        summ = report["summaries"][0]
        assert summ["engine"] == "backtest_engine"  # 폴백됨
        base_summ = baseline["summaries"][0]
        # 폴백 결과는 순수 legacy 실행과 동일 (fresh adapter 재생성 계약).
        for key in ("final_equity", "total_return_pct", "closed_trades"):
            assert summ[key] == base_summ[key], key

    def test_vectorbt_backend_used_for_expressible_strategy(self, monkeypatch):
        """허용 exit(williams_r)면 engine=vectorbt 가 실제로 라우팅된다."""
        pytest.importorskip("vectorbt")
        from shared.backtest.experiment_runner import (
            ExperimentSpec,
            run_stock_experiment,
        )

        _patch_engine_key(monkeypatch, "vectorbt")

        def minute_loader(*, symbol, asset_class, timeframe, start, end):
            assert timeframe == "minute"
            return _make_minute_data(seed=3, days=2, code=symbol)

        spec = ExperimentSpec.from_dict(
            {
                "id": "vbt_seam_wr",
                "strategies": [{"type": "registry", "name": "williams_r"}],
                "symbols": ["005930"],
                "start": "2026-06-01",
                "end": "2026-06-03",
                "initial_capital": 10_000_000,
            }
        )
        report = run_stock_experiment(
            spec, bar_loader=minute_loader, now=datetime(2026, 6, 3)
        )
        status = {s["strategy_id"]: s["status"] for s in report["status_by_strategy"]}
        assert status["williams_r"] == "ok"
        assert report["summaries"][0]["engine"] == "vectorbt"
