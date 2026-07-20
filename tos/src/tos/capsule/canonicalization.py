"""Canonicalization + digest contract (design §3).

ADR-002-018 OQ1 (line 641) and §28 gate item 1 (line 660) leave the production
canonical serialization *and* digest algorithm as unapproved open questions.
This module therefore never hard-codes a production choice. Instead:

* A :class:`CanonicalizationScheme` bundles a canonical-serialization function
  with an **injected** digest algorithm, and is identified by a versioned
  ``version`` string (design §3.1 — precedent:
  ``ORDER-CONFORMANCE-PROOF.construction_identity.canonicalization_version``).
* Artifacts record their ``canonicalization_version`` and resolve the matching
  scheme from a registry, so the digest invariant (design §4.1) is
  self-verifying on every construction.
* :class:`EVL1ProvisionalCanonicalizer` (``ev-l1-provisional-0``) is the
  **explicitly non-production** fixture used for EV-L1 property tests
  (design §3.4). Approving a production scheme means registering a new version;
  the must-pass property suite (design §3.4 (A)) regresses against it unchanged.

The default digest algorithm is ``hashlib.sha256`` — a stdlib primitive chosen
for reproducible tests, **not** a production selection (design §3.1, §9.2 item
1). It is injectable via ``digest_factory``.

Open question (revisit before introducing a second scheme): the
``canonicalization_version`` is stored as a meta envelope but excluded from both
the digest preimage and the derived ``id = f(digest)`` (design §2.6 template
byte-alignment). With a single provisional scheme this is harmless, but once
multiple schemes coexist the same covered content under two schemes could yield
the same digest -> same id, i.e. a cross-scheme identity collision. Resolving
this (folding the version into the preimage/id, or namespacing ids by version)
belongs to the production canonicalization + id policy (design §9.2 items 1/6,
Phase-0). Do not rely on version being part of identity until then.

Pure module: stdlib only (``hashlib``, ``decimal``); no ``numpy``/``pandas``
(design §0.3 closure minimisation), no ``shared.*``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

#: Canonicalization version string of the provisional EV-L1 fixture (design §3.4).
EV_L1_PROVISIONAL_VERSION = "ev-l1-provisional-0"

#: Non-production default digest algorithm (design §3.1). Injectable.
DigestFactory = Callable[[], "hashlib._Hash"]


@runtime_checkable
class CanonicalizationScheme(Protocol):
    """A versioned canonicalizer + digest algorithm (design §3.1).

    Implementations map a *covered* content mapping (the digest preimage, with
    the §3.2 self-exclusion set already removed by the caller) to canonical
    bytes and a hex digest.
    """

    version: str

    def canonical_bytes(self, covered: Mapping[str, Any]) -> bytes:
        """Serialize ``covered`` to canonical bytes."""
        ...

    def compute_digest(self, covered: Mapping[str, Any]) -> str:
        """Return the hex digest of ``canonical_bytes(covered)``."""
        ...


def _num_token(value: int | float | Decimal) -> str:
    """Normalize a numeric magnitude to an exponent-free decimal token.

    This is the design §3.4 (B) magnitude normalization: ``1.0`` == ``1.00`` and
    float binary noise is discarded. It applies **only** to a numeric leaf value;
    it never merges the separate ``scale``/``unit``/``multiplier``/``sign``
    metadata fields (those are distinct string keys, preserved verbatim — design
    §3.4 safety-significant-distinction preservation).

    Args:
        value: A numeric leaf (``int``, ``float``, or ``Decimal``).

    Returns:
        A canonical, exponent-free decimal string (e.g. ``"1"``, ``"1.5"``).
    """
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    dec = dec.normalize()
    if dec == 0:  # collapse -0 / 0E+n quirks to a single "0"
        return "0"
    return format(dec, "f")


def _encode(value: Any) -> str:
    """Recursively encode ``value`` to a canonical, injective token string.

    Type-tagged and length-prefixed so that distinct covered content cannot
    collapse to one canonical form on the modelled domain (design §3.4 (A5)
    injectivity). Mappings are key-sorted (design §3.4 (A2) key-order
    independence); sequence order is preserved (vectors are order-significant).

    Args:
        value: A JSON-native value (``None``/``bool``/number/``str``/mapping/
            sequence) or ``Decimal``.

    Returns:
        The canonical token string for ``value``.

    Raises:
        TypeError: If ``value`` is not a supported canonical type.
    """
    if value is None:
        return "N"
    # bool is an int subclass — must be checked before int/float.
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
    if isinstance(value, Sequence):  # list/tuple (str already handled above)
        return "L[" + ",".join(_encode(v) for v in value) + "]"
    raise TypeError(f"non-canonical value of type {type(value).__name__!r}")


class EVL1ProvisionalCanonicalizer:
    """Provisional, **non-production** EV-L1 canonicalizer (design §3.4).

    Recursive key-sorted, UTF-8, magnitude-decimal-normalized. The digest
    algorithm is injected (default ``hashlib.sha256``); neither the serialization
    nor the algorithm is a production selection (design §9.2 items 1 and 4).

    Any production canonicalizer registered later MUST pass the design §3.4 (A)
    must-pass property suite; the (B) magnitude property is bound to this
    fixture only and does not pre-empt the production numeric canonical form.
    """

    def __init__(
        self,
        *,
        version: str = EV_L1_PROVISIONAL_VERSION,
        digest_factory: DigestFactory = hashlib.sha256,
    ) -> None:
        """Initialize the provisional canonicalizer.

        Args:
            version: The canonicalization-version identifier this instance binds.
            digest_factory: Zero-arg callable returning a fresh hashlib-style
                hasher. Injectable to demonstrate digest-algorithm independence
                of the must-pass properties; default is the non-production
                ``hashlib.sha256``.
        """
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


# ---------------------------------------------------------------------------
# Scheme registry (design §3.1 — versions resolve to schemes)
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, CanonicalizationScheme] = {}


def register_scheme(scheme: CanonicalizationScheme) -> CanonicalizationScheme:
    """Register ``scheme`` under its ``version`` (design §3.1).

    Args:
        scheme: The scheme to register.

    Returns:
        The registered scheme (for convenient chaining).
    """
    _REGISTRY[scheme.version] = scheme
    return scheme


def get_scheme(version: str | None) -> CanonicalizationScheme:
    """Resolve a registered scheme by ``version`` (design §3.1, §4.1).

    Args:
        version: The ``canonicalization_version`` recorded on an artifact.

    Returns:
        The registered :class:`CanonicalizationScheme`.

    Raises:
        KeyError: If no scheme is registered for ``version`` (or it is ``None``).
    """
    if version is None or version not in _REGISTRY:
        raise KeyError(f"no canonicalization scheme registered for {version!r}")
    return _REGISTRY[version]


# The provisional EV-L1 fixture is registered by default so freshly-constructed
# artifacts can self-verify their digest (design §4.1).
register_scheme(EVL1ProvisionalCanonicalizer())
