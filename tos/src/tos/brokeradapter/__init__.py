"""Broker Adapter transport boundary + the synthetic paper transport (Phase 1, provisional)."""

from __future__ import annotations

from tos.brokeradapter.protocol import OutboundSendRequest, Transport
from tos.brokeradapter.synthetic import (
    FILL_CONTEXT,
    NON_FILL_DECLARABLE_KINDS,
    SyntheticFillPolicy,
    SyntheticPaperTransport,
    synthetic_transport_nature_fields,
)

__all__ = [
    "FILL_CONTEXT",
    "NON_FILL_DECLARABLE_KINDS",
    "OutboundSendRequest",
    "SyntheticFillPolicy",
    "SyntheticPaperTransport",
    "Transport",
    "synthetic_transport_nature_fields",
]
