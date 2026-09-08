"""Production segment-commitment scheme: SHA-256/HMAC chain + append receipt.

Realizes the *kernel* (pure, non-transmitting) half of design doc #40's D3 decision
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D3.1,
lines 85-96): "체인: ``evidence/ledger.py`` 의 ``ProvisionalHashChainScheme``
(«explicitly non-production») 을 **런타임 구현체** ``Sha256HmacChainScheme`` 로
대체 — 항목 digest = SHA-256(정본 바이트) · 체인 = HMAC-SHA256(key_generation,
prev_chain ‖ digest)(stdlib ``hashlib``/``hmac``). 키는 D4 custody 에서 온다. 커널의
``SegmentCommitmentScheme`` Protocol 을 그대로 만족" (design #40 §D3.1).

**D1 (runtime composition boundary) is NOT yet ratified** (design #40 §0). §5-A
explicitly carves this piece out as landable pre-ratification because it is *pure*:
:class:`Sha256HmacChainScheme` takes its ``key: bytes`` **by injection** — it never
reads a file, environment variable, or D4 custody store itself (that remains
``tos_runtime.custody`` territory once D1 lands). No I/O — no ``sqlite3``, ``socket``,
filesystem, or clock access.

**This module ADDS to, and never edits or deletes,** :mod:`tos.evidence.ledger`'s
:class:`~tos.evidence.ledger.ProvisionalHashChainScheme` (design #40 §5-A: "기존
``SegmentCommitmentScheme`` Protocol 구현" — beside it, not instead of it). The
provisional scheme stays the EV-L1 default; :class:`Sha256HmacChainScheme` is the
Phase-2 production alternative a caller opts into.

**Naming-collision note (anti-phantom, playbook §2.C).** The design doc's own D3-a
shorthand for the append-commit receipt is "EvidenceCommitReceipt", but
``tos.evidence.receipt.EvidenceCommitReceipt`` **already exists** (design #4 §2.2) and
is a *different*, incompatible artifact: it is a digest-bound ``EvidenceArtifact``
whose ``verification_status`` is invariant-locked to ``UNVERIFIED`` forever in Phase 1
("proving durable acceptance needs an out-of-scope durable store + anchor service",
``receipt.py`` lines 7-12) and whose four authority-effect flags are all-false by
construction. Reusing that name for a *different* artifact that IS the durable-commit
proof would either collide on import (both live under ``tos.evidence``) or silently
overload one name with two incompatible meanings. This module names the new artifact
:class:`EvidenceAppendReceipt` instead — deliberately parallel to
``tos.rcl.commitlog.AppendReceipt`` (the same "receipt in-hand => durability already
proved" shape, ``durable: Literal[True]``, no ``False`` variant constructible) — and
reports the collision here rather than resolving it by force. ``git grep -n "class
EvidenceCommitReceipt" tos/src/tos`` (before this module) -> exactly one hit,
``tos/src/tos/evidence/receipt.py:59`` (confirms the collision is real, not phantom).

**Scheme identifier convention.** ``EV_L1_PROVISIONAL_CHAIN_VERSION =
"ev-l1-provisional-chain-0"`` (design #4 §3.4) fixes the pattern
``ev-l{phase}-{scheme-name}-{sequence}``. This module's scheme is Phase-2, SHA-256
HMAC chain, first production revision, hence ``"ev-l2-sha256-hmac-chain-1"`` (task
directive default, consistent with the existing naming rule — no deviation needed).

**One ``key_generation`` axis (corrected from an earlier draft's two-axis split —
team-lead directive, 2026-09-08).** The pre-existing Phase-1 Protocol convention
(:meth:`SegmentCommitmentScheme.link_anchor`'s ``key_generation: int | None`` call
parameter, feeding ``IntegrityAnchor.key_generation: int | None``, ``ledger.py``
lines 56/76/118/215) IS the monotonic key-epoch axis design #40 D3/D4 means —
not a second concept. Every ``key_generation`` in this module is therefore ``int``:
:class:`Sha256HmacChainScheme`'s own ``key_generation`` attribute,
:class:`EvidenceAppendReceipt.key_generation`, :class:`ChainedEntry.key_generation`,
and :func:`verify_chain`'s ``keys_by_generation`` mapping key. :meth:`link_anchor`
defaults its ``key_generation`` call parameter to ``self.key_generation`` when the
caller does not override it, so an anchor produced by this scheme's own
``link_anchor`` call always carries the scheme's own generation unless a caller
deliberately asks for a different one (see the "anchor key_generation equals the
scheme's" test).

Key-rotation semantics (design #40 D4.1 "겹침 0 · deny-first"): one
:class:`Sha256HmacChainScheme` **instance is bound to exactly one key_generation** —
rotation is expressed by constructing a new instance with a new key, never by mutating
an existing one (this module has no setter). Verifying a chain that SPANS a rotation
(links signed under different generations) is :func:`verify_chain`'s job, not a single
scheme instance's — it looks up each link's key by the generation *recorded on that
link* and fails closed (returns ``False``, never skips or partially verifies) when a
link's generation has no key.

Pure module: ``pydantic`` + stdlib (``hashlib``, ``hmac``) only; no ``shared.*``, no
network / filesystem / clock (design #40 §5-A kernel-PORT-only scope) — actively
verified by the evidence package's §7.1 import-closure test.
"""

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

