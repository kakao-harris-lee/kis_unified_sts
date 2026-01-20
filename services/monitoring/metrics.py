"""메트릭 수집기

Prometheus 호환 메트릭 수집.

Usage:
    from services.monitoring import MetricsCollector

    metrics = MetricsCollector()

    # 거래 메트릭
    metrics.record_trade(pnl=10000, win=True)

    # 시그널 메트릭
    metrics.record_signal(strategy="bb_reversion", signal_type="entry")

    # 내보내기
    prometheus_metrics = metrics.export_prometheus()
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Optional Prometheus
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


@dataclass
class TradingMetrics:
    """트레이딩 메트릭"""

    # 거래 통계
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0

    # 시그널 통계
    entry_signals: int = 0
    exit_signals: int = 0
    rejected_signals: int = 0

    # 레이턴시
    signal_latency_ms: float = 0.0
    order_latency_ms: float = 0.0

    # 포지션
    open_positions: int = 0
    max_positions: int = 0

    # 시스템
    errors: int = 0
    uptime_seconds: float = 0.0

    # 타임스탬프
    last_trade_time: datetime | None = None
    last_signal_time: datetime | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades * 100

    @property
    def avg_pnl(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": {
                "total": self.total_trades,
                "winning": self.winning_trades,
                "losing": self.losing_trades,
                "win_rate": round(self.win_rate, 2),
                "total_pnl": round(self.total_pnl, 0),
                "avg_pnl": round(self.avg_pnl, 0),
            },
            "signals": {
                "entry": self.entry_signals,
                "exit": self.exit_signals,
                "rejected": self.rejected_signals,
            },
            "latency": {
                "signal_ms": round(self.signal_latency_ms, 2),
                "order_ms": round(self.order_latency_ms, 2),
            },
            "positions": {
                "open": self.open_positions,
                "max": self.max_positions,
            },
            "system": {
                "errors": self.errors,
                "uptime_seconds": round(self.uptime_seconds, 0),
            },
            "timestamps": {
                "last_trade": (
                    self.last_trade_time.isoformat() if self.last_trade_time else None
                ),
                "last_signal": (
                    self.last_signal_time.isoformat() if self.last_signal_time else None
                ),
                "updated_at": self.updated_at.isoformat(),
            },
        }


class MetricsCollector:
    """메트릭 수집기

    Prometheus 호환 메트릭 수집 및 내보내기.

    Usage:
        collector = MetricsCollector()

        # 거래 기록
        collector.record_trade(pnl=10000, win=True)

        # Prometheus 서버 시작 (선택)
        collector.start_prometheus_server(port=8080)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.metrics = TradingMetrics()
        self._start_time = time.time()

        # Prometheus 메트릭 (선택)
        if HAS_PROMETHEUS:
            self._setup_prometheus_metrics()

        logger.info("MetricsCollector initialized")

    def _setup_prometheus_metrics(self):
        """Prometheus 메트릭 설정"""
        # Counters
        self.prom_trades_total = Counter(
            "trading_trades_total",
            "Total number of trades",
            ["strategy", "outcome"],
        )
        self.prom_signals_total = Counter(
            "trading_signals_total",
            "Total number of signals",
            ["strategy", "type"],
        )
        self.prom_errors_total = Counter(
            "trading_errors_total",
            "Total number of errors",
            ["component"],
        )

        # Gauges
        self.prom_pnl_total = Gauge(
            "trading_pnl_total",
            "Total PnL in KRW",
        )
        self.prom_positions_open = Gauge(
            "trading_positions_open",
            "Number of open positions",
        )
        self.prom_win_rate = Gauge(
            "trading_win_rate",
            "Win rate percentage",
        )

        # Histograms
        self.prom_trade_pnl = Histogram(
            "trading_trade_pnl",
            "Trade PnL distribution",
            buckets=[-100000, -50000, -10000, 0, 10000, 50000, 100000, 500000],
        )
        self.prom_signal_latency = Histogram(
            "trading_signal_latency_ms",
            "Signal generation latency in ms",
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000],
        )
        self.prom_order_latency = Histogram(
            "trading_order_latency_ms",
            "Order execution latency in ms",
            buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000],
        )

    def record_trade(
        self,
        pnl: float,
        win: bool,
        strategy: str = "default",
    ):
        """거래 기록"""
        self.metrics.total_trades += 1
        self.metrics.total_pnl += pnl
        self.metrics.last_trade_time = datetime.now()

        if win:
            self.metrics.winning_trades += 1
        else:
            self.metrics.losing_trades += 1

        # Prometheus
        if HAS_PROMETHEUS:
            outcome = "win" if win else "loss"
            self.prom_trades_total.labels(strategy=strategy, outcome=outcome).inc()
            self.prom_pnl_total.set(self.metrics.total_pnl)
            self.prom_trade_pnl.observe(pnl)
            self.prom_win_rate.set(self.metrics.win_rate)

        logger.debug(f"Trade recorded: pnl={pnl:+,.0f}, win={win}")

    def record_signal(
        self,
        signal_type: str,  # "entry", "exit", "rejected"
        strategy: str = "default",
        latency_ms: float = 0.0,
    ):
        """시그널 기록"""
        if signal_type == "entry":
            self.metrics.entry_signals += 1
        elif signal_type == "exit":
            self.metrics.exit_signals += 1
        else:
            self.metrics.rejected_signals += 1

        self.metrics.last_signal_time = datetime.now()

        if latency_ms > 0:
            # 이동 평균
            self.metrics.signal_latency_ms = (
                self.metrics.signal_latency_ms * 0.9 + latency_ms * 0.1
            )

        # Prometheus
        if HAS_PROMETHEUS:
            self.prom_signals_total.labels(strategy=strategy, type=signal_type).inc()
            if latency_ms > 0:
                self.prom_signal_latency.observe(latency_ms)

    def record_order_latency(self, latency_ms: float):
        """주문 레이턴시 기록"""
        self.metrics.order_latency_ms = (
            self.metrics.order_latency_ms * 0.9 + latency_ms * 0.1
        )

        if HAS_PROMETHEUS:
            self.prom_order_latency.observe(latency_ms)

    def record_position_change(self, open_positions: int):
        """포지션 변경 기록"""
        self.metrics.open_positions = open_positions
        if open_positions > self.metrics.max_positions:
            self.metrics.max_positions = open_positions

        if HAS_PROMETHEUS:
            self.prom_positions_open.set(open_positions)

    def record_error(self, component: str = "unknown"):
        """에러 기록"""
        self.metrics.errors += 1

        if HAS_PROMETHEUS:
            self.prom_errors_total.labels(component=component).inc()

    def get_metrics(self) -> TradingMetrics:
        """메트릭 조회"""
        self.metrics.uptime_seconds = time.time() - self._start_time
        self.metrics.updated_at = datetime.now()
        return self.metrics

    def reset(self):
        """메트릭 초기화"""
        self.metrics = TradingMetrics()
        self._start_time = time.time()

    def start_prometheus_server(self, port: int = 8080):
        """Prometheus HTTP 서버 시작"""
        if not HAS_PROMETHEUS:
            logger.warning("Prometheus client not installed")
            return

        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")

    def export_prometheus(self) -> str:
        """Prometheus 텍스트 포맷으로 내보내기"""
        if not HAS_PROMETHEUS:
            return ""

        from prometheus_client import generate_latest

        return generate_latest().decode("utf-8")


# 전역 메트릭 컬렉터
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """전역 메트릭 컬렉터 반환"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
