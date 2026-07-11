"""VbtHarnessRunner 테스트 — import 격리 / 정적 게이트 / from_orders parity (P3-d).

:class:`~shared.backtest.vbt_harness_runner.VbtHarnessRunner` 는 선물 harness의
**컴포지션 래퍼**다 — :class:`~shared.backtest.decision_harness.
BacktestDecisionHarness` 가 여전히 SoT(결과 무변형 반환)이고, 이 래퍼는 harness
자체 트레이드 레코드로 독립 ``vbt.Portfolio.from_orders`` 원장을 세워 tick 회계를
재현하는지 대조한다. 주식 :class:`~shared.backtest.vbt_runner.VectorbtRunner`
(P3-a/b/c)의 legacy-vs-vbt 이중 엔진 비교와 달리, 여기서는 **같은 계산의 두 원장**
구성을 검증한다(harness 가 유일 엔진).

3개 층위(test_vbt_runner.py 구조를 미러):

1. **Import 격리 / 정적 게이트** (vectorbt 불필요): vectorbt 미설치 환경에서도
   ``import shared.backtest.vbt_harness_runner`` 가 되고, ``run`` 이 harness 를
   구동하기 *전에* 정적으로 :class:`VbtHarnessNotSupportedError` 를 던진다
   (vectorbt 는 lazy import 계약). ``_build_order_arrays`` 인코딩과 harness 의
   fill/exit bar-index 채움도 vectorbt 없이 검증한다.
2. **parity 게이트** (vectorbt 필요 → ``pytest.importorskip``): 합성 시나리오
   매트릭스에서 harness 원장 ↔ from_orders 원장 tick 합이 일치해야 한다. 대칭
   커버리지(롱/숏 × win/loss/time_exit/eod_exit + 멀티바/같은-bar)를 non-vacuity
   가드로 고정하고, 사이저 스케일링·틱 산술·음성 tamper 검출까지 핀한다.

시나리오 프리미티브(``run_harness_and_runner`` / ``HARNESS_PARITY_SCENARIOS`` /
``TICK_SIZE_POINTS`` / ``CONTRACT_SPEC`` / 각 ``scenario_*`` 빌더)는 모듈 레벨에
있고 ``scripts/vbt_parity_report.py`` 가 그대로 import 한다 — 리포트와 게이트가
항상 같은 매트릭스를 돌게 해 드리프트를 구조적으로 차단한다.
"""

from __future__ import annotations

import copy
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from shared.backtest.decision_harness import (
    BacktestDecisionHarness,
    HarnessResult,
    TradeRecord,
)
from shared.backtest.market_context_replay import MarketContextReplay
from shared.backtest.vbt_harness_runner import (
    VbtHarnessNotSupportedError,
    VbtHarnessParityError,
    VbtHarnessRunner,
    _build_order_arrays,
)
from shared.decision.signal import Signal
from shared.risk.layer import LayerResult, RiskFilterLayer
from shared.risk.state import RiskStateSnapshot
from tests.integration.test_backtest_harness import MINI_SPEC as CONTRACT_SPEC

pytestmark = pytest.mark.backtest

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ===========================================================================
# FROZEN, VALIDATED fixture primitives (embedded verbatim).
# Run against the REAL BacktestDecisionHarness + VbtHarnessRunner: all 7
# scenarios produce parity=OK with full symmetric coverage and correct sizer
# scaling. Excursion prices / bar timings / warmup counts / scenario scripts
# are LOAD-BEARING — coverage depends on them exactly. Do NOT edit.
# scripts/vbt_parity_report.py imports the public names from this module.
# ===========================================================================

KST = ZoneInfo("Asia/Seoul")
TICK_SIZE_POINTS: float = 0.05
# CONTRACT_SPEC 는 tests/integration/test_backtest_harness.py::MINI_SPEC 를 그대로
# 재사용한다 (동일 값이던 로컬 리터럴을 제거 → 단일 소스). 세 번째 사본은 아래
# TestImportIsolation 의 subprocess 문자열에 있으며, 그 코드는 자기완결이어야
# 하므로 인라인 ContractSpec(...) 을 유지한다. MINI_SPEC.tick_size_points 는
# TICK_SIZE_POINTS(0.05)와 일치한다.
_D1, _D2, _D3 = "2025-01-02", "2025-01-03", "2025-01-04"


