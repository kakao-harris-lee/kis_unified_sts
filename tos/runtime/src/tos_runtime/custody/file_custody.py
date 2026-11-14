"""``FileCustody`` — the Phase 2 :class:`~tos_runtime.custody.ports.CredentialCustody`"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from tos.evidence import scrub_secret_fields
from tos.workload import environment_label_consistent

from tos_runtime._named_tbd import is_named_tbd_placeholder
from tos_runtime.custody.ports import (
    CredentialHandle,
    CustodyLoadRefused,
    CustodyManifestError,
    CustodyScopeNotProvisioned,
)
from tos_runtime.evidence.ports import EvidenceAppendPort

__all__ = [
    "CustodyManifest",
    "FileCustody",
    "MANIFEST_FILENAME",
    "PROVISIONED_SCOPES",
    "verify_file_mode_and_owner",
]

MANIFEST_FILENAME = "custody.manifest.yaml"

PROVISIONED_SCOPES: frozenset[str] = frozenset(
    {
        "read.principal",
        "evidence.key",
        "replay.params",
        "kis_mock.app_key",
        "kis_mock.app_secret",
    }
)

_REQUIRED_MODE = 0o600


class _ScopeManifestEntry(BaseModel):
    """One scope's row in ``custody.manifest.yaml`` — frozen, load-only."""

    model_config = ConfigDict(frozen=True)

    file: str
    principal: str
    expected_sha256: str | None = None

    @field_validator("file")
    @classmethod
    def _file_must_be_relative_and_contained(cls, value: str) -> str:
        """Reject an absolute path or any ``..`` component (MEDIUM-1 fix)."""
        candidate = Path(value)
        if candidate.is_absolute():
            raise ValueError(
                f"scope 'file' must be relative to the custody directory — "
                f"got an absolute path {value!r} (design #40 D4.1, MEDIUM-1 "
                "path-escape guard)"
            )
        if ".." in candidate.parts:
            raise ValueError(
                f"scope 'file' must not contain a '..' path component — got "
                f"{value!r} (design #40 D4.1, MEDIUM-1 path-escape guard)"
            )
        return value

    @field_validator("principal")
    @classmethod
    def _principal_must_not_be_named_tbd(cls, value: str) -> str:
        """Refuse the named-TBD placeholder (W-A A-0 round 2) — a scope's own distinct"""
        if is_named_tbd_placeholder(value):
            raise ValueError(
                "scope 'principal' is still the template placeholder 'TBD' — "
                "operator-fill before activation"
            )
        return value


class CustodyManifest(BaseModel):
    """The parsed ``custody.manifest.yaml`` (design #40 D4.1, slice plan §2 item 4)."""

    model_config = ConfigDict(frozen=True)

    environment_label: str | None = None
    scopes: dict[str, _ScopeManifestEntry] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> CustodyManifest:
        """Parse ``path`` — fail-closed on anything but a well-shaped mapping."""
        try:
            raw_text = path.read_text()
        except OSError as exc:
            raise CustodyManifestError(
                f"CustodyManifest.load: cannot read {path}: {exc}"
            ) from exc
        try:
            raw = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise CustodyManifestError(
                f"CustodyManifest.load: {path} is not valid YAML: {exc}"
            ) from exc
        if not isinstance(raw, Mapping):
            raise CustodyManifestError(
                f"CustodyManifest.load: {path} must parse to a mapping "
                f"(got {type(raw).__name__})"
            )
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            raise CustodyManifestError(
                f"CustodyManifest.load: {path} failed validation: {exc}"
            ) from exc


def verify_file_mode_and_owner(
    path: Path, *, expected_owner_uid: int, getuid: Callable[[], int]
) -> None:
    """Fail-closed mode+owner gate shared by :class:`FileCustody` and"""
    mode = path.stat().st_mode & 0o777
    if mode != _REQUIRED_MODE:
        raise CustodyLoadRefused(
            f"verify_file_mode_and_owner: {path} has mode {oct(mode)}, "
            f"required exactly {oct(_REQUIRED_MODE)} — refuse (design #40 D4.1)"
        )
    file_owner_uid = path.stat().st_uid
    process_uid = getuid()
    if file_owner_uid != expected_owner_uid or process_uid != expected_owner_uid:
        raise CustodyLoadRefused(
            f"verify_file_mode_and_owner: {path} owner mismatch "
            f"(file_owner_uid={file_owner_uid}, process_uid={process_uid}, "
            f"expected_owner_uid={expected_owner_uid}) — refuse (design #40 D4.1)"
        )


def _read_into_bytearray(path: Path) -> bytearray:
    """Read ``path``'s full contents into a fresh, mutable ``bytearray``."""
    expected_size = path.stat().st_size
    buffer = bytearray(expected_size)
    with path.open("rb") as handle:
        bytes_read = handle.readinto(buffer)
    if bytes_read != expected_size:
        for index in range(len(buffer)):
            buffer[index] = 0
        raise CustodyLoadRefused(
            f"_read_into_bytearray: {path} changed size while being read "
            f"(expected {expected_size} bytes, read {bytes_read}) — refuse "
            "(possible concurrent modification)"
        )
    return buffer


