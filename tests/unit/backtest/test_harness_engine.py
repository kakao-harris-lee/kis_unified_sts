"""run_futures_backtest 엔진 선택기 테스트 — P3-d 후속 (walk-forward --engine 배선).

:func:`shared.backtest.harness_engine.run_futures_backtest` 는 walk-forward /
optimizer 스크립트들의 단일 chokepoint 다. 검증 계약:

1. ``engine="harness"`` (기본): :class:`BacktestDecisionHarness` 그대로 —
   라벨 ``"harness"``.
2. ``engine="vectorbt"``: :class:`VbtHarnessRunner`. vectorbt 미설치
   (:class:`VbtHarnessNotSupportedError`)는 **폴백 없이 전파** (명시 opt-in
   수동 스크립트 — 조용한 폴백 금지).
3. :class:`VbtHarnessParityError` 는 warning 로그 후 ``exc.harness_result``
   (1차 harness 결과)로 SoT 복원 — **재실행 없음** (stateful setup 은 재실행
   시 트레이드 소실). 라벨 ``"vectorbt_parity_failed"``. ``harness_result``
   가 없으면 :class:`RuntimeError` (조용한 재실행 금지).
4. 미지 engine 값은 :class:`ValueError`.

라우팅 로직은 모듈 어트리뷰트 monkeypatch(가짜 엔진)로, 실경로는
``test_vbt_harness_runner`` 의 검증된 시나리오 픽스처로 커버한다(vectorbt
필요 층은 ``importorskip``). argparse 스모크는 5개 스크립트의 ``--help`` 에
``--engine`` 노출을 확인한다.
"""

from __future__ import annotations

import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

import pytest

import shared.backtest.harness_engine as harness_engine
from shared.backtest.harness_engine import (
    ENGINE_HARNESS,
    ENGINE_VECTORBT,
    ENGINE_VECTORBT_PARITY_FAILED,
    SUPPORTED_ENGINES,
    run_futures_backtest,
)
from shared.backtest.market_context_replay import MarketContextReplay
from shared.backtest.vbt_harness_runner import (
    VbtHarnessNotSupportedError,
    VbtHarnessParityError,
)
from shared.risk.layer import RiskFilterLayer
from shared.risk.state import RiskStateSnapshot
from tests.unit.backtest.test_vbt_harness_runner import (
    CONTRACT_SPEC,
    TICK_SIZE_POINTS,
    _ScriptedSetup,
    scenario_symmetric_mix,
)

