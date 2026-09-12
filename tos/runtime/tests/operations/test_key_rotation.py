"""Evidence-signing key rotation tests (TOS Phase 5 W4 plan §2 decision 4).

Covers the pure continuity-verdict table, the real
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore` constructor gate built on top of it, and
the end-to-end :func:`~tos_runtime.operations.key_rotation.rotate_evidence_key` workflow
(evidence rotation + RCL commit, including the RCL-failure fallback, M8).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.store import KeyContinuityRefused, SqliteEvidenceStore
from tos_runtime.operations.key_rotation import (
    KeyContinuityVerdict,
    KeyRotationRefused,
    RotationOutcome,
    rotate_evidence_key,
    verify_key_generation_continuity,
)
from tos_runtime.rcl.log import SqliteCommitLog

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _write_key(root: Path, generation: int, data: bytes) -> None:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"evidence.key.{generation}"
    path.write_bytes(data)
    os.chmod(path, 0o600)


# ============================================================================
# verify_key_generation_continuity — pure-function table (every branch)
# ============================================================================


def test_fresh_store_single_generation_is_continuous() -> None:
    result = verify_key_generation_continuity(None, None, (1,))
    assert result.verdict == KeyContinuityVerdict.CONTINUOUS


def test_fresh_store_multiple_generations_is_rotation_pending() -> None:
    result = verify_key_generation_continuity(None, None, (1, 2))
    assert result.verdict == KeyContinuityVerdict.ROTATION_PENDING
    assert "fresh store" in result.reason


def test_no_generations_at_all_is_history_unverifiable() -> None:
    result = verify_key_generation_continuity(None, None, ())
    assert result.verdict == KeyContinuityVerdict.HISTORY_UNVERIFIABLE


def test_tip_matches_provider_max_is_continuous() -> None:
    result = verify_key_generation_continuity(2, lambda _generation: True, (1, 2))
    assert result.verdict == KeyContinuityVerdict.CONTINUOUS


def test_tip_generation_file_missing_is_history_unverifiable() -> None:
    result = verify_key_generation_continuity(2, None, (1,))
    assert result.verdict == KeyContinuityVerdict.HISTORY_UNVERIFIABLE


def test_tip_exceeds_every_generation_on_disk_is_history_unverifiable() -> None:
    result = verify_key_generation_continuity(5, None, (1, 5))
    # provider_max (5) == tip (5): still continuous — sanity check the boundary before the
    # genuinely-exceeds case below.
    assert result.verdict == KeyContinuityVerdict.CONTINUOUS
    result = verify_key_generation_continuity(5, None, (1, 3))
    assert result.verdict == KeyContinuityVerdict.HISTORY_UNVERIFIABLE


def test_provider_ahead_of_tip_with_no_rotation_commit_is_rotation_pending() -> None:
    """The gap this whole module closes: a new key file dropped on disk, no rotation commit
    recorded yet — must deny, never silently sign with it (design #40 D4.1 겹침 0)."""
    result = verify_key_generation_continuity(1, lambda _generation: False, (1, 2))
    assert result.verdict == KeyContinuityVerdict.ROTATION_PENDING
    assert "rotate-key" in result.reason


def test_provider_ahead_of_tip_but_rotation_commit_already_recorded_is_unverifiable() -> (
    None
):
    """An inconsistency the module refuses to guess through, rather than silently trust the
    (possibly stale) tip reading over the recorded rotation commit."""
    result = verify_key_generation_continuity(1, lambda _generation: True, (1, 2))
    assert result.verdict == KeyContinuityVerdict.HISTORY_UNVERIFIABLE


def test_provider_ahead_of_tip_with_no_cross_check_callable_is_rotation_pending() -> (
    None
):
    result = verify_key_generation_continuity(1, None, (1, 2))
    assert result.verdict == KeyContinuityVerdict.ROTATION_PENDING


# ============================================================================
# SqliteEvidenceStore constructor gate — real store, real FileKeyProvider
# ============================================================================


def test_fresh_store_single_generation_opens(tmp_path: Path) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    try:
        assert store.key_generation == 1
    finally:
        store.close()


def test_fresh_store_two_generations_is_refused(tmp_path: Path) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    _write_key(keydir, 2, b"gen-2-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    with pytest.raises(KeyContinuityRefused):
        SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)


def test_existing_chain_plus_ungated_new_generation_file_refuses_reopen(
    tmp_path: Path,
) -> None:
    """(M4) An existing chain at generation 1, with generation 2's file present on disk but NO
    rotation commit recorded — reopening must refuse. Removing the constructor's continuity
    check would let this reopen succeed silently, which is exactly the mutation this test
    exists to catch red."""
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.close()

    # Operator (or an attacker) drops the new generation's file WITHOUT running rotate-key.
    _write_key(keydir, 2, b"gen-2-key-bytes-000000000000000")

    with pytest.raises(KeyContinuityRefused, match="ROTATION_PENDING"):
        SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)


