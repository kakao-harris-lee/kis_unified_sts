"""Evidence-signing key rotation: deny-first continuity + explicit workflow
(design #40 D4.1 "키 회전", TOS Phase 5 W4 plan §2 decision 4).

**The gap this module closes.** :class:`~tos_runtime.custody.key_provider.FileKeyProvider`'s
``current()`` returns whatever the HIGHEST ``evidence.key.<generation>`` file on disk happens to
be, with no memory of what a durable :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` has
actually committed to so far. Left alone, an operator who merely places a new generation's key
file under the custody root causes the very next boot to sign with it — with no ``KEY_ROTATION``
evidence entry and no RCL commit ever recorded — which is exactly the "겹침" (overlap) design #40
D4.1 forbids: a generation must never sign anything before a committed marker proves the
transition. This module supplies the missing gate (:func:`verify_key_generation_continuity`,
consulted by :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s own constructor, BEFORE
the first append and BEFORE a signing key is even selected) and the one sanctioned way past it
(:func:`rotate_evidence_key`, an explicit, operator-invoked CLI-context operation — never
something a boot path calls on the caller's behalf).

**Two records, not one.** Design #40 D4.1 requires a rotation to leave marks in BOTH durable
stores: the evidence store's own ``KEY_ROTATION`` entry (already implemented,
:meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.rotate`) and an RCL commit-log entry
recording the same transition. :func:`rotate_evidence_key` performs the evidence-side rotation
FIRST (it is the one that actually changes what signs future entries) and the RCL commit SECOND;
if the RCL side fails for any reason, the evidence side has ALREADY rotated — this module never
pretends otherwise. It records a second evidence entry
(``KEY_ROTATION_RCL_UNRECORDED``) and returns :attr:`RotationOutcome.ROTATED_RCL_UNRECORDED`
rather than silently reporting success or (worse) claiming nothing happened when the signing key
plainly did change (a mutation-lens "M8" case: reporting "not rotated" when evidence already
rotated is itself a fault this module refuses to introduce).

**Why the RCL entry's ``kind`` is ``None``, not a new ``CommandType`` member.** ``tos.rcl``'s
``CommandType`` is a closed KERNEL vocabulary (``StrEnum``) — :class:`~tos.rcl.CommitEntry.kind`
only accepts one of its existing members or ``None``; the whole point of TOS Phase 5 W4's "커널
diff 0" rule is that this workload-level concern (evidence-signing key rotation, not an order,
reservation, or authority transition) has no kernel command type to reuse without inventing a
semantically wrong one. This module therefore leaves ``kind=None`` and puts the machine-readable
type marker (``"type": "KEY_ROTATION_COMMIT"``) inside the entry's own ``payload_json`` instead —
a deliberate, documented deviation from a literal ``kind="KEY_ROTATION_COMMIT"`` reading, since a
plain string cannot satisfy ``CommitEntry.kind``'s ``CommandType | None`` type at all
(``append_cas`` unconditionally does ``entry.kind.value`` — a bare ``str`` has no ``.value`` and
would raise ``AttributeError`` before ever reaching sqlite).

**Import-cycle avoidance — no ``tos_runtime`` sibling import at all.**
:class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s own constructor calls
:func:`verify_key_generation_continuity` at construction time, so this module is on the import
path of ``tos_runtime.evidence.store`` itself. Both ``tos_runtime.custody`` (via
``custody/__init__.py`` importing ``file_custody``, which imports ``tos_runtime.evidence.ports``)
and ``tos_runtime.rcl`` (``rcl/log.py`` also imports ``tos_runtime.evidence.ports``) transitively
re-enter ``tos_runtime.evidence``'s own package ``__init__`` — which imports ``evidence.backup``,
which imports ``evidence.store`` — a REAL circular import if this module (partially initialized,
still executing its OWN top-level imports) is re-entered before its classes/functions are defined
(confirmed by an actual ``ImportError: cannot import name ... from partially initialized module``
during development). This module therefore imports **nothing** from ``tos_runtime`` at all —
every cross-package argument (``store``, ``key_provider``, ``rcl_log``) is typed as a small
structural :class:`Protocol` naming only the members this module actually calls, mirroring
:mod:`tos_runtime.custody.ports`'s own "mirror the shape, don't import the class" convention (used
there for the identical reason, one layer over).

Firewall: stdlib (``json``, ``secrets``) + ``tos.canonical``/``tos.evidence``/``tos.rcl``/
``tos.workload`` only (R1 allowlist) — no ``tos_runtime.*`` import whatsoever (see above).
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.evidence import EvidenceAppendReceipt
from tos.rcl import AppendReceipt, CommitEntry, LogView, WriterEpoch
from tos.workload import RuntimeIdentity

__all__ = [
    "KeyContinuityCheck",
    "KeyContinuityRefused",
    "KeyContinuityVerdict",
    "KeyRotationRefused",
    "RotationOutcome",
    "rotate_evidence_key",
    "verify_key_generation_continuity",
]

#: The marker this module puts in the RCL rotation-commit entry's own ``payload_json`` (see the
#: module docstring's "why ``kind`` is ``None``" note) — never a kernel ``CommandType`` member.
_KEY_ROTATION_COMMIT_TYPE = "KEY_ROTATION_COMMIT"

#: The evidence ``kind`` this module appends when the RCL side of a rotation could not be
#: recorded (decision 4(b)'s "겹침 0" honesty requirement — never silently "not rotated").
KEY_ROTATION_RCL_UNRECORDED_KIND = "KEY_ROTATION_RCL_UNRECORDED"

_CANON_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class KeyContinuityVerdict:
    """The three outcomes :func:`verify_key_generation_continuity` can reach.

    Plain string constants (not a ``StrEnum``) so :class:`KeyContinuityCheck` — the function's
    actual return type — can carry a per-call free-text ``reason`` alongside one of these without
    needing an enum member to hold extra instance data it was never designed to hold.
    """

    CONTINUOUS = "CONTINUOUS"
    ROTATION_PENDING = "ROTATION_PENDING"
    HISTORY_UNVERIFIABLE = "HISTORY_UNVERIFIABLE"


@dataclass(frozen=True)
class KeyContinuityCheck:
    """The full result of :func:`verify_key_generation_continuity`.

    Attributes:
        verdict: One of :class:`KeyContinuityVerdict`'s three string constants.
        reason: A human-readable, case-specific explanation — never a constant string, always
            built from the actual generations/tip involved so a boot-refusal log line says
            exactly what was observed.
    """

    verdict: str
    reason: str


class KeyContinuityRefused(RuntimeError):
    """Raised by :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s constructor when
    :func:`verify_key_generation_continuity` returns anything but
    :attr:`KeyContinuityVerdict.CONTINUOUS` — the store never opens on any other verdict (no
    partial/degraded construction)."""


class KeyRotationRefused(RuntimeError):
    """Raised by :func:`rotate_evidence_key` when a rotation precondition is not met (wrong
    ``new_generation``, missing/invalid key file) — refusal, never a partial rotation.
    """


def verify_key_generation_continuity(
    tip_key_generation: int | None,
    tip_has_rotation_commit_for: Callable[[int], bool] | None,
    provider_generations: tuple[int, ...],
) -> KeyContinuityCheck:
    """Decide whether the custody root's key generations are consistent with what a store has
    already committed to (design #40 D4.1 "겹침 0", deny-first).

    Args:
        tip_key_generation: The ``key_generation`` of the store's own most recently committed
            entry, or ``None`` for a store with no entries yet (a genuine fresh store).
        tip_has_rotation_commit_for: An optional cross-check callable — ``True`` iff a
            ``KEY_ROTATION`` entry recording a transition TO the given generation is already
            durably recorded. Used only as a safety net against a ``tip_key_generation`` that
            disagrees with the store's own history (see the "provider_max >
            tip_key_generation" branch below); ``None`` when the caller has no cheaper way to
            answer this than :func:`verify_key_generation_continuity` itself would need, in
            which case that branch is decided without the extra cross-check.
        provider_generations: Every key generation with a file present under the custody root,
            as returned by :meth:`~tos_runtime.custody.key_provider.FileKeyProvider.generations`.

    Returns:
        A :class:`KeyContinuityCheck` — never raises; the caller (the store's own constructor)
        decides whether a non-``CONTINUOUS`` verdict becomes a boot refusal.
    """
    if not provider_generations:
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.HISTORY_UNVERIFIABLE,
            reason=(
                "no key generation files present under the custody root — nothing to sign "
                "or verify with"
            ),
        )
    provider_max = max(provider_generations)

    if tip_key_generation is None:
        # A genuine fresh store: exactly one generation file is the only unambiguous genesis.
        # More than one is ambiguous — this pure function cannot tell "the operator staged a
        # second generation ahead of time" apart from "a rotation is silently pending before
        # the store has ever appended anything", so it refuses rather than guess which one a
        # fresh store should start signing under.
        if len(provider_generations) == 1:
            return KeyContinuityCheck(
                verdict=KeyContinuityVerdict.CONTINUOUS,
                reason=f"fresh store; single key generation {provider_max} on disk (genesis)",
            )
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.ROTATION_PENDING,
            reason="fresh store, multiple key generations on disk",
        )

    return _verify_continuity_with_existing_tip(
        tip_key_generation,
        tip_has_rotation_commit_for,
        provider_generations,
        provider_max,
    )


def _verify_continuity_with_existing_tip(
    tip_key_generation: int,
    tip_has_rotation_commit_for: Callable[[int], bool] | None,
    provider_generations: tuple[int, ...],
    provider_max: int,
) -> KeyContinuityCheck:
    """The "store already has entries" half of :func:`verify_key_generation_continuity` —
    split out purely to stay under the repo's 100-line function budget (``tools/
    tos_size_budget.py``); no behavior difference from the single-function form."""
    if tip_key_generation not in provider_generations:
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.HISTORY_UNVERIFIABLE,
            reason=(
                f"store tip key generation {tip_key_generation} has no matching file under "
                "the custody root — cannot verify the signing key that produced the "
                "existing chain"
            ),
        )

    if provider_max == tip_key_generation:
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.CONTINUOUS,
            reason=f"provider's highest generation matches the store tip ({tip_key_generation})",
        )

    if provider_max < tip_key_generation:
        # Unreachable via the "not in provider_generations" check above only if
        # tip_key_generation IS present but is not the max — i.e. a HIGHER generation file was
        # removed after being used. Still a refusal: the store signed with a generation this
        # custody root can no longer account for as "current".
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.HISTORY_UNVERIFIABLE,
            reason=(
                f"store tip key generation {tip_key_generation} exceeds the highest "
                f"generation file now on disk ({provider_max})"
            ),
        )

    # provider_max > tip_key_generation: a newer key file exists than evidence has committed
    # to. Deny-first — unless a rotation commit for provider_max is ALREADY durably recorded
    # (guards against a caller-supplied tip_key_generation that is itself stale or cheaply
    # computed), refuse: the operator must run `rotate-key` before this generation ever signs
    # anything (design #40 D4.1 "겹침 0").
    if tip_has_rotation_commit_for is not None and tip_has_rotation_commit_for(
        provider_max
    ):
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.HISTORY_UNVERIFIABLE,
            reason=(
                f"a KEY_ROTATION commit for generation {provider_max} is already recorded, "
                f"yet the observed tip is {tip_key_generation} — inconsistent state, refuse "
                "rather than guess which is authoritative"
            ),
        )
    return KeyContinuityCheck(
        verdict=KeyContinuityVerdict.ROTATION_PENDING,
        reason=(
            f"key generation {provider_max} exists on disk beyond the committed tip "
            f"{tip_key_generation} with no rotation commit — run rotate-key before boot "
            "(design #40 D4.1 겹침 0, deny-first)"
        ),
    )


class RotationOutcome:
    """The two outcomes :func:`rotate_evidence_key` can return — always after the evidence side
    has already durably rotated; never a "nothing happened" outcome (module docstring's M8
    note)."""

    ROTATED = "ROTATED"
    ROTATED_RCL_UNRECORDED = "ROTATED_RCL_UNRECORDED"


@runtime_checkable
class _RotatableEvidenceStore(Protocol):
    """Structural mirror of the three
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore` members this module calls — see the
    module docstring's "import-cycle avoidance" note for why this is a Protocol and not a
    concrete import."""

    @property
    def key_generation(self) -> int: ...

    def rotate(self, new_generation: int, new_key: bytes) -> EvidenceAppendReceipt: ...

    def append(
        self,
        payload: Mapping[str, object],
        *,
        kind: str,
        record_class: str,
    ) -> EvidenceAppendReceipt: ...


@runtime_checkable
class _KeyGenerationProvider(Protocol):
    """Structural mirror of :class:`~tos_runtime.custody.key_provider.FileKeyProvider`'s
    relevant surface (see module docstring's "import-cycle avoidance" note). Any concrete key
    provider's own refusal type (e.g. ``tos_runtime.custody.ports.CustodyLoadRefused`` for
    :class:`~tos_runtime.custody.key_provider.FileKeyProvider`) propagates UNWRAPPED from
    :func:`rotate_evidence_key` — this module cannot import that exception type without
    recreating the same cycle, and re-raising it as :class:`KeyRotationRefused` would just add
    an extra frame without extra information (the concrete type already names its own cause).
    """

    def current(self) -> tuple[int, bytes]: ...

    def generations(self) -> tuple[int, ...]: ...

    def key_for(self, generation: int) -> bytes: ...


@runtime_checkable
class _RotationCommitLog(Protocol):
    """Structural mirror of the three
    :class:`~tos_runtime.rcl.log.SqliteCommitLog` members this module calls."""

    def acquire_epoch(self, identity: RuntimeIdentity) -> WriterEpoch: ...

    def read_linearizable(self, *, writer_epoch: WriterEpoch) -> LogView: ...

    def append_cas(
        self,
        entry: CommitEntry,
        *,
        expected_seq: int,
        writer_epoch: WriterEpoch,
        payload_json: str | None = None,
    ) -> object: ...


def rotate_evidence_key(
    store: _RotatableEvidenceStore,
    key_provider: _KeyGenerationProvider,
    rcl_log: _RotationCommitLog,
    new_generation: int,
) -> str:
    """Rotate the evidence-signing key: evidence side first, RCL commit second (design #40
    D4.1, TOS Phase 5 W4 plan §2 decision 4(b)).

    A CLI-context, operator-invoked operation — never called from a boot path (a boot path only
    ever CONSULTS :func:`verify_key_generation_continuity`, it never rotates on the caller's
    behalf). ``store`` and ``rcl_log`` must both already be open on the SAME data directory the
    operator intends to rotate; this function neither opens nor closes either.

    Args:
        store: The already-open evidence store to rotate.
        key_provider: The custody root's key provider — supplies the new generation's key bytes
            (already file-first per :class:`~tos_runtime.custody.key_provider.FileKeyProvider`'s
            own rotation-order contract; this function never writes a key file itself).
        rcl_log: The already-open RCL commit log to record the rotation commit into.
        new_generation: The key generation to rotate TO — must be exactly ``store.key_generation
            + 1`` (deny-first: no skipping, no re-rotating to the same or a lower generation).

    Returns:
        :attr:`RotationOutcome.ROTATED` if both the evidence rotation and the RCL commit
        succeeded, or :attr:`RotationOutcome.ROTATED_RCL_UNRECORDED` if the evidence side rotated
        but the RCL commit could not be durably recorded (never "not rotated" — the evidence side
        already changed what signs future entries either way).

    Raises:
        KeyRotationRefused: ``new_generation`` is not exactly ``store.key_generation + 1``.
        Exception: whatever ``key_provider.key_for(new_generation)`` itself raises when the new
            generation's key file fails ITS OWN preconditions (missing, wrong mode, wrong owner)
            — propagates unwrapped; see :class:`_KeyGenerationProvider`'s own docstring for why.
    """
    current_generation = store.key_generation
    if new_generation != current_generation + 1:
        raise KeyRotationRefused(
            "rotate_evidence_key: new_generation must be exactly current+1 "
            f"(current={current_generation}, requested={new_generation}) — design #40 "
            "D4.1 겹침 0 / deny-first"
        )
    new_key = key_provider.key_for(new_generation)

    evidence_receipt = store.rotate(new_generation, new_key)

    if _record_rotation_commit(
        rcl_log,
        previous_key_generation=current_generation,
        new_key_generation=new_generation,
        evidence_seq=evidence_receipt.seq,
    ):
        return RotationOutcome.ROTATED

    # The evidence side is ALREADY rotated at this point — reporting anything other than this
    # specific "rotated, but the RCL side is unrecorded" outcome would be the exact silent-
    # failure this module's docstring refuses to introduce (M8).
    store.append(
        {
            "previous_key_generation": current_generation,
            "new_key_generation": new_generation,
            "evidence_rotation_seq": evidence_receipt.seq,
        },
        kind=KEY_ROTATION_RCL_UNRECORDED_KIND,
        record_class="SYSTEM_KEY_ROTATION",
    )
    return RotationOutcome.ROTATED_RCL_UNRECORDED


def _record_rotation_commit(
    rcl_log: _RotationCommitLog,
    *,
    previous_key_generation: int,
    new_key_generation: int,
    evidence_seq: int | None,
) -> bool:
    """Append the RCL rotation-commit entry; ``True`` iff it durably committed.

    Never raises — any failure (a stale-epoch read, a locked file, an unexpected exception from
    the log itself) is reported as ``False`` so :func:`rotate_evidence_key` can fall through to
    its own ``KEY_ROTATION_RCL_UNRECORDED`` marking rather than letting an RCL-side fault escape
    with the evidence side already rotated and no record of the disagreement.
    """
    payload = {
        "type": _KEY_ROTATION_COMMIT_TYPE,
        "previous_key_generation": previous_key_generation,
        "new_key_generation": new_key_generation,
        "evidence_seq": evidence_seq,
    }
    try:
        identity = RuntimeIdentity(
            cell_id="key-rotation-cli", process_nonce=secrets.token_hex(8)
        )
        epoch = rcl_log.acquire_epoch(identity)
        view = rcl_log.read_linearizable(writer_epoch=epoch)
        expected_seq = -1 if view.last_seq is None else view.last_seq
        entry = CommitEntry(
            command_id=f"key-rotation-{new_key_generation}",
            command_digest=_CANON_SCHEME.compute_digest(payload),
        )
        result = rcl_log.append_cas(
            entry,
            expected_seq=expected_seq,
            writer_epoch=epoch,
            payload_json=json.dumps(payload, sort_keys=True),
        )
    except Exception:
        return False
    return isinstance(result, AppendReceipt)