class FileCustody:
    """The Phase 2 ``CredentialCustody`` implementation: scoped files under one"""

    def __init__(
        self,
        root_dir: Path,
        *,
        environment_label: str | None,
        expected_owner_uid: int,
        evidence: EvidenceAppendPort,
        getuid: Callable[[], int] = os.getuid,
        secret_field_names: frozenset[str] = frozenset(),
    ) -> None:
        """Load and validate the custody manifest at ``root_dir``."""
        self._root_dir = Path(root_dir)
        self._expected_owner_uid = expected_owner_uid
        self._evidence = evidence
        self._getuid = getuid
        self._secret_field_names = secret_field_names

        manifest_path = self._root_dir / MANIFEST_FILENAME
        self._manifest = CustodyManifest.load(manifest_path)
        self._resolved_root = self._root_dir.resolve(strict=True)
        if not environment_label_consistent(
            environment_label, self._manifest.environment_label
        ):
            raise CustodyLoadRefused(
                "FileCustody refuses to construct: runtime "
                f"environment_label={environment_label!r} does not match "
                f"custody manifest environment_label="
                f"{self._manifest.environment_label!r} at {manifest_path} "
                "(ADR-002-013 :498 — distinct environments must make "
                "cross-environment acceptance impossible; design #40 D4.1 "
                "line 113 boot refusal on mismatch)"
            )
        self._environment_label = environment_label

    def load(self, scope: str) -> CredentialHandle:
        """Load the credential bound to ``scope`` (design #40 D4.1)."""
        path, entry = self._verify_and_resolve(scope)
        data, actual_sha256, digest_pinned = self._read_and_verify_digest(
            scope, path, entry
        )
        payload: dict[str, object] = {
            "principal_id": entry.principal,
            "scope": scope,
            "file_sha256": actual_sha256,
            "digest_pinned": digest_pinned,
        }
        if not digest_pinned:
            payload["digest_note"] = "digest 미고정"
        scrubbed_payload, _masked_keys = scrub_secret_fields(
            payload, self._secret_field_names
        )
        self._evidence.append(
            scrubbed_payload, kind="CUSTODY_LOAD", record_class="CUSTODY_LOAD"
        )
        return CredentialHandle(scope=scope, principal_id=entry.principal, data=data)

    def scope_principal(self, scope: str) -> str:
        """Return ``scope``'s own manifest-declared ``principal`` — manifest-only, zero secret"""
        if scope not in PROVISIONED_SCOPES:
            raise CustodyScopeNotProvisioned(
                f"FileCustody.scope_principal: scope {scope!r} is not provisioned "
                f"(only {sorted(PROVISIONED_SCOPES)!r})"
            )
        entry = self._manifest.scopes.get(scope)
        if entry is None:
            raise CustodyLoadRefused(
                f"FileCustody.scope_principal: scope {scope!r} is provisioned by design "
                f"but the custody manifest at {self._root_dir / MANIFEST_FILENAME} "
                "does not configure it — refuse (fail-closed)"
            )
        return entry.principal

    def _verify_and_resolve(self, scope: str) -> tuple[Path, _ScopeManifestEntry]:
        """:meth:`load`'s checks 1-4 — everything before the file is opened."""
        if scope not in PROVISIONED_SCOPES:
            raise CustodyScopeNotProvisioned(
                f"FileCustody.load: scope {scope!r} is not provisioned in "
                f"Phase 2 (only {sorted(PROVISIONED_SCOPES)!r} — 'order.*' "
                "and every other scope is Phase 4 / futures-REAL-"
                "permanently-absent, design #40 D4.1 line 111, root "
                "CLAUDE.md non-negotiable rule)"
            )
        entry = self._manifest.scopes.get(scope)
        if entry is None:
            raise CustodyLoadRefused(
                f"FileCustody.load: scope {scope!r} is provisioned by design "
                f"but the custody manifest at {self._root_dir / MANIFEST_FILENAME} "
                "does not configure it — refuse (fail-closed)"
            )
        path = self._resolve_and_verify_contained(scope, entry.file)
        verify_file_mode_and_owner(
            path, expected_owner_uid=self._expected_owner_uid, getuid=self._getuid
        )
        return path, entry

    def _read_and_verify_digest(
        self, scope: str, path: Path, entry: _ScopeManifestEntry
    ) -> tuple[bytearray, str, bool]:
        """:meth:`load`'s check 5 — read the file and verify a pinned digest."""
        data = _read_into_bytearray(path)
        try:
            actual_sha256 = hashlib.sha256(data).hexdigest()
            digest_pinned = entry.expected_sha256 is not None
            if digest_pinned and actual_sha256 != entry.expected_sha256:
                raise CustodyLoadRefused(
                    f"FileCustody.load: scope {scope!r} file {path} digest "
                    f"mismatch (expected {entry.expected_sha256!r}, got "
                    f"{actual_sha256!r}) — refuse"
                )
        except BaseException:
            for index in range(len(data)):
                data[index] = 0
            raise
        return data, actual_sha256, digest_pinned

    def _resolve_and_verify_contained(self, scope: str, entry_file: str) -> Path:
        """Resolve ``root_dir / entry_file`` and refuse if it escapes ``root_dir``."""
        candidate = self._root_dir / entry_file
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise CustodyLoadRefused(
                f"FileCustody.load: scope {scope!r} file {candidate} does "
                "not exist — refuse"
            ) from exc
        if (
            resolved != self._resolved_root
            and self._resolved_root not in resolved.parents
        ):
            raise CustodyManifestError(
                f"FileCustody.load: scope {scope!r} file {entry_file!r} "
                f"resolves to {resolved}, which escapes custody root "
                f"{self._resolved_root} — refuse (design #40 D4.1, MEDIUM-1 "
                "path-escape guard; a manifest may not name a location "
                "outside its own custody directory, symlink or not)"
            )
        if not resolved.is_file():
            raise CustodyLoadRefused(
                f"FileCustody.load: scope {scope!r} file {resolved} exists "
                "but is not a regular file — refuse"
            )
        return resolved
