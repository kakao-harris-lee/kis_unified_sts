"""Shared fixtures for the ``tos_runtime.nontrade`` test suite (Phase 5 W5 plan
§2 decision 6, lane f3). Only this package's own tests use these — no other
lane's ``conftest.py`` is touched.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest
from tos.evidence import EvidenceAppendReceipt

from .fixtures.synthetic_observations import REQUIRED_LEGS_BY_CLASS

__all__ = ["FakeEvidenceRecorder"]


class FakeEvidenceRecorder:
    """A :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double — an
    in-memory list, never a real durable store (this suite is hermetic). Each
    ``append()`` returns a real :class:`~tos.evidence.EvidenceAppendReceipt` with
    a monotonically increasing ``seq``, exactly like a real store's contract
    (module docstring "a receipt proving durable commit").
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, object]]] = []
        self._seq = 0

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self._seq += 1
        self.calls.append((kind, record_class, dict(payload)))
        return EvidenceAppendReceipt(seq=self._seq)

    def kinds(self) -> list[str]:
        """The recorded evidence kinds, in append order."""
        return [kind for kind, _record_class, _payload in self.calls]


@pytest.fixture
def evidence_recorder() -> FakeEvidenceRecorder:
    return FakeEvidenceRecorder()


@pytest.fixture
def required_legs_by_class() -> Mapping:
    """The event-class -> applicable-leg policy the fixtures were built against
    (:data:`tests.nontrade.fixtures.synthetic_observations.REQUIRED_LEGS_BY_CLASS`)
    — a plain dict copy so a test mutating it cannot affect another test."""
    return dict(REQUIRED_LEGS_BY_CLASS)


@pytest.fixture
def fresh_time_provider():
    """A time-freshness provider reporting the kernel's own ``FRESH`` token."""
    return lambda: "FRESH"


@pytest.fixture
def admissible_provider():
    """A venue-admissibility provider reporting ``ADMISSIBLE`` for every route
    key — used by the fixtures this suite expects to reach a non-trapped
    disposition (everything except the LIFECYCLE expiry fixture, which
    deliberately supplies no provider — see its own docstring)."""
    return lambda _route_key: "ADMISSIBLE"
