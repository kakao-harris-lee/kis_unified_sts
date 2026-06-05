"""Compatibility no-op writer for removed durable signal mirror."""

from __future__ import annotations

from typing import Any

from shared.decision.signal import Signal
from shared.risk.layer import LayerResult


class SignalsAllWriter:
    """Accepts signal rows but no longer writes to an external DB."""

    def __init__(
        self,
        archive_client: Any | None = None,
        *,
        batch_size: int = 50,
        **legacy_kwargs: Any,
    ):
        _ = archive_client, batch_size, legacy_kwargs

    async def enqueue(
        self,
        signal: Signal,
        layer_result: LayerResult,
        *,
        executed: bool = False,
        signal_id: str | None = None,
    ) -> None:
        """Compatibility no-op."""
        _ = signal, layer_result, executed, signal_id
        return None

    async def flush(self) -> None:
        """Compatibility no-op."""
        return None
