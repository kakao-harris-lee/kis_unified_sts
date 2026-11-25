"""Backtest-local base — the reused canonical substrate + the §1.2 performance-surface seal."""

from __future__ import annotations

from collections.abc import Iterable

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    derive_id,
    get_scheme,
)

__all__ = [
    "PERFORMANCE_SURFACE_TOKENS",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "BacktestIntegrityError",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "FrozenModel",
    "derive_id",
    "get_scheme",
    "performance_surface_offenders",
    "seal_performance_surface",
]


class BacktestIntegrityError(ArtifactIntegrityError):
    """A D-E3 harness artifact breached a structural seal (fail-closed, never a warning)."""


PERFORMANCE_SURFACE_TOKENS: frozenset[str] = frozenset(
    {
        "admissibility",
        "admissible",
        "alpha",
        "cagr",
        "drawdown",
        "edge",
        "equity",
        "expectancy",
        "gain",
        "loss",
        "payoff",
        "performance",
        "pnl",
        "profit",
        "qualified",
        "return",
        "returns",
        "sharpe",
        "sortino",
        "verdict",
        "winrate",
        "win_rate",
    }
)


def performance_surface_offenders(field_names: Iterable[str]) -> tuple[str, ...]:
    """Field names that would give a D-E3 structure a performance / admissibility surface."""
    offenders: list[str] = []
    for name in field_names:
        lowered = name.lower()
        parts = {part for part in lowered.split("_") if part}
        if lowered in PERFORMANCE_SURFACE_TOKENS or parts & PERFORMANCE_SURFACE_TOKENS:
            offenders.append(name)
    return tuple(offenders)


def seal_performance_surface(owner: str, field_names: Iterable[str]) -> None:
    """Raise if ``field_names`` would give ``owner`` a performance / admissibility surface."""
    offenders = performance_surface_offenders(field_names)
    if offenders:
        raise BacktestIntegrityError(
            f"{owner} declares {list(offenders)} — a D-E3 backtest structure carries no Sharpe / "
            "return / edge / admissibility-verdict surface. A single-run slice backtest is "
            "disqualified by ADR-DEV-010 §8:191-192 ('it is out'), so the harness has nowhere to "
            "put such a claim: the seal is structural, not a self-reported disclaimer "
            "(design #33 §1.2 B1 / §8-9)"
        )