pytestmark = pytest.mark.backtest

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Routing tests — fake engines via module-attribute monkeypatch (no vectorbt,
# no real harness run).
# ---------------------------------------------------------------------------

_SENTINEL_HARNESS_RESULT = object()
_SENTINEL_VBT_RESULT = object()
# 러너 1차 실행에서 확정돼 VbtHarnessParityError.harness_result 로 전파되는
# SoT 결과 (실제 러너가 raise 전에 실어 주는 것을 흉내낸다).
_SENTINEL_FIRST_RUN_RESULT = object()
_SENTINEL_REPLAY = object()


class _FakeHarness:
    """Records ctor/run calls; returns the harness sentinel."""

    instances: list[_FakeHarness] = []

    def __init__(
        self, setups, filter_layer, state, tick, *, sizer=None, account_equity_krw=0.0
    ):
        self.ctor_args = (setups, filter_layer, state, tick, sizer, account_equity_krw)
        self.run_calls: list[object] = []
        _FakeHarness.instances.append(self)

    def run(self, replay):
        self.run_calls.append(replay)
        return _SENTINEL_HARNESS_RESULT


def _make_fake_runner(behavior: str):
    """behavior: 'ok' | 'parity_error' | 'parity_error_bare' | 'not_supported'."""

    class _FakeRunner:
        instances: list = []

        def __init__(
            self,
            setups,
            filter_layer,
            state,
            tick,
            *,
            sizer=None,
            account_equity_krw=0.0,
        ):
            self.ctor_args = (
                setups,
                filter_layer,
                state,
                tick,
                sizer,
                account_equity_krw,
            )
            _FakeRunner.instances.append(self)

        def run(self, replay):
            if behavior == "parity_error":
                # 실제 러너처럼 1차 harness(SoT) 결과를 예외에 실어 전파.
                err = VbtHarnessParityError("injected parity mismatch")
                err.harness_result = _SENTINEL_FIRST_RUN_RESULT
                raise err
            if behavior == "parity_error_bare":
                # harness_result 미탑재 — 폴백 불가, RuntimeError 여야 한다.
                raise VbtHarnessParityError("injected parity mismatch (bare)")
            if behavior == "not_supported":
                raise VbtHarnessNotSupportedError(
                    "vectorbt not installed — pip install -e '.[backtest]'"
                )
            return _SENTINEL_VBT_RESULT

    return _FakeRunner


@pytest.fixture(autouse=True)
def _reset_fake_instances():
    _FakeHarness.instances = []
    yield
    _FakeHarness.instances = []


def _call(engine: str, **kwargs):
    return run_futures_backtest(
        [],
        RiskFilterLayer(filters=[]),
        RiskStateSnapshot(),
        TICK_SIZE_POINTS,
        _SENTINEL_REPLAY,
        engine=engine,
        **kwargs,
    )


class TestRouting:
    def test_default_engine_is_harness(self, monkeypatch):
        """(a) 기본 harness 경로: harness 1회 구동, 라벨 'harness', vbt 미접촉."""
        fake_runner = _make_fake_runner("ok")
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        monkeypatch.setattr(harness_engine, "VbtHarnessRunner", fake_runner)

        result, label = run_futures_backtest(
            [],
            RiskFilterLayer(filters=[]),
            RiskStateSnapshot(),
            TICK_SIZE_POINTS,
            _SENTINEL_REPLAY,
        )
        assert result is _SENTINEL_HARNESS_RESULT
        assert label == ENGINE_HARNESS
        assert len(_FakeHarness.instances) == 1
        assert _FakeHarness.instances[0].run_calls == [_SENTINEL_REPLAY]
        assert fake_runner.instances == []

    def test_harness_forwards_sizer_and_equity(self, monkeypatch):
        """sizer / account_equity_krw 가 엔진 생성자로 전달된다."""
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        sizer = object()
        _call(ENGINE_HARNESS, sizer=sizer, account_equity_krw=5_000_000.0)
        assert _FakeHarness.instances[0].ctor_args[4] is sizer
        assert _FakeHarness.instances[0].ctor_args[5] == 5_000_000.0

    def test_vectorbt_engine_returns_vbt_label(self, monkeypatch):
        """engine='vectorbt' 성공 경로: 러너 결과 + 라벨 'vectorbt'."""
        fake_runner = _make_fake_runner("ok")
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        monkeypatch.setattr(harness_engine, "VbtHarnessRunner", fake_runner)

        result, label = _call(ENGINE_VECTORBT)
        assert result is _SENTINEL_VBT_RESULT
        assert label == ENGINE_VECTORBT
        assert _FakeHarness.instances == []  # harness 직접 구동 없음

    def test_not_supported_propagates_no_fallback(self, monkeypatch):
        """(b) vectorbt 미설치는 전파 — harness 로 조용히 폴백하지 않는다."""
        fake_runner = _make_fake_runner("not_supported")
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        monkeypatch.setattr(harness_engine, "VbtHarnessRunner", fake_runner)

        with pytest.raises(VbtHarnessNotSupportedError, match=r"\[backtest\]"):
            _call(ENGINE_VECTORBT)
        assert _FakeHarness.instances == []  # 폴백 실행이 없었다는 증거

    def test_parity_error_restores_first_run_result_without_rerun(
        self, monkeypatch, caplog
    ):
        """(c) ParityError → warning 로그 + exc.harness_result 복원 + 전용 라벨.

        harness 는 **재실행되지 않는다** — stateful setup(Setup C 의
        EventTradeTracker)은 재실행 시 트레이드가 소실되므로, 1차 실행 결과가
        예외에 실려 그대로 복원돼야 한다.
        """
        fake_runner = _make_fake_runner("parity_error")
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        monkeypatch.setattr(harness_engine, "VbtHarnessRunner", fake_runner)

        with caplog.at_level(logging.WARNING, logger="shared.backtest.harness_engine"):
            result, label = _call(ENGINE_VECTORBT)
        assert result is _SENTINEL_FIRST_RUN_RESULT
        assert label == ENGINE_VECTORBT_PARITY_FAILED
        assert _FakeHarness.instances == []  # 재실행 없음이 계약
        assert any(
            "parity" in rec.message and "injected parity mismatch" in rec.getMessage()
            for rec in caplog.records
        )

    def test_parity_error_without_result_raises_instead_of_rerun(self, monkeypatch):
        """(c') harness_result 없는 ParityError → RuntimeError (조용한 재실행 금지)."""
        fake_runner = _make_fake_runner("parity_error_bare")
        monkeypatch.setattr(harness_engine, "BacktestDecisionHarness", _FakeHarness)
        monkeypatch.setattr(harness_engine, "VbtHarnessRunner", fake_runner)

        with pytest.raises(RuntimeError, match="harness_result"):
            _call(ENGINE_VECTORBT)
        assert _FakeHarness.instances == []  # 재실행 폴백이 없었다는 증거

    @pytest.mark.parametrize(
        "bad", ["bogus", "", "HARNESS", "vbt", ENGINE_VECTORBT_PARITY_FAILED]
    )
    def test_unknown_engine_raises_value_error(self, bad):
        """(d) 미지 engine 값 → ValueError (결과 라벨은 입력으로 거부)."""
        with pytest.raises(ValueError, match="unknown engine"):
            _call(bad)

    def test_supported_engines_frozen(self):
        assert SUPPORTED_ENGINES == (ENGINE_HARNESS, ENGINE_VECTORBT)


# ---------------------------------------------------------------------------
# Real-path tests — validated scenario fixtures from test_vbt_harness_runner.
# ---------------------------------------------------------------------------


def _real_call(engine: str, *, setup_cls=_ScriptedSetup):
    df, script, sizer, eq = scenario_symmetric_mix()
    replay = MarketContextReplay(
        df=df,
        symbol="A05603",
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=CONTRACT_SPEC,
    )
    return run_futures_backtest(
        [setup_cls(script)],
        RiskFilterLayer(filters=[]),
        RiskStateSnapshot(),
        TICK_SIZE_POINTS,
        replay,
        engine=engine,
        sizer=sizer,
        account_equity_krw=eq,
    )


class TestRealEngines:
    def test_real_harness_path(self):
        """실 BacktestDecisionHarness 경로 (vectorbt 불필요) — 8 트레이드."""
        result, label = _real_call(ENGINE_HARNESS)
        assert label == ENGINE_HARNESS
        assert len(result.trades) == 8  # scenario_symmetric_mix 검증값

    def test_real_vectorbt_path(self):
        """실 VbtHarnessRunner 경로 — parity 통과 시 라벨 'vectorbt', 결과 동일."""
        pytest.importorskip("vectorbt")
        harness_result, _ = _real_call(ENGINE_HARNESS)
        vbt_result, label = _real_call(ENGINE_VECTORBT)
        assert label == ENGINE_VECTORBT
        assert len(vbt_result.trades) == len(harness_result.trades) == 8
        assert [t.ticks_net for t in vbt_result.trades] == [
            t.ticks_net for t in harness_result.trades
        ]


class _OneShotSetup(_ScriptedSetup):
    """상태 소비 setup — 시그널을 1회만 발화(check 가 script 를 pop).

    Setup C 의 ``EventTradeTracker``(1차 실행에서 이벤트를 mark, reset 없음)를
    최소로 재현한다: harness 를 **재실행**하면 script 가 이미 소비돼 트레이드
    0건이 된다 — parity 폴백이 재실행이면 이 테스트가 잡아낸다.
    """

    def check(self, ctx):
        return self._script.pop(ctx.now, None)


class TestParityFallbackStatefulRegression:
    def test_fallback_preserves_first_run_result_for_stateful_setup(
        self, monkeypatch, caplog
    ):
        """(F1 회귀) 상태 소비 setup + 강제 parity 실패 → 1차 결과 그대로 복원.

        ``VbtHarnessRunner._cross_check`` 를 실패로 강제해 실제 run() 경로가
        1차 harness 결과를 예외에 실어 전파하고, 엔진 선택기가 재실행 없이
        그 결과를 복원함을 종단으로 검증한다 (재실행이면 0 트레이드).
        """
        pytest.importorskip("vectorbt")
        from shared.backtest.vbt_harness_runner import VbtHarnessRunner

        def _forced_mismatch(self, result, df):
            raise VbtHarnessParityError("forced parity mismatch (test)")

        monkeypatch.setattr(VbtHarnessRunner, "_cross_check", _forced_mismatch)

        # 기준선: 동일 시나리오의 1차(유일) harness 실행 결과.
        baseline, _ = _real_call(ENGINE_HARNESS, setup_cls=_OneShotSetup)
        assert len(baseline.trades) == 8  # scenario_symmetric_mix 검증값

        with caplog.at_level(logging.WARNING, logger="shared.backtest.harness_engine"):
            result, label = _real_call(ENGINE_VECTORBT, setup_cls=_OneShotSetup)
        assert label == ENGINE_VECTORBT_PARITY_FAILED
        # 재실행이었다면 _OneShotSetup 의 script 소비로 트레이드가 소실된다.
        assert len(result.trades) == len(baseline.trades) == 8
        assert [t.ticks_net for t in result.trades] == [
            t.ticks_net for t in baseline.trades
        ]


# ---------------------------------------------------------------------------
# argparse smoke — all 5 scripts expose --engine in --help.
# ---------------------------------------------------------------------------

_SCRIPTS = [
    "scripts/walk_forward_phase3.py",
    "scripts/walk_forward_bootstrap.py",
    "scripts/walk_forward_sensitivity.py",
    "scripts/walk_forward_paper_foldin.py",
    "scripts/optimize_decision_engine.py",
]


class TestArgparseSmoke:
    @pytest.mark.parametrize("script", _SCRIPTS)
    def test_help_exposes_engine_flag(self, script):
        if (
            script == "scripts/optimize_decision_engine.py"
            and importlib.util.find_spec("optuna") is None
        ):
            # optimize_decision_engine.py 는 optuna 미설치 시 argparse 전에
            # SystemExit — optuna 없는 CI(gating test job)에서는 스킵.
            pytest.skip("optuna not installed — script exits before argparse")
        proc = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            timeout=180,
        )
        assert proc.returncode == 0, proc.stderr
        assert "--engine" in proc.stdout
        assert "vectorbt" in proc.stdout
