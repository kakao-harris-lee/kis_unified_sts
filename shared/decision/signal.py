"""Signal dataclass with stream serialization for the decision engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Signal:
    """Immutable trading signal produced by a Setup and passed through the RiskFilterLayer.

    Fields
    ------
    setup_type: str
        Name of the Setup that generated this signal (e.g. "A_gap_reversion").
    direction: str
        Trade direction — must be one of ``{"long", "short"}``.
    symbol: str
        Instrument symbol (e.g. "A05603").
    entry_price: float
        Target entry price in points.
    stop_loss: float
        Hard stop-loss price in points.
    take_profit: float
        Take-profit target price in points.
    confidence: float
        Model confidence score in ``[0.0, 1.0]``.
    reason_tags: list[str]
        Human-readable tags explaining the signal (e.g. ["sp500_gap_+1.20%"]).
    valid_until: datetime
        Expiry time after which the signal must be discarded (timezone-aware).
    generated_at: datetime
        When the signal was created (timezone-aware).
    """

    setup_type: str
    direction: str
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reason_tags: tuple[str, ...] = field(default_factory=tuple)
    valid_until: datetime | None = None
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.direction not in {"long", "short"}:
            raise ValueError(
                f"direction must be 'long' or 'short', got {self.direction!r}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        if self.entry_price <= 0:
            raise ValueError(f"entry_price must be > 0, got {self.entry_price}")
        if self.stop_loss <= 0:
            raise ValueError(f"stop_loss must be > 0, got {self.stop_loss}")

    # Support construction with a plain list for reason_tags convenience.
    def __init__(
        self,
        setup_type: str,
        direction: str,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
        reason_tags: list[str] | tuple[str, ...] | None = None,
        valid_until: datetime | None = None,
        generated_at: datetime | None = None,
    ) -> None:
        object.__setattr__(self, "setup_type", setup_type)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "entry_price", float(entry_price))
        object.__setattr__(self, "stop_loss", float(stop_loss))
        object.__setattr__(self, "take_profit", float(take_profit))
        object.__setattr__(self, "confidence", float(confidence))
        object.__setattr__(
            self,
            "reason_tags",
            tuple(reason_tags) if reason_tags is not None else (),
        )
        object.__setattr__(self, "valid_until", valid_until)
        object.__setattr__(self, "generated_at", generated_at)
        self.__post_init__()

    # ------------------------------------------------------------------
    # Stream serialization
    # ------------------------------------------------------------------

    def to_stream_dict(self) -> dict[str, str]:
        """Return a flat ``dict[str, str]`` suitable for Redis XADD / stream publish.

        Numeric fields are stringified; datetimes are epoch milliseconds (UTC,
        tz-stripped via ``.timestamp() * 1000``); ``reason_tags`` is JSON-encoded.
        """
        generated_ms = (
            str(int(self.generated_at.timestamp() * 1000))
            if self.generated_at is not None
            else ""
        )
        valid_ms = (
            str(int(self.valid_until.timestamp() * 1000))
            if self.valid_until is not None
            else ""
        )
        return {
            "setup_type": self.setup_type,
            "direction": self.direction,
            "symbol": self.symbol,
            "entry_price": str(self.entry_price),
            "stop_loss": str(self.stop_loss),
            "take_profit": str(self.take_profit),
            "confidence": str(self.confidence),
            "generated_at_ms": generated_ms,
            "valid_until_ms": valid_ms,
            "reason_tags_json": json.dumps(list(self.reason_tags)),
        }

    # ------------------------------------------------------------------
    # Analytics helpers
    # ------------------------------------------------------------------

    def risk_reward_ratio(self) -> float:
        """Return the reward-to-risk ratio.

        ``abs(take_profit - entry_price) / abs(entry_price - stop_loss)``
        """
        risk = abs(self.entry_price - self.stop_loss)
        if risk == 0:
            raise ValueError("entry_price equals stop_loss — risk is zero")
        return abs(self.take_profit - self.entry_price) / risk
