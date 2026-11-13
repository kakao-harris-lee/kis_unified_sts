"""Shared fixtures for the surviving ``tos_runtime.safety`` tests.

Every fixture writes REAL (non-null) YAML documents to ``tmp_path`` — the checked-in
``tos/runtime/config/*.example.yaml`` files stay all-null (named-TBD) on purpose; only test
fixtures carry concrete values (project convention — see
``tos/runtime/tests/compose/conftest.py``'s own fixtures for the precedent this mirrors).

The safety-mesh fixtures (the envelope/profile/activation triple, the deviation sets, the
time-health doubles) went with plan S2-a along with the services that read them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore


class FixedKeyProvider:
    """A :class:`~tos_runtime.evidence.store.KeyProvider` test double — fixed bytes
    (mirrors ``tos/runtime/tests/evidence/conftest.py``'s own double)."""

    def __init__(
        self, key_generation: int = 1, key: bytes = b"safety-test-fixed-key-bytes"
    ) -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        """The current ``(generation, key)`` pair."""
        return (self._key_generation, self._key)

    def generations(self) -> tuple[int, ...]:
        """Every generation this provider can serve."""
        return (self._key_generation,)

    def key_for(self, generation: int) -> bytes:
        """The key bytes for ``generation`` (one fixed key here)."""
        del generation
        return self._key


@pytest.fixture
def key_provider() -> KeyProvider:
    return FixedKeyProvider()


@pytest.fixture
def evidence_store(
    tmp_path: Path, key_provider: KeyProvider
) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def expected_owner_uid() -> int:
    return os.getuid()


class FakeNewRiskHaltInbox:
    """A :class:`~tos_runtime.safety.latch.NewRiskHaltReader`-shaped, and
    ``SqliteEventInbox.new_risk_halt``-shaped, double: a settable ``current`` row
    (or ``None``)."""

    def __init__(self, current: dict[str, object] | None = None) -> None:
        self.current = current

    def new_risk_halt(self) -> dict[str, object] | None:
        """The currently-latched row, or ``None``."""
        return self.current


def write_rearm_approval_file(
    approvals_dir: Path,
    *,
    latched_evidence_seq: int,
    environment_label: str = "non-live-test",
    approvals: list[dict[str, str]] | None = None,
    mode: int = 0o600,
) -> Path:
    """Write one ``approvals/rearm/<latched_evidence_seq>.yaml`` decision file
    (:mod:`tos_runtime.safety.rearm` module docstring).

    Defaults to a genuinely satisfying single-principal ``APPROVE``; a caller mutates
    ``approvals`` to exercise a refusal (two entries, a ``DENY``, a ``TBD`` principal, …).
    """
    if approvals is None:
        approvals = [{"principal_id": "alice", "decision": "APPROVE"}]
    path = approvals_dir / "rearm" / f"{latched_evidence_seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "latched_evidence_seq": latched_evidence_seq,
                "approvals": approvals,
            },
            sort_keys=False,
        )
    )
    os.chmod(path, mode)
    return path


def write_monitor_coverage_file(
    tmp_path: Path,
    *,
    coverage_generation: int | None = 1,
    max_evidence_tip_stall_ms: int | None = 60_000,
    max_inbox_unconsumed: int | None = 100,
    name: str = "monitor_coverage.yaml",
) -> Path:
    """Write one ``monitor_coverage.yaml`` for the slim monitor. A ``None`` for any field
    writes it as an explicit ``null`` — the named-TBD state the loader must refuse."""
    path = tmp_path / name
    path.write_text(
        yaml.safe_dump(
            {
                "coverage": {
                    "coverage_generation": coverage_generation,
                    "bounds": {
                        "max_evidence_tip_stall_ms": max_evidence_tip_stall_ms,
                        "max_inbox_unconsumed": max_inbox_unconsumed,
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path
