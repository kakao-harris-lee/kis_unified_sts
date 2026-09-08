"""Production SHA-256/HMAC chain scheme + append receipt tests (design #40 D3-a/D3-b).

Covers: a known-answer HMAC chain computation (derivation shown below, computed
once with stdlib ``hashlib``/``hmac`` — see the module docstring comment), chain
verification positive/negative (tampered entry digest, tampered prev link, missing
key generation), rotation across two key generations, empty-key rejection, and the
``EvidenceAppendReceipt`` durability-proof shape.

``key_generation`` is ``int`` throughout (team-lead correction, 2026-09-08): it is
the same monotonic axis as the pre-existing ``IntegrityAnchor.key_generation`` /
``SegmentCommitmentScheme.link_anchor`` Protocol parameter, not a separate string
label.

Known-answer derivation (Python one-liner, run once to produce the fixtures below)::

    import hashlib, hmac
    key = b"test-key-material-32-bytes-long"
    d1 = hashlib.sha256(b"record-one").hexdigest()
    d2 = hashlib.sha256(b"record-two").hexdigest()
    link1 = hmac.new(key, b"" + d1.encode(), hashlib.sha256).hexdigest()
    link2 = hmac.new(key, link1.encode() + d2.encode(), hashlib.sha256).hexdigest()
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.canonical import ArtifactIntegrityError
from tos.evidence import (
    EV_L2_SHA256_HMAC_CHAIN_VERSION,
    ChainedEntry,
    EvidenceAppendReceipt,
    SegmentCommitmentScheme,
    Sha256HmacChainScheme,
    verify_chain,
)

_KEY = b"test-key-material-32-bytes-long"
_KEY_GENERATION = 1
_D1 = "15b3cc804fba51afb8e484c6aa398a910c3b4de0bb1c7e4502511ae3fbe6f516"
_D2 = "5f2bb7d45a5203c8bea387d1236592dca74c632a07437b195c252f8a10144bb4"
_LINK1 = "fa2b0149c0da04f5f4ce07db5125a388f2b608b33bc55ec2bdb7249c04d5eee0"
_LINK2 = "dac0acc036661e8f6bc76e42d83e2e32931e9334ab80c8dc4cbb2bc9a6436c63"


def _scheme() -> Sha256HmacChainScheme:
    return Sha256HmacChainScheme(key=_KEY, key_generation=_KEY_GENERATION)


# ===========================================================================
# construction + Protocol conformance
# ===========================================================================


def test_scheme_satisfies_segment_commitment_scheme_protocol() -> None:
    scheme = _scheme()
    assert isinstance(scheme, SegmentCommitmentScheme)
    assert scheme.version == EV_L2_SHA256_HMAC_CHAIN_VERSION
    assert scheme.key_generation == _KEY_GENERATION


def test_empty_key_is_rejected() -> None:
    with pytest.raises(ArtifactIntegrityError):
        Sha256HmacChainScheme(key=b"", key_generation=_KEY_GENERATION)


@pytest.mark.parametrize("bad_generation", [None, -1, -100])
def test_negative_or_missing_key_generation_is_rejected(bad_generation) -> None:
    with pytest.raises(ArtifactIntegrityError):
        Sha256HmacChainScheme(key=_KEY, key_generation=bad_generation)


def test_zero_key_generation_is_accepted() -> None:
    """Zero is a valid (the initial) key generation."""
    scheme = Sha256HmacChainScheme(key=_KEY, key_generation=0)
    assert scheme.key_generation == 0


def test_custom_version_is_honored() -> None:
    scheme = Sha256HmacChainScheme(
        key=_KEY, key_generation=_KEY_GENERATION, version="ev-l2-sha256-hmac-chain-2"
    )
    assert scheme.version == "ev-l2-sha256-hmac-chain-2"


# ===========================================================================
# known-answer test (fixed key, hand-derived expected hex — see module docstring)
# ===========================================================================


def test_known_answer_single_entry_commit() -> None:
    scheme = _scheme()
    assert scheme.commit((_D1,)) == _LINK1


def test_known_answer_two_entry_commit() -> None:
    scheme = _scheme()
    assert scheme.commit((_D1, _D2)) == _LINK2


def test_known_answer_verify_append_matches_direct_commit() -> None:
    scheme = _scheme()
    prefix_commitment = scheme.commit((_D1,))
    assert scheme.verify_append(prefix_commitment, (_D2,)) == scheme.commit((_D1, _D2))


# ===========================================================================
# membership verification: positive + negative (tampering)
# ===========================================================================


def test_membership_verifies_at_correct_position() -> None:
    scheme = _scheme()
    commitment = scheme.commit((_D1, _D2))
    assert scheme.verify_membership(_D1, 0, commitment, (_D1, _D2))
    assert scheme.verify_membership(_D2, 1, commitment, (_D1, _D2))


def test_membership_rejects_out_of_range_position() -> None:
    scheme = _scheme()
    commitment = scheme.commit((_D1, _D2))
    assert not scheme.verify_membership(_D1, -1, commitment, (_D1, _D2))
    assert not scheme.verify_membership(_D1, 5, commitment, (_D1, _D2))


def test_tampered_entry_digest_is_detected() -> None:
    """Substituting a record digest breaks membership verification."""
    scheme = _scheme()
    commitment = scheme.commit((_D1, _D2))
    tampered_proof = ("__tampered__", _D2)
    assert not scheme.verify_membership("__tampered__", 0, commitment, tampered_proof)


def test_wrong_key_fails_to_reproduce_commitment() -> None:
    """A different key produces a different chain digest for the same content."""
    honest = Sha256HmacChainScheme(key=_KEY, key_generation=_KEY_GENERATION)
    dishonest = Sha256HmacChainScheme(
        key=b"a-completely-different-key-32by", key_generation=_KEY_GENERATION
    )
    assert honest.commit((_D1, _D2)) != dishonest.commit((_D1, _D2))


# ===========================================================================
# link_anchor
# ===========================================================================


def test_link_anchor_binds_commitment_and_is_deterministic() -> None:
    scheme = _scheme()
    commitment = scheme.commit((_D1,))
    anchor_a = scheme.link_anchor(commitment, predecessor_anchor=None)
    anchor_b = scheme.link_anchor(commitment, predecessor_anchor=None)
    assert anchor_a.anchor_id == anchor_b.anchor_id
    assert anchor_a.segment_commitment == commitment


def test_link_anchor_chains_to_predecessor() -> None:
    scheme = _scheme()
    commitment = scheme.commit((_D1,))
    first = scheme.link_anchor(commitment, predecessor_anchor=None)
    second = scheme.link_anchor(
        scheme.commit((_D1, _D2)), predecessor_anchor=first.anchor_id
    )
    assert second.predecessor_anchor == first.anchor_id


def test_link_anchor_defaults_key_generation_to_the_schemes_own() -> None:
    """When the caller does not override key_generation, the produced anchor's
    key_generation equals the scheme's own — one axis, not two (team-lead
    correction 2026-09-08)."""
    scheme = _scheme()
    anchor = scheme.link_anchor(scheme.commit((_D1,)))
    assert anchor.key_generation == scheme.key_generation == _KEY_GENERATION


def test_link_anchor_explicit_key_generation_overrides_the_default() -> None:
    """A caller MAY still pass a different key_generation explicitly (e.g. binding
    an anchor to a prior generation during a rotation window)."""
    scheme = _scheme()
    anchor = scheme.link_anchor(scheme.commit((_D1,)), key_generation=7)
    assert anchor.key_generation == 7
    assert scheme.key_generation == _KEY_GENERATION  # the scheme itself is untouched


# ===========================================================================
# verify_chain: positive, tampering, missing generation, rotation
# ===========================================================================


def test_verify_chain_empty_entries_is_vacuously_true() -> None:
    assert verify_chain((), {_KEY_GENERATION: _KEY}) is True


def test_verify_chain_verifies_a_two_link_chain() -> None:
    entries = (
        ChainedEntry(
            entry_digest=_D1, key_generation=_KEY_GENERATION, chain_digest=_LINK1
        ),
        ChainedEntry(
            entry_digest=_D2, key_generation=_KEY_GENERATION, chain_digest=_LINK2
        ),
    )
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is True


def test_verify_chain_detects_tampered_entry_digest() -> None:
    entries = (
        ChainedEntry(
            entry_digest="__tampered__",
            key_generation=_KEY_GENERATION,
            chain_digest=_LINK1,
        ),
        ChainedEntry(
            entry_digest=_D2, key_generation=_KEY_GENERATION, chain_digest=_LINK2
        ),
    )
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is False


def test_verify_chain_detects_tampered_prev_link() -> None:
    """The second link was computed over a different (tampered) prev commitment,
    so it fails to re-derive even though its own claimed values look internally
    consistent in isolation."""
    entries = (
        ChainedEntry(
            entry_digest=_D1,
            key_generation=_KEY_GENERATION,
            chain_digest="__wrong_link1__",
        ),
        ChainedEntry(
            entry_digest=_D2, key_generation=_KEY_GENERATION, chain_digest=_LINK2
        ),
    )
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is False


def test_verify_chain_missing_key_generation_fails_closed() -> None:
    """A generation absent from keys_by_generation fails the whole chain — never
    silently skipped, never treated as vacuously valid (playbook §2.A)."""
    entries = (ChainedEntry(entry_digest=_D1, key_generation=999, chain_digest=_LINK1),)
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is False
    assert verify_chain(entries, {}) is False


@pytest.mark.parametrize(
    "entry_digest,key_generation,chain_digest",
    [
        (None, _KEY_GENERATION, _LINK1),
        (_D1, None, _LINK1),
        (_D1, _KEY_GENERATION, None),
    ],
)
def test_verify_chain_none_axis_fails_closed(
    entry_digest, key_generation, chain_digest
) -> None:
    entries = (
        ChainedEntry(
            entry_digest=entry_digest,
            key_generation=key_generation,
            chain_digest=chain_digest,
        ),
    )
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is False


def test_verify_chain_rotation_across_two_generations_positive() -> None:
    """A chain whose first link is signed under generation 1 and whose second
    link is signed under generation 2 (a rotation mid-chain) verifies correctly
    when both keys are supplied — each link is checked with the key of its OWN
    recorded generation, not a single "current" key (design #40 D4.1 rotation
    semantics)."""
    key_2 = b"second-generation-key-material!"
    key_generation_2 = 2

    scheme_1 = Sha256HmacChainScheme(key=_KEY, key_generation=_KEY_GENERATION)
    link1 = scheme_1.commit((_D1,))

    scheme_2 = Sha256HmacChainScheme(key=key_2, key_generation=key_generation_2)
    link2 = scheme_2.verify_append(link1, (_D2,))

    entries = (
        ChainedEntry(
            entry_digest=_D1, key_generation=_KEY_GENERATION, chain_digest=link1
        ),
        ChainedEntry(
            entry_digest=_D2, key_generation=key_generation_2, chain_digest=link2
        ),
    )
    keys_by_generation = {_KEY_GENERATION: _KEY, key_generation_2: key_2}
    assert verify_chain(entries, keys_by_generation) is True

    # Sanity: verifying with only ONE of the two keys fails closed (missing
    # generation for the other link), proving the test actually exercises both.
    assert verify_chain(entries, {_KEY_GENERATION: _KEY}) is False
    assert verify_chain(entries, {key_generation_2: key_2}) is False


def test_verify_chain_rotation_with_wrong_second_key_is_detected() -> None:
    """Rotation to the WRONG key for the recorded generation fails, not passes."""
    key_2 = b"second-generation-key-material!"
    wrong_key_2 = b"an-entirely-different-key-value"
    key_generation_2 = 2

    scheme_1 = Sha256HmacChainScheme(key=_KEY, key_generation=_KEY_GENERATION)
    link1 = scheme_1.commit((_D1,))
    scheme_2 = Sha256HmacChainScheme(key=key_2, key_generation=key_generation_2)
    link2 = scheme_2.verify_append(link1, (_D2,))

    entries = (
        ChainedEntry(
            entry_digest=_D1, key_generation=_KEY_GENERATION, chain_digest=link1
        ),
        ChainedEntry(
            entry_digest=_D2, key_generation=key_generation_2, chain_digest=link2
        ),
    )
    assert (
        verify_chain(entries, {_KEY_GENERATION: _KEY, key_generation_2: wrong_key_2})
        is False
    )


# ===========================================================================
# EvidenceAppendReceipt
# ===========================================================================


def test_append_receipt_default_durable_is_true() -> None:
    receipt = EvidenceAppendReceipt(
        segment_id="seg-1", seq=0, chain_digest=_LINK1, key_generation=_KEY_GENERATION
    )
    assert receipt.durable is True


def test_append_receipt_durable_cannot_be_false() -> None:
    """durable: Literal[True] — there is no False variant constructible."""
    with pytest.raises((TypeError, ValueError)):
        EvidenceAppendReceipt(durable=False)  # type: ignore[arg-type]


@pytest.mark.parametrize("seq", [-1, -100])
def test_append_receipt_rejects_negative_seq(seq: int) -> None:
    with pytest.raises(ValidationError):
        EvidenceAppendReceipt(seq=seq)


def test_append_receipt_accepts_zero_seq() -> None:
    receipt = EvidenceAppendReceipt(seq=0)
    assert receipt.seq == 0


def test_append_receipt_is_distinct_from_phase1_evidence_commit_receipt() -> None:
    """Anti-collision: EvidenceAppendReceipt is NOT the same symbol as the
    pre-existing, UNVERIFIED-only tos.evidence.receipt.EvidenceCommitReceipt."""
    from tos.evidence import EvidenceCommitReceipt

    assert EvidenceAppendReceipt is not EvidenceCommitReceipt
    # The Phase-1 receipt has no `durable` field at all — it proves no
    # durability by construction (receipt.py docstring "Phase-1 honesty");
    # EvidenceAppendReceipt's whole purpose is that it can, via Literal[True].
    assert "durable" not in EvidenceCommitReceipt.model_fields
    assert "durable" in EvidenceAppendReceipt.model_fields
