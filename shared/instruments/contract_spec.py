"""Broker-agnostic contract-spec registry for index futures.

Pure instrument-metadata: a frozen :class:`ContractSpec` data record plus a
YAML-backed registry and symbol resolver. This carries no execution-logic
dependency (stdlib + ``pyyaml`` only), so it lives in the ``shared.instruments``
commons. The historical ``shared.execution.contract_spec`` path re-exports these
symbols for backward compatibility (see the 2026-07-20 tos boundary /
import-firewall design, §3.4 / F6 REUSE-AFTER-REFACTOR).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ContractSpec:
    """Immutable contract specification for a tradable index-futures product.

    Attributes:
        name: Registry key / product name (e.g. ``"kospi200_mini"``).
        multiplier_krw_per_point: KRW notional per index point.
        tick_size_points: Minimum price increment in index points.
        tick_value_krw: KRW value of a single tick.
        commission_rate: Fractional commission rate per notional.
        symbol_prefix: One or more comma-separated symbol prefixes that map to
            this spec (e.g. the continuous backtest code plus the live
            front-month code).
    """

    name: str
    multiplier_krw_per_point: int
    tick_size_points: float
    tick_value_krw: int
    commission_rate: float
    symbol_prefix: str


@dataclass
class ContractSpecRegistry:
    """A collection of :class:`ContractSpec` keyed by product name.

    Attributes:
        specs: Mapping of product name to its :class:`ContractSpec`.
    """

    specs: dict[str, ContractSpec] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str) -> ContractSpecRegistry:
        """Build a registry from a ``futures_contract_spec`` YAML block.

        Args:
            path: Path to a YAML file containing a top-level
                ``futures_contract_spec`` mapping.

        Returns:
            A registry populated from the file (empty if the block is absent).
        """
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        raw = data.get("futures_contract_spec", {})
        return cls(
            specs={
                name: ContractSpec(name=name, **fields) for name, fields in raw.items()
            }
        )


def resolve_contract_spec(symbol: str, registry: ContractSpecRegistry) -> ContractSpec:
    """Resolve the :class:`ContractSpec` for ``symbol`` by prefix match.

    Args:
        symbol: The instrument symbol (e.g. ``"A05603"`` or ``"101S6000"``).
        registry: The registry to search.

    Returns:
        The matching :class:`ContractSpec`.

    Raises:
        ValueError: If no registered spec matches ``symbol``.
    """
    for spec in registry.specs.values():
        # symbol_prefix may list several comma-separated prefixes — e.g. the full
        # KOSPI200 future is the continuous "101…" code (backtest) AND the live
        # "A01…" front-month. str.startswith accepts a tuple of prefixes.
        prefixes = tuple(p.strip() for p in spec.symbol_prefix.split(",") if p.strip())
        if symbol.startswith(prefixes):
            return spec
    raise ValueError(f"no contract spec for symbol={symbol}")
