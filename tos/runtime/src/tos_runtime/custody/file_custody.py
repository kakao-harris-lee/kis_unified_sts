"""``FileCustody`` — the Phase 2 :class:`~tos_runtime.custody.ports.CredentialCustody`
implementation (design #40 D4.1, slice plan §2 "레인 N" item 2).

Fault-contract table (slice plan §2 "장애 계약"; column = how THIS module
satisfies it):

=================  ==========================================================
Contract            How :class:`FileCustody` satisfies it
=================  ==========================================================
모드 0644           :func:`verify_file_mode_and_owner` refuses any mode other
                    than exactly ``0o600`` (:class:`CustodyLoadRefused`).
소유자 불일치        Same function additionally refuses unless BOTH the file's
                    real owner and the calling process's own uid
                    (injectable ``getuid``) equal ``expected_owner_uid`` —
                    see that function's own docstring for why the process-uid
                    half exists (hermetic testability without a real
                    ``chown``).
라벨 불일치          Checked once, at :meth:`FileCustody.__init__` — the
                    kernel predicate
                    :func:`tos.workload.environment_label_consistent` compares
                    the runtime's boot-arg ``environment_label`` against the
                    manifest's own label; a mismatch (or either side being
                    absent/blank — the predicate's own fail-closed rule)
                    refuses CONSTRUCTION entirely ("기동 거부", design #40
                    D4.1 line 113), not merely one ``load()`` call.
order 스코프         :meth:`FileCustody.load` raises
                    :class:`~tos_runtime.custody.ports.CustodyScopeNotProvisioned`
                    for any scope outside :data:`PROVISIONED_SCOPES` — checked
                    BEFORE the manifest is even consulted for that scope, so
                    an unprovisioned scope never reaches file-system I/O at
                    all.
부재 파일            :meth:`FileCustody.load` refuses when the manifest omits
                    the scope entirely, or the entry's file does not exist.
evidence 에 비밀 0   The evidence payload :meth:`FileCustody.load` appends
                    carries only ``principal_id``/``scope``/``file_sha256``/
                    ``digest_pinned`` (+ an unpinned-digest note) — never the
                    raw secret bytes — and is passed through
                    :func:`tos.evidence.scrub_secret_fields` as a second-line
                    defense even though none of those field names are
                    expected to collide with a caller's secret-field list.
=================  ==========================================================

Firewall: stdlib (``hashlib``, ``os``, ``pathlib``) + ``pyyaml`` (``yaml``) +
``pydantic`` + ``tos.evidence``/``tos.workload`` + ``tos_runtime.custody`` +
``tos_runtime.evidence`` only (R1 allowlist).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tos.evidence import scrub_secret_fields
from tos.workload import environment_label_consistent

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

#: The manifest's own filename, expected directly inside ``root_dir``.
MANIFEST_FILENAME = "custody.manifest.yaml"

#: Exactly the three scopes Phase 2 provisions (design #40 D4.1 line 111).
#: ``order.*`` — and every other scope name — is deliberately absent: futures
#: REAL is permanently absent (root CLAUDE.md non-negotiable rule) and stock
#: order-scope custody is Phase 4. This set is a Python-level constant, not
#: manifest-driven — a manifest cannot grant a scope Phase 2 does not
#: provision by simply declaring it.
PROVISIONED_SCOPES: frozenset[str] = frozenset(
    {"read.principal", "evidence.key", "replay.params"}
)

#: The exact permission bits a custody-scope file must carry. Compared against
#: ``path.stat().st_mode & 0o777`` — the low nine permission bits only, never
#: the file-type bits stat also carries.
_REQUIRED_MODE = 0o600


class _ScopeManifestEntry(BaseModel):
    """One scope's row in ``custody.manifest.yaml`` — frozen, load-only."""

    model_config = ConfigDict(frozen=True)

    #: Path to the scope's credential file, relative to the manifest's own
    #: directory (never absolute — a manifest does not name a location
    #: outside its own custody directory).
    file: str
    #: The scope's own, distinct principal string (ADR-002-013 :267-269 —
    #: no two scopes may share one).
    principal: str
    #: The expected sha256 hex digest of the file's bytes, or ``None``
    #: (named-TBD — digest pinning not yet approved for this scope; see
    #: :meth:`FileCustody.load`'s "digest 미고정" evidence note).
    expected_sha256: str | None = None


