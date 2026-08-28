"""Append-only ledger: segment commitment + integrity anchor (design #4 §2.4, §3.4).

Two layers, modelled separately (design §2.1 note / §13 line 335):

1. **record content-addressing** — each envelope's own ``canonical_digest``
   (:mod:`tos.evidence.envelope`).
2. **segment commitment + integrity anchor** — an authenticated commitment over
   an *ordered* segment of record digests, plus a chained anchor.

The anchor detects mutation; it does **not** validate the safety decision (ADR
§5.7 line 120).

:class:`SegmentCommitmentScheme` is an abstract Protocol that accepts **both**
chain and Merkle constructions (design §3.4), so a production choice of either
needs no model rework (§27 Q3, Phase-0). :class:`ProvisionalHashChainScheme`
(``ev-l1-provisional-chain-0``) is the **explicitly non-production** provisional
implementation: ``c_i = H(c_{i-1} || d_i)``, reusing the same injected digest
factory (default ``hashlib.sha256``) as the canonicalizer. Prefix preservation
(append-only) is immediate: ``commit(A + B) == verify_append(commit(A), B)``.

**Honest scope (design §3.4):** the MAC's cryptographic verification, real
"anchor outside the failure domain", and common-mode corruption are EV-L2+/
Security; the anchor cadence *timing* is an injected bound with no approved
profile key (``MAX_anchor_cadence_ms`` missing — Phase-0 §8/§9.2 item 4).

Pure module: ``pydantic`` + stdlib (``hashlib``) only; no ``shared.*``.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from tos.canonical import DigestFactory, FrozenModel

#: Version string of the provisional non-production chain scheme (design §3.4).
EV_L1_PROVISIONAL_CHAIN_VERSION = "ev-l1-provisional-chain-0"

#: Genesis commitment for the provisional chain (empty prefix).
_CHAIN_GENESIS = ""


class IntegrityAnchor(FrozenModel):
    """A chained integrity anchor over a segment commitment (design §2.4, ADR §5.7).

    Detects mutation of the committed segment; it does not validate the safety
    decision. ``predecessor_anchor`` chains anchors so a rollback / skipped
    interval is a discontinuity. ``anchor_cadence_ms`` is an injected bound (§8);
    ``None`` => UNKNOWN (no approved ``MAX_anchor_cadence_ms`` — Phase-0).
    """

    anchor_id: str
    segment_commitment: str
    store_continuity_id: str | None = None
    policy_generation: int | None = None
    key_generation: int | None = None
    predecessor_anchor: str | None = None
    anchor_cadence_ms: int | None = None


class EvidenceSegment(FrozenModel):
    """An ordered segment of record digests with an authenticated commitment (§2.4).

    ``record_digests`` is position-ordered (index = position). ``store_continuity_id``
    resets on restart/restore/reset (§11 line 315 => new continuity).
    ``segment_commitment`` is produced by a :class:`SegmentCommitmentScheme`;
    ``predecessor_commitment`` links to the prior segment (append-only prefix).
    """

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
    """A versioned segment-commitment scheme — chain or Merkle (design §3.4).

    Parallel to ``CanonicalizationScheme``: a production choice of chain or
    Merkle-equivalent commitment plugs in behind this Protocol without model
    rework.
    """

    version: str

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
    """Provisional, **non-production** hash-chain scheme (design §3.4).

    ``c_i = H(c_{i-1} || d_i)`` from the empty genesis, reusing the injected
    digest factory (default ``hashlib.sha256`` — a stdlib primitive for
    reproducible tests, not a production selection, design §9.2 item 2).
    """

    def __init__(
        self,
        *,
        version: str = EV_L1_PROVISIONAL_CHAIN_VERSION,
        digest_factory: DigestFactory = hashlib.sha256,
    ) -> None:
        """Initialize the provisional chain scheme.

        Args:
            version: The scheme version identifier this instance binds.
            digest_factory: Zero-arg callable returning a fresh hashlib-style
                hasher (default the non-production ``hashlib.sha256``).
        """
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
        """Verify chain inclusion of ``record_digest`` at ``position``.

        For the provisional chain the ``proof`` is the full ordered digest
        sequence of the segment: membership holds iff the position carries the
        claimed digest and the sequence re-commits to ``commitment`` (so any
        mutation, deletion, prefix truncation, or suffix loss fails to verify).

        Args:
            record_digest: The claimed digest at ``position``.
            position: The 0-based position in the segment.
            commitment: The segment commitment to verify against.
            proof: The ordered digest sequence of the segment.

        Returns:
            ``True`` iff membership verifies.
        """
        if position < 0 or position >= len(proof):
            return False
        if proof[position] != record_digest:
            return False
        return self.commit(proof) == commitment

    def verify_append(
        self, prev_commitment: str, appended_digests: tuple[str, ...]
    ) -> str:
        """Return the commitment after appending ``appended_digests`` to a prefix.

        Prefix-preserving by construction: ``commit(A + B) ==
        verify_append(commit(A), B)`` (append-only).

        Args:
            prev_commitment: The commitment over the existing prefix.
            appended_digests: The digests appended after the prefix.

        Returns:
            The new commitment.
        """
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
        """Bind ``commitment`` into a chained anchor with a deterministic id.

        The ``anchor_id`` is derived from the commitment and predecessor so the
        anchor chain is reproducible; ``anchor_cadence_ms`` is an injected bound
        (``None`` => UNKNOWN, no approved profile key — Phase-0 §8).

        Args:
            commitment: The segment commitment this anchor binds.
            store_continuity_id: The store continuity in effect.
            policy_generation: The EIP generation in effect.
            key_generation: The signing-key generation in effect.
            predecessor_anchor: The prior anchor id (chain link).
            anchor_cadence_ms: The injected cadence bound (§8), or ``None``.

        Returns:
            The :class:`IntegrityAnchor`.
        """
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
