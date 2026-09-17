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
경로 이탈 (MEDIUM-1) Two layers, added 2026-09-08 (independent review
                    reproduced an absolute path, a ``../`` value, and a
                    symlink escaping ``root_dir`` all loading successfully
                    and being recorded as ``CUSTODY_LOAD`` evidence):
                    (1) :meth:`_ScopeManifestEntry._file_must_be_relative_
                    and_contained` rejects an absolute or ``..``-containing
                    ``file`` string at manifest-parse time
                    (:class:`CustodyManifestError`); (2)
                    :meth:`FileCustody._resolve_and_verify_contained`
                    resolves the joined path (following symlinks) and
                    refuses (:class:`CustodyManifestError`) unless the
                    RESOLVED path is ``root_dir`` itself or a descendant —
                    the layer that actually closes a symlink escape, since
                    layer (1) never touches the filesystem.
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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
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

#: The Phase 2 three scopes (design #40 D4.1 line 111) PLUS the two Phase 4 KIS MOCK stock
#: order-verification scopes (TOS KIS MOCK transport plan T2 lane C —
#: docs/plans/2026-09-10-tos-kis-mock-transport-plan.md §2 decision 4). ``order.*`` — and every
#: futures-REAL scope name — is deliberately absent and always will be (root CLAUDE.md
#: non-negotiable rule: the real futures account is never funded with margin). ``kis_mock.account``
#: is likewise deliberately absent: the KIS account number is NOT a custody credential in this
#: design — it is the sealed outbound ``account`` coordinate, read directly off the
#: :class:`~tos.egressgw.SendSeal` (review F2 — see
#: :mod:`tos_runtime.transport.kis_mock.codec`'s own module docstring). This set is a
#: Python-level constant, not manifest-driven — a manifest cannot grant a scope this module does
#: not provision by simply declaring it.
PROVISIONED_SCOPES: frozenset[str] = frozenset(
    {
        "read.principal",
        "evidence.key",
        "replay.params",
        "kis_mock.app_key",
        "kis_mock.app_secret",
    }
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
    #: outside its own custody directory). Validated at parse time
    #: (:meth:`_file_must_be_relative_and_contained`, 2026-09-08
    #: independent-review MEDIUM-1) AND re-checked at load time against the
    #: RESOLVED filesystem path (:meth:`FileCustody.load`), since a
    #: string-level check alone cannot catch a symlink whose target escapes
    #: the custody root even though its own path string looks contained.
    file: str
    #: The scope's own, distinct principal string (ADR-002-013 :267-269 —
    #: no two scopes may share one).
    principal: str
    #: The expected sha256 hex digest of the file's bytes, or ``None``
    #: (named-TBD — digest pinning not yet approved for this scope; see
    #: :meth:`FileCustody.load`'s "digest 미고정" evidence note).
    expected_sha256: str | None = None

    @field_validator("file")
    @classmethod
    def _file_must_be_relative_and_contained(cls, value: str) -> str:
        """Reject an absolute path or any ``..`` component (MEDIUM-1 fix).

        String-level only — this is the FIRST of two layers, catching the
        common/obvious cases at manifest-parse time so a malformed manifest
        never even reaches :class:`FileCustody`. The SECOND layer
        (:meth:`FileCustody.load`'s ``resolve(strict=True)`` + containment
        check) is what actually closes the vulnerability for a symlink,
        since a symlink's own path string can look perfectly relative and
        contained while its resolved target is not — this validator cannot
        detect that (no filesystem access happens during manifest parsing).
        """
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


def _read_into_bytearray(path: Path) -> bytearray:
    """Read ``path``'s full contents into a fresh, mutable ``bytearray``.

    **2026-09-08 independent-review LOW-2.** ``path.read_bytes()`` (the
    pre-fix code) returns an immutable ``bytes`` object — Python has no way
    to zero an immutable object's backing memory in place, so that copy of
    the secret would sit in memory, unzeroable by anyone, for as long as
    the garbage collector happens to keep it alive, EVEN THOUGH
    :class:`~tos_runtime.custody.ports.CredentialHandle` faithfully zeroes
    its own (separate, copied-from-``bytes``) ``bytearray`` on
    :meth:`~tos_runtime.custody.ports.CredentialHandle.close`. This function
    instead pre-allocates a zero-filled ``bytearray`` sized from
    ``path.stat().st_size`` and reads directly into it with
    ``io.RawIOBase.readinto`` — no immutable ``bytes`` object is ever
    created on this path, so the ``bytearray`` this function returns (which
    :meth:`FileCustody.load` hands, without copying again, straight to the
    ``CredentialHandle`` it constructs — see that class's own "single-copy
    ownership" docstring note) is the ONE and ONLY copy of the secret that
    ever exists in memory, and closing the resulting handle is genuinely
    the end of its lifetime.

    Args:
        path: The file to read.

    Returns:
        A ``bytearray`` containing exactly the file's bytes.

    Raises:
        CustodyLoadRefused: The file's size changed between the initial
            ``stat()`` and the read completing (a concurrent writer) — the
            already-read partial buffer is zeroed before this raises, since
            it may already hold real secret bytes.
    """
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
    """The Phase 2 ``CredentialCustody`` implementation: scoped files under one
    directory, gated by mode/owner/label/digest checks (design #40 D4.1).

    Construction is where the manifest-level checks happen (parse + the
    environment-label boot-refusal gate) — see the module docstring's
    fault-contract table for why those two are one-time, not per-``load()``.

    **Root operation is impossible by construction.** :func:`verify_file_
    mode_and_owner`'s owner sub-check requires BOTH the file's real owner
    AND the calling process's own uid (``getuid()``) to equal
    ``expected_owner_uid`` — never ``0`` (root) unless ``expected_owner_uid``
    was itself configured as ``0``, which nothing in this class does for
    the caller. Running this process as root with a non-zero
    ``expected_owner_uid`` therefore refuses every single load: root's own
    ``getuid()`` is ``0``, which can never equal a non-zero
    ``expected_owner_uid``, so the owner sub-check fails unconditionally.
    This is a DELIBERATE deployment constraint (custody is scoped to one
    non-root service principal per environment, design #40 D4.1's "환경
    격리") — not a bug, and not something a future change should relax by,
    say, special-casing ``getuid() == 0`` to bypass the check.
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
        # Resolved once here (not per-``load()`` call): ``CustodyManifest.load``
        # just above already proved ``root_dir`` exists (it read a file
        # inside it), so this ``resolve(strict=True)`` cannot itself be the
        # site of a "root_dir missing" refusal — that's the manifest-load
        # failure's job. Cached as the containment boundary every
        # :meth:`load` call checks a scope's resolved file against
        # (2026-09-08 independent-review MEDIUM-1).
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
        """Load the credential bound to ``scope`` (design #40 D4.1).

        Pre-load checks run in this exact order, each fail-closed (module
        docstring's fault-contract table); see :meth:`_verify_and_resolve`
        (checks 1-4) and :meth:`_read_and_verify_digest` (check 5) for the
        full per-check detail this docstring only summarizes:

        1. ``scope`` is one of :data:`PROVISIONED_SCOPES`.
        2. The manifest actually configures ``scope``.
        3. The scope's file exists AND, once resolved (symlinks followed),
           lies inside ``root_dir`` (2026-09-08 independent-review
           MEDIUM-1).
        4. The file's mode is exactly ``0o600`` AND its owner (and the
           calling process's own uid) equal ``expected_owner_uid``.
        5. If the manifest pins ``expected_sha256`` for this scope, the
           file's actual sha256 matches it exactly; a ``None`` pin skips
           this check and the evidence record instead carries a "digest
           미고정" note.

        **Precisely which checks run before the file is ever opened
        (2026-09-08 independent-review LOW-1).** Checks 1-4 — entirely
        :meth:`_verify_and_resolve`'s job — run and must ALL pass before
        ``path.open()`` is ever called; a scope refused at any of those
        four never has its file's contents touched (see
        ``test_mode_0644_refuses_before_ever_opening_the_file``, which
        proves this by making ``open`` itself raise). Check 5 is different
        in kind: :meth:`_read_and_verify_digest` applies it to bytes it has
        ALREADY read — a mismatch there still zeroes those bytes before the
        refusal propagates (2026-09-08 independent-review LOW-2), but the
        file WAS opened and read by that point regardless. Only once check
        5 also passes does this method append an evidence record (secret-
        free — only ``principal_id``/``scope``/``file_sha256``/
        ``digest_pinned``) and return a :class:`CredentialHandle` that
        takes ownership of those same, already-read bytes (no second copy —
        see :class:`~tos_runtime.custody.ports.CredentialHandle`'s own
        docstring).

        Args:
            scope: The scope to load.

        Returns:
            A :class:`CredentialHandle` wrapping the file's bytes.

        Raises:
            CustodyScopeNotProvisioned: ``scope`` is not in
                :data:`PROVISIONED_SCOPES`.
            CustodyLoadRefused: Any other pre-load check fails.
        """
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
        """Return ``scope``'s own manifest-declared ``principal`` — manifest-only, zero secret
        I/O (TOS KIS MOCK transport plan T2 lane C — the custody-principal consistency check,
        docs/plans/2026-09-10-tos-kis-mock-transport-plan.md §2 decision 4).

        This is deliberately NOT a ``load()`` call: it never opens, reads, or hands back the
        scope's own credential file/bytes — only the already-parsed manifest entry's
        ``principal`` string, which is not itself a secret (module docstring's fault-contract
        table already treats ``principal_id`` as a non-secret evidence field). A caller that
        needs to prove "this custody scope's principal matches that broker scope's principal"
        (e.g. :mod:`tos_runtime.compose._transport_wiring`) can do so without ever loading the
        credential.

        Args:
            scope: The scope to look up.

        Returns:
            The manifest entry's own ``principal`` string.

        Raises:
            CustodyScopeNotProvisioned: ``scope`` is not in :data:`PROVISIONED_SCOPES`.
            CustodyLoadRefused: The manifest does not configure ``scope``.
        """
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
        """:meth:`load`'s checks 1-4 — everything before the file is opened.

        Split out of :meth:`load` itself (2026-09-08, size-budget decompose)
        so each method stays under the size budget while the documented
        check order and every existing test stay unchanged — this is pure
        extraction, no behavioural change.

        Args:
            scope: The scope to load.

        Returns:
            The ``(resolved_path, manifest_entry)`` pair for ``scope``, once
            all four checks have passed.

        Raises:
            CustodyScopeNotProvisioned: ``scope`` is not in
                :data:`PROVISIONED_SCOPES` (check 1).
            CustodyLoadRefused: The manifest does not configure ``scope``
                (check 2), the file does not exist (check 3), or the
                mode/owner gate fails (check 4).
            CustodyManifestError: The resolved path escapes ``root_dir``
                (check 3, MEDIUM-1).
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
        path = self._resolve_and_verify_contained(scope, entry.file)
        verify_file_mode_and_owner(
            path, expected_owner_uid=self._expected_owner_uid, getuid=self._getuid
        )
        return path, entry

    def _read_and_verify_digest(
        self, scope: str, path: Path, entry: _ScopeManifestEntry
    ) -> tuple[bytearray, str, bool]:
        """:meth:`load`'s check 5 — read the file and verify a pinned digest.

        Split out of :meth:`load` itself (2026-09-08, size-budget
        decompose) — pure extraction alongside :meth:`_verify_and_resolve`,
        no behavioural change. This is the ONLY part of the load path that
        opens the file (checks 1-4 in :meth:`_verify_and_resolve` never do).

        Args:
            scope: The scope being loaded (for the error message only).
            path: The resolved, already mode/owner-verified path
                (:meth:`_verify_and_resolve`'s return).
            entry: That same call's manifest entry.

        Returns:
            ``(data, actual_sha256, digest_pinned)`` — ``data`` is the
            file's bytes in a fresh, mutable ``bytearray`` (2026-09-08
            independent-review LOW-2 — never an immutable ``bytes`` copy);
            ``digest_pinned`` is whether ``entry.expected_sha256`` was set.

        Raises:
            CustodyLoadRefused: The file changed size mid-read
                (:func:`_read_into_bytearray`), or a pinned digest does not
                match — either way, ``data`` is zeroed before this
                propagates (LOW-2's "no exit path leaves an unzeroed
                already-read copy" discipline).
        """
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
        """Resolve ``root_dir / entry_file`` and refuse if it escapes ``root_dir``.

        **2026-09-08 independent-review MEDIUM-1.** The manifest-level
        validator (:meth:`_ScopeManifestEntry._file_must_be_relative_and_
        contained`) rejects an absolute path or a ``..`` component in the
        RAW string, but a raw-string check alone cannot catch a SYMLINK
        whose own path string looks perfectly relative and contained while
        its resolved target is not (e.g. ``root_dir/read.principal`` being a
        symlink to ``/etc/shadow``) — the review reproduced exactly this
        gap (and a plain absolute path, and a ``../`` value) actually
        loading a file outside ``root_dir`` and being recorded as a
        successful ``CUSTODY_LOAD``. This method is the second, filesystem-
        aware layer that closes it: it resolves symlinks with
        ``Path.resolve(strict=True)`` (raising if any component in the
        chain does not exist, converted below into the same "does not
        exist" refusal the pre-fix code gave for a missing file) and then
        requires the resolved path to be ``root_dir`` itself or a
        descendant of it — never merely "under the same parent" or any
        other looser containment test.

        Args:
            scope: The scope being loaded (for the error message only).
            entry_file: The manifest entry's own ``file`` value (relative
                to ``root_dir`` by the validator's contract, but this
                method does not trust that contract alone — see above).

        Returns:
            The resolved, contained :class:`~pathlib.Path`.

        Raises:
            CustodyLoadRefused: The path (or a component of it) does not
                exist on disk.
            CustodyManifestError: The resolved path is not ``root_dir`` or a
                descendant of it — a path-escape attempt, symlink or not.
        """
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
