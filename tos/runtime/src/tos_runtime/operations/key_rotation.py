"""Evidence-signing key rotation: deny-first continuity + explicit workflow"""

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

_KEY_ROTATION_COMMIT_TYPE = "KEY_ROTATION_COMMIT"

KEY_ROTATION_RCL_UNRECORDED_KIND = "KEY_ROTATION_RCL_UNRECORDED"

_CANON_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class KeyContinuityVerdict:
    """The three outcomes :func:`verify_key_generation_continuity` can reach."""

    CONTINUOUS = "CONTINUOUS"
    ROTATION_PENDING = "ROTATION_PENDING"
    HISTORY_UNVERIFIABLE = "HISTORY_UNVERIFIABLE"


@dataclass(frozen=True)
class KeyContinuityCheck:
    """The full result of :func:`verify_key_generation_continuity`."""

    verdict: str
    reason: str


class KeyContinuityRefused(RuntimeError):
    """Raised by :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`'s constructor when"""


class KeyRotationRefused(RuntimeError):
    """Raised by :func:`rotate_evidence_key` when a rotation precondition is not met (wrong"""


def verify_key_generation_continuity(
    tip_key_generation: int | None,
    tip_has_rotation_commit_for: Callable[[int], bool] | None,
    provider_generations: tuple[int, ...],
) -> KeyContinuityCheck:
    """Decide whether the custody root's key generations are consistent with what a store has"""
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
    """The "store already has entries" half of :func:`verify_key_generation_continuity` —"""
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
        return KeyContinuityCheck(
            verdict=KeyContinuityVerdict.HISTORY_UNVERIFIABLE,
            reason=(
                f"store tip key generation {tip_key_generation} exceeds the highest "
                f"generation file now on disk ({provider_max})"
            ),
        )

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
    """The two outcomes :func:`rotate_evidence_key` can return — always after the evidence side"""

    ROTATED = "ROTATED"
    ROTATED_RCL_UNRECORDED = "ROTATED_RCL_UNRECORDED"


@runtime_checkable
class _RotatableEvidenceStore(Protocol):
    """Structural mirror of the three"""

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
    """Structural mirror of :class:`~tos_runtime.custody.key_provider.FileKeyProvider`'s"""

    def current(self) -> tuple[int, bytes]: ...

    def generations(self) -> tuple[int, ...]: ...

    def key_for(self, generation: int) -> bytes: ...


@runtime_checkable
class _RotationCommitLog(Protocol):
    """Structural mirror of the three"""

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
    """Rotate the evidence-signing key: evidence side first, RCL commit second (design #40"""
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
    """Append the RCL rotation-commit entry; ``True`` iff it durably committed."""
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
