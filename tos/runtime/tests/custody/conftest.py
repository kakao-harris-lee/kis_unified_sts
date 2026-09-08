"""Shared fixtures for ``tos_runtime.custody`` tests (design #40 D4, slice plan §2)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml
from tos.evidence import EvidenceAppendReceipt


class FakeEvidenceDouble:
    """An in-memory :class:`tos_runtime.evidence.ports.EvidenceAppendPort` double.

    Records every ``append()`` call's ``(payload, kind, record_class)``
    verbatim — used to assert custody never writes secret bytes into an
    evidence record (test_file_custody.py's "evidence raw records contain no
    key bytes" fault case).
    """

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []
        self._next_seq = 0

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self.records.append(
            {"payload": dict(payload), "kind": kind, "record_class": record_class}
        )
        receipt = EvidenceAppendReceipt(
            segment_id=None,
            seq=self._next_seq,
            chain_digest="fake-chain-digest",
            key_generation=1,
        )
        self._next_seq += 1
        return receipt


@pytest.fixture
def evidence_double() -> FakeEvidenceDouble:
    return FakeEvidenceDouble()


@pytest.fixture
def expected_owner_uid() -> int:
    """The real uid of the test process — the default "everything matches" value."""
    return os.getuid()


def write_scope_file(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    """Write ``data`` to ``path`` and set its mode explicitly (never relying
    on the process umask, which some CI runners set narrower than 0644)."""
    path.write_bytes(data)
    os.chmod(path, mode)


def write_manifest(
    root: Path,
    *,
    environment_label: str | None,
    scopes: Mapping[str, Mapping[str, object]],
) -> Path:
    """Write a ``custody.manifest.yaml`` at ``root`` and return its path."""
    manifest_path = root / "custody.manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "scopes": {name: dict(entry) for name, entry in scopes.items()},
            }
        )
    )
    return manifest_path


@pytest.fixture
def custody_root(tmp_path: Path) -> Path:
    root = tmp_path / "custody"
    root.mkdir()
    return root
