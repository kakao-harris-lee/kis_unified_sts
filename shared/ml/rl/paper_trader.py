"""RL-MPPO 실시간 Paper Trading 엔진

학습된 MaskablePPO 모델을 KIS WebSocket 실시간 데이터로 추론.

데이터 흐름:
    KIS WebSocket (H0IFCNT0)
    → DataEngine.ingest_tick() → 1분봉 집계
    → pandas 변환 → RLFeatureCalculator (25개 지표)
    → MinMaxScaler 정규화
    → Observation (31차원) = market(25) + position(3) + time(3)
    → MaskablePPO.predict(obs, action_masks)
    → Paper 거래 실행 / Telegram 알림

Usage:
    trader = RLPaperTrader()
    asyncio.run(trader.run())
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import numpy as np

from core.data_engine import DataEngine, DataEngineConfig
from shared.collector.models import TickData
from shared.config import ConfigLoader
from shared.kis.auth import KISAuthConfig
from shared.kis.websocket import KISWebSocketAdapter
from shared.ml.rl.env import Action, PositionSide, RLEnvConfig
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS
from shared.ml.rl.position_sizing import KellyPositionSizer

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass
class PaperTradeRecord:
    """단건 거래 기록"""

    timestamp: str
    action: str
    side: str
    entry_price: float
    exit_price: float
    pnl: float
    balance: float


@dataclass
class SessionState:
    """일일 세션 상태 (env.py 포지션 로직 재사용)"""

    position: PositionSide = PositionSide.FLAT
    contracts: int = 0
    entry_price: float = 0.0
    total_pnl: float = 0.0
    n_trades: int = 0
    wins: int = 0
    losses: int = 0
    current_price: float = 0.0
    bar_count: int = 0
    trade_history: list[PaperTradeRecord] = field(default_factory=list)


class RLPaperTrader:
    """RL-MPPO 실시간 paper trading 엔진

    KIS WebSocket → DataEngine(분봉집계) → RLFeatureCalculator
    → MaskablePPO 추론 → Paper 거래 + Telegram 알림
    """

    def __init__(
        self,
        config_path: str = "ml/rl_mppo.yaml",
        model_name: str = "mppo_final",
        symbol: str | None = None,
        algo: str | None = None,
    ):
        # 설정 로드
        full_config = ConfigLoader.load(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)
        self.paper_config = full_config.get("paper", {})
        training_config = full_config.get("training", {})

        self.symbol = symbol or self.paper_config.get("symbol", "101S6000")
        self.warmup_bars = self.paper_config.get("warmup_bars", 200)
        self.force_close_time = self.paper_config.get("force_close_time", "15:35")
        self.telegram_enabled = self.paper_config.get("telegram_notify", True)
        self.log_dir = Path(self.paper_config.get("log_dir", "./results/rl/paper/"))
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 모델 경로 결정
        save_dir = Path(training_config.get("save_dir", "./models/futures/rl/"))

        # 알고리즘 자동 감지
        self.algo = algo or self._detect_algo(save_dir / model_name)

        # 모델 + scaler 로드
        scaler_path = save_dir / "scaler.joblib"
        if not scaler_path.exists():
            raise FileNotFoundError(
                f"Scaler not found: {scaler_path}. "
                "Run: python scripts/training/train_rl.py --save-scaler-only"
            )
        self.scaler = joblib.load(scaler_path)
        logger.info(f"Loaded scaler: {scaler_path}")

        if self.algo == "dt":
            from shared.ml.rl.decision_transformer.model import DTAgent

            model_dir = save_dir / model_name
            self.model = DTAgent.load(model_dir)
            self._dt_target_return = float(
                self.paper_config.get("target_return", 5_000_000)
            )
            self._last_reward = 0.0
            logger.info(f"Loaded DT model: {model_dir}")
        else:
            model_path = save_dir / model_name / "best_model.zip"
            if not model_path.exists():
                raise FileNotFoundError(f"Model not found: {model_path}")

            from sb3_contrib import MaskablePPO

            self.model = MaskablePPO.load(model_path)
            logger.info(f"Loaded model: {model_path}")

        # 데이터 인프라
        self.data_engine = DataEngine(DataEngineConfig(max_bars=600))
        self.feature_calc = RLFeatureCalculator()

        # 포지션/세션 상태
        self.state = SessionState()

        # WebSocket
        self._ws_adapter: KISWebSocketAdapter | None = None
        self._stop_event = threading.Event()

        # Kelly position sizing
        self._kelly_sizer = KellyPositionSizer.from_yaml(config_path)
        if self._kelly_sizer.config.enabled:
            logger.info(
                f"Kelly position sizing enabled: "
                f"fraction={self._kelly_sizer.config.fraction}, "
                f"min_scale={self._kelly_sizer.config.min_scale}"
            )

        # Notifier (lazy init)
        self._notifier = None

        # Main event loop reference (set in run())
        self._main_loop: asyncio.AbstractEventLoop | None = None

        # Monitoring (lazy init in run())
        self._state_publisher: Any = None
        self._metrics: Any = None
        self._entry_time: datetime | None = None

    @staticmethod
    def _detect_algo(model_dir: Path) -> str:
        """모델 디렉토리에서 알고리즘 자동 감지

        model.pt 존재 → DT, 아니면 MPPO.
        """
        if (model_dir / "model.pt").exists():
            return "dt"
        return "mppo"

    async def _get_notifier(self):
        """Telegram notifier (lazy init)"""
        if self._notifier is None and self.telegram_enabled:
            from services.monitoring.notifier import TelegramNotifier

            self._notifier = TelegramNotifier.from_env()
        return self._notifier

    async def _notify(self, message: str) -> None:
        """Telegram 메시지 전송"""
        notifier = await self._get_notifier()
        if notifier:
            try:
                await notifier.send(message)
            except Exception as e:
                logger.warning(f"Telegram send failed: {e}")

    # =========================================================================
    # Monitoring: Redis state publisher + Prometheus
    # =========================================================================

    def _init_monitoring(self) -> None:
        """Init Redis state publisher + Prometheus metrics."""
        try:
            from shared.streaming.trading_state import TradingStatePublisher

            self._state_publisher = TradingStatePublisher("futures")
            logger.info("Redis state publisher initialized for futures")
        except Exception as e:
            logger.warning(f"Redis state publisher init failed: {e}")

        try:
            from services.monitoring.metrics import MetricsCollector

            self._metrics = MetricsCollector()
            self._metrics.start_prometheus_server(port=9092)
            logger.info("Prometheus metrics server started on port 9092")
        except Exception as e:
            logger.warning(f"Prometheus metrics init failed: {e}")

    def _publish_status(self, state: str = "running") -> None:
        """Publish current status to Redis."""
        if not self._state_publisher:
            return
        s = self.state
        self._state_publisher.publish_status({
            "state": state,
            "config": {
                "strategy": "rl_mppo",
                "asset_class": "futures",
                "symbol": self.symbol,
            },
            "stats": {
                "total_pnl": s.total_pnl,
                "trades": s.n_trades,
                "wins": s.wins,
                "losses": s.losses,
                "start_time": datetime.now(KST).isoformat(),
            },
            "strategies": {"strategies": ["rl_mppo"]},
            "positions": {
                "open_positions": 1 if s.position != PositionSide.FLAT else 0,
            },
        })

    def _publish_position_update(self) -> None:
        """Publish current position to Redis (real-time unrealized PnL)."""
        if not self._state_publisher:
            return
        if self.state.position == PositionSide.FLAT:
            return

        unrealized = self._get_unrealized_pnl()
        cfg = self.env_config
        entry_val = self.state.entry_price * cfg.contract_multiplier * self.state.contracts
        pnl_pct = (unrealized / entry_val * 100) if entry_val > 0 else 0.0

        pos_id = f"rl_{self.symbol}"
        self._state_publisher.publish_raw_position(pos_id, {
            "id": pos_id,
            "code": self.symbol,
            "name": "KOSPI200 선물",
            "side": "long" if self.state.position == PositionSide.LONG else "short",
            "quantity": self.state.contracts,
            "entry_price": self.state.entry_price,
            "current_price": self.state.current_price,
            "unrealized_pnl": unrealized,
            "pnl_pct": round(pnl_pct, 2),
            "entry_time": self._entry_time.isoformat() if self._entry_time else datetime.now(KST).isoformat(),
            "strategy": "rl_mppo",
            "state": "OPEN",
        })

    def _publish_entry(self, side: str, price: float) -> None:
        """Publish entry signal + position to Redis + Prometheus."""
        self._entry_time = datetime.now(KST)
        now_str = self._entry_time.isoformat()

        if self._state_publisher:
            pos_id = f"rl_{self.symbol}"
            self._state_publisher.publish_raw_position(pos_id, {
                "id": pos_id,
                "code": self.symbol,
                "name": "KOSPI200 선물",
                "side": side.lower(),
                "quantity": self.state.contracts,
                "entry_price": price,
                "current_price": price,
                "unrealized_pnl": 0.0,
                "pnl_pct": 0.0,
                "entry_time": now_str,
                "strategy": "rl_mppo",
                "state": "OPEN",
            })
            self._state_publisher.publish_raw_signal({
                "symbol": self.symbol,
                "name": "KOSPI200 선물",
                "side": "entry",
                "signal_type": "entry",
                "strategy": "rl_mppo",
                "price": price,
                "confidence": 1.0,
                "timestamp": now_str,
                "executed": True,
            })

        if self._metrics:
            self._metrics.record_signal("entry", strategy="rl_mppo")
            self._metrics.record_position_change(1)

    def _publish_exit(self, side: str, entry_price: float, exit_price: float, pnl: float) -> None:
        """Publish exit signal + trade to Redis + Prometheus."""
        now_str = datetime.now(KST).isoformat()
        cfg = self.env_config
        entry_val = entry_price * cfg.contract_multiplier * self.state.contracts
        pnl_pct = (pnl / entry_val * 100) if entry_val > 0 else 0.0

        if self._state_publisher:
            pos_id = f"rl_{self.symbol}"
            self._state_publisher.remove_position(pos_id)
            self._state_publisher.publish_raw_trade({
                "id": f"rl_{int(time.time())}",
                "symbol": self.symbol,
                "name": "KOSPI200 선물",
                "side": side.lower(),
                "quantity": self.state.contracts,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": round(pnl_pct, 2),
                "strategy": "rl_mppo",
                "entry_time": self._entry_time.isoformat() if self._entry_time else now_str,
                "exit_time": now_str,
            })
            self._state_publisher.publish_raw_signal({
                "symbol": self.symbol,
                "name": "KOSPI200 선물",
                "side": "exit",
                "signal_type": "exit",
                "strategy": "rl_mppo",
                "price": exit_price,
                "confidence": 1.0,
                "timestamp": now_str,
                "executed": True,
            })

        if self._metrics:
            self._metrics.record_trade(pnl=pnl, win=(pnl > 0), strategy="rl_mppo")
            self._metrics.record_signal("exit", strategy="rl_mppo")
            self._metrics.record_position_change(0)

    # =========================================================================
    # Warmup: ClickHouse에서 과거 분봉 로드
    # =========================================================================

    def _load_warmup_bars(self) -> int:
        """ClickHouse에서 과거 분봉 로드 (당일 데이터 우선, 부족하면 전일 포함)"""
        try:
            import os

            from clickhouse_driver import Client

            client = Client(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            )

            rows = client.execute(
                f"""
                SELECT datetime, open, high, low, close, volume
                FROM kospi.kospi200f_1m
                WHERE code = %(symbol)s
                ORDER BY datetime DESC
                LIMIT %(limit)s
                """,
                {"symbol": self.symbol, "limit": self.warmup_bars},
            )

            if not rows:
                logger.warning("No warmup data from ClickHouse")
                return 0

            # DataEngine에 역순으로 로드 (oldest first)
            rows_dicts = [
                {
                    "code": self.symbol,
                    "datetime": r[0],
                    "open": float(r[1]),
                    "high": float(r[2]),
                    "low": float(r[3]),
                    "close": float(r[4]),
                    "volume": int(r[5]),
                    "value": 0,
                }
                for r in reversed(rows)
            ]

            self.data_engine.load_history(self.symbol, rows_dicts)
            logger.info(f"Warmup: loaded {len(rows_dicts)} bars from ClickHouse")
            return len(rows_dicts)

        except Exception as e:
            logger.warning(f"Warmup failed: {e}")
            return 0

    # =========================================================================
    # WebSocket 콜백
    # =========================================================================

    def _on_tick(self, tick: TickData) -> None:
        """체결(H0IFCNT0) 수신 콜백 — DataEngine으로 분봉 집계"""
        if tick.current_price is None or tick.current_price <= 0:
            return

        # 현재가 업데이트
        self.state.current_price = tick.current_price

        # 기존 바 카운트 저장
        frame = self.data_engine.get_frame(self.symbol)
        prev_count = len(frame) if frame is not None else 0

        # tick → DataEngine (1분봉 집계)
        self.data_engine.ingest_tick(
            {
                "symbol": self.symbol,
                "current_price": tick.current_price,
                "timestamp": tick.timestamp,
                "tick_volume": int(tick.tick_volume or 0),
            }
        )

        # 새 바 완성 감지
        frame = self.data_engine.get_frame(self.symbol)
        new_count = len(frame) if frame is not None else 0

        if new_count > prev_count:
            self.state.bar_count = new_count
            # 새 분봉 → RL 추론 (메인 이벤트 루프에 예약)
            if self._main_loop and self._main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._on_new_bar(), self._main_loop
                )
            else:
                logger.warning("Main event loop not available for RL inference")

    # =========================================================================
    # RL 추론
    # =========================================================================

    async def _on_new_bar(self) -> None:
        """새 1분봉 완성 시 RL 추론 실행"""
        frame = self.data_engine.get_frame(self.symbol)
        if frame is None:
            return

        try:
            df = frame.to_pandas()
        except Exception as e:
            logger.warning(f"Polars→pandas conversion failed: {e}")
            return

        if len(df) < 30:
            logger.debug(f"Not enough bars for features: {len(df)}")
            return

        # 피처 계산
        try:
            df = self.feature_calc.calculate(df)
            df = df.dropna(subset=RL_FEATURE_COLUMNS)
        except Exception as e:
            logger.warning(f"Feature calculation failed: {e}")
            return

        if df.empty:
            return

        # 최신 바의 피처
        features = df[RL_FEATURE_COLUMNS].iloc[-1:].values

        # scaler 정규화
        try:
            scaled = self.scaler.transform(features)
        except Exception as e:
            logger.warning(f"Scaler transform failed: {e}")
            return

        # Observation 구성 (env.py _get_observation과 동일 구조)
        obs = self._build_observation(scaled[0], total_bars=len(df))

        # Action mask
        masks = self._get_action_masks()

        # 모델 추론
        if self.algo == "dt":
            action_int, action_probs = self.model.predict(
                obs, action_masks=masks, reward=self._last_reward, deterministic=True,
            )
        else:
            action_int, _ = self.model.predict(
                obs, action_masks=masks, deterministic=True
            )
            action_probs = None
        action = Action(int(action_int))

        # Kelly 포지션 사이징: 진입 행동일 때만 확인
        if action in (Action.LONG_ENTRY, Action.SHORT_ENTRY):
            if self.algo == "dt":
                probs_for_kelly = action_probs
            else:
                probs_for_kelly = self._get_action_probs(obs, masks)
            if not self._kelly_sizer.should_trade(probs_for_kelly):
                logger.debug(
                    f"Kelly filter: skipping {action.name} (low confidence)"
                )
                action = Action.HOLD

        # 거래 실행 — DT RTG 업데이트를 위해 step reward 추적
        pnl_before = self.state.total_pnl + self._get_unrealized_pnl()
        if action != Action.HOLD:
            await self._execute_action(action)
            logger.info(
                f"Action: {action.name} | Price: {self.state.current_price:.2f} | "
                f"Position: {self.state.position.name} | PnL: {self.state.total_pnl:+,.0f}"
            )
        pnl_after = self.state.total_pnl + self._get_unrealized_pnl()
        if self.algo == "dt":
            self._last_reward = pnl_after - pnl_before

    def _build_observation(
        self, market_features: np.ndarray, _total_bars: int
    ) -> np.ndarray:
        """관측 벡터 구성 (31차원 = market 25 + position 3 + time 3)"""
        # 포지션 피처 (3개)
        unrealized = self._get_unrealized_pnl()
        position_features = np.array(
            [
                float(self.state.position),
                float(self.state.contracts) / max(self.env_config.max_contracts, 1),
                unrealized / self.env_config.initial_balance,
            ],
            dtype=np.float32,
        )

        # 시간 피처 (3개) — 장중 위치
        # 09:00~15:45 = 405분
        now = datetime.now(KST)
        market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=45, second=0, microsecond=0)
        total_minutes = (market_close - market_open).total_seconds() / 60
        elapsed = (now - market_open).total_seconds() / 60
        progress = max(0.0, min(1.0, elapsed / total_minutes))

        time_features = np.array(
            [
                progress,
                np.sin(2 * np.pi * progress),
                np.cos(2 * np.pi * progress),
            ],
            dtype=np.float32,
        )

        return np.concatenate(
            [market_features, position_features, time_features]
        ).astype(np.float32)

    def _get_action_probs(
        self, obs: np.ndarray, masks: np.ndarray
    ) -> np.ndarray | None:
        """모델의 행동 확률 분포 추출 (Kelly confidence 계산용)"""
        try:
            import torch

            with torch.no_grad():
                obs_tensor = torch.as_tensor(obs).unsqueeze(0).to(self.model.device)
                dist = self.model.policy.get_distribution(obs_tensor)
                probs = dist.distribution.probs.cpu().numpy()[0]
            # 유효 행동만 추출
            valid_probs = probs[masks]
            return valid_probs if len(valid_probs) > 0 else None
        except (AttributeError, RuntimeError) as e:
            logger.debug(f"Could not extract action probs for Kelly sizing: {e}")
            return None

    def _get_action_masks(self) -> np.ndarray:
        """유효 행동 마스크 (env.py action_masks와 동일 로직)"""
        masks = np.zeros(len(Action), dtype=bool)
        masks[Action.HOLD] = True

        if self.state.position == PositionSide.FLAT:
            masks[Action.LONG_ENTRY] = True
            masks[Action.SHORT_ENTRY] = True
        elif self.state.position == PositionSide.LONG:
            masks[Action.LONG_EXIT] = True
        elif self.state.position == PositionSide.SHORT:
            masks[Action.SHORT_EXIT] = True

        return masks

    # =========================================================================
    # 거래 실행 (Paper)
    # =========================================================================

    async def _execute_action(self, action: Action) -> None:
        """Paper 거래 실행 — env.py _execute_action PnL 로직 재사용"""
        price = self.state.current_price
        cfg = self.env_config
        now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

        if action == Action.LONG_ENTRY and self.state.position == PositionSide.FLAT:
            self.state.position = PositionSide.LONG
            self.state.contracts = cfg.max_contracts
            self.state.entry_price = price
            cost = price * cfg.contract_multiplier * cfg.commission_rate
            self.state.total_pnl -= cost
            self._publish_entry("long", price)

            await self._notify(
                f"<b>🔵 LONG 진입</b>\n"
                f"가격: {price:,.2f}\n"
                f"시각: {now_str}"
            )

        elif action == Action.LONG_EXIT and self.state.position == PositionSide.LONG:
            cost = price * cfg.contract_multiplier * cfg.commission_rate
            pnl = (
                (price - self.state.entry_price)
                * cfg.contract_multiplier
                * self.state.contracts
            ) - cost
            self.state.total_pnl += pnl
            self._record_trade(pnl, "LONG", price)
            self._publish_exit("LONG", self.state.entry_price, price, pnl)

            await self._notify(
                f"<b>🔵 LONG 청산</b>\n"
                f"진입: {self.state.entry_price:,.2f} → 청산: {price:,.2f}\n"
                f"{'🟢' if pnl >= 0 else '🔴'} 손익: {pnl:+,.0f}원\n"
                f"누적: {self.state.total_pnl:+,.0f}원"
            )
            self._clear_position()

        elif action == Action.SHORT_ENTRY and self.state.position == PositionSide.FLAT:
            self.state.position = PositionSide.SHORT
            self.state.contracts = cfg.max_contracts
            self.state.entry_price = price
            cost = price * cfg.contract_multiplier * cfg.commission_rate
            self.state.total_pnl -= cost
            self._publish_entry("short", price)

            await self._notify(
                f"<b>🔴 SHORT 진입</b>\n"
                f"가격: {price:,.2f}\n"
                f"시각: {now_str}"
            )

        elif action == Action.SHORT_EXIT and self.state.position == PositionSide.SHORT:
            cost = price * cfg.contract_multiplier * cfg.commission_rate
            pnl = (
                (self.state.entry_price - price)
                * cfg.contract_multiplier
                * self.state.contracts
            ) - cost
            self.state.total_pnl += pnl
            self._record_trade(pnl, "SHORT", price)
            self._publish_exit("SHORT", self.state.entry_price, price, pnl)

            await self._notify(
                f"<b>🔴 SHORT 청산</b>\n"
                f"진입: {self.state.entry_price:,.2f} → 청산: {price:,.2f}\n"
                f"{'🟢' if pnl >= 0 else '🔴'} 손익: {pnl:+,.0f}원\n"
                f"누적: {self.state.total_pnl:+,.0f}원"
            )
            self._clear_position()

    def _record_trade(self, pnl: float, side: str, exit_price: float) -> None:
        """거래 기록"""
        self.state.n_trades += 1
        if pnl > 0:
            self.state.wins += 1
        elif pnl < 0:
            self.state.losses += 1

        # Kelly sizer 이력 갱신
        self._kelly_sizer.record_trade(pnl)

        self.state.trade_history.append(
            PaperTradeRecord(
                timestamp=datetime.now(KST).isoformat(),
                action="EXIT",
                side=side,
                entry_price=self.state.entry_price,
                exit_price=exit_price,
                pnl=pnl,
                balance=self.env_config.initial_balance + self.state.total_pnl,
            )
        )

    def _clear_position(self) -> None:
        """포지션 초기화"""
        self.state.position = PositionSide.FLAT
        self.state.contracts = 0
        self.state.entry_price = 0.0

    def _get_unrealized_pnl(self) -> float:
        """미실현 손익"""
        if self.state.position == PositionSide.FLAT:
            return 0.0
        price = self.state.current_price
        cfg = self.env_config
        if self.state.position == PositionSide.LONG:
            return (price - self.state.entry_price) * cfg.contract_multiplier * self.state.contracts
        return (self.state.entry_price - price) * cfg.contract_multiplier * self.state.contracts

    # =========================================================================
    # 강제 청산 + 일일 요약
    # =========================================================================

    async def _force_close(self) -> None:
        """장 마감 전 강제 청산"""
        if self.state.position == PositionSide.FLAT:
            return

        if self.state.position == PositionSide.LONG:
            await self._execute_action(Action.LONG_EXIT)
        elif self.state.position == PositionSide.SHORT:
            await self._execute_action(Action.SHORT_EXIT)

        logger.info("Force close executed at session end")

    async def _send_daily_summary(self) -> None:
        """일일 요약 리포트 전송"""
        s = self.state
        wr = s.wins / max(s.n_trades, 1) * 100
        return_pct = s.total_pnl / self.env_config.initial_balance * 100

        summary = (
            f"<b>📊 RL Paper Trading 일일 요약</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 {datetime.now(KST).strftime('%Y-%m-%d')}\n"
            f"종목: {self.symbol}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"거래: {s.n_trades}건 (W:{s.wins} / L:{s.losses})\n"
            f"승률: {wr:.1f}%\n"
            f"{'🟢' if s.total_pnl >= 0 else '🔴'} "
            f"손익: {s.total_pnl:+,.0f}원 ({return_pct:+.2f}%)\n"
            f"분봉: {s.bar_count}개"
        )
        await self._notify(summary)

        # JSON 로그 저장
        self._save_session_log()

    def _save_session_log(self) -> None:
        """세션 거래 기록을 JSON으로 저장"""
        date_str = datetime.now(KST).strftime("%Y%m%d")
        log_path = self.log_dir / f"paper_{date_str}.json"

        log_data = {
            "date": date_str,
            "symbol": self.symbol,
            "n_trades": self.state.n_trades,
            "wins": self.state.wins,
            "losses": self.state.losses,
            "total_pnl": self.state.total_pnl,
            "bar_count": self.state.bar_count,
            "trades": [
                {
                    "timestamp": t.timestamp,
                    "action": t.action,
                    "side": t.side,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "balance": t.balance,
                }
                for t in self.state.trade_history
            ],
        }

        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Session log saved: {log_path}")

    # =========================================================================
    # 메인 루프
    # =========================================================================

    async def run(self) -> None:
        """메인 실행 — 단일 세션 (장 시작~종료)"""
        self._main_loop = asyncio.get_running_loop()
        now = datetime.now(KST)
        logger.info(
            f"RL Paper Trader starting | symbol={self.symbol} | "
            f"time={now.strftime('%H:%M:%S')}"
        )

        # 0. Monitoring (Redis + Prometheus)
        self._init_monitoring()

        # 시작 알림
        await self._notify(
            f"<b>🤖 RL Paper Trader 시작</b>\n"
            f"종목: {self.symbol}\n"
            f"모델: MaskablePPO (Phase 4 best)\n"
            f"시각: {now.strftime('%H:%M:%S')}"
        )

        # Publish initial status
        self._publish_status("running")

        # DT: 에피소드 초기화
        if self.algo == "dt":
            self.model.reset(target_return=self._dt_target_return)
            self._last_reward = 0.0

        # 1. Warmup (ClickHouse 과거 데이터)
        warmup_count = self._load_warmup_bars()
        logger.info(f"Warmup complete: {warmup_count} bars")

        # 2. KIS WebSocket 연결
        kis_config = KISAuthConfig(
            app_key=os.getenv("KIS_FUTURES_APP_KEY", os.getenv("KIS_APP_KEY", "")),
            app_secret=os.getenv("KIS_FUTURES_APP_SECRET", os.getenv("KIS_APP_SECRET", "")),
            is_real=True,
        )
        self._ws_adapter = KISWebSocketAdapter(kis_config)

        try:
            self._ws_adapter.connect()
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self._notify(f"❌ WebSocket 연결 실패: {e}")
            return

        # 3. subscribe를 별도 스레드에서 실행 (blocking 호출)
        ws_thread = threading.Thread(
            target=self._ws_subscribe_loop,
            daemon=True,
            name="RLPaper-WS",
        )
        ws_thread.start()

        # 4. 강제 청산 스케줄러 + 세션 종료 대기
        try:
            await self._session_loop()
        except asyncio.CancelledError:
            logger.info("Session cancelled")
        finally:
            # 세션 종료 처리
            await self._force_close()
            await self._send_daily_summary()

            # Publish final status + clear positions
            if self._state_publisher:
                self._state_publisher.remove_position(f"rl_{self.symbol}")
                self._publish_status("stopped")

            # WebSocket 종료
            if self._ws_adapter:
                self._ws_adapter.disconnect()

            # Notifier 정리
            if self._notifier:
                await self._notifier.close()

            logger.info("RL Paper Trader session ended")

    def _ws_subscribe_loop(self) -> None:
        """WebSocket subscribe (blocking, 별도 스레드)"""
        try:
            self._ws_adapter.subscribe([self.symbol], self._on_tick)
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"WebSocket subscribe error: {e}")

    async def _session_loop(self) -> None:
        """세션 루프 — 강제 청산 시각까지 대기 + periodic monitoring publish"""
        h, m = map(int, self.force_close_time.split(":"))
        last_status_publish = 0.0
        last_position_publish = 0.0

        while not self._stop_event.is_set():
            now = datetime.now(KST)

            # 강제 청산 시각 도달
            if now.hour > h or (now.hour == h and now.minute >= m):
                logger.info(f"Force close time reached: {self.force_close_time}")
                break

            # Periodic status publish (every 5s)
            mono = time.monotonic()
            if mono - last_status_publish >= 5.0:
                self._publish_status("running")
                last_status_publish = mono

            # Periodic position update (every 2s)
            if mono - last_position_publish >= 2.0:
                self._publish_position_update()
                last_position_publish = mono

            # 1초마다 체크
            await asyncio.sleep(1)

    def stop(self) -> None:
        """외부에서 세션 중단"""
        self._stop_event.set()
        if self._ws_adapter:
            self._ws_adapter.disconnect()


async def run_paper_trader(
    config_path: str = "ml/rl_mppo.yaml",
    model_name: str = "mppo_final",
    symbol: str | None = None,
    algo: str | None = None,
) -> None:
    """Paper trader 실행 진입점"""
    trader = RLPaperTrader(
        config_path=config_path,
        model_name=model_name,
        symbol=symbol,
        algo=algo,
    )

    # Ctrl+C 핸들링
    loop = asyncio.get_running_loop()

    def _signal_handler():
        logger.info("Received stop signal")
        trader.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await trader.run()
