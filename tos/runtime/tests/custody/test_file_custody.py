"""``FileCustody`` tests — the six §2 fault cases + handle/digest edge cases
(design #40 D4, slice plan §2 "레인 N").
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.ports import (
    CredentialHandle,
    CustodyError,
    CustodyLoadRefused,
    CustodyManifestError,
    CustodyScopeNotProvisioned,
)

from .conftest import FakeEvidenceDouble, write_manifest, write_scope_file

_DEFAULT_SCOPES = {
    "read.principal": {
        "file": "read.principal",
        "principal": "read-principal-v1",
        "expected_sha256": None,
    },
    "evidence.key": {
        "file": "evidence.key",
        "principal": "evidence-key-v1",
        "expected_sha256": None,
    },
    "replay.params": {
        "file": "replay.params",
        "principal": "replay-params-v1",
        "expected_sha256": None,
    },
}


def _make_custody(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    *,
    environment_label: str = "non-live-test",
    expected_owner_uid: int,
    getuid=None,
    scopes=None,
) -> FileCustody:
    write_manifest(
        custody_root,
        environment_label=environment_label,
        scopes=scopes if scopes is not None else _DEFAULT_SCOPES,
    )
    kwargs: dict[str, object] = {
        "root_dir": custody_root,
        "environment_label": environment_label,
        "expected_owner_uid": expected_owner_uid,
        "evidence": evidence_double,
    }
    if getuid is not None:
        kwargs["getuid"] = getuid
    return FileCustody(**kwargs)


# ============================================================================
# ① mode 0644 ⇒ refuse
# ============================================================================


def test_load_refuses_mode_0644(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    write_scope_file(custody_root / "read.principal", b"secret-bytes", mode=0o644)

    with pytest.raises(CustodyLoadRefused, match="0o600"):
        custody.load("read.principal")


# ============================================================================
# ② owner mismatch ⇒ refuse (inject getuid, never chown for real)
# ============================================================================


def test_load_refuses_owner_mismatch_via_injected_getuid(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root,
        evidence_double,
        expected_owner_uid=expected_owner_uid,
        getuid=lambda: expected_owner_uid + 1,
    )
    write_scope_file(custody_root / "read.principal", b"secret-bytes", mode=0o600)

    with pytest.raises(CustodyLoadRefused, match="owner mismatch"):
        custody.load("read.principal")


# ============================================================================
# ③ label mismatch ⇒ refuse (construction itself refuses — "기동 거부")
# ============================================================================


def test_construction_refuses_environment_label_mismatch(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    write_manifest(custody_root, environment_label="paper", scopes=_DEFAULT_SCOPES)

    with pytest.raises(CustodyLoadRefused, match="environment_label"):
        FileCustody(
            root_dir=custody_root,
            environment_label="restricted-live",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )


def test_construction_refuses_when_manifest_label_is_null(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    """A `null` manifest label never vacuously matches ANY runtime label."""
    write_manifest(custody_root, environment_label=None, scopes=_DEFAULT_SCOPES)

    with pytest.raises(CustodyLoadRefused):
        FileCustody(
            root_dir=custody_root,
            environment_label="non-live-test",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )


# ============================================================================
# ④ order scope ⇒ CustodyScopeNotProvisioned
# ============================================================================


@pytest.mark.parametrize("scope", ["order.equity", "order.futures", "order"])
def test_load_refuses_order_scope(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    scope: str,
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )

    with pytest.raises(CustodyScopeNotProvisioned):
        custody.load(scope)

    # No file-system access, no evidence write — refused BEFORE any I/O.
    assert evidence_double.records == []


# ============================================================================
# ⑤ missing file ⇒ refuse
# ============================================================================


def test_load_refuses_missing_file(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    # Deliberately never write custody_root / "read.principal".

    with pytest.raises(CustodyLoadRefused, match="does not exist"):
        custody.load("read.principal")


def test_load_refuses_scope_manifest_omits(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    """A PROVISIONED scope the manifest itself doesn't configure is refused."""
    scopes = dict(_DEFAULT_SCOPES)
    del scopes["replay.params"]
    custody = _make_custody(
        custody_root,
        evidence_double,
        expected_owner_uid=expected_owner_uid,
        scopes=scopes,
    )

    with pytest.raises(CustodyLoadRefused, match="does not configure"):
        custody.load("replay.params")