#: Version string of the production SHA-256/HMAC chain scheme (design #40 §D3.1).
EV_L2_SHA256_HMAC_CHAIN_VERSION = "ev-l2-sha256-hmac-chain-1"

#: Genesis commitment for the chain (empty prefix — same convention as the
#: provisional scheme's ``_CHAIN_GENESIS``, design #4 §3.4).
_CHAIN_GENESIS = ""


class EvidenceAppendReceipt(FrozenModel):
    """Proof that one entry was durably committed to the evidence store (design #40 D3-a).

    "커밋 영수증: ``append()`` 는 durable 커밋 **후에만** ``(segment_id, seq,
    chain_digest, key_generation)`` 을 돌려주며, 이 영수증이 없는 «기록됨» 주장은
    존재하지 않는다" (design #40 §D3.1 line 88). Mirrors
    ``tos.rcl.commitlog.AppendReceipt``'s shape exactly: ``durable`` is typed
    ``Literal[True]`` with a default of ``True`` — there is no ``False`` variant to
    construct, so an ``EvidenceAppendReceipt`` existing already **is** the durability
    claim (design #40 §D3.1 line 89's own gloss of ADR-002-016 line 19: "an
    unavailable, stale, contradictory, or unverifiable evidence path cannot be
    bypassed by buffering in ordinary application memory"). A failed or partial
    append never returns this type.

    ``chain_digest`` is documented as a lowercase hex digest (the
    ``hashlib``/``hmac`` ``.hexdigest()`` convention this module's chain scheme
    produces) but, matching every other digest field in this codebase (e.g.
    ``tos.canonical.DigestBoundArtifact.canonical_digest``,
    ``tos.rcl.commitlog.CommitEntry.command_digest``), is carried as an **opaque
    string** with no runtime hex-format check — digests are compared for equality,
    never parsed.
    """

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
    """One committed link of a :class:`Sha256HmacChainScheme` chain (design #40 D4.1).

    The unit :func:`verify_chain` re-verifies across a possible key rotation:
    ``entry_digest`` is the record's own SHA-256 digest (design #40 §D3.1 "항목
    digest = SHA-256(정본 바이트)" — computed upstream by the canonicalizer, not by
    this module); ``key_generation`` is the same Phase-1 ``int`` key-epoch axis as
    ``IntegrityAnchor.key_generation`` (see the module docstring's "one axis" note)
    that this link was signed under; ``chain_digest`` is the HMAC chain value this
    link claims to produce.

    A deliberately separate, lightweight record from
    :class:`~tos.evidence.ledger.EvidenceSegment` (design #4's *segment*-level
    aggregate over MANY record digests under ONE ``segment_commitment``) — kept
    distinct because :class:`EvidenceSegment` aggregates a whole committed segment
    while :class:`ChainedEntry` is the per-link unit :func:`verify_chain` folds one
    at a time across a possible rotation; both now share the same ``int``
    ``key_generation`` axis.
    """

    entry_digest: str | None = None
    key_generation: int | None = None
    chain_digest: str | None = None


