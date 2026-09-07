"""``FileKeyProvider`` tests: generation discovery, mode/owner gate, Protocol
conformance, and a real-store smoke test (design #40 D4.1, slice plan §2).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.custody.ports import KeyProvider as CustodyKeyProvider
from tos_runtime.evidence.store import KeyProvider as StoreKeyProvider
from tos_runtime.evidence.store import SqliteEvidenceStore

from .conftest import write_scope_file


def _write_key(root: Path, generation: int, data: bytes) -> None:
    write_scope_file(root / f"evidence.key.{generation}", data, mode=0o600)


def test_current_generation_is_the_highest_present(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    _write_key(tmp_path, 1, b"gen-1-key")
    _write_key(tmp_path, 2, b"gen-2-key")
    _write_key(tmp_path, 10, b"gen-10-key")
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    assert provider.current_generation() == 10


def test_current_generation_refuses_when_no_key_files_exist(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    with pytest.raises(CustodyLoadRefused):
        provider.current_generation()


def test_distinct_keys_per_generation(tmp_path: Path, expected_owner_uid: int) -> None:
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    _write_key(tmp_path, 2, b"gen-2-key-bytes")
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    assert provider.key_for(1) == b"gen-1-key-bytes"
    assert provider.key_for(2) == b"gen-2-key-bytes"
    assert provider.key_for(1) != provider.key_for(2)

    current_generation, current_key = provider.current()
    assert current_generation == 2
    assert current_key == b"gen-2-key-bytes"


def test_key_for_refuses_unknown_generation(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    with pytest.raises(CustodyLoadRefused, match="not found"):
        provider.key_for(99)


def test_key_for_refuses_wrong_mode(tmp_path: Path, expected_owner_uid: int) -> None:
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    os.chmod(tmp_path / "evidence.key.1", 0o644)
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    with pytest.raises(CustodyLoadRefused, match="0o600"):
        provider.key_for(1)


def test_key_for_refuses_owner_mismatch_via_injected_getuid(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    provider = FileKeyProvider(
        tmp_path,
        expected_owner_uid=expected_owner_uid,
        getuid=lambda: expected_owner_uid + 1,
    )

    with pytest.raises(CustodyLoadRefused, match="owner mismatch"):
        provider.key_for(1)


def test_old_generation_key_remains_readable_after_a_newer_one_appears(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    """ "옛 세대 키는 검증용으로 읽기만" — an old generation stays readable."""
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)
    assert provider.current_generation() == 1

    _write_key(tmp_path, 2, b"gen-2-key-bytes")  # rotation step 1: file first

    assert provider.current_generation() == 2
    assert provider.key_for(1) == b"gen-1-key-bytes"  # still readable
    assert provider.key_for(2) == b"gen-2-key-bytes"


# ============================================================================
# Protocol conformance — both the custody-local mirror AND the store's own
# ============================================================================


def test_file_key_provider_satisfies_both_key_provider_protocols(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    _write_key(tmp_path, 1, b"gen-1-key-bytes")
    provider = FileKeyProvider(tmp_path, expected_owner_uid=expected_owner_uid)

    assert isinstance(provider, CustodyKeyProvider)
    assert isinstance(provider, StoreKeyProvider)


# ============================================================================
# smoke test: a real SqliteEvidenceStore constructed with FileKeyProvider
# ============================================================================


def test_sqlite_evidence_store_accepts_file_key_provider_directly(
    tmp_path: Path, expected_owner_uid: int
) -> None:
    key_dir = tmp_path / "keys"
    key_dir.mkdir()
    _write_key(key_dir, 1, b"real-store-signing-key-bytes")
    provider = FileKeyProvider(key_dir, expected_owner_uid=expected_owner_uid)

    store = SqliteEvidenceStore(tmp_path / "evidence.sqlite3", key_provider=provider)
    try:
        receipt = store.append({"a": 1}, kind="TEST", record_class="TESTCLASS")
        assert receipt.durable is True
        assert receipt.key_generation == 1
        assert store.verify({1: b"real-store-signing-key-bytes"}) is True
    finally:
        store.close()
