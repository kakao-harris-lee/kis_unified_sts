"""Pin tests for the kernel half of the read-only-member Protocol sweep"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from tos.canonical import CanonicalizationScheme, EVL1ProvisionalCanonicalizer
from tos.evidence import (
    IntegrityAnchor,
    ProvisionalHashChainScheme,
    SegmentCommitmentScheme,
    Sha256HmacChainScheme,
)


def _real_canonicalization(x: EVL1ProvisionalCanonicalizer) -> CanonicalizationScheme:
    return x


def _real_segment_commitment_provisional(
    x: ProvisionalHashChainScheme,
) -> SegmentCommitmentScheme:
    return x


def _real_segment_commitment_sha256_hmac(
    x: Sha256HmacChainScheme,
) -> SegmentCommitmentScheme:
    return x


@dataclass(frozen=True)
class _FrozenCanonicalizationScheme:
    """A frozen double for :class:`CanonicalizationScheme` — every real implementer"""

    version: str

    def canonical_bytes(self, covered: Mapping[str, Any]) -> bytes:
        raise NotImplementedError

    def compute_digest(self, covered: Mapping[str, Any]) -> str:
        raise NotImplementedError


def _frozen_canonicalization(
    x: _FrozenCanonicalizationScheme,
) -> CanonicalizationScheme:
    return x


@dataclass(frozen=True)
class _FrozenSegmentCommitmentScheme:
    """A frozen double for :class:`SegmentCommitmentScheme` — every real implementer"""

    version: str

    def commit(self, ordered_record_digests: tuple[str, ...]) -> str:
        raise NotImplementedError

    def verify_membership(
        self,
        record_digest: str,
        position: int,
        commitment: str,
        proof: tuple[str, ...],
    ) -> bool:
        raise NotImplementedError

    def verify_append(
        self, prev_commitment: str, appended_digests: tuple[str, ...]
    ) -> str:
        raise NotImplementedError

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
        raise NotImplementedError


def _frozen_segment_commitment(
    x: _FrozenSegmentCommitmentScheme,
) -> SegmentCommitmentScheme:
    return x


_PROPERTY_MEMBERS = (
    (CanonicalizationScheme, "version"),
    (SegmentCommitmentScheme, "version"),
)


def test_members_are_read_only_properties() -> None:
    """Reverting ``version`` back to a plain ``version: str`` annotation on either"""
    for protocol, member in _PROPERTY_MEMBERS:
        assert inspect.isdatadescriptor(inspect.getattr_static(protocol, member))


def test_frozen_canonicalization_scheme_satisfies_protocol_isinstance() -> None:
    double = _FrozenCanonicalizationScheme(version="test-version")
    assert isinstance(double, CanonicalizationScheme)


def test_frozen_segment_commitment_scheme_satisfies_protocol_isinstance() -> None:
    double = _FrozenSegmentCommitmentScheme(version="test-version")
    assert isinstance(double, SegmentCommitmentScheme)