def _kst(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=KST)


def _bar(o, h, l, c, v=1000.0):  # noqa: E741
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _flat(p):
    # tight range keeps every bar < 2% move -> no MarketContextReplay data-quality warning
    return _bar(p, p + 0.15, p - 0.15, p)


def _ts(day: str, minute: int) -> datetime:
    return _kst(f"{day} 09:00") + timedelta(minutes=minute)


def build_harness_df(session2, session3=None, *, warmup_n=62, warmup_price=100.0):
    """Warmup session (flat, >=WARMUP_BARS=60, supplies prev_close) + engineered D2 [+ D3]."""
    rows = [
        {
            "timestamp": _kst(f"{_D1} 09:00") + timedelta(minutes=i),
            **_flat(warmup_price),
        }
        for i in range(warmup_n)
    ]
    rows += [{"timestamp": _ts(_D2, i), **b} for i, b in enumerate(session2)]
    if session3:
        rows += [{"timestamp": _ts(_D3, i), **b} for i, b in enumerate(session3)]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.reset_index(drop=True)


class _ScriptedSetup:
    """Duck-typed setup: emits the scripted Signal when ctx.now matches (deterministic).

    The harness only calls ``.check(ctx)``; a full Setup subclass is unnecessary.
    Stateless -> reusable across harness + runner.
    """

    def __init__(self, script: dict[datetime, Signal]) -> None:
        self._script = script

    def check(self, ctx):
        return self._script.get(ctx.now)


def _sig(direction, entry, stop, target, valid_until=None) -> Signal:
    return Signal(
        setup_type="scripted",
        direction=direction,
        symbol="A05603",
        entry_price=entry,
        stop_loss=stop,
        take_profit=target,
        confidence=0.9,
        valid_until=valid_until,
    )


def _make_replay(df) -> MarketContextReplay:
    return MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=CONTRACT_SPEC,
    )


class _StubSizer:
    """Deterministic sizer -> fixed contract count (exercises size_contracts>1 scaling)."""

    def __init__(self, contracts: int) -> None:
        self._contracts = contracts

    def calculate(self, *, signal, account_balance, current_positions, market_context):
        return self._contracts


# ---- Scenario builders: each returns (df, script, sizer, account_equity_krw) ----
# SYMMETRIC MIX (the headline scenario): validated to yield exactly, with parity OK,
#   dir×reason = {(long,win):1,(long,loss):1,(short,win):1,(short,loss):1,
#                 (long,time_exit):1,(long,eod_exit):2,(short,eod_exit):1}
#   => 8 trades, 7 multibar + 1 same-bar (last trade fill==exit).
def scenario_symmetric_mix():
    s2 = [_flat(100.0) for _ in range(40)]
    s2[20] = _bar(
        100.2, 101.4, 100.0, 100.6
    )  # g82 high spike (long target 101 / short stop <=101)
    s2[24] = _bar(
        99.8, 100.0, 98.6, 99.2
    )  # g86 low dip   (long stop 99 / short target 99)
    s3 = [
        _flat(100.0) for _ in range(6)
    ]  # D3 supplies the session boundary for eod exits
    df = build_harness_df(s2, s3)
    script = {
        _ts(_D2, 2): _sig("long", 100, 99.0, 101.0),  # long win  @101 g82
        _ts(_D2, 4): _sig("long", 100, 99.0, 105.0),  # long loss @99  g86
        _ts(_D2, 3): _sig("short", 100, 101.0, 95.0),  # short loss @101 g82
        _ts(_D2, 21): _sig("short", 100, 102.0, 99.0),  # short win  @99  g86
        _ts(_D2, 15): _sig(
            "long", 100, 99.5, 108.0, _ts(_D2, 18)
        ),  # time_exit at expiry
        _ts(_D2, 35): _sig("long", 100, 99.0, 108.0),  # eod long
        _ts(_D2, 36): _sig("short", 100, 108.0, 90.0),  # eod short
        _ts(_D2, 38): _sig("long", 100, 99.0, 108.0),  # same-bar eod (fill last D2 bar)
    }
    return df, script, None, 0.0


