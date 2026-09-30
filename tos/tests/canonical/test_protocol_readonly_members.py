"""Pin tests for the kernel half of the read-only-member Protocol sweep
(docs/plans/2026-09-23-tos-protocol-readonly-members-sweep-plan.md §2/§3).

``CanonicalizationScheme.version`` and ``SegmentCommitmentScheme.version`` were
converted from plain (settable) attributes to read-only ``@property`` members so a
frozen implementation (dataclass ``frozen=True`` / pydantic frozen model) can satisfy
either Protocol structurally — today's implementers are all mutable, so nothing here
regressed a real caller, but nothing mechanical prevented a future frozen implementer
from hitting the same break the runtime half of this sweep found already latent
(``_RecoveryVerdictLike`` / ``_ComposedForDrill``, see the runtime pin file). This
file pins the conversion two ways (plan §3 — one alone is not enough):

(i) **mypy conformance functions** — module-level, fully annotated, never called;
checked only by the test-tree mypy step
(``mypy tos/tests --disable-error-code=no-untyped-def``).
(ii) **runtime data-descriptor check** — reverting ``version`` to a plain attribute
leaves no class-level descriptor (only ``__annotations__``), so
``inspect.getattr_static`` raises ``AttributeError``.

Both Protocols are ``@runtime_checkable``, so this file also pins that ``isinstance``
still sees the frozen doubles as conforming (existence-only check — this is exactly
why (ii) is needed: ``isinstance`` alone would NOT catch a plain-attribute regression,
per the plan's mutation ③).

Kernel test — does not import ``tos_runtime`` (import firewall, ``tos/CLAUDE.md``).
"""

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

# ===========================================================================
# (i) mypy conformance functions — real implementers
# ===========================================================================


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


# ===========================================================================
# (i) mypy conformance functions — frozen doubles
# ===========================================================================


@dataclass(frozen=True)
class _FrozenCanonicalizationScheme:
    """A frozen double for :class:`CanonicalizationScheme` — every real implementer
    today is mutable, so only this double would have caught a regression to a plain
    attribute for ``version``."""

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
    """A frozen double for :class:`SegmentCommitmentScheme` — every real implementer
    today is mutable, so only this double would have caught a regression to a plain
    attribute for ``version``."""

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


# ===========================================================================
# (ii) runtime data-descriptor check
# ===========================================================================

#: The plan §1 inventory of kernel Protocol / member pairs converted to read-only
#: properties (2 Protocols, 2 members — the runtime's 5 Protocols / 8 members are
#: pinned separately in
#: ``tos/runtime/tests/operations/test_protocol_readonly_members.py``).
_PROPERTY_MEMBERS = (
    (CanonicalizationScheme, "version"),
    (SegmentCommitmentScheme, "version"),
)


def test_members_are_read_only_properties() -> None:
    """Reverting ``version`` back to a plain ``version: str`` annotation on either
    Protocol leaves no class-level descriptor at all (only ``__annotations__``), so
    ``inspect.getattr_static`` raises ``AttributeError`` instead of returning a
    ``property``."""
    for protocol, member in _PROPERTY_MEMBERS:
        assert inspect.isdatadescriptor(inspect.getattr_static(protocol, member))


# ===========================================================================
# @runtime_checkable isinstance — existence-only, does not by itself catch a
# plain-attribute regression (plan §3 mutation ③); kept as a companion pin, not a
# substitute for (ii) above.
# ===========================================================================


def test_frozen_canonicalization_scheme_satisfies_protocol_isinstance() -> None:
    double = _FrozenCanonicalizationScheme(version="test-version")
    assert isinstance(double, CanonicalizationScheme)


def test_frozen_segment_commitment_scheme_satisfies_protocol_isinstance() -> None:
    double = _FrozenSegmentCommitmentScheme(version="test-version")
    assert isinstance(double, SegmentCommitmentScheme)
