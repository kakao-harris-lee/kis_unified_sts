"""Risk 관리 모듈

Cross-asset 리스크 관리 프레임워크.

Usage:
    from shared.risk import RiskManager, RiskConfig, RiskState

    config = RiskConfig(...)
    manager = RiskManager(config)
    await manager.check_entry_allowed(symbol, "stock", quantity, price)
"""

from shared.risk.manager import RiskManager
from shared.risk.config import (
    RiskConfig,
    DrawdownThresholds,
    DrawdownConfig,
    AssetLimits,
    PositionSizingConfig,
    MonitoringConfig,
    NotificationConfig,
    RedisConfig,
)
from shared.risk.models import (
    RiskState,
    DrawdownLevel,
    BlockReason,
    AssetExposure,
    PortfolioMetrics,
)

__all__ = [
    # Manager
    "RiskManager",
    # Config
    "RiskConfig",
    "DrawdownThresholds",
    "DrawdownConfig",
    "AssetLimits",
    "PositionSizingConfig",
    "MonitoringConfig",
    "NotificationConfig",
    "RedisConfig",
    # Models
    "RiskState",
    "DrawdownLevel",
    "BlockReason",
    "AssetExposure",
    "PortfolioMetrics",
]
