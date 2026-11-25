"""Fakes for the ``kis_quote`` adapter test suite — controllable clocks, an in-memory custody,"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from tos.evidence import EvidenceAppendReceipt
from tos.workload import RuntimeIdentity
from tos_runtime.custody.ports import CredentialHandle, CustodyScopeNotProvisioned
from tos_runtime.time.sources import ReferenceObservation

__all__ = [
    "FakeMonotonicSource",
    "InMemoryCredentialCustody",
    "InMemoryEvidencePort",
    "RecordingEvidenceSink",
    "ScriptedClock",
    "ScriptedMonotonicSource",
    "ScriptedReferenceReader",
    "runtime_identity",
]


class InMemoryCredentialCustody:
    """A minimal :class:`~tos_runtime.custody.ports.CredentialCustody` double."""

    def __init__(self, secrets: Mapping[str, bytes]) -> None:
        self._secrets = dict(secrets)
        self.load_calls: list[str] = []

    def load(self, scope: str) -> CredentialHandle:
        self.load_calls.append(scope)
        if scope not in self._secrets:
            raise CustodyScopeNotProvisioned(
                f"scope {scope!r} not provisioned by this fake"
            )
        return CredentialHandle(
            scope=scope, principal_id=f"principal-{scope}", data=self._secrets[scope]
        )


class FakeMonotonicSource:
    """A controllable :class:`~tos_runtime.time.sources.MonotonicSource` double — advances only"""

    def __init__(self, start_ms: int = 0) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, delta_ms: int) -> None:
        self._now_ms += delta_ms


_LOCAL_SYSTEM_CLOCK_GROUP = "LOCAL_SYSTEM_CLOCK"


class ScriptedClock:
    """One (monotonic, wall-clock) pair that advances ONLY when a test says so, and advances"""

    def __init__(
        self, *, monotonic_ms: int = 5_000_000, wall_ms: int = 1_790_000_000_000
    ) -> None:
        self._lock = threading.Lock()
        self._monotonic_ms = monotonic_ms
        self._wall_ms = wall_ms

    @property
    def monotonic_ms(self) -> int:
        with self._lock:
            return self._monotonic_ms

    @property
    def wall_ms(self) -> int:
        with self._lock:
            return self._wall_ms

    def advance(self, delta_ms: int) -> None:
        """Move both hands forward by ``delta_ms``."""
        with self._lock:
            self._monotonic_ms += delta_ms
            self._wall_ms += delta_ms


class ScriptedMonotonicSource:
    """The :class:`~tos_runtime.time.sources.MonotonicSource` view of a :class:`ScriptedClock`"""

    def __init__(self, clock: ScriptedClock) -> None:
        self._clock = clock

    def now_ms(self) -> int:
        return self._clock.monotonic_ms


class ScriptedReferenceReader:
    """The :class:`~tos_runtime.time.sources.ReferenceSourceReader` view of a"""

    def __init__(self, clock: ScriptedClock) -> None:
        self._clock = clock

    def read(self) -> ReferenceObservation:
        return ReferenceObservation(
            reachable=True,
            healthy=True,
            quality=_LOCAL_SYSTEM_CLOCK_GROUP,
            common_mode_group=_LOCAL_SYSTEM_CLOCK_GROUP,
            wall_clock_unix_ms=self._clock.wall_ms,
        )


class InMemoryEvidencePort:
    """A minimal :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double — the durable"""

    def __init__(self) -> None:
        self._seq = 0

    def append(
        self, payload: Mapping[str, Any], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        del payload, kind, record_class
        self._seq += 1
        return EvidenceAppendReceipt(
            segment_id="kis-quote-test-segment",
            seq=self._seq,
            chain_digest=f"digest-{self._seq}",
            key_generation=0,
        )


def runtime_identity() -> RuntimeIdentity:
    """This process's identity, as a real :class:`~tos_runtime.time.service"""
    return RuntimeIdentity(
        cell_id="kis-quote-test-cell",
        runtime_generation=0,
        process_nonce="kis-quote-test-nonce",
        code_digest="kis-quote-test-digest",
    )


class RecordingEvidenceSink:
    """Records every evidence entry, in order, for inspection."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.records.append((kind, dict(fields)))

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [fields for k, fields in self.records if k == kind]