def test_missing_tip_generation_file_is_history_unverifiable_refusal(
    tmp_path: Path,
) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
    store.close()

    # The generation-1 key file this chain was signed under vanishes.
    (keydir / "evidence.key.1").unlink()

    with pytest.raises(KeyContinuityRefused, match="HISTORY_UNVERIFIABLE"):
        SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)


# ============================================================================
# rotate_evidence_key — end-to-end workflow
# ============================================================================


def _open_store_and_rcl(
    tmp_path: Path, provider: FileKeyProvider
) -> tuple[SqliteEvidenceStore, SqliteCommitLog]:
    store = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    rcl_log = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=store)
    return store, rcl_log


def test_rotate_evidence_key_reopens_at_new_generation_and_verifies_whole_chain(
    tmp_path: Path,
) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store, rcl_log = _open_store_and_rcl(tmp_path, provider)
    store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")

    _write_key(keydir, 2, b"gen-2-key-bytes-000000000000000")
    outcome = rotate_evidence_key(store, provider, rcl_log, 2)
    assert outcome == RotationOutcome.ROTATED
    assert store.key_generation == 2

    store.append({"b": 2}, kind="TEST", record_class="TESTCLASS")
    store.close()
    rcl_log.close()

    reopened = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    try:
        assert reopened.key_generation == 2
        assert (
            reopened.verify(
                {
                    1: b"gen-1-key-bytes-000000000000000",
                    2: b"gen-2-key-bytes-000000000000000",
                }
            )
            is True
        )
    finally:
        reopened.close()


def test_rotate_evidence_key_refuses_a_non_successor_generation(tmp_path: Path) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store, rcl_log = _open_store_and_rcl(tmp_path, provider)
    try:
        _write_key(keydir, 3, b"gen-3-key-bytes-000000000000000")
        with pytest.raises(KeyRotationRefused):
            rotate_evidence_key(store, provider, rcl_log, 3)
    finally:
        store.close()
        rcl_log.close()


def test_rotate_evidence_key_rejects_re_rotating_to_the_same_generation(
    tmp_path: Path,
) -> None:
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store, rcl_log = _open_store_and_rcl(tmp_path, provider)
    try:
        with pytest.raises(KeyRotationRefused):
            rotate_evidence_key(store, provider, rcl_log, 1)
    finally:
        store.close()
        rcl_log.close()


def test_rotate_evidence_key_when_rcl_write_fails_still_rotates_and_marks_unrecorded(
    tmp_path: Path,
) -> None:
    """(M8) The RCL side is forced to fail (read-only pragma) — the evidence side must have
    ALREADY rotated regardless, and the store must carry an honest
    ``KEY_ROTATION_RCL_UNRECORDED`` marker rather than silently reporting nothing happened.
    """
    keydir = tmp_path / "keys"
    _write_key(keydir, 1, b"gen-1-key-bytes-000000000000000")
    provider = FileKeyProvider(keydir, expected_owner_uid=os.getuid())

    store, rcl_log = _open_store_and_rcl(tmp_path, provider)
    try:
        _write_key(keydir, 2, b"gen-2-key-bytes-000000000000000")
        # SqliteCommitLog has no public connection accessor (unlike the evidence store's own
        # `.connection` property) — `_conn` is the same private-attribute fault-injection idiom
        # `tests/rcl/test_log_fault_contracts.py` already uses.
        rcl_log._conn.execute("PRAGMA query_only=ON")
        try:
            outcome = rotate_evidence_key(store, provider, rcl_log, 2)
        finally:
            rcl_log._conn.execute("PRAGMA query_only=OFF")

        assert outcome == RotationOutcome.ROTATED_RCL_UNRECORDED
        assert (
            store.key_generation == 2
        ), "evidence side must rotate regardless of RCL failure"

        markers = [
            m
            for m in store.iter_entry_meta()
            if m.kind == "KEY_ROTATION_RCL_UNRECORDED"
        ]
        assert len(markers) == 1
    finally:
        store.close()
        rcl_log.close()
