"""Custody ports: the seams :mod:`tos_runtime.custody`'s implementations satisfy"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

__all__ = [
    "CredentialCustody",
    "CredentialHandle",
    "CustodyError",
    "CustodyLoadRefused",
    "CustodyManifestError",
    "CustodyScopeNotProvisioned",
    "KeyProvider",
]


class CustodyError(RuntimeError):
    """Base class for every fail-closed custody refusal."""


class CustodyManifestError(CustodyError):
    """The ``custody.manifest.yaml`` file is missing, unreadable, or malformed."""


class CustodyScopeNotProvisioned(CustodyError):
    """The requested scope is not one Phase 2 provisions."""


class CustodyLoadRefused(CustodyError):
    """A provisioned scope's load-time preconditions were not met."""


@runtime_checkable
class KeyProvider(Protocol):
    """Structural mirror of :class:`tos_runtime.evidence.store.KeyProvider`."""

    def current(self) -> tuple[int, bytes]:
        """Return ``(key_generation, key_bytes)`` for the initial signing key."""
        ...


@runtime_checkable
class CredentialCustody(Protocol):
    """The seam a scoped-credential source implements (design #40 D4.1)."""

    def load(self, scope: str) -> CredentialHandle:
        """Load the credential bound to ``scope``."""
        ...


class CredentialHandle:
    """A loaded credential's lifetime container — use as a context manager."""

    __slots__ = ("scope", "principal_id", "_buffer", "_closed")

    def __init__(
        self, *, scope: str, principal_id: str, data: bytes | bytearray
    ) -> None:
        """Wrap ``data`` for ``scope``/``principal_id`` in a zeroable buffer."""
        self.scope = scope
        self.principal_id = principal_id
        self._buffer = data if isinstance(data, bytearray) else bytearray(data)
        self._closed = False

    def __enter__(self) -> CredentialHandle:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    @property
    def is_closed(self) -> bool:
        """Whether :meth:`close` has already zeroed this handle's buffer."""
        return self._closed

    def value(self) -> bytes:
        """Return a fresh ``bytes`` copy of the secret."""
        if self._closed:
            raise CustodyError(
                "CredentialHandle.value(): handle is closed — its buffer was "
                "already zeroed; the caller must not hold a reference past "
                "its own `with credential_handle:` block"
            )
        return bytes(self._buffer)

    def close(self) -> None:
        """Overwrite every byte of the internal buffer with ``0``. Idempotent."""
        if self._closed:
            return
        for index in range(len(self._buffer)):
            self._buffer[index] = 0
        self._closed = True

    def __repr__(self) -> str:
        return (
            f"CredentialHandle(scope={self.scope!r}, "
            f"principal_id={self.principal_id!r}, closed={self._closed})"
        )

    __str__ = __repr__


GetUid = Callable[[], int]
