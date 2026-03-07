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
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from shared.monitoring.drift_metrics import DriftMetrics

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

    # 성능 관측
    market_data_staleness_seconds: float = 0.0
    order_queue_depth: int = 0
    websocket_staleness_stock_seconds: float | None = None
    websocket_staleness_futures_seconds: float | None = None

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
            "performance": {
                "market_data_staleness_seconds": round(
                    self.market_data_staleness_seconds, 3
                ),
                "order_queue_depth": self.order_queue_depth,
                "websocket_staleness_seconds": {
                    "stock": round(self.websocket_staleness_stock_seconds, 3),
                    "futures": round(self.websocket_staleness_futures_seconds, 3),
                },
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
        self.prom_entry_blocks_total = Counter(
            "trading_entry_blocks_total",
            "Total entry blocks by execution guard reason",
            ["strategy", "reason"],
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
        self.prom_market_data_staleness = Gauge(
            "trading_market_data_staleness_seconds",
            "Market data snapshot staleness in seconds",
        )
        self.prom_websocket_staleness = Gauge(
            "trading_websocket_staleness_seconds",
            "WebSocket tick staleness in seconds",
            ["feed"],
        )
        self.prom_market_data_staleness_hist = Histogram(
            "trading_market_data_staleness_seconds_hist",
            "Market data snapshot staleness distribution",
            buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1, 2, 5],
        )
        self.prom_order_queue_depth = Gauge(
            "trading_order_queue_depth",
            "Number of queued order tasks waiting for execution capacity",
        )
        self.prom_universe_size = Gauge(
            "trading_universe_size",
            "Number of symbols in trading universe",
        )
        self.prom_warm_symbols = Gauge(
            "trading_warm_symbols",
            "Number of symbols with warm indicators",
        )
        self.prom_tracked_accumulators = Gauge(
            "trading_tracked_accumulators",
            "Total indicator accumulators",
        )
        self.prom_data_symbols_fetched = Gauge(
            "trading_data_symbols_fetched",
            "Symbols with valid market data in last fetch",
        )
        self.prom_rl_entry_action_probability = Gauge(
            "trading_rl_entry_action_probability",
            "RL entry action probability (masked and normalized)",
            ["strategy", "action"],
        )
        self.prom_signal_evaluations = Counter(
            "trading_signal_evaluations_total",
            "Total signal evaluation cycles",
        )
        self.prom_rl_kl_divergence = Gauge(
            "trading_rl_kl_divergence",
            "RL model KL divergence for observation distribution drift",
            ["strategy", "metric_type"],
        )
        self.prom_rl_action_distribution_drift = Gauge(
            "trading_rl_action_distribution_drift",
            "RL model action distribution drift",
            ["strategy"],
        )
        self.prom_rl_observation_mean_drift = Gauge(
            "trading_rl_observation_mean_drift",
            "RL model observation mean drift",
            ["strategy"],
        )
        self.prom_rl_observation_std_drift = Gauge(
            "trading_rl_observation_std_drift",
            "RL model observation std drift",
            ["strategy"],
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

    def register_strategies(self, strategy_names: list[str]) -> None:
        """Pre-initialize Prometheus counters with known strategy names.

        This ensures label_values() in Grafana can discover strategies
        even before any trades or signals are recorded.
        """
        if not HAS_PROMETHEUS:
            return

        for name in strategy_names:
            # Initialize with 0 — creates the time series in Prometheus
            self.prom_trades_total.labels(strategy=name, outcome="win")
            self.prom_trades_total.labels(strategy=name, outcome="loss")
            self.prom_signals_total.labels(strategy=name, type="entry")
            self.prom_signals_total.labels(strategy=name, type="exit")
            self.prom_signals_total.labels(strategy=name, type="rejected")

        logger.info("Registered %d strategies for Prometheus metrics", len(strategy_names))

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

    def record_entry_block(
        self,
        *,
        strategy: str = "default",
        reason: str = "unknown",
    ) -> None:
        """실행 가드 진입 차단 사유 기록."""
        if not HAS_PROMETHEUS:
            return

        normalized = str(reason or "unknown").strip().lower()
        if ":" in normalized:
            normalized = normalized.split(":", 1)[0]
        normalized = re.sub(r"[^a-z0-9_]+", "_", normalized).strip("_") or "unknown"
        self.prom_entry_blocks_total.labels(
            strategy=strategy,
            reason=normalized,
        ).inc()

    def record_rl_entry_action_probabilities(
        self,
        *,
        strategy: str,
        long_prob: float,
        short_prob: float,
        hold_prob: float,
    ) -> None:
        """RL entry 행동 확률 기록 (long/short/hold)."""
        if not HAS_PROMETHEUS:
            return

        self.prom_rl_entry_action_probability.labels(
            strategy=strategy, action="long"
        ).set(max(0.0, min(1.0, float(long_prob))))
        self.prom_rl_entry_action_probability.labels(
            strategy=strategy, action="short"
        ).set(max(0.0, min(1.0, float(short_prob))))
        self.prom_rl_entry_action_probability.labels(
            strategy=strategy, action="hold"
        ).set(max(0.0, min(1.0, float(hold_prob))))

    def record_drift_metrics(
        self,
        *,
        strategy: str,
        code: str,
        drift_metrics: "DriftMetrics",
    ) -> None:
        """RL 모델 드리프트 메트릭 기록.

        Args:
            strategy: 전략 이름 (e.g., 'rl_mppo')
            code: 거래 종목 코드 (e.g., 'A05xxx')
            drift_metrics: DriftMetrics 객체 (KL divergence, PSI, confidence 등)
        """
        if not HAS_PROMETHEUS:
            return

        try:
            # KL divergence 기록
            self.prom_rl_kl_divergence.labels(
                strategy=strategy, metric_type="kl"
            ).set(float(drift_metrics.kl_divergence))

            # PSI 기록
            self.prom_rl_kl_divergence.labels(
                strategy=strategy, metric_type="psi"
            ).set(float(drift_metrics.psi_score))

            # Confidence 분포 메트릭 기록
            self.prom_rl_observation_mean_drift.labels(strategy=strategy).set(
                float(drift_metrics.confidence_mean)
            )
            self.prom_rl_observation_std_drift.labels(strategy=strategy).set(
                float(drift_metrics.confidence_std)
            )

            logger.debug(
                f"Drift metrics recorded for {strategy}/{code}: "
                f"KL={drift_metrics.kl_divergence:.4f}, PSI={drift_metrics.psi_score:.4f}"
            )
        except Exception as e:
            logger.warning(f"Failed to record drift metrics: {e}")

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

    def record_market_data_staleness(self, staleness_seconds: float):
        """Market data snapshot staleness 기록"""
        self.metrics.market_data_staleness_seconds = staleness_seconds
        if HAS_PROMETHEUS:
            self.prom_market_data_staleness.set(staleness_seconds)
            self.prom_market_data_staleness_hist.observe(staleness_seconds)

    def record_websocket_staleness(self, feed: str, staleness_seconds: float | None) -> None:
        """WebSocket tick staleness 기록 (stock/futures)."""
        if staleness_seconds is None:
            return

        if feed == "stock":
            self.metrics.websocket_staleness_stock_seconds = staleness_seconds
        elif feed == "futures":
            self.metrics.websocket_staleness_futures_seconds = staleness_seconds
        else:
            return

        if HAS_PROMETHEUS:
            self.prom_websocket_staleness.labels(feed=feed).set(staleness_seconds)

    def record_order_queue_depth(self, depth: int):
        """Order queue depth 기록"""
        self.metrics.order_queue_depth = depth
        if HAS_PROMETHEUS:
            self.prom_order_queue_depth.set(depth)

    def record_universe_health(
        self, universe_size: int, warm_symbols: int, tracked: int
    ) -> None:
        """Universe/indicator health 기록"""
        if HAS_PROMETHEUS:
            self.prom_universe_size.set(universe_size)
            self.prom_warm_symbols.set(warm_symbols)
            self.prom_tracked_accumulators.set(tracked)

    def record_data_fetch(self, symbols_fetched: int) -> None:
        """Valid market data symbol count 기록"""
        if HAS_PROMETHEUS:
            self.prom_data_symbols_fetched.set(symbols_fetched)

    def record_signal_evaluation(self) -> None:
        """Signal evaluation cycle 기록"""
        if HAS_PROMETHEUS:
            self.prom_signal_evaluations.inc()

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

        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except OSError as e:
            logger.warning(f"Prometheus server failed to bind port {port}: {e}")

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
