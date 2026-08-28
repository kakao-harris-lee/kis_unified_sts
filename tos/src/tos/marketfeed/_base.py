"""Marketfeed-local base — the reused canonical substrate + the fetch-absence seal.

The digest-binding substrate (:class:`~tos.canonical.FrozenModel`,
:class:`~tos.canonical.CanonicalizationScheme`, :func:`~tos.canonical.get_scheme`,
:class:`~tos.canonical.ArtifactIntegrityError`) is reused verbatim from :mod:`tos.canonical` —
the series "재정의 금지" discipline (design #32 §12.1 REUSE). This module adds only what D-E2 owns:

* :class:`MarketFeedIntegrityError` — a structural seal breach, raised, never warned;
* :func:`seal_fetch_surface` / :data:`FETCH_SURFACE_TOKENS` — the **structural** form of RFC-004
  §9:242-244 "never by unattributed fetch or side channel". ``tos.marketfeed`` receives values by
  injection; it opens nothing. A docstring promising that is a self-report, so instead every
  marketfeed record runs its own field names through this check at construction: a field named
  ``fetch_url`` / ``endpoint_socket`` / ``websocket`` makes the model unconstructable. The import
  closure canary covers the *module* level (no ``socket`` / ``urllib`` / ``os.environ`` anywhere);
  this covers the *data* level, where a "just a string" field could smuggle a live source back in.

Matching is **token-wise** (split on ``_``, plus the whole name), never a bare substring: a
substring rule would reject ``field_key`` for containing "fetch"-adjacent letters and over-rejection
is its own defect class (the #26 WDR MAJOR-1 lesson).

⚠ **Provisional; closes no EV** (design #32 §1.1).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #1 §3.2). No clock, no RNG, no network.
"""

from __future__ import annotations

from collections.abc import Iterable

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalizationScheme,
    FrozenModel,
    get_scheme,
)

__all__ = [
    "FETCH_SURFACE_TOKENS",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalizationScheme",
    "FrozenModel",
    "MarketFeedIntegrityError",
    "fetch_surface_offenders",
    "get_scheme",
    "seal_fetch_surface",
]


class MarketFeedIntegrityError(ArtifactIntegrityError):
    """A D-E2 value-surface artifact breached a structural seal (fail-closed, never a warning)."""


#: The closed set of field-name tokens a marketfeed record may **not** carry (design #32 §0.3/§7.1).
#: Two families: live-transport surfaces (url / uri / host / port / socket / websocket / stream /
#: session / connection) and credential surfaces (token / secret / credential / apikey / password).
#: The first would make the package a transport; the second would make it a secret holder. It is
#: neither: values arrive already admitted, and the observation's ``trust_identity.credential_ref``
#: is a *reference* held by ``tos.capsule``, never a secret held here (design #2 §2.2).
FETCH_SURFACE_TOKENS: frozenset[str] = frozenset(
    {
        "api",
        "apikey",
        "connection",
        "credential",
        "credentials",
        "fetch",
        "host",
        "hostname",
        "password",
        "port",
        "secret",
        "socket",
        "stream",
        "subscribe",
        "subscription",
        "token",
        "uri",
        "url",
        "websocket",
    }
)
#: ⚠ ``endpoint`` is deliberately **absent**. ``tos.capsule``'s shipped ``SourceIdentity.endpoint``
#: (``observation.py:39``) is an opaque provenance scalar this package legitimately *reads* to
#: attribute a value, and a candidate record that echoed that provenance would be wrongly rejected.
#: The transport intent is already covered by ``url`` / ``host`` / ``socket`` / ``connection``.


def fetch_surface_offenders(field_names: Iterable[str]) -> tuple[str, ...]:
    """Field names that would give a marketfeed record a live-fetch or credential surface.

    Args:
        field_names: The candidate field names.

    Returns:
        The offending names, in the order supplied (empty when the surface is clean).
    """
    offenders: list[str] = []
    for name in field_names:
        lowered = name.lower()
        parts = {part for part in lowered.split("_") if part}
        if lowered in FETCH_SURFACE_TOKENS or parts & FETCH_SURFACE_TOKENS:
            offenders.append(name)
    return tuple(offenders)


def seal_fetch_surface(owner: str, field_names: Iterable[str]) -> None:
    """Raise if ``field_names`` would give ``owner`` a live-fetch / credential surface.

    Args:
        owner: The structure's name (recorded in the error).
        field_names: Its declared field names.

    Raises:
        MarketFeedIntegrityError: If any field name carries a forbidden token — the structural form
            of "the value surface receives, it never fetches" (RFC-004 §9:242-244; design #32
            §0.3/§7.1).
    """
    offenders = fetch_surface_offenders(field_names)
    if offenders:
        raise MarketFeedIntegrityError(
            f"{owner} declares {list(offenders)} — a D-E2 value-surface record carries no "
            "transport or credential field. Market values reach a decision only as admitted, "
            "attributed Critical Input, never by unattributed fetch or side channel "
            "(RFC-004 §9:242-244; design #32 §0.3)"
        )