class Sha256HmacChainScheme:
    """Production SHA-256/HMAC hash-chain :class:`SegmentCommitmentScheme` (design #40 D3-b).

    ``c_i = HMAC-SHA256(key, c_{i-1} || d_i)`` from the empty genesis — the same
    fold shape as :class:`~tos.evidence.ledger.ProvisionalHashChainScheme` but keyed,
    so an attacker who can forge a plain SHA-256 chain cannot forge this one without
    the key (the provisional scheme's own docstring calls out that gap as its "honest
    scope" exclusion, ``ledger.py`` lines 21-24 — this class is what closes it in
    production). ``prev_chain_digest`` and ``entry_digest`` are concatenated as their
    UTF-8-encoded hex-string representations with **no separator** — unambiguous
    because every digest this module folds is a fixed-length hex string (matching the
    provisional scheme's own pipe-joined-string convention, minus the separator,
    which the design doc's literal ``‖`` (concatenation, not "join with a delimiter")
    formula calls for).

    A scheme instance is bound to exactly **one** ``key_generation`` — rotation
    means constructing a new instance with a new key (design #40 D4.1 "겹침 0");
    verifying a chain that spans a rotation is :func:`verify_chain`'s job, not this
    class's (module docstring "Key-rotation semantics").
    """

    def __init__(
        self,
        *,
        key: bytes,
        key_generation: int,
        version: str = EV_L2_SHA256_HMAC_CHAIN_VERSION,
    ) -> None:
        """Initialize the HMAC chain scheme, bound to one key and one key generation.

        Args:
            key: The HMAC key bytes for this generation (injected — this module
                never reads a key from a file, environment variable, or D4 custody
                store; that remains ``tos_runtime.custody`` territory). Must be
                non-empty.
            key_generation: The monotonic key-epoch this instance signs under —
                the same ``int`` axis as ``IntegrityAnchor.key_generation`` /
                :meth:`link_anchor`'s Protocol call parameter (design #40 D3-a/
                D4.1; see the module docstring's "one axis" note). Must be
                non-negative.
            version: The scheme version identifier this instance binds (design #4
                §3.4 naming convention; see the module docstring).

        Raises:
            ArtifactIntegrityError: If ``key`` is empty or ``key_generation`` is
                ``None``/negative — an unkeyed or unlabelled chain is not a valid
                production scheme instance (fail-closed at construction, not at
                first use).
        """
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
        """Verify chain inclusion of ``record_digest`` at ``position`` under this key.

        Args:
            record_digest: The claimed digest at ``position``.
            position: The 0-based position in the segment.
            commitment: The segment commitment to verify against.
            proof: The ordered digest sequence of the segment.

        Returns:
            ``True`` iff membership verifies under this instance's key.
        """
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
        """Bind ``commitment`` into a chained :class:`IntegrityAnchor`.

        ``key_generation`` here is the pre-existing Protocol's ``int | None`` call
        parameter — the SAME axis as this instance's own ``self.key_generation``
        (module docstring "one axis" note, corrected 2026-09-08). When the caller
        does not override it (the common case), it defaults to
        ``self.key_generation``, so an anchor produced by this scheme always
        carries the scheme's own generation unless a caller deliberately asks for
        a different one.

        Args:
            commitment: The segment commitment this anchor binds.
            store_continuity_id: The store continuity in effect.
            policy_generation: The EIP generation in effect.
            key_generation: The signing-key generation to bind on the anchor;
                ``None`` (the default) resolves to this instance's own
                ``self.key_generation`` rather than staying ``None``.
            predecessor_anchor: The prior anchor id (chain link).
            anchor_cadence_ms: The injected cadence bound, or ``None``.

        Returns:
            The :class:`IntegrityAnchor`.
        """
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
    """Verify an HMAC chain that may span a key rotation (design #40 D4.1).

    Each link is verified with the key of the **generation recorded on that link**,
    never the caller's "current" key — so a chain signed under generations
    ``{1, 2}`` verifies correctly as long as both keys are supplied, regardless of
    which generation is active now. Fail-closed throughout
    (playbook §2.A): a link whose ``key_generation`` has no entry in
    ``keys_by_generation`` — or whose ``entry_digest``/``key_generation``/
    ``chain_digest`` is ``None`` — makes the **whole chain** fail verification; it is
    never silently skipped or treated as vacuously valid.

    Args:
        entries: The chain, in commit order, each carrying the key generation it
            was signed under and the chain-digest value it claims.
        keys_by_generation: The HMAC keys, keyed by ``key_generation``. A
            generation absent from this mapping cannot be verified (fails closed,
            not "assumed valid").

    Returns:
        ``True`` iff every link re-derives, under its own recorded generation's
        key, to exactly the ``chain_digest`` it claims. ``True`` for an empty
        ``entries`` sequence (nothing to falsify — the genesis commitment).
    """
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
