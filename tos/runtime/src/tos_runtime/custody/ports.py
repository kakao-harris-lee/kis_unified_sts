"""Custody ports: the seams :mod:`tos_runtime.custody`'s implementations satisfy
(design #40 D4, slice plan §2 "레인 N" item 1).

Design #40 D4.1 (``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`` line 110): "커널에 ``tos.liveauth``... 가 아니라 **런타임에**
``tos_runtime.custody.CredentialCustody`` Protocol(커널은 자격증명 개념을 모른다
— 커널은 principal 문자열과 route inventory 만 본다, ``egressgw/records.py``
``TransportNature``)." This module is the whole of that seam: the kernel never
imports anything from this package, and nothing here imports the kernel's
``egressgw``/``authority`` packages either — custody is a runtime-only concept,
one layer below whatever eventually consumes a loaded credential.

Two Protocols, one concrete value type, and the shared exception hierarchy:

* :class:`CredentialCustody` — ``load(scope) -> CredentialHandle``. Phase 2's
  only implementation is :class:`~tos_runtime.custody.file_custody.FileCustody`.
* :class:`KeyProvider` — mirrors
  :class:`tos_runtime.evidence.store.KeyProvider` **structurally** (same
  ``current() -> tuple[int, bytes]`` signature) rather than importing it, so
  this package stays independently importable without pulling in the evidence
  store module as a hard dependency (slice plan §3 "레인 간·후속 계약": "N 은
  슬라이스 #1 ``store.KeyProvider``(있으면) 시그니처만 소비" — signature only,
  not the type itself). Because both are ``@runtime_checkable`` structural
  Protocols with an identical method signature, any object satisfying one
  satisfies the other — :class:`~tos_runtime.custody.key_provider.FileKeyProvider`
  is accepted anywhere either Protocol is expected, including directly as the
  ``key_provider=`` argument of
  :class:`tos_runtime.evidence.store.SqliteEvidenceStore` (verified by this
  package's own smoke test).
* :class:`CredentialHandle` — the loaded secret's lifetime container. A
  context manager; its backing buffer is a mutable ``bytearray`` zeroed on
  :meth:`~CredentialHandle.close` (or context-manager exit), and neither
  ``__repr__`` nor ``__str__`` ever renders the secret bytes.

Firewall: stdlib only (``collections.abc``, ``typing``) — no ``tos``/``tos_runtime``
sibling import, so this module never risks an import cycle with anything it is
itself a seam for.
"""

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
    """Base class for every fail-closed custody refusal.

    Every subclass below is a REFUSAL, never a partial/best-effort success —
    consistent with this codebase's evidence-store convention
    (:class:`tos_runtime.evidence.store.EvidenceCorruption`,
    :class:`~tos_runtime.evidence.store.InjectedCrash`): a fault contract is
    modelled as "raises, or doesn't happen", never a returned sentinel a
    caller might forget to check.
    """


class CustodyManifestError(CustodyError):
    """The ``custody.manifest.yaml`` file is missing, unreadable, or malformed.

    Raised only at :class:`~tos_runtime.custody.file_custody.FileCustody`
    construction time (design #40 slice plan §2's fault-contract ordering:
    "manifest exists and parses" is the FIRST pre-load check, and — because a
    manifest cannot change shape between two ``load()`` calls without a
    process restart — it is checked exactly once, at construction, not
    re-parsed on every subsequent ``load()``).
    """


class CustodyScopeNotProvisioned(CustodyError):
    """The requested scope is not one Phase 2 provisions.

    Design #40 D4.1 line 111: "Phase 2 는 ``order`` 스코프 파일을 로드하는 코드
    경로를 두지 않는다(Phase 4 KIS MOCK 주식 주문 때 · 선물 REAL 은 영구
    부재 — 루트 CLAUDE.md 비협상)." Any scope other than the three Phase 2
    enumerates (``read.principal``, ``evidence.key``, ``replay.params`` —
    :data:`tos_runtime.custody.file_custody.PROVISIONED_SCOPES`) raises this,
    ``order.*`` included — there is no partial/degraded handling for an
    unprovisioned scope, only refusal.
    """


class CustodyLoadRefused(CustodyError):
    """A provisioned scope's load-time preconditions were not met.

    Covers every per-``load()`` fail-closed gate after the scope-enumeration
    check: the manifest not configuring this scope, the backing file being
    absent, its mode not being exactly ``0o600``, its owner (or the
    running process's own uid) not matching the expected owner, an
    environment-label mismatch against the custody manifest (design #40 D4.1
    line 113 / ADR-002-013 :498), or a pinned digest not matching.
    """