def scenario_short_only():
    df, _, _, _ = scenario_symmetric_mix()
    script = {
        _ts(_D2, 21): _sig("short", 100, 102.0, 99.0),  # short win
        _ts(_D2, 36): _sig("short", 100, 108.0, 90.0),  # short eod
    }
    return df, script, None, 0.0


def scenario_long_only():
    df, _, _, _ = scenario_symmetric_mix()
    script = {
        _ts(_D2, 2): _sig("long", 100, 99.0, 101.0),  # long win
        _ts(_D2, 4): _sig("long", 100, 99.0, 105.0),  # long loss
        _ts(_D2, 35): _sig("long", 100, 99.0, 108.0),  # long eod
    }
    return df, script, None, 0.0


def scenario_sizer_scaled():
    df, _, _, _ = scenario_symmetric_mix()
    script = {_ts(_D2, 2): _sig("long", 100, 99.0, 101.0)}
    return df, script, _StubSizer(3), 5_000_000.0


def scenario_zero_signal():
    df, _, _, _ = scenario_symmetric_mix()
    return df, {}, None, 0.0


def scenario_gap_past_stop():
    # next bar after the signal opens BELOW the long stop -> _simulate_fill returns None
    s2 = [_flat(100.0) for _ in range(10)]
    s2[6] = _bar(96.0, 96.2, 95.8, 96.0)  # fill open 96 <= stop 98 -> no fill
    df = build_harness_df(s2, [_flat(100.0)] * 3)
    return df, {_ts(_D2, 5): _sig("long", 100, 98.0, 102.0)}, None, 0.0


def scenario_no_next_bar():
    # signal at the very last bar of the df -> fill_bar >= n -> no fill
    s2 = [_flat(100.0) for _ in range(8)]
    df = build_harness_df(s2, None)  # last global idx = 62+7 = 69
    return df, {_ts(_D2, 7): _sig("long", 100, 99.0, 101.0)}, None, 0.0


# Public matrix consumed by BOTH the test module AND scripts/vbt_parity_report.py
HARNESS_PARITY_SCENARIOS: dict[str, Callable[[], tuple]] = {
    "symmetric_mix": scenario_symmetric_mix,
    "long_only": scenario_long_only,
    "short_only": scenario_short_only,
    "sizer_scaled": scenario_sizer_scaled,
    "zero_signal": scenario_zero_signal,
    "gap_past_stop": scenario_gap_past_stop,
    "no_next_bar": scenario_no_next_bar,
}


def run_harness_and_runner(df, script, *, sizer=None, account_equity_krw=0.0):
    """Run BacktestDecisionHarness (SoT) then VbtHarnessRunner (cross-check).

    Returns (harness_result, runner_result). VbtHarnessRunner.run raises
    VbtHarnessParityError on mismatch (do NOT swallow in tests).
    """
    replay = _make_replay(df)
    harness_result = BacktestDecisionHarness(
        [_ScriptedSetup(script)],
        RiskFilterLayer(filters=[]),
        RiskStateSnapshot(),
        TICK_SIZE_POINTS,
        sizer=sizer,
        account_equity_krw=account_equity_krw,
    ).run(replay)
    runner_result = VbtHarnessRunner(
        [_ScriptedSetup(script)],
        RiskFilterLayer(filters=[]),
        RiskStateSnapshot(),
        TICK_SIZE_POINTS,
        sizer=sizer,
        account_equity_krw=account_equity_krw,
    ).run(replay)
    return harness_result, runner_result


