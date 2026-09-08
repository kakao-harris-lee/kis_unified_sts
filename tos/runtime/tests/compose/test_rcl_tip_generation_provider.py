"""``tos_runtime.compose._wiring._rcl_tip_generation_provider`` unit tests
(re-review finding F2, 2026-09-08). Hermetic: a real
:class:`~tos_runtime.rcl.log.SqliteCommitLog` under ``tmp_path``, never a
double/mock of the log itself (per this repo's own anti-phantom discipline
— the failure mode under test is a REAL log's real fault contract).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from tos.evidence import EvidenceAppendReceipt
from tos.rcl import AppendReceipt, CommandType, CommitEntry
from tos.workload import RuntimeIdentity
from tos_runtime.compose._wiring import _rcl_tip_generation_provider
from tos_runtime.rcl.log import SqliteCommitLog, StaleEpochRead

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class _FakeEvidencePort:
    """A minimal ``EvidenceAppendPort`` double — this test exercises the RCL
    log's own tip/epoch mechanics, not evidence chaining."""

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        del payload, kind, record_class
        return EvidenceAppendReceipt(
            segment_id=None, seq=0, chain_digest="fake", key_generation=1
        )


def _append_one(log: SqliteCommitLog, *, writer_epoch: int, expected_seq: int) -> int:
    """Commit one entry via ``append_cas``; returns the new tip ``seq``."""
    entry = CommitEntry(
        command_id=f"cmd-{expected_seq + 1}",
        command_digest=f"dig-{expected_seq + 1}",
        kind=CommandType.COMMIT_RESERVATION,
    )
    receipt = log.append_cas(
        entry, expected_seq=expected_seq, writer_epoch=writer_epoch
    )
    assert isinstance(receipt, AppendReceipt)
    return receipt.seq


def test_empty_log_yields_zero(tmp_path: Path) -> None:
    """(i) An empty log (no committed tip) yields generation ``0``."""
    log = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=_FakeEvidencePort())
    try:
        identity = RuntimeIdentity(cell_id="test-cell", process_nonce="n1")
        writer_epoch = log.acquire_epoch(identity)
        provider = _rcl_tip_generation_provider(log, writer_epoch)
        assert provider(None) == 0
    finally:
        log.close()


def test_committed_entries_advance_and_reflect_the_real_tip(tmp_path: Path) -> None:
    """(ii) After N committed entries the provider returns the real
    ``last_seq`` and advances after one more append — never a constant.

    Mutation-kill note (verified manually, not committed): reverting this
    function's body to a hardcoded ``return 0`` makes this test fail with
    ``assert 0 == 1`` at the first post-commit assertion below.
    """
    log = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=_FakeEvidencePort())
    try:
        identity = RuntimeIdentity(cell_id="test-cell", process_nonce="n1")
        writer_epoch = log.acquire_epoch(identity)
        provider = _rcl_tip_generation_provider(log, writer_epoch)

        seq = _append_one(log, writer_epoch=writer_epoch, expected_seq=-1)
        seq = _append_one(log, writer_epoch=writer_epoch, expected_seq=seq)
        assert provider(None) == seq
        assert seq != 0

        next_seq = _append_one(log, writer_epoch=writer_epoch, expected_seq=seq)
        assert next_seq != seq
        assert provider(None) == next_seq
    finally:
        log.close()


def test_second_handle_acquiring_epoch_raises_stale_epoch_read(tmp_path: Path) -> None:
    """(iii) A second handle acquiring a new Writer Epoch on the SAME log
    file makes the first handle's provider raise ``StaleEpochRead`` —
    never a silently-returned ``0`` (re-review finding F2)."""
    log_path = tmp_path / "rcl.sqlite3"
    first = SqliteCommitLog(log_path, evidence_port=_FakeEvidencePort())
    second = SqliteCommitLog(log_path, evidence_port=_FakeEvidencePort())
    try:
        identity = RuntimeIdentity(cell_id="test-cell", process_nonce="n1")
        stale_epoch = first.acquire_epoch(identity)
        second.acquire_epoch(identity)  # invalidates `first`'s epoch

        provider = _rcl_tip_generation_provider(first, stale_epoch)
        with pytest.raises(StaleEpochRead):
            provider(None)
    finally:
        first.close()
        second.close()
