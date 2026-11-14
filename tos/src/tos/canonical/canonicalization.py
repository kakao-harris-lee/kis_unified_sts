"""Canonicalization + digest contract (design #2 §3 / design #4 §3)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Annotated, Any, Protocol, runtime_checkable

from pydantic import BeforeValidator

EV_L1_PROVISIONAL_VERSION = "ev-l1-provisional-0"

DigestFactory = Callable[[], "hashlib._Hash"]


@runtime_checkable
class CanonicalizationScheme(Protocol):
    """A versioned canonicalizer + digest algorithm (design §3.1)."""

    @property
    def version(self) -> str: ...

    def canonical_bytes(self, covered: Mapping[str, Any]) -> bytes:
        """Serialize ``covered`` to canonical bytes."""
        ...

    def compute_digest(self, covered: Mapping[str, Any]) -> str:
        """Return the hex digest of ``canonical_bytes(covered)``."""
        ...


def _num_token(value: int | float | Decimal) -> str:
    """Normalize a numeric magnitude to an exponent-free decimal token."""
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    dec = dec.normalize()
    if dec == 0:
        return "0"
    return format(dec, "f")


def _normalize_decimal(value: object) -> object:
    """Collapse numerically-equal Decimals to one canonical form (canonical §3.1a)."""
    if not isinstance(value, (Decimal, int, float, str)) or isinstance(value, bool):
        return value
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    dec = dec.normalize()
    return Decimal(0) if dec == 0 else dec


CanonicalDecimal = Annotated[Decimal, BeforeValidator(_normalize_decimal)]


def _encode(value: Any) -> str:
    """Recursively encode ``value`` to a canonical, injective token string."""
    if value is None:
        return "N"
    if isinstance(value, bool):
        return "B1" if value else "B0"
    if isinstance(value, (int, float, Decimal)):
        return "D:" + _num_token(value)
    if isinstance(value, str):
        return f"S{len(value)}:{value}"
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda kv: str(kv[0]))
        inner = ";".join(f"S{len(str(k))}:{k}={_encode(v)}" for k, v in items)
        return "M{" + inner + "}"
    if isinstance(value, Sequence):
        return "L[" + ",".join(_encode(v) for v in value) + "]"
    raise TypeError(f"non-canonical value of type {type(value).__name__!r}")


class EVL1ProvisionalCanonicalizer:
    """Provisional, **non-production** EV-L1 canonicalizer (design §3.4)."""

    def __init__(
        self,
        *,
        version: str = EV_L1_PROVISIONAL_VERSION,
        digest_factory: DigestFactory = hashlib.sha256,
    ) -> None:
        """Initialize the provisional canonicalizer."""
        self.version = version
        self._digest_factory = digest_factory

    def canonical_bytes(self, covered: Mapping[str, Any]) -> bytes:
        """Return UTF-8 canonical bytes for ``covered`` (design §3.4)."""
        return _encode(dict(covered)).encode("utf-8")

    def compute_digest(self, covered: Mapping[str, Any]) -> str:
        """Return the hex digest of the canonical bytes of ``covered``."""
        hasher = self._digest_factory()
        hasher.update(self.canonical_bytes(covered))
        return hasher.hexdigest()


_REGISTRY: dict[str, CanonicalizationScheme] = {}


def register_scheme(scheme: CanonicalizationScheme) -> CanonicalizationScheme:
    """Register ``scheme`` under its ``version`` (design §3.1)."""
    _REGISTRY[scheme.version] = scheme
    return scheme


def get_scheme(version: str | None) -> CanonicalizationScheme:
    """Resolve a registered scheme by ``version`` (design §3.1, §4.1/§4.2)."""
    if version is None or version not in _REGISTRY:
        from tos.canonical._base import ArtifactIntegrityError

        raise ArtifactIntegrityError(
            f"no canonicalization scheme registered for {version!r} — the digest "
            "cannot be recomputed, so artifact integrity cannot be established "
            "(design §3.1; EV-L2 pilot design §5 H-4)"
        )
    return _REGISTRY[version]


register_scheme(EVL1ProvisionalCanonicalizer())
