"""``FileCustody`` tests — the six §2 fault cases + handle/digest edge cases
(design #40 D4, slice plan §2 "레인 N").
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from tos_runtime.custody.file_custody import PROVISIONED_SCOPES, FileCustody
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


def test_mode_0644_refuses_before_ever_opening_the_file(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LOW-1 (2026-09-08 independent review): the mode/owner gate must run
    BEFORE ``FileCustody.load`` ever opens the file for reading — proven
    here by making ``Path.open`` itself raise loudly, so a mode refusal that
    somehow happened AFTER an open attempt would surface as that raise
    instead of the expected ``CustodyLoadRefused``."""
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    write_scope_file(custody_root / "read.principal", b"secret-bytes", mode=0o644)

    def _fail_if_opened(self: Path, *args: object, **kwargs: object) -> None:
        raise AssertionError(
            f"FileCustody.load must not open {self} for reading before its "
            "mode/owner gate refuses it"
        )

    monkeypatch.setattr(Path, "open", _fail_if_opened)

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


def test_provisioned_scopes_is_pinned_exactly() -> None:
    """MEDIUM-2 (2026-09-08 independent review): a mutation adding e.g.
    ``"order.principal"`` to ``PROVISIONED_SCOPES`` broke ZERO existing
    tests, because none of them asserted the constant's contents directly —
    only that a few sampled strings were refused. This pins the exact set,
    so ANY addition, removal, or rename is caught immediately regardless of
    which specific scope strings the behavioural tests happen to exercise.
    """
    assert (
        frozenset({"read.principal", "evidence.key", "replay.params"})
        == PROVISIONED_SCOPES
    )


@pytest.mark.parametrize(
    "scope",
    [
        "order",
        "Order",
        "ORDER",
        "oRdEr",
        "order.principal",
        "Order.Principal",
        "ORDER.KEY",
        "order.equity",
        "order.futures",
        "order_x",
        "orderx",
        "OrDeR.something.deeply.nested",
    ],
)
def test_load_refuses_any_order_prefixed_scope_case_insensitive(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    scope: str,
) -> None:
    """MEDIUM-2's behavioural companion to the exact-set pin above: every
    casing of an ``order``-prefixed scope must be refused, not merely the
    three literal strings the pre-review parametrize happened to cover.
    """
    assert scope.lower().startswith("order")  # the parametrize itself is honest
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )

    with pytest.raises(CustodyScopeNotProvisioned):
        custody.load(scope)

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
# LOW-2 (2026-09-08 independent review) — single-copy ownership + zeroing
# ============================================================================


def test_credential_handle_takes_ownership_of_a_bytearray_without_copying() -> None:
    """A ``bytearray`` passed as ``data`` is the SAME object the handle
    holds — not an equal-but-distinct copy — so there is exactly one copy
    of the secret in memory from construction through :meth:`close`."""
    secret = bytearray(b"single-copy-secret")

    handle = CredentialHandle(scope="s", principal_id="p", data=secret)

    assert handle._buffer is secret  # ownership, not a defensive copy
    handle.close()
    assert all(byte == 0 for byte in secret)  # closing the handle zeroed THIS object


