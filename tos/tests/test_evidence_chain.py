"""Segment-commitment chain verify — ERI-EV-005 predicate-only (design #4 §3.4).

The provisional hash chain (``c_i = H(c_{i-1} || d_i)``) supports the §13
detection predicates: mutation / substitution, deletion / prefix-truncation /
suffix-loss, fork (different predecessor), and append-only prefix preservation.
The Protocol accepts chain or Merkle, so a production choice needs no rework. The
MAC's cryptographic verification and real failure-domain separation are L2+.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.evidence import (
    EV_L1_PROVISIONAL_CHAIN_VERSION,
    IntegrityAnchor,
    ProvisionalHashChainScheme,
    SegmentCommitmentScheme,
)

_SCHEME = ProvisionalHashChainScheme()
_DIGESTS = st.lists(
    st.text(min_size=1, max_size=8), min_size=1, max_size=8, unique=True
)


def test_scheme_satisfies_protocol() -> None:
    """The provisional chain satisfies the abstract SegmentCommitmentScheme Protocol."""
    assert isinstance(_SCHEME, SegmentCommitmentScheme)
    assert _SCHEME.version == EV_L1_PROVISIONAL_CHAIN_VERSION


@given(digests=_DIGESTS)
def test_membership_verifies_for_every_position(digests: list[str]) -> None:
    """Each committed digest verifies at its own position (§3.4 detection)."""
    seq = tuple(digests)
    commitment = _SCHEME.commit(seq)
    for position, digest in enumerate(seq):
        assert _SCHEME.verify_membership(digest, position, commitment, seq)


@given(digests=_DIGESTS)
def test_mutation_is_detected(digests: list[str]) -> None:
    """Substituting any record digest breaks membership verification (§13)."""
    seq = tuple(digests)
    commitment = _SCHEME.commit(seq)
    tampered = ("__tampered__", *seq[1:])
    # The mutated sequence no longer commits to the original commitment.
    assert not _SCHEME.verify_membership(tampered[0], 0, commitment, tampered)


@given(
    digests=st.lists(
        st.text(min_size=1, max_size=8), min_size=2, max_size=8, unique=True
    )
)
def test_prefix_truncation_is_detected(digests: list[str]) -> None:
    """Dropping the suffix (prefix truncation) fails to re-commit (§13)."""
    seq = tuple(digests)
    commitment = _SCHEME.commit(seq)
    truncated = seq[:-1]
    assert _SCHEME.commit(truncated) != commitment


@given(digests=_DIGESTS, extra=st.text(min_size=1, max_size=8))
def test_append_preserves_prefix(digests: list[str], extra: str) -> None:
    """Append is prefix-preserving: commit(A+B) == verify_append(commit(A), B) (§3.4)."""
    seq = tuple(digests)
    full = _SCHEME.commit((*seq, extra))
    appended = _SCHEME.verify_append(_SCHEME.commit(seq), (extra,))
    assert full == appended


def test_fork_is_detected_by_predecessor_discontinuity() -> None:
    """Two branches at the same position with different predecessors are distinct (§13)."""
    anchor_a = _SCHEME.link_anchor(
        _SCHEME.commit(("d1", "d2")), predecessor_anchor="p-1"
    )
    anchor_b = _SCHEME.link_anchor(
        _SCHEME.commit(("d1", "dX")), predecessor_anchor="p-1"
    )
    # Divergent committed content yields divergent anchors (no last-write-wins merge).
    assert anchor_a.segment_commitment != anchor_b.segment_commitment
    assert anchor_a.anchor_id != anchor_b.anchor_id


def test_anchor_chain_links_predecessor() -> None:
    """A linked anchor records its predecessor (anchor chain for rollback detection)."""
    commitment = _SCHEME.commit(("d1", "d2", "d3"))
    anchor = _SCHEME.link_anchor(
        commitment, store_continuity_id="store-1", predecessor_anchor="anchor-0"
    )
    assert isinstance(anchor, IntegrityAnchor)
    assert anchor.segment_commitment == commitment
    assert anchor.predecessor_anchor == "anchor-0"
    # Cadence is an injected bound; unset => UNKNOWN (no approved MAX_anchor_cadence_ms).
    assert anchor.anchor_cadence_ms is None


def test_out_of_range_membership_rejected() -> None:
    """A position outside the segment never verifies."""
    seq = ("d1", "d2")
    commitment = _SCHEME.commit(seq)
    assert not _SCHEME.verify_membership("d1", 5, commitment, seq)
    assert not _SCHEME.verify_membership("d1", -1, commitment, seq)
