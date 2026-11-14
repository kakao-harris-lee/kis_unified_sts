"""Per-attempt request-bytes digest sources (T2 lane A — codec digest binding, plan"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from tos.canonical import EV_L1_PROVISIONAL_VERSION, CanonicalDecimal, get_scheme

from tos_runtime.transport.kis_mock.codec import KisOrderWireCodec

if TYPE_CHECKING:
    from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "CapsuleStandInDigest",
    "KisWireCodecDigest",
    "RequestBytesDigestSource",
    "default_request_bytes_digest_source",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


@runtime_checkable
class RequestBytesDigestSource(Protocol):
    """The ONE per-attempt digest :class:`~tos_runtime.compose.context.ComposeContextResolver`"""

    def __call__(
        self,
        *,
        account: str,
        instrument: str,
        quantity: CanonicalDecimal,
        price: CanonicalDecimal,
    ) -> str:
        """Compute this attempt's request-bytes digest."""
        ...


@dataclass(frozen=True)
class CapsuleStandInDigest:
    """The unchanged capsule-terminus stand-in (module docstring) — returns the SAME boot-time"""

    digest: str

    def __call__(
        self,
        *,
        account: str,  # noqa: ARG002 - stand-in: deliberately ignores every argument
        instrument: str,  # noqa: ARG002
        quantity: CanonicalDecimal,  # noqa: ARG002
        price: CanonicalDecimal,  # noqa: ARG002
    ) -> str:
        return self.digest


@dataclass(frozen=True)
class KisWireCodecDigest:
    """The genuine KIS-wire-codec digest (module docstring) — a ``sha256`` of"""

    field_map: Mapping[str, str]
    static_body_fields: Mapping[str, str]
    price_scale: int

    def __call__(
        self,
        *,
        account: str,
        instrument: str,
        quantity: CanonicalDecimal,
        price: CanonicalDecimal,
    ) -> str:
        body = KisOrderWireCodec.encode_fields(
            account=account,
            instrument=instrument,
            quantity=quantity,
            price=price,
            field_map=self.field_map,
            static_body_fields=self.static_body_fields,
            price_scale=self.price_scale,
        )
        return KisOrderWireCodec.digest(body)


def default_request_bytes_digest_source(
    construction: ConstructionConfig, capsule_terminus_fields: Iterable[str]
) -> CapsuleStandInDigest:
    """Build the DEFAULT :class:`CapsuleStandInDigest` (T2 lane C — moved out of"""
    return CapsuleStandInDigest(
        digest=_SCHEME.compute_digest(
            {name: getattr(construction, name) for name in capsule_terminus_fields}
        )
    )
