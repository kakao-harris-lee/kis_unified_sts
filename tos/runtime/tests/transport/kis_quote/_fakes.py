"""Fakes for the ``kis_quote`` adapter test suite — controllable clocks, an in-memory custody,
a recording evidence sink, and the two collaborators a REAL
:class:`~tos_runtime.time.service.TrustworthyTimeService` needs (the delay-injection tests
build one rather than faking the request anchor's own mapping).

Deliberately NOT imported from ``tests/transport/kis_mock/_fakes.py`` (even though
``InMemoryCredentialCustody``/``RecordingEvidenceSink`` are structurally identical there) — each
transport test package stays self-contained, the same convention
``tests/transport/kis_mock/_fakes.py`` itself follows (it does not import from anywhere outside
its own package either).
"""

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
    """A controllable :class:`~tos_runtime.time.sources.MonotonicSource` double — advances only
    when the test tells it to. Deliberately SEPARATE from :class:`FakeWallClock`: the two-clocks
    design (adapter.py's own module docstring) means a test that wants to exercise the token
    lifecycle's pacing independently of the wall-clock trust gate advances this one, not that
    one."""

    def __init__(self, start_ms: int = 0) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, delta_ms: int) -> None:
        self._now_ms += delta_ms


#: The label :class:`~tos_runtime.time.sources.LocalSystemClockReader` declares — reused so
#: ``tos.time.independent_reference_count`` collapses this reader exactly the way it collapses
#: the real one (one independent contribution, which is what
#: ``MIN_time_independent_reference_count: 1`` in the deployed paper profile requires).
_LOCAL_SYSTEM_CLOCK_GROUP = "LOCAL_SYSTEM_CLOCK"


class ScriptedClock:
    """One (monotonic, wall-clock) pair that advances ONLY when a test says so, and advances
    BOTH hands by the same amount.

    Both hands together is the whole point: the real
    :class:`~tos_runtime.time.service.TrustworthyTimeService` derives its observed suspension as
    ``max(0, Δwall - Δmonotonic)``, so a pair that moves in lockstep observes a suspension of
    exactly 0 — a real, measured 0, not a fabricated one — and
    :meth:`~tos_runtime.time.service.TrustworthyTimeService.wall_clock_at_monotonic` maps against
    it with no term this fixture has to guess at. Advancing one hand alone would inject a
    suspension the tests using this are not about.

    ``advance`` is called from the fake KIS server's own request thread (``set_response``'s
    ``on_request`` hook) while the test thread is blocked on the response, hence the lock.
    """

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
    """The :class:`~tos_runtime.time.sources.MonotonicSource` view of a :class:`ScriptedClock`
    — injected into BOTH the time service and the intake, exactly as compose injects one real
    source into both (the adapter's "one clock, two jobs" note)."""

    def __init__(self, clock: ScriptedClock) -> None:
        self._clock = clock

    def now_ms(self) -> int:
        return self._clock.monotonic_ms


class ScriptedReferenceReader:
    """The :class:`~tos_runtime.time.sources.ReferenceSourceReader` view of a
    :class:`ScriptedClock` — structurally what
    :class:`~tos_runtime.time.sources.LocalSystemClockReader` reports (same reachability,
    health, quality and common-mode group), reading the scripted wall hand instead of
    ``time.time_ns()``."""

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
    """A minimal :class:`~tos_runtime.evidence.ports.EvidenceAppendPort` double — the durable
    half a real :class:`~tos_runtime.time.service.TrustworthyTimeService` commits every
    snapshot through before exposing it. Records nothing a test reads back; it exists so the
    service can be driven to ``TRUSTED`` without a sqlite store."""

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
    """This process's identity, as a real :class:`~tos_runtime.time.service
    .TrustworthyTimeService` requires one (design #40 D4)."""
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
