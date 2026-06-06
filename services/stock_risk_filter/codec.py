"""Stock candidate codec — inverse of services.stock_strategy.candidate.

The 8 RiskFilterLayer filters read only ``signal.symbol`` and
``signal.generated_at`` (see shared/risk/filters/*.py), so a minimal duck-typed
object suffices. The futures Signal cannot be reused: its __post_init__ forbids
stop_loss <= 0 and the stock candidate has no stop/target.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class StockRiskSignal:
    """Minimal stock signal consumed by RiskFilterLayer + carried to final.

    ``symbol`` (== code) and ``generated_at`` are what the filters read; the
    remaining fields are carried through for the final-stream re-emit and for
    M4-O execution.
    """

    symbol: str
    code: str
    name: str
    strategy: str
    direction: str
    price: float
    quantity: int
    confidence: float
    generated_at: datetime | None


def stock_signal_from_stream_fields(
    fields: dict[bytes, bytes],
) -> tuple[str, StockRiskSignal]:
    """Parse Redis stream fields (M4-P candidate schema) into a StockRiskSignal."""

    def _s(key: str) -> str:
        raw = fields.get(key.encode(), b"")
        return (
            raw.decode("utf-8", errors="replace")
            if isinstance(raw, bytes)
            else str(raw)
        )

    def _ms_to_dt(ms: str) -> datetime | None:
        if not ms:
            return None
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC)

    code = _s("code")
    if not code:
        raise ValueError("stock candidate missing required field 'code'")

    direction = _s("direction") or "long"
    if direction not in {"long", "short"}:
        raise ValueError(f"invalid stock candidate direction {direction!r}")

    signal = StockRiskSignal(
        symbol=code,
        code=code,
        name=_s("name"),
        strategy=_s("strategy"),
        direction=direction,
        price=float(_s("price") or 0.0),
        # int(float(...)) tolerates decimal-strings like "10.0"; do not
        # "simplify" to int(...), which raises on a fractional string.
        quantity=int(float(_s("quantity") or 0)),
        confidence=float(_s("confidence") or 0.0),
        generated_at=_ms_to_dt(_s("generated_at_ms")),
    )
    return _s("signal_id"), signal


def decode_fields(fields: dict[bytes, bytes]) -> dict[str, str]:
    """Decode a raw Redis field dict to ``{str: str}`` for re-emit."""
    out: dict[str, str] = {}
    for k, v in fields.items():
        key = k.decode("utf-8", errors="replace") if isinstance(k, bytes) else str(k)
        val = v.decode("utf-8", errors="replace") if isinstance(v, bytes) else str(v)
        out[key] = val
    return out
