"""The KIS 모의투자(paper) stock-order transport (plan
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md``, slice T1).

Re-exports the public surface of this package's three modules
(:mod:`~tos_runtime.transport.kis_mock.config`, :mod:`~tos_runtime.transport.kis_mock.client`,
:mod:`~tos_runtime.transport.kis_mock.adapter`) so a caller (T2's compose root, or a test) can
``from tos_runtime.transport.kis_mock import KisMockTransport`` directly.
"""

from __future__ import annotations

from tos_runtime.transport.kis_mock.adapter import (
    EvidenceRecorder,
    KisMockAdapterError,
    KisMockTransport,
    SealLookup,
    SendRefused,
    TokenStale,
)
from tos_runtime.transport.kis_mock.client import (
    KisMockClientError,
    KisMockConnectionError,
    KisMockHttpClient,
    KisMockTimeoutError,
    RawResponse,
)
from tos_runtime.transport.kis_mock.config import (
    DYNAMIC_FIELD_SOURCES,
    KisMockTransportConfig,
    KisMockTransportConfigError,
    load_kis_mock_transport_config,
)

__all__ = [
    "DYNAMIC_FIELD_SOURCES",
    "EvidenceRecorder",
    "KisMockAdapterError",
    "KisMockClientError",
    "KisMockConnectionError",
    "KisMockHttpClient",
    "KisMockTimeoutError",
    "KisMockTransport",
    "KisMockTransportConfig",
    "KisMockTransportConfigError",
    "RawResponse",
    "SealLookup",
    "SendRefused",
    "TokenStale",
    "load_kis_mock_transport_config",
]