def _run_harness_only(
    df, script, *, sizer=None, account_equity_krw=0.0
) -> HarnessResult:
    """Run only the real BacktestDecisionHarness (no vectorbt needed).

    Layer-1 tests exercise the REAL ``_simulate_fill`` fill/exit bar-index
    bookkeeping without touching the runner (so they pass in the merge-gate CI
    that has no vectorbt).
    """
    return BacktestDecisionHarness(
        [_ScriptedSetup(script)],
        RiskFilterLayer(filters=[]),
        RiskStateSnapshot(),
        TICK_SIZE_POINTS,
        sizer=sizer,
        account_equity_krw=account_equity_krw,
    ).run(_make_replay(df))


# ===========================================================================
# 1. Import isolation / static gate — must work WITHOUT vectorbt
# ===========================================================================


class TestImportIsolation:
    def test_module_imports_with_vectorbt_masked(self):
        """모듈 import + ``run`` 정적 거부가 vectorbt 미설치 환경에서 동작.

        서브프로세스에서 ``sys.meta_path`` 훅으로 vectorbt import 를 차단해
        머지 게이트 CI(vectorbt 없음)를 재현한다: ``VbtHarnessRunner`` 를
        만들고 최소 유효 replay 로 ``run`` 하면 harness 를 구동하기 전에
        :class:`VbtHarnessNotSupportedError` 로 떨어져야 한다 (lazy import 계약).
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
                "import pandas as pd",
                "from datetime import datetime",
                "from shared.backtest.vbt_harness_runner import (",
                "    VbtHarnessNotSupportedError, VbtHarnessRunner)",
                "from shared.backtest.market_context_replay import (",
                "    MarketContextReplay)",
                "from shared.execution.contract_spec import ContractSpec",
                "from shared.risk.layer import RiskFilterLayer",
                "from shared.risk.state import RiskStateSnapshot",
                "spec = ContractSpec(name='t', multiplier_krw_per_point=100000,",
                "    tick_size_points=0.05, tick_value_krw=5000,",
                "    commission_rate=0.000015, symbol_prefix='A05')",
                "df = pd.DataFrame([{'timestamp': datetime(2025, 1, 2, 9, 0),",
                "    'open': 100.0, 'high': 100.1, 'low': 99.9, 'close': 100.0,",
                "    'volume': 1000}])",
                "df['timestamp'] = pd.to_datetime(df['timestamp'])",
                "replay = MarketContextReplay(df=df, symbol='A05603',",
                "    macro_snapshot=None, scheduled_events=[], contract_spec=spec)",
                "runner = VbtHarnessRunner([], RiskFilterLayer(filters=[]),",
                "    RiskStateSnapshot(), 0.05)",
                "try:",
                "    runner.run(replay)",
                "except VbtHarnessNotSupportedError:",
                "    pass",
                "else:",
                "    raise SystemExit('expected VbtHarnessNotSupportedError')",
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


class _RaisingSetup:
    """``.check`` 이 호출되면 카운트 증가 후 AssertionError — harness 구동 감지용."""

    def __init__(self) -> None:
        self.check_calls = 0

    def check(self, ctx):
        self.check_calls += 1
        raise AssertionError("harness must not run when vectorbt is masked")


class TestStaticGate:
    def test_static_gate_precedes_harness(self, monkeypatch):
        """정적 게이트가 harness 실행보다 *앞선다* (in-process 마스킹).

        vectorbt 를 meta_path 훅으로 차단하고 이미 로드된 vectorbt 모듈을
        제거한 뒤, harness 가 실제로 ``.check`` 를 부를 만큼 풍부한 replay
        (symmetric_mix df)로 ``run`` 한다. :class:`VbtHarnessNotSupportedError`
        가 나야 하고, 셋업의 ``.check`` 호출 카운트는 0 이어야 한다 — 게이트가
        harness 를 구동하지 않았다는 증거.
        """
        import importlib.abc

        class _Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name == "vectorbt" or name.startswith("vectorbt."):
                    raise ImportError("vectorbt masked for test")
                return None

        for mod in [m for m in sys.modules if m.split(".")[0] == "vectorbt"]:
            monkeypatch.delitem(sys.modules, mod)
        monkeypatch.setattr(sys, "meta_path", [_Block(), *sys.meta_path])

        setup = _RaisingSetup()
        df, _, _, _ = scenario_symmetric_mix()
        runner = VbtHarnessRunner(
            [setup], RiskFilterLayer(filters=[]), RiskStateSnapshot(), TICK_SIZE_POINTS
        )
        with pytest.raises(VbtHarnessNotSupportedError, match="not installed"):
            runner.run(_make_replay(df))
        assert setup.check_calls == 0


# ---------------------------------------------------------------------------
# _build_order_arrays — pure-numpy order encoding (vectorbt 불필요)
# ---------------------------------------------------------------------------

_DUMMY_LAYER = LayerResult(
    passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
)


def _mk_trade(
    direction: str,
    fill_price: float,
    exit_price: float,
    *,
    fill_bar: int,
    exit_bar: int,
    size: int = 1,
    ticks_net: float = 0.0,
    exit_reason: str = "win",
) -> TradeRecord:
    """Hand-built TradeRecord with fill/exit bar indices for _build_order_arrays tests."""
    return TradeRecord(
        setup_type="scripted",
        direction=direction,
        symbol="A05603",
        bar_index=fill_bar - 1,
        signal_entry=fill_price,
        fill_price=fill_price,
        stop=0.0,
        target=0.0,
        exit_price=exit_price,
        exit_reason=exit_reason,
        ticks_net=ticks_net,
        layer_result=_DUMMY_LAYER,
        size_contracts=size,
        ticks_net_total=ticks_net * size,
        fill_bar_index=fill_bar,
        exit_bar_index=exit_bar,
    )


def _nonnan_cells(arr: np.ndarray) -> set[tuple[int, int]]:
    """Return {(row, col)} of the non-NaN cells in a 2-D array."""
    rows, cols = np.where(~np.isnan(arr))
    return set(zip(rows.tolist(), cols.tolist()))


class TestBuildOrderArrays:
    def test_single_long(self):
        t = _mk_trade("long", 100.0, 101.0, fill_bar=1, exit_bar=3)
        arrays = _build_order_arrays([t], 5)
        assert arrays.n_cols == 1
        assert arrays.multibar == [t]
        assert arrays.samebar == []
        # entry: +size @ fill; exit: -size @ exit; everything else NaN.
        assert arrays.size[1, 0] == pytest.approx(1.0)
        assert arrays.price[1, 0] == pytest.approx(100.0)
        assert arrays.size[3, 0] == pytest.approx(-1.0)
        assert arrays.price[3, 0] == pytest.approx(101.0)
        assert _nonnan_cells(arrays.size) == {(1, 0), (3, 0)}
        assert _nonnan_cells(arrays.price) == {(1, 0), (3, 0)}

    def test_single_short(self):
        t = _mk_trade("short", 100.0, 98.0, fill_bar=1, exit_bar=4)
        arrays = _build_order_arrays([t], 6)
        assert arrays.n_cols == 1
        # short: entry -size, exit +size.
        assert arrays.size[1, 0] == pytest.approx(-1.0)
        assert arrays.size[4, 0] == pytest.approx(1.0)
        assert _nonnan_cells(arrays.size) == {(1, 0), (4, 0)}

    def test_sized_long(self):
        t = _mk_trade("long", 100.0, 102.0, fill_bar=2, exit_bar=5, size=3)
        arrays = _build_order_arrays([t], 8)
        assert arrays.size[2, 0] == pytest.approx(3.0)
        assert arrays.size[5, 0] == pytest.approx(-3.0)
        assert _nonnan_cells(arrays.size) == {(2, 0), (5, 0)}

    def test_two_multibar_independent_columns(self):
        t1 = _mk_trade("long", 100.0, 101.0, fill_bar=1, exit_bar=3)
        t2 = _mk_trade("short", 100.0, 99.0, fill_bar=2, exit_bar=4, size=2)
        arrays = _build_order_arrays([t1, t2], 6)
        assert arrays.n_cols == 2
        assert arrays.multibar == [t1, t2]
        # each trade only touches its own column.
        assert arrays.size[1, 0] == pytest.approx(1.0)
        assert arrays.size[3, 0] == pytest.approx(-1.0)
        assert arrays.size[2, 1] == pytest.approx(-2.0)
        assert arrays.size[4, 1] == pytest.approx(2.0)
        assert _nonnan_cells(arrays.size) == {(1, 0), (3, 0), (2, 1), (4, 1)}

    def test_same_bar_excluded_from_columns(self):
        mb = _mk_trade("long", 100.0, 101.0, fill_bar=1, exit_bar=3)
        sb = _mk_trade(
            "long", 100.0, 100.0, fill_bar=2, exit_bar=2, exit_reason="eod_exit"
        )
        arrays = _build_order_arrays([mb, sb], 5)
        # same-bar trade lands in samebar, excluded from the from_orders columns.
        assert arrays.n_cols == 1
        assert arrays.multibar == [mb]
        assert arrays.samebar == [sb]
        # only the multibar trade's two orders are encoded (column 0).
        assert _nonnan_cells(arrays.size) == {(1, 0), (3, 0)}


# ---------------------------------------------------------------------------
# TradeRecord fill/exit bar-index population — REAL _simulate_fill (no vbt)
# ---------------------------------------------------------------------------


class TestTradeRecordIndexPopulation:
    def test_fill_and_exit_indices_populated(self):
        df, script, _, _ = scenario_symmetric_mix()
        result = _run_harness_only(df, script)
        closes = df["close"].to_numpy(dtype=float)

        # All four exit reasons are present in the headline scenario.
        reasons = {t.exit_reason for t in result.trades}
        for r in ("win", "loss", "time_exit", "eod_exit"):
            assert r in reasons, (r, reasons)

        for t in result.trades:
            assert isinstance(t.fill_bar_index, int)
            assert isinstance(t.exit_bar_index, int)
            # fill = the bar AFTER the signal bar.
            assert t.fill_bar_index == t.bar_index + 1
            assert t.exit_bar_index >= t.fill_bar_index

        # same-bar (eod) carve-out: exit marked at the fill bar's close.
        samebar = [t for t in result.trades if t.exit_bar_index == t.fill_bar_index]
        assert len(samebar) == 1
        st = samebar[0]
        assert st.exit_reason == "eod_exit"
        assert st.exit_price == pytest.approx(closes[st.fill_bar_index])

    def test_samebar_classification(self):
        df, script, _, _ = scenario_symmetric_mix()
        result = _run_harness_only(df, script)
        samebar = [t for t in result.trades if t.exit_bar_index == t.fill_bar_index]
        multibar = [t for t in result.trades if t.exit_bar_index > t.fill_bar_index]
        assert len(samebar) == 1
        assert len(multibar) == len(result.trades) - 1
        for t in multibar:
            assert t.exit_bar_index > t.fill_bar_index


# ===========================================================================
# 2. Parity gate — vectorbt 필요 (from_orders 원장 대조)
# ===========================================================================


class TestParity:
    @pytest.fixture(autouse=True)
    def _require_vectorbt(self):
        pytest.importorskip("vectorbt")

    @pytest.mark.parametrize("scenario", sorted(HARNESS_PARITY_SCENARIOS))
    def test_scenario_parity(self, scenario):
        """각 시나리오에서 harness 원장 ↔ from_orders 원장 tick 회계 일치.

        ``run_harness_and_runner`` 의 ``VbtHarnessRunner.run`` 이 불일치 시
        :class:`VbtHarnessParityError` 를 던지므로(잡지 않음), 이 호출이 예외
        없이 반환하면 parity 가 성립한 것이다.
        """
        df, script, sizer, eq = HARNESS_PARITY_SCENARIOS[scenario]()
        harness_result, runner_result = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        assert len(runner_result.trades) == len(harness_result.trades)
        assert sum(t.ticks_net_total for t in runner_result.trades) == pytest.approx(
            sum(t.ticks_net_total for t in harness_result.trades)
        )

    def test_symmetric_matrix_nonvacuity(self):
        """헤드라인 시나리오가 대칭 커버리지를 실제로 산출하는지 고정."""
        df, script, sizer, eq = scenario_symmetric_mix()
        harness_result, _ = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        combos = Counter((t.direction, t.exit_reason) for t in harness_result.trades)
        expected = {
            ("long", "win"),
            ("long", "loss"),
            ("short", "win"),
            ("short", "loss"),
            ("long", "time_exit"),
            ("long", "eod_exit"),
            ("short", "eod_exit"),
        }
        assert expected <= set(combos), combos
        multibar = [
            t for t in harness_result.trades if t.exit_bar_index > t.fill_bar_index
        ]
        samebar = [
            t for t in harness_result.trades if t.exit_bar_index == t.fill_bar_index
        ]
        assert len(multibar) >= 2
        assert len(samebar) == 1

    def test_nonvacuity_coverage_across_matrix(self):
        """전 시나리오 집계로 각 축(win/loss/time_exit/eod_exit/숏/멀티바/같은-bar)이
        최소 1회 발생함을 확인 — parity 가 공허(0거래)로 통과하지 않는 증거."""
        reasons: Counter = Counter()
        directions: Counter = Counter()
        total_samebar = 0
        max_multibar = 0
        for factory in HARNESS_PARITY_SCENARIOS.values():
            df, script, sizer, eq = factory()
            harness_result, _ = run_harness_and_runner(
                df, script, sizer=sizer, account_equity_krw=eq
            )
            for t in harness_result.trades:
                reasons[t.exit_reason] += 1
                directions[t.direction] += 1
            mb = sum(
                1 for t in harness_result.trades if t.exit_bar_index > t.fill_bar_index
            )
            sb = sum(
                1 for t in harness_result.trades if t.exit_bar_index == t.fill_bar_index
            )
            total_samebar += sb
            max_multibar = max(max_multibar, mb)
        for r in ("win", "loss", "time_exit", "eod_exit"):
            assert reasons[r] >= 1, (r, reasons)
        assert directions["short"] >= 1, directions
        assert max_multibar >= 2  # overlapping (multibar) trades occur somewhere
        assert total_samebar >= 1

    def test_sizer_scales_ledger(self):
        """사이저 주입 시 원장이 계약 수만큼 스케일되고 from_orders 셀도 반영."""
        df, script, sizer, eq = scenario_sizer_scaled()
        _, runner_result = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        assert len(runner_result.trades) == 1
        t = runner_result.trades[0]
        assert t.size_contracts == 3
        assert t.ticks_net_total == pytest.approx(t.ticks_net * 3)
        arrays = _build_order_arrays(runner_result.trades, len(df))
        fill_idx = int(t.fill_bar_index)
        assert arrays.size[fill_idx, 0] == pytest.approx(3.0)

    def test_zero_trade_window_no_crash(self):
        df, script, sizer, eq = scenario_zero_signal()
        _, runner_result = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        assert isinstance(runner_result, HarnessResult)
        assert len(runner_result.trades) == 0

    def test_gap_past_stop_no_fill(self):
        df, script, sizer, eq = scenario_gap_past_stop()
        _, runner_result = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        assert isinstance(runner_result, HarnessResult)
        assert len(runner_result.trades) == 0

    def test_no_next_bar_no_fill(self):
        df, script, sizer, eq = scenario_no_next_bar()
        _, runner_result = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        assert isinstance(runner_result, HarnessResult)
        assert len(runner_result.trades) == 0

    def test_spot_check_known_trade_ticks(self):
        """롱 win 트레이드의 ticks_net 이 (exit-fill)/tick_size 와 일치."""
        df, script, _, _ = scenario_symmetric_mix()
        _, runner_result = run_harness_and_runner(df, script)
        long_wins = [
            t
            for t in runner_result.trades
            if t.direction == "long" and t.exit_reason == "win"
        ]
        assert len(long_wins) == 1
        t = long_wins[0]
        assert t.ticks_net == pytest.approx(
            (t.exit_price - t.fill_price) / TICK_SIZE_POINTS
        )

    def test_negative_tamper_raises(self):
        """멀티바 트레이드의 ticks_net 을 조작하면 cross-check 가 검출해야 한다.

        harness 결과를 정상 실행한 뒤 deepcopy 로 복제해 멀티바 트레이드의
        ``ticks_net`` 에 +5 틱을 주입하면, from_orders 원장(가격 배열 불변)의
        pnl 과 어긋나 :class:`VbtHarnessParityError` 가 나야 한다.
        """
        df, script, sizer, eq = scenario_symmetric_mix()
        harness_result, _ = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        tampered = copy.deepcopy(harness_result)
        mb = next(t for t in tampered.trades if t.exit_bar_index > t.fill_bar_index)
        mb.ticks_net += 5.0
        mb.ticks_net_total = mb.ticks_net * mb.size_contracts  # F2 불변식은 유지
        runner = VbtHarnessRunner(
            [_ScriptedSetup(script)],
            RiskFilterLayer(filters=[]),
            RiskStateSnapshot(),
            TICK_SIZE_POINTS,
            sizer=sizer,
            account_equity_krw=eq,
        )
        with pytest.raises(VbtHarnessParityError):
            runner._cross_check(tampered, df)

    def test_negative_tamper_samebar_ticks_raises(self):
        """같은-bar 트레이드의 ticks_net 조작을 해석적 재계산이 검출해야 한다.

        헤드라인 tick 합 불변식은 같은-bar 트레이드에 대해 대수적으로 공허하므로
        (그 항이 samebar_pnl 과 all_pnl 에 동일하게 들어가 상쇄), 종가 마킹은
        건드리지 않고 ``ticks_net`` 만 어긋내면 **오직** 같은-bar 해석적 tick
        재계산(``ticks_net == (exit-fill)/tick``)만이 이를 검출한다. F2
        불변식(``ticks_net_total``)은 함께 맞춰 두어 이 경로만 격리한다.
        """
        df, script, sizer, eq = scenario_symmetric_mix()
        harness_result, _ = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        tampered = copy.deepcopy(harness_result)
        sb = next(t for t in tampered.trades if t.exit_bar_index == t.fill_bar_index)
        sb.ticks_net += 5.0
        sb.ticks_net_total = sb.ticks_net * sb.size_contracts  # F2 불변식은 유지
        runner = VbtHarnessRunner(
            [_ScriptedSetup(script)],
            RiskFilterLayer(filters=[]),
            RiskStateSnapshot(),
            TICK_SIZE_POINTS,
            sizer=sizer,
            account_equity_krw=eq,
        )
        with pytest.raises(VbtHarnessParityError):
            runner._cross_check(tampered, df)

    def test_negative_tamper_ticks_net_total_raises(self):
        """소비자 합산 필드(``ticks_net_total``) 조작을 cross-check 가 검출.

        ``ticks_net`` / 가격은 그대로 두고 ``ticks_net_total`` 만 어긋내면
        from_orders 원장·같은-bar 재계산은 통과하지만, 전 트레이드 대상
        ``ticks_net_total == ticks_net × size_contracts`` 불변식이 걸린다.
        """
        df, script, sizer, eq = scenario_symmetric_mix()
        harness_result, _ = run_harness_and_runner(
            df, script, sizer=sizer, account_equity_krw=eq
        )
        tampered = copy.deepcopy(harness_result)
        tampered.trades[0].ticks_net_total += 3.0
        runner = VbtHarnessRunner(
            [_ScriptedSetup(script)],
            RiskFilterLayer(filters=[]),
            RiskStateSnapshot(),
            TICK_SIZE_POINTS,
            sizer=sizer,
            account_equity_krw=eq,
        )
        with pytest.raises(VbtHarnessParityError):
            runner._cross_check(tampered, df)
