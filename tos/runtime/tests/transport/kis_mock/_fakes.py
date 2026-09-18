"""Shared fakes for the adapter test suite: an in-memory custody, a controllable monotonic
clock, and a recording evidence sink."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tos.egressgw import SendSeal
from tos_runtime.custody.ports import CredentialHandle, CustodyScopeNotProvisioned

__all__ = [
    "FakeMonotonicSource",
    "InMemoryCredentialCustody",
    "RecordingEvidenceSink",
    "make_seal_lookup",
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
    """A controllable monotonic clock — advances only when the test tells it to."""

    def __init__(self, start_ms: int = 0) -> None:
        self._now_ms = start_ms

    def now_ms(self) -> int:
        return self._now_ms

    def advance(self, delta_ms: int) -> None:
        self._now_ms += delta_ms


class RecordingEvidenceSink:
    """Records every evidence entry, in order, for inspection."""

    def __init__(self) -> None:
        self.records: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.records.append((kind, dict(fields)))

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [fields for k, fields in self.records if k == kind]


class _SealLookup:
    """A ``SealLookup`` double backed by a plain mapping.

    A bare closure has type ``Callable[[str], SendSeal | None]``, which mypy will not accept
    where a ``SealLookup`` (a callback ``Protocol`` with a named ``attempt_id`` parameter) is
    expected — ``Callable`` erases parameter names, and ``SealLookup.__call__`` is not
    positional-only. A small class whose ``__call__`` matches the protocol's signature exactly
    satisfies it structurally.
    """

    def __init__(self, seal_by_attempt_id: Mapping[str, SendSeal]) -> None:
        self._seal_by_attempt_id = seal_by_attempt_id

    def __call__(self, attempt_id: str) -> SendSeal | None:
        return self._seal_by_attempt_id.get(attempt_id)


def make_seal_lookup(seal_by_attempt_id: Mapping[str, SendSeal]) -> _SealLookup:
    return _SealLookup(seal_by_attempt_id)
