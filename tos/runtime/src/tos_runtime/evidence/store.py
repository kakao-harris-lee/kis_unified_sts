"""The durable, append-only, chained Evidence Store (design #40 D3, §2 item 1).

Implements the kernel's pure D3 seams over a single sqlite3 file: scrubbing
(:func:`tos.evidence.scrub.scrub_secret_fields`), canonical digesting
(:mod:`tos.canonical`'s EV-L1 provisional scheme — no production
canonicalization scheme has been registered yet; see the module-level
``_CANONICALIZATION_VERSION`` note), HMAC chaining
(:class:`tos.evidence.chain.Sha256HmacChainScheme` /
:func:`tos.evidence.chain.verify_chain`), and the append receipt contract
(:class:`tos.evidence.EvidenceAppendReceipt` — never constructed except after
a durable commit).

Fault-contract table (design #40 §5 lane L / slice plan §2 "장애 계약";
column = how THIS module satisfies it):

=======  ============================================================
Contract  How :class:`SqliteEvidenceStore` satisfies it
=======  ============================================================
②        ``seq`` is the sqlite ``PRIMARY KEY`` on ``entries`` — a caller
         cannot cause two rows to share one ``seq``; this module never
         accepts a caller-supplied ``seq`` in the first place (allocated
         internally from ``MAX(seq) + 1`` inside the same locked
         transaction as the insert).
④        ``append()`` writes inside ``BEGIN IMMEDIATE`` ... ``COMMIT``.
         An injectable ``crash_hook`` (test-only) can raise
         :class:`InjectedCrash` at ``"before_commit"`` (caught, the
         transaction is rolled back, the row never exists) or
         ``"after_commit_before_receipt"`` (the row is already durably
         committed and chain-consistent; only the receipt's return to
         the caller is what never happens) — modelling a process death
         at exactly those two points, since a real ``os._exit`` /
         subprocess crash-injection harness (the ``tests/tos_l3``
         pattern) is unavailable here: ``subprocess`` is firewall-
         forbidden in runtime scope (``tools/tos_firewall_check.py``
         R1). Reopening a fresh :class:`SqliteEvidenceStore` on the same
         path after either crash point observes exactly the disjunction
         the contract requires: "항목 부재 또는 체인 정합".
⑤        :meth:`verify` re-derives every link with
         :func:`tos.evidence.chain.verify_chain`, which is fail-closed
         (never silently skips a link) and raises
         :class:`~tos.evidence.chain.ArtifactIntegrityError`-free — it
         returns ``False`` on any mismatch; this module raises
         :class:`EvidenceCorruption` when :meth:`verify` is asked to
         raise instead of report (see :meth:`verify_or_raise`). Plain
         ``bool`` ``verify()`` is vacuously ``True`` on an empty store
         (:func:`verify_chain`'s own "nothing to falsify" contract) —
         :meth:`verify_detailed` (2026-09-08 independent-review LOW-4)
         returns a :class:`ChainVerification` so a caller can tell
         "0 links, vacuously ok" apart from "N links, genuinely
         verified" instead of collapsing both to the same ``True``.
⑦        Any sqlite failure during the transaction (locked file,
         read-only filesystem, disk full) propagates as the underlying
         :class:`sqlite3.Error` from inside the ``try``/``except`` that
         guards ``COMMIT``; the ``except`` clause always issues
         ``ROLLBACK`` first, so a partial write never becomes a partial
         commit. No :class:`~tos.evidence.EvidenceAppendReceipt` is
         constructed on any exception path. If ``ROLLBACK`` ITSELF
         raises (2026-09-08 independent-review LOW-6), that rollback
         failure is caught, attached to the ORIGINAL commit-path
         exception via :meth:`BaseException.add_note`, and the
         ORIGINAL exception is what propagates — never silently
         replaced by the rollback failure's own (possibly unrelated)
         type.
=======  ============================================================

**Canonicalization version note.** Design #40 D3.1 fixes only the *chain*
scheme's new version (``ev-l2-sha256-hmac-chain-1``, :mod:`tos.evidence.chain`);
no Phase-2 *canonicalization* scheme has been registered in the kernel. This
module therefore reuses the kernel's one existing registered scheme,
:data:`tos.canonical.EV_L1_PROVISIONAL_VERSION`
(:class:`tos.canonical.EVL1ProvisionalCanonicalizer`), for ``entry_digest`` —
consistent with every other kernel package's own "항목 digest = SHA-256(정본
바이트)" convention (:mod:`tos.evidence.chain` module docstring) rather than
inventing a second, parallel canonical-JSON encoder. The version is
constructor-injected (``canonicalization_version``) so a future PR that
registers a production scheme needs no change here — only a different
injected version string.

**Append-only, mechanically.** ``entries`` carries ``BEFORE UPDATE``/
``BEFORE DELETE`` triggers that ``RAISE(ABORT, ...)`` unconditionally — the
invariant is unrepresentable through this store's own sqlite handle, not
merely undocumented.

Firewall: stdlib (``sqlite3``, ``json``, ``time``) + ``pydantic`` +
``tos.canonical``/``tos.evidence``/``tos.workload`` + ``tos_runtime.evidence``
only (R1 allowlist).
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.evidence import (
    ChainedEntry,
    EvidenceAppendReceipt,
    Sha256HmacChainScheme,
    scrub_secret_fields,
    verify_chain,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence import outbox as _outbox

__all__ = [
    "ChainVerification",
    "EvidenceCorruption",
    "InjectedCrash",
    "KeyProvider",
    "SqliteEvidenceStore",
]

#: The genesis commitment every fresh chain folds from — matches
#: :mod:`tos.evidence.chain`'s own (private) ``_CHAIN_GENESIS`` convention.
_CHAIN_GENESIS = ""

#: See the module docstring's "canonicalization version note".
_CANONICALIZATION_VERSION = EV_L1_PROVISIONAL_VERSION

_CREATE_ENTRIES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    seq INTEGER PRIMARY KEY,
    segment_id TEXT,
    kind TEXT NOT NULL,
    record_class TEXT NOT NULL,
    runtime_identity_json TEXT,
    payload_json TEXT NOT NULL,
    entry_digest TEXT NOT NULL,
    chain_digest TEXT NOT NULL,
    key_generation INTEGER NOT NULL,
    appended_at_monotonic_ns INTEGER NOT NULL
)
"""

