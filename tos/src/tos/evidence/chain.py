"""Production segment-commitment scheme: SHA-256/HMAC chain + append receipt."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel
from tos.evidence.ledger import IntegrityAnchor

__all__ = [
    "EV_L2_SHA256_HMAC_CHAIN_VERSION",
    "ChainedEntry",
    "EvidenceAppendReceipt",
    "Sha256HmacChainScheme",
    "verify_chain",
]

EV_L2_SHA256_HMAC_CHAIN_VERSION = "ev-l2-sha256-hmac-chain-1"

_CHAIN_GENESIS = ""


class EvidenceAppendReceipt(FrozenModel):
    """Proof that one entry was durably committed to the evidence store (design #40 D3-a)."""

    segment_id: str | None = None
    seq: int | None = None
    chain_digest: str | None = None
    key_generation: int | None = None
    durable: Literal[True] = True

    @model_validator(mode="after")
    def _seq_non_negative(self) -> EvidenceAppendReceipt:
        """Reject a negative ``seq`` (design #40 D3-a "seq (int >= 0)")."""
        if self.seq is not None and self.seq < 0:
            raise ArtifactIntegrityError(
                f"EvidenceAppendReceipt.seq must be non-negative (got {self.seq})"
            )
        return self


class ChainedEntry(FrozenModel):
    """One committed link of a :class:`Sha256HmacChainScheme` chain (design #40 D4.1)."""

    entry_digest: str | None = None
    key_generation: int | None = None
    chain_digest: str | None = None


class Sha256HmacChainScheme:
    """Production SHA-256/HMAC hash-chain :class:`SegmentCommitmentScheme` (design #40 D3-b)."""

    def __init__(
        self,
        *,
        key: bytes,
        key_generation: int,
        version: str = EV_L2_SHA256_HMAC_CHAIN_VERSION,
    ) -> None:
        """Initialize the HMAC chain scheme, bound to one key and one key generation."""
        if not key:
            raise ArtifactIntegrityError(
                "Sha256HmacChainScheme requires a non-empty key — an unkeyed chain "
                "is not a production HMAC chain (design #40 D3-b)"
            )
        if key_generation is None or key_generation < 0:
            raise ArtifactIntegrityError(
                "Sha256HmacChainScheme requires a non-negative key_generation "
                f"(got {key_generation!r})"
            )
        self._key = key
        self.key_generation = key_generation
        self.version = version

    def _link(self, prev_chain_digest: str, entry_digest: str) -> str:
        """Fold one entry digest into the running HMAC chain (module docstring formula)."""
        mac = hmac.new(
            self._key,
            prev_chain_digest.encode() + entry_digest.encode(),
            hashlib.sha256,
        )
        return mac.hexdigest()

    def _fold(self, start: str, digests: tuple[str, ...]) -> str:
        """Fold ``digests`` into a running HMAC chain starting from ``start``."""
        commitment = start
        for digest in digests:
            commitment = self._link(commitment, digest)
        return commitment

    def commit(self, ordered_record_digests: tuple[str, ...]) -> str:
        """Return the HMAC chain commitment over the ordered digests (from genesis)."""
        return self._fold(_CHAIN_GENESIS, ordered_record_digests)

    def verify_membership(
        self,
        record_digest: str,
        position: int,
        commitment: str,
        proof: tuple[str, ...],
    ) -> bool:
        """Verify chain inclusion of ``record_digest`` at ``position`` under this key."""
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
        """Bind ``commitment`` into a chained :class:`IntegrityAnchor`."""
        resolved_key_generation = (
            self.key_generation if key_generation is None else key_generation
        )
        hasher = hashlib.sha256()
        hasher.update(f"{predecessor_anchor or ''}|{commitment}".encode())
        anchor_id = f"anchor-{hasher.hexdigest()}"
        return IntegrityAnchor(
            anchor_id=anchor_id,
            segment_commitment=commitment,
            store_continuity_id=store_continuity_id,
            policy_generation=policy_generation,
            key_generation=resolved_key_generation,
            predecessor_anchor=predecessor_anchor,
            anchor_cadence_ms=anchor_cadence_ms,
        )


def verify_chain(
    entries: Sequence[ChainedEntry], keys_by_generation: Mapping[int, bytes]
) -> bool:
    """Verify an HMAC chain that may span a key rotation (design #40 D4.1)."""
    commitment = _CHAIN_GENESIS
    for entry in entries:
        if (
            entry.entry_digest is None
            or entry.key_generation is None
            or entry.chain_digest is None
        ):
            return False
        key = keys_by_generation.get(entry.key_generation)
        if not key:
            return False
        mac = hmac.new(
            key, commitment.encode() + entry.entry_digest.encode(), hashlib.sha256
        )
        if mac.hexdigest() != entry.chain_digest:
            return False
        commitment = entry.chain_digest
    return True
