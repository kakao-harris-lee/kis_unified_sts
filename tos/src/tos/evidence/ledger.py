"""Append-only ledger: segment commitment + integrity anchor (design #4 §2.4, §3.4)."""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from tos.canonical import DigestFactory, FrozenModel

EV_L1_PROVISIONAL_CHAIN_VERSION = "ev-l1-provisional-chain-0"

_CHAIN_GENESIS = ""


class IntegrityAnchor(FrozenModel):
    """A chained integrity anchor over a segment commitment (design §2.4, ADR §5.7)."""

    anchor_id: str
    segment_commitment: str
    store_continuity_id: str | None = None
    policy_generation: int | None = None
    key_generation: int | None = None
    predecessor_anchor: str | None = None
    anchor_cadence_ms: int | None = None


class EvidenceSegment(FrozenModel):
    """An ordered segment of record digests with an authenticated commitment (§2.4)."""

    segment_id: str | None = None
    record_ids: tuple[str, ...] = ()
    record_digests: tuple[str, ...] = ()
    store_continuity_id: str | None = None
    store_generation: int | None = None
    policy_generation: int | None = None
    key_generation: int | None = None
    segment_commitment: str | None = None
    predecessor_commitment: str | None = None


@runtime_checkable
class SegmentCommitmentScheme(Protocol):
    """A versioned segment-commitment scheme — chain or Merkle (design §3.4)."""

    @property
    def version(self) -> str: ...

    def commit(self, ordered_record_digests: tuple[str, ...]) -> str:
        """Return the commitment over an ordered sequence of record digests."""
        ...

    def verify_membership(
        self,
        record_digest: str,
        position: int,
        commitment: str,
        proof: tuple[str, ...],
    ) -> bool:
        """Whether ``record_digest`` is committed at ``position`` under ``commitment``."""
        ...

    def verify_append(
        self, prev_commitment: str, appended_digests: tuple[str, ...]
    ) -> str:
        """Return the new commitment after appending (prefix-preserving)."""
        ...

    def link_anchor(
        self,
        commitment: str,
        *,
        store_continuity_id: str | None = None,
        policy_generation: int | None = None,
        key_generation: int | None = None,
        predecessor_anchor: str | None = None,
        anchor_cadence_ms: int | None = None,
    ) -> IntegrityAnchor:
        """Bind ``commitment`` into a chained :class:`IntegrityAnchor`."""
        ...


class ProvisionalHashChainScheme:
    """Provisional, **non-production** hash-chain scheme (design §3.4)."""

    def __init__(
        self,
        *,
        version: str = EV_L1_PROVISIONAL_CHAIN_VERSION,
        digest_factory: DigestFactory = hashlib.sha256,
    ) -> None:
        """Initialize the provisional chain scheme."""
        self.version = version
        self._digest_factory = digest_factory

    def _fold(self, start: str, digests: tuple[str, ...]) -> str:
        """Fold ``digests`` into a running chain hash starting from ``start``."""
        commitment = start
        for digest in digests:
            hasher = self._digest_factory()
            hasher.update(f"{commitment}|{digest}".encode())
            commitment = hasher.hexdigest()
        return commitment

    def commit(self, ordered_record_digests: tuple[str, ...]) -> str:
        """Return the chain commitment over the ordered digests (from genesis)."""
        return self._fold(_CHAIN_GENESIS, ordered_record_digests)

    def verify_membership(
        self,
        record_digest: str,
        position: int,
        commitment: str,
        proof: tuple[str, ...],
    ) -> bool:
        """Verify chain inclusion of ``record_digest`` at ``position``."""
        if position < 0 or position >= len(proof):
            return False
        if proof[position] != record_digest:
            return False
        return self.commit(proof) == commitment

    def verify_append(
        self, prev_commitment: str, appended_digests: tuple[str, ...]
    ) -> str:
        """Return the commitment after appending ``appended_digests`` to a prefix."""
        return self._fold(prev_commitment, appended_digests)

    def link_anchor(
        self,
        commitment: str,
        *,
        store_continuity_id: str | None = None,
        policy_generation: int | None = None,
        key_generation: int | None = None,
        predecessor_anchor: str | None = None,
        anchor_cadence_ms: int | None = None,
    ) -> IntegrityAnchor:
        """Bind ``commitment`` into a chained anchor with a deterministic id."""
        hasher = self._digest_factory()
        hasher.update(f"{predecessor_anchor or ''}|{commitment}".encode())
        anchor_id = f"anchor-{hasher.hexdigest()}"
        return IntegrityAnchor(
            anchor_id=anchor_id,
            segment_commitment=commitment,
            store_continuity_id=store_continuity_id,
            policy_generation=policy_generation,
            key_generation=key_generation,
            predecessor_anchor=predecessor_anchor,
            anchor_cadence_ms=anchor_cadence_ms,
        )