_CREATE_NO_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS entries_no_update
BEFORE UPDATE ON entries
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — UPDATE forbidden');
END
"""

_CREATE_NO_DELETE_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS entries_no_delete
BEFORE DELETE ON entries
BEGIN
    SELECT RAISE(ABORT, 'tos_runtime evidence store: entries is append-only — DELETE forbidden');
END
"""


class EvidenceCorruption(RuntimeError):
    """Raised by :meth:`SqliteEvidenceStore.verify_or_raise` on chain mismatch (contract ⑤)."""


class InjectedCrash(RuntimeError):
    """Raised by a test-supplied ``crash_hook`` to simulate a process death (contract ④).

    Never raised by production code paths — this module only *calls* the
    injected hook; the hook itself decides whether, and with what, to raise.
    """


class ChainVerification(BaseModel):
    """The detailed result of :meth:`SqliteEvidenceStore.verify_detailed` (contract ⑤).

    A plain ``bool`` (:meth:`SqliteEvidenceStore.verify`) cannot distinguish
    "0 links, vacuously ``True``" (an empty store — :func:`verify_chain`'s
    own "nothing to falsify" contract) from "N links, genuinely re-derived" —
    both collapse to the same ``True``. This record keeps ``ok`` (so a
    caller that only wants the boolean still gets it) but ALSO reports how
    many links were actually re-verified, so the two cases stay
    distinguishable (2026-09-08 independent-review LOW-4).

    ``verified_links`` is fail-closed on failure: :func:`verify_chain` is
    "the WHOLE chain fails, never partially" (its own docstring) — it does
    not report which link broke or how far it got — so this record never
    overclaims a partial count when ``ok`` is ``False``; ``verified_links``
    is ``0`` in that case, not "however many links exist".
    """

    model_config = ConfigDict(frozen=True)

    ok: bool
    verified_links: int
    last_seq: int | None