class CustodyManifest(BaseModel):
    """The parsed ``custody.manifest.yaml`` (design #40 D4.1, slice plan §2 item 4)."""

    model_config = ConfigDict(frozen=True)

    #: The environment this custody directory is bound to (``non-live-test``
    #: / ``paper`` / ``restricted-live`` / ``production``, ADR-002-013 :498).
    #: ``None`` is a valid parse (named-TBD) but always fails
    #: :func:`tos.workload.environment_label_consistent` against any runtime
    #: label — construction refuses in that case (fail-closed, never a
    #: vacuous match).
    environment_label: str | None = None
    #: Every configured scope's manifest row, keyed by scope name. A scope in
    #: :data:`PROVISIONED_SCOPES` that is absent here is refused at
    #: ``load()`` time (the manifest not configuring a Phase-2-provisioned
    #: scope is itself a fail-closed condition, not silently skipped).
    scopes: dict[str, _ScopeManifestEntry] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> CustodyManifest:
        """Parse ``path`` — fail-closed on anything but a well-shaped mapping.

        Args:
            path: The ``custody.manifest.yaml`` file.

        Returns:
            The parsed manifest.

        Raises:
            CustodyManifestError: The file does not exist, is not readable,
                does not parse as YAML, does not parse as a mapping, or does
                not validate against this model's shape (e.g. a ``scopes``
                row missing its required ``file``/``principal`` fields).
        """
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
    """Fail-closed mode+owner gate shared by :class:`FileCustody` and
    :class:`~tos_runtime.custody.key_provider.FileKeyProvider` (design #40 D4.1).

    Two independent sub-checks; either one failing is a refusal:

    1. **Mode.** ``path.stat().st_mode & 0o777`` must equal exactly
       :data:`_REQUIRED_MODE` (``0o600``) — not merely "no more permissive
       than 0600"; a stricter mode (e.g. ``0o400``) still refuses, since the
       manifest's own contract is an exact expectation, not an upper bound.
    2. **Owner.** BOTH the file's real owner (``path.stat().st_uid``) and the
       calling process's own uid (``getuid()``) must equal
       ``expected_owner_uid``.

       The ``getuid()`` half exists specifically so an "owner mismatch"
       fault is exercisable hermetically (slice plan §2 "hermetic 주의"): a
       test cannot ``chown`` a ``tmp_path`` file to a different REAL uid
       without root privileges, so it cannot make sub-check 2's file-owner
       half fail on its own. It CAN, however, inject a fake ``getuid``
       callable that returns a uid different from ``expected_owner_uid`` —
       no real ownership change required — and that alone is sufficient to
       trip this function's refusal, since both halves are required to
       match, not just one.

    Args:
        path: The file to check.
        expected_owner_uid: The uid both the file's owner and the calling
            process are expected to be.
        getuid: An ``os.getuid``-shaped callable (no arguments, returns an
            int) — the calling PROCESS's own uid, injectable for tests.

    Raises:
        CustodyLoadRefused: Either sub-check fails.
    """
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


