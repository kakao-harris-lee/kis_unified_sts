"""Fakes for the ``kis_quote`` adapter test suite — a controllable monotonic clock, an
in-memory custody, a recording evidence sink, and the two collaborators a REAL
:class:`~tos_runtime.time.service.TrustworthyTimeService` needs (the delay-injection tests
build one rather than faking the request anchor's own mapping).

Deliberately NOT imported from ``tests/transport/kis_mock/_fakes.py`` (even though
``InMemoryCredentialCustody``/``RecordingEvidenceSink`` are structurally identical there) — each
transport test package stays self-contained, the same convention
``tests/transport/kis_mock/_fakes.py`` itself follows (it does not import from anywhere outside
its own package either).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tos.evidence import EvidenceAppendReceipt
from tos.workload import RuntimeIdentity
from tos_runtime.custody.ports import CredentialHandle, CustodyScopeNotProvisioned

__all__ = [
    "FakeMonotonicSource",
    "InMemoryCredentialCustody",
    "InMemoryEvidencePort",
    "RecordingEvidenceSink",
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