@runtime_checkable
class KeyProvider(Protocol):
    """The injected source of the store's initial signing key (design #40 D4).

    Custody of the real key bytes is ``tos_runtime.custody`` territory
    (design #40 D4, sequence item 4 — out of this slice's scope); this
    Protocol is the seam a future custody implementation satisfies. Tests
    inject a fixed-byte double. Consulted exactly once, at construction —
    :meth:`SqliteEvidenceStore.rotate` is the ongoing rotation mechanism
    thereafter (explicit ``new_generation``/``new_key`` arguments, not a
    second ``KeyProvider`` call).
    """

    def current(self) -> tuple[int, bytes]:
        """Return ``(key_generation, key_bytes)`` for the initial signing key."""
        ...


class _EntryRow(NamedTuple):
    """One raw ``entries`` row, meta fields only (no payload) — retention's read shape."""

    seq: int
    segment_id: str | None
    kind: str
    record_class: str
    key_generation: int
    appended_at_monotonic_ns: int
    entry_digest: str
    chain_digest: str


class SqliteEvidenceStore:
    """The append-only, HMAC-chained, durable evidence log (design #40 D3.1).

    One sqlite3 file (``journal_mode=WAL``, ``synchronous=FULL``). Every
    write happens inside ``BEGIN IMMEDIATE`` ... ``COMMIT`` so a concurrent
    writer is serialized rather than corrupting the file (SQLite's own
    reserved-lock semantics), and every failure path issues ``ROLLBACK``
    before propagating (contract ⑦).
    """

    def __init__(
        self,
        path: Path,
        *,
        key_provider: KeyProvider,
        secret_keys: frozenset[str] = frozenset(),
        canonicalization_version: str = _CANONICALIZATION_VERSION,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        crash_hook: Callable[[str], None] | None = None,
    ) -> None:
        """Open (or create) the evidence store at ``path``.

        Args:
            path: The sqlite file path. Parent directory must already exist
                (this module never creates directories — a runtime hermetic
                test's ``tmp_path`` already does).
            key_provider: Supplies the initial ``(key_generation, key_bytes)``
                pair, consulted exactly once here.
            secret_keys: Field names :func:`~tos.evidence.scrub_secret_fields`
                masks, at any depth, before a payload is digested or stored.
                Never a hard-coded literal set (design #40 D3-d) — always
                caller-injected.
            canonicalization_version: The registered
                :mod:`tos.canonical` scheme version used to compute
                ``entry_digest`` (see module docstring).
            monotonic_ns: Injected monotonic-clock callable for
                ``appended_at_monotonic_ns`` — never ``time.monotonic_ns``
                read directly inline, so tests can inject a fake source.
            crash_hook: Test-only crash-injection callable (contract ④); see
                the module docstring's fault-contract table. ``None`` in
                production.
        """
        self.path = path
        self._secret_keys = secret_keys
        self._canon_scheme = get_scheme(canonicalization_version)
        self._monotonic_ns = monotonic_ns
        self._crash_hook = crash_hook
        self._conn = sqlite3.connect(str(path), isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute(_CREATE_ENTRIES_TABLE_SQL)
        self._conn.execute(_CREATE_NO_UPDATE_TRIGGER_SQL)
        self._conn.execute(_CREATE_NO_DELETE_TRIGGER_SQL)
        _outbox.create_outbox_table(self._conn)
        key_generation, key = key_provider.current()
        self._scheme = Sha256HmacChainScheme(key=key, key_generation=key_generation)

    @property
    def connection(self) -> sqlite3.Connection:
        """The live sqlite3 connection — :mod:`tos_runtime.evidence.backup` reuses it."""
        return self._conn

    @property
    def key_generation(self) -> int:
        """The key generation currently signing new appends."""
        return self._scheme.key_generation

    def close(self) -> None:
        """Close the underlying sqlite3 connection."""
        self._conn.close()

    def _read_tail(self) -> tuple[int, str]:
        """Return ``(next_seq, last_chain_digest)``, read fresh from disk every call.

        Deliberately uncached (never a Python-side running counter) so a
        crash-injected instance and a freshly reopened instance observe
        identical behaviour — the durable table is the only source of
        truth for "what has already been committed".
        """
        row = self._conn.execute(
            "SELECT seq, chain_digest FROM entries ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return 0, _CHAIN_GENESIS
        last_seq, last_chain_digest = row
        return last_seq + 1, last_chain_digest

    def scrub_payload(
        self, payload: Mapping[str, object]
    ) -> tuple[dict[str, object], tuple[str, ...]]:
        """Scrub ``payload`` with this store's OWN configured ``secret_keys``.

        Exposed so a caller writing the SAME record to a second, non-sqlite
        path (e.g. :mod:`tos_runtime.evidence.emergency`'s JSONL log) can
        obtain byte-identical scrubbed content without re-implementing or
        duplicating the secret-field list — :meth:`append` calls this exact
        function internally too, so scrubbing a payload here and then
        passing the ALREADY-scrubbed result into :meth:`append` is safe:
        :func:`~tos.evidence.scrub_secret_fields` is idempotent (masking an
        already-``"***REDACTED***"`` value under the same key re-masks it to
        the identical value), so nothing is double-redacted or corrupted.

        Args:
            payload: The record's own fields, prior to scrubbing.

        Returns:
            The ``(scrubbed_payload, masked_keys)`` pair
            :func:`~tos.evidence.scrub_secret_fields` returns.
        """
        return scrub_secret_fields(payload, self._secret_keys)

    def _compute_entry_digest(
        self,
        *,
        kind: str,
        record_class: str,
        segment_id: str | None,
        scrubbed_payload: Mapping[str, object],
        masked_keys: Sequence[str],
        runtime_identity: RuntimeIdentity | None,
    ) -> str:
        """Digest the covered content over canonical bytes (module docstring)."""
        covered: dict[str, object] = {
            "kind": kind,
            "record_class": record_class,
            "segment_id": segment_id,
            "payload": dict(scrubbed_payload),
            "masked_keys": list(masked_keys),
            "runtime_identity": (
                runtime_identity.model_dump(mode="json")
                if runtime_identity is not None
                else None
            ),
        }
        return self._canon_scheme.compute_digest(covered)

    def append(
        self,
        payload: Mapping[str, object],
        *,
        kind: str,
        record_class: str,
        segment_id: str | None = None,
        runtime_identity: RuntimeIdentity | None = None,
        outbox_targets: Sequence[str] = (),
    ) -> EvidenceAppendReceipt:
        """Durably append one scrubbed, digested, chained entry (design #40 D3.1).

        Order (module docstring / design #40 §D3.1 line 88): scrub -> canonical
        digest -> chain link -> ``INSERT`` (+ same-transaction outbox enqueue)
        -> ``COMMIT`` -> receipt. No :class:`~tos.evidence.EvidenceAppendReceipt`
        is constructed on any failure path.

        Args:
            payload: The record's own fields, prior to scrubbing.
            kind: The record kind (caller vocabulary).
            record_class: The retention/durability class label.
            segment_id: An optional caller-supplied grouping label — this
                slice does not itself implement a segment-boundary policy
                (time- or count-based rollover), so a caller either omits it
                (implicit single segment, ``None``) or manages segmentation
                itself.
            runtime_identity: The issuing process's identity (design #40 D4),
                bound into the digest so tampering with it is detected too.
            outbox_targets: Target names to enqueue for at-least-once
                delivery, in the SAME transaction as this append.

        Returns:
            The commit receipt — ``durable=True`` by construction, only ever
            returned after ``COMMIT`` succeeds.
        """
        return self._append_with_scheme(
            payload,
            kind=kind,
            record_class=record_class,
            segment_id=segment_id,
            runtime_identity=runtime_identity,
            outbox_targets=outbox_targets,
            scheme=self._scheme,
        )

    def _append_with_scheme(
        self,
        payload: Mapping[str, object],
        *,
        kind: str,
        record_class: str,
        segment_id: str | None,
        runtime_identity: RuntimeIdentity | None,
        outbox_targets: Sequence[str],
        scheme: Sha256HmacChainScheme,
    ) -> EvidenceAppendReceipt:
        """The whole durable-append body, signed under an EXPLICIT ``scheme``.

        :meth:`append` always passes ``self._scheme`` (the store's current,
        already-committed-to generation). :meth:`rotate` is the one other
        caller: it passes a LOCAL, not-yet-assigned scheme so the
        rotation-commit entry is signed under the new generation while
        ``self._scheme`` itself stays untouched until that append durably
        succeeds — see :meth:`rotate`'s own docstring for why this
        parameterization is what makes rotation atomic.
        """
        scrubbed_payload, masked_keys = scrub_secret_fields(payload, self._secret_keys)
        entry_digest = self._compute_entry_digest(
            kind=kind,
            record_class=record_class,
            segment_id=segment_id,
            scrubbed_payload=scrubbed_payload,
            masked_keys=masked_keys,
            runtime_identity=runtime_identity,
        )
        appended_at_ns = self._monotonic_ns()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            next_seq, last_chain_digest = self._read_tail()
            chain_digest = scheme.verify_append(last_chain_digest, (entry_digest,))
            runtime_identity_json = (
                json.dumps(runtime_identity.model_dump(mode="json"), sort_keys=True)
                if runtime_identity is not None
                else None
            )
            payload_json = json.dumps(
                {"payload": scrubbed_payload, "masked_keys": list(masked_keys)},
                sort_keys=True,
                separators=(",", ":"),
            )
            cur = self._conn.execute(
                "INSERT INTO entries (seq, segment_id, kind, record_class, "
                "runtime_identity_json, payload_json, entry_digest, chain_digest, "
                "key_generation, appended_at_monotonic_ns) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    next_seq,
                    segment_id,
                    kind,
                    record_class,
                    runtime_identity_json,
                    payload_json,
                    entry_digest,
                    chain_digest,
                    scheme.key_generation,
                    appended_at_ns,
                ),
            )
            for target in outbox_targets:
                _outbox.enqueue(cur, entry_seq=next_seq, target=target)
            if self._crash_hook is not None:
                self._crash_hook("before_commit")
            self._conn.execute("COMMIT")
        except BaseException as commit_error:
            # LOW-6 (2026-09-08 independent review): if ROLLBACK itself
            # raises, catching it here (rather than letting it propagate
            # unguarded) stops it from REPLACING commit_error as the
            # exception the caller sees. The rollback failure is recorded as
            # a note on the ORIGINAL error instead, and the bare `raise`
            # below re-raises `commit_error` — never the rollback failure —
            # so the root cause always survives, and no receipt is ever
            # constructed on this path either way.
            try:
                self._conn.execute("ROLLBACK")
            except Exception as rollback_error:
                commit_error.add_note(
                    f"ROLLBACK also failed after this error: {rollback_error!r} — "
                    "the original commit-path error above is what propagates; "
                    "this store's on-disk state is not authoritative until "
                    "reopened and independently verified"
                )
            raise
        if self._crash_hook is not None:
            self._crash_hook("after_commit_before_receipt")
        return EvidenceAppendReceipt(
            segment_id=segment_id,
            seq=next_seq,
            chain_digest=chain_digest,
            key_generation=scheme.key_generation,
        )

    def rotate(self, new_generation: int, new_key: bytes) -> EvidenceAppendReceipt:
        """Rotate the signing key: append a rotation-commit entry under the new key.

        **Atomic.** ``self._scheme`` is assigned the new generation ONLY
        after the rotation-commit entry has durably committed and its
        receipt has been built — never before. The new scheme is built
        LOCALLY and passed straight to :meth:`_append_with_scheme` (which
        signs the rotation-commit entry under it), so a failure anywhere in
        that append (the same ``BEGIN IMMEDIATE``/``COMMIT``/``ROLLBACK``
        discipline every other append uses) propagates BEFORE
        ``self._scheme`` is ever touched: the store's generation, its
        ``verify()`` behaviour against the OLD key, and every already-signed
        entry are all left exactly as they were (design #40 D4.1 "겹침 0" —
        no generation is ever live without a committed marker proving it).

        Args:
            new_generation: The new monotonic key-epoch (must be greater
                than the current generation — enforced by
                :class:`~tos.evidence.chain.Sha256HmacChainScheme`'s own
                non-negative-generation construction check plus this
                method's own strictly-increasing check).
            new_key: The new HMAC key bytes.

        Returns:
            The receipt for the rotation-commit entry itself.
        """
        current_generation = self._scheme.key_generation
        if new_generation <= current_generation:
            raise ValueError(
                "SqliteEvidenceStore.rotate requires a strictly increasing "
                f"key_generation (current={current_generation}, "
                f"new={new_generation}) — design #40 D4.1 겹침 0"
            )
        new_scheme = Sha256HmacChainScheme(key=new_key, key_generation=new_generation)
        receipt = self._append_with_scheme(
            {
                "previous_key_generation": current_generation,
                "new_key_generation": new_generation,
            },
            kind="KEY_ROTATION",
            record_class="SYSTEM_KEY_ROTATION",
            segment_id=None,
            runtime_identity=None,
            outbox_targets=(),
            scheme=new_scheme,
        )
        # Only reached after the rotation-commit entry is durably committed —
        # see this method's own docstring on why the assignment happens here
        # and not before the append.
        self._scheme = new_scheme
        return receipt

    def replay(self) -> Iterator[ChainedEntry]:
        """Yield every committed entry, in commit order, for :func:`verify_chain`."""
        cur = self._conn.execute(
            "SELECT entry_digest, key_generation, chain_digest FROM entries ORDER BY seq ASC"
        )
        for entry_digest, key_generation, chain_digest in cur:
            yield ChainedEntry(
                entry_digest=entry_digest,
                key_generation=key_generation,
                chain_digest=chain_digest,
            )

    def verify(self, keys_by_generation: Mapping[int, bytes]) -> bool:
        """Re-verify the whole chain (contract ⑤); ``True`` iff every link re-derives.

        See :meth:`verify_detailed` if the caller needs to tell an empty
        store's vacuous ``True`` apart from a populated chain's genuine
        ``True`` (LOW-4) — this method keeps its original plain-``bool``
        contract unchanged for existing callers.
        """
        return verify_chain(tuple(self.replay()), keys_by_generation)

    def verify_detailed(
        self, keys_by_generation: Mapping[int, bytes]
    ) -> ChainVerification:
        """Like :meth:`verify`, but reports how many links were actually verified.

        Args:
            keys_by_generation: The HMAC keys, keyed by ``key_generation``.

        Returns:
            A :class:`ChainVerification` — ``verified_links`` is the entry
            count when ``ok`` is ``True`` (an empty store is ``ok=True,
            verified_links=0`` — the vacuous case, now visible instead of
            indistinguishable from a real N-link verification) and ``0``
            when ``ok`` is ``False`` (never a partial/overclaimed count —
            see this type's own docstring).
        """
        entries = tuple(self.replay())
        ok = bool(verify_chain(entries, keys_by_generation))
        last_seq, _, _ = self.last_committed()
        return ChainVerification(
            ok=ok, verified_links=len(entries) if ok else 0, last_seq=last_seq
        )

    def verify_or_raise(self, keys_by_generation: Mapping[int, bytes]) -> None:
        """Like :meth:`verify`, but raises :class:`EvidenceCorruption` on mismatch."""
        if not self.verify(keys_by_generation):
            raise EvidenceCorruption(
                "SqliteEvidenceStore.verify_or_raise: chain verification failed "
                f"for {self.path} (contract ⑤ — replay mismatch)"
            )

    def last_committed(self) -> tuple[int | None, str, int | None]:
        """Return ``(last_seq, last_chain_digest, last_key_generation)``.

        ``last_seq``/``last_key_generation`` are ``None`` for an empty store;
        ``last_chain_digest`` is the genesis value in that case. Used by
        :mod:`tos_runtime.evidence.backup` to build a :class:`BackupManifest`.
        """
        row = self._conn.execute(
            "SELECT seq, chain_digest, key_generation FROM entries "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None, _CHAIN_GENESIS, None
        last_seq, last_chain_digest, last_key_generation = row
        return last_seq, last_chain_digest, last_key_generation

    def iter_entry_meta(self) -> Iterator[_EntryRow]:
        """Yield every entry's meta fields (no payload) — :mod:`tos_runtime.evidence.retention`'s read shape."""
        cur = self._conn.execute(
            "SELECT seq, segment_id, kind, record_class, key_generation, "
            "appended_at_monotonic_ns, entry_digest, chain_digest "
            "FROM entries ORDER BY seq ASC"
        )
        for row in cur:
            yield _EntryRow(*row)
