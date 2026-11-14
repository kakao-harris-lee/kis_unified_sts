"""Marketfeed-local base — the reused canonical substrate + the fetch-absence seal."""

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


def fetch_surface_offenders(field_names: Iterable[str]) -> tuple[str, ...]:
    """Field names that would give a marketfeed record a live-fetch or credential surface."""
    offenders: list[str] = []
    for name in field_names:
        lowered = name.lower()
        parts = {part for part in lowered.split("_") if part}
        if lowered in FETCH_SURFACE_TOKENS or parts & FETCH_SURFACE_TOKENS:
            offenders.append(name)
    return tuple(offenders)


def seal_fetch_surface(owner: str, field_names: Iterable[str]) -> None:
    """Raise if ``field_names`` would give ``owner`` a live-fetch / credential surface."""
    offenders = fetch_surface_offenders(field_names)
    if offenders:
        raise MarketFeedIntegrityError(
            f"{owner} declares {list(offenders)} — a D-E2 value-surface record carries no "
            "transport or credential field. Market values reach a decision only as admitted, "
            "attributed Critical Input, never by unattributed fetch or side channel "
            "(RFC-004 §9:242-244; design #32 §0.3)"
        )
