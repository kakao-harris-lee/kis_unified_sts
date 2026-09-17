"""The KIS 모의투자 quote intake (TOS tick-source wave, W2 lane, plan
``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`` §4 W2).

Re-exports the public surface of this package's two modules
(:mod:`~tos_runtime.transport.kis_quote.config`, :mod:`~tos_runtime.transport.kis_quote.adapter`)
so a caller (compose wiring, or a test) can
``from tos_runtime.transport.kis_quote import KisQuoteObservationIntake`` directly.
"""

from __future__ import annotations

from tos_runtime.transport.kis_quote.adapter import (
    KisQuoteAdapterError,
    KisQuoteMalformedResponse,
    KisQuoteObservationIntake,
    KisQuoteRejected,
    KisQuoteWallClockUntrusted,
    TokenStale,
    WallClockSource,
    build_quote_client,
)
from tos_runtime.transport.kis_quote.config import (
    KisQuoteTransportConfig,
    KisQuoteTransportConfigError,
    load_kis_quote_transport_config,
)

__all__ = [
    "KisQuoteAdapterError",
    "KisQuoteMalformedResponse",
    "KisQuoteObservationIntake",
    "KisQuoteRejected",
    "KisQuoteTransportConfig",
    "KisQuoteTransportConfigError",
    "KisQuoteWallClockUntrusted",
    "TokenStale",
    "WallClockSource",
    "build_quote_client",
    "load_kis_quote_transport_config",
]