# ============================================================================
# ⑥ evidence raw records contain no key bytes
# ============================================================================


def test_evidence_record_never_contains_secret_bytes(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    secret = b"THIS-IS-THE-SECRET-KEY-MATERIAL"
    write_scope_file(custody_root / "read.principal", secret, mode=0o600)

    handle = custody.load("read.principal")

    assert handle.value() == secret
    assert len(evidence_double.records) == 1
    record = evidence_double.records[0]
    serialized = repr(record)
    assert secret not in serialized.encode()
    assert secret.decode() not in serialized
    assert record["payload"]["principal_id"] == "read-principal-v1"
    assert record["payload"]["scope"] == "read.principal"
    assert record["payload"]["file_sha256"] == hashlib.sha256(secret).hexdigest()
    assert record["kind"] == "CUSTODY_LOAD"


# ============================================================================
# handle zeroed after context exit
# ============================================================================


def test_credential_handle_zeroed_after_context_exit(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    write_scope_file(custody_root / "read.principal", b"zero-me-please", mode=0o600)

    with custody.load("read.principal") as handle:
        assert handle.value() == b"zero-me-please"
        assert handle.is_closed is False

    assert handle.is_closed is True
    with pytest.raises(CustodyError):
        handle.value()


def test_credential_handle_repr_never_contains_secret_bytes() -> None:
    handle = CredentialHandle(
        scope="read.principal", principal_id="read-principal-v1", data=b"super-secret"
    )
    assert b"super-secret" not in repr(handle).encode()
    assert b"super-secret" not in str(handle).encode()
    handle.close()


def test_credential_handle_close_is_idempotent() -> None:
    handle = CredentialHandle(scope="s", principal_id="p", data=b"abc")
    handle.close()
    handle.close()  # must not raise
    assert handle.is_closed is True


# ============================================================================
# manifest digest pinning: mismatch ⇒ refuse; null ⇒ unpinned success
# ============================================================================


def test_load_refuses_pinned_digest_mismatch(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    scopes = dict(_DEFAULT_SCOPES)
    scopes["read.principal"] = {
        "file": "read.principal",
        "principal": "read-principal-v1",
        "expected_sha256": "0" * 64,
    }
    custody = _make_custody(
        custody_root,
        evidence_double,
        expected_owner_uid=expected_owner_uid,
        scopes=scopes,
    )
    write_scope_file(custody_root / "read.principal", b"actual-bytes", mode=0o600)

    with pytest.raises(CustodyLoadRefused, match="digest"):
        custody.load("read.principal")


def test_load_succeeds_with_correctly_pinned_digest(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    data = b"pinned-bytes"
    scopes = dict(_DEFAULT_SCOPES)
    scopes["read.principal"] = {
        "file": "read.principal",
        "principal": "read-principal-v1",
        "expected_sha256": hashlib.sha256(data).hexdigest(),
    }
    custody = _make_custody(
        custody_root,
        evidence_double,
        expected_owner_uid=expected_owner_uid,
        scopes=scopes,
    )
    write_scope_file(custody_root / "read.principal", data, mode=0o600)

    handle = custody.load("read.principal")

    assert handle.value() == data
    record = evidence_double.records[0]
    assert record["payload"]["digest_pinned"] is True
    assert "digest_note" not in record["payload"]


def test_load_with_null_digest_succeeds_and_records_unpinned_note(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    write_scope_file(custody_root / "evidence.key", b"unpinned-key-bytes", mode=0o600)

    handle = custody.load("evidence.key")

    assert handle.value() == b"unpinned-key-bytes"
    record = evidence_double.records[0]
    assert record["payload"]["digest_pinned"] is False
    assert record["payload"]["digest_note"] == "digest 미고정"


# ============================================================================
# manifest existence/parse failures
# ============================================================================


def test_construction_refuses_missing_manifest(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    with pytest.raises(CustodyManifestError):
        FileCustody(
            root_dir=custody_root,
            environment_label="non-live-test",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )


def test_construction_refuses_malformed_manifest(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    (custody_root / "custody.manifest.yaml").write_text("scopes: [1, 2\n")

    with pytest.raises(CustodyManifestError):
        FileCustody(
            root_dir=custody_root,
            environment_label="non-live-test",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )
