"""``FileKeyProvider`` — generation-numbered evidence-signing key files
(design #40 D4.1 "키 회전", slice plan §2 "레인 N" item 3).

Realizes design #40 D4.1 line 112's rotation discipline: "새 ``key_generation``
은 RCL/evidence 양쪽에 «회전 커밋» 항목을 남기고 그 seq 부터만 유효 · 이전
키는 **회전 커밋과 동시에** 서명 무효(검증에는 유효 — 과거 체인 검증용) ·
겹침 0(ADR-002-013 :401-418 deny-first)."

**This module does not itself rotate anything.** Rotation, as
:class:`tos_runtime.evidence.store.SqliteEvidenceStore.rotate`'s own
docstring makes explicit, is the store's ongoing mechanism — a
:class:`~tos_runtime.custody.ports.KeyProvider` is "consulted exactly once, at
construction" for the INITIAL key only. The rotation ORDER this module's
callers must follow (never enforced here, since this module cannot see the
store) is: (1) place the new generation's key file
(``evidence.key.<new_generation>``) on disk FIRST — this is what makes
:meth:`FileKeyProvider.key_for` able to read it at all — (2) only THEN call
``store.rotate(new_generation, new_key_bytes)`` with those same bytes. Doing
it in the other order would let the store commit a rotation-commit entry
under a key that is not yet durably readable back from this provider — a gap
this module's own file-first / rotate-second contract closes by construction
of the CALLING sequence, not by anything enforced inside this class.

Old-generation files are retained and remain READABLE (:meth:`key_for`) —
never deleted by this module — because :meth:`SqliteEvidenceStore.verify`
needs every historical key to re-derive a chain spanning more than one
generation (module docstring's own "옛 세대 키는 검증용으로 읽기만").

Firewall: stdlib (``os``, ``pathlib``) + ``tos_runtime.custody`` only (R1
allowlist) — no ``tos`` kernel import at all (this module's whole surface is
a file-scanning implementation of a Protocol, nothing kernel-facing).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused

__all__ = ["FileKeyProvider"]

#: Generation-numbered key files are named ``evidence.key.<generation>`` —
#: e.g. ``evidence.key.1``, ``evidence.key.2`` — directly under the
#: provider's own directory (design #40 D4.1 line 112, slice plan §2 item 3).
KEY_FILENAME_PREFIX = "evidence.key."


class FileKeyProvider:
    """A :class:`~tos_runtime.custody.ports.KeyProvider` over
    ``evidence.key.<generation>`` files (design #40 D4.1).

    Structurally satisfies BOTH
    :class:`tos_runtime.custody.ports.KeyProvider` and
    :class:`tos_runtime.evidence.store.KeyProvider` (identical
    ``current() -> tuple[int, bytes]`` signature on each) — this class can be
    passed directly as the ``key_provider=`` argument of
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` without any
    adapter (this package's own smoke test constructs exactly that).
    """

    def __init__(
        self,
        root_dir: Path,
        *,
        expected_owner_uid: int,
        getuid: Callable[[], int] = os.getuid,
    ) -> None:
        """Bind to the directory holding ``evidence.key.<generation>`` files.

        Args:
            root_dir: The directory to scan for generation-numbered key
                files.
            expected_owner_uid: The uid every key file (and the calling
                process itself) must be owned by/run as — see
                :func:`tos_runtime.custody.file_custody.verify_file_mode_and_owner`,
                reused here unchanged so both custody modules apply the
                identical fail-closed mode+owner gate.
            getuid: An ``os.getuid``-shaped callable, injectable for tests.
        """
        self._root_dir = Path(root_dir)
        self._expected_owner_uid = expected_owner_uid
        self._getuid = getuid

    def _generation_path(self, generation: int) -> Path:
        return self._root_dir / f"{KEY_FILENAME_PREFIX}{generation}"

    def _discover_generations(self) -> list[int]:
        """Every generation with a matching file on disk, sorted ascending.

        Only a purely-digit suffix after :data:`KEY_FILENAME_PREFIX` counts
        as a generation file — anything else matching the glob (e.g. a
        stray ``evidence.key.bak``) is silently not a generation, not an
        error; this directory is not assumed to hold only key files.
        """
        generations: list[int] = []
        for candidate in self._root_dir.glob(f"{KEY_FILENAME_PREFIX}*"):
            suffix = candidate.name[len(KEY_FILENAME_PREFIX) :]
            if suffix.isdigit():
                generations.append(int(suffix))
        return sorted(generations)

    def current_generation(self) -> int:
        """The highest generation with a file present on disk.

        Raises:
            CustodyLoadRefused: No ``evidence.key.<generation>`` file exists
                under ``root_dir`` — fail-closed; there is no implicit
                "generation 0" or any other default.
        """
        generations = self._discover_generations()
        if not generations:
            raise CustodyLoadRefused(
                f"FileKeyProvider.current_generation: no "
                f"{KEY_FILENAME_PREFIX}<generation> files found under "
                f"{self._root_dir} — refuse (fail-closed, no implicit key)"
            )
        return generations[-1]

    def key_for(self, generation: int) -> bytes:
        """Read one specific generation's key bytes (current OR historical).

        Applies the same mode/owner gate as
        :meth:`~tos_runtime.custody.file_custody.FileCustody.load`
        (:func:`~tos_runtime.custody.file_custody.verify_file_mode_and_owner`)
        — a key file is exactly as sensitive as any other custody-scoped
        secret and gets the identical fail-closed treatment.

        Args:
            generation: The key generation to read.

        Returns:
            The raw key bytes for ``generation``.

        Raises:
            CustodyLoadRefused: The generation's file does not exist, or
                fails the mode/owner gate.
        """
        path = self._generation_path(generation)
        if not path.is_file():
            raise CustodyLoadRefused(
                f"FileKeyProvider.key_for: key generation {generation} not "
                f"found at {path} — refuse"
            )
        verify_file_mode_and_owner(
            path, expected_owner_uid=self._expected_owner_uid, getuid=self._getuid
        )
        return path.read_bytes()

    def current(self) -> tuple[int, bytes]:
        """Return ``(current_generation, key_bytes)`` — the ``KeyProvider`` contract.

        Consulted exactly once, at a durable store's construction (see the
        module docstring's rotation-order note for why this method is never
        called again as part of an ongoing rotation).
        """
        generation = self.current_generation()
        return generation, self.key_for(generation)