class FileCustody:
    """The Phase 2 ``CredentialCustody`` implementation: scoped files under one
    directory, gated by mode/owner/label/digest checks (design #40 D4.1).

    Construction is where the manifest-level checks happen (parse + the
    environment-label boot-refusal gate) — see the module docstring's
    fault-contract table for why those two are one-time, not per-``load()``.
    """

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
        """Load and validate the custody manifest at ``root_dir``.

        Args:
            root_dir: The custody directory. Must contain
                :data:`MANIFEST_FILENAME` plus each provisioned scope's own
                file (checked lazily, at :meth:`load` time, not here).
            environment_label: This runtime's own boot-argument environment
                label (never read from an environment variable — CLAUDE.md
                "ambient env로 라우팅하지 않는다" / design #40 D1.1 config
                row — always an explicit CLI-sourced value the caller
                passes in).
            expected_owner_uid: The uid every provisioned scope's file (and
                the calling process itself) is expected to be owned by/run
                as — see :func:`verify_file_mode_and_owner`.
            evidence: The durable append port every successful :meth:`load`
                records to (design #40 D3's ``EvidenceAppendPort`` — never
                the concrete
                :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`
                directly, so a test can inject an in-memory double).
            getuid: An ``os.getuid``-shaped callable, injectable for tests.
                Defaults to the real ``os.getuid`` — a syscall wrapper, not
                environment access, and unrelated to the ``os.environ``/
                ``os.getenv`` firewall rule (TOS-FW-C) this codebase forbids
                everywhere, kernel and runtime scope alike.
            secret_field_names: Field names
                :func:`tos.evidence.scrub_secret_fields` masks in the
                evidence payload — a second-line defense; this class's own
                payload never uses any of these key names by construction
                (module docstring's fault-contract table, "evidence 에 비밀
                0" row).

        Raises:
            CustodyManifestError: The manifest is missing, unreadable, not
                YAML, not a mapping, or fails schema validation.
            CustodyLoadRefused: The manifest's own ``environment_label``
                does not byte-exact match ``environment_label`` (or either
                is absent/blank) — construction refuses outright ("기동
                거부").
        """
        self._root_dir = Path(root_dir)
        self._expected_owner_uid = expected_owner_uid
        self._evidence = evidence
        self._getuid = getuid
        self._secret_field_names = secret_field_names

        manifest_path = self._root_dir / MANIFEST_FILENAME
        self._manifest = CustodyManifest.load(manifest_path)
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
        """Load the credential bound to ``scope`` (design #40 D4.1).

        Pre-load checks run in this exact order, each fail-closed (module
        docstring's fault-contract table):

        1. ``scope`` is one of :data:`PROVISIONED_SCOPES` — else
           :class:`~tos_runtime.custody.ports.CustodyScopeNotProvisioned`.
        2. The manifest actually configures ``scope`` — else
           :class:`~tos_runtime.custody.ports.CustodyLoadRefused`.
        3. The scope's file exists.
        4. The file's mode is exactly ``0o600`` AND its owner (and the
           calling process's own uid) equal ``expected_owner_uid``
           (:func:`verify_file_mode_and_owner`).
        5. If the manifest pins ``expected_sha256`` for this scope, the
           file's actual sha256 matches it exactly; a ``None`` pin skips
           this check and the evidence record instead carries a "digest
           미고정" note.

        Only after all of the above succeed does this method read the file's
        bytes, append an evidence record (secret-free — only
        ``principal_id``/``scope``/``file_sha256``/``digest_pinned``), and
        return a :class:`CredentialHandle`.

        Args:
            scope: The scope to load.

        Returns:
            A :class:`CredentialHandle` wrapping the file's bytes.

        Raises:
            CustodyScopeNotProvisioned: ``scope`` is not in
                :data:`PROVISIONED_SCOPES`.
            CustodyLoadRefused: Any other pre-load check fails.
        """
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
        path = self._root_dir / entry.file
        if not path.is_file():
            raise CustodyLoadRefused(
                f"FileCustody.load: scope {scope!r} file {path} does not "
                "exist — refuse"
            )
        verify_file_mode_and_owner(
            path, expected_owner_uid=self._expected_owner_uid, getuid=self._getuid
        )
        data = path.read_bytes()
        actual_sha256 = hashlib.sha256(data).hexdigest()
        digest_pinned = entry.expected_sha256 is not None
        if digest_pinned and actual_sha256 != entry.expected_sha256:
            raise CustodyLoadRefused(
                f"FileCustody.load: scope {scope!r} file {path} digest "
                f"mismatch (expected {entry.expected_sha256!r}, got "
                f"{actual_sha256!r}) — refuse"
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
