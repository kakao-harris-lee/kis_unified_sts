"""Fakes for the ``kis_quote`` adapter test suite — a controllable wall clock, an in-memory
custody, and a recording evidence sink.

Deliberately NOT imported from ``tests/transport/kis_mock/_fakes.py`` (even though
``InMemoryCredentialCustody``/``RecordingEvidenceSink`` are structurally identical there) — each
transport test package stays self-contained, the same convention
``tests/transport/kis_mock/_fakes.py`` itself follows (it does not import from anywhere outside
its own package either).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tos_runtime.custody.ports import CredentialHandle, CustodyScopeNotProvisioned

__all__ = [
    "FakeMonotonicSource",
    "FakeWallClock",
    "InMemoryCredentialCustody",
    "RecordingEvidenceSink",
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


class FakeWallClock:
    """A controllable :class:`~tos_runtime.transport.kis_quote.adapter.WallClockSource` double.

    ``None`` means "not yet TRUSTED" (the real service's own honest answer before it reaches
    that health state) — a test sets it explicitly to exercise
    :class:`~tos_runtime.transport.kis_quote.adapter.KisQuoteWallClockUntrusted`.
    """

    def __init__(self, start_ms: int | None = 1_700_000_000_000) -> None:
        self._now_ms = start_ms

    def wall_clock_now(self) -> int | None:
        return self._now_ms

    def set(self, value_ms: int | None) -> None:
        self._now_ms = value_ms

    def advance(self, delta_ms: int) -> None:
        assert self._now_ms is not None
        self._now_ms += delta_ms


class RecordingEvidenceSink:
    """Records every evidence entry, in order, for inspection."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.records.append((kind, dict(fields)))

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [fields for k, fields in self.records if k == kind]
