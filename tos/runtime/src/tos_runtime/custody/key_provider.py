"""``FileKeyProvider`` — generation-numbered evidence-signing key files"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from tos_runtime.custody.file_custody import verify_file_mode_and_owner
from tos_runtime.custody.ports import CustodyLoadRefused

__all__ = ["FileKeyProvider"]

KEY_FILENAME_PREFIX = "evidence.key."


class FileKeyProvider:
    """A :class:`~tos_runtime.custody.ports.KeyProvider` over"""

    def __init__(
        self,
        root_dir: Path,
        *,
        expected_owner_uid: int,
        getuid: Callable[[], int] = os.getuid,
    ) -> None:
        """Bind to the directory holding ``evidence.key.<generation>`` files."""
        self._root_dir = Path(root_dir)
        self._expected_owner_uid = expected_owner_uid
        self._getuid = getuid

    def _generation_path(self, generation: int) -> Path:
        return self._root_dir / f"{KEY_FILENAME_PREFIX}{generation}"

    def _discover_generations(self) -> list[int]:
        """Every generation with a matching file on disk, sorted ascending."""
        generations: list[int] = []
        for candidate in self._root_dir.glob(f"{KEY_FILENAME_PREFIX}*"):
            suffix = candidate.name[len(KEY_FILENAME_PREFIX) :]
            if suffix.isdigit():
                generations.append(int(suffix))
        return sorted(generations)

    def generations(self) -> tuple[int, ...]:
        """Every key generation with a file on disk, sorted ascending."""
        generations: list[int] = []
        for candidate in self._root_dir.glob(f"{KEY_FILENAME_PREFIX}*"):
            suffix = candidate.name[len(KEY_FILENAME_PREFIX) :]
            if not suffix.isdigit():
                raise CustodyLoadRefused(
                    f"FileKeyProvider.generations: {candidate.name!r} under "
                    f"{self._root_dir} does not match {KEY_FILENAME_PREFIX}<digits> — "
                    "refuse (fail-closed, continuity verification cannot tolerate an "
                    "ambiguous custody root)"
                )
            generations.append(int(suffix))
        return tuple(sorted(generations))

    def current_generation(self) -> int:
        """The highest generation with a file present on disk."""
        generations = self._discover_generations()
        if not generations:
            raise CustodyLoadRefused(
                f"FileKeyProvider.current_generation: no "
                f"{KEY_FILENAME_PREFIX}<generation> files found under "
                f"{self._root_dir} — refuse (fail-closed, no implicit key)"
            )
        return generations[-1]

    def key_for(self, generation: int) -> bytes:
        """Read one specific generation's key bytes (current OR historical)."""
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
        """Return ``(current_generation, key_bytes)`` — the ``KeyProvider`` contract."""
        generation = self.current_generation()
        return generation, self.key_for(generation)
