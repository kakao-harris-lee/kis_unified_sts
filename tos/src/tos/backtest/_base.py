"""Backtest-local base — the reused canonical substrate + the §1.2 performance-surface seal.

The digest-binding substrate (``FrozenModel``, ``CanonicalDecimal``, ``ArtifactIntegrityError``,
``CanonicalizationScheme``, ``get_scheme``) is reused verbatim from :mod:`tos.canonical` — the
series "재정의 금지" discipline (design #33 §7.1 REUSE). This module adds only the piece D-E3
itself owns:

* :func:`performance_surface_offenders` / :data:`PERFORMANCE_SURFACE_TOKENS` — the **structural**
  seal behind design #33 §1.2 B1. The design's requirement is that a backtest result type has no
  Sharpe / return / edge / admissibility-verdict field *at all*: "성과를 주장하지 않습니다"라는
  문장(자기신고)이 아니라 성과를 담을 필드가 결과 구조에 부재하도록 설계한다. A disclaimer string
  is a self-report; an unconstructable field is a structure. Every D-E3 result / trace / fill record
  runs its own field names through this check at construction time, so smuggling a ``sharpe_ratio``
  or an ``admissibility_verdict`` in makes the model unconstructable rather than merely frowned upon.

Matching is **token-wise**, never a bare substring: field names are split on ``_`` and each part is
compared against the closed token set (plus the whole name, for the multi-word tokens). A substring
match would false-positive on legitimate names — ``acknowledged`` contains ``edge`` — and the #26
WDR MAJOR-1 lesson is that an over-rejecting guard is its own defect class.

⚠ **Provisional; closes no EV** (design #33 §1.1). Nothing here demonstrates cost realism,
population significance, or live edge.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG, no network.
"""

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


#: The closed set of field-name tokens a D-E3 result structure may **not** carry (design #33
#: §1.2 B1 / §8-9). Two families: strategy-performance surfaces (Sharpe, return, PnL, edge,
#: drawdown, win rate …) and admissibility-verdict surfaces (``admissible``, ``verdict``,
#: ``qualified``). Both are surfaces the harness deliberately has no right to produce — a single-run
#: slice backtest is disqualified by ADR-DEV-010 §8:191-192, so the honest design is to have nowhere
#: to put the claim (§12.2-1).
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
#: ⚠ ``yield`` is deliberately **absent** from the token set. It is a genuine performance word (a
#: bond yield) but it is also the generator verb, and the harness's ordering coordinate is literally
#: a *yield* sequence — banning it would over-reject a correct field, which is the #26 WDR MAJOR-1
#: defect class (a fail-closed guard swallowing a case the contract explicitly permits). The
#: performance intent is already covered by ``return`` / ``pnl`` / ``profit`` / ``gain``.



def performance_surface_offenders(field_names: Iterable[str]) -> tuple[str, ...]:
    """Field names that would give a D-E3 structure a performance / admissibility surface.

    Token-wise matching (split on ``_``, plus the whole name) rather than substring matching, so a
    legitimate ``acknowledged`` / ``remaining_quantity`` is not over-rejected while a
    ``sharpe_ratio`` / ``net_return`` / ``admissibility_verdict`` is caught (design #33 §1.2).

    Args:
        field_names: The candidate field names.

    Returns:
        The offending names, in the order supplied (empty when the surface is clean).
    """
    offenders: list[str] = []
    for name in field_names:
        lowered = name.lower()
        parts = {part for part in lowered.split("_") if part}
        if lowered in PERFORMANCE_SURFACE_TOKENS or parts & PERFORMANCE_SURFACE_TOKENS:
            offenders.append(name)
    return tuple(offenders)


def seal_performance_surface(owner: str, field_names: Iterable[str]) -> None:
    """Raise if ``field_names`` would give ``owner`` a performance / admissibility surface.

    Args:
        owner: The structure's name (recorded in the error).
        field_names: Its declared field names.

    Raises:
        BacktestIntegrityError: If any field name carries a forbidden token — the structural form
            of design #33 §1.2's "결과 타입에 성과 표면 자체를 두지 않음".
    """
    offenders = performance_surface_offenders(field_names)
    if offenders:
        raise BacktestIntegrityError(
            f"{owner} declares {list(offenders)} — a D-E3 backtest structure carries no Sharpe / "
            "return / edge / admissibility-verdict surface. A single-run slice backtest is "
            "disqualified by ADR-DEV-010 §8:191-192 ('it is out'), so the harness has nowhere to "
            "put such a claim: the seal is structural, not a self-reported disclaimer "
            "(design #33 §1.2 B1 / §8-9)"
        )