def test_file_custody_load_hands_credential_handle_the_only_copy(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    """End-to-end: ``FileCustody.load`` must read the secret into a
    ``bytearray`` (never an immutable ``bytes`` object it could not zero)
    and hand that exact buffer to the returned handle, so closing the
    handle actually erases the one and only in-memory copy the load path
    produced."""
    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    secret = b"end-to-end-single-copy-secret"
    write_scope_file(custody_root / "read.principal", secret, mode=0o600)

    handle = custody.load("read.principal")

    assert isinstance(handle._buffer, bytearray)
    assert bytes(handle._buffer) == secret

    handle.close()

    assert all(byte == 0 for byte in handle._buffer)


def test_load_zeroes_already_read_bytes_when_digest_check_refuses(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A digest mismatch is discovered only AFTER the file has already been
    read (LOW-1's "check 5 runs on already-read bytes" — the read cannot be
    undone), so the refusal path must zero that already-read buffer itself
    rather than leaving it to a ``CredentialHandle`` that is never
    constructed and therefore never gets the chance."""
    import tos_runtime.custody.file_custody as file_custody_module

    data = b"digest-mismatch-secret-bytes"
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
    write_scope_file(custody_root / "read.principal", data, mode=0o600)

    captured: dict[str, bytearray] = {}
    real_read = file_custody_module._read_into_bytearray

    def _capturing_read(path: Path) -> bytearray:
        buffer = real_read(path)
        captured["buffer"] = buffer
        return buffer

    monkeypatch.setattr(file_custody_module, "_read_into_bytearray", _capturing_read)

    with pytest.raises(CustodyLoadRefused, match="digest"):
        custody.load("read.principal")

    assert "buffer" in captured
    assert all(byte == 0 for byte in captured["buffer"])


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


# ============================================================================
# MEDIUM-1 (2026-09-08 independent review) — path-escape guard
#
# Reproduced pre-fix: an absolute path, a "../" value, AND a symlink whose
# target lies outside root_dir all loaded successfully and were recorded as
# a CUSTODY_LOAD evidence entry. Two layers now close this (see
# file_custody.py's module docstring fault-contract table row "경로 이탈"):
# (1) a manifest-parse-time string validator (absolute / ".." rejected as
# CustodyManifestError from CustodyManifest.load, surfacing at FileCustody
# CONSTRUCTION, before any scope is ever loaded); (2) a load-time resolved-
# path containment check (catches a symlink, which layer (1) cannot).
# ============================================================================


def test_manifest_rejects_absolute_file_path(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    tmp_path: Path,
) -> None:
    outside_secret = tmp_path / "outside_secret.pem"
    write_scope_file(outside_secret, b"OUTSIDE-SECRET-ABSOLUTE", mode=0o600)
    scopes = dict(_DEFAULT_SCOPES)
    scopes["read.principal"] = {
        "file": str(outside_secret),
        "principal": "read-principal-v1",
        "expected_sha256": None,
    }
    write_manifest(custody_root, environment_label="non-live-test", scopes=scopes)

    with pytest.raises(CustodyManifestError, match="absolute"):
        FileCustody(
            root_dir=custody_root,
            environment_label="non-live-test",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )

    # Refused at CONSTRUCTION — no scope was ever loaded, no evidence write.
    assert evidence_double.records == []


def test_manifest_rejects_dotdot_file_path(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    tmp_path: Path,
) -> None:
    outside_dir = tmp_path / "rel_outside"
    outside_dir.mkdir()
    write_scope_file(
        outside_dir / "rel_secret.pem", b"OUTSIDE-SECRET-DOTDOT", mode=0o600
    )
    scopes = dict(_DEFAULT_SCOPES)
    scopes["read.principal"] = {
        "file": "../rel_outside/rel_secret.pem",
        "principal": "read-principal-v1",
        "expected_sha256": None,
    }
    write_manifest(custody_root, environment_label="non-live-test", scopes=scopes)

    with pytest.raises(CustodyManifestError, match=r"\.\."):
        FileCustody(
            root_dir=custody_root,
            environment_label="non-live-test",
            expected_owner_uid=expected_owner_uid,
            evidence=evidence_double,
        )

    assert evidence_double.records == []


def test_load_refuses_symlink_escaping_root(
    custody_root: Path,
    evidence_double: FakeEvidenceDouble,
    expected_owner_uid: int,
    tmp_path: Path,
) -> None:
    """A symlink's OWN path string (``"read.principal"``) looks perfectly
    relative and contained — only resolving it reveals the escape, which is
    exactly what the manifest-parse-time string validator cannot do."""
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_secret = outside_dir / "outside_secret.pem"
    write_scope_file(outside_secret, b"OUTSIDE-SECRET-VIA-SYMLINK", mode=0o600)

    custody = _make_custody(
        custody_root, evidence_double, expected_owner_uid=expected_owner_uid
    )
    (custody_root / "read.principal").symlink_to(outside_secret)

    with pytest.raises(CustodyManifestError, match="escapes custody root"):
        custody.load("read.principal")

    assert evidence_double.records == []


def test_load_succeeds_with_honest_relative_nested_path(
    custody_root: Path, evidence_double: FakeEvidenceDouble, expected_owner_uid: int
) -> None:
    """Regression guard: the MEDIUM-1 fix must not reject a genuinely
    contained relative path, including one nested in a subdirectory."""
    scopes = dict(_DEFAULT_SCOPES)
    scopes["read.principal"] = {
        "file": "nested/read.principal",
        "principal": "read-principal-v1",
        "expected_sha256": None,
    }
    custody = _make_custody(
        custody_root,
        evidence_double,
        expected_owner_uid=expected_owner_uid,
        scopes=scopes,
    )
    nested_dir = custody_root / "nested"
    nested_dir.mkdir()
    write_scope_file(nested_dir / "read.principal", b"nested-honest-bytes", mode=0o600)

    handle = custody.load("read.principal")

    assert handle.value() == b"nested-honest-bytes"
    assert len(evidence_double.records) == 1
