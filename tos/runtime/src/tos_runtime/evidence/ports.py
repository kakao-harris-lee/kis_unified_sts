"""The runtime-side append port lane K's Trustworthy Time service depends on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from tos.evidence import EvidenceAppendReceipt

__all__ = ["EvidenceAppendPort"]


@runtime_checkable
class EvidenceAppendPort(Protocol):
    """The durable-append seam a runtime service evidences its state through."""

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        """Durably append one evidence record and return its commit receipt."""
        ...
