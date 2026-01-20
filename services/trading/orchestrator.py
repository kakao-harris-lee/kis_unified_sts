"""Trading Orchestrator

통합 트레이딩 오케스트레이터.

주식/선물 모두 지원하는 통합 트레이딩 시스템 관리.

Usage:
    config = TradingConfig(
        asset_class="stock",
        strategy_name="bb_reversion",
        initial_capital=10_000_000,
    )

    orchestrator = TradingOrchestrator(config)
    await orchestrator.start()

    # 상태 조회
    status = orchestrator.get_status()

    # 종료
    await orchestrator.stop()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from services.trading.pipeline import TradingPipeline, PipelineStage

if TYPE_CHECKING:
    from shared.config.schema import MarketScheduleConfig, PipelineConfig

logger = logging.getLogger(__name__)


def _load_holidays_from_config(config_path: str = "config/market_schedule.yaml") -> set[date]:
    """설정 파일에서 공휴일 로드"""
    holidays: set[date] = set()
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Holiday config not found: {config_path}, using empty set")
        return holidays

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for holiday_str in data.get("holidays", []):
            try:
                holidays.add(date.fromisoformat(holiday_str))
            except (ValueError, TypeError):
                pass
    except Exception as e:
        logger.error(f"Failed to load holidays: {e}")

    return holidays


# 설정에서 로드된 공휴일 (lazy load)
_cached_holidays: set[date] | None = None


def _get_holidays() -> set[date]:
    """공휴일 가져오기 (캐시 사용)"""
    global _cached_holidays
    if _cached_holidays is None:
        _cached_holidays = _load_holidays_from_config()
    return _cached_holidays


def reload_holidays():
    """공휴일 다시 로드 (설정 변경 시)"""
    global _cached_holidays
    _cached_holidays = None


class TradingState(Enum):
    """트레이딩 상태"""

    IDLE = "idle"  # 대기 중
    WAITING = "waiting"  # 장 시작 대기
    RUNNING = "running"  # 거래 중
    PAUSED = "paused"  # 일시 정지
    STOPPED = "stopped"  # 종료됨


@dataclass
class MarketSchedule:
    """장 시간 설정"""

    # 주식
    stock_open: time = field(default_factory=lambda: time(9, 0))
    stock_close: time = field(default_factory=lambda: time(15, 30))

    # 선물
    futures_open: time = field(default_factory=lambda: time(9, 0))
    futures_close: time = field(default_factory=lambda: time(15, 45))

    # 서비스 시작/종료 (장 시작 전/후 여유)
    service_start_offset_minutes: int = 5
    service_end_offset_minutes: int = 5

    def get_open_time(self, asset_class: str) -> time:
        return self.stock_open if asset_class == "stock" else self.futures_open

    def get_close_time(self, asset_class: str) -> time:
        return self.stock_close if asset_class == "stock" else self.futures_close


def is_trading_day(d: date | None = None, holidays: set[date] | None = None) -> bool:
    """거래일 여부 확인

    Args:
        d: 확인할 날짜 (None이면 오늘)
        holidays: 공휴일 set (None이면 설정 파일에서 로드)

    Returns:
        거래일이면 True
    """
    if d is None:
        d = date.today()

    # 주말
    if d.weekday() >= 5:
        return False

    # 공휴일
    if holidays is None:
        holidays = _get_holidays()

    if d in holidays:
        return False

    return True


@dataclass
class TradingConfig:
    """트레이딩 설정"""

    # 기본 설정
    asset_class: str = "stock"  # "stock" or "futures"
    strategy_name: str = "bb_reversion"
    initial_capital: float = 10_000_000

    # 거래 대상
    symbols: list[str] = field(default_factory=list)  # 주식 종목 코드들

    # 스케줄
    schedule: MarketSchedule = field(default_factory=MarketSchedule)

    # 모드
    paper_trading: bool = True  # 모의투자 여부
    auto_start: bool = True  # 장 시작 시 자동 시작

    # 알림
    enable_telegram: bool = True
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Redis (선택)
    redis_url: str | None = None

    @classmethod
    def stock(
        cls,
        strategy_name: str = "bb_reversion",
        symbols: list[str] | None = None,
        initial_capital: float = 10_000_000,
    ) -> TradingConfig:
        """주식용 설정"""
        return cls(
            asset_class="stock",
            strategy_name=strategy_name,
            symbols=symbols or [],
            initial_capital=initial_capital,
        )

    @classmethod
    def futures(
        cls,
        strategy_name: str = "pure_micro",
        initial_capital: float = 10_000_000,
    ) -> TradingConfig:
        """선물용 설정"""
        return cls(
            asset_class="futures",
            strategy_name=strategy_name,
            initial_capital=initial_capital,
        )


class TradingOrchestrator:
    """트레이딩 오케스트레이터

    트레이딩 시스템의 전체 생명주기 관리:
    - 장 시간 감지 및 자동 시작/종료
    - 파이프라인 관리
    - 상태 모니터링
    - 알림 전송

    Usage:
        orchestrator = TradingOrchestrator(config)
        await orchestrator.run()  # 데몬 모드 (매일 반복)
        # 또는
        await orchestrator.run_session()  # 오늘만 실행
    """

    def __init__(self, config: TradingConfig):
        """
        Args:
            config: 트레이딩 설정
        """
        self.config = config
        self.state = TradingState.IDLE
        self.pipeline: TradingPipeline | None = None

        # 통계
        self.start_time: datetime | None = None
        self.session_count = 0
        self.total_trades = 0
        self.total_pnl = 0.0

        # 내부 상태
        self._running = False
        self._main_task: asyncio.Task | None = None

        logger.info(
            f"TradingOrchestrator initialized: "
            f"{config.asset_class}/{config.strategy_name}"
        )

    @property
    def is_running(self) -> bool:
        return self._running and self.state in (TradingState.RUNNING, TradingState.WAITING)

    async def start(self):
        """거래 시작"""
        if self.state == TradingState.RUNNING:
            logger.warning("Already running")
            return

        self.state = TradingState.RUNNING
        self.start_time = datetime.now()

        logger.info("Starting trading...")

        # 파이프라인 생성 및 시작
        self.pipeline = self._create_pipeline()
        await self.pipeline.start()

        await self._notify(
            f"🚀 Trading Started\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}\n"
            f"Capital: {self.config.initial_capital:,.0f}"
        )

    async def stop(self):
        """거래 종료"""
        if self.state == TradingState.STOPPED:
            return

        logger.info("Stopping trading...")

        if self.pipeline:
            await self.pipeline.stop()
            self.pipeline = None

        self.state = TradingState.STOPPED
        self._running = False

        await self._notify(
            f"🛑 Trading Stopped\n"
            f"Session: {self.session_count}\n"
            f"Trades: {self.total_trades}\n"
            f"PnL: {self.total_pnl:+,.0f}"
        )

    async def pause(self):
        """일시 정지"""
        if self.state != TradingState.RUNNING:
            return

        logger.info("Pausing trading...")
        self.state = TradingState.PAUSED

        if self.pipeline:
            await self.pipeline.stop()

        await self._notify("⏸️ Trading Paused")

    async def resume(self):
        """재개"""
        if self.state != TradingState.PAUSED:
            return

        logger.info("Resuming trading...")
        self.state = TradingState.RUNNING

        if self.pipeline:
            await self.pipeline.start()

        await self._notify("▶️ Trading Resumed")

    async def run_session(self):
        """단일 세션 실행 (오늘만)"""
        today = date.today()

        # 거래일 체크
        if not is_trading_day(today):
            reason = "주말" if today.weekday() >= 5 else "공휴일"
            logger.info(f"Not a trading day: {reason}")
            await self._notify(f"🏖️ 휴장일: {reason}")
            return

        now = datetime.now()
        schedule = self.config.schedule
        open_time = schedule.get_open_time(self.config.asset_class)
        close_time = schedule.get_close_time(self.config.asset_class)

        # 장 시작 대기
        open_dt = datetime.combine(today, open_time)
        if now < open_dt:
            wait_seconds = (open_dt - now).total_seconds()
            logger.info(f"Waiting for market open: {wait_seconds:.0f}s")
            self.state = TradingState.WAITING
            await asyncio.sleep(wait_seconds)

        # 거래 시작
        await self.start()
        self.session_count += 1

        # 장 종료까지 대기
        close_dt = datetime.combine(today, close_time)
        now = datetime.now()

        if now < close_dt:
            wait_seconds = (close_dt - now).total_seconds()
            logger.info(f"Trading until market close: {wait_seconds:.0f}s")

            try:
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                pass

        # 거래 종료
        await self.stop()

    async def run(self):
        """데몬 모드 실행 (매일 반복)"""
        logger.info("Starting trading orchestrator (daemon mode)")
        self._running = True

        await self._notify(
            f"🤖 Trading Orchestrator Started\n"
            f"Mode: {'Paper' if self.config.paper_trading else 'Live'}\n"
            f"Asset: {self.config.asset_class}\n"
            f"Strategy: {self.config.strategy_name}"
        )

        while self._running:
            try:
                await self.run_session()

                # 다음 날까지 대기
                now = datetime.now()
                tomorrow = (now + timedelta(days=1)).replace(
                    hour=8,
                    minute=55,
                    second=0,
                    microsecond=0,
                )

                wait_seconds = (tomorrow - now).total_seconds()
                logger.info(f"Next session in {wait_seconds / 3600:.1f} hours")

                self.state = TradingState.IDLE
                await asyncio.sleep(wait_seconds)

            except asyncio.CancelledError:
                logger.info("Orchestrator cancelled")
                break
            except Exception as e:
                logger.error(f"Session error: {e}")
                await self._notify(f"⚠️ Error: {e}")
                await asyncio.sleep(60)  # 1분 후 재시도

        await self.stop()

    def _create_pipeline(self) -> TradingPipeline:
        """파이프라인 생성"""
        # 실제 구현에서는 전략에 따라 핸들러 설정
        # 여기서는 더미 핸들러 사용
        async def dummy_regime():
            return None

        async def dummy_entry():
            return None

        async def dummy_monitoring():
            return None

        async def dummy_exit():
            return None

        return TradingPipeline(
            regime_handler=dummy_regime,
            entry_handler=dummy_entry,
            monitoring_handler=dummy_monitoring,
            exit_handler=dummy_exit,
        )

    async def _notify(self, message: str):
        """알림 전송"""
        if not self.config.enable_telegram:
            logger.info(f"Notification (telegram disabled): {message}")
            return

        try:
            from services.monitoring.notifier import TelegramConfig, TelegramNotifier

            # 환경변수 또는 config에서 토큰 로드
            config = TelegramConfig.from_env()

            # config에 토큰이 있으면 우선 사용
            if self.config.telegram_token and self.config.telegram_chat_id:
                config = TelegramConfig(
                    token=self.config.telegram_token,
                    chat_id=self.config.telegram_chat_id,
                )

            if not config.is_configured:
                logger.warning("Telegram not configured, skipping notification")
                return

            notifier = TelegramNotifier(config)
            try:
                success = await notifier.send(message)
                if not success:
                    logger.warning(f"Failed to send telegram notification: {message[:50]}...")
            finally:
                await notifier.close()

        except ImportError:
            logger.debug("TelegramNotifier not available")
        except Exception as e:
            logger.error(f"Notification error: {e}")

    def get_status(self) -> dict[str, Any]:
        """상태 조회"""
        pipeline_status = self.pipeline.get_status() if self.pipeline else {}

        return {
            "state": self.state.value,
            "config": {
                "asset_class": self.config.asset_class,
                "strategy": self.config.strategy_name,
                "capital": self.config.initial_capital,
                "paper_trading": self.config.paper_trading,
            },
            "stats": {
                "session_count": self.session_count,
                "total_trades": self.total_trades,
                "total_pnl": self.total_pnl,
                "start_time": self.start_time.isoformat() if self.start_time else None,
            },
            "pipeline": pipeline_status,
        }

    def get_metrics(self) -> dict[str, Any]:
        """메트릭 조회"""
        if self.pipeline:
            return self.pipeline.metrics.to_dict()
        return {}


# 편의 함수
async def run_stock_trading(
    strategy: str = "bb_reversion",
    symbols: list[str] | None = None,
    capital: float = 10_000_000,
    daemon: bool = False,
):
    """주식 트레이딩 실행"""
    config = TradingConfig.stock(
        strategy_name=strategy,
        symbols=symbols,
        initial_capital=capital,
    )

    orchestrator = TradingOrchestrator(config)

    if daemon:
        await orchestrator.run()
    else:
        await orchestrator.run_session()


async def run_futures_trading(
    strategy: str = "pure_micro",
    capital: float = 10_000_000,
    daemon: bool = False,
):
    """선물 트레이딩 실행"""
    config = TradingConfig.futures(
        strategy_name=strategy,
        initial_capital=capital,
    )

    orchestrator = TradingOrchestrator(config)

    if daemon:
        await orchestrator.run()
    else:
        await orchestrator.run_session()