@runtime_checkable
class KeyProvider(Protocol):
    """Structural mirror of :class:`tos_runtime.evidence.store.KeyProvider`.

    Consulted exactly once, at a durable store's construction, for the
    initial ``(key_generation, key_bytes)`` pair — ongoing rotation is the
    store's own ``rotate(new_generation, new_key)`` method, never a second
    call to this Protocol (see
    :class:`tos_runtime.evidence.store.KeyProvider`'s own docstring, which
    this mirrors verbatim to keep the two seams behaviourally identical
    without a hard import edge between the two packages).
    """

    def current(self) -> tuple[int, bytes]:
        """Return ``(key_generation, key_bytes)`` for the initial signing key."""
        ...


@runtime_checkable
class CredentialCustody(Protocol):
    """The seam a scoped-credential source implements (design #40 D4.1).

    ``load`` either returns a :class:`CredentialHandle` for a provisioned,
    precondition-satisfying scope, or raises one of this module's
    :class:`CustodyError` subclasses — there is no third, degraded outcome.
    """

    def load(self, scope: str) -> CredentialHandle:
        """Load the credential bound to ``scope``.

        Args:
            scope: One of the scopes this implementation provisions (Phase 2:
                ``read.principal``, ``evidence.key``, ``replay.params`` —
                never ``order.*``, see :class:`CustodyScopeNotProvisioned`).

        Returns:
            A :class:`CredentialHandle` wrapping the loaded secret bytes.

        Raises:
            CustodyScopeNotProvisioned: ``scope`` is not provisioned.
            CustodyLoadRefused: A provisioned scope's load-time precondition
                failed (missing file, wrong mode, wrong owner, digest
                mismatch, ...).
        """
        ...


class CredentialHandle:
    """A loaded credential's lifetime container — use as a context manager.

    The secret bytes live in a mutable ``bytearray`` (never a ``bytes``
    object, which Python cannot zero in place) so :meth:`close` can
    overwrite every byte with ``0`` once the caller is done. Neither
    ``__repr__`` nor ``__str__`` renders the secret — only ``scope``,
    ``principal_id``, and whether the handle is closed, so an accidental
    ``print(handle)`` or an uncaught-exception traceback that stringifies a
    local variable never leaks the secret bytes.

    **Zeroing happens ONLY through :meth:`close` (or the context-manager
    ``__exit__`` that calls it) — there is deliberately no ``__del__``.** A
    caller that never enters a ``with credential_handle:`` block and never
    calls :meth:`close` explicitly gets a buffer that is NEVER zeroed by
    this class; CPython finalizer timing (when, or whether, ``__del__``
    runs — e.g. never, under a reference cycle, or at interpreter shutdown
    in an unspecified order) is not a guarantee this class is willing to
    lean on for a security property, so it provides no best-effort
    finalizer at all rather than one that sometimes silently fails to run.
    :meth:`value` raises :class:`CustodyError` once the handle is closed,
    rather than returning stale all-zero bytes that could be mistaken for a
    real (if degenerate) secret.

    **Single-copy ownership (2026-09-08 independent-review LOW-2).**
    :meth:`__init__` takes OWNERSHIP of a ``bytearray`` passed as ``data``
    (no defensive copy) specifically so that a caller which itself read the
    secret into a ``bytearray`` (never into an immutable ``bytes`` object,
    which this class could never zero regardless of what it does
    internally — see :meth:`__init__`'s own docstring) hands over the ONE
    and ONLY copy of the secret that will ever exist, and closing this
    handle is the end of its lifetime in memory. A caller that instead
    passes an immutable ``bytes`` literal (this codebase's own tests do,
    for convenience) gets a defensive COPY into a fresh ``bytearray`` — the
    original ``bytes`` object stays unzeroable and outside this class's
    control either way, so copying costs nothing additional there.
    """

    __slots__ = ("scope", "principal_id", "_buffer", "_closed")

    def __init__(
        self, *, scope: str, principal_id: str, data: bytes | bytearray
    ) -> None:
        """Wrap ``data`` for ``scope``/``principal_id`` in a zeroable buffer.

        Args:
            scope: The scope this credential was loaded for.
            principal_id: The distinct principal string bound to ``scope``
                (ADR-002-013 :267-269 — every scope has its own principal,
                never shared across scopes).
            data: The raw secret bytes. If already a ``bytearray``, this
                handle takes OWNERSHIP of that exact object (no copy) — the
                caller must not retain or reuse its own reference to it
                afterward, since mutating or zeroing it outside this class
                would silently corrupt or erase the handle's own view (see
                the class docstring's "single-copy ownership" note). If an
                immutable ``bytes`` object, it is copied into a fresh
                ``bytearray`` instead (there is no ownership to take — Python
                cannot zero a ``bytes`` object in place either way, so the
                original stays unzeroable regardless of what this class
                does).
        """
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
        """Return a fresh ``bytes`` copy of the secret.

        Raises:
            CustodyError: The handle was already closed (its buffer is
                zeroed) — a caller reading a closed handle would silently
                observe all-zero bytes and mistake that for a real secret,
                which this raises loudly against instead.
        """
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


#: Re-exported only for type-hint convenience in sibling modules — not part of
#: this module's own runtime behaviour.
GetUid = Callable[[], int]
