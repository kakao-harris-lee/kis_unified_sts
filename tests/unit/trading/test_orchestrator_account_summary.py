"""TradingOrchestrator.get_status — `account` 블록 회귀 테스트.

운영자가 paper engine의 현금/equity/실현손익을 `sts paper status`나 dashboard로
확인하려면 orchestrator가 broker 상태를 status 응답에 노출해야 한다.  KIS 선물
모의서버는 잔고조회(CTFO6118R) 미지원이라 paper engine이 유일한 진실의 원천이다.

테스트 시나리오:
  1. broker 미연결(live 또는 startup 직전) → ``account`` 키 생략
  2. ``get_summary()`` 지원 broker → 모든 필드 노출 (balance / equity / realized_pnl / open_positions + unrealized_pnl 파생)
  3. ``get_summary()`` 미지원 broker → ``balance`` / ``get_equity()`` / ``initial_balance``로 fallback
  4. broker 예외 발생 → ``account`` 키 생략 (status 응답 자체는 정상)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator


@pytest.fixture
def orchestrator() -> TradingOrchestrator:
    cfg = TradingConfig(
        asset_class="futures",
        strategy_name="setup_a_gap_reversion",
        initial_capital=100_000_000.0,
        order_amount_per_trade=1_000_000.0,
        paper_trading=True,
    )
    return TradingOrchestrator(cfg)


class TestAccountSummaryAbsent:
    def test_no_account_block_when_broker_missing(self, orchestrator):
        # _paper_broker는 init 시 None (start() 호출 전)
        assert orchestrator._paper_broker is None
        status = orchestrator.get_status()
        assert "account" not in status

    def test_no_account_block_when_broker_raises(self, orchestrator):
        broker = MagicMock()
        broker.get_summary = MagicMock(side_effect=RuntimeError("boom"))
        # fallback 경로도 막는다 — balance 접근 시 예외
        type(broker).balance = property(
            lambda _self: (_ for _ in ()).throw(RuntimeError("balance fail"))
        )
        orchestrator._paper_broker = broker
        status = orchestrator.get_status()
        assert "account" not in status


class TestAccountSummaryFromGetSummary:
    def test_full_summary_passthrough(self, orchestrator):
        broker = MagicMock()
        broker.get_summary = MagicMock(
            return_value={
                "initial_balance": 100_000_000.0,
                "balance": 95_000_000.0,
                "equity": 97_500_000.0,
                "total_pnl": -3_000_000.0,  # closed trade pnl 누적
                "open_positions": 2,
            }
        )
        orchestrator._paper_broker = broker
        status = orchestrator.get_status()

        assert "account" in status
        account = status["account"]
        assert account["initial_balance"] == pytest.approx(100_000_000.0)
        assert account["balance"] == pytest.approx(95_000_000.0)
        assert account["equity"] == pytest.approx(97_500_000.0)
        assert account["realized_pnl"] == pytest.approx(-3_000_000.0)
        assert account["open_positions"] == 2
        # 미실현 = equity - balance (오픈 포지션 평가손익)
        assert account["unrealized_pnl"] == pytest.approx(2_500_000.0)

    def test_unrealized_pnl_zero_when_flat(self, orchestrator):
        broker = MagicMock()
        broker.get_summary = MagicMock(
            return_value={
                "initial_balance": 100_000_000.0,
                "balance": 101_000_000.0,
                "equity": 101_000_000.0,
                "total_pnl": 1_000_000.0,
                "open_positions": 0,
            }
        )
        orchestrator._paper_broker = broker
        status = orchestrator.get_status()
        assert status["account"]["unrealized_pnl"] == pytest.approx(0.0)


class TestAccountSummaryFallback:
    def test_fallback_uses_balance_and_get_equity(self, orchestrator):
        # get_summary 미지원, 개별 속성/메서드만 노출
        broker = MagicMock(
            spec=["balance", "initial_balance", "get_equity", "positions"]
        )
        broker.balance = 95_000_000.0
        broker.initial_balance = 100_000_000.0
        broker.get_equity = MagicMock(return_value=97_500_000.0)
        broker.positions = {"101S6000": object(), "101S6001": object()}

        orchestrator._paper_broker = broker
        status = orchestrator.get_status()

        account = status["account"]
        assert account["initial_balance"] == pytest.approx(100_000_000.0)
        assert account["balance"] == pytest.approx(95_000_000.0)
        assert account["equity"] == pytest.approx(97_500_000.0)
        # realized_pnl ≈ balance - initial (체결로 변동한 현금)
        assert account["realized_pnl"] == pytest.approx(-5_000_000.0)
        assert account["unrealized_pnl"] == pytest.approx(2_500_000.0)
        assert account["open_positions"] == 2

    def test_fallback_uses_config_capital_when_initial_balance_missing(
        self, orchestrator
    ):
        broker = MagicMock(spec=["balance", "get_equity"])
        broker.balance = 99_000_000.0
        broker.get_equity = MagicMock(return_value=99_000_000.0)

        orchestrator._paper_broker = broker
        status = orchestrator.get_status()

        account = status["account"]
        # initial 미지원 시 config.initial_capital(=100M)로 폴백
        assert account["initial_balance"] == pytest.approx(100_000_000.0)
        assert account["balance"] == pytest.approx(99_000_000.0)
