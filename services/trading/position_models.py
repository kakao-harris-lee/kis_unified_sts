"""Position tracker model and configuration types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

MIN_MAX_POSITIONS = 1

MAX_MAX_POSITIONS = 100

MIN_PRICE = 0.0

MAX_PRICE = 100_000_000.0  # 1억원 (reasonable max for Korean stocks)


class UUIDGenerator(Protocol):
    """Protocol for UUID generation (allows injection for testing)."""

    def __call__(self) -> str:
        """Generate a unique ID."""
        ...


def default_uuid_generator() -> str:
    """Default UUID generator."""
    return str(uuid.uuid4())


@dataclass
class PositionTrackerConfig:
    """Position tracker configuration"""

    # Maximum positions allowed
    max_positions: int = 10

    # Maximum positions per symbol
    max_positions_per_symbol: int = 1

    # State transition thresholds (can be overridden per strategy)
    default_breakeven_threshold_pct: float = 0.015  # 1.5%
    default_maximize_threshold_pct: float = 0.03  # 3%
    default_fee_rate: float = 0.003  # 0.3%

    # History limits (bounded memory)
    max_events: int = 1000
    max_closed_positions: int = 100

    # Legacy database name kept for backward-compatible config construction.
    database: str = ""

    # Batch insert configuration
    batch_size: int = 50  # Number of closed positions to batch before flush
    flush_interval_seconds: float = 5.0  # Max seconds to wait before flush

    # Durable open-position snapshot mirroring. When True, the auto-flush
    # loop also mirrors all currently-open positions to the runtime ledger
    # ``position_snapshots`` table every ``flush_interval_seconds`` so that
    # open positions survive a Redis loss / container recreate and remain
    # queryable for testing. Idempotent: each position UPSERTs a single row
    # keyed by ``<asset_class>:<position_id>`` (no duplicate-row spam).
    snapshot_open_positions: bool = True

    # Asset class for this tracker instance (used to guard stock-only paths)
    asset_class: str = ""  # e.g. 'stock', 'futures'

    # Runtime ledger backend.
    runtime_ledger_backend: str = "sqlite"  # sqlite|null
    runtime_ledger_sqlite_path: str = ""

    def __post_init__(self):
        """Validate configuration values."""
        self._validate()

    def _validate(self):
        """Validate all configuration parameters."""
        if not (MIN_MAX_POSITIONS <= self.max_positions <= MAX_MAX_POSITIONS):
            raise ValueError(
                f"max_positions must be between {MIN_MAX_POSITIONS} "
                f"and {MAX_MAX_POSITIONS}, got {self.max_positions}"
            )

        if not (
            MIN_MAX_POSITIONS <= self.max_positions_per_symbol <= self.max_positions
        ):
            raise ValueError(
                f"max_positions_per_symbol must be between {MIN_MAX_POSITIONS} "
                f"and max_positions ({self.max_positions}), got {self.max_positions_per_symbol}"
            )

        if not (0 <= self.default_breakeven_threshold_pct <= 1.0):
            raise ValueError(
                f"default_breakeven_threshold_pct must be between 0 and 1.0, "
                f"got {self.default_breakeven_threshold_pct}"
            )

        if not (0 <= self.default_maximize_threshold_pct <= 1.0):
            raise ValueError(
                f"default_maximize_threshold_pct must be between 0 and 1.0, "
                f"got {self.default_maximize_threshold_pct}"
            )

        if self.default_maximize_threshold_pct <= self.default_breakeven_threshold_pct:
            raise ValueError(
                f"default_maximize_threshold_pct ({self.default_maximize_threshold_pct}) "
                f"must be greater than default_breakeven_threshold_pct "
                f"({self.default_breakeven_threshold_pct})"
            )

        if not (0 <= self.default_fee_rate <= 0.1):
            raise ValueError(
                f"default_fee_rate must be between 0 and 0.1, got {self.default_fee_rate}"
            )

        if self.max_events < 1:
            raise ValueError(f"max_events must be >= 1, got {self.max_events}")

        if self.max_closed_positions < 1:
            raise ValueError(
                f"max_closed_positions must be >= 1, got {self.max_closed_positions}"
            )

        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")

        if self.flush_interval_seconds < 0:
            raise ValueError(
                f"flush_interval_seconds must be >= 0, got {self.flush_interval_seconds}"
            )
        if self.runtime_ledger_backend not in {"sqlite", "null"}:
            raise ValueError(
                "runtime_ledger_backend must be one of sqlite|null, "
                f"got {self.runtime_ledger_backend!r}"
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PositionTrackerConfig:
        """Create config from dict with validation.

        Args:
            data: Configuration dictionary

        Returns:
            Validated PositionTrackerConfig

        Raises:
            ValueError: If validation fails
            TypeError: If type validation fails
        """
        max_positions = data.get("max_positions", 10)
        max_per_symbol = data.get("max_positions_per_symbol", 1)
        breakeven_pct = data.get("default_breakeven_threshold_pct", 0.015)
        maximize_pct = data.get("default_maximize_threshold_pct", 0.03)
        fee_rate = data.get("default_fee_rate", 0.003)
        max_events = data.get("max_events", 1000)
        max_closed = data.get("max_closed_positions", 100)
        database = data.get("database", "")
        batch_size = data.get("batch_size", 50)
        flush_interval = data.get("flush_interval_seconds", 5.0)
        asset_class = data.get("asset_class", "")
        runtime_ledger_backend = data.get("runtime_ledger_backend", "sqlite")
        runtime_ledger_sqlite_path = data.get("runtime_ledger_sqlite_path", "")

        # Type validation
        if not isinstance(max_positions, int):
            raise TypeError(f"max_positions must be int, got {type(max_positions)}")
        if not isinstance(max_per_symbol, int):
            raise TypeError(
                f"max_positions_per_symbol must be int, got {type(max_per_symbol)}"
            )
        if not isinstance(breakeven_pct, (int, float)):
            raise TypeError(
                f"default_breakeven_threshold_pct must be numeric, got {type(breakeven_pct)}"
            )
        if not isinstance(maximize_pct, (int, float)):
            raise TypeError(
                f"default_maximize_threshold_pct must be numeric, got {type(maximize_pct)}"
            )
        if not isinstance(fee_rate, (int, float)):
            raise TypeError(f"default_fee_rate must be numeric, got {type(fee_rate)}")
        if not isinstance(batch_size, int):
            raise TypeError(f"batch_size must be int, got {type(batch_size)}")
        if not isinstance(flush_interval, (int, float)):
            raise TypeError(
                f"flush_interval_seconds must be numeric, got {type(flush_interval)}"
            )

        return cls(
            max_positions=int(max_positions),
            max_positions_per_symbol=int(max_per_symbol),
            default_breakeven_threshold_pct=float(breakeven_pct),
            default_maximize_threshold_pct=float(maximize_pct),
            default_fee_rate=float(fee_rate),
            max_events=int(max_events),
            max_closed_positions=int(max_closed),
            database=str(database),
            batch_size=int(batch_size),
            flush_interval_seconds=float(flush_interval),
            asset_class=str(asset_class),
            runtime_ledger_backend=str(runtime_ledger_backend),
            runtime_ledger_sqlite_path=str(runtime_ledger_sqlite_path),
        )


@dataclass
class PositionEvent:
    """Position lifecycle event"""

    event_type: str  # "opened", "state_changed", "closed"
    position_id: str
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)
